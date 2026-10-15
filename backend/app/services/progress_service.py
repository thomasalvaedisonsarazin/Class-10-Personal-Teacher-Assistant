"""Topic locking and unlocking — the single source of truth.

Rules:
- Every subject is open. In each subject the topics form one ordered path
  (chapter order, then topic order); only published topics count.
- The first topic of every subject is open from the start.
- A topic is ``completed`` only after a quiz attempt scores >= ``QUIZ_PASS_PCT``;
  that opens the next topic of the same subject.
- Completed topics stay open for review. Anything after the first unfinished
  topic of a subject is ``locked``.

Lessons, "Not clear" and quiz endpoints must call :func:`require_topic_access`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.curriculum import Chapter, Subject, Topic
from app.models.enums import TopicStatus
from app.models.progress import TopicProgress
from app.models.user import User

logger = logging.getLogger(__name__)


class TopicState(StrEnum):
    """What a student may do with a topic."""

    locked = "locked"  # finish the previous topic of this subject first
    available = "available"  # open, not started yet
    active = "active"  # started, quiz not passed yet
    completed = "completed"  # quiz passed; open for review


@dataclass(frozen=True)
class TopicStatusInfo:
    """Derived state of one topic for one student."""

    topic_id: int
    subject_id: int
    state: TopicState
    best_score_pct: float | None


def _board_id(user: User) -> int:
    if user.board_id is None:
        raise BadRequestError("Choose your board first", code="onboarding_required")
    return user.board_id


def compute_states(
    ordered_topic_ids: list[int], progress: dict[int, TopicProgress]
) -> dict[int, TopicState]:
    """Derive states for one subject's ordered topics from stored progress.

    Args:
        ordered_topic_ids: Published topics of a subject in study order
        progress: The student's TopicProgress rows keyed by topic id

    Returns:
        State for every topic id
    """
    states: dict[int, TopicState] = {}
    frontier_open = True
    for topic_id in ordered_topic_ids:
        row = progress.get(topic_id)
        if row is not None and row.status == TopicStatus.completed:
            states[topic_id] = TopicState.completed
        elif frontier_open:
            started = row is not None and row.status == TopicStatus.active
            states[topic_id] = TopicState.active if started else TopicState.available
            frontier_open = False
        else:
            states[topic_id] = TopicState.locked
    return states


def board_topic_statuses(
    db: Session, user: User, subject_id: int | None = None
) -> dict[int, TopicStatusInfo]:
    """States of all published topics on the student's board (or one subject).

    Uses two queries (topics + progress) regardless of the number of subjects.
    """
    query = (
        select(Topic.id, Chapter.subject_id)
        .join(Chapter, Topic.chapter_id == Chapter.id)
        .join(Subject, Chapter.subject_id == Subject.id)
        .where(Subject.board_id == _board_id(user), Topic.is_published.is_(True))
        .order_by(Subject.display_order, Chapter.display_order, Topic.display_order)
    )
    if subject_id is not None:
        query = query.where(Subject.id == subject_id)
    rows = db.execute(query).all()

    per_subject: dict[int, list[int]] = {}
    for topic_id, sid in rows:
        per_subject.setdefault(sid, []).append(topic_id)

    topic_ids = [topic_id for topic_id, _ in rows]
    progress: dict[int, TopicProgress] = {}
    if topic_ids:
        progress = {
            row.topic_id: row
            for row in db.scalars(
                select(TopicProgress).where(
                    TopicProgress.user_id == user.id, TopicProgress.topic_id.in_(topic_ids)
                )
            )
        }

    result: dict[int, TopicStatusInfo] = {}
    for sid, ordered in per_subject.items():
        for topic_id, state in compute_states(ordered, progress).items():
            row = progress.get(topic_id)
            result[topic_id] = TopicStatusInfo(
                topic_id=topic_id,
                subject_id=sid,
                state=state,
                best_score_pct=row.best_score_pct if row else None,
            )
    return result


def get_topic_for_student(db: Session, user: User, topic_id: int) -> Topic:
    """Load a published topic on the student's board, else 404."""
    topic = db.scalar(
        select(Topic)
        .join(Chapter, Topic.chapter_id == Chapter.id)
        .join(Subject, Chapter.subject_id == Subject.id)
        .where(
            Topic.id == topic_id,
            Topic.is_published.is_(True),
            Subject.board_id == _board_id(user),
        )
    )
    if topic is None:
        raise NotFoundError("Topic not found")
    return topic


def get_topic_status(db: Session, user: User, topic: Topic) -> TopicStatusInfo:
    """Derived status of ``topic`` for ``user``."""
    statuses = board_topic_statuses(db, user, subject_id=topic.chapter.subject_id)
    return statuses[topic.id]


def require_topic_access(db: Session, user: User, topic_id: int) -> tuple[Topic, TopicStatusInfo]:
    """Return the topic if the student may study it, else raise.

    Raises:
        NotFoundError: unknown/unpublished topic or another board's topic
        ForbiddenError: the topic is locked (code ``topic_locked``)
    """
    topic = get_topic_for_student(db, user, topic_id)
    status = get_topic_status(db, user, topic)
    if status.state == TopicState.locked:
        raise ForbiddenError(
            "Pass the previous topic's test (60% or more) to unlock this topic",
            code="topic_locked",
        )
    return topic, status


def start_topic(db: Session, user: User, topic_id: int) -> TopicStatusInfo:
    """Mark an open topic as started (idempotent). Completed topics stay completed."""
    topic, status = require_topic_access(db, user, topic_id)
    if status.state == TopicState.available:
        db.add(TopicProgress(user_id=user.id, topic_id=topic.id, status=TopicStatus.active))
        db.commit()
        status = get_topic_status(db, user, topic)
    return status


def record_quiz_result(db: Session, user: User, topic: Topic, score_pct: float) -> bool:
    """Store a graded quiz attempt; completes the topic when ``score_pct`` passes.

    Called only from quiz grading. Does not commit — the caller commits together
    with the attempt.

    Returns:
        True if the attempt passed (``score_pct >= QUIZ_PASS_PCT``)
    """
    passed = score_pct >= settings.QUIZ_PASS_PCT
    row = db.scalar(
        select(TopicProgress).where(
            TopicProgress.user_id == user.id, TopicProgress.topic_id == topic.id
        )
    )
    if row is None:
        row = TopicProgress(
            user_id=user.id, topic_id=topic.id, status=TopicStatus.active, attempts_count=0
        )
        db.add(row)
        db.flush()  # a second result in the same transaction must update, not insert
    row.attempts_count = (row.attempts_count or 0) + 1
    if row.best_score_pct is None or score_pct > row.best_score_pct:
        row.best_score_pct = score_pct
    if passed and row.status != TopicStatus.completed:
        row.status = TopicStatus.completed
        row.completed_at = datetime.now(UTC)
        logger.info("Topic completed user_id=%s topic_id=%s", user.id, topic.id)
    return passed
