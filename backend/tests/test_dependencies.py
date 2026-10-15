"""Tests for auth dependencies, JWT helpers and the error envelope."""

from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    sha256_hex,
)
from app.database import get_db
from app.dependencies import AdminUser, CurrentUser
from app.exceptions import ConflictError, UnauthorizedError, register_exception_handlers
from app.models.enums import UserRole
from app.models.user import User


class Body(BaseModel):
    value: int


@pytest.fixture()
def guarded_client(db: Session) -> Iterator[TestClient]:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/me")
    def me(user: CurrentUser) -> dict[str, int]:
        return {"id": user.id}

    @app.get("/admin")
    def admin(user: AdminUser) -> dict[str, str]:
        return {"ok": "yes"}

    @app.post("/body")
    def body(payload: Body) -> dict[str, int]:
        return {"value": payload.value}

    @app.get("/conflict")
    def conflict() -> None:
        raise ConflictError("Another topic is active")

    def _db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = _db
    with TestClient(app) as c:
        yield c


def test_jwt_roundtrip() -> None:
    token = create_access_token(42, "student")
    payload = decode_access_token(token)
    assert payload.sub == 42
    assert payload.role == "student"


def test_jwt_invalid() -> None:
    with pytest.raises(UnauthorizedError):
        decode_access_token("not-a-token")


def test_refresh_token_hash() -> None:
    raw, digest = create_refresh_token()
    assert len(raw) > 40
    assert digest == sha256_hex(raw)


def test_missing_token_401(guarded_client: TestClient) -> None:
    response = guarded_client.get("/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_valid_token(
    guarded_client: TestClient,
    make_user: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    user = make_user()
    response = guarded_client.get("/me", headers=auth_headers(user))
    assert response.status_code == 200
    assert response.json() == {"id": user.id}


def test_inactive_user_401(
    guarded_client: TestClient,
    make_user: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    user = make_user(is_active=False)
    assert guarded_client.get("/me", headers=auth_headers(user)).status_code == 401


def test_role_guard(
    guarded_client: TestClient,
    make_user: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    student = make_user()
    admin = make_user(role=UserRole.admin)
    forbidden = guarded_client.get("/admin", headers=auth_headers(student))
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"
    assert guarded_client.get("/admin", headers=auth_headers(admin)).status_code == 200


def test_validation_envelope(guarded_client: TestClient) -> None:
    response = guarded_client.post("/body", json={"value": "abc"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]


def test_app_error_envelope(guarded_client: TestClient) -> None:
    response = guarded_client.get("/conflict")
    assert response.status_code == 409
    assert response.json() == {"error": {"code": "conflict", "message": "Another topic is active"}}
