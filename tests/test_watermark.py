from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.exceptions import AppError
from app.models.source import SourceSheet
from app.schemas.source import SheetWatermarkUpdate
from app.services.source_service import SourceService
from app.services.watermark_service import incremental_values


def sheet(**overrides):
    values = {
        "header_row": 1,
        "data_start_row": 2,
        "watermark_source_column": "Sequence",
        "watermark_kind": "INTEGER",
        "watermark_value": "2",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_incremental_values_preserves_source_rows_and_finds_candidate():
    values = [["Sequence", "Name"], [1, "old"], [3, "new"], [2, "same"], [5, "latest"]]

    filtered, candidate, count = incremental_values(values, sheet())

    assert filtered == [["Sequence", "Name"], [], [3, "new"], [], [5, "latest"]]
    assert candidate == "5" and count == 2


def test_incremental_values_rejects_invalid_or_missing_values():
    with pytest.raises(AppError) as invalid:
        incremental_values([["Sequence"], ["wrong"]], sheet(watermark_value=None))
    assert invalid.value.code == "WATERMARK_VALUE_INVALID"
    with pytest.raises(AppError) as missing:
        incremental_values([["Other"], [1]], sheet())
    assert missing.value.code == "WATERMARK_COLUMN_INVALID"


async def test_watermark_configuration_resets_value_and_uses_revision(monkeypatch):
    session = Mock()
    user = SimpleNamespace(tenant_id="tenant", id="editor")
    source_sheet = SimpleNamespace(
        id="sheet",
        watermark_revision=1,
        watermark_source_column=None,
        watermark_kind=None,
        watermark_value="old",
        watermark_updated_at="yesterday",
        active_configuration_id=None,
    )
    profile = SimpleNamespace(profile_json={"columns": [{"source_column": "Sequence"}]})
    service = SourceService(session, user, google=Mock())
    service.repo.get = AsyncMock(return_value=source_sheet)
    service.repo.latest_profile = AsyncMock(return_value=profile)
    monkeypatch.setattr("app.services.source_service.record", lambda value: vars(value).copy())

    result = await service.update_watermark(
        "sheet",
        SheetWatermarkUpdate(revision_no=1, source_column="Sequence", kind="INTEGER"),
    )

    service.repo.get.assert_awaited_once_with(SourceSheet, "sheet", lock=True)
    assert result["watermark_revision"] == 2
    assert result["watermark_value"] is None and result["watermark_updated_at"] is None
    assert session.add.call_args.args[0].event == "sheet.watermark_updated"

    with pytest.raises(AppError) as conflict:
        await service.update_watermark(
            "sheet",
            SheetWatermarkUpdate(revision_no=1, source_column="Sequence", kind="INTEGER"),
        )
    assert conflict.value.code == "WATERMARK_REVISION_CONFLICT"
