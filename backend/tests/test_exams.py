"""Exam practice: full-subject tests and board-pattern model papers marked from photos."""

from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.curriculum import Board, Chapter, Subject, Topic
from app.models.enums import Medium, UserRole
from app.models.exam import ModelPaper, SubjectTest
from app.models.user import User
from app.services.ai.exam_grading import GradedAnswer, GradingResult
from app.services.ai.exam_paper import GeneratedPart
from app.services.ai.llm import LLMError, get_fake_llm_client
from app.services.exam_paper_html import key_html, paper_html
from app.services.exam_patterns import PATTERNS, pattern_for
from app.services.model_paper_service import paper_language, score_paper

Headers = Callable[[User], dict[str, str]]
CORRECT = "Correct answer"  # the offline fake LLM's right option


@pytest.fixture()
def subject(db: Session) -> Subject:
    board = Board(code="TN_SSLC", name="Tamil Nadu State Board", grade=10, is_active=True)
    subject = Subject(
        board=board, name="Mathematics", tile_color="#3B6EA5", icon="calculator", display_order=1
    )
    first = Chapter(subject=subject, title="Relations and Functions", display_order=1)
    second = Chapter(subject=subject, title="Numbers and Sequences", display_order=2)
    for i in range(3):
        Topic(
            chapter=first,
            title=f"Functions {i}",
            learning_objectives="Define a function",
            display_order=i,
            is_published=True,
        )
    for i in range(2):
        Topic(chapter=second, title=f"Sequences {i}", display_order=i, is_published=True)
    db.add(board)
    db.commit()
    db.refresh(subject)
    return subject


@pytest.fixture()
def student(make_user: Callable[..., User], subject: Subject) -> User:
    return make_user(role=UserRole.student, board_id=subject.board_id, medium=Medium.en)


def _topics(subject: Subject) -> list[Topic]:
    return [t for c in subject.chapters for t in c.topics]


def _pass_topic(client: TestClient, headers: dict[str, str], topic: Topic) -> None:
    attempt = client.post(f"/api/v1/topics/{topic.id}/quiz-attempts", headers=headers).json()
    answers = [{"questionId": q["questionId"], "answer": CORRECT} for q in attempt["questions"]]
    res = client.post(
        f"/api/v1/quiz-attempts/{attempt['attemptId']}/submit",
        json={"answers": answers},
        headers=headers,
    )
    assert res.json()["passed"] is True


def _photo(fmt: str = "PNG") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (1200, 1600), "white").save(out, format=fmt)
    return out.getvalue()


def _create_paper(
    client: TestClient, headers: dict[str, str], subject: Subject, **body: Any
) -> dict[str, Any]:
    res = client.post(
        f"/api/v1/subjects/{subject.id}/model-papers",
        json={"scope": "full", **body},
        headers=headers,
    )
    assert res.status_code == 202, res.text
    return res.json()


def _upload(client: TestClient, headers: dict[str, str], paper_id: int, photos: list[bytes]) -> Any:
    files = [("photos", (f"page{i}.png", data, "image/png")) for i, data in enumerate(photos)]
    return client.post(f"/api/v1/model-papers/{paper_id}/answers", files=files, headers=headers)


# --- full-subject test ---------------------------------------------------------------------


def test_subject_test_needs_passed_topics(
    client: TestClient, student: User, auth_headers: Headers, subject: Subject
) -> None:
    headers = auth_headers(student)
    res = client.post(f"/api/v1/subjects/{subject.id}/subject-tests", headers=headers)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "not_enough_topics"


