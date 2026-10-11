from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.models.source import DataSource
from app.schemas.access import AccessRequestBatchDecision
from app.schemas.auth import UserCreate
from app.schemas.configuration import Decision
from app.services import auth_service, configuration_service, source_service
from app.services.access_service import AccessService
from app.services.semantic_catalog_service import inventory_update_state


def test_onboarding_contract_requires_unique_explicit_targets():
    target = str(uuid4())
    user = UserCreate(username="new_reader", password="test-password-123", initial_access={
        "attribute_ids": [target], "business_reason": "Akses laporan unit bisnis.",
    })
    assert str(user.initial_access.attribute_ids[0]) == target
    with pytest.raises(ValidationError):
        UserCreate(username="new_reader", password="test-password-123", initial_access={
            "attribute_ids": [target, target], "business_reason": "Akses laporan unit bisnis.",
        })
    with pytest.raises(ValidationError):
        UserCreate(username="new_reader", password="test-password-123", initial_access={
            "business_reason": "Akses laporan unit bisnis.",
        })


async def test_onboarding_creates_requests_for_366_days_without_granting_access(monkeypatch):
    account = SimpleNamespace(id=str(uuid4()))
    repo = Mock()
    repo.add = AsyncMock(return_value=account)
    monkeypatch.setattr(auth_service, "TenantRepository", Mock(return_value=repo))
    monkeypatch.setattr(auth_service, "public_user", lambda user: {"id": user.id})
    monkeypatch.setattr(auth_service, "audit", Mock())
    requested = AsyncMock(return_value={"status": "PENDING"})
    monkeypatch.setattr(auth_service, "AccessService", Mock(return_value=SimpleNamespace(create_access_request=requested)))
    data = UserCreate(username="new_reader", password="test-password-123", initial_access={
        "attribute_ids": [str(uuid4()), str(uuid4()), str(uuid4())],
        "bundle_ids": [str(uuid4())], "business_reason": "Akses laporan unit bisnis.",
    })
    result = await auth_service.AuthService(Mock()).create_user(
        SimpleNamespace(tenant_id="tenant", id="maker"), data,
    )
    assert result["access_requests"] == [{"status": "PENDING"}] * 4
    for call in requested.await_args_list:
        request = call.args[0]
        assert str(request.subject_user_id) == account.id
        assert request.valid_to - request.valid_from == timedelta(days=366)
        assert request.business_reason == data.initial_access.business_reason
    assert [call.args[0].request_type for call in requested.await_args_list] == ["ATTRIBUTE"] * 3 + ["PERMISSION_BUNDLE"]
    repo.add.assert_awaited_once()


async def test_batch_approval_propagates_stale_request_and_requires_admin():
    data = AccessRequestBatchDecision(requests=[
        {"id": str(uuid4()), "revision": 1}, {"id": str(uuid4()), "revision": 2},
    ])
    service = AccessService(Mock(), SimpleNamespace(tenant_id="tenant", role="PLATFORM_ADMIN"))
    service.decide_access_request = AsyncMock(side_effect=[{"status": "APPROVED"}, AppError("STALE_REVISION", "Stale", 409)])
    with pytest.raises(AppError, match="Stale"):
        await service.approve_access_requests(data)
    assert service.decide_access_request.await_count == 2
    service.actor.role = "TECHNICAL_APPROVER"
    with pytest.raises(AppError) as error:
        await service.approve_access_requests(data)
    assert error.value.code == "FORBIDDEN"
    with pytest.raises(ValidationError):
        AccessRequestBatchDecision(requests=[data.requests[0], data.requests[0]])


