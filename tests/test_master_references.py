"""BE-08 PostgreSQL resolution, lifecycle, and final-write dependency gates."""
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from test_master_apply_postgres import master as master

from app.core.database import SessionFactory
from app.core.exceptions import AppError
from app.models.etl import Snapshot
from app.models.import_review import ImportReview, ImportReviewRow
from app.models.master import MasterColumnBinding, MasterDefinition
from app.schemas.configuration import ETLConfiguration
from app.schemas.import_review import ImportReferenceResolveRequest, ImportReviewPreviewRequest
from app.schemas.master import MasterColumnBindingCreate
from app.services.import_review_service import ImportReviewService
from app.services.master_service import MasterService
from app.services.schema_compiler_service import compile_table

pytestmark = pytest.mark.integration


@pytest.fixture
async def reference(master):
    sheet = master.sheets[1]
    config = ETLConfiguration.model_validate({
        "dataset_business_name": "Transactions", "grain": "One transaction", "target_table": "references",
        "load_strategy": "UPSERT", "columns": [
            {"source_column": "ID", "target_column": "code", "target_type": "text", "is_business_key": True, "nullable": False},
            {"source_column": "Product", "target_column": "product_id", "target_type": "uuid"}],
        "semantic": {"code": "TRANSACTIONS", "dimensions": ["code"], "metrics": []}})
    table = compile_table(config, sheet.id)
    async with SessionFactory() as session, session.begin():
        snapshot = await session.scalar(select(Snapshot).where(Snapshot.source_sheet_id == sheet.id))
        batch = ImportReview(tenant_id=master.tenant_id, source_id=sheet.source_id, source_sheet_id=sheet.id,
                             snapshot_id=snapshot.id, created_by=master.editor.id, idempotency_key=uuid4().hex,
                             status="READY_FOR_APPROVAL", configuration_json=config.model_dump(mode="json"),
                             dependencies={"dataset_kind": "NON_MASTER", "snapshot_hash": "fixture", "policy": {}})
        session.add(batch)
        await session.flush()
        row = ImportReviewRow(tenant_id=master.tenant_id, import_review_id=batch.id, source_row=2,
                              raw_data={"ID": "T1", "Product": "001"},
                              transformed_data={"code": "T1", "product_id": None})
        session.add(row)
        await session.flush()
        await (await session.connection()).run_sync(table.create)

    async def bind(revision=0, aliases=None, required=True, approve=True, field="code", source_sheet=None):
        async with SessionFactory() as session, session.begin():
            saved = await MasterService(session, master.editor).save_column_binding(
                source_sheet or sheet.id, MasterColumnBindingCreate(
                    revision_no=revision, source_column="Product", master_definition_id=master.master_id,
                    master_field=field, master_version=1, required=required,
                    aliases=aliases or {}))
            if approve:
                return await MasterService(session, master.approver).column_binding_decision(
                    saved["id"], SimpleNamespace(revision_no=saved["revision_no"]))
            return saved

    async def resolve(value="001", write=False, user=None, revision=None, **overrides):
        async with SessionFactory() as session, session.begin():
            stored = await session.get(ImportReview, batch.id)
            data = {"revision_no": revision or stored.revision_no, "master_definition_id": master.master_id,
                    "source_column": "Product", "value": value}
            if write:
                data.update(staging_row_id=row.id, target_column="product_id")
            data.update(overrides)
            return await ImportReviewService(session, user or master.editor).resolve_reference(
                batch.id, ImportReferenceResolveRequest(**data))

    async def preview(approve=False):
        async with SessionFactory() as session, session.begin():
            stored = await session.get(ImportReview, batch.id)
            result = await ImportReviewService(session, master.editor).preview(
                batch.id, ImportReviewPreviewRequest(revision_no=stored.revision_no))
            if approve:
                await ImportReviewService(session, master.approver).approve(
                    batch.id, SimpleNamespace(revision_no=stored.revision_no, comment="Approved references"))
            return result

    async def apply(preview):
        async with SessionFactory() as session, session.begin():
            stored = await session.get(ImportReview, batch.id)
            return await ImportReviewService(session, master.editor).apply(
                batch.id, SimpleNamespace(revision_no=stored.revision_no, preview_token=preview["preview_token"]))

    try:
        yield SimpleNamespace(**{**vars(master), "bind": bind, "resolve": resolve, "preview": preview, "apply": apply,
                                 "batch_id": batch.id, "row_id": row.id, "consumer": table, "sheet_id": sheet.id})
    finally:
        async with SessionFactory() as session, session.begin():
            await (await session.connection()).run_sync(table.drop)
            await session.execute(delete(MasterColumnBinding).where(MasterColumnBinding.tenant_id == master.tenant_id))


