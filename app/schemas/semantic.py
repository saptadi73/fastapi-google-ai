from typing import Literal

from pydantic import Field, model_validator

from app.domain.enums import Role
from app.schemas.common import StrictModel


class QueryFilter(StrictModel):
    field: str = Field(max_length=63)
    operator: Literal["eq", "in", "between", "gte", "lte", "gt", "lt"]
    value: str | int | float | bool | list[str | int | float] | None

    @model_validator(mode="after")
    def valid_value(self):
        if self.operator in ("in", "between"):
            if not isinstance(self.value, list) or not 1 <= len(self.value) <= 100:
                raise ValueError("in/between require a non-empty list of at most 100 values")
            if self.operator == "between" and len(self.value) != 2:
                raise ValueError("between requires exactly two values")
        elif isinstance(self.value, list):
            raise ValueError("This operator requires a scalar")
        return self


class SortField(StrictModel):
    field: str
    direction: Literal["asc", "desc"] = "asc"


class QueryPlan(StrictModel):
    metrics: list[str] = Field(default_factory=list, max_length=20)
    dimensions: list[str] = Field(default_factory=list, max_length=20)
    filters: list[QueryFilter] = Field(default_factory=list, max_length=20)
    sort: list[SortField] = Field(default_factory=list, max_length=10)
    time_grain: Literal["none", "day", "week", "month", "quarter", "year"] = "none"
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0, le=100000)


class ProductUpdate(StrictModel):
    allowed_roles: list[Role] | None = None
    status: Literal["ACTIVE", "SUSPENDED"] | None = None


class SavedQueryCreate(StrictModel):
    code: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,62}$")
    data_product_code: str
    plan: QueryPlan
    examples: list[str] = Field(default_factory=list, max_length=50)
    allowed_roles: list[Role] = [Role.ANALYST, Role.VIEWER, Role.PLATFORM_ADMIN]
