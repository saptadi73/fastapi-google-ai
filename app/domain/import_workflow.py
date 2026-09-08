"""Import lifecycle used by durable BE-05 batches; approval/apply gates follow later."""

from enum import Enum

from app.core.exceptions import AppError
from app.domain.enums import EDIT_ROLES, REVIEW_ROLES, Role


class ImportStatus(str, Enum):
    CLASSIFICATION_REQUIRED = "CLASSIFICATION_REQUIRED"
    MAPPING_REQUIRED = "MAPPING_REQUIRED"
    VALIDATING = "VALIDATING"
    AI_REVIEWING = "AI_REVIEWING"
    NEEDS_INPUT = "NEEDS_INPUT"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    APPROVED = "APPROVED"
    APPLYING = "APPLYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    STALE_REVIEW = "STALE_REVIEW"


class ImportAction(str, Enum):
    CLASSIFY = "CLASSIFY"
    SUBMIT_MAPPING = "SUBMIT_MAPPING"
    REQUEST_INPUT = "REQUEST_INPUT"
    RESUME = "RESUME"
    START_AI = "START_AI"
    FINISH_REVIEW = "FINISH_REVIEW"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    APPLY = "APPLY"
    COMPLETE = "COMPLETE"
    FAIL = "FAIL"
    INVALIDATE = "INVALIDATE"
    REVALIDATE = "REVALIDATE"
    CANCEL = "CANCEL"


# Actions without a role entry are reserved for the worker, never a public role.
USER_ACTION_ROLES = {
    ImportAction.CLASSIFY: EDIT_ROLES,
    ImportAction.SUBMIT_MAPPING: EDIT_ROLES,
    ImportAction.RESUME: EDIT_ROLES,
    ImportAction.REVALIDATE: EDIT_ROLES,
    ImportAction.CANCEL: EDIT_ROLES,
    ImportAction.APPROVE: REVIEW_ROLES,
    ImportAction.REJECT: REVIEW_ROLES,
    ImportAction.APPLY: EDIT_ROLES,
}
S = ImportStatus
A = ImportAction
TRANSITIONS = {
    (S.CLASSIFICATION_REQUIRED, A.CLASSIFY): S.MAPPING_REQUIRED,
    (S.MAPPING_REQUIRED, A.SUBMIT_MAPPING): S.VALIDATING,
    (S.VALIDATING, A.START_AI): S.AI_REVIEWING,
    (S.VALIDATING, A.REQUEST_INPUT): S.NEEDS_INPUT,
    (S.AI_REVIEWING, A.REQUEST_INPUT): S.NEEDS_INPUT,
    (S.NEEDS_INPUT, A.RESUME): S.VALIDATING,
    (S.AI_REVIEWING, A.FINISH_REVIEW): S.READY_FOR_APPROVAL,
    (S.READY_FOR_APPROVAL, A.APPROVE): S.APPROVED,
    (S.READY_FOR_APPROVAL, A.REJECT): S.NEEDS_INPUT,
    (S.APPROVED, A.APPLY): S.APPLYING,
    (S.APPLYING, A.COMPLETE): S.SUCCEEDED,
    (S.STALE_REVIEW, A.REVALIDATE): S.VALIDATING,
    (S.FAILED, A.REVALIDATE): S.VALIDATING,
}
for state in (S.VALIDATING, S.AI_REVIEWING, S.APPLYING):
    TRANSITIONS[state, A.FAIL] = S.FAILED
for state in (S.VALIDATING, S.AI_REVIEWING, S.NEEDS_INPUT, S.READY_FOR_APPROVAL, S.APPROVED, S.FAILED):
    TRANSITIONS[state, A.INVALIDATE] = S.STALE_REVIEW
for state in S:
    if state not in (S.APPLYING, S.SUCCEEDED, S.CANCELLED):
        TRANSITIONS[state, A.CANCEL] = S.CANCELLED


def next_import_status(status: ImportStatus, action: ImportAction, *, role: Role | None) -> ImportStatus:
    """role=None is an internal worker context, not a request-supplied parameter.

    This checks only lifecycle and role. The service MUST additionally enforce
    tenant ownership, revisions, evidence coverage, mandatory questions, separate
    approver, and transactional locks before persisting any resulting status.
    """
    allowed_roles = USER_ACTION_ROLES.get(action)
    if (allowed_roles is None and role is not None) or (
        allowed_roles is not None and role not in allowed_roles
    ):
        raise AppError("IMPORT_ACTION_FORBIDDEN", "Peran tidak diizinkan menjalankan aksi import ini.", 403)
    target = TRANSITIONS.get((status, action))
    if target is None:
        raise AppError("IMPORT_STATE_CONFLICT", "Aksi tidak berlaku pada status import saat ini.", 409)
    return target
