from uuid import UUID
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


class TaxonomyColumnBindingCreate(StrictModel):
    source_column: str = Field(min_length=1, max_length=200)
    taxonomy_id: UUID
    taxonomy_version: int = Field(ge=1)
    required: bool = False
    normalization: str = Field(default="TRIM_CASEFOLD", pattern=r"^[A-Z0-9_]{2,40}$")
    revision_no: int = Field(default=0, ge=0)


class TaxonomyTermResolveRequest(StrictModel):
    value: str = Field(min_length=1, max_length=500)


class TaxonomyAmbiguityQuestionRequest(TaxonomyTermResolveRequest):
    import_review_id: UUID
    staging_row_id: UUID | None = None
    source_column: str | None = Field(default=None, max_length=63)
    target_column: str | None = Field(default=None, max_length=63)


class TaxonomyValuesValidateRequest(StrictModel):
    values: list[str] = Field(min_length=1, max_length=10000)
    taxonomy_version: int | None = Field(default=None, ge=1)


class TaxonomyRecommendRequest(StrictModel):
    values: list[str] = Field(min_length=1, max_length=500)
    limit: int = Field(default=3, ge=1, le=10)
