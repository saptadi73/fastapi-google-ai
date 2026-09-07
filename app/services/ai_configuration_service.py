from app.core.exceptions import AppError
from app.models.source import DataSource, SourceSheet
from app.repositories.source_repository import SourceRepository
from app.schemas.configuration import ETLConfiguration
from app.services.configuration_service import ConfigurationService
from app.services.openai_service import OpenAIService
from app.services.profiling_service import canonical_json


class AIConfigurationService:
    def __init__(self, session, user):
        self.session, self.user = session, user
        self.repo = SourceRepository(session, user.tenant_id)

    async def generate(self, source_id, sheet_id):
        source = await self.repo.get(DataSource, source_id)
        sheet = await self.repo.get(SourceSheet, sheet_id)
        if sheet.source_id != source.id:
            raise AppError("RESOURCE_NOT_FOUND", "Tab tidak ditemukan pada source ini.", 404)
        profile = await self.repo.latest_profile(sheet.id)
        if not profile:
            raise AppError("PROFILE_REQUIRED", "Profiling diperlukan terlebih dahulu.", 409)
        context = canonical_json(
            {
                "business_context": source.description,
                "sheet_name": sheet.sheet_name,
                "profile": profile.profile_json,
            }
        )
        parsed, metadata = await OpenAIService().generate(self.user, "ETL_CONFIG", context, ETLConfiguration)
        config = await ConfigurationService(self.session, self.user).create(
            sheet.id, parsed, "AI_DRAFT", **metadata
        )
        return {"configuration_id": config.id, "status": config.status}
