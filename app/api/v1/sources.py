from uuid import UUID

from fastapi import Depends, Query
from sqlalchemy import func, or_, select

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import AppError, success
from app.core.routing import APIRouter
from app.domain.enums import EDIT_ROLES
from app.models.audit import AuditEvent
from app.models.auth import User
from app.models.configuration import Configuration
from app.models.etl import ETLRun, Job
from app.models.import_review import ImportReview
from app.models.master import MasterColumnBinding, MasterSourceBinding
from app.models.semantic import DataProduct
from app.models.source import DataSource, ProfilingRun, SourceSheet
from app.models.taxonomy import TaxonomyColumnBinding
from app.repositories.base import record
from app.repositories.source_repository import SourceRepository
from app.schemas.configuration import AIConfigurationRequest
from app.schemas.source import (
    SheetClassificationUpdate,
    SheetUpdate,
    SheetWatermarkUpdate,
    SourceAccessActivation,
    SourceAccessMetadataUpdate,
    SourceApproversUpdate,
    SourceCreate,
    SourceDelete,
    SourceMetadataReview,
    SourceScheduleUpdate,
    SourceUnlink,
)
from app.services.classification_service import ClassificationService
from app.services.job_service import enqueue
from app.services.release_approval_service import release_status
from app.services.source_approver_service import SourceApproverService
from app.services.source_service import SourceService, source_records

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
    session: Session,
    user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: str = Query("", max_length=200),
    include_unlinked: bool = Query(False),
):
    repo = SourceRepository(session, user.tenant_id)
    query = repo.query(DataSource)
    conditions = []
    if not include_unlinked:
        conditions.append(DataSource.unlinked_at.is_(None))
    if search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append(or_(
            DataSource.name.ilike(pattern),
            DataSource.source_code.ilike(pattern),
            DataSource.spreadsheet_id.ilike(pattern),
        ))
    query = query.where(*conditions)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list((await session.scalars(
        query.order_by(DataSource.created_at.desc(), DataSource.id)
        .offset(offset).limit(limit)
    )).all())
    return success(
        await source_records(session, items),
        offset=offset,
        limit=limit,
        total=total,
        search=search,
        include_unlinked=include_unlinked,
    )


