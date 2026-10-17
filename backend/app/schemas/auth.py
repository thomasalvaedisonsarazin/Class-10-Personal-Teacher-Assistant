"""Auth request/response schemas (camelCase on the wire)."""

from __future__ import annotations

from typing import Literal

from pydantic import EmailStr, Field, field_validator

from app.models.enums import LessonLanguage, Medium, UserRole
from app.schemas.common import CamelModel, ORMModel


class UserOut(ORMModel):
    """The signed-in user's profile."""

    id: int
    email: str
    full_name: str | None
    avatar_url: str | None
    role: UserRole
    board_id: int | None
    medium: Medium | None
    lesson_language: LessonLanguage | None
    has_password: bool = False


class AuthTokens(CamelModel):
    """Tokens issued on sign-in and refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth token type, not a secret
    expires_in: int = Field(description="Access-token lifetime in seconds")
    user: UserOut


class GoogleLoginRequest(CamelModel):
    """Google ID token obtained by the client from Google Sign-In."""

    id_token: str = Field(min_length=20, max_length=4096)


class DevLoginRequest(CamelModel):
    """Development-only sign-in as an existing (e.g. seeded) user."""

    # Plain pattern, not EmailStr: seeded users use the reserved ``.local`` domain.
    email: str = Field(default="student@dev.local", max_length=255, pattern=r"^[^@\s]+@[^@\s]+$")


class EmailCodeRequest(CamelModel):
    """Ask for a 6-digit sign-in code by email."""

    email: EmailStr = Field(max_length=255)


class EmailCodeSent(CamelModel):
    """Always the same answer, so it never reveals whether an account exists."""

    sent: bool = True
    expires_in_minutes: int


class EmailCodeLogin(CamelModel):
    """Sign in (or sign up) with an emailed code."""

    email: EmailStr = Field(max_length=255)
    code: str = Field(pattern=r"^\d{6}$")


def _check_password(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password is too long")
    if value.strip() != value or len(set(value)) < 4:
        raise ValueError("Choose a stronger password")
    return value


class PasswordSetRequest(EmailCodeLogin):
    """Create an account with a password, or reset a forgotten one (proved by an emailed code)."""

    password: str = Field(min_length=8, max_length=72)
    full_name: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def _password_rules(cls, value: str) -> str:
        """At most 72 bytes (bcrypt limit), no leading/trailing spaces, not trivially repetitive."""
        return _check_password(value)


class PasswordLoginRequest(CamelModel):
    """Sign in with email and password."""

    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=1, max_length=72)


class RefreshRequest(CamelModel):
    """Refresh-token rotation / logout body."""

    refresh_token: str = Field(min_length=20, max_length=512)


class UpdateMeRequest(CamelModel):
    """Profile fields a user can change (all optional)."""

    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    board_id: int | None = Field(default=None, gt=0)
    medium: Medium | None = None
    lesson_language: LessonLanguage | None = None
    # Chosen once during setup: "I'm a student" / "I'm a parent" (admins are never self-made).
    role: Literal["student", "parent"] | None = None

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        """Trim whitespace; reject names that are only spaces."""
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty")
        return value
