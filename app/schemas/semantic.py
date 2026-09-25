from typing import Annotated, Literal

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


class VisualizationSeries(StrictModel):
    field: str = Field(max_length=63)
    type: Literal["bar", "line", "area"] = "bar"
    axis: Literal["left", "right"] = "left"


class VisualizationSpec(StrictModel):
    type: Literal["table", "kpi", "bar", "line", "area", "pie", "donut", "combo", "scatter", "heatmap"]
    title: str = Field(default="", max_length=200)
    x_field: str | None = Field(default=None, max_length=63)
    y_field: str | None = Field(default=None, max_length=63)
    series: list[VisualizationSeries] = Field(default_factory=list, max_length=10)


class QueryPlan(StrictModel):
    metrics: list[str] = Field(default_factory=list, max_length=20)
    dimensions: list[str] = Field(default_factory=list, max_length=20)
    filters: list[QueryFilter] = Field(default_factory=list, max_length=20)
    sort: list[SortField] = Field(default_factory=list, max_length=10)
    time_grain: Literal["none", "day", "week", "month", "quarter", "year"] = "none"
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0, le=100000)
    visualization: VisualizationSpec | None = None

    @model_validator(mode="after")
    def valid_visualization(self):
        spec = self.visualization
        if spec is None:
            return self
        metric_fields = {item.field for item in spec.series}
        if len(metric_fields) != len(spec.series) or not metric_fields.issubset(self.metrics):
            raise ValueError("Visualization series must use unique selected metrics")
        if spec.x_field is not None and spec.x_field not in self.dimensions:
            raise ValueError("Visualization x_field must use a selected dimension")
        if spec.y_field is not None and spec.y_field not in self.dimensions:
            raise ValueError("Visualization y_field must use a selected dimension")
        if spec.type == "table":
            if spec.x_field is not None or spec.y_field is not None or spec.series:
                raise ValueError("Table visualization does not accept chart fields")
        elif spec.type == "kpi":
            if len(spec.series) != 1 or spec.x_field is not None or spec.y_field is not None:
                raise ValueError("KPI requires exactly one metric and no dimensions")
        elif spec.type in ("pie", "donut"):
            if len(spec.series) != 1 or spec.x_field is None or spec.y_field is not None:
                raise ValueError("Pie/donut require one metric and one dimension")
        elif spec.type in ("bar", "line", "area"):
            if not spec.series or spec.x_field is None or spec.y_field is not None:
                raise ValueError("Bar/line/area require metrics and one dimension")
        elif spec.type == "combo":
            if len(spec.series) < 2 or spec.x_field is None or spec.y_field is not None:
                raise ValueError("Combo requires at least two metrics and one dimension")
        elif spec.type == "scatter":
            if len(spec.series) != 2 or spec.x_field is not None or spec.y_field is not None:
                raise ValueError("Scatter requires exactly two metrics")
        elif spec.type == "heatmap":
            if (
                len(spec.series) != 1
                or spec.x_field is None
                or spec.y_field is None
                or spec.x_field == spec.y_field
            ):
                raise ValueError("Heatmap requires one metric and two distinct dimensions")
        return self


class MetricMetadataUpdate(StrictModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    unit: str | None = Field(default=None, max_length=40)
    synonyms: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def valid_metadata(self):
        if not ({"unit", "synonyms"} & self.model_fields_set):
            raise ValueError("Specify unit or synonyms")
        if self.unit is not None:
            self.unit = self.unit.strip() or None
        normalized = [" ".join(value.split()) for value in self.synonyms]
        if any(not value for value in normalized) or len({value.casefold() for value in normalized}) != len(normalized):
            raise ValueError("Synonyms must be nonblank and unique ignoring case")
        if "synonyms" in self.model_fields_set:
            self.synonyms = normalized
        return self


class ProductUpdate(StrictModel):
    allowed_roles: list[Role] | None = None
    status: Literal["ACTIVE", "SUSPENDED"] | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    expected_version: int | None = Field(default=None, ge=1)
    metric_metadata: list[MetricMetadataUpdate] | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def metadata_version(self):
        if {"name", "description", "metric_metadata"} & self.model_fields_set:
            if self.expected_version is None:
                raise ValueError("Metadata edits require expected_version")
            if "name" in self.model_fields_set:
                if self.name is None or not self.name.strip():
                    raise ValueError("Product name must not be blank")
                self.name = self.name.strip()
            if "description" in self.model_fields_set and self.description is None:
                raise ValueError("Use an empty string to clear description")
            if "metric_metadata" in self.model_fields_set:
                if self.metric_metadata is None:
                    raise ValueError("metric_metadata must be a non-empty list")
                codes = [item.code for item in self.metric_metadata]
                if len(set(codes)) != len(codes):
                    raise ValueError("Metric codes must be unique")
        return self


class SavedQueryCreate(StrictModel):
    code: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,62}$")
    data_product_code: str
    plan: QueryPlan
    examples: list[str] = Field(default_factory=list, max_length=50)
    allowed_roles: list[Role] = [Role.ANALYST, Role.VIEWER, Role.PLATFORM_ADMIN]
