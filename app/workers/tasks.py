import asyncio

from app.services.source_change_monitor import monitor_source_changes
from app.workers.celery_app import celery_app
from app.workers.runner import run_pending, schedule_sources


@celery_app.task(name="platform.poll", ignore_result=True)
def poll():
    return asyncio.run(run_pending())


@celery_app.task(name="platform.schedule", ignore_result=True)
def schedule():
    return asyncio.run(schedule_sources())


@celery_app.task(name="platform.monitor-source-changes", ignore_result=True)
def monitor_changes():
    return asyncio.run(monitor_source_changes())