def configuration_context(monkeypatch):
    config = SimpleNamespace(
        id=str(uuid4()), source_id=str(uuid4()), source_sheet_id=str(uuid4()),
        created_by="maker", status="NEEDS_REVIEW", revision_no=2,
        review_state={"submitted_revision": 2, "snapshot_hash": "snapshot"},
    )
    source = SimpleNamespace(id=config.source_id, access_revision=1, access_review_status="PENDING")
    session = Mock()
    session.scalar = AsyncMock(return_value=source)
    service = configuration_service.ConfigurationService(
        session, SimpleNamespace(id="reviewer", tenant_id="tenant", role="TECHNICAL_APPROVER"),
    )
    service.repo.get = AsyncMock(return_value=config)
    service.repo.add = AsyncMock()
    service.validate = AsyncMock(return_value={"valid": True, "snapshot_hash": "snapshot"})
    service.require_classification_evidence = Mock()
    service.artifacts.create = AsyncMock()
    monkeypatch.setattr(configuration_service, "require_source_approver", AsyncMock())
    monkeypatch.setattr(configuration_service, "ClassificationService", Mock(return_value=SimpleNamespace(locked_sheet=AsyncMock())))
    monkeypatch.setattr(configuration_service, "get_settings", lambda: SimpleNamespace(require_separate_approver=False))
    monkeypatch.setattr(configuration_service, "audit", Mock())

    async def review(*args, **kwargs):
        source.access_revision += 1
        source.access_review_status = "APPROVED"

    async def activate(*args, **kwargs):
        source.access_revision += 1
        source.access_status = "POLICY_APPROVED"

    access = SimpleNamespace(review_access_metadata=AsyncMock(side_effect=review), activate_source_access=AsyncMock(side_effect=activate))
    monkeypatch.setattr(source_service, "SourceService", Mock(return_value=access))
    return service, config, source, access


async def test_combined_approval_uses_configuration_reviewer_and_explicit_policy(monkeypatch):
    service, config, source, access = configuration_context(monkeypatch)
    policy_id = str(uuid4())
    approved = await service.decision(config.id, Decision(
        revision_no=2, source_access={"revision_no": 1, "policy_id": policy_id},
    ), "APPROVED")
    assert approved.status == "APPROVED" and approved.revision_no == 3
    assert access.review_access_metadata.await_args.kwargs == {"workflow": "configuration"}
    assert access.review_access_metadata.await_args.args[1].reason == "METADATA_VERIFIED"
    assert access.activate_source_access.await_args.args[1].revision_no == 2
    assert str(access.activate_source_access.await_args.args[1].policy_id) == policy_id
    assert source.access_status == "POLICY_APPROVED"
    service.artifacts.create.assert_awaited_once()


@pytest.mark.parametrize("blocker", ["self", "stale", "policy"])
async def test_combined_approval_blockers_do_not_approve_configuration(monkeypatch, blocker):
    service, config, source, access = configuration_context(monkeypatch)
    if blocker == "self":
        config.created_by = service.user.id
    elif blocker == "stale":
        source.access_revision = 2
    else:
        access.activate_source_access = AsyncMock(side_effect=AppError("SOURCE_ACCESS_POLICY_REQUIRED", "Policy belum approved.", 409))
    with pytest.raises(AppError):
        await service.decision(config.id, Decision(
            revision_no=2, source_access={"revision_no": 1, "policy_id": str(uuid4())},
        ), "APPROVED")
    assert config.status == "NEEDS_REVIEW" and config.revision_no == 2
    service.artifacts.create.assert_not_awaited()
    service.repo.add.assert_not_awaited()


@pytest.mark.parametrize("pending", [False, True])
async def test_manual_sync_uses_durable_queue_and_rejects_existing_job(monkeypatch, pending):
    session = Mock()
    session.scalar = AsyncMock(return_value=SimpleNamespace(id="existing") if pending else None)
    service = source_service.SourceService(session, SimpleNamespace(tenant_id="tenant", id="operator"), google=Mock())
    service.repo.get = AsyncMock(return_value=SimpleNamespace(id="source", unlinked_at=None))
    enqueue = AsyncMock(return_value={"job_id": "job", "status": "QUEUED"})
    monkeypatch.setattr(source_service, "enqueue", enqueue)
    if pending:
        with pytest.raises(AppError) as error:
            await service.queue_sync_review("source")
        assert error.value.code == "SOURCE_JOB_RUNNING"
        enqueue.assert_not_awaited()
    else:
        assert (await service.queue_sync_review("source"))["status"] == "QUEUED"
        assert enqueue.await_args.args[2:] == ("SYNC_REVIEW", "source")
    service.repo.get.assert_awaited_once_with(DataSource, "source", lock=True)


