from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.schemas.master import MasterSchema
from app.services.effective_dating_service import validate_versions


@pytest.fixture
def definition():
    return MasterSchema.model_validate({
        "name": "Price history", "fields": [
            {"name": "code", "type": "text", "nullable": False},
            {"name": "starts", "type": "date", "nullable": False},
            {"name": "ends", "type": "date"}, {"name": "price", "type": "numeric", "nullable": False}],
        "business_key": ["code", "starts"], "label_field": "code",
        "policy": {"new_record_policy": "PROPOSE_INSERT", "source_conflict_policy": "REQUIRE_REVIEW",
                   "effective_dating": {"valid_from_column": "starts", "valid_to_column": "ends"}}})


def row(start="2026-01-01", end="2026-02-01", **changes):
    return {"code": "001", "starts": start, "ends": end, "price": "10", **changes}


def test_adjacent_versions_preserve_history_and_idempotence(definition):
    old = row()
    candidates, identical = validate_versions(definition, [old, row("2026-02-01", None, price="20")], [old])
    assert candidates[1]["price"] == Decimal("20")
    assert identical == {("001", date(2026, 1, 1))}
    assert old["price"] == "10"


@pytest.mark.parametrize("incoming,existing,code", [
    ([row(end="2026-01-01")], [], "MASTER_PERIOD_INVALID"),
    ([row(start=None)], [], "MASTER_PERIOD_INVALID"),
    ([row(price="invalid")], [], "MASTER_PERIOD_INVALID"),
    ([row(), row()], [], "MASTER_VERSION_DUPLICATE"),
    ([row(price="20")], [row()], "MASTER_VERSION_IMMUTABLE"),
    ([row(end="2026-03-01")], [row()], "MASTER_VERSION_IMMUTABLE"),
    ([row("2026-01-15", "2026-03-01")], [row()], "MASTER_PERIOD_OVERLAP"),
    ([row("2026-02-01", None)], [row(end=None)], "MASTER_PERIOD_OVERLAP"),
    ([row(), row("2026-01-15", None)], [], "MASTER_PERIOD_OVERLAP"),
])
def test_invalid_versions(definition, incoming, existing, code):
    with pytest.raises(AppError) as exc:
        validate_versions(definition, incoming, existing)
    assert exc.value.code == code


def test_other_entities_and_gaps_allowed(definition):
    validate_versions(definition, [row("2026-03-01", None), row(code="002")], [row()])


@pytest.mark.parametrize("keys", [["code"], ["starts"], ["code", "starts", "ends"]])
def test_explicit_version_identity_required(definition, keys):
    data = definition.model_dump(mode="json")
    data["business_key"] = keys
    with pytest.raises(ValidationError):
        MasterSchema.model_validate(data)


