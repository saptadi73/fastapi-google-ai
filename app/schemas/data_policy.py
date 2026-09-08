"""Versioned contracts for the master/import workflow (wired to APIs in BE-02 onward)."""

from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import StrictModel


class DatasetKind(str, Enum):
    MASTER = "MASTER"
    NON_MASTER = "NON_MASTER"


class ClassificationScope(str, Enum):
    SHEET = "SHEET"


class NewMasterRecordPolicy(str, Enum):
    UPDATE_ONLY = "UPDATE_ONLY"
    PROPOSE_INSERT = "PROPOSE_INSERT"


class SourceConflictPolicy(str, Enum):
    REQUIRE_REVIEW = "REQUIRE_REVIEW"
    AUTHORITATIVE_SOURCE = "AUTHORITATIVE_SOURCE"


class EffectiveDating(StrictModel):
    valid_from_column: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    valid_to_column: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    interval: Literal["START_INCLUSIVE_END_EXCLUSIVE"] = "START_INCLUSIVE_END_EXCLUSIVE"
    overlap_policy: Literal["REJECT"] = "REJECT"

    @model_validator(mode="after")
    def distinct_columns(self):
        if self.valid_from_column == self.valid_to_column:
            raise ValueError("Kolom awal dan akhir masa berlaku harus berbeda")
        return self


class MasterImportPolicy(StrictModel):
    # Explicit fields record the policy approved for this master.
    new_record_policy: NewMasterRecordPolicy
    source_conflict_policy: SourceConflictPolicy
    authoritative_source_sheet_id: UUID | None = None
    missing_record_policy: Literal["KEEP"] = "KEEP"
    deactivation_policy: Literal["EXPLICIT_REVIEW"] = "EXPLICIT_REVIEW"
    business_key_change_policy: Literal["EXPLICIT_MIGRATION"] = "EXPLICIT_MIGRATION"
    delete_referenced_policy: Literal["RESTRICT"] = "RESTRICT"
    effective_dating: EffectiveDating | None = None

    @model_validator(mode="after")
    def authority_matches_policy(self):
        needs_source = self.source_conflict_policy == SourceConflictPolicy.AUTHORITATIVE_SOURCE
        if needs_source != (self.authoritative_source_sheet_id is not None):
            raise ValueError("Sumber otoritatif wajib dan hanya boleh diisi pada AUTHORITATIVE_SOURCE")
        return self


class DatasetPolicy(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    classification_scope: ClassificationScope
    dataset_kind: DatasetKind
    master: MasterImportPolicy | None = None
    apply_mode: Literal["ATOMIC_BATCH"] = "ATOMIC_BATCH"
    mandatory_question_policy: Literal["BLOCK_APPLY"] = "BLOCK_APPLY"
    ai_review_policy: Literal["REQUIRED_FOR_ALLOWED_FIELDS"] = "REQUIRED_FOR_ALLOWED_FIELDS"

    @model_validator(mode="after")
    def master_policy_matches_kind(self):
        if (self.dataset_kind == DatasetKind.MASTER) != (self.master is not None):
            raise ValueError("Policy master wajib untuk MASTER dan tidak berlaku untuk NON_MASTER")
        return self
