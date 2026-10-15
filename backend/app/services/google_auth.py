"""Server-side verification of Google Sign-In ID tokens."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.config import settings
from app.exceptions import AppError, UnauthorizedError

logger = logging.getLogger(__name__)

GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


@dataclass(frozen=True)
class GoogleIdentity:
    """Verified claims from a Google ID token."""

    sub: str
    email: str
    name: str | None
    picture: str | None


GoogleVerifier = Callable[[str], GoogleIdentity]


class GoogleNotConfiguredError(AppError):
    """503: no Google OAuth client IDs are configured on the server."""

    status_code = 503
    code = "google_not_configured"
    message = "Google Sign-In is not configured on the server yet"


def verify_google_id_token(token: str) -> GoogleIdentity:
    """Verify signature, expiry, issuer and audience of a Google ID token.

    The audience must be one of the configured OAuth client IDs
    (``GOOGLE_CLIENT_ID`` / ``GOOGLE_ANDROID_CLIENT_ID``) and the email must be verified.

    Raises:
        GoogleNotConfiguredError: no client IDs configured.
        UnauthorizedError: the token is invalid, expired, for another app or unverified.
    """
    audiences = settings.google_client_ids
    if not audiences:
        raise GoogleNotConfiguredError()

    from google.auth.exceptions import GoogleAuthError
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    try:
        claims = id_token.verify_oauth2_token(
            token, google_requests.Request(), audience=audiences, clock_skew_in_seconds=10
        )
    except (ValueError, GoogleAuthError) as exc:
        logger.info("Rejected Google ID token: %s", exc)
        raise UnauthorizedError("Google sign-in failed", code="invalid_google_token") from exc

    email = claims.get("email")
    if claims.get("iss") not in GOOGLE_ISSUERS or not claims.get("sub"):
        raise UnauthorizedError("Google sign-in failed", code="invalid_google_token")
    if not email or not claims.get("email_verified"):
        raise UnauthorizedError("Your Google email is not verified", code="email_not_verified")

    return GoogleIdentity(
        sub=str(claims["sub"]),
        email=str(email).lower(),
        name=claims.get("name"),
        picture=claims.get("picture"),
    )


def get_google_verifier() -> GoogleVerifier:
    """FastAPI dependency returning the verifier (overridden in tests)."""
    return verify_google_id_token
