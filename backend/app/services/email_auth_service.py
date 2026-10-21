"""Email sign-in: 6-digit codes and email + password (admins use Google only)."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import ForbiddenError, RateLimitedError, UnauthorizedError
from app.models.enums import UserRole
from app.models.user import EmailCode, User
from app.schemas.auth import AuthTokens
from app.services import partner_service
from app.services.auth_service import issue_tokens

logger = logging.getLogger(__name__)

# Compared against when the email has no password, so timing does not reveal accounts.
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt()).decode()
WRONG_CODE = "That code is wrong or has expired. Ask for a new one."
WRONG_PASSWORD = "Wrong email or password."  # noqa: S105 - user-facing message


def _normalize(email: str) -> str:
    return email.strip().lower()


def _code_hash(email: str, code: str) -> str:
    """Keyed hash: a leaked table cannot be brute-forced without SECRET_KEY."""
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _find_user(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email))


def _refuse_admin(user: User | None) -> None:
    if user is not None and user.role == UserRole.admin:
        raise ForbiddenError("Admins sign in with Google.", code="admin_google_only")


def create_sign_in_code(db: Session, email: str, now: datetime | None = None) -> str:
    """Create a new one-time code for ``email`` (older unused codes stop working).

    Args:
        db: Database session
        email: Address the code will be sent to
        now: Current time (tests)

    Returns:
        The plain 6-digit code, to be emailed (only its hash is stored)

    Raises:
        RateLimitedError: Too many codes asked for this email in the last hour
    """
    email = _normalize(email)
    now = now or datetime.now(UTC)
    recent = db.scalar(
        select(func.count(EmailCode.id)).where(
            EmailCode.email == email, EmailCode.created_at >= now - timedelta(hours=1)
        )
    )
    if (recent or 0) >= settings.EMAIL_CODES_PER_HOUR:
        raise RateLimitedError("Too many codes asked for. Please try again in an hour.")
    db.execute(
        update(EmailCode)
        .where(EmailCode.email == email, EmailCode.used.is_(False))
        .values(used=True)
    )
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        EmailCode(
            email=email,
            code_hash=_code_hash(email, code),
            expires_at=now + timedelta(minutes=settings.EMAIL_CODE_TTL_MINUTES),
            created_at=now,
        )
    )
    db.commit()
    return code


def _consume_code(db: Session, email: str, code: str, now: datetime | None = None) -> None:
    """Accept the latest live code for ``email`` once; wrong guesses count against it."""
    now = now or datetime.now(UTC)
    row = db.scalar(
        select(EmailCode)
        .where(EmailCode.email == email, EmailCode.used.is_(False))
        .order_by(EmailCode.id.desc())
        .limit(1)
    )
    if row is None or _aware(row.expires_at) < now:
        raise UnauthorizedError(WRONG_CODE, code="invalid_code")
    if row.attempts >= settings.EMAIL_CODE_MAX_ATTEMPTS:
        row.used = True
        db.commit()
        raise UnauthorizedError(WRONG_CODE, code="invalid_code")
    if not hmac.compare_digest(row.code_hash, _code_hash(email, code)):
        row.attempts += 1
        db.commit()
        raise UnauthorizedError(WRONG_CODE, code="invalid_code")
    row.used = True
    db.flush()


def _get_or_create(db: Session, email: str, full_name: str | None = None) -> User:
    user = _find_user(db, email)
    if user is None:
        user = User(email=email, full_name=full_name, role=UserRole.student, is_active=True)
        db.add(user)
        try:
            db.flush()
            partner_service.claim_partner_role(db, user)
        except IntegrityError:
            db.rollback()
            user = _find_user(db, email)
            if user is None:  # pragma: no cover - the other insert must exist
                raise
    user.is_verified = True
    if full_name and not user.full_name:
        user.full_name = full_name
    if user.oauth_provider is None:
        user.oauth_provider = "email"
    return user


def login_with_code(db: Session, email: str, code: str) -> AuthTokens:
    """Sign in with an emailed code; a new email gets a new student account.

    Args:
        db: Database session
        email: The address the code was sent to
        code: The 6-digit code

    Returns:
        Tokens plus the user's profile
    """
    email = _normalize(email)
    _refuse_admin(_find_user(db, email))
    _consume_code(db, email, code)
    user = _get_or_create(db, email)
    logger.info("Email-code sign-in user_id=%s", user.id)
    return issue_tokens(db, user)


def set_password_with_code(
    db: Session, email: str, code: str, password: str, full_name: str | None = None
) -> AuthTokens:
    """Create an account with a password, or reset a forgotten password, using an emailed code.

    Args:
        db: Database session
        email: The address the code was sent to (proves the student owns it)
        code: The 6-digit code
        password: New password (already validated by the schema)
        full_name: Optional name for a new account

    Returns:
        Tokens plus the user's profile (other sessions stay signed in)
    """
    email = _normalize(email)
    _refuse_admin(_find_user(db, email))
    _consume_code(db, email, code)
    user = _get_or_create(db, email, full_name)
    user.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    logger.info("Password set user_id=%s", user.id)
    return issue_tokens(db, user)


def login_with_password(db: Session, email: str, password: str) -> AuthTokens:
    """Sign in with email + password (same error for unknown email and wrong password).

    Args:
        db: Database session
        email: Account email
        password: Password

    Returns:
        Tokens plus the user's profile
    """
    user = _find_user(db, _normalize(email))
    stored = user.password_hash if user is not None and user.password_hash else _DUMMY_HASH
    matches = bcrypt.checkpw(password.encode(), stored.encode())
    if user is None or user.password_hash is None or not matches:
        raise UnauthorizedError(WRONG_PASSWORD, code="invalid_credentials")
    _refuse_admin(user)
    logger.info("Password sign-in user_id=%s", user.id)
    return issue_tokens(db, user)
