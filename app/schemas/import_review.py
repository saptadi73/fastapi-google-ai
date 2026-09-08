from uuid import UUID

from pydantic import Field

from app.schemas.common import StrictModel


class ImportReviewCreate(StrictModel):
    source_sheet_id: UUID
    configuration_id: UUID | None = None


class ImportReviewAction(StrictModel):
    revision_no: int = Field(ge=1)
    comment: str = Field(default="", max_length=2000)
