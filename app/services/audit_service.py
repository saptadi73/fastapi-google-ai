from app.models.audit import AuditEvent


def audit(session, user, event, resource_id=None, **details):
    session.add(
        AuditEvent(
            tenant_id=user.tenant_id,
            user_id=user.id,
            event=event,
            resource_id=str(resource_id) if resource_id else None,
            details=details,
        )
    )


def system_audit(session, tenant_id, event, resource_id=None, **details):
    details["actor_type"] = "SYSTEM"
    session.add(
        AuditEvent(
            tenant_id=tenant_id,
            user_id=None,
            event=event,
            resource_id=str(resource_id) if resource_id else None,
            details=details,
        )
    )
