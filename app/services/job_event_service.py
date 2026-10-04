import asyncio
import json
import time

from fastapi.encoders import jsonable_encoder

from app.core.database import SessionFactory
from app.models.etl import Job
from app.repositories.base import TenantRepository, record

TERMINAL_JOB_STATUSES = {"SUCCEEDED", "SUCCEEDED_WITH_WARNINGS", "FAILED", "CANCELLED", "SKIPPED"}


def sse_message(event, data):
    return f"event: {event}\ndata: {json.dumps(jsonable_encoder(data), separators=(',', ':'))}\n\n"


async def job_event_stream(request, *, tenant_id, job_id, interval_seconds=1.0, max_seconds=120):
    last_signature = None
    last_heartbeat = time.monotonic()
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline and not await request.is_disconnected():
        async with SessionFactory() as session:
            job = await session.scalar(
                TenantRepository(session, tenant_id).query(Job).where(Job.id == str(job_id))
            )
            if job is None:
                yield sse_message("error", {"code": "JOB_NOT_FOUND"})
                return
            payload = record(job)
        signature = (
            payload["status"],
            payload.get("started_at"),
            payload.get("finished_at"),
            payload.get("error_code"),
            payload.get("result"),
        )
        if signature != last_signature:
            yield sse_message("job", payload)
            last_signature = signature
        if payload["status"] in TERMINAL_JOB_STATUSES:
            yield sse_message("complete", payload)
            return
        if time.monotonic() - last_heartbeat >= 15:
            yield ": heartbeat\n\n"
            last_heartbeat = time.monotonic()
        await asyncio.sleep(interval_seconds)
    yield sse_message("timeout", {"job_id": str(job_id)})
