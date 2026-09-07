from celery import Celery

from app.core.config import get_settings

s = get_settings()
celery_app = Celery(
    "google_sheet_ai",
    broker=s.celery_broker_url.get_secret_value(),
    backend=s.celery_result_backend.get_secret_value(),
    include=["app.workers.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "dispatch-durable-jobs": {"task": "platform.poll", "schedule": s.job_poll_seconds},
        "schedule-sources": {"task": "platform.schedule", "schedule": 60.0},
    },
)
