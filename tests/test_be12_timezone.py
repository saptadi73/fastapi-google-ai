from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.configuration import ETLConfiguration
from app.services.etl_compiler_service import cast_value, matches_format, transform_rows


@pytest.mark.parametrize("zone,value,expected", [
    ("Asia/Jakarta", "2026-09-09T01:30:00", "2026-09-08T18:30:00+00:00"),
    ("Asia/Kathmandu", "2026-09-09T01:30:00", "2026-09-08T19:45:00+00:00"),
    ("America/New_York", "2026-01-09T10:00:00", "2026-01-09T15:00:00+00:00"),
    ("America/New_York", "2026-07-09T10:00:00", "2026-07-09T14:00:00+00:00"),
    ("UTC", "2024-02-29T12:00:00", "2024-02-29T12:00:00+00:00"),
])
def test_local_timestamp_normalized(zone, value, expected):
    result = cast_value(value, "timestamptz", source_timezone=zone)
    assert result.isoformat() == expected and result.tzinfo is UTC


@pytest.mark.parametrize("value", ["2026-03-08T02:30:00", "2026-11-01T01:30:00"])
def test_dst_gap_and_overlap_rejected(value):
    with pytest.raises(ValueError, match="Ambiguous or nonexistent"):
        cast_value(value, "timestamptz", source_timezone="America/New_York")


def test_explicit_offsets_disambiguate_and_override_source_zone():
    first = cast_value("2026-11-01T01:30:00-04:00", "timestamptz", source_timezone="America/New_York")
    second = cast_value("2026-11-01T01:30:00-05:00", "timestamptz", source_timezone="America/New_York")
    assert (second - first).total_seconds() == 3600
    assert cast_value("2026-09-09T01:00:00+09:00", "timestamptz", source_timezone="Asia/Jakarta").hour == 16


def test_legacy_naive_requires_zone_and_timestamp_keeps_wall_time():
    with pytest.raises(ValueError, match="Timezone is required"):
        cast_value("2026-09-09T12:00:00", "timestamptz")
    assert cast_value("2026-09-09T12:00:00", "timestamp") == datetime(2026, 9, 9, 12)
    with pytest.raises(ValueError):
        cast_value("2026-09-09T12:00:00Z", "timestamp")


@pytest.mark.parametrize("zone,kind,transforms", [
    ("Not/AZone", "timestamptz", []), ("../UTC", "timestamptz", []),
    ("", "timestamptz", []), ("Asia/Jakarta", "timestamp", []),
    ("Asia/Jakarta", "date", []), ("UTC", "timestamptz", ["parse_date_id"]),
])
def test_timezone_contract(config_data, zone, kind, transforms):
    config_data["columns"][1].update(target_type=kind, source_timezone=zone, transformation_codes=transforms)
    with pytest.raises(ValidationError):
        ETLConfiguration.model_validate(config_data)


def test_runtime_quarantine_raw_and_dq_utc(config_data, sheet_values):
    config_data["columns"][1].update(target_type="timestamptz", source_timezone="America/New_York",
                                    transformation_codes=[])
    config_data["data_quality_rules"] = [{"column": "transaction_date", "rule": "max_age_days", "max_age_days": 1}]
    sheet_values[1][1], sheet_values[2][1], sheet_values[3][1] = (
        "2026-11-01T01:30:00", "2026-11-01T01:30:00-04:00", "2026-11-01T01:30:00-05:00")
    config = ETLConfiguration.model_validate(config_data)
    good, issues, _ = transform_rows(sheet_values, SimpleNamespace(header_row=1, data_start_row=2), config,
                                    reference_time=datetime(2026, 11, 2, 6, tzinfo=UTC))
    assert len(good) == 1 and good[0][0] == 4
    assert issues[0]["data"][1] == "2026-11-01T01:30:00"
    assert issues[0]["errors"][0]["code"] == "TYPE_OR_NULL_ERROR"
    assert issues[1]["errors"][0]["code"] == "MAX_AGE_DAYS"


def test_default_uses_target_offset_not_source_zone(config_data, sheet_values):
    config_data["columns"][1].update(target_type="timestamptz", source_timezone="Asia/Jakarta",
                                    transformation_codes=[])
    config_data["data_quality_rules"] = [{"column": "transaction_date", "rule": "not_null",
                                         "default_value": "2026-09-09T01:00:00Z"}]
    sheet_values[1][1] = None
    config = ETLConfiguration.model_validate(config_data)
    assert ETLConfiguration.model_validate_json(config.model_dump_json()) == config
    good, _, _ = transform_rows(sheet_values, SimpleNamespace(header_row=1, data_start_row=2), config)
    assert good[0][1]["transaction_date"].hour == 1
    config.data_quality_rules[0].default_value = "2026-09-09T01:00:00"
    _, issues, _ = transform_rows(sheet_values, SimpleNamespace(header_row=1, data_start_row=2), config)
    assert issues[0]["source_row"] == 2


def test_iso_format_quality_accepts_normalized_timestamp():
    instant = cast_value("2026-09-09T10:00:00", "timestamptz", source_timezone="Asia/Jakarta")
    assert matches_format(instant, "ISO_DATETIME")
    assert not matches_format(instant, "ISO_DATE")
