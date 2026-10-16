from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.cli import source_access_backfill_row
from app.core.exceptions import AppError
from app.domain.import_workflow import ImportAction, ImportStatus, next_import_status
from app.models.source import DataSource
from app.schemas.access import AccessRequestBatchDecision
from app.schemas.auth import UserCreate
from app.schemas.configuration import Decision, ReviewSubmission
from app.services import auth_service, configuration_service, master_service, source_service
from app.services.access_service import AccessService
from app.services.release_approval_service import owner_workflow_compatible
from app.services.semantic_catalog_service import inventory_update_state


@pytest.fixture(autouse=True)
def legacy_contract(monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "etl_owner_workflow_enabled", False)


def test_owner_configuration_submit_payload_does_not_require_checklist_fields():
    payload = ReviewSubmission(revision_no=1, snapshot_hash="a" * 64)
    assert payload.reviewed_columns == []
    assert payload.reviewed_sections == []


def test_source_access_backfill_report_never_auto_approves_legacy_sources():
    source = SimpleNamespace(
        tenant_id=uuid4(),
        id=uuid4(),
        source_code="legacy_source",
        access_status="ACCESS_POLICY_REQUIRED",
        access_review_status="PENDING",
        access_metadata=None,
    )
    report = source_access_backfill_row(source)
    assert report["action"] == "OWNER_METADATA_REQUIRED"
    assert report["missing_metadata_fields"] == [
        "owner_unit_id",
        "business_domain_id",
        "jurisdiction_id",
        "purpose_id",
        "data_owner_user_id",
        "data_steward_user_id",
        "sensitivity",
    ]
    assert "spreadsheet_id" not in report


def test_owner_report_requests_unit_validation_instead_of_another_approver(monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "etl_owner_workflow_enabled", True)
    source = SimpleNamespace(tenant_id=uuid4(), id=uuid4(), source_code="unit_source",
        access_status="ACCESS_POLICY_REQUIRED", access_review_status="PENDING",
        access_metadata={"owner_unit_id": str(uuid4())})
    report = source_access_backfill_row(source)
    assert report["action"] == "OWNER_ACCESS_VALIDATION_REQUIRED"
    assert report["missing_metadata_fields"] == []


def test_source_access_backfill_report_distinguishes_review_and_activation():
    source = SimpleNamespace(
        tenant_id=uuid4(),
        id=uuid4(),
        source_code="legacy_source",
        access_status="ACCESS_POLICY_REQUIRED",
        access_review_status="APPROVED",
        access_reviewed_by="reviewer-id",
        access_reviewed_at=timedelta(days=1),
        access_metadata={
            "owner_unit_id": "unit",
            "business_domain_id": "domain",
            "jurisdiction_id": "jurisdiction",
            "purpose_id": "purpose",
            "data_owner_user_id": "owner",
            "data_steward_user_id": "steward",
            "sensitivity": "MEDIUM",
        },
    )
    assert source_access_backfill_row(source)["action"] == "OWNER_ACCESS_ACTIVATION_REQUIRED"
    source.access_status = "POLICY_APPROVED"
    assert source_access_backfill_row(source)["action"] == "READY_NO_BACKFILL"


def test_legacy_compatibility_report_requires_evidence_before_preserving_approval():
    source = SimpleNamespace(
        tenant_id=uuid4(),
        id=uuid4(),
        source_code="legacy_source_without_review_evidence",
        access_status="POLICY_APPROVED",
        access_review_status="APPROVED",
        access_reviewed_by=None,
        access_reviewed_at=None,
        access_metadata={
            "owner_unit_id": "unit",
            "business_domain_id": "domain",
            "jurisdiction_id": "jurisdiction",
            "purpose_id": "purpose",
            "data_owner_user_id": "owner",
            "data_steward_user_id": "steward",
            "sensitivity": "MEDIUM",
        },
    )
    assert source_access_backfill_row(source)["action"] == "SOURCE_REVIEW_REQUIRED"


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


def test_owner_batch_apply_uses_explicit_role_checked_transition():
    assert next_import_status(
        ImportStatus.READY_FOR_APPROVAL,
        ImportAction.OWNER_APPROVE,
        role="SOURCE_OWNER",
    ) is ImportStatus.APPROVED
    with pytest.raises(AppError) as error:
        next_import_status(
            ImportStatus.READY_FOR_APPROVAL,
            ImportAction.OWNER_APPROVE,
            role="TECHNICAL_APPROVER",
        )
    assert error.value.code == "IMPORT_ACTION_FORBIDDEN"
    with pytest.raises(ValidationError):
        UserCreate(username="new_reader", password="test-password-123", initial_access={
            "business_reason": "Akses laporan unit bisnis.",
        })