@router.get("/sources/tracking")
async def source_tracking(
    session: Session,
    user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    search: str = Query("", max_length=200),
    include_unlinked: bool = Query(False),
):
    repo = SourceRepository(session, user.tenant_id)
    source_query = repo.query(DataSource)
    conditions = []
    if not include_unlinked:
        conditions.append(DataSource.unlinked_at.is_(None))
    if search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append(or_(
            DataSource.name.ilike(pattern),
            DataSource.source_code.ilike(pattern),
            DataSource.spreadsheet_id.ilike(pattern),
        ))
    source_query = source_query.where(*conditions)
    total = await session.scalar(select(func.count()).select_from(source_query.subquery())) or 0
    sources = list((await session.scalars(
        source_query.order_by(DataSource.created_at.desc(), DataSource.id)
        .offset(offset).limit(limit)
    )).all())
    source_ids = [item.id for item in sources]
    if not source_ids:
        return success([], offset=offset, limit=limit, total=total, search=search)

    sheets = list((await session.scalars(
        select(SourceSheet).where(
            SourceSheet.tenant_id == user.tenant_id,
            SourceSheet.source_id.in_(source_ids),
        ).order_by(SourceSheet.sheet_name)
    )).all())
    sheet_ids = [item.id for item in sheets]
    profiles = list((await session.scalars(
        select(ProfilingRun).where(
            ProfilingRun.tenant_id == user.tenant_id,
            ProfilingRun.source_sheet_id.in_(sheet_ids),
        ).order_by(ProfilingRun.created_at.desc())
    )).all()) if sheet_ids else []
    configs = list((await session.scalars(
        select(Configuration).where(
            Configuration.tenant_id == user.tenant_id,
            Configuration.source_sheet_id.in_(sheet_ids),
        ).order_by(Configuration.created_at.desc())
    )).all()) if sheet_ids else []
    runs = list((await session.scalars(
        select(ETLRun).where(
            ETLRun.tenant_id == user.tenant_id,
            ETLRun.source_sheet_id.in_(sheet_ids),
        ).order_by(ETLRun.created_at.desc())
    )).all()) if sheet_ids else []
    products = list((await session.scalars(
        select(DataProduct).where(
            DataProduct.tenant_id == user.tenant_id,
            DataProduct.source_sheet_id.in_(sheet_ids),
        )
    )).all()) if sheet_ids else []
    imports = list((await session.scalars(
        select(ImportReview).where(
            ImportReview.tenant_id == user.tenant_id,
            ImportReview.source_sheet_id.in_(sheet_ids),
        ).order_by(ImportReview.created_at.desc())
    )).all()) if sheet_ids else []
    bindings = list((await session.scalars(
        select(MasterSourceBinding).where(
            MasterSourceBinding.tenant_id == user.tenant_id,
            MasterSourceBinding.source_sheet_id.in_(sheet_ids),
        ).order_by(MasterSourceBinding.created_at.desc())
    )).all()) if sheet_ids else []
    jobs = list((await session.scalars(
        select(Job).where(
            Job.tenant_id == user.tenant_id,
            Job.source_id.in_(source_ids),
        ).order_by(Job.created_at.desc())
    )).all())

    profile_by_sheet = {}
    for item in profiles:
        profile_by_sheet.setdefault(str(item.source_sheet_id), item)
    config_by_sheet = {}
    for item in configs:
        config_by_sheet.setdefault(str(item.source_sheet_id), item)
    config_by_id = {str(item.id): item for item in configs}
    run_by_sheet = {}
    for item in runs:
        run_by_sheet.setdefault(str(item.source_sheet_id), item)
    product_by_sheet = {str(item.source_sheet_id): item for item in products}
    import_by_sheet = {}
    for item in imports:
        import_by_sheet.setdefault(str(item.source_sheet_id), item)
    binding_by_sheet = {str(item.source_sheet_id): item for item in bindings}
    sheets_by_source = {}
    for item in sheets:
        sheets_by_source.setdefault(str(item.source_id), []).append(item)
    discover_by_source = {}
    source_failures = {}
    sheet_failures = {}
    for item in jobs:
        source_key = str(item.source_id)
        if item.kind == "DISCOVER":
            discover_by_source.setdefault(source_key, item)
        stage = {
            "DISCOVER": "discovery",
            "PROFILE": "profiling",
            "AI_CONFIG": "configuration",
            "DEPLOY": "configuration",
            "ROLLBACK": "configuration",
            "ETL": "database",
            "SYNC_REVIEW": "database",
            "IMPORT_REVIEW": "database",
        }.get(item.kind)
        if not stage:
            continue
        sheet_key = str(item.payload.get("source_sheet_id")) if item.payload.get("source_sheet_id") else None
        if item.status == "FAILED":
            failure = {
                "stage": stage,
                "status": "FAILED",
                "code": item.error_code,
                "message": item.error_message,
                "occurred_at": item.finished_at or item.created_at,
                "job_kind": item.kind,
            }
            source_failures.setdefault(source_key, {}).setdefault(stage, failure)
            if sheet_key:
                sheet_failures.setdefault(sheet_key, {}).setdefault(stage, failure)
        profile_error = (item.result or {}).get("profile_error") if item.kind == "DISCOVER" else None
        if profile_error:
            failure = {
                "stage": "profiling",
                "status": "FAILED",
                "code": profile_error.get("code"),
                "message": profile_error.get("message"),
                "occurred_at": item.finished_at or item.created_at,
                "job_kind": item.kind,
            }
            source_failures.setdefault(source_key, {}).setdefault("profiling", failure)

    user_ids = set()
    for source in sources:
        if source.owner_user_id:
            user_ids.add(str(source.owner_user_id))
        metadata = source.access_metadata or {}
        for key in ("data_owner_user_id", "data_steward_user_id"):
            if metadata.get(key):
                user_ids.add(str(metadata[key]))
    users = list((await session.scalars(
        select(User).where(User.tenant_id == user.tenant_id, User.id.in_(user_ids))
    )).all()) if user_ids else []
    people = {str(item.id): item for item in users}

    def rollup(values):
        if not values:
            return "NOT_STARTED"
        normalized = [str(value or "NOT_STARTED").upper() for value in values]
        success_states = {"SUCCEEDED", "SUCCEEDED_WITH_WARNINGS", "ACTIVE", "DEPLOYED", "CONFIRMED", "APPROVED", "BINDING_READY"}
        if all(value == "NOT_STARTED" for value in normalized):
            return "NOT_STARTED"
        if all(value in success_states for value in normalized):
            return "SUCCEEDED_WITH_WARNINGS" if "SUCCEEDED_WITH_WARNINGS" in normalized else "SUCCEEDED"
        if any("FAIL" in value or value in {"REJECTED", "BLOCKED"} for value in normalized):
            return "FAILED"
        return "IN_PROGRESS"

    def it_approval_status(config, source):
        if config is None:
            return "NOT_STARTED"
        status = str(config.status or "").upper()
        if status == "NEEDS_REVIEW":
            review_state = config.review_state or {}
            return (
                "PENDING_IT_APPROVAL"
                if review_state.get("submitted_revision") == config.revision_no
                else "NOT_SUBMITTED"
            )
        if status in {"APPROVED", "SUPERSEDED", "ACTIVE"}:
            release = release_status(config, source)
            technical = next((group for group in release["groups"] if group["key"] == "TECHNICAL"), None)
            if technical and technical["status"] == "PENDING":
                return "PENDING_IT_APPROVAL"
            if technical and technical["status"] == "REJECTED":
                return "REJECTED"
            return "APPROVED"
        if status == "REJECTED":
            return "REJECTED"
        return "NOT_SUBMITTED"

    def it_approval_rollup(values):
        applicable = [value for value in values if value != "NOT_APPLICABLE"]
        if not applicable:
            return "NOT_APPLICABLE"
        if "PENDING_IT_APPROVAL" in applicable:
            return "PENDING_IT_APPROVAL"
        if "REJECTED" in applicable:
            return "REJECTED"
        if "NOT_SUBMITTED" in applicable:
            return "NOT_SUBMITTED"
        if all(value == "APPROVED" for value in applicable):
            return "APPROVED"
        if all(value == "NOT_STARTED" for value in applicable):
            return "NOT_STARTED"
        return "IN_PROGRESS"

    result = []
    for source in sources:
        source_sheets = sheets_by_source.get(str(source.id), [])
        sheet_records = []
        for sheet in source_sheets:
            profile = profile_by_sheet.get(str(sheet.id))
            config = config_by_id.get(str(sheet.active_configuration_id)) if sheet.active_configuration_id else None
            config = config or config_by_sheet.get(str(sheet.id))
            etl_run = run_by_sheet.get(str(sheet.id))
            product = product_by_sheet.get(str(sheet.id))
            import_review = import_by_sheet.get(str(sheet.id))
            master_binding = binding_by_sheet.get(str(sheet.id))
            sheet_it_approval_status = (
                "NOT_APPLICABLE"
                if sheet.dataset_kind == "MASTER"
                else it_approval_status(config, source)
            )
            database_status = etl_run.status if etl_run else (
                import_review.status if import_review else "NOT_STARTED"
            )
            if import_review and import_review.status not in ("SUCCEEDED", "FAILED"):
                database_status = "IN_PROGRESS"
            sheet_records.append({
                "id": sheet.id,
                "name": sheet.sheet_name,
                "enabled": sheet.enabled,
                "is_present": sheet.is_present,
                "presence_status": "PRESENT" if sheet.is_present else "MISSING",
                "dataset_kind": sheet.dataset_kind,
                "profiling_status": profile.status if profile else ("FAILED" if source.status == "PROFILE_FAILED" else "NOT_STARTED"),
                "profiled_at": profile.created_at if profile else None,
                "configuration_status": config.status if config else ("AI_FAILED" if source.status == "AI_FAILED" else "NOT_STARTED"),
                "it_approval_status": sheet_it_approval_status,
                "configuration_id": config.id if config else None,
                "configured_at": config.created_at if config else None,
                "database_status": database_status,
                "rows_loaded": etl_run.rows_loaded if etl_run else int((import_review.checkpoint or {}).get("rows_applied", 0)) if import_review and import_review.status == "SUCCEEDED" else 0,
                "loaded_at": etl_run.finished_at if etl_run else None,
                "master_binding_status": master_binding.status if master_binding else "NOT_STARTED",
                "data_product_code": product.code if product else None,
                "last_failures": sheet_failures.get(str(sheet.id), {}),
            })
        metadata = source.access_metadata or {}
        steward = people.get(str(metadata.get("data_steward_user_id"))) if metadata.get("data_steward_user_id") else None
        owner = people.get(str(metadata.get("data_owner_user_id"))) if metadata.get("data_owner_user_id") else None
        registration_owner = people.get(str(source.owner_user_id))
        discovery_job = discover_by_source.get(str(source.id))
        result.append({
            **record(source),
            "discovery_status": "SUCCEEDED" if any(item["is_present"] for item in sheet_records) else (discovery_job.status if discovery_job else "NOT_STARTED"),
            "profiling_status": rollup([item["profiling_status"] for item in sheet_records if item["enabled"] and item["is_present"]]),
            "configuration_status": rollup([
                item["master_binding_status"] if item["dataset_kind"] == "MASTER" else item["configuration_status"]
                for item in sheet_records if item["enabled"] and item["is_present"]
            ]),
            "database_status": rollup([item["database_status"] for item in sheet_records if item["enabled"] and item["is_present"]]),
            "it_approval_status": it_approval_rollup([
                item["it_approval_status"] for item in sheet_records
                if item["enabled"] and item["is_present"]
            ]),
            "it_approval_pending_tabs": [
                item["name"] for item in sheet_records
                if item["enabled"] and item["is_present"]
                and item["it_approval_status"] == "PENDING_IT_APPROVAL"
            ],
            "access_review_status": source.access_review_status,
            "last_failures": source_failures.get(str(source.id), {}),
            "steward_name": (steward.full_name or steward.username) if steward else None,
            "steward_username": steward.username if steward else None,
            "owner_name": (owner.full_name or owner.username) if owner else None,
            "registered_by": (registration_owner.full_name or registration_owner.username) if registration_owner else None,
            "sheets": sheet_records,
        })
    return success(result, offset=offset, limit=limit, total=total, search=search, include_unlinked=include_unlinked)


