from uuid import uuid4

import pytest
from sqlalchemy import select, update
from test_import_reviews import create, detail, non_master
from test_integration import context as context
from test_integration import request
from test_masters import definition

from app.core.database import SessionFactory
from app.models.configuration import Configuration
from app.models.import_review import ImportDecision, ImportQuestion, ImportReviewRow
from app.workers.runner import run_pending

pytestmark = pytest.mark.integration


async def question_batch(ctx, config_data):
    body = await non_master(ctx, config_data)
    ctx.values[1][3] = "not-a-number"
    # The source reader is mocked by the shared context; replace persisted snapshot via a new batch setup.
    from app.models.etl import Snapshot
    from app.services.profiling_service import digest

    async with SessionFactory() as session, session.begin():
        snapshot = await session.scalar(
            select(Snapshot).where(Snapshot.source_sheet_id == body["source_sheet_id"])
        )
        values = [row[:] for row in snapshot.values]
        values[1][3] = "not-a-number"
        snapshot.values, snapshot.content_hash = values, digest(values)
    review = await create(ctx, body)
    await run_pending(ctx.tenant_id)
    assert (await detail(ctx, review))["status"] == "NEEDS_INPUT"
    questions = (await request(ctx, "GET", f"/import-reviews/{review['id']}/questions?status=OPEN"))["data"]
    return review, questions["items"]


async def test_questions_create_staging_and_typed_correction(context, config_data):
    ctx = context
    review, questions = await question_batch(ctx, config_data)
    question = questions[0]
    assert question["category"] == "DATA_QUALITY" and question["mandatory"]
    assert "evidence" not in question and question["candidate_count"] == 0
    answer = await request(
        ctx,
        "POST",
        f"/import-reviews/{review['id']}/questions/{question['id']}/answer",
        data={"revision_no": 1, "action": "APPLY_CORRECTION", "corrected_value": 321},
    )
    assert answer["data"]["question"]["status"] == "ANSWERED"
    assert answer["data"]["review"]["checkpoint"]["open_question_count"] == 0
    assert "DATA_QUALITY_ISSUES" not in answer["data"]["review"]["checkpoint"]["blocking_codes"]
    async with SessionFactory() as session:
        row = await session.scalar(
            select(ImportReviewRow).where(
                ImportReviewRow.import_review_id == review["id"],
                ImportReviewRow.source_row == question["source_row"],
            )
        )
        decision = await session.scalar(
            select(ImportDecision).where(ImportDecision.import_question_id == question["id"])
        )
        assert row.raw_data["Total"] == "not-a-number"
        assert row.corrected_data == {"net_amount": 321}
        assert decision.before_data == {"net_amount": "[REDACTED]"} and decision.after_data == {
            "net_amount": 321
        }
    listed = (await request(ctx, "GET", f"/import-reviews/{review['id']}/questions?status=ANSWERED&limit=1"))[
        "data"
    ]
    assert listed["items"][0]["decisions"][0]["action"] == "APPLY_CORRECTION"
    assert "not-a-number" not in str(listed)
    duplicate = await request(
        ctx,
        "POST",
        f"/import-reviews/{review['id']}/questions/{question['id']}/answer",
        data={"revision_no": 2, "action": "APPLY_CORRECTION", "corrected_value": 1},
        expected=409,
    )
    assert duplicate["errors"][0]["code"] == "IMPORT_QUESTION_ALREADY_ANSWERED"


async def test_question_action_candidate_and_tenant_guards(context, config_data):
    ctx = context
    review, questions = await question_batch(ctx, config_data)
    question = questions[0]
    candidate_id = str(uuid4())
    async with SessionFactory() as session, session.begin():
        row = await session.get(ImportQuestion, question["id"])
        row.allowed_actions = ["SELECT_RECORD"]
        row.candidates = [{"id": candidate_id, "label": "Kandidat A", "evidence": "exact key"}]
    bad = await request(
        ctx,
        "POST",
        f"/import-reviews/{review['id']}/questions/{question['id']}/answer",
        data={"revision_no": 1, "action": "SELECT_RECORD", "selected_candidate_id": str(uuid4())},
        expected=422,
    )
    assert bad["errors"][0]["code"] == "IMPORT_DECISION_CANDIDATE_INVALID"
    answer = await request(
        ctx,
        "POST",
        f"/import-reviews/{review['id']}/questions/{question['id']}/answer",
        data={"revision_no": 1, "action": "SELECT_RECORD", "selected_candidate_id": candidate_id},
    )
    assert answer["data"]["question"]["decisions"][0]["selected_candidate_id"] == candidate_id
    async with SessionFactory() as session:
        row = await session.scalar(
            select(ImportReviewRow).where(
                ImportReviewRow.import_review_id == review["id"],
                ImportReviewRow.source_row == question["source_row"],
            )
        )
        assert row.corrected_data == {"net_amount": candidate_id}
    await request(ctx, "GET", f"/import-reviews/{review['id']}/questions", who="outsider", expected=404)
    await request(
        ctx,
        "POST",
        f"/import-reviews/{review['id']}/questions/{question['id']}/answer",
        who="viewer",
        data={"revision_no": 2, "action": "SELECT_RECORD", "selected_candidate_id": candidate_id},
        expected=403,
    )


