from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.models.semantic import DataProduct
from app.schemas.semantic import ProductUpdate
from app.services.semantic_catalog_service import SemanticCatalogService


@pytest.mark.parametrize("payload", [
    {"name": "New"}, {"name": "  ", "expected_version": 1},
    {"name": None, "expected_version": 1}, {"description": None, "expected_version": 1},
    {"name": "a" * 201, "expected_version": 1},
    {"description": "a" * 4001, "expected_version": 1},
    {"description": "x", "expected_version": 0},
])
def test_metadata_schema_rejects_ambiguous_edits(payload):
    with pytest.raises(ValidationError):
        ProductUpdate.model_validate(payload)


def test_metadata_clear_trim_and_legacy_access():
    assert ProductUpdate(name=" New ", description="", expected_version=1).name == "New"
    assert ProductUpdate(status="SUSPENDED").expected_version is None


@pytest.mark.asyncio
async def test_metadata_lock_conflict_and_version_invalidation(monkeypatch):
    session = Mock()
    user = SimpleNamespace(tenant_id="tenant", id="editor")
    product = SimpleNamespace(id="product", version=3, name="Before", description="Before")
    service = SemanticCatalogService(session, user)
    service.repo.get = AsyncMock(return_value=product)
    monkeypatch.setattr("app.services.semantic_catalog_service.record", lambda p, **kwargs: vars(p).copy())
    with pytest.raises(AppError) as failure:
        await service.update_product("product", ProductUpdate(name="Rejected", expected_version=2))
    assert failure.value.code == "PRODUCT_VERSION_CONFLICT"
    assert product.name == "Before" and product.version == 3
    session.add.assert_not_called()
    result = await service.update_product("product", ProductUpdate(name="After", description="", expected_version=3))
    service.repo.get.assert_awaited_with(DataProduct, "product", lock=True)
    assert result["version"] == 4 and result["description"] == ""
    assert result["name"] == "After" and "expected_version" not in result
    audit = session.add.call_args.args[0]
    assert audit.details == {"changed_fields": ["description", "name"], "semantic_version": 4}


@pytest.mark.asyncio
async def test_existing_template_becomes_stale_after_metadata_edit(monkeypatch):
    session = Mock(scalar=AsyncMock(return_value=SimpleNamespace(
        allowed_roles=["VIEWER"], data_product_code="SALES", semantic_version=3)))
    service = SemanticCatalogService(session, SimpleNamespace(tenant_id="tenant", role="VIEWER"))
    service.repo.product = AsyncMock(return_value=SimpleNamespace(version=4))
    with pytest.raises(AppError) as failure:
        await service.saved("sales")
    assert failure.value.code == "TEMPLATE_STALE"
