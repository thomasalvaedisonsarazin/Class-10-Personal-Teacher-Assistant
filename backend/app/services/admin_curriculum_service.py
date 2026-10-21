"""Admin curriculum management: tree view, create/update, bulk JSON import (upsert)."""

from __future__ import annotations

import logging
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError
from app.models.curriculum import (
    Board,
    Chapter,
    ChapterTranslation,
    Subject,
    SubjectTranslation,
    Topic,
    TopicTranslation,
)
from app.models.enums import Medium
from app.models.lesson import Lesson
from app.models.quiz import Question
from app.schemas.admin import (
    AdminBoard,
    AdminChapter,
    AdminSubject,
    AdminTopic,
    BoardUpdate,
    ChapterCreate,
    ChapterUpdate,
    CurriculumImport,
    CurriculumTree,
    ImportResult,
    SubjectCreate,
    SubjectUpdate,
    TopicCreate,
    TopicUpdate,
)

logger = logging.getLogger(__name__)

ORDER_TAKEN = "Another item already uses this position. Choose a different display order."


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(ORDER_TAKEN, code="display_order_taken") from exc


# --- tree -----------------------------------------------------------------------------------


def list_boards(db: Session) -> list[AdminBoard]:
    """All boards (active or not)."""
    boards = db.scalars(select(Board).order_by(Board.family, Board.grade, Board.id))
    return [AdminBoard.model_validate(b) for b in boards]


def update_board(db: Session, board_id: int, data: BoardUpdate) -> AdminBoard:
    """Rename a class or show / hide it to students (existing students keep it)."""
    board = db.get(Board, board_id)
    if board is None:
        raise NotFoundError("Board not found")
    if data.name is not None:
        board.name = data.name.strip()
    if data.is_active is not None:
        board.is_active = data.is_active
    _commit(db)
    return AdminBoard.model_validate(board)


def curriculum_tree(db: Session, board_id: int) -> CurriculumTree:
    """Whole syllabus of a board, including unpublished topics, with content counts."""
    board = db.get(Board, board_id)
    if board is None:
        raise NotFoundError("Board not found")
    subjects = db.scalars(
        select(Subject).where(Subject.board_id == board.id).order_by(Subject.display_order)
    ).all()
    topic_ids = [t.id for s in subjects for c in s.chapters for t in c.topics]
    lessons: Counter[int] = Counter()
    questions: Counter[int] = Counter()
    if topic_ids:
        lesson_rows = db.execute(
            select(Lesson.topic_id, func.count(Lesson.id))
            .where(Lesson.topic_id.in_(topic_ids))
            .group_by(Lesson.topic_id)
        ).all()
        lessons.update({topic_id: n for topic_id, n in lesson_rows})
        question_rows = db.execute(
            select(Question.topic_id, func.count(Question.id))
            .where(Question.topic_id.in_(topic_ids))
            .group_by(Question.topic_id)
        ).all()
        questions.update({topic_id: n for topic_id, n in question_rows})

    def topic_out(t: Topic) -> AdminTopic:
        ta = next((x for x in t.translations if x.medium == Medium.ta), None)
        return AdminTopic(
            id=t.id,
            title=t.title,
            title_ta=ta.title if ta else None,
            learning_objectives=t.learning_objectives,
            learning_objectives_ta=ta.learning_objectives if ta else None,
            display_order=t.display_order,
            is_published=t.is_published,
            lesson_count=lessons[t.id],
            question_count=questions[t.id],
        )

    def chapter_out(c: Chapter) -> AdminChapter:
        ta = next((x for x in c.translations if x.medium == Medium.ta), None)
        return AdminChapter(
            id=c.id,
            title=c.title,
            title_ta=ta.title if ta else None,
            display_order=c.display_order,
            topics=[topic_out(t) for t in c.topics],
        )

    return CurriculumTree(
        board=AdminBoard.model_validate(board),
        subjects=[
            AdminSubject(
                id=s.id,
                name=s.name,
                name_ta=next((x.name for x in s.translations if x.medium == Medium.ta), None),
                tile_color=s.tile_color,
                icon=s.icon,
                display_order=s.display_order,
                fixed_medium=Medium(s.fixed_medium) if s.fixed_medium else None,
                chapters=[chapter_out(c) for c in s.chapters],
            )
            for s in subjects
        ],
    )


# --- translations ---------------------------------------------------------------------------


