"""Domain enums shared by models, schemas and services.

All enums are ``StrEnum`` (``str`` + ``Enum``) so they serialise naturally in JSON and compare
equal to their raw string values.  Database columns store the enum *values*
(see :func:`app.models.base.enum_column_type`).
"""

from enum import StrEnum


class UserRole(StrEnum):
    """Account role."""

    student = "student"
    parent = "parent"
    admin = "admin"
    partner = "partner"  # school / teacher referral partner


class Medium(StrEnum):
    """Medium of instruction (content language)."""

    en = "en"
    ta = "ta"


class LessonLanguage(StrEnum):
    """Language a lesson is explained in (independent of the textbook medium)."""

    en = "en"
    ta = "ta"
    tanglish = "tanglish"  # Tamil sentences with English technical words, as spoken in class


class LessonStyle(StrEnum):
    """Teaching style of a lesson. Order defines the "Not clear" rotation."""

    base = "base"
    analogy = "analogy"
    step_by_step = "step_by_step"
    story = "story"
    real_life = "real_life"
    worked_example = "worked_example"
    visual = "visual"


class LessonSource(StrEnum):
    """Where a lesson came from."""

    uploaded = "uploaded"
    ai_generated = "ai_generated"


class LessonStatus(StrEnum):
    """Media pipeline status of a lesson."""

    pending = "pending"
    generating = "generating"
    audio_ready = "audio_ready"
    ready = "ready"
    failed = "failed"


class JobKind(StrEnum):
    """Kind of background generation job."""

    explanation = "explanation"
    questions = "questions"


class JobStatus(StrEnum):
    """Background job status."""

    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class QuestionType(StrEnum):
    """Quiz question type."""

    mcq = "mcq"
    true_false = "true_false"
    fill_blank = "fill_blank"


class QuestionSource(StrEnum):
    """Who authored a question."""

    ai = "ai"
    admin = "admin"


class TopicStatus(StrEnum):
    """Stored topic progress status ("available"/"locked" are derived)."""

    active = "active"
    completed = "completed"


class ParentLinkStatus(StrEnum):
    """Parent ↔ student link status."""

    pending = "pending"
    accepted = "accepted"
    revoked = "revoked"
