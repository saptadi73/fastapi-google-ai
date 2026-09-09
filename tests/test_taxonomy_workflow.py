"""Taxonomy review guards on real PostgreSQL; provider approval is fixture state."""
import asyncio
import json

import pytest
from sqlalchemy import select, update
from test_be12_append import append_config
from test_import_reviews import create, non_master
from test_integration import context as context
from test_integration import request

from app.core.database import SessionFactory
from app.models.import_review import ImportReview, ImportReviewRow
from app.models.taxonomy import Taxonomy, TaxonomyTerm
from app.services.etl_compiler_service import transform_rows
from app.services.profiling_service import canonical_json
from app.services.schema_compiler_service import compile_table

pytestmark = pytest.mark.integration


async def taxonomy(ctx):
    taxonomy = (await request(ctx, "POST", "/taxonomies", expected=201,
                              data={"code": "branches", "name": "Branches"}))["data"]
    terms = []
    for code in ("alpha", "beta"):
        terms.append((await request(ctx, "POST", f"/taxonomies/{taxonomy['id']}/terms", expected=201,
                                    data={"code": code, "label": code.title(), "aliases": [" SHARED "]}))["data"])
    approved = (await request(ctx, "POST", f"/taxonomies/{taxonomy['id']}/approve", who="approver"))["data"]
    return approved, terms


async def batch(ctx, config_data, *, ambiguous=False, required=True):
    from types import SimpleNamespace

    definition, terms = await taxonomy(ctx)
    for index, values in enumerate(ctx.values[1:]):
        values[2] = "shared" if ambiguous and index < 2 else "alpha"
    config_data["columns"][2].update(taxonomy_id=definition["id"], taxonomy_version=definition["version"],
                                     taxonomy_required=required)
    config = append_config(config_data, "SKIP_IDENTICAL")
    body = await non_master(ctx, config.model_dump(mode="json"))
    binding = (await request(ctx, "PUT", f"/taxonomies/source-sheets/{body['source_sheet_id']}/column-bindings",
                             data={"source_column": "Cabang", "taxonomy_id": definition["id"],
                                   "taxonomy_version": definition["version"], "required": required}))["data"]
    approved_binding = (await request(ctx, "POST", f"/taxonomies/column-bindings/{binding['id']}/approve",
                                      who="approver", data={"revision_no": binding["revision_no"]}))["data"]
    review = await create(ctx, body)
    table = compile_table(config, body["source_sheet_id"])
    good, issues, _ = transform_rows(ctx.values, SimpleNamespace(header_row=1, data_start_row=2), config)
    assert not issues
    async with SessionFactory() as session, session.begin():
        await (await session.connection()).run_sync(table.create)
        stored = await session.get(ImportReview, review["id"])
        stored.status = "NEEDS_INPUT" if ambiguous else "READY_FOR_APPROVAL"
        stored.checkpoint = {"blocking_codes": []}
        for number, values in good:
            session.add(ImportReviewRow(tenant_id=ctx.tenant_id, import_review_id=review["id"], source_row=number,
                                        raw_data={"Cabang": values["branch_name"]},
                                        transformed_data=json.loads(canonical_json(values))))
    return definition, terms, review, table, approved_binding


async def test_approved_terms_are_immutable_and_repeated_approval_does_not_change_version(context):
    definition, _ = await taxonomy(context)
    error = await request(context, "POST", f"/taxonomies/{definition['id']}/terms", expected=409,
                          data={"code": "late", "label": "Late", "aliases": ["alpha"]})
    assert error["errors"][0]["code"] == "TAXONOMY_IMMUTABLE"
    approved = (await request(context, "POST", f"/taxonomies/{definition['id']}/approve", who="approver"))["data"]
    assert approved["version"] == definition["version"]
    resolution = (await request(context, "POST", f"/taxonomies/{definition['id']}/resolve-term",
                                data={"value": "shared"}))["data"]
    assert resolution["status"] == "AMBIGUOUS" and len(resolution["candidates"]) == 2
    check = (await request(context, "POST", f"/taxonomies/{definition['id']}/validate-values",
                           data={"values": ["shared", "ALPHA", "missing"]}))["data"]
    assert check["ambiguous_values"] == ["shared"] and check["invalid_values"] == ["missing"]


