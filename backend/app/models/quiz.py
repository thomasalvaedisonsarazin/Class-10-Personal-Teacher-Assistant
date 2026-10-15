"""Quiz questions, attempts and served questions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    MEDIUM,
    QUESTION_SOURCE,
    QUESTION_TYPE,
    Base,
    JSONType,
    TimestampMixin,
)
from app.models.enums import Medium, QuestionSource, QuestionType


class Question(TimestampMixin, Base):
    """A quiz question for (topic, medium). ``content_hash`` dedupes per topic+medium."""

    __tablename__ = "questions"
    __table_args__ = (
        sa.UniqueConstraint("topic_id", "medium", "content_hash"),
        sa.Index("ix_questions_topic_medium_approved", "topic_id", "medium", "is_approved"),
        sa.CheckConstraint("difficulty BETWEEN 1 AND 3", name="difficulty_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    medium: Mapped[Medium] = mapped_column(MEDIUM, nullable=False)
    type: Mapped[QuestionType] = mapped_column(QUESTION_TYPE, nullable=False)
    stem: Mapped[str] = mapped_column(sa.Text, nullable=False)
    options: Mapped[list[Any] | None] = mapped_column(JSONType, nullable=True)
    correct_answer: Mapped[str] = mapped_column(sa.Text, nullable=False)
    explanation: Mapped[str] = mapped_column(sa.Text, nullable=False)
    difficulty: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, default=2, server_default="2"
    )
    source: Mapped[QuestionSource] = mapped_column(QUESTION_SOURCE, nullable=False)
    is_approved: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    is_flagged: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    content_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)


class QuizAttempt(TimestampMixin, Base):
    """One quiz attempt by a student on a topic."""

    __tablename__ = "quiz_attempts"
    __table_args__ = (
        sa.Index("ix_quiz_attempts_user_topic", "user_id", "topic_id"),
        sa.CheckConstraint(
            "score_pct IS NULL OR (score_pct >= 0 AND score_pct <= 100)", name="score_pct_range"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    topic_id: Mapped[int] = mapped_column(
        sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score_pct: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    passed: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    started_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    questions: Mapped[list[QuizAttemptQuestion]] = relationship(
        back_populates="attempt",
        order_by="QuizAttemptQuestion.position",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class QuizAttemptQuestion(TimestampMixin, Base):
    """A question served within an attempt (and the student's answer)."""

    __tablename__ = "quiz_attempt_questions"
    __table_args__ = (
        sa.UniqueConstraint("attempt_id", "question_id"),
        sa.UniqueConstraint("attempt_id", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        sa.ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    served_options: Mapped[list[Any] | None] = mapped_column(JSONType, nullable=True)
    selected_answer: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)

    attempt: Mapped[QuizAttempt] = relationship(back_populates="questions")
    question: Mapped[Question] = relationship(lazy="selectin")
