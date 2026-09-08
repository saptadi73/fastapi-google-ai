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
from app.schemas.import_review import ImportReviewCreate
from app.services.classification_service import ClassificationService
from app.services.job_service import enqueue
from app.services.source_service import SourceService
from app.services.import_review_service import ImportReviewService

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
    job = await enqueue(session, user, "ETL", str(source_id))
    return success({**job, "pipeline": "LEGACY_ETL", "review_required": True, "recommended_endpoint": f"/sources/{source_id}/sync-review"})


@router.post("/sources/{source_id}/sync-review", status_code=202, dependencies=edit)
async def sync_review(source_id: UUID, session: Session, user: CurrentUser):
    repo = SourceRepository(session, user.tenant_id)
    sheets = await repo.sheets(source_id)
    reviews = []
    seen = set()
    for sheet in sheets:
        config_id = sheet.active_configuration_id if sheet.dataset_kind != "MASTER" else None
        try:
            result = await ImportReviewService(session, user).create(
                ImportReviewCreate(source_sheet_id=sheet.id, configuration_id=config_id)
            )
            key = result.get("review", {}).get("id") if isinstance(result, dict) else None
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            reviews.append(result)
        except AppError as exc:
            reviews.append({"source_sheet_id": sheet.id, "status": "BLOCKED", "code": exc.code})
    return success({"source_id": str(source_id), "reviews": reviews})


@router.get("/sources/{source_id}/master-migration-preview")
async def master_migration_preview(source_id: UUID, session: Session, user: CurrentUser):
    repo = SourceRepository(session, user.tenant_id)
    sheets = await repo.sheets(source_id)
    result = []
    from app.services.master_service import MasterService

    masters = MasterService(session, user)
    for sheet in sheets:
        if sheet.dataset_kind != "MASTER":
            continue
        binding = await masters.binding_detail(sheet.id)
        result.append({"source_sheet_id": sheet.id, "sheet_name": sheet.sheet_name, "binding": binding, "migration_ready": bool(binding.get("metadata_ready") and binding.get("validation", {}).get("valid"))})
    return success({
        "source_id": str(source_id),
        "tabs": result,
        "destructive_apply": False,
        "rollback_plan": {
            "required_before_apply": True,
            "backup_snapshot_ids": [tab["binding"].get("binding", {}).get("snapshot_hash") for tab in result if tab["binding"].get("binding")],
            "strategy": "RETAIN_SOURCE_AND_RESTORE_TARGET_FROM_BACKUP",
        },
    })


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
