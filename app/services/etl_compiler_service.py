import re
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.exceptions import AppError


def decimal_id(value, locale="ID"):
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    value = str(value).strip().replace("Rp", "").replace(" ", "")
    pattern = r"-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?" if locale == "ID" else r"-?\d+(?:\.\d+)?"
    if not re.fullmatch(pattern, value):
        raise ValueError("Invalid Indonesian decimal")
    return Decimal(value.replace(".", "").replace(",", ".") if locale == "ID" else value)


def date_id(value, fmt=None):
    if isinstance(value, (int, float)):
        return (datetime(1899, 12, 30) + timedelta(days=value)).date()
    for current in ((fmt,) if fmt else ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d")):
        try:
            return datetime.strptime(str(value).strip(), current).date()
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


def local_timestamp_to_utc(value, timezone_name):
    zone = ZoneInfo(timezone_name)
    candidates = set()
    for fold in (0, 1):
        instant = value.replace(tzinfo=zone, fold=fold).astimezone(UTC)
        # A nonexistent wall time does not survive a round-trip; an ambiguous one
        # yields two distinct instants. Neither may be silently guessed.
        if instant.astimezone(zone).replace(tzinfo=None) == value:
            candidates.add(instant)
    if len(candidates) != 1:
        raise ValueError("Ambiguous or nonexistent local timestamp; provide an explicit offset")
    return candidates.pop()


def cast_value(value, kind, *, source_timezone=None):
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
        if kind == "timestamptz":
            if result.tzinfo is None:
                if source_timezone is None:
                    raise ValueError("Timezone is required")
                return local_timestamp_to_utc(result, source_timezone)
            return result.astimezone(UTC)
        if kind == "timestamp" and result.tzinfo is not None:
            raise ValueError("Use timestamptz for timezone-aware values")
        return result
    if kind == "uuid":
        return str(UUID(str(value)))
    raise ValueError("Unsupported type")


ROUNDING_MODES = {"HALF_UP": ROUND_HALF_UP, "HALF_EVEN": ROUND_HALF_EVEN, "DOWN": ROUND_DOWN}


def apply_numeric_parameters(value, column, *, use_conversion=True):
    conversion = (column.unit_conversion or column.currency_conversion) if use_conversion else None
    # Precision is local: ambient Decimal precision must not change imported values.
    with localcontext() as context:
        context.prec = max(120, len(value.as_tuple().digits) + 100)
        if conversion is not None:
            factor = conversion.factor if column.unit_conversion is not None else conversion.rate
            value = (value * factor).quantize(
                Decimal(1).scaleb(-conversion.output_scale), rounding=ROUNDING_MODES[conversion.rounding]
            )
        if column.numeric_precision is not None:
            scale = column.numeric_scale or 0
            value = value.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)
            if abs(value) >= Decimal(10) ** (column.numeric_precision - scale):
                raise ValueError("Numeric precision overflow")
    return value


def matches_format(value, format_name):
    try:
        text = value.isoformat() if isinstance(value, (date, datetime)) else str(value)
        if format_name == "UUID":
            return str(UUID(text)) == text.lower()
        if format_name == "ISO_DATE":
            return date.fromisoformat(text).isoformat() == text
        return "T" in text and datetime.fromisoformat(text) is not None
    except (ValueError, TypeError):
        return False


def transform_rows(values, sheet, config, *, reference_time=None):
    reference_time = reference_time or datetime.now(UTC)
    if reference_time.tzinfo is None:
        raise ValueError("reference_time requires timezone")
    reference_time = reference_time.astimezone(UTC)
    defaults = {r.column: r.default_value for r in config.data_quality_rules if r.default_value is not None}
    headers = [str(v).strip() for v in values[sheet.header_row - 1]]
    positions = {h: i for i, h in enumerate(headers)}
    if not {c.source_column for c in config.columns}.issubset(positions):
        raise AppError(
            "CONFIGURATION_CONFLICT", "Kolom sumber berubah; lakukan profiling dan review ulang.", 409
        )
    good, issues, warnings, seen = [], [], [], {}
    dq_seen, dq_failed = {}, {}
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
                        if transform == "parse_date_id":
                            value = date_id(value, column.date_format)
                        elif transform == "parse_decimal_id":
                            value = decimal_id(value, column.number_locale or "ID")
                        else:
                            value = TRANSFORMS[transform](value)
                used_default = (value is None or value == "") and column.target_column in defaults
                if used_default:
                    value = defaults[column.target_column]
                value = cast_value(
                    value, column.target_type,
                    source_timezone=None if used_default else column.source_timezone,
                )
                if value is not None and column.target_type == "numeric":
                    value = apply_numeric_parameters(value, column, use_conversion=not used_default)
                if value is not None and column.varchar_length is not None and len(value) > column.varchar_length:
                    raise ValueError("Text length exceeds varchar_length")
                if value is None and not column.nullable:
                    raise ValueError("Required value")
                result[column.target_column] = value
            except (ValueError, TypeError, InvalidOperation, OverflowError):
                errors.append({"column": column.target_column, "code": "TYPE_OR_NULL_ERROR"})
        if not errors:
            for rule_index, rule in enumerate(config.data_quality_rules):
                value = result[rule.column]
                dq_seen[rule_index] = dq_seen.get(rule_index, 0) + 1
                failed = False
                if rule.rule == "not_null":
                    failed = value is None
                elif rule.rule == "unique":
                    bucket = seen.setdefault(rule_index, set())
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
                elif rule.rule == "format" and value is not None:
                    failed = not matches_format(value, rule.value)
                elif rule.rule == "max_age_days" and value is not None:
                    if isinstance(value, datetime):
                        instant = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
                        failed = instant < reference_time - timedelta(days=rule.max_age_days)
                    else:
                        failed = value < reference_time.date() - timedelta(days=rule.max_age_days)
                if failed:
                    dq_failed[rule_index] = dq_failed.get(rule_index, 0) + 1
                    detail = {"column": rule.column, "code": rule.rule.upper(),
                              "rule_index": rule_index, "severity": rule.severity, "owner": rule.owner}
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
    for rule_index, rule in enumerate(config.data_quality_rules):
        if rule.threshold_percent is not None and dq_seen.get(rule_index, 0):
            rate = dq_failed.get(rule_index, 0) * 100 / dq_seen[rule_index]
            if rate > rule.threshold_percent:
                raise AppError("DQ_THRESHOLD_EXCEEDED", f"Rule {rule.rule} pada {rule.column} melebihi threshold.")
    return good, issues, warnings
