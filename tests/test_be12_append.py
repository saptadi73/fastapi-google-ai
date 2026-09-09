from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.schemas.configuration import ETLConfiguration
from app.services.append_service import append_values
from app.services.etl_compiler_service import transform_rows
from app.services.profiling_service import digest


def append_config(data, policy=None):
    data["load_strategy"] = "APPEND"
    data["append_duplicate_policy"] = policy
    for column in data["columns"]:
        column["is_business_key"] = column["is_primary_key"] = False
    return ETLConfiguration.model_validate(data)


@pytest.mark.parametrize("policy", [None, "SKIP_IDENTICAL"])
def test_append_default_and_skip_report_identical_after_transform(config_data, sheet_values, policy):
    config = append_config(config_data, policy)
    sheet_values.append(sheet_values[1].copy())
    good, issues, warnings = transform_rows(sheet_values, SimpleNamespace(header_row=1, data_start_row=2), config)
    assert len(good) == 4 and not issues
    assert warnings == [{"source_row": 5, "code": "APPEND_IDENTICAL_SKIPPED"}]
    serialized = {k: str(v) if v is not None else None for k, v in good[0][1].items()}
    assert digest(append_values(config, serialized)) == digest(good[0][1])


def test_append_reject_stops_duplicate_snapshot(config_data, sheet_values):
    config = append_config(config_data, "REJECT_IDENTICAL")
    sheet_values.append(sheet_values[1].copy())
    with pytest.raises(AppError) as exc:
        transform_rows(sheet_values, SimpleNamespace(header_row=1, data_start_row=2), config)
    assert exc.value.code == "APPEND_IDENTICAL_REJECTED"


@pytest.mark.parametrize("strategy,key", [("UPSERT", True), ("FULL_REFRESH", False), ("APPEND", True)])
def test_append_policy_rejects_incompatible_identity(config_data, strategy, key):
    config_data.update(load_strategy=strategy, append_duplicate_policy="SKIP_IDENTICAL")
    config_data["columns"][0]["is_business_key"] = key
    with pytest.raises(ValidationError, match="append_duplicate_policy requires"):
        ETLConfiguration.model_validate(config_data)


def test_append_policy_roundtrip_and_dependency_hash(config_data):
    config = append_config(config_data, "SKIP_IDENTICAL")
    assert ETLConfiguration.model_validate_json(config.model_dump_json()) == config
    old = digest(config.model_dump(mode="json"))
    config.append_duplicate_policy = "REJECT_IDENTICAL"
    assert digest(config.model_dump(mode="json")) != old
