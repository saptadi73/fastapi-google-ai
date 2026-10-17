from pydantic import Field

from app.schemas.common import StrictModel
from app.schemas.semantic import QueryPlan


class QuestionRequest(StrictModel):
    question: str = Field(min_length=3, max_length=2000)
    data_product_code: str | None = None
    saved_query_code: str | None = None


class AIQueryPlan(StrictModel):
    data_product_code: str | None
    plan: QueryPlan | None
    clarification_required: bool
    clarification_question: str | None


class FeedbackRequest(StrictModel):
    feedback: str = Field(min_length=1, max_length=1000)


class SavedNL2SQLQueryCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    question: str = Field(min_length=3, max_length=2000)


class SavedNL2SQLQueryUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)

    def model_post_init(self, __context):
        if not self.model_fields_set:
            raise ValueError("At least one field must be updated")
        if any(value is None for value in self.model_dump(exclude_unset=True).values()):
            raise ValueError("Updated fields cannot be null")
