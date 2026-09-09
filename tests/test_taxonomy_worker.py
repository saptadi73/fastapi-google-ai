"""Automatic taxonomy questions use the real import worker and PostgreSQL."""
import pytest
from sqlalchemy import select
from test_import_reviews import create, detail, non_master
from test_integration import context as context
from test_integration import request
from test_taxonomy_workflow import taxonomy

from app.core.database import SessionFactory
from app.models.import_review import ImportReviewRow
from app.workers.runner import run_pending

pytestmark = pytest.mark.integration


async def test_worker_blocks_canonical_business_key_collision(context, config_data):
    definition, _ = await taxonomy(context)
    for row, value in zip(context.values[1:], [" ALPHA ", "alpha", "beta"]):
        row[2] = value
    config_data["columns"][0]["is_business_key"] = False
    config_data["columns"][2].update(taxonomy_id=definition["id"], taxonomy_version=definition["version"],
                                    taxonomy_required=True, is_business_key=True, nullable=False)
    body = await non_master(context, config_data)
    binding = (await request(context, "PUT", f"/taxonomies/source-sheets/{body['source_sheet_id']}/column-bindings",
                             data={"source_column": "Cabang", "taxonomy_id": definition["id"],
                                   "taxonomy_version": definition["version"], "required": True}))["data"]
    await request(context, "POST", f"/taxonomies/column-bindings/{binding['id']}/approve", who="approver",
                  data={"revision_no": binding["revision_no"]})
    review = await create(context, body)
    await run_pending(context.tenant_id)
    waiting = await detail(context, review)
    assert waiting["status"] == "NEEDS_INPUT"
    assert waiting["checkpoint"]["blocking_codes"] == ["TAXONOMY_KEY_COLLISION"]
    await request(context, "POST", f"/import-reviews/{review['id']}/resume", expected=409,
                  data={"revision_no": waiting["revision_no"]})


@pytest.mark.parametrize("explicit_rule", [False, True])
async def test_worker_normalizes_and_questions_then_resumes_without_duplicates(context, config_data, explicit_rule):
    definition, terms = await taxonomy(context)
    for row, value in zip(context.values[1:], [" ALPHA ", "shared", "unknown"]):
        row[2] = value
    config_data["columns"][2].update(taxonomy_id=definition["id"], taxonomy_version=definition["version"], taxonomy_required=True)
    if explicit_rule:
        config_data["data_quality_rules"] = [{"column": "branch_name", "rule": "in_taxonomy", "action_on_fail": "REQUIRE_REVIEW"}]
    body = await non_master(context, config_data)
    binding = (await request(context, "PUT", f"/taxonomies/source-sheets/{body['source_sheet_id']}/column-bindings",
                             data={"source_column": "Cabang", "taxonomy_id": definition["id"],
                                   "taxonomy_version": definition["version"], "required": True}))["data"]
    await request(context, "POST", f"/taxonomies/column-bindings/{binding['id']}/approve", who="approver",
                  data={"revision_no": binding["revision_no"]})
    review = await create(context, body)
    await run_pending(context.tenant_id)
    waiting = await detail(context, review)
    assert waiting["status"] == "NEEDS_INPUT"
    assert waiting["checkpoint"]["rows_valid"] == 1 and waiting["checkpoint"]["rows_invalid"] == 2
    path = f"/import-reviews/{review['id']}"
    questions = (await request(context, "GET", path + "/questions"))["data"]["items"]
    assert len(questions) == 2
    async with SessionFactory() as session:
        rows = (await session.scalars(select(ImportReviewRow).where(
            ImportReviewRow.import_review_id == review["id"]).order_by(ImportReviewRow.source_row))).all()
        assert rows[0].corrected_data == {"branch_name": "alpha"} and rows[0].raw_data["Cabang"] == " ALPHA "
    ambiguous = next(q for q in questions if q["category"] == "TAXONOMY_AMBIGUOUS")
    unknown = next(q for q in questions if q["category"] == "TAXONOMY_INVALID")
    await request(context, "POST", path + f"/questions/{unknown['id']}/answer", expected=422,
                  data={"revision_no": 1, "action": "APPLY_CORRECTION", "corrected_value": "still unknown"})
    await request(context, "POST", path + f"/questions/{unknown['id']}/answer",
                  data={"revision_no": 1, "action": "APPLY_CORRECTION", "corrected_value": " BETA "})
    await request(context, "POST", path + f"/questions/{ambiguous['id']}/answer",
                  data={"revision_no": 1, "action": "SELECT_RECORD", "selected_candidate_id": terms[0]["id"]})
    answered = await detail(context, review)
    assert not answered["checkpoint"]["blocking_codes"]
    assert answered["checkpoint"]["open_question_count"] == 0
    await request(context, "POST", path + "/resume", data={"revision_no": answered["revision_no"]})
    await run_pending(context.tenant_id)
    assert (await detail(context, review))["status"] == "AI_REVIEWING"
    assert len((await request(context, "GET", path + "/questions"))["data"]["items"]) == 2