def test_legacy_configuration_rollback_still_requires_reviewer():
    service = SimpleNamespace(user=SimpleNamespace(role="SOURCE_OWNER"))
    with pytest.raises(AppError) as error:
        configuration_service.ConfigurationService.require_legacy_reviewer(service)
    assert error.value.code == "CONFIGURATION_REVIEWER_REQUIRED"
    service.user.role = "TECHNICAL_APPROVER"
    configuration_service.ConfigurationService.require_legacy_reviewer(service)


@pytest.mark.parametrize("reason", [None, "", "  ", "no"])
def test_master_deactivation_requires_auditable_reason(reason):
    with pytest.raises(AppError) as error:
        master_service.validate_deactivation_reason(reason)
    assert error.value.code == "MASTER_DEACTIVATION_REASON_REQUIRED"


def test_master_deactivation_accepts_a_nonblank_reason():
    master_service.validate_deactivation_reason("Sumber resmi diganti")


@pytest.mark.parametrize(
    "config,enabled,expected",
    [
        (SimpleNamespace(status="AI_DRAFT", review_state={}, approved_by=None, approved_at=None), True, False),
        (SimpleNamespace(status="NEEDS_REVIEW", review_state={}, approved_by=None, approved_at=None), True, False),
        (SimpleNamespace(status="ACTIVE", review_state={}, approved_by="reviewer", approved_at="2026-01-01"), True, True),
        (SimpleNamespace(status="APPROVED", review_state={"owner_managed": True}, approved_by="owner", approved_at="2026-01-01"), True, True),
        (SimpleNamespace(status="ACTIVE", review_state={}, approved_by="reviewer", approved_at="2026-01-01"), False, False),
        (SimpleNamespace(status="ACTIVE", review_state={}, approved_by=None, approved_at=None), True, True),
    ],
)
def test_release_gate_compatibility_requires_owner_workflow_or_prior_approval(monkeypatch, config, enabled, expected):
    from app.services import release_approval_service

    monkeypatch.setattr(release_approval_service, "get_settings", lambda: SimpleNamespace(
        etl_owner_workflow_enabled=enabled,
    ))
    assert owner_workflow_compatible(config) is expected


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
        review_state={"submitted_revision": 2, "snapshot_hash": "snapshot",
                      "schema_migration": {"fingerprint": "schema"}},
    )
    source = SimpleNamespace(id=config.source_id, access_revision=1, access_review_status="PENDING")
    session = Mock()
    session.scalar = AsyncMock(return_value=source)
    service = configuration_service.ConfigurationService(
        session, SimpleNamespace(id="reviewer", tenant_id="tenant", role="TECHNICAL_APPROVER"),
    )
    service.repo.get = AsyncMock(return_value=config)
    service.repo.add = AsyncMock()
    service.validate = AsyncMock(return_value={"valid": True, "snapshot_hash": "snapshot",
        "deployment_plan": {"migration": {"fingerprint": "schema", "requires_migration": False}}})
    service.require_classification_evidence = Mock()
    service.artifacts.create = AsyncMock()
    monkeypatch.setattr(configuration_service, "require_source_approver", AsyncMock())
    monkeypatch.setattr(configuration_service, "ClassificationService", Mock(return_value=SimpleNamespace(locked_sheet=AsyncMock())))
    monkeypatch.setattr(configuration_service, "get_settings", lambda: SimpleNamespace(
        require_separate_approver=False, etl_owner_workflow_enabled=False,
    ))
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