async def test_question_stale_and_proposed_master_stay_blocked(context, config_data):
    ctx = context
    review, questions = await question_batch(ctx, config_data)
    question = questions[0]
    async with SessionFactory() as session, session.begin():
        await session.execute(
            update(Configuration).where(Configuration.id == review["configuration_id"]).values(revision_no=2)
        )
    stale = await request(
        ctx,
        "POST",
        f"/import-reviews/{review['id']}/questions/{question['id']}/answer",
        data={"revision_no": 1, "action": "APPLY_CORRECTION", "corrected_value": 1},
    )
    assert stale["data"]["stale"] and stale["data"]["question"] is None
    assert (await detail(ctx, review))["status"] == "STALE_REVIEW"

    # A separate current batch records a master proposal without treating it as approved data.
    body = {"source_sheet_id": review["source_sheet_id"], "configuration_id": review["configuration_id"]}
    review = await create(ctx, body)
    await run_pending(ctx.tenant_id)
    questions = (await request(ctx, "GET", f"/import-reviews/{review['id']}/questions?status=OPEN"))["data"][
        "items"
    ]
    question = questions[0]
    master_proposal = definition(config_data)
    master_proposal["code"] = "proposed_amounts"
    proposal = await request(
        ctx,
        "POST",
        f"/import-reviews/{review['id']}/questions/{question['id']}/answer",
        data={
            "revision_no": 1,
            "action": "PROPOSE_MASTER",
            "reason": "Kode belum ada; ajukan master baru",
            "master_proposal": master_proposal,
        },
    )
    assert proposal["data"]["question"]["status"] == "PENDING_APPROVAL"
    assert "MASTER_PROPOSAL_PENDING" in proposal["data"]["review"]["checkpoint"]["blocking_codes"]
    decision = proposal["data"]["question"]["decisions"][0]
    master_id = decision["proposed_master_definition_id"]
    await request(ctx, "POST", f"/master-definitions/{master_id}/submit-review", data={"revision_no": 1})
    await request(ctx, "POST", f"/master-definitions/{master_id}/approve", who="approver", data={"revision_no": 2})
    resolved = await request(
        ctx,
        "POST",
        f"/import-reviews/{review['id']}/questions/{question['id']}/resolve-master-proposal",
        who="approver",
        data={"revision_no": 2, "master_definition_id": master_id},
    )
    assert resolved["data"]["question"]["status"] == "ANSWERED"
    assert "MASTER_PROPOSAL_PENDING" not in resolved["data"]["review"]["checkpoint"]["blocking_codes"]
    resumed = await request(
        ctx,
        "POST",
        f"/import-reviews/{review['id']}/resume",
        data={"revision_no": resolved["data"]["review"]["revision_no"]},
    )
    assert resumed["data"]["status"] == "VALIDATING"
    await run_pending(ctx.tenant_id)
    await run_pending(ctx.tenant_id)
    assert (await detail(ctx, review))["checkpoint"]["blocking_codes"] == ["AI_REVIEW_NOT_IMPLEMENTED"]


async def test_question_correct_source_requires_reason_and_preserves_raw(context, config_data):
    ctx = context
    review, questions = await question_batch(ctx, config_data)
    question = questions[0]
    missing = await request(
        ctx,
        "POST",
        f"/import-reviews/{review['id']}/questions/{question['id']}/answer",
        data={"revision_no": 1, "action": "CORRECT_SOURCE"},
        expected=422,
    )
    assert missing["errors"][0]["code"] == "IMPORT_DECISION_REASON_REQUIRED"
    answer = await request(
        ctx,
        "POST",
        f"/import-reviews/{review['id']}/questions/{question['id']}/answer",
        data={
            "revision_no": 1,
            "action": "CORRECT_SOURCE",
            "reason": "User memperbaiki Google Sheet lalu membuat batch baru",
        },
    )
    assert answer["data"]["question"]["status"] == "ANSWERED"
    async with SessionFactory() as session:
        row = await session.scalar(
            select(ImportReviewRow).where(
                ImportReviewRow.import_review_id == review["id"],
                ImportReviewRow.source_row == question["source_row"],
            )
        )
        assert row.raw_data["Total"] == "not-a-number" and row.corrected_data == {}
