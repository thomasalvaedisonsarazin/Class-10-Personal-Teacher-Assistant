"""School / teacher referral partners, commissions and payouts.

Revision ID: 0006_partners
Revises: 0005_billing
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_partners"
down_revision: str | Sequence[str] | None = "0005_billing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
    """Add the partner role, partner tables and ``users.referred_by_partner_id``."""
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'partner'")
    op.create_table(
        "partners",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            unique=True,
        ),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("commission_pct", sa.Numeric(5, 2), server_default="2", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("payout_details_enc", sa.Text(), nullable=True),
        sa.Column("pan_enc", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_partners_code", "partners", ["code"], unique=True)
    op.create_table(
        "payouts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "partner_id",
            sa.Integer(),
            sa.ForeignKey("partners.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reference", sa.String(120), nullable=True),
        sa.Column("admin_note", sa.String(500), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('requested', 'approved', 'paid', 'rejected')", name="payout_status"
        ),
    )
    op.create_index("ix_payouts_partner_id", "payouts", ["partner_id"])
    op.create_table(
        "commissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "partner_id",
            sa.Integer(),
            sa.ForeignKey("partners.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "purchase_id",
            sa.Integer(),
            sa.ForeignKey("purchases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("order_key", sa.String(120), nullable=False),
        sa.Column("product", sa.String(60), nullable=False),
        sa.Column("net_paise", sa.Integer(), nullable=False),
        sa.Column("rate_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reversed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "payout_id",
            sa.Integer(),
            sa.ForeignKey("payouts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        *_timestamps(),
        sa.UniqueConstraint("purchase_id", "order_key"),
    )
    op.create_index("ix_commissions_partner_id", "commissions", ["partner_id"])
    op.create_index("ix_commissions_payout_id", "commissions", ["payout_id"])
    op.add_column("users", sa.Column("referred_by_partner_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("referred_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_users_referred_by_partner_id_partners",
        "users",
        "partners",
        ["referred_by_partner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_users_referred_by_partner_id", "users", ["referred_by_partner_id"])


def downgrade() -> None:
    """Drop partner tables and columns (the enum value stays; Postgres can't drop it)."""
    op.drop_index("ix_users_referred_by_partner_id", table_name="users")
    op.drop_constraint("fk_users_referred_by_partner_id_partners", "users", type_="foreignkey")
    op.drop_column("users", "referred_at")
    op.drop_column("users", "referred_by_partner_id")
    op.drop_index("ix_commissions_payout_id", table_name="commissions")
    op.drop_index("ix_commissions_partner_id", table_name="commissions")
    op.drop_table("commissions")
    op.drop_index("ix_payouts_partner_id", table_name="payouts")
    op.drop_table("payouts")
    op.drop_index("ix_partners_code", table_name="partners")
    op.drop_table("partners")
