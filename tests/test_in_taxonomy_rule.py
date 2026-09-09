from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.schemas.configuration import ETLConfiguration, QualityRule
from app.services.etl_compiler_service import transform_rows


def configuration(data, action="REQUIRE_REVIEW"):
    data["columns"][2].update(taxonomy_id="00000000-0000-0000-0000-000000000001", taxonomy_version=1,
                              taxonomy_required=True)
    data["data_quality_rules"] = [{"column": "branch_name", "rule": "in_taxonomy", "action_on_fail": action}]
    config = ETLConfiguration.model_validate(data)
    column = config.columns[2]
    terms = [SimpleNamespace(code="tea", label="Tea", aliases=["Teh", "shared"], is_active=True),
             SimpleNamespace(code="coffee", label="Coffee", aliases=["shared"], is_active=True)]
    return config, {"branch_name": (column, None, None, terms)}


def test_taxonomy_rule_needs_mapping_and_cannot_be_warning_only(config_data):
    with pytest.raises(ValidationError):
        QualityRule(column="branch_name", rule="in_taxonomy", action_on_fail="WARN")
    with pytest.raises(ValidationError):
        QualityRule(column="branch_name", rule="in_taxonomy", value=["tea"])
    config_data["data_quality_rules"] = [{"column": "branch_name", "rule": "in_taxonomy"}]
    with pytest.raises(ValidationError):
        ETLConfiguration.model_validate(config_data)


@pytest.mark.parametrize("action", ["REJECT_ROW", "REQUIRE_REVIEW", "STOP_BATCH"])
def test_compiler_taxonomy_rule_fails_closed_and_retains_review_output(config_data, sheet_values, action):
    config, context = configuration(config_data, action)
    sheet = SimpleNamespace(header_row=1, data_start_row=2)
    for row, value in zip(sheet_values[1:], [" Teh ", "shared", "missing"]):
        row[2] = value
    with pytest.raises(AppError) as exc:
        transform_rows(sheet_values, sheet, config)
    assert exc.value.code == "TAXONOMY_CONTEXT_REQUIRED"
    if action != "REJECT_ROW":
        with pytest.raises(AppError) as exc:
            transform_rows(sheet_values, sheet, config, taxonomy=context)
        assert exc.value.code == "DQ_" + action
    if action == "STOP_BATCH":
        return
    good, issues, _ = transform_rows(sheet_values, sheet, config, taxonomy=context, review_mode=True)
    assert len(good) == 1 and len(issues) == 2
    assert issues[0]["transformed_data"]["branch_name"] == "shared"
    assert all(issue["errors"][0]["code"] == "IN_TAXONOMY" for issue in issues)


def test_optional_taxonomy_allows_blank_but_not_unknown(config_data, sheet_values):
    config, context = configuration(config_data, "REJECT_ROW")
    config.columns[2].taxonomy_required = False
    for row, value in zip(sheet_values[1:], [None, "", "missing"]):
        row[2] = value
    good, issues, _ = transform_rows(sheet_values, SimpleNamespace(header_row=1, data_start_row=2), config, taxonomy=context)
    assert len(good) == 2 and len(issues) == 1
    assert "transformed_data" not in issues[0]