async def test_preview_and_apply_store_canonical_code_without_changing_raw(context, config_data):
    _, _, review, table, _ = await batch(context, config_data)
    async with SessionFactory() as session, session.begin():
        rows = (await session.scalars(select(ImportReviewRow).where(
            ImportReviewRow.import_review_id == review["id"]))).all()
        for row in rows:
            row.raw_data = {"Cabang": " ALPHA "}
            row.transformed_data = {**row.transformed_data, "branch_name": " ALPHA "}
    path = f"/import-reviews/{review['id']}"
    preview = (await request(context, "POST", path + "/preview", data={"revision_no": 1}))["data"]
    approved = (await request(context, "POST", path + "/approve", who="approver", data={"revision_no": 1}))["data"]
    await request(context, "POST", path + "/apply", data={"revision_no": approved["revision_no"],
                                                         "preview_token": preview["preview_token"]})
    async with SessionFactory() as session:
        stored = (await session.execute(select(table))).mappings().all()
        assert stored and all(row["branch_name"] == "alpha" for row in stored)
        rows = (await session.scalars(select(ImportReviewRow).where(
            ImportReviewRow.import_review_id == review["id"]))).all()
        assert all(row.corrected_data["branch_name"] == "alpha" and row.raw_data == {"Cabang": " ALPHA "} for row in rows)


async def test_questions_are_distinct_scoped_and_selection_stores_code(context, config_data):
    definition, terms, review, _, _ = await batch(context, config_data, ambiguous=True)
    async with SessionFactory() as session:
        rows = (await session.scalars(select(ImportReviewRow).where(
            ImportReviewRow.import_review_id == review["id"]).order_by(ImportReviewRow.source_row))).all()
    url = f"/taxonomies/{definition['id']}/ambiguity-question"
    payload = {"import_review_id": review["id"], "staging_row_id": rows[0].id,
               "target_column": "branch_name", "value": "shared"}
    first = (await request(context, "POST", url, data=payload, expected=201))["data"]
    repeated = (await request(context, "POST", url, data=payload, expected=201))["data"]
    second = (await request(context, "POST", url, expected=201,
                            data={**payload, "staging_row_id": rows[1].id}))["data"]
    assert first["id"] == repeated["id"] != second["id"]
    error = await request(context, "POST", url, data={**payload, "value": "invented"}, expected=409)
    assert error["errors"][0]["code"] == "TAXONOMY_QUESTION_VALUE_STALE"
    await request(context, "POST", url, data=payload, who="outsider", expected=404)
    answer = await request(context, "POST", f"/import-reviews/{review['id']}/questions/{first['id']}/answer",
                           data={"revision_no": 1, "action": "SELECT_RECORD", "selected_candidate_id": terms[0]["id"]})
    assert answer["data"]["question"]["status"] == "ANSWERED"
    async with SessionFactory() as session:
        stored = await session.get(ImportReviewRow, rows[0].id)
        assert stored.corrected_data == {"branch_name": "alpha"}
        assert stored.raw_data == {"Cabang": "shared"}
    # A row in a different batch of the same tenant must not be accepted either.
    async with SessionFactory() as session, session.begin():
        sibling = await session.get(ImportReview, review["id"])
        other = ImportReview(tenant_id=context.tenant_id, source_id=sibling.source_id,
                             source_sheet_id=sibling.source_sheet_id, snapshot_id=sibling.snapshot_id,
                             created_by=sibling.created_by, idempotency_key="other-taxonomy-batch",
                             configuration_json=sibling.configuration_json, dependencies=sibling.dependencies)
        session.add(other)
        await session.flush()
        foreign_row = ImportReviewRow(tenant_id=context.tenant_id, import_review_id=other.id,
                                      source_row=2, raw_data={}, transformed_data={"branch_name": "shared"})
        session.add(foreign_row)
        await session.flush()
        foreign_id = foreign_row.id
    error = await request(context, "POST", url, expected=409, data={**payload, "staging_row_id": foreign_id})
    assert error["errors"][0]["code"] == "IMPORT_STAGING_MISSING"


