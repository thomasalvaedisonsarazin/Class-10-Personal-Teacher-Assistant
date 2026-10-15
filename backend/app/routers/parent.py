"""Parent linking (student side) and read-only child reports (parent side)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.dependencies import DbSession, ParentUser, StudentUser
from app.rate_limit import limiter
from app.schemas.parent import (
    ChildReportOut,
    ChildSummaryOut,
    InviteOut,
    RedeemInviteRequest,
    StudentLinksOut,
)
from app.services import parent_service

router = APIRouter(prefix="/api/v1", tags=["parent"])


# --- student ---------------------------------------------------------------------------------


@router.post("/parent-links/invite", response_model=InviteOut)
def create_invite(db: DbSession, student: StudentUser) -> InviteOut:
    """Get a code to share with a parent (reuses an unexpired one)."""
    return parent_service.create_invite(db, student)


@router.get("/parent-links", response_model=StudentLinksOut)
def my_parents(db: DbSession, student: StudentUser) -> StudentLinksOut:
    """Parents who can see my progress, and my open invite."""
    return parent_service.student_links(db, student)


@router.delete("/parent-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_parent(link_id: int, db: DbSession, student: StudentUser) -> Response:
    """Remove a parent's access."""
    parent_service.remove_parent(db, student, link_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- parent ----------------------------------------------------------------------------------


@router.post("/parent/links", response_model=ChildSummaryOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
def redeem_invite(
    request: Request, body: RedeemInviteRequest, db: DbSession, parent: ParentUser
) -> ChildSummaryOut:
    """Link to a child with the code they shared (rate limited against guessing)."""
    return parent_service.redeem_invite(db, parent, body.code)


@router.get("/parent/children", response_model=list[ChildSummaryOut])
def list_children(db: DbSession, parent: ParentUser) -> list[ChildSummaryOut]:
    """My linked children with a progress summary."""
    return parent_service.list_children(db, parent)


@router.get("/parent/children/{student_id}", response_model=ChildReportOut)
def child_report(student_id: int, db: DbSession, parent: ParentUser) -> ChildReportOut:
    """Read-only report for one linked child (404 if not linked)."""
    return parent_service.child_report(db, parent, student_id)
