from pydantic import Field

from app.schemas.common import StrictModel


class HelpQuestion(StrictModel):
    question: str = Field(min_length=3, max_length=2000)
    route: str | None = Field(default=None, max_length=300, pattern=r"^/[^\s]*$")


class HelpCitation(StrictModel):
    article_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    title: str = Field(min_length=1, max_length=200)


class HelpAnswer(StrictModel):
    answer: str = Field(min_length=1, max_length=8000)
    citations: list[HelpCitation] = Field(default_factory=list, max_length=8)
    suggested_questions: list[str] = Field(default_factory=list, max_length=4)
    insufficient_context: bool = False

