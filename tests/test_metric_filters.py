from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import postgresql

from app.core.exceptions import AppError
from app.schemas.configuration import ETLConfiguration
from app.schemas.semantic import QueryPlan
from app.services.query_execution_service import build_query


def context(filters):
    product = SimpleNamespace(
        code="SALES",
        view_name="sales",
        columns=[
            {"target_column": "amount", "target_type": "numeric"},
            {"target_column": "branch", "target_type": "text"},
        ],
        dimensions=["branch"],
        metrics=[{"code": "result", "column": "amount", "aggregation": "sum", "filters": filters}],
    )
    user = SimpleNamespace(
        tenant_id="00000000-0000-4000-8000-000000000001", role="VIEWER", row_scope={}
    )
    return product, user


def test_metric_filter_schema_validates_field_shape_and_type(config_data):
    metric = config_data["semantic"]["metrics"][0]
    metric["filters"] = [{"field": "branch_name", "operator": "in", "value": ["A", "B"]}]
    assert ETLConfiguration.model_validate(config_data).semantic.metrics[0].filters[0].field == "branch_name"
    metric["filters"] = [{"field": "unknown", "operator": "eq", "value": "A"}]
    with pytest.raises(ValidationError, match="non-sensitive"):
        ETLConfiguration.model_validate(config_data)
    metric["filters"] = [{"field": "net_amount", "operator": "gte", "value": "invalid"}]
    with pytest.raises(ValidationError, match="does not match"):
        ETLConfiguration.model_validate(config_data)


def test_metric_filter_is_inside_aggregate_and_preserves_query_scope():
    product, user = context([{"field": "branch", "operator": "eq", "value": "A"}])
    statement = build_query(product, user, QueryPlan(metrics=["result"]), today=None)
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "sum(semantic.sales.amount) FILTER (WHERE semantic.sales.branch = 'A')" in sql
    assert "_tenant_id" in sql

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("ATTACH DATABASE ':memory:' AS semantic"))
        conn.execute(text("CREATE TABLE semantic.sales (_tenant_id text, amount numeric, branch text)"))
        conn.execute(
            text("INSERT INTO semantic.sales VALUES (:tenant, 10, 'A'), (:tenant, 90, 'B'), ('other', 1000, 'A')"),
            {"tenant": user.tenant_id.replace("-", "")},
        )
        assert conn.execute(statement).scalar() == 10
    engine.dispose()


@pytest.mark.parametrize(
    "filters",
    [
        [{"field": "branch", "operator": "raw_sql", "value": "1=1"}],
        [{"field": "missing", "operator": "eq", "value": "A"}],
        [{"field": "branch", "operator": "between", "value": ["A"]}],
        [{"field": "branch", "operator": "eq", "value": "A", "sql": "DROP TABLE x"}],
    ],
)
def test_invalid_catalog_metric_filter_is_rejected(filters):
    product, user = context(filters)
    with pytest.raises(AppError) as failure:
        build_query(product, user, QueryPlan(metrics=["result"]))
    assert failure.value.code == "SEMANTIC_METRIC_INVALID"
