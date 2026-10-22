"""Full-subject tests: questions from every topic the student completed, graded on the server.

A subject test never completes or unlocks a topic; it is revision across the subject.
Plan holders only (see ``billing_service.require_exam_practice``).
"""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.curriculum import Subject, Topic
from app.models.exam import SubjectTest, SubjectTestQuestion
from app.models.quiz import Question
from app.models.user import User
from app.schemas.exam import (
    SubjectTestOut,
    SubjectTestQuestionResultOut,
    SubjectTestResultOut,
    SubjectTestSummary,
    TopicScoreOut,
)
from app.schemas.quiz import AnswerIn, QuizQuestionOut
from app.services.ai.questions import normalize_answer
from app.services.billing_service import require_exam_practice
from app.services.curriculum_service import student_medium, topic_title
from app.services.progress_service import (
    TopicState,
    board_topic_statuses,
    get_subject_for_student,
)
from app.services.quiz_service import MIN_QUESTIONS, QuestionsUnavailableError
from app.services.streak_service import record_study

logger = logging.getLogger(__name__)

_rng = random.SystemRandom()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def completed_topic_ids(db: Session, user: User, subject_id: int) -> list[int]:
    """Topics of the subject the student has passed, in study order."""
    statuses = board_topic_statuses(db, user, subject_id=subject_id)
    return [tid for tid, info in statuses.items() if info.state == TopicState.completed]


def _round_robin(by_topic: dict[int, list[Question]], count: int) -> list[Question]:
    """Take questions topic by topic so every completed topic is represented."""
    pools = [list(qs) for qs in by_topic.values() if qs]
    for pool in pools:
        _rng.shuffle(pool)
    _rng.shuffle(pools)
    picked: list[Question] = []
    while pools and len(picked) < count:
        for pool in list(pools):
            if len(picked) >= count:
                break
            picked.append(pool.pop())
            if not pool:
                pools.remove(pool)
    return picked


def _test_out(test: SubjectTest) -> SubjectTestOut:
    return SubjectTestOut(
        test_id=test.id,
        subject_id=test.subject_id,
        expires_at=_aware(test.expires_at),
        questions=[
            QuizQuestionOut(
                question_id=tq.question_id,
                position=tq.position,
                type=tq.question.type,
                stem=tq.question.stem,
                options=list(tq.served_options or tq.question.options or []),
            )
            for tq in test.questions
        ],
    )


def start_subject_test(db: Session, user: User, subject_id: int) -> SubjectTestOut:
    """Start (or resume) a full-subject test.

    Questions come from the topics already passed, spread across them, preferring
    questions not used in this student's earlier subject tests.

    Raises:
        NotFoundError: not one of the student's subjects
        PlanRequiredError: no plan (code ``plan_required``)
        BadRequestError: too few topics passed yet (code ``not_enough_topics``)
        QuestionsUnavailableError: the question bank is too small
    """
    subject = get_subject_for_student(db, user, subject_id)
    require_exam_practice(db, user)
    now = datetime.now(UTC)
    open_test = db.scalar(
        select(SubjectTest)
        .where(
            SubjectTest.user_id == user.id,
            SubjectTest.subject_id == subject.id,
            SubjectTest.submitted_at.is_(None),
        )
        .order_by(SubjectTest.id.desc())
        .limit(1)
    )
    if open_test is not None and _aware(open_test.expires_at) > now:
        return _test_out(open_test)

    topic_ids = completed_topic_ids(db, user, subject.id)
    if len(topic_ids) < settings.SUBJECT_TEST_MIN_TOPICS:
        raise BadRequestError(
            f"Pass at least {settings.SUBJECT_TEST_MIN_TOPICS} topic tests in this subject first",
            code="not_enough_topics",
        )
    medium = student_medium(user, subject)
    questions = db.scalars(
        select(Question).where(
            Question.topic_id.in_(topic_ids),
            Question.medium == medium,
            Question.is_approved.is_(True),
            Question.is_flagged.is_(False),
        )
    ).all()
    used = set(
        db.scalars(
            select(SubjectTestQuestion.question_id)
            .join(SubjectTest, SubjectTest.id == SubjectTestQuestion.test_id)
            .where(SubjectTest.user_id == user.id, SubjectTest.subject_id == subject.id)
        )
    )
    fresh: dict[int, list[Question]] = {}
    old: dict[int, list[Question]] = {}
    for q in questions:
        (old if q.id in used else fresh).setdefault(q.topic_id, []).append(q)
    wanted = settings.SUBJECT_TEST_QUESTIONS
    picked = _round_robin(fresh, wanted)
    if len(picked) < wanted:
        picked += _round_robin(old, wanted - len(picked))
    if len(picked) < MIN_QUESTIONS:
        raise QuestionsUnavailableError()

    _rng.shuffle(picked)
    test = SubjectTest(
        user_id=user.id,
        subject_id=subject.id,
        started_at=now,
        expires_at=now + timedelta(minutes=settings.SUBJECT_TEST_EXPIRE_MINUTES),
    )
    for position, question in enumerate(picked, start=1):
        options = list(question.options or [])
        _rng.shuffle(options)
        test.questions.append(
            SubjectTestQuestion(question_id=question.id, position=position, served_options=options)
        )
    db.add(test)
    db.commit()
    db.refresh(test)
    return _test_out(test)


