from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.schemas.semantic import ProductUpdate, QueryPlan
from app.services.query_execution_service import build_query
from app.services.semantic_catalog_service import SemanticCatalogService


@pytest.mark.parametrize("metadata", [
    None, [], [{"code": "sales"}],
    [{"code": "sales", "synonyms": [" "]}],
    [{"code": "sales", "synonyms": ["Net sales", " net  SALES "]}],
    [{"code": "sales", "unit": "a" * 41}],
    [{"code": "sales", "synonyms": ["a" * 101]}],
    [{"code": "sales", "column": "secret", "unit": "IDR"}],
    [{"code": "sales", "unit": "IDR"}, {"code": "sales", "unit": None}],
])
def test_metric_metadata_invalid(metadata):
    with pytest.raises(ValidationError):
        ProductUpdate(metric_metadata=metadata, expected_version=1)


def test_metric_metadata_requires_version():
    with pytest.raises(ValidationError):
        ProductUpdate(metric_metadata=[{"code": "sales", "unit": "IDR"}])


@pytest.mark.asyncio
async def test_metric_metadata_preserves_calculation_and_rejects_alias_collision(monkeypatch):
    sales = {"code": "sales", "label": "Sales", "column": "amount", "aggregation": "sum"}
    product = SimpleNamespace(id="product", version=1, name="Before", metrics=[sales,
        {"code": "returns", "label": "Returns", "column": "amount", "aggregation": "count"}])
    service = SemanticCatalogService(Mock(), SimpleNamespace(id="user", tenant_id="tenant"))
    service.repo.get = AsyncMock(return_value=product)
    monkeypatch.setattr("app.services.semantic_catalog_service.record", lambda p, **kwargs: vars(p).copy())
    for code, aliases, expected in [("missing", [], "METRIC_NOT_FOUND"),
                                     ("sales", [" Returns "], "METRIC_SYNONYM_CONFLICT")]:
        with pytest.raises(AppError) as failure:
            await service.update_product("product", ProductUpdate(name="Do not save", expected_version=1,
                metric_metadata=[{"code": code, "synonyms": aliases}]))
        assert failure.value.code == expected
        assert product.version == 1 and product.name == "Before" and product.metrics[0] == sales
    await service.update_product("product", ProductUpdate(expected_version=1,
        metric_metadata=[{"code": "sales", "unit": " IDR ", "synonyms": ["Net   sales"]}]))
    assert product.metrics[0] == {**sales, "unit": "IDR", "synonyms": ["Net sales"]}
    assert product.version == 2
    await service.update_product("product", ProductUpdate(expected_version=2,
        metric_metadata=[{"code": "sales", "unit": None}]))
    assert product.metrics[0]["unit"] is None
    assert product.metrics[0]["synonyms"] == ["Net sales"]
    await service.update_product("product", ProductUpdate(expected_version=3,
        metric_metadata=[{"code": "sales", "synonyms": []}]))
    assert product.metrics[0]["synonyms"] == []


def test_metadata_does_not_change_sql_or_enable_synonym_as_metric(config_data):
    from app.schemas.configuration import ETLConfiguration
    cfg = ETLConfiguration.model_validate(config_data)
    product = SimpleNamespace(code="SALES", view_name="sales",
        columns=[c.model_dump() for c in cfg.columns], dimensions=cfg.semantic.dimensions,
        metrics=[m.model_dump() for m in cfg.semantic.metrics])
    user = SimpleNamespace(tenant_id="00000000-0000-4000-8000-000000000001", role="VIEWER", row_scope={})
    plan = QueryPlan(metrics=[product.metrics[0]["code"]])
    before = str(build_query(product, user, plan))
    product.metrics[0].update(unit="IDR", synonyms=["Revenue"])
    assert str(build_query(product, user, plan)) == before
    with pytest.raises(AppError):
        build_query(product, user, QueryPlan(metrics=["Revenue"]))
