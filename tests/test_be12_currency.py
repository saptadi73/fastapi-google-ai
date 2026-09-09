from decimal import Decimal, localcontext
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.configuration import CurrencyConversion, ETLConfiguration
from app.services.etl_compiler_service import transform_rows
from app.services.profiling_service import digest


def rate(**changes):
    # Synthetic test rate, not a market quote.
    return {"from_currency": "USD", "to_currency": "IDR", "rate": "12345.5",
            "rate_date": "2026-09-09", "rate_reference": "synthetic-test-rate",
            "output_scale": 2, "rounding": "HALF_UP", **changes}


def run(data, values):
    return transform_rows(values, SimpleNamespace(header_row=1, data_start_row=2),
                          ETLConfiguration.model_validate(data))


def test_conversion_before_dq_and_raw_preserved(config_data, sheet_values):
    config_data["columns"][3]["currency_conversion"] = rate()
    config_data["data_quality_rules"] = [{"column": "net_amount", "rule": "max", "value": 2000000}]
    good, issues, _ = run(config_data, sheet_values)
    assert good[0][1]["net_amount"] == Decimal("1234550.00")
    assert issues[0]["data"][3] == 200 and issues[0]["errors"][0]["code"] == "MAX"
    assert sheet_values[1][3] == 100


@pytest.mark.parametrize("rounding,expected", [("HALF_UP", "1.01"), ("HALF_EVEN", "1.00"), ("DOWN", "1.00")])
@pytest.mark.parametrize("sign", [1, -1])
def test_decimal_rounding_independent_of_context(config_data, sheet_values, rounding, expected, sign):
    config_data["columns"][3]["currency_conversion"] = rate(rate="1.005", rounding=rounding)
    sheet_values[1][3] = sign
    with localcontext() as ctx:
        ctx.prec = 2
        good, _, _ = run(config_data, sheet_values)
    assert good[0][1]["net_amount"] == Decimal(expected) * sign


@pytest.mark.parametrize("change", [{"rate": 0}, {"rate": -1}, {"rate": "NaN"}, {"rate": "Infinity"},
                                   {"rate_reference": "  "}, {"rate_date": "invalid"},
                                   {"to_currency": "USD"}, {"from_currency": "XXX"},
                                   {"on_error": "IGNORE"}, {"rounding": "AUTO"}])
def test_invalid_rate_contract(change):
    with pytest.raises(ValidationError):
        CurrencyConversion.model_validate(rate(**change))


def test_default_already_target_and_overflow(config_data, sheet_values):
    config_data["columns"][3].update(currency_conversion=rate(), numeric_precision=5, numeric_scale=2)
    config_data["data_quality_rules"] = [{"column": "net_amount", "rule": "not_null", "default_value": "2.5"}]
    sheet_values[1][3] = None
    good, issues, _ = run(config_data, sheet_values)
    assert good[0][1]["net_amount"] == Decimal("2.50")
    assert len(issues) == 2 and issues[0]["errors"][0]["code"] == "TYPE_OR_NULL_ERROR"


@pytest.mark.parametrize("patch", [{"is_business_key": True, "nullable": False},
                                    {"is_primary_key": True, "nullable": False},
                                    {"numeric_precision": 10, "numeric_scale": 3}])
def test_incompatible_column(config_data, patch):
    config_data["columns"][3].update(currency_conversion=rate(), **patch)
    with pytest.raises(ValidationError):
        ETLConfiguration.model_validate(config_data)


def test_rate_metadata_preserved_and_changes_configuration_hash(config_data):
    config_data["columns"][3]["currency_conversion"] = rate()
    config = ETLConfiguration.model_validate(config_data)
    restored = ETLConfiguration.model_validate_json(config.model_dump_json())
    assert restored == config
    before = digest(config.model_dump(mode="json"))
    for key, value in [("rate", "12346"), ("rate_date", "2026-09-08"), ("rate_reference", "another-source")]:
        config_data["columns"][3]["currency_conversion"] = rate(**{key: value})
        assert digest(ETLConfiguration.model_validate(config_data).model_dump(mode="json")) != before


def test_unit_and_currency_combination_rejected(config_data):
    config_data["columns"][3].update(currency_conversion=rate(), unit_conversion={
        "from_unit": "KG", "to_unit": "G", "factor": "1000", "output_scale": 2, "rounding": "HALF_UP"})
    with pytest.raises(ValidationError, match="cannot be combined"):
        ETLConfiguration.model_validate(config_data)
