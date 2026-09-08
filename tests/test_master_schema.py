import pytest
from pydantic import ValidationError

from app.schemas.master import MasterSchema


def test_master_key_label_and_period_validation():
    data = {
        "name": "Products",
        "fields": [{"name": "code", "type": "text", "nullable": False}],
        "business_key": ["code"],
        "label_field": "code",
        "policy": {"new_record_policy": "PROPOSE_INSERT", "source_conflict_policy": "REQUIRE_REVIEW"},
    }
    MasterSchema(**data)
    for changed in (
        {"business_key": ["missing"]},
        {"label_field": "missing"},
        {"business_key": ["code", "code"]},
        {"fields": [{"name": "code", "type": "text", "nullable": True}]},
        {
            "policy": {
                **data["policy"],
                "effective_dating": {"valid_from_column": "start_date", "valid_to_column": "end_date"},
            }
        },
    ):
        with pytest.raises(ValidationError):
            MasterSchema(**{**data, **changed})
