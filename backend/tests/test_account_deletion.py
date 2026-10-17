"""Account deletion (DELETE /auth/me) and the public privacy / delete-account pages."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import Medium, UserRole
from app.models.notification import DeviceToken
from app.models.parent import ParentLink
from app.models.progress import StudyStreak
from app.models.user import RefreshToken, User

Headers = Callable[[User], dict[str, str]]


def _count(db: Session, model: type, **where: int) -> int:
    query = select(func.count()).select_from(model)
    for column, value in where.items():
        query = query.where(getattr(model, column) == value)
    return db.scalar(query) or 0


def test_student_can_delete_their_account(
    client: TestClient, db: Session, make_user: Callable[..., User], auth_headers: Headers
) -> None:
    student = make_user(role=UserRole.student, medium=Medium.en, email="kavya@example.com")
    parent = make_user(role=UserRole.parent, medium=Medium.ta, email="amma@example.com")
    code = client.post("/api/v1/parent-links/invite", headers=auth_headers(student)).json()["code"]
    linked = client.post("/api/v1/parent/links", json={"code": code}, headers=auth_headers(parent))
    assert linked.status_code in (200, 201), linked.text
    token = "ExponentPushToken[abc]"
    db.add(DeviceToken(user_id=student.id, expo_push_token=token, platform="android"))
    db.add(StudyStreak(user_id=student.id))
    db.commit()
    login = client.post("/api/v1/auth/dev-login", json={"email": "kavya@example.com"})
    assert login.status_code == 200
    student_id, parent_id = student.id, parent.id

    res = client.delete("/api/v1/auth/me", headers=auth_headers(student))
    assert res.status_code == 204, res.text

    db.expire_all()
    assert db.get(User, student_id) is None
    assert db.get(User, parent_id) is not None  # the parent keeps their own account
    for model in (DeviceToken, StudyStreak, RefreshToken):
        assert _count(db, model, user_id=student_id) == 0
    assert _count(db, ParentLink, student_user_id=student_id) == 0
    # The old access token no longer works.
    assert client.get("/api/v1/auth/me", headers=auth_headers(student)).status_code == 401


def test_admin_cannot_delete_own_account(
    client: TestClient, make_user: Callable[..., User], auth_headers: Headers
) -> None:
    admin = make_user(role=UserRole.admin)
    assert client.delete("/api/v1/auth/me", headers=auth_headers(admin)).status_code == 403


def test_delete_needs_sign_in(client: TestClient) -> None:
    assert client.delete("/api/v1/auth/me").status_code == 401


def test_public_pages(client: TestClient) -> None:
    for path, text in (("/privacy", "Privacy Policy"), ("/delete-account", "Delete your")):
        res = client.get(path)
        assert res.status_code == 200 and text in res.text
        assert res.headers["content-type"].startswith("text/html")
