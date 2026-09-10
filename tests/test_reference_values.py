from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.reference_service import resolve_value


@pytest.mark.parametrize("kind,stored,value,status", [
    ("text", "001", "001", "EXACT"),
    ("text", "001", "1", "NOT_FOUND"),
    ("text", None, "None", "NOT_FOUND"),
    ("numeric", Decimal("1.25"), "1.250", "EXACT"),
    ("integer", 2, "2.5", "NOT_FOUND"),
    ("date", date(2026, 9, 10), "2026-09-10", "EXACT"),
    ("uuid", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA", "EXACT"),
    ("uuid", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "bad-uuid", "NOT_FOUND"),
])
def test_typed_reference_lookup_preserves_identity(kind, stored, value, status):
    record_id = str(uuid4())
    item = {
        "binding": SimpleNamespace(master_field="value", required=True),
        "definition": SimpleNamespace(fields=[SimpleNamespace(name="value", type=kind, pii_classification="NONE")],
                                      label_field="label"),
        "active": {record_id: {"_record_id": record_id, "value": stored, "label": None}}, "aliases": {},
    }
    result = resolve_value(item, value, SimpleNamespace(role="DATA_STEWARD"))
    assert result["status"] == status
    if status == "EXACT":
        assert result["record"]["_record_id"] == record_id
    else:
        assert result["requires_question"] and not result["candidates"]
