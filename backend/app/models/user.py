"""User, refresh-token and email-code models (Google, email code or email + password sign-in)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import LESSON_LANGUAGE, MEDIUM, USER_ROLE, Base, TimestampMixin
from app.models.enums import LessonLanguage, Medium, UserRole

if TYPE_CHECKING:
    from app.models.curriculum import Board


class User(TimestampMixin, Base):
    """An account: student, parent or admin."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(sa.String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(sa.String(1024), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        USER_ROLE, nullable=False, default=UserRole.student, server_default=UserRole.student.value
    )
    board_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("boards.id", ondelete="SET NULL"), nullable=True, index=True
    )
    medium: Mapped[Medium | None] = mapped_column(MEDIUM, nullable=True)
    # Preferred explanation language; None = same as the textbook medium.
    lesson_language: Mapped[LessonLanguage | None] = mapped_column(LESSON_LANGUAGE, nullable=True)
    oauth_provider: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    google_sub: Mapped[str | None] = mapped_column(
        sa.String(255), unique=True, index=True, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=True, server_default=sa.true()
    )
    is_verified: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    # bcrypt hash; None = no password set (Google or email-code sign-in only).
    password_hash: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    # School / teacher partner whose code brought this student (set once).
    referred_by_partner_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("partners.id", ondelete="SET NULL", use_alter=True),
        index=True,
        nullable=True,
    )
    referred_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    board: Mapped[Board | None] = relationship()

    @property
    def has_password(self) -> bool:
        """True when the user can sign in with email + password."""
        return self.password_hash is not None

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"


class RefreshToken(TimestampMixin, Base):
    """Hashed refresh token; ``replaced_by_id`` forms the rotation chain."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(sa.String(128), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    replaced_by_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True, index=True
    )

    user: Mapped[User] = relationship()


class EmailCode(TimestampMixin, Base):
    """A one-time 6-digit sign-in code sent by email (only its keyed hash is stored)."""

    __tablename__ = "email_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(sa.String(255), index=True, nullable=False)
    code_hash: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0, server_default="0")
    used: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
