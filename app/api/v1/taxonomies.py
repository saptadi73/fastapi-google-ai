from uuid import UUID
from fastapi import Depends
from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import success, AppError
from app.core.routing import APIRouter
from app.domain.enums import EDIT_ROLES, REVIEW_ROLES
from app.models.taxonomy import Taxonomy, TaxonomyTerm
from app.repositories.base import TenantRepository, record
from app.schemas.taxonomy import TaxonomyCreate, TaxonomyTermCreate

router = APIRouter(prefix="/taxonomies", tags=["Taxonomy"], dependencies=[Depends(require_roles(*EDIT_ROLES, *REVIEW_ROLES))])
edit = [Depends(require_roles(*EDIT_ROLES))]
review = [Depends(require_roles(*REVIEW_ROLES))]


@router.post("", dependencies=edit, status_code=201)
async def create_taxonomy(data: TaxonomyCreate, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    return success(record(await repo.add(Taxonomy, code=data.code, name=data.name, created_by=user.id)))


@router.get("")
async def list_taxonomies(session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    return success([record(item) for item in await repo.list(Taxonomy)])


@router.get("/{taxonomy_id}/terms")
async def list_terms(taxonomy_id: UUID, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    await repo.get(Taxonomy, taxonomy_id)
    terms = (await session.scalars(repo.query(TaxonomyTerm).where(TaxonomyTerm.taxonomy_id == str(taxonomy_id)))).all()
    return success([record(term) for term in terms])


@router.post("/{taxonomy_id}/terms", dependencies=edit, status_code=201)
async def create_term(taxonomy_id: UUID, data: TaxonomyTermCreate, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    await repo.get(Taxonomy, taxonomy_id)
    if data.parent_id:
        parent = await repo.get(TaxonomyTerm, data.parent_id)
        if parent.taxonomy_id != str(taxonomy_id):
            raise AppError("TAXONOMY_PARENT_INVALID", "Parent term harus berasal dari taxonomy yang sama.", 422)
    return success(record(await repo.add(TaxonomyTerm, taxonomy_id=str(taxonomy_id), **data.model_dump())))


@router.post("/{taxonomy_id}/approve", dependencies=review)
async def approve_taxonomy(taxonomy_id: UUID, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    taxonomy = await repo.get(Taxonomy, taxonomy_id)
    taxonomy.status, taxonomy.version = "APPROVED", taxonomy.version + 1
    return success(record(taxonomy))