async def test_apply_revalidates_after_lock_and_skips_identical(definition, monkeypatch):
    from app.services import import_review_service as module
    from app.services.schema_compiler_service import compile_master_table

    tenant, master_id = str(uuid4()), str(uuid4())
    table = compile_master_table(definition, master_id, tenant)
    stored = [row()]
    result = Mock()
    result.mappings.return_value.all.side_effect = lambda: stored
    session = SimpleNamespace(execute=AsyncMock(return_value=result), connection=AsyncMock())
    service = module.ImportReviewService(session, SimpleNamespace(id=str(uuid4()), tenant_id=tenant))
    review = SimpleNamespace(id=str(uuid4()), tenant_id=tenant, status="APPROVED", source_sheet_id=str(uuid4()),
                             dependencies={"dataset_kind": "MASTER", "master_id": master_id, "snapshot_hash": "x"},
                             checkpoint={"preview_revision": 1, "preview_hash": "hash"})
    rows = [SimpleNamespace(source_row=2, transformed_data=row(), corrected_data={})]
    service._preview_context = AsyncMock(return_value=(review, None, rows))
    monkeypatch.setattr(module, "reference_context", AsyncMock(return_value={}))
    service.read_preview = AsyncMock(return_value={"blocking_codes": [], "requires_source_confirmation": False,
                                                  "changes": []})
    service.role = Mock()
    service.move = Mock()
    service.response = Mock(return_value={})
    monkeypatch.setattr(module.MasterStorageService, "target", AsyncMock(return_value=(None, definition, table)))
    monkeypatch.setattr(module, "audit", Mock())
    monkeypatch.setattr(module, "decode", lambda *args: {"review_id": review.id, "tenant_id": tenant,
                                                       "revision_no": 1, "preview_hash": "hash"})
    data = SimpleNamespace(revision_no=2, preview_token="token")
    output = await service.apply(review.id, data)
    assert output["rows_applied"] == 0
    calls = session.execute.call_args_list
    assert "pg_advisory_xact_lock" in str(calls[0].args[0])
    assert all(not str(call.args[0]).startswith("INSERT") for call in calls)
    session.execute.reset_mock()
    service.move.reset_mock()
    rows[0].transformed_data = row("2026-01-15", None)
    with pytest.raises(AppError) as exc:
        await service.apply(review.id, data)
    assert exc.value.code == "MASTER_PERIOD_OVERLAP"
    service.move.assert_not_called()
    assert all(not str(call.args[0]).startswith("INSERT") for call in session.execute.call_args_list)
    session.execute.reset_mock()
    rows[0].transformed_data = row("2026-02-01", None, price="20")
    output = await service.apply(review.id, data)
    assert output["rows_applied"] == 1
    statements = [call.args[0] for call in session.execute.call_args_list if str(call.args[0]).startswith("INSERT")]
    assert len(statements) == 1 and "ON CONFLICT" not in str(statements[0])
    assert statements[0].compile().params["starts"] == date(2026, 2, 1)


def test_disabling_history_requires_migration(definition):
    from app.services.schema_compiler_service import validate_master_evolution

    proposed = definition.model_copy(deep=True)
    proposed.policy.effective_dating = None
    with pytest.raises(AppError) as exc:
        validate_master_evolution(definition, proposed)
    assert exc.value.code == "MASTER_SCHEMA_MIGRATION_REQUIRED"


async def test_attribute_update_cannot_rewrite_history(definition):
    from app.services.master_storage_service import MasterStorageService

    service = MasterStorageService(Mock(), SimpleNamespace(id=str(uuid4()), tenant_id=str(uuid4())))
    service.require_role = Mock()
    service.target = AsyncMock(return_value=(None, definition, None))
    with pytest.raises(AppError) as exc:
        await service.update_attributes(str(uuid4()), str(uuid4()), 1, {"price": "20"})
    assert exc.value.code == "MASTER_VERSION_IMMUTABLE"


def test_offset_normalization_for_version_identity(definition):
    data = definition.model_dump(mode="json")
    for field in data["fields"]:
        if field["name"] in ("starts", "ends"):
            field["type"] = "timestamptz"
    definition = MasterSchema.model_validate(data)
    _, identical = validate_versions(definition, [row("2026-01-01T07:00:00+07:00", None)],
                                     [row("2026-01-01T00:00:00Z", None)])
    assert len(identical) == 1


def test_unknown_staging_fields_rejected(definition):
    with pytest.raises(AppError) as exc:
        validate_versions(definition, [row(unmapped="ignored?")], [])
    assert exc.value.code == "MASTER_PERIOD_INVALID"


@pytest.mark.parametrize("as_of,expected", [("2025-12-31", []), ("2026-01-01", ["v1"]),
                                            ("2026-01-31", ["v1"]), ("2026-02-01", ["v2"]),
                                            ("2099-01-01", ["v2"])])
