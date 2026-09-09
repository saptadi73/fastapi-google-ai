"""HTTP preview/approval/apply with real PostgreSQL; seed AI review completion."""
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_be12_append import append_config
from test_import_reviews import create, non_master
from test_integration import activate, onboard, request, sync
from test_integration import context as context

from app.core.database import SessionFactory
from app.models.import_review import ImportReview, ImportReviewRow
from app.services.append_service import append_row
from app.services.etl_compiler_service import transform_rows
from app.services.profiling_service import canonical_json
from app.services.schema_compiler_service import compile_table

pytestmark = pytest.mark.integration


async def staged(ctx, config_data, policy):
    config = append_config(config_data, policy)
    body = await non_master(ctx, config.model_dump(mode="json"))
    review = await create(ctx, body)
    table = compile_table(config, body["source_sheet_id"])
    good, issues, _ = transform_rows(ctx.values, SimpleNamespace(header_row=1, data_start_row=2), config)
    assert not issues
    async with SessionFactory() as session, session.begin():
        await (await session.connection()).run_sync(table.create)
        record = await session.get(ImportReview, review["id"])
        # Upstream provider review is outside these APPEND transaction tests.
        record.status = "READY_FOR_APPROVAL"
        record.checkpoint = {"blocking_codes": []}
        for number, values in good:
            session.add(ImportReviewRow(
                tenant_id=ctx.tenant_id, import_review_id=record.id, source_row=number,
                raw_data={}, transformed_data=json.loads(canonical_json(values))))
    return config, table, review, good


async def seed(ctx, config, table, review, row):
    async with SessionFactory() as session, session.begin():
        return await append_row(session, table, {
            **row[1], "_tenant_id": ctx.tenant_id, "_source_sheet_id": review["source_sheet_id"],
            "_source_row": row[0], "_etl_run_id": review["id"],
        }, config)


async def preview_and_approve(ctx, review):
    path = f"/import-reviews/{review['id']}"
    preview = (await request(ctx, "POST", path + "/preview", data={"revision_no": 1}))["data"]
    approved = (await request(ctx, "POST", path + "/approve", who="approver",
                              data={"revision_no": 1}))["data"]
    return path, preview, {"revision_no": approved["revision_no"], "preview_token": preview["preview_token"]}


@pytest.mark.parametrize("policy", [None, "SKIP_IDENTICAL"])
async def test_keyless_append_preview_and_apply_skip_target_and_batch_duplicates(context, config_data, policy):
    context.values.append(context.values[1].copy())
    config, table, review, good = await staged(context, config_data, policy)
    await seed(context, config, table, review, good[0])
    path, preview, body = await preview_and_approve(context, review)
    assert preview["summary"]["insert"] == 2 and preview["summary"]["unchanged"] == 2
    output = (await request(context, "POST", path + "/apply", data=body))["data"]
    assert output["rows_applied"] == 2 and output["status"] == "SUCCEEDED"
    async with SessionFactory() as session:
        rows = (await session.execute(select(table))).mappings().all()
    assert len(rows) == 3 and sorted(str(row["net_amount"]) for row in rows) == ["100", "200", "50"]


async def test_reject_identical_preview_blocks_approval(context, config_data):
    config, table, review, good = await staged(context, config_data, "REJECT_IDENTICAL")
    await seed(context, config, table, review, good[0])
    path = f"/import-reviews/{review['id']}"
    preview = (await request(context, "POST", path + "/preview", data={"revision_no": 1}))["data"]
    assert preview["summary"]["duplicate"] == 1 and not preview["can_approve"]
    error = await request(context, "POST", path + "/approve", who="approver",
                          data={"revision_no": 1}, expected=409)
    assert error["errors"][0]["code"] == "IMPORT_PREVIEW_CONFLICT"


async def test_identical_arrives_after_approval_and_rolls_back_earlier_inserts(context, config_data):
    config, table, review, good = await staged(context, config_data, "REJECT_IDENTICAL")
    path, _, body = await preview_and_approve(context, review)
    await seed(context, config, table, review, good[1])
    error = await request(context, "POST", path + "/apply", data=body, expected=409)
    assert error["errors"][0]["code"] == "APPEND_IDENTICAL_REJECTED"
    async with SessionFactory() as session:
        rows = (await session.execute(select(table))).mappings().all()
        record = await session.get(ImportReview, review["id"])
    assert len(rows) == 1 and rows[0]["transaction_id"] == "002"
    assert record.status == "APPROVED" and record.revision_no == 2


@pytest.mark.parametrize("policy", ["SKIP_IDENTICAL", "REJECT_IDENTICAL"])
async def test_legacy_sync_uses_same_append_policy(context, config_data, policy):
    config = append_config(config_data, policy)
    source_id, sheet_id, stored_config = await onboard(context, config.model_dump(mode="json"))
    await activate(context, stored_config)
    assert (await sync(context, source_id))["status"] == "SUCCEEDED"
    # A different snapshot contains a new event followed by already-loaded events.
    context.values.insert(1, ["004", "2026-09-04", "Jakarta", 75])
    job = await sync(context, source_id)
    table = compile_table(config, sheet_id)
    async with SessionFactory() as session:
        rows = (await session.execute(select(table))).mappings().all()
    if policy == "SKIP_IDENTICAL":
        assert job["status"] == "SUCCEEDED" and len(rows) == 4
        assert job["result"]["runs"][0]["rows_loaded"] == 1
    else:
        assert job["status"] == "FAILED" and job["error_code"] == "APPEND_IDENTICAL_REJECTED"
        assert len(rows) == 3 and all(row["transaction_id"] != "004" for row in rows)
