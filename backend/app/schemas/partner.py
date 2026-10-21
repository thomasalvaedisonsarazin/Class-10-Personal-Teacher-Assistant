"""School / teacher partner program."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import EmailStr, Field, field_validator, model_validator

from app.schemas.common import CamelModel

UPI_RE = re.compile(r"^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


class ReferralIn(CamelModel):
    code: str = Field(min_length=3, max_length=30)


class ReferralOut(CamelModel):
    partner_name: str


class PayoutDetailsIn(CamelModel):
    """Where the partner wants to be paid. Stored encrypted."""

    method: Literal["upi", "bank"]
    upi_id: str | None = Field(default=None, max_length=320)
    holder_name: str | None = Field(default=None, max_length=120)
    account_number: str | None = Field(default=None, min_length=6, max_length=20)
    ifsc: str | None = Field(default=None, max_length=11)
    pan: str | None = Field(default=None, max_length=10)

    @field_validator("ifsc", "pan")
    @classmethod
    def _upper(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value

    @model_validator(mode="after")
    def _check(self) -> PayoutDetailsIn:
        if self.method == "upi":
            if not self.upi_id or not UPI_RE.match(self.upi_id.strip()):
                raise ValueError("Enter a valid UPI ID, e.g. name@okbank")
        else:
            if not (self.holder_name and self.account_number and self.ifsc):
                raise ValueError("Enter account holder name, account number and IFSC")
            if not self.account_number.isdigit():
                raise ValueError("Account number must contain only digits")
            if not IFSC_RE.match(self.ifsc):
                raise ValueError("Enter a valid IFSC code, e.g. SBIN0001234")
        if self.pan and not PAN_RE.match(self.pan):
            raise ValueError("Enter a valid PAN, e.g. ABCDE1234F")
        return self


class PayoutOut(CamelModel):
    id: int
    amount: float  # rupees
    status: str
    reference: str | None
    requested_at: datetime
    paid_at: datetime | None


class PartnerDashboard(CamelModel):
    """What a partner sees: counts and money only, never student names."""

    name: str
    code: str
    share_link: str
    commission_pct: float
    students_joined: int
    paying_students: int
    earned: float
    on_hold: float
    available: float
    requested: float
    paid: float
    payout_minimum: float
    hold_days: int
    can_request_payout: bool
    payout_method: str | None  # masked, e.g. "UPI ••••@okhdfc" / "Bank ••••1234"
    pan_added: bool
    payouts: list[PayoutOut]


class PartnerCreate(CamelModel):
    name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    commission_pct: Decimal | None = Field(default=None, ge=0, le=50)


class PartnerUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    commission_pct: Decimal | None = Field(default=None, ge=0, le=50)
    is_active: bool | None = None


class AdminPartnerOut(CamelModel):
    id: int
    name: str
    email: str
    code: str
    share_link: str
    commission_pct: float
    is_active: bool
    signed_in: bool
    students_joined: int
    paying_students: int
    earned: float
    available: float
    paid: float


class AdminPayoutOut(CamelModel):
    id: int
    partner_id: int
    partner_name: str
    amount: float
    status: str
    reference: str | None
    admin_note: str | None
    requested_at: datetime
    paid_at: datetime | None
    # Decrypted for the admin who sends the money.
    payout_details: dict[str, str] | None
    pan: str | None


class PayoutDecision(CamelModel):
    reference: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=500)
