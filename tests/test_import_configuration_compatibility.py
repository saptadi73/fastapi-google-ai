from copy import deepcopy

import pytest

from app.services.import_review_service import ImportReviewService


def test_only_inert_reference_defaults_preserve_legacy_hash():
    pinned = {"columns": [{"source_column": "Bisnis", "target_type": "text"}]}
    current = deepcopy(pinned)
    current["columns"][0].update(master_reference=None, master_reference_disabled=False)
    assert ImportReviewService.compatible_configuration_hash(pinned, current)
    assert "master_reference" in current["columns"][0]


@pytest.mark.parametrize("change", ["detach", "reference", "type", "nullable", "other_default", "remove_field"])
def test_real_changes_are_not_legacy_defaults(change):
    pinned = {"columns": [{"source_column": "Bisnis", "target_type": "text", "nullable": False}]}
    current = deepcopy(pinned)
    current["columns"][0].update(master_reference=None, master_reference_disabled=False)
    column = current["columns"][0]
    if change == "detach":
        column["master_reference_disabled"] = True
    elif change == "reference":
        column["master_reference"] = {"master_definition_id": "different-master"}
    elif change == "type":
        column["target_type"] = "uuid"
    elif change == "nullable":
        column["nullable"] = True
    elif change == "other_default":
        column["unknown_policy"] = False
    else:
        del column["nullable"]
    assert not ImportReviewService.compatible_configuration_hash(pinned, current)
