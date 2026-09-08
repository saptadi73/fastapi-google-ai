from types import SimpleNamespace

from sqlalchemy import text

from app.core.exceptions import AppError
from app.domain.enums import EDIT_ROLES, REVIEW_ROLES
from app.domain.import_workflow import ImportAction, ImportStatus, next_import_status
from app.models.configuration import Configuration
from app.models.etl import Snapshot
from app.models.import_review import ImportReview
from app.models.master import MasterDefinition, MasterSourceBinding
from app.models.source import DataSource, SourceSheet
from app.repositories.base import TenantRepository, record
from app.schemas.configuration import ETLConfiguration
from app.schemas.data_policy import DatasetPolicy
from app.schemas.import_review import ImportReviewCreate
from app.services.audit_service import audit
from app.services.etl_compiler_service import transform_rows
from app.services.job_service import enqueue
from app.services.profiling_service import digest


class ImportReviewService:
    def __init__(self, session, user):
        self.session, self.user = session, user
        self.repo = TenantRepository(session, user.tenant_id)

    def role(self, edit=False):
        if self.user.role not in (EDIT_ROLES if edit else (*EDIT_ROLES, *REVIEW_ROLES)):
            raise AppError("FORBIDDEN", "Peran tidak diizinkan mengakses batch import.", 403)

    async def locked(self, review_id):
        self.role()
        review = await self.session.scalar(
            self.repo.query(ImportReview)
            .where(ImportReview.id == str(review_id))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if review is None:
            raise AppError("RESOURCE_NOT_FOUND", "Batch tidak ditemukan.", 404)
        return review

    def move(self, review, action, *, worker=False):
        review.status = next_import_status(
            ImportStatus(review.status), action, role=None if worker else self.user.role
        ).value
        review.revision_no += 1
        audit(
            self.session,
            self.user,
            "import." + action.value.lower(),
            review.id,
            status=review.status,
            revision_no=review.revision_no,
        )

    async def capture(self, data):
        sheet = await self.repo.get(SourceSheet, data.source_sheet_id)
        source = await self.repo.get(DataSource, sheet.source_id)
        # Refresh identity-map objects: dependency checks can run twice in one transaction.
        await self.session.refresh(sheet)
        await self.session.refresh(source)
        if not sheet.enabled or source.paused:
            raise AppError("IMPORT_SOURCE_UNAVAILABLE", "Sumber/tab nonaktif atau dijeda.", 409)
        if sheet.classification_status != "CONFIRMED" or not sheet.last_fingerprint:
            raise AppError("IMPORT_CLASSIFICATION_REQUIRED", "Klasifikasi dan profiling harus tersedia.", 409)
        snapshot = await self.session.scalar(
            self.repo.query(Snapshot)
            .where(Snapshot.source_sheet_id == sheet.id)
            .order_by(Snapshot.created_at.desc(), Snapshot.id.desc())
            .limit(1)
        )
        if snapshot is None or digest(snapshot.values) != snapshot.content_hash:
            raise AppError(
                "IMPORT_SNAPSHOT_INVALID", "Snapshot tidak tersedia atau integritasnya berubah.", 409
            )
        dependencies = {
            "schema_version": "1.0",
            "tenant_id": self.user.tenant_id,
            "source_id": source.id,
            "source_sheet_id": sheet.id,
            "snapshot_hash": snapshot.content_hash,
            "dataset_kind": sheet.dataset_kind,
            "classification_revision": sheet.classification_revision,
            "fingerprint": sheet.last_fingerprint,
            "sheet": {
                "header_row": sheet.header_row,
                "data_start_row": sheet.data_start_row,
                "range_a1": sheet.range_a1,
            },
        }
        master_policy = None
        if sheet.dataset_kind == "MASTER":
            if data.configuration_id:
                raise AppError(
                    "IMPORT_MAPPING_INVALID",
                    "MASTER menggunakan binding approved, bukan configuration_id.",
                    409,
                )
            binding = await self.session.scalar(
                self.repo.query(MasterSourceBinding)
                .where(MasterSourceBinding.source_sheet_id == sheet.id)
                .execution_options(populate_existing=True)
            )
            if (
                binding is None
                or binding.status != "APPROVED"
                or binding.classification_revision != sheet.classification_revision
                or binding.snapshot_hash != snapshot.content_hash
                or binding.fingerprint != sheet.last_fingerprint
            ):
                raise AppError(
                    "IMPORT_BINDING_REQUIRED",
                    "Binding approved harus sesuai snapshot dan klasifikasi terkini.",
                    409,
                )
            master = await self.repo.get(MasterDefinition, binding.master_definition_id)
            await self.session.refresh(master)
            if (
                not master.is_active
                or not master.approved_definition_json
                or master.approved_version != binding.master_version
            ):
                raise AppError("IMPORT_MASTER_STALE", "Versi master tidak aktif atau berubah.", 409)
            definition = master.approved_definition_json
            master_policy = definition["policy"]
            config = ETLConfiguration(
                dataset_business_name=definition["name"],
                grain="Satu record master per business key",
                target_table="master_preview",
                load_strategy="UPSERT",
                columns=binding.columns_json,
                semantic={"code": "MASTER_PREVIEW", "dimensions": [], "metrics": []},
            ).model_dump(mode="json")
            dependencies.update(
                binding_id=binding.id,
                binding_revision=binding.revision_no,
                master_id=master.id,
                master_version=master.approved_version,
                master_definition_hash=digest(definition),
            )
        else:
            if not data.configuration_id:
                raise AppError(
                    "IMPORT_CONFIGURATION_REQUIRED", "NON_MASTER memerlukan configuration_id approved.", 409
                )
            configuration = await self.repo.get(Configuration, data.configuration_id)
            await self.session.refresh(configuration)
            if (
                configuration.source_sheet_id != sheet.id
                or configuration.status not in ("APPROVED", "ACTIVE")
                or configuration.based_on_fingerprint != sheet.last_fingerprint
            ):
                raise AppError(
                    "IMPORT_CONFIGURATION_INVALID",
                    "Konfigurasi harus approved untuk tab/fingerprint ini.",
                    409,
                )
            config = ETLConfiguration.model_validate(configuration.configuration_json).model_dump(mode="json")
            dependencies.update(
                configuration_id=configuration.id, configuration_revision=configuration.revision_no
            )
        dependencies["configuration_hash"] = digest(config)
        dependencies["policy"] = DatasetPolicy(
            classification_scope="SHEET", dataset_kind=sheet.dataset_kind, master=master_policy
        ).model_dump(mode="json")
        return sheet, snapshot, dependencies, config

    async def is_current(self, review):
        try:
            _, _, deps, _ = await self.capture(
                ImportReviewCreate(
                    source_sheet_id=review.source_sheet_id,
                    configuration_id=review.dependencies.get("configuration_id"),
                )
            )
            pinned = await self.repo.get(Snapshot, review.snapshot_id)
            return (
                digest(deps) == review.idempotency_key
                and digest(review.configuration_json) == review.dependencies["configuration_hash"]
                and pinned.source_sheet_id == review.source_sheet_id
                and pinned.content_hash == review.dependencies["snapshot_hash"]
                and digest(pinned.values) == review.dependencies["snapshot_hash"]
            )
        except AppError:
            return False

    @staticmethod
    def response(review):
        # Neither raw snapshot nor frozen configuration (which may contain sensitive literals) is exposed.
        data = record(review, exclude=("configuration_json", "dependencies", "findings"))
        deps = review.dependencies
        data.update(
            dataset_kind=deps["dataset_kind"],
            snapshot_hash=deps["snapshot_hash"],
            configuration_id=deps.get("configuration_id"),
            configuration_revision=deps.get("configuration_revision"),
            master_id=deps.get("master_id"),
            master_version=deps.get("master_version"),
            policy=deps["policy"],
            finding_count=len(review.findings),
            execution_ready=False,
        )
        return data

    async def queue(self, review):
        job = await enqueue(
            self.session,
            self.user,
            "IMPORT_REVIEW",
            review.source_id,
            import_review_id=review.id,
            generation=review.generation,
        )
        review.job_id = job["job_id"]

    async def create(self, data):
        self.role(edit=True)
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": "import:" + self.user.tenant_id + ":" + str(data.source_sheet_id)},
        )
        sheet, snapshot, dependencies, configuration = await self.capture(data)
        key = digest(dependencies)
        existing = await self.session.scalar(
            self.repo.query(ImportReview).where(ImportReview.idempotency_key == key)
        )
        if existing:
            return {"review": self.response(existing), "reused": True}
        review = await self.repo.add(
            ImportReview,
            source_id=sheet.source_id,
            source_sheet_id=sheet.id,
            snapshot_id=snapshot.id,
            created_by=self.user.id,
            dependencies=dependencies,
            configuration_json=configuration,
            idempotency_key=key,
        )
        await self.queue(review)
        audit(
            self.session, self.user, "import.created", review.id, snapshot_id=snapshot.id, idempotency_key=key
        )
        return {"review": self.response(review), "reused": False}

    async def detail(self, review_id):
        self.role()
        review = await self.repo.get(ImportReview, review_id)
        return {**self.response(review), "dependencies_current": await self.is_current(review)}

    async def list(self, status=None, sheet_id=None, offset=0, limit=50):
        self.role()
        query = self.repo.query(ImportReview)
        if status:
            query = query.where(ImportReview.status == status)
        if sheet_id:
            await self.repo.get(SourceSheet, sheet_id)
            query = query.where(ImportReview.source_sheet_id == str(sheet_id))
        rows = (
            await self.session.scalars(
                query.order_by(ImportReview.created_at.desc(), ImportReview.id)
                .offset(offset)
                .limit(limit + 1)
            )
        ).all()
        return {"items": [self.response(r) for r in rows[:limit]], "has_more": len(rows) > limit}

    async def findings(self, review_id, offset, limit):
        self.role()
        review = await self.repo.get(ImportReview, review_id)
        return {
            "items": review.findings[offset : offset + limit],
            "has_more": len(review.findings) > offset + limit,
        }

    async def action(self, review_id, data, action):
        self.role(edit=True)
        review = await self.locked(review_id)
        if review.revision_no != data.revision_no:
            raise AppError("IMPORT_REVISION_CONFLICT", "Revisi batch berubah; muat ulang.", 409)
        if action == ImportAction.CANCEL:
            self.move(review, action)
        else:
            if review.status not in ("NEEDS_INPUT", "FAILED", "STALE_REVIEW"):
                raise AppError("IMPORT_STATE_CONFLICT", "Batch belum dapat dilanjutkan.", 409)
            if not await self.is_current(review):
                if review.status != "STALE_REVIEW":
                    self.move(review, ImportAction.INVALIDATE, worker=True)
                audit(
                    self.session,
                    self.user,
                    "import.stale",
                    review.id,
                    action=action.value,
                    comment=data.comment,
                )
                return self.response(review)
            if action == ImportAction.RESUME and (
                review.status != "NEEDS_INPUT" or review.checkpoint.get("blocking_codes")
            ):
                raise AppError(
                    "IMPORT_INPUT_PENDING",
                    "Selesaikan temuan atau tunggu capability review; resume tidak mengabaikan blocker.",
                    409,
                )
            # Revalidating unchanged NEEDS_INPUT cannot resolve missing capabilities or data issues.
            if review.status == "NEEDS_INPUT" and action != ImportAction.RESUME:
                raise AppError(
                    "IMPORT_INPUT_PENDING",
                    "Snapshot tetap memiliki blocker; perbaiki sumber dan buat batch baru.",
                    409,
                )
            self.move(review, action)
            review.generation += 1
            await self.queue(review)
        audit(
            self.session,
            self.user,
            "import.user_action",
            review.id,
            action=action.value,
            comment=data.comment,
        )
        return self.response(review)

    async def work(self, job):
        review = await self.locked(job.payload["import_review_id"])
        if (
            job.payload.get("generation") != review.generation
            or job.id != review.job_id
            or review.status not in ("VALIDATING", "AI_REVIEWING")
        ):
            return {"import_review_id": review.id, "status": review.status, "skipped": True}
        if not await self.is_current(review):
            self.move(review, ImportAction.INVALIDATE, worker=True)
            return {"import_review_id": review.id, "status": review.status}
        if review.status == "VALIDATING":
            if review.checkpoint.get("deterministic_complete") and not review.checkpoint.get(
                "blocking_codes"
            ):
                self.move(review, ImportAction.START_AI, worker=True)
                await self.queue(review)
                return {"import_review_id": review.id, "status": review.status, "checkpoint_reused": True}
            snapshot = await self.repo.get(Snapshot, review.snapshot_id)
            try:
                config = ETLConfiguration.model_validate(review.configuration_json)
                good, issues, warnings = transform_rows(
                    snapshot.values, SimpleNamespace(**review.dependencies["sheet"]), config
                )
                findings = [{"source_row": i["source_row"], "errors": i["errors"]} for i in issues]
                findings.extend({"severity": "WARN", **warning} for warning in warnings)
                blockers = ["DATA_QUALITY_ISSUES"] if issues else []
                if config.unresolved_questions:
                    blockers.append("CONFIGURATION_QUESTIONS_PENDING")
                checkpoint = {
                    "deterministic_complete": True,
                    "rows_valid": len(good),
                    "rows_invalid": len(issues),
                    "warning_count": len(warnings),
                    "blocking_codes": blockers,
                    "ai_coverage": "NOT_STARTED",
                }
            except AppError as exc:
                if not exc.code.startswith("DQ_") and exc.code != "CONFIGURATION_CONFLICT":
                    raise
                findings = [{"code": exc.code}]
                checkpoint = {
                    "deterministic_complete": False,
                    "blocking_codes": [exc.code],
                    "ai_coverage": "NOT_STARTED",
                }
            review.findings, review.checkpoint = findings, checkpoint
            if not await self.is_current(review):
                self.move(review, ImportAction.INVALIDATE, worker=True)
            elif checkpoint["blocking_codes"]:
                self.move(review, ImportAction.REQUEST_INPUT, worker=True)
            else:
                self.move(review, ImportAction.START_AI, worker=True)
                await self.queue(review)
        else:
            # BE-10 will replace this capability blocker with resumable AI evidence.
            review.checkpoint = {**review.checkpoint, "blocking_codes": ["AI_REVIEW_NOT_IMPLEMENTED"]}
            self.move(review, ImportAction.REQUEST_INPUT, worker=True)
        return {"import_review_id": review.id, "status": review.status, "execution_ready": False}


async def fail_import_job(session, job, code):
    """Called in the failure/recovery transaction after the failed worker rolls back."""
    if job.kind != "IMPORT_REVIEW":
        return
    review = await session.scalar(
        TenantRepository(session, job.tenant_id)
        .query(ImportReview)
        .where(ImportReview.id == job.payload.get("import_review_id"))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        review
        and review.job_id == job.id
        and review.generation == job.payload.get("generation")
        and review.status in ("VALIDATING", "AI_REVIEWING")
    ):
        review.status = next_import_status(ImportStatus(review.status), ImportAction.FAIL, role=None).value
        review.revision_no += 1
        review.checkpoint = {**review.checkpoint, "last_error_code": code}
        audit(
            session,
            SimpleNamespace(tenant_id=job.tenant_id, id=job.requested_by),
            "import.failed",
            review.id,
            job_id=job.id,
            error_code=code,
            revision_no=review.revision_no,
        )
