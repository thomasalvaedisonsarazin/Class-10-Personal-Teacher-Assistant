"""Quiz schemas. Start responses never include correct answers or explanations."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.models.enums import QuestionType
from app.schemas.common import CamelModel


class QuizQuestionOut(CamelModel):
    """A served question (no answer!)."""

    question_id: int
    position: int
    type: QuestionType
    stem: str
    options: list[str]


class QuizAttemptOut(CamelModel):
    """A started (or resumed) attempt."""

    attempt_id: int
    topic_id: int
    expires_at: datetime
    pass_pct: float
    questions: list[QuizQuestionOut]


class AnswerIn(CamelModel):
    """The student's answer to one question."""

    question_id: int = Field(gt=0)
    answer: str | None = Field(default=None, max_length=500)


class SubmitAttemptRequest(CamelModel):
    """All answers for an attempt (unanswered questions count as wrong)."""

    answers: list[AnswerIn] = Field(max_length=50)


class QuestionResultOut(CamelModel):
    """Per-question feedback after grading."""

    question_id: int
    position: int
    stem: str
    options: list[str]
    selected_answer: str | None
    correct_answer: str
    is_correct: bool
    explanation: str


class NextTopicOut(CamelModel):
    """The topic unlocked by passing."""

    id: int
    title: str


class QuizResultOut(CamelModel):
    """Graded attempt."""

    attempt_id: int
    topic_id: int
    score_pct: float
    correct_count: int
    total: int
    passed: bool
    pass_pct: float
    results: list[QuestionResultOut]
    next_topic: NextTopicOut | None
