"""School / teacher partner program: student codes, partner dashboard, admin payouts."""

from __future__ import annotations

import json
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import AdminUser, DbSession, PartnerUser, StudentUser
from app.exceptions import NotFoundError
from app.models.partner import Partner, Payout
from app.rate_limit import limiter
from app.schemas.partner import (
    AdminPartnerOut,
    AdminPayoutOut,
    PartnerCreate,
    PartnerDashboard,
    PartnerUpdate,
    PayoutDecision,
    PayoutDetailsIn,
    PayoutOut,
    ReferralIn,
    ReferralOut,
)
from app.services import partner_service

router = APIRouter(tags=["partners"])


def _rupees(paise: int) -> float:
    return round(paise / 100, 2)


def share_link(code: str) -> str:
    """Public link a partner shares; opens the Play Store with the code attached."""
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/r/{code}"


def _mask(details: dict[str, str] | None) -> str | None:
    if not details:
        return None
    if details.get("method") == "upi":
        upi = details.get("upi", "")
        return f"UPI ••••@{upi.split('@')[-1]}" if "@" in upi else "UPI"
    return f"Bank ••••{details.get('account', '')[-4:]}"


def _details(partner: Partner) -> dict[str, str] | None:
    raw = partner_service.decrypt(partner.payout_details_enc)
    return json.loads(raw) if raw else None


def _payout_out(payout: Payout) -> PayoutOut:
    return PayoutOut(
        id=payout.id,
        amount=_rupees(payout.amount_paise),
        status=payout.status,
        reference=payout.reference,
        requested_at=payout.created_at,
        paid_at=payout.paid_at,
    )


def _dashboard(db: Session, partner: Partner) -> PartnerDashboard:
    bal = partner_service.balances(db, partner)
    joined, paying = partner_service.student_counts(db, partner)
    payouts = db.scalars(
        select(Payout).where(Payout.partner_id == partner.id).order_by(Payout.id.desc()).limit(20)
    ).all()
    return PartnerDashboard(
        name=partner.name,
        code=partner.code,
        share_link=share_link(partner.code),
        commission_pct=float(partner.commission_pct),
        students_joined=joined,
        paying_students=paying,
        earned=_rupees(bal.earned),
        on_hold=_rupees(bal.on_hold),
        available=_rupees(bal.available),
        requested=_rupees(bal.requested),
        paid=_rupees(bal.paid),
        payout_minimum=_rupees(settings.PARTNER_PAYOUT_MIN_PAISE),
        hold_days=settings.PARTNER_HOLD_DAYS,
        can_request_payout=(
            bal.available >= settings.PARTNER_PAYOUT_MIN_PAISE
            and bal.requested == 0
            and partner.payout_details_enc is not None
        ),
        payout_method=_mask(_details(partner)),
        pan_added=partner.pan_enc is not None,
        payouts=[_payout_out(p) for p in payouts],
    )


# --- public link -------------------------------------------------------------------------------


@router.get("/r/{code}", include_in_schema=False)
def referral_link(code: Annotated[str, Path(max_length=30)]) -> RedirectResponse:
    """Send the visitor to the Play Store; the app reads the code from the install referrer."""
    clean = partner_service.normalize_code(code)
    referrer = quote(f"pta_ref={clean}", safe="")
    url = (
        "https://play.google.com/store/apps/details"
        f"?id={settings.PLAY_PACKAGE_NAME}&referrer={referrer}"
    )
    return RedirectResponse(url, status_code=302)


# --- students ----------------------------------------------------------------------------------


@router.post("/api/v1/referrals", response_model=ReferralOut)
@limiter.limit("10/hour")
def use_referral_code(
    request: Request, body: ReferralIn, user: StudentUser, db: DbSession
) -> ReferralOut:
    """Link me to the school / teacher whose code I entered (once, before paying)."""
    partner = partner_service.apply_referral(db, user, body.code)
    return ReferralOut(partner_name=partner.name)


# --- partners ----------------------------------------------------------------------------------


@router.get("/api/v1/partner-program/me", response_model=PartnerDashboard)
def my_dashboard(user: PartnerUser, db: DbSession) -> PartnerDashboard:
    """My code, link, students and commission."""
    return _dashboard(db, partner_service.partner_for_user(db, user))


@router.put("/api/v1/partner-program/payout-details", response_model=PartnerDashboard)
def save_payout_details(
    body: PayoutDetailsIn, user: PartnerUser, db: DbSession
) -> PartnerDashboard:
    """Save where to send my money (UPI or bank) and optionally my PAN (stored encrypted)."""
    partner = partner_service.partner_for_user(db, user)
    if body.method == "upi":
        details = {"method": "upi", "upi": (body.upi_id or "").strip()}
    else:
        details = {
            "method": "bank",
            "holder": (body.holder_name or "").strip(),
            "account": body.account_number or "",
            "ifsc": body.ifsc or "",
        }
    partner.payout_details_enc = partner_service.encrypt(details)
    if body.pan:
        partner.pan_enc = partner_service.encrypt(body.pan)
    db.commit()
    return _dashboard(db, partner)


