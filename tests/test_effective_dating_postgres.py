"""Real storage/transaction tests; upstream snapshot validation is held current.

Only is_current is stubbed: preview, token, approval, review row locks, master
locks, storage validation, writes, audit and rollback use production code.
"""
import asyncio
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, select, text
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionFactory
from app.core.exceptions import AppError
from app.models.audit import AuditEvent
from app.models.auth import Tenant, User
from app.models.etl import Snapshot
from app.models.import_review import ImportReview, ImportReviewRow
from app.models.master import MasterDefinition
from app.models.source import DataSource, SourceSheet
from app.schemas.import_review import ImportReviewPreviewRequest
from app.schemas.master import MasterSchema
from app.services.effective_dating_service import effective_at_condition
from app.services.import_review_service import ImportReviewService
from app.services.schema_compiler_service import compile_master_table

pytestmark = pytest.mark.integration


@pytest.fixture
async def history(monkeypatch):
    monkeypatch.setattr(ImportReviewService, "is_current", AsyncMock(return_value=True))
    tenant_id, master_id, record_id = (str(uuid4()) for _ in range(3))
    definition = MasterSchema.model_validate({
        "name": "Price history", "fields": [
            {"name": "code", "type": "text", "nullable": False},
            {"name": "starts", "type": "date", "nullable": False},
            {"name": "ends", "type": "date"},
            {"name": "price", "type": "numeric", "nullable": False}],
        "business_key": ["code", "starts"], "label_field": "code",
        "policy": {"new_record_policy": "PROPOSE_INSERT", "source_conflict_policy": "REQUIRE_REVIEW",
                   "effective_dating": {"valid_from_column": "starts", "valid_to_column": "ends"}}})
    table = compile_master_table(definition, master_id, tenant_id)
    config = {
        "dataset_business_name": "Prices", "grain": "One row per code and start date",
        "target_table": "prices", "load_strategy": "UPSERT",
        "semantic": {"code": "PRICES", "dimensions": ["code", "starts"], "metrics": []},
        "columns": [{"source_column": f.name, "target_column": f.name, "target_type": f.type,
                     "nullable": f.nullable, "is_business_key": f.name in definition.business_key}
                    for f in definition.fields],
    }
    async with SessionFactory() as session, session.begin():
        session.add(Tenant(id=tenant_id, code="be12_" + uuid4().hex))
        await session.flush()
        editor = User(tenant_id=tenant_id, username="editor", password_hash="unused", role="DATA_STEWARD")
        approver = User(tenant_id=tenant_id, username="approver", password_hash="unused",
                        role="PLATFORM_ADMIN")
        session.add_all([editor, approver])
        await session.flush()
        source = DataSource(tenant_id=tenant_id, source_code="prices", name="Prices",
                            spreadsheet_id="fixture", owner_user_id=editor.id)
        session.add(source)
        await session.flush()
        sheet = SourceSheet(tenant_id=tenant_id, source_id=source.id, sheet_id=1, sheet_name="Prices")
        session.add(sheet)
        await session.flush()
        snapshot = Snapshot(tenant_id=tenant_id, source_id=source.id, source_sheet_id=sheet.id,
                            content_hash="fixture", row_count=1, values=[])
        session.add(snapshot)
        session.add(MasterDefinition(
            id=master_id, tenant_id=tenant_id, code="prices", name="Prices", created_by=editor.id,
            definition_json=definition.model_dump(mode="json"),
            approved_definition_json=definition.model_dump(mode="json"),
            approved_version=1, status="APPROVED"))
        await session.flush()
        connection = await session.connection()
        await connection.run_sync(table.create)
        await session.execute(table.insert().values(
            _tenant_id=tenant_id, _record_id=record_id, _source_sheet_id=sheet.id,
            _source_row=2, _source_snapshot_hash="original", code="001",
            starts=date(2026, 1, 1), ends=None, price=Decimal("10")))

    async def prepare(start="2026-02-01", price="20", close=True):
        async with SessionFactory() as session, session.begin():
            review = ImportReview(
                tenant_id=tenant_id, source_id=source.id, source_sheet_id=sheet.id,
                snapshot_id=snapshot.id, created_by=editor.id, idempotency_key=uuid4().hex,
                status="READY_FOR_APPROVAL", configuration_json=config,
                dependencies={"dataset_kind": "MASTER", "master_id": master_id,
                              "snapshot_hash": "fixture", "policy": {"new_record_policy": "PROPOSE_INSERT"}})
            session.add(review)
            await session.flush()
            session.add(ImportReviewRow(
                tenant_id=tenant_id, import_review_id=review.id, source_row=3, raw_data={},
                transformed_data={"code": "001", "starts": start, "ends": None, "price": price}))
            await session.flush()
            preview = await ImportReviewService(session, editor).preview(
                review.id, ImportReviewPreviewRequest(revision_no=1, close_open_periods=close))
            await ImportReviewService(session, approver).approve(
                review.id, SimpleNamespace(revision_no=1, comment="Reviewed period closure"))
            return review.id, SimpleNamespace(revision_no=2, preview_token=preview["preview_token"])

    async def apply(prepared):
        async with SessionFactory() as session, session.begin():
            await session.execute(text("SET LOCAL statement_timeout = '10s'"))
            return await ImportReviewService(session, editor).apply(*prepared)

    async def state(review_id):
        async with SessionFactory() as session:
            rows = [dict(r) for r in (await session.execute(select(table).order_by(table.c.starts))).mappings()]
            review = await session.get(ImportReview, review_id)
            audits = (await session.scalars(select(AuditEvent).where(
                AuditEvent.tenant_id == tenant_id, AuditEvent.event == "master.period_closed"))).all()
            return rows, review, audits

    try:
        yield SimpleNamespace(prepare=prepare, apply=apply, state=state, table=table,
                              tenant_id=tenant_id, master_id=master_id, editor=editor, record_id=record_id)
    finally:
        async with SessionFactory() as session, session.begin():
            connection = await session.connection()
            await connection.run_sync(table.drop)
            for model in (AuditEvent, ImportReviewRow, ImportReview, MasterDefinition,
                          Snapshot, SourceSheet, DataSource, User):
                await session.execute(delete(model).where(model.tenant_id == tenant_id))
            await session.execute(delete(Tenant).where(Tenant.id == tenant_id))