def test_as_of_half_open_intervals(definition, as_of, expected):
    from sqlalchemy import Column, Date, MetaData, String, Table, create_engine, select

    from app.services.effective_dating_service import effective_at_condition

    # In-memory SQL behavior test; does not claim PostgreSQL integration coverage.
    table = Table("versions", MetaData(), Column("code", String), Column("starts", Date), Column("ends", Date))
    engine = create_engine("sqlite://")
    try:
        table.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(table.insert(), [{"code": "v1", "starts": date(2026, 1, 1), "ends": date(2026, 2, 1)},
                                          {"code": "v2", "starts": date(2026, 2, 1), "ends": None}])
            assert conn.execute(select(table.c.code).where(effective_at_condition(definition, table, as_of))).scalars().all() == expected
    finally:
        engine.dispose()


@pytest.mark.parametrize("kind,value,valid", [
    ("date", "2026-02-30", False), ("date", "20260101", False),
    ("date", "2026-01-01T00:00:00Z", False), ("date", "' OR 1=1 --", False),
    ("timestamp", "2026-01-01T00:00:00", True), ("timestamp", "2026-01-01T00:00:00Z", False),
    ("timestamptz", "2026-01-01T07:00:00+07:00", True), ("timestamptz", "2026-01-01T00:00:00", False),
])
def test_as_of_type_contract(definition, kind, value, valid):
    from app.services.effective_dating_service import effective_at_condition
    from app.services.schema_compiler_service import compile_master_table

    for field in definition.fields:
        if field.name in ("starts", "ends"):
            field.type = kind
    table = compile_master_table(definition, str(uuid4()), str(uuid4()))
    if valid:
        predicate = effective_at_condition(definition, table, value)
        assert value not in str(predicate)
        if kind == "timestamptz":
            assert next(iter(predicate.compile().params.values())).hour == 0
    else:
        with pytest.raises(AppError) as exc:
            effective_at_condition(definition, table, value)
        assert exc.value.code == "MASTER_AS_OF_INVALID"


def test_as_of_forbids_sensitive_period_filter_and_non_temporal_master(definition):
    from app.services.effective_dating_service import effective_at_condition

    with pytest.raises(AppError) as exc:
        effective_at_condition(definition, None, "2026-01-01", masked_fields={"starts"})
    assert exc.value.code == "MASTER_PERIOD_FILTER_FORBIDDEN"
    definition.policy.effective_dating = None
    with pytest.raises(AppError) as exc:
        effective_at_condition(definition, None, "2026-01-01")
    assert exc.value.code == "MASTER_EFFECTIVE_DATING_REQUIRED"


async def test_record_query_keeps_tenant_scope_masking_and_pagination(definition):
    from app.services.master_storage_service import MasterStorageService
    from app.services.schema_compiler_service import compile_master_table

    tenant = str(uuid4())
    table = compile_master_table(definition, str(uuid4()), tenant)
    definition.fields[-1].pii_classification = "HIGH"
    result = Mock()
    result.mappings.return_value.all.return_value = [{"code": "001"}, {"code": "002"}]
    session = SimpleNamespace(execute=AsyncMock(return_value=result), connection=AsyncMock())
    service = MasterStorageService(session, SimpleNamespace(tenant_id=tenant, role="TECHNICAL_APPROVER"))
    service.target = AsyncMock(return_value=(None, definition, table))
    output = await service.records(str(uuid4()), limit=1, as_of="2026-01-01")
    stmt = session.execute.call_args.args[0]
    assert "price" not in stmt.selected_columns.keys()
    assert tenant in stmt.compile().params.values()
    assert "_is_active IS true" in str(stmt)
    assert "starts <=" in str(stmt) and "ends >" in str(stmt)
    assert output == {"items": [{"code": "001", "price": "***"}], "has_more": True, "masked_fields": ["price"]}