async def test_owner_workflow_self_validates_without_reviewer_checklists(monkeypatch):
    monkeypatch.setattr(configuration_service, "require_source_manager", AsyncMock())
    actor = SimpleNamespace(id="owner", tenant_id="tenant", role="SOURCE_OWNER")
    service = configuration_service.ConfigurationService(Mock(), actor)
    service.session.execute = AsyncMock()
    config = SimpleNamespace(
        id="config", source_id="source", source_sheet_id="sheet", status="AI_DRAFT",
        revision_no=4, configuration_json={"columns": [{"target_column": "code"}]},
        review_state={"answers": {"grain": "one row per code"}},
    )
    sheet = SimpleNamespace(classification_revision=3, classification_status="CONFIRMED", dataset_kind="NON_MASTER")
    service.repo.get = AsyncMock(return_value=config)
    service.artifacts.create = AsyncMock()
    service.validate = AsyncMock(return_value={
        "valid": True, "snapshot_hash": "snapshot-hash", "snapshot_id": "snapshot-id",
        "deployment_plan": {"migration": {"fingerprint": "schema", "operations": [{"action": "CREATE_TABLE"}]}},
    })
    monkeypatch.setattr(configuration_service, "get_settings", lambda: SimpleNamespace(etl_owner_workflow_enabled=True))
    monkeypatch.setattr(configuration_service, "ClassificationService", Mock(return_value=SimpleNamespace(
        locked_sheet=AsyncMock(return_value=sheet),
    )))
    audit = Mock()
    monkeypatch.setattr(configuration_service, "audit", audit)
    submission = SimpleNamespace(
        revision_no=4, snapshot_hash="snapshot-hash", reviewed_columns=[],
        reviewed_sections=[], reviewed_schema_fingerprint=None,
    )

    result = await service.submit_review("config", submission)

    assert result.status == "APPROVED"
    assert result.approved_by == "owner"
    assert result.review_state["owner_managed"] is True
    assert result.review_state["snapshot_id"] == "snapshot-id"
    audit.assert_called_once()
    assert audit.call_args.args[2] == "configuration.owner_validated"
    service.artifacts.create.assert_awaited_once_with(config)


async def test_owner_workflow_does_not_skip_invalid_configuration(monkeypatch):
    monkeypatch.setattr(configuration_service, "require_source_manager", AsyncMock())
    actor = SimpleNamespace(id="owner", tenant_id="tenant", role="SOURCE_OWNER")
    service = configuration_service.ConfigurationService(Mock(), actor)
    service.session.execute = AsyncMock()
    config = SimpleNamespace(
        id="config", source_id="source", source_sheet_id="sheet", status="AI_DRAFT",
        revision_no=4, configuration_json={"columns": [{"target_column": "code"}]}, review_state={},
    )
    service.repo.get = AsyncMock(return_value=config)
    service.validate = AsyncMock(return_value={
        "valid": False, "snapshot_hash": "snapshot-hash", "deployment_plan": {"migration": {"operations": []}},
    })
    monkeypatch.setattr(configuration_service, "get_settings", lambda: SimpleNamespace(etl_owner_workflow_enabled=True))
    monkeypatch.setattr(configuration_service, "ClassificationService", Mock(return_value=SimpleNamespace(
        locked_sheet=AsyncMock(return_value=SimpleNamespace(
            classification_status="CONFIRMED", classification_revision=3, dataset_kind="NON_MASTER",
        )),
    )))
    with pytest.raises(AppError) as error:
        await service.submit_review("config", SimpleNamespace(revision_no=4, snapshot_hash="snapshot-hash"))
    assert error.value.code == "CONFIGURATION_INVALID"
    assert config.status == "AI_DRAFT"


async def test_owner_workflow_approves_master_only_after_definition_checks(monkeypatch):
    actor = SimpleNamespace(id="owner", tenant_id="tenant", role="SOURCE_OWNER")
    service = master_service.MasterService(Mock(), actor)
    definition = {
        "name": "Produk", "aliases": [],
        "fields": [{"name": "product_code", "type": "text", "nullable": False}],
        "business_key": ["product_code"], "label_field": "product_code",
        "policy": {"new_record_policy": "PROPOSE_INSERT", "source_conflict_policy": "REQUIRE_REVIEW"},
    }
    master = SimpleNamespace(
        id="master", revision_no=1, status="DRAFT", definition_json=definition,
        created_by=actor.id, submitted_by=None, approved_definition_json=None,
        approved_version=0, is_active=False,
    )
    service.lock_master = AsyncMock(return_value=master)
    service.check_authority = AsyncMock()
    monkeypatch.setattr(master_service, "get_settings", lambda: SimpleNamespace(
        etl_owner_workflow_enabled=True, require_separate_approver=True,
    ))
    monkeypatch.setattr(master_service, "audit", Mock())

    result = await service.action("master", SimpleNamespace(revision_no=1, comment=""), "submit-review")

    assert result.status == "APPROVED" and result.is_active is True
    assert result.approved_version == 1 and result.approved_by == actor.id
    assert result.revision_no == 2
    assert service.check_authority.await_count == 2


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
    assert review.status == ("READY_FOR_APPROVAL" if case in ("valid", "partial") else "NEEDS_INPUT")
    if case == "open":
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
    if case not in ("valid", "partial"):
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


