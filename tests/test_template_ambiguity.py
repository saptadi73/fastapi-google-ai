from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.dialects import postgresql

from app.core.exceptions import AppError
from app.repositories.semantic_repository import SemanticRepository
from app.schemas.nl2sql import QuestionRequest
from app.services.nl2sql_service import NL2SQLService
from app.services.semantic_catalog_service import SemanticCatalogService


@pytest.mark.asyncio
async def test_matching_templates_scopes_both_product_and_template():
    session = Mock(scalars=AsyncMock(return_value=Mock(all=Mock(return_value=[]))))
    repo = SemanticRepository(session, "00000000-0000-4000-8000-000000000001")
    await repo.matching_templates("sales", SimpleNamespace(role="VIEWER"), "SALES")
    sql = str(session.scalars.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "data_product.tenant_id = platform.validated_query_template.tenant_id" in sql
    assert "validated_query_template.tenant_id =" in sql
    assert "validated_query_template.allowed_roles @>" in sql and "data_product.allowed_roles @>" in sql
    assert "validated_query_template.examples @>" in sql
    assert "validated_query_template.data_product_code =" in sql and "LIMIT" in sql


@pytest.mark.asyncio
async def test_ambiguity_never_calls_ai_or_executes_and_caps_candidates(monkeypatch):
    service = NL2SQLService(Mock(), SimpleNamespace(id="user", tenant_id="tenant", role="VIEWER"))
    service.repo.matching_templates = AsyncMock(return_value=[SimpleNamespace(code=f"t{i}", data_product_code="SALES") for i in range(21)])
    service.repo.add = AsyncMock(return_value=SimpleNamespace(id="clarification"))
    service.executor.execute = AsyncMock()
    ai = AsyncMock()
    monkeypatch.setattr("app.services.nl2sql_service.OpenAIService", lambda: SimpleNamespace(generate=ai))
    result = await service.query(QuestionRequest(question=" Sales?! "))
    assert result["rows"] == [] and result["meta"]["clarification_required"]
    assert len(result["meta"]["template_candidates"]) == 20
    assert result["meta"]["template_candidates_more"] and result["meta"]["openai_called"] is False
    service.executor.execute.assert_not_awaited()
    ai.assert_not_awaited()
    assert service.repo.add.call_args.kwargs["status"] == "CLARIFICATION_REQUIRED"


@pytest.mark.asyncio
async def test_explicit_choice_rechecks_access_version_and_product(monkeypatch):
    service = NL2SQLService(Mock(), SimpleNamespace(id="user", tenant_id="tenant", role="VIEWER"))
    selected = SimpleNamespace(data_product_code="SALES", plan={})
    saved = AsyncMock(return_value=selected)
    monkeypatch.setattr(SemanticCatalogService, "saved", saved)
    service.repo.add = AsyncMock(return_value=SimpleNamespace(id="query"))
    service.executor.execute = AsyncMock(return_value={"rows": [], "meta": {}})
    await service.query(QuestionRequest(question="sales", saved_query_code="chosen", data_product_code="SALES"))
    saved.assert_awaited_with("chosen")
    assert service.executor.execute.call_args.kwargs["ai"] is False
    with pytest.raises(AppError) as failure:
        await service.query(QuestionRequest(question="sales", saved_query_code="chosen", data_product_code="OTHER"))
    assert failure.value.code == "SAVED_QUERY_PRODUCT_MISMATCH"
    saved.side_effect = AppError("TEMPLATE_STALE", "stale", 409)
    with pytest.raises(AppError) as failure:
        await service.query(QuestionRequest(question="sales", saved_query_code="chosen"))
    assert failure.value.code == "TEMPLATE_STALE"
    assert service.executor.execute.await_count == 1


@pytest.mark.asyncio
async def test_single_match_keeps_deterministic_template_route(monkeypatch):
    service = NL2SQLService(Mock(), SimpleNamespace(id="user", tenant_id="tenant", role="VIEWER"))
    service.repo.matching_templates = AsyncMock(return_value=[SimpleNamespace(code="daily")])
    monkeypatch.setattr(SemanticCatalogService, "saved", AsyncMock(return_value=SimpleNamespace(data_product_code="SALES", plan={})))
    service.repo.add = AsyncMock(return_value=SimpleNamespace(id="query"))
    service.executor.execute = AsyncMock(return_value={"rows": [], "meta": {}})
    await service.query(QuestionRequest(question="  Daily Sales?! ", data_product_code="SALES"))
    service.repo.matching_templates.assert_awaited_once_with("daily sales", service.user, "SALES")
    assert service.executor.execute.call_args.kwargs == {"ai": False, "query_source": "INTENT_TEMPLATE"}