@router.post("/api/v1/partner-program/payouts", response_model=PayoutOut, status_code=201)
@limiter.limit("10/hour")
def request_payout(request: Request, user: PartnerUser, db: DbSession) -> PayoutOut:
    """Ask the admin to pay out my available commission."""
    partner = partner_service.partner_for_user(db, user)
    return _payout_out(partner_service.request_payout(db, partner))


# --- admin -------------------------------------------------------------------------------------


def _admin_partner(db: Session, partner: Partner) -> AdminPartnerOut:
    bal = partner_service.balances(db, partner)
    joined, paying = partner_service.student_counts(db, partner)
    return AdminPartnerOut(
        id=partner.id,
        name=partner.name,
        email=partner.email,
        code=partner.code,
        share_link=share_link(partner.code),
        commission_pct=float(partner.commission_pct),
        is_active=partner.is_active,
        signed_in=partner.user_id is not None,
        students_joined=joined,
        paying_students=paying,
        earned=_rupees(bal.earned),
        available=_rupees(bal.available),
        paid=_rupees(bal.paid),
    )


@router.get("/api/v1/admin/partners", response_model=list[AdminPartnerOut])
def list_partners(_: AdminUser, db: DbSession) -> list[AdminPartnerOut]:
    """All partners with their numbers."""
    partners = db.scalars(select(Partner).order_by(Partner.id.desc())).all()
    return [_admin_partner(db, p) for p in partners]


@router.post("/api/v1/admin/partners", response_model=AdminPartnerOut, status_code=201)
def create_partner(body: PartnerCreate, _: AdminUser, db: DbSession) -> AdminPartnerOut:
    """Invite a school / teacher; they sign in with this email to see their dashboard."""
    partner = partner_service.create_partner(db, body.name, body.email, body.commission_pct)
    return _admin_partner(db, partner)


@router.patch("/api/v1/admin/partners/{partner_id}", response_model=AdminPartnerOut)
def update_partner(
    partner_id: int, body: PartnerUpdate, _: AdminUser, db: DbSession
) -> AdminPartnerOut:
    """Change a partner's name, commission % (applies to new payments) or active state."""
    partner = db.get(Partner, partner_id)
    if partner is None:
        raise NotFoundError("Partner not found")
    if body.name is not None:
        partner.name = body.name.strip()
    if body.commission_pct is not None:
        partner.commission_pct = body.commission_pct  # type: ignore[assignment]
    if body.is_active is not None:
        partner.is_active = body.is_active
    db.commit()
    return _admin_partner(db, partner)


def _admin_payout(payout: Payout, partner: Partner) -> AdminPayoutOut:
    return AdminPayoutOut(
        id=payout.id,
        partner_id=partner.id,
        partner_name=partner.name,
        amount=_rupees(payout.amount_paise),
        status=payout.status,
        reference=payout.reference,
        admin_note=payout.admin_note,
        requested_at=payout.created_at,
        paid_at=payout.paid_at,
        payout_details=_details(partner),
        pan=partner_service.decrypt(partner.pan_enc),
    )


@router.get("/api/v1/admin/payouts", response_model=list[AdminPayoutOut])
def list_payouts(
    _: AdminUser,
    db: DbSession,
    status: Annotated[
        Literal["requested", "approved", "paid", "rejected"] | None, Query()
    ] = None,
) -> list[AdminPayoutOut]:
    """Payout requests, newest first (optionally one status)."""
    query = select(Payout, Partner).join(Partner, Partner.id == Payout.partner_id)
    if status is not None:
        query = query.where(Payout.status == status)
    rows = db.execute(query.order_by(Payout.id.desc()).limit(200)).all()
    return [_admin_payout(payout, partner) for payout, partner in rows]


@router.post("/api/v1/admin/payouts/{payout_id}/{action}", response_model=AdminPayoutOut)
def decide_payout(
    payout_id: int,
    action: Literal["approve", "paid", "reject"],
    body: PayoutDecision,
    _: AdminUser,
    db: DbSession,
) -> AdminPayoutOut:
    """Approve, mark paid (with the UPI / bank reference) or reject a payout."""
    payout = partner_service.decide_payout(db, payout_id, action, body.reference, body.note)
    partner = db.get(Partner, payout.partner_id)
    if partner is None:  # pragma: no cover - payouts cascade with their partner
        raise NotFoundError("Partner not found")
    return _admin_payout(payout, partner)
