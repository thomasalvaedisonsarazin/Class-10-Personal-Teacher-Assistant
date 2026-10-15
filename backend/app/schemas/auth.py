"""Auth request/response schemas (camelCase on the wire)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

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
