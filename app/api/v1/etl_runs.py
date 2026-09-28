from uuid import UUID

from fastapi import Depends, Query

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import AppError, success
from app.core.routing import APIRouter
from app.domain.enums import EDIT_ROLES
from app.models.etl import ETLRun, Job, QualityIssue, StagingRow
from app.models.source import DataSource
from app.repositories.base import TenantRepository, record
from app.schemas.access import AccessEvaluationRequest
from app.services.access_service import AccessService
from app.services.job_service import enqueue
from app.services.monitoring_service import MonitoringService
from app.services.source_service import source_records

router = APIRouter(
    tags=["Jobs and ETL"], dependencies=[Depends(require_roles(*EDIT_ROLES, "TECHNICAL_APPROVER"))]
)


async def _guard_run_source(session, user, run):
    if not await _source_discover_allowed(session, user, run.source_id):
        raise AppError("ETL_RUN_NOT_FOUND", "ETL run tidak tersedia untuk akses Anda.", 404)


async def _source_discover_allowed(session, user, source_id):
    source = await TenantRepository(session, user.tenant_id).get(DataSource, source_id)
    if source.access_metadata is None:
        return True
    decision = await AccessService(session, user).evaluate(
        AccessEvaluationRequest(
            action="DISCOVER", resource_type="SOURCE", resource_id=source.source_code
        )
    )
    return decision["allowed"]


@router.get("/jobs")
async def jobs(
    session: Session, user: CurrentUser, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)
):
    items = await TenantRepository(session, user.tenant_id).list(Job, offset=offset, limit=limit)
    visible = [j for j in items if j.source_id is None or await _source_discover_allowed(session, user, j.source_id)]
    return success(
        [record(j) for j in visible],
        offset=offset,
        limit=limit,
    )


@router.get("/jobs/{job_id}")
async def job(job_id: UUID, session: Session, user: CurrentUser):
    return success(record(await TenantRepository(session, user.tenant_id).get(Job, job_id)))


@router.post("/jobs/{job_id}/retry", status_code=202)
async def retry(job_id: UUID, session: Session, user: CurrentUser):
    return success(await MonitoringService(session, user).retry(job_id))


@router.get("/etl-jobs")
async def schedules(session: Session, user: CurrentUser):
    sources = await TenantRepository(session, user.tenant_id).list(DataSource)
    visible = [source for source in sources if await _source_discover_allowed(session, user, source.id)]
    return success(await source_records(session, visible))


@router.post("/etl-jobs/{job_id}/run", status_code=202, dependencies=[Depends(require_roles(*EDIT_ROLES))])
async def run(job_id: UUID, session: Session, user: CurrentUser):
    return success(await enqueue(session, user, "ETL", str(job_id)))


@router.post("/etl-jobs/{job_id}/pause", dependencies=[Depends(require_roles(*EDIT_ROLES))])
async def pause(job_id: UUID, session: Session, user: CurrentUser):
    return success(await MonitoringService(session, user).pause(job_id, True))


@router.post("/etl-jobs/{job_id}/resume", dependencies=[Depends(require_roles(*EDIT_ROLES))])
async def resume(job_id: UUID, session: Session, user: CurrentUser):
    return success(await MonitoringService(session, user).pause(job_id, False))


@router.get("/etl-runs")
async def runs(
    session: Session, user: CurrentUser, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)
):
    items = await TenantRepository(session, user.tenant_id).list(ETLRun, offset=offset, limit=limit)
    visible = [r for r in items if await _source_discover_allowed(session, user, r.source_id)]
    return success(
        [record(r) for r in visible],
        offset=offset,
        limit=limit,
    )


@router.get("/etl-runs/{run_id}")
async def etl_run(run_id: UUID, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    run = await repo.get(ETLRun, run_id)
    await _guard_run_source(session, user, run)
    return success(record(run))


@router.get("/etl-runs/{run_id}/errors")
async def errors(run_id: UUID, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    run = await repo.get(ETLRun, run_id)
    await _guard_run_source(session, user, run)
    return success(
        [
            record(r, exclude=("data",))
            for r in await repo.list(QualityIssue, conditions=(QualityIssue.etl_run_id == str(run_id),))
        ]
    )


@router.get("/etl-runs/{run_id}/lineage")
async def lineage(
    run_id: UUID,
    session: Session,
    user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    repo = TenantRepository(session, user.tenant_id)
    run = await repo.get(ETLRun, run_id)
    await _guard_run_source(session, user, run)
    rows = await repo.list(
        StagingRow, offset=offset, limit=limit, conditions=(StagingRow.etl_run_id == str(run_id),)
    )
    return success(
        {
            "configuration_id": run.configuration_id,
            "source_sheet_id": run.source_sheet_id,
            "snapshot_id": run.snapshot_id,
            "source_rows": [r.source_row for r in rows],
        },
        offset=offset,
        limit=limit,
    )
