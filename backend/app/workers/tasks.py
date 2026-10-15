"""Celery tasks and the dispatcher that picks the configured job runner."""

from __future__ import annotations

import logging
import threading

from app.config import settings
from app.services.ai.lesson_pipeline import run_explanation_job
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="lessons.generate_explanation", acks_late=True)
def generate_explanation_task(job_id: int) -> None:
    """Celery entry point for an explanation job."""
    run_explanation_job(job_id)


@celery_app.task(name="notifications.daily_reminders")
def daily_reminders_task() -> int:
    """Celery beat: study reminders for students who have not studied today."""
    from app.database import SessionLocal
    from app.services.notification_service import send_daily_reminders

    with SessionLocal() as db:
        return send_daily_reminders(db)


@celery_app.task(name="notifications.parent_weekly")
def parent_weekly_task() -> int:
    """Celery beat: weekly progress summaries for parents."""
    from app.database import SessionLocal
    from app.services.notification_service import send_parent_weekly

    with SessionLocal() as db:
        return send_parent_weekly(db)


def dispatch_explanation_job(job_id: int) -> None:
    """Run an explanation job using ``settings.job_runner`` (celery / thread / sync)."""
    runner = settings.job_runner
    if runner == "celery":
        generate_explanation_task.delay(job_id)
    elif runner == "thread":
        threading.Thread(
            target=run_explanation_job, args=(job_id,), name=f"explanation-{job_id}", daemon=True
        ).start()
    else:
        run_explanation_job(job_id)
    logger.info("Dispatched explanation job %s via %s", job_id, runner)
