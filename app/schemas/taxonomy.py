from pydantic import Field
from app.schemas.common import StrictModel


class TaxonomyCreate(StrictModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    name: str = Field(min_length=1, max_length=200)


class TaxonomyTermCreate(StrictModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    label: str = Field(min_length=1, max_length=200)
    parent_id: str | None = None
    aliases: list[str] = Field(default_factory=list, max_length=30)