async def test_as_of_http_parameter_contract_and_roles(monkeypatch):
    import httpx
    from fastapi import FastAPI

    from app.api.dependencies import current_user, get_session
    from app.api.v1.masters import router
    from app.core.exceptions import install_handlers
    from app.services.master_storage_service import MasterStorageService

    api = FastAPI()
    api.include_router(router)
    install_handlers(api)
    user = SimpleNamespace(role="TECHNICAL_APPROVER", tenant_id=str(uuid4()))
    api.dependency_overrides[current_user] = lambda: user
    api.dependency_overrides[get_session] = lambda: None
    records = AsyncMock(return_value={"items": [], "has_more": False, "masked_fields": []})
    monkeypatch.setattr(MasterStorageService, "records", records)
    path = f"/master-definitions/{uuid4()}/records"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://test") as client:
        point = "2026-02-01T12:00:00+07:00"
        response = await client.get(path, params={"as_of": point})
        assert response.status_code == 200
        assert records.call_args.args[-1] == point
        assert response.json()["meta"] == {"offset": 0, "limit": 50}
        for invalid in ("", "x" * 65):
            assert (await client.get(path, params={"as_of": invalid})).status_code == 422
        assert records.await_count == 1
        user.role = "VIEWER"
        assert (await client.get(path, params={"as_of": point})).status_code == 403
        assert records.await_count == 1



def open_record(**changes):
    return {**row(end=None), "_record_id": "11111111-1111-4111-8111-111111111111", "_revision_no": 3,
            "_is_active": True, **changes}


def test_closure_plan_preserves_attributes_and_proposes_only_end(definition):
    from app.services.effective_dating_service import plan_version_closures

    original = open_record()
    typed, identical, closures = plan_version_closures(definition, [row("2026-02-01", None, price="20")], [original])
    assert not identical and typed[0]["price"] == Decimal("20")
    assert closures == [{"record_id": original["_record_id"], "revision_no": 3, "column": "ends",
                         "before": None, "after": date(2026, 2, 1)}]
    assert original["ends"] is None and original["price"] == "10"


@pytest.mark.parametrize("incoming,existing,code", [
    ([row("2025-12-01", None)], [open_record()], "MASTER_PERIOD_OVERLAP"),
    ([row(price="20", end=None)], [open_record()], "MASTER_VERSION_IMMUTABLE"),
    ([row(end="2026-02-01")], [open_record()], "MASTER_VERSION_IMMUTABLE"),
    ([row("2026-02-01", None)], [open_record(_is_active=False)], "MASTER_PERIOD_CLOSURE_INVALID"),
    ([row("2026-02-01", None)], [open_record(_revision_no=None)], "MASTER_PERIOD_CLOSURE_INVALID"),
    ([row("2026-02-01", None), row("2026-03-01", None)], [open_record()], "MASTER_PERIOD_OVERLAP"),
])
def test_closure_rejects_invalid_history_edits(definition, incoming, existing, code):
    from app.services.effective_dating_service import plan_version_closures

    with pytest.raises(AppError) as exc:
        plan_version_closures(definition, incoming, existing)
    assert exc.value.code == code


def test_closure_hash_detects_target_and_staging_changes():
    from app.services.effective_dating_service import version_plan_hash

    a, b = open_record(), open_record(code="002")
    incoming = [row("2026-02-01", None)]
    original = version_plan_hash(incoming, [a, b])
    assert version_plan_hash(incoming, [b, a]) == original
    assert version_plan_hash(incoming, [{**a, "_revision_no": 4}, b]) != original
    assert version_plan_hash([row("2026-03-01", None)], [a, b]) != original


