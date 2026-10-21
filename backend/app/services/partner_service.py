"""School / teacher referral partners: codes, commissions and payouts.

Rules:
- An admin creates a partner with an email; the account signing in with that email gets the
  ``partner`` role (never an existing student/parent/admin account).
- A student is linked to one partner, once, by code (typed, or from the Play install link),
  and only before their first purchase.
- Every verified payment by a linked student (first purchase and every renewal) earns the
  partner ``commission_pct`` % of the **net** amount (price minus Google's fee). It becomes
  payable after ``PARTNER_HOLD_DAYS`` (refund window).
- Partners request a payout once their payable balance reaches ``PARTNER_PAYOUT_MIN_PAISE``;
  an admin approves and pays by UPI / bank, then records the reference.
- Partners only see counts and amounts, never student names (students are minors).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.billing import Purchase
from app.models.enums import UserRole
from app.models.partner import Commission, Partner, Payout
from app.models.user import User

logger = logging.getLogger(__name__)

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


# --- encryption of payout details --------------------------------------------------------------


def _fernet() -> Fernet:
    key = hashlib.sha256(f"partner-payout:{settings.SECRET_KEY}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(value: dict[str, Any] | str) -> str:
    """Encrypt payout details / PAN with a key derived from SECRET_KEY."""
    raw = value if isinstance(value, str) else json.dumps(value)
    return _fernet().encrypt(raw.encode()).decode()


def decrypt(token: str | None) -> str | None:
    """Decrypt; None when missing or unreadable (e.g. SECRET_KEY changed)."""
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        logger.error("Could not decrypt partner payout data")
        return None


# --- helpers -----------------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def normalize_code(code: str) -> str:
    """Upper-case and strip spaces/dashes so codes are easy to type."""
    return "".join(ch for ch in code.upper() if ch.isalnum())


def new_code(db: Session, name: str) -> str:
    """A unique code: up to 6 letters of the name + 3 random characters (e.g. STJOSE7K2)."""
    prefix = "".join(ch for ch in name.upper() if ch.isalpha())[:6] or "PTA"
    for _ in range(20):
        code = prefix + "".join(secrets.choice(CODE_ALPHABET) for _ in range(3))
        if db.scalar(select(Partner.id).where(Partner.code == code)) is None:
            return code
    raise ConflictError("Could not create a unique code, try again")  # pragma: no cover


def partner_for_user(db: Session, user: User) -> Partner:
    """The partner profile of a partner account (404 otherwise)."""
    partner = db.scalar(select(Partner).where(Partner.user_id == user.id))
    if partner is None:
        raise NotFoundError("Partner profile not found")
    return partner


def claim_partner_role(db: Session, user: User) -> None:
    """Called when a new account is created: an invited partner email becomes a partner.

    Does not commit (the caller commits with the new user).
    """
    if user.role != UserRole.student:
        return
    partner = db.scalar(
        select(Partner).where(Partner.email == user.email.lower(), Partner.user_id.is_(None))
    )
    if partner is None:
        return
    db.flush()
    partner.user_id = user.id
    user.role = UserRole.partner
    logger.info("Partner %s claimed by user %s", partner.id, user.id)


# --- admin: partners ---------------------------------------------------------------------------


def create_partner(db: Session, name: str, email: str, commission_pct: Decimal | None) -> Partner:
    """Create a partner; links an existing *new-style* account with that email if safe."""
    email = email.strip().lower()
    if db.scalar(select(Partner.id).where(Partner.email == email)) is not None:
        raise ConflictError("A partner with this email already exists", code="partner_exists")
    existing = db.scalar(select(User).where(func.lower(User.email) == email))
    if existing is not None and existing.role != UserRole.partner:
        raise ConflictError(
            "This email already belongs to a student, parent or admin account. "
            "Use a different email for the partner.",
            code="email_in_use",
        )
    partner = Partner(
        name=name.strip(),
        email=email,
        code=new_code(db, name),
        commission_pct=commission_pct if commission_pct is not None else Decimal("2"),
        user_id=existing.id if existing is not None else None,
    )
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner


# --- students: referral ------------------------------------------------------------------------


def apply_referral(db: Session, student: User, code: str) -> Partner:
    """Link a student to the partner with ``code`` (once, before any purchase)."""
    if student.role != UserRole.student:
        raise ForbiddenError("Only students can use a school code", code="not_student")
    partner = db.scalar(select(Partner).where(Partner.code == normalize_code(code)))
    if partner is None or not partner.is_active:
        raise NotFoundError("This school code is not valid", code="invalid_code")
    if student.referred_by_partner_id == partner.id:
        return partner
    if student.referred_by_partner_id is not None:
        raise ConflictError("You already joined with a school code", code="already_referred")
    paid = db.scalar(select(Purchase.id).where(Purchase.beneficiary_user_id == student.id))
    if paid is not None:
        raise ConflictError(
            "School codes can only be added before the first purchase", code="already_paid"
        )
    student.referred_by_partner_id = partner.id
    student.referred_at = _now()
    db.commit()
    return partner


# --- commissions -------------------------------------------------------------------------------


def _price_paise(product_id: str, base_plan: str | None) -> int | None:
    key = base_plan if product_id in settings.PLAY_SUBSCRIPTION_IDS else product_id
    return settings.PARTNER_PRICE_PAISE.get(key or "")


def record_commission(
    db: Session, purchase: Purchase, order_key: str, base_plan: str | None = None
) -> Commission | None:
    """Add the partner's commission for one payment (idempotent per purchase + order).

    Does not commit. Returns None when the student has no active partner.
    """
    student = db.get(User, purchase.beneficiary_user_id)
    if student is None or student.referred_by_partner_id is None:
        return None
    partner = db.get(Partner, student.referred_by_partner_id)
    if partner is None or not partner.is_active:
        return None
    exists = db.scalar(
        select(Commission.id).where(
            Commission.purchase_id == purchase.id, Commission.order_key == order_key
        )
    )
    if exists is not None:
        return None
    price = _price_paise(purchase.product_id, base_plan)
    if price is None:
        logger.warning("No price for %s/%s; commission skipped", purchase.product_id, base_plan)
        return None
    net = price * settings.PARTNER_NET_REVENUE_PCT // 100
    rate = Decimal(str(partner.commission_pct))
    amount = int((Decimal(net) * rate / Decimal(100)).to_integral_value())
    commission = Commission(
        partner_id=partner.id,
        purchase_id=purchase.id,
        order_key=order_key,
        product=base_plan or purchase.product_id,
        net_paise=net,
        rate_pct=rate,
        amount_paise=amount,
        available_at=_now() + timedelta(days=settings.PARTNER_HOLD_DAYS),
    )
    db.add(commission)
    return commission


# --- partner dashboard -------------------------------------------------------------------------


@dataclass(frozen=True)
class Balances:
    """Commission totals in paise."""

    earned: int  # all non-reversed commissions
    on_hold: int  # inside the refund window
    available: int  # payable now, not yet requested
    requested: int  # in a payout waiting for the admin
    paid: int


def balances(db: Session, partner: Partner) -> Balances:
    """Commission totals for the dashboard."""
    now = _now()
    rows = db.execute(
        select(Commission.amount_paise, Commission.available_at, Payout.status)
        .outerjoin(Payout, Commission.payout_id == Payout.id)
        .where(Commission.partner_id == partner.id, Commission.reversed.is_(False))
    ).all()
    earned = on_hold = available = requested = paid = 0
    for amount, available_at, payout_status in rows:
        earned += amount
        if payout_status == "paid":
            paid += amount
        elif payout_status in ("requested", "approved"):
            requested += amount
        elif _aware(available_at) > now:
            on_hold += amount
        else:
            available += amount
    return Balances(earned, on_hold, available, requested, paid)


def student_counts(db: Session, partner: Partner) -> tuple[int, int]:
    """(students who joined with the code, students who have paid at least once)."""
    joined = (
        db.scalar(select(func.count(User.id)).where(User.referred_by_partner_id == partner.id))
        or 0
    )
    paying = (
        db.scalar(
            select(func.count(func.distinct(Purchase.beneficiary_user_id)))
            .join(User, User.id == Purchase.beneficiary_user_id)
            .where(User.referred_by_partner_id == partner.id)
        )
        or 0
    )
    return joined, paying


def _payable_commissions(db: Session, partner: Partner) -> list[Commission]:
    return list(
        db.scalars(
            select(Commission).where(
                Commission.partner_id == partner.id,
                Commission.reversed.is_(False),
                Commission.payout_id.is_(None),
                Commission.available_at <= _now(),
            )
        )
    )


def request_payout(db: Session, partner: Partner) -> Payout:
    """Bundle every payable commission into one payout request for the admin."""
    if not partner.payout_details_enc:
        raise BadRequestError(
            "Add your UPI ID or bank account first", code="payout_details_missing"
        )
    open_payout = db.scalar(
        select(Payout.id).where(
            Payout.partner_id == partner.id, Payout.status.in_(("requested", "approved"))
        )
    )
    if open_payout is not None:
        raise ConflictError("You already have a payout in progress", code="payout_in_progress")
    items = _payable_commissions(db, partner)
    total = sum(c.amount_paise for c in items)
    if total < settings.PARTNER_PAYOUT_MIN_PAISE:
        minimum = settings.PARTNER_PAYOUT_MIN_PAISE // 100
        raise BadRequestError(f"You can request a payout from ₹{minimum}", code="below_minimum")
    payout = Payout(partner_id=partner.id, amount_paise=total, status="requested")
    db.add(payout)
    db.flush()
    for item in items:
        item.payout_id = payout.id
    db.commit()
    db.refresh(payout)
    logger.info("Payout %s requested by partner %s", payout.id, partner.id)
    return payout


# --- admin: payouts ----------------------------------------------------------------------------


def _get_payout(db: Session, payout_id: int) -> Payout:
    payout = db.get(Payout, payout_id)
    if payout is None:
        raise NotFoundError("Payout not found")
    return payout


def decide_payout(
    db: Session, payout_id: int, action: str, reference: str | None, note: str | None
) -> Payout:
    """Admin: approve, mark paid (with the UPI / bank reference) or reject a payout."""
    payout = _get_payout(db, payout_id)
    allowed = {
        "approve": ("requested",),
        "paid": ("requested", "approved"),
        "reject": ("requested", "approved"),
    }
    if payout.status not in allowed.get(action, ()):
        raise ConflictError(f"Cannot {action} a {payout.status} payout", code="bad_status")
    now = _now()
    if action == "approve":
        payout.status = "approved"
        payout.decided_at = now
    elif action == "paid":
        if not reference or not reference.strip():
            raise BadRequestError("Enter the UPI / bank transaction reference", code="reference")
        payout.status = "paid"
        payout.reference = reference.strip()
        payout.paid_at = now
        payout.decided_at = payout.decided_at or now
    else:
        payout.status = "rejected"
        payout.decided_at = now
        for item in db.scalars(select(Commission).where(Commission.payout_id == payout.id)):
            item.payout_id = None  # back to the partner's available balance
    payout.admin_note = note or payout.admin_note
    db.commit()
    db.refresh(payout)
    return payout


def ready_partners(db: Session) -> list[tuple[Partner, int]]:
    """Partners whose payable balance reached the minimum and have no payout in progress."""
    out: list[tuple[Partner, int]] = []
    for partner in db.scalars(
        select(Partner).where(Partner.is_active.is_(True), Partner.user_id.is_not(None))
    ):
        bal = balances(db, partner)
        if bal.available >= settings.PARTNER_PAYOUT_MIN_PAISE and bal.requested == 0:
            out.append((partner, bal.available))
    return out

