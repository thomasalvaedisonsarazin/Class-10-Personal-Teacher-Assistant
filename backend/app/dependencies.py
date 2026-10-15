"""Shared FastAPI dependencies: DB session, current user, role guards."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.database import get_db
from app.exceptions import ForbiddenError, UnauthorizedError
from app.models.enums import UserRole
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Resolve the authenticated user from the ``Authorization: Bearer`` header.

    Raises:
        UnauthorizedError: missing/invalid token, unknown or inactive user.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError()
    payload = decode_access_token(credentials.credentials)
    user = db.get(User, payload.sub)
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive", code="invalid_user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


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
