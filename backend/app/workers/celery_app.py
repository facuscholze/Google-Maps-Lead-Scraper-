"""Celery application (used when EXECUTION_MODE=celery)."""
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "avascho",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=settings.default_timezone,
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Send due emails on a fixed cadence (variable delays are enforced in the queue).
celery_app.conf.beat_schedule = {
    "process-email-queue-every-30s": {
        "task": "app.workers.tasks.process_email_queue",
        "schedule": 30.0,
        "args": (),
    }
}
