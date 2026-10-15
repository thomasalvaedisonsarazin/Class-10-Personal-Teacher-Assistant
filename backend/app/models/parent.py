"""Parent <-> student links (Phase 2B)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import PARENT_LINK_STATUS, Base, TimestampMixin
from app.models.enums import ParentLinkStatus


class ParentLink(TimestampMixin, Base):
    """Student-generated invite code; ``parent_user_id`` is set when a parent redeems it."""

    __tablename__ = "parent_links"
    __table_args__ = (
        sa.UniqueConstraint("parent_user_id", "student_user_id"),
        sa.CheckConstraint(
            "parent_user_id IS NULL OR parent_user_id <> student_user_id",
            name="parent_not_student",
        ),
        sa.CheckConstraint("length(invite_code) = 8", name="invite_code_length"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_user_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    student_user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invite_code: Mapped[str] = mapped_column(
        sa.String(8), unique=True, index=True, nullable=False
    )
    invite_expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    status: Mapped[ParentLinkStatus] = mapped_column(
        PARENT_LINK_STATUS,
        nullable=False,
        default=ParentLinkStatus.pending,
        server_default=ParentLinkStatus.pending.value,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