def test_subject_test_mixes_passed_topics_and_never_unlocks(
    client: TestClient, student: User, auth_headers: Headers, subject: Subject, db: Session
) -> None:
    headers = auth_headers(student)
    topics = _topics(subject)
    for topic in topics[:3]:
        _pass_topic(client, headers, topic)

    res = client.post(f"/api/v1/subjects/{subject.id}/subject-tests", headers=headers)
    assert res.status_code == 201, res.text
    test = res.json()
    assert len(test["questions"]) == settings.SUBJECT_TEST_QUESTIONS
    assert "correctAnswer" not in res.text
    again = client.post(f"/api/v1/subjects/{subject.id}/subject-tests", headers=headers).json()
    assert again["testId"] == test["testId"]  # an open test is resumed

    answers = [
        {
            "questionId": q["questionId"],
            "answer": CORRECT if i % 2 == 0 else next(o for o in q["options"] if o != CORRECT),
        }
        for i, q in enumerate(test["questions"])
    ]
    graded = client.post(
        f"/api/v1/subject-tests/{test['testId']}/submit", json={"answers": answers}, headers=headers
    )
    assert graded.status_code == 200
    result = graded.json()
    assert result["correctCount"] == 10 and result["scorePct"] == 50.0
    assert {r["topicId"] for r in result["results"]} <= {t.id for t in topics[:3]}
    assert all(r["topicTitle"] for r in result["results"])

    detail = client.get(f"/api/v1/subjects/{subject.id}", headers=headers).json()
    states = [t["status"] for c in detail["chapters"] for t in c["topics"]]
    assert states[3] in ("available", "active") and states[4] == "locked"

    twice = client.post(
        f"/api/v1/subject-tests/{test['testId']}/submit", json={"answers": answers}, headers=headers
    )
    assert twice.status_code == 409
    overview = client.get(f"/api/v1/subjects/{subject.id}/exam-practice", headers=headers).json()
    assert overview["completedTopics"] == 3
    assert overview["recentTests"][0]["scorePct"] == 50.0


def test_exam_practice_needs_a_plan(
    client: TestClient,
    student: User,
    auth_headers: Headers,
    subject: Subject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "BILLING_ENABLED", True)
    headers = auth_headers(student)
    overview = client.get(f"/api/v1/subjects/{subject.id}/exam-practice", headers=headers).json()
    assert overview["planRequired"] is True
    res = client.post(
        f"/api/v1/subjects/{subject.id}/model-papers", json={"scope": "full"}, headers=headers
    )
    assert res.status_code == 402 and res.json()["error"]["code"] == "plan_required"
    res = client.post(f"/api/v1/subjects/{subject.id}/subject-tests", headers=headers)
    assert res.status_code == 402

    monkeypatch.setattr(settings, "COMPLIMENTARY_EMAILS", [student.email.lower()])
    overview = client.get(f"/api/v1/subjects/{subject.id}/exam-practice", headers=headers).json()
    assert overview["planRequired"] is False


# --- model papers --------------------------------------------------------------------------


def test_full_paper_follows_the_board_pattern_and_hides_the_key(
    client: TestClient, student: User, auth_headers: Headers, subject: Subject
) -> None:
    headers = auth_headers(student)
    paper = _create_paper(client, headers, subject)
    detail = client.get(f"/api/v1/model-papers/{paper['id']}", headers=headers).json()
    assert detail["status"] == "ready"
    assert detail["totalMarks"] == 100 and detail["durationMinutes"] == 180
    parts = detail["parts"]
    assert [(p["label"], p["printed"], p["answer"], p["marks"]) for p in parts] == [
        ("I", 14, 14, 1),
        ("II", 14, 10, 2),
        ("III", 14, 10, 5),
        ("IV", 2, 2, 8),
    ]
    numbers = [q["number"] for p in parts for q in p["questions"]]
    assert numbers == list(range(1, 45))
    assert all(len(q["options"]) == 4 for q in parts[0]["questions"])
    assert parts[1]["questions"][-1]["compulsory"] is True
    assert all(q["altText"] for q in parts[3]["questions"])
    assert detail["answerKey"] is None
    assert "sample model answer" not in str(detail).lower()

    doc = client.get(f"/api/v1/model-papers/{paper['id']}/document", headers=headers)
    assert doc.status_code == 200
    assert "PART – IV" in doc.json()["html"] and "(OR)" in doc.json()["html"]
    key = client.get(f"/api/v1/model-papers/{paper['id']}/document?kind=key", headers=headers)
    assert key.status_code == 403 and key.json()["error"]["code"] == "key_locked"


