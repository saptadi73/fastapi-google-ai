import pytest
from sqlalchemy import BigInteger, Column, Date, Text
from sqlalchemy.dialects import postgresql

from app.core.exceptions import AppError
from app.services.schema_compiler_service import validate_semantic_view_columns


def test_identical_view_and_appended_columns_remain_supported():
    existing = [{"name": "period", "type": Text()}]
    validate_semantic_view_columns(existing, [Column("period", Text)], postgresql.dialect())
    validate_semantic_view_columns(
        existing, [Column("period", Text), Column("start_date", Date)], postgresql.dialect()
    )


@pytest.mark.parametrize(
    "proposed",
    [
        [Column("start_date", Date)],
        [Column("renamed", BigInteger)],
        [],
        [Column("end_date", BigInteger), Column("start_date", BigInteger)],
    ],
)
def test_incompatible_view_requires_explicit_migration(proposed):
    existing = [{"name": "start_date", "type": BigInteger()}]
    with pytest.raises(AppError) as error:
        validate_semantic_view_columns(existing, proposed, postgresql.dialect())
    assert error.value.code == "SEMANTIC_SCHEMA_MIGRATION_REQUIRED"
    assert "start_date" in error.value.message


def test_date_type_failure_identifies_old_and_new_types():
    with pytest.raises(AppError) as error:
        validate_semantic_view_columns(
            [{"name": "start_date", "type": BigInteger()}],
            [Column("start_date", Date)],
            postgresql.dialect(),
        )
    assert "bigint" in error.value.message
    assert "date" in error.value.message
    assert error.value.status_code == 409