async def test_exact_resolution_preserves_raw_and_loads_uuid(reference):
    await reference.bind()
    result = await reference.resolve(write=True)
    assert result["status"] == "EXACT" and result["staging_updated"] and result["revision_no"] == 2
    async with SessionFactory() as session:
        row = await session.get(ImportReviewRow, reference.row_id)
        assert row.raw_data["Product"] == "001" and row.corrected_data["product_id"] == reference.record_id
    assert (await reference.apply(await reference.preview(approve=True)))["rows_applied"] == 1
    async with SessionFactory() as session:
        assert str(await session.scalar(select(reference.consumer.c.product_id))) == reference.record_id


async def test_alias_is_scoped_to_batch_sheet_and_edits_revoke_approval(reference):
    await reference.bind(aliases={"local": reference.record_id})
    await reference.bind(aliases={"elsewhere": reference.record_id}, source_sheet=reference.sheets[0].id)
    assert (await reference.resolve("local"))["status"] == "ALIAS"
    assert (await reference.resolve("elsewhere"))["status"] == "NOT_FOUND"
    draft = await reference.bind(revision=2, aliases={"new": reference.record_id}, approve=False)
    assert draft["status"] == "DRAFT" and draft["approved_by"] is None and draft["approved_at"] is None
    with pytest.raises(AppError) as exc:
        await reference.resolve("new")
    assert exc.value.code == "REFERENCE_BINDING_REQUIRED"


@pytest.mark.parametrize("required", [True, False])
async def test_empty_reference_respects_optionality(reference, required):
    await reference.bind(required=required)
    result = await reference.resolve(" ", write=True)
    assert result["requires_question"] is required
    if required:
        with pytest.raises(AppError) as exc:
            await reference.preview()
        assert exc.value.code == "REFERENCE_REQUIRED"
    else:
        assert result["status"] == "EMPTY" and result["staging_updated"]
        assert (await reference.apply(await reference.preview(approve=True)))["rows_applied"] == 1


async def test_missing_and_ambiguous_values_never_write_staging(reference):
    await reference.bind(field="label")
    async with SessionFactory() as session, session.begin():
        await session.execute(reference.table.insert().values(
            _tenant_id=reference.tenant_id, _record_id=str(uuid4()), _source_sheet_id=reference.sheets[0].id,
            _source_row=3, _source_snapshot_hash="fixture", code="002", label="Original"))
    result = await reference.resolve("original", write=True)
    assert result["status"] == "AMBIGUOUS" and len(result["candidates"]) == 2
    assert not result["staging_updated"] and result["requires_question"]
    missing = await reference.resolve("unknown-zzzz", write=True)
    assert missing["status"] == "NOT_FOUND" and missing["requires_question"]
    async with SessionFactory() as session:
        assert (await session.get(ImportReviewRow, reference.row_id)).corrected_data == {}


