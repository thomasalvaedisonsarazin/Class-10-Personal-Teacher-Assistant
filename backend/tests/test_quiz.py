"""Quiz module: fresh questions per attempt, no answer leakage, server grading, 60% gate."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.curriculum import Board, Chapter, Subject, Topic
from app.models.enums import Medium, UserRole
from app.models.quiz import QuizAttempt
from app.models.user import User
from app.services.ai.llm import LLMError, get_fake_llm_client
from app.services.ai.questions import GeneratedQuestion, QuestionBatch, validate_question

Headers = Callable[[User], dict[str, str]]
CORRECT = "Correct answer"  # the offline fake LLM always uses this as the right option


@pytest.fixture()
def topics(db: Session) -> tuple[Topic, Topic]:
    board = Board(code="TN_SSLC", name="Tamil Nadu State Board", is_active=True)
    subject = Subject(
        board=board, name="Maths", tile_color="#3B6EA5", icon="calculator", display_order=1
    )
    chapter = Chapter(subject=subject, title="Sets", display_order=1)
    first = Topic(
        chapter=chapter,
        title="Sets basics",
        learning_objectives="Define a set",
        display_order=1,
        is_published=True,
    )
    second = Topic(chapter=chapter, title="Venn diagrams", display_order=2, is_published=True)
    db.add_all([board, subject, chapter, first, second])
    db.commit()
    return first, second


@pytest.fixture()
def student(make_user: Callable[..., User], topics: tuple[Topic, Topic]) -> User:
    return make_user(
        role=UserRole.student, board_id=topics[0].chapter.subject.board_id, medium=Medium.en
    )


def _start(client: TestClient, headers: dict[str, str], topic: Topic) -> dict:
    res = client.post(f"/api/v1/topics/{topic.id}/quiz-attempts", headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _submit(client: TestClient, headers: dict[str, str], attempt: dict, correct: int) -> dict:
    answers = []
    for i, q in enumerate(attempt["questions"]):
        wrong = next(o for o in q["options"] if o != CORRECT)
        answers.append({"questionId": q["questionId"], "answer": CORRECT if i < correct else wrong})
    res = client.post(
        f"/api/v1/quiz-attempts/{attempt['attemptId']}/submit",
        json={"answers": answers},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    return res.json()


# --- Starting ------------------------------------------------------------------------------------


def test_start_serves_ten_questions_without_answers(
    client: TestClient, student: User, auth_headers: Headers, topics: tuple[Topic, Topic]
) -> None:
    res = client.post(f"/api/v1/topics/{topics[0].id}/quiz-attempts", headers=auth_headers(student))
    assert res.status_code == 201
    body = res.json()
    assert len(body["questions"]) == 10
    assert body["passPct"] == 60
    assert all(len(q["options"]) == 4 for q in body["questions"])
    assert "correctAnswer" not in res.text and "explanation" not in res.text
    assert "correct_answer" not in res.text


def test_consecutive_attempts_share_no_questions(
    client: TestClient, student: User, auth_headers: Headers, topics: tuple[Topic, Topic]
) -> None:
    headers = auth_headers(student)
    seen: set[int] = set()
    for _ in range(3):
        attempt = _start(client, headers, topics[0])
        ids = {q["questionId"] for q in attempt["questions"]}
        assert not ids & seen
        seen |= ids
        _submit(client, headers, attempt, correct=0)


def test_open_attempt_is_resumed(
    client: TestClient, student: User, auth_headers: Headers, topics: tuple[Topic, Topic]
) -> None:
    headers = auth_headers(student)
    assert (
        _start(client, headers, topics[0])["attemptId"]
        == _start(client, headers, topics[0])["attemptId"]
    )


def test_locked_topic_quiz_forbidden(
    client: TestClient, student: User, auth_headers: Headers, topics: tuple[Topic, Topic]
) -> None:
    res = client.post(f"/api/v1/topics/{topics[1].id}/quiz-attempts", headers=auth_headers(student))
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "topic_locked"


def test_generation_failure_without_pool_returns_503(
    client: TestClient, student: User, auth_headers: Headers, topics: tuple[Topic, Topic]
) -> None:
    def _broken(system: str, user: str) -> QuestionBatch:
        raise LLMError("down")

    get_fake_llm_client().register(QuestionBatch, _broken)
    res = client.post(f"/api/v1/topics/{topics[0].id}/quiz-attempts", headers=auth_headers(student))
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "questions_unavailable"


# --- Grading & the 60% gate ----------------------------------------------------------------------


def test_below_pass_mark_does_not_unlock(
    client: TestClient, student: User, auth_headers: Headers, topics: tuple[Topic, Topic]
) -> None:
    headers = auth_headers(student)
    result = _submit(client, headers, _start(client, headers, topics[0]), correct=5)
    assert result["scorePct"] == 50 and result["passed"] is False and result["nextTopic"] is None
    assert client.get(f"/api/v1/topics/{topics[1].id}", headers=headers).status_code == 403


def test_pass_mark_unlocks_next_topic(
    client: TestClient, student: User, auth_headers: Headers, topics: tuple[Topic, Topic]
) -> None:
    headers = auth_headers(student)
    result = _submit(client, headers, _start(client, headers, topics[0]), correct=6)
    assert result["scorePct"] == 60 and result["passed"] is True
    assert result["correctCount"] == 6 and result["total"] == 10
    assert result["nextTopic"] == {"id": topics[1].id, "title": "Venn diagrams"}
    # Results reveal answers and explanations only after submitting.
    assert all(r["correctAnswer"] == CORRECT and r["explanation"] for r in result["results"])
    assert (
        client.get(f"/api/v1/topics/{topics[0].id}", headers=headers).json()["status"]
        == "completed"
    )
    assert (
        client.get(f"/api/v1/topics/{topics[1].id}", headers=headers).json()["status"]
        == "available"
    )


def test_unanswered_questions_count_as_wrong(
    client: TestClient, student: User, auth_headers: Headers, topics: tuple[Topic, Topic]
) -> None:
    headers = auth_headers(student)
    attempt = _start(client, headers, topics[0])
    first = attempt["questions"][0]["questionId"]
    res = client.post(
        f"/api/v1/quiz-attempts/{attempt['attemptId']}/submit",
        json={"answers": [{"questionId": first, "answer": f"  {CORRECT.upper()} "}]},
        headers=headers,
    )
    assert res.json()["scorePct"] == 10  # case/space-insensitive match, 9 unanswered


def test_cannot_submit_twice(
    client: TestClient, student: User, auth_headers: Headers, topics: tuple[Topic, Topic]
) -> None:
    headers = auth_headers(student)
    attempt = _start(client, headers, topics[0])
    _submit(client, headers, attempt, correct=10)
    res = client.post(
        f"/api/v1/quiz-attempts/{attempt['attemptId']}/submit",
        json={"answers": []},
        headers=headers,
    )
    assert res.status_code == 409 and res.json()["error"]["code"] == "attempt_submitted"


def test_expired_attempt_rejected_and_new_one_started(
    client: TestClient,
    db: Session,
    student: User,
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
) -> None:
    headers = auth_headers(student)
    attempt = _start(client, headers, topics[0])
    row = db.get(QuizAttempt, attempt["attemptId"])
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    res = client.post(
        f"/api/v1/quiz-attempts/{attempt['attemptId']}/submit",
        json={"answers": []},
        headers=headers,
    )
    assert res.status_code == 409 and res.json()["error"]["code"] == "attempt_expired"
    assert _start(client, headers, topics[0])["attemptId"] != attempt["attemptId"]


def test_other_students_attempt_not_found(
    client: TestClient,
    student: User,
    make_user: Callable[..., User],
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
) -> None:
    attempt = _start(client, auth_headers(student), topics[0])
    other = make_user(role=UserRole.student, board_id=student.board_id, medium=Medium.en)
    res = client.post(
        f"/api/v1/quiz-attempts/{attempt['attemptId']}/submit",
        json={"answers": []},
        headers=auth_headers(other),
    )
    assert res.status_code == 404
    assert db_attempt_unsubmitted(client, attempt, student, auth_headers)


def db_attempt_unsubmitted(
    client: TestClient, attempt: dict, student: User, auth_headers: Headers
) -> bool:
    """The owner can still submit after the failed attempt by someone else."""
    res = client.post(
        f"/api/v1/quiz-attempts/{attempt['attemptId']}/submit",
        json={"answers": []},
        headers=auth_headers(student),
    )
    return res.status_code == 200


def test_tamil_medium_uses_separate_question_pool(
    client: TestClient,
    db: Session,
    make_user: Callable[..., User],
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
) -> None:
    tamil = make_user(
        role=UserRole.student, board_id=topics[0].chapter.subject.board_id, medium=Medium.ta
    )
    _start(client, auth_headers(tamil), topics[0])
    system, user, _ = next(c for c in get_fake_llm_client().calls if c[2] is QuestionBatch)
    assert "Tamil" in user
    from app.models.quiz import Question

    assert set(db.scalars(select(Question.medium))) == {Medium.ta}


# --- Validation ---------------------------------------------------------------------------------


def _q(**overrides: object) -> GeneratedQuestion:
    data: dict[str, object] = {
        "type": "mcq",
        "stem": "2 + 2 = ?",
        "options": ["3", "4", "5", "6"],
        "correct_answer": "4",
        "explanation": "Two plus two is four.",
        "difficulty": 1,
    }
    data.update(overrides)
    return GeneratedQuestion.model_validate(data)


def test_validate_question_rules() -> None:
    assert validate_question(_q()) is not None
    assert validate_question(_q(options=["3", "4", "4", "6"])) is None  # duplicate options
    assert validate_question(_q(options=["3", "4", "5"])) is None  # MCQ needs 4
    assert validate_question(_q(correct_answer="7")) is None  # answer not among options
    assert validate_question(_q(explanation=" ")) is None
    tf = validate_question(_q(type="true_false", options=["True", "False"], correct_answer="false"))
    assert tf is not None and tf.correct_answer == "False"
    assert validate_question(_q(difficulty=9)).difficulty == 3  # type: ignore[union-attr]


# --- Question quality checks ---------------------------------------------------------------------


def test_difficulty_mix_always_has_hard_questions() -> None:
    from app.services.ai.questions import difficulty_mix

    assert difficulty_mix(15) == (6, 6, 3)
    assert difficulty_mix(5) == (2, 2, 1)
    assert sum(difficulty_mix(10)) == 10 and difficulty_mix(10)[2] >= 1


def test_prompt_asks_for_exact_difficulty_counts(
    client: TestClient, student: User, auth_headers: Headers, topics: tuple[Topic, Topic]
) -> None:
    _start(client, auth_headers(student), topics[0])
    batch_call = next(c for c in get_fake_llm_client().calls if c[2] is QuestionBatch)
    assert "Exactly 6 easy" in batch_call[1] and "3 hard" in batch_call[1]


def test_questions_with_unconfirmed_answers_are_dropped(
    client: TestClient,
    db: Session,
    student: User,
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
) -> None:
    from app.models.quiz import Question
    from app.services.ai.questions import AnswerCheck, AnswerItem

    def doubting_checker(system: str, user: str) -> AnswerCheck:
        numbers = [
            int(line[1:].split(".")[0])
            for line in user.splitlines()
            if line[:1] == "Q" and "." in line
        ]
        # Disagree with every 3rd question's key.
        return AnswerCheck(
            answers=[
                AnswerItem(number=n, answer="NONE" if n % 3 == 0 else CORRECT) for n in numbers
            ]
        )

    get_fake_llm_client().register(AnswerCheck, doubting_checker)
    _start(client, auth_headers(student), topics[0])
    assert db.scalar(select(func.count(Question.id))) == 10  # 15 generated, 5 rejected


def test_checker_failure_keeps_questions(
    client: TestClient,
    db: Session,
    student: User,
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
) -> None:
    from app.models.quiz import Question
    from app.services.ai.questions import AnswerCheck

    def broken(system: str, user: str) -> AnswerCheck:
        raise LLMError("checker down")

    get_fake_llm_client().register(AnswerCheck, broken)
    _start(client, auth_headers(student), topics[0])
    assert db.scalar(select(func.count(Question.id))) == 15
