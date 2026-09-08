import json

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.base import now
from app.models.configuration import Approval, Artifact, Configuration
from app.models.etl import Snapshot
from app.models.semantic import DataProduct
from app.models.source import DataSource, SourceSheet
from app.repositories.configuration_repository import ConfigurationRepository
from app.repositories.source_repository import SourceRepository
from app.schemas.configuration import REVIEW_SECTIONS, ETLConfiguration
from app.services.artifact_service import ArtifactService
from app.services.audit_service import audit
from app.services.classification_service import (
    ClassificationService,
    classification_record,
    require_classification,
)
from app.services.etl_compiler_service import transform_rows
from app.services.google_sheets_service import GoogleSheetsService
from app.services.job_service import enqueue
from app.services.profiling_service import digest, profile_values
from app.services.schema_compiler_service import deploy_schema, schema_plan


class ConfigurationService:
    def __init__(self, session, user):
        self.session, self.user = session, user
        self.repo = ConfigurationRepository(session, user.tenant_id)
        self.artifacts = ArtifactService(session, user.tenant_id)

    async def submit_review(self, config_id, data):
        config = await self.repo.get(Configuration, config_id, lock=True)
        if config.status not in ("AI_DRAFT", "NEEDS_REVIEW"):
            raise AppError("CONFIGURATION_CONFLICT", "Konfigurasi tidak dapat diajukan review.", 409)
        if config.revision_no != data.revision_no:
            raise AppError("CONFIGURATION_CONFLICT", "Revision berubah; muat ulang draft.", 409)
        sheet = await ClassificationService(self.session, self.user).locked_sheet(config.source_sheet_id)
        require_classification(sheet)
        validation = await self.validate(config)
        if not validation["valid"]:
            raise AppError(
                "CONFIGURATION_INVALID", "Selesaikan pertanyaan dan error sebelum mengajukan review."
            )
        if data.snapshot_hash != validation["snapshot_hash"]:
            raise AppError("REVIEW_STALE", "Snapshot berubah; validasi kembali.", 409)
        expected_columns = {c["target_column"] for c in config.configuration_json["columns"]}
        if set(data.reviewed_columns) != expected_columns or set(data.reviewed_sections) != set(
            REVIEW_SECTIONS
        ):
            raise AppError("REVIEW_INCOMPLETE", "Periksa seluruh kolom dan bagian konfigurasi.")
        config.status = "NEEDS_REVIEW"
        config.revision_no += 1
        config.review_state = {
            "answers": (config.review_state or {}).get("answers", {}),
            "submitted_by": self.user.id,
            "submitted_at": now().isoformat(),
            "submitted_revision": config.revision_no,
            "reviewed_columns": data.reviewed_columns,
            "reviewed_sections": data.reviewed_sections,
            "snapshot_hash": validation["snapshot_hash"],
            "snapshot_id": validation["snapshot_id"],
            "classification_revision": sheet.classification_revision,
            "dataset_kind": sheet.dataset_kind,
        }
        audit(self.session, self.user, "configuration.review_requested", config.id)
        return config

    async def queue_deployment(self, config_id, rollback=False):
        config = await self.repo.get(Configuration, config_id)
        expected = "SUPERSEDED" if rollback else "APPROVED"
        if config.status != expected:
            raise AppError("APPROVAL_REQUIRED", f"Konfigurasi harus berstatus {expected}.", 409)
        sheet = await self.repo.get(SourceSheet, config.source_sheet_id)
        self.require_classification_evidence(config, sheet)
        return await enqueue(
            self.session,
            self.user,
            "ROLLBACK" if rollback else "DEPLOY",
            config.source_id,
            configuration_id=config.id,
        )

    async def compare(self, config_id, against):
        current = await self.repo.get(Configuration, config_id)
        previous = await self.repo.get(Configuration, against)
        if current.source_sheet_id != previous.source_sheet_id:
            raise AppError(
                "CONFIGURATION_CONFLICT", "Hanya versi dari tab yang sama dapat dibandingkan.", 409
            )
        return {
            k: {"before": previous.configuration_json.get(k), "after": v}
            for k, v in current.configuration_json.items()
            if v != previous.configuration_json.get(k)
        }

    @staticmethod
    def require_classification_evidence(config, sheet):
        require_classification(sheet)
        evidence = config.review_state or {}
        if (
            evidence.get("classification_revision") != sheet.classification_revision
            or evidence.get("dataset_kind") != sheet.dataset_kind
        ):
            raise AppError(
                "CLASSIFICATION_REVIEW_STALE",
                "Klasifikasi berubah atau belum tercakup review; ajukan review baru. Clone jika konfigurasi sudah disetujui.",
                409,
            )

    async def create(self, sheet_id, configuration, status="NEEDS_REVIEW", **ai_metadata):
        sheet = await self.repo.get(SourceSheet, sheet_id, lock=True)
        profile = await SourceRepository(self.session, self.user.tenant_id).latest_profile(sheet.id)
        if not profile or not sheet.last_fingerprint:
            raise AppError("PROFILE_REQUIRED", "Jalankan profiling sebelum membuat konfigurasi.", 409)
        version = await self.repo.next_version(sheet.id)
        self.validate_columns(configuration, profile.profile_json)
        config = await self.repo.add(
            Configuration,
            source_id=sheet.source_id,
            source_sheet_id=sheet.id,
            version_no=version,
            status=status,
            based_on_fingerprint=profile.fingerprint,
            configuration_json=configuration.model_dump(mode="json"),
            created_by=self.user.id,
            **ai_metadata,
        )
        audit(self.session, self.user, "configuration.created", config.id, version=version)
        return config

    @staticmethod
    def validate_columns(config, profile):
        headers = {c["source_column"] for c in profile["columns"]}
        if not {c.source_column for c in config.columns}.issubset(headers):
            raise AppError("AI_CONFIGURATION_INVALID", "Mapping merujuk header yang tidak tersedia.")

    async def validate(self, config):
        parsed = ETLConfiguration.model_validate(config.configuration_json)
        sheet = await self.repo.get(SourceSheet, config.source_sheet_id)
        if sheet.last_fingerprint != config.based_on_fingerprint:
            raise AppError(
                "CONFIGURATION_CONFLICT", "Fingerprint berubah; buat draft baru dari profile terkini.", 409
            )
        profile = await SourceRepository(self.session, self.user.tenant_id).latest_profile(sheet.id)
        if not profile:
            raise AppError("PROFILE_REQUIRED", "Profiling belum tersedia.", 409)
        self.validate_columns(parsed, profile.profile_json)
        snapshot = await self.session.scalar(
            self.repo.query(Snapshot)
            .where(Snapshot.source_sheet_id == sheet.id)
            .order_by(Snapshot.created_at.desc())
            .limit(1)
        )
        if snapshot is None:
            raise AppError("PROFILE_REQUIRED", "Snapshot belum tersedia.", 409)
        good, issues, warnings = transform_rows(snapshot.values, sheet, parsed)
        suspected = {c["source_column"] for c in profile.profile_json["columns"] if c.get("pii_suspected")}
        headers = [str(v).strip() for v in snapshot.values[sheet.header_row - 1]]
        previews = []
        for row_number, output in good[:10]:
            original = snapshot.values[row_number - 1]
            before, after = {}, {}
            for column in parsed.columns:
                sensitive = (
                    column.pii_classification in ("MEDIUM", "HIGH") or column.source_column in suspected
                )
                i = headers.index(column.source_column)
                before[column.source_column] = (
                    "[REDACTED]" if sensitive else (original[i] if i < len(original) else None)
                )
                after[column.target_column] = "[REDACTED]" if sensitive else output[column.target_column]
            previews.append({"source_row": row_number, "before": before, "after": after})
        return {
            "valid": not parsed.unresolved_questions and not issues,
            "classification": classification_record(sheet),
            "ready_for_review": not parsed.unresolved_questions
            and not issues
            and classification_record(sheet)["execution_ready"],
            "sample_rows_valid": len(good),
            "sample_rows_invalid": len(issues),
            "warnings": warnings[:20],
            "unresolved_questions": parsed.unresolved_questions,
            "snapshot_id": snapshot.id,
            "snapshot_hash": snapshot.content_hash,
            "row_previews": previews,
            "issues": [{"source_row": i["source_row"], "errors": i["errors"]} for i in issues[:50]],
            "deployment_plan": schema_plan(parsed, sheet.id, self.user.tenant_id),
        }

    async def patch(self, config_id, data):
        config = await self.repo.get(Configuration, config_id, lock=True)
        if config.status not in ("AI_DRAFT", "NEEDS_REVIEW"):
            raise AppError(
                "CONFIGURATION_IMMUTABLE", "Clone konfigurasi menjadi draft baru sebelum mengedit.", 409
            )
        if config.revision_no != data.revision_no:
            raise AppError("CONFIGURATION_CONFLICT", "Revision berubah; muat ulang konfigurasi.", 409)
        before = config.configuration_json
        removed = set(before.get("unresolved_questions", [])) - set(data.configuration.unresolved_questions)
        if not removed.issubset(data.question_answers):
            raise AppError(
                "QUESTION_ANSWER_REQUIRED", "Isi jawaban untuk setiap pertanyaan yang diselesaikan."
            )
        if not set(data.question_answers).issubset(set(before.get("unresolved_questions", []))):
            raise AppError("QUESTION_INVALID", "Jawaban merujuk pertanyaan yang tidak ada pada draft.")
        answers = {**(config.review_state or {}).get("answers", {})}
        for question in removed:
            answers[question] = {
                "answer": data.question_answers[question],
                "user_id": self.user.id,
                "at": now().isoformat(),
            }
        config.review_state = {"answers": answers}
        config.configuration_json = data.configuration.model_dump(mode="json")
        config.revision_no += 1
        config.created_by = self.user.id
        await self.validate(config)
        audit(
            self.session,
            self.user,
            "configuration.updated",
            config.id,
            revision=config.revision_no,
            changed_fields=[k for k in before if before[k] != config.configuration_json.get(k)],
        )
        return config

    async def decision(self, config_id, data, decision):
        config = await self.repo.get(Configuration, config_id, lock=True)
        if config.status != "NEEDS_REVIEW" or data.revision_no != config.revision_no:
            raise AppError(
                "CONFIGURATION_CONFLICT",
                "Konfigurasi tidak sedang menunggu review atau revision berubah.",
                409,
            )
        if decision == "APPROVED":
            if get_settings().require_separate_approver and config.created_by == self.user.id:
                raise AppError(
                    "SEPARATE_APPROVER_REQUIRED", "Approval harus dilakukan oleh akun approver lain.", 403
                )
            sheet = await ClassificationService(self.session, self.user).locked_sheet(config.source_sheet_id)
            self.require_classification_evidence(config, sheet)
            validation = await self.validate(config)
            evidence = config.review_state or {}
            if evidence.get("submitted_revision") != config.revision_no:
                raise AppError("REVIEW_REQUIRED", "Ajukan review revision ini sebelum approval.", 409)
            if evidence.get("snapshot_hash") != validation["snapshot_hash"]:
                raise AppError(
                    "REVIEW_STALE", "Snapshot berubah setelah review; validasi dan ajukan kembali.", 409
                )
            if not validation["valid"]:
                raise AppError(
                    "CONFIGURATION_INVALID", "Selesaikan pertanyaan dan error dry-run sebelum approval."
                )
            config.approved_by, config.approved_at = self.user.id, now()
            await self.artifacts.create(config)
        config.status = decision
        config.revision_no += 1
        await self.repo.add(
            Approval,
            configuration_id=config.id,
            reviewer_id=self.user.id,
            decision=decision,
            comment=data.comment,
        )
        audit(self.session, self.user, "configuration." + decision.lower(), config.id)
        return config

    async def clone(self, config_id):
        config = await self.repo.get(Configuration, config_id)
        return await self.create(
            config.source_sheet_id, ETLConfiguration.model_validate(config.configuration_json)
        )

    async def deploy(self, config_id, *, rollback=False, google=None):
        config = await self.repo.get(Configuration, config_id, lock=True)
        allowed = ("APPROVED", "SUPERSEDED") if rollback else ("APPROVED",)
        if config.status not in allowed:
            raise AppError(
                "APPROVAL_REQUIRED", "Konfigurasi belum disetujui atau tidak dapat diaktifkan.", 409
            )
        sheet = await ClassificationService(self.session, self.user).locked_sheet(config.source_sheet_id)
        self.require_classification_evidence(config, sheet)
        source = await self.repo.get(DataSource, config.source_id)
        artifact = await self.session.scalar(
            self.repo.query(Artifact).where(
                Artifact.configuration_version_id == config.id,
                Artifact.artifact_type == "RUNTIME_CONFIG",
                Artifact.is_current,
            )
        )
        if not artifact:
            raise AppError("ARTIFACT_MISSING", "Runtime artifact belum tersedia.", 409)
        _, content = await self.artifacts.read(config, artifact.id)
        if json.loads(content)["configuration"] != config.configuration_json:
            raise AppError("ARTIFACT_HASH_MISMATCH", "Artifact berbeda dari registry.", 409)
        parsed = ETLConfiguration.model_validate(config.configuration_json)
        values = (await (google or GoogleSheetsService()).read_sheets(source.spreadsheet_id, [sheet]))[0]
        if (config.review_state or {}).get("snapshot_hash") != digest(values):
            raise AppError(
                "REVIEW_STALE", "Data sumber berubah sejak review; profile dan review draft baru.", 409
            )
        profile = profile_values(
            values,
            sheet.sheet_name,
            sheet.header_row,
            sheet.data_start_row,
            sheet.range_a1,
            get_settings().etl_sample_row_limit,
        )
        if profile["fingerprint"] != config.based_on_fingerprint:
            raise AppError("CONFIGURATION_CONFLICT", "Schema sumber berubah sejak approval.", 409)
        _, issues, _ = transform_rows(values, sheet, parsed)
        if issues or parsed.unresolved_questions:
            raise AppError("CONFIGURATION_INVALID", "Dry-run gagal; perbaiki data atau konfigurasi.")
        # Check catalog collisions before DDL.
        product = await self.session.scalar(
            self.repo.query(DataProduct).where(DataProduct.source_sheet_id == sheet.id)
        )
        collision = await self.session.scalar(
            self.repo.query(DataProduct).where(
                DataProduct.code == parsed.semantic.code, DataProduct.source_sheet_id != sheet.id
            )
        )
        if collision:
            raise AppError("CONFIGURATION_CONFLICT", "Kode data product sudah digunakan tab lain.", 409)
        _, view_name = await deploy_schema(parsed, sheet.id, self.user.tenant_id)
        if sheet.active_configuration_id:
            old = await self.repo.get(Configuration, sheet.active_configuration_id)
            old.status = "SUPERSEDED"
            await self.session.flush()
        config.status = "ACTIVE"
        sheet.active_configuration_id = config.id
        sheet.last_fingerprint = profile["fingerprint"]
        source.status = "ACTIVE"
        attributes = {
            "code": parsed.semantic.code,
            "name": parsed.dataset_business_name,
            "description": parsed.dataset_description,
            "view_name": view_name,
            "columns": [
                c.model_dump(mode="json") for c in parsed.columns if c.pii_classification in ("NONE", "LOW")
            ],
            "dimensions": parsed.semantic.dimensions,
            "metrics": [m.model_dump() for m in parsed.semantic.metrics],
            "allowed_roles": parsed.semantic.allowed_roles,
            "status": "ACTIVE",
        }
        if product:
            for field, value in attributes.items():
                setattr(product, field, value)
            product.version += 1
        else:
            product = await self.repo.add(DataProduct, source_sheet_id=sheet.id, **attributes)
        audit(
            self.session,
            self.user,
            "configuration.rollback" if rollback else "configuration.activated",
            config.id,
            product=product.code,
            version=config.version_no,
        )
        return {"configuration_id": config.id, "data_product_code": product.code, "status": "ACTIVE"}
