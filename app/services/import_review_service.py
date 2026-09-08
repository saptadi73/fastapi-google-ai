from difflib import SequenceMatcher
import json
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.domain.enums import EDIT_ROLES, REVIEW_ROLES
from app.domain.import_workflow import ImportAction, ImportStatus, next_import_status
from app.models.configuration import Configuration
from app.models.etl import Snapshot
from app.models.import_review import ImportDecision, ImportQuestion, ImportReview, ImportReviewRow
from app.models.master import MasterDefinition, MasterSourceBinding
from app.models.source import DataSource, SourceSheet
from app.repositories.base import TenantRepository, record
from app.schemas.configuration import ETLConfiguration
from app.schemas.data_policy import DatasetPolicy
from app.schemas.import_review import (
    ImportProposalResolution,
    ImportQuestionDecision,
    ImportReviewCreate,
)
from app.services.audit_service import audit
from app.services.etl_compiler_service import cast_value, transform_rows
from app.services.job_service import enqueue
from app.services.master_service import MasterService
from app.services.master_storage_service import MasterStorageService, check_storage
from app.services.profiling_service import digest
from app.services.workbook_service import decode, token


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
            execution_ready=review.status in ("APPROVED", "APPLYING"),
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

    @staticmethod
    def json_value(value):
        def encode(item):
            if isinstance(item, Decimal):
                return int(item) if item == item.to_integral_value() else float(item)
            return str(item)

        return json.loads(json.dumps(value, default=encode))

    @staticmethod
    def question_response(question, decisions=()):
        data = record(question, exclude=("evidence",))
        data["candidate_count"] = len(question.candidates)
        data["decisions"] = [
            record(decision, exclude=("before_data", "after_data", "evidence")) for decision in decisions
        ]
        return data

    async def questions(self, review_id, status=None, category=None, offset=0, limit=50):
        self.role()
        await self.repo.get(ImportReview, review_id)
        query = self.repo.query(ImportQuestion).where(ImportQuestion.import_review_id == str(review_id))
        if status:
            query = query.where(ImportQuestion.status == status)
        if category:
            query = query.where(ImportQuestion.category == category)
        rows = (
            await self.session.scalars(
                query.order_by(ImportQuestion.source_row, ImportQuestion.created_at, ImportQuestion.id)
                .offset(offset)
                .limit(limit + 1)
            )
        ).all()
        question_ids = [q.id for q in rows[:limit]]
        decisions = {}
        if question_ids:
            for decision in (
                await self.session.scalars(
                    self.repo.query(ImportDecision)
                    .where(ImportDecision.import_question_id.in_(question_ids))
                    .order_by(ImportDecision.created_at)
                )
            ).all():
                decisions.setdefault(decision.import_question_id, []).append(decision)
        return {
            "items": [self.question_response(q, decisions.get(q.id, ())) for q in rows[:limit]],
            "has_more": len(rows) > limit,
        }

    async def answer_question(self, review_id, question_id, data: ImportQuestionDecision):
        self.role(edit=True)
        review = await self.locked(review_id)
        if review.status not in ("NEEDS_INPUT", "FAILED"):
            raise AppError("IMPORT_STATE_CONFLICT", "Batch belum menunggu keputusan pengguna.", 409)
        if not await self.is_current(review):
            if review.status != "STALE_REVIEW":
                self.move(review, ImportAction.INVALIDATE, worker=True)
            audit(
                self.session,
                self.user,
                "import.question_stale",
                review.id,
                question_id=str(question_id),
            )
            return {"question": None, "review": self.response(review), "stale": True}
        question = await self.session.scalar(
            self.repo.query(ImportQuestion)
            .where(ImportQuestion.id == str(question_id), ImportQuestion.import_review_id == review.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if question is None:
            raise AppError("RESOURCE_NOT_FOUND", "Pertanyaan tidak ditemukan.", 404)
        if question.revision_no != data.revision_no:
            raise AppError("IMPORT_QUESTION_REVISION_CONFLICT", "Revisi pertanyaan berubah; muat ulang.", 409)
        if question.status != "OPEN":
            raise AppError("IMPORT_QUESTION_ALREADY_ANSWERED", "Pertanyaan sudah memiliki keputusan.", 409)
        if data.action not in question.allowed_actions:
            raise AppError(
                "IMPORT_DECISION_ACTION_INVALID", "Aksi tidak diizinkan untuk pertanyaan ini.", 422
            )
        candidates = {str(c["id"]): c for c in question.candidates if c.get("id")}
        if data.action == "SELECT_RECORD":
            if data.selected_candidate_id is None or str(data.selected_candidate_id) not in candidates:
                raise AppError(
                    "IMPORT_DECISION_CANDIDATE_INVALID",
                    "Pilih kandidat yang tersedia pada pertanyaan ini.",
                    422,
                )
        elif data.selected_candidate_id is not None:
            raise AppError(
                "IMPORT_DECISION_CANDIDATE_INVALID", "Aksi ini tidak menerima kandidat record.", 422
            )
        if data.action == "KEEP_ORIGINAL" and question.mandatory:
            raise AppError(
                "IMPORT_DECISION_ACTION_INVALID",
                "Nilai asli tidak dapat dipertahankan untuk masalah wajib.",
                422,
            )
        if data.action in ("CORRECT_SOURCE", "PROPOSE_MASTER") and not data.reason.strip():
            raise AppError("IMPORT_DECISION_REASON_REQUIRED", "Alasan wajib diisi untuk tindakan ini.", 422)
        if data.action == "APPLY_CORRECTION" and data.corrected_value is None:
            raise AppError("IMPORT_DECISION_VALUE_REQUIRED", "Nilai koreksi wajib diisi.", 422)
        if data.action != "APPLY_CORRECTION" and data.corrected_value is not None:
            raise AppError(
                "IMPORT_DECISION_VALUE_INVALID", "Nilai koreksi hanya berlaku untuk APPLY_CORRECTION.", 422
            )
        if data.action == "PROPOSE_MASTER" and data.master_proposal is None:
            raise AppError(
                "IMPORT_MASTER_PROPOSAL_REQUIRED",
                "Usulan master lengkap wajib diisi untuk PROPOSE_MASTER.",
                422,
            )
        if data.action != "PROPOSE_MASTER" and data.master_proposal is not None:
            raise AppError(
                "IMPORT_MASTER_PROPOSAL_INVALID",
                "Usulan master hanya berlaku untuk PROPOSE_MASTER.",
                422,
            )
        after = {}
        if data.action == "APPLY_CORRECTION":
            column = next(
                (
                    c
                    for c in review.configuration_json["columns"]
                    if c["target_column"] == question.target_column
                ),
                None,
            )
            if column is None:
                raise AppError(
                    "IMPORT_DECISION_TARGET_INVALID",
                    "Target pertanyaan tidak tersedia pada konfigurasi batch.",
                    409,
                )
            try:
                after[question.target_column] = self.json_value(
                    cast_value(data.corrected_value, column["target_type"])
                )
            except (TypeError, ValueError):
                raise AppError(
                    "IMPORT_DECISION_VALUE_INVALID", "Nilai koreksi tidak cocok dengan tipe target.", 422
                ) from None
        elif data.action == "SELECT_RECORD":
            after[question.target_column] = str(data.selected_candidate_id)
        proposal = None
        if data.action == "PROPOSE_MASTER":
            proposal = await MasterService(self.session, self.user).create(data.master_proposal)
        if question.staging_row_id and after:
            row = await self.session.scalar(
                self.repo.query(ImportReviewRow)
                .where(ImportReviewRow.id == question.staging_row_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if row is None:
                raise AppError("IMPORT_STAGING_MISSING", "Staging batch tidak tersedia.", 409)
            row.corrected_data = {**row.corrected_data, **after}
        before = {question.target_column: "[REDACTED]"} if question.target_column else {}
        decision = await self.repo.add(
            ImportDecision,
            import_review_id=review.id,
            import_question_id=question.id,
            decided_by=self.user.id,
            revision_no=question.revision_no,
            action=data.action,
            selected_candidate_id=str(data.selected_candidate_id) if data.selected_candidate_id else None,
            proposed_master_definition_id=proposal.id if proposal else None,
            reason=data.reason,
            before_data=before,
            after_data=after,
            evidence={
                "scope": "ROW",
                "source_row": question.source_row,
                "question_key": question.question_key,
            },
        )
        question.status = "PENDING_APPROVAL" if data.action == "PROPOSE_MASTER" else "ANSWERED"
        question.revision_no += 1
        open_mandatory = await self.session.scalar(
            select(ImportQuestion.id)
            .where(
                ImportQuestion.tenant_id == self.user.tenant_id,
                ImportQuestion.import_review_id == review.id,
                ImportQuestion.status == "OPEN",
                ImportQuestion.mandatory.is_(True),
            )
            .limit(1)
        )
        blockers = list(review.checkpoint.get("blocking_codes", []))
        if not open_mandatory:
            blockers = [code for code in blockers if code != "DATA_QUALITY_ISSUES"]
        pending_proposal = await self.session.scalar(
            select(ImportQuestion.id)
            .where(
                ImportQuestion.tenant_id == self.user.tenant_id,
                ImportQuestion.import_review_id == review.id,
                ImportQuestion.status == "PENDING_APPROVAL",
            )
            .limit(1)
        )
        blockers = [code for code in blockers if code != "MASTER_PROPOSAL_PENDING"]
        if pending_proposal:
            blockers.append("MASTER_PROPOSAL_PENDING")
        review.checkpoint = {**review.checkpoint, "blocking_codes": blockers}
        # Count explicitly to keep SQLAlchemy portable and avoid exposing raw staging data.
        open_count = len(
            (
                await self.session.scalars(
                    self.repo.query(ImportQuestion).where(
                        ImportQuestion.import_review_id == review.id, ImportQuestion.status == "OPEN"
                    )
                )
            ).all()
        )
        review.checkpoint["open_question_count"] = open_count
        review.revision_no += 1
        audit(
            self.session,
            self.user,
            "import.question_answered",
            question.id,
            import_review_id=review.id,
            action=data.action,
            source_row=question.source_row,
            source_column=question.source_column,
            decision_id=decision.id,
        )
        return {"question": self.question_response(question, [decision]), "review": self.response(review)}

    async def resolve_master_proposal(self, review_id, question_id, data: ImportProposalResolution):
        self.role(edit=False)
        if self.user.role not in REVIEW_ROLES:
            raise AppError("FORBIDDEN", "Reviewer diperlukan untuk menyelesaikan proposal master.", 403)
        review = await self.locked(review_id)
        if review.status not in ("NEEDS_INPUT", "FAILED"):
            raise AppError("IMPORT_STATE_CONFLICT", "Batch belum menunggu keputusan pengguna.", 409)
        if not await self.is_current(review):
            if review.status != "STALE_REVIEW":
                self.move(review, ImportAction.INVALIDATE, worker=True)
            return {"question": None, "review": self.response(review), "stale": True}
        question = await self.session.scalar(
            self.repo.query(ImportQuestion)
            .where(ImportQuestion.id == str(question_id), ImportQuestion.import_review_id == review.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if question is None:
            raise AppError("RESOURCE_NOT_FOUND", "Pertanyaan tidak ditemukan.", 404)
        if question.revision_no != data.revision_no:
            raise AppError("IMPORT_QUESTION_REVISION_CONFLICT", "Revisi pertanyaan berubah; muat ulang.", 409)
        if question.status != "PENDING_APPROVAL":
            raise AppError(
                "IMPORT_PROPOSAL_STATE_CONFLICT", "Pertanyaan tidak menunggu approval proposal master.", 409
            )
        decision = await self.session.scalar(
            self.repo.query(ImportDecision)
            .where(
                ImportDecision.import_question_id == question.id,
                ImportDecision.action == "PROPOSE_MASTER",
                ImportDecision.proposed_master_definition_id == str(data.master_definition_id),
            )
            .with_for_update()
        )
        if decision is None:
            raise AppError(
                "IMPORT_MASTER_PROPOSAL_INVALID", "Proposal tidak terkait dengan pertanyaan ini.", 422
            )
        master = await self.repo.get(MasterDefinition, data.master_definition_id)
        if not master.is_active or master.status != "APPROVED" or not master.approved_definition_json:
            raise AppError("IMPORT_MASTER_PROPOSAL_PENDING", "Master usulan belum approved dan aktif.", 409)
        question.status = "ANSWERED"
        question.revision_no += 1
        pending = await self.session.scalar(
            select(ImportQuestion.id)
            .where(
                ImportQuestion.tenant_id == self.user.tenant_id,
                ImportQuestion.import_review_id == review.id,
                ImportQuestion.status == "PENDING_APPROVAL",
            )
            .limit(1)
        )
        blockers = [
            code for code in review.checkpoint.get("blocking_codes", []) if code != "MASTER_PROPOSAL_PENDING"
        ]
        if pending:
            blockers.append("MASTER_PROPOSAL_PENDING")
        review.checkpoint = {**review.checkpoint, "blocking_codes": blockers}
        review.revision_no += 1
        audit(
            self.session,
            self.user,
            "import.master_proposal_resolved",
            question.id,
            import_review_id=review.id,
            master_definition_id=master.id,
            decision_id=decision.id,
        )
        return {"question": self.question_response(question, [decision]), "review": self.response(review)}

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

    async def _preview_context(self, review_id, revision_no):
        self.role()
        review = await self.locked(review_id)
        if review.revision_no != revision_no:
            raise AppError("IMPORT_REVISION_CONFLICT", "Revisi batch berubah; muat ulang.", 409)
        if review.status not in ("READY_FOR_APPROVAL", "APPROVED"):
            raise AppError("IMPORT_STATE_CONFLICT", "Batch belum dapat dipreview.", 409)
        if review.checkpoint.get("blocking_codes"):
            raise AppError("IMPORT_INPUT_PENDING", "Selesaikan seluruh blocker sebelum preview.", 409)
        if not await self.is_current(review):
            self.move(review, ImportAction.INVALIDATE, worker=True)
            raise AppError("IMPORT_STALE_REVIEW", "Snapshot atau konfigurasi berubah; jalankan validasi ulang.", 409)
        config = ETLConfiguration.model_validate(review.configuration_json)
        rows = (await self.session.scalars(
            self.repo.query(ImportReviewRow)
            .where(ImportReviewRow.import_review_id == review.id)
            .order_by(ImportReviewRow.source_row)
        )).all()
        return review, config, rows

    async def preview(self, review_id, data):
        review, config, rows = await self._preview_context(review_id, data.revision_no)
        target = None
        definition = None
        if review.dependencies["dataset_kind"] == "MASTER":
            _, definition, target = await MasterStorageService(self.session, self.user).target(
                review.dependencies["master_id"]
            )
        else:
            from app.services.schema_compiler_service import compile_table

            target = compile_table(config, review.source_sheet_id)
        connection = await self.session.connection()
        await connection.run_sync(lambda sync: check_storage(sync, target))
        keys = (definition.business_key if definition else [
            c.target_column for c in config.columns if c.is_business_key or c.is_primary_key
        ])
        existing = {}
        if keys:
            query = select(*[target.c[k] for k in keys], target.c._record_id if hasattr(target.c, "_record_id") else target.c._row_hash).where(
                target.c._tenant_id == self.user.tenant_id
            )
            for row in (await self.session.execute(query)).mappings():
                normalized = self.json_value(dict(row))
                existing[tuple(normalized.get(k) for k in keys)] = normalized
        changes = []
        for row in rows:
            after = {**row.transformed_data, **row.corrected_data}
            key = tuple(after.get(k) for k in keys) if keys else None
            before = existing.get(key) if key is not None else None
            if before is None:
                outcome = "INSERT"
            else:
                comparable = {k: before.get(k) for k in after}
                outcome = "UNCHANGED" if comparable == after else "UPDATE"
            changes.append({"source_row": row.source_row, "outcome": outcome, "before": before, "after": after})
        preview_hash = digest({"review_id": str(review.id), "revision_no": review.revision_no, "changes": changes})
        preview_token = token(
            {"review_id": str(review.id), "tenant_id": str(review.tenant_id), "revision_no": review.revision_no, "preview_hash": preview_hash},
            "import-review-preview",
            30,
        )
        review.checkpoint = {**review.checkpoint, "preview_hash": preview_hash, "preview_revision": review.revision_no}
        return {
            "review": self.response(review),
            "target": target.fullname,
            "changes": changes,
            "summary": {
                "insert": sum(c["outcome"] == "INSERT" for c in changes),
                "update": sum(c["outcome"] == "UPDATE" for c in changes),
                "unchanged": sum(c["outcome"] == "UNCHANGED" for c in changes),
            },
            "preview_hash": preview_hash,
            "preview_token": preview_token,
            "can_approve": True,
        }

    async def approve(self, review_id, data):
        self.role()
        if self.user.role not in REVIEW_ROLES:
            raise AppError("FORBIDDEN", "Reviewer diperlukan untuk menyetujui batch import.", 403)
        review = await self.locked(review_id)
        if review.revision_no != data.revision_no:
            raise AppError("IMPORT_REVISION_CONFLICT", "Revisi batch berubah; muat ulang.", 409)
        if review.status != "READY_FOR_APPROVAL":
            raise AppError("IMPORT_STATE_CONFLICT", "Batch belum siap disetujui.", 409)
        if review.checkpoint.get("blocking_codes"):
            raise AppError("IMPORT_INPUT_PENDING", "Selesaikan seluruh blocker sebelum approval.", 409)
        if not review.checkpoint.get("preview_hash"):
            raise AppError("IMPORT_PREVIEW_REQUIRED", "Buat preview batch terlebih dahulu.", 409)
        if get_settings().require_separate_approver and review.created_by == self.user.id:
            raise AppError("SEPARATE_APPROVER_REQUIRED", "Approval harus dilakukan oleh akun reviewer lain.", 403)
        self.move(review, ImportAction.APPROVE)
        review.checkpoint = {**review.checkpoint, "approved_by": str(self.user.id), "approval_comment": data.comment}
        audit(self.session, self.user, "import.approved", review.id, comment=data.comment)
        return self.response(review)

    async def apply(self, review_id, data):
        self.role(edit=True)
        review, config, rows = await self._preview_context(review_id, data.revision_no)
        if review.status != "APPROVED":
            raise AppError("IMPORT_APPROVAL_REQUIRED", "Batch harus approved sebelum apply.", 409)
        claims = decode(data.preview_token, "import-review-preview")
        if any(claims.get(k) != v for k, v in {"review_id": str(review.id), "tenant_id": str(review.tenant_id), "revision_no": review.checkpoint.get("preview_revision"), "preview_hash": review.checkpoint.get("preview_hash")}.items()):
            raise AppError("IMPORT_PREVIEW_STALE", "Preview tidak sesuai dengan batch terbaru; jalankan preview ulang.", 409)
        self.move(review, ImportAction.APPLY)
        if review.dependencies["dataset_kind"] == "MASTER":
            _, definition, table = await MasterStorageService(self.session, self.user).target(review.dependencies["master_id"])
            keys = definition.business_key
        else:
            from app.services.schema_compiler_service import compile_table

            table = compile_table(config, review.source_sheet_id)
            keys = [c.target_column for c in config.columns if c.is_business_key or c.is_primary_key]
        connection = await self.session.connection()
        await connection.run_sync(lambda sync: check_storage(sync, table))
        loaded = 0
        for row in rows:
            values = {**row.transformed_data, **row.corrected_data}
            if not values:
                continue
            if review.dependencies["dataset_kind"] == "MASTER":
                values = {**values, "_tenant_id": self.user.tenant_id, "_record_id": str(uuid4()), "_source_sheet_id": review.source_sheet_id, "_source_row": row.source_row, "_source_snapshot_hash": review.dependencies["snapshot_hash"]}
            else:
                values = {**values, "_tenant_id": self.user.tenant_id, "_source_sheet_id": review.source_sheet_id, "_source_row": row.source_row, "_etl_run_id": review.id, "_row_hash": digest(values)}
            stmt = insert(table).values(**values)
            if keys:
                stmt = stmt.on_conflict_do_update(index_elements=["_tenant_id", *keys], set_={k: stmt.excluded[k] for k in values if k not in ("_tenant_id", *keys, "_record_id")})
            await self.session.execute(stmt)
            loaded += 1
        self.move(review, ImportAction.COMPLETE, worker=True)
        review.checkpoint = {**review.checkpoint, "rows_applied": loaded, "applied_by": str(self.user.id)}
        audit(self.session, self.user, "import.applied", review.id, rows_applied=loaded)
        return {"review": self.response(review), "rows_applied": loaded, "status": review.status}

    async def resolve_reference(self, review_id, data):
        self.role()
        review = await self.repo.get(ImportReview, review_id)
        if review.revision_no != data.revision_no:
            raise AppError("IMPORT_REVISION_CONFLICT", "Revisi batch berubah; muat ulang.", 409)
        master, definition, table = await MasterStorageService(self.session, self.user).target(
            data.master_definition_id
        )
        connection = await self.session.connection()
        await connection.run_sync(lambda sync: check_storage(sync, table))
        value = data.value.strip()
        predicates = [table.c[key] == value for key in definition.business_key]
        query = select(table).where(table.c._tenant_id == self.user.tenant_id)
        if len(definition.business_key) == 1:
            query = query.where(predicates[0])
        else:
            query = query.where(text(" AND ".join(f'"{key}" = :value' for key in definition.business_key))).params(value=value)
        exact = (await self.session.execute(query.limit(2))).mappings().all()
        if len(exact) == 1:
            return {"status": "EXACT", "master_id": master.id, "record": self.json_value(dict(exact[0]))}
        label = definition.label_field
        pattern = "%" + value.replace("%", "\\%").replace("_", "\\_") + "%"
        candidates = (await self.session.execute(
            select(table).where(table.c._tenant_id == self.user.tenant_id, table.c[label].ilike(pattern, escape="\\")).limit(6)
        )).mappings().all()
        candidate_items = []
        for row in candidates:
            item = self.json_value(dict(row))
            label_value = str(item.get(label, ""))
            item["match_score"] = round(SequenceMatcher(None, value.casefold(), label_value.casefold()).ratio(), 4)
            candidate_items.append(item)
        candidate_items.sort(key=lambda item: item["match_score"], reverse=True)
        status = "AMBIGUOUS" if len(candidate_items) > 1 else "NOT_FOUND" if not candidate_items else "CANDIDATE"
        return {"status": status, "master_id": master.id, "candidates": candidate_items}

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
                headers = [
                    str(value).strip()
                    for value in snapshot.values[review.dependencies["sheet"]["header_row"] - 1]
                ]
                target_for_source = {column.target_column: column.source_column for column in config.columns}
                outputs = {row_number: output for row_number, output in good}
                staging = {}
                for row_number, raw in enumerate(
                    snapshot.values[review.dependencies["sheet"]["data_start_row"] - 1 :],
                    review.dependencies["sheet"]["data_start_row"],
                ):
                    if not any(value is not None and value != "" for value in raw):
                        continue
                    row = await self.repo.add(
                        ImportReviewRow,
                        import_review_id=review.id,
                        source_row=row_number,
                        raw_data={
                            headers[i]: self.json_value(value)
                            for i, value in enumerate(raw)
                            if i < len(headers)
                        },
                        transformed_data=self.json_value(outputs.get(row_number, {})),
                    )
                    staging[row_number] = row
                findings = [{"source_row": i["source_row"], "errors": i["errors"]} for i in issues]
                findings.extend({"severity": "WARN", **warning} for warning in warnings)
                mandatory_questions = 0
                for issue in issues:
                    for error in issue["errors"]:
                        target = error["column"].split(",", 1)[0] if error.get("column") else None
                        source = target_for_source.get(target)
                        key = digest({"row": issue["source_row"], "target": target, "code": error["code"]})
                        await self.repo.add(
                            ImportQuestion,
                            import_review_id=review.id,
                            staging_row_id=staging[issue["source_row"]].id,
                            source_row=issue["source_row"],
                            source_column=source,
                            target_column=target,
                            question_key=key,
                            category="DUPLICATE_KEY"
                            if error["code"] == "DUPLICATE_BUSINESS_KEY"
                            else "DATA_QUALITY",
                            prompt="Nilai pada baris/kolom ini tidak dapat digunakan tanpa keputusan pengguna.",
                            mandatory=True,
                            allowed_actions=["APPLY_CORRECTION", "CORRECT_SOURCE", "PROPOSE_MASTER"],
                            evidence={
                                "error_code": error["code"],
                                "source_row": issue["source_row"],
                                "source_column": source,
                                "target_column": target,
                            },
                        )
                        mandatory_questions += 1
                for warning in warnings:
                    target = warning.get("column")
                    source = target_for_source.get(target)
                    row_number = warning.get("source_row")
                    await self.repo.add(
                        ImportQuestion,
                        import_review_id=review.id,
                        staging_row_id=staging.get(row_number).id if staging.get(row_number) else None,
                        source_row=row_number,
                        source_column=source,
                        target_column=target,
                        question_key=digest(
                            {
                                "row": row_number,
                                "target": target,
                                "code": warning.get("code"),
                                "warning": True,
                            }
                        ),
                        category="DATA_QUALITY_WARNING",
                        prompt="Periksa peringatan nilai ini; nilai asli dapat dipertahankan bila sah.",
                        mandatory=False,
                        allowed_actions=["KEEP_ORIGINAL", "APPLY_CORRECTION", "CORRECT_SOURCE"],
                        evidence={
                            "error_code": warning.get("code"),
                            "source_row": row_number,
                            "source_column": source,
                            "target_column": target,
                        },
                    )
                for prompt in config.unresolved_questions:
                    await self.repo.add(
                        ImportQuestion,
                        import_review_id=review.id,
                        question_key=digest({"configuration_question": prompt}),
                        category="CONFIGURATION",
                        prompt=prompt,
                        mandatory=True,
                        allowed_actions=["CORRECT_SOURCE"],
                        evidence={"scope": "CONFIGURATION"},
                    )
                    mandatory_questions += 1
                blockers = ["DATA_QUALITY_ISSUES"] if mandatory_questions else []
                if config.unresolved_questions:
                    blockers.append("CONFIGURATION_QUESTIONS_PENDING")
                checkpoint = {
                    "deterministic_complete": True,
                    "rows_valid": len(good),
                    "rows_invalid": len(issues),
                    "warning_count": len(warnings),
                    "blocking_codes": blockers,
                    "open_question_count": mandatory_questions + len(warnings),
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
