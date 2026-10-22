"""Celery tasks and the dispatcher that picks the configured job runner."""

from __future__ import annotations

import logging
import threading
from typing import Literal

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


@celery_app.task(name="exams.generate_paper", acks_late=True)
def generate_paper_task(paper_id: int) -> None:
    """Celery entry point: write a model question paper."""
    from app.services.model_paper_service import run_generation_job

    run_generation_job(paper_id)


@celery_app.task(name="exams.grade_paper", acks_late=True)
def grade_paper_task(paper_id: int) -> None:
    """Celery entry point: mark a model paper's answer photos."""
    from app.services.model_paper_service import run_grading_job

    run_grading_job(paper_id)


def dispatch_paper_job(kind: Literal["generate", "grade"], paper_id: int) -> None:
    """Run a model-paper job using ``settings.job_runner`` (celery / thread / sync)."""
    from app.services.model_paper_service import run_generation_job, run_grading_job

    task = generate_paper_task if kind == "generate" else grade_paper_task
    target = run_generation_job if kind == "generate" else run_grading_job
    runner = settings.job_runner
    if runner == "celery":
        task.delay(paper_id)
    elif runner == "thread":
        threading.Thread(
            target=target, args=(paper_id,), name=f"paper-{kind}-{paper_id}", daemon=True
        ).start()
    else:
        target(paper_id)
    logger.info("Dispatched paper %s job %s via %s", kind, paper_id, runner)


@celery_app.task(name="partners.daily")
def partners_daily_task() -> int:
    """Celery beat: pick up subscription renewals, then tell partners whose payout is ready."""
    from app.database import SessionLocal
    from app.services.billing_service import refresh_due_subscriptions
    from app.services.notification_service import send_partner_payout_ready

    with SessionLocal() as db:
        refresh_due_subscriptions(db)
        return send_partner_payout_ready(db)
