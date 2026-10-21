"""JWT access tokens and opaque refresh tokens."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pydantic import BaseModel

from app.config import settings
from app.exceptions import UnauthorizedError


class TokenPayload(BaseModel):
    """Decoded access-token claims."""

    sub: int
    role: str
    exp: int
    iat: int
    jti: str
    type: str = "access"
    sid: str | None = None  # sign-in session (one device); absent on older tokens


def sha256_hex(value: str) -> str:
    """Return the hex SHA-256 digest of ``value`` (used to store refresh tokens)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_access_token(user_id: int, role: str, session_id: str | None = None) -> str:
    """Create a signed short-lived access token for ``user_id`` with ``role``."""
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "role": str(getattr(role, "value", role)),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    if session_id:
        claims["sid"] = session_id
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token() -> tuple[str, str]:
    """Create an opaque refresh token.

    Returns:
        ``(raw_token, sha256_hash)`` — give the raw token to the client and store
        only the hash.
    """
    raw = secrets.token_urlsafe(48)
    return raw, sha256_hex(raw)


def refresh_token_expiry() -> datetime:
    """Absolute expiry timestamp for a refresh token issued now."""
    return datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)


def decode_access_token(token: str) -> TokenPayload:
    """Validate and decode an access token.

    Raises:
        UnauthorizedError: if the token is malformed, expired, has a bad signature
            or is not an access token.
    """
    try:
        data = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
        payload = TokenPayload.model_validate(data)
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token expired", code="token_expired") from exc
    except (jwt.PyJWTError, ValueError) as exc:
        raise UnauthorizedError("Invalid token", code="invalid_token") from exc
    if payload.type != "access":
        raise UnauthorizedError("Invalid token type", code="invalid_token")
    return payload
