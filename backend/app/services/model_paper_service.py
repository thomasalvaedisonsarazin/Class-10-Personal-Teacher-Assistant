"""Model question papers: AI writes them in the board pattern, AI marks photos of the answers.

Rules:
- Plan holders only to create a paper or have it marked (``require_exam_practice``);
  at most ``MODEL_PAPERS_PER_DAY`` new papers per student per 24 hours.
- The answer key and suggested answers are shown only after the student has
  submitted photos of their written answers (status ``grading`` or later).
- Photos are resized, stored privately under a random key, and deleted as soon as
  marking finishes (or fails).
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
)
from app.models.curriculum import Chapter, Subject
from app.models.enums import Medium
from app.models.exam import ModelPaper
from app.models.user import User
from app.schemas.exam import (
    AnswerKeyItemOut,
    CreateModelPaperRequest,
    ExamOverviewOut,
    ModelPaperOut,
    ModelPaperSummary,
    PaperHtmlOut,
    PaperPartOut,
    PaperQuestionOut,
    PartScoreOut,
    PatternInfo,
)
from app.services.ai.exam_grading import GradedAnswer, KeyItem, grade_script
from app.services.ai.exam_paper import (
    PaperContext,
    PaperGenerationError,
    PaperQuestion,
    SyllabusChapter,
    generate_paper,
)
from app.services.ai.llm import LLMError, get_llm_client
from app.services.billing_service import has_exam_practice, require_exam_practice
from app.services.curriculum_service import (
    chapter_title,
    student_medium,
    subject_name,
    topic_objectives,
    topic_title,
)
from app.services.exam_paper_html import key_html, paper_html
from app.services.exam_patterns import PATTERNS, is_language_subject, pattern_for
from app.services.progress_service import get_subject_for_student
from app.services.storage import StorageError, get_storage
from app.services.subject_test_service import completed_topic_ids, recent_subject_tests

logger = logging.getLogger(__name__)

SUBMITTED = ("grading", "graded", "grading_failed")
PHOTO_MAX_SIDE = 1800
PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
ENGLISH_SUBJECTS = {"english", "communicative english"}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def paper_language(user: User, subject: Subject) -> Medium:
    """English papers are in English, Tamil papers in Tamil; others follow the medium."""
    if subject.name.strip().casefold() in ENGLISH_SUBJECTS:
        return Medium.en
    return student_medium(user, subject)


# --- creating ------------------------------------------------------------------------------


def _chosen_chapters(subject: Subject, body: CreateModelPaperRequest) -> list[Chapter]:
    chapters = [c for c in subject.chapters if any(t.is_published for t in c.topics)]
    if body.scope == "full":
        return chapters
    wanted = set(body.chapter_ids)
    picked = [c for c in chapters if c.id in wanted]
    if not wanted or len(picked) != len(wanted):
        raise BadRequestError(
            "Choose one or more chapters of this subject", code="invalid_chapters"
        )
    return picked


def papers_left_today(db: Session, user: User) -> int:
    """How many more papers the student may create in the current 24 hours."""
    since = datetime.now(UTC) - timedelta(days=1)
    made = db.scalar(
        select(func.count(ModelPaper.id)).where(
            ModelPaper.user_id == user.id, ModelPaper.created_at >= since
        )
    )
    return max(0, settings.MODEL_PAPERS_PER_DAY - int(made or 0))


def create_model_paper(
    db: Session, user: User, subject_id: int, body: CreateModelPaperRequest
) -> ModelPaper:
    """Create a paper (status ``generating``); the caller dispatches the generation job.

    Raises:
        NotFoundError: not one of the student's subjects
        PlanRequiredError: no plan
        BadRequestError: unknown chapters (``invalid_chapters``)
        RateLimitedError: daily paper limit reached (``paper_limit``)
    """
    subject = get_subject_for_student(db, user, subject_id)
    require_exam_practice(db, user)
    if papers_left_today(db, user) <= 0:
        raise RateLimitedError(
            f"You can create {settings.MODEL_PAPERS_PER_DAY} model papers a day. "
            "Please try again tomorrow.",
            code="paper_limit",
        )
    chapters = _chosen_chapters(subject, body)
    if not chapters:
        raise BadRequestError("This subject has no lessons yet", code="invalid_chapters")
    language = paper_language(user, subject)
    pattern = pattern_for(subject.board.grade, subject.name, body.scope)
    paper = ModelPaper(
        user_id=user.id,
        subject_id=subject.id,
        scope=body.scope,
        chapter_ids=[c.id for c in chapters] if body.scope == "chapters" else [],
        medium=language,
        pattern_id=pattern.id,
        status="generating",
        total_marks=pattern.total_marks,
        duration_minutes=pattern.duration_minutes,
        paper={
            "header": {
                "board": subject.board.name,
                "grade": subject.board.grade,
                "subject": subject_name(subject, language),
                "scope": body.scope,
                "chapters": [chapter_title(c, language) for c in chapters]
                if body.scope == "chapters"
                else [],
                "total_marks": pattern.total_marks,
                "duration_minutes": pattern.duration_minutes,
            },
            "parts": [],
        },
        image_keys=[],
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    logger.info("Model paper %s queued user_id=%s pattern=%s", paper.id, user.id, pattern.id)
    return paper


def _paper_json(
    header: dict[str, Any], parts: list[list[PaperQuestion]], pattern_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split generated questions into the printed paper and the hidden answer key."""
    pattern = PATTERNS[pattern_id]
    printed: list[dict[str, Any]] = []
    key: dict[str, Any] = {}
    for spec, questions in zip(pattern.parts, parts, strict=True):
        printed.append(
            {
                "label": spec.label,
                "kind": spec.kind,
                "marks": spec.marks,
                "printed": spec.printed,
                "answer": spec.answer,
                "either_or": spec.either_or,
                "questions": [
                    {
                        "number": q.number,
                        "text": q.text,
                        "options": q.options,
                        "alt_text": q.alt_text,
                        "compulsory": q.compulsory,
                    }
                    for q in questions
                ],
            }
        )
        for q in questions:
            key[str(q.number)] = {
                "marks": spec.marks,
                "answer": q.answer,
                "points": q.points,
                "alt_answer": q.alt_answer,
                "alt_points": q.alt_points,
            }
    return {"header": header, "parts": printed}, {"answers": key}


