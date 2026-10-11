from sqlalchemy import BigInteger, Column, Date, MetaData, Table, Text
from sqlalchemy.dialects import postgresql

from app.services.schema_migration_service import column_changes


def test_empty_table_type_changes_and_required_additions_are_safe():
    table = Table(
        "data", MetaData(), Column("start_date", Date, nullable=False), Column("name", Text, nullable=False)
    )
    operations, blockers = column_changes(
        [{"name": "start_date", "type": BigInteger(), "nullable": False}],
        table,
        0,
        postgresql.dialect(),
    )
    assert not blockers
    assert [op["action"] for op in operations] == ["ALTER_TYPE", "ADD_COLUMN"]


def test_populated_required_addition_and_column_removal_are_blocked():
    table = Table("data", MetaData(), Column("new", Text, nullable=False))
    _, blockers = column_changes(
        [{"name": "old", "type": Text(), "nullable": True}], table, 10, postgresql.dialect()
    )
    assert len(blockers) == 2
    assert "old" in blockers[0]
    assert "record lama" in blockers[1]


def test_populated_serial_dates_are_explicit_operations_not_generic_casts():
    table = Table("data", MetaData(), Column("start_date", Date, nullable=True))
    operations, blockers = column_changes(
        [{"name": "start_date", "type": BigInteger(), "nullable": True}],
        table,
        3,
        postgresql.dialect(),
    )
    assert not blockers
    assert operations[0]["action"] == "SERIAL_TO_DATE"


def test_populated_unsupported_cast_is_blocked():
    table = Table("data", MetaData(), Column("name", Date, nullable=True))
    _, blockers = column_changes(
        [{"name": "name", "type": Text(), "nullable": True}], table, 3, postgresql.dialect()
    )
    assert "belum didukung" in blockers[0]
