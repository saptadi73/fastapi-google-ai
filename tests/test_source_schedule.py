from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.models.source import DataSource
from app.schemas.source import SourceCreate, SourceScheduleUpdate, cron_schedule
from app.services.source_service import SourceService, dependency_graph_has_cycle, source_code_base
from app.workers import runner


def test_source_schedule_validates_cron_timezone_and_policy():
    with pytest.raises(ValidationError):
        SourceCreate(source_code="sales", name="Sales", spreadsheet_url="sheet-id")
    payload = SourceScheduleUpdate(
        revision_no=1,
        sync_schedule="0 7 * * 1-5",
        schedule_timezone="Asia/Jakarta",
        concurrency_policy="SKIP_IF_RUNNING",
    )
    assert payload.schedule_timezone == "Asia/Jakarta"
    assert str(cron_schedule(payload.sync_schedule, payload.schedule_timezone))
    with pytest.raises(ValidationError):
        SourceScheduleUpdate(
            revision_no=1,
            sync_schedule="0 7 * * *",
            schedule_timezone="Mars/Olympus",
        )
    with pytest.raises(ValidationError):
        SourceCreate(
            source_code="sales",
            name="Sales",
            spreadsheet_url="sheet-id",
            access_metadata={
                "owner_unit_id": "11111111-1111-4111-8111-111111111111",
                "business_domain_id": "22222222-2222-4222-8222-222222222222",
                "jurisdiction_id": "33333333-3333-4333-8333-333333333333",
                "purpose_id": "44444444-4444-4444-8444-444444444444",
                "data_owner_user_id": "55555555-5555-4555-8555-555555555555",
                "data_steward_user_id": "66666666-6666-4666-8666-666666666666",
                "sensitivity": "LOW",
            },
            concurrency_policy="OVERLAP",
        )


async def test_schedule_update_uses_revision_resets_clock_and_audits(monkeypatch):
    session = Mock()
    user = SimpleNamespace(tenant_id="tenant", id="editor")
    source = SimpleNamespace(
        id="source",
        schedule_revision=2,
        sync_schedule=None,
        schedule_timezone="UTC",
        concurrency_policy="QUEUE_LATEST",
        last_scheduled_at=None,
    )
    service = SourceService(session, user, google=Mock())
    service.repo.get = AsyncMock(return_value=source)
    session.execute = AsyncMock(
        side_effect=[None, SimpleNamespace(all=lambda: []), None]
    )
    monkeypatch.setattr("app.services.source_service.record", lambda value: vars(value).copy())
    payload = SourceScheduleUpdate(
        revision_no=2,
        sync_schedule="0 6 * * *",
        schedule_timezone="Asia/Bangkok",
        concurrency_policy="SKIP_IF_RUNNING",
    )

    result = await service.update_schedule("source", payload)

    service.repo.get.assert_awaited_once_with(DataSource, "source", lock=True)
    assert result["schedule_revision"] == 3
    assert result["schedule_timezone"] == "Asia/Bangkok"
    assert result["last_scheduled_at"] is not None
    event = session.add.call_args.args[0]
    assert event.event == "source.schedule_updated"
    assert event.details["concurrency_policy"] == "SKIP_IF_RUNNING"

    with pytest.raises(AppError) as error:
        await service.update_schedule("source", payload)
    assert error.value.code == "SOURCE_SCHEDULE_CONFLICT"


def test_dependency_graph_rejects_cycles():
    assert dependency_graph_has_cycle([("b", "a"), ("c", "b")]) is False
    assert dependency_graph_has_cycle([("b", "a"), ("a", "b")]) is True


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Laporan Penjualan Harian", "laporan_penjualan_harian"),
        ("Data Produksi 2026", "data_produksi_2026"),
        ("123", "source_123"),
        ("---", "source"),
    ],
)
def test_source_code_base_is_human_readable(name, expected):
    assert source_code_base(name) == expected


@pytest.mark.parametrize(
    ("downstream_finished", "upstream_finished", "ready"),
    [
        (None, datetime(2026, 9, 27, tzinfo=timezone.utc), True),
        (
            datetime(2026, 9, 27, tzinfo=timezone.utc),
            datetime(2026, 9, 28, tzinfo=timezone.utc),
            True,
        ),
        (
            datetime(2026, 9, 28, tzinfo=timezone.utc),
            datetime(2026, 9, 27, tzinfo=timezone.utc),
            False,
        ),
        (None, None, False),
    ],
)
async def test_dependency_requires_newer_success(
    downstream_finished, upstream_finished, ready
):
    source = SimpleNamespace(id="downstream", tenant_id="tenant")
    rows = []
    if downstream_finished:
        rows.append(("downstream", downstream_finished))
    if upstream_finished:
        rows.append(("upstream", upstream_finished))

    class Session:
        async def scalars(self, *_args, **_kwargs):
            return ["upstream"]

        async def execute(self, *_args, **_kwargs):
            return rows

    assert await runner.dependencies_ready(Session(), source) is ready


@pytest.mark.parametrize(
    ("policy", "advances_clock"),
    [("SKIP_IF_RUNNING", True), ("QUEUE_LATEST", False)],
)
async def test_scheduler_applies_pending_job_concurrency_policy(
    monkeypatch, policy, advances_clock
):
    previous = datetime.now(timezone.utc) - timedelta(days=1)
    source = SimpleNamespace(
        id="source",
        tenant_id="tenant",
        owner_user_id="owner",
        sync_schedule="* * * * *",
        schedule_timezone="UTC",
        concurrency_policy=policy,
        last_scheduled_at=previous,
        created_at=previous,
    )

    class Session:
        def __init__(self):
            self.scalar_calls = 0
            self.scalars_calls = 0
            self.add = Mock()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def begin(self):
            return self

        async def scalar(self, *_args, **_kwargs):
            self.scalar_calls += 1
            return True if self.scalar_calls == 1 else "pending-job"

        async def scalars(self, *_args, **_kwargs):
            self.scalars_calls += 1
            if self.scalars_calls == 1:
                return []
            if self.scalars_calls == 2:
                return [source]
            return []

    session = Session()
    monkeypatch.setattr(runner, "SessionFactory", lambda: session)

    await runner.schedule_sources()

    assert (source.last_scheduled_at != previous) is advances_clock
    session.add.assert_not_called()
