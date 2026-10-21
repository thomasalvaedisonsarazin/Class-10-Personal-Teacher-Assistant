"""Admin: dashboard stats, lesson review/upload, question review, user management."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.curriculum import Subject, Topic
from app.models.enums import (
    JobKind,
    JobStatus,
    LessonLanguage,
    LessonSource,
    LessonStatus,
    LessonStyle,
    Medium,
    QuestionSource,
    UserRole,
)
from app.models.lesson import GenerationJob, Lesson, LessonView
from app.models.quiz import Question, QuizAttempt
from app.models.user import User
from app.schemas.admin import (
    AdminLesson,
    AdminQuestion,
    AdminStats,
    AdminUserOut,
    AdminUserUpdate,
    QuestionCreate,
    QuestionUpdate,
)
from app.schemas.common import Page
from app.services import auth_service
from app.services.ai.questions import GeneratedQuestion, validate_question
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

UPLOAD_TYPES = {
    "video/mp4": ("video", "mp4"),
    "audio/mpeg": ("audio", "mp3"),
    "audio/mp3": ("audio", "mp3"),
}
MAX_UPLOAD_BYTES = 150 * 1024 * 1024


def _looks_like(kind: str, data: bytes) -> bool:
    """Check the file's real format (magic bytes), not the client's claimed type."""
    if kind == "video":
        return len(data) > 12 and data[4:8] == b"ftyp"  # ISO base media (MP4)
    return data[:3] == b"ID3" or (len(data) > 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0)


def _since(days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


def _count(db: Session, query: object) -> int:
    return int(db.scalar(query) or 0)  # type: ignore[call-overload]


# --- stats ----------------------------------------------------------------------------------


def stats(db: Session) -> AdminStats:
    """Headline numbers for the dashboard."""
    week = _since(7)
    attempts = db.execute(
        select(
            func.count(QuizAttempt.id),
            func.count(QuizAttempt.id).filter(QuizAttempt.passed.is_(True)),
        ).where(QuizAttempt.submitted_at.is_not(None), QuizAttempt.submitted_at >= week)
    ).one()
    active = db.scalar(
        select(func.count(func.distinct(LessonView.user_id))).where(LessonView.updated_at >= week)
    )
    return AdminStats(
        students=_count(db, select(func.count(User.id)).where(User.role == UserRole.student)),
        active_students_week=int(active or 0),
        subjects=_count(db, select(func.count(Subject.id))),
        topics_published=_count(
            db, select(func.count(Topic.id)).where(Topic.is_published.is_(True))
        ),
        lessons_ready=_count(
            db,
            select(func.count(Lesson.id)).where(
                Lesson.status.in_((LessonStatus.audio_ready, LessonStatus.ready))
            ),
        ),
        lessons_flagged=_count(
            db, select(func.count(Lesson.id)).where(Lesson.is_flagged.is_(True))
        ),
        questions_approved=_count(
            db, select(func.count(Question.id)).where(Question.is_approved.is_(True))
        ),
        questions_flagged=_count(
            db, select(func.count(Question.id)).where(Question.is_flagged.is_(True))
        ),
        quiz_attempts_week=int(attempts[0]),
        pass_rate_week=round(attempts[1] * 100 / attempts[0], 1) if attempts[0] else None,
        generations_today=_count(
            db,
            select(func.count(GenerationJob.id)).where(
                GenerationJob.kind == JobKind.explanation, GenerationJob.created_at >= _since(1)
            ),
        ),
        failed_jobs_week=_count(
            db,
            select(func.count(GenerationJob.id)).where(
                GenerationJob.status == JobStatus.failed, GenerationJob.created_at >= week
            ),
        ),
    )


# --- lessons --------------------------------------------------------------------------------


def _lesson_out(lesson: Lesson, topic_title: str) -> AdminLesson:
    storage = get_storage()
    return AdminLesson(
        id=lesson.id,
        topic_id=lesson.topic_id,
        topic_title=topic_title,
        medium=Medium(lesson.medium),
        language=LessonLanguage(lesson.language),
        style=LessonStyle(lesson.style),
        source=LessonSource(lesson.source),
        title=lesson.title,
        status=LessonStatus(lesson.status),
        is_flagged=lesson.is_flagged,
        duration_sec=lesson.duration_sec,
        audio_url=storage.signed_url(lesson.audio_key) if lesson.audio_key else None,
        video_url=storage.signed_url(lesson.video_key) if lesson.video_key else None,
        created_at=lesson.created_at,
    )


def list_lessons(
    db: Session, *, topic_id: int | None, flagged: bool | None, page: int, size: int
) -> Page[AdminLesson]:
    """Lessons newest first, optionally filtered."""
    query = select(Lesson, Topic.title).join(Topic, Topic.id == Lesson.topic_id)
    if topic_id is not None:
        query = query.where(Lesson.topic_id == topic_id)
    if flagged is not None:
        query = query.where(Lesson.is_flagged.is_(flagged))
    total = _count(db, select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(Lesson.id.desc()).offset((page - 1) * size).limit(size)).all()
    return Page(
        items=[_lesson_out(lesson, title) for lesson, title in rows],
        total=total,
        page=page,
        size=size,
    )


def set_lesson_flag(db: Session, lesson_id: int, flagged: bool) -> AdminLesson:
    """Flag (hide from students) or restore a lesson."""
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise NotFoundError("Lesson not found")
    lesson.is_flagged = flagged
    db.commit()
    return _lesson_out(lesson, lesson.topic.title)


def upload_lesson(
    db: Session,
    *,
    topic_id: int,
    medium: Medium,
    language: LessonLanguage | None = None,
    style: LessonStyle,
    title: str,
    content_type: str,
    data: bytes,
) -> AdminLesson:
    """Store an admin-made video (MP4) or audio (MP3) lesson; preferred over AI lessons."""
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise NotFoundError("Topic not found")
    kind = UPLOAD_TYPES.get(content_type)
    if kind is None:
        raise BadRequestError("Upload an MP4 video or an MP3 audio file", code="unsupported_media")
    if not data:
        raise BadRequestError("The file is empty", code="empty_file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise BadRequestError("The file is larger than 150 MB", code="file_too_large")
    if not _looks_like(kind[0], data):
        raise BadRequestError(
            "This file is not a valid MP4 video or MP3 audio", code="unsupported_media"
        )
    lesson = Lesson(
        topic_id=topic.id,
        medium=medium,
        language=language or LessonLanguage(medium.value),
        style=style,
        source=LessonSource.uploaded,
        title=title.strip() or topic.title,
        summary="",
        slides_json={"slides": []},
        status=LessonStatus.pending,
    )
    db.add(lesson)
    db.flush()
    field, ext = kind
    key = f"lessons/{lesson.id}/uploaded.{ext}"
    get_storage().put_object(key, data, content_type)
    if field == "video":
        lesson.video_key = key
    else:
        lesson.audio_key = key
    lesson.status = LessonStatus.ready
    db.commit()
    logger.info("Uploaded lesson id=%s topic_id=%s (%s bytes)", lesson.id, topic.id, len(data))
    return _lesson_out(lesson, topic.title)


# --- questions ------------------------------------------------------------------------------


def list_questions(
    db: Session,
    *,
    topic_id: int | None,
    medium: Medium | None,
    flagged: bool | None,
    approved: bool | None,
    page: int,
    size: int,
) -> Page[AdminQuestion]:
    """Questions newest first, optionally filtered."""
    query = select(Question)
    if topic_id is not None:
        query = query.where(Question.topic_id == topic_id)
    if medium is not None:
        query = query.where(Question.medium == medium)
    if flagged is not None:
        query = query.where(Question.is_flagged.is_(flagged))
    if approved is not None:
        query = query.where(Question.is_approved.is_(approved))
    total = _count(db, select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(Question.id.desc()).offset((page - 1) * size).limit(size)
    ).all()
    return Page(
        items=[AdminQuestion.model_validate(q) for q in rows], total=total, page=page, size=size
    )


def _validated(
    type_: str, stem: str, options: list[str], correct: str, explanation: str, difficulty: int
) -> GeneratedQuestion:
    if type_ not in ("mcq", "true_false"):
        raise BadRequestError(
            "Only multiple-choice and true/false questions are supported", code="invalid_question"
        )
    raw = GeneratedQuestion(
        type=type_,  # type: ignore[arg-type]
        stem=stem,
        options=options,
        correct_answer=correct,
        explanation=explanation,
        difficulty=difficulty,
    )
    if validate_question(raw) is None:
        raise BadRequestError(
            "Check the question: MCQ needs 4 different options, true/false needs 2, and the "
            "correct answer must be exactly one of the options.",
            code="invalid_question",
        )
    return raw


def create_question(db: Session, data: QuestionCreate) -> AdminQuestion:
    """Add an admin-written (approved) question."""
    if db.get(Topic, data.topic_id) is None:
        raise NotFoundError("Topic not found")
    raw = _validated(
        data.type.value,
        data.stem,
        data.options,
        data.correct_answer,
        data.explanation,
        data.difficulty,
    )
    valid = validate_question(raw)
    assert valid is not None  # noqa: S101 - checked in _validated
    question = Question(
        topic_id=data.topic_id,
        medium=data.medium,
        type=valid.type,
        stem=valid.stem,
        options=valid.options,
        correct_answer=valid.correct_answer,
        explanation=valid.explanation,
        difficulty=valid.difficulty,
        source=QuestionSource.admin,
        is_approved=True,
        content_hash=valid.content_hash,
    )
    db.add(question)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "This question already exists for the topic", code="duplicate_question"
        ) from exc
    return AdminQuestion.model_validate(question)


def update_question(db: Session, question_id: int, data: QuestionUpdate) -> AdminQuestion:
    """Approve/flag or edit a question (edits are re-validated)."""
    question = db.get(Question, question_id)
    if question is None:
        raise NotFoundError("Question not found")
    if any(
        v is not None
        for v in (data.stem, data.options, data.correct_answer, data.explanation, data.difficulty)
    ):
        raw = _validated(
            question.type.value,
            data.stem if data.stem is not None else question.stem,
            data.options if data.options is not None else list(question.options or []),
            data.correct_answer if data.correct_answer is not None else question.correct_answer,
            data.explanation if data.explanation is not None else question.explanation,
            data.difficulty if data.difficulty is not None else question.difficulty,
        )
        valid = validate_question(raw)
        assert valid is not None  # noqa: S101 - checked in _validated
        question.stem, question.options = valid.stem, valid.options
        question.correct_answer, question.explanation = valid.correct_answer, valid.explanation
        question.difficulty, question.content_hash = valid.difficulty, valid.content_hash
    if data.is_approved is not None:
        question.is_approved = data.is_approved
    if data.is_flagged is not None:
        question.is_flagged = data.is_flagged
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "Another question with the same text exists", code="duplicate_question"
        ) from exc
    return AdminQuestion.model_validate(question)


# --- users ----------------------------------------------------------------------------------


def list_users(
    db: Session, *, role: UserRole | None, q: str | None, page: int, size: int
) -> Page[AdminUserOut]:
    """Users newest first; ``q`` matches email or name."""
    query = select(User)
    if role is not None:
        query = query.where(User.role == role)
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.where(
            or_(func.lower(User.email).like(like), func.lower(User.full_name).like(like))
        )
    total = _count(db, select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(User.id.desc()).offset((page - 1) * size).limit(size)).all()
    return Page(
        items=[AdminUserOut.model_validate(u) for u in rows], total=total, page=page, size=size
    )


def update_user(db: Session, admin: User, user_id: int, data: AdminUserUpdate) -> AdminUserOut:
    """Change a user's role or disable/enable them (never your own account)."""
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    if user.id == admin.id:
        raise ForbiddenError("You cannot change your own account here", code="self_update")
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.board_id is not None or data.subject_ids is not None:
        auth_service.set_class(db, user, data.board_id, data.subject_ids, by_admin=True)
    db.commit()
    logger.info(
        "Admin %s updated user %s role=%s active=%s", admin.id, user.id, user.role, user.is_active
    )
    return AdminUserOut.model_validate(user)
