"""Parent module: invite codes, linking, read-only reports, privacy (IDOR) and setup role."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.curriculum import Board, Chapter, Subject, Topic
from app.models.enums import Medium, UserRole
from app.models.parent import ParentLink
from app.models.quiz import QuizAttempt
from app.models.user import User
from app.schemas.parent import INVITE_CODE_ALPHABET
from app.services import progress_service

Headers = Callable[[User], dict[str, str]]


@pytest.fixture()
def topics(db: Session) -> tuple[Topic, Topic]:
    board = Board(code="TN_SSLC", name="Tamil Nadu State Board", is_active=True)
    subject = Subject(
        board=board, name="Science", tile_color="#4F8A6B", icon="flask", display_order=1
    )
    chapter = Chapter(subject=subject, title="Motion", display_order=1)
    first = Topic(chapter=chapter, title="Speed", display_order=1, is_published=True)
    second = Topic(chapter=chapter, title="Velocity", display_order=2, is_published=True)
    db.add_all([board, subject, chapter, first, second])
    db.commit()
    return first, second


@pytest.fixture()
def student(make_user: Callable[..., User], topics: tuple[Topic, Topic]) -> User:
    board_id = topics[0].chapter.subject.board_id
    return make_user(role=UserRole.student, board_id=board_id, medium=Medium.en, full_name="Kavya")


@pytest.fixture()
def parent(make_user: Callable[..., User]) -> User:
    return make_user(role=UserRole.parent, medium=Medium.ta, full_name="Amma")


def _invite(client: TestClient, headers: dict[str, str]) -> str:
    res = client.post("/api/v1/parent-links/invite", headers=headers)
    assert res.status_code == 200, res.text
    code: str = res.json()["code"]
    return code


def _redeem(client: TestClient, headers: dict[str, str], code: str) -> Any:
    return client.post("/api/v1/parent/links", json={"code": code}, headers=headers)


# --- invites ----------------------------------------------------------------------------------


def test_invite_code_format_and_reuse(
    client: TestClient, student: User, auth_headers: Headers
) -> None:
    headers = auth_headers(student)
    code = _invite(client, headers)
    assert len(code) == 8 and all(ch in INVITE_CODE_ALPHABET for ch in code)
    assert _invite(client, headers) == code  # same open invite is reused
    links = client.get("/api/v1/parent-links", headers=headers).json()
    assert links["invite"]["code"] == code and links["parents"] == []


def test_parent_links_with_code(
    client: TestClient, student: User, parent: User, auth_headers: Headers
) -> None:
    code = _invite(client, auth_headers(student))
    formatted = f"{code[:4].lower()}-{code[4:]}"  # dashes/lowercase are fine
    res = _redeem(client, auth_headers(parent), formatted)
    assert res.status_code == 201, res.text
    child = res.json()
    assert child["name"] == "Kavya" and child["topicsTotal"] == 2 and child["topicsCompleted"] == 0
    # The student sees the parent; the code is used up.
    links = client.get("/api/v1/parent-links", headers=auth_headers(student)).json()
    assert [p["name"] for p in links["parents"]] == ["Amma"] and links["invite"] is None
    other_parent_code_reuse = _redeem(client, auth_headers(parent), code)
    assert other_parent_code_reuse.status_code == 404


@pytest.mark.parametrize("code", ["ABC", "ABCD-EFG0", "OOOOIIII"])
def test_badly_formed_codes_rejected(
    client: TestClient, parent: User, auth_headers: Headers, code: str
) -> None:
    assert _redeem(client, auth_headers(parent), code).status_code == 422


def test_unknown_and_expired_codes(
    client: TestClient, db: Session, student: User, parent: User, auth_headers: Headers
) -> None:
    assert _redeem(client, auth_headers(parent), "ABCDEFGH").status_code == 404
    code = _invite(client, auth_headers(student))
    link = db.scalar(select(ParentLink).where(ParentLink.invite_code == code))
    assert link is not None
    link.invite_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    res = _redeem(client, auth_headers(parent), code)
    assert res.status_code == 410 and res.json()["error"]["code"] == "invite_expired"


def test_roles_are_enforced(
    client: TestClient, student: User, parent: User, auth_headers: Headers
) -> None:
    assert (
        client.post("/api/v1/parent-links/invite", headers=auth_headers(parent)).status_code == 403
    )
    code = _invite(client, auth_headers(student))
    assert _redeem(client, auth_headers(student), code).status_code == 403
    assert client.get("/api/v1/parent/children", headers=auth_headers(student)).status_code == 403
    # Parents can't use student learning endpoints either.
    assert client.get("/api/v1/subjects", headers=auth_headers(parent)).status_code == 403


def test_already_linked_conflict(
    client: TestClient, student: User, parent: User, auth_headers: Headers
) -> None:
    _redeem(client, auth_headers(parent), _invite(client, auth_headers(student)))
    second = _redeem(client, auth_headers(parent), _invite(client, auth_headers(student)))
    assert second.status_code == 409 and second.json()["error"]["code"] == "already_linked"


# --- reports & privacy ------------------------------------------------------------------------


def test_report_shows_progress_and_tests(
    client: TestClient,
    db: Session,
    student: User,
    parent: User,
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
) -> None:
    _redeem(client, auth_headers(parent), _invite(client, auth_headers(student)))
    now = datetime.now(UTC)
    for score in (40.0, 80.0):
        db.add(
            QuizAttempt(
                user_id=student.id,
                topic_id=topics[0].id,
                score_pct=score,
                passed=score >= 60,
                started_at=now,
                submitted_at=now,
                expires_at=now + timedelta(hours=1),
            )
        )
        progress_service.record_quiz_result(db, student, topics[0], score)
        db.commit()  # each real submission is committed on its own

    children = client.get("/api/v1/parent/children", headers=auth_headers(parent)).json()
    assert len(children) == 1 and children[0]["topicsCompleted"] == 1
    assert children[0]["testsThisWeek"] == 2 and children[0]["averageScoreThisWeek"] == 60.0

    report = client.get(
        f"/api/v1/parent/children/{student.id}", headers=auth_headers(parent)
    ).json()
    statuses = {t["title"]: t["status"] for s in report["subjectsDetail"] for t in s["topics"]}
    assert statuses == {"Speed": "completed", "Velocity": "available"}
    assert [t["scorePct"] for t in report["recentTests"]] == [40.0, 80.0] or [
        t["scorePct"] for t in report["recentTests"]
    ] == [80.0, 40.0]
    assert report["recentTests"][0]["subjectName"] == "Science"


def test_unlinked_parent_cannot_see_child(
    client: TestClient,
    student: User,
    parent: User,
    make_user: Callable[..., User],
    auth_headers: Headers,
) -> None:
    _redeem(client, auth_headers(parent), _invite(client, auth_headers(student)))
    stranger = make_user(role=UserRole.parent)
    res = client.get(f"/api/v1/parent/children/{student.id}", headers=auth_headers(stranger))
    assert res.status_code == 404
    assert client.get("/api/v1/parent/children", headers=auth_headers(stranger)).json() == []


def test_student_can_remove_parent(
    client: TestClient, student: User, parent: User, auth_headers: Headers
) -> None:
    _redeem(client, auth_headers(parent), _invite(client, auth_headers(student)))
    link_id = client.get("/api/v1/parent-links", headers=auth_headers(student)).json()["parents"][
        0
    ]["linkId"]
    assert (
        client.delete(f"/api/v1/parent-links/{link_id}", headers=auth_headers(student)).status_code
        == 204
    )
    assert (
        client.get(
            f"/api/v1/parent/children/{student.id}", headers=auth_headers(parent)
        ).status_code
        == 404
    )
    # The same parent can be re-linked with a fresh code.
    again = _redeem(client, auth_headers(parent), _invite(client, auth_headers(student)))
    assert again.status_code == 201


def test_other_students_link_cannot_be_removed(
    client: TestClient,
    student: User,
    parent: User,
    make_user: Callable[..., User],
    auth_headers: Headers,
) -> None:
    _redeem(client, auth_headers(parent), _invite(client, auth_headers(student)))
    link_id = client.get("/api/v1/parent-links", headers=auth_headers(student)).json()["parents"][
        0
    ]["linkId"]
    other = make_user(role=UserRole.student)
    assert (
        client.delete(f"/api/v1/parent-links/{link_id}", headers=auth_headers(other)).status_code
        == 404
    )


def test_parent_limit(
    client: TestClient, student: User, make_user: Callable[..., User], auth_headers: Headers
) -> None:
    for _ in range(4):
        _redeem(
            client,
            auth_headers(make_user(role=UserRole.parent)),
            _invite(client, auth_headers(student)),
        )
    res = client.post("/api/v1/parent-links/invite", headers=auth_headers(student))
    assert res.status_code == 409 and res.json()["error"]["code"] == "too_many_parents"


# --- setup role --------------------------------------------------------------------------------


def test_new_user_can_choose_parent_role(
    client: TestClient, make_user: Callable[..., User], auth_headers: Headers
) -> None:
    newcomer = make_user(role=UserRole.student)
    res = client.put(
        "/api/v1/auth/me", json={"role": "parent", "medium": "ta"}, headers=auth_headers(newcomer)
    )
    assert res.status_code == 200 and res.json()["role"] == "parent"


def test_role_locked_after_studying(
    client: TestClient,
    db: Session,
    student: User,
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
) -> None:
    progress_service.start_topic(db, student, topics[0].id)
    res = client.put("/api/v1/auth/me", json={"role": "parent"}, headers=auth_headers(student))
    assert res.status_code == 409 and res.json()["error"]["code"] == "role_locked"


def test_admin_cannot_self_change_role(
    client: TestClient, make_user: Callable[..., User], auth_headers: Headers
) -> None:
    admin = make_user(role=UserRole.admin)
    assert (
        client.put(
            "/api/v1/auth/me", json={"role": "parent"}, headers=auth_headers(admin)
        ).status_code
        == 403
    )
