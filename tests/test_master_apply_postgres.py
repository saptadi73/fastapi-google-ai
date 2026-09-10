"""BE-07 transactions on PostgreSQL; upstream freshness/provider review is seeded."""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionFactory
from app.core.exceptions import AppError
from app.models.audit import AuditEvent
from app.models.auth import Tenant, User
from app.models.etl import Snapshot
from app.models.import_review import ImportReview, ImportReviewRow
from app.models.master import MasterDefinition, MasterSourceBinding
from app.models.source import DataSource, SourceSheet
from app.schemas.import_review import ImportReviewPreviewRequest
from app.schemas.master import MasterSchema
from app.services.import_review_service import ImportReviewService
from app.services.schema_compiler_service import compile_master_table

pytestmark = pytest.mark.integration


@pytest.fixture
async def master(monkeypatch):
    monkeypatch.setattr(ImportReviewService, "is_current", AsyncMock(return_value=True))
    tenant_id, master_id, record_id = (str(uuid4()) for _ in range(3))
    definition = MasterSchema.model_validate({
        "name": "Products", "fields": [
            {"name": "code", "type": "text", "nullable": False},
            {"name": "label", "type": "text", "nullable": False}],
        "business_key": ["code"], "label_field": "label",
        "policy": {"new_record_policy": "PROPOSE_INSERT", "source_conflict_policy": "REQUIRE_REVIEW"}})
    table = compile_master_table(definition, master_id, tenant_id)
    config = {
        "dataset_business_name": "Products", "grain": "One product per code",
        "target_table": "products", "load_strategy": "UPSERT",
        "semantic": {"code": "PRODUCTS", "dimensions": ["code", "label"], "metrics": []},
        "columns": [{"source_column": f.name, "target_column": f.name, "target_type": f.type,
                     "nullable": f.nullable, "is_business_key": f.name in definition.business_key}
                    for f in definition.fields],
    }
    async with SessionFactory() as session, session.begin():
        session.add(Tenant(id=tenant_id, code="be07_" + uuid4().hex))
        await session.flush()
        editor = User(tenant_id=tenant_id, username="editor", password_hash="unused", role="DATA_STEWARD")
        approver = User(tenant_id=tenant_id, username="approver", password_hash="unused", role="PLATFORM_ADMIN")
        session.add_all([editor, approver])
        await session.flush()
        source = DataSource(tenant_id=tenant_id, source_code="products", name="Products",
                            spreadsheet_id="fixture", owner_user_id=editor.id)
        session.add(source)
        await session.flush()
        sheets = [SourceSheet(tenant_id=tenant_id, source_id=source.id, sheet_id=n, sheet_name=f"Products {n}",
                              dataset_kind="MASTER", classification_status="CONFIRMED", last_fingerprint="fixture",
                              classification_confirmed_by=editor.id,
                              classification_confirmed_at=datetime.now(timezone.utc)) for n in (1, 2)]
        sheet = sheets[0]
        session.add_all(sheets)
        await session.flush()
        snapshots = [Snapshot(tenant_id=tenant_id, source_id=source.id, source_sheet_id=item.id,
                              content_hash="fixture", row_count=1, values=[]) for item in sheets]
        session.add_all(snapshots)
        session.add(MasterDefinition(
            id=master_id, tenant_id=tenant_id, code="products", name="Products", created_by=editor.id,
            definition_json=definition.model_dump(mode="json"),
            approved_definition_json=definition.model_dump(mode="json"), approved_version=1, status="APPROVED"))
        await session.flush()
        for bound_sheet in sheets:
            session.add(MasterSourceBinding(tenant_id=tenant_id, source_sheet_id=bound_sheet.id,
                        master_definition_id=master_id, master_version=1, classification_revision=1,
                        status="APPROVED", columns_json=config["columns"], fingerprint="fixture",
                        snapshot_hash="fixture", created_by=editor.id, approved_by=approver.id))
        await (await session.connection()).run_sync(table.create)
        await session.execute(table.insert().values(
            _tenant_id=tenant_id, _record_id=record_id, _source_sheet_id=sheet.id,
            _source_row=2, _source_snapshot_hash="original", code="001", label="Original"))

    async def prepare(values=None, approve=True, source_index=0, confirm=False):
        if values is None:
            values = [{"code": "001", "label": "Updated"}, {"code": "002", "label": "New"}]
        async with SessionFactory() as session, session.begin():
            review = ImportReview(
                tenant_id=tenant_id, source_id=source.id, source_sheet_id=sheets[source_index].id,
                snapshot_id=snapshots[source_index].id, created_by=editor.id, idempotency_key=uuid4().hex,
                status="READY_FOR_APPROVAL", configuration_json=config,
                dependencies={"dataset_kind": "MASTER", "master_id": master_id,
                              "snapshot_hash": "fixture", "policy": {"master": definition.policy.model_dump(mode="json")}})
            session.add(review)
            await session.flush()
            for number, value in enumerate(values, 2):
                session.add(ImportReviewRow(tenant_id=tenant_id, import_review_id=review.id,
                                           source_row=number, raw_data=value, transformed_data=value))
            await session.flush()
            preview = await ImportReviewService(session, editor).preview(
                review.id, ImportReviewPreviewRequest(revision_no=1))
            if approve:
                await ImportReviewService(session, approver).approve(
                    review.id, SimpleNamespace(revision_no=1, comment="Reviewed", preview_hash=preview["preview_hash"],
                                               accept_source_conflicts=confirm))
            return review.id, SimpleNamespace(revision_no=2 if approve else 1,
                                             preview_token=preview["preview_token"]), preview

    async def apply(prepared):
        async with SessionFactory() as session, session.begin():
            await session.execute(text("SET LOCAL statement_timeout = '10s'"))
            return await ImportReviewService(session, editor).apply(*prepared[:2])

    async def state(review_id):
        async with SessionFactory() as session:
            rows = [dict(r) for r in (await session.execute(select(table).order_by(table.c.code))).mappings()]
            review = await session.get(ImportReview, review_id)
            audits = (await session.scalars(select(AuditEvent).where(
                AuditEvent.tenant_id == tenant_id, AuditEvent.event == "import.applied"))).all()
            return rows, review, audits

    async def policy(**changes):
        data = definition.model_dump(mode="json")
        data["policy"].update(changes)
        updated = MasterSchema.model_validate(data)
        definition.policy = updated.policy
        async with SessionFactory() as session, session.begin():
            record = await session.get(MasterDefinition, master_id)
            record.approved_definition_json = updated.model_dump(mode="json")

    try:
        yield SimpleNamespace(prepare=prepare, apply=apply, state=state, table=table,
                              tenant_id=tenant_id, editor=editor, approver=approver, record_id=record_id,
                              policy=policy, sheets=sheets, master_id=master_id)
    finally:
        async with SessionFactory() as session, session.begin():
            await (await session.connection()).run_sync(table.drop)
            for model in (AuditEvent, ImportReviewRow, ImportReview, MasterSourceBinding, MasterDefinition,
                          Snapshot, SourceSheet, DataSource, User):
                await session.execute(delete(model).where(model.tenant_id == tenant_id))
            await session.execute(delete(Tenant).where(Tenant.id == tenant_id))


