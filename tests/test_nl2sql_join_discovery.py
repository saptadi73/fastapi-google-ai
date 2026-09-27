import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.exceptions import AppError
from app.schemas.nl2sql import AIQueryPlan, QuestionRequest
from app.schemas.semantic import QueryPlan
from app.services.nl2sql_service import NL2SQLService
from app.services.semantic_catalog_service import SemanticCatalogService


def product(code):
    return {
        "code": code,
        "name": code.title(),
        "metrics": [{"code": "amount", "column": "amount", "aggregation": "sum"}],
        "dimensions": ["id", "name"],
        "columns": [
            {"target_column": "id", "target_type": "uuid", "pii_classification": "NONE"},
            {"target_column": "product_id", "target_type": "uuid", "pii_classification": "NONE"},
            {"target_column": "category_id", "target_type": "uuid", "pii_classification": "NONE"},
            {"target_column": "name", "target_type": "text", "pii_classification": "NONE"},
        ],
    }


def relationship(code="sales_product", left="SALES", right="PRODUCT"):
    return SimpleNamespace(
        code=code,
        left_product_code=left,
        left_column="product_id",
        right_product_code=right,
        right_column="id",
        cardinality="MANY_TO_ONE",
        join_type="LEFT",
        duplicate_policy="REJECT_AMBIGUOUS",
    )


@pytest.mark.asyncio
async def test_ai_receives_only_reachable_approved_relationships(monkeypatch):
    user = SimpleNamespace(id="user", tenant_id="tenant", role="VIEWER", row_scope={})
    service = NL2SQLService(Mock(), user)
    service.repo.matching_templates = AsyncMock(return_value=[])
    service.repo.approved_join_relationships = AsyncMock(
        return_value=[
            relationship(),
            relationship("product_category", "PRODUCT", "CATEGORY"),
            relationship("other_secret", "OTHER", "SECRET"),
            relationship("stale", "SALES", "STALE"),
        ]
    )
    service.repo.add = AsyncMock(return_value=SimpleNamespace(id="query"))
    service.executor.execute = AsyncMock(return_value={"rows": [], "meta": {}})
    monkeypatch.setattr(
        SemanticCatalogService,
        "products",
        AsyncMock(
            return_value=[
                product("SALES"),
                product("PRODUCT"),
                product("CATEGORY"),
                product("OTHER"),
                product("SECRET"),
                {
                    **product("STALE"),
                    "columns": [
                        {
                            "target_column": "id",
                            "target_type": "uuid",
                            "pii_classification": "HIGH",
                        }
                    ],
                },
            ]
        ),
    )
    contexts = []

    async def generate(_user, _purpose, context, _schema, **kwargs):
        contexts.append(json.loads(context))
        contexts[-1]["policy_data_product_code"] = kwargs.get("data_product_code")
        return (
            AIQueryPlan(
                data_product_code="SALES",
                plan=QueryPlan(
                    join_relationships=["sales_product", "product_category"],
                    dimensions=["CATEGORY.name"],
                ),
                clarification_required=False,
                clarification_question=None,
            ),
            {},
        )

    monkeypatch.setattr(
        "app.services.nl2sql_service.OpenAIService",
        lambda: SimpleNamespace(generate=generate),
    )
    await service.query(QuestionRequest(question="Penjualan berdasarkan kategori", data_product_code="SALES"))

    assert {item["code"] for item in contexts[0]["catalog"]} == {"SALES", "PRODUCT", "CATEGORY"}
    assert [item["code"] for item in contexts[0]["approved_join_relationships"]] == [
        "sales_product",
        "product_category",
    ]
    assert contexts[0]["policy_data_product_code"] == "SALES"
    plan = service.executor.execute.await_args.args[1]
    assert plan.join_relationships == ["sales_product", "product_category"]
    assert service.executor.execute.await_args.kwargs == {"ai": True, "query_source": "OPENAI"}


@pytest.mark.asyncio
async def test_ai_cannot_invent_relationship_or_change_requested_root(monkeypatch):
    user = SimpleNamespace(id="user", tenant_id="tenant", role="VIEWER", row_scope={})
    service = NL2SQLService(Mock(), user)
    service.repo.matching_templates = AsyncMock(return_value=[])
    service.repo.approved_join_relationships = AsyncMock(return_value=[relationship()])
    monkeypatch.setattr(
        SemanticCatalogService,
        "products",
        AsyncMock(return_value=[product("SALES"), product("PRODUCT")]),
    )

    async def generate(_user, _purpose, _context, _schema, **_kwargs):
        return (
            AIQueryPlan(
                data_product_code="PRODUCT",
                plan=QueryPlan(join_relationships=["invented"], dimensions=["name"]),
                clarification_required=False,
                clarification_question=None,
            ),
            {},
        )

    monkeypatch.setattr(
        "app.services.nl2sql_service.OpenAIService",
        lambda: SimpleNamespace(generate=generate),
    )
    with pytest.raises(AppError) as failure:
        await service.query(QuestionRequest(question="Penjualan produk", data_product_code="SALES"))
    assert failure.value.code == "NL2SQL_UNSAFE_QUERY"
