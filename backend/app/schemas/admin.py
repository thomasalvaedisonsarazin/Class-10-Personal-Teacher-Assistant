"""Admin panel schemas (camelCase on the wire)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.models.enums import (
    LessonLanguage,
    LessonSource,
    LessonStatus,
    LessonStyle,
    Medium,
    QuestionSource,
    QuestionType,
    UserRole,
)
from app.schemas.common import CamelModel, ORMModel

# Must match mobile/src/theme/palette.ts subjectColors (flat focus palette).
APPROVED_TILE_COLORS = ("#3B6EA5", "#4F8A6B", "#3E8C8C", "#7A6A9E", "#B0745A", "#5C7A99")


def _tile_color(value: str | None) -> str | None:
    if value is None:
        return None
    upper = value.strip().upper()
    if upper not in APPROVED_TILE_COLORS:
        raise ValueError(f"tileColor must be one of {', '.join(APPROVED_TILE_COLORS)}")
    return upper


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("Cannot be empty")
    return value


# --- stats ---------------------------------------------------------------------------------


class AdminStats(CamelModel):
    """Dashboard numbers."""

    students: int
    active_students_week: int
    subjects: int
    topics_published: int
    lessons_ready: int
    lessons_flagged: int
    questions_approved: int
    questions_flagged: int
    quiz_attempts_week: int
    pass_rate_week: float | None
    generations_today: int
    failed_jobs_week: int


# --- curriculum ------------------------------------------------------------------------------


class AdminTopic(CamelModel):
    id: int
    title: str
    title_ta: str | None
    learning_objectives: str
    learning_objectives_ta: str | None
    display_order: int
    is_published: bool
    lesson_count: int
    question_count: int


class AdminChapter(CamelModel):
    id: int
    title: str
    title_ta: str | None
    display_order: int
    topics: list[AdminTopic]


class AdminSubject(CamelModel):
    id: int
    name: str
    name_ta: str | None
    tile_color: str
    icon: str
    display_order: int
    fixed_medium: Medium | None = None
    chapters: list[AdminChapter]


class AdminBoard(ORMModel):
    id: int
    code: str
    name: str
    is_active: bool
    family: str
    grade: int
    choose_subjects: bool


class BoardUpdate(CamelModel):
    """Show / hide a class to students, or rename it."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None


class CurriculumTree(CamelModel):
    board: AdminBoard
    subjects: list[AdminSubject]


class SubjectCreate(CamelModel):
    board_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=120)
    name_ta: str | None = Field(default=None, max_length=120)
    tile_color: str
    icon: str = Field(default="book-open-variant", min_length=1, max_length=64)
    display_order: int | None = Field(default=None, ge=0)

    @field_validator("tile_color")
    @classmethod
    def _check_color(cls, value: str | None) -> str | None:
        """Only approved flat palette colours."""
        return _tile_color(value)


class SubjectUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=120)
    name_ta: str | None = Field(default=None, max_length=120)
    tile_color: str | None = None
    icon: str | None = Field(default=None, max_length=64)
    display_order: int | None = Field(default=None, ge=0)
    # Language subject: "ta" = always in Tamil; "" = follow the student's medium.
    fixed_medium: Medium | Literal[""] | None = None

    @field_validator("tile_color")
    @classmethod
    def _check_color(cls, value: str | None) -> str | None:
        """Only approved flat palette colours."""
        return _tile_color(value)

    @field_validator("name", "icon")
    @classmethod
    def _not_blank(cls, value: str | None) -> str | None:
        """Trim; reject blank strings."""
        return _clean(value)


class ChapterCreate(CamelModel):
    subject_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    title_ta: str | None = Field(default=None, max_length=255)
    display_order: int | None = Field(default=None, ge=0)


class ChapterUpdate(CamelModel):
    title: str | None = Field(default=None, max_length=255)
    title_ta: str | None = Field(default=None, max_length=255)
    display_order: int | None = Field(default=None, ge=0)

    @field_validator("title")
    @classmethod
    def _not_blank(cls, value: str | None) -> str | None:
        """Trim; reject blank strings."""
        return _clean(value)


class TopicCreate(CamelModel):
    chapter_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    title_ta: str | None = Field(default=None, max_length=255)
    learning_objectives: str = Field(default="", max_length=4000)
    learning_objectives_ta: str | None = Field(default=None, max_length=4000)
    display_order: int | None = Field(default=None, ge=0)
    is_published: bool = False


