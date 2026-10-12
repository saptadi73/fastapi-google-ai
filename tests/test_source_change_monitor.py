from datetime import datetime, timezone

import pytest

from app.services.source_change_monitor import _has_changed, _parse_google_time


def test_drive_modified_time_is_parsed_as_aware_utc():
    value = _parse_google_time("2026-10-13T12:34:56.000Z")
    assert value == datetime(2026, 10, 13, 12, 34, 56, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("previous", "current", "expected"),
    [
        (None, datetime(2026, 1, 1, tzinfo=timezone.utc), False),
        (datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc), False),
        (datetime(2026, 1, 2, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc), False),
        (datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc), True),
    ],
)
def test_only_newer_drive_timestamp_counts_as_external_change(previous, current, expected):
    assert _has_changed(previous, current) is expected
