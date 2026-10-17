"""Email sign-in: 6-digit codes, email + password, resets, limits and account linking."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.user import EmailCode, User
from app.services import email_auth_service
from app.services.email_service import OUTBOX

EMAIL = "Kavya.Student@Example.com"


@pytest.fixture(autouse=True)
def _clear_outbox() -> Iterator[None]:
    OUTBOX.clear()
    yield
    OUTBOX.clear()


def _request_code(client: TestClient, email: str = EMAIL) -> str:
    res = client.post("/api/v1/auth/email/code", json={"email": email})
    assert res.status_code == 202, res.text
    assert res.json() == {"sent": True, "expiresInMinutes": 10}
    return OUTBOX[-1].subject.split()[0]


def test_code_sign_in_creates_student(client: TestClient, db: Session) -> None:
    code = _request_code(client)
    assert OUTBOX[-1].to == EMAIL.lower() and code in OUTBOX[-1].body
    stored = db.scalar(select(EmailCode.code_hash))
    assert stored is not None and code not in stored  # only a keyed hash is stored
    res = client.post("/api/v1/auth/email/login", json={"email": EMAIL, "code": code})
    assert res.status_code == 200, res.text
    user = res.json()["user"]
    assert user["email"] == EMAIL.lower() and user["role"] == "student"
    assert user["hasPassword"] is False
    # A code works only once.
    again = client.post("/api/v1/auth/email/login", json={"email": EMAIL, "code": code})
    assert again.status_code == 401


def test_wrong_code_attempts_are_limited(client: TestClient) -> None:
    code = _request_code(client)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        res = client.post("/api/v1/auth/email/login", json={"email": EMAIL, "code": wrong})
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "invalid_code"
    # After 5 wrong guesses even the right code is refused.
    res = client.post("/api/v1/auth/email/login", json={"email": EMAIL, "code": code})
    assert res.status_code == 401


def test_new_code_replaces_old_and_codes_expire(client: TestClient, db: Session) -> None:
    first = _request_code(client)
    second = _request_code(client)
    if first != second:
        res = client.post("/api/v1/auth/email/login", json={"email": EMAIL, "code": first})
        assert res.status_code == 401
    row = db.scalars(select(EmailCode).order_by(EmailCode.id.desc())).first()
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    res = client.post("/api/v1/auth/email/login", json={"email": EMAIL, "code": second})
    assert res.status_code == 401


def test_codes_per_hour_are_limited(client: TestClient) -> None:
    for _ in range(5):
        _request_code(client)
    res = client.post("/api/v1/auth/email/code", json={"email": EMAIL})
    assert res.status_code == 429


def test_unknown_and_known_emails_get_the_same_reply(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    make_user(email="known@example.com")
    known = client.post("/api/v1/auth/email/code", json={"email": "known@example.com"})
    unknown = client.post("/api/v1/auth/email/code", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()


def test_sign_up_with_password_then_password_login(client: TestClient) -> None:
    code = _request_code(client)
    res = client.post(
        "/api/v1/auth/password/set",
        json={"email": EMAIL, "code": code, "password": "mango-tree-42", "fullName": "Kavya"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["user"]["hasPassword"] is True
    assert res.json()["user"]["fullName"] == "Kavya"
    ok = client.post(
        "/api/v1/auth/password/login", json={"email": EMAIL.upper(), "password": "mango-tree-42"}
    )
    assert ok.status_code == 200
    bad = client.post(
        "/api/v1/auth/password/login", json={"email": EMAIL, "password": "wrong-pass"}
    )
    unknown = client.post(
        "/api/v1/auth/password/login", json={"email": "x@example.com", "password": "mango-tree-42"}
    )
    assert bad.status_code == unknown.status_code == 401
    assert bad.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_forgot_password_resets_it(client: TestClient) -> None:
    code = _request_code(client)
    client.post(
        "/api/v1/auth/password/set", json={"email": EMAIL, "code": code, "password": "first-pass-1"}
    )
    code = _request_code(client)
    reset = {"email": EMAIL, "code": code, "password": "second-pass-2"}
    assert client.post("/api/v1/auth/password/set", json=reset).status_code == 200
    login = {"email": EMAIL, "password": "first-pass-1"}
    assert client.post("/api/v1/auth/password/login", json=login).status_code == 401
    login["password"] = "second-pass-2"
    assert client.post("/api/v1/auth/password/login", json=login).status_code == 200


def test_setting_password_needs_a_valid_code(client: TestClient) -> None:
    res = client.post(
        "/api/v1/auth/password/set",
        json={"email": EMAIL, "code": "123456", "password": "mango-tree-42"},
    )
    assert res.status_code == 401


@pytest.mark.parametrize("password", ["short", " leading-space", "aaaaaaaaaaaa", "x" * 73])
def test_weak_passwords_are_rejected(client: TestClient, password: str) -> None:
    code = _request_code(client)
    res = client.post(
        "/api/v1/auth/password/set", json={"email": EMAIL, "code": code, "password": password}
    )
    assert res.status_code == 422


def test_same_email_is_the_same_account_as_google(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    google_user = make_user(email="kavya@gmail.com", google_sub="g-123", oauth_provider="google")
    code = _request_code(client, "kavya@gmail.com")
    res = client.post("/api/v1/auth/email/login", json={"email": "kavya@gmail.com", "code": code})
    assert res.json()["user"]["id"] == google_user.id


def test_admins_must_use_google(
    client: TestClient, make_user: Callable[..., User], db: Session
) -> None:
    make_user(role=UserRole.admin, email="boss@example.com")
    code = email_auth_service.create_sign_in_code(db, "boss@example.com")
    res = client.post("/api/v1/auth/email/login", json={"email": "boss@example.com", "code": code})
    assert res.status_code == 403


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/v1/auth/email/code", {"email": "not-an-email"}),
        ("/api/v1/auth/email/login", {"email": EMAIL, "code": "12ab56"}),
    ],
)
def test_invalid_input_is_rejected(client: TestClient, path: str, body: dict[str, str]) -> None:
    assert client.post(path, json=body).status_code == 422
