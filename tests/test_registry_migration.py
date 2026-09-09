"""Run the repair against isolated legacy-shaped tables using transactional DDL."""
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionFactory

pytestmark = pytest.mark.integration


@pytest.fixture
async def registry():
    path = Path(__file__).resolve().parents[1] / (
        "alembic/versions/8a96b7c5d4ef_reconcile_registry_tenant_constraints.py")
    spec = importlib.util.spec_from_file_location("registry_repair_test", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    schema = "registry_test_" + uuid4().hex
    migration.SCHEMA = schema
    tenants = [str(uuid4()), str(uuid4())]
    tables = ["app_user", "source_sheet", "master_definition", *migration.REFERENCES]
    ids = {table: [str(uuid4()), str(uuid4())] for table in tables}
    async with SessionFactory() as session:
        try:
            await session.execute(text(f'CREATE SCHEMA "{schema}"'))
            for table in tables:
                extra = "".join(f', "{column}" uuid' for column in migration.REFERENCES.get(table, {}))
                # Metadata is deliberately present before the repair and must survive.
                await session.execute(text(
                    f'CREATE TABLE "{schema}"."{table}" '
                    f'(id uuid PRIMARY KEY, tenant_id uuid NOT NULL, fingerprint text, '
                    f'snapshot_hash text, approved_at timestamptz {extra})'))
                if table not in migration.REFERENCES:
                    await session.execute(text(
                        f'ALTER TABLE "{schema}"."{table}" ADD UNIQUE (tenant_id, id)'))
                for i, tenant in enumerate(tenants):
                    values = {"id": ids[table][i], "tenant_id": tenant,
                              "fingerprint": "existing-fingerprint", "snapshot_hash": "existing-snapshot",
                              "approved_at": datetime(2026, 9, 1, tzinfo=timezone.utc)}
                    for column, parent in migration.REFERENCES.get(table, {}).items():
                        values[column] = None if column == "parent_id" else ids[parent][i]
                    names = ", ".join(f'"{key}"' for key in values)
                    params = ", ".join(f':{key}' for key in values)
                    await session.execute(text(f'INSERT INTO "{schema}"."{table}" ({names}) VALUES ({params})'),
                                          values)
            connection = await session.connection()

            async def run(action):
                def execute(sync):
                    migration.op = Operations(MigrationContext.configure(sync))
                    getattr(migration, action)()
                await connection.run_sync(execute)

            yield session, connection, migration, ids, run
        finally:
            await session.rollback()


@pytest.mark.parametrize("master_already_repaired", [False, True])
async def test_repair_is_repeatable_preserves_metadata_and_enforces_all_tenant_links(registry,
                                                                                  master_already_repaired):
    session, connection, migration, ids, run = registry
    references = migration.REFERENCES
    if master_already_repaired:
        migration.REFERENCES = {"master_column_binding": references["master_column_binding"]}
        await run("upgrade")
        migration.REFERENCES = references
    await run("upgrade")
    await run("upgrade")
    # This additive repair retains protections when rolling back the application.
    await run("downgrade")
    for table, columns in references.items():
        row = (await session.execute(text(
            f'SELECT * FROM "{migration.SCHEMA}"."{table}" WHERE id=:id'), {"id": ids[table][0]})).mappings().one()
        assert row["fingerprint"] == "existing-fingerprint" and row["snapshot_hash"] == "existing-snapshot"
        assert row["approved_at"] == datetime(2026, 9, 1, tzinfo=timezone.utc)
        assert str(row["approved_by"]) == ids["app_user"][0]
        for column, parent in columns.items():
            with pytest.raises(IntegrityError):
                async with session.begin_nested():
                    await session.execute(text(
                        f'UPDATE "{migration.SCHEMA}"."{table}" SET "{column}"=:foreign_id WHERE id=:id'),
                        {"foreign_id": ids[parent][1], "id": ids[table][0]})
        fks = await connection.run_sync(lambda sync: inspect(sync).get_foreign_keys(table, schema=migration.SCHEMA))
        assert len(fks) == len(columns)  # Repeated upgrade does not duplicate constraints.


async def test_cross_tenant_legacy_data_aborts_repair_without_rewriting_records(registry):
    session, connection, migration, ids, run = registry
    await session.execute(text(
        f'UPDATE "{migration.SCHEMA}".taxonomy SET created_by=:foreign_id WHERE id=:id'),
        {"foreign_id": ids["app_user"][1], "id": ids["taxonomy"][0]})
    with pytest.raises(IntegrityError):
        async with connection.begin_nested():
            await run("upgrade")
    constraints = await connection.run_sync(lambda sync: inspect(sync).get_unique_constraints(
        "taxonomy", schema=migration.SCHEMA))
    assert not constraints
    actor = await session.scalar(text(
        f'SELECT created_by FROM "{migration.SCHEMA}".taxonomy WHERE id=:id'), {"id": ids["taxonomy"][0]})
    assert str(actor) == ids["app_user"][1]
