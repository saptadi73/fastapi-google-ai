from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import StrictModel

Identifier = str
PGType = Literal[
    "text", "varchar", "integer", "bigint", "numeric", "boolean", "date", "timestamp", "timestamptz", "uuid"
]
Transform = Literal[
    "trim",
    "normalize_whitespace",
    "parse_date_id",
    "parse_decimal_id",
    "uppercase",
    "lowercase",
    "null_if_empty",
]


class ColumnMapping(StrictModel):
    source_column: str = Field(min_length=1, max_length=200)
    target_column: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    target_type: PGType
    business_name: str = ""
    nullable: bool = True
    is_business_key: bool = False
    is_primary_key: bool = False
    transformation_codes: list[Transform] = Field(default_factory=list, max_length=10)
    pii_classification: Literal["NONE", "LOW", "MEDIUM", "HIGH"] = "NONE"
    confidence: float = Field(default=1, ge=0, le=1)
    reason: str = ""


class QualityRule(StrictModel):
    column: str
    rule: Literal["not_null", "unique", "min", "max", "allowed_values"]
    value: str | int | float | list[str] | None = None
    action_on_fail: Literal["REJECT_ROW", "WARN", "STOP_BATCH", "REQUIRE_REVIEW"] = "REJECT_ROW"


class MetricDefinition(StrictModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    column: str
    aggregation: Literal["sum", "count", "avg", "min", "max", "count_distinct"]
    label: str = ""


class SemanticDefinition(StrictModel):
    code: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,62}$")
    dimensions: list[str] = Field(default_factory=list)
    metrics: list[MetricDefinition] = Field(default_factory=list)
    allowed_roles: list[
        Literal["PLATFORM_ADMIN", "DATA_STEWARD", "SOURCE_OWNER", "TECHNICAL_APPROVER", "ANALYST", "VIEWER"]
    ] = ["PLATFORM_ADMIN", "DATA_STEWARD", "ANALYST", "VIEWER"]


class ETLConfiguration(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_business_name: str = Field(min_length=1, max_length=200)
    dataset_description: str = Field(default="", max_length=2000)
    grain: str = Field(min_length=1, max_length=500)
    target_schema: Literal["trusted"] = "trusted"
    target_table: str = Field(pattern=r"^[a-z][a-z0-9_]{0,29}$")
    load_strategy: Literal["APPEND", "UPSERT", "FULL_REFRESH"]
    columns: list[ColumnMapping] = Field(min_length=1, max_length=100)
    data_quality_rules: list[QualityRule] = Field(default_factory=list, max_length=100)
    semantic: SemanticDefinition
    unresolved_questions: list[str] = Field(default_factory=list)
    overall_confidence: float = Field(default=1, ge=0, le=1)

    @model_validator(mode="after")
    def valid_mapping(self):
        names = [c.target_column for c in self.columns]
        sources = [c.source_column for c in self.columns]
        if len(names) != len(set(names)) or len(sources) != len(set(sources)):
            raise ValueError("Source/target columns must be unique")
        keys = [c for c in self.columns if c.is_business_key or c.is_primary_key]
        if self.load_strategy == "UPSERT" and not keys:
            raise ValueError("UPSERT requires a business key")
        if any(c.nullable for c in keys):
            raise ValueError("Business keys cannot be nullable")
        public = {c.target_column: c for c in self.columns if c.pii_classification in ("NONE", "LOW")}
        if not set(self.semantic.dimensions).issubset(public):
            raise ValueError("Dimensions must reference non-sensitive mapped columns")
        metric_names = [m.code for m in self.semantic.metrics]
        if len(set(metric_names)) != len(metric_names) or set(metric_names) & set(names):
            raise ValueError("Metric codes must be unique and distinct from column names")
        for m in self.semantic.metrics:
            if m.column not in public:
                raise ValueError("Metrics must reference non-sensitive columns")
            if m.aggregation in ("sum", "avg") and public[m.column].target_type not in (
                "integer",
                "bigint",
                "numeric",
            ):
                raise ValueError("sum/avg require numeric columns")
        for rule in self.data_quality_rules:
            if rule.column not in names:
                raise ValueError("DQ rule references an unknown column")
            if rule.rule in ("min", "max") and not isinstance(rule.value, (int, float)):
                raise ValueError("min/max require a numeric value")
            if rule.rule == "allowed_values" and not isinstance(rule.value, list):
                raise ValueError("allowed_values requires a list")
        return self


class ConfigurationCreate(StrictModel):
    source_sheet_id: UUID
    configuration: ETLConfiguration


class ConfigurationPatch(StrictModel):
    revision_no: int = Field(ge=1)
    configuration: ETLConfiguration
    question_answers: dict[str, str] = Field(default_factory=dict, max_length=100)

    @model_validator(mode="after")
    def valid_answers(self):
        if any(
            not key.strip() or not value.strip() or len(value) > 2000
            for key, value in self.question_answers.items()
        ):
            raise ValueError("Jawaban pertanyaan wajib terisi dan maksimal 2000 karakter")
        return self


REVIEW_SECTIONS = ["identity", "columns", "cleansing", "quality", "load", "semantic"]


class ReviewSubmission(StrictModel):
    revision_no: int = Field(ge=1)
    snapshot_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewed_columns: list[str] = Field(min_length=1, max_length=100)
    reviewed_sections: list[Literal["identity", "columns", "cleansing", "quality", "load", "semantic"]]


class WorkbookPreviewRequest(StrictModel):
    content_base64: str = Field(min_length=1, max_length=2_800_000)


class WorkbookApplyRequest(ConfigurationPatch):
    preview_token: str = Field(min_length=1, max_length=8192)


class Decision(StrictModel):
    revision_no: int = Field(ge=1)
    comment: str = Field(default="", max_length=2000)


class ExportRequest(StrictModel):
    format: Literal["JSON", "YAML", "XLSX"] = "JSON"


class AIConfigurationRequest(StrictModel):
    source_sheet_id: UUID
