"""Two-account preview reads on real PostgreSQL, with AI completion seeded."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from sqlalchemy import select, update
from test_import_reviews import create, non_master
from test_integration import context as context
from test_integration import request

from app.core.config import get_settings
from app.core.database import SessionFactory
from app.models.configuration import Configuration
from app.models.import_review import ImportReview, ImportReviewRow
from app.schemas.configuration import ETLConfiguration
from app.services.etl_compiler_service import transform_rows
from app.services.import_review_service import ImportReviewService
from app.services.profiling_service import digest
from app.services.schema_compiler_service import compile_table

pytestmark = pytest.mark.integration


async def test_read_canonical_taxonomy_preview_does_not_write_corrections(context, config_data):
    from test_taxonomy_workflow import batch

    _, _, review, _, _ = await batch(context, config_data)
    path = f"/import-reviews/{review['id']}"
    preview = (await request(context, "POST", path + "/preview", data={"revision_no": 1}))["data"]
    async with SessionFactory() as session, session.begin():
        rows = (await session.scalars(select(ImportReviewRow).where(
            ImportReviewRow.import_review_id == review["id"]))).all()
        for row in rows:
            row.transformed_data = {**row.transformed_data, "branch_name": " ALPHA "}
            row.corrected_data = {}
    # Equivalent category spelling keeps the canonical plan unchanged.
    reader = (await request(context, "GET", path + "/preview", who="approver"))["data"]
    assert reader["preview_hash"] == preview["preview_hash"]
    assert all(c["after"]["branch_name"] == "alpha" for c in reader["changes"])
    async with SessionFactory() as session:
        rows = (await session.scalars(select(ImportReviewRow).where(
            ImportReviewRow.import_review_id == review["id"]))).all()
        assert all(row.corrected_data == {} and row.transformed_data["branch_name"] == " ALPHA " for row in rows)


async def staged(ctx, data):
    data["columns"][2]["pii_classification"] = "HIGH"
    data["semantic"]["dimensions"].remove("branch_name")
    config = ETLConfiguration.model_validate(data)
    body = await non_master(ctx, config.model_dump(mode="json"))
    review = await create(ctx, body)
    table = compile_table(config, body["source_sheet_id"])
    good, issues, _ = transform_rows(ctx.values, SimpleNamespace(header_row=1, data_start_row=2), config)
    assert not issues
    async with SessionFactory() as session, session.begin():
        await (await session.connection()).run_sync(table.create)
        stored = await session.get(ImportReview, review["id"])
        stored.status, stored.checkpoint = "READY_FOR_APPROVAL", {"blocking_codes": []}
        for number, values in good:
            session.add(ImportReviewRow(tenant_id=ctx.tenant_id, import_review_id=review["id"], source_row=number,
                                        raw_data={"Cabang": values["branch_name"]},
                                        transformed_data=ImportReviewService.json_value(values)))
        before = {**good[0][1], "branch_name": "sensitive-before", "net_amount": 777}
        await session.execute(table.insert().values(**before, _tenant_id=ctx.tenant_id,
            _source_sheet_id=body["source_sheet_id"], _source_row=2, _etl_run_id=review["id"], _row_hash=digest(before)))
    return review, table


async def test_reviewer_reads_same_hash_masked_without_mutation_then_approves(context, config_data):
    review, table = await staged(context, config_data)
    path = f"/import-reviews/{review['id']}"
    error = await request(context, "GET", path + "/preview", who="approver", expected=409)
    assert error["errors"][0]["code"] == "IMPORT_PREVIEW_REQUIRED"
    editor = (await request(context, "POST", path + "/preview", data={"revision_no": 1}))["data"]
    async with SessionFactory() as session:
        before = (await session.get(ImportReview, review["id"])).checkpoint
        staging_before = [(r.transformed_data, r.corrected_data) for r in (await session.scalars(
            select(ImportReviewRow).where(ImportReviewRow.import_review_id == review["id"])
            .order_by(ImportReviewRow.source_row))).all()]
    for who, expected in [("viewer", 403), ("outsider", 404)]:
        await request(context, "GET", path + "/preview", who=who, expected=expected)
    await request(context, "POST", path + "/preview", who="approver", expected=403, data={"revision_no": 1})
    reader = (await request(context, "GET", path + "/preview", who="approver"))["data"]
    assert reader["read_only"] and "preview_token" not in reader
    assert reader["preview_hash"] == editor["preview_hash"] and reader["preview_revision"] == 1
    assert reader["summary"] == editor["summary"] and reader["can_approve"]
    assert reader["masked_fields"] == ["branch_name"]
    assert reader["changes"][0]["before"]["branch_name"] == "[REDACTED]"
    assert reader["changes"][0]["after"]["branch_name"] == "[REDACTED]"
    assert editor["changes"][0]["before"]["branch_name"] == "sensitive-before"
    assert reader["changes"][0]["before"]["net_amount"] == 777
    async with SessionFactory() as session:
        stored = await session.get(ImportReview, review["id"])
        assert stored.revision_no == 1 and stored.checkpoint == before
        assert [(r.transformed_data, r.corrected_data) for r in (await session.scalars(
            select(ImportReviewRow).where(ImportReviewRow.import_review_id == review["id"])
            .order_by(ImportReviewRow.source_row))).all()] == staging_before
    await request(context, "POST", path + "/approve", who="approver", expected=409,
                  data={"revision_no": 1, "preview_hash": "0" * 64})
    approved = (await request(context, "POST", path + "/approve", who="approver",
                             data={"revision_no": 1, "preview_hash": reader["preview_hash"]}))["data"]
    after = (await request(context, "GET", path + "/preview", who="approver"))["data"]
    assert after["preview_hash"] == reader["preview_hash"] and not after["can_approve"]
    await request(context, "POST", path + "/apply", data={"revision_no": approved["revision_no"],
                                                         "preview_token": editor["preview_token"]})
    async with SessionFactory() as session:
        values = (await session.execute(select(table).order_by(table.c.transaction_id))).mappings().all()
        assert len(values) == 3 and values[0]["net_amount"] == 100
        assert values[0]["transaction_date"].isoformat() == "2026-09-01"


async def test_owner_applies_clean_preview_without_second_approver(context, config_data, monkeypatch):
    monkeypatch.setattr(get_settings(), "etl_owner_workflow_enabled", True)
    review, table = await staged(context, config_data)
    path = f"/import-reviews/{review['id']}"
    preview = (await request(context, "POST", path + "/preview", data={"revision_no": 1}))["data"]

    result = (await request(context, "POST", path + "/apply", data={
        "revision_no": 1,
        "preview_token": preview["preview_token"],
        "preview_hash": preview["preview_hash"],
    }))["data"]

    assert result["status"] == "SUCCEEDED"
    assert result["review"]["checkpoint"]["approval_mode"] == "OWNER_VALIDATED"
    assert result["review"]["checkpoint"]["approved_by"]
    async with SessionFactory() as session:
        values = (await session.execute(select(table).order_by(table.c.transaction_id))).mappings().all()
        assert len(values) == 3


async def test_legacy_defaults_allow_preview_and_owner_apply(context, config_data, monkeypatch):
    monkeypatch.setattr(get_settings(), "etl_owner_workflow_enabled", True)
    review, _ = await staged(context, config_data)
    async with SessionFactory() as session, session.begin():
        stored = await session.get(ImportReview, review["id"])
        legacy = deepcopy(stored.configuration_json)
        for column in legacy["columns"]:
            column.pop("master_reference", None)
            column.pop("master_reference_disabled", None)
        deps = {**stored.dependencies, "configuration_hash": digest(legacy)}
        stored.configuration_json, stored.dependencies, stored.idempotency_key = legacy, deps, digest(deps)
    path = f"/import-reviews/{review['id']}"
    detail = (await request(context, "GET", path))["data"]
    assert detail["dependencies_current"] and detail["status"] == "READY_FOR_APPROVAL"
    preview = (await request(context, "POST", path + "/preview", data={"revision_no": 1}))["data"]
    result = (await request(context, "POST", path + "/apply", data={
        "revision_no": 1, "preview_token": preview["preview_token"], "preview_hash": preview["preview_hash"],
    }))["data"]
    assert result["status"] == "SUCCEEDED"
    assert result["review"]["checkpoint"]["approval_mode"] == "OWNER_VALIDATED"


async def test_keyed_append_keeps_existing_values_and_counts_only_inserts(context, config_data, monkeypatch):
    monkeypatch.setattr(get_settings(), "etl_owner_workflow_enabled", True)
    config_data["load_strategy"] = "APPEND"
    review, table = await staged(context, config_data)
    path = f"/import-reviews/{review['id']}"
    preview = (await request(context, "POST", path + "/preview", data={"revision_no": 1}))["data"]
    assert preview["summary"]["unchanged"] == 1 and preview["summary"]["update"] == 0
    assert preview["changes"][0]["reason_code"] == "APPEND_KEY_EXISTS"
    result = (await request(context, "POST", path + "/apply", data={
        "revision_no": 1, "preview_token": preview["preview_token"], "preview_hash": preview["preview_hash"],
    }))["data"]
    assert result["status"] == "SUCCEEDED" and result["rows_applied"] == 2
    async with SessionFactory() as session:
        records = (await session.execute(select(table).order_by(table.c.transaction_id))).mappings().all()
        assert len(records) == 3 and records[0]["net_amount"] == 777
        assert records[0]["branch_name"] == "sensitive-before"


async def test_stale_readiness_and_replacement_use_active_config_and_latest_snapshot(context, config_data):
    from app.models.etl import Snapshot
    from app.models.source import SourceSheet

    review, _ = await staged(context, config_data)
    path = f"/import-reviews/{review['id']}"
    async with SessionFactory() as session, session.begin():
        old = await session.get(ImportReview, review["id"])
        previous = await session.get(Configuration, old.dependencies["configuration_id"])
        previous.status = "SUPERSEDED"
        successor = Configuration(
            tenant_id=previous.tenant_id, source_id=previous.source_id, source_sheet_id=previous.source_sheet_id,
            version_no=previous.version_no + 1, revision_no=1, status="ACTIVE",
            based_on_fingerprint=previous.based_on_fingerprint, configuration_json=previous.configuration_json,
            created_by=previous.created_by,
        )
        session.add(successor)
        await session.flush()
        sheet = await session.get(SourceSheet, old.source_sheet_id)
        sheet.active_configuration_id = successor.id
        snapshot = await session.get(Snapshot, old.snapshot_id)
        values = deepcopy(snapshot.values)
        values[1][3] = 999
        latest = Snapshot(tenant_id=snapshot.tenant_id, source_id=snapshot.source_id,
                          source_sheet_id=snapshot.source_sheet_id, values=values,
                          content_hash=digest(values), row_count=snapshot.row_count)
        session.add(latest)
        await session.flush()
        config_id, snapshot_id = successor.id, latest.id
    detail = (await request(context, "GET", path))["data"]
    assert detail["status"] == "STALE_REVIEW" and detail["stored_status"] == "READY_FOR_APPROVAL"
    listing = (await request(context, "GET", "/import-reviews"))["data"]["items"]
    assert next(r for r in listing if r["id"] == review["id"])["status"] == "STALE_REVIEW"
    ready = (await request(context, "GET", "/import-reviews?status=READY_FOR_APPROVAL"))["data"]["items"]
    stale = (await request(context, "GET", "/import-reviews?status=STALE_REVIEW"))["data"]["items"]
    assert not ready and any(r["id"] == review["id"] for r in stale)
    await request(context, "POST", path + "/preview", data={"revision_no": 1}, expected=409)
    result = (await request(context, "POST", path + "/revalidate", data={"revision_no": 1}))["data"]
    new = result["replacement_review"]
    assert new["id"] != review["id"] and new["configuration_id"] == config_id
    assert new["snapshot_id"] == snapshot_id and new["status"] == "VALIDATING"
    assert "approved_by" not in new["checkpoint"] and "preview_hash" not in new["checkpoint"]
    repeated = (await request(context, "POST", path + "/revalidate", data={"revision_no": result["revision_no"]}))["data"]
    assert repeated["replacement_review_id"] == new["id"] and repeated["replacement_reused"]
    await request(context, "POST", path + "/revalidate", who="outsider", data={"revision_no": result["revision_no"]}, expected=404)


@pytest.mark.parametrize("change", ["target", "staging", "dependency", "revision"])
async def test_read_and_approval_reject_stale_preview(context, config_data, change):
    review, table = await staged(context, config_data)
    path = f"/import-reviews/{review['id']}"
    preview = (await request(context, "POST", path + "/preview", data={"revision_no": 1}))["data"]
    async with SessionFactory() as session, session.begin():
        stored = await session.get(ImportReview, review["id"])
        if change == "target":
            await session.execute(update(table).values(net_amount=888))
        elif change == "staging":
            await session.execute(update(ImportReviewRow).where(ImportReviewRow.import_review_id == review["id"])
                                  .values(corrected_data={"net_amount": 999}))
        elif change == "dependency":
            config = await session.get(Configuration, stored.dependencies["configuration_id"])
            config.revision_no += 1
        else:
            stored.revision_no += 1
    error = await request(context, "GET", path + "/preview", who="approver", expected=409)
    assert error["errors"][0]["code"] in ("IMPORT_PREVIEW_STALE", "IMPORT_STALE_REVIEW")
    await request(context, "POST", path + "/approve", who="approver", expected=409,
                  data={"revision_no": 2 if change == "revision" else 1, "preview_hash": preview["preview_hash"]})
