from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.schemas.configuration import ETLConfiguration
from app.services.etl_compiler_service import cast_value, decimal_id, transform_rows


def test_transforms():
    assert decimal_id("Rp 1.234,56") == Decimal("1234.56")
    assert decimal_id(1234.56) == Decimal("1234.56")
    assert cast_value("tidak", "boolean") is False
    with pytest.raises(ValueError):
        cast_value("1.5", "integer")
    with pytest.raises(ValueError):
        cast_value("NaN", "numeric")
    with pytest.raises(ValueError):
        cast_value("2026-09-01T00:00:00", "timestamptz")


def test_keys_and_quarantine(config_data, sheet_values):
    config = ETLConfiguration.model_validate(config_data)
    sheet_values.append(sheet_values[1].copy())
    sheet_values.append(["004", "not a date", "Jakarta", 10])
    good, issues, warnings = transform_rows(
        sheet_values, SimpleNamespace(header_row=1, data_start_row=2), config
    )
    assert len(good) == 3
    assert [i["source_row"] for i in issues] == [5, 6]
    assert issues[0]["errors"][0]["code"] == "DUPLICATE_BUSINESS_KEY"


def test_stop_batch(config_data, sheet_values):
    config_data["data_quality_rules"] = [
        {"column": "net_amount", "rule": "max", "value": 100, "action_on_fail": "STOP_BATCH"}
    ]
    config = ETLConfiguration.model_validate(config_data)
    with pytest.raises(AppError, match="review"):
        transform_rows(sheet_values, SimpleNamespace(header_row=1, data_start_row=2), config)


def test_configuration_rejects_arbitrary_code_and_sensitive_metrics(config_data):
    config_data["columns"][0]["transformation_codes"] = ["eval"]
    with pytest.raises(ValidationError):
        ETLConfiguration.model_validate(config_data)
    config_data["columns"][0]["transformation_codes"] = []
    config_data["columns"][0]["pii_classification"] = "HIGH"
    with pytest.raises(ValidationError):
        ETLConfiguration.model_validate(config_data)
