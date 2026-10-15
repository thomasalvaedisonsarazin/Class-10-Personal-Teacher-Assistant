"""Database engine, session factory and FastAPI session dependency."""

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def _engine_kwargs(url: str) -> dict[str, Any]:
    """Return dialect-specific ``create_engine`` keyword arguments."""
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return kwargs


engine = create_engine(settings.DATABASE_URL, **_engine_kwargs(settings.DATABASE_URL))

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and always close it afterwards (FastAPI dependency)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
