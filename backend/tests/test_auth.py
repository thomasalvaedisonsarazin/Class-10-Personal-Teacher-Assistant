"""Auth module: Google sign-in, dev login, refresh rotation, logout, profile."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.jwt import sha256_hex
from app.config import settings
from app.exceptions import UnauthorizedError
from app.main import app as fastapi_app
from app.models.curriculum import Board
from app.models.enums import UserRole
from app.models.user import RefreshToken, User
from app.services import google_auth
from app.services.google_auth import GoogleIdentity, get_google_verifier

FAKE_ID_TOKEN = "fake-google-id-token-0123456789"


@pytest.fixture()
def google_identity() -> Iterator[Callable[[GoogleIdentity], None]]:
    """Make ``/auth/google`` accept any token as the given identity."""

    def _set(identity: GoogleIdentity) -> None:
        fastapi_app.dependency_overrides[get_google_verifier] = lambda: lambda _token: identity

    yield _set
    fastapi_app.dependency_overrides.pop(get_google_verifier, None)


def _identity(email: str = "kavya@gmail.com", sub: str = "google-sub-1") -> GoogleIdentity:
    return GoogleIdentity(sub=sub, email=email, name="Kavya", picture="https://img/k.png")


def _google_login(client: TestClient) -> Any:
    return client.post("/api/v1/auth/google", json={"idToken": FAKE_ID_TOKEN})


# --- Google sign-in -------------------------------------------------------------------


def test_google_login_creates_student(
    client: TestClient, db: Session, google_identity: Callable[[GoogleIdentity], None]
) -> None:
    google_identity(_identity())
    res = _google_login(client)
    assert res.status_code == 200
    body = res.json()
    assert body["accessToken"] and body["refreshToken"]
    assert body["tokenType"] == "bearer"
    assert body["user"]["role"] == "student"
    assert body["user"]["email"] == "kavya@gmail.com"
    assert body["user"]["boardId"] is None
    user = db.scalar(select(User).where(User.email == "kavya@gmail.com"))
    assert user is not None and user.google_sub == "google-sub-1" and user.is_verified
    # Only the hash is stored.
    stored = db.scalar(select(RefreshToken).where(RefreshToken.user_id == user.id))
    assert stored is not None and stored.token_hash == sha256_hex(body["refreshToken"])


def test_google_login_is_idempotent(
    client: TestClient, db: Session, google_identity: Callable[[GoogleIdentity], None]
) -> None:
    google_identity(_identity())
    first = _google_login(client).json()["user"]["id"]
    second = _google_login(client).json()["user"]["id"]
    assert first == second
    assert len(db.scalars(select(User)).all()) == 1


def test_google_login_links_existing_email(
    client: TestClient,
    google_identity: Callable[[GoogleIdentity], None],
    make_user: Callable[..., User],
) -> None:
    existing = make_user(email="kavya@gmail.com")
    google_identity(_identity())
    res = _google_login(client)
    assert res.json()["user"]["id"] == existing.id


def test_google_login_admin_email_gets_admin_role(
    client: TestClient,
    google_identity: Callable[[GoogleIdentity], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ADMIN_EMAILS", ["boss@gmail.com"])
    google_identity(_identity(email="boss@gmail.com"))
    assert _google_login(client).json()["user"]["role"] == "admin"


def test_google_login_disabled_account_forbidden(
    client: TestClient,
    google_identity: Callable[[GoogleIdentity], None],
    make_user: Callable[..., User],
) -> None:
    make_user(email="kavya@gmail.com", is_active=False)
    google_identity(_identity())
    res = _google_login(client)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "account_disabled"


def test_google_login_rejected_token(client: TestClient) -> None:
    def _reject(_token: str) -> GoogleIdentity:
        raise UnauthorizedError("Google sign-in failed", code="invalid_google_token")

    fastapi_app.dependency_overrides[get_google_verifier] = lambda: _reject
    try:
        res = _google_login(client)
    finally:
        fastapi_app.dependency_overrides.pop(get_google_verifier, None)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "invalid_google_token"


def test_google_not_configured_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(settings, "GOOGLE_ANDROID_CLIENT_ID", "")
    res = _google_login(client)
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "google_not_configured"


# --- verify_google_id_token (library call mocked) --------------------------------------


@pytest.fixture()
def configured_google(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "web-client.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "GOOGLE_ANDROID_CLIENT_ID", "")  # ignore a developer's .env
    return monkeypatch


def _patch_verify(monkeypatch: pytest.MonkeyPatch, result: Any) -> list[Any]:
    from google.oauth2 import id_token

    calls: list[Any] = []

    def _fake(token: str, request: Any, audience: Any = None, **kwargs: Any) -> Any:
        calls.append(audience)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(id_token, "verify_oauth2_token", _fake)
    return calls


@pytest.mark.parametrize(
    "error", [ValueError("Token has wrong audience"), ValueError("Token expired")]
)
def test_verify_rejects_bad_audience_or_expired(
    configured_google: pytest.MonkeyPatch, error: Exception
) -> None:
    _patch_verify(configured_google, error)
    with pytest.raises(UnauthorizedError) as exc:
        google_auth.verify_google_id_token(FAKE_ID_TOKEN)
    assert exc.value.code == "invalid_google_token"


def test_verify_rejects_unverified_email(configured_google: pytest.MonkeyPatch) -> None:
    _patch_verify(
        configured_google,
        {"iss": "accounts.google.com", "sub": "1", "email": "a@b.com", "email_verified": False},
    )
    with pytest.raises(UnauthorizedError) as exc:
        google_auth.verify_google_id_token(FAKE_ID_TOKEN)
    assert exc.value.code == "email_not_verified"


def test_verify_accepts_valid_token_with_configured_audience(
    configured_google: pytest.MonkeyPatch,
) -> None:
    calls = _patch_verify(
        configured_google,
        {
            "iss": "https://accounts.google.com",
            "sub": "123",
            "email": "Kavya@Gmail.com",
            "email_verified": True,
            "name": "Kavya",
        },
    )
    identity = google_auth.verify_google_id_token(FAKE_ID_TOKEN)
    assert identity.sub == "123" and identity.email == "kavya@gmail.com"
    assert calls == [["web-client.apps.googleusercontent.com"]]


# --- Dev login --------------------------------------------------------------------------


def test_dev_login_signs_in_seeded_user(client: TestClient, make_user: Callable[..., User]) -> None:
    make_user(email="student@dev.local")
    res = client.post("/api/v1/auth/dev-login", json={})
    assert res.status_code == 200
    assert res.json()["user"]["email"] == "student@dev.local"


def test_dev_login_unknown_user(client: TestClient) -> None:
    res = client.post("/api/v1/auth/dev-login", json={"email": "nobody@dev.local"})
    assert res.status_code == 401


def test_dev_login_disabled_in_production(
    client: TestClient, make_user: Callable[..., User], monkeypatch: pytest.MonkeyPatch
) -> None:
    make_user(email="student@dev.local")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    res = client.post("/api/v1/auth/dev-login", json={})
    assert res.status_code == 404


# --- Refresh / logout -------------------------------------------------------------------


def _dev_tokens(client: TestClient, make_user: Callable[..., User]) -> dict[str, Any]:
    make_user(email="student@dev.local")
    data: dict[str, Any] = client.post("/api/v1/auth/dev-login", json={}).json()
    return data


def test_refresh_rotates_token(client: TestClient, make_user: Callable[..., User]) -> None:
    tokens = _dev_tokens(client, make_user)
    res = client.post("/api/v1/auth/refresh", json={"refreshToken": tokens["refreshToken"]})
    assert res.status_code == 200
    new = res.json()
    assert new["refreshToken"] != tokens["refreshToken"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new['accessToken']}"})
    assert me.status_code == 200


def test_refresh_reuse_revokes_whole_chain(
    client: TestClient, make_user: Callable[..., User]
) -> None:
    first = _dev_tokens(client, make_user)["refreshToken"]
    second = client.post("/api/v1/auth/refresh", json={"refreshToken": first}).json()[
        "refreshToken"
    ]
    reuse = client.post("/api/v1/auth/refresh", json={"refreshToken": first})
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "token_reused"
    # The legitimately rotated token is now revoked as well.
    assert client.post("/api/v1/auth/refresh", json={"refreshToken": second}).status_code == 401


def test_refresh_expired_token(
    client: TestClient, db: Session, make_user: Callable[..., User]
) -> None:
    raw = _dev_tokens(client, make_user)["refreshToken"]
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(raw)))
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    res = client.post("/api/v1/auth/refresh", json={"refreshToken": raw})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "token_expired"


def test_refresh_unknown_token(client: TestClient) -> None:
    res = client.post("/api/v1/auth/refresh", json={"refreshToken": "x" * 40})
    assert res.status_code == 401


def test_logout_revokes_refresh_token(client: TestClient, make_user: Callable[..., User]) -> None:
    raw = _dev_tokens(client, make_user)["refreshToken"]
    assert client.post("/api/v1/auth/logout", json={"refreshToken": raw}).status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refreshToken": raw}).status_code == 401
    # Logging out twice is harmless.
    assert client.post("/api/v1/auth/logout", json={"refreshToken": raw}).status_code == 204


# --- Profile ----------------------------------------------------------------------------


def test_me_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401


def test_update_me_onboarding(
    client: TestClient,
    db: Session,
    make_user: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    board = Board(code="TN_SSLC", name="Tamil Nadu State Board", is_active=True)
    db.add(board)
    db.commit()
    user = make_user()
    res = client.put(
        "/api/v1/auth/me",
        json={"boardId": board.id, "medium": "ta", "fullName": "  Arun  "},
        headers=auth_headers(user),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["boardId"] == board.id and body["medium"] == "ta" and body["fullName"] == "Arun"


def test_update_me_rejects_inactive_board(
    client: TestClient,
    db: Session,
    make_user: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    board = Board(code="CBSE", name="CBSE", is_active=False)
    db.add(board)
    db.commit()
    res = client.put(
        "/api/v1/auth/me", json={"boardId": board.id}, headers=auth_headers(make_user())
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "invalid_board"


def test_update_me_rejects_bad_medium(
    client: TestClient,
    make_user: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    res = client.put("/api/v1/auth/me", json={"medium": "fr"}, headers=auth_headers(make_user()))
    assert res.status_code == 422


def test_list_boards_only_active(
    client: TestClient,
    db: Session,
    make_user: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    db.add_all(
        [
            Board(code="TN_SSLC", name="Tamil Nadu State Board", is_active=True),
            Board(code="CBSE", name="CBSE", is_active=False),
        ]
    )
    db.commit()
    res = client.get("/api/v1/boards", headers=auth_headers(make_user(role=UserRole.student)))
    assert res.status_code == 200
    assert [b["code"] for b in res.json()] == ["TN_SSLC"]


# --- Security hardening --------------------------------------------------------------------------


def test_dev_login_off_unless_explicitly_enabled(
    client: TestClient, make_user: Callable[..., User], monkeypatch: pytest.MonkeyPatch
) -> None:
    make_user(email="student@dev.local")
    monkeypatch.setattr(settings, "DEV_LOGIN_ENABLED", False)
    assert client.post("/api/v1/auth/dev-login", json={}).status_code == 404


@pytest.mark.parametrize(
    "secret",
    ["short", "dev-only-insecure-secret-key-change-me", "please-change-me-0123456789abcdefghij"],
)
def test_production_refuses_weak_secrets(secret: str) -> None:
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", SECRET_KEY=secret, DEV_LOGIN_ENABLED=False)


def test_production_refuses_dev_login() -> None:
    from pydantic import ValidationError

    from app.config import Settings

    strong = "k3Jd9-qW2x_Lm8Rt5Yv1Bn6Hc4Fg7Ps0Ze2Ua9"
    smtp = {"EMAIL_PROVIDER": "smtp", "SMTP_HOST": "smtp.example.com"}
    assert Settings(ENVIRONMENT="production", SECRET_KEY=strong, DEV_LOGIN_ENABLED=False, **smtp)
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", SECRET_KEY=strong, DEV_LOGIN_ENABLED=True, **smtp)


def test_production_refuses_log_email_provider() -> None:
    from pydantic import ValidationError

    from app.config import Settings

    strong = "k3Jd9-qW2x_Lm8Rt5Yv1Bn6Hc4Fg7Ps0Ze2Ua9"
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", SECRET_KEY=strong, EMAIL_PROVIDER="log")
