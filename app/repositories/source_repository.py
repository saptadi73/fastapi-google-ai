from app.models.source import DataSource, ProfilingRun, SourceSheet
from app.repositories.base import TenantRepository


class SourceRepository(TenantRepository):
    async def sheets(self, source_id):
        await self.get(DataSource, source_id)
        return await self.list(SourceSheet, conditions=(SourceSheet.source_id == str(source_id),))

    async def latest_profile(self, sheet_id):
        await self.get(SourceSheet, sheet_id)
        return await self.session.scalar(
            self.query(ProfilingRun)
            .where(ProfilingRun.source_sheet_id == str(sheet_id))
            .order_by(ProfilingRun.created_at.desc())
            .limit(1)
        )