def _set_subject_ta(subject: Subject, name: str | None) -> None:
    if name is None:
        return
    row = next((t for t in subject.translations if t.medium == Medium.ta), None)
    if row is None:
        subject.translations.append(SubjectTranslation(medium=Medium.ta, name=name))
    else:
        row.name = name


def _set_chapter_ta(chapter: Chapter, title: str | None) -> None:
    if title is None:
        return
    row = next((t for t in chapter.translations if t.medium == Medium.ta), None)
    if row is None:
        chapter.translations.append(ChapterTranslation(medium=Medium.ta, title=title))
    else:
        row.title = title


def _set_topic_ta(topic: Topic, title: str | None, objectives: str | None) -> None:
    if title is None and objectives is None:
        return
    row = next((t for t in topic.translations if t.medium == Medium.ta), None)
    if row is None:
        row = TopicTranslation(medium=Medium.ta, title=title or topic.title, learning_objectives="")
        topic.translations.append(row)
    if title is not None:
        row.title = title
    if objectives is not None:
        row.learning_objectives = objectives


def _next_order(db: Session, column: object, parent_column: object, parent_id: int) -> int:
    current = db.scalar(select(func.max(column)).where(parent_column == parent_id))  # type: ignore[arg-type]
    return (current or 0) + 1


# --- create / update -------------------------------------------------------------------------


def create_subject(db: Session, data: SubjectCreate) -> Subject:
    if db.get(Board, data.board_id) is None:
        raise NotFoundError("Board not found")
    subject = Subject(
        board_id=data.board_id,
        name=data.name.strip(),
        tile_color=data.tile_color,
        icon=data.icon,
        display_order=data.display_order
        if data.display_order is not None
        else _next_order(db, Subject.display_order, Subject.board_id, data.board_id),
    )
    subject.translations.append(SubjectTranslation(medium=Medium.en, name=subject.name))
    _set_subject_ta(subject, data.name_ta)
    db.add(subject)
    _commit(db)
    return subject


def update_subject(db: Session, subject_id: int, data: SubjectUpdate) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise NotFoundError("Subject not found")
    if data.name is not None:
        subject.name = data.name
    if data.tile_color is not None:
        subject.tile_color = data.tile_color
    if data.icon is not None:
        subject.icon = data.icon
    if data.display_order is not None:
        subject.display_order = data.display_order
    if data.fixed_medium is not None:
        subject.fixed_medium = data.fixed_medium or None
    if data.name is not None:
        en = next((t for t in subject.translations if t.medium == Medium.en), None)
        if en is not None:
            en.name = data.name
    _set_subject_ta(subject, data.name_ta)
    _commit(db)
    return subject


def _ta_name(subject: Subject) -> str | None:
    row = next((t for t in subject.translations if t.medium == Medium.ta), None)
    return row.name if row else None


def create_chapter(db: Session, data: ChapterCreate) -> Chapter:
    if db.get(Subject, data.subject_id) is None:
        raise NotFoundError("Subject not found")
    chapter = Chapter(
        subject_id=data.subject_id,
        title=data.title.strip(),
        display_order=data.display_order
        if data.display_order is not None
        else _next_order(db, Chapter.display_order, Chapter.subject_id, data.subject_id),
    )
    chapter.translations.append(ChapterTranslation(medium=Medium.en, title=chapter.title))
    _set_chapter_ta(chapter, data.title_ta)
    db.add(chapter)
    _commit(db)
    return chapter


def update_chapter(db: Session, chapter_id: int, data: ChapterUpdate) -> Chapter:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise NotFoundError("Chapter not found")
    if data.title is not None:
        chapter.title = data.title
        en = next((t for t in chapter.translations if t.medium == Medium.en), None)
        if en is not None:
            en.title = data.title
    if data.display_order is not None:
        chapter.display_order = data.display_order
    _set_chapter_ta(chapter, data.title_ta)
    _commit(db)
    return chapter


def create_topic(db: Session, data: TopicCreate) -> Topic:
    if db.get(Chapter, data.chapter_id) is None:
        raise NotFoundError("Chapter not found")
    topic = Topic(
        chapter_id=data.chapter_id,
        title=data.title.strip(),
        learning_objectives=data.learning_objectives.strip(),
        is_published=data.is_published,
        display_order=data.display_order
        if data.display_order is not None
        else _next_order(db, Topic.display_order, Topic.chapter_id, data.chapter_id),
    )
    topic.translations.append(
        TopicTranslation(
            medium=Medium.en, title=topic.title, learning_objectives=topic.learning_objectives
        )
    )
    _set_topic_ta(topic, data.title_ta, data.learning_objectives_ta)
    db.add(topic)
    _commit(db)
    return topic


