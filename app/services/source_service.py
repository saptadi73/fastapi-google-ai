import re
import unicodedata
from datetime import datetime, timezone

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, or_, select, text

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.access import AccessAttribute, AccessPolicy, AccessPolicyBinding, UserAssignment
from app.models.auth import User
from app.models.base import now
from app.models.configuration import Configuration
from app.models.etl import ETLRun, Job, Snapshot
from app.models.master import MasterColumnBinding, MasterSourceBinding
from app.models.semantic import DataProduct
from app.models.source import DataSource, ProfilingRun, SourceDependency, SourceSheet
from app.repositories.base import record
from app.repositories.source_repository import SourceRepository
from app.schemas.import_review import ImportReviewCreate
from app.schemas.source import SourceAccessMetadata, spreadsheet_id
from app.services.audit_service import audit
from app.services.google_sheets_service import GoogleSheetsService
from app.services.import_review_service import ImportReviewService
from app.services.job_service import enqueue
from app.services.profiling_service import digest, profile_values
from app.services.release_approval_service import require_release_ready
from app.services.source_approver_service import require_source_approver


async def source_records(session, sources):
    sources = list(sources)
    if not sources:
        return []
    rows = await session.execute(
        select(SourceDependency.downstream_source_id, SourceDependency.upstream_source_id)
        .where(SourceDependency.downstream_source_id.in_([source.id for source in sources]))
        .order_by(SourceDependency.upstream_source_id)
    )
    dependencies = {}
    for downstream_id, upstream_id in rows:
        dependencies.setdefault(str(downstream_id), []).append(str(upstream_id))
    return [
        {**record(source), "dependency_source_ids": dependencies.get(str(source.id), [])}
        for source in sources
    ]


def dependency_graph_has_cycle(edges):
    graph = {}
    for downstream, upstream in edges:
        graph.setdefault(str(downstream), set()).add(str(upstream))
    visiting, visited = set(), set()

    def visit(node):
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(parent) for parent in graph.get(node, ())):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


