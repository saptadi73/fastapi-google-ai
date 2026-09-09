from uuid import UUID
from datetime import datetime, timezone
import hashlib
from fastapi import Depends
from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import success, AppError
from app.core.routing import APIRouter
from app.domain.enums import EDIT_ROLES, REVIEW_ROLES
from app.models.taxonomy import Taxonomy, TaxonomyTerm, TaxonomyColumnBinding
from app.models.source import SourceSheet
from app.repositories.base import TenantRepository, record
from app.schemas.taxonomy import TaxonomyCreate, TaxonomyTermCreate, TaxonomyColumnBindingCreate
from app.schemas.master import MasterRevisionRequest

router = APIRouter(prefix="/taxonomies", tags=["Taxonomy"], dependencies=[Depends(require_roles(*EDIT_ROLES, *REVIEW_ROLES))])
edit = [Depends(require_roles(*EDIT_ROLES))]
review = [Depends(require_roles(*REVIEW_ROLES))]


@router.post("", dependencies=edit, status_code=201)
async def create_taxonomy(data: TaxonomyCreate, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    fp = hashlib.sha256(data.code.encode()).hexdigest()
    snap = hashlib.sha256(f"{data.code}:{data.name}".encode()).hexdigest()
    return success(record(await repo.add(Taxonomy, code=data.code, name=data.name, created_by=user.id, fingerprint=fp, snapshot_hash=snap)))


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
    fp = hashlib.sha256(f"{taxonomy_id}:{data.code}".encode()).hexdigest()
    snap = hashlib.sha256(f"{taxonomy_id}:{data.code}:{data.label}".encode()).hexdigest()
    return success(record(await repo.add(TaxonomyTerm, taxonomy_id=str(taxonomy_id), fingerprint=fp, snapshot_hash=snap, created_by=user.id, **data.model_dump())))


@router.post("/{taxonomy_id}/approve", dependencies=review)
async def approve_taxonomy(taxonomy_id: UUID, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    taxonomy = await repo.get(Taxonomy, taxonomy_id)
    taxonomy.status, taxonomy.version = "APPROVED", taxonomy.version + 1
    return success(record(taxonomy))


@router.get("/source-sheets/{sheet_id}/column-bindings")
async def list_column_bindings(sheet_id: UUID, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    await repo.get(SourceSheet, sheet_id)
    rows = (await session.scalars(repo.query(TaxonomyColumnBinding).where(TaxonomyColumnBinding.source_sheet_id == str(sheet_id)))).all()
    return success([record(row) for row in rows])


@router.put("/source-sheets/{sheet_id}/column-bindings", dependencies=edit)
async def save_column_binding(sheet_id: UUID, data: TaxonomyColumnBindingCreate, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    await repo.get(SourceSheet, sheet_id)
    taxonomy = await repo.get(Taxonomy, data.taxonomy_id)
    if taxonomy.status != "APPROVED" or not taxonomy.is_active:
        raise AppError("TAXONOMY_NOT_APPROVED", "Taxonomy harus approved dan aktif sebelum dipetakan.", 422)
    if data.taxonomy_version != taxonomy.version:
        raise AppError("TAXONOMY_VERSION_MISMATCH", "Versi taxonomy sudah berubah; muat ulang rekomendasi.", 409)
    existing = (await session.scalars(repo.query(TaxonomyColumnBinding).where(TaxonomyColumnBinding.source_sheet_id == str(sheet_id), TaxonomyColumnBinding.source_column == data.source_column))).first()
    values = data.model_dump()
    values.pop("revision_no", None)
    values["taxonomy_id"] = str(data.taxonomy_id)
    if existing:
        if data.revision_no != existing.revision_no:
            raise AppError("REVISION_CONFLICT", "Binding telah berubah; ambil data terbaru.", 409)
        for key, value in values.items(): setattr(existing, key, value)
        existing.revision_no += 1; existing.status = "DRAFT"; existing.approved_by = None; existing.approved_at = None
        return success(record(existing))
    fp = hashlib.sha256(f"{sheet_id}:{data.source_column}".encode()).hexdigest()
    snap = hashlib.sha256(f"{data.taxonomy_id}:{data.taxonomy_version}:{data.source_column}".encode()).hexdigest()
    return success(record(await repo.add(TaxonomyColumnBinding, source_sheet_id=str(sheet_id), created_by=user.id, fingerprint=fp, snapshot_hash=snap, **values)))


@router.post("/column-bindings/{binding_id}/approve", dependencies=review)
async def approve_column_binding(binding_id: UUID, data: MasterRevisionRequest, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    binding = await repo.get(TaxonomyColumnBinding, binding_id)
    if data.revision_no != binding.revision_no:
        raise AppError("REVISION_CONFLICT", "Binding telah berubah; ambil data terbaru.", 409)
    binding.status, binding.approved_by, binding.approved_at = "APPROVED", user.id, datetime.now(timezone.utc)
    return success(record(binding))


@router.post("/column-bindings/{binding_id}/reject", dependencies=review)
async def reject_column_binding(binding_id: UUID, data: MasterRevisionRequest, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    binding = await repo.get(TaxonomyColumnBinding, binding_id)
    if data.revision_no != binding.revision_no:
        raise AppError("REVISION_CONFLICT", "Binding telah berubah; ambil data terbaru.", 409)
    binding.status, binding.approved_by, binding.approved_at = "REJECTED", None, None
    return success(record(binding))
