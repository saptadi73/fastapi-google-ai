import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.domain.enums import Role
from app.domain.import_workflow import ImportAction as A
from app.domain.import_workflow import ImportStatus as S
from app.domain.import_workflow import next_import_status
from app.schemas.data_policy import DatasetPolicy


def master_policy(**overrides):
    return {
        "classification_scope": "SHEET",
        "dataset_kind": "MASTER",
        "master": {
            "new_record_policy": "PROPOSE_INSERT",
            "source_conflict_policy": "REQUIRE_REVIEW",
            **overrides,
        },
    }


def test_explicit_business_choices_and_kind_consistency():
    with pytest.raises(ValidationError):
        DatasetPolicy(dataset_kind="MASTER")
    with pytest.raises(ValidationError):
        DatasetPolicy(classification_scope="SHEET", dataset_kind="MASTER", master={})
    with pytest.raises(ValidationError):
        DatasetPolicy(**{**master_policy(), "dataset_kind": "NON_MASTER"})
    policy = DatasetPolicy(**master_policy())
    assert policy.master.missing_record_policy == "KEEP"
    assert DatasetPolicy.model_validate_json(policy.model_dump_json()) == policy


def test_authoritative_source_is_required_and_not_implicit():
    with pytest.raises(ValidationError):
        DatasetPolicy(**master_policy(source_conflict_policy="AUTHORITATIVE_SOURCE"))
    with pytest.raises(ValidationError):
        DatasetPolicy(**master_policy(authoritative_source_sheet_id="11111111-1111-4111-8111-111111111111"))
    DatasetPolicy(
        **master_policy(
            source_conflict_policy="AUTHORITATIVE_SOURCE",
            authoritative_source_sheet_id="11111111-1111-4111-8111-111111111111",
        )
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("apply_mode", "PARTIAL"),
        ("mandatory_question_policy", "IGNORE"),
        ("ai_review_policy", "SKIP_ON_ERROR"),
    ],
)
def test_unsupported_bypass_policies_rejected(field, value):
    with pytest.raises(ValidationError):
        DatasetPolicy(**{**master_policy(), field: value})


def test_effective_dates_need_distinct_boundaries():
    with pytest.raises(ValidationError):
        DatasetPolicy(
            **master_policy(
                effective_dating={"valid_from_column": "valid_from", "valid_to_column": "valid_from"}
            )
        )


def test_workflow_requires_review_and_disallows_user_worker_actions():
    with pytest.raises(AppError) as error:
        next_import_status(S.VALIDATING, A.APPLY, role=Role.DATA_STEWARD)
    assert error.value.status_code == 409
    with pytest.raises(AppError) as error:
        next_import_status(S.APPLYING, A.COMPLETE, role=Role.PLATFORM_ADMIN)
    assert error.value.status_code == 403
    with pytest.raises(AppError):
        next_import_status(S.READY_FOR_APPROVAL, A.APPROVE, role=None)
    with pytest.raises(AppError):
        next_import_status(S.READY_FOR_APPROVAL, A.APPROVE, role=Role.SOURCE_OWNER)


def test_resume_revalidates_and_approval_becomes_stale():
    assert next_import_status(S.NEEDS_INPUT, A.RESUME, role=Role.DATA_STEWARD) == S.VALIDATING
    assert next_import_status(S.APPROVED, A.INVALIDATE, role=None) == S.STALE_REVIEW
    with pytest.raises(AppError):
        next_import_status(S.STALE_REVIEW, A.APPLY, role=Role.DATA_STEWARD)
    assert next_import_status(S.STALE_REVIEW, A.REVALIDATE, role=Role.DATA_STEWARD) == S.VALIDATING


def test_valid_lifecycle_and_terminal_states():
    state = S.CLASSIFICATION_REQUIRED
    for action, role in [
        (A.CLASSIFY, Role.SOURCE_OWNER),
        (A.SUBMIT_MAPPING, Role.DATA_STEWARD),
        (A.START_AI, None),
        (A.FINISH_REVIEW, None),
        (A.APPROVE, Role.TECHNICAL_APPROVER),
        (A.APPLY, Role.DATA_STEWARD),
        (A.COMPLETE, None),
    ]:
        state = next_import_status(state, action, role=role)
    assert state == S.SUCCEEDED
    for terminal in (S.SUCCEEDED, S.CANCELLED):
        with pytest.raises(AppError):
            next_import_status(terminal, A.REVALIDATE, role=Role.DATA_STEWARD)