def run_generation_job(paper_id: int) -> None:
    """Write the paper with the LLM (idempotent: only runs for ``generating`` papers)."""
    with SessionLocal() as db:
        paper = db.get(ModelPaper, paper_id)
        if paper is None or paper.status != "generating":
            return
        subject = db.get(Subject, paper.subject_id)
        if subject is None:
            paper.status = "generation_failed"
            db.commit()
            return
        language = Medium(paper.medium)
        wanted = set(paper.chapter_ids or [])
        chapters = [
            SyllabusChapter(
                title=chapter_title(c, language),
                topics=[
                    (topic_title(t, language), topic_objectives(t, language) or "")
                    for t in c.topics
                    if t.is_published
                ],
            )
            for c in subject.chapters
            if (not wanted or c.id in wanted) and any(t.is_published for t in c.topics)
        ]
        context = PaperContext(
            board=subject.board.name,
            grade=subject.board.grade,
            subject=subject_name(subject, language),
            language=language.value,
            chapters=chapters,
            language_subject=is_language_subject(subject.name),
            unit=paper.scope == "chapters",
        )
        try:
            parts = generate_paper(
                get_llm_client(),
                context,
                PATTERNS[paper.pattern_id],
                settings.CHECK_REASONING_EFFORT,
            )
        except (PaperGenerationError, LLMError) as exc:
            logger.warning("Model paper %s failed: %s", paper.id, exc)
            paper.status = "generation_failed"
            db.commit()
            return
        except Exception:
            logger.exception("Model paper %s crashed", paper.id)
            paper.status = "generation_failed"
            db.commit()
            return
        header = dict((paper.paper or {}).get("header", {}))
        paper.paper, paper.answer_key = _paper_json(header, parts, paper.pattern_id)
        paper.status = "ready"
        db.commit()
        logger.info("Model paper %s ready", paper.id)


# --- submitting answers --------------------------------------------------------------------