@pytest.mark.parametrize(
    "pending_config,import_status,running,profile,loaded,expected",
    [
        (None, None, False, "reviewed", None, "ACTIVE"),
        (None, "SUCCEEDED", False, "loaded", "loaded", "ACTIVE"),
        ("NEEDS_REVIEW", "SUCCEEDED", False, "loaded", "loaded", "UPDATING"),
        (None, "NEEDS_INPUT", False, "loaded", "loaded", "UPDATING"),
        (None, "FAILED", False, "loaded", "loaded", "UPDATING"),
        (None, "SUCCEEDED", True, "loaded", "loaded", "UPDATING"),
        (None, "SUCCEEDED", False, "new", "loaded", "UPDATING"),
    ],
)
def test_catalog_preserves_active_version_and_reports_real_update_state(pending_config, import_status, running, profile, loaded, expected):
    sheet = SimpleNamespace(is_present=True, enabled=True, last_fingerprint="fingerprint")
    config = SimpleNamespace(based_on_fingerprint="fingerprint", review_state={"snapshot_hash": "reviewed"})
    status, reason = inventory_update_state(sheet, config, pending_config, import_status, running, profile, loaded)
    assert status == expected and reason


async def test_failed_workflow_rolls_back_request_session(monkeypatch):
    from app.core import database

    session = AsyncMock()
    session.__aenter__.return_value = session
    monkeypatch.setattr(database, "SessionFactory", Mock(return_value=session))
    dependency = database.get_session()
    assert await anext(dependency) is session
    with pytest.raises(AppError):
        await dependency.athrow(AppError("SOURCE_ACCESS_POLICY_REQUIRED", "Policy belum approved.", 409))
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


def test_existing_ai_questions_offer_explicit_confirmation_without_mutating_storage():
    from app.models.import_review import ImportQuestion
    from app.services.import_review_service import ImportReviewService

    question = ImportQuestion(
        category="AI_REVIEW", mandatory=True, allowed_actions=["APPLY_CORRECTION", "CORRECT_SOURCE"],
        candidates=[], evidence={"source": "AI", "issue": {"message": "Verify nullable value"}},
    )
    result = ImportReviewService.question_response(question)
    assert result["mandatory"] is True
    assert result["allowed_actions"] == ["APPLY_CORRECTION", "CORRECT_SOURCE", "KEEP_ORIGINAL"]
    assert result["review_message"] == "Verify nullable value"
    assert question.allowed_actions == ["APPLY_CORRECTION", "CORRECT_SOURCE"]
    assert "evidence" not in result
    question.category = "DATA_QUALITY"
    assert "KEEP_ORIGINAL" not in ImportReviewService.question_actions(question)


