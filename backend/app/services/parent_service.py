"""Parent module: invite codes, linking, and read-only reports.

A parent can only see a student who shared an invite code (and has not removed them).
Every report lookup goes through :func:`linked_student`, which is the IDOR guard.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import AppError, ConflictError, NotFoundError
from app.models.curriculum import Chapter, Subject, Topic
from app.models.enums import Medium, ParentLinkStatus, UserRole
from app.models.lesson import ClarityFeedback, LessonView
from app.models.parent import ParentLink
from app.models.quiz import QuizAttempt
from app.models.user import User
from app.schemas.parent import (
    INVITE_CODE_ALPHABET,
    ChildReportOut,
    ChildSummaryOut,
    InviteOut,
    LinkedParentOut,
    StudentLinksOut,
    SubjectProgressOut,
    SubjectReportOut,
    TestResultOut,
    TopicReportOut,
)
from app.services import curriculum_service

logger = logging.getLogger(__name__)

INVITE_VALID_DAYS = 7
MAX_PARENTS_PER_STUDENT = 4
RECENT_TESTS = 10


class InviteExpiredError(AppError):
    """410: the code was valid but has expired."""

    status_code = 410
    code = "invite_expired"
    message = "This code has expired. Ask your child to create a new one in the app."


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _new_code() -> str:
    return "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(8))


# --- student side -----------------------------------------------------------------------------


def _pending_invite(db: Session, student: User) -> ParentLink | None:
    link = db.scalar(
        select(ParentLink)
        .where(
            ParentLink.student_user_id == student.id,
            ParentLink.status == ParentLinkStatus.pending,
        )
        .order_by(ParentLink.id.desc())
        .limit(1)
    )
    if link is not None and _aware(link.invite_expires_at) > _now():
        return link
    return None


def create_invite(db: Session, student: User) -> InviteOut:
    """Return the student's current invite code, creating one if needed.

    Raises:
        ConflictError: already linked to the maximum number of parents
    """
    existing = _pending_invite(db, student)
    if existing is not None:
        return InviteOut(code=existing.invite_code, expires_at=_aware(existing.invite_expires_at))
    linked = db.scalar(
        select(func.count(ParentLink.id)).where(
            ParentLink.student_user_id == student.id,
            ParentLink.status == ParentLinkStatus.accepted,
        )
    )
    if (linked or 0) >= MAX_PARENTS_PER_STUDENT:
        raise ConflictError(
            f"You can link up to {MAX_PARENTS_PER_STUDENT} parents", code="too_many_parents"
        )
    for _ in range(5):
        link = ParentLink(
            student_user_id=student.id,
            invite_code=_new_code(),
            invite_expires_at=_now() + timedelta(days=INVITE_VALID_DAYS),
            status=ParentLinkStatus.pending,
        )
        db.add(link)
        try:
            db.commit()
        except IntegrityError:  # code collision: try another
            db.rollback()
            continue
        return InviteOut(code=link.invite_code, expires_at=_aware(link.invite_expires_at))
    raise ConflictError("Could not create a code, please try again", code="invite_failed")


def student_links(db: Session, student: User) -> StudentLinksOut:
    """The student's linked parents and their open invite."""
    rows = db.execute(
        select(ParentLink, User)
        .join(User, User.id == ParentLink.parent_user_id)
        .where(
            ParentLink.student_user_id == student.id,
            ParentLink.status == ParentLinkStatus.accepted,
        )
        .order_by(ParentLink.accepted_at)
    ).all()
    invite = _pending_invite(db, student)
    return StudentLinksOut(
        parents=[
            LinkedParentOut(
                link_id=link.id,
                name=parent.full_name,
                email=parent.email,
                status=ParentLinkStatus(link.status),
                linked_at=_aware(link.accepted_at) if link.accepted_at else None,
            )
            for link, parent in rows
        ],
        invite=InviteOut(code=invite.invite_code, expires_at=_aware(invite.invite_expires_at))
        if invite
        else None,
    )


def remove_parent(db: Session, student: User, link_id: int) -> None:
    """Student removes a parent's access (or cancels an invite)."""
    link = db.get(ParentLink, link_id)
    if link is None or link.student_user_id != student.id:
        raise NotFoundError("Link not found")
    link.status = ParentLinkStatus.revoked
    db.commit()
    logger.info("Parent link %s revoked by student %s", link.id, student.id)


# --- parent side ------------------------------------------------------------------------------


def redeem_invite(db: Session, parent: User, code: str) -> ChildSummaryOut:
    """Link ``parent`` to the student who created ``code``.

    Raises:
        NotFoundError: unknown or already-used code
        InviteExpiredError: the code expired
        ConflictError: already linked to this child
    """
    link = db.scalar(select(ParentLink).where(ParentLink.invite_code == code))
    if link is None or link.status != ParentLinkStatus.pending:
        raise NotFoundError(
            "That code is not valid. Check it and try again.", code="invalid_invite"
        )
    if _aware(link.invite_expires_at) <= _now():
        raise InviteExpiredError()
    if link.student_user_id == parent.id:
        raise NotFoundError(
            "That code is not valid. Check it and try again.", code="invalid_invite"
        )
    already = db.scalar(
        select(ParentLink).where(
            ParentLink.parent_user_id == parent.id,
            ParentLink.student_user_id == link.student_user_id,
        )
    )
    if already is not None and already.status == ParentLinkStatus.accepted:
        raise ConflictError("You are already linked to this child", code="already_linked")
    if already is not None:  # re-linking after removal: reuse the old row
        already.status = ParentLinkStatus.accepted
        already.accepted_at = _now()
        link.status = ParentLinkStatus.revoked  # the one-time code is used up
    else:
        link.parent_user_id = parent.id
        link.status = ParentLinkStatus.accepted
        link.accepted_at = _now()
    db.commit()
    logger.info("Parent %s linked to student %s", parent.id, link.student_user_id)
    student = db.get(User, link.student_user_id)
    assert student is not None  # noqa: S101 - FK guarantees it
    return _summary(db, student)


