from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from app.core.exceptions import AppError


def parse_watermark(value, kind):
    try:
        if kind == "INTEGER":
            return int(str(value))
        if kind == "DECIMAL":
            result = Decimal(str(value))
            if not result.is_finite():
                raise ValueError
            return result
        if kind == "DATE":
            return date.fromisoformat(str(value))
        if kind == "DATETIME":
            result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if result.tzinfo is None:
                raise ValueError
            return result.astimezone(timezone.utc)
    except (ValueError, TypeError, InvalidOperation, OverflowError):
        pass
    raise AppError("WATERMARK_VALUE_INVALID", "Nilai watermark tidak sesuai kind yang dipilih.")


def serialize_watermark(value, kind):
    if kind == "DATETIME":
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return value.isoformat() if kind == "DATE" else str(value)


def incremental_values(values, sheet):
    column = getattr(sheet, "watermark_source_column", None)
    kind = getattr(sheet, "watermark_kind", None)
    if not column or not kind:
        return values, None, None
    if len(values) < sheet.header_row:
        raise AppError("WATERMARK_COLUMN_INVALID", "Header watermark tidak tersedia.")
    headers = [str(item).strip() for item in values[sheet.header_row - 1]]
    if column not in headers:
        raise AppError("WATERMARK_COLUMN_INVALID", "Kolom watermark tidak ditemukan pada tab.", 409)
    position = headers.index(column)
    base_text = getattr(sheet, "watermark_value", None)
    base = parse_watermark(base_text, kind) if base_text is not None else None
    candidate = base
    selected = 0
    filtered = list(values[: sheet.data_start_row - 1])
    for row in values[sheet.data_start_row - 1 :]:
        if not any(item is not None and item != "" for item in row):
            filtered.append([])
            continue
        raw = row[position] if position < len(row) else None
        current = parse_watermark(raw, kind)
        if base is None or current > base:
            filtered.append(row)
            selected += 1
            if candidate is None or current > candidate:
                candidate = current
        else:
            filtered.append([])
    candidate_text = serialize_watermark(candidate, kind) if selected else None
    return filtered, candidate_text, selected
