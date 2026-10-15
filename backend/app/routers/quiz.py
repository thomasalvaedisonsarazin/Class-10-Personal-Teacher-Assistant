"""Quiz endpoints: start a fresh attempt, submit for server-side grading."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request, status

from app.dependencies import DbSession, StudentUser
from app.rate_limit import limiter
from app.schemas.quiz import QuizAttemptOut, QuizResultOut, SubmitAttemptRequest
from app.services import notification_service, quiz_service

router = APIRouter(prefix="/api/v1", tags=["quiz"])


@router.post(
    "/topics/{topic_id}/quiz-attempts",
    response_model=QuizAttemptOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/hour")
def start_quiz(request: Request, topic_id: int, db: DbSession, user: StudentUser) -> QuizAttemptOut:
    """Start (or resume) a test with never-seen questions. Answers are not included."""
    return quiz_service.start_attempt(db, user, topic_id)


@router.post("/quiz-attempts/{attempt_id}/submit", response_model=QuizResultOut)
def submit_quiz(
    attempt_id: int,
    body: SubmitAttemptRequest,
    background: BackgroundTasks,
    db: DbSession,
    user: StudentUser,
) -> QuizResultOut:
    """Grade the test; >= 60% completes the topic and unlocks the next one."""
    result = quiz_service.submit_attempt(db, user, attempt_id, body.answers)
    if result.passed:
        background.add_task(
            notification_service.notify_quiz_passed_in_background,
            user.id,
            result.topic_id,
            result.score_pct,
            (result.next_topic.id, result.next_topic.title) if result.next_topic else None,
        )
    return result
