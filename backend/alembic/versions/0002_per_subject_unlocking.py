"""Allow studying several subjects at once: drop the one-active-topic-per-user index.

Unlocking is now sequential *within each subject* (first topic of every subject is
open; pass a topic's quiz with >= 60% to unlock the next one). That rule is
enforced in ``services/progress_service.py``.

Revision ID: 0002_per_subject_unlocking
Revises: 0001_initial
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_per_subject_unlocking"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the partial unique index."""
    op.drop_index("uq_topic_progress_one_active", table_name="topic_progress")


def downgrade() -> None:
    """Restore the partial unique index (fails if a user has several active topics)."""
    op.create_index(
        "uq_topic_progress_one_active",
        "topic_progress",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )
