"""Lessons: open a topic's lesson, "Not clear" style rotation, caching, jobs, progress."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import NotFoundError, RateLimitedError
from app.models.curriculum import Topic
from app.models.enums import (
    JobKind,
    JobStatus,
    LessonLanguage,
    LessonSource,
    LessonStatus,
    LessonStyle,
    Medium,
)
from app.models.lesson import ClarityFeedback, GenerationJob, Lesson, LessonView
from app.models.user import User
from app.schemas.lessons import JobOut, LessonOut, LessonResponse, SlideOut
from app.services.ai.explanation import STYLE_LABELS
from app.services.curriculum_service import student_medium
from app.services.progress_service import require_topic_access
from app.services.storage import get_storage
from app.services.streak_service import record_study

logger = logging.getLogger(__name__)

# First lesson of every topic is a story; "Not clear" then walks through the other styles.
STYLE_ROTATION: list[LessonStyle] = [
    LessonStyle.story,
    LessonStyle.analogy,
    LessonStyle.step_by_step,
    LessonStyle.real_life,
    LessonStyle.worked_example,
    LessonStyle.visual,
    LessonStyle.base,
]
DEFAULT_STYLE = STYLE_ROTATION[0]
PLAYABLE = (LessonStatus.audio_ready, LessonStatus.ready)
IN_FLIGHT = (LessonStatus.pending, LessonStatus.generating)


def student_language(user: User) -> LessonLanguage:
    """Preferred explanation language; defaults to the textbook medium."""
    if user.lesson_language:
        return LessonLanguage(user.lesson_language)
    return LessonLanguage(student_medium(user).value)


# --- serialisation --------------------------------------------------------------------------


def _slides(lesson: Lesson) -> list[SlideOut]:
    raw: Any = lesson.slides_json
    items = raw.get("slides", []) if isinstance(raw, dict) else raw or []
    storage = get_storage()
    slides: list[SlideOut] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        slide = SlideOut.model_validate(item)
        image_key = item.get("imageKey")
        if isinstance(image_key, str) and image_key:
            slide.image_url = storage.signed_url(image_key)
        slides.append(slide)
    return slides


def lesson_out(lesson: Lesson) -> LessonOut:
    """Serialise a playable lesson with short-lived media URLs."""
    storage = get_storage()
    style = LessonStyle(lesson.style)
    return LessonOut(
        id=lesson.id,
        topic_id=lesson.topic_id,
        medium=Medium(lesson.medium),
        language=LessonLanguage(lesson.language),
        style=style,
        style_label=STYLE_LABELS[style],
        title=lesson.title or "",
        summary=lesson.summary or "",
        slides=_slides(lesson),
        audio_url=storage.signed_url(lesson.audio_key) if lesson.audio_key else None,
        video_url=storage.signed_url(lesson.video_key) if lesson.video_key else None,
        duration_sec=lesson.duration_sec,
        status=LessonStatus(lesson.status),
    )


def job_out(job: GenerationJob) -> JobOut:
    """Serialise a job; includes the lesson once it is playable."""
    lesson = job.lesson
    style = LessonStyle(job.requested_style) if job.requested_style else None
    return JobOut(
        id=job.id,
        status=JobStatus(job.status),
        style=style,
        style_label=STYLE_LABELS[style] if style else None,
        error=job.error,
        lesson=lesson_out(lesson) if lesson and lesson.status in PLAYABLE else None,
    )


def _ready(lesson: Lesson) -> LessonResponse:
    return LessonResponse(state="ready", lesson=lesson_out(lesson))


def _generating(job: GenerationJob) -> LessonResponse:
    return LessonResponse(state="generating", job=job_out(job))


# --- lookup helpers -------------------------------------------------------------------------


def _find_lesson(
    db: Session,
    topic_id: int,
    language: LessonLanguage,
    style: LessonStyle,
    statuses: tuple[LessonStatus, ...],
) -> Lesson | None:
    return db.scalar(
        select(Lesson)
        .where(
            Lesson.topic_id == topic_id,
            Lesson.language == language,
            Lesson.style == style,
            Lesson.status.in_(statuses),
            Lesson.is_flagged.is_(False),
        )
        .order_by(  # uploaded (admin) lessons before AI ones, then newest first
            case((Lesson.source == LessonSource.uploaded, 0), else_=1), Lesson.id.desc()
        )
        .limit(1)
    )


def _job_for_lesson(db: Session, lesson: Lesson) -> GenerationJob | None:
    return db.scalar(
        select(GenerationJob)
        .where(GenerationJob.lesson_id == lesson.id)
        .order_by(GenerationJob.id.desc())
        .limit(1)
    )


def _viewed_styles(db: Session, user: User, topic_id: int) -> dict[LessonStyle, datetime]:
    """Styles this student has opened for the topic → last time viewed."""
    rows = db.execute(
        select(Lesson.style, func.max(LessonView.updated_at))
        .join(LessonView, LessonView.lesson_id == Lesson.id)
        .where(LessonView.user_id == user.id, Lesson.topic_id == topic_id)
        .group_by(Lesson.style)
    ).all()
    return {LessonStyle(style): seen for style, seen in rows}


def choose_next_style(
    viewed: dict[LessonStyle, datetime], current: LessonStyle | None
) -> LessonStyle:
    """First rotation style not yet seen; once all are seen, the least recently seen (≠ current)."""
    for style in STYLE_ROTATION:
        if style not in viewed and style != current:
            return style
    candidates = [s for s in STYLE_ROTATION if s != current] or STYLE_ROTATION
    epoch = datetime.min.replace(tzinfo=UTC)
    return min(candidates, key=lambda s: _aware(viewed.get(s, epoch)))


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _generations_today(db: Session, user: User) -> int:
    since = datetime.now(UTC) - timedelta(days=1)
    return (
        db.scalar(
            select(func.count(GenerationJob.id)).where(
                GenerationJob.user_id == user.id,
                GenerationJob.kind == JobKind.explanation,
                GenerationJob.requested_style != DEFAULT_STYLE,
                GenerationJob.created_at >= since,
            )
        )
        or 0
    )


def _queue_generation(
    db: Session, user: User, topic: Topic, language: LessonLanguage, style: LessonStyle
) -> GenerationJob:
    """Create (pending lesson + queued job) and dispatch it."""
    lesson = Lesson(
        topic_id=topic.id,
        medium=student_medium(user),
        language=language,
        style=style,
        source=LessonSource.ai_generated,
        status=LessonStatus.pending,
    )
    db.add(lesson)
    db.flush()
    job = GenerationJob(
        user_id=user.id,
        topic_id=topic.id,
        medium=student_medium(user),
        requested_style=style,
        kind=JobKind.explanation,
        status=JobStatus.queued,
        lesson_id=lesson.id,
    )
    db.add(job)
    db.commit()

    from app.workers.tasks import dispatch_explanation_job

    dispatch_explanation_job(job.id)
    db.refresh(job)
    return job


def _lesson_or_job(
    db: Session, user: User, topic: Topic, language: LessonLanguage, style: LessonStyle
) -> LessonResponse:
    """Cached playable lesson, else the in-flight job, else a newly queued job."""
    cached = _find_lesson(db, topic.id, language, style, PLAYABLE)
    if cached is not None:
        return _ready(cached)
    in_flight = _find_lesson(db, topic.id, language, style, IN_FLIGHT)
    if in_flight is not None:
        job = _job_for_lesson(db, in_flight)
        if job is not None and job.status in (JobStatus.queued, JobStatus.running):
            return _generating(job)
    if (
        style != DEFAULT_STYLE
        and _generations_today(db, user) >= settings.AI_GENERATIONS_PER_USER_PER_DAY
    ):
        raise RateLimitedError(
            "You have asked for many new explanations today. Please try again tomorrow, "
            "or ask your teacher.",
            code="generation_limit",
        )
    return _generating(_queue_generation(db, user, topic, language, style))


# --- public API -----------------------------------------------------------------------------


def open_lesson(db: Session, user: User, topic_id: int) -> LessonResponse:
    """The lesson to show when a student opens a topic.

    The style they watched most recently (if still playable), else a teacher-uploaded
    lesson, else the story lesson.
    """
    topic, _ = require_topic_access(db, user, topic_id)
    language = student_language(user)
    last_seen = db.scalar(
        select(Lesson)
        .join(LessonView, LessonView.lesson_id == Lesson.id)
        .where(
            LessonView.user_id == user.id,
            Lesson.topic_id == topic.id,
            Lesson.language == language,
            Lesson.status.in_(PLAYABLE),
            Lesson.is_flagged.is_(False),
        )
        .order_by(LessonView.updated_at.desc())
        .limit(1)
    )
    if last_seen is not None:
        return _ready(last_seen)
    uploaded = db.scalar(  # a teacher's own lesson comes first, whatever its style
        select(Lesson)
        .where(
            Lesson.topic_id == topic.id,
            Lesson.language == language,
            Lesson.source == LessonSource.uploaded,
            Lesson.status.in_(PLAYABLE),
            Lesson.is_flagged.is_(False),
        )
        .order_by(case((Lesson.style == DEFAULT_STYLE, 0), else_=1), Lesson.id.desc())
        .limit(1)
    )
    if uploaded is not None:
        return _ready(uploaded)
    return _lesson_or_job(db, user, topic, language, DEFAULT_STYLE)


def choose_style(db: Session, user: User, topic_id: int, style: LessonStyle) -> LessonResponse:
    """The student picked an explanation style: cached lesson, or start generating it."""
    topic, _ = require_topic_access(db, user, topic_id)
    return _lesson_or_job(db, user, topic, student_language(user), style)


def choose_language(
    db: Session, user: User, topic_id: int, language: LessonLanguage, style: LessonStyle | None
) -> LessonResponse:
    """Switch the explanation language (remembered for next lessons) and return that lesson."""
    topic, _ = require_topic_access(db, user, topic_id)
    user.lesson_language = language
    db.commit()
    return _lesson_or_job(db, user, topic, language, style or DEFAULT_STYLE)


def not_clear(
    db: Session, user: User, topic_id: int, lesson_id: int | None, note: str | None
) -> LessonResponse:
    """Record "Not clear" and return (or start generating) an explanation in a new style."""
    topic, _ = require_topic_access(db, user, topic_id)
    language = student_language(user)
    current = db.get(Lesson, lesson_id) if lesson_id else None
    if current is not None and current.topic_id != topic.id:
        current = None
    db.add(
        ClarityFeedback(
            user_id=user.id,
            topic_id=topic.id,
            lesson_id=current.id if current else None,
            is_clear=False,
            note=note.strip() if note else None,
        )
    )
    db.commit()
    style = choose_next_style(
        _viewed_styles(db, user, topic.id), LessonStyle(current.style) if current else None
    )
    logger.info("Not clear user_id=%s topic_id=%s -> style=%s", user.id, topic.id, style)
    return _lesson_or_job(db, user, topic, language, style)


def mark_clear(db: Session, user: User, topic_id: int, lesson_id: int) -> None:
    """Record that the student understood the lesson."""
    topic, _ = require_topic_access(db, user, topic_id)
    lesson = db.get(Lesson, lesson_id)
    if lesson is None or lesson.topic_id != topic.id:
        raise NotFoundError("Lesson not found")
    db.add(ClarityFeedback(user_id=user.id, topic_id=topic.id, lesson_id=lesson.id, is_clear=True))
    db.commit()


def get_job(db: Session, user: User, job_id: int) -> JobOut:
    """A job the student started (or a shared job for a topic they can open)."""
    job = db.get(GenerationJob, job_id)
    if job is None or job.kind != JobKind.explanation:
        raise NotFoundError("Job not found")
    if job.user_id != user.id:
        require_topic_access(db, user, job.topic_id)  # shared in-flight job for the same topic
    db.refresh(job)
    return job_out(job)


def record_progress(
    db: Session, user: User, lesson_id: int, watched_sec: int, completed: bool
) -> None:
    """Upsert the student's watch progress (never decreases)."""
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise NotFoundError("Lesson not found")
    require_topic_access(db, user, lesson.topic_id)
    view = db.scalar(
        select(LessonView).where(LessonView.user_id == user.id, LessonView.lesson_id == lesson.id)
    )
    if view is None:
        view = LessonView(user_id=user.id, lesson_id=lesson.id, watched_sec=0, completed=False)
        db.add(view)
    view.watched_sec = max(view.watched_sec or 0, watched_sec)
    view.completed = bool(view.completed) or completed
    view.updated_at = datetime.now(UTC)
    record_study(db, user)
    db.commit()
