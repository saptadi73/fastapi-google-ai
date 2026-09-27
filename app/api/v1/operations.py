from uuid import UUID

from fastapi import Depends, Query

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import success
from app.core.routing import APIRouter
from app.domain.enums import EDIT_ROLES
from app.services.notification_service import NotificationService

router = APIRouter(
    tags=["Operations"], dependencies=[Depends(require_roles(*EDIT_ROLES, "TECHNICAL_APPROVER"))]
)


@router.get("/operations/summary")
async def summary(session: Session, user: CurrentUser):
    return success(await NotificationService(session, user).summary())


@router.get("/notifications")
async def notifications(
    session: Session,
    user: CurrentUser,
    unacknowledged_only: bool = True,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    result = await NotificationService(session, user).list(
        unacknowledged_only=unacknowledged_only, offset=offset, limit=limit
    )
    return success(result["items"], offset=offset, limit=limit, has_more=result["has_more"])


@router.post("/notifications/{notification_id}/acknowledge")
async def acknowledge(notification_id: UUID, session: Session, user: CurrentUser):
    return success(await NotificationService(session, user).acknowledge(notification_id))
