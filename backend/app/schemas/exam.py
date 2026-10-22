"""Exam practice schemas: full-subject tests and model question papers.

A model paper's answer key is only included after the student has submitted photos
of their written answers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import CamelModel
from app.schemas.quiz import QuestionResultOut, QuizQuestionOut

PaperScope = Literal["full", "chapters"]
PaperStatus = Literal[
    "generating", "ready", "grading", "graded", "generation_failed", "grading_failed"
]

# --- full-subject test ---------------------------------------------------------------------


class SubjectTestOut(CamelModel):
    """A started (or resumed) full-subject test. Answers are not included."""

    test_id: int
    subject_id: int
    expires_at: datetime
    questions: list[QuizQuestionOut]


class SubjectTestQuestionResultOut(QuestionResultOut):
    """Per-question feedback, with the topic the question came from."""

    topic_id: int
    topic_title: str


class TopicScoreOut(CamelModel):
    """How the student did on one topic within a subject test."""

    topic_id: int
    title: str
    correct: int
    total: int


class SubjectTestResultOut(CamelModel):
    """A graded full-subject test."""

    test_id: int
    subject_id: int
    score_pct: float
    correct_count: int
    total: int
    results: list[SubjectTestQuestionResultOut]
    weak_topics: list[TopicScoreOut]


class SubjectTestSummary(CamelModel):
    """A past full-subject test."""

    id: int
    score_pct: float
    correct_count: int
    total: int
    submitted_at: datetime


# --- model papers --------------------------------------------------------------------------


class CreateModelPaperRequest(CamelModel):
    """A full-syllabus paper, or a unit paper for chosen chapters."""

    scope: PaperScope
    chapter_ids: list[int] = Field(default_factory=list, max_length=60)


class PaperQuestionOut(CamelModel):
    """A question as printed on the paper (no answer)."""

    number: int
    text: str
    options: list[str]
    alt_text: str | None  # the "(OR)" question of an either / or pair
    compulsory: bool


class PaperPartOut(CamelModel):
    """One part of the paper."""

    label: str
    kind: str
    marks: int
    printed: int
    answer: int
    either_or: bool
    questions: list[PaperQuestionOut]


class AnswerKeyItemOut(CamelModel):
    """Answer key and suggested answer for one question, with the marks given (if marked)."""

    number: int
    max_marks: int
    answer: str
    points: list[str]
    alt_answer: str | None
    alt_points: list[str]
    attempted: bool | None
    marks_awarded: float | None
    feedback: str | None


class PartScoreOut(CamelModel):
    """Marks scored in one part (best answers counted, as an examiner would)."""

    label: str
    scored: float
    total: int


class ModelPaperSummary(CamelModel):
    """A model paper in the list."""

    id: int
    subject_id: int
    title: str
    scope: PaperScope
    chapter_ids: list[int]
    status: PaperStatus
    total_marks: int
    duration_minutes: int
    score: float | None
    created_at: datetime


class ModelPaperOut(ModelPaperSummary):
    """A model paper; ``answer_key`` stays empty until the answers are submitted."""

    parts: list[PaperPartOut]
    answer_key: list[AnswerKeyItemOut] | None
    part_scores: list[PartScoreOut] | None
    feedback: str | None
    photos_submitted: int


class PaperHtmlOut(CamelModel):
    """Printable HTML (the app turns it into a PDF to save or share)."""

    html: str
    file_name: str


class PatternInfo(CamelModel):
    """Marks and time of a paper pattern."""

    total_marks: int
    duration_minutes: int


class ExamOverviewOut(CamelModel):
    """Everything the subject's "Exam practice" section shows."""

    subject_id: int
    plan_required: bool
    completed_topics: int
    min_topics: int
    recent_tests: list[SubjectTestSummary]
    papers: list[ModelPaperSummary]
    papers_left_today: int
    full_pattern: PatternInfo
    unit_pattern: PatternInfo
