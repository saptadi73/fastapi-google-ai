from uuid import UUID

from fastapi import Depends, Query

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import success
from app.core.routing import APIRouter
from app.domain.enums import DATA_ROLES
from app.models.etl import QualityIssue
from app.models.source import DataSource
from app.repositories.base import TenantRepository, record
from app.schemas.monitoring import ResolutionRequest
from app.services.job_service import enqueue
from app.services.monitoring_service import MonitoringService

router = APIRouter(tags=["Data quality"], dependencies=[Depends(require_roles(*DATA_ROLES))])


@router.get("/data-quality/issues")
async def issues(
    session: Session, user: CurrentUser, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)
):
    return success(
        [
            record(r, exclude=("data",))
            for r in await TenantRepository(session, user.tenant_id).list(
                QualityIssue, offset=offset, limit=limit
            )
        ],
        offset=offset,
        limit=limit,
    )


@router.post("/data-quality/issues/{issue_id}/resolve")
async def resolve(issue_id: UUID, data: ResolutionRequest, session: Session, user: CurrentUser):
    return success(await MonitoringService(session, user).resolve(issue_id, data.resolution))


@router.get("/quarantine/{source_id}/rows")
async def quarantine(
    source_id: UUID,
    session: Session,
    user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    repo = TenantRepository(session, user.tenant_id)
    await repo.get(DataSource, source_id)
    return success(
        [
            record(r)
            for r in await repo.list(
                QualityIssue,
                offset=offset,
                limit=limit,
                conditions=(QualityIssue.source_id == str(source_id),),
            )
        ],
        offset=offset,
        limit=limit,
    )


@router.post("/quarantine/{source_id}/reprocess", status_code=202)
async def reprocess(source_id: UUID, session: Session, user: CurrentUser):
    # Re-read corrected source data under the active config; never load unreviewed quarantine edits.
    return success(await enqueue(session, user, "ETL", str(source_id)))