@pytest.mark.parametrize("case", ["valid", "no-reason", "technical", "partial", "open", "source-correction", "proposal", "stale"])
async def test_ai_confirmation_is_audited_without_bypassing_remaining_gates(monkeypatch, case):
    from app.models.import_review import ImportDecision, ImportQuestion
    from app.schemas.import_review import ImportQuestionDecision
    from app.services import import_review_service

    question = ImportQuestion(
        id=str(uuid4()), import_review_id=str(uuid4()), category="AI_REVIEW",
        mandatory=True, allowed_actions=["APPLY_CORRECTION", "CORRECT_SOURCE"],
        candidates=[], evidence={}, revision_no=1, status="OPEN", target_column="amount",
        source_row=2, question_key="question",
    )
    review = SimpleNamespace(
        id=question.import_review_id, status="NEEDS_INPUT", revision_no=6,
        checkpoint={"deterministic_complete": True, "ai_coverage": "COMPLETE", "blocking_codes": ["AI_REVIEW_ISSUES"]},
    )
    if case == "technical":
        question.category = "DATA_QUALITY"
        question.allowed_actions.append("KEEP_ORIGINAL")
    if case == "partial":
        review.checkpoint["ai_coverage"] = "PARTIAL"
    session = Mock()
    session.scalar = AsyncMock(side_effect=[
        question, "open" if case == "open" else None,
        "proposal" if case == "proposal" else None,
        "source-correction" if case == "source-correction" else None,
    ])
    session.scalars = AsyncMock(return_value=SimpleNamespace(all=lambda: [question] if case == "open" else []))
    service = import_review_service.ImportReviewService(
        session, SimpleNamespace(id="editor", tenant_id="tenant", role="PLATFORM_ADMIN"),
    )
    service.locked = AsyncMock(return_value=review)
    service.is_current = AsyncMock(return_value=case != "stale")
    service.repo.add = AsyncMock(return_value=SimpleNamespace(id="decision"))
    service.response = Mock(return_value={})
    service.question_response = Mock(return_value={})
    monkeypatch.setattr(import_review_service, "audit", Mock())
    payload = ImportQuestionDecision(revision_no=1, action="KEEP_ORIGINAL", reason="" if case == "no-reason" else "Blank permitted by approved nullable mapping; verified with source owner.")
    if case in ("no-reason", "technical"):
        with pytest.raises(AppError) as error:
            await service.answer_question(review.id, question.id, payload)
        assert error.value.code == ("IMPORT_DECISION_REASON_REQUIRED" if case == "no-reason" else "IMPORT_DECISION_ACTION_INVALID")
        service.repo.add.assert_not_awaited()
        return
    result = await service.answer_question(review.id, question.id, payload)
    if case == "stale":
        assert result["stale"] and review.status == "STALE_REVIEW"
        service.repo.add.assert_not_awaited()
        return
    args = service.repo.add.await_args
    assert args.args[0] is ImportDecision
    assert args.kwargs["action"] == "KEEP_ORIGINAL"
    assert args.kwargs["reason"] == payload.reason
    assert args.kwargs["after_data"] == {}
    assert question.status == "ANSWERED"
    assert review.status == ("READY_FOR_APPROVAL" if case == "valid" else "NEEDS_INPUT")
    if case in ("partial", "open"):
        assert "AI_REVIEW_ISSUES" in review.checkpoint["blocking_codes"]
    if case == "source-correction":
        assert "SOURCE_CORRECTION_REQUIRED" in review.checkpoint["blocking_codes"]


@pytest.mark.parametrize("case", ["valid", "not-enabled", "partial", "open", "conflict", "invalid-preview", "source-conflict"])
async def test_auto_load_reuses_active_approval_only_after_all_data_checks(monkeypatch, case):
    from app.services import import_review_service

    review = SimpleNamespace(
        id="batch", status="READY_FOR_APPROVAL", revision_no=6,
        checkpoint={"auto_load": True, "deterministic_complete": True, "ai_coverage": "COMPLETE"},
    )
    if case == "not-enabled":
        review.checkpoint["auto_load"] = False
    if case == "partial":
        review.checkpoint["ai_coverage"] = "PARTIAL"
    session = Mock()
    session.scalar = AsyncMock(return_value="open" if case == "open" else None)
    service = import_review_service.ImportReviewService(
        session, SimpleNamespace(id="operator", tenant_id="tenant", role="SOURCE_OWNER"),
    )
    service.active_load_configuration = AsyncMock(return_value=SimpleNamespace(id="config", approved_by="reviewer", revision_no=4))
    service.preview = AsyncMock(return_value={
        "blocking_codes": ["DUPLICATE"] if case == "conflict" else [],
        "requires_source_confirmation": case == "source-conflict",
        "can_approve": case != "invalid-preview", "preview_token": "signed-token",
    })
    service.apply = AsyncMock()
    monkeypatch.setattr(import_review_service, "audit", Mock())
    if case != "valid":
        with pytest.raises(AppError):
            await service.auto_load(review)
        service.apply.assert_not_awaited()
        assert review.status == "READY_FOR_APPROVAL"
        return
    await service.auto_load(review)
    assert review.status == "APPROVED"
    assert review.checkpoint["approved_by"] == "reviewer"
    assert review.checkpoint["approval_mode"] == "ACTIVE_CONFIGURATION"
    assert review.checkpoint["approval_basis_configuration_revision"] == 4
    assert service.apply.await_args.args[1].preview_token == "signed-token"
    assert service.apply.await_args.args[1].revision_no == review.revision_no


