"""Approved, sheet-scoped master reference resolution and dependency evidence."""
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy import select

from app.core.exceptions import AppError
from app.domain.enums import DATA_ROLES
from app.models.master import MasterColumnBinding
from app.models.source import SourceSheet
from app.repositories.base import TenantRepository
from app.services.etl_compiler_service import cast_value
from app.services.master_storage_service import MasterStorageService, check_storage
from app.services.profiling_service import digest


def normalized(value):
    return str(value).strip().casefold()


async def reference_context(session, user, sheet_id, config=None):
    repo = TenantRepository(session, user.tenant_id)
    # Same first lock as binding save/approval, including first binding creation.
    sheet = await session.scalar(repo.query(SourceSheet).where(SourceSheet.id == str(sheet_id)).with_for_update())
    if sheet is None:
        raise AppError("RESOURCE_NOT_FOUND", "Tab referensi tidak ditemukan.", 404)
    bindings = (await session.scalars(repo.query(MasterColumnBinding).where(
        MasterColumnBinding.source_sheet_id == str(sheet_id)
    ).order_by(MasterColumnBinding.master_definition_id, MasterColumnBinding.source_column)
      .with_for_update().execution_options(populate_existing=True))).all()
    context = {}
    for binding in bindings:
        if binding.status != "APPROVED":
            raise AppError("REFERENCE_BINDING_REQUIRED", "Binding referensi harus approved sebelum digunakan.", 409)
        master, definition, table = await MasterStorageService(session, user).target(binding.master_definition_id)
        if master.approved_version != binding.master_version:
            raise AppError("REFERENCE_BINDING_STALE", "Versi master berubah; perbarui dan approve binding.", 409)
        if binding.normalization != "TRIM_CASEFOLD":
            raise AppError("REFERENCE_NORMALIZATION_UNSUPPORTED", "Normalisasi referensi belum didukung.", 409)
        if binding.master_field not in {field.name for field in definition.fields}:
            raise AppError("MASTER_FIELD_INVALID", "Field referensi tidak tersedia.", 409)
        column = next((c for c in config.columns if c.source_column == binding.source_column), None) if config else None
        if config and (not column or column.target_type != "uuid"):
            raise AppError("REFERENCE_MAPPING_INVALID", "Binding referensi memerlukan kolom konfigurasi bertipe UUID.", 409)
        await (await session.connection()).run_sync(lambda sync: check_storage(sync, table))
        records = [dict(r) for r in (await session.execute(select(table).where(
            table.c._tenant_id == user.tenant_id).order_by(table.c._record_id))).mappings()]
        active = {str(r["_record_id"]): r for r in records if r["_is_active"]}
        aliases = {}
        for alias, record_id in binding.aliases_json.items():
            key = normalized(alias)
            try:
                record_id = str(UUID(str(record_id)))
            except (TypeError, ValueError):
                raise AppError("MASTER_ALIAS_INVALID", "Alias harus menunjuk UUID record aktif.", 409) from None
            if not key or key in aliases or record_id not in active:
                raise AppError("MASTER_ALIAS_INVALID", "Alias harus unik setelah normalisasi dan menunjuk record aktif.", 409)
            aliases[key] = record_id
        evidence = {"binding_id": binding.id, "revision": binding.revision_no,
                    "master_id": master.id, "master_version": master.approved_version,
                    "definition": master.approved_definition_json, "records": records,
                    "field": binding.master_field, "required": binding.required,
                    "cardinality": binding.cardinality, "normalization": binding.normalization, "aliases": aliases}
        context[binding.source_column] = {"binding": binding, "definition": definition, "active": active,
                                          "aliases": aliases, "column": column, "hash": digest(evidence)}
    return context


def reference_hash(context):
    return digest({name: item["hash"] for name, item in context.items()}) if context else None


def validate_reference_rows(context, rows):
    for item in context.values():
        binding, column, seen = item["binding"], item["column"], set()
        for row in rows:
            value = {**row.transformed_data, **row.corrected_data}.get(column.target_column)
            if value in (None, ""):
                if binding.required:
                    raise AppError("REFERENCE_REQUIRED", "Referensi wajib belum diselesaikan.", 409)
                continue
            try:
                record_id = str(UUID(str(value)))
            except (ValueError, TypeError):
                raise AppError("REFERENCE_UNRESOLVED", "Referensi harus berupa UUID master, bukan label.", 409) from None
            if record_id not in item["active"]:
                raise AppError("REFERENCE_RECORD_UNAVAILABLE", "UUID referensi tidak tersedia atau nonaktif.", 409)
            if binding.cardinality == "ONE_TO_ONE" and record_id in seen:
                raise AppError("REFERENCE_CARDINALITY_CONFLICT", "Record yang sama dirujuk berulang pada ONE_TO_ONE.", 409)
            seen.add(record_id)


def resolve_value(item, value, user):
    binding, definition = item["binding"], item["definition"]
    sensitive = {f.name for f in definition.fields if f.pii_classification in ("MEDIUM", "HIGH")}
    masked = sensitive if user.role not in DATA_ROLES else set()
    if binding.master_field in masked:
        raise AppError("REFERENCE_SEARCH_FORBIDDEN", "Role ini tidak boleh mencari melalui field master sensitif.", 403)
    if not value.strip():
        return {"status": "NOT_FOUND" if binding.required else "EMPTY",
                "requires_question": binding.required, "candidates": [], "masked_fields": sorted(masked)}
    field = next(f for f in definition.fields if f.name == binding.master_field)
    try:
        typed = str(UUID(value.strip())) if field.type == "uuid" else cast_value(value.strip(), field.type)
    except (ValueError, TypeError, ArithmeticError, OverflowError):
        typed = None
    exact = []
    for record_id, row in item["active"].items():
        if row[binding.master_field] is None:
            continue
        equal = (normalized(row[binding.master_field]) == normalized(value)
                 if field.type in ("text", "varchar") else typed is not None and row[binding.master_field] == typed)
        if equal:
            exact.append(record_id)
    alias_id = item["aliases"].get(normalized(value))
    matches = sorted(set(exact) | ({alias_id} if alias_id else set()))

    def visible(record_id):
        return {k: "[REDACTED]" if k in masked else v for k, v in item["active"][record_id].items()}

    if len(matches) == 1:
        return {"status": "EXACT" if exact else "ALIAS", "record": visible(matches[0]),
                "requires_question": False, "masked_fields": sorted(masked)}
    if len(matches) > 1:
        return {"status": "AMBIGUOUS", "candidates": [visible(rid) for rid in matches[:6]],
                "requires_question": True, "masked_fields": sorted(masked)}
    label = definition.label_field
    candidates = []
    if label not in masked:
        for rid, row in item["active"].items():
            if row[label] is None:
                continue
            score = SequenceMatcher(None, normalized(value), normalized(row[label])).ratio()
            if normalized(value) in normalized(row[label]) or score >= 0.6:
                candidates.append({**visible(rid), "match_score": round(score, 4)})
    candidates.sort(key=lambda row: (-row["match_score"], str(row["_record_id"])))
    status = "AMBIGUOUS" if len(candidates) > 1 else "CANDIDATE" if candidates else "NOT_FOUND"
    return {"status": status, "candidates": candidates[:6], "requires_question": True,
            "masked_fields": sorted(masked)}
