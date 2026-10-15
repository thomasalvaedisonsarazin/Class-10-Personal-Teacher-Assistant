"""Quizzes: fresh (never-served) questions per attempt, server-side grading, 60% gate."""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import AppError, ConflictError, NotFoundError
from app.models.curriculum import Topic
from app.models.enums import Medium, QuestionSource
from app.models.quiz import Question, QuizAttempt, QuizAttemptQuestion
from app.models.user import User
from app.schemas.quiz import (
    AnswerIn,
    NextTopicOut,
    QuestionResultOut,
    QuizAttemptOut,
    QuizQuestionOut,
    QuizResultOut,
)
from app.services.ai.llm import LLMError, get_llm_client
from app.services.ai.questions import generate_questions, normalize_answer, verify_questions
from app.services.curriculum_service import student_medium, topic_context, topic_title
from app.services.progress_service import (
    TopicState,
    board_topic_statuses,
    record_quiz_result,
    require_topic_access,
)
from app.services.streak_service import record_study

logger = logging.getLogger(__name__)

GENERATION_BATCH = 15
MIN_QUESTIONS = 5  # serve a shorter test rather than none if generation underdelivers
DIFFICULTY_MIX = {1: 0.4, 2: 0.4, 3: 0.2}

_rng = random.SystemRandom()


class QuestionsUnavailableError(AppError):
    """503: not enough questions could be prepared."""

    status_code = 503
    code = "questions_unavailable"
    message = "We could not prepare your test right now. Please try again in a minute."


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


# --- question pool ------------------------------------------------------------------------


def served_question_ids(db: Session, user: User, topic_id: int) -> set[int]:
    """Every question ever served to ``user`` for ``topic_id``."""
    return set(
        db.scalars(
            select(QuizAttemptQuestion.question_id)
            .join(QuizAttempt, QuizAttempt.id == QuizAttemptQuestion.attempt_id)
            .where(QuizAttempt.user_id == user.id, QuizAttempt.topic_id == topic_id)
        )
    )


def _unseen_questions(
    db: Session, topic_id: int, medium: Medium, served: set[int]
) -> list[Question]:
    query = select(Question).where(
        Question.topic_id == topic_id,
        Question.medium == medium,
        Question.is_approved.is_(True),
        Question.is_flagged.is_(False),
    )
    if served:
        query = query.where(Question.id.not_in(served))
    return list(db.scalars(query))


def add_generated_questions(db: Session, topic: Topic, medium: Medium) -> int:
    """Generate a batch with the LLM and store new (de-duplicated) questions.

    Returns:
        Number of questions added
    """
    existing = list(
        db.scalars(
            select(Question.stem)
            .where(Question.topic_id == topic.id, Question.medium == medium)
            .order_by(Question.id.desc())
            .limit(40)
        )
    )
    llm = get_llm_client()
    context = topic_context(topic, medium)
    generated = generate_questions(llm, context, medium, GENERATION_BATCH, existing)
    if settings.QUESTION_VERIFY_ENABLED:
        generated = verify_questions(llm, context, generated, settings.CHECK_REASONING_EFFORT)
    added = 0
    for q in generated:
        try:
            with db.begin_nested():
                db.add(
                    Question(
                        topic_id=topic.id,
                        medium=medium,
                        type=q.type,
                        stem=q.stem,
                        options=q.options,
                        correct_answer=q.correct_answer,
                        explanation=q.explanation,
                        difficulty=q.difficulty,
                        source=QuestionSource.ai,
                        is_approved=settings.AI_QUESTIONS_AUTO_APPROVE,
                        content_hash=q.content_hash,
                    )
                )
            added += 1
        except IntegrityError:
            continue  # duplicate of an existing question
    db.commit()
    logger.info("Added %s AI questions topic_id=%s medium=%s", added, topic.id, medium)
    return added


def _pick(candidates: list[Question], count: int) -> list[Question]:
    """Random sample with roughly 40% easy, 40% medium, 20% hard; topped up from the rest."""
    by_level: dict[int, list[Question]] = {1: [], 2: [], 3: []}
    for q in candidates:
        by_level.setdefault(q.difficulty, []).append(q)
    picked: list[Question] = []
    for level, share in DIFFICULTY_MIX.items():
        pool = by_level.get(level, [])
        picked += _rng.sample(pool, min(len(pool), round(count * share)))
    rest = [q for q in candidates if q not in picked]
    picked += _rng.sample(rest, min(len(rest), count - len(picked)))
    _rng.shuffle(picked)
    return picked[:count]


# --- attempts ---------------------------------------------------------------------------------


def _attempt_out(attempt: QuizAttempt) -> QuizAttemptOut:
    return QuizAttemptOut(
        attempt_id=attempt.id,
        topic_id=attempt.topic_id,
        expires_at=_aware(attempt.expires_at),
        pass_pct=settings.QUIZ_PASS_PCT,
        questions=[
            QuizQuestionOut(
                question_id=aq.question_id,
                position=aq.position,
                type=aq.question.type,
                stem=aq.question.stem,
                options=list(aq.served_options or aq.question.options or []),
            )
            for aq in attempt.questions
        ],
    )


