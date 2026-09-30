from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import StrictModel

PURPOSE_PROMPTS = {
    "ETL_CONFIG": "etl_configuration_v1.md",
    "TAXONOMY_RECOMMEND": "taxonomy_recommend_v1.md",
    "NL2SQL": "nl2sql_v1.md",
}


class AITaskPolicyCreate(StrictModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    purpose: Literal["ETL_CONFIG", "TAXONOMY_RECOMMEND", "NL2SQL"]
    prompt_version: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,79}$")
    model: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,99}$")
    allowed_models: list[str] = Field(min_length=1, max_length=20)
    data_product_code: str | None = Field(default=None, pattern=r"^[A-Za-z][A-Za-z0-9_]{0,62}$")
    data_source_id: UUID | None = None
    taxonomy_id: UUID | None = None
    max_context_chars: int = Field(default=200_000, ge=1_000, le=2_000_000)
    daily_budget_usd: float | None = Field(default=None, gt=0, le=1_000_000)
    fallback_model: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,99}$"
    )

    @model_validator(mode="after")
    def validate_assignment(self):
        if self.model not in self.allowed_models:
            raise ValueError("model must be included in allowed_models")
        if self.prompt_version != PURPOSE_PROMPTS[self.purpose]:
            raise ValueError("prompt_version is not registered for purpose")
        if len(set(self.allowed_models)) != len(self.allowed_models):
            raise ValueError("allowed_models must be unique")
        if self.data_product_code is not None and self.purpose != "NL2SQL":
            raise ValueError("data_product_code is only supported for NL2SQL")
        if self.data_source_id is not None and self.purpose != "ETL_CONFIG":
            raise ValueError("data_source_id is only supported for ETL_CONFIG")
        if self.taxonomy_id is not None and self.purpose != "TAXONOMY_RECOMMEND":
            raise ValueError("taxonomy_id is only supported for TAXONOMY_RECOMMEND")
        if self.fallback_model is not None:
            if self.fallback_model == self.model:
                raise ValueError("fallback_model must differ from model")
            if self.fallback_model not in self.allowed_models:
                raise ValueError("fallback_model must be included in allowed_models")
        return self


class AITaskPolicyUpdate(AITaskPolicyCreate):
    revision_no: int = Field(ge=1)


class AITaskPolicyAction(StrictModel):
    revision_no: int = Field(ge=1)
    comment: str = Field(default="", max_length=2000)
