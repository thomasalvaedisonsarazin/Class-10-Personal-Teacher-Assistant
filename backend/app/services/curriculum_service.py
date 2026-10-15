"""Student-facing curriculum views: localised names plus derived topic states."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import NotFoundError
from app.models.curriculum import Chapter, Subject, Topic
from app.models.enums import Medium
from app.models.user import User
from app.schemas.curriculum import (
    ChapterOut,
    CurrentTopic,
    SubjectDetail,
    SubjectRef,
    SubjectSummary,
    TopicDetail,
    TopicItem,
)
from app.services.ai.explanation import TopicContext
from app.services.progress_service import (
    TopicState,
    TopicStatusInfo,
    board_topic_statuses,
    require_topic_access,
)


def student_medium(user: User) -> Medium:
    """The medium to show content in (English until onboarding sets one)."""
    return Medium(user.medium) if user.medium else Medium.en


def subject_name(subject: Subject, medium: Medium) -> str:
    """Subject name in ``medium`` (falls back to the default name)."""
    return next((t.name for t in subject.translations if t.medium == medium), subject.name)


def chapter_title(chapter: Chapter, medium: Medium) -> str:
    """Chapter title in ``medium`` (falls back to the default title)."""
    return next((t.title for t in chapter.translations if t.medium == medium), chapter.title)


def topic_title(topic: Topic, medium: Medium) -> str:
    """Topic title in ``medium`` (falls back to the default title)."""
    return next((t.title for t in topic.translations if t.medium == medium), topic.title)


def topic_objectives(topic: Topic, medium: Medium) -> str:
    """Learning objectives in ``medium`` (falls back to the default text)."""
    return next(
        (
            t.learning_objectives
            for t in topic.translations
            if t.medium == medium and t.learning_objectives
        ),
        topic.learning_objectives,
    )


def _published_topics(subject: Subject) -> list[Topic]:
    return [topic for chapter in subject.chapters for topic in chapter.topics if topic.is_published]


def _summary_fields(
    subject: Subject, statuses: dict[int, TopicStatusInfo], medium: Medium
) -> dict[str, object]:
    topics = [t for t in _published_topics(subject) if t.id in statuses]
    current = next(
        (t for t in topics if statuses[t.id].state in (TopicState.available, TopicState.active)),
        None,
    )
    return {
        "id": subject.id,
        "name": subject_name(subject, medium),
        "tile_color": subject.tile_color,
        "icon": subject.icon,
        "total_topics": len(topics),
        "completed_topics": sum(1 for t in topics if statuses[t.id].state == TopicState.completed),
        "current_topic": (
            CurrentTopic(
                id=current.id,
                title=topic_title(current, medium),
                status=statuses[current.id].state,
            )
            if current
            else None
        ),
    }


def list_subjects(db: Session, user: User) -> list[SubjectSummary]:
    """All subjects on the student's board with progress (Home tiles)."""
    statuses = board_topic_statuses(db, user)
    subjects = db.scalars(
        select(Subject).where(Subject.board_id == user.board_id).order_by(Subject.display_order)
    ).all()
    medium = student_medium(user)
    return [SubjectSummary.model_validate(_summary_fields(s, statuses, medium)) for s in subjects]


def get_subject(db: Session, user: User, subject_id: int) -> SubjectDetail:
    """One subject with chapters and every topic's state."""
    subject = db.get(Subject, subject_id)
    if subject is None or subject.board_id != user.board_id:
        raise NotFoundError("Subject not found")
    statuses = board_topic_statuses(db, user, subject_id=subject.id)
    medium = student_medium(user)
    chapters = [
        ChapterOut(
            id=chapter.id,
            title=chapter_title(chapter, medium),
            topics=[
                TopicItem(
                    id=topic.id,
                    title=topic_title(topic, medium),
                    status=statuses[topic.id].state,
                    best_score_pct=statuses[topic.id].best_score_pct,
                )
                for topic in chapter.topics
                if topic.id in statuses
            ],
        )
        for chapter in subject.chapters
    ]
    return SubjectDetail.model_validate(
        {
            **_summary_fields(subject, statuses, medium),
            "chapters": [c for c in chapters if c.topics],
        }
    )


def get_topic_detail(db: Session, user: User, topic_id: int) -> TopicDetail:
    """Topic screen data; raises 403 for locked topics."""
    topic, status = require_topic_access(db, user, topic_id)
    medium = student_medium(user)
    subject = topic.chapter.subject
    return TopicDetail(
        id=topic.id,
        title=topic_title(topic, medium),
        learning_objectives=topic_objectives(topic, medium),
        status=status.state,
        best_score_pct=status.best_score_pct,
        chapter_title=chapter_title(topic.chapter, medium),
        subject=SubjectRef(
            id=subject.id, name=subject_name(subject, medium), tile_color=subject.tile_color
        ),
        pass_pct=settings.QUIZ_PASS_PCT,
    )


def topic_context(topic: Topic, medium: Medium) -> TopicContext:
    """Prompt context for AI generation, localised to ``medium``."""
    chapter = topic.chapter
    subject = chapter.subject
    return TopicContext(
        board=subject.board.name,
        subject=subject_name(subject, medium),
        chapter=chapter_title(chapter, medium),
        topic=topic_title(topic, medium),
        learning_objectives=topic_objectives(topic, medium),
    )
