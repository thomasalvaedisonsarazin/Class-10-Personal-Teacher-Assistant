"""Classes per board, chosen subjects, language-only subjects and one active session.

Revision ID: 0007_courses
Revises: 0006_partners
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_courses"
down_revision: str | Sequence[str] | None = "0006_partners"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add ``family`` / ``grade`` / ``choose_subjects`` to boards and ``student_subjects``."""
    op.add_column(
        "boards",
        sa.Column("family", sa.String(32), server_default="TN_STATE", nullable=False),
    )
    op.add_column(
        "boards", sa.Column("grade", sa.SmallInteger(), server_default="10", nullable=False)
    )
    op.add_column(
        "boards",
        sa.Column("choose_subjects", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.execute("UPDATE boards SET family = 'CBSE' WHERE code LIKE 'CBSE%'")
    op.create_table(
        "student_subjects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subject_id",
            sa.Integer(),
            sa.ForeignKey("subjects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "subject_id"),
    )
    op.create_index("ix_student_subjects_user_id", "student_subjects", ["user_id"])
    op.create_index("ix_student_subjects_subject_id", "student_subjects", ["subject_id"])
    op.add_column("subjects", sa.Column("fixed_medium", sa.String(8), nullable=True))
    op.add_column("users", sa.Column("active_session_id", sa.String(36), nullable=True))
    op.add_column(
        "users", sa.Column("active_session_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("refresh_tokens", sa.Column("session_id", sa.String(36), nullable=True))


def downgrade() -> None:
    """Drop the class columns, chosen subjects, fixed medium and session columns."""
    op.drop_column("refresh_tokens", "session_id")
    op.drop_column("users", "active_session_seen_at")
    op.drop_column("users", "active_session_id")
    op.drop_column("subjects", "fixed_medium")
    op.drop_index("ix_student_subjects_subject_id", table_name="student_subjects")
    op.drop_index("ix_student_subjects_user_id", table_name="student_subjects")
    op.drop_table("student_subjects")
    op.drop_column("boards", "choose_subjects")
    op.drop_column("boards", "grade")
    op.drop_column("boards", "family")