def test_photos_are_marked_then_key_opens_and_photos_are_deleted(
    client: TestClient, student: User, auth_headers: Headers, subject: Subject, db: Session
) -> None:
    headers = auth_headers(student)
    paper = _create_paper(client, headers, subject)
    res = _upload(client, headers, paper["id"], [_photo(), _photo("JPEG")])
    assert res.status_code == 202, res.text
    assert get_fake_llm_client().image_counts == [2]

    detail = client.get(f"/api/v1/model-papers/{paper['id']}", headers=headers).json()
    assert detail["status"] == "graded"
    # Fake examiner: 1 mark per question; best 14 + 10 + 10 + 2 answers count.
    assert detail["score"] == 36
    assert [p["scored"] for p in detail["partScores"]] == [14, 10, 10, 2]
    assert len(detail["answerKey"]) == 44
    assert detail["answerKey"][0]["marksAwarded"] == 1
    assert detail["feedback"]

    row = db.get(ModelPaper, paper["id"])
    db.refresh(row)
    assert row.image_keys == []
    photo_dir = Path(settings.MEDIA_ROOT) / "answer-sheets" / str(student.id) / str(paper["id"])
    assert not photo_dir.exists() or not any(photo_dir.iterdir())

    key = client.get(f"/api/v1/model-papers/{paper['id']}/document?kind=key", headers=headers)
    assert key.status_code == 200 and "Your marks" in key.json()["html"]
    again = _upload(client, headers, paper["id"], [_photo()])
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_submitted"


def test_unreadable_photos_can_be_sent_again(
    client: TestClient, student: User, auth_headers: Headers, subject: Subject
) -> None:
    headers = auth_headers(student)
    paper = _create_paper(client, headers, subject)
    fake = get_fake_llm_client()
    fake.register(
        GradingResult,
        lambda s, u: GradingResult(readable=False, answers=[], overall_feedback=""),
    )
    _upload(client, headers, paper["id"], [_photo()])
    detail = client.get(f"/api/v1/model-papers/{paper['id']}", headers=headers).json()
    assert detail["status"] == "grading_failed"
    assert "photos" in detail["feedback"]
    assert detail["answerKey"] is not None  # submitted, so the key is open

    fake.unregister(GradingResult)
    assert _upload(client, headers, paper["id"], [_photo()]).status_code == 202
    detail = client.get(f"/api/v1/model-papers/{paper['id']}", headers=headers).json()
    assert detail["status"] == "graded"


def test_bad_photo_is_refused(
    client: TestClient, student: User, auth_headers: Headers, subject: Subject
) -> None:
    headers = auth_headers(student)
    paper = _create_paper(client, headers, subject)
    res = _upload(client, headers, paper["id"], [b"not an image"])
    assert res.status_code == 400 and res.json()["error"]["code"] == "invalid_photo"
    detail = client.get(f"/api/v1/model-papers/{paper['id']}", headers=headers).json()
    assert detail["status"] == "ready"


def test_unit_paper_for_chosen_chapters(
    client: TestClient, student: User, auth_headers: Headers, subject: Subject
) -> None:
    headers = auth_headers(student)
    bad = client.post(
        f"/api/v1/subjects/{subject.id}/model-papers",
        json={"scope": "chapters", "chapterIds": [99999]},
        headers=headers,
    )
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_chapters"
    chapter = subject.chapters[1]
    paper = _create_paper(client, headers, subject, scope="chapters", chapterIds=[chapter.id])
    assert paper["chapterIds"] == [chapter.id]
    detail = client.get(f"/api/v1/model-papers/{paper['id']}", headers=headers).json()
    assert detail["totalMarks"] == 50 and detail["durationMinutes"] == 90
    calls = [u for _, u, schema in get_fake_llm_client().calls if schema is GeneratedPart]
    assert "Numbers and Sequences" in calls[0] and "Relations and Functions" not in calls[0]


