"""Configurable release gates for technical and affected-unit approval."""

from uuid import UUID

from fastapi import Depends, Query

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import success
from app.core.routing import APIRouter
from app.schemas.source import ConfigurationReleaseDecision, SourceReleasePolicyUpdate
from app.services.release_approval_service import ReleaseApprovalService

router = APIRouter(prefix="/release-approvals", tags=["Release approvals"])
admin = [Depends(require_roles("PLATFORM_ADMIN"))]


@router.get("/candidates", dependencies=admin)
async def candidates(session: Session, user: CurrentUser):
    return success(await ReleaseApprovalService(session, user).candidates())


@router.get("/inbox")
async def inbox(session: Session, user: CurrentUser, offset: int = Query(0, ge=0),
                limit: int = Query(50, ge=1, le=100)):
    return success(await ReleaseApprovalService(session, user).inbox(offset, limit))


@router.get("/sources/{source_id}/policy", dependencies=admin)
async def policy(source_id: UUID, session: Session, user: CurrentUser):
    return success(await ReleaseApprovalService(session, user).policy(source_id))


@router.put("/sources/{source_id}/policy", dependencies=admin)
async def replace_policy(source_id: UUID, data: SourceReleasePolicyUpdate,
                         session: Session, user: CurrentUser):
    return success(await ReleaseApprovalService(session, user).replace_policy(source_id, data))


@router.get("/configurations/{config_id}")
async def status(config_id: UUID, session: Session, user: CurrentUser):
    return success(await ReleaseApprovalService(session, user).status(config_id))


@router.post("/configurations/{config_id}/decisions")
async def decide(config_id: UUID, data: ConfigurationReleaseDecision,
                 session: Session, user: CurrentUser):
    return success(await ReleaseApprovalService(session, user).decide(config_id, data))