@pytest.mark.parametrize("case", ["valid", "master", "inactive", "self-approved", "revoked", "paused", "full-refresh", "revision", "stale", "release"])
async def test_auto_load_requires_current_active_configuration_and_valid_release(monkeypatch, case):
    from app.services import import_review_service

    sheet = SimpleNamespace(active_configuration_id="config")
    source = SimpleNamespace(unlinked_at=None, paused=False, access_status="POLICY_APPROVED")
    config = SimpleNamespace(id="config", status="ACTIVE", revision_no=4, approved_by="reviewer", created_by="maker", configuration_json={"load_strategy": "UPSERT"})
    review = SimpleNamespace(id="batch", source_id="source", source_sheet_id="sheet", dependencies={"dataset_kind": "NON_MASTER", "configuration_id": "config", "configuration_revision": 4})
    if case == "master":
        review.dependencies["dataset_kind"] = "MASTER"
    if case == "inactive":
        config.status = "APPROVED"
    if case == "self-approved":
        config.approved_by = config.created_by
    if case == "revoked":
        source.access_status = "ACCESS_POLICY_REQUIRED"
    if case == "paused":
        source.paused = True
    if case == "full-refresh":
        config.configuration_json["load_strategy"] = "FULL_REFRESH"
    if case == "revision":
        config.revision_no += 1
    session = Mock()
    session.refresh = AsyncMock()
    service = import_review_service.ImportReviewService(session, SimpleNamespace(id="operator", tenant_id="tenant", role="SOURCE_OWNER"))
    service.repo.get = AsyncMock(side_effect=[sheet, source, config])
    service.is_current = AsyncMock(return_value=case != "stale")
    release = Mock(side_effect=AppError("RELEASE_APPROVAL_REQUIRED", "Pending", 409) if case == "release" else None)
    monkeypatch.setattr(import_review_service, "require_release_ready", release)
    if case != "valid":
        with pytest.raises(AppError):
            await service.active_load_configuration(review)
    else:
        assert await service.active_load_configuration(review) is config
        release.assert_called_once_with(config, source)


@pytest.mark.parametrize("case", ["valid", "decided", "technical"])
async def test_manual_sync_rechecks_old_ai_only_batches_without_erasing_user_decisions(monkeypatch, case):
    from app.services import import_review_service

    question = SimpleNamespace(category="AI_REVIEW" if case != "technical" else "DATA_QUALITY", status="OPEN", revision_no=1, evidence={"issue": {"message": "Verify null"}})
    review = SimpleNamespace(id="batch", source_id="source", source_sheet_id="sheet", status="NEEDS_INPUT", revision_no=6, generation=2, findings=[{"message": "Verify null"}], dependencies={"configuration_id": "config"}, checkpoint={"deterministic_complete": True, "blocking_codes": ["AI_REVIEW_ISSUES"], "ai_chunks": {"old": {}}})
    session = Mock()
    session.scalars = AsyncMock(return_value=SimpleNamespace(all=lambda: [question]))
    session.scalar = AsyncMock(return_value="decision" if case == "decided" else None)
    service = import_review_service.ImportReviewService(session, SimpleNamespace(id="operator", tenant_id="tenant", role="SOURCE_OWNER"))
    service.locked = AsyncMock(return_value=review)
    service.active_load_configuration = AsyncMock()
    service.queue = AsyncMock()
    monkeypatch.setattr(import_review_service, "audit", Mock())
    if case != "valid":
        with pytest.raises(AppError):
            await service.enable_auto_load(review.id)
        assert question.status == "OPEN"
        service.queue.assert_not_awaited()
    else:
        await service.enable_auto_load(review.id)
        assert question.status == "CANCELLED"
        assert review.status == "AI_REVIEWING"
        assert review.checkpoint["auto_load"] is True
        assert review.checkpoint["ai_chunks"] == {}
        assert review.generation == 3
        service.queue.assert_awaited_once_with(review)