def test_daily_paper_limit(
    client: TestClient,
    student: User,
    auth_headers: Headers,
    subject: Subject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MODEL_PAPERS_PER_DAY", 1)
    headers = auth_headers(student)
    _create_paper(client, headers, subject)
    res = client.post(
        f"/api/v1/subjects/{subject.id}/model-papers", json={"scope": "full"}, headers=headers
    )
    assert res.status_code == 429 and res.json()["error"]["code"] == "paper_limit"


def test_generation_failure_is_reported(
    client: TestClient, student: User, auth_headers: Headers, subject: Subject
) -> None:
    def broken(system: str, user: str) -> GeneratedPart:
        raise LLMError("down")

    get_fake_llm_client().register(GeneratedPart, broken)
    headers = auth_headers(student)
    paper = _create_paper(client, headers, subject)
    assert paper["status"] == "generation_failed"
    doc = client.get(f"/api/v1/model-papers/{paper['id']}/document", headers=headers)
    assert doc.status_code == 409


def test_papers_are_private(
    client: TestClient,
    student: User,
    auth_headers: Headers,
    subject: Subject,
    make_user: Callable[..., User],
) -> None:
    paper = _create_paper(client, auth_headers(student), subject)
    other = make_user(role=UserRole.student, board_id=subject.board_id, medium=Medium.en)
    res = client.get(f"/api/v1/model-papers/{paper['id']}", headers=auth_headers(other))
    assert res.status_code == 404


def test_account_deletion_removes_exam_practice(
    client: TestClient, student: User, auth_headers: Headers, subject: Subject, db: Session
) -> None:
    headers = auth_headers(student)
    for topic in _topics(subject)[:3]:
        _pass_topic(client, headers, topic)
    client.post(f"/api/v1/subjects/{subject.id}/subject-tests", headers=headers)
    _create_paper(client, headers, subject)
    assert client.delete("/api/v1/auth/me", headers=headers).status_code in (200, 204)
    assert db.scalar(select(ModelPaper.id)) is None
    assert db.scalar(select(SubjectTest.id)) is None


# --- patterns and scoring ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("grade", "name", "scope", "pattern_id"),
    [
        (10, "Mathematics", "full", "sslc_100"),
        (9, "Social Science", "full", "sslc_100"),
        (10, "Science", "full", "sslc_science_75"),
        (10, "Tamil", "full", "sslc_tamil_100"),
        (10, "Science", "chapters", "sslc_science_unit_40"),
        (12, "Physics", "full", "hsc_70"),
        (11, "Accountancy", "full", "hsc_90"),
        (12, "English", "full", "hsc_90"),
        (11, "Chemistry", "chapters", "hsc_unit_50"),
    ],
)
def test_pattern_for_class_and_subject(grade: int, name: str, scope: str, pattern_id: str) -> None:
    assert pattern_for(grade, name, scope).id == pattern_id  # type: ignore[arg-type]


def test_every_pattern_adds_up() -> None:
    for pattern in PATTERNS.values():
        assert sum(p.total for p in pattern.parts) == pattern.total_marks, pattern.id
        assert all(p.answer <= p.printed for p in pattern.parts)


def test_scoring_counts_the_best_answers_of_each_part() -> None:
    paper = {
        "parts": [
            {
                "label": "II",
                "answer": 2,
                "marks": 2,
                "questions": [{"number": n} for n in (1, 2, 3)],
            },
            {"label": "IV", "answer": 1, "marks": 5, "questions": [{"number": 4}]},
        ]
    }
    answers = [
        GradedAnswer(number=1, attempted=True, choice="", marks=2, feedback=""),
        GradedAnswer(number=2, attempted=True, choice="", marks=0.5, feedback=""),
        GradedAnswer(number=3, attempted=True, choice="", marks=1.5, feedback=""),
        GradedAnswer(number=4, attempted=True, choice="b", marks=4, feedback=""),
    ]
    result = score_paper(paper, answers)
    assert result["score"] == 7.5
    assert result["parts"] == [
        {"label": "II", "scored": 3.5, "total": 4},
        {"label": "IV", "scored": 4, "total": 5},
    ]


def test_english_paper_is_in_english_for_tamil_medium(
    make_user: Callable[..., User], subject: Subject, db: Session
) -> None:
    student = make_user(role=UserRole.student, board_id=subject.board_id, medium=Medium.ta)
    english = Subject(
        board_id=subject.board_id,
        name="English",
        tile_color="#3B6EA5",
        icon="book",
        display_order=2,
    )
    db.add(english)
    db.commit()
    assert paper_language(student, english) == Medium.en
    assert paper_language(student, subject) == Medium.ta


def test_tamil_paper_and_key_labels() -> None:
    paper = {
        "header": {
            "board": "TN",
            "grade": 10,
            "subject": "கணிதம்",
            "scope": "full",
            "chapters": [],
            "total_marks": 100,
            "duration_minutes": 180,
        },
        "parts": [
            {
                "label": "I",
                "kind": "mcq",
                "marks": 1,
                "printed": 1,
                "answer": 1,
                "either_or": False,
                "questions": [
                    {"number": 1, "text": "<b>2+2?</b>", "options": ["3", "4", "5", "6"]}
                ],
            }
        ],
    }
    html = paper_html(paper, "ta")
    assert "பகுதி – I" in html and "3 மணி நேரம்" in html and "(ஆ) 4" in html
    assert "<b>2+2?</b>" not in html  # escaped
    key = key_html(paper, {"answers": {"1": {"answer": "4", "points": []}}}, None, "ta")
    assert "விடை" in key and "(ஆ) 4" in key