@pytest.mark.parametrize("change", ["alias", "record", "inactive_record", "inactive_master", "version"])
@pytest.mark.parametrize("approved", [False, True])
async def test_dependency_change_blocks_approval_or_apply(reference, change, approved):
    await reference.bind(aliases={"local": reference.record_id})
    await reference.resolve("local", write=True)
    preview = await reference.preview(approve=approved)
    if change == "alias":
        await reference.bind(revision=2, aliases={"different": reference.record_id})
    else:
        async with SessionFactory() as session, session.begin():
            if change in ("record", "inactive_record"):
                await session.execute(reference.table.update().values(
                    **({"label": "Changed", "_revision_no": 2} if change == "record" else {"_is_active": False})))
            else:
                master = await session.get(MasterDefinition, reference.master_id)
                if change == "version":
                    master.approved_version += 1
                else:
                    master.is_active = False
    with pytest.raises(AppError) as exc:
        if approved:
            await reference.apply(preview)
        else:
            async with SessionFactory() as session, session.begin():
                batch = await session.get(ImportReview, reference.batch_id)
                await ImportReviewService(session, reference.approver).approve(
                    batch.id, SimpleNamespace(revision_no=batch.revision_no, comment="Old preview"))
    assert exc.value.code in {"REFERENCE_RESOLUTION_STALE", "MASTER_ALIAS_INVALID", "REFERENCE_BINDING_STALE",
                              "MASTER_NOT_APPROVED"}
    async with SessionFactory() as session:
        assert not (await session.execute(select(reference.consumer))).all()


async def test_terminal_and_wrong_target_writes_are_rejected(reference):
    await reference.bind()
    with pytest.raises(AppError) as exc:
        await reference.resolve(write=True, target_column="code")
    assert exc.value.code == "REFERENCE_MAPPING_INVALID"
    with pytest.raises(AppError) as exc:
        await reference.resolve(write=True, staging_row_id=str(uuid4()))
    assert exc.value.code == "IMPORT_STAGING_MISSING"
    await reference.resolve(write=True)
    await reference.preview(approve=True)
    with pytest.raises(AppError) as exc:
        await reference.resolve(write=True)
    assert exc.value.code == "IMPORT_STATE_CONFLICT"


async def test_sensitive_fields_are_masked_and_not_searchable(reference):
    await reference.bind()
    async with SessionFactory() as session, session.begin():
        master = await session.get(MasterDefinition, reference.master_id)
        data = dict(master.approved_definition_json)
        data["fields"] = [{**field, "pii_classification": "HIGH" if field["name"] == "label" else "NONE"}
                          for field in data["fields"]]
        master.approved_definition_json = data
    reader = SimpleNamespace(id=reference.approver.id, tenant_id=reference.tenant_id, role="TECHNICAL_APPROVER")
    result = await reference.resolve(user=reader)
    assert result["record"]["label"] == "[REDACTED]"
    with pytest.raises(AppError) as exc:
        await reference.resolve(user=reader, write=True)
    assert exc.value.code == "FORBIDDEN"
    await reference.bind(revision=2, field="label")
    with pytest.raises(AppError) as exc:
        await reference.resolve("Original", user=reader)
    assert exc.value.code == "REFERENCE_SEARCH_FORBIDDEN"


async def test_candidate_and_inactive_record_are_never_auto_selected(reference):
    await reference.bind()
    candidate = await reference.resolve("Origina", write=True)
    assert candidate["status"] == "CANDIDATE" and candidate["requires_question"] and not candidate["staging_updated"]
    async with SessionFactory() as session, session.begin():
        await session.execute(reference.table.update().values(_is_active=False))
    missing = await reference.resolve("001", write=True)
    assert missing["status"] == "NOT_FOUND" and not missing["staging_updated"]


async def test_binding_creation_and_approval_are_serialized(reference):
    outcomes = await asyncio.gather(reference.bind(approve=False), reference.bind(approve=False), return_exceptions=True)
    assert sum(isinstance(result, dict) for result in outcomes) == 1
    error = next(result for result in outcomes if isinstance(result, AppError))
    assert error.code == "MASTER_COLUMN_BINDING_CONFLICT"
    binding = next(result for result in outcomes if isinstance(result, dict))

    async def approve():
        async with SessionFactory() as session, session.begin():
            return await MasterService(session, reference.approver).column_binding_decision(
                binding["id"], SimpleNamespace(revision_no=1))

    outcomes = await asyncio.gather(approve(), approve(), return_exceptions=True)
    assert sum(isinstance(result, dict) for result in outcomes) == 1
    assert next(result for result in outcomes if isinstance(result, AppError)).code == "MASTER_COLUMN_BINDING_CONFLICT"


