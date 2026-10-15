"""Progress module: every subject open, sequential unlocking within a subject, 60% gate."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.curriculum import Board, Chapter, Subject, Topic, TopicTranslation
from app.models.enums import Medium, UserRole
from app.models.user import User
from app.services import progress_service

Headers = Callable[[User], dict[str, str]]


@dataclass
class Curriculum:
    board: Board
    maths: Subject
    science: Subject
    m1: Topic  # Maths ch1 topic 1
    m2: Topic  # Maths ch1 topic 2
    m_draft: Topic  # unpublished, between m2 and m3
    m3: Topic  # Maths ch2 topic 1
    s1: Topic  # Science ch1 topic 1
    s2: Topic  # Science ch1 topic 2
    other_board_topic: Topic


def _topic(chapter: Chapter, order: int, title: str, published: bool = True) -> Topic:
    return Topic(
        chapter=chapter,
        title=title,
        learning_objectives=f"Understand {title}",
        display_order=order,
        is_published=published,
    )


@pytest.fixture()
def curriculum(db: Session) -> Curriculum:
    board = Board(code="TN_SSLC", name="TN SSLC", is_active=True)
    other = Board(code="CBSE", name="CBSE", is_active=True)
    maths = Subject(
        board=board, name="Maths", tile_color="#3B6EA5", icon="calculator", display_order=1
    )
    science = Subject(
        board=board, name="Science", tile_color="#4F8A6B", icon="flask", display_order=2
    )
    other_subject = Subject(
        board=other, name="Maths", tile_color="#3B6EA5", icon="calculator", display_order=1
    )
    # Chapter 2 is inserted first to prove ordering uses display_order, not ids.
    m_ch2 = Chapter(subject=maths, title="Algebra", display_order=2)
    m_ch1 = Chapter(subject=maths, title="Sets", display_order=1)
    s_ch1 = Chapter(subject=science, title="Motion", display_order=1)
    o_ch1 = Chapter(subject=other_subject, title="Numbers", display_order=1)
    m3 = _topic(m_ch2, 1, "Polynomials")
    m2 = _topic(m_ch1, 2, "Venn diagrams")
    m1 = _topic(m_ch1, 1, "What is a set")
    m_draft = _topic(m_ch1, 3, "Draft topic", published=False)
    s1 = _topic(s_ch1, 1, "Speed")
    s2 = _topic(s_ch1, 2, "Velocity")
    other_topic = _topic(o_ch1, 1, "Integers")
    m1.translations.append(
        TopicTranslation(medium=Medium.ta, title="கணம் என்றால் என்ன", learning_objectives="கணம்")
    )
    db.add_all(
        [board, other, maths, science, other_subject, m3, m2, m1, m_draft, s1, s2, other_topic]
    )
    db.commit()
    return Curriculum(board, maths, science, m1, m2, m_draft, m3, s1, s2, other_topic)


@pytest.fixture()
def student(make_user: Callable[..., User], curriculum: Curriculum) -> User:
    return make_user(role=UserRole.student, board_id=curriculum.board.id, medium=Medium.en)


def _subject_states(
    client: TestClient, headers: dict[str, str], subject: Subject
) -> dict[str, str]:
    body = client.get(f"/api/v1/subjects/{subject.id}", headers=headers).json()
    return {t["title"]: t["status"] for ch in body["chapters"] for t in ch["topics"]}


def _pass(db: Session, user: User, topic: Topic, score: float = 80.0) -> bool:
    passed = progress_service.record_quiz_result(db, user, topic, score)
    db.commit()
    return passed


# --- Initial state -----------------------------------------------------------------------


def test_all_subjects_open_with_first_topic_available(
    client: TestClient, student: User, auth_headers: Headers, curriculum: Curriculum
) -> None:
    res = client.get("/api/v1/subjects", headers=auth_headers(student))
    assert res.status_code == 200
    tiles = res.json()
    assert [t["name"] for t in tiles] == ["Maths", "Science"]
    maths, science = tiles
    assert maths["currentTopic"] == {
        "id": curriculum.m1.id,
        "title": "What is a set",
        "status": "available",
    }
    assert science["currentTopic"]["id"] == curriculum.s1.id
    assert maths["totalTopics"] == 3 and maths["completedTopics"] == 0  # draft not counted
    assert maths["tileColor"] == "#3B6EA5"


def test_only_first_topic_of_subject_is_open(
    client: TestClient, student: User, auth_headers: Headers, curriculum: Curriculum
) -> None:
    states = _subject_states(client, auth_headers(student), curriculum.maths)
    assert states == {
        "What is a set": "available",
        "Venn diagrams": "locked",
        "Polynomials": "locked",
    }


def test_locked_topic_returns_403(
    client: TestClient, student: User, auth_headers: Headers, curriculum: Curriculum
) -> None:
    headers = auth_headers(student)
    res = client.get(f"/api/v1/topics/{curriculum.m2.id}", headers=headers)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "topic_locked"
    assert (
        client.post(f"/api/v1/topics/{curriculum.m2.id}/start", headers=headers).status_code == 403
    )


def test_open_topic_detail(
    client: TestClient, student: User, auth_headers: Headers, curriculum: Curriculum
) -> None:
    res = client.get(f"/api/v1/topics/{curriculum.m1.id}", headers=auth_headers(student))
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "available"
    assert body["chapterTitle"] == "Sets"
    assert body["subject"] == {"id": curriculum.maths.id, "name": "Maths", "tileColor": "#3B6EA5"}
    assert body["passPct"] == 60


# --- Studying several subjects at once ----------------------------------------------------


def test_can_start_topics_in_several_subjects(
    client: TestClient, student: User, auth_headers: Headers, curriculum: Curriculum
) -> None:
    headers = auth_headers(student)
    a = client.post(f"/api/v1/topics/{curriculum.m1.id}/start", headers=headers)
    b = client.post(f"/api/v1/topics/{curriculum.s1.id}/start", headers=headers)
    assert a.status_code == 200 and a.json()["status"] == "active"
    assert b.status_code == 200 and b.json()["status"] == "active"
    # Idempotent.
    assert (
        client.post(f"/api/v1/topics/{curriculum.m1.id}/start", headers=headers).json()["status"]
        == "active"
    )


# --- 60% gate -------------------------------------------------------------------------------


def test_score_below_pass_mark_keeps_next_topic_locked(
    client: TestClient, db: Session, student: User, auth_headers: Headers, curriculum: Curriculum
) -> None:
    assert _pass(db, student, curriculum.m1, 59.9) is False
    states = _subject_states(client, auth_headers(student), curriculum.maths)
    assert states["What is a set"] == "active"
    assert states["Venn diagrams"] == "locked"


def test_score_at_pass_mark_unlocks_next_topic(
    client: TestClient, db: Session, student: User, auth_headers: Headers, curriculum: Curriculum
) -> None:
    assert _pass(db, student, curriculum.m1, 60.0) is True
    headers = auth_headers(student)
    states = _subject_states(client, headers, curriculum.maths)
    assert states == {
        "What is a set": "completed",
        "Venn diagrams": "available",
        "Polynomials": "locked",
    }
    # Other subjects are unaffected.
    assert _subject_states(client, headers, curriculum.science)["Velocity"] == "locked"
    tile = client.get("/api/v1/subjects", headers=headers).json()[0]
    assert tile["completedTopics"] == 1 and tile["currentTopic"]["id"] == curriculum.m2.id


def test_unlocking_crosses_chapters_and_skips_unpublished(
    client: TestClient, db: Session, student: User, auth_headers: Headers, curriculum: Curriculum
) -> None:
    _pass(db, student, curriculum.m1)
    _pass(db, student, curriculum.m2)
    states = _subject_states(client, auth_headers(student), curriculum.maths)
    assert states["Polynomials"] == "available"
    assert "Draft topic" not in states


def test_completed_topic_stays_open_for_review(
    client: TestClient, db: Session, student: User, auth_headers: Headers, curriculum: Curriculum
) -> None:
    _pass(db, student, curriculum.m1, 90)
    _pass(db, student, curriculum.m1, 40)  # a later low score never re-locks
    res = client.get(f"/api/v1/topics/{curriculum.m1.id}", headers=auth_headers(student))
    assert res.status_code == 200
    assert res.json()["status"] == "completed"
    assert res.json()["bestScorePct"] == 90


def test_finished_subject_has_no_current_topic(
    client: TestClient, db: Session, student: User, auth_headers: Headers, curriculum: Curriculum
) -> None:
    for topic in (curriculum.s1, curriculum.s2):
        _pass(db, student, topic)
    science = client.get("/api/v1/subjects", headers=auth_headers(student)).json()[1]
    assert science["currentTopic"] is None and science["completedTopics"] == 2


# --- Isolation & guards ---------------------------------------------------------------------


def test_progress_is_per_student(
    client: TestClient,
    db: Session,
    student: User,
    make_user: Callable[..., User],
    auth_headers: Headers,
    curriculum: Curriculum,
) -> None:
    _pass(db, student, curriculum.m1)
    other = make_user(role=UserRole.student, board_id=curriculum.board.id, medium=Medium.en)
    assert (
        _subject_states(client, auth_headers(other), curriculum.maths)["Venn diagrams"] == "locked"
    )


def test_other_board_topic_not_found(
    client: TestClient, student: User, auth_headers: Headers, curriculum: Curriculum
) -> None:
    res = client.get(
        f"/api/v1/topics/{curriculum.other_board_topic.id}", headers=auth_headers(student)
    )
    assert res.status_code == 404


def test_tamil_medium_titles(
    client: TestClient,
    make_user: Callable[..., User],
    auth_headers: Headers,
    curriculum: Curriculum,
) -> None:
    tamil = make_user(role=UserRole.student, board_id=curriculum.board.id, medium=Medium.ta)
    tile = client.get("/api/v1/subjects", headers=auth_headers(tamil)).json()[0]
    assert tile["currentTopic"]["title"] == "கணம் என்றால் என்ன"


def test_onboarding_required(
    client: TestClient,
    make_user: Callable[..., User],
    auth_headers: Headers,
    curriculum: Curriculum,
) -> None:
    res = client.get("/api/v1/subjects", headers=auth_headers(make_user(role=UserRole.student)))
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "onboarding_required"


@pytest.mark.parametrize("role", [UserRole.parent, UserRole.admin])
def test_non_students_forbidden(
    client: TestClient,
    make_user: Callable[..., User],
    auth_headers: Headers,
    curriculum: Curriculum,
    role: UserRole,
) -> None:
    user = make_user(role=role, board_id=curriculum.board.id)
    assert client.get("/api/v1/subjects", headers=auth_headers(user)).status_code == 403


def test_compute_states_pure() -> None:
    from app.models.enums import TopicStatus
    from app.models.progress import TopicProgress

    progress: dict[int, Any] = {
        1: TopicProgress(status=TopicStatus.completed),
        2: TopicProgress(status=TopicStatus.active),
    }
    states = progress_service.compute_states([1, 2, 3], progress)
    assert [s.value for s in states.values()] == ["completed", "active", "locked"]
