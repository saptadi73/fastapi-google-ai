import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from test_integration import context as context
from test_integration import onboard, request
from test_masters import approved_master, binding_body, master_sheet

from app.core.database import SessionFactory
from app.models.auth import User
from app.models.base import now
from app.models.configuration import Configuration
from app.models.etl import Job, Snapshot
from app.models.import_review import ImportReview
from app.models.master import MasterDefinition
from app.services.profiling_service import digest
from app.workers.runner import run_pending, schedule_sources

pytestmark = pytest.mark.integration


async def non_master(ctx, config_data):
    _, sheet, config = await onboard(ctx, config_data)
    config = config["id"]
    # Configuration approval itself is tested separately; seed its postcondition here.
    async with SessionFactory() as session, session.begin():
        await session.execute(
            update(Configuration).where(Configuration.id == config).values(status="APPROVED")
        )
    return {"source_sheet_id": sheet, "configuration_id": config}


async def create(ctx, body):
    return (await request(ctx, "POST", "/import-reviews", data=body, expected=202))["data"]["review"]


async def detail(ctx, review):
    return (await request(ctx, "GET", f"/import-reviews/{review['id']}"))["data"]


async def test_import_idempotency_checkpoint_and_blocked_resume(context, config_data):
    ctx = context
    body = await non_master(ctx, config_data)
    results = await asyncio.gather(
        *(request(ctx, "POST", "/import-reviews", data=body, expected=202) for _ in range(2))
    )
    assert sorted(r["data"]["reused"] for r in results) == [False, True]
    review = results[0]["data"]["review"]
    assert results[1]["data"]["review"]["id"] == review["id"]
    await run_pending(ctx.tenant_id)
    reviewing = await detail(ctx, review)
    assert reviewing["status"] == "AI_REVIEWING" and reviewing["checkpoint"]["rows_valid"] == 3
    assert reviewing["job_id"] != review["job_id"]
    await run_pending(ctx.tenant_id)
    waiting = await detail(ctx, review)
    assert waiting["status"] == "NEEDS_INPUT" and waiting["checkpoint"]["ai_coverage"] == "NOT_STARTED"
    assert waiting["checkpoint"]["blocking_codes"] == ["AI_REVIEW_NOT_IMPLEMENTED"]
    assert (await run_pending(ctx.tenant_id))["processed"] == 0
    for action in ("resume", "revalidate"):
        result = await request(
            ctx,
            "POST",
            f"/import-reviews/{review['id']}/{action}",
            data={"revision_no": waiting["revision_no"]},
            expected=409,
        )
        assert result["errors"][0]["code"] == "IMPORT_INPUT_PENDING"
    for who, expected in (("viewer", 403), ("outsider", 404)):
        await request(ctx, "GET", f"/import-reviews/{review['id']}", who=who, expected=expected)
    await request(ctx, "POST", "/import-reviews", data=body, who="approver", expected=403)
    listed = (await request(ctx, "GET", "/import-reviews?status=NEEDS_INPUT&limit=1"))["data"]
    assert listed["items"][0]["id"] == review["id"] and not listed["has_more"]
    assert "configuration_json" not in waiting and "dependencies" not in waiting


async def test_import_bad_data_persists_findings_without_raw_values(context, config_data):
    ctx = context
    body = await non_master(ctx, config_data)
    async with SessionFactory() as session, session.begin():
        snapshot = await session.scalar(
            select(Snapshot).where(Snapshot.source_sheet_id == body["source_sheet_id"])
        )
        values = [r[:] for r in snapshot.values]
        values[1][3] = "SensitiveInvalidValue"
        snapshot.values, snapshot.content_hash = values, digest(values)
    review = await create(ctx, body)
    await run_pending(ctx.tenant_id)
    result = await detail(ctx, review)
    assert result["status"] == "NEEDS_INPUT" and result["checkpoint"]["rows_invalid"] == 1
    findings = await request(ctx, "GET", f"/import-reviews/{review['id']}/findings?limit=1")
    assert findings["data"]["items"][0]["errors"][0]["code"] == "TYPE_OR_NULL_ERROR"
    assert "SensitiveInvalidValue" not in str(findings) + str(result)
    assert (await request(ctx, "GET", f"/jobs/{review['job_id']}"))["data"]["status"] == "SUCCEEDED"


