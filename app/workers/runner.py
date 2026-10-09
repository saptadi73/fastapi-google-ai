import asyncio
import logging
from datetime import timedelta

from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.core.database import SessionFactory
from app.core.exceptions import AppError
from app.domain.enums import EDIT_ROLES, REVIEW_ROLES
from app.models.audit import AuditEvent
from app.models.auth import User
from app.models.base import now
from app.models.etl import Job
from app.models.source import DataSource, SourceDependency
from app.schemas.source import cron_schedule
from app.services.ai_configuration_service import AIConfigurationService
from app.services.configuration_service import ConfigurationService
from app.services.etl_execution_service import ETLExecutionService
from app.services.import_review_service import ImportReviewService, fail_import_job
from app.services.notification_service import add_notification
from app.services.source_service import SourceService

logger = logging.getLogger(__name__)


def _job_failure_details(exc, job_kind):
    """Return a user-safe diagnosis while keeping raw driver details in server logs."""
    if isinstance(exc, AppError):
        return exc.code, exc.message

    sqlstate = None
    for candidate in (exc, getattr(exc, "orig", None), getattr(exc, "__cause__", None)):
        if candidate is not None:
            sqlstate = getattr(candidate, "sqlstate", None) or getattr(candidate, "pgcode", None)
            if sqlstate:
                break

    if sqlstate == "42501":
        if job_kind in ("DEPLOY", "ROLLBACK"):
            return (
                "DATABASE_PERMISSION_DENIED",
                "Database menolak hak akses (PostgreSQL 42501). Untuk deploy ETL, minta administrator "
                "memastikan role pada DATABASE_DDL_URL memiliki USAGE dan CREATE pada schema trusted "
                "dan semantic, serta hak pada objek target. Detail teknis tersedia di log worker.",
            )
        return (
            "DATABASE_PERMISSION_DENIED",
            "Database menolak hak akses (PostgreSQL 42501). Minta administrator memeriksa privilege "
            "role database pada schema atau objek yang digunakan. Detail teknis tersedia di log worker.",
        )
    if sqlstate and str(sqlstate).startswith("08"):
        return (
            "DATABASE_CONNECTION_FAILED",
            f"Koneksi database gagal (SQLSTATE {sqlstate}). Periksa ketersediaan database dan konfigurasi "
            "DATABASE_URL/DATABASE_DDL_URL. Detail teknis tersedia di log worker.",
        )
    return (
        "JOB_EXECUTION_FAILED",
        f"Job gagal karena kesalahan backend ({type(exc).__name__}). Tim teknis dapat melacak detail "
        "lengkap melalui log worker menggunakan ID job ini.",
    )


async def dependencies_ready(session, source):
    dependency_ids = list(
        await session.scalars(
            select(SourceDependency.upstream_source_id).where(
                SourceDependency.tenant_id == source.tenant_id,
                SourceDependency.downstream_source_id == source.id,
            )
        )
    )
    if not dependency_ids:
        return True
    rows = await session.execute(
        select(Job.source_id, func.max(Job.finished_at))
        .where(
            Job.tenant_id == source.tenant_id,
            Job.source_id.in_([source.id, *dependency_ids]),
            Job.kind.in_(["ETL", "SYNC_REVIEW"]),
            Job.status == "SUCCEEDED",
        )
        .group_by(Job.source_id)
    )
    latest = {str(source_id): finished_at for source_id, finished_at in rows}
    downstream_finished = latest.get(str(source.id))
    return all(
        latest.get(str(dependency_id)) is not None
        and (
            downstream_finished is None
            or latest[str(dependency_id)] > downstream_finished
        )
        for dependency_id in dependency_ids
    )


async def execute_job(session, job):
    if job.source_id:
        source = await session.get(DataSource, job.source_id)
        if source and source.unlinked_at is not None:
            raise AppError("SOURCE_UNLINKED", "Job sumber yang sudah di-unlink tidak dapat dijalankan.", 409)
    user = await session.get(User, job.requested_by)
    roles = REVIEW_ROLES if job.kind in ("DEPLOY", "ROLLBACK") else EDIT_ROLES
    if not user or not user.is_active or user.tenant_id != job.tenant_id or user.role not in roles:
        raise AppError("FORBIDDEN", "Akun pembuat job tidak lagi memiliki izin.", 403)
    if job.kind == "DISCOVER":
        return await SourceService(session, user).discover(job.source_id)
    if job.kind == "PROFILE":
        return await SourceService(session, user).profile(job.source_id)
    if job.kind == "AI_CONFIG":
        return await AIConfigurationService(session, user).generate(
            job.source_id, job.payload["source_sheet_id"]
        )
    if job.kind in ("DEPLOY", "ROLLBACK"):
        return await ConfigurationService(session, user).deploy(
            job.payload["configuration_id"], rollback=job.kind == "ROLLBACK"
        )
    if job.kind == "ETL":
        return await ETLExecutionService(session, user).run(job.source_id)
    if job.kind == "SYNC_REVIEW":
        return await SourceService(session, user).sync_review(job.source_id)
    if job.kind == "IMPORT_REVIEW":
        return await ImportReviewService(session, user).work(job)
    raise AppError("JOB_INVALID", "Jenis job tidak dikenal.")


