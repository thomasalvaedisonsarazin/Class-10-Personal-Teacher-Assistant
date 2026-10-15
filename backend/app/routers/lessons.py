"""Lesson endpoints: open lesson, "Not clear" re-explanations, jobs, watch progress."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.dependencies import DbSession, StudentUser
from app.schemas.lessons import (
    ChooseLanguageRequest,
    ChooseStyleRequest,
    ClearRequest,
    JobOut,
    LessonProgressRequest,
    LessonResponse,
    NotClearRequest,
)
from app.services import learning_service

router = APIRouter(prefix="/api/v1", tags=["lessons"])

_RESPONSES: dict[int | str, dict[str, object]] = {
    202: {"model": LessonResponse, "description": "Lesson is being generated; poll the job"}
}


def _with_status(result: LessonResponse, response: Response) -> LessonResponse:
    response.status_code = (
        status.HTTP_200_OK if result.state == "ready" else status.HTTP_202_ACCEPTED
    )
    return result


@router.get("/topics/{topic_id}/lesson", response_model=LessonResponse, responses=_RESPONSES)
def open_lesson(
    topic_id: int, response: Response, db: DbSession, user: StudentUser
) -> LessonResponse:
    """200 with the lesson to play, or 202 with a generation job (403 if locked)."""
    return _with_status(learning_service.open_lesson(db, user, topic_id), response)


@router.post("/topics/{topic_id}/not-clear", response_model=LessonResponse, responses=_RESPONSES)
def not_clear(
    topic_id: int, body: NotClearRequest, response: Response, db: DbSession, user: StudentUser
) -> LessonResponse:
    """Explain again in a style the student has not seen: 200 cached, 202 generating, 429 limit."""
    return _with_status(
        learning_service.not_clear(db, user, topic_id, body.lesson_id, body.note), response
    )


@router.post("/topics/{topic_id}/lesson-style", response_model=LessonResponse, responses=_RESPONSES)
def choose_style(
    topic_id: int, body: ChooseStyleRequest, response: Response, db: DbSession, user: StudentUser
) -> LessonResponse:
    """Explain in the style the student picked: 200 cached, 202 generating, 429 limit."""
    return _with_status(learning_service.choose_style(db, user, topic_id, body.style), response)


@router.post(
    "/topics/{topic_id}/lesson-language", response_model=LessonResponse, responses=_RESPONSES
)
def choose_language(
    topic_id: int,
    body: ChooseLanguageRequest,
    response: Response,
    db: DbSession,
    user: StudentUser,
) -> LessonResponse:
    """Explain in English, Tamil or Tanglish (remembered as the student's preference)."""
    return _with_status(
        learning_service.choose_language(db, user, topic_id, body.language, body.style), response
    )


@router.post("/topics/{topic_id}/clear", status_code=status.HTTP_204_NO_CONTENT)
def mark_clear(topic_id: int, body: ClearRequest, db: DbSession, user: StudentUser) -> Response:
    """Record that the lesson was clear."""
    learning_service.mark_clear(db, user, topic_id, body.lesson_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: DbSession, user: StudentUser) -> JobOut:
    """Poll a generation job; includes the lesson once audio is ready."""
    return learning_service.get_job(db, user, job_id)


@router.put("/lessons/{lesson_id}/progress", status_code=status.HTTP_204_NO_CONTENT)
def lesson_progress(
    lesson_id: int, body: LessonProgressRequest, db: DbSession, user: StudentUser
) -> Response:
    """Save how far the student watched/listened."""
    learning_service.record_progress(db, user, lesson_id, body.watched_sec, body.completed)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