@pytest.fixture
def closure_service(definition, monkeypatch):
    from app.services import import_review_service as module
    from app.services.effective_dating_service import version_plan_hash
    from app.services.schema_compiler_service import compile_master_table

    tenant, master_id = str(uuid4()), str(uuid4())
    table = compile_master_table(definition, master_id, tenant)
    stored = [open_record()]
    result = Mock(rowcount=1)
    mappings = MagicMock()
    mappings.__iter__.side_effect = lambda: iter(stored)
    mappings.all.side_effect = lambda: stored
    result.mappings.return_value = mappings
    session = SimpleNamespace(execute=AsyncMock(return_value=result), connection=AsyncMock())
    user = SimpleNamespace(id=str(uuid4()), tenant_id=tenant, role="PLATFORM_ADMIN")
    service = module.ImportReviewService(session, user)
    rows = [SimpleNamespace(source_row=2, transformed_data=row("2026-02-01", None, price="20"), corrected_data={})]
    review = SimpleNamespace(id=str(uuid4()), tenant_id=tenant, revision_no=1, status="APPROVED", source_sheet_id=str(uuid4()),
                             dependencies={"dataset_kind": "MASTER", "master_id": master_id, "snapshot_hash": "x", "policy": {}},
                             checkpoint={"preview_revision": 1, "preview_hash": "hash", "close_open_periods": True,
                                         "effective_plan_hash": version_plan_hash([rows[0].transformed_data], stored)})
    service._preview_context = AsyncMock(return_value=(review, SimpleNamespace(columns=[]), rows))
    monkeypatch.setattr(module, "reference_context", AsyncMock(return_value={}))
    service.read_preview = AsyncMock(return_value={"blocking_codes": [], "requires_source_confirmation": False,
                                                  "changes": []})
    stored[0]["_source_sheet_id"] = review.source_sheet_id
    review.checkpoint["effective_plan_hash"] = version_plan_hash([rows[0].transformed_data], stored)
    service.role = Mock()
    service.move = Mock()
    service.response = Mock(return_value={})
    monkeypatch.setattr(module.MasterStorageService, "target", AsyncMock(return_value=(None, definition, table)))
    events = Mock()
    monkeypatch.setattr(module, "audit", events)
    monkeypatch.setattr(module, "decode", lambda *args: {"review_id": review.id, "tenant_id": tenant,
                                                       "revision_no": 1, "preview_hash": "hash"})
    return service, review, rows, stored, result, events


async def test_closure_apply_updates_once_then_inserts_and_audits(closure_service):
    service, review, rows, stored, result, events = closure_service
    output = await service.apply(review.id, SimpleNamespace(revision_no=2, preview_token="token"))
    assert output["periods_closed"] == 1 and output["rows_applied"] == 1
    statements = [call.args[0] for call in service.session.execute.call_args_list]
    assert "pg_advisory_xact_lock" in str(statements[0])
    update = next(stmt for stmt in statements if str(stmt).startswith("UPDATE"))
    insert = next(stmt for stmt in statements if str(stmt).startswith("INSERT"))
    assert statements.index(update) < statements.index(insert)
    assert "ends IS NULL" in str(update) and "_revision_no =" in str(update)
    params = update.compile().params
    assert params["ends"] == date(2026, 2, 1) and "price" not in params
    assert review.tenant_id in params.values() and stored[0]["_record_id"] in params.values()
    assert any(call.args[2] == "master.period_closed" for call in events.call_args_list)


async def test_closure_stale_target_blocks_before_mutation(closure_service):
    service, review, rows, stored, result, events = closure_service
    stored[0]["_revision_no"] += 1
    with pytest.raises(AppError) as exc:
        await service.apply(review.id, SimpleNamespace(revision_no=2, preview_token="token"))
    assert exc.value.code == "IMPORT_PREVIEW_STALE"
    service.move.assert_not_called()
    assert not any(str(c.args[0]).startswith(("UPDATE", "INSERT")) for c in service.session.execute.call_args_list)


async def test_closure_revision_failure_does_not_insert(closure_service):
    service, review, rows, stored, result, events = closure_service
    result.rowcount = 0
    with pytest.raises(AppError) as exc:
        await service.apply(review.id, SimpleNamespace(revision_no=2, preview_token="token"))
    assert exc.value.code == "MASTER_RECORD_REVISION_CONFLICT"
    assert not any(str(c.args[0]).startswith("INSERT") for c in service.session.execute.call_args_list)
    events.assert_not_called()


