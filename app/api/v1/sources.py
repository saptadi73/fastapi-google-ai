from uuid import UUID

from fastapi import Depends, Query

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import AppError, success
from app.core.routing import APIRouter
from app.domain.enums import EDIT_ROLES
from app.models.configuration import Configuration
from app.models.source import DataSource, SourceSheet
from app.repositories.base import record
from app.repositories.source_repository import SourceRepository
from app.schemas.configuration import AIConfigurationRequest
from app.schemas.source import SheetClassificationUpdate, SheetUpdate, SourceCreate
from app.services.classification_service import ClassificationService
from app.services.job_service import enqueue
from app.services.source_service import SourceService

router = APIRouter(tags=["Sources"], dependencies=[Depends(require_roles(*EDIT_ROLES, "TECHNICAL_APPROVER"))])
edit = [Depends(require_roles(*EDIT_ROLES))]


@router.get("/source-sheets/{sheet_id}/classification")
async def get_classification(sheet_id: UUID, session: Session, user: CurrentUser):
    return success(await ClassificationService(session, user).get(sheet_id))


@router.put("/source-sheets/{sheet_id}/classification", dependencies=edit)
async def classify_sheet(
    sheet_id: UUID, data: SheetClassificationUpdate, session: Session, user: CurrentUser
):
    return success(await ClassificationService(session, user).update(sheet_id, data))


@router.post("/sources/google-sheets", status_code=202, dependencies=edit)
async def create(data: SourceCreate, session: Session, user: CurrentUser):
    return success(await SourceService(session, user).register(data))


@router.get("/sources")
async def sources(
    session: Session, user: CurrentUser, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)
):
    return success(
        [
            record(s)
            for s in await SourceRepository(session, user.tenant_id).list(
                DataSource, offset=offset, limit=limit
            )
        ],
        offset=offset,
        limit=limit,
    )


@router.get("/sources/{source_id}")
async def get_source(source_id: UUID, session: Session, user: CurrentUser):
    return success(record(await SourceRepository(session, user.tenant_id).get(DataSource, source_id)))


@router.get("/sources/{source_id}/sheets")
async def sheets(source_id: UUID, session: Session, user: CurrentUser):
    return success([record(s) for s in await SourceRepository(session, user.tenant_id).sheets(source_id)])


@router.patch("/source-sheets/{sheet_id}", dependencies=edit)
async def update_sheet(sheet_id: UUID, data: SheetUpdate, session: Session, user: CurrentUser):
    return success(await SourceService(session, user).update_sheet(sheet_id, data))


@router.post("/sources/{source_id}/discover", status_code=202, dependencies=edit)
async def discover(source_id: UUID, session: Session, user: CurrentUser):
    return success(await enqueue(session, user, "DISCOVER", str(source_id)))


@router.post("/sources/{source_id}/profile", status_code=202, dependencies=edit)
async def profile(source_id: UUID, session: Session, user: CurrentUser):
    return success(await enqueue(session, user, "PROFILE", str(source_id)))


@router.post("/sources/{source_id}/sync", status_code=202, dependencies=edit)
async def sync(source_id: UUID, session: Session, user: CurrentUser):
    await ClassificationService(session, user).require_source_ready(source_id)
    return success(await enqueue(session, user, "ETL", str(source_id)))


@router.post("/sources/{source_id}/ai-configurations", status_code=202, dependencies=edit)
async def ai_configuration(
    source_id: UUID, data: AIConfigurationRequest, session: Session, user: CurrentUser
):
    sheet = await SourceRepository(session, user.tenant_id).get(SourceSheet, data.source_sheet_id)
    if sheet.source_id != str(source_id):
        raise AppError("RESOURCE_NOT_FOUND", "Tab tidak ditemukan pada source ini.", 404)
    return success(await enqueue(session, user, "AI_CONFIG", str(source_id), source_sheet_id=sheet.id))


@router.get("/source-sheets/{sheet_id}/configurations")
async def configurations(sheet_id: UUID, session: Session, user: CurrentUser):
    repo = SourceRepository(session, user.tenant_id)
    await repo.get(SourceSheet, sheet_id)
    return success(
        [
            record(c)
            for c in await repo.list(
                Configuration, conditions=(Configuration.source_sheet_id == str(sheet_id),)
            )
        ]
    )


@router.get("/source-sheets/{sheet_id}/configurations/active")
async def active_configuration(sheet_id: UUID, session: Session, user: CurrentUser):
    repo = SourceRepository(session, user.tenant_id)
    sheet = await repo.get(SourceSheet, sheet_id)
    return success(
        record(await repo.get(Configuration, sheet.active_configuration_id))
        if sheet.active_configuration_id
        else None
    )
