"""Payments: plan status and verified Google Play purchases."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.dependencies import CurrentUser, DbSession
from app.rate_limit import limiter
from app.schemas.billing import BillingStatusOut, PurchaseIn, PurchaseOut
from app.services import billing_service
from app.services.play_billing import PlayVerifier, get_play_verifier

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


@router.get("/status", response_model=BillingStatusOut)
def status(
    user: CurrentUser,
    db: DbSession,
    student_id: Annotated[int | None, Query(alias="studentId")] = None,
) -> BillingStatusOut:
    """Plan status for me (student) or my linked child (parent: ``?studentId=``)."""
    return billing_service.billing_status(db, user, student_id)


@router.post("/purchases", response_model=PurchaseOut)
@limiter.limit("30/hour")
def record_purchase(
    request: Request,
    body: PurchaseIn,
    user: CurrentUser,
    db: DbSession,
    verifier: Annotated[PlayVerifier, Depends(get_play_verifier)],
) -> PurchaseOut:
    """Check a Google Play purchase with Google and unlock what it paid for (idempotent)."""
    return billing_service.record_purchase(db, user, body, verifier)
