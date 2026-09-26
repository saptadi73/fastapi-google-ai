from typing import Literal

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

    @model_validator(mode="after")
    def validate_assignment(self):
        if self.model not in self.allowed_models:
            raise ValueError("model must be included in allowed_models")
        if self.prompt_version != PURPOSE_PROMPTS[self.purpose]:
            raise ValueError("prompt_version is not registered for purpose")
        if len(set(self.allowed_models)) != len(self.allowed_models):
            raise ValueError("allowed_models must be unique")
        return self


class AITaskPolicyAction(StrictModel):
    revision_no: int = Field(ge=1)
    comment: str = Field(default="", max_length=2000)
