from datetime import datetime

from sqlalchemy import func, select, update

from app.core.config import get_settings
from app.core.database import transaction
from app.core.exceptions import AppError
from app.models.base import now
from app.models.etl import Job
from app.models.notification import OperationalNotification
from app.models.source import DataSource, ProfilingRun, SourceSheet
from app.services.audit_service import system_audit
from app.services.google_sheets_service import GoogleSheetsService


def _parse_google_time(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _has_changed(previous, current):
    return previous is not None and current is not None and current > previous


async def monitor_source_changes(google=None):
    """Poll Drive metadata and queue discovery+profiling when a spreadsheet changes."""
    settings = get_settings()
    if not settings.source_change_monitor_enabled:
        return {"checked": 0, "changed": 0, "queued": 0}
    google = google or GoogleSheetsService()
    checked = changed = queued = 0
    # Keep DB locks short; network calls happen outside a transaction.
    async with transaction() as session:
        sources = list((await session.scalars(
            select(DataSource)
            .where(DataSource.unlinked_at.is_(None))
            .order_by(DataSource.change_checked_at.asc().nullsfirst(), DataSource.created_at)
            .limit(settings.source_change_monitor_batch_size)
            .with_for_update(skip_locked=True)
        )).all())
        source_data = [
            (source.id, source.tenant_id, source.spreadsheet_id, source.owner_user_id,
             dict(source.access_metadata or {}))
            for source in sources
        ]
        last_profiles = {}
        if sources:
            rows = await session.execute(
                select(SourceSheet.source_id, func.max(ProfilingRun.created_at))
                .join(ProfilingRun, ProfilingRun.source_sheet_id == SourceSheet.id)
                .where(SourceSheet.source_id.in_([source.id for source in sources]))
                .group_by(SourceSheet.source_id)
            )
            last_profiles = {str(source_id): profiled_at for source_id, profiled_at in rows}
        source_data = [
            (*item, last_profiles.get(str(item[0])))
            for item in source_data
        ]
        # Claim before releasing the transaction so overlapping Beat ticks don't
        # repeatedly check the same slow upstream file.
        for source in sources:
            source.change_checked_at = now()

    for source_id, tenant_id, spreadsheet_id, owner_id, access_metadata, last_profiled_at in source_data:
        try:
            current_modified = _parse_google_time(await google.modified_time(spreadsheet_id))
        except AppError as exc:
            # Inform the steward once; never block ordinary ETL or flood the notification center.
            async with transaction() as session:
                event_key = f"source-monitor-unavailable:{source_id}"
                exists = await session.scalar(select(OperationalNotification.id).where(
                    OperationalNotification.tenant_id == tenant_id,
                    OperationalNotification.event_key == event_key,
                ))
                if not exists:
                    session.add(OperationalNotification(
                        tenant_id=tenant_id, event_key=event_key, kind="SOURCE_MONITOR_UNAVAILABLE",
                        severity="WARN", resource_type="SOURCE", resource_id=source_id,
                        title="Pemantauan perubahan belum aktif",
                        message="Sistem belum dapat membaca metadata perubahan Google Drive. Aktifkan Drive API dan izin metadata untuk Service Account; discovery dan profiling manual tetap dapat digunakan.",
                        details={"error_code": exc.code}, recipient_user_id=owner_id,
                    ))
                    system_audit(session, tenant_id, "source.change_monitor_unavailable", source_id,
                                 error_code=exc.code)
            continue
        async with transaction() as session:
            source = await session.scalar(
                select(DataSource).where(DataSource.id == source_id).with_for_update(skip_locked=True)
            )
            if source is None or source.unlinked_at is not None:
                continue
            checked += 1
            source.change_checked_at = now()
            await session.execute(
                update(OperationalNotification)
                .where(
                    OperationalNotification.tenant_id == tenant_id,
                    OperationalNotification.resource_id == source_id,
                    OperationalNotification.kind == "SOURCE_MONITOR_UNAVAILABLE",
                    OperationalNotification.acknowledged_at.is_(None),
                )
                .values(acknowledged_at=now())
            )
            if current_modified is None:
                continue
            # Compare the first observation against the latest existing profiling
            # time, so rollout can find already-stale reviews on the initial scan.
            initial_baseline = source.drive_modified_at is None
            old_modified = source.drive_modified_at
            if initial_baseline:
                source.drive_modified_at = current_modified
                if last_profiled_at is None or current_modified <= last_profiled_at:
                    continue
            elif not _has_changed(source.drive_modified_at, current_modified):
                continue

            changed += 1
            source.drive_modified_at = current_modified
            source.status = "CHANGE_DETECTED"
            pending = await session.scalar(
                select(Job.id).where(
                    Job.source_id == source.id,
                    Job.kind == "DISCOVER",
                    Job.status.in_(("QUEUED", "RUNNING")),
                ).limit(1)
            )
            job_id = str(pending) if pending else None
            if pending is None:
                job = Job(
                    tenant_id=source.tenant_id,
                    source_id=source.id,
                    requested_by=source.owner_user_id,
                    kind="DISCOVER",
                    payload={
                        "system_trigger": "DRIVE_CHANGE",
                        "observed_modified_at": current_modified.isoformat(),
                    },
                )
                session.add(job)
                await session.flush()
                job_id = str(job.id)
                queued += 1
            system_audit(
                session,
                tenant_id,
                "source.external_change_detected",
                source_id,
                previous_modified_at=old_modified.isoformat() if old_modified else None,
                modified_at=current_modified.isoformat(),
                initial_baseline=initial_baseline,
                since_profiled_at=last_profiled_at.isoformat() if initial_baseline and last_profiled_at else None,
                job_id=job_id,
                detected_by="DRIVE_METADATA_POLL",
            )

            recipient_ids = {
                str(user_id) for user_id in (
                    owner_id,
                    access_metadata.get("data_owner_user_id"),
                    access_metadata.get("data_steward_user_id"),
                ) if user_id
            }
            if not recipient_ids:
                recipient_ids = {None}
            for recipient_id in recipient_ids:
                event_key = f"source-change:{source_id}:{current_modified.isoformat()}:{recipient_id or 'all'}"
                exists = await session.scalar(select(OperationalNotification.id).where(
                    OperationalNotification.tenant_id == tenant_id,
                    OperationalNotification.event_key == event_key,
                ))
                if exists:
                    continue
                session.add(OperationalNotification(
                    tenant_id=tenant_id,
                    event_key=event_key,
                    kind="SOURCE_CHANGED",
                    severity="WARN",
                    resource_type="SOURCE",
                    resource_id=source_id,
                    title="Google Sheet berubah",
                    message="Perubahan file terdeteksi. Discovery dan profiling otomatis dijalankan; periksa tab serta buat review baru jika snapshot sebelumnya sudah usang.",
                    details={
                        "modified_at": current_modified.isoformat(),
                        "job_id": job_id,
                        "resolution": "DISCOVERY_AND_PROFILE",
                    },
                    recipient_user_id=recipient_id,
                ))
    return {"checked": checked, "changed": changed, "queued": queued}
