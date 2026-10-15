"""Background explanation job: LLM script → TTS audio (delivered first) → slide video."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.enums import JobStatus, LessonLanguage, LessonStatus, LessonStyle, Medium
from app.models.lesson import GenerationJob, Lesson, LessonView
from app.services.ai.explanation import LessonScript, generate_script
from app.services.ai.images import ImageError, get_image_client
from app.services.ai.llm import LLMError, get_llm_client
from app.services.ai.tts import TTSError, get_tts_client
from app.services.ai.video_render import (
    RenderError,
    SlideText,
    audio_duration,
    concat_mp3,
    contains_tamil,
    render_slide_frames,
    render_video,
    tamil_shaping_available,
)
from app.services.curriculum_service import topic_context
from app.services.storage import StorageError, get_storage

logger = logging.getLogger(__name__)


def voice_for(language: LessonLanguage) -> str:
    """TTS voice key: Tanglish is read by the Tamil voice (it handles the English words)."""
    return "en" if language == LessonLanguage.en else "ta"


FRIENDLY_ERROR = "We could not prepare this explanation. Please try again in a moment."


def _previous_summary(db: Session, job: GenerationJob, lesson: Lesson) -> str | None:
    """Summary of the lesson this student watched most recently for the topic (to avoid repeats)."""
    if job.user_id is None:
        return None
    return db.scalar(
        select(Lesson.summary)
        .join(LessonView, LessonView.lesson_id == Lesson.id)
        .where(
            LessonView.user_id == job.user_id,
            Lesson.topic_id == lesson.topic_id,
            Lesson.id != lesson.id,
        )
        .order_by(LessonView.updated_at.desc())
        .limit(1)
    )


def _finish(db: Session, job: GenerationJob, status: JobStatus, error: str | None = None) -> None:
    job.status = status
    job.error = error
    job.finished_at = datetime.now(UTC)
    db.commit()


def run_explanation_job(job_id: int) -> None:
    """Execute one explanation job end to end (idempotent for finished jobs)."""
    with SessionLocal() as db:
        job = db.get(GenerationJob, job_id)
        if job is None or job.status in (JobStatus.done, JobStatus.failed) or job.lesson_id is None:
            return
        lesson = db.get(Lesson, job.lesson_id)
        if lesson is None:
            _finish(db, job, JobStatus.failed, "Lesson missing")
            return
        job.status = JobStatus.running
        job.started_at = datetime.now(UTC)
        lesson.status = LessonStatus.generating
        db.commit()

        language = LessonLanguage(lesson.language)
        # Topic text: Tamil for Tamil lessons; English terms for English and Tanglish.
        medium = Medium.ta if language == LessonLanguage.ta else Medium.en
        try:
            script = generate_script(
                get_llm_client(),
                topic_context(lesson.topic, medium),
                LessonStyle(lesson.style),
                language,
                _previous_summary(db, job, lesson),
            )
            audios, durations, pictures = _deliver_audio(db, lesson, script, language)
        except (LLMError, TTSError, StorageError, RenderError) as exc:
            logger.warning("Explanation job %s failed: %s", job.id, exc)
            lesson.status = LessonStatus.failed
            _finish(db, job, JobStatus.failed, FRIENDLY_ERROR)
            return
        except Exception:
            logger.exception("Explanation job %s crashed", job.id)
            db.rollback()
            lesson.status = LessonStatus.failed
            _finish(db, job, JobStatus.failed, FRIENDLY_ERROR)
            return

        # Audio is playable now; the video is a bonus that must not fail the job.
        _render_video(db, lesson, script, language, audios, durations, pictures)
        _finish(db, job, JobStatus.done)


def _illustrate(prompt: str) -> bytes | None:
    """One storybook picture; a failure only drops this scene's picture."""
    if not prompt.strip():
        return None
    try:
        return get_image_client().generate(prompt)
    except ImageError as exc:
        logger.warning("Scene illustration failed (scene shown without picture): %s", exc)
        return None


def _deliver_audio(
    db: Session, lesson: Lesson, script: LessonScript, language: LessonLanguage
) -> tuple[list[bytes], list[float], list[bytes | None]]:
    """TTS each slide while the scene pictures are drawn in parallel, upload everything
    and mark the lesson ``audio_ready``.

    Returns:
        Per-slide MP3 clips, their durations (seconds) and pictures, for the video renderer
    """
    pool = ThreadPoolExecutor(max_workers=max(1, settings.IMAGE_PARALLELISM))
    picture_jobs = [pool.submit(_illustrate, slide.image_prompt) for slide in script.slides]
    tts = get_tts_client()
    audios: list[bytes] = []
    durations: list[float] = []
    slides_out: list[dict[str, object]] = []
    start = 0.0
    for slide in script.slides:
        mp3 = tts.synthesize(slide.narration, voice_for(language))
        audios.append(mp3)
        duration = audio_duration(mp3, slide.narration)
        durations.append(duration)
        slides_out.append({**slide.model_dump(), "startSec": round(start, 2)})
        start += duration

    storage = get_storage()
    key = f"lessons/{lesson.id}/audio.mp3"
    storage.put_object(key, concat_mp3(audios), "audio/mpeg")

    pictures = [job.result() for job in picture_jobs]
    pool.shutdown()
    for i, picture in enumerate(pictures):
        if picture is not None:
            picture_key = f"lessons/{lesson.id}/scene-{i + 1}.jpg"
            storage.put_object(picture_key, picture, "image/jpeg")
            slides_out[i]["imageKey"] = picture_key

    lesson.title = script.title
    lesson.summary = script.summary
    lesson.script_text = "\n\n".join(slide.narration for slide in script.slides)
    lesson.slides_json = {"slides": slides_out}
    lesson.audio_key = key
    lesson.duration_sec = round(start)
    lesson.status = LessonStatus.audio_ready
    db.commit()
    return audios, durations, pictures


def _render_video(
    db: Session,
    lesson: Lesson,
    script: LessonScript,
    language: LessonLanguage,
    audios: list[bytes],
    durations: list[float],
    pictures: list[bytes | None],
) -> None:
    needs_tamil = language != LessonLanguage.en or any(
        contains_tamil(s.heading + "".join(s.bullets)) for s in script.slides
    )
    if needs_tamil and not tamil_shaping_available():
        logger.warning(
            "Skipping video for lesson %s: Tamil text shaping (libraqm) is not available; "
            "the narrated animated slides are still served",
            lesson.id,
        )
    elif settings.VIDEO_RENDER_ENABLED:
        try:
            accent = lesson.topic.chapter.subject.tile_color
            total = len(script.slides)
            frames = [
                render_slide_frames(
                    SlideText(
                        s.heading,
                        s.bullets,
                        s.emoji,
                        picture=pictures[i],
                    ),
                    accent,
                    i + 1,
                    total,
                )
                for i, s in enumerate(script.slides)
            ]
            key = f"lessons/{lesson.id}/video.mp4"
            video = render_video(frames, audios, durations, pictures)
            get_storage().put_object(key, video, "video/mp4")
            lesson.video_key = key
        except (RenderError, StorageError, OSError) as exc:
            logger.warning(
                "Video render failed for lesson %s (audio still available): %s", lesson.id, exc
            )
    lesson.status = LessonStatus.ready
    db.commit()
