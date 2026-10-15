from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas.configuration import ETLConfiguration
from app.services.etl_compiler_service import transform_rows
from app.services.reference_service import validate_reference_rows
from app.services.schema_compiler_service import compile_table


def setup_reference(required=False, cardinality="MANY_TO_ONE", pii="LOW"):
    master_id, record_id = str(uuid4()), str(uuid4())
    config = ETLConfiguration.model_validate({
        "dataset_business_name": "Business targets", "grain": "One row per business",
        "target_table": "business_targets", "load_strategy": "APPEND",
        "columns": [{"source_column": "BISNIS", "target_column": "bisnis", "target_type": "text",
                     "master_reference": {"master_definition_id": master_id, "master_field": "code",
                                          "required": required, "cardinality": cardinality}}],
        "semantic": {"code": "business_targets", "dimensions": ["bisnis"], "metrics": []},
    })
    item = {
        "binding": SimpleNamespace(master_field="code", required=required, cardinality=cardinality),
        "definition": SimpleNamespace(fields=[SimpleNamespace(name="code", type="text", pii_classification=pii)], label_field="code"),
        "active": {record_id: {"_record_id": record_id, "code": "BC06"}}, "aliases": {},
        "user": SimpleNamespace(role="SOURCE_OWNER"), "column": config.columns[0],
    }
    return config, {"BISNIS": item}, record_id


def transform(values, config, context):
    return transform_rows([["BISNIS"], *[[v] for v in values]],
                          SimpleNamespace(header_row=1, data_start_row=2), config, references=context)


def test_text_source_is_preserved_while_master_identity_is_resolved():
    config, context, identity = setup_reference()
    good, issues, _ = transform([" BC06 "], config, context)
    assert issues == []
    assert good == [(2, {"bisnis": "BC06", "_ref_bisnis": identity})]
    table = compile_table(config, uuid4())
    assert table.c.bisnis.type.__class__.__name__ == "Text"
    assert table.c._ref_bisnis.type.__class__.__name__ == "Uuid"
    assert table.c._ref_bisnis.nullable  # Safe addition alongside historical data.


@pytest.mark.parametrize("value,required,code", [
    ("missing", False, "REFERENCE_NOT_FOUND"),
    ("", True, "REFERENCE_NOT_FOUND"),
])
def test_unmatched_reference_never_silently_loads(value, required, code):
    config, context, _ = setup_reference(required=required)
    good, issues, _ = transform([value], config, context)
    # Empty rows are intentionally ignored; use a present second field for the
    # required-empty scenario as in a real business dataset.
    if value == "":
        config.columns.append(config.columns[0].model_copy(update={"source_column": "ID", "target_column": "id", "master_reference": None}))
        good, issues, _ = transform_rows([["BISNIS", "ID"], ["", "1"]],
            SimpleNamespace(header_row=1, data_start_row=2), config, references=context)
    assert good == []
    assert issues[0]["errors"][0]["code"] == code


def test_ambiguity_and_cardinality_block_without_guessing_a_record():
    config, context, _ = setup_reference(cardinality="ONE_TO_ONE")
    good, issues, _ = transform(["BC06", "bc06"], config, context)
    assert len(good) == 1
    assert issues[0]["errors"][0]["code"] == "REFERENCE_CARDINALITY_CONFLICT"
    second = str(uuid4())
    context["BISNIS"]["active"][second] = {"_record_id": second, "code": "bc06"}
    good, issues, _ = transform(["BC06"], config, context)
    assert not good
    assert issues[0]["errors"][0]["code"] == "REFERENCE_AMBIGUOUS"


def test_missing_context_blocks_but_does_not_cast_source_label_as_uuid():
    config, _, _ = setup_reference()
    good, issues, _ = transform(["BC06"], config, None)
    assert not good
    assert issues[0]["errors"][0]["code"] == "REFERENCE_CONTEXT_REQUIRED"


def test_final_check_recomputes_identity_from_human_value_instead_of_trusting_staging():
    config, context, identity = setup_reference()
    row = SimpleNamespace(source_row=2, transformed_data={"bisnis": "BC06", "_ref_bisnis": str(uuid4())}, corrected_data={})
    validate_reference_rows(context, [row])
    assert row.corrected_data["_ref_bisnis"] == identity
    assert row.transformed_data["bisnis"] == "BC06"


def test_sensitive_master_lookup_stays_forbidden():
    from app.core.exceptions import AppError

    config, context, _ = setup_reference(pii="HIGH")
    with pytest.raises(AppError, match="field master sensitif"):
        transform(["BC06"], config, context)


def test_detached_mapping_retains_internal_storage_without_looking_up_master():
    config, _, _ = setup_reference()
    before = compile_table(config, uuid4())
    column = config.columns[0]
    column.master_reference = None
    column.master_reference_disabled = True
    restored = ETLConfiguration.model_validate_json(config.model_dump_json())
    assert restored.columns[0].master_reference_disabled
    after = compile_table(restored, uuid4())
    assert list(before.c.keys()) == list(after.c.keys())
    good, issues, _ = transform(["A business outside the master"], restored, {})
    assert issues == []
    assert good[0][1] == {"bisnis": "A business outside the master", "_ref_bisnis": None}


def test_disabled_and_enabled_reference_cannot_be_submitted_together():
    from pydantic import ValidationError

    config, _, _ = setup_reference()
    data = config.model_dump(mode="json")
    data["columns"][0]["master_reference_disabled"] = True
    with pytest.raises(ValidationError):
        ETLConfiguration.model_validate(data)
