"""Authentication endpoints: Google Sign-In, dev login, refresh, logout, profile."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.config import settings
from app.dependencies import CurrentUser, DbSession
from app.exceptions import NotFoundError
from app.rate_limit import limiter
from app.schemas.auth import (
    AuthTokens,
    DevLoginRequest,
    GoogleLoginRequest,
    RefreshRequest,
    UpdateMeRequest,
    UserOut,
)
from app.services import auth_service
from app.services.google_auth import GoogleVerifier, get_google_verifier

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/google", response_model=AuthTokens)
@limiter.limit("10/minute")
def google_login(
    request: Request,
    body: GoogleLoginRequest,
    db: DbSession,
    verify: Annotated[GoogleVerifier, Depends(get_google_verifier)],
) -> AuthTokens:
    """Verify a Google ID token and return our tokens (creates the account if new)."""
    identity = verify(body.id_token)
    return auth_service.login_with_google(db, identity)


@router.post("/dev-login", response_model=AuthTokens)
@limiter.limit("30/minute")
def dev_login(request: Request, body: DevLoginRequest, db: DbSession) -> AuthTokens:
    """Sign in as a seeded user without Google. Returns 404 in production."""
    if settings.is_production:
        raise NotFoundError()
    return auth_service.dev_login(db, str(body.email))


@router.post("/refresh", response_model=AuthTokens)
@limiter.limit("30/minute")
def refresh(request: Request, body: RefreshRequest, db: DbSession) -> AuthTokens:
    """Rotate a refresh token and return a new token pair."""
    return auth_service.rotate_refresh_token(db, body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshRequest, db: DbSession) -> Response:
    """Revoke the given refresh token (always succeeds)."""
    auth_service.revoke_refresh_token(db, body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
def get_me(user: CurrentUser) -> UserOut:
    """Return the current user's profile."""
    return UserOut.model_validate(user)


@router.put("/me", response_model=UserOut)
def update_me(body: UpdateMeRequest, user: CurrentUser, db: DbSession) -> UserOut:
    """Update name, board and/or medium (used by onboarding and profile)."""
    return UserOut.model_validate(auth_service.update_profile(db, user, body))
