from uuid import UUID

from fastapi import Depends, Query

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import success
from app.core.routing import APIRouter
from app.domain.enums import EDIT_ROLES, REVIEW_ROLES
from app.models.master import MasterDefinition
from app.repositories.base import record
from app.schemas.master import (
    MasterBindingUpdate,
    MasterDefinitionCreate,
    MasterDefinitionPatch,
    MasterRevisionRequest,
    MasterColumnBindingCreate,
)
from app.services.master_service import MasterService
from app.services.master_storage_service import MasterStorageService

router = APIRouter(
    tags=["Master registry"], dependencies=[Depends(require_roles(*EDIT_ROLES, *REVIEW_ROLES))]
)
edit = [Depends(require_roles(*EDIT_ROLES))]
review = [Depends(require_roles(*REVIEW_ROLES))]


@router.get("/master-definitions/{master_id}/storage-plan")
async def master_storage_plan(master_id: UUID, session: Session, user: CurrentUser):
    return success(await MasterStorageService(session, user).plan(master_id))


@router.post("/master-definitions/{master_id}/deploy-storage", dependencies=review)
async def deploy_master_storage(
    master_id: UUID, data: MasterRevisionRequest, session: Session, user: CurrentUser
):
    return success(await MasterStorageService(session, user).deploy(master_id, data))


@router.get("/master-definitions/{master_id}/records")
async def master_records(
    master_id: UUID,
    session: Session,
    user: CurrentUser,
    search: str = Query("", max_length=200),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    active_only: bool = True,
    record_id: UUID | None = None,
):
    return success(
        await MasterStorageService(session, user).records(
            master_id, search, offset, limit, active_only, record_id
        ),
        offset=offset,
        limit=limit,
    )


@router.get("/master-definitions")
async def list_masters(
    session: Session,
    user: CurrentUser,
    search: str = Query("", max_length=200),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    return success(await MasterService(session, user).list(search, offset, limit), offset=offset, limit=limit)


@router.post("/master-definitions/preview", dependencies=edit)
async def preview_master(
    data: MasterDefinitionCreate, session: Session, user: CurrentUser, against: UUID | None = None
):
    service = MasterService(session, user)
    if against:
        await service.repo.get(MasterDefinition, against)
    return success(
        {
            "candidates": await service.candidates(data.definition, exclude_id=against),
            "creates_master": False,
        }
    )


@router.post("/master-definitions", status_code=201, dependencies=edit)
async def create_master(data: MasterDefinitionCreate, session: Session, user: CurrentUser):
    return success(record(await MasterService(session, user).create(data)))


@router.get("/master-definitions/{master_id}")
async def get_master(master_id: UUID, session: Session, user: CurrentUser):
    return success(record(await MasterService(session, user).repo.get(MasterDefinition, master_id)))


@router.patch("/master-definitions/{master_id}", dependencies=edit)
async def patch_master(master_id: UUID, data: MasterDefinitionPatch, session: Session, user: CurrentUser):
    return success(record(await MasterService(session, user).patch(master_id, data)))


@router.post("/master-definitions/{master_id}/submit-review", dependencies=edit)
async def submit_master(master_id: UUID, data: MasterRevisionRequest, session: Session, user: CurrentUser):
    return success(record(await MasterService(session, user).action(master_id, data, "submit-review")))


@router.post("/master-definitions/{master_id}/approve", dependencies=review)
async def approve_master(master_id: UUID, data: MasterRevisionRequest, session: Session, user: CurrentUser):
    return success(record(await MasterService(session, user).action(master_id, data, "approve")))


@router.post("/master-definitions/{master_id}/reject", dependencies=review)
async def reject_master(master_id: UUID, data: MasterRevisionRequest, session: Session, user: CurrentUser):
    return success(record(await MasterService(session, user).action(master_id, data, "reject")))


@router.post("/master-definitions/{master_id}/deactivate", dependencies=review)
async def deactivate_master(
    master_id: UUID, data: MasterRevisionRequest, session: Session, user: CurrentUser
):
    return success(record(await MasterService(session, user).action(master_id, data, "deactivate")))


@router.get("/source-sheets/{sheet_id}/master-binding")
async def get_binding(sheet_id: UUID, session: Session, user: CurrentUser):
    return success(await MasterService(session, user).binding_detail(sheet_id))


@router.put("/source-sheets/{sheet_id}/master-binding", dependencies=edit)
async def put_binding(sheet_id: UUID, data: MasterBindingUpdate, session: Session, user: CurrentUser):
    return success(await MasterService(session, user).save_binding(sheet_id, data))


@router.post("/source-sheets/{sheet_id}/master-binding/approve", dependencies=review)
async def approve_binding(sheet_id: UUID, data: MasterRevisionRequest, session: Session, user: CurrentUser):
    return success(record(await MasterService(session, user).binding_decision(sheet_id, data, True)))


@router.post("/source-sheets/{sheet_id}/master-binding/reject", dependencies=review)
async def reject_binding(sheet_id: UUID, data: MasterRevisionRequest, session: Session, user: CurrentUser):
    return success(record(await MasterService(session, user).binding_decision(sheet_id, data, False)))


@router.get("/source-sheets/{sheet_id}/column-bindings")
async def get_column_bindings(sheet_id: UUID, session: Session, user: CurrentUser):
    return success(await MasterService(session, user).column_bindings(sheet_id))


@router.put("/source-sheets/{sheet_id}/column-bindings", dependencies=edit)
async def put_column_binding(
    sheet_id: UUID, data: MasterColumnBindingCreate, session: Session, user: CurrentUser
):
    return success(await MasterService(session, user).save_column_binding(sheet_id, data))


@router.post("/column-bindings/{binding_id}/approve", dependencies=review)
async def approve_column_binding(
    binding_id: UUID, data: MasterRevisionRequest, session: Session, user: CurrentUser
):
    return success(await MasterService(session, user).column_binding_decision(binding_id, data, True))


@router.post("/column-bindings/{binding_id}/reject", dependencies=review)
async def reject_column_binding(
    binding_id: UUID, data: MasterRevisionRequest, session: Session, user: CurrentUser
):
    return success(await MasterService(session, user).column_binding_decision(binding_id, data, False))
