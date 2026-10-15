"""Streaks, device registration, pass notifications, daily reminders, parent weekly."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.curriculum import Board, Chapter, Subject, Topic
from app.models.enums import Medium, ParentLinkStatus, UserRole
from app.models.notification import DeviceToken
from app.models.parent import ParentLink
from app.models.user import User
from app.services import notification_service, streak_service
from app.services.push import get_push_sender

Headers = Callable[[User], dict[str, str]]
CORRECT = "Correct answer"
TOKEN = "ExponentPushToken[student-phone]"
PARENT_TOKEN = "ExponentPushToken[parent-phone]"


@pytest.fixture(autouse=True)
def pushes() -> Iterator[list[dict[str, Any]]]:
    sender = get_push_sender()
    sent: list[dict[str, Any]] = sender.sent  # type: ignore[attr-defined]
    sent.clear()
    yield sent
    sent.clear()


@pytest.fixture()
def topics(db: Session) -> tuple[Topic, Topic]:
    board = Board(code="TN_SSLC", name="Tamil Nadu State Board", is_active=True)
    subject = Subject(
        board=board, name="Maths", tile_color="#3B6EA5", icon="calculator", display_order=1
    )
    chapter = Chapter(subject=subject, title="Sets", display_order=1)
    first = Topic(chapter=chapter, title="What is a set", display_order=1, is_published=True)
    second = Topic(chapter=chapter, title="Venn diagrams", display_order=2, is_published=True)
    db.add_all([board, subject, chapter, first, second])
    db.commit()
    return first, second


@pytest.fixture()
def student(make_user: Callable[..., User], topics: tuple[Topic, Topic], db: Session) -> User:
    user = make_user(
        role=UserRole.student,
        board_id=topics[0].chapter.subject.board_id,
        medium=Medium.en,
        full_name="Kavya R",
    )
    db.add(DeviceToken(user_id=user.id, expo_push_token=TOKEN, platform="android"))
    db.commit()
    return user


@pytest.fixture()
def parent(make_user: Callable[..., User], student: User, db: Session) -> User:
    user = make_user(role=UserRole.parent, medium=Medium.ta, full_name="Amma")
    db.add_all(
        [
            DeviceToken(user_id=user.id, expo_push_token=PARENT_TOKEN, platform="android"),
            ParentLink(
                parent_user_id=user.id,
                student_user_id=student.id,
                invite_code="ABCDEFGH",
                invite_expires_at=datetime.now(UTC) + timedelta(days=7),
                status=ParentLinkStatus.accepted,
                accepted_at=datetime.now(UTC),
            ),
        ]
    )
    db.commit()
    return user


# --- streaks ------------------------------------------------------------------------------------


def test_streak_counts_consecutive_days(db: Session, student: User) -> None:
    day1 = datetime(2026, 10, 10, 6, 0, tzinfo=UTC)  # 11:30 IST
    streak_service.record_study(db, student, day1)
    streak_service.record_study(db, student, day1 + timedelta(hours=3))  # same day: no change
    streak_service.record_study(db, student, day1 + timedelta(days=1))
    db.commit()
    s = streak_service.get_streak(db, student, day1 + timedelta(days=1))
    assert (s.current, s.longest, s.studied_today) == (2, 2, True)
    # Next day, not studied yet: streak still alive, today not counted.
    s = streak_service.get_streak(db, student, day1 + timedelta(days=2))
    assert (s.current, s.studied_today) == (2, False)
    # A missed day breaks it; the best is remembered.
    assert streak_service.get_streak(db, student, day1 + timedelta(days=3)).current == 0
    streak_service.record_study(db, student, day1 + timedelta(days=4))
    db.commit()
    s = streak_service.get_streak(db, student, day1 + timedelta(days=4))
    assert (s.current, s.longest) == (1, 2)


def test_streak_uses_india_time(db: Session, student: User) -> None:
    # 20:00 UTC on the 10th is already the 11th in India.
    streak_service.record_study(db, student, datetime(2026, 10, 10, 20, 0, tzinfo=UTC))
    db.commit()
    s = streak_service.get_streak(db, student, datetime(2026, 10, 11, 5, 0, tzinfo=UTC))
    assert s.studied_today is True


def test_streak_endpoint(client: TestClient, student: User, auth_headers: Headers) -> None:
    res = client.get("/api/v1/streak", headers=auth_headers(student))
    assert res.status_code == 200 and res.json() == {
        "current": 0,
        "longest": 0,
        "studiedToday": False,
    }


# --- devices ------------------------------------------------------------------------------------


def test_device_registration(
    client: TestClient,
    db: Session,
    student: User,
    make_user: Callable[..., User],
    auth_headers: Headers,
) -> None:
    other = make_user(role=UserRole.student)
    bad = client.post(
        "/api/v1/devices", json={"expoPushToken": "not-a-token"}, headers=auth_headers(other)
    )
    assert bad.status_code == 422
    # Same phone signs in to another account → token moves.
    assert (
        client.post(
            "/api/v1/devices", json={"expoPushToken": TOKEN}, headers=auth_headers(other)
        ).status_code
        == 204
    )
    assert (
        db.scalar(select(DeviceToken.user_id).where(DeviceToken.expo_push_token == TOKEN))
        == other.id
    )
    # Only the owner can remove it.
    client.post(
        "/api/v1/devices/remove", json={"expoPushToken": TOKEN}, headers=auth_headers(student)
    )
    assert (
        db.scalar(select(func.count(DeviceToken.id)).where(DeviceToken.expo_push_token == TOKEN))
        == 1
    )
    client.post(
        "/api/v1/devices/remove", json={"expoPushToken": TOKEN}, headers=auth_headers(other)
    )
    db.expire_all()
    assert (
        db.scalar(select(func.count(DeviceToken.id)).where(DeviceToken.expo_push_token == TOKEN))
        == 0
    )


# --- pass notifications -----------------------------------------------------------------


def test_passing_a_test_notifies_student_and_parent(
    client: TestClient,
    student: User,
    parent: User,
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
    pushes: list[dict[str, Any]],
) -> None:
    headers = auth_headers(student)
    attempt = client.post(f"/api/v1/topics/{topics[0].id}/quiz-attempts", headers=headers).json()
    answers = [{"questionId": q["questionId"], "answer": CORRECT} for q in attempt["questions"]]
    res = client.post(
        f"/api/v1/quiz-attempts/{attempt['attemptId']}/submit",
        json={"answers": answers},
        headers=headers,
    )
    assert res.json()["passed"] is True

    by_token = {p["tokens"][0]: p for p in pushes}
    mine = by_token[TOKEN]
    assert "Venn diagrams" in mine["body"] and mine["data"] == {
        "screen": "topic",
        "topicId": topics[1].id,
    }
    theirs = by_token[PARENT_TOKEN]
    assert "Kavya" in theirs["title"] and "ஒரு பாடத்தில்" in theirs["title"]  # parent reads Tamil
    # Studying today was recorded.
    assert client.get("/api/v1/streak", headers=headers).json()["studiedToday"] is True


def test_failing_a_test_sends_nothing(
    client: TestClient,
    student: User,
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
    pushes: list[dict[str, Any]],
) -> None:
    headers = auth_headers(student)
    attempt = client.post(f"/api/v1/topics/{topics[0].id}/quiz-attempts", headers=headers).json()
    client.post(
        f"/api/v1/quiz-attempts/{attempt['attemptId']}/submit",
        json={"answers": []},
        headers=headers,
    )
    assert pushes == []


# --- scheduled ------------------------------------------------------------------------------


def test_daily_reminder_once_and_only_if_not_studied(
    db: Session, student: User, pushes: list[dict[str, Any]]
) -> None:
    now = datetime(2026, 10, 15, 12, 30, tzinfo=UTC)  # 18:00 IST
    assert notification_service.send_daily_reminders(db, now) == 1
    assert pushes[0]["body"] == "Your next topic is waiting: What is a set"
    assert notification_service.send_daily_reminders(db, now) == 0  # de-duplicated
    # Tomorrow, after studying, no reminder.
    tomorrow = now + timedelta(days=1)
    streak_service.record_study(db, student, tomorrow)
    db.commit()
    assert notification_service.send_daily_reminders(db, tomorrow) == 0


def test_reminder_mentions_streak(db: Session, student: User, pushes: list[dict[str, Any]]) -> None:
    now = datetime(2026, 10, 15, 12, 30, tzinfo=UTC)
    for days_ago in (2, 1):
        streak_service.record_study(db, student, now - timedelta(days=days_ago))
    db.commit()
    notification_service.send_daily_reminders(db, now)
    assert "2-day streak" in pushes[0]["body"]


def test_dead_tokens_are_removed(
    db: Session, student: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    def gone(tokens: list[str], *_: Any, **__: Any) -> list[dict[str, Any]]:
        return [{"status": "error", "details": {"error": "DeviceNotRegistered"}} for _ in tokens]

    monkeypatch.setattr(notification_service, "send_push", gone)
    notification_service.notify(db, student, "test", "t", "b")
    assert (
        db.scalar(select(func.count(DeviceToken.id)).where(DeviceToken.user_id == student.id)) == 0
    )


def test_parent_weekly_once_per_week(
    db: Session, student: User, parent: User, pushes: list[dict[str, Any]]
) -> None:
    sunday = datetime(2026, 10, 18, 13, 30, tzinfo=UTC)
    assert notification_service.send_parent_weekly(db, sunday) == 1
    assert pushes[0]["tokens"] == [PARENT_TOKEN] and "Kavya" in pushes[0]["title"]
    assert notification_service.send_parent_weekly(db, sunday + timedelta(hours=1)) == 0
    assert notification_service.send_parent_weekly(db, sunday + timedelta(days=7)) == 1


def test_cli_send_reminders(student: User, pushes: list[dict[str, Any]]) -> None:
    from app.cli import main

    assert main(["send-reminders"]) == 0
    assert len(pushes) == 1
