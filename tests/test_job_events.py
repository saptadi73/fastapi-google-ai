import json
from datetime import datetime, timezone
from types import SimpleNamespace

from app.models.etl import Job
from app.services import job_event_service


def completed_job():
    return Job(
        id="33333333-3333-4333-8333-333333333333",
        tenant_id="11111111-1111-4111-8111-111111111111",
        created_at=datetime(2026, 10, 4, tzinfo=timezone.utc),
        kind="ETL",
        source_id=None,
        requested_by="22222222-2222-4222-8222-222222222222",
        payload={},
        status="SUCCEEDED",
        result={"runs": []},
        error_code=None,
        error_message=None,
        started_at=datetime(2026, 10, 4, tzinfo=timezone.utc),
        finished_at=datetime(2026, 10, 4, 0, 0, 1, tzinfo=timezone.utc),
    )


async def test_job_event_stream_emits_snapshot_and_terminal_event(monkeypatch):
    class FakeSession:
        async def scalar(self, query):
            return completed_job()

    class FakeContext:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, exc_type, exc, traceback):
            pass

    monkeypatch.setattr(job_event_service, "SessionFactory", lambda: FakeContext())
    request = SimpleNamespace(is_disconnected=lambda: disconnected())

    events = [
        item
        async for item in job_event_service.job_event_stream(
            request,
            tenant_id="11111111-1111-4111-8111-111111111111",
            job_id="33333333-3333-4333-8333-333333333333",
        )
    ]

    assert [item.splitlines()[0] for item in events] == ["event: job", "event: complete"]
    payload = json.loads(events[-1].split("data: ", 1)[1])
    assert payload["status"] == "SUCCEEDED"


async def disconnected():
    return False
