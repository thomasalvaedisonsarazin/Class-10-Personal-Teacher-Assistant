"""Account deletion (Google Play requires in-app deletion for apps with sign-up)."""

from __future__ import annotations

import logging

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.exceptions import ForbiddenError
from app.models.billing import Purchase
from app.models.enums import UserRole
from app.models.lesson import ClarityFeedback, GenerationJob, LessonView
from app.models.notification import DeviceToken, NotificationLog
from app.models.parent import ParentLink
from app.models.progress import StudyStreak, TopicProgress
from app.models.quiz import QuizAttempt, QuizAttemptQuestion
from app.models.user import EmailCode, RefreshToken, User

logger = logging.getLogger(__name__)


def delete_account(db: Session, user: User) -> None:
    """
    Permanently delete a student or parent account and all of its personal data.

    Rows are deleted explicitly (not only via database cascades) so the result is the
    same on every database. Shared course material (lessons, questions) is kept; the
    generation jobs a student triggered just lose their link to the account.

    Args:
        db: Database session
        user: The signed-in user deleting their own account

    Raises:
        ForbiddenError: admins cannot delete their own account in the app.
    """
    if user.role == UserRole.admin:
        raise ForbiddenError("Admin accounts cannot be deleted in the app.", code="admin_delete")
    user_id = user.id
    attempt_ids = select(QuizAttempt.id).where(QuizAttempt.user_id == user_id)
    db.execute(delete(QuizAttemptQuestion).where(QuizAttemptQuestion.attempt_id.in_(attempt_ids)))
    for model in (
        QuizAttempt,
        LessonView,
        ClarityFeedback,
        TopicProgress,
        StudyStreak,
        DeviceToken,
        NotificationLog,
        RefreshToken,
    ):
        db.execute(delete(model).where(model.user_id == user_id))
    db.execute(update(GenerationJob).where(GenerationJob.user_id == user_id).values(user_id=None))
    # A parent's payments for a child stay with the child; the student's own access goes.
    db.execute(update(Purchase).where(Purchase.payer_user_id == user_id).values(payer_user_id=None))
    db.execute(delete(Purchase).where(Purchase.beneficiary_user_id == user_id))
    db.execute(
        delete(ParentLink).where(
            or_(ParentLink.parent_user_id == user_id, ParentLink.student_user_id == user_id)
        )
    )
    db.execute(delete(EmailCode).where(EmailCode.email == user.email.lower()))
    db.execute(delete(User).where(User.id == user_id))
    db.commit()
    logger.info("Deleted account %s", user_id)