@router.get("/sources/{source_id}/history")
async def source_history(
    source_id: UUID,
    session: Session,
    user: CurrentUser,
    offset: int = Query(0, ge=0, le=10000),
    limit: int = Query(50, ge=1, le=100),
):
    source = await SourceRepository(session, user.tenant_id).get(DataSource, source_id)
    sheet_ids = list(await session.scalars(select(SourceSheet.id).where(
        SourceSheet.tenant_id == user.tenant_id, SourceSheet.source_id == source.id
    )))
    config_ids = list(await session.scalars(select(Configuration.id).where(
        Configuration.tenant_id == user.tenant_id, Configuration.source_id == source.id
    )))
    review_ids = list(await session.scalars(select(ImportReview.id).where(
        ImportReview.tenant_id == user.tenant_id, ImportReview.source_id == source.id
    )))
    related_binding_ids = list(await session.scalars(select(MasterSourceBinding.id).where(
        MasterSourceBinding.tenant_id == user.tenant_id,
        MasterSourceBinding.source_sheet_id.in_(sheet_ids),
    ))) if sheet_ids else []
    related_binding_ids.extend(list(await session.scalars(select(MasterColumnBinding.id).where(
        MasterColumnBinding.tenant_id == user.tenant_id,
        MasterColumnBinding.source_sheet_id.in_(sheet_ids),
    )))) if sheet_ids else None
    related_binding_ids.extend(list(await session.scalars(select(TaxonomyColumnBinding.id).where(
        TaxonomyColumnBinding.tenant_id == user.tenant_id,
        TaxonomyColumnBinding.source_sheet_id.in_(sheet_ids),
    )))) if sheet_ids else None
    jobs = list((await session.scalars(select(Job).where(
        Job.tenant_id == user.tenant_id, Job.source_id == source.id
    ).order_by(Job.created_at.desc()))).all())
    resource_ids = {str(source.id), *(str(value) for value in sheet_ids),
                    *(str(value) for value in config_ids), *(str(value) for value in review_ids),
                    *(str(value) for value in related_binding_ids),
                    *(str(item.id) for item in jobs)}
    audit_rows = list((await session.scalars(select(AuditEvent).where(
        AuditEvent.tenant_id == user.tenant_id,
        AuditEvent.resource_id.in_(resource_ids),
    ).order_by(AuditEvent.created_at.desc()).limit(offset + limit + 1))).all()) if resource_ids else []

    def stage_for_job(kind):
        return {
            "DISCOVER": "DISCOVERY", "PROFILE": "PROFILING", "AI_CONFIG": "CONFIGURATION",
            "DEPLOY": "CONFIGURATION", "ROLLBACK": "CONFIGURATION", "ETL": "DATABASE",
            "SYNC_REVIEW": "DATABASE", "IMPORT_REVIEW": "DATABASE",
        }.get(kind, "OPERATIONS")

    actor_ids = {str(item.user_id) for item in audit_rows if item.user_id}
    actor_ids.update(str(item.requested_by) for item in jobs if item.requested_by)
    actors = list((await session.scalars(select(User).where(
        User.tenant_id == user.tenant_id, User.id.in_(actor_ids)
    ))).all()) if actor_ids else []
    actor_names = {str(item.id): item.full_name or item.username for item in actors}
    event_names = {
        "source.registered": "Sumber didaftarkan", "source.discovered": "Tab ditemukan",
        "source.profiled": "Profiling selesai", "source.unlinked": "Sumber di-unlink",
        "source.unlink_restored": "Link sumber dipulihkan",
        "source.access_metadata_updated": "Metadata akses diperbarui",
        "source.access_metadata_reviewed": "Metadata akses direview",
        "source.stage_started": "Tahap pemrosesan dimulai",
        "source.stage_succeeded": "Tahap pemrosesan berhasil",
        "source.stage_failed": "Tahap pemrosesan gagal",
        "sheet.classified": "Tab diklasifikasikan", "sheet.updated": "Pengaturan tab diperbarui",
        "configuration.created": "Draft konfigurasi dibuat",
        "configuration.submitted": "Konfigurasi diajukan untuk review",
        "configuration.approved": "Konfigurasi disetujui",
    }
    timeline = []
    safe_detail_keys = {"kind", "decision", "drift", "sheet_count", "revision_no", "changed_fields", "stage",
                        "reason_code", "reason", "job_kind", "status", "error_code"}
    for item in audit_rows:
        if item.event == "job.queued":
            continue
        details = item.details or {}
        stage = "OPERATIONS"
        if item.event.startswith("source."):
            stage = "SOURCE"
        elif item.event.startswith("source_sheet.") or item.event.startswith("sheet."):
            stage = "CLASSIFICATION"
        elif item.event.startswith("configuration."):
            stage = "CONFIGURATION"
        elif item.event.startswith("master."):
            stage = "MASTER"
        elif item.event.startswith("taxonomy."):
            stage = "TAXONOMY"
        summary = event_names.get(item.event, item.event.replace(".", " ").replace("_", " ").capitalize())
        if item.event == "source.stage_failed":
            stage = details.get("stage") or stage_for_job(details.get("job_kind"))
            summary = f"Tahap {stage.lower()} gagal"
        elif item.event == "source.stage_succeeded":
            stage = details.get("stage") or stage_for_job(details.get("job_kind"))
            summary = f"Tahap {stage.lower()} berhasil"
        elif item.event == "source.stage_started":
            stage = details.get("stage") or stage_for_job(details.get("job_kind"))
            summary = f"Tahap {stage.lower()} dimulai"
        elif item.event == "source_sheet.classified":
            summary = "Tab diklasifikasikan"
        timeline.append({
            "id": f"audit:{item.id}", "occurred_at": item.created_at, "stage": stage,
            "status": details.get("status") or ("FAILED" if item.event.endswith("failed") else "RECORDED"),
            "event": item.event, "summary": summary, "actor_name": actor_names.get(str(item.user_id)),
            "error_code": details.get("error_code"), "error_message": details.get("error_message"),
            "details": {key: value for key, value in details.items() if key in safe_detail_keys},
        })
    # Older job attempts predate lifecycle audit events. Include each attempt as a fallback.
    audited_job_ids = {
        str((item.details or {}).get("job_id")) for item in audit_rows
        if item.event.startswith("source.stage_") and (item.details or {}).get("job_id")
    }
    audited_profile_failure_ids = {
        str((item.details or {}).get("job_id")) for item in audit_rows
        if item.event == "source.stage_failed"
        and (item.details or {}).get("stage") == "PROFILING"
        and (item.details or {}).get("job_id")
    }
    for job in jobs:
        if str(job.id) not in audited_job_ids:
            status = job.status
            timeline.append({
                "id": f"job:{job.id}", "occurred_at": job.finished_at or job.started_at or job.created_at,
                "stage": stage_for_job(job.kind), "status": status,
                "event": f"job.{status.lower()}",
                "summary": f"{stage_for_job(job.kind).capitalize()} {'gagal' if status == 'FAILED' else 'berhasil' if status == 'SUCCEEDED' else status.lower()}",
                "actor_name": actor_names.get(str(job.requested_by)),
                "error_code": job.error_code, "error_message": job.error_message,
                "details": {"job_kind": job.kind},
            })
        profile_error = (job.result or {}).get("profile_error") if job.kind == "DISCOVER" else None
        if profile_error and str(job.id) not in audited_profile_failure_ids:
            timeline.append({
                "id": f"job:{job.id}:profile-failure",
                "occurred_at": job.finished_at or job.created_at,
                "stage": "PROFILING", "status": "FAILED", "event": "source.stage_failed",
                "summary": "Tahap profiling gagal", "actor_name": actor_names.get(str(job.requested_by)),
                "error_code": profile_error.get("code"), "error_message": profile_error.get("message"),
                "details": {"job_kind": job.kind, "stage": "PROFILING"},
            })
    timeline.sort(key=lambda item: item["occurred_at"], reverse=True)
    total = len(timeline)
    page = timeline[offset:offset + limit]
    return success(page, offset=offset, limit=limit, total=total)


