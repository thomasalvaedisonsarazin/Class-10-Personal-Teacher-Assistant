"""Payments (Google Play Billing)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import Field

from app.schemas.common import CamelModel

if TYPE_CHECKING:
    from app.models.billing import Purchase


class PurchaseIn(CamelModel):
    """A purchase the app just completed with Google Play."""

    product_id: str = Field(min_length=1, max_length=100)
    purchase_token: str = Field(min_length=10, max_length=512)
    # Parents: the linked child this is for. Students: leave empty.
    student_id: int | None = None
    # Single-topic purchase: the topic to unlock.
    topic_id: int | None = None


class PurchaseOut(CamelModel):
    """The access a verified purchase gave."""

    kind: str
    student_id: int
    topic_id: int | None
    expires_at: datetime | None

    @classmethod
    def from_row(cls, row: Purchase) -> PurchaseOut:
        """Build from a stored purchase."""
        return cls(
            kind=row.kind,
            student_id=row.beneficiary_user_id,
            topic_id=row.topic_id,
            expires_at=row.expires_at,
        )


class BillingStatusOut(CamelModel):
    """Plan status shown on the Premium screen."""

    billing_enabled: bool
    student_id: int
    premium_until: datetime | None
    purchased_topic_ids: list[int]
    free_topics_per_subject: int
    # Plan product to buy next: Google allows one active subscription per product per
    # account, so a parent's children use premium, premium_2, premium_3. None = all in use.
    next_subscription_id: str | None
    # Passed to Google Play as obfuscatedAccountId / obfuscatedProfileId.
    account_tag: str
    profile_tag: str
