from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.exceptions import AppError
from app.models.source import ProfilingRun
from app.services import source_service


@pytest.mark.asyncio
async def test_profile_captures_actual_file_title_without_renaming_source(monkeypatch):
    source = SimpleNamespace(id="source", spreadsheet_id="google-id", name="Custom registered name")
    sheet = SimpleNamespace(
        id="sheet", enabled=True, is_present=True, sheet_name="REKAP (2026)",
        header_row=1, data_start_row=2, range_a1="A:C",
        last_fingerprint=None, active_configuration_id=None,
    )
    google = Mock(
        metadata=AsyncMock(return_value={"properties": {"title": "Original file & 2026"}}),
        read_sheets=AsyncMock(return_value=[[["Kode"], ["A"]]]),
    )
    service = source_service.SourceService(
        Mock(), SimpleNamespace(tenant_id="tenant", id="editor"), google=google,
    )
    service.repo.get = AsyncMock(return_value=source)
    service.repo.sheets = AsyncMock(return_value=[sheet])
    service.repo.add = AsyncMock(return_value=SimpleNamespace(id="created"))
    monkeypatch.setattr(source_service, "audit", Mock())

    await service.profile(source.id)

    profile_call = next(call for call in service.repo.add.await_args_list if call.args[0] is ProfilingRun)
    profile = profile_call.kwargs["profile_json"]
    assert profile["spreadsheet_title"] == "Original file & 2026"
    assert profile["sheet_name"] == "REKAP (2026)"
    assert source.name == "Custom registered name"
    google.metadata.return_value = {"properties": {"title": "Renamed file"}}
    await service.profile(source.id)
    profiles = [
        call.kwargs["profile_json"] for call in service.repo.add.await_args_list
        if call.args[0] is ProfilingRun
    ]
    assert profiles[-1]["spreadsheet_title"] == "Renamed file"
    assert profiles[-1]["fingerprint"] == profile["fingerprint"]


@pytest.mark.asyncio
async def test_missing_google_title_fails_explicitly_before_profile_writes():
    source = SimpleNamespace(id="source", spreadsheet_id="google-id")
    google = Mock(metadata=AsyncMock(return_value={}), read_sheets=AsyncMock())
    service = source_service.SourceService(
        Mock(), SimpleNamespace(tenant_id="tenant", id="editor"), google=google,
    )
    service.repo.get = AsyncMock(return_value=source)
    service.repo.sheets = AsyncMock(return_value=[SimpleNamespace(enabled=True, is_present=True)])
    service.repo.add = AsyncMock()
    with pytest.raises(AppError) as error:
        await service.profile(source.id)
    assert error.value.code == "SOURCE_METADATA_INVALID"
    service.repo.add.assert_not_awaited()
    google.read_sheets.assert_not_awaited()
