"""ORM models. Importing this package registers every table on ``Base.metadata``."""

from app.models.base import Base, TimestampMixin
from app.models.billing import Purchase
from app.models.curriculum import (
    Board,
    Chapter,
    ChapterTranslation,
    Subject,
    SubjectTranslation,
    Topic,
    TopicTranslation,
)
from app.models.enums import (
    JobKind,
    JobStatus,
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
from app.models.lesson import ClarityFeedback, GenerationJob, Lesson, LessonView
from app.models.notification import DeviceToken, NotificationLog
from app.models.parent import ParentLink
from app.models.partner import Commission, Partner, Payout
from app.models.progress import StudyStreak, TopicProgress
from app.models.quiz import Question, QuizAttempt, QuizAttemptQuestion
from app.models.user import EmailCode, RefreshToken, User

__all__ = [
    "Base",
    "Board",
    "Chapter",
    "ChapterTranslation",
    "ClarityFeedback",
    "DeviceToken",
    "GenerationJob",
    "JobKind",
    "JobStatus",
    "Lesson",
    "LessonSource",
    "LessonStatus",
    "LessonStyle",
    "LessonView",
    "Medium",
    "NotificationLog",
    "ParentLink",
    "ParentLinkStatus",
    "Partner",
    "Commission",
    "Payout",
    "Purchase",
    "Question",
    "QuestionSource",
    "QuestionType",
    "QuizAttempt",
    "QuizAttemptQuestion",
    "RefreshToken",
    "StudyStreak",
    "Subject",
    "SubjectTranslation",
    "TimestampMixin",
    "Topic",
    "TopicProgress",
    "TopicStatus",
    "TopicTranslation",
    "User",
    "EmailCode",
    "UserRole",
]
