import pytest
from pydantic import ValidationError

from app.schemas.configuration import ColumnMapping, ETLConfiguration


MASTER_ID = "11111111-1111-4111-8111-111111111111"


def reference_column(**overrides):
    values = {
        "source_column": "Product name",
        "target_column": "product_id",
        "target_type": "uuid",
        "nullable": True,
        "master_reference": {
            "master_definition_id": MASTER_ID,
            "master_field": "label",
            "required": False,
        },
    }
    values.update(overrides)
    return ColumnMapping.model_validate(values)


def test_non_master_column_can_declare_optional_master_reference():
    column = reference_column()
    assert str(column.master_reference.master_definition_id) == MASTER_ID
    assert column.master_reference.required is False
    assert column.master_reference.cardinality == "MANY_TO_ONE"


@pytest.mark.parametrize(
    "overrides",
    [
        {"target_type": "text"},
        {"is_business_key": True},
        {"master_reference": {"master_definition_id": MASTER_ID, "master_field": "label", "required": True}},
        {"master_reference": {"master_definition_id": MASTER_ID, "master_field": "label", "aliases": {" A ": MASTER_ID, "a": MASTER_ID}}},
        {"master_reference": {"master_definition_id": MASTER_ID, "master_field": "label", "aliases": {"local": "not-a-uuid"}}},
    ],
)
def test_master_reference_rejects_unsafe_or_ambiguous_column_mapping(overrides):
    with pytest.raises(ValidationError):
        reference_column(**overrides)


def test_etl_configuration_round_trips_reference_mapping():
    payload = {
        "dataset_business_name": "Sales",
        "grain": "One row per sale",
        "target_table": "sales",
        "load_strategy": "UPSERT",
        "columns": [
            {
                "source_column": "Sale ID",
                "target_column": "sale_id",
                "target_type": "text",
                "nullable": False,
                "is_business_key": True,
            },
            {
                "source_column": "Product name",
                "target_column": "product_id",
                "target_type": "uuid",
                "master_reference": {
                    "master_definition_id": MASTER_ID,
                    "master_field": "label",
                    "required": False,
                    "aliases": {"legacy product": MASTER_ID},
                },
            }
        ],
        "semantic": {"code": "sales", "dimensions": [], "metrics": []},
    }
    parsed = ETLConfiguration.model_validate(payload)
    restored = ETLConfiguration.model_validate_json(parsed.model_dump_json())
    assert restored.columns[1].master_reference.aliases == {"legacy product": MASTER_ID}
