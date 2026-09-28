from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.core.exceptions import AppError
from app.repositories.semantic_repository import SemanticRepository
from app.schemas.configuration import ETLConfiguration
from app.schemas.semantic import QueryFilter, QueryPlan
from app.services.query_execution_service import build_query, cache_key
from app.services.sql_guard_service import validate_readonly_sql


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM semantic.sales",
        "SELECT branch_name FROM semantic.sales; DROP TABLE platform.app_user",
        "SELECT * FROM semantic.sales LIMIT 1",
        "SELECT pg_sleep(100) FROM semantic.sales LIMIT 1",
        "SELECT branch_name INTO temp_copy FROM semantic.sales LIMIT 1",
        "SELECT branch_name FROM platform.app_user LIMIT 1",
        "SELECT branch_name FROM semantic.sales LIMIT 1 FOR UPDATE",
        "WITH x AS (DELETE FROM semantic.sales RETURNING branch_name) SELECT branch_name FROM x LIMIT 1",
        "SELECT branch_name FROM semantic.sales -- bypass\n LIMIT 1",
        "SELECT secret FROM semantic.sales LIMIT 1",
        "SELECT branch_name FROM semantic.sales",
        "SELECT (SELECT password_hash FROM platform.app_user LIMIT 1) FROM semantic.sales LIMIT 1",
    ],
)
def test_sql_guard_rejects(sql):
    with pytest.raises(AppError):
        validate_readonly_sql(sql, {"semantic.sales"}, {"branch_name"})


def test_query_scope_and_bind_values(config_data):
    cfg = ETLConfiguration.model_validate(config_data)
    product = SimpleNamespace(
        code="SALES",
        view_name="sales",
        columns=[c.model_dump() for c in cfg.columns],
        metrics=[m.model_dump() for m in cfg.semantic.metrics],
        dimensions=cfg.semantic.dimensions,
        version=1,
        freshness_version=1,
    )
    user = SimpleNamespace(
        tenant_id=str(uuid4()), role="VIEWER", row_scope={"SALES": {"branch_name": ["Jakarta"]}}
    )
    plan = QueryPlan(
        metrics=["net_sales"],
        dimensions=["branch_name"],
        filters=[QueryFilter(field="branch_name", operator="eq", value="' OR 1=1 --")],
    )
    stmt = build_query(product, user, plan)
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    validate_readonly_sql(sql, {"semantic.sales"}, {"_tenant_id", *(c.target_column for c in cfg.columns)})
    assert "Jakarta" in sql and user.tenant_id.replace("-", "") in sql
    key = cache_key(user, product, plan)
    user.row_scope = {"SALES": {"branch_name": ["Bandung"]}}
    assert cache_key(user, product, plan) != key
    user.token_version = 2
    assert cache_key(user, product, plan) != key
    assert cache_key(user, product, plan, authorization_revisions=[("policy-a", 1)]) != key


def test_monthly_query_allowed(config_data):
    cfg = ETLConfiguration.model_validate(config_data)
    product = SimpleNamespace(
        code="SALES",
        view_name="sales",
        columns=[c.model_dump() for c in cfg.columns],
        metrics=[m.model_dump() for m in cfg.semantic.metrics],
        dimensions=cfg.semantic.dimensions,
    )
    user = SimpleNamespace(tenant_id=str(uuid4()), role="VIEWER", row_scope={})
    stmt = build_query(
        product, user, QueryPlan(metrics=["net_sales"], dimensions=["transaction_date"], time_grain="month")
    )
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    validate_readonly_sql(sql, {"semantic.sales"}, {"_tenant_id", *(c.target_column for c in cfg.columns)})


def test_be16_row_scope_and_masked_column_are_enforced_by_compiler(config_data):
    cfg = ETLConfiguration.model_validate(config_data)
    product = SimpleNamespace(
        code="SALES",
        view_name="sales",
        columns=[c.model_dump() for c in cfg.columns],
        metrics=[m.model_dump() for m in cfg.semantic.metrics],
        dimensions=cfg.semantic.dimensions,
        version=1,
        freshness_version=1,
    )
    user = SimpleNamespace(tenant_id=str(uuid4()), role="VIEWER", row_scope={})
    decision = {
        "row_scope": {"branch_name": ["Jakarta"]},
        "columns": {"branch_name": "MASKED"},
    }
    stmt = build_query(
        product,
        user,
        QueryPlan(dimensions=["branch_name"]),
        access_decision=decision,
    )
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "[MASKED]" in sql and "Jakarta" in sql
    with pytest.raises(AppError) as error:
        build_query(
            product,
            user,
            QueryPlan(
                dimensions=["branch_name"],
                filters=[QueryFilter(field="branch_name", operator="eq", value="Jakarta")],
            ),
            access_decision=decision,
        )
    assert error.value.code == "QUERY_FIELD_FORBIDDEN"


def test_be16_sensitive_column_defaults_hidden(config_data):
    cfg = ETLConfiguration.model_validate(config_data)
    columns = [c.model_dump() for c in cfg.columns]
    columns[0]["pii_classification"] = "HIGH"
    field = columns[0]["target_column"]
    product = SimpleNamespace(
        code="SALES",
        view_name="sales",
        columns=columns,
        metrics=[m.model_dump() for m in cfg.semantic.metrics],
        dimensions=[field],
        version=1,
        freshness_version=1,
    )
    user = SimpleNamespace(tenant_id=str(uuid4()), role="VIEWER", row_scope={})
    with pytest.raises(AppError) as error:
        build_query(product, user, QueryPlan(dimensions=[field]), access_decision={"columns": {}})
    assert error.value.code == "QUERY_FIELD_FORBIDDEN"


def test_be16_catalog_hides_columns_and_metrics_without_access():
    product = SimpleNamespace(
        code="SALES",
        columns=[
            {"target_column": "public_field", "pii_classification": "NONE"},
            {"target_column": "secret_field", "pii_classification": "HIGH"},
            {"target_column": "masked_field", "pii_classification": "LOW"},
        ],
        dimensions=["public_field", "secret_field", "masked_field"],
        metrics=[
            {"code": "public_metric", "column": "public_field"},
            {"code": "secret_metric", "column": "secret_field"},
        ],
    )
    view = SemanticRepository._sanitize_product(
        product,
        {"columns": {"masked_field": "MASKED"}},
    )
    assert [item["target_column"] for item in view["columns"]] == ["public_field", "masked_field"]
    assert view["columns"][1]["access_visibility"] == "MASKED"
    assert view["dimensions"] == ["public_field", "masked_field"]
    assert [item["code"] for item in view["metrics"]] == ["public_metric"]