def _normalise_photo(data: bytes) -> bytes:
    """Validate an uploaded photo and re-encode it as a resized JPEG (drops EXIF / location)."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            rgb = img.convert("RGB")
            rgb.thumbnail((PHOTO_MAX_SIDE, PHOTO_MAX_SIDE))
            out = io.BytesIO()
            rgb.save(out, format="JPEG", quality=82, optimize=True)
            return out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise BadRequestError(
            "One of the photos could not be opened", code="invalid_photo"
        ) from exc


def _delete_photos(keys: list[Any]) -> None:
    storage = get_storage()
    for key in keys:
        try:
            storage.delete_object(str(key))
        except StorageError:
            logger.warning("Could not delete answer photo %s", key)


async def submit_answers(
    db: Session, user: User, paper_id: int, photos: list[UploadFile]
) -> ModelPaper:
    """Store the answer-sheet photos and mark the paper as submitted (key now visible).

    Raises:
        NotFoundError: not this student's paper
        ConflictError: paper not ready (``paper_not_ready``) or already submitted
        PlanRequiredError: no plan
        BadRequestError: no / too many / invalid photos
    """
    paper = _own_paper(db, user, paper_id)
    if paper.status in ("generating", "generation_failed"):
        raise ConflictError("This paper is not ready yet", code="paper_not_ready")
    if paper.status in ("grading", "graded"):
        raise ConflictError("Your answers were already submitted", code="already_submitted")
    require_exam_practice(db, user)
    if not photos:
        raise BadRequestError("Add photos of your answer sheets", code="no_photos")
    if len(photos) > settings.MODEL_PAPER_MAX_PHOTOS:
        raise BadRequestError(
            f"Upload at most {settings.MODEL_PAPER_MAX_PHOTOS} photos", code="too_many_photos"
        )
    images: list[bytes] = []
    for photo in photos:
        if photo.content_type and photo.content_type not in PHOTO_TYPES:
            raise BadRequestError("Upload photos (JPEG or PNG)", code="invalid_photo")
        data = await photo.read(settings.MODEL_PAPER_MAX_PHOTO_BYTES + 1)
        if len(data) > settings.MODEL_PAPER_MAX_PHOTO_BYTES:
            raise BadRequestError("One of the photos is too large", code="photo_too_large")
        images.append(_normalise_photo(data))

    _delete_photos(paper.image_keys or [])
    storage = get_storage()
    keys: list[str] = []
    for data in images:
        key = f"answer-sheets/{user.id}/{paper.id}/{uuid.uuid4().hex}.jpg"
        storage.put_object(key, data, "image/jpeg")
        keys.append(key)
    paper.image_keys = keys
    paper.status = "grading"
    paper.results = None
    paper.score = None
    paper.submitted_at = datetime.now(UTC)
    db.commit()
    db.refresh(paper)
    logger.info("Model paper %s submitted with %s photos", paper.id, len(keys))
    return paper


def score_paper(paper: dict[str, Any], answers: list[GradedAnswer]) -> dict[str, Any]:
    """Apply the paper's choice rules: in each part the best ``answer`` questions count."""
    by_number = {a.number: a for a in answers}
    parts: list[dict[str, Any]] = []
    score = 0.0
    for part in paper["parts"]:
        marks = sorted(
            (by_number[q["number"]].marks for q in part["questions"] if q["number"] in by_number),
            reverse=True,
        )
        scored = sum(marks[: part["answer"]])
        score += scored
        parts.append(
            {"label": part["label"], "scored": scored, "total": part["answer"] * part["marks"]}
        )
    return {
        "questions": {
            str(a.number): {
                "attempted": a.attempted,
                "choice": a.choice,
                "marks": a.marks,
                "feedback": a.feedback,
            }
            for a in answers
        },
        "parts": parts,
        "score": score,
    }


def _key_items(paper: ModelPaper) -> list[KeyItem]:
    keys = (paper.answer_key or {}).get("answers", {})
    items: list[KeyItem] = []
    for part in (paper.paper or {}).get("parts", []):
        for q in part["questions"]:
            key = keys.get(str(q["number"]), {})
            text = q["text"]
            if q.get("options"):
                text += " Options: " + " | ".join(q["options"])
            items.append(
                KeyItem(
                    number=q["number"],
                    marks=part["marks"],
                    text=text,
                    answer=key.get("answer", ""),
                    points=list(key.get("points", [])),
                    alt_text=q.get("alt_text"),
                    alt_answer=key.get("alt_answer"),
                    alt_points=tuple(key.get("alt_points", [])),
                )
            )
    return items


