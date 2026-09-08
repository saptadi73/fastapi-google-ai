from difflib import SequenceMatcher
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import Text, cast, or_, text

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.domain.enums import EDIT_ROLES, REVIEW_ROLES
from app.models.base import now
from app.models.master import MasterColumnBinding, MasterDefinition, MasterSourceBinding
from app.models.configuration import Configuration
from app.models.source import SourceSheet
from app.repositories.base import TenantRepository, record
from app.repositories.source_repository import SourceRepository
from app.schemas.configuration import ETLConfiguration
from app.schemas.master import MasterSchema
from app.services.audit_service import audit
from app.services.classification_service import ClassificationService
from app.services.configuration_service import ConfigurationService


class MasterService:
    def __init__(self, session, user):
        self.session, self.user = session, user
        self.repo = TenantRepository(session, user.tenant_id)

    def require_role(self, roles):
        if self.user.role not in roles:
            raise AppError("FORBIDDEN", "Peran tidak diizinkan mengubah master.", 403)

    async def lock_master(self, master_id):
        result = await self.session.scalar(
            self.repo.query(MasterDefinition)
            .where(MasterDefinition.id == str(master_id))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if result is None:
            raise AppError("RESOURCE_NOT_FOUND", "Master tidak ditemukan.", 404)
        return result

    async def registry_lock(self):
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": "master-registry:" + self.user.tenant_id},
        )

    async def list(self, search="", offset=0, limit=50):
        query = self.repo.query(MasterDefinition)
        if search:
            pattern = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            query = query.where(
                or_(
                    MasterDefinition.code.ilike(pattern, escape="\\"),
                    MasterDefinition.name.ilike(pattern, escape="\\"),
                    cast(MasterDefinition.aliases, Text).ilike(pattern, escape="\\"),
                    MasterDefinition.approved_definition_json["name"].astext.ilike(pattern, escape="\\"),
                    cast(MasterDefinition.approved_definition_json["aliases"], Text).ilike(
                        pattern, escape="\\"
                    ),
                )
            )
        rows = (
            await self.session.scalars(
                query.order_by(MasterDefinition.code, MasterDefinition.id).offset(offset).limit(limit)
            )
        ).all()
        return [record(row) for row in rows]

    async def candidates(self, definition, *, exclude_id=None):
        query = self.repo.query(MasterDefinition)
        if exclude_id:
            query = query.where(MasterDefinition.id != str(exclude_id))
        labels = [definition.name.casefold(), *(a.casefold() for a in definition.aliases)]
        candidates = []
        # Includes inactive/draft masters; they must not silently be recreated under another code.
        for existing in (await self.session.scalars(query.order_by(MasterDefinition.code))).all():
            approved = existing.approved_definition_json or {}
            existing_labels = [
                existing.name.casefold(),
                existing.code.casefold(),
                *(a.casefold() for a in existing.aliases),
                str(approved.get("name", existing.name)).casefold(),
                *(a.casefold() for a in approved.get("aliases", [])),
            ]
            score = max(
                SequenceMatcher(None, left, right).ratio() for left in labels for right in existing_labels
            )
            if score >= 0.82:
                candidates.append(
                    {
                        "id": existing.id,
                        "code": existing.code,
                        "name": existing.name,
                        "status": existing.status,
                        "is_active": existing.is_active,
                        "score": round(score, 3),
                        "reason": "Nama/alias mirip; periksa apakah master yang sama.",
                    }
                )
        return sorted(candidates, key=lambda c: (-c["score"], c["code"]))

    async def check_candidates(self, data, *, exclude_id=None):
        candidates = await self.candidates(data.definition, exclude_id=exclude_id)
        actual_ids = {c["id"] for c in candidates}
        reviewed = {str(value) for value in data.reviewed_candidate_ids}
        if not reviewed.issubset(actual_ids):
            raise AppError(
                "MASTER_CANDIDATES_CHANGED", "Daftar kandidat berubah; jalankan preview ulang.", 409
            )
        if actual_ids - reviewed or (actual_ids and not data.duplicate_review_reason.strip()):
            raise AppError(
                "MASTER_DUPLICATE_REVIEW_REQUIRED",
                "Ada kandidat master serupa. Jalankan preview, pilih master lama atau tinjau semua kandidat dan isi alasan membuat definisi berbeda.",
                409,
            )

    async def check_authority(self, definition):
        if source_id := definition.policy.authoritative_source_sheet_id:
            sheet = await ClassificationService(self.session, self.user).locked_sheet(source_id)
            if sheet.classification_status != "CONFIRMED" or sheet.dataset_kind != "MASTER":
                raise AppError(
                    "MASTER_AUTHORITY_INVALID",
                    "Sumber otoritatif harus tab MASTER yang sudah dikonfirmasi dalam tenant ini.",
                    409,
                )

    async def create(self, data):
        self.require_role(EDIT_ROLES)
        await self.registry_lock()
        await self.check_candidates(data)
        await self.check_authority(data.definition)
        master = await self.repo.add(
            MasterDefinition,
            code=data.code,
            name=data.definition.name,
            aliases=data.definition.aliases,
            definition_json=data.definition.model_dump(mode="json"),
            created_by=self.user.id,
        )
        audit(
            self.session,
            self.user,
            "master.created",
            master.id,
            code=master.code,
            reviewed_candidates=[str(v) for v in data.reviewed_candidate_ids],
            reason=data.duplicate_review_reason,
        )
        return master

    @staticmethod
    def check_revision(master, revision):
        if master.revision_no != revision:
            raise AppError("MASTER_REVISION_CONFLICT", "Revisi master berubah; muat ulang.", 409)

    async def patch(self, master_id, data):
        self.require_role(EDIT_ROLES)
        await self.registry_lock()
        master = await self.lock_master(master_id)
        self.check_revision(master, data.revision_no)
        await self.check_candidates(data, exclude_id=master.id)
        await self.check_authority(data.definition)
        before = master.definition_json
        master.definition_json = data.definition.model_dump(mode="json")
        master.name, master.aliases = data.definition.name, data.definition.aliases
        master.status, master.submitted_by = "DRAFT", None
        master.created_by = self.user.id
        master.revision_no += 1
        audit(
            self.session,
            self.user,
            "master.updated",
            master.id,
            before=before,
            after=master.definition_json,
            reviewed_candidates=[str(v) for v in data.reviewed_candidate_ids],
            reason=data.duplicate_review_reason,
        )
        return master

    async def action(self, master_id, data, action):
        self.require_role(EDIT_ROLES if action == "submit-review" else REVIEW_ROLES)
        master = await self.lock_master(master_id)
        self.check_revision(master, data.revision_no)
        if action == "submit-review":
            if master.status not in ("DRAFT", "REJECTED"):
                raise AppError("MASTER_STATE_CONFLICT", "Master tidak berada pada draft.", 409)
            await self.check_authority(MasterSchema.model_validate(master.definition_json))
            master.status, master.submitted_by = "NEEDS_REVIEW", self.user.id
        elif action in ("approve", "reject"):
            if master.status != "NEEDS_REVIEW":
                raise AppError("MASTER_STATE_CONFLICT", "Ajukan master untuk review terlebih dahulu.", 409)
            if action == "approve":
                if get_settings().require_separate_approver and self.user.id in (
                    master.created_by,
                    master.submitted_by,
                ):
                    raise AppError(
                        "SEPARATE_APPROVER_REQUIRED",
                        "Approver harus berbeda dari editor/pengaju master.",
                        403,
                    )
                parsed = MasterSchema.model_validate(master.definition_json)
                if master.approved_definition_json:
                    from app.services.schema_compiler_service import validate_master_evolution

                    validate_master_evolution(
                        MasterSchema.model_validate(master.approved_definition_json), parsed
                    )
                await self.check_authority(parsed)
                audit(
                    self.session,
                    self.user,
                    "master.version_approved",
                    master.id,
                    previous_version=master.approved_version,
                    previous=master.approved_definition_json,
                    approved=parsed.model_dump(mode="json"),
                )
                master.approved_definition_json = parsed.model_dump(mode="json")
                master.approved_version += 1
                master.approved_by, master.approved_at = self.user.id, now()
                master.is_active, master.status = True, "APPROVED"
            else:
                master.status = "REJECTED"
        elif action == "deactivate":
            if not master.is_active:
                raise AppError("MASTER_STATE_CONFLICT", "Master sudah nonaktif.", 409)
            master.is_active, master.status = False, "INACTIVE"
        else:
            raise AppError("MASTER_ACTION_INVALID", "Aksi master tidak dikenal.")
        master.revision_no += 1
        audit(
            self.session,
            self.user,
            "master." + action,
            master.id,
            comment=data.comment,
            revision=master.revision_no,
        )
        return master

    async def binding(self, sheet_id, *, lock=False):
        await self.repo.get(SourceSheet, sheet_id)
        query = self.repo.query(MasterSourceBinding).where(
            MasterSourceBinding.source_sheet_id == str(sheet_id)
        )
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(query)

    async def binding_validation(
        self, master, sheet, columns, master_version, classification_revision, fingerprint
    ):
        if (
            not master.is_active
            or not master.approved_definition_json
            or master.approved_version != master_version
        ):
            raise AppError(
                "MASTER_VERSION_UNAVAILABLE", "Master harus aktif dan versi approved harus sesuai.", 409
            )
        if (
            sheet.dataset_kind != "MASTER"
            or sheet.classification_status != "CONFIRMED"
            or sheet.classification_revision != classification_revision
        ):
            raise AppError(
                "CLASSIFICATION_CONFLICT", "Binding memerlukan revision klasifikasi MASTER yang sesuai.", 409
            )
        definition = MasterSchema.model_validate(master.approved_definition_json)
        fields = {f.name: f for f in definition.fields}
        targets = {c.target_column for c in columns}
        required = (
            set(definition.business_key)
            | {definition.label_field}
            | {f.name for f in definition.fields if not f.nullable}
        )
        if not required.issubset(targets) or not targets.issubset(fields):
            raise AppError(
                "MASTER_MAPPING_INVALID",
                "Mapping harus mencakup key, label, dan field wajib master tanpa field asing.",
            )
        for column in columns:
            field = fields[column.target_column]
            if (
                column.target_type != field.type
                or column.nullable != field.nullable
                or column.pii_classification != field.pii_classification
                or column.is_primary_key
                or column.is_business_key != (column.target_column in definition.business_key)
            ):
                raise AppError(
                    "MASTER_MAPPING_INVALID",
                    "Tipe, nullable, sensitivitas, dan business key mapping harus sesuai schema master; primary key record dikelola server.",
                )
        configuration = ETLConfiguration(
            dataset_business_name=definition.name,
            grain="Satu record master per business key",
            target_table="master_preview",
            load_strategy="UPSERT",
            columns=columns,
            semantic={"code": "MASTER_PREVIEW", "dimensions": [], "metrics": []},
        )
        return await ConfigurationService(self.session, self.user).validate(
            SimpleNamespace(
                configuration_json=configuration.model_dump(mode="json"),
                source_sheet_id=sheet.id,
                based_on_fingerprint=fingerprint,
            )
        )

    async def save_binding(self, sheet_id, data):
        self.require_role(EDIT_ROLES)
        # Consistent lock order: master -> sheet -> binding. Classification only locks the sheet.
        master = await self.lock_master(data.master_definition_id)
        sheet = await ClassificationService(self.session, self.user).locked_sheet(sheet_id)
        binding = await self.binding(sheet_id, lock=True)
        if data.revision_no != (binding.revision_no if binding else 0):
            raise AppError("MASTER_BINDING_CONFLICT", "Revisi binding berubah; muat ulang.", 409)
        profile = await SourceRepository(self.session, self.user.tenant_id).latest_profile(sheet.id)
        if profile is None:
            raise AppError("PROFILE_REQUIRED", "Profiling diperlukan sebelum binding.", 409)
        validation = await self.binding_validation(
            master,
            sheet,
            data.columns,
            data.master_version,
            data.classification_revision,
            profile.fingerprint,
        )
        attributes = dict(
            master_definition_id=master.id,
            master_version=data.master_version,
            classification_revision=data.classification_revision,
            columns_json=[c.model_dump(mode="json") for c in data.columns],
            fingerprint=profile.fingerprint,
            snapshot_hash=validation["snapshot_hash"],
            status="DRAFT",
            created_by=self.user.id,
            approved_by=None,
            approved_at=None,
        )
        if binding:
            before = record(binding)
            for name, value in attributes.items():
                setattr(binding, name, value)
            binding.revision_no += 1
            # Metadata fields with datetimes are excluded from the JSON audit snapshot.
            before = {k: v for k, v in before.items() if k not in ("created_at", "approved_at")}
        else:
            before = None
            binding = await self.repo.add(MasterSourceBinding, source_sheet_id=sheet.id, **attributes)
        audit(
            self.session,
            self.user,
            "master.binding_saved",
            binding.id,
            before=before,
            master_id=master.id,
            columns=attributes["columns_json"],
            revision=binding.revision_no,
        )
        return {"binding": record(binding), "validation": validation, "execution_ready": False}

    async def binding_decision(self, sheet_id, data, approve):
        self.require_role(REVIEW_ROLES)
        initial = await self.binding(sheet_id)
        if initial is None:
            raise AppError("RESOURCE_NOT_FOUND", "Binding belum tersedia.", 404)
        master = await self.lock_master(initial.master_definition_id)
        sheet = await ClassificationService(self.session, self.user).locked_sheet(sheet_id)
        binding = await self.binding(sheet_id, lock=True)
        if (
            binding.master_definition_id != master.id
            or binding.revision_no != data.revision_no
            or binding.status != "DRAFT"
        ):
            raise AppError("MASTER_BINDING_CONFLICT", "Binding berubah atau tidak dalam draft.", 409)
        if approve:
            if get_settings().require_separate_approver and binding.created_by == self.user.id:
                raise AppError(
                    "SEPARATE_APPROVER_REQUIRED", "Approver harus berbeda dari editor binding.", 403
                )
            from app.schemas.configuration import ColumnMapping

            result = await self.binding_validation(
                master,
                sheet,
                [ColumnMapping(**c) for c in binding.columns_json],
                binding.master_version,
                binding.classification_revision,
                binding.fingerprint,
            )
            if result["snapshot_hash"] != binding.snapshot_hash:
                raise AppError(
                    "MASTER_BINDING_STALE", "Snapshot berubah; simpan dan review binding ulang.", 409
                )
            if not result["valid"]:
                raise AppError("MASTER_BINDING_INVALID", "Perbaiki error dry-run binding sebelum approval.")
            binding.approved_by, binding.approved_at = self.user.id, now()
        binding.status = "APPROVED" if approve else "REJECTED"
        binding.revision_no += 1
        audit(
            self.session,
            self.user,
            "master.binding_decided",
            binding.id,
            status=binding.status,
            revision=binding.revision_no,
            comment=data.comment,
        )
        return binding

    async def binding_detail(self, sheet_id):
        binding = await self.binding(sheet_id)
        if binding is None:
            return {
                "binding": None,
                "metadata_ready": False,
                "execution_ready": False,
                "blocking_reason": "MASTER_BINDING_REQUIRED",
            }
        master = await self.repo.get(MasterDefinition, binding.master_definition_id)
        sheet = await self.repo.get(SourceSheet, sheet_id)
        from app.schemas.configuration import ColumnMapping

        try:
            validation = await self.binding_validation(
                master,
                sheet,
                [ColumnMapping(**c) for c in binding.columns_json],
                binding.master_version,
                binding.classification_revision,
                binding.fingerprint,
            )
            ready = (
                binding.status == "APPROVED"
                and validation["valid"]
                and validation["snapshot_hash"] == binding.snapshot_hash
            )
            reason = "MASTER_RUNTIME_PENDING" if ready else "MASTER_BINDING_REVIEW_REQUIRED"
        except AppError as exc:
            ready, reason = False, exc.code
            validation = {"valid": False, "errors": [{"code": exc.code, "message": exc.message}]}
        return {
            "binding": record(binding),
            "metadata_ready": ready,
            "execution_ready": False,
            "blocking_reason": reason,
            "validation": validation,
        }

    async def column_bindings(self, sheet_id):
        await self.repo.get(SourceSheet, sheet_id)
        rows = (await self.session.scalars(self.repo.query(MasterColumnBinding).where(
            MasterColumnBinding.source_sheet_id == str(sheet_id)
        ).order_by(MasterColumnBinding.source_column))).all()
        return [record(row) for row in rows]

    async def binding_recommendations(self, sheet_id):
        sheet = await self.repo.get(SourceSheet, sheet_id)
        profile = await SourceRepository(self.session, self.user.tenant_id).latest_profile(sheet.id)
        headers = profile.profile_json.get("columns", []) if profile else []
        masters = (await self.session.scalars(self.repo.query(MasterDefinition).where(
            MasterDefinition.status == "APPROVED", MasterDefinition.is_active.is_(True)
        ))).all()
        recommendations = []
        for header in headers:
            source = str(header.get("name", header) if isinstance(header, dict) else header)
            candidates = []
            for master in masters:
                definition = MasterSchema.model_validate(master.approved_definition_json)
                for field in definition.fields:
                    score = SequenceMatcher(None, source.casefold().replace(" ", "_"), field.name.casefold()).ratio()
                    if score >= 0.55:
                        candidates.append({"master_definition_id": master.id, "master_field": field.name, "score": round(score, 3)})
            recommendations.append({"source_column": source, "candidates": sorted(candidates, key=lambda item: -item["score"])[:10]})
        return {"items": recommendations, "requires_confirmation": True}

    async def save_column_binding(self, sheet_id, data):
        self.require_role(EDIT_ROLES)
        await self.repo.get(SourceSheet, sheet_id)
        master = await self.repo.get(MasterDefinition, data.master_definition_id)
        if master.status != "APPROVED" or master.approved_version != data.master_version:
            raise AppError("MASTER_VERSION_UNAVAILABLE", "Master harus aktif dan versi approved sesuai.", 409)
        definition = MasterSchema.model_validate(master.approved_definition_json)
        if data.master_field not in {field.name for field in definition.fields}:
            raise AppError("MASTER_FIELD_INVALID", "Field tujuan tidak tersedia pada master.", 422)
        try:
            for alias, record_id in data.aliases.items():
                if not alias.strip() or UUID(str(record_id)) is None:
                    raise ValueError
        except (TypeError, ValueError):
            raise AppError("MASTER_ALIAS_INVALID", "Alias harus memetakan ke UUID record master yang valid.", 422) from None
        binding = await self.session.scalar(self.repo.query(MasterColumnBinding).where(
            MasterColumnBinding.source_sheet_id == str(sheet_id),
            MasterColumnBinding.source_column == data.source_column,
        ).with_for_update())
        if data.revision_no != (binding.revision_no if binding else 0):
            raise AppError("MASTER_COLUMN_BINDING_CONFLICT", "Revisi binding berubah; muat ulang.", 409)
        values = data.model_dump(exclude={"revision_no", "aliases"})
        values["aliases_json"] = data.aliases
        values["created_by"] = self.user.id
        if binding:
            for key, value in values.items(): setattr(binding, key, value)
            binding.revision_no += 1
        else:
            binding = await self.repo.add(MasterColumnBinding, source_sheet_id=str(sheet_id), **values)
        audit(self.session, self.user, "master.column_binding_saved", binding.id, source_column=data.source_column)
        return record(binding)

    async def column_binding_decision(self, binding_id, data, approve=True):
        self.require_role(REVIEW_ROLES)
        binding = await self.repo.get(MasterColumnBinding, binding_id)
        if binding.revision_no != data.revision_no or binding.status != "DRAFT":
            raise AppError("MASTER_COLUMN_BINDING_CONFLICT", "Binding berubah atau bukan draft.", 409)
        if approve:
            if get_settings().require_separate_approver and binding.created_by == self.user.id:
                raise AppError("SEPARATE_APPROVER_REQUIRED", "Approver harus berbeda dari editor binding.", 403)
            master = await self.repo.get(MasterDefinition, binding.master_definition_id)
            if master.status != "APPROVED" or master.approved_version != binding.master_version:
                raise AppError("MASTER_VERSION_UNAVAILABLE", "Versi master binding sudah tidak aktif.", 409)
            binding.approved_by, binding.approved_at = self.user.id, now()
            binding.status = "APPROVED"
        else:
            binding.status = "REJECTED"
        binding.revision_no += 1
        audit(self.session, self.user, "master.column_binding_decided", binding.id, status=binding.status)
        return record(binding)

    async def dependency_plan(self):
        self.require_role((*EDIT_ROLES, *REVIEW_ROLES))
        rows = (await self.session.scalars(self.repo.query(MasterColumnBinding).where(
            MasterColumnBinding.status == "APPROVED"
        ))).all()
        masters = {row.master_definition_id for row in rows}
        graph = {master_id: set() for master_id in masters}
        # Bindings are currently column-level edges; expose a stable plan for the
        # FK compiler while keeping DDL disabled until target relation metadata exists.
        targets = {}
        for row in rows:
            sheet = await self.repo.get(SourceSheet, row.source_sheet_id)
            source_binding = await self.session.scalar(self.repo.query(MasterSourceBinding).where(
                MasterSourceBinding.source_sheet_id == str(sheet.id),
                MasterSourceBinding.status == "APPROVED",
            ))
            if source_binding:
                masters.add(source_binding.master_definition_id)
                graph.setdefault(source_binding.master_definition_id, set()).add(row.master_definition_id)
            config = None
            if sheet.active_configuration_id:
                config = await self.repo.get(Configuration, sheet.active_configuration_id)
            target_column = row.source_column
            if config:
                for column in config.configuration_json.get("columns", []):
                    if column.get("source_column") == row.source_column:
                        target_column = column["target_column"]
                        break
            targets[str(row.id)] = {
                "target_table": f"trusted.{config.configuration_json['target_table']}_{str(sheet.id).replace('-', '')}" if config else None,
                "target_column": target_column,
            }
        visiting, visited = set(), set()

        def cycle(node):
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            if any(cycle(child) for child in graph.get(node, ())):
                return True
            visiting.remove(node)
            visited.add(node)
            return False

        has_cycle = any(cycle(node) for node in graph)
        indegree = {node: 0 for node in graph}
        for children in graph.values():
            for child in children:
                indegree[child] = indegree.get(child, 0) + 1
        queue = sorted(node for node, degree in indegree.items() if degree == 0)
        order = []
        while queue:
            node = queue.pop(0)
            order.append(node)
            for child in sorted(graph.get(node, ())):
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
                    queue.sort()
        return {
            "nodes": sorted(masters),
            "load_order": order,
            "edges": [
                {
                    "source_sheet_id": row.source_sheet_id,
                    "master_definition_id": row.master_definition_id,
                    "master_field": row.master_field,
                    "source_column": row.source_column,
                    "master_version": row.master_version,
                    **targets[str(row.id)],
                }
                for row in rows
            ],
            "has_cycle": has_cycle,
            "correction_actions": ([
                "Hapus atau ubah salah satu binding yang membentuk siklus.",
                "Deploy FK hanya setelah dependency plan tidak memiliki siklus.",
            ] if has_cycle else []),
            "execution_ready": False,
            "blocking_reason": "FK_TARGET_RELATION_METADATA_REQUIRED",
        }

    async def validate_reference_orphans(self):
        self.require_role((*EDIT_ROLES, *REVIEW_ROLES))
        rows = (await self.session.scalars(self.repo.query(MasterColumnBinding).where(
            MasterColumnBinding.status == "APPROVED"
        ))).all()
        results = []
        for binding in rows:
            sheet = await self.repo.get(SourceSheet, binding.source_sheet_id)
            config = await self.repo.get(Configuration, sheet.active_configuration_id) if sheet.active_configuration_id else None
            master = await self.repo.get(MasterDefinition, binding.master_definition_id)
            if not config or master.status != "APPROVED":
                results.append({"binding_id": binding.id, "status": "BLOCKED", "reason": "TARGET_OR_MASTER_NOT_READY"})
                continue
            definition = MasterSchema.model_validate(master.approved_definition_json)
            if len(definition.business_key) != 1:
                results.append({"binding_id": binding.id, "status": "BLOCKED", "reason": "COMPOSITE_KEY_REQUIRES_EXPLICIT_MAPPING"})
                continue
            from app.services.schema_compiler_service import compile_master_table, compile_table

            target = compile_table(ETLConfiguration.model_validate(config.configuration_json), sheet.id)
            master_table = compile_master_table(definition, master.id, self.user.tenant_id)
            target_column = next((c["target_column"] for c in config.configuration_json["columns"] if c["source_column"] == binding.source_column), None)
            if not target_column or target_column not in target.c:
                results.append({"binding_id": binding.id, "status": "BLOCKED", "reason": "TARGET_COLUMN_NOT_FOUND"})
                continue
            target_type = target.c[target_column].type.__class__.__name__.lower()
            master_type = master_table.c[definition.business_key[0]].type.__class__.__name__.lower()
            if target_type != master_type:
                results.append({"binding_id": binding.id, "status": "BLOCKED", "reason": "REFERENCE_TYPE_MISMATCH", "target_type": target_type, "master_type": master_type})
                continue
            connection = await self.session.connection()
            await connection.run_sync(lambda sync: check_storage(sync, target))
            await connection.run_sync(lambda sync: check_storage(sync, master_table))
            values = (await self.session.execute(select(target.c[target_column]).where(
                target.c._tenant_id == self.user.tenant_id, target.c[target_column].is_not(None)
            ).distinct())).scalars().all()
            known = set((await self.session.execute(select(master_table.c[definition.business_key[0]]).where(
                master_table.c._tenant_id == self.user.tenant_id, master_table.c._is_active.is_(True)
            ))).scalars().all())
            orphan_values = [value for value in values if value not in known]
            results.append({"binding_id": binding.id, "status": "ORPHANS_FOUND" if orphan_values else "VALID", "orphan_count": len(orphan_values), "orphan_values": [str(value) for value in orphan_values[:100]]})
        return {"items": results, "execution_ready": bool(results) and all(item["status"] == "VALID" for item in results)}

    async def deploy_foreign_keys(self):
        self.require_role(REVIEW_ROLES)
        plan = await self.dependency_plan()
        if plan["has_cycle"]:
            raise AppError("REFERENCE_DEPENDENCY_CYCLE", "Siklus dependency harus diperbaiki sebelum deployment FK.", 409)
        validation = await self.validate_reference_orphans()
        if not validation["execution_ready"]:
            raise AppError("REFERENCE_VALIDATION_REQUIRED", "Selesaikan orphan/type validation sebelum memasang FK.", 409)
        rows = (await self.session.scalars(self.repo.query(MasterColumnBinding).where(
            MasterColumnBinding.status == "APPROVED"
        ))).all()
        connection = await self.session.connection()
        created = []
        for binding in rows:
            sheet = await self.repo.get(SourceSheet, binding.source_sheet_id)
            config = await self.repo.get(Configuration, sheet.active_configuration_id)
            target_name = f"{config.configuration_json['target_table']}_{str(sheet.id).replace('-', '')}"
            master = await self.repo.get(MasterDefinition, binding.master_definition_id)
            master_table = "master_" + str(master.id).replace("-", "")
            target_column = next(c["target_column"] for c in config.configuration_json["columns"] if c["source_column"] == binding.source_column)
            constraint = f"fk_{target_name[:35]}_{target_column[:20]}"
            quote = connection.dialect.identifier_preparer.quote
            privileges = await connection.execute(text(
                "SELECT has_table_privilege(current_user, :target, 'REFERENCES') "
                "AND has_table_privilege(current_user, :master, 'REFERENCES')"
            ), {"target": f"trusted.{target_name}", "master": f"trusted.{master_table}"})
            if not privileges.scalar():
                raise AppError("DDL_REFERENCES_REQUIRED", "Role DDL memerlukan privilege REFERENCES pada target dan master.", 403)
            exists = await connection.scalar(text(
                "SELECT 1 FROM pg_constraint WHERE conname = :name"
            ), {"name": constraint})
            if exists:
                created.append({"binding_id": binding.id, "constraint": constraint, "reused": True})
                continue
            await connection.execute(text(
                f"ALTER TABLE trusted.{quote(target_name)} ADD CONSTRAINT {quote(constraint)} "
                f"FOREIGN KEY ({quote('_tenant_id')}, {quote(target_column)}) "
                f"REFERENCES trusted.{quote(master_table)} ({quote('_tenant_id')}, {quote('_record_id')}) ON DELETE RESTRICT"
            ))
            created.append({"binding_id": binding.id, "constraint": constraint})
        audit(self.session, self.user, "master.foreign_keys_deployed", self.user.tenant_id, count=len(created))
        return {"created": created, "execution_ready": True}