@pytest.mark.parametrize("change", ["term", "taxonomy", "staging", "binding"])
async def test_apply_rechecks_taxonomy_after_approval(context, config_data, change):
    definition, terms, review, table, binding = await batch(context, config_data)
    path = f"/import-reviews/{review['id']}"
    preview = (await request(context, "POST", path + "/preview", data={"revision_no": 1}))["data"]
    approved = (await request(context, "POST", path + "/approve", who="approver", data={"revision_no": 1}))["data"]
    async with SessionFactory() as session, session.begin():
        if change == "term":
            await session.execute(update(TaxonomyTerm).where(TaxonomyTerm.id == terms[0]["id"]).values(is_active=False))
        elif change == "taxonomy":
            await session.execute(update(Taxonomy).where(Taxonomy.id == definition["id"]).values(version=99))
        elif change == "staging":
            await session.execute(update(ImportReviewRow).where(ImportReviewRow.import_review_id == review["id"])
                                  .values(corrected_data={"branch_name": "shared"}))
    if change == "binding":
        await request(context, "POST", f"/taxonomies/column-bindings/{binding['id']}/reject", who="approver",
                      data={"revision_no": binding["revision_no"]})
    error = await request(context, "POST", path + "/apply", expected=422 if change == "staging" else 409,
                          data={"revision_no": approved["revision_no"], "preview_token": preview["preview_token"]})
    assert error["errors"][0]["code"] == ("TAXONOMY_VALUE_AMBIGUOUS" if change == "staging" else "IMPORT_STALE_REVIEW")
    async with SessionFactory() as session:
        assert not (await session.execute(select(table))).all()


async def test_concurrent_binding_edits_have_one_winner_and_revoke_approval(context, config_data):
    definition, _, review, _, binding = await batch(context, config_data)
    path = f"/taxonomies/source-sheets/{review['source_sheet_id']}/column-bindings"
    body = {"source_column": "Cabang", "taxonomy_id": definition["id"], "taxonomy_version": definition["version"],
            "revision_no": binding["revision_no"], "required": True}
    replies = await asyncio.gather(*(context.client.put("/api/v1" + path, headers=context.headers["admin"], json=body)
                                     for _ in range(2)))
    assert sorted(response.status_code for response in replies) == [200, 409]
    stored = (await request(context, "GET", path))["data"][0]
    assert stored["revision_no"] == binding["revision_no"] + 1 and stored["status"] == "DRAFT"
    assert stored["approved_by"] is None and stored["approved_at"] is None
    error = await request(context, "POST", f"/taxonomies/column-bindings/{binding['id']}/approve", who="approver",
                          data={"revision_no": binding["revision_no"]}, expected=409)
    assert error["errors"][0]["code"] == "REVISION_CONFLICT"


async def test_optional_taxonomy_allows_blank_but_rejects_unknown_value(context, config_data):
    _, _, review, _, _ = await batch(context, config_data, required=False)
    path = f"/import-reviews/{review['id']}/preview"
    async with SessionFactory() as session, session.begin():
        await session.execute(update(ImportReviewRow).where(ImportReviewRow.import_review_id == review["id"])
                              .values(corrected_data={"branch_name": None}))
    await request(context, "POST", path, data={"revision_no": 1})
    async with SessionFactory() as session, session.begin():
        await session.execute(update(ImportReviewRow).where(ImportReviewRow.import_review_id == review["id"])
                              .values(corrected_data={"branch_name": "unknown"}))
    error = await request(context, "POST", path, data={"revision_no": 1}, expected=422)
    assert error["errors"][0]["code"] == "TAXONOMY_VALUE_INVALID"


async def test_approval_rejects_changed_taxonomy_since_preview(context, config_data):
    _, terms, review, _, _ = await batch(context, config_data)
    path = f"/import-reviews/{review['id']}"
    await request(context, "POST", path + "/preview", data={"revision_no": 1})
    async with SessionFactory() as session, session.begin():
        await session.execute(update(TaxonomyTerm).where(TaxonomyTerm.id == terms[0]["id"])
                              .values(aliases=["different"]))
    error = await request(context, "POST", path + "/approve", who="approver", expected=409,
                          data={"revision_no": 1})
    assert error["errors"][0]["code"] == "IMPORT_STALE_REVIEW"
