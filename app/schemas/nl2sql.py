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
