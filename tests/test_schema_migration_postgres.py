"""Standalone PostgreSQL migration tests; only run against an explicit *_test DB."""

import os
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from app.core.database import make_engine
from app.core.exceptions import AppError
from app.schemas.configuration import ETLConfiguration
from app.services.profiling_service import digest
from app.services.schema_compiler_service import compile_table
from app.services.schema_migration_service import apply_migration, inspect_migration, restore_view_access


@pytest.fixture
async def migration_db():
    url = os.environ.get("SCHEMA_WORKFLOW_TEST_URL")
    if not url:
        pytest.skip("Requires SCHEMA_WORKFLOW_TEST_URL pointing to a dedicated *_test database")
    assert make_url(url).database.endswith("_test")
    engine = make_engine(url)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS trusted"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS semantic"))
    try:
        yield engine
    finally:
        await engine.dispose()


def configs():
    data = {
        "dataset_business_name": "Dates",
        "grain": "One event",
        "target_table": "dates",
        "load_strategy": "APPEND",
        "columns": [
            {
                "source_column": "start_date",
                "target_column": "start_date",
                "target_type": "bigint",
                "nullable": False,
            }
        ],
        "semantic": {"code": "dates", "dimensions": ["start_date"], "metrics": []},
    }
    old = ETLConfiguration.model_validate(data)
    new = old.model_copy(deep=True)
    new.columns[0].target_type = "date"
    new.columns[0].transformation_codes = ["parse_date_id"]
    return old, new


async def seed(conn, old, sheet, tenant, populated):
    table = compile_table(old, sheet)
    await conn.run_sync(table.create)
    view = "v_" + sheet.replace("-", "")
    await conn.execute(
        text(f"CREATE VIEW semantic.{view} AS SELECT _tenant_id,start_date FROM trusted.{table.name}")
    )
    await conn.execute(text(f"GRANT SELECT ON semantic.{view} TO PUBLIC"))
    if populated:
        await conn.execute(
            table.insert().values(
                _tenant_id=tenant,
                _source_sheet_id=sheet,
                _source_row=2,
                _etl_run_id=str(uuid4()),
                _row_hash=digest({"start_date": 46023}),
                start_date=46023,
            )
        )
    return table, view


@pytest.mark.parametrize("populated", [False, True])
async def test_reviewed_date_conversion_preserves_data_and_grants(migration_db, populated):
    old, new = configs()
    sheet, tenant = str(uuid4()), str(uuid4())
    async with migration_db.connect() as conn:
        tx = await conn.begin()
        original, view = await seed(conn, old, sheet, tenant, populated)
        target = compile_table(new, sheet)
        plan, _ = await conn.run_sync(
            lambda sync: inspect_migration(sync, target, view, {"parsed": new, "tenant_id": tenant})
        )
        assert plan["allowed"] and plan["requires_migration"]
        if populated:
            assert plan["operations"][0]["examples"] == [{"before": 46023, "after": "2026-01-01"}]
        applied, grants, comments, info = await conn.run_sync(
            lambda sync: apply_migration(sync, target, view, new, tenant, plan["fingerprint"])
        )
        await conn.execute(
            text(f"CREATE VIEW semantic.{view} AS SELECT _tenant_id,start_date FROM trusted.{target.name}")
        )
        await conn.run_sync(lambda sync: restore_view_access(sync, view, grants, comments, info))
        assert applied == plan
        assert (
            await conn.scalar(
                text(
                    "SELECT count(*) FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a "
                    "WHERE c.oid=to_regclass(:view) AND a.grantee=0 AND a.privilege_type='SELECT'"
                ),
                {"view": "semantic." + view},
            )
            == 1
        )
        values = (await conn.execute(target.select())).mappings().all()
        if populated:
            assert values[0]["start_date"] == date(2026, 1, 1)
            assert values[0]["_row_hash"] == digest({"start_date": date(2026, 1, 1)})
        else:
            assert not values
        await tx.rollback()


async def test_schema_or_data_drift_rejects_old_review(migration_db):
    old, new = configs()
    sheet, tenant = str(uuid4()), str(uuid4())
    async with migration_db.connect() as conn:
        tx = await conn.begin()
        original, view = await seed(conn, old, sheet, tenant, True)
        target = compile_table(new, sheet)
        plan, _ = await conn.run_sync(
            lambda sync: inspect_migration(sync, target, view, {"parsed": new, "tenant_id": tenant})
        )
        await conn.execute(original.update().values(start_date=46054))
        with pytest.raises(AppError) as error:
            await conn.run_sync(
                lambda sync: apply_migration(sync, target, view, new, tenant, plan["fingerprint"])
            )
        assert error.value.code == "SCHEMA_MIGRATION_STALE"
        # Rollback cannot use its compatibility exception to change the schema.
        with pytest.raises(AppError) as error:
            await conn.run_sync(
                lambda sync: apply_migration(
                    sync, target, view, new, tenant, plan["fingerprint"], compatible_rollback=True
                )
            )
        assert error.value.code == "SCHEMA_MIGRATION_STALE"
        assert (await conn.run_sync(lambda sync: inspect(sync).get_columns(original.name, schema="trusted")))[
            -1
        ]["type"].__class__.__name__ == "BIGINT"
        await tx.rollback()