def source_code_base(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    code = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    if not code or not code[0].isalpha():
        code = f"source_{code}" if code else "source"
    return code[:63].rstrip("_")


class SourceService:
    def __init__(self, session, user, google=None):
        self.session, self.user = session, user
        self.repo = SourceRepository(session, user.tenant_id)
        self.google = google or GoogleSheetsService()

    async def _validated_access_metadata(self, data, *, subject_id=None):
        metadata = data.model_dump(mode="json")
        scope_ids = {}
        for field, kind in (
            ("owner_unit_id", "DEPARTMENT"),
            ("business_domain_id", "BUSINESS_DOMAIN"),
            ("jurisdiction_id", "JURISDICTION"),
            ("purpose_id", "PURPOSE"),
        ):
            attribute = await self.repo.get(AccessAttribute, metadata[field])
            if not attribute.is_active or attribute.kind != kind:
                raise AppError("SOURCE_ACCESS_SCOPE_INVALID", "Atribut metadata sumber tidak sesuai atau nonaktif.")
            if kind != "PURPOSE":
                scope_ids[field] = attribute.id
        instant = now()
        assigned_ids = set((await self.session.scalars(
            select(UserAssignment.attribute_id).where(
                UserAssignment.tenant_id == self.user.tenant_id,
                UserAssignment.user_id == (subject_id or self.user.id),
                UserAssignment.status == "ACTIVE",
                UserAssignment.valid_from <= instant,
                or_(UserAssignment.valid_to.is_(None), UserAssignment.valid_to > instant),
                UserAssignment.attribute_id.in_(scope_ids.values()),
            )
        )).all())
        if assigned_ids != set(scope_ids.values()):
            raise AppError("SOURCE_SCOPE_NOT_ASSIGNED", "Scope sumber harus menjadi assignment aktif pendaftar.", 403)
        for field in ("data_owner_user_id", "data_steward_user_id"):
            target = await self.repo.get(User, metadata[field])
            if not target.is_active:
                raise AppError("SOURCE_ACCESS_USER_INACTIVE", "Owner atau steward tidak aktif.")
        return metadata

    async def register(self, data):
        if data.credential_ref != get_settings().google_credential_ref:
            raise AppError("UNKNOWN_CREDENTIAL_REF", "credential_ref belum dikonfigurasi pada server.")
        try:
            sid = spreadsheet_id(data.spreadsheet_url)
        except ValueError as exc:
            raise AppError("INVALID_SPREADSHEET_ID", str(exc)) from None
        metadata = await self._validated_access_metadata(data.access_metadata)
        # Serialize all registrations of a Sheet within a tenant. This covers a
        # repeated request after the client lost its first response and stops a
        # different owner from creating a second source for the same Sheet.
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"source-sheet:{self.user.tenant_id}:{sid}"},
        )
        registered = list((await self.session.scalars(
            select(DataSource)
            .where(
                DataSource.tenant_id == self.user.tenant_id,
                DataSource.spreadsheet_id == sid,
                DataSource.unlinked_at.is_(None),
            )
            .order_by(DataSource.created_at, DataSource.id)
        )).all())
        previous = [source for source in registered if source.owner_user_id == self.user.id]
        if registered and not previous:
            raise AppError(
                "SOURCE_ALREADY_REGISTERED",
                "Spreadsheet sudah terdaftar pada tenant ini. Hubungi admin untuk menggunakan sumber yang ada.",
                409,
            )
        if previous:
            canonical = previous[0]
            latest_job = await self.session.scalar(
                select(Job)
                .where(
                    Job.tenant_id == self.user.tenant_id,
                    Job.source_id == canonical.id,
                    Job.kind == "DISCOVER",
                )
                .order_by(Job.created_at.desc(), Job.id.desc())
                .limit(1)
            )
            if latest_job is None:
                job = await enqueue(self.session, self.user, "DISCOVER", canonical.id)
            else:
                job = {
                    "job_id": latest_job.id,
                    "status": latest_job.status,
                    "status_url": f"/api/v1/jobs/{latest_job.id}",
                }
            return {
                "source": record(canonical),
                **job,
                "already_registered": True,
                "duplicate_source_ids": [source.id for source in previous[1:]],
            }
        source_code = data.source_code
        if source_code is None:
            await self.session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                {"key": f"source-code:{self.user.tenant_id}"},
            )
            base = source_code_base(data.name)
            existing = set(
                (
                    await self.session.scalars(
                        select(DataSource.source_code).where(
                            DataSource.tenant_id == self.user.tenant_id,
                            DataSource.source_code.startswith(base, autoescape=True),
                        )
                    )
                ).all()
            )
            source_code = base
            suffix = 2
            while source_code in existing:
                ending = f"_{suffix}"
                source_code = f"{base[: 63 - len(ending)].rstrip('_')}{ending}"
                suffix += 1
        source = await self.repo.add(
            DataSource,
            **data.model_dump(exclude={"spreadsheet_url", "access_metadata", "source_code"}),
            source_code=source_code,
            spreadsheet_id=sid,
            owner_user_id=self.user.id,
            access_metadata=metadata,
            access_metadata_editor_id=self.user.id,
        )
        audit(self.session, self.user, "source.registered", source.id)
        job = await enqueue(self.session, self.user, "DISCOVER", source.id)
        return {"source": record(source), **job, "already_registered": False, "duplicate_source_ids": []}

    async def duplicate_groups(self):
        query = select(DataSource).where(DataSource.tenant_id == self.user.tenant_id)
        if self.user.role != "PLATFORM_ADMIN":
            query = query.where(DataSource.owner_user_id == self.user.id)
        sources = (await self.session.scalars(
            query.order_by(DataSource.spreadsheet_id, DataSource.created_at, DataSource.id)
        )).all()
        grouped = {}
        for source in sources:
            if source.unlinked_at is not None:
                continue
            grouped.setdefault(source.spreadsheet_id, []).append(source)
        return [
            {
                "spreadsheet_id": spreadsheet_id,
                "same_owner": len({source.owner_user_id for source in items}) == 1,
                "suggested_source_id": next((source.id for source in items if source.unlinked_at is None), None)
                if len({source.owner_user_id for source in items}) == 1 else None,
                "sources": [
                    {
                        "id": source.id,
                        "source_code": source.source_code,
                        "name": source.name,
                        "owner_user_id": source.owner_user_id,
                        "status": source.status,
                        "created_at": source.created_at,
                    }
                    for source in items
                ],
            }
            for spreadsheet_id, items in grouped.items()
            if len(items) > 1
        ]

    async def check_registration(self, spreadsheet_url):
        try:
            sid = spreadsheet_id(spreadsheet_url)
        except ValueError as exc:
            raise AppError("INVALID_SPREADSHEET_ID", str(exc)) from None
        existing = (await self.session.scalars(
            select(DataSource).where(
                DataSource.tenant_id == self.user.tenant_id,
                DataSource.spreadsheet_id == sid,
                DataSource.unlinked_at.is_(None),
            ).order_by(DataSource.created_at, DataSource.id)
        )).all()
        own = next((item for item in existing if item.owner_user_id == self.user.id), None)
        return {
            "registered": bool(existing),
            "owned_by_me": own is not None,
            "source_id": own.id if own else None,
            "source_name": own.name if own else None,
        }

    async def unlink_duplicate(self, source_id, data):
        # Share the registration lock so a concurrent registration cannot pick a source
        # while it is being unlinked. The source remains in the database for audit.
        source = await self.repo.get(DataSource, source_id)
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"source-sheet:{self.user.tenant_id}:{source.spreadsheet_id}"},
        )
        source = await self.repo.get(DataSource, source_id, lock=True)
        canonical = await self.repo.get(DataSource, data.canonical_source_id, lock=True)
        if source.unlinked_at is not None:
            raise AppError("SOURCE_ALREADY_UNLINKED", "Sumber sudah di-unlink.", 409)
        if (source.id == canonical.id or source.spreadsheet_id != canonical.spreadsheet_id
                or canonical.unlinked_at is not None):
            raise AppError("SOURCE_CANONICAL_INVALID", "Pilih sumber utama aktif dari Spreadsheet yang sama.", 409)
        if source.status == "ACTIVE" or source.access_status == "POLICY_APPROVED":
            raise AppError("SOURCE_UNLINK_IN_USE", "Sumber aktif atau policy akses sudah berlaku. Tinjau pemakaian sebelum unlink.", 409)
        sheet_ids = select(SourceSheet.id).where(
            SourceSheet.tenant_id == self.user.tenant_id, SourceSheet.source_id == source.id
        )
        checks = (
            ("konfigurasi", select(Configuration.id).where(Configuration.source_id == source.id)),
            ("hasil ETL", select(ETLRun.id).where(ETLRun.source_id == source.id)),
            ("data product", select(DataProduct.id).where(DataProduct.source_sheet_id.in_(sheet_ids))),
            ("binding master", select(MasterSourceBinding.id).where(MasterSourceBinding.source_sheet_id.in_(sheet_ids))),
            ("binding kolom master", select(MasterColumnBinding.id).where(MasterColumnBinding.source_sheet_id.in_(sheet_ids))),
            ("dependensi sumber", select(SourceDependency.id).where(or_(
                SourceDependency.downstream_source_id == source.id,
                SourceDependency.upstream_source_id == source.id,
            ))),
            ("job berjalan", select(Job.id).where(Job.source_id == source.id, Job.status.in_(["QUEUED", "RUNNING"]))),
        )
        for label, query in checks:
            if await self.session.scalar(query.limit(1)):
                raise AppError("SOURCE_UNLINK_IN_USE", f"Sumber masih memiliki {label}. Tinjau dahulu sebelum unlink.", 409)
        source.paused_before_unlink = source.paused
        source.paused = True
        source.unlinked_at = now()
        source.unlinked_by = self.user.id
        source.unlinked_to_source_id = canonical.id
        source.unlink_reason = data.reason.strip()
        audit(self.session, self.user, "source.unlinked", source.id,
              canonical_source_id=canonical.id, reason=source.unlink_reason)
        return record(source)

    async def restore_unlinked(self, source_id):
        source = await self.repo.get(DataSource, source_id, lock=True)
        if source.unlinked_at is None:
            raise AppError("SOURCE_NOT_UNLINKED", "Sumber belum di-unlink.", 409)
        source.paused = source.paused_before_unlink if source.paused_before_unlink is not None else True
        source.paused_before_unlink = None
        source.unlinked_at = None
        source.unlinked_by = None
        source.unlinked_to_source_id = None
        source.unlink_reason = None
        audit(self.session, self.user, "source.unlink_restored", source.id)
        return record(source)

    async def update_access_metadata(self, source_id, data):
        source = await self.session.scalar(
            self.repo.query(DataSource)
            .where(DataSource.id == str(source_id))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if source is None:
            raise AppError("RESOURCE_NOT_FOUND", "Data tidak ditemukan.", 404)
        if source.access_revision != data.revision_no:
            raise AppError("SOURCE_ACCESS_REVISION_CONFLICT", "Metadata akses berubah; muat ulang sumber.", 409)
        metadata = await self._validated_access_metadata(data.access_metadata)
        if (source.access_metadata == metadata and source.access_status == "ACCESS_POLICY_REQUIRED"
            and source.access_review_status != "REJECTED" and source.access_metadata_editor_id):
            return record(source)
        previous_status = source.access_status
        changed_fields = [
            field for field, value in metadata.items()
            if (source.access_metadata or {}).get(field) != value
        ]
        source.access_metadata = metadata
        source.access_metadata_editor_id = self.user.id
        source.access_status = "ACCESS_POLICY_REQUIRED"
        source.access_review_status = "PENDING"
        source.access_reviewed_by = None
        source.access_reviewed_at = None
        source.access_review_reason = ""
        source.access_revision += 1
        audit(
            self.session, self.user, "source.access_metadata_updated", source.id,
            revision_no=source.access_revision,
            changed_fields=changed_fields,
            previous_status=previous_status,
        )
        return record(source)

    async def review_access_metadata(self, source_id, data):
        source = await self.session.scalar(
            self.repo.query(DataSource)
            .where(DataSource.id == str(source_id))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if source is None:
            raise AppError("RESOURCE_NOT_FOUND", "Data tidak ditemukan.", 404)
        await require_source_approver(self.session, self.user, source.id, "metadata_review")
        if source.access_revision != data.revision_no:
            raise AppError("SOURCE_ACCESS_REVISION_CONFLICT", "Metadata akses berubah; muat ulang sumber.", 409)
        if source.access_review_status != "PENDING":
            raise AppError("SOURCE_METADATA_ALREADY_REVIEWED", "Metadata sudah diputuskan; muat ulang sumber.", 409)
        if not source.access_metadata or not source.access_metadata_editor_id:
            raise AppError("SOURCE_METADATA_INCOMPLETE", "Metadata perlu diisi ulang oleh editor.", 409)
        if source.access_metadata_editor_id == self.user.id:
            raise AppError("SOURCE_METADATA_SELF_REVIEW", "Editor metadata tidak boleh menjadi reviewer.", 403)
        if data.decision == "APPROVE":
            editor = await self.repo.get(User, source.access_metadata_editor_id)
            if not editor.is_active:
                raise AppError("SOURCE_METADATA_EDITOR_INACTIVE", "Editor metadata tidak lagi aktif.", 409)
            await self._validated_access_metadata(
                SourceAccessMetadata.model_validate(source.access_metadata), subject_id=editor.id
            )
        source.access_review_status = "APPROVED" if data.decision == "APPROVE" else "REJECTED"
        source.access_reviewed_by = self.user.id
        source.access_reviewed_at = now()
        source.access_review_reason = data.reason
        source.access_status = "ACCESS_POLICY_REQUIRED"
        source.access_revision += 1
        audit(
            self.session, self.user, "source.access_metadata_reviewed", source.id,
            revision_no=source.access_revision,
            decision=data.decision,
            reason_code=data.reason,
        )
        return record(source)

    async def metadata_review_context(self, source_id):
        source = await self.repo.get(DataSource, source_id)
        await require_source_approver(self.session, self.user, source.id, "metadata_review")
        metadata = source.access_metadata or {}
        attribute_fields = ("owner_unit_id", "business_domain_id", "jurisdiction_id", "purpose_id")
        user_fields = ("data_owner_user_id", "data_steward_user_id")
        attribute_ids = [metadata[field] for field in attribute_fields if metadata.get(field)]
        user_ids = [metadata[field] for field in user_fields if metadata.get(field)]
        attributes = {}
        people = {}
        if attribute_ids:
            attributes = {
                item.id: item for item in (await self.session.scalars(
                    self.repo.query(AccessAttribute).where(AccessAttribute.id.in_(attribute_ids))
                )).all()
            }
        if user_ids:
            people = {
                item.id: item for item in (await self.session.scalars(
                    self.repo.query(User).where(User.id.in_(user_ids))
                )).all()
            }
        return {
            "source_id": source.id,
            "can_decide": source.approval_assignees is None or self.user.id in source.approval_assignees.get("metadata_review", []),
            "source_code": source.source_code,
            "access_revision": source.access_revision,
            "access_status": source.access_status,
            "review_status": source.access_review_status,
            "attributes": {
                field: (
                    {"code": attributes[metadata[field]].code, "label": attributes[metadata[field]].label,
                     "is_active": attributes[metadata[field]].is_active}
                    if metadata.get(field) in attributes else None
                ) for field in attribute_fields
            },
            "people": {
                field: (
                    {"username": people[metadata[field]].username, "is_active": people[metadata[field]].is_active}
                    if metadata.get(field) in people else None
                ) for field in user_fields
            },
            "sensitivity": metadata.get("sensitivity"),
        }

    async def activate_source_access(self, source_id, data):
        source = await self.repo.get(DataSource, source_id, lock=True)
        if source.release_policy is not None:
            active_configs = (await self.session.scalars(
                self.repo.query(Configuration).where(
                    Configuration.source_id == source.id, Configuration.status == "ACTIVE"
                )
            )).all()
            for config in active_configs:
                require_release_ready(config, source)
        if source.access_revision != data.revision_no:
            raise AppError("SOURCE_ACCESS_REVISION_CONFLICT", "Metadata akses berubah; muat ulang sumber.", 409)
        if not source.access_metadata or source.access_review_status != "APPROVED":
            raise AppError("SOURCE_METADATA_REVIEW_REQUIRED", "Metadata sumber harus direview terlebih dahulu.", 409)
        if source.access_metadata_editor_id == self.user.id:
            raise AppError("SOURCE_ACCESS_APPROVER_CONFLICT", "Editor metadata tidak boleh mengaktifkan akses.", 403)
        editor = await self.repo.get(User, source.access_metadata_editor_id)
        if not editor.is_active:
            raise AppError("SOURCE_METADATA_EDITOR_INACTIVE", "Editor metadata tidak lagi aktif.", 409)
        await self._validated_access_metadata(
            SourceAccessMetadata.model_validate(source.access_metadata), subject_id=editor.id
        )
        policy = await self.repo.get(AccessPolicy, data.policy_id, lock=True)
        instant = now()
        binding = await self.session.scalar(
            self.repo.query(AccessPolicyBinding).where(
                AccessPolicyBinding.policy_id == policy.id,
                AccessPolicyBinding.resource_type == "SOURCE",
                AccessPolicyBinding.resource_id == source.source_code,
            )
        )
        if (binding is None or policy.status != "APPROVED" or policy.effect != "ALLOW"
                or policy.valid_from > instant or (policy.valid_to and policy.valid_to <= instant)
                or not {"DISCOVER", "QUERY"}.issubset(policy.actions)):
            raise AppError("SOURCE_ACCESS_POLICY_REQUIRED", "Policy SOURCE ALLOW belum approved atau tidak berlaku.", 409)
        scope_ids = {
            source.access_metadata[field]
            for field in ("owner_unit_id", "business_domain_id", "jurisdiction_id")
        }
        if not scope_ids.issubset(policy.required_attribute_ids):
            raise AppError("SOURCE_POLICY_SCOPE_REQUIRED", "Policy wajib memuat unit, domain, dan yurisdiksi sumber.", 422)
        if policy.row_scope or policy.column_rules:
            raise AppError("SOURCE_POLICY_CONTROLS_UNSUPPORTED", "Aturan baris/kolom belum didukung untuk aktivasi.", 422)
        if source.access_status == "POLICY_APPROVED":
            return record(source)
        source.access_status = "POLICY_APPROVED"
        source.access_revision += 1
        audit(
            self.session, self.user, "source.access_activated", source.id,
            revision_no=source.access_revision, policy_id=policy.id,
        )
        return record(source)

    async def source_policy_options(self, source_id):
        source = await self.repo.get(DataSource, source_id)
        instant = now()
        scope_ids = {
            source.access_metadata[field]
            for field in ("owner_unit_id", "business_domain_id", "jurisdiction_id")
        } if source.access_metadata else set()
        policies = (await self.session.scalars(
            self.repo.query(AccessPolicy)
            .join(AccessPolicyBinding, AccessPolicyBinding.policy_id == AccessPolicy.id)
            .where(
                AccessPolicyBinding.tenant_id == self.user.tenant_id,
                AccessPolicyBinding.resource_type == "SOURCE",
                AccessPolicyBinding.resource_id == source.source_code,
                AccessPolicy.status == "APPROVED",
                AccessPolicy.effect == "ALLOW",
                AccessPolicy.valid_from <= instant,
                or_(AccessPolicy.valid_to.is_(None), AccessPolicy.valid_to > instant),
                AccessPolicy.actions.contains(["DISCOVER", "QUERY"]),
                AccessPolicy.row_scope == {},
                AccessPolicy.column_rules == {},
            )
            .order_by(AccessPolicy.code)
            .limit(100)
        )).all()
        return [
            {"id": policy.id, "code": policy.code, "label": policy.label,
             "actions": policy.actions, "export_allowed": policy.export_allowed}
            for policy in policies
            if scope_ids.issubset(policy.required_attribute_ids)
        ]

    async def discover(self, source_id):
        source = await self.repo.get(DataSource, source_id)
        metadata = await self.google.metadata(source.spreadsheet_id)
        existing = {s.sheet_id: s for s in await self.repo.sheets(source.id)}
        discovered = []
        for tab in metadata.get("sheets", []):
            props = tab["properties"]
            if props.get("sheetType", "GRID") != "GRID":
                continue
            if props["sheetId"] not in existing:
                sheet = await self.repo.add(
                    SourceSheet, source_id=source.id, sheet_id=props["sheetId"], sheet_name=props["title"]
                )
            else:
                sheet = existing[props["sheetId"]]
                sheet.sheet_name = props["title"]
            discovered.append({"id": sheet.id, "sheet_id": sheet.sheet_id, "sheet_name": sheet.sheet_name})
        audit(self.session, self.user, "source.discovered", source.id, sheet_count=len(discovered))
        if not discovered:
            source.status = "PROFILE_FAILED"
            raise AppError("SOURCE_NOT_FOUND", "Belum ada tab aktif; Google Sheet tidak memiliki tab GRID.", 404)
        # Keep discovered tabs even when profiling rejects a header. A savepoint
        # prevents profile snapshots/runs from being persisted while preserving
        # the SourceSheet rows so the user can fix the tab and retry profiling.
        try:
            async with self.session.begin_nested():
                return await self.profile(source.id)
        except AppError as exc:
            source.status = "PROFILE_FAILED"
            return {
                "sheets": discovered,
                "profile_required": True,
                "profile_error": {"code": exc.code, "message": exc.message},
            }

    async def profile(self, source_id):
        source = await self.repo.get(DataSource, source_id)
        sheets = [s for s in await self.repo.sheets(source.id) if s.enabled]
        if not sheets:
            raise AppError("SOURCE_NOT_FOUND", "Belum ada tab aktif; jalankan discovery.", 404)
        results = []
        batches = await self.google.read_sheets(source.spreadsheet_id, sheets)
        drift = False
        for sheet, values in zip(sheets, batches):
            profile = profile_values(
                values,
                sheet.sheet_name,
                sheet.header_row,
                sheet.data_start_row,
                sheet.range_a1,
                get_settings().etl_sample_row_limit,
            )
            snapshot = await self.repo.add(
                Snapshot,
                source_id=source.id,
                source_sheet_id=sheet.id,
                content_hash=digest(values),
                row_count=profile["row_count"],
                values=values,
            )
            run = await self.repo.add(
                ProfilingRun,
                source_id=source.id,
                source_sheet_id=sheet.id,
                fingerprint=profile["fingerprint"],
                profile_json=profile,
            )
            drift = drift or bool(sheet.last_fingerprint and sheet.last_fingerprint != profile["fingerprint"])
            sheet.last_fingerprint = profile["fingerprint"]
            results.append(
                {"profiling_run_id": run.id, "source_sheet_id": sheet.id, "snapshot_id": snapshot.id}
            )
        source.status = (
            "CHANGE_DETECTED"
            if drift
            else ("ACTIVE" if all(s.active_configuration_id for s in sheets) else "NEEDS_REVIEW")
        )
        audit(self.session, self.user, "source.profiled", source.id, drift=drift)
        return {"profiles": results, "schema_drift": drift}

    async def sync_review(self, source_id):
        await self.profile(source_id)
        sheets = await self.repo.sheets(source_id)
        reviews = []
        for sheet in sheets:
            config_id = sheet.active_configuration_id if sheet.dataset_kind != "MASTER" else None
            try:
                result = await ImportReviewService(self.session, self.user).create(
                    ImportReviewCreate(source_sheet_id=sheet.id, configuration_id=config_id)
                )
                reviews.append(jsonable_encoder(result))
            except AppError as exc:
                reviews.append({"source_sheet_id": sheet.id, "status": "BLOCKED", "code": exc.code})
        return {"source_id": str(source_id), "reviews": reviews}

    async def update_sheet(self, sheet_id, data):
        sheet = await self.repo.get(SourceSheet, sheet_id, lock=True)
        if sheet.active_configuration_id:
            raise AppError(
                "CONFIGURATION_CONFLICT", "Range/header tab aktif tidak dapat diubah langsung.", 409
            )
        for name, value in data.model_dump(exclude_none=True).items():
            setattr(sheet, name, value)
        if sheet.data_start_row <= sheet.header_row:
            raise AppError("INVALID_RANGE", "data_start_row harus setelah header_row.")
        sheet.last_fingerprint = None
        audit(self.session, self.user, "sheet.updated", sheet.id)
        return record(sheet)

    async def update_watermark(self, sheet_id, data):
        sheet = await self.repo.get(SourceSheet, sheet_id, lock=True)
        if sheet.watermark_revision != data.revision_no:
            raise AppError("WATERMARK_REVISION_CONFLICT", "Watermark tab telah berubah; muat ulang.", 409)
        if data.source_column:
            profile = await self.repo.latest_profile(sheet.id)
            columns = {
                item["source_column"] for item in (profile.profile_json.get("columns", []) if profile else [])
            }
            if data.source_column not in columns:
                raise AppError("WATERMARK_COLUMN_INVALID", "Pilih kolom dari profil tab terbaru.")
            if sheet.active_configuration_id:
                config = await self.repo.get(Configuration, sheet.active_configuration_id)
                if config.configuration_json.get("load_strategy") == "FULL_REFRESH":
                    raise AppError(
                        "WATERMARK_STRATEGY_INVALID",
                        "Incremental watermark tidak didukung untuk FULL_REFRESH.",
                    )
        changed = (
            sheet.watermark_source_column != data.source_column
            or sheet.watermark_kind != data.kind
        )
        sheet.watermark_source_column = data.source_column
        sheet.watermark_kind = data.kind
        if changed or data.source_column is None:
            sheet.watermark_value = None
            sheet.watermark_updated_at = None
        sheet.watermark_revision += 1
        audit(
            self.session,
            self.user,
            "sheet.watermark_updated",
            sheet.id,
            revision_no=sheet.watermark_revision,
            source_column=sheet.watermark_source_column,
            kind=sheet.watermark_kind,
            reset=changed,
        )
        return record(sheet)

    async def update_schedule(self, source_id, data):
        source = await self.repo.get(DataSource, source_id, lock=True)
        if source.schedule_revision != data.revision_no:
            raise AppError("SOURCE_SCHEDULE_CONFLICT", "Jadwal sumber telah berubah; muat ulang.", 409)
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": "source-dependency:" + self.user.tenant_id},
        )
        dependency_ids = [str(item) for item in data.dependency_source_ids]
        if str(source.id) in dependency_ids:
            raise AppError("SOURCE_DEPENDENCY_INVALID", "Source tidak dapat bergantung pada dirinya sendiri.")
        for dependency_id in dependency_ids:
            await self.repo.get(DataSource, dependency_id)
        existing_edges = list(
            (
                await self.session.execute(
                    select(
                        SourceDependency.downstream_source_id,
                        SourceDependency.upstream_source_id,
                    ).where(SourceDependency.tenant_id == self.user.tenant_id)
                )
            ).all()
        )
        candidate_edges = [
            (str(downstream), str(upstream))
            for downstream, upstream in existing_edges
            if str(downstream) != str(source.id)
        ] + [(str(source.id), dependency_id) for dependency_id in dependency_ids]
        if dependency_graph_has_cycle(candidate_edges):
            raise AppError("SOURCE_DEPENDENCY_CYCLE", "Dependency source membentuk siklus.", 409)
        await self.session.execute(
            delete(SourceDependency).where(
                SourceDependency.tenant_id == self.user.tenant_id,
                SourceDependency.downstream_source_id == source.id,
            )
        )
        for dependency_id in dependency_ids:
            self.session.add(
                SourceDependency(
                    tenant_id=self.user.tenant_id,
                    downstream_source_id=source.id,
                    upstream_source_id=dependency_id,
                )
            )
        source.sync_schedule = data.sync_schedule
        source.schedule_timezone = data.schedule_timezone
        source.concurrency_policy = data.concurrency_policy
        source.schedule_revision += 1
        source.last_scheduled_at = datetime.now(timezone.utc) if data.sync_schedule else None
        audit(
            self.session,
            self.user,
            "source.schedule_updated",
            source.id,
            revision_no=source.schedule_revision,
            sync_schedule=source.sync_schedule,
            schedule_timezone=source.schedule_timezone,
            concurrency_policy=source.concurrency_policy,
            dependency_source_ids=dependency_ids,
        )
        return {**record(source), "dependency_source_ids": dependency_ids}
