"""Google Play purchases that give a student access to paid topics."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

# "pass" (one-time 30/365-day access) is no longer sold; kept so old rows stay valid.
PURCHASE_KINDS = ("subscription", "pass", "topic")


class Purchase(TimestampMixin, Base):
    """One verified Google Play purchase.

    ``beneficiary_user_id`` is the student who gets access (the payer's own account, or a
    linked child when a parent pays). ``expires_at`` is NULL for a single topic (forever).
    """

    __tablename__ = "purchases"
    __table_args__ = (
        sa.CheckConstraint(f"kind IN {PURCHASE_KINDS}", name="purchase_kind"),
        sa.CheckConstraint(
            "(kind = 'topic') = (topic_id IS NOT NULL)", name="topic_purchase_has_topic"
        ),
        sa.Index("ix_purchases_beneficiary_kind", "beneficiary_user_id", "kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    payer_user_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    beneficiary_user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    product_id: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    topic_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=True
    )
    # Google's purchase token: unique, so one payment can never be claimed twice.
    purchase_token: Mapped[str] = mapped_column(sa.String(512), unique=True, nullable=False)
    order_id: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    auto_renewing: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    last_checked_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
