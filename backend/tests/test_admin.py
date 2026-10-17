"""Admin panel API: access control, curriculum editing/import, lessons, questions, users."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.curriculum import Board, Topic
from app.models.enums import Medium, UserRole
from app.models.user import User
from app.services.ai.tts import _silent_mp3

Headers = Callable[[User], dict[str, str]]

IMPORT: dict[str, Any] = {
    "boardCode": "TN_SSLC",
    "subjects": [
        {
            "name": "Mathematics",
            "nameTa": "கணிதம்",
            "tileColor": "#3B6EA5",
            "icon": "calculator-variant",
            "displayOrder": 1,
            "chapters": [
                {
                    "title": "Sets",
                    "titleTa": "கணங்கள்",
                    "displayOrder": 1,
                    "topics": [
                        {
                            "title": "What is a set",
                            "titleTa": "கணம்",
                            "learningObjectives": "Define a set",
                            "displayOrder": 1,
                        },
                        {
                            "title": "Venn diagrams",
                            "learningObjectives": "Draw Venn diagrams",
                            "displayOrder": 2,
                        },
                    ],
                }
            ],
        }
    ],
}


@pytest.fixture()
def board(db: Session) -> Board:
    row = Board(code="TN_SSLC", name="Tamil Nadu State Board", is_active=True)
    db.add(row)
    db.commit()
    return row


@pytest.fixture()
def admin(make_user: Callable[..., User]) -> User:
    return make_user(role=UserRole.admin)


@pytest.fixture()
def imported(
    client: TestClient, admin: User, auth_headers: Headers, board: Board
) -> dict[str, Any]:
    res = client.post("/api/v1/admin/curriculum/import", json=IMPORT, headers=auth_headers(admin))
    assert res.status_code == 200, res.text
    tree = client.get(
        f"/api/v1/admin/boards/{board.id}/curriculum", headers=auth_headers(admin)
    ).json()
    return tree


def _first_topic_id(tree: dict[str, Any]) -> int:
    return int(tree["subjects"][0]["chapters"][0]["topics"][0]["id"])


# --- access ---------------------------------------------------------------------------------


@pytest.mark.parametrize("role", [UserRole.student, UserRole.parent])
def test_non_admins_forbidden(
    client: TestClient, make_user: Callable[..., User], auth_headers: Headers, role: UserRole
) -> None:
    user = make_user(role=role)
    for path in ("/api/v1/admin/stats", "/api/v1/admin/users", "/api/v1/admin/questions"):
        assert client.get(path, headers=auth_headers(user)).status_code == 403


def test_stats(
    client: TestClient, admin: User, auth_headers: Headers, imported: dict[str, Any]
) -> None:
    res = client.get("/api/v1/admin/stats", headers=auth_headers(admin))
    assert res.status_code == 200
    body = res.json()
    assert body["subjects"] == 1 and body["topicsPublished"] == 2 and body["passRateWeek"] is None


# --- curriculum -----------------------------------------------------------------------------


def test_import_creates_tree_with_tamil(
    client: TestClient,
    admin: User,
    auth_headers: Headers,
    board: Board,
    imported: dict[str, Any],
    make_user: Callable[..., User],
) -> None:
    subject = imported["subjects"][0]
    assert subject["nameTa"] == "கணிதம்"
    assert [t["title"] for t in subject["chapters"][0]["topics"]] == [
        "What is a set",
        "Venn diagrams",
    ]
    tamil = make_user(role=UserRole.student, board_id=board.id, medium=Medium.ta)
    tile = client.get("/api/v1/subjects", headers=auth_headers(tamil)).json()[0]
    assert tile["name"] == "கணிதம்" and tile["currentTopic"]["title"] == "கணம்"


def test_reimport_updates_instead_of_duplicating(
    client: TestClient, admin: User, auth_headers: Headers, board: Board, imported: dict[str, Any]
) -> None:
    changed = {**IMPORT}
    changed["subjects"] = [{**IMPORT["subjects"][0], "name": "Maths"}]
    res = client.post("/api/v1/admin/curriculum/import", json=changed, headers=auth_headers(admin))
    assert res.json() == {"created": {}, "updated": {"subjects": 1, "chapters": 1, "topics": 2}}
    tree = client.get(
        f"/api/v1/admin/boards/{board.id}/curriculum", headers=auth_headers(admin)
    ).json()
    assert tree["subjects"][0]["name"] == "Maths" and len(tree["subjects"]) == 1


def test_tile_color_must_be_from_palette(
    client: TestClient, admin: User, auth_headers: Headers, board: Board
) -> None:
    res = client.post(
        "/api/v1/admin/subjects",
        json={"boardId": board.id, "name": "Art", "tileColor": "#FF00FF"},
        headers=auth_headers(admin),
    )
    assert res.status_code == 422


def test_create_with_auto_order_and_duplicate_order_conflict(
    client: TestClient, admin: User, auth_headers: Headers, imported: dict[str, Any]
) -> None:
    headers = auth_headers(admin)
    chapter_id = imported["subjects"][0]["chapters"][0]["id"]
    assert (
        client.post(
            "/api/v1/admin/topics",
            json={"chapterId": chapter_id, "title": "Subsets"},
            headers=headers,
        ).status_code
        == 201
    )
    dup = client.post(
        "/api/v1/admin/topics",
        json={"chapterId": chapter_id, "title": "Again", "displayOrder": 1},
        headers=headers,
    )
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "display_order_taken"


def test_unpublished_topic_hidden_from_students(
    client: TestClient,
    admin: User,
    auth_headers: Headers,
    board: Board,
    imported: dict[str, Any],
    make_user: Callable[..., User],
) -> None:
    topic_id = _first_topic_id(imported)
    res = client.patch(
        f"/api/v1/admin/topics/{topic_id}", json={"isPublished": False}, headers=auth_headers(admin)
    )
    assert res.status_code == 200
    student = make_user(role=UserRole.student, board_id=board.id, medium=Medium.en)
    tile = client.get("/api/v1/subjects", headers=auth_headers(student)).json()[0]
    assert tile["totalTopics"] == 1 and tile["currentTopic"]["title"] == "Venn diagrams"


# --- lessons --------------------------------------------------------------------------------


def test_uploaded_lesson_is_served_to_students(
    client: TestClient,
    admin: User,
    auth_headers: Headers,
    board: Board,
    imported: dict[str, Any],
    make_user: Callable[..., User],
) -> None:
    topic_id = _first_topic_id(imported)
    res = client.post(
        f"/api/v1/admin/topics/{topic_id}/lessons",
        data={"medium": "en", "style": "base", "title": "Teacher's lesson"},
        files={"file": ("lesson.mp3", _silent_mp3(), "audio/mpeg")},
        headers=auth_headers(admin),
    )
    assert res.status_code == 201, res.text
    assert res.json()["source"] == "uploaded"
    student = make_user(role=UserRole.student, board_id=board.id, medium=Medium.en)
    opened = client.get(f"/api/v1/topics/{topic_id}/lesson", headers=auth_headers(student))
    assert opened.status_code == 200
    assert opened.json()["lesson"]["title"] == "Teacher's lesson"


def test_upload_rejects_other_file_types(
    client: TestClient, admin: User, auth_headers: Headers, imported: dict[str, Any]
) -> None:
    res = client.post(
        f"/api/v1/admin/topics/{_first_topic_id(imported)}/lessons",
        data={"medium": "en"},
        files={"file": ("notes.pdf", b"%PDF-1.4", "application/pdf")},
        headers=auth_headers(admin),
    )
    assert res.status_code == 400 and res.json()["error"]["code"] == "unsupported_media"


def test_flagged_lesson_not_served(
    client: TestClient,
    admin: User,
    auth_headers: Headers,
    board: Board,
    imported: dict[str, Any],
    make_user: Callable[..., User],
) -> None:
    topic_id = _first_topic_id(imported)
    student = make_user(role=UserRole.student, board_id=board.id, medium=Medium.en)
    first = client.get(f"/api/v1/topics/{topic_id}/lesson", headers=auth_headers(student)).json()
    lesson_id = first["job"]["lesson"]["id"]
    lessons = client.get(
        f"/api/v1/admin/lessons?topicId={topic_id}", headers=auth_headers(admin)
    ).json()
    assert lessons["total"] == 1 and lessons["items"][0]["id"] == lesson_id
    client.patch(
        f"/api/v1/admin/lessons/{lesson_id}", json={"isFlagged": True}, headers=auth_headers(admin)
    )
    other = make_user(role=UserRole.student, board_id=board.id, medium=Medium.en)
    again = client.get(f"/api/v1/topics/{topic_id}/lesson", headers=auth_headers(other)).json()
    assert again["job"]["lesson"]["id"] != lesson_id


# --- questions ------------------------------------------------------------------------------


def _question(topic_id: int, **overrides: Any) -> dict[str, Any]:
    body = {
        "topicId": topic_id,
        "medium": "en",
        "stem": "Which is a set?",
        "options": ["{1, 2}", "(1, 2)", "[1, 2]", "1-2"],
        "correctAnswer": "{1, 2}",
        "explanation": "Sets use curly braces.",
        "difficulty": 1,
    }
    body.update(overrides)
    return body


def test_admin_questions_validated(
    client: TestClient, admin: User, auth_headers: Headers, imported: dict[str, Any]
) -> None:
    headers = auth_headers(admin)
    topic_id = _first_topic_id(imported)
    bad = client.post(
        "/api/v1/admin/questions", json=_question(topic_id, correctAnswer="{3}"), headers=headers
    )
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_question"
    ok = client.post("/api/v1/admin/questions", json=_question(topic_id), headers=headers)
    assert ok.status_code == 201 and ok.json()["source"] == "admin" and ok.json()["isApproved"]
    dup = client.post("/api/v1/admin/questions", json=_question(topic_id), headers=headers)
    assert dup.status_code == 409


def test_edit_and_flag_question(
    client: TestClient, admin: User, auth_headers: Headers, imported: dict[str, Any]
) -> None:
    headers = auth_headers(admin)
    qid = client.post(
        "/api/v1/admin/questions", json=_question(_first_topic_id(imported)), headers=headers
    ).json()["id"]
    invalid = client.patch(
        f"/api/v1/admin/questions/{qid}", json={"correctAnswer": "nope"}, headers=headers
    )
    assert invalid.status_code == 400
    flagged = client.patch(
        f"/api/v1/admin/questions/{qid}",
        json={"isFlagged": True, "stem": "Pick the set"},
        headers=headers,
    )
    assert flagged.json()["isFlagged"] is True and flagged.json()["stem"] == "Pick the set"
    listed = client.get("/api/v1/admin/questions?flagged=true", headers=headers).json()
    assert [q["id"] for q in listed["items"]] == [qid]


# --- users ----------------------------------------------------------------------------------


def test_users_search_disable_and_self_protection(
    client: TestClient,
    db: Session,
    admin: User,
    make_user: Callable[..., User],
    auth_headers: Headers,
) -> None:
    headers = auth_headers(admin)
    kavya = make_user(role=UserRole.student, email="kavya@school.in", full_name="Kavya R")
    found = client.get("/api/v1/admin/users?q=kavya", headers=headers).json()
    assert [u["id"] for u in found["items"]] == [kavya.id]
    res = client.patch(f"/api/v1/admin/users/{kavya.id}", json={"isActive": False}, headers=headers)
    assert res.status_code == 200 and res.json()["isActive"] is False
    assert client.get("/api/v1/auth/me", headers=auth_headers(kavya)).status_code == 401
    self_res = client.patch(
        f"/api/v1/admin/users/{admin.id}", json={"role": "student"}, headers=headers
    )
    assert self_res.status_code == 403
    assert db.scalar(select(User.role).where(User.id == admin.id)) == UserRole.admin
    assert db.scalar(select(Topic.id)) is None  # untouched curriculum


def test_upload_checks_real_file_contents(
    client: TestClient, admin: User, auth_headers: Headers, imported: dict[str, Any]
) -> None:
    res = client.post(
        f"/api/v1/admin/topics/{_first_topic_id(imported)}/lessons",
        data={"medium": "en"},
        files={"file": ("fake.mp4", b"<html>not a video</html>", "video/mp4")},
        headers=auth_headers(admin),
    )
    assert res.status_code == 400 and res.json()["error"]["code"] == "unsupported_media"


def test_full_syllabus_file_imports(db: Session, board: Board) -> None:
    """The shipped TN SSLC syllabus is valid and loads in order, in English and Tamil."""
    from app.cli import DEFAULT_CURRICULUM, main
    from app.models.curriculum import Subject

    assert main(["import-curriculum", str(DEFAULT_CURRICULUM)]) == 0
    db.expire_all()
    subjects = db.scalars(select(Subject).order_by(Subject.display_order)).all()
    names = ["Mathematics", "Science", "Social Science", "Tamil", "English"]
    assert [s.name for s in subjects] == names
    topics = db.scalars(select(Topic)).all()
    assert len(topics) > 250
    assert all(t.learning_objectives for t in topics)
    first = subjects[0].chapters[0].topics[0]
    assert first.title == "Ordered Pair"
    assert {t.medium: t.title for t in first.translations}[Medium.ta] == "வரிசைச் சோடி"
    # Re-running updates in place instead of duplicating.
    assert main(["import-curriculum", str(DEFAULT_CURRICULUM)]) == 0
    assert len(db.scalars(select(Topic)).all()) == len(topics)


def test_import_curriculum_cli_reports_missing_board(db: Session, tmp_path: Any) -> None:
    from app.cli import main

    bad = tmp_path / "x.json"
    bad.write_text('{"boardCode": "NOPE", "subjects": []}', encoding="utf-8")
    assert main(["import-curriculum", str(bad)]) == 2
    assert main(["import-curriculum", str(tmp_path / "missing.json")]) == 2


def test_full_syllabus_creates_board_on_empty_database(db: Session) -> None:
    """A fresh production database gets the board from the file's boardName."""
    from app.cli import DEFAULT_CURRICULUM, main

    assert db.scalar(select(Board).where(Board.code == "TN_SSLC")) is None
    assert main(["import-curriculum", str(DEFAULT_CURRICULUM)]) == 0
    db.expire_all()
    board = db.scalar(select(Board).where(Board.code == "TN_SSLC"))
    assert board is not None and board.is_active and board.name.startswith("Tamil Nadu")
