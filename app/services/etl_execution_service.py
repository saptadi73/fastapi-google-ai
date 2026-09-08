import json

from sqlalchemy import delete, text
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.base import now
from app.models.configuration import Artifact, Configuration
from app.models.etl import ETLRun, QualityIssue, Snapshot, StagingRow
from app.models.semantic import DataProduct
from app.models.source import DataSource, ProfilingRun, SourceSheet
from app.repositories.source_repository import SourceRepository
from app.schemas.configuration import ETLConfiguration
from app.services.artifact_service import ArtifactService
from app.services.audit_service import audit
from app.services.classification_service import ClassificationService, require_classification
from app.services.etl_compiler_service import transform_rows
from app.services.google_sheets_service import GoogleSheetsService
from app.services.job_service import enqueue
from app.services.profiling_service import canonical_json, digest, profile_values
from app.services.schema_compiler_service import compile_table


class ETLExecutionService:
    def __init__(self, session, user, google=None):
        self.session, self.user = session, user
        self.repo = SourceRepository(session, user.tenant_id)
        self.google = google or GoogleSheetsService()

    async def run(self, source_id):
        source = await self.repo.get(DataSource, source_id)
        locked = await self.session.scalar(
            text("SELECT pg_try_advisory_xact_lock(hashtext(:key))"), {"key": f"etl:{source.id}"}
        )
        if not locked:
            raise AppError("ETL_RUN_LOCKED", "ETL sumber ini masih berjalan.", 409)
        if source.paused:
            raise AppError("SOURCE_PAUSED", "Jadwal sumber sedang dijeda.", 409)
        sheets = await ClassificationService(self.session, self.user).require_source_ready(
            source.id, lock=True
        )
        batches = await self.google.read_sheets(source.spreadsheet_id, sheets)
        results = []
        for sheet, values in zip(sheets, batches):
            # Serializes with activation so a run cannot accidentally read two configuration versions.
            sheet = await self.repo.get(SourceSheet, sheet.id, lock=True)
            require_classification(sheet)
            if not sheet.active_configuration_id:
                raise AppError("APPROVAL_REQUIRED", "Tab belum memiliki konfigurasi aktif.", 409)
            config = await self.repo.get(Configuration, sheet.active_configuration_id)
            if config.status != "ACTIVE":
                raise AppError("APPROVAL_REQUIRED", "Registry konfigurasi tidak aktif.", 409)
            artifact = await self.session.scalar(
                self.repo.query(Artifact).where(
                    Artifact.configuration_version_id == config.id,
                    Artifact.artifact_type == "RUNTIME_CONFIG",
                    Artifact.is_current,
                )
            )
            if not artifact:
                raise AppError("ARTIFACT_MISSING", "Runtime artifact tidak tersedia.", 409)
            _, payload = await ArtifactService(self.session, self.user.tenant_id).read(config, artifact.id)
            if json.loads(payload)["configuration"] != config.configuration_json:
                raise AppError("ARTIFACT_HASH_MISMATCH", "Artifact tidak sesuai registry.", 409)
            parsed = ETLConfiguration.model_validate(config.configuration_json)
            profile = profile_values(
                values,
                sheet.sheet_name,
                sheet.header_row,
                sheet.data_start_row,
                sheet.range_a1,
                get_settings().etl_sample_row_limit,
            )
            if profile["fingerprint"] != config.based_on_fingerprint:
                source.status = "CHANGE_DETECTED"
                sheet.last_fingerprint = profile["fingerprint"]
                await self.repo.add(
                    ProfilingRun,
                    source_id=source.id,
                    source_sheet_id=sheet.id,
                    fingerprint=profile["fingerprint"],
                    profile_json=profile,
                )
                await self.repo.add(
                    Snapshot,
                    source_id=source.id,
                    source_sheet_id=sheet.id,
                    content_hash=digest(values),
                    row_count=profile["row_count"],
                    values=values,
                )
                if (
                    get_settings().openai_api_key.get_secret_value()
                    and get_settings().openai_model_etl_config
                ):
                    await enqueue(self.session, self.user, "AI_CONFIG", source.id, source_sheet_id=sheet.id)
                audit(self.session, self.user, "source.schema_drift", source.id, sheet_id=sheet.id)
                results.append({"source_sheet_id": sheet.id, "status": "CHANGE_DETECTED"})
                continue
            run_key = digest([source.id, sheet.id, digest(values), config.id])
            previous = await self.session.scalar(self.repo.query(ETLRun).where(ETLRun.run_key == run_key))
            if previous:
                results.append({"etl_run_id": previous.id, "status": "SKIPPED_DUPLICATE"})
                continue
            snapshot = await self.repo.add(
                Snapshot,
                source_id=source.id,
                source_sheet_id=sheet.id,
                content_hash=digest(values),
                row_count=profile["row_count"],
                values=values,
            )
            run = await self.repo.add(
                ETLRun,
                source_id=source.id,
                source_sheet_id=sheet.id,
                configuration_id=config.id,
                snapshot_id=snapshot.id,
                run_key=run_key,
                rows_extracted=profile["row_count"],
            )
            good, issues, warnings = transform_rows(values, sheet, parsed)
            # Never replace trusted data with a partial/invalid FULL_REFRESH snapshot.
            if parsed.load_strategy == "FULL_REFRESH" and issues:
                raise AppError(
                    "DQ_STOP_BATCH",
                    "FULL_REFRESH memerlukan seluruh baris valid; trusted data dipertahankan.",
                )
            for issue in issues:
                await self.repo.add(QualityIssue, etl_run_id=run.id, source_id=source.id, **issue)
            table = compile_table(parsed, sheet.id)
            if parsed.load_strategy == "FULL_REFRESH":
                await self.session.execute(delete(table).where(table.c._tenant_id == self.user.tenant_id))
            keys = [c.target_column for c in parsed.columns if c.is_business_key or c.is_primary_key]
            for row_number, values_dict in good:
                await self.repo.add(
                    StagingRow,
                    etl_run_id=run.id,
                    source_row=row_number,
                    data=json.loads(canonical_json(values_dict)),
                )
                row = {
                    **values_dict,
                    "_tenant_id": self.user.tenant_id,
                    "_source_sheet_id": sheet.id,
                    "_source_row": row_number,
                    "_etl_run_id": run.id,
                    "_row_hash": digest(values_dict),
                }
                stmt = insert(table).values(**row)
                if parsed.load_strategy == "UPSERT":
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["_tenant_id", *keys],
                        set_={k: stmt.excluded[k] for k in row if k not in ("_tenant_id", *keys)},
                    )
                else:
                    stmt = stmt.on_conflict_do_nothing()
                outcome = await self.session.execute(stmt)
                run.rows_loaded += max(0, outcome.rowcount)
            run.rows_quarantined = len(issues)
            run.status = "SUCCEEDED_WITH_WARNINGS" if issues or warnings else "SUCCEEDED"
            run.finished_at = now()
            product = await self.session.scalar(
                self.repo.query(DataProduct).where(DataProduct.source_sheet_id == sheet.id)
            )
            if product:
                product.freshness_version += 1
            audit(
                self.session,
                self.user,
                "etl.completed",
                run.id,
                loaded=run.rows_loaded,
                quarantined=len(issues),
                warning_count=len(warnings),
            )
            results.append(
                {
                    "etl_run_id": run.id,
                    "status": run.status,
                    "rows_loaded": run.rows_loaded,
                    "rows_quarantined": run.rows_quarantined,
                }
            )
        return {"runs": results}
