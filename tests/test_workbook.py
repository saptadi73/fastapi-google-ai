import base64
import io
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from app.core.exceptions import AppError
from app.schemas.configuration import ETLConfiguration
from app.services.workbook_service import REVIEW, export_workbook, parse_workbook


@pytest.fixture
def workbook_context(config_data):
    config = SimpleNamespace(
        id="config",
        tenant_id="tenant",
        revision_no=1,
        based_on_fingerprint="abc",
        configuration_json=ETLConfiguration(**config_data).model_dump(mode="json"),
    )
    source = SimpleNamespace(source_code="SALES", name="Sales", spreadsheet_id="sheet", owner_user_id="owner")
    sheet = SimpleNamespace(sheet_name="Sales", range_a1="A:CV", enabled=True, header_row=1, data_start_row=2)
    snapshot = SimpleNamespace(content_hash="a" * 64)
    return config, source, sheet, snapshot


def encode(raw):
    return base64.b64encode(raw).decode()


def edited(ctx, tab, cell, value):
    book = load_workbook(io.BytesIO(export_workbook(*ctx)))
    book[tab][cell] = value
    stream = io.BytesIO()
    book.save(stream)
    return encode(stream.getvalue())


def test_roundtrip_preserves_configuration_and_all_tabs(workbook_context):
    raw = export_workbook(*workbook_context)
    assert len(load_workbook(io.BytesIO(raw)).sheetnames) == 16
    result = parse_workbook(encode(raw), *workbook_context)
    assert result["errors"] == []
    assert result["configuration"] == workbook_context[0].configuration_json


def test_edit_identity_and_reject_unsupported_or_formula(workbook_context):
    result = parse_workbook(edited(workbook_context, REVIEW, "B2", "Penjualan baru"), *workbook_context)
    assert result["errors"] == []
    assert result["configuration"]["dataset_business_name"] == "Penjualan baru"
    for tab, cell, value in [
        ("04 Taxonomy Mapping", "C5", "NEW"),
        (REVIEW, "B2", "=1+1"),
        ("02 Struktur Kolom", "D50", "extra column"),
    ]:
        assert parse_workbook(edited(workbook_context, tab, cell, value), *workbook_context)["errors"]


def test_stale_and_invalid_upload(workbook_context):
    raw = encode(export_workbook(*workbook_context))
    workbook_context[0].revision_no += 1
    with pytest.raises(AppError, match="revision"):
        parse_workbook(raw, *workbook_context)
    with pytest.raises(AppError):
        parse_workbook("not base64", *workbook_context)


def test_question_cannot_be_closed_without_answer(workbook_context):
    workbook_context[0].configuration_json["unresolved_questions"] = ["Apakah ID unik?"]
    assert parse_workbook(edited(workbook_context, REVIEW, "C10", "Selesai"), *workbook_context)["errors"]
