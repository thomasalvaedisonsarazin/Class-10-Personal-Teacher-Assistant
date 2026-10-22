"""Full-subject tests and board-pattern model question papers.

Revision ID: 0008_exam_practice
Revises: 0007_courses
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008_exam_practice"
down_revision: str | Sequence[str] | None = "0007_courses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    """Create ``subject_tests``, ``subject_test_questions`` and ``model_papers``."""
    op.create_table(
        "subject_tests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "subject_id",
            sa.Integer(),
            sa.ForeignKey("subjects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score_pct", sa.Float(), nullable=True),
        sa.Column("correct_count", sa.SmallInteger(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "score_pct IS NULL OR (score_pct >= 0 AND score_pct <= 100)",
            name="subject_test_score_range",
        ),
    )
    op.create_index("ix_subject_tests_user_subject", "subject_tests", ["user_id", "subject_id"])

    op.create_table(
        "subject_test_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "test_id",
            sa.Integer(),
            sa.ForeignKey("subject_tests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            sa.Integer(),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("served_options", JSON, nullable=True),
        sa.Column("selected_answer", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("test_id", "question_id"),
        sa.UniqueConstraint("test_id", "position"),
    )
    op.create_index(
        "ix_subject_test_questions_question_id", "subject_test_questions", ["question_id"]
    )

    op.create_table(
        "model_papers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "subject_id",
            sa.Integer(),
            sa.ForeignKey("subjects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("chapter_ids", JSON, nullable=False),
        sa.Column(
            "medium", postgresql.ENUM("en", "ta", name="medium", create_type=False), nullable=False
        ),
        sa.Column("pattern_id", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("total_marks", sa.SmallInteger(), nullable=False),
        sa.Column("duration_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("paper", JSON, nullable=True),
        sa.Column("answer_key", JSON, nullable=True),
        sa.Column("image_keys", JSON, nullable=False),
        sa.Column("results", JSON, nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_model_papers_user_subject", "model_papers", ["user_id", "subject_id"])


def downgrade() -> None:
    """Drop the exam practice tables."""
    op.drop_index("ix_model_papers_user_subject", table_name="model_papers")
    op.drop_table("model_papers")
    op.drop_index("ix_subject_test_questions_question_id", table_name="subject_test_questions")
    op.drop_table("subject_test_questions")
    op.drop_index("ix_subject_tests_user_subject", table_name="subject_tests")
    op.drop_table("subject_tests")
