"""Sign-in, refresh-token rotation and profile updates."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    refresh_token_expiry,
    sha256_hex,
)
from app.config import settings
from app.exceptions import BadRequestError, ConflictError, ForbiddenError, UnauthorizedError
from app.models.curriculum import Board
from app.models.enums import UserRole
from app.models.progress import TopicProgress
from app.models.quiz import QuizAttempt
from app.models.user import RefreshToken, User
from app.schemas.auth import AuthTokens, UpdateMeRequest, UserOut
from app.services import partner_service
from app.services.google_auth import GoogleIdentity

logger = logging.getLogger(__name__)


def _aware(value: datetime) -> datetime:
    """Treat naive datetimes (SQLite) as UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _ensure_active(user: User) -> None:
    if not user.is_active:
        raise ForbiddenError("This account has been disabled", code="account_disabled")


def _new_refresh_token(db: Session, user: User) -> tuple[str, RefreshToken]:
    raw, token_hash = create_refresh_token()
    row = RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=refresh_token_expiry())
    db.add(row)
    db.flush()
    return raw, row


def _tokens(user: User, raw_refresh: str) -> AuthTokens:
    return AuthTokens(
        access_token=create_access_token(user.id, UserRole(user.role).value),
        refresh_token=raw_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )


def issue_tokens(db: Session, user: User) -> AuthTokens:
    """Create a fresh access + refresh token pair for ``user`` and commit.

    Args:
        db: Database session
        user: Active user signing in

    Returns:
        Tokens plus the user's profile
    """
    _ensure_active(user)
    raw, _ = _new_refresh_token(db, user)
    db.commit()
    db.refresh(user)
    return _tokens(user, raw)


def _find_google_user(db: Session, identity: GoogleIdentity) -> User | None:
    user = db.scalar(select(User).where(User.google_sub == identity.sub))
    if user is not None:
        return user
    user = db.scalar(select(User).where(func.lower(User.email) == identity.email))
    if user is not None and user.google_sub and user.google_sub != identity.sub:
        raise UnauthorizedError("This email is linked to another Google account")
    return user


def get_or_create_google_user(db: Session, identity: GoogleIdentity) -> User:
    """Find the user for a verified Google identity, linking by email or creating one.

    New users are students, unless their email is listed in ``ADMIN_EMAILS``.

    Args:
        db: Database session
        identity: Verified Google claims

    Returns:
        The persisted (committed) user
    """
    is_admin_email = identity.email in settings.ADMIN_EMAILS
    for attempt in range(2):
        user = _find_google_user(db, identity)
        if user is None:
            user = User(
                email=identity.email,
                full_name=identity.name,
                role=UserRole.admin if is_admin_email else UserRole.student,
                is_active=True,
            )
            db.add(user)
            partner_service.claim_partner_role(db, user)
        user.google_sub = identity.sub
        user.oauth_provider = "google"
        user.is_verified = True
        if identity.picture:
            user.avatar_url = identity.picture
        if not user.full_name and identity.name:
            user.full_name = identity.name
        if is_admin_email and user.role != UserRole.admin:
            user.role = UserRole.admin
        try:
            db.commit()
        except IntegrityError:
            # Two first sign-ins raced; the other one created the row — load it.
            db.rollback()
            if attempt == 1:
                raise
            continue
        db.refresh(user)
        return user
    raise RuntimeError("unreachable")  # pragma: no cover


def login_with_google(db: Session, identity: GoogleIdentity) -> AuthTokens:
    """Sign in (or sign up) with a verified Google identity."""
    user = get_or_create_google_user(db, identity)
    _ensure_active(user)
    logger.info("Google sign-in user_id=%s", user.id)
    return issue_tokens(db, user)


def dev_login(db: Session, email: str) -> AuthTokens:
    """Sign in as an existing user by email (development only — the router guards this)."""
    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None:
        raise UnauthorizedError("No such user. Run the seed script first.", code="unknown_user")
    return issue_tokens(db, user)


def _revoke_chain(db: Session, token: RefreshToken) -> None:
    """Revoke ``token`` and every token that replaced it (reuse detected)."""
    seen: set[int] = set()
    current: RefreshToken | None = token
    while current is not None and current.id not in seen:
        seen.add(current.id)
        current.revoked = True
        current = db.get(RefreshToken, current.replaced_by_id) if current.replaced_by_id else None


def rotate_refresh_token(db: Session, raw_token: str) -> AuthTokens:
    """Exchange a refresh token for a new pair; the old token is revoked.

    Presenting an already-rotated (revoked) token is treated as theft: the whole
    rotation chain is revoked and the request is rejected.

    Raises:
        UnauthorizedError: unknown, expired, revoked or reused token, or inactive user.
    """
    row = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == sha256_hex(raw_token))
        .with_for_update()
    )
    if row is None:
        raise UnauthorizedError("Invalid refresh token", code="invalid_refresh_token")
    if row.revoked:
        logger.warning("Refresh token reuse detected user_id=%s", row.user_id)
        _revoke_chain(db, row)
        db.commit()
        raise UnauthorizedError("Session expired, please sign in again", code="token_reused")
    if _aware(row.expires_at) <= datetime.now(UTC):
        raise UnauthorizedError("Session expired, please sign in again", code="token_expired")

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive", code="invalid_user")

    raw, new_row = _new_refresh_token(db, user)
    row.revoked = True
    row.replaced_by_id = new_row.id
    db.commit()
    db.refresh(user)
    return _tokens(user, raw)


def revoke_refresh_token(db: Session, raw_token: str) -> None:
    """Revoke a refresh token (logout). Unknown tokens are ignored."""
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(raw_token)))
    if row is not None and not row.revoked:
        row.revoked = True
        db.commit()


def _change_setup_role(db: Session, user: User, role: UserRole) -> None:
    """Switch between student and parent while the account is still being set up."""
    if user.role == UserRole.admin:
        raise ForbiddenError("Admins cannot change their own role", code="self_update")
    started = db.scalar(
        select(func.count(TopicProgress.id)).where(TopicProgress.user_id == user.id)
    ) or db.scalar(select(func.count(QuizAttempt.id)).where(QuizAttempt.user_id == user.id))
    if started:
        raise ConflictError(
            "This account already has study progress, so it stays a student account. "
            "Please sign in with a different Google account as a parent.",
            code="role_locked",
        )
    user.role = role
    if role == UserRole.parent:
        user.board_id = None  # parents follow their children's boards


def update_profile(db: Session, user: User, data: UpdateMeRequest) -> User:
    """Apply profile changes (name, board, medium, lesson language, setup role) for ``user``.

    Raises:
        BadRequestError: the board does not exist or is not active.
        ConflictError: role change after the account has started studying.
        ForbiddenError: admins cannot change their own role here.
    """
    if data.role is not None and data.role != user.role:
        _change_setup_role(db, user, UserRole(data.role))
    if data.board_id is not None:
        board = db.get(Board, data.board_id)
        if board is None or not board.is_active:
            raise BadRequestError("This board is not available", code="invalid_board")
        user.board_id = board.id
    if data.medium is not None:
        user.medium = data.medium
    if data.lesson_language is not None:
        user.lesson_language = data.lesson_language
    if data.full_name is not None:
        user.full_name = data.full_name
    db.commit()
    db.refresh(user)
    return user
