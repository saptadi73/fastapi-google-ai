from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.schemas.semantic import ProductUpdate
from app.services.semantic_catalog_service import SemanticCatalogService


@pytest.fixture(autouse=True)
def owner_workflow_off(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "etl_owner_workflow_enabled", False)


def catalog_product():
    return SimpleNamespace(
        id="product-id",
        tenant_id="tenant-id",
        source_sheet_id="sheet-id",
        version=1,
        name="Weekly Sales",
        description="",
        columns=[
            {"target_column": "unit_bisnis", "source_column": "Unit Bisnis", "target_type": "text", "business_name": "", "pii_classification": "LOW"},
            {"target_column": "realisasi", "source_column": "Realisasi", "target_type": "numeric", "business_name": "", "pii_classification": "LOW"},
            {"target_column": "start_date", "source_column": "Start Date", "target_type": "date", "business_name": "", "pii_classification": "LOW"},
            {"target_column": "email", "source_column": "Email", "target_type": "text", "business_name": "", "pii_classification": "HIGH"},
        ],
        dimensions=["unit_bisnis", "start_date"],
        metrics=[],
    )


@pytest.mark.parametrize("payload", [
    {"dimensions": ["unit_bisnis" ]},
    {"metric_definitions": []},
    {"column_metadata": [{"target_column": "unit_bisnis", "description": "Unit bisnis"}]},
])
def test_catalog_semantic_edits_require_expected_version(payload):
    with pytest.raises(ValidationError):
        ProductUpdate.model_validate(payload)


@pytest.mark.asyncio
async def test_catalog_semantic_metadata_edit_updates_without_etl_fields(monkeypatch):
    product = catalog_product()
    session = Mock()
    service = SemanticCatalogService(session, SimpleNamespace(tenant_id="tenant-id", id="editor", role="DATA_STEWARD"))
    service.repo.get = AsyncMock(return_value=product)
    monkeypatch.setattr("app.services.semantic_catalog_service.record", lambda item, **kwargs: vars(item).copy())

    result = await service.update_product("product-id", ProductUpdate(
        expected_version=1,
        description="Target dan realisasi penjualan per unit bisnis dan tanggal.",
        dimensions=["unit_bisnis", "start_date"],
        column_metadata=[
            {"target_column": "unit_bisnis", "business_name": "Unit bisnis", "description": "Unit yang melaporkan kinerja.", "synonyms": ["cabang", "unit"]},
            {"target_column": "realisasi", "business_name": "Realisasi", "description": "Nilai realisasi dalam rupiah."},
        ],
        metric_definitions=[{
            "code": "total_realisasi", "column": "realisasi", "aggregation": "sum",
            "label": "Total realisasi", "description": "Jumlah nilai realisasi.",
            "unit": "IDR", "synonyms": ["total penjualan", "nilai aktual"],
        }],
    ))

    assert product.version == 2
    assert product.columns[0]["business_name"] == "Unit bisnis"
    assert product.columns[0]["synonyms"] == ["cabang", "unit"]
    assert product.dimensions == ["unit_bisnis", "start_date"]
    assert product.metrics[0]["code"] == "total_realisasi"
    assert product.metrics[0]["aggregation"] == "sum"
    assert result["version"] == 2
    assert "configuration_json" not in result
    audit = session.add.call_args.args[0]
    assert audit.event == "data_product.updated"
    assert "metrics" in audit.details["changed_fields"]
    assert audit.details["semantic_version"] == 2


@pytest.mark.asyncio
async def test_catalog_semantic_edit_rejects_unknown_sensitive_and_invalid_aggregate_columns(monkeypatch):
    product = catalog_product()
    service = SemanticCatalogService(Mock(), SimpleNamespace(tenant_id="tenant-id", id="editor", role="DATA_STEWARD"))
    service.repo.get = AsyncMock(return_value=product)
    monkeypatch.setattr("app.services.semantic_catalog_service.record", lambda item, **kwargs: vars(item).copy())

    cases = [
        (ProductUpdate(expected_version=1, dimensions=["not_a_column"]), "PRODUCT_DIMENSION_INVALID"),
        (ProductUpdate(expected_version=1, column_metadata=[{"target_column": "email", "description": "PII"}]), "PRODUCT_COLUMN_FORBIDDEN"),
        (ProductUpdate(expected_version=1, metric_definitions=[{"code": "sum_unit", "column": "unit_bisnis", "aggregation": "sum"}]), "PRODUCT_METRIC_TYPE_INVALID"),
        (ProductUpdate(expected_version=1, metric_definitions=[{"code": "count_email", "column": "email", "aggregation": "count"}]), "PRODUCT_METRIC_COLUMN_INVALID"),
    ]
    for payload, error_code in cases:
        with pytest.raises(AppError) as failure:
            await service.update_product("product-id", payload)
        assert failure.value.code == error_code
        assert product.version == 1
        assert product.metrics == []


@pytest.mark.asyncio
async def test_catalog_semantic_edit_preserves_advanced_existing_metric_settings(monkeypatch):
    product = catalog_product()
    product.metrics = [{
        "code": "sum_realisasi", "column": "realisasi", "aggregation": "sum",
        "label": "Realisasi", "description": "Jumlah", "synonyms": [], "unit": "IDR",
        "null_handling": "ZERO_RESULT", "filters": [],
        "default_period": {"dimension": "start_date", "days": 30},
    }]
    service = SemanticCatalogService(Mock(), SimpleNamespace(tenant_id="tenant-id", id="editor", role="DATA_STEWARD"))
    service.repo.get = AsyncMock(return_value=product)
    monkeypatch.setattr("app.services.semantic_catalog_service.record", lambda item, **kwargs: vars(item).copy())

    await service.update_product("product-id", ProductUpdate(
        expected_version=1,
        metric_definitions=[{"code": "sum_realisasi", "column": "realisasi", "aggregation": "sum", "label": "Nilai realisasi"}],
    ))

    assert product.metrics[0]["null_handling"] == "ZERO_RESULT"
    assert product.metrics[0]["unit"] == "IDR"
    assert product.metrics[0]["default_period"] == {"dimension": "start_date", "days": 30}