def run_grading_job(paper_id: int) -> None:
    """Mark the uploaded photos with the vision model, then delete the photos."""
    with SessionLocal() as db:
        paper = db.get(ModelPaper, paper_id)
        if paper is None or paper.status != "grading":
            return
        keys = list(paper.image_keys or [])
        subject = db.get(Subject, paper.subject_id)
        try:
            storage = get_storage()
            images = [(storage.get_object(str(k)), "image/jpeg") for k in keys]
            result = grade_script(
                get_llm_client(),
                subject.board.name if subject else "",
                subject.board.grade if subject else 10,
                (paper.paper or {}).get("header", {}).get("subject", ""),
                Medium(paper.medium).value,
                _key_items(paper),
                images,
                settings.GRADING_REASONING_EFFORT,
            )
        except (LLMError, StorageError) as exc:
            logger.warning("Marking failed for model paper %s: %s", paper.id, exc)
            paper.status = "grading_failed"
            paper.results = {"error": "failed"}
        except Exception:
            logger.exception("Marking crashed for model paper %s", paper.id)
            paper.status = "grading_failed"
            paper.results = {"error": "failed"}
        else:
            if not result.readable:
                paper.status = "grading_failed"
                paper.results = {"error": "unreadable"}
            else:
                results = score_paper(paper.paper or {"parts": []}, result.answers)
                results["feedback"] = result.overall_feedback
                paper.results = results
                paper.score = results["score"]
                paper.status = "graded"
                paper.graded_at = datetime.now(UTC)
        _delete_photos(keys)
        paper.image_keys = []
        db.commit()
        logger.info("Model paper %s marking finished: %s", paper.id, paper.status)


# --- reading -------------------------------------------------------------------------------


def _own_paper(db: Session, user: User, paper_id: int) -> ModelPaper:
    paper = db.get(ModelPaper, paper_id)
    if paper is None or paper.user_id != user.id:
        raise NotFoundError("Model paper not found")
    return paper


SCOPE_TITLE = {
    "en": {"full": "Full syllabus", "chapters": "Unit test"},
    "ta": {"full": "முழுப் பாடத்திட்டம்", "chapters": "அலகுத் தேர்வு"},
}


def _summary_fields(paper: ModelPaper) -> dict[str, Any]:
    header = (paper.paper or {}).get("header", {})
    scope_title = SCOPE_TITLE.get(Medium(paper.medium).value, SCOPE_TITLE["en"])[paper.scope]
    return {
        "id": paper.id,
        "subject_id": paper.subject_id,
        "title": f"{header.get('subject', '')} · {scope_title}",
        "scope": paper.scope,
        "chapter_ids": list(paper.chapter_ids or []),
        "status": paper.status,
        "total_marks": paper.total_marks,
        "duration_minutes": paper.duration_minutes,
        "score": paper.score,
        "created_at": _aware(paper.created_at),
    }


FAILURE_TEXT = {
    "en": {
        "failed": "We could not mark your answers. Please upload the photos again.",
        "unreadable": "We could not read the photos. Take clear, bright photos of every page "
        "and upload them again.",
    },
    "ta": {
        "failed": "உங்கள் விடைகளை மதிப்பிட முடியவில்லை. புகைப்படங்களை மீண்டும் பதிவேற்றவும்.",
        "unreadable": "புகைப்படங்களைப் படிக்க முடியவில்லை. ஒவ்வொரு பக்கத்தையும் வெளிச்சத்தில் "
        "தெளிவாகப் படம் எடுத்து மீண்டும் பதிவேற்றவும்.",
    },
}


