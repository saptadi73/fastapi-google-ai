"""Fresh snapshot migration/backfill using transactional isolated PostgreSQL DDL."""
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from test_integration import context as context
from test_integration import request
from test_taxonomy_workflow import taxonomy

from app.core.database import SessionFactory

pytestmark = pytest.mark.integration


async def test_fresh_migration_backfills_current_only_and_preserves_live_on_downgrade(context):
    definition, terms = await taxonomy(context)
    await request(context, "POST", "/taxonomies", expected=201, data={"code": "draft", "name": "Draft"})
    path = Path(__file__).resolve().parents[1] / "alembic/versions/9b07c8d6e5fa_immutable_taxonomy_version_snapshots.py"
    spec = importlib.util.spec_from_file_location("taxonomy_snapshot_test", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    schema = migration.SCHEMA = "snapshot_test_" + uuid4().hex
    async with SessionFactory() as session:
        try:
            await session.execute(text(f'CREATE SCHEMA "{schema}"'))
            for table in ("tenant", "app_user", "taxonomy", "taxonomy_term"):
                await session.execute(text(f'CREATE TABLE "{schema}".{table} (LIKE platform.{table} INCLUDING ALL)'))
                key = "id" if table == "tenant" else "tenant_id"
                await session.execute(text(f'INSERT INTO "{schema}".{table} SELECT * FROM platform.{table} WHERE {key}=:id'),
                                      {"id": context.tenant_id})
            connection = await session.connection()

            def run(sync, action):
                migration.op = Operations(MigrationContext.configure(sync))
                getattr(migration, action)()

            await connection.run_sync(run, "upgrade")
            snapshots = (await session.execute(text(f'SELECT * FROM "{schema}".taxonomy_version'))).mappings().all()
            assert len(snapshots) == 1
            version = snapshots[0]
            assert str(version["taxonomy_id"]) == definition["id"] and version["version"] == definition["version"]
            assert {t["id"] for t in version["definition_json"]["terms"]} == {t["id"] for t in terms}
            fks = await connection.run_sync(lambda sync: inspect(sync).get_foreign_keys("taxonomy_version", schema=schema))
            assert len([fk for fk in fks if len(fk["constrained_columns"]) == 2]) == 3
            outsider = str(uuid4())
            # Existing tenant, but mismatched creator/taxonomy references must fail.
            await session.execute(text(f'INSERT INTO "{schema}".tenant SELECT * FROM platform.tenant WHERE id != :id LIMIT 1'),
                                  {"id": context.tenant_id})
            other = await session.scalar(text(f'SELECT id FROM "{schema}".tenant WHERE id != :id LIMIT 1'),
                                         {"id": context.tenant_id})
            with pytest.raises(IntegrityError), session.no_autoflush:
                async with session.begin_nested():
                    await session.execute(text(f'UPDATE "{schema}".taxonomy_version SET tenant_id=:other'), {"other": other or outsider})
            await connection.run_sync(run, "downgrade")
            assert await session.scalar(text(f'SELECT count(*) FROM "{schema}".taxonomy_term')) == 2
            assert await session.scalar(text(f'SELECT version FROM "{schema}".taxonomy WHERE id=:id'),
                                        {"id": definition["id"]}) == definition["version"]
        finally:
            await session.rollback()
