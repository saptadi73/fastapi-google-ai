from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.retired_table_service import collect_retired_tables


def _row(config_id, status, version, table_name, *, sheet_id="sheet-1", source_id="source-1"):
    config = SimpleNamespace(
        id=config_id,
        status=status,
        version_no=version,
        configuration_json={"target_table": table_name},
        created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    sheet = SimpleNamespace(id=sheet_id, sheet_name="Products")
    source = SimpleNamespace(id=source_id, source_code="products", name="Products source")
    return config, sheet, source


def test_groups_old_physical_tables_and_keeps_active_table_out():
    rows = [
        _row("cfg-v1", "SUPERSEDED", 1, "products_v1"),
        _row("cfg-v2", "SUPERSEDED", 2, "products_v1"),
        _row("cfg-active", "ACTIVE", 3, "products_v2"),
    ]

    candidates = collect_retired_tables(rows)

    assert len(candidates) == 1
    assert candidates[0]["qualified_name"].startswith("trusted.products_v1_")
    assert [item["version_no"] for item in candidates[0]["superseded_configurations"]] == [1, 2]
    assert candidates[0]["current_configuration"]["version_no"] == 3
    assert candidates[0]["cleanup_candidate"] is True
    assert candidates[0]["delete_ready"] is False


def test_does_not_list_historical_config_when_it_shares_active_table():
    rows = [
        _row("cfg-old", "SUPERSEDED", 1, "same_table"),
        _row("cfg-active", "ACTIVE", 2, "same_table"),
    ]

    assert collect_retired_tables(rows) == []


def test_tables_from_distinct_sheets_are_not_collapsed():
    rows = [
        _row("cfg-old-1", "SUPERSEDED", 1, "products", sheet_id="sheet-1"),
        _row("cfg-old-2", "SUPERSEDED", 1, "products", sheet_id="sheet-2"),
    ]

    candidates = collect_retired_tables(rows)

    assert len(candidates) == 2
    assert candidates[0]["table_name"] != candidates[1]["table_name"]