def update_topic(db: Session, topic_id: int, data: TopicUpdate) -> Topic:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise NotFoundError("Topic not found")
    en = next((t for t in topic.translations if t.medium == Medium.en), None)
    if data.title is not None:
        topic.title = data.title
        if en is not None:
            en.title = data.title
    if data.learning_objectives is not None:
        topic.learning_objectives = data.learning_objectives.strip()
        if en is not None:
            en.learning_objectives = topic.learning_objectives
    if data.display_order is not None:
        topic.display_order = data.display_order
    if data.is_published is not None:
        topic.is_published = data.is_published
    _set_topic_ta(topic, data.title_ta, data.learning_objectives_ta)
    _commit(db)
    return topic


# --- bulk import ------------------------------------------------------------------------------


def import_curriculum(db: Session, data: CurriculumImport) -> ImportResult:
    """Create or update subjects/chapters/topics, matched by display order within each parent.

    Nothing is deleted. All-or-nothing: any error rolls the whole import back.
    """
    code = data.board_code.strip().upper()
    created: Counter[str] = Counter()
    updated: Counter[str] = Counter()
    board = db.scalar(select(Board).where(Board.code == code))
    if board is None:
        if not data.board_name:
            raise NotFoundError(f"Board {data.board_code!r} not found")
        board = Board(code=code, name=data.board_name.strip(), is_active=data.is_active)
        db.add(board)
        created["boards"] += 1
    board.family = data.family.strip().upper()
    board.grade = data.grade
    board.choose_subjects = data.choose_subjects
    db.flush()

    for s in data.subjects:
        subject = db.scalar(
            select(Subject).where(
                Subject.board_id == board.id, Subject.display_order == s.display_order
            )
        )
        if subject is None:
            subject = Subject(
                board_id=board.id,
                display_order=s.display_order,
                name=s.name,
                tile_color=s.tile_color,
                icon=s.icon,
            )
            db.add(subject)
            created["subjects"] += 1
        else:
            updated["subjects"] += 1
        subject.name, subject.tile_color, subject.icon = s.name, s.tile_color, s.icon
        subject.fixed_medium = s.fixed_medium.value if s.fixed_medium else None
        en_s = next((x for x in subject.translations if x.medium == Medium.en), None)
        if en_s is None:
            subject.translations.append(SubjectTranslation(medium=Medium.en, name=s.name))
        else:
            en_s.name = s.name
        _set_subject_ta(subject, s.name_ta)
        db.flush()

        for c in s.chapters:
            chapter = db.scalar(
                select(Chapter).where(
                    Chapter.subject_id == subject.id, Chapter.display_order == c.display_order
                )
            )
            if chapter is None:
                chapter = Chapter(
                    subject_id=subject.id, display_order=c.display_order, title=c.title
                )
                chapter.translations.append(ChapterTranslation(medium=Medium.en, title=c.title))
                db.add(chapter)
                created["chapters"] += 1
            else:
                updated["chapters"] += 1
                chapter.title = c.title
                en = next((t for t in chapter.translations if t.medium == Medium.en), None)
                if en is not None:
                    en.title = c.title
            _set_chapter_ta(chapter, c.title_ta)
            db.flush()

            for t in c.topics:
                topic = db.scalar(
                    select(Topic).where(
                        Topic.chapter_id == chapter.id, Topic.display_order == t.display_order
                    )
                )
                if topic is None:
                    topic = Topic(
                        chapter_id=chapter.id, display_order=t.display_order, title=t.title
                    )
                    topic.translations.append(
                        TopicTranslation(medium=Medium.en, title=t.title, learning_objectives="")
                    )
                    db.add(topic)
                    created["topics"] += 1
                else:
                    updated["topics"] += 1
                topic.title = t.title
                topic.learning_objectives = t.learning_objectives.strip()
                topic.is_published = t.is_published
                en_t = next((x for x in topic.translations if x.medium == Medium.en), None)
                if en_t is not None:
                    en_t.title, en_t.learning_objectives = t.title, topic.learning_objectives
                _set_topic_ta(topic, t.title_ta, t.learning_objectives_ta)
                db.flush()

    _commit(db)
    logger.info(
        "Curriculum import board=%s created=%s updated=%s", board.code, dict(created), dict(updated)
    )
    return ImportResult(created=dict(created), updated=dict(updated))