@router.get("/sources/duplicate-groups")
async def duplicate_groups(session: Session, user: CurrentUser):
    return success(await SourceService(session, user).duplicate_groups())


@router.get("/sources/registration-check")
async def registration_check(spreadsheet_url: str, session: Session, user: CurrentUser):
    return success(await SourceService(session, user).check_registration(spreadsheet_url))


@router.get("/sources/approver-options", dependencies=[Depends(require_roles("PLATFORM_ADMIN"))])
async def source_approver_options(session: Session, user: CurrentUser):
    return success(await SourceApproverService(session, user).options())


@router.post("/sources/{source_id}/unlink", dependencies=[Depends(require_roles("PLATFORM_ADMIN"))])
async def unlink_source(source_id: UUID, data: SourceUnlink, session: Session, user: CurrentUser):
    return success(await SourceService(session, user).unlink_duplicate(source_id, data))


@router.post("/sources/{source_id}/restore", dependencies=[Depends(require_roles("PLATFORM_ADMIN"))])
async def restore_source(source_id: UUID, session: Session, user: CurrentUser):
    return success(await SourceService(session, user).restore_unlinked(source_id))


@router.get("/sources/{source_id}/delete-preview", dependencies=[Depends(require_roles("PLATFORM_ADMIN"))])
async def source_delete_preview(source_id: UUID, session: Session, user: CurrentUser):
    return success(await SourceService(session, user).delete_preview(source_id))


