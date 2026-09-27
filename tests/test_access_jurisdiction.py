from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.access import AccessAttributeCreate, PermissionBundleCreate, UserAssignmentCreate


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