async def test_upsert_preserves_identity_advances_revision_and_rejects_retry(master):
    prepared = await master.prepare()
    assert (await master.apply(prepared))["rows_applied"] == 2
    rows, review, audits = await master.state(prepared[0])
    assert rows[0]["_record_id"] == master.record_id and rows[0]["_revision_no"] == 2
    assert rows[0]["label"] == "Updated" and rows[0]["_source_snapshot_hash"] == "fixture"
    assert rows[1]["code"] == "002" and rows[1]["_record_id"] != master.record_id
    assert review.status == "SUCCEEDED" and len(audits) == 1
    with pytest.raises(AppError, match="Revisi"):
        await master.apply(prepared)
    assert (await master.state(prepared[0]))[0] == rows


@pytest.mark.parametrize("values,outcome", [
    ([{"code": None, "label": "Invalid"}], "KEY_CONFLICT"),
    ([{"code": "", "label": "Invalid"}], "KEY_CONFLICT"),
    ([{"code": "001", "label": "A"}, {"code": "001", "label": "B"}], "DUPLICATE"),
    ([{}], "INVALID"),
])
async def test_invalid_keys_block_approval_and_direct_apply(master, values, outcome):
    prepared = await master.prepare(values, approve=False)
    assert not prepared[2]["can_approve"]
    assert outcome in {c["outcome"] for c in prepared[2]["changes"]}
    async with SessionFactory() as session, session.begin():
        with pytest.raises(AppError) as exc:
            await ImportReviewService(session, master.approver).approve(
                prepared[0], SimpleNamespace(revision_no=1, comment=""))
        assert exc.value.code == "IMPORT_PREVIEW_CONFLICT"
    with pytest.raises(AppError) as exc:
        await master.apply(prepared)
    assert exc.value.code == "IMPORT_APPROVAL_REQUIRED"
    rows, review, audits = await master.state(prepared[0])
    assert len(rows) == 1 and rows[0]["label"] == "Original" and not audits
    assert review.status == "READY_FOR_APPROVAL"