@router.delete("/sources/{source_id}", dependencies=[Depends(require_roles("PLATFORM_ADMIN"))])
async def delete_source(source_id: UUID, data: SourceDelete, session: Session, user: CurrentUser):
    return success(await SourceService(session, user).permanently_delete_source(source_id, data))


@router.get("/sources/{source_id}")
async def get_source(source_id: UUID, session: Session, user: CurrentUser):
    source = await SourceRepository(session, user.tenant_id).get(DataSource, source_id)
    return success((await source_records(session, [source]))[0])


@router.patch("/sources/{source_id}/access-metadata", dependencies=edit)
async def update_access_metadata(
    source_id: UUID, data: SourceAccessMetadataUpdate, session: Session, user: CurrentUser
):
    return success(await SourceService(session, user).update_access_metadata(source_id, data))


@router.post("/sources/{source_id}/access-review", dependencies=[Depends(require_roles("PLATFORM_ADMIN", "TECHNICAL_APPROVER"))])
async def review_access_metadata(
    source_id: UUID, data: SourceMetadataReview, session: Session, user: CurrentUser
):
    return success(await SourceService(session, user).review_access_metadata(source_id, data))


@router.get("/sources/{source_id}/access-review-context", dependencies=[Depends(require_roles("PLATFORM_ADMIN", "TECHNICAL_APPROVER"))])
async def access_review_context(source_id: UUID, session: Session, user: CurrentUser):
    return success(await SourceService(session, user).metadata_review_context(source_id))


