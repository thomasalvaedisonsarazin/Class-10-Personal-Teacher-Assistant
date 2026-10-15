"""Admin panel endpoints (role: admin)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.dependencies import AdminUser, DbSession
from app.models.enums import LessonLanguage, LessonStyle, Medium, UserRole
from app.schemas.admin import (
    AdminBoard,
    AdminLesson,
    AdminQuestion,
    AdminStats,
    AdminUserOut,
    AdminUserUpdate,
    ChapterCreate,
    ChapterUpdate,
    CurriculumImport,
    CurriculumTree,
    ImportResult,
    LessonFlagUpdate,
    QuestionCreate,
    QuestionUpdate,
    SubjectCreate,
    SubjectUpdate,
    TopicCreate,
    TopicUpdate,
)
from app.schemas.common import Message, Page
from app.services import admin_curriculum_service as curriculum
from app.services import admin_service

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get("/stats", response_model=AdminStats)
def get_stats(db: DbSession, _: AdminUser) -> AdminStats:
    """Dashboard numbers."""
    return admin_service.stats(db)


# --- curriculum -----------------------------------------------------------------------------


@router.get("/boards", response_model=list[AdminBoard])
def list_boards(db: DbSession, _: AdminUser) -> list[AdminBoard]:
    """All boards."""
    return curriculum.list_boards(db)


@router.get("/boards/{board_id}/curriculum", response_model=CurriculumTree)
def get_curriculum(board_id: int, db: DbSession, _: AdminUser) -> CurriculumTree:
    """Full syllabus tree (including unpublished topics)."""
    return curriculum.curriculum_tree(db, board_id)


@router.post("/curriculum/import", response_model=ImportResult)
def import_curriculum(body: CurriculumImport, db: DbSession, _: AdminUser) -> ImportResult:
    """Bulk create/update the syllabus from JSON (matched by display order)."""
    return curriculum.import_curriculum(db, body)


@router.post("/subjects", response_model=Message, status_code=status.HTTP_201_CREATED)
def create_subject(body: SubjectCreate, db: DbSession, _: AdminUser) -> Message:
    """Add a subject."""
    subject = curriculum.create_subject(db, body)
    return Message(message=f"Subject {subject.id} created")


@router.patch("/subjects/{subject_id}", response_model=Message)
def update_subject(subject_id: int, body: SubjectUpdate, db: DbSession, _: AdminUser) -> Message:
    """Edit a subject."""
    curriculum.update_subject(db, subject_id, body)
    return Message(message="Saved")


@router.post("/chapters", response_model=Message, status_code=status.HTTP_201_CREATED)
def create_chapter(body: ChapterCreate, db: DbSession, _: AdminUser) -> Message:
    """Add a chapter."""
    chapter = curriculum.create_chapter(db, body)
    return Message(message=f"Chapter {chapter.id} created")


@router.patch("/chapters/{chapter_id}", response_model=Message)
def update_chapter(chapter_id: int, body: ChapterUpdate, db: DbSession, _: AdminUser) -> Message:
    """Edit a chapter."""
    curriculum.update_chapter(db, chapter_id, body)
    return Message(message="Saved")


@router.post("/topics", response_model=Message, status_code=status.HTTP_201_CREATED)
def create_topic(body: TopicCreate, db: DbSession, _: AdminUser) -> Message:
    """Add a topic."""
    topic = curriculum.create_topic(db, body)
    return Message(message=f"Topic {topic.id} created")


@router.patch("/topics/{topic_id}", response_model=Message)
def update_topic(topic_id: int, body: TopicUpdate, db: DbSession, _: AdminUser) -> Message:
    """Edit a topic (title, objectives, Tamil text, order, published)."""
    curriculum.update_topic(db, topic_id, body)
    return Message(message="Saved")


# --- lessons --------------------------------------------------------------------------------


@router.get("/lessons", response_model=Page[AdminLesson])
def list_lessons(
    db: DbSession,
    _: AdminUser,
    topic_id: Annotated[int | None, Query(alias="topicId", gt=0)] = None,
    flagged: bool | None = None,
    page: PageNo = 1,
    size: PageSize = 20,
) -> Page[AdminLesson]:
    """Lessons for review."""
    return admin_service.list_lessons(db, topic_id=topic_id, flagged=flagged, page=page, size=size)


@router.patch("/lessons/{lesson_id}", response_model=AdminLesson)
def flag_lesson(lesson_id: int, body: LessonFlagUpdate, db: DbSession, _: AdminUser) -> AdminLesson:
    """Flag (hide) or restore a lesson."""
    return admin_service.set_lesson_flag(db, lesson_id, body.is_flagged)


@router.post(
    "/topics/{topic_id}/lessons", response_model=AdminLesson, status_code=status.HTTP_201_CREATED
)
async def upload_lesson(
    topic_id: int,
    db: DbSession,
    _: AdminUser,
    file: Annotated[UploadFile, File(description="MP4 video or MP3 audio")],
    medium: Annotated[Medium, Form()],
    language: Annotated[LessonLanguage | None, Form()] = None,
    style: Annotated[LessonStyle, Form()] = LessonStyle.story,
    title: Annotated[str, Form(max_length=255)] = "",
) -> AdminLesson:
    """Upload your own lesson; students get it before AI lessons of the same style."""
    data = await file.read(admin_service.MAX_UPLOAD_BYTES + 1)
    return admin_service.upload_lesson(
        db,
        topic_id=topic_id,
        medium=medium,
        language=language,
        style=style,
        title=title,
        content_type=file.content_type or "",
        data=data,
    )


# --- questions ------------------------------------------------------------------------------


@router.get("/questions", response_model=Page[AdminQuestion])
def list_questions(
    db: DbSession,
    _: AdminUser,
    topic_id: Annotated[int | None, Query(alias="topicId", gt=0)] = None,
    medium: Medium | None = None,
    flagged: bool | None = None,
    approved: bool | None = None,
    page: PageNo = 1,
    size: PageSize = 20,
) -> Page[AdminQuestion]:
    """Questions for review."""
    return admin_service.list_questions(
        db,
        topic_id=topic_id,
        medium=medium,
        flagged=flagged,
        approved=approved,
        page=page,
        size=size,
    )


@router.post("/questions", response_model=AdminQuestion, status_code=status.HTTP_201_CREATED)
def create_question(body: QuestionCreate, db: DbSession, _: AdminUser) -> AdminQuestion:
    """Write a question yourself (approved immediately)."""
    return admin_service.create_question(db, body)


@router.patch("/questions/{question_id}", response_model=AdminQuestion)
def update_question(
    question_id: int, body: QuestionUpdate, db: DbSession, _: AdminUser
) -> AdminQuestion:
    """Approve, flag or edit a question."""
    return admin_service.update_question(db, question_id, body)


# --- users ----------------------------------------------------------------------------------


@router.get("/users", response_model=Page[AdminUserOut])
def list_users(
    db: DbSession,
    _: AdminUser,
    role: UserRole | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: PageNo = 1,
    size: PageSize = 20,
) -> Page[AdminUserOut]:
    """Search users."""
    return admin_service.list_users(db, role=role, q=q, page=page, size=size)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: int, body: AdminUserUpdate, db: DbSession, admin: AdminUser
) -> AdminUserOut:
    """Change role or enable/disable a user."""
    return admin_service.update_user(db, admin, user_id, body)
