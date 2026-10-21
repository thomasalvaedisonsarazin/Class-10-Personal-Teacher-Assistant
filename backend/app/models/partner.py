"""School / teacher referral partners, their commissions and payouts."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

PAYOUT_STATUSES = ("requested", "approved", "paid", "rejected")


class Partner(TimestampMixin, Base):
    """A school, principal or teacher who brings students with a referral code.

    Created by an admin with the partner's email; the account that signs in with that
    email becomes the partner (``user_id``). Payout details are stored encrypted.
    """

    __tablename__ = "partners"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    email: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    code: Mapped[str] = mapped_column(sa.String(20), unique=True, index=True, nullable=False)
    commission_pct: Mapped[float] = mapped_column(
        sa.Numeric(5, 2), nullable=False, default=2, server_default="2"
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=True, server_default=sa.true()
    )
    # Encrypted JSON: {"method": "upi" | "bank", "upi", "account", "ifsc", "holder"}
    payout_details_enc: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    pan_enc: Mapped[str | None] = mapped_column(sa.Text, nullable=True)


class Commission(TimestampMixin, Base):
    """Commission on one verified payment by a referred student.

    One row per Google order (a subscription renewal is a new order), so every payment
    is counted once. Payable after ``available_at`` (refund window).
    """

    __tablename__ = "commissions"
    __table_args__ = (sa.UniqueConstraint("purchase_id", "order_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    partner_id: Mapped[int] = mapped_column(
        sa.ForeignKey("partners.id", ondelete="CASCADE"), index=True, nullable=False
    )
    purchase_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("purchases.id", ondelete="SET NULL"), nullable=True
    )
    order_key: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    product: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    net_paise: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    rate_pct: Mapped[float] = mapped_column(sa.Numeric(5, 2), nullable=False)
    amount_paise: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    available_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    reversed: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    payout_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("payouts.id", ondelete="SET NULL"), index=True, nullable=True
    )


class Payout(TimestampMixin, Base):
    """A partner's payout request; an admin approves it and pays by UPI / bank."""

    __tablename__ = "payouts"
    __table_args__ = (sa.CheckConstraint(f"status IN {PAYOUT_STATUSES}", name="payout_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    partner_id: Mapped[int] = mapped_column(
        sa.ForeignKey("partners.id", ondelete="CASCADE"), index=True, nullable=False
    )
    amount_paise: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="requested")
    reference: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    admin_note: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
