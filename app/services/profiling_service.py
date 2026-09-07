import hashlib
import json
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

from app.core.exceptions import AppError


def canonical_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def normalize_identifier(value):
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    if not value or not value[0].isalpha():
        value = "col_" + value
    return value[:63]


def infer_type(values):
    values = [v for v in values if v is not None and v != ""]
    if not values:
        return "text"
    if all(isinstance(v, bool) for v in values):
        return "boolean"
    # Preserve leading-zero identifiers (customer codes, phone numbers).
    if any(isinstance(v, str) and re.match(r"^0\d+", v) for v in values):
        return "text"
    try:
        nums = [Decimal(str(v)) for v in values]
        if not all(v.is_finite() for v in nums):
            return "text"
        return "bigint" if all(v == v.to_integral_value() for v in nums) else "numeric"
    except InvalidOperation:
        pass
    try:
        for value in values:
            date.fromisoformat(str(value))
        return "date"
    except ValueError:
        return "text"


def profile_values(values, sheet_name, header_row=1, data_start_row=2, range_a1="A:CV", sample_limit=200):
    if len(values) < header_row:
        raise AppError("PROFILE_FAILED", "Sheet kosong atau header row tidak tersedia.")
    headers = [str(v).strip() for v in values[header_row - 1]]
    if not headers or any(not h for h in headers) or len(set(headers)) != len(headers):
        raise AppError("PROFILE_FAILED", "Header harus terisi dan unik; perbaiki header/range Sheet.")
    normalized = [normalize_identifier(h) for h in headers]
    if len(set(normalized)) != len(normalized):
        raise AppError("PROFILE_FAILED", "Nama header bertabrakan setelah normalisasi.")
    rows = [r for r in values[data_start_row - 1 :] if any(v is not None and v != "" for v in r)]
    if any(len(r) > len(headers) for r in rows):
        raise AppError("PROFILE_FAILED", "Ada data di kolom tanpa header.")
    columns = []
    # Evenly sample rows; schema fingerprint does not include cell values.
    step = max(1, len(rows) // sample_limit)
    sample = rows[::step][:sample_limit]
    for index, (header, name) in enumerate(zip(headers, normalized)):
        cells = [r[index] if index < len(r) else None for r in sample]
        present = [v for v in cells if v is not None and v != ""]
        pii = bool(re.search(r"email|phone|telepon|alamat|address|nik|ktp|nama|name", name, re.I))
        pii = pii or any(re.search(r"[^\s@]+@[^\s@]+\.[^\s@]+", str(v)) for v in present)
        columns.append(
            {
                "source_column": header,
                "normalized_name": name,
                "inferred_type": infer_type(present),
                "null_ratio": 1 - len(present) / max(1, len(cells)),
                "distinct_ratio": len({str(v) for v in present}) / max(1, len(present)),
                "pii_suspected": pii,
                # All samples are withheld from AI, not only heuristically detected PII.
                "sample_masked": ["[REDACTED]" for _ in present[:3]],
            }
        )
    stable = {
        "sheet_name": sheet_name,
        "header_row": header_row,
        "range_a1": range_a1,
        "columns": [{"name": c["normalized_name"], "type": c["inferred_type"]} for c in columns],
    }
    return {
        "sheet_name": sheet_name,
        "header_row": header_row,
        "range_a1": range_a1,
        "row_count": len(rows),
        "sample_size": len(sample),
        "columns": columns,
        "fingerprint": digest(stable),
        "warnings": ["Review inferred types and PII classification before approval."],
    }