async def test_closure_preview_contains_signed_plan_and_approved_plan_is_frozen(closure_service):
    from app.schemas.import_review import ImportReviewPreviewRequest
    from app.services.workbook_service import decode

    service, review, rows, stored, result, events = closure_service
    review.status = "READY_FOR_APPROVAL"
    preview = await service.preview(review.id, ImportReviewPreviewRequest(revision_no=1, close_open_periods=True))
    assert preview["period_closures"][0]["after"] == "2026-02-01"
    assert review.checkpoint["periods_to_close"] == 1
    assert decode(preview["preview_token"], "import-review-preview")["preview_hash"] == preview["preview_hash"]
    approved_hash = preview["preview_hash"]
    review.status = "APPROVED"
    rows[0].transformed_data = row("2026-03-01", None, price="20")
    with pytest.raises(AppError) as exc:
        await service.preview(review.id, ImportReviewPreviewRequest(revision_no=1, close_open_periods=True))
    assert exc.value.code == "IMPORT_PREVIEW_STALE"
    assert review.checkpoint["preview_hash"] == approved_hash


async def test_revalidate_approved_batch_discards_closure_approval(closure_service):
    from app.domain.import_workflow import ImportAction
    from app.services.import_review_service import ImportReviewService

    service, review, rows, stored, result, events = closure_service
    review.generation = 1
    review.checkpoint.update(approved_by="reviewer", approval_comment="approved", periods_to_close=1,
                             source_conflicts_approved_hash="old-confirmation")
    service.locked = AsyncMock(return_value=review)
    service.is_current = AsyncMock(return_value=True)
    service.queue = AsyncMock()
    service.move = ImportReviewService.move.__get__(service, ImportReviewService)
    await service.action(review.id, SimpleNamespace(revision_no=1, comment="review again"), ImportAction.REVALIDATE)
    assert review.status == "VALIDATING" and review.generation == 2
    assert all(key not in review.checkpoint for key in (
        "preview_hash", "approved_by", "close_open_periods", "effective_plan_hash", "source_conflicts_approved_hash"))
    service.queue.assert_awaited_once()


def test_closure_requires_insert_policy_and_sensitive_period_access(definition):
    from app.services.effective_dating_service import plan_version_closures
    from app.services.import_review_service import ImportReviewService

    definition.policy.new_record_policy = "UPDATE_ONLY"
    with pytest.raises(AppError) as exc:
        plan_version_closures(definition, [row("2026-02-01", None)], [open_record()])
    assert exc.value.code == "MASTER_PERIOD_CLOSURE_INVALID"
    definition.fields[1].pii_classification = "HIGH"
    service = ImportReviewService(Mock(), SimpleNamespace(tenant_id=str(uuid4()), role="TECHNICAL_APPROVER"))
    with pytest.raises(AppError) as exc:
        service.check_closure_visibility(definition, [True])
    assert exc.value.code == "MASTER_PERIOD_FILTER_FORBIDDEN"


async def test_closure_preview_approval_apply_with_real_token(closure_service, monkeypatch):
    from app.schemas.import_review import ImportReviewPreviewRequest
    from app.services import import_review_service as module
    from app.services.workbook_service import decode

    service, review, rows, stored, result, events = closure_service
    del service.read_preview  # Exercise the real policy/preview gate in this service-flow test.
    monkeypatch.setattr(module, "decode", decode)
    review.status = "READY_FOR_APPROVAL"
    review.created_by = str(uuid4())
    service.locked = AsyncMock(return_value=review)
    service.move = module.ImportReviewService.move.__get__(service, module.ImportReviewService)
    preview = await service.preview(review.id, ImportReviewPreviewRequest(revision_no=1, close_open_periods=True))
    await service.approve(review.id, SimpleNamespace(revision_no=1, comment="close and insert"))
    assert review.status == "APPROVED" and review.revision_no == 2
    output = await service.apply(review.id, SimpleNamespace(revision_no=2, preview_token=preview["preview_token"]))
    assert output["status"] == "SUCCEEDED" and output["periods_closed"] == 1 and output["rows_applied"] == 1
    assert review.revision_no == 4
