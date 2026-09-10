from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import StrictModel
from app.schemas.master import MasterDefinitionCreate


class ImportReviewCreate(StrictModel):
    source_sheet_id: UUID
    configuration_id: UUID | None = None


class ImportReviewAction(StrictModel):
    revision_no: int = Field(ge=1)
    comment: str = Field(default="", max_length=2000)


class ImportReviewPreviewRequest(StrictModel):
    revision_no: int = Field(ge=1)
    close_open_periods: bool = False


class ImportReviewApproveRequest(StrictModel):
    revision_no: int = Field(ge=1)
    comment: str = Field(default="", max_length=2000)
    preview_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    accept_source_conflicts: bool = False


class ImportReviewApplyRequest(StrictModel):
    revision_no: int = Field(ge=1)
    preview_token: str


class ImportReferenceResolveRequest(StrictModel):
    revision_no: int = Field(ge=1)
    master_definition_id: UUID
    value: str = Field(max_length=500)
    source_column: str = Field(min_length=1, max_length=200)
    staging_row_id: UUID | None = None
    target_column: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,62}$")

    @model_validator(mode="after")
    def staging_target_pair(self):
        if (self.staging_row_id is None) != (self.target_column is None):
            raise ValueError("staging_row_id dan target_column harus dikirim bersama")
        return self


class AIImportReviewResult(StrictModel):
    issues: list[dict] = Field(default_factory=list, max_length=500)
    reviewed_rows: list[int] = Field(default_factory=list, max_length=10000)
    coverage: str = Field(pattern=r"^(COMPLETE|PARTIAL)$")


class ImportQuestionDecision(StrictModel):
    revision_no: int = Field(ge=1)
    action: str = Field(
        pattern=r"^(KEEP_ORIGINAL|APPLY_CORRECTION|CORRECT_SOURCE|SELECT_RECORD|PROPOSE_MASTER)$"
    )
    selected_candidate_id: UUID | None = None
    corrected_value: int | float | bool | str | None = None
    reason: str = Field(default="", max_length=2000)
    master_proposal: MasterDefinitionCreate | None = None


class ImportProposalResolution(StrictModel):
    revision_no: int = Field(ge=1)
    master_definition_id: UUID
