from sqlalchemy import func, select

from app.core.exceptions import AppError
from app.models.audit import AIUsage
from app.models.etl import Job, QualityIssue
from app.models.source import DataSource
from app.repositories.base import TenantRepository, record
from app.services.audit_service import audit
from app.services.job_service import enqueue


class MonitoringService:
    def __init__(self, session, user):
        self.session, self.user = session, user
        self.repo = TenantRepository(session, user.tenant_id)

    async def retry(self, job_id):
        job = await self.repo.get(Job, job_id)
        if job.kind == "IMPORT_REVIEW":
            raise AppError(
                "IMPORT_REVALIDATE_REQUIRED",
                "Gunakan revalidate batch dengan revision_no; retry job tidak boleh melewati checkpoint.",
                409,
            )
        if job.status != "FAILED":
            raise AppError("JOB_CONFLICT", "Hanya job gagal yang dapat dicoba ulang.", 409)
        return await enqueue(self.session, self.user, job.kind, job.source_id, **job.payload)

    async def pause(self, source_id, paused):
        source = await self.repo.get(DataSource, source_id, lock=True)
        source.paused = paused
        audit(self.session, self.user, "source.paused" if paused else "source.resumed", source.id)
        return record(source)

    async def resolve(self, issue_id, resolution):
        issue = await self.repo.get(QualityIssue, issue_id, lock=True)
        issue.status, issue.resolution = "RESOLVED", resolution
        audit(self.session, self.user, "quality_issue.resolved", issue.id)
        return record(issue, exclude=("data",))

    async def quality_summary(self):
        rows = await self.session.execute(
            select(QualityIssue.status, func.count())
            .where(QualityIssue.tenant_id == self.user.tenant_id)
            .group_by(QualityIssue.status)
        )
        return {status: count for status, count in rows}

    async def ai_summary(self, by_user=False):
        columns = [
            func.count(AIUsage.id).label("requests"),
            func.sum(AIUsage.input_tokens).label("input_tokens"),
            func.sum(AIUsage.output_tokens).label("output_tokens"),
            func.sum(AIUsage.cached_tokens).label("cached_tokens"),
            func.sum(AIUsage.estimated_cost_usd).label("estimated_cost_usd"),
        ]
        stmt = select(*columns).where(AIUsage.tenant_id == self.user.tenant_id)
        if by_user:
            stmt = stmt.add_columns(AIUsage.user_id).group_by(AIUsage.user_id)
        return [dict(row) for row in (await self.session.execute(stmt)).mappings()]
