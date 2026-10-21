"""Shared FastAPI dependencies: DB session, current user, role guards."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt import TokenPayload, decode_access_token
from app.config import settings
from app.database import get_db
from app.exceptions import ConflictError, ForbiddenError, UnauthorizedError
from app.models.enums import UserRole
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


SESSION_TOUCH_SECONDS = 30  # write "last seen" at most this often


def get_token_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> tuple[User, TokenPayload]:
    """The authenticated user and token claims, without the one-device check.

    Raises:
        UnauthorizedError: missing/invalid token, unknown or inactive user.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError()
    payload = decode_access_token(credentials.credentials)
    user = db.get(User, payload.sub)
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive", code="invalid_user")
    return user, payload


def claim_session(db: Session, user: User, session_id: str | None) -> None:
    """Let a student use one device at a time.

    The device whose session was seen within ``SESSION_IDLE_SECONDS`` keeps the account;
    any other device gets 409 ``session_active`` until that one closes the app (or signs
    out). Tokens issued before sessions existed carry no session and are not checked.
    """
    if user.role != UserRole.student or session_id is None:
        return
    now = datetime.now(UTC)
    seen = user.active_session_seen_at
    if seen is not None and seen.tzinfo is None:
        seen = seen.replace(tzinfo=UTC)  # SQLite
    in_use = seen is not None and now - seen < timedelta(seconds=settings.SESSION_IDLE_SECONDS)
    if user.active_session_id not in (None, session_id) and in_use:
        raise ConflictError(
            "An active session is open on another device. Please close the app there and "
            "open it here.",
            code="session_active",
        )
    stale = seen is None or now - seen >= timedelta(seconds=SESSION_TOUCH_SECONDS)
    if user.active_session_id != session_id or stale:
        user.active_session_id = session_id
        user.active_session_seen_at = now
        db.commit()


def get_current_user(
    db: DbSession, token_user: Annotated[tuple[User, TokenPayload], Depends(get_token_user)]
) -> User:
    """Resolve the authenticated user from the ``Authorization: Bearer`` header.

    Raises:
        UnauthorizedError: missing/invalid token, unknown or inactive user.
        ConflictError: the student's account is in use on another device (``session_active``).
    """
    user, payload = token_user
    claim_session(db, user, payload.sid)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
TokenUser = Annotated[tuple[User, TokenPayload], Depends(get_token_user)]


def require_role(*roles: UserRole) -> Callable[[User], User]:
    """Dependency factory that only admits users having one of ``roles``.

    Usage: ``user: Annotated[User, Depends(require_role(UserRole.admin))]``.
    """
    allowed = {UserRole(r) for r in roles}

    def _checker(user: CurrentUser) -> User:
        if UserRole(user.role) not in allowed:
            raise ForbiddenError()
        return user

    return _checker


AdminUser = Annotated[User, Depends(require_role(UserRole.admin))]
StudentUser = Annotated[User, Depends(require_role(UserRole.student))]
ParentUser = Annotated[User, Depends(require_role(UserRole.parent))]
PartnerUser = Annotated[User, Depends(require_role(UserRole.partner))]