async def test_insert_failure_rolls_back_earlier_update_and_allows_retry(master):
    prepared = await master.prepare()
    async with SessionFactory() as session, session.begin():
        await session.execute(text(f"ALTER TABLE {master.table.fullname} "
                                   "ADD CONSTRAINT reject_new CHECK (code <> '002')"))
    with pytest.raises(IntegrityError):
        await master.apply(prepared)
    rows, review, audits = await master.state(prepared[0])
    assert len(rows) == 1 and rows[0]["label"] == "Original" and rows[0]["_revision_no"] == 1
    assert review.status == "APPROVED" and review.revision_no == 2 and not audits
    async with SessionFactory() as session, session.begin():
        await session.execute(text(f"ALTER TABLE {master.table.fullname} DROP CONSTRAINT reject_new"))
    assert (await master.apply(prepared))["rows_applied"] == 2


async def test_unchanged_rows_preserve_revision_and_missing_records_are_kept(master):
    prepared = await master.prepare([{"code": "001", "label": "Original"}])
    before = (await master.state(prepared[0]))[0]
    assert (await master.apply(prepared))["rows_applied"] == 0
    assert (await master.state(prepared[0]))[0] == before
    second = await master.prepare([{"code": "002", "label": "New"}])
    assert (await master.apply(second))["rows_applied"] == 1
    rows, _, _ = await master.state(second[0])
    assert len(rows) == 2 and rows[0] == before[0]


@pytest.mark.parametrize("change", ["target", "staging"])
async def test_changes_after_approval_cannot_be_applied_with_old_token(master, change):
    prepared = await master.prepare()
    async with SessionFactory() as session, session.begin():
        if change == "target":
            await session.execute(master.table.update().values(label="Concurrent", _revision_no=2))
        else:
            await session.execute(ImportReviewRow.__table__.update().where(
                ImportReviewRow.import_review_id == prepared[0]).values(corrected_data={"label": "Unapproved"}))
    with pytest.raises(AppError) as exc:
        await master.apply(prepared)
    assert exc.value.code == "IMPORT_PREVIEW_STALE"
    rows, review, audits = await master.state(prepared[0])
    assert len(rows) == 1 and rows[0]["label"] == ("Concurrent" if change == "target" else "Original")
    assert review.status == "APPROVED" and not audits


async def test_two_approved_imports_wait_then_reject_stale_target(master):
    first, second = await master.prepare(), await master.prepare()
    contender_pid = None
    started = asyncio.Event()
    async with SessionFactory() as winner, winner.begin():
        await ImportReviewService(winner, master.editor).apply(*first[:2])
        winner_pid = await winner.scalar(text("SELECT pg_backend_pid()"))

        async def compete():
            nonlocal contender_pid
            async with SessionFactory() as loser, loser.begin():
                await loser.execute(text("SET LOCAL statement_timeout = '10s'"))
                contender_pid = await loser.scalar(text("SELECT pg_backend_pid()"))
                started.set()
                return await ImportReviewService(loser, master.editor).apply(*second[:2])

        task = asyncio.create_task(compete())
        try:
            await asyncio.wait_for(started.wait(), timeout=5)

            async def confirm_wait():
                while winner_pid not in await winner.scalar(
                    text("SELECT pg_blocking_pids(:pid)"), {"pid": contender_pid}
                ):
                    await asyncio.sleep(0.01)

            await asyncio.wait_for(confirm_wait(), timeout=5)
            assert not task.done()
        except BaseException:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise
    with pytest.raises(AppError) as exc:
        await asyncio.wait_for(task, timeout=10)
    assert exc.value.code == "IMPORT_PREVIEW_STALE"
    rows, review, audits = await master.state(second[0])
    assert len(rows) == 2 and review.status == "APPROVED" and len(audits) == 1
