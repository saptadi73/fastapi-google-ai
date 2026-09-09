import hashlib
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, Query

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.config import get_settings
from app.core.exceptions import AppError, success
from app.core.routing import APIRouter
from app.domain.enums import EDIT_ROLES, REVIEW_ROLES
from app.models.import_review import ImportQuestion, ImportReview, ImportReviewRow
from app.models.source import SourceSheet
from app.models.taxonomy import Taxonomy, TaxonomyColumnBinding, TaxonomyTerm, TaxonomyVersion
from app.repositories.base import TenantRepository, record
from app.schemas.master import MasterRevisionRequest
from app.schemas.taxonomy import (
    TaxonomyAmbiguityQuestionRequest,
    TaxonomyColumnBindingCreate,
    TaxonomyCreate,
    TaxonomyRecommendRequest,
    TaxonomyTermCreate,
    TaxonomyTermResolveRequest,
    TaxonomyValuesValidateRequest,
    TaxonomyVersionCreate,
    TaxonomyVersionUpdate,
)
from app.services.audit_service import audit
from app.services.profiling_service import digest
from app.services.taxonomy_validation_service import exact_terms, normalized
from app.services.taxonomy_version_service import TaxonomyVersionService, archive_current

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
    taxonomy = await repo.get(Taxonomy, taxonomy_id, lock=True)
    if taxonomy.status != "DRAFT" or not taxonomy.is_active:
        raise AppError("TAXONOMY_IMMUTABLE", "Term dan alias hanya boleh ditambah pada taxonomy draft aktif.", 409)
    if data.parent_id:
        parent = await repo.get(TaxonomyTerm, data.parent_id)
        if parent.taxonomy_id != str(taxonomy_id):
            raise AppError("TAXONOMY_PARENT_INVALID", "Parent term harus berasal dari taxonomy yang sama.", 422)
    fp = hashlib.sha256(f"{taxonomy_id}:{data.code}".encode()).hexdigest()
    snap = hashlib.sha256(f"{taxonomy_id}:{data.code}:{data.label}".encode()).hexdigest()
    return success(record(await repo.add(TaxonomyTerm, taxonomy_id=str(taxonomy_id), fingerprint=fp, snapshot_hash=snap, created_by=user.id, **data.model_dump(mode="json"))))


