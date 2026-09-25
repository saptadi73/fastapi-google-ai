from datetime import date
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppError
from app.schemas.configuration import ETLConfiguration
from app.schemas.semantic import QueryFilter, QueryPlan
from app.services.query_execution_service import build_query, resolve_default_period


def product(config_data):
    config = ETLConfiguration.model_validate(config_data)
    return SimpleNamespace(
        code="SALES",
        view_name="sales_view",
        columns=[column.model_dump(mode="json") for column in config.columns],
        dimensions=config.semantic.dimensions,
        metrics=[metric.model_dump(mode="json") for metric in config.semantic.metrics],
        version=1,
        freshness_version=1,
    )


def user():
    return SimpleNamespace(tenant_id="00000000-0000-0000-0000-000000000001", role="VIEWER", row_scope={})


def test_default_period_schema_requires_temporal_semantic_dimension(config_data):
    config_data["semantic"]["metrics"][0]["default_period"] = {
        "dimension": "transaction_date",
        "days": 30,
    }
    metric = ETLConfiguration.model_validate(config_data).semantic.metrics[0]
    assert metric.default_period.days == 30
    config_data["semantic"]["metrics"][0]["default_period"]["dimension"] = "branch_name"
    with pytest.raises(ValueError, match="temporal semantic dimension"):
        ETLConfiguration.model_validate(config_data)


def test_default_period_compiles_utc_date_range_and_explicit_filter_overrides(config_data):
    config_data["semantic"]["metrics"][0]["default_period"] = {
        "dimension": "transaction_date",
        "days": 30,
    }
    catalog = product(config_data)
    plan = QueryPlan(metrics=["net_sales"])
    period = resolve_default_period(catalog, plan, date(2026, 9, 25))
    assert period == {
        "dimension": "transaction_date",
        "days": 30,
        "start": "2026-08-27",
        "end": "2026-09-25",
    }
    sql = str(build_query(catalog, user(), plan, today=date(2026, 9, 25)).compile(compile_kwargs={"literal_binds": True}))
    assert "2026-08-27" in sql and "2026-09-25" in sql

    explicit = QueryPlan(
        metrics=["net_sales"],
        filters=[QueryFilter(field="transaction_date", operator="gte", value="2026-01-01")],
    )
    assert resolve_default_period(catalog, explicit, date(2026, 9, 25)) is None
    explicit_sql = str(build_query(catalog, user(), explicit, today=date(2026, 9, 25)).compile(compile_kwargs={"literal_binds": True}))
    assert "2026-08-27" not in explicit_sql


def test_conflicting_metric_defaults_require_explicit_filter(config_data):
    config_data["semantic"]["metrics"][0]["default_period"] = {
        "dimension": "transaction_date",
        "days": 30,
    }
    config_data["semantic"]["metrics"][1]["default_period"] = {
        "dimension": "transaction_date",
        "days": 7,
    }
    catalog = product(config_data)
    with pytest.raises(AppError) as exc:
        resolve_default_period(
            catalog,
            QueryPlan(metrics=["net_sales", "transaction_count"]),
            date(2026, 9, 25),
        )
    assert exc.value.code == "QUERY_DEFAULT_PERIOD_CONFLICT"
