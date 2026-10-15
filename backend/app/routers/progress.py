"""Progress endpoints: starting topics (unlocking happens via quiz grading)."""

from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import DbSession, StudentUser
from app.schemas.curriculum import TopicItem
from app.services import progress_service, streak_service
from app.services.curriculum_service import student_medium, topic_title

router = APIRouter(prefix="/api/v1", tags=["progress"])


@router.get("/streak", response_model=streak_service.StreakOut)
def my_streak(db: DbSession, user: StudentUser) -> streak_service.StreakOut:
    """Study streak for the Home screen."""
    return streak_service.get_streak(db, user)


@router.post("/topics/{topic_id}/start", response_model=TopicItem)
def start_topic(topic_id: int, db: DbSession, user: StudentUser) -> TopicItem:
    """Mark an open topic as started (idempotent); 403 ``topic_locked`` if locked."""
    status = progress_service.start_topic(db, user, topic_id)
    topic = progress_service.get_topic_for_student(db, user, topic_id)
    return TopicItem(
        id=topic.id,
        title=topic_title(topic, student_medium(user)),
        status=status.state,
        best_score_pct=status.best_score_pct,
    )
