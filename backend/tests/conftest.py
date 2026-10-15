"""Shared pytest fixtures.

Environment is forced to a safe test configuration BEFORE the app is imported:
SQLite temp database, no OpenAI key (fake LLM), fake TTS, local storage in a
temp directory. Real external services are never called from tests.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable, Generator, Iterator
from pathlib import Path
from typing import Any

_TMP_DIR = Path(tempfile.mkdtemp(prefix="pta-tests-"))

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP_DIR / 'test.db').as_posix()}"
os.environ["OPENAI_API_KEY"] = ""
os.environ["TTS_PROVIDER"] = "fake"
os.environ["TTS_API_KEY"] = ""
os.environ["S3_BUCKET"] = ""
os.environ["PUSH_ENABLED"] = "false"
os.environ["JOB_RUNNER"] = "sync"
os.environ["VIDEO_RENDER_ENABLED"] = "false"
os.environ["MEDIA_ROOT"] = str(_TMP_DIR / "media")
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only-0123456789"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: E402,F401  - registers all tables on Base.metadata
from app.auth.jwt import create_access_token  # noqa: E402
from app.database import SessionLocal, engine, get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.ai.llm import get_fake_llm_client  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema() -> Iterator[None]:
    """Create all tables once for the test session and clean up the temp dir after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


@pytest.fixture()
def db() -> Iterator[Session]:
    """A database session; all table rows are deleted after each test."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())


@pytest.fixture(autouse=True)
def _reset_fakes() -> Iterator[None]:
    """Clear fake LLM factories/calls between tests."""
    yield
    get_fake_llm_client().clear()


@pytest.fixture()
def client(db: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient whose ``get_db`` dependency yields the test session."""

    def _override_get_db() -> Iterator[Session]:
        yield db

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.pop(get_db, None)


_counter = {"n": 0}


@pytest.fixture()
def make_user(db: Session) -> Callable[..., User]:
    """Factory fixture: ``make_user(role=UserRole.student, **fields) -> User`` (committed)."""

    def _make(role: UserRole = UserRole.student, **fields: Any) -> User:
        _counter["n"] += 1
        n = _counter["n"]
        values: dict[str, Any] = {
            "email": f"user{n}@example.com",
            "full_name": f"Test User {n}",
            "role": role,
            "is_active": True,
        }
        values.update(fields)
        user = User(**values)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


def auth_headers(user: User) -> dict[str, str]:
    """Return an ``Authorization`` header with a valid access token for ``user``."""
    token = create_access_token(user.id, UserRole(user.role).value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(name="auth_headers")
def auth_headers_fixture() -> Callable[[User], dict[str, str]]:
    """Fixture form of :func:`auth_headers`."""
    return auth_headers
