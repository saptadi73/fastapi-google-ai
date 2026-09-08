import asyncio
import hashlib
from pathlib import Path
from uuid import uuid4

import yaml

from app.core.config import ROOT, get_settings
from app.core.exceptions import AppError
from app.models.configuration import Artifact
from app.models.etl import Snapshot
from app.models.source import DataSource, SourceSheet
from app.repositories.base import TenantRepository
from app.services.profiling_service import canonical_json
from app.services.workbook_service import MIME, export_workbook


class ArtifactService:
    def __init__(self, session, tenant_id):
        self.repo = TenantRepository(session, tenant_id)

    def root(self):
        path = get_settings().artifact_storage_path
        return (path if path.is_absolute() else ROOT / path).resolve()

    async def create(self, config, kind="RUNTIME_CONFIG", fmt="JSON"):
        payload = {
            "schema_version": "1.0",
            "configuration_id": config.id,
            "configuration_version": config.version_no,
            "tenant_id": config.tenant_id,
            "source_id": config.source_id,
            "source_sheet_id": config.source_sheet_id,
            "configuration": config.configuration_json,
        }
        if fmt == "JSON":
            content, mime = canonical_json(payload).encode(), "application/json"
        elif fmt == "YAML":
            content, mime = yaml.safe_dump(payload, allow_unicode=True).encode(), "application/yaml"
        else:
            source = await self.repo.get(DataSource, config.source_id)
            sheet = await self.repo.get(SourceSheet, config.source_sheet_id)
            snapshot = await self.repo.session.scalar(
                self.repo.query(Snapshot)
                .where(Snapshot.source_sheet_id == sheet.id)
                .order_by(Snapshot.created_at.desc())
                .limit(1)
            )
            if snapshot is None:
                raise AppError("PROFILE_REQUIRED", "Jalankan profiling sebelum export.", 409)
            content = await asyncio.to_thread(export_workbook, config, source, sheet, snapshot)
            mime = MIME
        name = f"config-v{config.version_no}.{fmt.lower()}"
        path = self.root() / config.tenant_id / config.source_sheet_id / config.id / f"{uuid4()}-{name}"
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, content)
        return await self.repo.add(
            Artifact,
            configuration_version_id=config.id,
            artifact_type=kind,
            file_name=name,
            storage_uri=str(path),
            mime_type=mime,
            content_hash=hashlib.sha256(content).hexdigest(),
            file_size_bytes=len(content),
        )

    async def read(self, config, artifact_id):
        artifact = await self.repo.get(Artifact, artifact_id)
        if artifact.configuration_version_id != config.id:
            raise AppError("RESOURCE_NOT_FOUND", "Artifact tidak ditemukan.", 404)
        path = Path(artifact.storage_uri).resolve()
        if not path.is_relative_to(self.root()):
            raise AppError("ARTIFACT_INVALID", "Lokasi artifact tidak valid.", 409)
        try:
            content = await asyncio.to_thread(path.read_bytes)
        except OSError:
            raise AppError("ARTIFACT_MISSING", "File artifact tidak tersedia.", 409) from None
        if hashlib.sha256(content).hexdigest() != artifact.content_hash:
            raise AppError("ARTIFACT_HASH_MISMATCH", "Integritas artifact gagal; deployment dihentikan.", 409)
        return artifact, content
