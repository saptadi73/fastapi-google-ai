from fastapi import Depends, Query

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import success
from app.core.routing import APIRouter
from app.models.audit import AuditEvent
from app.repositories.base import TenantRepository, record
from app.services.monitoring_service import MonitoringService

router = APIRouter(
    prefix="/admin", tags=["Audit and AI usage"], dependencies=[Depends(require_roles("PLATFORM_ADMIN"))]
)


@router.get("/ai-usage/summary")
@router.get("/ai-usage/by-tenant")
async def summary(session: Session, user: CurrentUser):
    return success(await MonitoringService(session, user).ai_summary())


@router.get("/ai-usage/by-user")
async def by_user(session: Session, user: CurrentUser):
    return success(await MonitoringService(session, user).ai_summary(by_user=True))


@router.get("/audit-events")
async def events(
    session: Session, user: CurrentUser, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)
):
    return success(
        [
            record(e)
            for e in await TenantRepository(session, user.tenant_id).list(
                AuditEvent, offset=offset, limit=limit
            )
        ],
        offset=offset,
        limit=limit,
    )
