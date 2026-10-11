from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.configuration import ColumnMapping
from app.services.etl_compiler_service import date_id


@pytest.mark.parametrize("value", [46023, 46023.0, Decimal("46023")])
def test_explicit_serial_dates(value):
    assert date_id(value, input_format="GOOGLE_SHEETS_SERIAL") == date(2026, 1, 1)


@pytest.mark.parametrize("value", [True, "46023", "2026-01-01", 0, -1, 2958466, 46023.5, float("nan"), float("inf")])
def test_explicit_serial_rejects_ambiguous_or_invalid_values(value):
    with pytest.raises(ValueError):
        date_id(value, input_format="GOOGLE_SHEETS_SERIAL")


def test_text_date_does_not_guess_numeric_serials():
    assert date_id("2026-01-01", input_format="TEXT") == date(2026, 1, 1)
    with pytest.raises(ValueError):
        date_id(46023, input_format="TEXT")


def test_format_requires_date_parser():
    with pytest.raises(ValidationError):
        ColumnMapping(source_column="Date", target_column="date", target_type="bigint",
                      date_input_format="GOOGLE_SHEETS_SERIAL")