@pytest.mark.parametrize("case", ["valid", "owner-managed", "legacy-approved", "full-refresh-owner", "master", "inactive", "self-approved", "revoked", "paused", "revision", "stale", "release"])
async def test_auto_load_requires_current_active_configuration_and_valid_release(monkeypatch, case):
    from app.services import import_review_service

    sheet = SimpleNamespace(active_configuration_id="config")
    source = SimpleNamespace(unlinked_at=None, paused=False, access_status="POLICY_APPROVED")
    config = SimpleNamespace(id="config", status="ACTIVE", revision_no=4, approved_by="reviewer", created_by="maker", configuration_json={"load_strategy": "UPSERT"}, review_state={})
    review = SimpleNamespace(id="batch", source_id="source", source_sheet_id="sheet", dependencies={"dataset_kind": "NON_MASTER", "configuration_id": "config", "configuration_revision": 4})
    if case == "master":
        review.dependencies["dataset_kind"] = "MASTER"
    if case == "inactive":
        config.status = "APPROVED"
    if case == "self-approved":
        config.approved_by = config.created_by
    if case in ("owner-managed", "full-refresh-owner"):
        config.approved_by = config.created_by
        config.review_state["owner_managed"] = True
    if case == "legacy-approved":
        config.approved_at = "2026-01-01"
    if case == "revoked":
        source.access_status = "ACCESS_POLICY_REQUIRED"
    if case == "paused":
        source.paused = True
    if case == "full-refresh-owner":
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
    monkeypatch.setattr(import_review_service, "get_settings", lambda: SimpleNamespace(
        etl_owner_workflow_enabled=case in ("owner-managed", "legacy-approved", "full-refresh-owner"),
    ))
    from app.services import release_approval_service
    monkeypatch.setattr(release_approval_service, "get_settings", lambda: SimpleNamespace(
        etl_owner_workflow_enabled=case in ("owner-managed", "legacy-approved", "full-refresh-owner"),
    ))
    if case not in ("valid", "owner-managed", "legacy-approved", "full-refresh-owner"):
        with pytest.raises(AppError):
            await service.active_load_configuration(review)
    else:
        assert await service.active_load_configuration(review) is config
        if case in ("owner-managed", "legacy-approved", "full-refresh-owner"):
            release.assert_not_called()
        else:
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
        assert review.status == "VALIDATING"
        assert review.checkpoint["deterministic_complete"] is False
        assert review.checkpoint["reprocess_staging"] is True
        assert review.checkpoint["auto_load"] is True
        assert review.checkpoint["ai_chunks"] == {}
        assert review.generation == 3
        service.queue.assert_awaited_once_with(review)


@pytest.mark.parametrize("has_duplicate", [False, True])
async def test_owner_can_dismiss_ai_value_suggestions_but_not_duplicate_blockers(monkeypatch, has_duplicate):
    from app.schemas.import_review import ImportAISuggestionsDismissRequest
    from app.services import import_review_service

    advisory = SimpleNamespace(
        status="OPEN", revision_no=1, mandatory=True,
        evidence={"issue": {"issue_kind": "VALUE_ISSUE", "message": "Check label"}},
    )
    duplicate = SimpleNamespace(
        status="OPEN", revision_no=1, mandatory=True,
        evidence={"issue": {"issue_kind": "EXACT_DUPLICATE", "message": "Exact row duplicate"}},
    )
    review = SimpleNamespace(
        id="batch", tenant_id="tenant", source_sheet_id="sheet", status="NEEDS_INPUT", revision_no=4,
        checkpoint={"blocking_codes": ["AI_REVIEW_ISSUES"], "open_question_count": 2},
    )
    session = Mock()
    session.scalars = AsyncMock(return_value=SimpleNamespace(all=lambda: [advisory, duplicate] if has_duplicate else [advisory]))
    session.scalar = AsyncMock(side_effect=["duplicate" if has_duplicate else None,
                                           "duplicate" if has_duplicate else None,
                                           1 if has_duplicate else 0])
    service = import_review_service.ImportReviewService(
        session, SimpleNamespace(id="owner", tenant_id="tenant", role="SOURCE_OWNER"),
    )
    service.locked = AsyncMock(return_value=review)
    service.is_current = AsyncMock(return_value=True)
    service.response = Mock(return_value={"status": review.status})
    monkeypatch.setattr(import_review_service, "audit", Mock())
    monkeypatch.setattr(import_review_service, "add_notification", Mock())

    result = await service.dismiss_ai_suggestions(
        review.id,
        ImportAISuggestionsDismissRequest(revision_no=4, reason="AI labels are advisory; deterministic checks passed."),
    )

    assert advisory.status == "CANCELLED"
    assert result["dismissed_count"] == 1
    if has_duplicate:
        assert duplicate.status == "OPEN"
        assert review.checkpoint["blocking_codes"] == ["AI_REVIEW_ISSUES"]
        assert review.status == "NEEDS_INPUT"
    else:
        assert review.checkpoint["blocking_codes"] == []
        assert review.status == "READY_FOR_APPROVAL"