async def test_closure_commits_identity_lineage_audit_and_blocks_retry(history):
    prepared = await history.prepare()
    output = await history.apply(prepared)
    assert (output["periods_closed"], output["rows_applied"]) == (1, 1)
    rows, review, audits = await history.state(prepared[0])
    assert len(rows) == 2 and review.status == "SUCCEEDED" and review.revision_no == 4
    assert rows[0]["_record_id"] == history.record_id and rows[0]["_revision_no"] == 2
    assert rows[0]["ends"] == rows[1]["starts"] == date(2026, 2, 1)
    assert rows[0]["price"] == Decimal("10") and rows[0]["_source_snapshot_hash"] == "original"
    assert rows[1]["_record_id"] != history.record_id and rows[1]["ends"] is None
    assert review.checkpoint["periods_closed"] == 1
    assert len(audits) == 1 and audits[0].details["after"] == "2026-02-01"
    with pytest.raises(AppError) as exc:
        await history.apply(prepared)
    assert exc.value.code == "IMPORT_REVISION_CONFLICT"
    assert (await history.state(prepared[0]))[0] == rows


async def test_insert_failure_rolls_back_closure_review_and_audit_then_can_retry(history):
    prepared = await history.prepare()
    async with SessionFactory() as session, session.begin():
        # A database failure after UPDATE has executed, not a simulated session exception.
        await session.execute(text(f'ALTER TABLE {history.table.fullname} '
                                   'ADD CONSTRAINT test_reject_new_price CHECK (price < 20)'))
    with pytest.raises(IntegrityError):
        await history.apply(prepared)
    rows, review, audits = await history.state(prepared[0])
    assert len(rows) == 1 and rows[0]["ends"] is None and rows[0]["_revision_no"] == 1
    assert review.status == "APPROVED" and review.revision_no == 2 and not audits
    async with SessionFactory() as session, session.begin():
        await session.execute(text(f'ALTER TABLE {history.table.fullname} DROP CONSTRAINT test_reject_new_price'))
    assert (await history.apply(prepared))["rows_applied"] == 1