@router.post("/{taxonomy_id}/approve", dependencies=review)
async def approve_taxonomy(taxonomy_id: UUID, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    taxonomy = await repo.get(Taxonomy, taxonomy_id, lock=True)
    if not taxonomy.is_active:
        raise AppError("TAXONOMY_NOT_APPROVED", "Taxonomy nonaktif tidak dapat disetujui.", 409)
    if taxonomy.status == "APPROVED":
        return success(record(taxonomy))
    if taxonomy.status != "DRAFT":
        raise AppError("TAXONOMY_STATE_CONFLICT", "Taxonomy harus draft sebelum approval.", 409)
    if get_settings().require_separate_approver and taxonomy.created_by == user.id:
        raise AppError("SEPARATE_APPROVER_REQUIRED", "Reviewer taxonomy harus berbeda dari pembuat.", 403)
    taxonomy.status, taxonomy.version = "APPROVED", taxonomy.version + 1
    taxonomy.approved_by, taxonomy.approved_at = user.id, datetime.now(timezone.utc)
    await archive_current(session, taxonomy)
    audit(session, user, "taxonomy.approved", taxonomy.id, version=taxonomy.version)
    return success(record(taxonomy))


@router.post("/{taxonomy_id}/versions", dependencies=edit, status_code=201)
async def create_version(taxonomy_id: UUID, data: TaxonomyVersionCreate, session: Session, user: CurrentUser):
    return success(record(await TaxonomyVersionService(session, user).create(taxonomy_id, data)))


@router.get("/{taxonomy_id}/versions")
async def list_versions(taxonomy_id: UUID, session: Session, user: CurrentUser,
                        offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    repo = TenantRepository(session, user.tenant_id)
    await repo.get(Taxonomy, taxonomy_id)
    versions = (await session.scalars(repo.query(TaxonomyVersion).where(TaxonomyVersion.taxonomy_id == str(taxonomy_id))
                                      .order_by(TaxonomyVersion.version.desc()).offset(offset).limit(limit + 1))).all()
    return success({"items": [record(v) for v in versions[:limit]], "has_more": len(versions) > limit})


@router.get("/versions/{version_id}")
async def get_version(version_id: UUID, session: Session, user: CurrentUser):
    return success(record(await TenantRepository(session, user.tenant_id).get(TaxonomyVersion, version_id)))


@router.put("/versions/{version_id}", dependencies=edit)
async def update_version(version_id: UUID, data: TaxonomyVersionUpdate, session: Session, user: CurrentUser):
    return success(record(await TaxonomyVersionService(session, user).update(version_id, data)))


@router.post("/versions/{version_id}/approve", dependencies=review)
async def publish_version(version_id: UUID, data: MasterRevisionRequest, session: Session, user: CurrentUser):
    return success(record(await TaxonomyVersionService(session, user).approve(version_id, data)))


@router.get("/source-sheets/{sheet_id}/column-bindings")
async def list_column_bindings(sheet_id: UUID, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    await repo.get(SourceSheet, sheet_id)
    rows = (await session.scalars(repo.query(TaxonomyColumnBinding).where(TaxonomyColumnBinding.source_sheet_id == str(sheet_id)))).all()
    return success([record(row) for row in rows])


@router.put("/source-sheets/{sheet_id}/column-bindings", dependencies=edit)
async def save_column_binding(sheet_id: UUID, data: TaxonomyColumnBindingCreate, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    await repo.get(SourceSheet, sheet_id, lock=True)
    taxonomy = await repo.get(Taxonomy, data.taxonomy_id, lock=True)
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
        for key, value in values.items():
            setattr(existing, key, value)
        existing.revision_no += 1
        existing.status = "DRAFT"
        existing.approved_by = None
        existing.approved_at = None
        existing.snapshot_hash = digest(values)
        return success(record(existing))
    if data.revision_no != 0:
        raise AppError("REVISION_CONFLICT", "Binding baru memerlukan revision_no=0.", 409)
    fp = hashlib.sha256(f"{sheet_id}:{data.source_column}".encode()).hexdigest()
    snap = hashlib.sha256(f"{data.taxonomy_id}:{data.taxonomy_version}:{data.source_column}".encode()).hexdigest()
    return success(record(await repo.add(TaxonomyColumnBinding, source_sheet_id=str(sheet_id), created_by=user.id, fingerprint=fp, snapshot_hash=snap, **values)))


@router.post("/column-bindings/{binding_id}/approve", dependencies=review)
async def approve_column_binding(binding_id: UUID, data: MasterRevisionRequest, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    binding = await repo.get(TaxonomyColumnBinding, binding_id)
    taxonomy = await repo.get(Taxonomy, binding.taxonomy_id, lock=True)
    binding = await repo.get(TaxonomyColumnBinding, binding_id, lock=True)
    await session.refresh(binding)
    if data.revision_no != binding.revision_no:
        raise AppError("REVISION_CONFLICT", "Binding telah berubah; ambil data terbaru.", 409)
    if (binding.status != "DRAFT" or taxonomy.id != binding.taxonomy_id or not taxonomy.is_active
            or taxonomy.status != "APPROVED" or taxonomy.version != binding.taxonomy_version):
        raise AppError("TAXONOMY_BINDING_STALE", "Binding harus draft dan merujuk versi taxonomy approved terkini.", 409)
    if get_settings().require_separate_approver and binding.created_by == user.id:
        raise AppError("SEPARATE_APPROVER_REQUIRED", "Reviewer binding harus berbeda dari pembuat.", 403)
    binding.status, binding.approved_by, binding.approved_at = "APPROVED", user.id, datetime.now(timezone.utc)
    binding.revision_no += 1
    audit(session, user, "taxonomy.binding_approved", binding.id, revision_no=binding.revision_no)
    return success(record(binding))


@router.post("/column-bindings/{binding_id}/reject", dependencies=review)
async def reject_column_binding(binding_id: UUID, data: MasterRevisionRequest, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    binding = await repo.get(TaxonomyColumnBinding, binding_id, lock=True)
    if data.revision_no != binding.revision_no:
        raise AppError("REVISION_CONFLICT", "Binding telah berubah; ambil data terbaru.", 409)
    binding.status, binding.approved_by, binding.approved_at = "REJECTED", None, None
    binding.revision_no += 1
    return success(record(binding))


@router.post("/{taxonomy_id}/resolve-term")
async def resolve_term(taxonomy_id: UUID, data: TaxonomyTermResolveRequest, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    taxonomy = await repo.get(Taxonomy, taxonomy_id)
    if taxonomy.status != "APPROVED" or not taxonomy.is_active:
        raise AppError("TAXONOMY_NOT_APPROVED", "Taxonomy harus approved dan aktif.", 422)
    value = data.value.strip().casefold()
    terms = (await session.scalars(repo.query(TaxonomyTerm).where(TaxonomyTerm.taxonomy_id == str(taxonomy_id), TaxonomyTerm.is_active.is_(True)))).all()
    exact = exact_terms(terms, value)
    if len(exact) == 1:
        return success({"status": "EXACT", "taxonomy_id": str(taxonomy_id), "taxonomy_version": taxonomy.version, "term": record(exact[0]), "requires_question": False})
    if len(exact) > 1:
        return success({"status": "AMBIGUOUS", "taxonomy_id": str(taxonomy_id), "taxonomy_version": taxonomy.version,
                        "candidates": [record(t) for t in exact], "requires_question": True})
    from difflib import SequenceMatcher
    candidates = [t for t in terms if value in t.label.casefold() or value in t.code.casefold() or any(value in str(a).casefold() for a in (t.aliases or []))]
    candidates.sort(key=lambda t: max(SequenceMatcher(None, value, t.label.casefold()).ratio(), SequenceMatcher(None, value, t.code.casefold()).ratio()), reverse=True)
    status = "AMBIGUOUS" if len(candidates) > 1 else "NOT_FOUND" if not candidates else "CANDIDATE"
    return success({"status": status, "taxonomy_id": str(taxonomy_id), "taxonomy_version": taxonomy.version, "candidates": [record(t) for t in candidates[:10]], "requires_question": status != "EXACT"})


@router.post("/{taxonomy_id}/ambiguity-question", dependencies=edit, status_code=201)
async def create_ambiguity_question(taxonomy_id: UUID, data: TaxonomyAmbiguityQuestionRequest, session: Session, user: CurrentUser):
    repo = TenantRepository(session, user.tenant_id)
    review = await repo.get(ImportReview, data.import_review_id, lock=True)
    if review.status not in ("NEEDS_INPUT", "FAILED"):
        raise AppError("IMPORT_STATE_CONFLICT", "Pertanyaan taxonomy hanya untuk batch yang menunggu input/gagal.", 409)
    from app.services.import_review_service import ImportReviewService

    if not await ImportReviewService(session, user).is_current(review):
        raise AppError("IMPORT_STALE_REVIEW", "Dependency batch berubah; revalidate sebelum membuat pertanyaan.", 409)
    taxonomy = await repo.get(Taxonomy, taxonomy_id, lock=True)
    if not data.staging_row_id or not data.target_column:
        raise AppError("TAXONOMY_QUESTION_TARGET_REQUIRED", "Pilih staging row dan target_column pertanyaan.", 422)
    row = await repo.get(ImportReviewRow, data.staging_row_id, lock=True)
    if row.import_review_id != review.id:
        raise AppError("IMPORT_STAGING_MISSING", "Staging row bukan milik batch ini.", 409)
    column = next((c for c in review.configuration_json["columns"]
                   if c["target_column"] == data.target_column), None)
    if (not column or str(column.get("taxonomy_id")) != str(taxonomy_id)
            or column.get("taxonomy_version") != taxonomy.version
            or (data.source_column and data.source_column != column["source_column"])):
        raise AppError("TAXONOMY_QUESTION_TARGET_INVALID", "Kolom pertanyaan tidak sesuai mapping taxonomy batch.", 422)
    current = {**row.transformed_data, **row.corrected_data}.get(data.target_column)
    if normalized(current) != normalized(data.value):
        raise AppError("TAXONOMY_QUESTION_VALUE_STALE", "Nilai pertanyaan berbeda dari staging terbaru.", 409)
    resolution = await resolve_term(taxonomy_id, TaxonomyTermResolveRequest(value=data.value), session, user)
    payload = resolution.get("data", resolution)
    if not payload.get("requires_question"):
        return success({"created": False, "resolution": payload})
    key = digest({"taxonomy_id": str(taxonomy_id), "version": taxonomy.version, "row_id": row.id,
                  "target": data.target_column, "value": normalized(data.value)})
    existing = (await session.scalars(repo.query(ImportQuestion).where(ImportQuestion.import_review_id == str(review.id), ImportQuestion.question_key == key))).first()
    if existing:
        return success(record(existing))
    candidates = ImportReviewService.json_value(payload.get("candidates", []))
    q = await repo.add(ImportQuestion, import_review_id=review.id, staging_row_id=row.id,
                       source_column=column["source_column"], target_column=data.target_column,
                       source_row=row.source_row, question_key=key, category="TAXONOMY_AMBIGUOUS",
                       prompt="Pilih term taxonomy untuk nilai pada baris ini.", mandatory=True,
                       allowed_actions=(["SELECT_RECORD"] if candidates else []) + ["CORRECT_SOURCE"],
                       candidates=candidates, evidence={"taxonomy_id": str(taxonomy_id),
                                                        "taxonomy_version": taxonomy.version},
                       status="OPEN", revision_no=1)
    questions = (await session.scalars(repo.query(ImportQuestion).where(
        ImportQuestion.import_review_id == review.id, ImportQuestion.status == "OPEN"))).all()
    review.checkpoint = {**review.checkpoint, "open_question_count": len(questions),
                         "blocking_codes": sorted(set(review.checkpoint.get("blocking_codes", []))
                                                  | {"DATA_QUALITY_ISSUES"})}
    review.revision_no += 1
    audit(session, user, "taxonomy.question_created", q.id, import_review_id=review.id)
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
    invalid, ambiguous = [], []
    for raw in data.values:
        matches = exact_terms(terms, raw)
        if not matches:
            invalid.append(raw)
        elif len(matches) > 1:
            ambiguous.append(raw)
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
