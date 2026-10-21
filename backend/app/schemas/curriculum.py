"""Curriculum schemas (boards, subjects, chapters, topics)."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import CamelModel, ORMModel
from app.services.billing_service import TopicAccess
from app.services.progress_service import TopicState


class BoardOut(ORMModel):
    """A class of a board (e.g. TN State Board, Class 11) a student can pick during onboarding."""

    id: int
    code: str
    name: str
    family: str
    grade: int
    choose_subjects: bool


class SubjectChoice(CamelModel):
    """A subject of a class, for the higher-secondary subject picker."""

    id: int
    name: str
    tile_color: str
    icon: str


class TopicItem(CamelModel):
    """A topic row in a subject's chapter list."""

    id: int
    title: str
    status: TopicState
    best_score_pct: float | None = None
    access: TopicAccess = TopicAccess.free


class ChapterOut(CamelModel):
    """A chapter with its topics in study order."""

    id: int
    title: str
    topics: list[TopicItem]


class CurrentTopic(CamelModel):
    """The topic a student should study next in a subject."""

    id: int
    title: str
    status: TopicState


class SubjectSummary(CamelModel):
    """A Home-screen subject tile."""

    id: int
    name: str
    tile_color: str
    icon: str
    total_topics: int
    completed_topics: int
    current_topic: CurrentTopic | None = Field(
        description="First unfinished topic (None when the subject is finished)"
    )


class SubjectDetail(SubjectSummary):
    """A subject with all chapters and topic states."""

    chapters: list[ChapterOut]


class SubjectRef(CamelModel):
    """Minimal subject info shown on a topic screen."""

    id: int
    name: str
    tile_color: str


class TopicDetail(CamelModel):
    """A topic the student may open (never returned for locked topics)."""

    id: int
    title: str
    learning_objectives: str
    status: TopicState
    best_score_pct: float | None
    access: TopicAccess = TopicAccess.free
    chapter_title: str
    subject: SubjectRef
    pass_pct: float
    # Language subject (Tamil): lessons and tests always in that language — no language switch.
    language_fixed: bool = False
