"""Lesson, generation-job and clarity schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.models.enums import JobStatus, LessonLanguage, LessonStatus, LessonStyle, Medium
from app.schemas.common import CamelModel


class SlideOut(CamelModel):
    """One slide with its narration and when it starts in the audio."""

    heading: str
    bullets: list[str]
    narration: str
    emoji: str = ""
    image_url: str | None = None  # storybook illustration (short-lived link)
    start_sec: float = 0


class LessonOut(CamelModel):
    """A playable lesson (audio always present; video once rendered)."""

    id: int
    topic_id: int
    medium: Medium
    language: LessonLanguage
    style: LessonStyle
    style_label: str
    title: str
    summary: str
    slides: list[SlideOut]
    audio_url: str | None
    video_url: str | None
    duration_sec: int | None
    status: LessonStatus


class JobOut(CamelModel):
    """Status of an AI generation job."""

    id: int
    status: JobStatus
    style: LessonStyle | None
    style_label: str | None
    error: str | None
    lesson: LessonOut | None = None


class LessonResponse(CamelModel):
    """Either a ready lesson (HTTP 200) or a job being generated (HTTP 202)."""

    state: Literal["ready", "generating"]
    lesson: LessonOut | None = None
    job: JobOut | None = None


class NotClearRequest(CamelModel):
    """The student did not understand ``lesson_id``."""

    lesson_id: int | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=500)


class ChooseStyleRequest(CamelModel):
    """The explanation style the student wants."""

    style: LessonStyle


class ChooseLanguageRequest(CamelModel):
    """Explain in this language (and keep the current style if given)."""

    language: LessonLanguage
    style: LessonStyle | None = None


class ClearRequest(CamelModel):
    """The student understood ``lesson_id``."""

    lesson_id: int = Field(gt=0)


class LessonProgressRequest(CamelModel):
    """Watch progress for a lesson."""

    watched_sec: int = Field(ge=0, le=6 * 60 * 60)
    completed: bool = False