@pytest.mark.parametrize("auto_load", [True, False])
async def test_new_batch_keeps_manual_auto_load_intent_after_validation(monkeypatch, config_data, auto_load):
    from app.services import import_review_service

    review = SimpleNamespace(
        id="batch", job_id="job", generation=1, status="VALIDATING", revision_no=1,
        snapshot_id="snapshot", source_sheet_id="sheet", configuration_json=config_data,
        dependencies={"sheet": {"header_row": 1, "data_start_row": 2}},
        checkpoint={"auto_load": True} if auto_load else {}, findings=[],
    )
    service = import_review_service.ImportReviewService(
        Mock(), SimpleNamespace(id="operator", tenant_id="tenant", role="SOURCE_OWNER"),
    )
    service.locked = AsyncMock(return_value=review)
    service.is_current = AsyncMock(return_value=True)
    service.repo.get = AsyncMock(return_value=SimpleNamespace(values=[["ID", "Tanggal", "Cabang", "Total"]]))
    service.queue = AsyncMock()
    monkeypatch.setattr(import_review_service, "incremental_values", lambda values, sheet: (values, None, None))
    monkeypatch.setattr(import_review_service, "taxonomy_context", AsyncMock(return_value={}))
    monkeypatch.setattr(import_review_service, "transform_rows", Mock(return_value=([], [], [])))
    monkeypatch.setattr(import_review_service, "review_taxonomy_rows", AsyncMock(return_value=(0, set(), [])))
    monkeypatch.setattr(import_review_service, "audit", Mock())

    await service.work(SimpleNamespace(id="job", payload={"import_review_id": "batch", "generation": 1}))

    assert review.status == "AI_REVIEWING"
    assert review.checkpoint["deterministic_complete"] is True
    assert review.checkpoint.get("auto_load", False) is auto_load
    service.queue.assert_awaited_once_with(review)


async def test_recheck_reuses_staging_identity_and_replaces_old_uncleansed_output(monkeypatch, config_data):
    from app.services import import_review_service

    row = SimpleNamespace(id="existing-row", source_row=2, raw_data={}, transformed_data={"branch_name": " Jakarta "})
    review = SimpleNamespace(id="batch", job_id="job", generation=3, status="VALIDATING", revision_no=7,
        snapshot_id="snapshot", source_sheet_id="sheet", configuration_json=config_data,
        dependencies={"sheet": {"header_row": 1, "data_start_row": 2}},
        checkpoint={"auto_load": True, "deterministic_complete": False, "reprocess_staging": True}, findings=[])
    session = Mock()
    session.scalars = AsyncMock(return_value=SimpleNamespace(all=lambda: [row]))
    service = import_review_service.ImportReviewService(session, SimpleNamespace(id="operator", tenant_id="tenant", role="SOURCE_OWNER"))
    service.locked = AsyncMock(return_value=review)
    service.is_current = AsyncMock(return_value=True)
    service.repo.get = AsyncMock(return_value=SimpleNamespace(values=[["ID", "Tanggal", "Cabang", "Total"], ["001", "2026-01-01", " Jakarta ", 1]]))
    service.repo.add = AsyncMock()
    service.queue = AsyncMock()
    monkeypatch.setattr(import_review_service, "incremental_values", lambda values, sheet: (values, None, None))
    monkeypatch.setattr(import_review_service, "taxonomy_context", AsyncMock(return_value={}))
    monkeypatch.setattr(import_review_service, "review_taxonomy_rows", AsyncMock(return_value=(0, set(), [])))
    monkeypatch.setattr(import_review_service, "audit", Mock())
    await service.work(SimpleNamespace(id="job", payload={"import_review_id": "batch", "generation": 3}))
    assert review.status == "AI_REVIEWING"
    assert row.id == "existing-row" and row.transformed_data["branch_name"] == "Jakarta"
    assert row.raw_data["Cabang"] == " Jakarta "
    assert review.checkpoint["text_cleansing_policy_version"] == "text-trim-v1"
    service.repo.add.assert_not_awaited()


