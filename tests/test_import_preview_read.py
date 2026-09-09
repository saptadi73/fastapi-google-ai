"""Two-account preview reads on real PostgreSQL, with AI completion seeded."""
from types import SimpleNamespace

import pytest
from sqlalchemy import select, update
from test_import_reviews import create, non_master
from test_integration import context as context
from test_integration import request

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
