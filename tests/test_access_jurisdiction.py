from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.access import (
    AccessAttributeCreate,
    AccessRequestCreate,
    PermissionBundleCreate,
    UserAssignmentCreate,
)


def test_access_attribute_and_assignment_contracts():
    attribute = AccessAttributeCreate(kind="DEPARTMENT", code="finance.id", label="Finance")
    assert attribute.kind == "DEPARTMENT"
    with pytest.raises(ValidationError):
        AccessAttributeCreate(kind="TEAM", code="finance", label="Finance")
    with pytest.raises(ValidationError):
        UserAssignmentCreate(
            attribute_id="11111111-1111-4111-8111-111111111111",
            valid_from=datetime(2027, 1, 1, tzinfo=timezone.utc),
            valid_to=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    bundle = PermissionBundleCreate(code="exporter", label="Exporter", actions=["QUERY", "EXPORT"])
    assert bundle.actions == ["QUERY", "EXPORT"]
    with pytest.raises(ValidationError):
        PermissionBundleCreate(code="duplicate", label="Duplicate", actions=["QUERY", "QUERY"])


def test_access_request_requires_one_target_and_bounded_period():
    request = AccessRequestCreate(
        request_type="ATTRIBUTE",
        attribute_id="11111111-1111-4111-8111-111111111111",
        valid_from=datetime(2026, 10, 1, tzinfo=timezone.utc),
        valid_to=datetime(2027, 1, 1, tzinfo=timezone.utc),
        business_reason="Membutuhkan laporan finance triwulan.",
    )
    assert request.bundle_id is None
    with pytest.raises(ValidationError):
        AccessRequestCreate(
            request_type="ATTRIBUTE",
            attribute_id="11111111-1111-4111-8111-111111111111",
            bundle_id="22222222-2222-4222-8222-222222222222",
            valid_to=datetime(2027, 1, 1, tzinfo=timezone.utc),
            business_reason="Target tidak boleh ganda.",
        )
    with pytest.raises(ValidationError):
        AccessRequestCreate(
            request_type="PERMISSION_BUNDLE",
            bundle_id="22222222-2222-4222-8222-222222222222",
            valid_from=datetime(2026, 10, 1, tzinfo=timezone.utc),
            valid_to=datetime(2028, 1, 1, tzinfo=timezone.utc),
            business_reason="Periode ini melewati batas maksimum.",
        )