def start_attempt(db: Session, user: User, topic_id: int) -> QuizAttemptOut:
    """Start a quiz with questions this student has never been served (or resume an open one).

    Raises:
        ForbiddenError: topic locked
        QuestionsUnavailableError: fewer than ``MIN_QUESTIONS`` fresh questions available
    """
    topic, _ = require_topic_access(db, user, topic_id)
    now = datetime.now(UTC)
    open_attempt = db.scalar(
        select(QuizAttempt)
        .where(
            QuizAttempt.user_id == user.id,
            QuizAttempt.topic_id == topic.id,
            QuizAttempt.submitted_at.is_(None),
        )
        .order_by(QuizAttempt.id.desc())
        .limit(1)
    )
    if open_attempt is not None and _aware(open_attempt.expires_at) > now:
        return _attempt_out(open_attempt)

    medium = student_medium(user)
    wanted = settings.QUIZ_QUESTIONS_PER_ATTEMPT
    served = served_question_ids(db, user, topic.id)
    candidates = _unseen_questions(db, topic.id, medium, served)
    if len(candidates) < wanted:
        try:
            add_generated_questions(db, topic, medium)
        except LLMError as exc:
            logger.warning("Question generation failed for topic %s: %s", topic.id, exc)
        candidates = _unseen_questions(db, topic.id, medium, served)
    if len(candidates) < MIN_QUESTIONS:
        raise QuestionsUnavailableError()

    attempt = QuizAttempt(
        user_id=user.id,
        topic_id=topic.id,
        started_at=now,
        expires_at=now + timedelta(minutes=settings.QUIZ_ATTEMPT_EXPIRE_MINUTES),
    )
    for position, question in enumerate(_pick(candidates, wanted), start=1):
        options = list(question.options or [])
        _rng.shuffle(options)
        attempt.questions.append(
            QuizAttemptQuestion(question_id=question.id, position=position, served_options=options)
        )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return _attempt_out(attempt)


def _next_topic(db: Session, user: User, topic: Topic) -> NextTopicOut | None:
    """The topic now available in the same subject (after a pass)."""
    statuses = board_topic_statuses(db, user, subject_id=topic.chapter.subject_id)
    next_id = next(
        (
            tid
            for tid, info in statuses.items()
            if info.state in (TopicState.available, TopicState.active)
        ),
        None,
    )
    if next_id is None or next_id == topic.id:
        return None
    next_topic = db.get(Topic, next_id)
    return (
        NextTopicOut(id=next_id, title=topic_title(next_topic, student_medium(user)))
        if next_topic
        else None
    )


def submit_attempt(
    db: Session, user: User, attempt_id: int, answers: list[AnswerIn]
) -> QuizResultOut:
    """Grade an attempt on the server and apply the pass mark.

    Raises:
        NotFoundError: not this student's attempt
        ConflictError: already submitted (``attempt_submitted``) or expired (``attempt_expired``)
    """
    attempt = db.get(QuizAttempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise NotFoundError("Test not found")
    if attempt.submitted_at is not None:
        raise ConflictError("This test was already submitted", code="attempt_submitted")
    if _aware(attempt.expires_at) <= datetime.now(UTC):
        raise ConflictError(
            "Time is up for this test. Please start a new one.", code="attempt_expired"
        )
    topic = db.get(Topic, attempt.topic_id)
    if topic is None:
        raise NotFoundError("Topic not found")

    given = {a.question_id: a.answer for a in answers}
    results: list[QuestionResultOut] = []
    correct = 0
    for aq in attempt.questions:
        question = aq.question
        selected = given.get(aq.question_id)
        is_correct = selected is not None and normalize_answer(selected) == normalize_answer(
            question.correct_answer
        )
        aq.selected_answer = selected
        aq.is_correct = is_correct
        correct += int(is_correct)
        results.append(
            QuestionResultOut(
                question_id=aq.question_id,
                position=aq.position,
                stem=question.stem,
                options=list(aq.served_options or question.options or []),
                selected_answer=selected,
                correct_answer=question.correct_answer,
                is_correct=is_correct,
                explanation=question.explanation,
            )
        )

    total = len(attempt.questions)
    score = round(correct * 100 / total, 1) if total else 0.0
    attempt.score_pct = score
    attempt.submitted_at = datetime.now(UTC)
    attempt.passed = record_quiz_result(db, user, topic, score)
    record_study(db, user)
    db.commit()
    logger.info(
        "Quiz graded user_id=%s topic_id=%s score=%s passed=%s",
        user.id,
        topic.id,
        score,
        attempt.passed,
    )

    return QuizResultOut(
        attempt_id=attempt.id,
        topic_id=topic.id,
        score_pct=score,
        correct_count=correct,
        total=total,
        passed=attempt.passed,
        pass_pct=settings.QUIZ_PASS_PCT,
        results=results,
        next_topic=_next_topic(db, user, topic) if attempt.passed else None,
    )
