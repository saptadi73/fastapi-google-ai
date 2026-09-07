from app.models.etl import Job
from app.models.source import DataSource
from app.repositories.base import TenantRepository
from app.services.audit_service import audit


async def enqueue(session, user, kind, source_id=None, **payload):
    repo = TenantRepository(session, user.tenant_id)
    if source_id:
        await repo.get(DataSource, source_id)
    job = await repo.add(Job, kind=kind, source_id=source_id, requested_by=user.id, payload=payload)
    audit(session, user, "job.queued", job.id, kind=kind)
    # The database is the durable queue. Celery beat dispatches pending rows after commit.
    return {"job_id": job.id, "status": "QUEUED", "status_url": f"/api/v1/jobs/{job.id}"}