@pytest.mark.parametrize("aliases", [{"bad": str(uuid4())}, {"A": "RECORD", " a ": "RECORD"}])
async def test_alias_uuid_and_normalized_uniqueness_checked_on_save(reference, aliases):
    aliases = {key: reference.record_id if value == "RECORD" else value for key, value in aliases.items()}
    with pytest.raises(AppError) as exc:
        await reference.bind(aliases=aliases)
    assert exc.value.code == "MASTER_ALIAS_INVALID"


async def test_alias_target_rechecked_at_binding_approval(reference):
    binding = await reference.bind(aliases={"local": reference.record_id}, approve=False)
    async with SessionFactory() as session, session.begin():
        await session.execute(reference.table.update().values(_is_active=False))
    async with SessionFactory() as session, session.begin():
        with pytest.raises(AppError) as exc:
            await MasterService(session, reference.approver).column_binding_decision(
                binding["id"], SimpleNamespace(revision_no=1))
        assert exc.value.code == "MASTER_ALIAS_INVALID"
    async with SessionFactory() as session:
        stored = await session.get(MasterColumnBinding, binding["id"])
        assert stored.status == "DRAFT" and stored.revision_no == 1


async def test_other_tenant_and_stale_revision_cannot_resolve(reference):
    await reference.bind()
    outsider = SimpleNamespace(id=str(uuid4()), tenant_id=str(uuid4()), role="PLATFORM_ADMIN")
    with pytest.raises(AppError) as exc:
        await reference.resolve(user=outsider)
    assert exc.value.code == "RESOURCE_NOT_FOUND"
    await reference.resolve(write=True)
    with pytest.raises(AppError) as exc:
        await reference.resolve(write=True, revision=1)
    assert exc.value.code == "IMPORT_REVISION_CONFLICT"


async def test_optional_does_not_allow_foreign_uuid_or_label(reference):
    await reference.bind(required=False)
    for value, code in [(str(uuid4()), "REFERENCE_RECORD_UNAVAILABLE"), ("Original", "REFERENCE_UNRESOLVED")]:
        async with SessionFactory() as session, session.begin():
            row = await session.get(ImportReviewRow, reference.row_id)
            row.corrected_data = {"product_id": value}
        with pytest.raises(AppError) as exc:
            await reference.preview()
        assert exc.value.code == code


async def test_one_to_one_blocks_repeated_record_with_different_transaction_keys(reference):
    binding = await reference.bind()
    async with SessionFactory() as session, session.begin():
        stored = await session.get(MasterColumnBinding, binding["id"])
        stored.cardinality = "ONE_TO_ONE"
        row = await session.get(ImportReviewRow, reference.row_id)
        row.corrected_data = {"product_id": reference.record_id}
        session.add(ImportReviewRow(tenant_id=reference.tenant_id, import_review_id=reference.batch_id,
                    source_row=3, raw_data={}, transformed_data={"code": "T2", "product_id": reference.record_id}))
    with pytest.raises(AppError) as exc:
        await reference.preview()
    assert exc.value.code == "REFERENCE_CARDINALITY_CONFLICT"


async def test_resolver_http_requires_binding_column_and_complete_staging_pair(reference, monkeypatch):
    import httpx

    from app.api.dependencies import current_user
    from app.main import app

    await reference.bind()
    monkeypatch.setitem(app.dependency_overrides, current_user, lambda: reference.editor)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        path = f"/api/v1/import-reviews/{reference.batch_id}/resolve-reference"
        body = {"revision_no": 1, "master_definition_id": reference.master_id, "value": "001"}
        assert (await client.post(path, json=body)).status_code == 422
        body["source_column"] = "Product"
        assert (await client.post(path, json={**body, "staging_row_id": reference.row_id})).status_code == 422
        response = await client.post(path, json={**body, "staging_row_id": reference.row_id, "target_column": "product_id"})
        assert response.status_code == 200, response.text
        assert response.json()["data"]["record"]["_record_id"] == reference.record_id