@router.post("/sources/{source_id}/access-activate", dependencies=[Depends(require_roles("PLATFORM_ADMIN"))])
async def activate_source_access(
    source_id: UUID, data: SourceAccessActivation, session: Session, user: CurrentUser
):
    return success(await SourceService(session, user).activate_source_access(source_id, data))


@router.get("/sources/{source_id}/access-policy-options", dependencies=[Depends(require_roles("PLATFORM_ADMIN"))])
async def source_policy_options(source_id: UUID, session: Session, user: CurrentUser):
    return success(await SourceService(session, user).source_policy_options(source_id))


@router.get("/sources/{source_id}/approvers", dependencies=[Depends(require_roles("PLATFORM_ADMIN"))])
async def source_approvers(source_id: UUID, session: Session, user: CurrentUser):
    return success(await SourceApproverService(session, user).get(source_id))


@router.put("/sources/{source_id}/approvers", dependencies=[Depends(require_roles("PLATFORM_ADMIN"))])
async def replace_source_approvers(source_id: UUID, data: SourceApproversUpdate, session: Session, user: CurrentUser):
    return success(await SourceApproverService(session, user).replace(source_id, data))


@router.patch("/sources/{source_id}/schedule", dependencies=edit)
async def update_schedule(
    source_id: UUID, data: SourceScheduleUpdate, session: Session, user: CurrentUser
):
    return success(await SourceService(session, user).update_schedule(source_id, data))


@router.get("/sources/{source_id}/sheets")
async def sheets(source_id: UUID, session: Session, user: CurrentUser):
    return success([record(s) for s in await SourceRepository(session, user.tenant_id).sheets(source_id)])


@router.patch("/source-sheets/{sheet_id}", dependencies=edit)
async def update_sheet(sheet_id: UUID, data: SheetUpdate, session: Session, user: CurrentUser):
    return success(await SourceService(session, user).update_sheet(sheet_id, data))


@router.patch("/source-sheets/{sheet_id}/watermark", dependencies=edit)
async def update_watermark(
    sheet_id: UUID, data: SheetWatermarkUpdate, session: Session, user: CurrentUser
):
    return success(await SourceService(session, user).update_watermark(sheet_id, data))


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
    return success(await SourceService(session, user).sync_review(source_id))


@router.post("/sources/{source_id}/sync-review/start", status_code=202, dependencies=edit)
async def start_sync_review(source_id: UUID, session: Session, user: CurrentUser):
    return success(await SourceService(session, user).queue_sync_review(source_id))


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
