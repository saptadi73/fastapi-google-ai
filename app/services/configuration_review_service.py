"""Review projections and two-step workbook imports; no deployment side effects."""

import asyncio
from types import SimpleNamespace

from app.core.exceptions import AppError
from app.models.configuration import Configuration
from app.models.etl import Snapshot
from app.models.source import DataSource, SourceSheet
from app.repositories.base import record
from app.repositories.source_repository import SourceRepository
from app.schemas.configuration import REVIEW_SECTIONS, ConfigurationPatch
from app.services.classification_service import classification_record
from app.services.configuration_service import ConfigurationService
from app.services.profiling_service import digest
from app.services.workbook_service import decode, identities, parse_workbook, token

CAPABILITIES = {
    "review_sections": REVIEW_SECTIONS,
    "editable_template_tabs": [
        "02 Struktur Kolom",
        "03 Aturan Cleansing",
        "05 Data Quality",
        "06 Target Database",
        "10 Data Product Catalog",
        "11 Metric Definitions",
        "14 Review",
    ],
    "unsupported": [
        "Master registry dan foreign key otomatis",
        "Taxonomy mapping",
        "Join relationships",
        "Intent query mapping",
        "Ekspresi transformasi bebas",
        "Pengaturan OpenAI dan operasional melalui Excel",
    ],
    "max_workbook_bytes": 2_000_000,
    "preview_expiry_minutes": 15,
}


class ConfigurationReviewService(ConfigurationService):
    async def context(self, config_id, *, lock=False):
        config = await self.repo.get(Configuration, config_id, lock=lock)
        source = await self.repo.get(DataSource, config.source_id)
        sheet = await self.repo.get(SourceSheet, config.source_sheet_id)
        snapshot = await self.session.scalar(
            self.repo.query(Snapshot)
            .where(Snapshot.source_sheet_id == sheet.id)
            .order_by(Snapshot.created_at.desc())
            .limit(1)
        )
        if snapshot is None:
            raise AppError("PROFILE_REQUIRED", "Profiling diperlukan sebelum review.", 409)
        return config, source, sheet, snapshot

    async def review(self, config_id):
        config, source, sheet, _ = await self.context(config_id)
        profile = await SourceRepository(self.session, self.user.tenant_id).latest_profile(sheet.id)
        try:
            validation = await self.validate(config)
        except AppError as exc:
            validation = {"valid": False, "errors": [{"code": exc.code, "message": exc.message}]}
        return {
            "configuration": record(config),
            "source": record(source),
            "sheet": record(sheet),
            "classification": classification_record(sheet),
            "profile": profile.profile_json if profile else None,
            "validation": validation,
            "capabilities": CAPABILITIES,
        }

    async def preview(self, config_id, data):
        config, source, sheet, snapshot = await self.context(config_id)
        self.require_draft(config)
        parsed = await asyncio.to_thread(parse_workbook, data.content_base64, config, source, sheet, snapshot)
        result = {
            **parsed,
            "can_apply": False,
            "revision_no": config.revision_no,
            "diff": {},
            "preview_token": None,
        }
        if parsed["errors"]:
            return result
        candidate = SimpleNamespace(
            source_sheet_id=config.source_sheet_id,
            based_on_fingerprint=config.based_on_fingerprint,
            configuration_json=parsed["configuration"],
        )
        try:
            result["validation"] = await self.validate(candidate)
        except AppError as exc:
            result["errors"] = [{"location": "validation", "message": exc.message, "code": exc.code}]
            return result
        result["diff"] = {
            key: {"before": config.configuration_json.get(key), "after": value}
            for key, value in parsed["configuration"].items()
            if config.configuration_json.get(key) != value
        }
        result["preview_token"] = token(
            {
                **identities(config, snapshot),
                "actor_id": str(self.user.id),
                "candidate_hash": digest(
                    {"configuration": parsed["configuration"], "question_answers": parsed["question_answers"]}
                ),
            },
            "etl-workbook-preview",
            15,
        )
        result["can_apply"] = True
        return result

    @staticmethod
    def require_draft(config):
        if config.status not in ("AI_DRAFT", "NEEDS_REVIEW"):
            raise AppError("CONFIGURATION_IMMUTABLE", "Clone menjadi draft sebelum mengimpor Excel.", 409)

    async def apply(self, config_id, data):
        config, _, _, snapshot = await self.context(config_id, lock=True)
        self.require_draft(config)
        claims = decode(data.preview_token, "etl-workbook-preview")
        expected = {
            **identities(config, snapshot),
            "actor_id": str(self.user.id),
            "candidate_hash": digest(
                {
                    "configuration": data.configuration.model_dump(mode="json"),
                    "question_answers": data.question_answers,
                }
            ),
        }
        if any(claims.get(key) != value for key, value in expected.items()):
            raise AppError(
                "WORKBOOK_PREVIEW_STALE",
                "Draft, snapshot, pengguna, atau isi preview berubah; lakukan preview ulang.",
                409,
            )
        return await self.patch(config_id, ConfigurationPatch(**data.model_dump(exclude={"preview_token"})))
