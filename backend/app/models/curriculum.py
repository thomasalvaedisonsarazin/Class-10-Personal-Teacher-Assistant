"""Curriculum hierarchy: Board → Subject → Chapter → Topic (+ translations)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MEDIUM, Base, TimestampMixin
from app.models.enums import Medium


class Board(TimestampMixin, Base):
    """An examination board, e.g. ``TN_SSLC`` or ``CBSE``."""

    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(sa.String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=True, server_default=sa.true()
    )

    subjects: Mapped[list[Subject]] = relationship(
        back_populates="board",
        order_by="Subject.display_order",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Subject(TimestampMixin, Base):
    """A subject within a board, rendered as a flat-coloured tile."""

    __tablename__ = "subjects"
    __table_args__ = (
        sa.UniqueConstraint("board_id", "display_order"),
        sa.CheckConstraint("tile_color LIKE '#______'", name="tile_color_hex"),
        sa.CheckConstraint("display_order >= 0", name="display_order_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[int] = mapped_column(
        sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    tile_color: Mapped[str] = mapped_column(sa.String(7), nullable=False)
    icon: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    display_order: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    board: Mapped[Board] = relationship(back_populates="subjects")
    chapters: Mapped[list[Chapter]] = relationship(
        back_populates="subject",
        order_by="Chapter.display_order",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    translations: Mapped[list[SubjectTranslation]] = relationship(
        back_populates="subject",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SubjectTranslation(TimestampMixin, Base):
    """Localised subject name for a medium."""

    __tablename__ = "subject_translations"
    __table_args__ = (sa.UniqueConstraint("subject_id", "medium"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(
        sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    medium: Mapped[Medium] = mapped_column(MEDIUM, nullable=False)
    name: Mapped[str] = mapped_column(sa.String(120), nullable=False)

    subject: Mapped[Subject] = relationship(back_populates="translations")


class Chapter(TimestampMixin, Base):
    """A chapter (unit) of a subject."""

    __tablename__ = "chapters"
    __table_args__ = (
        sa.UniqueConstraint("subject_id", "display_order"),
        sa.CheckConstraint("display_order >= 0", name="display_order_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(
        sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    display_order: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    subject: Mapped[Subject] = relationship(back_populates="chapters")
    topics: Mapped[list[Topic]] = relationship(
        back_populates="chapter",
        order_by="Topic.display_order",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    translations: Mapped[list[ChapterTranslation]] = relationship(
        back_populates="chapter",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ChapterTranslation(TimestampMixin, Base):
    """Localised chapter title for a medium."""

    __tablename__ = "chapter_translations"
    __table_args__ = (sa.UniqueConstraint("chapter_id", "medium"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(
        sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )
    medium: Mapped[Medium] = mapped_column(MEDIUM, nullable=False)
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)

    chapter: Mapped[Chapter] = relationship(back_populates="translations")


class Topic(TimestampMixin, Base):
    """The unit of study: one topic is active per student at a time."""

    __tablename__ = "topics"
    __table_args__ = (
        sa.UniqueConstraint("chapter_id", "display_order"),
        sa.CheckConstraint("display_order >= 0", name="display_order_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(
        sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    learning_objectives: Mapped[str] = mapped_column(
        sa.Text, nullable=False, default="", server_default=""
    )
    display_order: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    is_published: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )

    chapter: Mapped[Chapter] = relationship(back_populates="topics")
    translations: Mapped[list[TopicTranslation]] = relationship(
        back_populates="topic",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TopicTranslation(TimestampMixin, Base):
    """Localised topic title and learning objectives for a medium."""

    __tablename__ = "topic_translations"
    __table_args__ = (sa.UniqueConstraint("topic_id", "medium"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    medium: Mapped[Medium] = mapped_column(MEDIUM, nullable=False)
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    learning_objectives: Mapped[str] = mapped_column(
        sa.Text, nullable=False, default="", server_default=""
    )

    topic: Mapped[Topic] = relationship(back_populates="translations")
