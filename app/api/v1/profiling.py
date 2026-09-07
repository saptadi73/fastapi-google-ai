from uuid import UUID

from fastapi import Depends

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import AppError, success
from app.core.routing import APIRouter
from app.domain.enums import EDIT_ROLES
from app.models.source import DataSource, ProfilingRun
from app.repositories.base import record
from app.repositories.source_repository import SourceRepository

router = APIRouter(
    tags=["Profiling"], dependencies=[Depends(require_roles(*EDIT_ROLES, "TECHNICAL_APPROVER"))]
)


@router.get("/sources/{source_id}/profiling-runs")
async def profiles(source_id: UUID, session: Session, user: CurrentUser):
    repo = SourceRepository(session, user.tenant_id)
    await repo.get(DataSource, source_id)
    return success(
        [
            record(p)
            for p in await repo.list(ProfilingRun, conditions=(ProfilingRun.source_id == str(source_id),))
        ]
    )


@router.get("/sources/{source_id}/profiling-runs/{run_id}")
async def profile(source_id: UUID, run_id: UUID, session: Session, user: CurrentUser):
    run = await SourceRepository(session, user.tenant_id).get(ProfilingRun, run_id)
    if run.source_id != str(source_id):
        raise AppError("RESOURCE_NOT_FOUND", "Profile tidak ditemukan.", 404)
    return success(record(run))
