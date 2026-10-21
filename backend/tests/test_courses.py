"""Classes per board (course = board + class), the 11th/12th subject group, language subjects
and one device at a time."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.billing import Purchase
from app.models.curriculum import (
    Board,
    Chapter,
    Subject,
    SubjectTranslation,
    Topic,
    TopicTranslation,
)
from app.models.enums import Medium, UserRole
from app.models.user import User
from app.schemas.admin import CurriculumImport
from app.services import auth_service
from app.services.ai import explanation, questions

Headers = Callable[[User], dict[str, str]]

GROUP = ["Tamil", "English", "Physics", "Chemistry", "Maths", "Biology", "Accountancy"]


@dataclass
class Classes:
    tenth: Board
    eleventh: Board
    hidden: Board
    group: list[Subject]  # eleventh's subjects; group[0] is Tamil (always in Tamil)
    tenth_maths: Subject

    @property
    def physics(self) -> Subject:
        return self.group[2]

    def six(self) -> list[int]:
        """A valid group: Tamil, English and four more (not Accountancy)."""
        return [s.id for s in self.group[:6]]

    def first_topic(self, subject: Subject) -> int:
        return subject.chapters[0].topics[0].id


@pytest.fixture()
def classes(db: Session) -> Classes:
    tenth = Board(code="TN_SSLC", name="TN Class 10", is_active=True, grade=10)
    eleventh = Board(
        code="TN_11", name="TN Class 11", is_active=True, grade=11, choose_subjects=True
    )
    hidden = Board(code="TN_12", name="TN Class 12", is_active=False, grade=12)
    group = [
        Subject(
            board=eleventh,
            name=name,
            tile_color="#3B6EA5",
            icon="book",
            display_order=i,
            fixed_medium="ta" if name == "Tamil" else None,
        )
        for i, name in enumerate(GROUP, start=1)
    ]
    for subject in group:
        chapter = Chapter(subject=subject, title=f"{subject.name} unit 1", display_order=1)
        Topic(chapter=chapter, title=f"{subject.name} topic 1", display_order=1, is_published=True)
    group[0].translations.append(SubjectTranslation(medium=Medium.ta, name="தமிழ்"))
    group[0].chapters[0].topics[0].translations.append(
        TopicTranslation(medium=Medium.ta, title="அன்னை மொழியே", learning_objectives="")
    )
    tenth_maths = Subject(
        board=tenth, name="Maths", tile_color="#3B6EA5", icon="calculator", display_order=1
    )
    db.add_all([tenth, eleventh, hidden, *group, tenth_maths])
    db.commit()
    return Classes(tenth, eleventh, hidden, group, tenth_maths)


def _pay(db: Session, user: User) -> None:
    now = datetime.now(UTC)
    db.add(
        Purchase(
            payer_user_id=user.id,
            beneficiary_user_id=user.id,
            kind="subscription",
            product_id="premium",
            purchase_token=f"tok-{user.id}-course",
            expires_at=now + timedelta(days=30),
            last_checked_at=now,
        )
    )
    db.commit()


def _lesson_language(body: dict[str, dict[str, dict[str, str]]]) -> str:
    lesson = body["lesson"] or body["job"]["lesson"]
    return lesson["language"]


# --- classes --------------------------------------------------------------------------------


def test_boards_list_active_classes_in_order(
    client: TestClient, classes: Classes, make_user: Callable[..., User], auth_headers: Headers
) -> None:
    user = make_user()
    body = client.get("/api/v1/boards", headers=auth_headers(user)).json()
    assert [(b["code"], b["grade"], b["chooseSubjects"]) for b in body] == [
        ("TN_SSLC", 10, False),
        ("TN_11", 11, True),
    ]
    assert body[0]["family"] == "TN_STATE"


def test_board_subjects_for_picker(
    client: TestClient, classes: Classes, make_user: Callable[..., User], auth_headers: Headers
) -> None:
    user = make_user(medium=Medium.en)
    res = client.get(f"/api/v1/boards/{classes.eleventh.id}/subjects", headers=auth_headers(user))
    assert [s["name"] for s in res.json()] == ["தமிழ்", *GROUP[1:]]  # Tamil named in Tamil
    hidden = client.get(f"/api/v1/boards/{classes.hidden.id}/subjects", headers=auth_headers(user))
    assert hidden.status_code == 404


def test_hidden_class_cannot_be_picked(
    client: TestClient, classes: Classes, make_user: Callable[..., User], auth_headers: Headers
) -> None:
    user = make_user()
    res = client.put(
        "/api/v1/auth/me", json={"boardId": classes.hidden.id}, headers=auth_headers(user)
    )
    assert res.status_code == 400


def test_admin_shows_hidden_class(
    client: TestClient, classes: Classes, make_user: Callable[..., User], auth_headers: Headers
) -> None:
    admin = make_user(role=UserRole.admin)
    res = client.patch(
        f"/api/v1/admin/boards/{classes.hidden.id}",
        json={"isActive": True},
        headers=auth_headers(admin),
    )
    assert res.status_code == 200
    assert res.json()["isActive"] is True
    student = make_user()
    res = client.patch(
        f"/api/v1/admin/boards/{classes.hidden.id}",
        json={"isActive": False},
        headers=auth_headers(student),
    )
    assert res.status_code == 403


# --- 11th / 12th subject group ----------------------------------------------------------------


def test_only_the_chosen_six_subjects_exist_for_the_student(
    client: TestClient, classes: Classes, make_user: Callable[..., User], auth_headers: Headers
) -> None:
    user = make_user(board_id=classes.eleventh.id, medium=Medium.en)
    headers = auth_headers(user)
    # Nothing chosen yet: no subjects at all (the app asks for the group first).
    assert client.get("/api/v1/subjects", headers=headers).json() == []
    assert client.get("/api/v1/auth/me", headers=headers).json()["needsSubjects"] is True

    res = client.put("/api/v1/auth/me", json={"subjectIds": classes.six()}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["subjectIds"] == classes.six()
    assert len(client.get("/api/v1/subjects", headers=headers).json()) == 6

    # The 7th subject is hidden and refused — even its free first topic.
    other = classes.group[6]
    topic_id = classes.first_topic(other)
    assert client.get(f"/api/v1/subjects/{other.id}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/topics/{topic_id}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/topics/{topic_id}/lesson", headers=headers).status_code == 404

    # Moving to another class clears the old group.
    res = client.put("/api/v1/auth/me", json={"boardId": classes.tenth.id}, headers=headers)
    assert res.json()["subjectIds"] == []
    assert [s["name"] for s in client.get("/api/v1/subjects", headers=headers).json()] == ["Maths"]


@pytest.mark.parametrize("count", [5, 7])
def test_group_must_have_exactly_six_subjects(
    client: TestClient,
    classes: Classes,
    make_user: Callable[..., User],
    auth_headers: Headers,
    count: int,
) -> None:
    user = make_user(board_id=classes.eleventh.id, medium=Medium.en)
    ids = [s.id for s in classes.group[:count]]
    res = client.put("/api/v1/auth/me", json={"subjectIds": ids}, headers=auth_headers(user))
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "invalid_subjects"


def test_cannot_choose_subjects_of_another_class(
    client: TestClient, classes: Classes, make_user: Callable[..., User], auth_headers: Headers
) -> None:
    user = make_user(board_id=classes.eleventh.id, medium=Medium.en)
    res = client.put(
        "/api/v1/auth/me",
        json={"subjectIds": [*classes.six()[:5], classes.tenth_maths.id]},
        headers=auth_headers(user),
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "invalid_subjects"


def test_class_and_subjects_are_fixed_after_payment(
    client: TestClient,
    db: Session,
    classes: Classes,
    make_user: Callable[..., User],
    auth_headers: Headers,
) -> None:
    user = make_user(board_id=classes.eleventh.id, medium=Medium.en)
    headers = auth_headers(user)
    assert client.get("/api/v1/auth/me", headers=headers).json()["classLocked"] is False
    client.put("/api/v1/auth/me", json={"subjectIds": classes.six()}, headers=headers)
    _pay(db, user)
    assert client.get("/api/v1/auth/me", headers=headers).json()["classLocked"] is True

    swap = [*classes.six()[:5], classes.group[6].id]
    for body in ({"subjectIds": swap}, {"boardId": classes.tenth.id}):
        res = client.put("/api/v1/auth/me", json=body, headers=headers)
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "class_locked"
    # Saving the same class and subjects (with a name change) is still fine.
    res = client.put(
        "/api/v1/auth/me",
        json={"fullName": "Kavya", "boardId": classes.eleventh.id, "subjectIds": classes.six()},
        headers=headers,
    )
    assert res.status_code == 200

    # An admin can still change them.
    admin = make_user(role=UserRole.admin)
    res = client.patch(
        f"/api/v1/admin/users/{user.id}", json={"subjectIds": swap}, headers=auth_headers(admin)
    )
    assert res.status_code == 200, res.text
    assert res.json()["subjectIds"] == sorted(swap)


# --- language subjects ------------------------------------------------------------------------


def test_tamil_subject_is_always_in_tamil(
    client: TestClient, classes: Classes, make_user: Callable[..., User], auth_headers: Headers
) -> None:
    user = make_user(board_id=classes.eleventh.id, medium=Medium.en, lesson_language="en")
    headers = auth_headers(user)
    client.put("/api/v1/auth/me", json={"subjectIds": classes.six()}, headers=headers)
    tiles = {s["id"]: s["name"] for s in client.get("/api/v1/subjects", headers=headers).json()}
    assert tiles[classes.group[0].id] == "தமிழ்"
    assert tiles[classes.physics.id] == "Physics"

    topic_id = classes.first_topic(classes.group[0])
    detail = client.get(f"/api/v1/topics/{topic_id}", headers=headers).json()
    assert detail["title"] == "அன்னை மொழியே"
    assert detail["languageFixed"] is True
    lesson = client.get(f"/api/v1/topics/{topic_id}/lesson", headers=headers).json()
    assert _lesson_language(lesson) == "ta"
    # Asking for English is ignored for the Tamil subject and not remembered.
    res = client.post(
        f"/api/v1/topics/{topic_id}/lesson-language", json={"language": "en"}, headers=headers
    )
    assert _lesson_language(res.json()) == "ta"
    assert client.get("/api/v1/auth/me", headers=headers).json()["lessonLanguage"] == "en"
    physics = client.get(
        f"/api/v1/topics/{classes.first_topic(classes.physics)}", headers=headers
    ).json()
    assert physics["languageFixed"] is False


# --- one device at a time -------------------------------------------------------------------


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_second_device_is_refused_while_the_first_is_in_use(
    client: TestClient, db: Session, classes: Classes, make_user: Callable[..., User]
) -> None:
    user = make_user(board_id=classes.tenth.id, medium=Medium.en)
    phone = auth_service.issue_tokens(db, user)
    tablet = auth_service.issue_tokens(db, user)

    assert client.get("/api/v1/subjects", headers=_bearer(phone.access_token)).status_code == 200
    res = client.get("/api/v1/subjects", headers=_bearer(tablet.access_token))
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "session_active"
    assert "active session" in res.json()["error"]["message"]

    # The phone closes the app: the tablet may now continue (and holds the account).
    res = client.post("/api/v1/auth/session/release", headers=_bearer(phone.access_token))
    assert res.status_code == 204
    assert client.get("/api/v1/subjects", headers=_bearer(tablet.access_token)).status_code == 200
    phone_again = client.post("/api/v1/auth/session/ping", headers=_bearer(phone.access_token))
    assert phone_again.status_code == 409

    # A refreshed token keeps its device's session.
    renewed = client.post("/api/v1/auth/refresh", json={"refreshToken": tablet.refresh_token})
    token = renewed.json()["accessToken"]
    assert client.post("/api/v1/auth/session/ping", headers=_bearer(token)).status_code == 204


def test_idle_session_and_sign_out_free_the_account(
    client: TestClient, db: Session, classes: Classes, make_user: Callable[..., User]
) -> None:
    user = make_user(board_id=classes.tenth.id, medium=Medium.en)
    phone = auth_service.issue_tokens(db, user)
    tablet = auth_service.issue_tokens(db, user)
    client.post("/api/v1/auth/session/ping", headers=_bearer(phone.access_token))

    # Phone not seen for a while (app killed without saying goodbye): the tablet takes over.
    user.active_session_seen_at = datetime.now(UTC) - timedelta(minutes=10)
    db.commit()
    assert client.get("/api/v1/subjects", headers=_bearer(tablet.access_token)).status_code == 200

    # Signing out on the tablet frees it for the phone straight away.
    client.post("/api/v1/auth/logout", json={"refreshToken": tablet.refresh_token})
    assert client.get("/api/v1/subjects", headers=_bearer(phone.access_token)).status_code == 200


def test_parents_and_admins_are_not_limited_to_one_device(
    client: TestClient, db: Session, make_user: Callable[..., User]
) -> None:
    parent = make_user(role=UserRole.parent)
    first = auth_service.issue_tokens(db, parent)
    second = auth_service.issue_tokens(db, parent)
    for tokens in (first, second):
        res = client.get("/api/v1/auth/me", headers=_bearer(tokens.access_token))
        assert res.status_code == 200


# --- import and prompts -----------------------------------------------------------------------


def test_import_creates_hidden_class_with_grade_and_language_subject(
    client: TestClient, db: Session, make_user: Callable[..., User], auth_headers: Headers
) -> None:
    admin = make_user(role=UserRole.admin)
    payload = {
        "boardCode": "TN_9",
        "boardName": "Tamil Nadu State Board - Class 9",
        "grade": 9,
        "isActive": False,
        "subjects": [
            {
                "name": "Tamil",
                "tileColor": "#4F8A6B",
                "displayOrder": 1,
                "fixedMedium": "ta",
                "chapters": [
                    {
                        "title": "Unit 1",
                        "displayOrder": 1,
                        "topics": [{"title": "Annai Mozhiye", "displayOrder": 1}],
                    }
                ],
            }
        ],
    }
    res = client.post("/api/v1/admin/curriculum/import", json=payload, headers=auth_headers(admin))
    assert res.status_code == 200, res.text
    board = db.query(Board).filter_by(code="TN_9").one()
    assert (board.grade, board.is_active, board.family) == (9, False, "TN_STATE")
    assert board.subjects[0].fixed_medium == "ta"


def test_prompts_follow_the_class() -> None:
    ctx = explanation.TopicContext(
        board="TN State Board",
        subject="Physics",
        chapter="Kinematics",
        topic="Projectile motion",
        learning_objectives="Derive the range",
        grade=11,
    )
    system, _ = explanation.build_prompts(ctx, explanation.LessonStyle.base, Medium.en, None)
    assert "Class 11 students (about 16 years old)" in system
    assert "derivations" in system
    q_system, _ = questions.build_prompts(ctx, Medium.en, 10, [])
    assert "Class 11 students" in q_system


@pytest.mark.parametrize(
    "name", ["tn_sslc_full.json", "tn_class9.json", "tn_class11.json", "tn_class12.json"]
)
def test_syllabus_files_are_valid(name: str) -> None:
    path = Path(__file__).resolve().parent.parent / "data" / "curriculum" / name
    data = CurriculumImport.model_validate_json(path.read_text(encoding="utf-8"))
    topics = [t for s in data.subjects for c in s.chapters for t in c.topics]
    assert topics
    assert all(t.title_ta and t.learning_objectives_ta for t in topics)
    # The Tamil language subjects are always studied in Tamil.
    tamil = [s for s in data.subjects if "Tamil" in s.name]
    assert tamil and all(s.fixed_medium == Medium.ta for s in tamil)
