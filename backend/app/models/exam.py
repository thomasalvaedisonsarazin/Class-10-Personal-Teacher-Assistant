"""Exam practice: full-subject tests and board-pattern model question papers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MEDIUM, Base, JSONType, TimestampMixin
from app.models.enums import Medium
from app.models.quiz import Question


class SubjectTest(TimestampMixin, Base):
    """An in-app test mixing questions from every topic the student completed in a subject.

    Kept apart from ``quiz_attempts``: it never completes or unlocks a topic.
    """

    __tablename__ = "subject_tests"
    __table_args__ = (
        sa.Index("ix_subject_tests_user_subject", "user_id", "subject_id"),
        sa.CheckConstraint(
            "score_pct IS NULL OR (score_pct >= 0 AND score_pct <= 100)",
            name="subject_test_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    score_pct: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    correct_count: Mapped[int | None] = mapped_column(sa.SmallInteger, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    questions: Mapped[list[SubjectTestQuestion]] = relationship(
        back_populates="test",
        order_by="SubjectTestQuestion.position",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SubjectTestQuestion(TimestampMixin, Base):
    """A question served within a subject test (and the student's answer)."""

    __tablename__ = "subject_test_questions"
    __table_args__ = (
        sa.UniqueConstraint("test_id", "question_id"),
        sa.UniqueConstraint("test_id", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(
        sa.ForeignKey("subject_tests.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    served_options: Mapped[list[Any] | None] = mapped_column(JSONType, nullable=True)
    selected_answer: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)

    test: Mapped[SubjectTest] = relationship(back_populates="questions")
    question: Mapped[Question] = relationship(lazy="selectin")


class ModelPaper(TimestampMixin, Base):
    """A board-pattern question paper written on paper, then marked from photos.

    Status: ``generating`` → ``ready`` (download and write) → ``grading`` (photos uploaded;
    answer key now visible) → ``graded``. ``generation_failed`` / ``grading_failed`` on errors
    (a failed grading can be retried with new photos).
    """

    __tablename__ = "model_papers"
    __table_args__ = (sa.Index("ix_model_papers_user_subject", "user_id", "subject_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[str] = mapped_column(sa.String(16), nullable=False)  # full | chapters
    chapter_ids: Mapped[list[Any]] = mapped_column(JSONType, nullable=False, default=list)
    medium: Mapped[Medium] = mapped_column(MEDIUM, nullable=False)
    pattern_id: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="generating")
    total_marks: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    # Questions as shown on the paper (no answers) and the answer key, kept apart.
    paper: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    answer_key: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    image_keys: Mapped[list[Any]] = mapped_column(JSONType, nullable=False, default=list)
    results: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    score: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    graded_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
