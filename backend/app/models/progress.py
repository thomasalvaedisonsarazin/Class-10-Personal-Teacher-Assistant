"""Topic progress (one active topic per student) and study streaks."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TOPIC_STATUS, Base, TimestampMixin
from app.models.enums import TopicStatus

if TYPE_CHECKING:
    from app.models.curriculum import Topic


class TopicProgress(TimestampMixin, Base):
    """Stored progress for (user, topic). "available"/"locked" are derived in services."""

    __tablename__ = "topic_progress"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "topic_id"),
        sa.CheckConstraint("attempts_count >= 0", name="attempts_count_non_negative"),
        sa.CheckConstraint(
            "best_score_pct IS NULL OR (best_score_pct >= 0 AND best_score_pct <= 100)",
            name="best_score_pct_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    topic_id: Mapped[int] = mapped_column(
        sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[TopicStatus] = mapped_column(
        TOPIC_STATUS,
        nullable=False,
        default=TopicStatus.active,
        server_default=TopicStatus.active.value,
    )
    best_score_pct: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    attempts_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )
    started_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    topic: Mapped[Topic] = relationship()


# DB-level guarantee: at most one active topic per user.
sa.Index(
    "uq_topic_progress_one_active",
    TopicProgress.user_id,
    unique=True,
    postgresql_where=sa.text("status = 'active'"),
    sqlite_where=sa.text("status = 'active'"),
)


class StudyStreak(TimestampMixin, Base):
    """Daily study streak counters for a user."""

    __tablename__ = "study_streaks"
    __table_args__ = (
        sa.CheckConstraint("current_streak_days >= 0", name="current_streak_non_negative"),
        sa.CheckConstraint("longest_streak_days >= 0", name="longest_streak_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    current_streak_days: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )
    longest_streak_days: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )
    last_study_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
