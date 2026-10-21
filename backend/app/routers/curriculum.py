"""Curriculum (boards, subjects, chapters, topics) endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.dependencies import CurrentUser, DbSession, StudentUser
from app.models.curriculum import Board
from app.schemas.curriculum import (
    BoardOut,
    SubjectChoice,
    SubjectDetail,
    SubjectSummary,
    TopicDetail,
)
from app.services import curriculum_service

router = APIRouter(prefix="/api/v1", tags=["curriculum"])


@router.get("/boards", response_model=list[BoardOut])
def list_boards(db: DbSession, user: CurrentUser) -> list[BoardOut]:
    """List the active classes of every board (onboarding board + class picker)."""
    boards = db.scalars(
        select(Board).where(Board.is_active.is_(True)).order_by(Board.family, Board.grade, Board.id)
    ).all()
    return [BoardOut.model_validate(b) for b in boards]


@router.get("/boards/{board_id}/subjects", response_model=list[SubjectChoice])
def list_board_subjects(board_id: int, db: DbSession, user: CurrentUser) -> list[SubjectChoice]:
    """Every subject of a class, for choosing a higher-secondary group's subjects."""
    return curriculum_service.board_subject_choices(db, user, board_id)


@router.get("/subjects", response_model=list[SubjectSummary])
def list_subjects(db: DbSession, user: StudentUser) -> list[SubjectSummary]:
    """All subjects with progress and the next topic to study (Home tiles)."""
    return curriculum_service.list_subjects(db, user)


@router.get("/subjects/{subject_id}", response_model=SubjectDetail)
def get_subject(subject_id: int, db: DbSession, user: StudentUser) -> SubjectDetail:
    """A subject's chapters with each topic's state (locked/available/active/completed)."""
    return curriculum_service.get_subject(db, user, subject_id)


@router.get("/topics/{topic_id}", response_model=TopicDetail)
def get_topic(topic_id: int, db: DbSession, user: StudentUser) -> TopicDetail:
    """Topic details; 403 ``topic_locked`` until the previous topic is passed."""
    return curriculum_service.get_topic_detail(db, user, topic_id)
