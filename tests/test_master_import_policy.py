"""Real PostgreSQL policy gates with upstream review seeded by the transaction fixture."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_effective_dating_postgres import history as history
from test_master_apply_postgres import master as master

from app.core.database import SessionFactory
from app.core.exceptions import AppError
from app.models.audit import AuditEvent
from app.models.import_review import ImportReview
from app.models.master import MasterSourceBinding
from app.services.import_review_service import ImportReviewService

pytestmark = pytest.mark.integration


async def approve(master, prepared, **kwargs):
    async with SessionFactory() as session, session.begin():
        return await ImportReviewService(session, master.approver).approve(
            prepared[0], SimpleNamespace(revision_no=1, comment="Reviewed conflicting source",
                                        **kwargs))


async def test_update_only_blocks_mixed_batch_and_cannot_bypass_approval(master):
    await master.policy(new_record_policy="UPDATE_ONLY")
    prepared = await master.prepare(approve=False)
    preview = prepared[2]
    assert preview["summary"]["update"] == 1 and preview["summary"]["invalid"] == 1
    assert preview["changes"][1]["reason_code"] == "MASTER_INSERT_FORBIDDEN"
    with pytest.raises(AppError) as exc:
        await approve(master, prepared)
    assert exc.value.code == "IMPORT_PREVIEW_CONFLICT"
    # Even a legacy approved checkpoint cannot bypass the final policy gate.
    async with SessionFactory() as session, session.begin():
        review = await session.get(ImportReview, prepared[0])
        review.status, review.revision_no = "APPROVED", 2
        review.checkpoint = {**review.checkpoint, "preview_blockers": []}
    prepared[1].revision_no = 2
    with pytest.raises(AppError) as exc:
        await master.apply(prepared)
    assert exc.value.code == "IMPORT_PREVIEW_CONFLICT"
    rows, _, audits = await master.state(prepared[0])
    assert len(rows) == 1 and rows[0]["label"] == "Original" and not audits


async def test_update_only_allows_existing_and_propose_insert_labels_new_rows(master):
    await master.policy(new_record_policy="UPDATE_ONLY")
    prepared = await master.prepare([{"code": "001", "label": "Updated"}])
    assert (await master.apply(prepared))["rows_applied"] == 1
    await master.policy(new_record_policy="PROPOSE_INSERT")
    proposed = await master.prepare([{"code": "002", "label": "New"}], approve=False)
    assert proposed[2]["summary"]["insert_proposed"] == 1 and proposed[2]["summary"]["insert"] == 0
    with pytest.raises(AppError) as exc:
        await master.apply(proposed)
    assert exc.value.code == "IMPORT_APPROVAL_REQUIRED"
    await approve(master, proposed)
    proposed[1].revision_no = 2
    assert (await master.apply(proposed))["rows_applied"] == 1


@pytest.mark.parametrize("kwargs", [{}, {"accept_source_conflicts": True}, {"preview_hash": "0" * 64}])
async def test_cross_source_updates_need_explicit_hash_bound_confirmation(master, kwargs):
    prepared = await master.prepare([{"code": "001", "label": "Other source"}], approve=False, source_index=1)
    assert prepared[2]["requires_source_confirmation"]
    assert prepared[2]["source_conflicts"] == [{"source_row": 2, "record_id": master.record_id}]
    with pytest.raises(AppError) as exc:
        await approve(master, prepared, **kwargs)
    assert exc.value.code in {"IMPORT_SOURCE_CONFIRMATION_REQUIRED", "IMPORT_PREVIEW_STALE"}


async def test_confirmed_source_conflict_is_audited_and_apply_requires_evidence(master):
    prepared = await master.prepare([{"code": "001", "label": "Other source"}], source_index=1, confirm=True)
    async with SessionFactory() as session, session.begin():
        evidence = await session.scalar(select(AuditEvent).where(
            AuditEvent.tenant_id == master.tenant_id, AuditEvent.event == "import.source_conflicts_approved"))
        assert evidence.user_id == master.approver.id
        assert evidence.details["preview_hash"] == prepared[2]["preview_hash"]
        review = await session.get(ImportReview, prepared[0])
        checkpoint = dict(review.checkpoint)
        review.checkpoint = {k: v for k, v in checkpoint.items() if k != "source_conflicts_approved_hash"}
    with pytest.raises(AppError) as exc:
        await master.apply(prepared)
    assert exc.value.code == "IMPORT_SOURCE_CONFIRMATION_REQUIRED"
    async with SessionFactory() as session, session.begin():
        review = await session.get(ImportReview, prepared[0])
        review.checkpoint = checkpoint
    assert (await master.apply(prepared))["rows_applied"] == 1
    rows, _, _ = await master.state(prepared[0])
    assert rows[0]["_source_sheet_id"] == master.sheets[1].id


async def test_identical_cross_source_values_do_not_require_confirmation(master):
    prepared = await master.prepare([{"code": "001", "label": "Original"}], source_index=1)
    assert not prepared[2]["requires_source_confirmation"]
    assert (await master.apply(prepared))["rows_applied"] == 0
    assert (await master.state(prepared[0]))[0][0]["_source_sheet_id"] == master.sheets[0].id


async def test_authority_blocks_other_source_even_with_confirmation(master):
    await master.policy(source_conflict_policy="AUTHORITATIVE_SOURCE",
                        authoritative_source_sheet_id=master.sheets[0].id)
    blocked = await master.prepare([{"code": "001", "label": "Unauthorized"}], approve=False, source_index=1)
    assert blocked[2]["changes"][0]["reason_code"] == "MASTER_SOURCE_FORBIDDEN"
    with pytest.raises(AppError) as exc:
        await approve(master, blocked, accept_source_conflicts=True, preview_hash=blocked[2]["preview_hash"])
    assert exc.value.code == "IMPORT_PREVIEW_CONFLICT"
    allowed = await master.prepare([{"code": "001", "label": "Authoritative"}])
    assert (await master.apply(allowed))["rows_applied"] == 1


@pytest.mark.parametrize("change", ["policy", "binding", "missing_authority", "disabled", "fingerprint", "version"])
async def test_policy_and_authority_changes_invalidate_approved_apply(master, change):
    await master.policy(source_conflict_policy="AUTHORITATIVE_SOURCE",
                        authoritative_source_sheet_id=master.sheets[0].id)
    prepared = await master.prepare()
    if change == "policy":
        await master.policy(new_record_policy="UPDATE_ONLY")
    elif change == "missing_authority":
        await master.policy(authoritative_source_sheet_id=str(uuid4()))
    else:
        from app.models.source import SourceSheet

        async with SessionFactory() as session, session.begin():
            binding = await session.scalar(select(MasterSourceBinding).where(
                MasterSourceBinding.source_sheet_id == master.sheets[0].id))
            if change == "disabled":
                sheet = await session.get(SourceSheet, master.sheets[0].id)
                sheet.enabled = False
            elif change == "fingerprint":
                binding.fingerprint = "outdated"
            elif change == "version":
                binding.master_version = 2
            else:
                binding.status = "REJECTED"
    with pytest.raises(AppError) as exc:
        await master.apply(prepared)
    assert exc.value.code in {"IMPORT_PREVIEW_STALE", "MASTER_AUTHORITY_INVALID"}
    rows, review, audits = await master.state(prepared[0])
    assert len(rows) == 1 and rows[0]["label"] == "Original" and review.status == "APPROVED" and not audits


async def test_closing_period_from_different_source_requires_confirmation(history):
    async with SessionFactory() as session, session.begin():
        await session.execute(history.table.update().values(_source_sheet_id=str(uuid4())))
    with pytest.raises(AppError) as exc:
        await history.prepare()
    assert exc.value.code == "IMPORT_SOURCE_CONFIRMATION_REQUIRED"
    prepared = await history.prepare(confirm=True)
    assert (await history.apply(prepared))["periods_closed"] == 1


async def test_update_only_blocks_new_effective_version_without_closure(history):
    from datetime import date

    from app.models.master import MasterDefinition

    async with SessionFactory() as session, session.begin():
        record = await session.get(MasterDefinition, history.master_id)
        data = dict(record.approved_definition_json)
        data["policy"] = {**data["policy"], "new_record_policy": "UPDATE_ONLY"}
        record.approved_definition_json = data
        await session.execute(history.table.update().values(ends=date(2026, 2, 1)))
    with pytest.raises(AppError) as exc:
        await history.prepare(close=False)
    assert exc.value.code == "IMPORT_PREVIEW_CONFLICT"


async def test_non_authoritative_source_cannot_close_period(history):
    from datetime import datetime, timezone

    from app.models.master import MasterDefinition
    from app.models.source import SourceSheet

    async with SessionFactory() as session, session.begin():
        original_id = await session.scalar(select(history.table.c._source_sheet_id))
        original = await session.get(SourceSheet, original_id)
        authority = SourceSheet(tenant_id=history.tenant_id, source_id=original.source_id,
                                sheet_id=2, sheet_name="Authority", dataset_kind="MASTER",
                                classification_status="CONFIRMED", last_fingerprint="fixture",
                                classification_confirmed_by=history.editor.id,
                                classification_confirmed_at=datetime.now(timezone.utc))
        session.add(authority)
        await session.flush()
        session.add(MasterSourceBinding(tenant_id=history.tenant_id, source_sheet_id=authority.id,
                    master_definition_id=history.master_id, master_version=1, classification_revision=1,
                    status="APPROVED", columns_json=[], fingerprint="fixture", snapshot_hash="fixture",
                    created_by=history.editor.id))
        record = await session.get(MasterDefinition, history.master_id)
        data = dict(record.approved_definition_json)
        data["policy"] = {**data["policy"], "source_conflict_policy": "AUTHORITATIVE_SOURCE",
                          "authoritative_source_sheet_id": authority.id}
        record.approved_definition_json = data
    with pytest.raises(AppError) as exc:
        await history.prepare(confirm=True)
    assert exc.value.code == "MASTER_SOURCE_FORBIDDEN"


async def test_authority_cannot_reference_other_tenant(master, history):
    async with SessionFactory() as session:
        foreign_id = await session.scalar(select(history.table.c._source_sheet_id))
    await master.policy(source_conflict_policy="AUTHORITATIVE_SOURCE", authoritative_source_sheet_id=foreign_id)
    with pytest.raises(AppError) as exc:
        await master.prepare()
    assert exc.value.code == "MASTER_AUTHORITY_INVALID"


async def test_http_conflict_confirmation_contract(master, monkeypatch):
    import httpx

    from app.api.dependencies import current_user
    from app.main import app

    prepared = await master.prepare([{"code": "001", "label": "Reviewed via HTTP"}],
                                    approve=False, source_index=1)
    monkeypatch.setitem(app.dependency_overrides, current_user, lambda: master.approver)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        path = f"/api/v1/import-reviews/{prepared[0]}/approve"
        body = {"revision_no": 1, "preview_hash": prepared[2]["preview_hash"], "comment": "Prefer corrected source"}
        response = await client.post(path, json=body)
        assert response.status_code == 409
        assert response.json()["errors"][0]["code"] == "IMPORT_SOURCE_CONFIRMATION_REQUIRED"
        response = await client.post(path, json={**body, "accept_source_conflicts": True, "comment": "   "})
        assert response.status_code == 409
        monkeypatch.setitem(app.dependency_overrides, current_user, lambda: master.editor)
        response = await client.post(path, json={**body, "accept_source_conflicts": True})
        assert response.status_code == 403
        monkeypatch.setitem(app.dependency_overrides, current_user, lambda: master.approver)
        response = await client.post(path, json={**body, "accept_source_conflicts": True})
        assert response.status_code == 200, response.text