def paper_out(paper: ModelPaper) -> ModelPaperOut:
    """The paper as the student may see it now (answer key only after submitting)."""
    content = paper.paper or {"parts": []}
    parts = [
        PaperPartOut(
            label=p["label"],
            kind=p["kind"],
            marks=p["marks"],
            printed=p["printed"],
            answer=p["answer"],
            either_or=p["either_or"],
            questions=[
                PaperQuestionOut(
                    number=q["number"],
                    text=q["text"],
                    options=list(q.get("options") or []),
                    alt_text=q.get("alt_text"),
                    compulsory=bool(q.get("compulsory")),
                )
                for q in p["questions"]
            ],
        )
        for p in content.get("parts", [])
    ]
    answer_key: list[AnswerKeyItemOut] | None = None
    part_scores: list[PartScoreOut] | None = None
    feedback: str | None = None
    results = paper.results or {}
    if paper.status in SUBMITTED and paper.answer_key:
        keys = paper.answer_key.get("answers", {})
        marked = results.get("questions", {})
        answer_key = []
        for part in parts:
            for q in part.questions:
                key = keys.get(str(q.number), {})
                mark = marked.get(str(q.number))
                answer_key.append(
                    AnswerKeyItemOut(
                        number=q.number,
                        max_marks=part.marks,
                        answer=key.get("answer", ""),
                        points=list(key.get("points", [])),
                        alt_answer=key.get("alt_answer"),
                        alt_points=list(key.get("alt_points", [])),
                        attempted=mark.get("attempted") if mark else None,
                        marks_awarded=mark.get("marks") if mark else None,
                        feedback=mark.get("feedback") if mark else None,
                    )
                )
    if paper.status == "graded":
        part_scores = [PartScoreOut(**p) for p in results.get("parts", [])]
        feedback = results.get("feedback")
    elif paper.status == "grading_failed":
        texts = FAILURE_TEXT.get(Medium(paper.medium).value, FAILURE_TEXT["en"])
        feedback = texts.get(str(results.get("error")), texts["failed"])
    return ModelPaperOut(
        **_summary_fields(paper),
        parts=parts,
        answer_key=answer_key,
        part_scores=part_scores,
        feedback=feedback,
        photos_submitted=len(paper.image_keys or []),
    )


def get_model_paper(db: Session, user: User, paper_id: int) -> ModelPaperOut:
    """One of the student's papers."""
    return paper_out(_own_paper(db, user, paper_id))


def list_model_papers(db: Session, user: User, subject_id: int) -> list[ModelPaperSummary]:
    """The student's papers for a subject, newest first."""
    rows = db.scalars(
        select(ModelPaper)
        .where(ModelPaper.user_id == user.id, ModelPaper.subject_id == subject_id)
        .order_by(ModelPaper.id.desc())
        .limit(30)
    ).all()
    return [ModelPaperSummary(**_summary_fields(p)) for p in rows]


def paper_document(db: Session, user: User, paper_id: int, kind: str) -> PaperHtmlOut:
    """Printable HTML of the question paper, or of the answer key once submitted.

    Raises:
        ConflictError: paper not ready (``paper_not_ready``)
        ForbiddenError: answer key before submitting (``key_locked``)
    """
    paper = _own_paper(db, user, paper_id)
    if paper.status in ("generating", "generation_failed") or not paper.paper:
        raise ConflictError("This paper is not ready yet", code="paper_not_ready")
    language = Medium(paper.medium).value
    subject = paper.paper["header"].get("subject", "paper").replace(" ", "-")
    if kind == "key":
        if paper.status not in SUBMITTED or not paper.answer_key:
            raise ForbiddenError(
                "Submit photos of your answers to see the answer key", code="key_locked"
            )
        html = key_html(
            paper.paper,
            paper.answer_key,
            paper.results if paper.status == "graded" else None,
            language,
        )
        return PaperHtmlOut(html=html, file_name=f"{subject}-answer-key-{paper.id}.pdf")
    return PaperHtmlOut(
        html=paper_html(paper.paper, language), file_name=f"{subject}-model-paper-{paper.id}.pdf"
    )


def exam_overview(db: Session, user: User, subject_id: int) -> ExamOverviewOut:
    """The subject's exam practice section: plan status, subject tests and model papers."""
    subject = get_subject_for_student(db, user, subject_id)
    full = pattern_for(subject.board.grade, subject.name, "full")
    unit = pattern_for(subject.board.grade, subject.name, "chapters")
    return ExamOverviewOut(
        subject_id=subject.id,
        plan_required=not has_exam_practice(db, user),
        completed_topics=len(completed_topic_ids(db, user, subject.id)),
        min_topics=settings.SUBJECT_TEST_MIN_TOPICS,
        recent_tests=recent_subject_tests(db, user, subject.id),
        papers=list_model_papers(db, user, subject.id),
        papers_left_today=papers_left_today(db, user),
        full_pattern=PatternInfo(
            total_marks=full.total_marks, duration_minutes=full.duration_minutes
        ),
        unit_pattern=PatternInfo(
            total_marks=unit.total_marks, duration_minutes=unit.duration_minutes
        ),
    )


def delete_user_papers(db: Session, user_id: int) -> None:
    """Remove a user's answer photos from storage (rows are deleted with the account)."""
    for keys in db.scalars(select(ModelPaper.image_keys).where(ModelPaper.user_id == user_id)):
        _delete_photos(list(keys or []))