async def test_target_change_after_approval_rejects_closure_without_writes(history):
    prepared = await history.prepare()
    async with SessionFactory() as session, session.begin():
        await session.execute(history.table.update().values(_revision_no=2))
    with pytest.raises(AppError) as exc:
        await history.apply(prepared)
    assert exc.value.code == "IMPORT_PREVIEW_STALE"
    rows, review, audits = await history.state(prepared[0])
    assert len(rows) == 1 and rows[0]["ends"] is None
    assert review.status == "APPROVED" and not audits


async def test_competing_approved_closures_wait_for_lock_then_recheck_target(history):
    first, second = await history.prepare(), await history.prepare(start="2026-03-01")
    waiting = asyncio.Event()
    contender_pid = None
    async with SessionFactory() as winner, winner.begin():
        await ImportReviewService(winner, history.editor).apply(*first)
        winner_pid = await winner.scalar(text("SELECT pg_backend_pid()"))

        async def compete():
            nonlocal contender_pid
            async with SessionFactory() as loser, loser.begin():
                await loser.execute(text("SET LOCAL statement_timeout = '10s'"))
                contender_pid = await loser.scalar(text("SELECT pg_backend_pid()"))
                connection = await loser.connection()

                def before_execute(conn, cursor, statement, parameters, context, executemany):
                    if "pg_advisory_xact_lock" in statement:
                        waiting.set()

                event.listen(connection.sync_connection, "before_cursor_execute", before_execute)
                try:
                    return await ImportReviewService(loser, history.editor).apply(*second)
                finally:
                    event.remove(connection.sync_connection, "before_cursor_execute", before_execute)

        task = asyncio.create_task(compete())
        try:
            await asyncio.wait_for(waiting.wait(), timeout=5)

            async def confirm_database_wait():
                while True:
                    blockers = await winner.scalar(text("SELECT pg_blocking_pids(:pid)"),
                                                   {"pid": contender_pid})
                    if winner_pid in blockers:
                        return
                    await asyncio.sleep(0.01)

            await asyncio.wait_for(confirm_database_wait(), timeout=5)
            assert not task.done()
        except BaseException:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise
    # Commit the first transaction before waiting for the second one to finish.
    with pytest.raises(AppError) as exc:
        await asyncio.wait_for(task, timeout=10)
    assert exc.value.code == "IMPORT_PREVIEW_STALE"
    rows, review, audits = await history.state(second[0])
    assert len(rows) == 2 and rows[1]["starts"] == date(2026, 2, 1)
    assert review.status == "APPROVED" and len(audits) == 1


async def test_identical_version_in_new_batch_is_skipped(history):
    prepared = await history.prepare(start="2026-01-01", price="10", close=False)
    output = await history.apply(prepared)
    assert output["rows_applied"] == output["periods_closed"] == 0
    rows, review, audits = await history.state(prepared[0])
    assert len(rows) == 1 and rows[0]["_revision_no"] == 1 and not audits
    assert review.status == "SUCCEEDED"


async def test_as_of_boundary_uses_new_version_in_postgres(history):
    await history.apply(await history.prepare())
    async with SessionFactory() as session:
        master = await session.get(MasterDefinition, history.master_id)
        definition = MasterSchema.model_validate(master.approved_definition_json)
        for point, expected in [("2025-12-31", None), ("2026-01-31", Decimal("10")),
                                ("2026-02-01", Decimal("20")), ("2030-01-01", Decimal("20"))]:
            prices = (await session.scalars(select(history.table.c.price).where(
                history.table.c._tenant_id == history.tenant_id,
                effective_at_condition(definition, history.table, point)))).all()
            assert prices == ([] if expected is None else [expected])


async def test_other_tenant_cannot_apply_review_or_insert_into_master(history):
    prepared = await history.prepare()
    outsider = SimpleNamespace(id=str(uuid4()), tenant_id=str(uuid4()), role="PLATFORM_ADMIN")
    with pytest.raises(AppError) as exc:
        async with SessionFactory() as session, session.begin():
            await ImportReviewService(session, outsider).apply(*prepared)
    assert exc.value.code == "RESOURCE_NOT_FOUND"
    rows, review, audits = await history.state(prepared[0])
    assert review.status == "APPROVED" and not audits
    with pytest.raises(IntegrityError):
        async with SessionFactory() as session, session.begin():
            await session.execute(history.table.insert().values(
                **{**rows[0], "_tenant_id": outsider.tenant_id, "_record_id": str(uuid4())}))
    assert (await history.state(prepared[0]))[0] == rows
