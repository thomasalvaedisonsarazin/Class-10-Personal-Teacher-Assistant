"""Daily study streaks (India time). A study day = watched a lesson or submitted a test."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.progress import StudyStreak
from app.models.user import User
from app.schemas.common import CamelModel

IST = timezone(timedelta(hours=5, minutes=30))  # India has no daylight saving


class StreakOut(CamelModel):
    """The student's streak for the Home screen."""

    current: int
    longest: int
    studied_today: bool


def today_ist(now: datetime | None = None) -> date:
    """Today's date in India."""
    return (now or datetime.now(UTC)).astimezone(IST).date()


def record_study(db: Session, user: User, now: datetime | None = None) -> StudyStreak:
    """Count today as a study day (idempotent within a day). Does not commit.

    Yesterday → streak + 1; a gap → streak restarts at 1.
    """
    today = today_ist(now)
    streak = db.scalar(select(StudyStreak).where(StudyStreak.user_id == user.id))
    if streak is None:
        streak = StudyStreak(user_id=user.id, current_streak_days=0, longest_streak_days=0)
        db.add(streak)
        db.flush()  # visible to later lookups in the same transaction
    if streak.last_study_date == today:
        return streak
    if streak.last_study_date == today - timedelta(days=1):
        streak.current_streak_days = (streak.current_streak_days or 0) + 1
    else:
        streak.current_streak_days = 1
    streak.longest_streak_days = max(streak.longest_streak_days or 0, streak.current_streak_days)
    streak.last_study_date = today
    return streak


def get_streak(db: Session, user: User, now: datetime | None = None) -> StreakOut:
    """Current streak (0 once a day is missed), best streak, and whether today counts yet."""
    streak = db.scalar(select(StudyStreak).where(StudyStreak.user_id == user.id))
    if streak is None or streak.last_study_date is None:
        return StreakOut(current=0, longest=0, studied_today=False)
    today = today_ist(now)
    alive = streak.last_study_date >= today - timedelta(days=1)
    return StreakOut(
        current=streak.current_streak_days if alive else 0,
        longest=streak.longest_streak_days,
        studied_today=streak.last_study_date == today,
    )
