import base64
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.schemas.configuration import ETLConfiguration
from app.services.etl_compiler_service import transform_rows
from app.services.workbook_service import export_workbook, parse_workbook


def run(config_data, sheet_values, rules, **kwargs):
    config_data["data_quality_rules"] = rules
    return transform_rows(sheet_values, SimpleNamespace(header_row=1, data_start_row=2),
                          ETLConfiguration.model_validate(config_data), **kwargs)


def test_thresholds_are_per_rule_and_boundary_is_inclusive(config_data, sheet_values):
    rules = [
        {"column": "net_amount", "rule": "min", "value": 100, "action_on_fail": "WARN", "threshold_percent": 34},
        {"column": "net_amount", "rule": "max", "value": 200, "threshold_percent": 0},
    ]
    good, issues, warnings = run(config_data, sheet_values, rules)
    assert len(good) == 3 and not issues and len(warnings) == 1
    rules[0]["threshold_percent"] = 33
    with pytest.raises(AppError) as exc:
        run(config_data, sheet_values, rules)
    assert exc.value.code == "DQ_THRESHOLD_EXCEEDED"
    rules[0]["threshold_percent"] = 100 / 3
    run(config_data, sheet_values, rules)


def test_default_is_cast_before_required_check_and_invalid_default_rejected(config_data, sheet_values):
    config_data["columns"][3]["nullable"] = False
    sheet_values[1][3] = ""
    rules = [{"column": "net_amount", "rule": "min", "value": 0, "default_value": "12.50"}]
    good, issues, _ = run(config_data, sheet_values, rules)
    assert not issues and good[0][1]["net_amount"] == Decimal("12.50")
    rules[0]["default_value"] = "invalid"
    _, issues, _ = run(config_data, sheet_values, rules)
    assert issues[0]["errors"][0]["code"] == "TYPE_OR_NULL_ERROR"


def test_temporal_boundary_and_metadata(config_data, sheet_values):
    rules = [{"column": "transaction_date", "rule": "max_age_days", "max_age_days": 2,
              "action_on_fail": "WARN", "severity": "INFO", "owner": "data-team"}]
    _, issues, warnings = run(config_data, sheet_values, rules, reference_time=datetime(2026, 9, 4, tzinfo=UTC))
    assert not issues
    assert warnings == [{"source_row": 2, "column": "transaction_date", "code": "MAX_AGE_DAYS",
                         "rule_index": 0, "severity": "INFO", "owner": "data-team"}]


@pytest.mark.parametrize("name,valid,invalid", [
    ("UUID", "12345678-1234-1234-1234-123456789abc", "123"),
    ("ISO_DATE", "2024-02-29", "2025-02-29"),
    ("ISO_DATETIME", "2026-09-01T01:00:00+07:00", "2026-09-01"),
])
def test_format_allowlist(config_data, sheet_values, name, valid, invalid):
    sheet_values[1][2], sheet_values[2][2], sheet_values[3][2] = valid, invalid, None
    good, issues, _ = run(config_data, sheet_values, [{"column": "branch_name", "rule": "format", "value": name}])
    assert len(good) == 2 and [x["source_row"] for x in issues] == [3]


@pytest.mark.parametrize("rule", [
    {"column": "branch_name", "rule": "format", "value": ".*"},
    {"column": "branch_name", "rule": "max_age_days", "max_age_days": 1},
    {"column": "transaction_date", "rule": "max_age_days"},
    {"column": "transaction_date", "rule": "not_null", "max_age_days": 1},
])
def test_invalid_rule_contract(config_data, rule):
    config_data["data_quality_rules"] = [rule]
    with pytest.raises(ValidationError):
        ETLConfiguration.model_validate(config_data)


def test_dq_workbook_roundtrip(config_data):
    config_data["data_quality_rules"] = [
        {"column": "transaction_date", "rule": "max_age_days", "max_age_days": 0,
         "threshold_percent": 0, "severity": "WARN", "owner": "team", "default_value": "2026-09-01"},
        {"column": "net_amount", "rule": "min", "value": 0, "default_value": 0},
        {"column": "branch_name", "rule": "allowed_values", "value": ["Jakarta"], "action_on_fail": "WARN"},
    ]
    config = SimpleNamespace(id="config", tenant_id="tenant", revision_no=1, based_on_fingerprint="abc",
                             configuration_json=ETLConfiguration.model_validate(config_data).model_dump(mode="json"))
    source = SimpleNamespace(source_code="SALES", name="Sales", spreadsheet_id="sheet", owner_user_id="owner")
    sheet = SimpleNamespace(sheet_name="Sales", range_a1="A:CV", enabled=True, header_row=1, data_start_row=2)
    ctx = (config, source, sheet, SimpleNamespace(content_hash="a" * 64))
    result = parse_workbook(base64.b64encode(export_workbook(*ctx)).decode(), *ctx)
    assert result["errors"] == []
    assert result["configuration"] == config.configuration_json


@pytest.mark.parametrize("kind,values", [
    ("timestamp", ["2026-09-02T00:00:00", "2026-09-01T23:59:59"]),
    ("timestamptz", ["2026-09-02T07:00:00+07:00", "2026-09-02T06:59:59+07:00"]),
])
def test_age_timestamp_offset_and_exact_boundary(config_data, sheet_values, kind, values):
    config_data["columns"][1].update(target_type=kind, transformation_codes=[])
    sheet_values[1][1], sheet_values[2][1], sheet_values[3][1] = *values, None
    good, issues, _ = run(config_data, sheet_values,
                         [{"column": "transaction_date", "rule": "max_age_days", "max_age_days": 2}],
                         reference_time=datetime(2026, 9, 4, tzinfo=UTC))
    assert len(good) == 2 and [i["source_row"] for i in issues] == [3]


def test_defaults_conflict_is_rejected(config_data):
    config_data["data_quality_rules"] = [
        {"column": "net_amount", "rule": "min", "value": 0, "default_value": 1},
        {"column": "net_amount", "rule": "max", "value": 100, "default_value": 2},
    ]
    with pytest.raises(ValidationError, match="Conflicting default"):
        ETLConfiguration.model_validate(config_data)


def test_domain_and_empty_population(config_data, sheet_values):
    rules = [{"column": "branch_name", "rule": "allowed_values", "value": ["Jakarta"],
              "threshold_percent": 100}]
    good, issues, _ = run(config_data, sheet_values, rules)
    assert len(good) == 2 and [i["source_row"] for i in issues] == [3]
    rules[0]["threshold_percent"] = 0
    assert run(config_data, sheet_values[:1], rules) == ([], [], [])
