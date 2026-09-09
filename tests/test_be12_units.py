from decimal import Decimal, localcontext
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.schemas.configuration import ETLConfiguration, UnitConversion
from app.services.etl_compiler_service import transform_rows
from app.services.schema_compiler_service import mapped_type


def conversion(**overrides):
    return {"from_unit": "KG", "to_unit": "G", "factor": "1000", "output_scale": 2,
            "rounding": "HALF_UP", **overrides}


def execute(config_data, sheet_values):
    return transform_rows(sheet_values, SimpleNamespace(header_row=1, data_start_row=2),
                          ETLConfiguration.model_validate(config_data))


def test_conversion_precedes_quality_and_preserves_raw(config_data, sheet_values):
    config_data["columns"][3]["unit_conversion"] = conversion()
    config_data["data_quality_rules"] = [{"column": "net_amount", "rule": "max", "value": 100000}]
    good, issues, _ = execute(config_data, sheet_values)
    assert good[0][1]["net_amount"] == Decimal("100000.00")
    assert issues[0]["source_row"] == 3
    assert issues[0]["data"][3] == 200
    assert sheet_values[1][3] == 100


@pytest.mark.parametrize("rounding,expected", [("HALF_UP", "1.01"), ("HALF_EVEN", "1.00"), ("DOWN", "1.00")])
@pytest.mark.parametrize("sign", [1, -1])
def test_exact_decimal_rounding(config_data, sheet_values, rounding, expected, sign):
    config_data["columns"][3]["unit_conversion"] = conversion(from_unit="G", to_unit="KG", factor="0.001", rounding=rounding)
    sheet_values[1][3] = str(Decimal("1005") * sign)
    with localcontext() as context:
        context.prec = 3
        good, _, _ = execute(config_data, sheet_values)
    assert good[0][1]["net_amount"] == Decimal(expected) * sign


@pytest.mark.parametrize("override", [
    {"to_unit": "L"}, {"to_unit": "KG"}, {"factor": "999"}, {"factor": "NaN"},
    {"factor": "-1"}, {"from_unit": "USD"}, {"rounding": "CEILING"}, {"on_error": "IGNORE"},
])
def test_invalid_conversion_rejected(override):
    with pytest.raises(ValidationError):
        UnitConversion.model_validate(conversion(**override))


def test_default_is_already_in_target_unit(config_data, sheet_values):
    config_data["columns"][3]["unit_conversion"] = conversion()
    config_data["data_quality_rules"] = [{"column": "net_amount", "rule": "not_null", "default_value": "2.5"}]
    sheet_values[1][3] = None
    good, _, _ = execute(config_data, sheet_values)
    assert good[0][1]["net_amount"] == Decimal("2.5")
    config_data["data_quality_rules"] = []
    good, _, _ = execute(config_data, sheet_values)
    assert good[0][1]["net_amount"] is None


def test_precision_runtime_matches_ddl_and_rounding_overflow(config_data, sheet_values):
    config_data["columns"][3].update(numeric_precision=5, numeric_scale=2)
    sheet_values[1][3], sheet_values[2][3], sheet_values[3][3] = "999.994", "999.995", "-999.995"
    good, issues, _ = execute(config_data, sheet_values)
    assert good[0][1]["net_amount"] == Decimal("999.99")
    assert [i["source_row"] for i in issues] == [3, 4]
    column = ETLConfiguration.model_validate(config_data).columns[3]
    assert str(mapped_type(column).compile(dialect=postgresql.dialect())) == "NUMERIC(5, 2)"


def test_scale_requires_precision_and_conversion_scale_must_match(config_data):
    config_data["columns"][3]["numeric_scale"] = 2
    with pytest.raises(ValidationError):
        ETLConfiguration.model_validate(config_data)
    config_data["columns"][3].update(numeric_precision=6, unit_conversion=conversion(output_scale=3))
    with pytest.raises(ValidationError):
        ETLConfiguration.model_validate(config_data)


def test_varchar_length_counts_characters(config_data, sheet_values):
    config_data["columns"][2]["varchar_length"] = 2
    sheet_values[1][2], sheet_values[2][2] = "AB", "ABC"
    good, issues, _ = execute(config_data, sheet_values)
    assert len(good) == 1 and [i["source_row"] for i in issues] == [3, 4]


@pytest.mark.parametrize("patch", [{"is_business_key": True, "nullable": False}, {"is_primary_key": True, "nullable": False}])
def test_identity_columns_cannot_be_converted(config_data, patch):
    config_data["columns"][3].update(unit_conversion=conversion(), **patch)
    with pytest.raises(ValidationError, match="non-key numeric"):
        ETLConfiguration.model_validate(config_data)


def test_conversion_overflow_rejected_and_decimal_serialization_preserved(config_data, sheet_values):
    config_data["columns"][3].update(unit_conversion=conversion(), numeric_precision=5, numeric_scale=2)
    original = ETLConfiguration.model_validate(config_data)
    restored = ETLConfiguration.model_validate_json(original.model_dump_json())
    assert restored == original
    good, issues, _ = execute(config_data, sheet_values)
    assert not good and len(issues) == 3
    assert all(i["errors"][0]["code"] == "TYPE_OR_NULL_ERROR" for i in issues)


def test_large_precision_not_limited_by_decimal_context(config_data, sheet_values):
    config_data["columns"][3].update(numeric_precision=40, numeric_scale=2)
    sheet_values[1][3] = "123456789012345678901234567890.125"
    good, issues, _ = execute(config_data, sheet_values)
    assert not issues
    assert good[0][1]["net_amount"] == Decimal("123456789012345678901234567890.13")
