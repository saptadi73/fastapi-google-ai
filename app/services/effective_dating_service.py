"""Immutable explicit master versions; intervals are [start, end), null end is unbounded."""
import json
import re
from collections import defaultdict
from datetime import date, datetime

from sqlalchemy import and_, or_

from app.core.exceptions import AppError
from app.services.etl_compiler_service import cast_value


def validate_versions(definition, incoming, existing):
    """Return typed incoming rows and keys already present identically, without writes.

    Callers must scope existing records to tenant and hold the master apply lock
    during validation and writes. Inactive history participates in overlap checks.
    """
    period = definition.policy.effective_dating
    fields = {f.name: f for f in definition.fields}
    keys = definition.business_key
    entity_keys = [key for key in keys if key != period.valid_from_column]

    def typed(row):
        result = {}
        try:
            for name, field in fields.items():
                value = cast_value(row.get(name), field.type)
                if value is None and not field.nullable:
                    raise ValueError("Required value")
                result[name] = value
            start, end = result[period.valid_from_column], result[period.valid_to_column]
            if start is None or (end is not None and end <= start):
                raise ValueError("Invalid interval")
        except (ValueError, TypeError, ArithmeticError, OverflowError):
            raise AppError("MASTER_PERIOD_INVALID", "Field atau interval versi tidak valid; akhir harus setelah awal.") from None
        return result

    if any(set(row) - fields.keys() for row in incoming):
        raise AppError("MASTER_PERIOD_INVALID", "Kandidat versi memiliki field di luar schema master.")
    stored = [typed(row) for row in existing]
    candidates = [typed(row) for row in incoming]
    stored_by_key = {tuple(row[k] for k in keys): row for row in stored}
    identical, seen = set(), set()
    intervals = defaultdict(list)
    for row in stored:
        intervals[tuple(row[k] for k in entity_keys)].append(row)
    for row in candidates:
        key = tuple(row[k] for k in keys)
        if key in seen:
            raise AppError("MASTER_VERSION_DUPLICATE", "Versi yang sama muncul lebih dari sekali dalam batch.")
        seen.add(key)
        if key in stored_by_key:
            if row != stored_by_key[key]:
                raise AppError("MASTER_VERSION_IMMUTABLE", "Versi tersimpan tidak boleh ditimpa; koreksi memerlukan migrasi yang direview.", 409)
            identical.add(key)
        else:
            intervals[tuple(row[k] for k in entity_keys)].append(row)
    for versions in intervals.values():
        versions.sort(key=lambda row: row[period.valid_from_column])
        for previous, current in zip(versions, versions[1:]):
            end = previous[period.valid_to_column]
            if end is None or current[period.valid_from_column] < end:
                raise AppError("MASTER_PERIOD_OVERLAP", "Masa berlaku versi master bertumpang tindih.", 409)
    return candidates, identical


def effective_at_condition(definition, table, value, *, masked_fields=()):
    """Build a parameterized [start, end) filter, without leaking hidden periods."""
    period = definition.policy.effective_dating
    if period is None:
        raise AppError("MASTER_EFFECTIVE_DATING_REQUIRED", "Filter as_of memerlukan policy masa berlaku.", 409)
    if {period.valid_from_column, period.valid_to_column} & set(masked_fields):
        raise AppError("MASTER_PERIOD_FILTER_FORBIDDEN", "Periode sensitif tidak boleh dipakai sebagai filter oleh role ini.", 403)
    kind = next(field.type for field in definition.fields if field.name == period.valid_from_column)
    try:
        if kind == "date":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("Expected date")
            point = date.fromisoformat(value)
        else:
            if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value):
                raise ValueError("Expected timestamp")
            point = cast_value(value, kind)
            if not isinstance(point, datetime):
                raise ValueError("Expected timestamp")
    except (ValueError, TypeError, OverflowError):
        raise AppError("MASTER_AS_OF_INVALID", "as_of harus sesuai tipe periode: YYYY-MM-DD atau timestamp ISO dengan T; timestamptz wajib offset.") from None
    return and_(
        table.c[period.valid_from_column] <= point,
        or_(table.c[period.valid_to_column].is_(None), table.c[period.valid_to_column] > point),
    )


def version_plan_hash(incoming, existing):
    from app.services.profiling_service import digest

    # Preserve Decimal/temporal values exactly; database row ordering is irrelevant.
    def serialize(row):
        return json.dumps(dict(row), sort_keys=True, default=str)
    return digest({"incoming": [serialize(row) for row in incoming],
                   "existing": sorted(serialize(row) for row in existing)})


def plan_version_closures(definition, incoming, existing):
    """Propose only NULL -> next start closures; caller must preview/approve the plan."""
    period = definition.policy.effective_dating
    if definition.policy.new_record_policy != "PROPOSE_INSERT":
        raise AppError("MASTER_PERIOD_CLOSURE_INVALID", "Penutupan dengan versi baru memerlukan policy PROPOSE_INSERT.", 409)
    names = {field.name for field in definition.fields}
    stored, _ = validate_versions(definition, [{k: v for k, v in row.items() if k in names} for row in existing], [])
    candidates, _ = validate_versions(definition, incoming, [])
    keys = definition.business_key
    entity = [key for key in keys if key != period.valid_from_column]
    known = {tuple(row[key] for key in keys) for row in stored}
    closures = []
    revised = [dict(row) for row in stored]
    for index, old in enumerate(stored):
        if old[period.valid_to_column] is not None:
            continue
        following = [row[period.valid_from_column] for row in candidates
                     if tuple(row[key] for key in keys) not in known
                     and all(row[key] == old[key] for key in entity)
                     and row[period.valid_from_column] > old[period.valid_from_column]]
        if not following:
            continue
        metadata = existing[index]
        if not metadata.get("_is_active", True):
            raise AppError("MASTER_PERIOD_CLOSURE_INVALID", "Periode versi nonaktif tidak boleh ditutup oleh import.", 409)
        if not metadata.get("_record_id") or not isinstance(metadata.get("_revision_no"), int):
            raise AppError("MASTER_PERIOD_CLOSURE_INVALID", "Identitas/revisi target penutupan tidak valid.", 409)
        cutoff = min(following)
        revised[index][period.valid_to_column] = cutoff
        closures.append({"record_id": str(metadata["_record_id"]), "revision_no": metadata["_revision_no"],
                         "column": period.valid_to_column, "before": None, "after": cutoff})
    # Also rejects backdating, non-NULL edits and changes to any historical attributes.
    typed, identical = validate_versions(definition, incoming, revised)
    return typed, identical, sorted(closures, key=lambda item: item["record_id"])
