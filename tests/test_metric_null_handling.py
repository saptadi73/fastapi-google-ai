from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import postgresql

from app.core.exceptions import AppError
from app.schemas.configuration import ETLConfiguration
from app.schemas.semantic import QueryPlan
from app.services.query_execution_service import build_query
from app.services.sql_guard_service import validate_readonly_sql


def context(policy="PRESERVE", aggregation="avg", column_type="numeric"):
    product = SimpleNamespace(code="SALES", view_name="sales",
        columns=[{"target_column": "amount", "target_type": column_type},
                 {"target_column": "branch", "target_type": "text"}],
        dimensions=["branch"], metrics=[{"code": "result", "column": "amount",
            "aggregation": aggregation, "null_handling": policy}])
    user = SimpleNamespace(tenant_id="00000000-0000-4000-8000-000000000001", role="VIEWER",
                           row_scope={"SALES": {"branch": ["A"]}})
    return product, user


def test_schema_defaults_and_rejects_non_numeric_zero(config_data):
    cfg = ETLConfiguration.model_validate(config_data)
    assert cfg.semantic.metrics[0].null_handling == "PRESERVE"
    metric = config_data["semantic"]["metrics"][0]
    metric.update(null_handling="ZERO_RESULT", aggregation="min", column="branch_name")
    with pytest.raises(ValidationError):
        ETLConfiguration.model_validate(config_data)
    metric["aggregation"] = "count"
    assert ETLConfiguration.model_validate(config_data).semantic.metrics[0].null_handling == "ZERO_RESULT"


@pytest.mark.parametrize("policy,aggregation,column_type", [
    ("unknown", "sum", "numeric"), (None, "sum", "numeric"),
    ("ZERO_RESULT", "min", "text"), ("ZERO_RESULT", "max", "date"),
])
def test_invalid_catalog_policy_is_rejected(policy, aggregation, column_type):
    product, user = context(policy, aggregation, column_type)
    with pytest.raises(AppError) as failure:
        build_query(product, user, QueryPlan(metrics=["result"]))
    assert failure.value.code == "SEMANTIC_METRIC_INVALID"


def test_zero_is_applied_after_aggregation_with_tenant_and_row_scope():
    product, user = context("ZERO_RESULT")
    statement = build_query(product, user, QueryPlan(metrics=["result"]))
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "coalesce(avg(semantic.sales.amount), 0)" in sql
    assert "semantic.sales.branch IN ('A')" in sql and "_tenant_id" in sql
    validate_readonly_sql(sql, {"semantic.sales"}, {"amount", "branch", "_tenant_id"})
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("ATTACH DATABASE ':memory:' AS semantic"))
        conn.execute(text("CREATE TABLE semantic.sales (_tenant_id text, amount numeric, branch text)"))
        def result():
            return conn.execute(build_query(product, user, QueryPlan(metrics=["result"]))).scalar()
        assert result() == 0
        assert conn.execute(build_query(product, user, QueryPlan(metrics=["result"], dimensions=["branch"]))).all() == []
        conn.execute(text("INSERT INTO semantic.sales VALUES (:tenant, NULL, 'A'), (:tenant, 10, 'A'), (:tenant, 900, 'B'), ('other', 700, 'A')"),
                     {"tenant": user.tenant_id.replace("-", "")})
        assert result() == 10  # Null inputs are not converted to zero before AVG.
        conn.execute(text("DELETE FROM semantic.sales WHERE amount = 10"))
        assert result() == 0
        product.metrics[0]["null_handling"] = "PRESERVE"
        assert result() is None
        del product.metrics[0]["null_handling"]
        assert result() is None  # Existing catalogs retain SQL's original behavior.
    engine.dispose()
