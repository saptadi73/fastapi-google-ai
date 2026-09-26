from uuid import UUID

from fastapi import Depends

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import success
from app.core.routing import APIRouter
from app.domain.enums import DATA_ROLES
from app.models.semantic import JoinRelationship, SavedQuery
from app.repositories.base import record
from app.schemas.semantic import (
    JoinRelationshipAction,
    JoinRelationshipCreate,
    JoinRelationshipUpdate,
    ProductUpdate,
    SavedQueryCreate,
)
from app.services.semantic_catalog_service import SemanticCatalogService

router = APIRouter(prefix="/semantic", tags=["Semantic catalog"])
admin = [Depends(require_roles(*DATA_ROLES))]


@router.get("/data-products")
async def products(session: Session, user: CurrentUser):
    return success(await SemanticCatalogService(session, user).products())


@router.patch("/data-products/{product_id}", dependencies=admin)
async def patch_product(product_id: UUID, data: ProductUpdate, session: Session, user: CurrentUser):
    return success(await SemanticCatalogService(session, user).update_product(product_id, data))


@router.get("/metrics")
async def metrics(session: Session, user: CurrentUser):
    products = await SemanticCatalogService(session, user).products()
    return success([{"data_product": p["code"], **m} for p in products for m in p["metrics"]])


@router.get("/join-relationships")
async def join_relationships(session: Session, user: CurrentUser):
    service = SemanticCatalogService(session, user)
    return success([record(item) for item in await service.repo.list(JoinRelationship)])


@router.post("/join-relationships", status_code=201, dependencies=admin)
async def create_join_relationship(data: JoinRelationshipCreate, session: Session, user: CurrentUser):
    return success(await SemanticCatalogService(session, user).create_join_relationship(data))


@router.patch("/join-relationships/{relationship_id}", dependencies=admin)
async def update_join_relationship(relationship_id: UUID, data: JoinRelationshipUpdate, session: Session, user: CurrentUser):
    return success(await SemanticCatalogService(session, user).update_join_relationship(relationship_id, data))


@router.post("/join-relationships/{relationship_id}/approve", dependencies=admin)
async def approve_join_relationship(relationship_id: UUID, data: JoinRelationshipAction, session: Session, user: CurrentUser):
    return success(await SemanticCatalogService(session, user).approve_join_relationship(relationship_id, data))


@router.post("/join-relationships/{relationship_id}/reject", dependencies=admin)
async def reject_join_relationship(relationship_id: UUID, data: JoinRelationshipAction, session: Session, user: CurrentUser):
    return success(await SemanticCatalogService(session, user).reject_join_relationship(relationship_id, data))


@router.get("/intents")
@router.get("/query-templates")
async def saved_queries(session: Session, user: CurrentUser):
    service = SemanticCatalogService(session, user)
    items = await service.repo.list(SavedQuery)
    return success([record(i) for i in items if user.role in i.allowed_roles])


@router.post("/intents", status_code=201, dependencies=admin)
@router.post("/query-templates", status_code=201, dependencies=admin)
async def create_saved(data: SavedQueryCreate, session: Session, user: CurrentUser):
    return success(await SemanticCatalogService(session, user).create_saved(data))


@router.post("/query-templates/{template_id}/validate", dependencies=admin)
async def validate_template(template_id: UUID, session: Session, user: CurrentUser):
    return success(await SemanticCatalogService(session, user).validate_saved(template_id))


@router.post("/query-templates/{template_id}/activate", dependencies=admin)
async def activate_template(template_id: UUID, session: Session, user: CurrentUser):
    return success(await SemanticCatalogService(session, user).activate_saved(template_id))