@pytest.mark.parametrize("status", ["NEEDS_INPUT", "FAILED", "STALE_REVIEW", "READY_FOR_APPROVAL", "APPROVED", "SUCCEEDED", "AI_REVIEWING"])
def test_process_attention_exposes_blockers_without_source_values(status):
    from app.services.import_review_service import ImportReviewService

    review = SimpleNamespace(
        id="batch", source_sheet_id="sheet", status=status, revision_no=9,
        checkpoint={"blocking_codes": ["AI_REVIEW_ISSUES"], "ai_coverage": "COMPLETE"},
        findings=[{"message": "Potential personal name: do-not-expose"}],
    )
    result = ImportReviewService.attention(review)
    if status in ("SUCCEEDED", "AI_REVIEWING"):
        assert result is None
    else:
        assert result["review_id"] == "batch"
        assert result["blocking_codes"] == ["AI_REVIEW_ISSUES"]
        assert "do-not-expose" not in str(result)
        if status == "NEEDS_INPUT":
            assert "Menunggu saja" in result["message"]


def test_request_input_audit_includes_safe_diagnosis(monkeypatch):
    from app.domain.import_workflow import ImportAction
    from app.services import import_review_service

    review = SimpleNamespace(
        id="batch", source_sheet_id="sheet", tenant_id="tenant",
        status="AI_REVIEWING", revision_no=8,
        checkpoint={"blocking_codes": ["AI_REVIEW_ISSUES"], "ai_coverage": "COMPLETE"},
    )
    log = Mock()
    monkeypatch.setattr(import_review_service, "audit", log)
    monkeypatch.setattr(import_review_service, "add_notification", Mock())
    service = import_review_service.ImportReviewService(Mock(), SimpleNamespace(id="user", tenant_id="tenant"))
    service.move(review, ImportAction.REQUEST_INPUT, worker=True)
    assert log.call_args.args[2] == "import.request_input"
    diagnosis = log.call_args.kwargs["attention"]
    assert diagnosis["status"] == "NEEDS_INPUT"
    assert diagnosis["revision_no"] == 9
    assert diagnosis["blocking_codes"] == ["AI_REVIEW_ISSUES"]


@pytest.mark.parametrize(("statuses", "expected"), [
    (["SUCCEEDED", "NEEDS_INPUT"], "NEEDS_INPUT"),
    (["SUCCEEDED", "STALE_REVIEW"], "NEEDS_INPUT"),
    (["SUCCEEDED", "AI_REVIEWING", "NEEDS_INPUT"], "RUNNING"),
    (["VALIDATING"], "RUNNING"), (["APPLYING"], "RUNNING"),
    (["SUCCEEDED", "FAILED"], "FAILED"),
    (["SUCCEEDED", "SUCCEEDED"], "SUCCEEDED"),
    (["SUCCEEDED", "NOT_STARTED"], "IN_PROGRESS"), ([], "NOT_STARTED"),
])
def test_tracking_distinguishes_waiting_from_running(statuses, expected):
    from app.api.v1.sources import tracking_rollup

    assert tracking_rollup(statuses) == expected


def test_audit_locations_preserve_sheet_row_numbers_cap_and_deduplicate():
    from app.services.import_review_service import ImportReviewService

    findings = [
        {"source_row": row, "target_column": "level_jabatan", "message": "private-value"}
        for row in range(13, 38)
    ]
    findings += [
        findings[0],
        {"source_row": 13, "errors": [{"column": "amount", "code": "INVALID", "value": "private-value"}]},
        {"source_row": 0, "target_column": "invalid"},
    ]
    review = SimpleNamespace(
        id="batch", source_sheet_id="sheet", status="NEEDS_INPUT", revision_no=9,
        checkpoint={"blocking_codes": ["AI_REVIEW_ISSUES"]}, findings=findings,
    )
    attention = ImportReviewService.attention(review)
    assert attention["affected_row_count"] == 25
    assert len(attention["locations"]) == 20
    assert attention["locations"][:2] == [
        {"source_row": 13, "target_column": "amount"},
        {"source_row": 13, "target_column": "level_jabatan"},
    ]
    assert attention["has_more_locations"] is True
    assert "private-value" not in str(attention)
