"""Learning module: open lesson, "Not clear" style rotation, caching, failures, limits."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.curriculum import Board, Chapter, Subject, Topic
from app.models.enums import JobStatus, LessonStatus, LessonStyle, Medium, UserRole
from app.models.lesson import ClarityFeedback, GenerationJob, Lesson
from app.models.user import User
from app.services.ai.explanation import LessonScript
from app.services.ai.images import get_fake_image_client
from app.services.ai.llm import LLMError, get_fake_llm_client
from app.services.ai.tts import get_fake_tts_client
from app.services.learning_service import choose_next_style

Headers = Callable[[User], dict[str, str]]


@pytest.fixture()
def topics(db: Session) -> tuple[Topic, Topic]:
    """Board → Science → Motion → (Speed [open], Velocity [locked])."""
    board = Board(code="TN_SSLC", name="Tamil Nadu State Board", is_active=True)
    subject = Subject(
        board=board, name="Science", tile_color="#4F8A6B", icon="flask", display_order=1
    )
    chapter = Chapter(subject=subject, title="Motion", display_order=1)
    speed = Topic(
        chapter=chapter,
        title="Speed",
        learning_objectives="Define speed; use speed = distance / time",
        display_order=1,
        is_published=True,
    )
    velocity = Topic(chapter=chapter, title="Velocity", display_order=2, is_published=True)
    db.add_all([board, subject, chapter, speed, velocity])
    db.commit()
    return speed, velocity


@pytest.fixture()
def student(make_user: Callable[..., User], topics: tuple[Topic, Topic]) -> User:
    board_id = topics[0].chapter.subject.board_id
    return make_user(role=UserRole.student, board_id=board_id, medium=Medium.en)


def _open(client: TestClient, headers: dict[str, str], topic: Topic) -> dict:
    res = client.get(f"/api/v1/topics/{topic.id}/lesson", headers=headers)
    assert res.status_code in (200, 202), res.text
    return res.json()


def _lesson_of(body: dict) -> dict:
    lesson = body["lesson"] or body["job"]["lesson"]
    assert lesson is not None, body
    return lesson


def _watch(client: TestClient, headers: dict[str, str], lesson_id: int) -> None:
    res = client.put(
        f"/api/v1/lessons/{lesson_id}/progress",
        json={"watchedSec": 30, "completed": True},
        headers=headers,
    )
    assert res.status_code == 204


def _not_clear(
    client: TestClient, headers: dict[str, str], topic: Topic, lesson_id: int | None
) -> dict:
    res = client.post(
        f"/api/v1/topics/{topic.id}/not-clear", json={"lessonId": lesson_id}, headers=headers
    )
    assert res.status_code in (200, 202), res.text
    return res.json()


# --- Opening a topic --------------------------------------------------------------------------


def test_first_open_generates_story_lesson_with_audio(
    client: TestClient, student: User, auth_headers: Headers, topics: tuple[Topic, Topic]
) -> None:
    speed, _ = topics
    res = client.get(f"/api/v1/topics/{speed.id}/lesson", headers=auth_headers(student))
    assert res.status_code == 202
    body = res.json()
    assert body["state"] == "generating"
    assert body["job"]["status"] == "done"  # sync runner in tests
    lesson = _lesson_of(body)
    assert lesson["style"] == "story" and lesson["styleLabel"] == "Story"
    assert lesson["slides"][0]["emoji"] == "💡"
    # Every scene has a storybook picture, drawn from the script's image prompt.
    assert all(slide["imageUrl"] for slide in lesson["slides"])
    assert lesson["slides"][0]["imageUrl"].endswith(f"/lessons/{lesson['id']}/scene-1.jpg")
    assert any("brakes suddenly" in prompt for prompt in get_fake_image_client().prompts)
    assert lesson["status"] == "ready"
    assert len(lesson["slides"]) == 4
    assert lesson["slides"][0]["startSec"] == 0
    assert lesson["audioUrl"].endswith(f"/media/lessons/{lesson['id']}/audio.mp3")
    assert lesson["videoUrl"] is None  # video rendering disabled in tests
    assert len(get_fake_tts_client().calls) >= 4


def test_second_open_uses_cached_lesson(
    client: TestClient,
    db: Session,
    student: User,
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
) -> None:
    speed, _ = topics
    headers = auth_headers(student)
    first = _lesson_of(_open(client, headers, speed))
    res = client.get(f"/api/v1/topics/{speed.id}/lesson", headers=headers)
    assert res.status_code == 200
    assert res.json()["lesson"]["id"] == first["id"]
    assert db.scalar(select(func.count(GenerationJob.id))) == 1


def test_prompt_is_grounded_in_topic(
    client: TestClient, student: User, auth_headers: Headers, topics: tuple[Topic, Topic]
) -> None:
    speed, _ = topics
    _open(client, auth_headers(student), speed)
    system, user, schema = get_fake_llm_client().calls[-1]
    assert schema is LessonScript
    assert "Topic: Speed" in user and "speed = distance / time" in user
    assert "Tamil Nadu State Board" in system and "15 years old" in system


def test_locked_topic_blocks_lessons_and_not_clear(
    client: TestClient, student: User, auth_headers: Headers, topics: tuple[Topic, Topic]
) -> None:
    _, velocity = topics
    headers = auth_headers(student)
    assert client.get(f"/api/v1/topics/{velocity.id}/lesson", headers=headers).status_code == 403
    res = client.post(f"/api/v1/topics/{velocity.id}/not-clear", json={}, headers=headers)
    assert res.status_code == 403 and res.json()["error"]["code"] == "topic_locked"


# --- "Not clear" ---------------------------------------------------------------------------------


def test_not_clear_rotates_to_unseen_styles(
    client: TestClient,
    db: Session,
    student: User,
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
) -> None:
    speed, _ = topics
    headers = auth_headers(student)
    base = _lesson_of(_open(client, headers, speed))
    _watch(client, headers, base["id"])

    second = _lesson_of(_not_clear(client, headers, speed, base["id"]))
    assert second["style"] == "analogy" and second["styleLabel"]
    _watch(client, headers, second["id"])

    third = _lesson_of(_not_clear(client, headers, speed, second["id"]))
    assert third["style"] == "step_by_step"

    # The new prompt asks to avoid the previous explanation.
    assert "did not understand" in get_fake_llm_client().calls[-1][1]
    feedback = db.scalars(select(ClarityFeedback)).all()
    assert [f.is_clear for f in feedback] == [False, False]

    # Reopening the topic shows the most recently watched style.
    assert _open(client, headers, speed)["lesson"]["id"] == second["id"]


def test_second_student_gets_cached_explanation(
    client: TestClient,
    db: Session,
    student: User,
    make_user: Callable[..., User],
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
) -> None:
    speed, _ = topics
    a = auth_headers(student)
    base = _lesson_of(_open(client, a, speed))
    _watch(client, a, base["id"])
    analogy = _lesson_of(_not_clear(client, a, speed, base["id"]))
    jobs_before = db.scalar(select(func.count(GenerationJob.id)))

    other = make_user(role=UserRole.student, board_id=student.board_id, medium=Medium.en)
    b = auth_headers(other)
    assert client.get(f"/api/v1/topics/{speed.id}/lesson", headers=b).status_code == 200
    _watch(client, b, base["id"])
    res = client.post(
        f"/api/v1/topics/{speed.id}/not-clear", json={"lessonId": base["id"]}, headers=b
    )
    assert res.status_code == 200
    assert res.json()["lesson"]["id"] == analogy["id"]
    assert db.scalar(select(func.count(GenerationJob.id))) == jobs_before


def test_invalid_llm_output_retries_once_then_fails_friendly(
    client: TestClient,
    db: Session,
    student: User,
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
) -> None:
    speed, _ = topics
    attempts: list[int] = []

    def _broken(system: str, user: str) -> LessonScript:
        attempts.append(1)
        raise LLMError("invalid JSON")

    get_fake_llm_client().register(LessonScript, _broken)
    body = _open(client, auth_headers(student), speed)
    assert len(attempts) == 2
    assert body["job"]["status"] == "failed"
    assert "try again" in body["job"]["error"]
    assert body["job"]["lesson"] is None
    assert db.scalar(select(Lesson.status)) == LessonStatus.failed

    # After the AI recovers, opening again queues a fresh job.
    get_fake_llm_client().unregister(LessonScript)
    retry = _open(client, auth_headers(student), speed)
    assert retry["job"]["status"] == "done"


def test_daily_generation_limit(
    client: TestClient,
    student: User,
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    speed, _ = topics
    monkeypatch.setattr(settings, "AI_GENERATIONS_PER_USER_PER_DAY", 1)
    headers = auth_headers(student)
    base = _lesson_of(_open(client, headers, speed))  # base lessons don't count
    _watch(client, headers, base["id"])
    second = _lesson_of(_not_clear(client, headers, speed, base["id"]))
    _watch(client, headers, second["id"])
    res = client.post(
        f"/api/v1/topics/{speed.id}/not-clear", json={"lessonId": second["id"]}, headers=headers
    )
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "generation_limit"


def test_mark_clear_records_feedback(
    client: TestClient,
    db: Session,
    student: User,
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
) -> None:
    speed, _ = topics
    headers = auth_headers(student)
    base = _lesson_of(_open(client, headers, speed))
    res = client.post(
        f"/api/v1/topics/{speed.id}/clear", json={"lessonId": base["id"]}, headers=headers
    )
    assert res.status_code == 204
    assert db.scalar(select(ClarityFeedback.is_clear)) is True


# --- Jobs ---------------------------------------------------------------------------------------


def test_get_job_and_access_checks(
    client: TestClient,
    db: Session,
    student: User,
    make_user: Callable[..., User],
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
) -> None:
    speed, velocity = topics
    headers = auth_headers(student)
    job_id = _open(client, headers, speed)["job"]["id"]
    res = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert res.status_code == 200 and res.json()["status"] == "done"
    assert client.get("/api/v1/jobs/999999", headers=headers).status_code == 404

    # A job for a topic this student cannot open is hidden.
    locked_job = GenerationJob(
        user_id=None,
        topic_id=velocity.id,
        medium=Medium.en,
        kind="explanation",
        status=JobStatus.queued,
    )
    db.add(locked_job)
    db.commit()
    assert client.get(f"/api/v1/jobs/{locked_job.id}", headers=headers).status_code == 403


# --- Pure helpers ---------------------------------------------------------------------------------


def test_choose_next_style_prefers_unseen_then_least_recent() -> None:
    now = datetime.now(UTC)
    assert choose_next_style({}, LessonStyle.story) == LessonStyle.analogy
    seen = {style: now - timedelta(minutes=i) for i, style in enumerate(LessonStyle)}
    # All seen: least recently seen that is not the current one.
    assert choose_next_style(seen, LessonStyle.visual) == LessonStyle.worked_example
    assert choose_next_style(seen, LessonStyle.base) == LessonStyle.visual


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_render_video_produces_mp4() -> None:
    from app.services.ai.tts import _silent_mp3
    from app.services.ai.video_render import SlideText, render_slide_frames, render_video

    english = render_slide_frames(
        SlideText("Speed", ["distance / time", "km per hour"], "🚌"), "#4F8A6B", 1, 2
    )
    tamil = render_slide_frames(SlideText("வேகம்", ["தூரம் / நேரம்"]), "#4F8A6B", 2, 2)
    assert len(english) == 3 and len(tamil) == 2  # heading, then one frame per bullet
    mp4 = render_video([english, tamil], [_silent_mp3(), _silent_mp3()], [2.0, 2.0])
    assert mp4[4:8] == b"ftyp"


def test_reveal_offsets_spread_bullets_over_narration() -> None:
    from app.services.ai.video_render import reveal_offsets

    assert reveal_offsets(12.0, 3) == [3.0, 6.0, 9.0]
    assert reveal_offsets(5.0, 0) == []


def test_student_can_pick_a_style(
    client: TestClient,
    db: Session,
    student: User,
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
) -> None:
    speed, velocity = topics
    headers = auth_headers(student)
    res = client.post(
        f"/api/v1/topics/{speed.id}/lesson-style", json={"style": "worked_example"}, headers=headers
    )
    assert res.status_code == 202
    assert _lesson_of(res.json())["style"] == "worked_example"
    again = client.post(
        f"/api/v1/topics/{speed.id}/lesson-style", json={"style": "worked_example"}, headers=headers
    )
    assert again.status_code == 200  # cached, no new job
    assert db.scalar(select(func.count(GenerationJob.id))) == 1
    bad = client.post(
        f"/api/v1/topics/{speed.id}/lesson-style", json={"style": "poem"}, headers=headers
    )
    assert bad.status_code == 422
    locked = client.post(
        f"/api/v1/topics/{velocity.id}/lesson-style", json={"style": "story"}, headers=headers
    )
    assert locked.status_code == 403


# --- Explanation language (English / Tamil / Tanglish) --------------------------------------------


def test_lesson_language_defaults_to_medium_and_can_switch_to_tanglish(
    client: TestClient,
    db: Session,
    student: User,
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
) -> None:
    speed, _ = topics
    headers = auth_headers(student)
    english = _lesson_of(_open(client, headers, speed))
    assert english["language"] == "en"
    get_fake_tts_client().calls.clear()

    res = client.post(
        f"/api/v1/topics/{speed.id}/lesson-language",
        json={"language": "tanglish", "style": "story"},
        headers=headers,
    )
    assert res.status_code == 202
    tanglish = _lesson_of(res.json())
    assert tanglish["language"] == "tanglish" and tanglish["style"] == "story"
    assert tanglish["id"] != english["id"]
    assert "Tanglish" in get_fake_llm_client().calls[-1][1]
    assert {voice for _, voice in get_fake_tts_client().calls} == {"ta"}  # Tamil voice

    # Remembered: the profile shows it and the next open uses Tanglish.
    assert client.get("/api/v1/auth/me", headers=headers).json()["lessonLanguage"] == "tanglish"
    reopened = client.get(f"/api/v1/topics/{speed.id}/lesson", headers=headers)
    assert reopened.status_code == 200 and reopened.json()["lesson"]["id"] == tanglish["id"]


def test_language_preference_via_profile_and_validation(
    client: TestClient, student: User, auth_headers: Headers, topics: tuple[Topic, Topic]
) -> None:
    headers = auth_headers(student)
    assert (
        client.put("/api/v1/auth/me", json={"lessonLanguage": "ta"}, headers=headers).status_code
        == 200
    )
    lesson = _lesson_of(_open(client, headers, topics[0]))
    assert lesson["language"] == "ta" and lesson["medium"] == "en"  # textbook medium unchanged
    bad = client.post(
        f"/api/v1/topics/{topics[0].id}/lesson-language",
        json={"language": "hindi"},
        headers=headers,
    )
    assert bad.status_code == 422


def test_mixed_script_runs_split_tamil_and_latin() -> None:
    from app.services.ai.video_render import _runs, contains_tamil

    assert _runs("இந்த object வேகம்") == [(True, "இந்த "), (False, "object "), (True, "வேகம்")]
    assert contains_tamil("velocity மாறாது") and not contains_tamil("velocity")


def test_lesson_still_delivered_when_a_picture_fails(
    client: TestClient,
    student: User,
    auth_headers: Headers,
    topics: tuple[Topic, Topic],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.ai import images

    calls = {"n": 0}
    real_generate = images.FakeImageClient().generate

    def flaky(scene_prompt: str) -> bytes:
        calls["n"] += 1
        if calls["n"] == 1:
            raise images.ImageError("content filter")
        return real_generate(scene_prompt)

    monkeypatch.setattr(images.get_fake_image_client(), "generate", flaky)
    lesson = _lesson_of(_open(client, auth_headers(student), topics[0]))
    assert lesson["status"] == "ready"
    urls = [slide["imageUrl"] for slide in lesson["slides"]]
    assert urls.count(None) == 1 and len(urls) == 4
