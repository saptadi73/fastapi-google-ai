from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from app.domain.import_workflow import ImportAction
from app.models.audit import AuditEvent
from app.models.notification import OperationalNotification
from app.services.import_review_service import ImportReviewService
from app.services.notification_service import NotificationService


def test_import_needs_input_creates_persistent_notification():
    session = Mock()
    user = SimpleNamespace(tenant_id="11111111-1111-4111-8111-111111111111", id="editor")
    review = SimpleNamespace(
        id="22222222-2222-4222-8222-222222222222",
        tenant_id=user.tenant_id,
        status="VALIDATING",
        revision_no=2,
    )

    ImportReviewService(session, user).move(review, ImportAction.REQUEST_INPUT, worker=True)

    assert review.status == "NEEDS_INPUT"
    added = [call.args[0] for call in session.add.call_args_list]
    assert any(isinstance(item, AuditEvent) for item in added)
    notification = next(item for item in added if isinstance(item, OperationalNotification))
    assert notification.kind == "IMPORT_NEEDS_INPUT"
    assert notification.event_key.endswith(":needs-input:3")
    assert notification.details == {"status": "NEEDS_INPUT", "revision_no": 3}


async def test_acknowledge_is_idempotent_and_audited():
    session = Mock()
    session.scalar = AsyncMock()
    user = SimpleNamespace(
        tenant_id="11111111-1111-4111-8111-111111111111",
        id="33333333-3333-4333-8333-333333333333",
    )
    notification = OperationalNotification(
        id="44444444-4444-4444-8444-444444444444",
        tenant_id=user.tenant_id,
        event_key="job:55555555-5555-4555-8555-555555555555:failed",
        kind="JOB_FAILED",
        severity="ERROR",
        resource_type="JOB",
        resource_id="55555555-5555-4555-8555-555555555555",
        title="Job gagal",
        message="Periksa kode kegagalan.",
        details={"error_code": "JOB_EXECUTION_FAILED"},
        recipient_user_id=user.id,
        acknowledged_by=None,
        acknowledged_at=None,
    )
    service = NotificationService(session, user)
    session.scalar.return_value = notification

    result = await service.acknowledge(notification.id)

    assert result["acknowledged_by"] == user.id
    assert result["acknowledged_at"] is not None
    assert isinstance(session.add.call_args.args[0], AuditEvent)
    session.add.reset_mock()

    await service.acknowledge(notification.id)
    session.add.assert_not_called()
