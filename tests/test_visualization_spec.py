from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.semantic import QueryPlan
from app.services.query_execution_service import cache_key


def plan(visualization):
    return QueryPlan(
        metrics=["sales", "count"],
        dimensions=["month", "branch"],
        visualization=visualization,
    )


@pytest.mark.parametrize(
    "visualization",
    [
        {"type": "bar", "x_field": "branch", "series": [{"field": "sales"}]},
        {"type": "line", "x_field": "month", "series": [{"field": "sales", "type": "line"}]},
        {"type": "pie", "x_field": "branch", "series": [{"field": "sales"}]},
        {"type": "combo", "x_field": "month", "series": [{"field": "sales"}, {"field": "count", "type": "line", "axis": "right"}]},
        {"type": "scatter", "series": [{"field": "sales"}, {"field": "count"}]},
        {"type": "heatmap", "x_field": "month", "y_field": "branch", "series": [{"field": "sales"}]},
        {"type": "kpi", "series": [{"field": "sales"}]},
        {"type": "table"},
    ],
)
def test_visualization_allowlist_accepts_valid_shapes(visualization):
    assert plan(visualization).visualization.type == visualization["type"]


@pytest.mark.parametrize(
    "visualization",
    [
        {"type": "pie", "x_field": "branch", "series": [{"field": "sales"}, {"field": "count"}]},
        {"type": "line", "x_field": "unknown", "series": [{"field": "sales"}]},
        {"type": "bar", "x_field": "branch", "series": [{"field": "secret"}]},
        {"type": "scatter", "series": [{"field": "sales"}]},
        {"type": "heatmap", "x_field": "branch", "y_field": "branch", "series": [{"field": "sales"}]},
        {"type": "combo", "x_field": "month", "series": [{"field": "sales"}], "options": {"formatter": "evil"}},
    ],
)
def test_visualization_rejects_invalid_or_free_form_configuration(visualization):
    with pytest.raises(ValidationError):
        plan(visualization)


def test_visualization_does_not_fragment_query_result_cache():
    user = SimpleNamespace(tenant_id="tenant", role="VIEWER", row_scope={})
    data_product = SimpleNamespace(code="SALES", version=1, freshness_version=1)
    first = QueryPlan(
        metrics=["net_sales"], dimensions=["branch_name"],
        visualization={"type": "bar", "x_field": "branch_name", "series": [{"field": "net_sales"}]},
    )
    second = QueryPlan(
        metrics=["net_sales"], dimensions=["branch_name"],
        visualization={"type": "pie", "x_field": "branch_name", "series": [{"field": "net_sales"}]},
    )
    assert cache_key(user, data_product, first) == cache_key(user, data_product, second)