async def test_import_cancel_stale_generation_and_snapshot_replacement(context, config_data):
    ctx = context
    body = await non_master(ctx, config_data)
    review = await create(ctx, body)
    path = f"/import-reviews/{review['id']}"
    await request(ctx, "POST", path + "/cancel", data={"revision_no": 99}, expected=409)
    await request(ctx, "POST", path + "/cancel", data={"revision_no": 1})
    await run_pending(ctx.tenant_id)
    assert (await detail(ctx, review))["status"] == "CANCELLED"
    assert (await request(ctx, "GET", f"/jobs/{review['job_id']}"))["data"]["result"]["skipped"]
    async with SessionFactory() as session, session.begin():
        old = await session.get(Snapshot, review["snapshot_id"])
        values = [r[:] for r in old.values]
        values[1][3] = 999
        session.add(
            Snapshot(
                tenant_id=ctx.tenant_id,
                source_id=old.source_id,
                source_sheet_id=old.source_sheet_id,
                content_hash=digest(values),
                row_count=old.row_count,
                values=values,
            )
        )
    fresh = await create(ctx, body)
    assert fresh["id"] != review["id"] and fresh["snapshot_id"] != review["snapshot_id"]
    async with SessionFactory() as session, session.begin():
        await session.execute(
            update(Configuration).where(Configuration.id == body["configuration_id"]).values(revision_no=2)
        )
    await run_pending(ctx.tenant_id)
    stale = await detail(ctx, fresh)
    assert stale["status"] == "STALE_REVIEW" and not stale["dependencies_current"]
    refreshed = (
        await request(
            ctx,
            "POST",
            f"/import-reviews/{fresh['id']}/revalidate",
            data={"revision_no": stale["revision_no"]},
        )
    )["data"]
    assert refreshed["status"] == "STALE_REVIEW" and refreshed["snapshot_id"] == fresh["snapshot_id"]
    assert (await create(ctx, body))["id"] != fresh["id"]


async def test_import_worker_crash_recovery_reuses_checkpoint(context, config_data, monkeypatch):
    ctx = context
    body = await non_master(ctx, config_data)
    review = await create(ctx, body)
    await run_pending(ctx.tenant_id)
    after_validation = await detail(ctx, review)
    # Simulate termination after durable job claim, before executing the next phase.
    async with SessionFactory() as session, session.begin():
        await session.execute(
            update(Job)
            .where(Job.id == after_validation["job_id"])
            .values(status="RUNNING", started_at=now() - timedelta(days=1))
        )
    await schedule_sources()
    failed = await detail(ctx, review)
    assert failed["status"] == "FAILED" and failed["checkpoint"]["deterministic_complete"]
    await request(ctx, "POST", f"/jobs/{failed['job_id']}/retry", expected=409)
    retried = (
        await request(
            ctx,
            "POST",
            f"/import-reviews/{review['id']}/revalidate",
            data={"revision_no": failed["revision_no"]},
        )
    )["data"]
    assert retried["generation"] == 2

    def must_not_transform(*args):
        raise AssertionError("Completed deterministic checkpoint must be reused")

    monkeypatch.setattr("app.services.import_review_service.transform_rows", must_not_transform)
    await run_pending(ctx.tenant_id)
    assert (await detail(ctx, review))["status"] == "AI_REVIEWING"
    await run_pending(ctx.tenant_id)
    assert (await detail(ctx, review))["status"] == "NEEDS_INPUT"


async def test_import_worker_failure_rolls_back_then_records_failed(context, config_data, monkeypatch):
    ctx = context
    body = await non_master(ctx, config_data)
    review = await create(ctx, body)

    def broken(*args):
        raise RuntimeError("sensitive provider detail")

    monkeypatch.setattr("app.services.import_review_service.transform_rows", broken)
    await run_pending(ctx.tenant_id)
    failed = await detail(ctx, review)
    assert failed["status"] == "FAILED" and failed["checkpoint"]["last_error_code"] == "JOB_EXECUTION_FAILED"
    assert "sensitive provider detail" not in str(failed)
    async with SessionFactory() as session:
        row = await session.get(ImportReview, review["id"])
        outsider_id = await session.scalar(select(User.id).where(User.tenant_id != ctx.tenant_id).limit(1))
        with pytest.raises(IntegrityError):
            row.created_by = outsider_id
            await session.flush()
        await session.rollback()


