"""Parent ↔ student linking and read-only progress reports."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from app.models.enums import Medium, ParentLinkStatus
from app.schemas.common import CamelModel
from app.services.progress_service import TopicState

INVITE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I confusion


class InviteOut(CamelModel):
    """An invite code the student shares with a parent."""

    code: str
    expires_at: datetime


class LinkedParentOut(CamelModel):
    """A parent linked to the student (shown on the student's profile)."""

    link_id: int
    name: str | None
    email: str
    status: ParentLinkStatus
    linked_at: datetime | None


class StudentLinksOut(CamelModel):
    """The student's parents and current invite, if any."""

    parents: list[LinkedParentOut]
    invite: InviteOut | None


class RedeemInviteRequest(CamelModel):
    """A parent enters the code the student shared (dashes/spaces ignored)."""

    code: str = Field(min_length=8, max_length=16)

    @field_validator("code")
    @classmethod
    def _normalise(cls, value: str) -> str:
        """Upper-case and strip separators; must be 8 valid characters."""
        code = "".join(ch for ch in value.upper() if ch.isalnum())
        if len(code) != 8 or any(ch not in INVITE_CODE_ALPHABET for ch in code):
            raise ValueError("Enter the 8-character code exactly as shared")
        return code


class SubjectProgressOut(CamelModel):
    """Completed vs total topics in one subject."""

    subject_id: int
    name: str
    tile_color: str
    completed: int
    total: int


class ChildSummaryOut(CamelModel):
    """One linked child on the parent's home screen."""

    student_id: int
    name: str | None
    medium: Medium | None
    topics_completed: int
    topics_total: int
    subjects: list[SubjectProgressOut]
    last_active_at: datetime | None
    tests_this_week: int
    average_score_this_week: float | None


class TopicReportOut(CamelModel):
    """A topic and how the child is doing in it."""

    title: str
    status: TopicState
    best_score_pct: float | None


class SubjectReportOut(SubjectProgressOut):
    """A subject with each topic's status."""

    topics: list[TopicReportOut]


class TestResultOut(CamelModel):
    """A submitted test."""

    topic_title: str
    subject_name: str
    score_pct: float
    passed: bool
    submitted_at: datetime


class ChildReportOut(ChildSummaryOut):
    """Full read-only report for one linked child."""

    subjects_detail: list[SubjectReportOut]
    recent_tests: list[TestResultOut]
    minutes_learning_this_week: int
    re_explanations_this_week: int
