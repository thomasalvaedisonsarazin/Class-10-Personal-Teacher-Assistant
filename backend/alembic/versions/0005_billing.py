"""Google Play purchases (subscriptions, passes, single topics).

Revision ID: 0005_billing
Revises: 0004_email_login
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_billing"
down_revision: str | Sequence[str] | None = "0004_email_login"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the ``purchases`` table."""
    op.create_table(
        "purchases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "payer_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "beneficiary_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("product_id", sa.String(100), nullable=False),
        sa.Column(
            "topic_id", sa.Integer(), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("purchase_token", sa.String(512), nullable=False),
        sa.Column("order_id", sa.String(100), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_renewing", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("kind IN ('subscription', 'pass', 'topic')", name="purchase_kind"),
        sa.CheckConstraint(
            "(kind = 'topic') = (topic_id IS NOT NULL)", name="topic_purchase_has_topic"
        ),
        sa.UniqueConstraint("purchase_token"),
    )
    op.create_index(
        "ix_purchases_beneficiary_kind", "purchases", ["beneficiary_user_id", "kind"]
    )


def downgrade() -> None:
    """Drop the ``purchases`` table."""
    op.drop_index("ix_purchases_beneficiary_kind", table_name="purchases")
    op.drop_table("purchases")
