"""Celery application (Redis broker). Tasks run eagerly under the test environment."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "personal_teacher_assistant",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    task_always_eager=settings.is_test,
    task_eager_propagates=settings.is_test,
    task_store_eager_result=False,
    beat_schedule={
        # Times are Asia/Kolkata (``timezone`` above).
        "daily-study-reminders": {
            "task": "notifications.daily_reminders",
            "schedule": crontab(hour=18, minute=0),
        },
        "parent-weekly-summary": {
            "task": "notifications.parent_weekly",
            "schedule": crontab(hour=19, minute=0, day_of_week="sun"),
        },
        "partners-daily": {
            "task": "partners.daily",
            "schedule": crontab(hour=10, minute=0),
        },
    },
)
