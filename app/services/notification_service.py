from sqlalchemy import func, or_, select, update

from app.core.exceptions import AppError
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
    recipient_user_id=None,
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
        recipient_user_id=recipient_user_id,
    )
    session.add(notification)
    return notification


class NotificationService:
    def __init__(self, session, user):
        self.session, self.user = session, user
        self.repo = TenantRepository(session, user.tenant_id)

    async def list(self, *, unacknowledged_only=True, offset=0, limit=50):
        query = self.repo.query(OperationalNotification).where(
            or_(
                OperationalNotification.recipient_user_id.is_(None),
                OperationalNotification.recipient_user_id == self.user.id,
            )
        )
        if unacknowledged_only:
            query = query.where(OperationalNotification.acknowledged_at.is_(None))
        rows = (
            await self.session.scalars(
                query.order_by(OperationalNotification.created_at.desc(), OperationalNotification.id.desc())
                .offset(offset)
                .limit(limit + 1)
            )
        ).all()
        return {"items": [record(item) for item in rows[:limit]], "has_more": len(rows) > limit}

    async def acknowledge(self, notification_id):
        notification = await self.session.scalar(
            self.repo.query(OperationalNotification)
            .where(
                OperationalNotification.id == str(notification_id),
                or_(
                    OperationalNotification.recipient_user_id.is_(None),
                    OperationalNotification.recipient_user_id == self.user.id,
                ),
            )
            .with_for_update()
        )
        if notification is None:
            raise AppError("RESOURCE_NOT_FOUND", "Data tidak ditemukan.", 404)
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
                or_(
                    OperationalNotification.recipient_user_id.is_(None),
                    OperationalNotification.recipient_user_id == self.user.id,
                ),
            )
        )
        return {
            "jobs": await counts(Job),
            "import_reviews": await counts(ImportReview),
            "unacknowledged_notifications": unacknowledged or 0,
            "generated_at": now(),
        }


async def resolve_notifications(session, *, tenant_id, resource_type, resource_id, actor_id):
    await session.execute(
        update(OperationalNotification)
        .where(
            OperationalNotification.tenant_id == tenant_id,
            OperationalNotification.resource_type == resource_type,
            OperationalNotification.resource_id == str(resource_id),
            OperationalNotification.acknowledged_at.is_(None),
        )
        .values(acknowledged_by=actor_id, acknowledged_at=now())
    )
