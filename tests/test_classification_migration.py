"""Exercise the real migration against isolated PostgreSQL tables, then roll back."""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.core.database import SessionFactory

pytestmark = pytest.mark.integration


async def test_classification_backfill_and_downgrade_preserve_legacy_rows():
    module_path = (
        Path(__file__).resolve().parents[1] / "alembic/versions/b762af03e219_sheet_classification.py"
    )
    spec = importlib.util.spec_from_file_location("classification_migration_test", module_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    schema = "migration_test_" + uuid4().hex
    tenant_id, actor_id, sheet_id, active_id = (str(uuid4()) for _ in range(4))
    async with SessionFactory() as session:
        try:
            await session.execute(text(f'CREATE SCHEMA "{schema}"'))
            await session.execute(
                text(f'CREATE TABLE "{schema}".app_user (tenant_id uuid, id uuid, UNIQUE(tenant_id,id))')
            )
            await session.execute(
                text(
                    f'CREATE TABLE "{schema}".source_sheet (id uuid PRIMARY KEY, tenant_id uuid NOT NULL, active_configuration_id uuid, sheet_name text)'
                )
            )
            await session.execute(
                text(f'INSERT INTO "{schema}".app_user VALUES (:tenant,:actor)'),
                {"tenant": tenant_id, "actor": actor_id},
            )
            await session.execute(
                text(f"INSERT INTO \"{schema}\".source_sheet VALUES (:id,:tenant,:active,'Legacy Sales')"),
                {"id": sheet_id, "tenant": tenant_id, "active": active_id},
            )
            connection = await session.connection()

            def execute_migration(sync_connection, action):
                operations = Operations(MigrationContext.configure(sync_connection))

                class IsolatedOperations:
                    def __getattr__(self, name):
                        def apply(*args, **kwargs):
                            # Only route the migration's literal platform schema to our test namespace.
                            for key in ("schema", "source_schema", "referent_schema"):
                                if kwargs.get(key) == "platform":
                                    kwargs[key] = schema
                            return getattr(operations, name)(*args, **kwargs)

                        return apply

                migration.op = IsolatedOperations()
                getattr(migration, action)()

            await connection.run_sync(execute_migration, "upgrade")
            row = (await session.execute(text(f'SELECT * FROM "{schema}".source_sheet'))).mappings().one()
            assert row["classification_status"] == "CLASSIFICATION_REQUIRED"
            assert row["classification_revision"] == 1
            assert row["dataset_kind"] is None and row["classification_confirmed_by"] is None
            assert str(row["active_configuration_id"]) == active_id
            assert row["sheet_name"] == "Legacy Sales"
            await connection.run_sync(execute_migration, "downgrade")
            row = (await session.execute(text(f'SELECT * FROM "{schema}".source_sheet'))).mappings().one()
            assert "dataset_kind" not in row
            assert str(row["id"]) == sheet_id and str(row["active_configuration_id"]) == active_id
        finally:
            # PostgreSQL transactional DDL removes only this test's uncommitted schema/data.
            await session.rollback()
