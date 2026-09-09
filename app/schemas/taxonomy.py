from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import StrictModel


class TaxonomyCreate(StrictModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    name: str = Field(min_length=1, max_length=200)


class TaxonomyTermCreate(StrictModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    label: str = Field(min_length=1, max_length=200)
    parent_id: UUID | None = None
    aliases: list[str] = Field(default_factory=list, max_length=30)


class TaxonomyColumnBindingCreate(StrictModel):
    source_column: str = Field(min_length=1, max_length=200)
    taxonomy_id: UUID
    taxonomy_version: int = Field(ge=1)
    required: bool = False
    normalization: Literal["TRIM_CASEFOLD"] = "TRIM_CASEFOLD"
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


class TaxonomyVersionCreate(StrictModel):
    base_version: int = Field(ge=1)


class TaxonomyVersionTerm(TaxonomyTermCreate):
    id: UUID
    is_active: bool = True


class TaxonomyVersionUpdate(StrictModel):
    revision_no: int = Field(ge=1)
    terms: list[TaxonomyVersionTerm] = Field(max_length=2000)

    @model_validator(mode="after")
    def valid_tree(self):
        terms = {term.id: term for term in self.terms}
        if len(terms) != len(self.terms) or len({t.code for t in self.terms}) != len(self.terms):
            raise ValueError("Term IDs and codes must be unique")
        for term in self.terms:
            if not term.label.strip() or any(not alias.strip() for alias in term.aliases):
                raise ValueError("Labels and aliases must not be blank")
            seen, current = set(), term
            while current.parent_id is not None:
                if current.id in seen or current.parent_id not in terms:
                    raise ValueError("Hierarchy must be acyclic with parents in this version")
                seen.add(current.id)
                current = terms[current.parent_id]
                if term.is_active and not current.is_active:
                    raise ValueError("Active terms require active ancestors")
        return self
