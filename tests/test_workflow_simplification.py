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