async def test_import_master_pins_binding_and_approved_version(context, config_data):
    ctx = context
    master = await approved_master(ctx, config_data)
    _, sheet, _ = await master_sheet(ctx, config_data)
    await request(
        ctx, "PUT", f"/source-sheets/{sheet}/master-binding", data=binding_body(master, config_data)
    )
    await request(
        ctx, "POST", f"/source-sheets/{sheet}/master-binding/approve", who="approver", data={"revision_no": 1}
    )
    review = await create(ctx, {"source_sheet_id": sheet})
    assert (
        review["master_version"] == 1 and review["policy"]["master"]["new_record_policy"] == "PROPOSE_INSERT"
    )
    async with SessionFactory() as session, session.begin():
        await session.execute(
            update(MasterDefinition).where(MasterDefinition.id == master["id"]).values(is_active=False)
        )
    await run_pending(ctx.tenant_id)
    assert (await detail(ctx, review))["status"] == "STALE_REVIEW"


async def test_import_duplicate_job_and_identical_snapshot_are_idempotent(context, config_data):
    ctx = context
    body = await non_master(ctx, config_data)
    review = await create(ctx, body)
    async with SessionFactory() as session, session.begin():
        original = await session.get(Job, review["job_id"])
        duplicate = Job(
            tenant_id=ctx.tenant_id,
            source_id=original.source_id,
            requested_by=original.requested_by,
            kind=original.kind,
            payload={**original.payload, "generation": 0},
        )
        session.add(duplicate)
        old = await session.get(Snapshot, review["snapshot_id"])
        session.add(
            Snapshot(
                tenant_id=ctx.tenant_id,
                source_id=old.source_id,
                source_sheet_id=old.source_sheet_id,
                values=old.values,
                content_hash=old.content_hash,
                row_count=old.row_count,
            )
        )
    assert (await create(ctx, body))["id"] == review["id"]
    await asyncio.gather(run_pending(ctx.tenant_id), run_pending(ctx.tenant_id))
    assert (await request(ctx, "GET", f"/jobs/{duplicate.id}"))["data"]["result"]["skipped"]
    assert (await detail(ctx, review))["status"] == "AI_REVIEWING"
    await run_pending(ctx.tenant_id)
    assert (await detail(ctx, review))["status"] == "NEEDS_INPUT"


async def test_import_migration_roundtrip_in_rolled_back_transaction():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect

    path = (
        Path(__file__).resolve().parents[1] / "alembic/versions/5ab90e816eee_durable_import_review_batches.py"
    )
    spec = importlib.util.spec_from_file_location("import_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    question_path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/6d1305460956_structured_import_questions_and_.py"
    )
    question_spec = importlib.util.spec_from_file_location("import_question_migration", question_path)
    question_migration = importlib.util.module_from_spec(question_spec)
    question_spec.loader.exec_module(question_migration)
    async with SessionFactory() as session:
        try:
            connection = await session.connection()

            def verify(sync):
                operations = Operations(MigrationContext.configure(sync))
                migration.op = operations
                question_migration.op = operations
                question_migration.downgrade()
                migration.downgrade()
                assert not inspect(sync).has_table("import_review", schema="platform")
                migration.upgrade()
                question_migration.upgrade()
                inspector = inspect(sync)
                unique = {
                    tuple(u["column_names"])
                    for u in inspector.get_unique_constraints("import_review", schema="platform")
                }
                assert ("tenant_id", "idempotency_key") in unique
                foreign = {
                    tuple(f["constrained_columns"])
                    for f in inspector.get_foreign_keys("import_review", schema="platform")
                }
                assert ("tenant_id", "created_by") in foreign
                assert ("tenant_id", "snapshot_id") in foreign
                assert inspect(sync).has_table("import_question", schema="platform")
                decision_foreign = {
                    tuple(f["constrained_columns"])
                    for f in inspector.get_foreign_keys("import_decision", schema="platform")
                }
                assert ("tenant_id", "proposed_master_definition_id") in decision_foreign

            await connection.run_sync(verify)
        finally:
            await session.rollback()
