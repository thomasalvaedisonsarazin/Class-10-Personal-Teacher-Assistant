"""Lesson explanation language (en / ta / tanglish), independent of the textbook medium.

Revision ID: 0003_lesson_language
Revises: 0002_per_subject_unlocking
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_lesson_language"
down_revision: str | Sequence[str] | None = "0002_per_subject_unlocking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

lesson_language = postgresql.ENUM("en", "ta", "tanglish", name="lesson_language", create_type=False)


def upgrade() -> None:
    """Add ``lessons.language`` (backfilled from ``medium``) and ``users.lesson_language``."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        lesson_language.create(bind, checkfirst=True)
    column_type = lesson_language if bind.dialect.name == "postgresql" else sa.String(16)
    op.add_column(
        "lessons", sa.Column("language", column_type, server_default="en", nullable=False)
    )
    if bind.dialect.name == "postgresql":
        op.execute("UPDATE lessons SET language = medium::text::lesson_language")
    else:
        op.execute("UPDATE lessons SET language = medium")
    op.create_index(
        "ix_lessons_topic_language_style_status",
        "lessons",
        ["topic_id", "language", "style", "status"],
    )
    op.add_column("users", sa.Column("lesson_language", column_type, nullable=True))


def downgrade() -> None:
    """Remove the language columns and type."""
    op.drop_column("users", "lesson_language")
    op.drop_index("ix_lessons_topic_language_style_status", table_name="lessons")
    op.drop_column("lessons", "language")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        lesson_language.drop(bind, checkfirst=True)
