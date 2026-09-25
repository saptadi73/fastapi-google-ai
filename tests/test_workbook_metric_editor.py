from types import SimpleNamespace

import pytest

from app.schemas.configuration import ETLConfiguration
from app.services import workbook_service as service


@pytest.fixture
def context(config_data, monkeypatch):
    config = SimpleNamespace(id="config", tenant_id="tenant", revision_no=1,
        based_on_fingerprint="abc", configuration_json=ETLConfiguration(**config_data).model_dump(mode="json"))
    source = SimpleNamespace(source_code="SALES", name="Sales", spreadsheet_id="sheet", owner_user_id="owner")
    sheet = SimpleNamespace(sheet_name="Sales", range_a1="A:CV", enabled=True, header_row=1, data_start_row=2)
    snapshot = SimpleNamespace(content_hash="a" * 64)
    book = service.render(config, source, sheet)
    claims = {**service.identities(config, snapshot), "tabs": book.sheetnames,
              "readonly_hash": service.digest(service.readonly_values(book)), "metric_null_editor": 1,
              "metric_metadata_editor": 1, "metric_default_period_editor": 1,
              "metric_filter_editor": 1}
    book.create_sheet(service.META)["B2"] = service.token(claims, "etl-workbook-export", 5)
    monkeypatch.setattr(service, "load_upload", lambda encoded: book)
    return book, claims, (config, source, sheet, snapshot)


def test_metric_editor_values_and_rejections(context):
    book, _, args = context
    tab = book["11 Metric Definitions"]
    assert tab["M5"].value == "PRESERVE" and not tab["M5"].protection.locked
    for value, expected in [("ZERO_RESULT", "ZERO_RESULT"), ("PRESERVE", "PRESERVE"), (None, "PRESERVE")]:
        tab["M5"] = value
        parsed = service.parse_workbook("fixture", *args)
        assert not parsed["errors"]
        assert parsed["configuration"]["semantic"]["metrics"][0]["null_handling"] == expected
    for value in ["ZERO", "=1+1", "#DIV/0!"]:
        tab["M5"] = value
        assert service.parse_workbook("fixture", *args)["errors"]
    tab["M5"] = "ZERO_RESULT"
    tab["F5"] = "branch_name"
    tab["G5"] = "min"
    assert service.parse_workbook("fixture", *args)["errors"]
    tab["M5"] = "PRESERVE"
    tab["M100"] = "ZERO_RESULT"
    assert service.parse_workbook("fixture", *args)["errors"]  # Orphan cells cannot vanish silently.


def test_legacy_editor_marker_cannot_be_forged(context):
    book, claims, args = context
    args[0].configuration_json["semantic"]["metrics"][0]["null_handling"] = "ZERO_RESULT"
    for row in range(5, 205):
        book["11 Metric Definitions"].cell(row, 13).value = None
    claims.pop("metric_null_editor")
    claims.update(service.identities(args[0], args[3]))
    book[service.META]["B2"] = service.token(claims, "etl-workbook-export", 5)
    parsed = service.parse_workbook("fixture", *args)
    assert not parsed["errors"]
    assert parsed["configuration"]["semantic"]["metrics"][0]["null_handling"] == "ZERO_RESULT"
    book["11 Metric Definitions"]["M5"] = "PRESERVE"
    parsed = service.parse_workbook("fixture", *args)
    assert parsed["errors"] and "terbaru" in str(parsed["errors"])


def test_metric_metadata_round_trip_and_legacy_preservation(context):
    book, claims, args = context
    tab = book["11 Metric Definitions"]
    tab["C5"] = " Total pendapatan bersih "
    tab["D5"] = '["Pendapatan bersih", "Net revenue"]'
    tab["K5"] = " IDR "
    tab["I5"] = "transaction_date"
    tab["J5"] = 30
    tab["H5"] = '[{"field":"branch_name","operator":"eq","value":"Jakarta"}]'
    parsed = service.parse_workbook("fixture", *args)
    metric = parsed["configuration"]["semantic"]["metrics"][0]
    assert metric["description"] == "Total pendapatan bersih"
    assert metric["synonyms"] == ["Pendapatan bersih", "Net revenue"]
    assert metric["unit"] == "IDR"
    assert metric["default_period"] == {"dimension": "transaction_date", "days": 30}
    assert metric["filters"] == [{"field": "branch_name", "operator": "eq", "value": "Jakarta"}]

    args[0].configuration_json["semantic"]["metrics"][0].update(
        description="Deskripsi lama", synonyms=["Alias lama"], unit="KG",
        default_period={"dimension": "transaction_date", "days": 14},
        filters=[{"field": "branch_name", "operator": "eq", "value": "Bandung"}],
    )
    for row in range(5, 205):
        for column in (3, 4, 8, 9, 10, 11):
            tab.cell(row, column).value = None
    claims.pop("metric_metadata_editor")
    claims.pop("metric_default_period_editor")
    claims.pop("metric_filter_editor")
    claims.update(service.identities(args[0], args[3]))
    book[service.META]["B2"] = service.token(claims, "etl-workbook-export", 5)
    parsed = service.parse_workbook("fixture", *args)
    metric = parsed["configuration"]["semantic"]["metrics"][0]
    assert metric["description"] == "Deskripsi lama"
    assert metric["synonyms"] == ["Alias lama"]
    assert metric["unit"] == "KG"
    assert metric["default_period"] == {"dimension": "transaction_date", "days": 14}
    assert metric["filters"] == [{"field": "branch_name", "operator": "eq", "value": "Bandung"}]
    tab["C5"] = "Pemalsuan"
    assert "terbaru" in str(service.parse_workbook("fixture", *args)["errors"])
