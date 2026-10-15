"""Lessons (uploaded or AI-generated), views, clarity feedback and generation jobs."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    JOB_KIND,
    JOB_STATUS,
    LESSON_SOURCE,
    LESSON_STATUS,
    LESSON_STYLE,
    MEDIUM,
    Base,
    JSONType,
    TimestampMixin,
)
from app.models.enums import JobKind, JobStatus, LessonSource, LessonStatus, LessonStyle, Medium

if TYPE_CHECKING:
    from app.models.curriculum import Topic
    from app.models.user import User


class Lesson(TimestampMixin, Base):
    """A lesson for (topic, medium, style). Media is stored as object-storage keys."""

    __tablename__ = "lessons"
    __table_args__ = (
        sa.Index("ix_lessons_topic_medium_style_status", "topic_id", "medium", "style", "status"),
        sa.CheckConstraint(
            "duration_sec IS NULL OR duration_sec >= 0", name="duration_sec_non_negative"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    medium: Mapped[Medium] = mapped_column(MEDIUM, nullable=False)
    style: Mapped[LessonStyle] = mapped_column(LESSON_STYLE, nullable=False)
    source: Mapped[LessonSource] = mapped_column(LESSON_SOURCE, nullable=False)
    title: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    script_text: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    slides_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSONType, nullable=True
    )
    audio_key: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    video_key: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    status: Mapped[LessonStatus] = mapped_column(
        LESSON_STATUS,
        nullable=False,
        default=LessonStatus.pending,
        server_default=LessonStatus.pending.value,
    )
    is_flagged: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )

    topic: Mapped[Topic] = relationship()


class LessonView(TimestampMixin, Base):
    """A student's watch progress on a lesson (``updated_at`` = last viewed)."""

    __tablename__ = "lesson_views"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "lesson_id"),
        sa.CheckConstraint("watched_sec >= 0", name="watched_sec_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    lesson_id: Mapped[int] = mapped_column(
        sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    watched_sec: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )
    completed: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )

    lesson: Mapped[Lesson] = relationship()


class ClarityFeedback(TimestampMixin, Base):
    """A "Clear" / "Not clear" signal from a student on a topic (optionally a lesson)."""

    __tablename__ = "clarity_feedback"
    __table_args__ = (sa.Index("ix_clarity_feedback_user_topic", "user_id", "topic_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    topic_id: Mapped[int] = mapped_column(
        sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_clear: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)


class GenerationJob(TimestampMixin, Base):
    """A background AI job (explanation lesson or question batch).

    ``user_id`` is nullable so system-triggered jobs (e.g. question pre-warm)
    and jobs of deleted users are kept for stats.
    """

    __tablename__ = "generation_jobs"
    __table_args__ = (
        sa.Index("ix_generation_jobs_user_created", "user_id", "created_at"),
        sa.Index("ix_generation_jobs_topic_kind_status", "topic_id", "kind", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    topic_id: Mapped[int] = mapped_column(
        sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    medium: Mapped[Medium] = mapped_column(MEDIUM, nullable=False)
    requested_style: Mapped[LessonStyle | None] = mapped_column(LESSON_STYLE, nullable=True)
    kind: Mapped[JobKind] = mapped_column(JOB_KIND, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        JOB_STATUS, nullable=False, default=JobStatus.queued, server_default=JobStatus.queued.value
    )
    error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    lesson_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    user: Mapped[User | None] = relationship()
    lesson: Mapped[Lesson | None] = relationship()
