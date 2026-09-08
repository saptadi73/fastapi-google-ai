from uuid import UUID

from pydantic import Field

from app.schemas.common import StrictModel
from app.schemas.master import MasterDefinitionCreate


class ImportReviewCreate(StrictModel):
    source_sheet_id: UUID
    configuration_id: UUID | None = None


class ImportReviewAction(StrictModel):
    revision_no: int = Field(ge=1)
    comment: str = Field(default="", max_length=2000)


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
