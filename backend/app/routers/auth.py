"""Authentication endpoints: Google, email code, email + password, dev login, refresh, profile."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status

from app.config import settings
from app.dependencies import CurrentUser, DbSession
from app.exceptions import NotFoundError
from app.rate_limit import limiter
from app.schemas.auth import (
    AuthTokens,
    DevLoginRequest,
    EmailCodeLogin,
    EmailCodeRequest,
    EmailCodeSent,
    GoogleLoginRequest,
    PasswordLoginRequest,
    PasswordSetRequest,
    RefreshRequest,
    UpdateMeRequest,
    UserOut,
)
from app.services import auth_service, email_auth_service, email_service
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


@router.post("/email/code", response_model=EmailCodeSent, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
def request_email_code(
    request: Request, body: EmailCodeRequest, db: DbSession, background: BackgroundTasks
) -> EmailCodeSent:
    """Email a 6-digit code (sign in, sign up or reset password). Same reply for every email."""
    code = email_auth_service.create_sign_in_code(db, str(body.email))
    background.add_task(email_service.send_sign_in_code, str(body.email).lower(), code)
    return EmailCodeSent(expires_in_minutes=settings.EMAIL_CODE_TTL_MINUTES)


@router.post("/email/login", response_model=AuthTokens)
@limiter.limit("10/minute")
def email_code_login(request: Request, body: EmailCodeLogin, db: DbSession) -> AuthTokens:
    """Sign in with an emailed code (creates a student account for a new email)."""
    return email_auth_service.login_with_code(db, str(body.email), body.code)


@router.post("/password/set", response_model=AuthTokens)
@limiter.limit("10/minute")
def set_password(request: Request, body: PasswordSetRequest, db: DbSession) -> AuthTokens:
    """Create an account with a password, or reset a forgotten one, using an emailed code."""
    return email_auth_service.set_password_with_code(
        db, str(body.email), body.code, body.password, body.full_name
    )


@router.post("/password/login", response_model=AuthTokens)
@limiter.limit("10/minute")
def password_login(request: Request, body: PasswordLoginRequest, db: DbSession) -> AuthTokens:
    """Sign in with email and password."""
    return email_auth_service.login_with_password(db, str(body.email), body.password)


@router.post("/dev-login", response_model=AuthTokens)
@limiter.limit("30/minute")
def dev_login(request: Request, body: DevLoginRequest, db: DbSession) -> AuthTokens:
    """Sign in as a seeded user without Google (only with DEV_LOGIN_ENABLED; never production)."""
    if not settings.dev_login_allowed:
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
