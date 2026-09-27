from sqlalchemy import func, select

from app.models.base import now
from app.models.etl import Job
from app.models.import_review import ImportReview
from app.models.notification import OperationalNotification
from app.repositories.base import TenantRepository, record
from app.services.audit_service import audit


def add_notification(
    session,
    *,
    tenant_id,
    event_key,
    kind,
    severity,
    resource_type,
    resource_id,
    title,
    message,
    details=None,
):
    notification = OperationalNotification(
        tenant_id=tenant_id,
        event_key=event_key,
        kind=kind,
        severity=severity,
        resource_type=resource_type,
        resource_id=resource_id,
        title=title,
        message=message,
        details=details or {},
    )
    session.add(notification)
    return notification


class NotificationService:
    def __init__(self, session, user):
        self.session, self.user = session, user
        self.repo = TenantRepository(session, user.tenant_id)

    async def list(self, *, unacknowledged_only=True, offset=0, limit=50):
        query = self.repo.query(OperationalNotification)
        if unacknowledged_only:
            query = query.where(OperationalNotification.acknowledged_at.is_(None))
        rows = (
            await self.session.scalars(
                query.order_by(
                    OperationalNotification.created_at.desc(), OperationalNotification.id.desc()
                )
                .offset(offset)
                .limit(limit + 1)
            )
        ).all()
        return {"items": [record(item) for item in rows[:limit]], "has_more": len(rows) > limit}

    async def acknowledge(self, notification_id):
        notification = await self.repo.get(OperationalNotification, notification_id, lock=True)
        if notification.acknowledged_at is None:
            notification.acknowledged_by = self.user.id
            notification.acknowledged_at = now()
            audit(
                self.session,
                self.user,
                "notification.acknowledged",
                notification.id,
                kind=notification.kind,
                resource_type=notification.resource_type,
                target_resource_id=notification.resource_id,
            )
        return record(notification)

    async def summary(self):
        async def counts(model):
            result = await self.session.execute(
                select(model.status, func.count(model.id))
                .where(model.tenant_id == self.user.tenant_id)
                .group_by(model.status)
            )
            return {status: count for status, count in result}

        unacknowledged = await self.session.scalar(
            select(func.count(OperationalNotification.id)).where(
                OperationalNotification.tenant_id == self.user.tenant_id,
                OperationalNotification.acknowledged_at.is_(None),
            )
        )
        return {
            "jobs": await counts(Job),
            "import_reviews": await counts(ImportReview),
            "unacknowledged_notifications": unacknowledged or 0,
            "generated_at": now(),
        }
