"""Keyless APPEND shares the physical tenant/hash identity across execution paths."""
from sqlalchemy.dialects.postgresql import insert

from app.core.exceptions import AppError
from app.services.profiling_service import digest


def keyless_append(config):
    return config.load_strategy == "APPEND" and not any(
        c.is_business_key or c.is_primary_key for c in config.columns
    )


def append_outcome(config, duplicate):
    if not duplicate:
        return "INSERT"
    return "DUPLICATE" if config.append_duplicate_policy == "REJECT_IDENTICAL" else "UNCHANGED"


def append_values(config, values):
    # Staging JSON serializes Decimal/date values; restore target types without
    # rerunning source transforms or conversions on already transformed values.
    from app.services.etl_compiler_service import cast_value

    try:
        return {c.target_column: cast_value(values.get(c.target_column), c.target_type) for c in config.columns}
    except (ValueError, TypeError, ArithmeticError):
        raise AppError("APPEND_VALUE_INVALID", "Nilai staging APPEND tidak sesuai tipe target.") from None


async def append_row(session, table, values, config):
    business = append_values(config, values)
    values = {**values, **business, "_row_hash": digest(business)}
    # PostgreSQL arbitrates concurrent identical inserts; never count a skipped row.
    result = await session.execute(insert(table).values(**values).on_conflict_do_nothing(
        index_elements=["_tenant_id", "_row_hash"]))
    loaded = max(0, result.rowcount)
    if not loaded and config.append_duplicate_policy == "REJECT_IDENTICAL":
        raise AppError("APPEND_IDENTICAL_REJECTED", "Baris APPEND identik sudah tersedia; batch dibatalkan.", 409)
    return loaded
