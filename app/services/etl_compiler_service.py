import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID

from app.core.exceptions import AppError


def decimal_id(value):
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    value = str(value).strip().replace("Rp", "").replace(" ", "")
    if not re.fullmatch(r"-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?", value):
        raise ValueError("Invalid Indonesian decimal")
    return Decimal(value.replace(".", "").replace(",", "."))


def date_id(value):
    if isinstance(value, (int, float)):
        return (datetime(1899, 12, 30) + timedelta(days=value)).date()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError("Invalid date")


TRANSFORMS = {
    "trim": lambda v: v.strip() if isinstance(v, str) else v,
    "normalize_whitespace": lambda v: " ".join(v.split()) if isinstance(v, str) else v,
    "uppercase": lambda v: str(v).upper(),
    "lowercase": lambda v: str(v).lower(),
    "null_if_empty": lambda v: None if isinstance(v, str) and not v.strip() else v,
    "parse_decimal_id": decimal_id,
    "parse_date_id": date_id,
}


def cast_value(value, kind):
    if value is None or value == "":
        return None
    if kind in ("text", "varchar"):
        return str(value)
    if kind in ("integer", "bigint", "numeric"):
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError("Non-finite numeric value")
        if kind != "numeric":
            bound = 2 ** (31 if kind == "integer" else 63)
            if number != number.to_integral_value() or not -bound <= number < bound:
                raise ValueError("Invalid integer")
            return int(number)
        return number
    if kind == "boolean":
        if str(value).lower() in ("true", "1", "ya", "yes"):
            return True
        if str(value).lower() in ("false", "0", "tidak", "no"):
            return False
        raise ValueError("Invalid boolean")
    if kind == "date":
        return value if isinstance(value, date) else date.fromisoformat(str(value))
    if kind in ("timestamp", "timestamptz"):
        result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        if kind == "timestamptz" and result.tzinfo is None:
            raise ValueError("Timezone is required")
        if kind == "timestamp" and result.tzinfo is not None:
            raise ValueError("Use timestamptz for timezone-aware values")
        return result
    if kind == "uuid":
        return str(UUID(str(value)))
    raise ValueError("Unsupported type")


def transform_rows(values, sheet, config):
    headers = [str(v).strip() for v in values[sheet.header_row - 1]]
    positions = {h: i for i, h in enumerate(headers)}
    if not {c.source_column for c in config.columns}.issubset(positions):
        raise AppError(
            "CONFIGURATION_CONFLICT", "Kolom sumber berubah; lakukan profiling dan review ulang.", 409
        )
    good, issues, warnings, seen = [], [], [], {}
    keys = [c.target_column for c in config.columns if c.is_business_key or c.is_primary_key]
    for row_number, raw in enumerate(values[sheet.data_start_row - 1 :], sheet.data_start_row):
        if not any(v is not None and v != "" for v in raw):
            continue
        result, errors = {}, []
        for column in config.columns:
            i = positions[column.source_column]
            value = raw[i] if i < len(raw) else None
            try:
                for transform in column.transformation_codes:
                    if value is not None:
                        value = TRANSFORMS[transform](value)
                value = cast_value(value, column.target_type)
                if value is None and not column.nullable:
                    raise ValueError("Required value")
                result[column.target_column] = value
            except (ValueError, TypeError, InvalidOperation, OverflowError):
                errors.append({"column": column.target_column, "code": "TYPE_OR_NULL_ERROR"})
        if not errors:
            for rule in config.data_quality_rules:
                value = result[rule.column]
                failed = False
                if rule.rule == "not_null":
                    failed = value is None
                elif rule.rule == "unique":
                    bucket = seen.setdefault(rule.column, set())
                    failed = value in bucket
                    bucket.add(value)
                elif rule.rule in ("min", "max") and value is not None:
                    try:
                        failed = (
                            Decimal(str(value)) < Decimal(str(rule.value))
                            if rule.rule == "min"
                            else Decimal(str(value)) > Decimal(str(rule.value))
                        )
                    except InvalidOperation:
                        failed = True
                elif rule.rule == "allowed_values":
                    failed = str(value) not in rule.value
                if failed:
                    detail = {"column": rule.column, "code": rule.rule.upper()}
                    if rule.action_on_fail == "WARN":
                        warnings.append({"source_row": row_number, **detail})
                    elif rule.action_on_fail in ("STOP_BATCH", "REQUIRE_REVIEW"):
                        raise AppError(
                            "DQ_" + rule.action_on_fail, "Data quality rule menghentikan batch untuk review."
                        )
                    else:
                        errors.append(detail)
            if keys:
                key = tuple(result[k] for k in keys)
                bucket = seen.setdefault("__business_keys", set())
                if key in bucket:
                    errors.append({"column": ",".join(keys), "code": "DUPLICATE_BUSINESS_KEY"})
                bucket.add(key)
        if errors:
            issues.append({"source_row": row_number, "data": raw, "errors": errors})
        else:
            good.append((row_number, result))
    return good, issues, warnings
