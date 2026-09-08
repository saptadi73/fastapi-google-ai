import asyncio
from datetime import timedelta

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.database import SessionFactory
from app.core.exceptions import AppError
from app.domain.enums import EDIT_ROLES, REVIEW_ROLES
from app.models.auth import User
from app.models.base import now
from app.models.etl import Job
from app.models.source import DataSource
from app.schemas.source import cron_schedule
from app.services.ai_configuration_service import AIConfigurationService
from app.services.configuration_service import ConfigurationService
from app.services.etl_execution_service import ETLExecutionService
from app.services.import_review_service import ImportReviewService, fail_import_job
from app.services.source_service import SourceService


async def execute_job(session, job):
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
    if job.kind == "IMPORT_REVIEW":
        return await ImportReviewService(session, user).work(job)
    raise AppError("JOB_INVALID", "Jenis job tidak dikenal.")


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
        job_id = job.id
    try:
        async with SessionFactory() as session, session.begin():
            job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if job.status != "RUNNING":
                return {"processed": 0, "job_id": job_id}
            timeout = max(30, (get_settings().job_stale_minutes - 1) * 60)
            result = await asyncio.wait_for(execute_job(session, job), timeout=timeout)
            job.status, job.result, job.finished_at = "SUCCEEDED", result, now()
    except Exception as exc:
        async with SessionFactory() as session, session.begin():
            job = await session.get(Job, job_id)
            job.status, job.finished_at = "FAILED", now()
            job.error_code = exc.code if isinstance(exc, AppError) else "JOB_EXECUTION_FAILED"
            job.error_message = (
                exc.message
                if isinstance(exc, AppError)
                else "Job gagal. Periksa konfigurasi dan koneksi layanan."
            )
            await fail_import_job(session, job, job.error_code)
            if job.source_id and job.kind in ("DISCOVER", "PROFILE", "AI_CONFIG"):
                source = await session.get(DataSource, job.source_id)
                if source:
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
            await fail_import_job(session, job, job.error_code)
        sources = await session.scalars(
            select(DataSource)
            .where(
                DataSource.sync_schedule.is_not(None),
                DataSource.paused.is_(False),
                DataSource.status == "ACTIVE",
            )
            .with_for_update(skip_locked=True)
        )
        for source in sources:
            last = source.last_scheduled_at or source.created_at
            if not cron_schedule(source.sync_schedule).is_due(last).is_due:
                continue
            pending = await session.scalar(
                select(Job.id)
                .where(Job.source_id == source.id, Job.kind == "ETL", Job.status.in_(["QUEUED", "RUNNING"]))
                .limit(1)
            )
            if not pending:
                session.add(
                    Job(
                        tenant_id=source.tenant_id,
                        source_id=source.id,
                        requested_by=source.owner_user_id,
                        kind="ETL",
                        payload={},
                    )
                )
                source.last_scheduled_at = now()