def submit_subject_test(
    db: Session, user: User, test_id: int, answers: list[AnswerIn]
) -> SubjectTestResultOut:
    """Grade a subject test on the server and show which topics need revision.

    Raises:
        NotFoundError: not this student's test
        ConflictError: already submitted (``attempt_submitted``) or expired (``attempt_expired``)
    """
    test = db.get(SubjectTest, test_id)
    if test is None or test.user_id != user.id:
        raise NotFoundError("Test not found")
    if test.submitted_at is not None:
        raise ConflictError("This test was already submitted", code="attempt_submitted")
    if _aware(test.expires_at) <= datetime.now(UTC):
        raise ConflictError(
            "Time is up for this test. Please start a new one.", code="attempt_expired"
        )
    subject = db.get(Subject, test.subject_id)
    medium = student_medium(user, subject)
    topics = {
        t.id: t
        for t in db.scalars(
            select(Topic).where(Topic.id.in_({tq.question.topic_id for tq in test.questions}))
        )
    }

    given = {a.question_id: a.answer for a in answers}
    results: list[SubjectTestQuestionResultOut] = []
    per_topic: dict[int, list[int]] = {}
    correct = 0
    for tq in test.questions:
        question = tq.question
        selected = given.get(tq.question_id)
        is_correct = selected is not None and normalize_answer(selected) == normalize_answer(
            question.correct_answer
        )
        tq.selected_answer = selected
        tq.is_correct = is_correct
        correct += int(is_correct)
        tally = per_topic.setdefault(question.topic_id, [0, 0])
        tally[0] += int(is_correct)
        tally[1] += 1
        topic = topics.get(question.topic_id)
        results.append(
            SubjectTestQuestionResultOut(
                question_id=tq.question_id,
                position=tq.position,
                stem=question.stem,
                options=list(tq.served_options or question.options or []),
                selected_answer=selected,
                correct_answer=question.correct_answer,
                is_correct=is_correct,
                explanation=question.explanation,
                topic_id=question.topic_id,
                topic_title=topic_title(topic, medium) if topic else "",
            )
        )

    total = len(test.questions)
    score = round(correct * 100 / total, 1) if total else 0.0
    test.score_pct = score
    test.correct_count = correct
    test.submitted_at = datetime.now(UTC)
    record_study(db, user)
    db.commit()
    logger.info(
        "Subject test graded user_id=%s subject_id=%s score=%s", user.id, test.subject_id, score
    )

    weak = [
        TopicScoreOut(
            topic_id=tid,
            title=topic_title(topics[tid], medium) if tid in topics else "",
            correct=right,
            total=asked,
        )
        for tid, (right, asked) in per_topic.items()
        if right * 100 < asked * settings.QUIZ_PASS_PCT
    ]
    return SubjectTestResultOut(
        test_id=test.id,
        subject_id=test.subject_id,
        score_pct=score,
        correct_count=correct,
        total=total,
        results=results,
        weak_topics=weak,
    )


def recent_subject_tests(
    db: Session, user: User, subject_id: int, limit: int = 5
) -> list[SubjectTestSummary]:
    """The student's latest graded subject tests (newest first)."""
    rows = db.scalars(
        select(SubjectTest)
        .where(
            SubjectTest.user_id == user.id,
            SubjectTest.subject_id == subject_id,
            SubjectTest.submitted_at.is_not(None),
        )
        .order_by(SubjectTest.submitted_at.desc())
        .limit(limit)
    ).all()
    return [
        SubjectTestSummary(
            id=t.id,
            score_pct=t.score_pct or 0.0,
            correct_count=t.correct_count or 0,
            total=len(t.questions),
            submitted_at=_aware(t.submitted_at) if t.submitted_at else datetime.now(UTC),
        )
        for t in rows
    ]
