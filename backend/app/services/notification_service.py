"""Push notifications: device registration, test results, daily reminders, parent weekly.

Messages are short, in the user's language (English or Tamil), never more than one of a
kind per day/week (``NotificationLog`` is the de-duplication record), and dead Expo tokens
are removed when Expo reports ``DeviceNotRegistered``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import Medium, ParentLinkStatus, UserRole
from app.models.notification import DeviceToken, NotificationLog
from app.models.parent import ParentLink
from app.models.quiz import QuizAttempt
from app.models.user import User
from app.services import curriculum_service
from app.services.push import send_push
from app.services.streak_service import IST, get_streak, today_ist

logger = logging.getLogger(__name__)

MESSAGES: dict[str, dict[str, str]] = {
    "payout_ready_title": {
        "en": "Your commission is ready 💰",
        "ta": "உங்கள் கமிஷன் தயார் 💰",
    },
    "payout_ready_body": {
        "en": "You have ₹{amount} to claim. Tap to request your payout.",
        "ta": "₹{amount} பெறலாம். பணம் பெற தட்டவும்.",
    },
    "passed_title": {"en": "You passed! 🎉", "ta": "நீங்கள் தேர்ச்சி பெற்றீர்கள்! 🎉"},
    "passed_body_next": {
        "en": "{score}% in {topic}. Next topic unlocked: {next}",
        "ta": "{topic}: {score}%. அடுத்த பாடம் திறக்கப்பட்டது: {next}",
    },
    "passed_body_done": {
        "en": "{score}% in {topic}. You finished this subject!",
        "ta": "{topic}: {score}%. இந்தப் பாடப்பிரிவை முடித்துவிட்டீர்கள்!",
    },
    "parent_passed_title": {"en": "{child} passed a topic", "ta": "{child} ஒரு பாடத்தில் தேர்ச்சி"},
    "parent_passed_body": {
        "en": "{topic}: {score}% ✅",
        "ta": "{topic}: {score}% ✅",
    },
    "reminder_title": {"en": "Time to learn 📚", "ta": "படிக்கும் நேரம் 📚"},
    "reminder_body": {
        "en": "Your next topic is waiting: {topic}",
        "ta": "உங்கள் அடுத்த பாடம் காத்திருக்கிறது: {topic}",
    },
    "reminder_body_streak": {
        "en": "Keep your 🔥 {days}-day streak! Next: {topic}",
        "ta": "உங்கள் 🔥 {days} நாள் தொடரைத் தொடருங்கள்! அடுத்து: {topic}",
    },
    "weekly_title": {"en": "{child}'s week", "ta": "{child} இந்த வாரம்"},
    "weekly_body": {
        "en": "{passed} topic(s) passed, {tests} test(s), average {avg}.",
        "ta": "{passed} பாடங்களில் தேர்ச்சி, {tests} தேர்வுகள், சராசரி {avg}.",
    },
}


def _lang(user: User) -> str:
    return "ta" if user.medium == Medium.ta else "en"


def _text(key: str, user: User, **values: object) -> str:
    return MESSAGES[key][_lang(user)].format(**values)


# --- devices --------------------------------------------------------------------------------


def register_device(db: Session, user: User, token: str, platform: str) -> None:
    """Save (or move to this user) an Expo push token."""
    row = db.scalar(select(DeviceToken).where(DeviceToken.expo_push_token == token))
    if row is None:
        db.add(DeviceToken(user_id=user.id, expo_push_token=token, platform=platform))
    else:  # same phone, different account
        row.user_id = user.id
        row.platform = platform
    db.commit()


def unregister_device(db: Session, user: User, token: str) -> None:
    """Forget a token on sign-out (only the caller's own)."""
    row = db.scalar(
        select(DeviceToken).where(
            DeviceToken.expo_push_token == token, DeviceToken.user_id == user.id
        )
    )
    if row is not None:
        db.delete(row)
        db.commit()


# --- sending --------------------------------------------------------------------------------


def _already_sent(db: Session, user_id: int, kind: str, key: str) -> bool:
    rows = db.scalars(
        select(NotificationLog.payload).where(
            NotificationLog.user_id == user_id,
            NotificationLog.type == kind,
            NotificationLog.sent_at >= datetime.now(UTC) - timedelta(days=8),
        )
    ).all()
    return any(isinstance(p, dict) and p.get("key") == key for p in rows)


def notify(
    db: Session,
    user: User,
    kind: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> bool:
    """Push to all of ``user``'s devices and log it. Returns False if skipped.

    Skips users without devices and (with ``dedupe_key``) anything already sent.
    """
    if dedupe_key and _already_sent(db, user.id, kind, dedupe_key):
        return False
    tokens = list(
        db.scalars(select(DeviceToken.expo_push_token).where(DeviceToken.user_id == user.id))
    )
    if not tokens:
        return False
    tickets = send_push(tokens, title, body, data)
    dead = [
        token
        for token, ticket in zip(tokens, tickets, strict=False)
        if isinstance(ticket, dict)
        and (ticket.get("details") or {}).get("error") == "DeviceNotRegistered"
    ]
    for token in dead:
        row = db.scalar(select(DeviceToken).where(DeviceToken.expo_push_token == token))
        if row is not None:
            db.delete(row)
    db.add(
        NotificationLog(
            user_id=user.id,
            type=kind,
            payload={"key": dedupe_key, "title": title, "body": body, "data": data or {}},
        )
    )
    db.commit()
    return True


def notify_quiz_passed(
    db: Session, student: User, topic_title: str, score: float, next_topic: tuple[int, str] | None
) -> None:
    """Tell the student (and their linked parents) about a pass."""
    score_txt = str(round(score))
    body = (
        _text("passed_body_next", student, score=score_txt, topic=topic_title, next=next_topic[1])
        if next_topic
        else _text("passed_body_done", student, score=score_txt, topic=topic_title)
    )
    data: dict[str, Any] = {"screen": "topic", "topicId": next_topic[0]} if next_topic else {}
    notify(db, student, "quiz_passed", _text("passed_title", student), body, data)

    parents = db.scalars(
        select(User)
        .join(ParentLink, ParentLink.parent_user_id == User.id)
        .where(
            ParentLink.student_user_id == student.id,
            ParentLink.status == ParentLinkStatus.accepted,
        )
    ).all()
    child = (student.full_name or "Your child").split(" ")[0]
    for parent in parents:
        notify(
            db,
            parent,
            "child_passed",
            _text("parent_passed_title", parent, child=child),
            _text("parent_passed_body", parent, topic=topic_title, score=score_txt),
            {"screen": "child", "studentId": student.id},
        )


def notify_quiz_passed_in_background(
    student_id: int, topic_id: int, score: float, next_topic: tuple[int, str] | None
) -> None:
    """Background task (own DB session): never let a push failure affect the student."""
    from app.database import SessionLocal
    from app.models.curriculum import Topic

    try:
        with SessionLocal() as db:
            student = db.get(User, student_id)
            topic = db.get(Topic, topic_id)
            if student is None or topic is None:
                return
            title = curriculum_service.topic_title(
                topic, curriculum_service.student_medium(student)
            )
            notify_quiz_passed(db, student, title, score, next_topic)
    except Exception:
        logger.exception("Pass notification failed for student %s", student_id)


def _next_topic(db: Session, student: User) -> tuple[int, str] | None:
    """The topic to nudge towards: one already in progress, else the first open one."""
    subjects = curriculum_service.list_subjects(db, student)
    current = [s.current_topic for s in subjects if s.current_topic]
    active = [t for t in current if t.status.value == "active"]
    choices = active or current
    return (choices[0].id, choices[0].title) if choices else None


def send_daily_reminders(db: Session, now: datetime | None = None) -> int:
    """Remind students with a device who have not studied today. Returns pushes sent."""
    today = today_ist(now)
    students = db.scalars(
        select(User)
        .join(DeviceToken, DeviceToken.user_id == User.id)
        .where(User.role == UserRole.student, User.is_active.is_(True), User.board_id.is_not(None))
        .distinct()
    ).all()
    sent = 0
    for student in students:
        streak = get_streak(db, student, now)
        if streak.studied_today:
            continue
        topic = _next_topic(db, student)
        if topic is None:
            continue
        body = (
            _text("reminder_body_streak", student, days=streak.current, topic=topic[1])
            if streak.current >= 2
            else _text("reminder_body", student, topic=topic[1])
        )
        if notify(
            db,
            student,
            "daily_reminder",
            _text("reminder_title", student),
            body,
            {"screen": "topic", "topicId": topic[0]},
            dedupe_key=today.isoformat(),
        ):
            sent += 1
    logger.info("Daily reminders sent: %s", sent)
    return sent


def send_parent_weekly(db: Session, now: datetime | None = None) -> int:
    """One summary per linked child to each parent with a device. Returns pushes sent."""
    moment = now or datetime.now(UTC)
    week_key = "{}-W{:02d}".format(*moment.astimezone(IST).isocalendar()[:2])
    since = moment - timedelta(days=7)
    links = db.execute(
        select(ParentLink.parent_user_id, ParentLink.student_user_id).where(
            ParentLink.status == ParentLinkStatus.accepted
        )
    ).all()
    sent = 0
    for parent_id, student_id in links:
        parent = db.get(User, parent_id) if parent_id else None
        student = db.get(User, student_id)
        if parent is None or student is None:
            continue
        tests, passed, average = db.execute(
            select(
                func.count(QuizAttempt.id),
                func.count(QuizAttempt.id).filter(QuizAttempt.passed.is_(True)),
                func.avg(QuizAttempt.score_pct),
            ).where(
                QuizAttempt.user_id == student.id,
                QuizAttempt.submitted_at.is_not(None),
                QuizAttempt.submitted_at >= since,
            )
        ).one()
        child = (student.full_name or "Your child").split(" ")[0]
        if notify(
            db,
            parent,
            "parent_weekly",
            _text("weekly_title", parent, child=child),
            _text(
                "weekly_body",
                parent,
                passed=passed,
                tests=tests,
                avg=f"{round(average)}%" if average is not None else "—",
            ),
            {"screen": "child", "studentId": student.id},
            dedupe_key=f"{week_key}:{student.id}",
        ):
            sent += 1
    logger.info("Parent weekly summaries sent: %s", sent)
    return sent


def send_partner_payout_ready(db: Session, now: datetime | None = None) -> int:
    """Tell partners whose payable commission reached the payout minimum (once a week)."""
    from app.services import partner_service

    week = today_ist(now).isocalendar()
    sent = 0
    for partner, available_paise in partner_service.ready_partners(db):
        user = db.get(User, partner.user_id) if partner.user_id else None
        if user is None:
            continue
        amount = f"{available_paise / 100:,.0f}"
        if notify(
            db,
            user,
            "partner_payout_ready",
            _text("payout_ready_title", user),
            _text("payout_ready_body", user, amount=amount),
            data={"screen": "partner"},
            dedupe_key=f"payout-ready-{week.year}-{week.week}",
        ):
            sent += 1
    logger.info("Partner payout-ready notices sent: %s", sent)
    return sent
