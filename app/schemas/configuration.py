from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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


# Multipliers to the base unit within each dimension; never currency rates or aliases.
UNIT_DEFINITIONS = {
    "KG": ("mass", Decimal("1000")), "G": ("mass", Decimal("1")),
    "MG": ("mass", Decimal("0.001")), "T": ("mass", Decimal("1000000")),
    "L": ("volume", Decimal("1000")), "ML": ("volume", Decimal("1")),
    "M": ("length", Decimal("1000")), "CM": ("length", Decimal("10")),
    "MM": ("length", Decimal("1")),
}


class UnitConversion(StrictModel):
    from_unit: Literal["KG", "G", "MG", "T", "L", "ML", "M", "CM", "MM"]
    to_unit: Literal["KG", "G", "MG", "T", "L", "ML", "M", "CM", "MM"]
    factor: Decimal = Field(gt=0, max_digits=20, decimal_places=12, allow_inf_nan=False)
    output_scale: int = Field(ge=0, le=50)
    rounding: Literal["HALF_UP", "HALF_EVEN", "DOWN"]
    on_error: Literal["REJECT_ROW"] = "REJECT_ROW"

    @model_validator(mode="after")
    def valid_conversion(self):
        source_dimension, source_factor = UNIT_DEFINITIONS[self.from_unit]
        target_dimension, target_factor = UNIT_DEFINITIONS[self.to_unit]
        if source_dimension != target_dimension or self.from_unit == self.to_unit:
            raise ValueError("Conversion requires distinct units of the same dimension")
        if self.factor != source_factor / target_factor:
            raise ValueError("Conversion factor does not match the declared units")
        return self


CurrencyCode = Literal["IDR", "USD", "EUR", "SGD", "JPY", "THB"]


class CurrencyConversion(StrictModel):
    from_currency: CurrencyCode
    to_currency: CurrencyCode
    rate: Decimal = Field(gt=0, max_digits=30, decimal_places=18, allow_inf_nan=False)
    rate_date: date
    rate_reference: str = Field(min_length=1, max_length=500)
    output_scale: int = Field(ge=0, le=50)
    rounding: Literal["HALF_UP", "HALF_EVEN", "DOWN"]
    on_error: Literal["REJECT_ROW"] = "REJECT_ROW"

    @model_validator(mode="after")
    def valid_conversion(self):
        if self.from_currency == self.to_currency:
            raise ValueError("Currency conversion requires distinct currencies")
        if not self.rate_reference.strip():
            raise ValueError("Currency rate_reference must not be blank")
        return self


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
    numeric_precision: int | None = Field(default=None, ge=1, le=100)
    numeric_scale: int | None = Field(default=None, ge=0, le=50)
    date_format: str | None = Field(default=None, max_length=40)
    number_locale: str | None = Field(default=None, pattern=r"^(ID|US)$")
    varchar_length: int | None = Field(default=None, ge=1, le=10485760)
    unit_conversion: UnitConversion | None = None
    currency_conversion: CurrencyConversion | None = None
    source_timezone: str | None = Field(default=None, min_length=1, max_length=100)
    taxonomy_id: UUID | None = None
    taxonomy_version: int | None = Field(default=None, ge=1)
    taxonomy_required: bool = False

    @model_validator(mode="after")
    def valid_numeric_scale(self):
        if self.source_timezone is not None:
            if self.target_type != "timestamptz" or "parse_date_id" in self.transformation_codes:
                raise ValueError("source_timezone requires timestamptz without parse_date_id")
            try:
                ZoneInfo(self.source_timezone)
            except (ZoneInfoNotFoundError, ValueError):
                raise ValueError("source_timezone must be a known IANA timezone") from None
        if self.currency_conversion is not None:
            if self.unit_conversion is not None:
                raise ValueError("unit_conversion and currency_conversion cannot be combined")
            if self.target_type != "numeric" or self.is_business_key or self.is_primary_key:
                raise ValueError("currency_conversion requires a non-key numeric column")
            if self.numeric_precision is not None and (self.numeric_scale or 0) != self.currency_conversion.output_scale:
                raise ValueError("numeric_scale must equal currency conversion output_scale")
        if self.unit_conversion is not None:
            if self.target_type != "numeric" or self.is_business_key or self.is_primary_key:
                raise ValueError("unit_conversion requires a non-key numeric column")
            if self.numeric_precision is not None and (self.numeric_scale or 0) != self.unit_conversion.output_scale:
                raise ValueError("numeric_scale must equal unit conversion output_scale")
        if self.numeric_scale is not None and self.numeric_precision is None:
            raise ValueError("numeric_scale requires numeric_precision")
        if self.taxonomy_version is not None and self.taxonomy_id is None:
            raise ValueError("taxonomy_version memerlukan taxonomy_id")
        if self.taxonomy_required and self.taxonomy_id is None:
            raise ValueError("taxonomy_required memerlukan taxonomy_id")
        if (self.numeric_precision is not None or self.numeric_scale is not None) and self.target_type != "numeric":
            raise ValueError("numeric_precision/scale hanya berlaku untuk target numeric")
        if self.numeric_scale is not None and self.numeric_precision is not None and self.numeric_scale > self.numeric_precision:
            raise ValueError("numeric_scale tidak boleh melebihi numeric_precision")
        if self.date_format is not None and "parse_date_id" not in self.transformation_codes:
            raise ValueError("date_format memerlukan transform parse_date_id")
        if self.number_locale is not None and "parse_decimal_id" not in self.transformation_codes:
            raise ValueError("number_locale memerlukan transform parse_decimal_id")
        if self.varchar_length is not None and self.target_type not in ("text", "varchar"):
            raise ValueError("varchar_length hanya berlaku untuk target text/varchar")
        return self


class QualityRule(StrictModel):
    column: str
    rule: Literal["not_null", "unique", "min", "max", "allowed_values", "format", "max_age_days"]
    value: str | int | float | list[str] | None = None
    action_on_fail: Literal["REJECT_ROW", "WARN", "STOP_BATCH", "REQUIRE_REVIEW"] = "REJECT_ROW"
    severity: Literal["INFO", "WARN", "ERROR", "CRITICAL"] = "ERROR"
    owner: str | None = Field(default=None, max_length=100)
    threshold_percent: float | None = Field(default=None, ge=0, le=100)
    max_age_days: int | None = Field(default=None, ge=0, le=36500)
    default_value: str | int | float | bool | None = None

    @model_validator(mode="after")
    def valid_parameters(self):
        if self.rule == "format" and self.value not in ("UUID", "ISO_DATE", "ISO_DATETIME"):
            raise ValueError("format requires UUID, ISO_DATE, or ISO_DATETIME")
        if (self.rule == "max_age_days") != (self.max_age_days is not None):
            raise ValueError("max_age_days is required exclusively for rule max_age_days")
        return self


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
        defaults = {}
        for rule in self.data_quality_rules:
            if rule.column not in names:
                raise ValueError("DQ rule references an unknown column")
            column = next(c for c in self.columns if c.target_column == rule.column)
            if rule.rule == "max_age_days" and column.target_type not in ("date", "timestamp", "timestamptz"):
                raise ValueError("max_age_days requires a temporal column")
            if rule.default_value is not None:
                if rule.column in defaults and (type(defaults[rule.column]) is not type(rule.default_value) or defaults[rule.column] != rule.default_value):
                    raise ValueError("Conflicting default values for column")
                defaults[rule.column] = rule.default_value
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