async def test_external_migration_cannot_bypass_review_by_matching_target(migration_db):
    old, new = configs()
    sheet, tenant = str(uuid4()), str(uuid4())
    async with migration_db.connect() as conn:
        tx = await conn.begin()
        original, view = await seed(conn, old, sheet, tenant, True)
        target = compile_table(new, sheet)
        plan, _ = await conn.run_sync(
            lambda sync: inspect_migration(sync, target, view, {"parsed": new, "tenant_id": tenant})
        )
        await conn.execute(text(f"DROP VIEW semantic.{view} RESTRICT"))
        await conn.execute(text(
            f"ALTER TABLE trusted.{original.name} ALTER COLUMN start_date TYPE date "
            "USING (DATE '1899-12-30' + start_date::integer)"
        ))
        await conn.execute(text(
            f"CREATE VIEW semantic.{view} AS SELECT _tenant_id,start_date FROM trusted.{original.name}"
        ))
        await conn.execute(text(f"GRANT SELECT ON semantic.{view} TO PUBLIC"))
        current, _ = await conn.run_sync(
            lambda sync: inspect_migration(sync, target, view, {"parsed": new, "tenant_id": tenant})
        )
        assert not current["requires_migration"]
        with pytest.raises(AppError) as error:
            await conn.run_sync(
                lambda sync: apply_migration(sync, target, view, new, tenant, plan["fingerprint"])
            )
        assert error.value.code == "SCHEMA_MIGRATION_STALE"
        await tx.rollback()


async def test_data_drift_without_ddl_operations_rejects_old_review(migration_db):
    old, _ = configs()
    sheet, tenant = str(uuid4()), str(uuid4())
    async with migration_db.connect() as conn:
        tx = await conn.begin()
        target, view = await seed(conn, old, sheet, tenant, True)
        plan, _ = await conn.run_sync(
            lambda sync: inspect_migration(sync, target, view, {"parsed": old, "tenant_id": tenant})
        )
        assert not plan["requires_migration"]
        await conn.execute(target.update().values(start_date=46054))
        with pytest.raises(AppError) as error:
            await conn.run_sync(
                lambda sync: apply_migration(sync, target, view, old, tenant, plan["fingerprint"])
            )
        assert error.value.code == "SCHEMA_MIGRATION_STALE"
        await tx.rollback()


async def test_invalid_serial_and_dependent_view_block_before_changes(migration_db):
    old, new = configs()
    sheet, tenant = str(uuid4()), str(uuid4())
    async with migration_db.connect() as conn:
        tx = await conn.begin()
        original, view = await seed(conn, old, sheet, tenant, True)
        await conn.execute(original.update().values(start_date=999999999))
        await conn.execute(
            text(f"CREATE VIEW semantic.child_{sheet.replace('-', '')} AS SELECT * FROM semantic.{view}")
        )
        plan, _ = await conn.run_sync(
            lambda sync: inspect_migration(
                sync, compile_table(new, sheet), view, {"parsed": new, "tenant_id": tenant}
            )
        )
        assert not plan["allowed"]
        assert any("rentang serial" in b for b in plan["blockers"])
        assert any("View turunan" in b for b in plan["blockers"])
        await tx.rollback()


async def test_nullable_addition_rehashes_populated_append_without_duplicates(migration_db):
    old, new = configs()
    new = old.model_copy(deep=True)
    new.columns.append(
        new.columns[0].model_copy(
            update={"source_column": "note", "target_column": "note", "target_type": "text", "nullable": True}
        )
    )
    sheet, tenant = str(uuid4()), str(uuid4())
    async with migration_db.connect() as conn:
        tx = await conn.begin()
        original, view = await seed(conn, old, sheet, tenant, True)
        target = compile_table(new, sheet)
        plan, _ = await conn.run_sync(
            lambda sync: inspect_migration(sync, target, view, {"parsed": new, "tenant_id": tenant})
        )
        assert plan["allowed"]
        await conn.run_sync(
            lambda sync: apply_migration(sync, target, view, new, tenant, plan["fingerprint"])
        )
        row = (await conn.execute(target.select())).mappings().one()
        assert row["note"] is None
        assert row["_row_hash"] == digest({"start_date": 46023, "note": None})
        await tx.rollback()


async def test_failure_after_migration_rolls_back_table_view_and_hashes(migration_db):
    old, new = configs()
    sheet, tenant = str(uuid4()), str(uuid4())
    async with migration_db.connect() as conn:
        tx = await conn.begin()
        original, view = await seed(conn, old, sheet, tenant, True)
        await tx.commit()
        try:
            tx = await conn.begin()
            target = compile_table(new, sheet)
            plan, _ = await conn.run_sync(
                lambda sync: inspect_migration(sync, target, view, {"parsed": new, "tenant_id": tenant})
            )
            await conn.run_sync(
                lambda sync: apply_migration(sync, target, view, new, tenant, plan["fingerprint"])
            )
            await tx.rollback()
            row = (await conn.execute(original.select())).mappings().one()
            assert row["start_date"] == 46023 and row["_row_hash"] == digest({"start_date": 46023})
            assert await conn.scalar(text(f"SELECT count(*) FROM semantic.{view}")) == 1
        finally:
            await conn.rollback()
            await conn.execute(text(f"DROP VIEW semantic.{view} RESTRICT"))
            await conn.run_sync(original.drop)
            await conn.commit()