def _audit_stage(session, job, status, *, stage=None, error_code=None, error_message=None):
    if not job.source_id:
        return
    details = {
        "job_id": str(job.id),
        "job_kind": job.kind,
        "status": status,
    }
    if stage:
        details["stage"] = stage
    source_sheet_id = (job.payload or {}).get("source_sheet_id")
    if source_sheet_id:
        details["source_sheet_id"] = str(source_sheet_id)
    if status == "FAILED":
        details["error_code"] = error_code or job.error_code
        details["error_message"] = error_message or job.error_message
    session.add(AuditEvent(
        tenant_id=job.tenant_id,
        user_id=job.requested_by,
        event=f"source.stage_{status.lower()}",
        resource_id=str(job.source_id),
        details=details,
    ))


async def run_pending(tenant_id=None):
    async with SessionFactory() as session, session.begin():
        query = select(Job)
        if tenant_id is not None:
            query = query.where(Job.tenant_id == tenant_id)
        job = await session.scalar(
            query.where(Job.status == "QUEUED")
            .order_by(Job.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return {"processed": 0}
        job.status, job.started_at = "RUNNING", now()
        _audit_stage(session, job, "STARTED")
        job_id = job.id
    try:
        async with SessionFactory() as session, session.begin():
            job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if job.status != "RUNNING":
                return {"processed": 0, "job_id": job_id}
            timeout = max(30, (get_settings().job_stale_minutes - 1) * 60)
            result = await asyncio.wait_for(execute_job(session, job), timeout=timeout)
            job.status, job.result, job.finished_at = "SUCCEEDED", result, now()
            _audit_stage(session, job, "SUCCEEDED")
            profile_error = (result or {}).get("profile_error") if job.kind == "DISCOVER" else None
            if profile_error:
                _audit_stage(
                    session, job, "FAILED", stage="PROFILING",
                    error_code=profile_error.get("code"),
                    error_message=profile_error.get("message"),
                )
    except Exception as exc:
        if not isinstance(exc, AppError):
            logger.exception(
                "Unhandled background job failure",
                extra={"job_id": str(job_id), "job_kind": job.kind},
            )
        async with SessionFactory() as session, session.begin():
            job = await session.get(Job, job_id)
            job.status, job.finished_at = "FAILED", now()
            job.error_code, job.error_message = _job_failure_details(exc, job.kind)
            _audit_stage(session, job, "FAILED")
            add_notification(
                session,
                tenant_id=job.tenant_id,
                event_key=f"job:{job.id}:failed",
                kind="JOB_FAILED",
                severity="ERROR",
                resource_type="JOB",
                resource_id=job.id,
                title="Job gagal",
                message="Job berhenti karena kegagalan teknis. Periksa kode kegagalan.",
                details={"error_code": job.error_code, "job_kind": job.kind},
            )
            await fail_import_job(session, job, job.error_code)
            if job.source_id and job.kind in ("DISCOVER", "PROFILE", "AI_CONFIG"):
                source = await session.get(DataSource, job.source_id)
                if source and source.unlinked_at is None:
                    source.status = "AI_FAILED" if job.kind == "AI_CONFIG" else "PROFILE_FAILED"
    return {"processed": 1, "job_id": job_id}


async def schedule_sources():
    async with SessionFactory() as session, session.begin():
        locked = await session.scalar(text("SELECT pg_try_advisory_xact_lock(hashtext('etl-scheduler'))"))
        if not locked:
            return
        stale = await session.scalars(
            select(Job)
            .where(
                Job.status == "RUNNING",
                Job.started_at < now() - timedelta(minutes=get_settings().job_stale_minutes),
            )
            .with_for_update(skip_locked=True)
        )
        for job in stale:
            job.status, job.error_code = "FAILED", "WORKER_INTERRUPTED"
            job.error_message, job.finished_at = (
                "Worker terputus atau melewati batas durasi; retry job secara eksplisit.",
                now(),
            )
            _audit_stage(session, job, "FAILED")
            add_notification(
                session,
                tenant_id=job.tenant_id,
                event_key=f"job:{job.id}:failed",
                kind="JOB_FAILED",
                severity="ERROR",
                resource_type="JOB",
                resource_id=job.id,
                title="Job worker terputus",
                message="Job melewati batas durasi dan perlu diperiksa sebelum retry.",
                details={"error_code": job.error_code, "job_kind": job.kind},
            )
            await fail_import_job(session, job, job.error_code)
        sources = await session.scalars(
            select(DataSource)
            .where(
                DataSource.sync_schedule.is_not(None),
                DataSource.paused.is_(False),
                DataSource.unlinked_at.is_(None),
                DataSource.status == "ACTIVE",
            )
            .with_for_update(skip_locked=True)
        )
        for source in sources:
            last = source.last_scheduled_at or source.created_at
            if not cron_schedule(source.sync_schedule, source.schedule_timezone).is_due(last).is_due:
                continue
            if not await dependencies_ready(session, source):
                continue
            pending = await session.scalar(
                select(Job.id)
                .where(Job.source_id == source.id, Job.kind.in_(["ETL", "SYNC_REVIEW"]), Job.status.in_(["QUEUED", "RUNNING"]))
                .limit(1)
            )
            if pending:
                if source.concurrency_policy == "SKIP_IF_RUNNING":
                    source.last_scheduled_at = now()
                continue
            session.add(
                Job(
                    tenant_id=source.tenant_id,
                    source_id=source.id,
                    requested_by=source.owner_user_id,
                    kind="SYNC_REVIEW",
                    payload={},
                )
            )
            source.last_scheduled_at = now()