def linked_student(db: Session, parent: User, student_id: int) -> User:
    """The child, only if this parent holds an accepted link (else 404, never 403)."""
    linked = db.scalar(
        select(ParentLink.id).where(
            ParentLink.parent_user_id == parent.id,
            ParentLink.student_user_id == student_id,
            ParentLink.status == ParentLinkStatus.accepted,
        )
    )
    student = db.get(User, student_id) if linked else None
    if student is None or student.role != UserRole.student:
        raise NotFoundError("Child not found")
    return student


def list_children(db: Session, parent: User) -> list[ChildSummaryOut]:
    """Every child linked to this parent."""
    students = db.scalars(
        select(User)
        .join(ParentLink, ParentLink.student_user_id == User.id)
        .where(
            ParentLink.parent_user_id == parent.id,
            ParentLink.status == ParentLinkStatus.accepted,
            User.role == UserRole.student,
        )
        .order_by(User.full_name)
    ).all()
    return [_summary(db, s) for s in students]


def _week_tests(db: Session, student: User) -> tuple[int, float | None]:
    count, average = db.execute(
        select(func.count(QuizAttempt.id), func.avg(QuizAttempt.score_pct)).where(
            QuizAttempt.user_id == student.id,
            QuizAttempt.submitted_at.is_not(None),
            QuizAttempt.submitted_at >= _now() - timedelta(days=7),
        )
    ).one()
    return int(count), round(float(average), 1) if average is not None else None


def _last_active(db: Session, student: User) -> datetime | None:
    times = [
        db.scalar(select(func.max(LessonView.updated_at)).where(LessonView.user_id == student.id)),
        db.scalar(
            select(func.max(QuizAttempt.submitted_at)).where(QuizAttempt.user_id == student.id)
        ),
    ]
    present = [_aware(t) for t in times if t is not None]
    return max(present) if present else None


def _summary(db: Session, student: User) -> ChildSummaryOut:
    subjects = curriculum_service.list_subjects(db, student) if student.board_id else []
    tests, average = _week_tests(db, student)
    return ChildSummaryOut(
        student_id=student.id,
        name=student.full_name,
        medium=Medium(student.medium) if student.medium else None,
        topics_completed=sum(s.completed_topics for s in subjects),
        topics_total=sum(s.total_topics for s in subjects),
        subjects=[
            SubjectProgressOut(
                subject_id=s.id,
                name=s.name,
                tile_color=s.tile_color,
                completed=s.completed_topics,
                total=s.total_topics,
            )
            for s in subjects
        ],
        last_active_at=_last_active(db, student),
        tests_this_week=tests,
        average_score_this_week=average,
    )


def child_report(db: Session, parent: User, student_id: int) -> ChildReportOut:
    """Full read-only report for one linked child (404 if not linked)."""
    student = linked_student(db, parent, student_id)
    summary = _summary(db, student)
    detail = []
    if student.board_id:
        for subject in summary.subjects:
            info = curriculum_service.get_subject(db, student, subject.subject_id)
            detail.append(
                SubjectReportOut(
                    **subject.model_dump(),
                    topics=[
                        TopicReportOut(
                            title=t.title, status=t.status, best_score_pct=t.best_score_pct
                        )
                        for chapter in info.chapters
                        for t in chapter.topics
                    ],
                )
            )
    medium = curriculum_service.student_medium(student)
    attempts = db.execute(
        select(QuizAttempt, Topic, Subject)
        .join(Topic, Topic.id == QuizAttempt.topic_id)
        .join(Chapter, Chapter.id == Topic.chapter_id)
        .join(Subject, Subject.id == Chapter.subject_id)
        .where(QuizAttempt.user_id == student.id, QuizAttempt.submitted_at.is_not(None))
        .order_by(QuizAttempt.submitted_at.desc())
        .limit(RECENT_TESTS)
    ).all()
    week = _now() - timedelta(days=7)
    watched = db.scalar(
        select(func.coalesce(func.sum(LessonView.watched_sec), 0)).where(
            LessonView.user_id == student.id, LessonView.updated_at >= week
        )
    )
    not_clear = db.scalar(
        select(func.count(ClarityFeedback.id)).where(
            ClarityFeedback.user_id == student.id,
            ClarityFeedback.is_clear.is_(False),
            ClarityFeedback.created_at >= week,
        )
    )
    return ChildReportOut(
        **summary.model_dump(),
        subjects_detail=detail,
        recent_tests=[
            TestResultOut(
                topic_title=curriculum_service.topic_title(topic, medium),
                subject_name=curriculum_service.subject_name(subject, medium),
                score_pct=attempt.score_pct or 0.0,
                passed=attempt.passed,
                submitted_at=_aware(attempt.submitted_at or attempt.started_at),
            )
            for attempt, topic, subject in attempts
        ],
        minutes_learning_this_week=int((watched or 0) // 60),
        re_explanations_this_week=int(not_clear or 0),
    )
