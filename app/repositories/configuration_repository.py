from sqlalchemy import func, select

from app.models.configuration import Configuration
from app.models.source import SourceSheet
from app.repositories.base import TenantRepository


class ConfigurationRepository(TenantRepository):
    async def next_version(self, sheet_id):
        await self.get(SourceSheet, sheet_id, lock=True)
        current = await self.session.scalar(
            select(func.max(Configuration.version_no)).where(
                Configuration.tenant_id == self.tenant_id, Configuration.source_sheet_id == str(sheet_id)
            )
        )
        return (current or 0) + 1
