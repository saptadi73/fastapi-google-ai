from uuid import UUID

from fastapi import Depends, Query

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import AppError, success
from app.core.routing import APIRouter
from app.domain.enums import DATA_ROLES
from app.models.semantic import QueryRequest
from app.repositories.base import TenantRepository, record
from app.schemas.nl2sql import (
    FeedbackRequest,
    QuestionRequest,
    SavedNL2SQLQueryCreate,
    SavedNL2SQLQueryUpdate,
)
from app.schemas.semantic import SavedQueryCreate
from app.services.nl2sql_service import NL2SQLService
from app.services.saved_nl2sql_service import SavedNL2SQLService
from app.services.semantic_catalog_service import SemanticCatalogService

router = APIRouter(prefix="/nl2sql", tags=["NL2SQL"])


async def owned_log(session, user, request_id):
    log = await TenantRepository(session, user.tenant_id).get(QueryRequest, request_id)
    if log.user_id != user.id and user.role != "PLATFORM_ADMIN":
        raise AppError("RESOURCE_NOT_FOUND", "Query request tidak ditemukan.", 404)
    return log


@router.post("/query")
async def query(data: QuestionRequest, session: Session, user: CurrentUser):
    result = await NL2SQLService(session, user).query(data)
    return success(result["rows"], **result["meta"])


@router.get("/requests/{request_id}")
async def request_log(request_id: UUID, session: Session, user: CurrentUser):
    return success(record(await owned_log(session, user, request_id)))


@router.post("/requests/{request_id}/feedback")
async def feedback(request_id: UUID, data: FeedbackRequest, session: Session, user: CurrentUser):
    log = await owned_log(session, user, request_id)
    log.feedback = data.feedback
    return success({"recorded": True})


@router.get("/saved-commands")
async def saved_commands(
    session: Session,
    user: CurrentUser,
    q: str = Query(default="", max_length=200),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    return success(await SavedNL2SQLService(session, user).list(search=q, offset=offset, limit=limit))


@router.get("/saved-commands/{query_id}")
async def saved_command(query_id: UUID, session: Session, user: CurrentUser):
    service = SavedNL2SQLService(session, user)
    return success(service.payload(await service.owned(query_id)))


@router.patch("/saved-commands/{query_id}")
async def update_saved_command(
    query_id: UUID, data: SavedNL2SQLQueryUpdate, session: Session, user: CurrentUser
):
    return success(await SavedNL2SQLService(session, user).update(query_id, data))


@router.delete("/saved-commands/{query_id}")
async def delete_saved_command(query_id: UUID, session: Session, user: CurrentUser):
    return success(await SavedNL2SQLService(session, user).delete(query_id))


@router.post("/saved-commands/{query_id}/run")
async def run_saved_command(query_id: UUID, session: Session, user: CurrentUser):
    result = await SavedNL2SQLService(session, user).run(query_id)
    return success(result["rows"], **result["meta"])


@router.post("/requests/{request_id}/saved-command", status_code=201)
async def create_saved_command(
    request_id: UUID,
    data: SavedNL2SQLQueryCreate,
    session: Session,
    user: CurrentUser,
):
    return success(await SavedNL2SQLService(session, user).create_from_request(request_id, data))


@router.post("/clarifications/{request_id}")
async def clarify(request_id: UUID, data: QuestionRequest, session: Session, user: CurrentUser):
    log = await owned_log(session, user, request_id)
    if log.status != "CLARIFICATION_REQUIRED":
        raise AppError("QUERY_CONFLICT", "Request tidak menunggu klarifikasi.", 409)
    result = await NL2SQLService(session, user).query(data)
    return success(result["rows"], **result["meta"], parent_request_id=str(request_id))


@router.post(
    "/requests/{request_id}/promote", status_code=201, dependencies=[Depends(require_roles(*DATA_ROLES))]
)
async def promote(request_id: UUID, data: SavedQueryCreate, session: Session, user: CurrentUser):
    log = await TenantRepository(session, user.tenant_id).get(QueryRequest, request_id)
    if (
        log.status != "SUCCEEDED"
        or data.plan.model_dump(mode="json") != log.plan.get("plan")
        or data.data_product_code != log.plan.get("data_product_code")
    ):
        raise AppError("QUERY_CONFLICT", "Template harus cocok dengan query yang berhasil dijalankan.", 409)
    return success(await SemanticCatalogService(session, user).create_saved(data))