class TopicUpdate(CamelModel):
    title: str | None = Field(default=None, max_length=255)
    title_ta: str | None = Field(default=None, max_length=255)
    learning_objectives: str | None = Field(default=None, max_length=4000)
    learning_objectives_ta: str | None = Field(default=None, max_length=4000)
    display_order: int | None = Field(default=None, ge=0)
    is_published: bool | None = None

    @field_validator("title")
    @classmethod
    def _not_blank(cls, value: str | None) -> str | None:
        """Trim; reject blank strings."""
        return _clean(value)


class ImportTopic(CamelModel):
    title: str = Field(min_length=1, max_length=255)
    title_ta: str | None = Field(default=None, max_length=255)
    learning_objectives: str = Field(default="", max_length=4000)
    learning_objectives_ta: str | None = Field(default=None, max_length=4000)
    display_order: int = Field(ge=0)
    is_published: bool = True


class ImportChapter(CamelModel):
    title: str = Field(min_length=1, max_length=255)
    title_ta: str | None = Field(default=None, max_length=255)
    display_order: int = Field(ge=0)
    topics: list[ImportTopic] = Field(default_factory=list, max_length=200)


class ImportSubject(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    name_ta: str | None = Field(default=None, max_length=120)
    tile_color: str
    icon: str = Field(default="book-open-variant", max_length=64)
    display_order: int = Field(ge=0)
    # Language subject studied only in this language (Tamil = "ta"), whatever the medium.
    fixed_medium: Medium | None = None
    chapters: list[ImportChapter] = Field(default_factory=list, max_length=100)

    @field_validator("tile_color")
    @classmethod
    def _check_color(cls, value: str | None) -> str | None:
        """Only approved flat palette colours."""
        return _tile_color(value)


class CurriculumImport(CamelModel):
    """Upsert a syllabus: items are matched by ``displayOrder`` within their parent."""

    board_code: str = Field(min_length=1, max_length=32)
    # Creates the board when it does not exist yet (e.g. a fresh production database).
    board_name: str | None = Field(default=None, min_length=1, max_length=255)
    family: str = Field(default="TN_STATE", min_length=1, max_length=32)
    grade: int = Field(default=10, ge=1, le=12)
    choose_subjects: bool = False
    # Only for a new board: hidden from students until an admin switches it on.
    is_active: bool = True
    subjects: list[ImportSubject] = Field(max_length=60)


class ImportResult(CamelModel):
    created: dict[str, int]
    updated: dict[str, int]


# --- lessons --------------------------------------------------------------------------------


class AdminLesson(CamelModel):
    id: int
    topic_id: int
    topic_title: str
    medium: Medium
    language: LessonLanguage
    style: LessonStyle
    source: LessonSource
    title: str | None
    status: LessonStatus
    is_flagged: bool
    duration_sec: int | None
    audio_url: str | None
    video_url: str | None
    created_at: datetime


class LessonFlagUpdate(CamelModel):
    is_flagged: bool


# --- questions ------------------------------------------------------------------------------


class AdminQuestion(ORMModel):
    id: int
    topic_id: int
    medium: Medium
    type: QuestionType
    stem: str
    options: list[str] | None
    correct_answer: str
    explanation: str
    difficulty: int
    source: QuestionSource
    is_approved: bool
    is_flagged: bool
    created_at: datetime


class QuestionCreate(CamelModel):
    topic_id: int = Field(gt=0)
    medium: Medium
    type: QuestionType = QuestionType.mcq
    stem: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(min_length=2, max_length=4)
    correct_answer: str = Field(min_length=1, max_length=200)
    explanation: str = Field(min_length=1, max_length=600)
    difficulty: int = Field(default=2, ge=1, le=3)


class QuestionUpdate(CamelModel):
    is_approved: bool | None = None
    is_flagged: bool | None = None
    stem: str | None = Field(default=None, max_length=500)
    options: list[str] | None = Field(default=None, min_length=2, max_length=4)
    correct_answer: str | None = Field(default=None, max_length=200)
    explanation: str | None = Field(default=None, max_length=600)
    difficulty: int | None = Field(default=None, ge=1, le=3)


# --- users ----------------------------------------------------------------------------------


class AdminUserOut(ORMModel):
    id: int
    email: str
    full_name: str | None
    role: UserRole
    medium: Medium | None
    is_active: bool
    created_at: datetime
    board_id: int | None = None
    subject_ids: list[int] = []


class AdminUserUpdate(CamelModel):
    role: UserRole | None = None
    is_active: bool | None = None
    # Change a student's class / chosen subjects (also after they paid).
    board_id: int | None = Field(default=None, gt=0)
    subject_ids: list[int] | None = Field(default=None, max_length=20)
