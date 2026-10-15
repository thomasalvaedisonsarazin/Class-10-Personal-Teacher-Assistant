"""Declarative base, naming convention and shared column helpers."""

from datetime import datetime
from enum import Enum
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.models.enums import (
    JobKind,
    JobStatus,
    LessonLanguage,
    LessonSource,
    LessonStatus,
    LessonStyle,
    Medium,
    ParentLinkStatus,
    QuestionSource,
    QuestionType,
    TopicStatus,
    UserRole,
)

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Portable JSON: JSONB on PostgreSQL, JSON (text) elsewhere (SQLite tests).
JSONType: sa.types.TypeEngine[Any] = sa.JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    metadata = sa.MetaData(naming_convention=NAMING_CONVENTION)


def enum_column_type(enum_cls: type[Enum], name: str) -> sa.Enum:
    """Build a SQLAlchemy Enum type that stores the enum *values*.

    Args:
        enum_cls: The Python ``Enum`` class.
        name: PostgreSQL enum type name (shared across tables if reused).

    Returns:
        A configured ``sa.Enum`` instance.
    """
    return sa.Enum(
        enum_cls,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


class TimestampMixin:
    """Adds timezone-aware ``created_at`` / ``updated_at`` columns."""

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )


# Shared enum column types (one PostgreSQL type per enum, reused across tables).
USER_ROLE = enum_column_type(UserRole, "user_role")
MEDIUM = enum_column_type(Medium, "medium")
LESSON_STYLE = enum_column_type(LessonStyle, "lesson_style")
LESSON_LANGUAGE = enum_column_type(LessonLanguage, "lesson_language")
LESSON_SOURCE = enum_column_type(LessonSource, "lesson_source")
LESSON_STATUS = enum_column_type(LessonStatus, "lesson_status")
JOB_KIND = enum_column_type(JobKind, "job_kind")
JOB_STATUS = enum_column_type(JobStatus, "job_status")
QUESTION_TYPE = enum_column_type(QuestionType, "question_type")
QUESTION_SOURCE = enum_column_type(QuestionSource, "question_source")
TOPIC_STATUS = enum_column_type(TopicStatus, "topic_status")
PARENT_LINK_STATUS = enum_column_type(ParentLinkStatus, "parent_link_status")
