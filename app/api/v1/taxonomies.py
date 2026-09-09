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
from app.models.import_review import ImportReview, ImportQuestion
from app.repositories.base import TenantRepository, record
from app.schemas.taxonomy import TaxonomyCreate, TaxonomyTermCreate, TaxonomyColumnBindingCreate, TaxonomyTermResolveRequest, TaxonomyAmbiguityQuestionRequest, TaxonomyValuesValidateRequest, TaxonomyRecommendRequest
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


@router.post("/{taxonomy_id}/resolve-term")
async def resolve_term(taxonomy_id: UUID, data: TaxonomyTermResolveRequest, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    taxonomy = await repo.get(Taxonomy, taxonomy_id)
    if taxonomy.status != "APPROVED" or not taxonomy.is_active:
        raise AppError("TAXONOMY_NOT_APPROVED", "Taxonomy harus approved dan aktif.", 422)
    value = data.value.strip().casefold()
    terms = (await session.scalars(repo.query(TaxonomyTerm).where(TaxonomyTerm.taxonomy_id == str(taxonomy_id), TaxonomyTerm.is_active.is_(True)))).all()
    exact = [t for t in terms if t.code.casefold() == value or t.label.casefold() == value or value in {str(a).casefold() for a in (t.aliases or [])}]
    if len(exact) == 1:
        return success({"status": "EXACT", "taxonomy_id": str(taxonomy_id), "taxonomy_version": taxonomy.version, "term": record(exact[0]), "requires_question": False})
    from difflib import SequenceMatcher
    candidates = [t for t in terms if value in t.label.casefold() or value in t.code.casefold() or any(value in str(a).casefold() for a in (t.aliases or []))]
    candidates.sort(key=lambda t: max(SequenceMatcher(None, value, t.label.casefold()).ratio(), SequenceMatcher(None, value, t.code.casefold()).ratio()), reverse=True)
    status = "AMBIGUOUS" if len(candidates) > 1 else "NOT_FOUND" if not candidates else "CANDIDATE"
    return success({"status": status, "taxonomy_id": str(taxonomy_id), "taxonomy_version": taxonomy.version, "candidates": [record(t) for t in candidates[:10]], "requires_question": status != "EXACT"})


@router.post("/{taxonomy_id}/ambiguity-question", dependencies=edit, status_code=201)
async def create_ambiguity_question(taxonomy_id: UUID, data: TaxonomyAmbiguityQuestionRequest, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    await repo.get(Taxonomy, taxonomy_id)
    review = await repo.get(ImportReview, data.import_review_id)
    resolution = await resolve_term(taxonomy_id, TaxonomyTermResolveRequest(value=data.value), session, user)
    payload = resolution.get("data", resolution)
    if not payload.get("requires_question"):
        return success({"created": False, "resolution": payload})
    key = f"taxonomy:{taxonomy_id}:{data.staging_row_id}:{data.source_column}:{data.value.casefold()}"[:64]
    existing = (await session.scalars(repo.query(ImportQuestion).where(ImportQuestion.import_review_id == str(review.id), ImportQuestion.question_key == key))).first()
    if existing:
        return success(record(existing))
    candidates = payload.get("candidates", [])
    q = await repo.add(ImportQuestion, import_review_id=str(review.id), staging_row_id=str(data.staging_row_id) if data.staging_row_id else None, source_column=data.source_column, target_column=data.target_column, source_row=None, question_key=key, category="TAXONOMY_AMBIGUOUS", prompt=f"Pilih term taxonomy untuk nilai '{data.value}'.", allowed_actions=["SELECT_RECORD", "CORRECT_SOURCE"], candidates=candidates, evidence={"taxonomy_id": str(taxonomy_id), "taxonomy_version": payload.get("taxonomy_version")}, status="OPEN", revision_no=1, fingerprint=key, snapshot_hash=key)
    return success(record(q))


@router.post("/{taxonomy_id}/validate-values")
async def validate_taxonomy_values(taxonomy_id: UUID, data: TaxonomyValuesValidateRequest, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    taxonomy = await repo.get(Taxonomy, taxonomy_id)
    if taxonomy.status != "APPROVED" or not taxonomy.is_active:
        raise AppError("TAXONOMY_NOT_APPROVED", "Taxonomy harus approved dan aktif.", 422)
    if data.taxonomy_version is not None and data.taxonomy_version != taxonomy.version:
        return success({"valid": False, "code": "TAXONOMY_VERSION_STALE", "expected_version": taxonomy.version, "received_version": data.taxonomy_version})
    terms = (await session.scalars(repo.query(TaxonomyTerm).where(TaxonomyTerm.taxonomy_id == str(taxonomy_id), TaxonomyTerm.is_active.is_(True)))).all()
    index = {}
    for term in terms:
        for key in [term.code, term.label, *(term.aliases or [])]: index[str(key).strip().casefold()] = term
    invalid, ambiguous = [], []
    for raw in data.values:
        key = raw.strip().casefold()
        matches = [t for t in terms if key in {t.code.casefold(), t.label.casefold(), *(str(a).casefold() for a in (t.aliases or []))}]
        if not matches: invalid.append(raw)
        elif len(matches) > 1: ambiguous.append(raw)
    return success({"valid": not invalid and not ambiguous, "taxonomy_version": taxonomy.version, "checked": len(data.values), "invalid_values": invalid[:100], "ambiguous_values": ambiguous[:100]})


@router.post("/{taxonomy_id}/recommend-terms")
async def recommend_terms(taxonomy_id: UUID, data: TaxonomyRecommendRequest, session: Session, user: CurrentUser):
    from difflib import SequenceMatcher
    repo = TenantRepository(session, user.tenant_id)
    taxonomy = await repo.get(Taxonomy, taxonomy_id)
    if taxonomy.status != "APPROVED" or not taxonomy.is_active:
        raise AppError("TAXONOMY_NOT_APPROVED", "Taxonomy harus approved dan aktif.", 422)
    terms = (await session.scalars(repo.query(TaxonomyTerm).where(TaxonomyTerm.taxonomy_id == str(taxonomy_id), TaxonomyTerm.is_active.is_(True)))).all()
    result = []
    for raw in data.values:
        value = raw.strip().casefold()
        scored = []
        for term in terms:
            labels = [term.code, term.label, *(term.aliases or [])]
            score = max(SequenceMatcher(None, value, str(label).casefold()).ratio() for label in labels)
            scored.append((score, term))
        scored.sort(key=lambda x: x[0], reverse=True)
        result.append({"value": raw, "candidates": [{"term": record(term), "confidence": round(score, 4)} for score, term in scored[:data.limit]], "requires_confirmation": True})
    return success({"taxonomy_id": str(taxonomy_id), "taxonomy_version": taxonomy.version, "recommendations": result})
