from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from app.schemas.common import StrictModel
from app.schemas.semantic import QueryPlan

Code = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")]


class AnalyticsFormula(StrictModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    formula_code: Code
    expression: str = Field(min_length=1, max_length=500)
    output_unit: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=500)


class ActionPlanRule(StrictModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    rule_code: Code
    formula_code: Code
    operator: Literal["gt", "gte", "lt", "lte", "eq", "between"]
    threshold: Decimal = Field(allow_inf_nan=False, ge=Decimal("-1e30"), le=Decimal("1e30"))
    threshold_upper: Decimal | None = Field(
        default=None, allow_inf_nan=False, ge=Decimal("-1e30"), le=Decimal("1e30")
    )
    action_description: str = Field(min_length=1, max_length=1000)
    owner_team_code: str = Field(min_length=1, max_length=63)
    priority: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    due_days: int = Field(default=7, ge=1, le=365)

    @model_validator(mode="after")
    def bounds(self):
        if self.operator == "between":
            if self.threshold_upper is None or self.threshold_upper < self.threshold:
                raise ValueError("between memerlukan threshold_upper >= threshold")
        elif self.threshold_upper is not None:
            raise ValueError("threshold_upper hanya untuk between")
        return self


class AnalyticsRuleDefinition(StrictModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    product_code: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,62}$")
    query: QueryPlan
    formulas: list[AnalyticsFormula] = Field(min_length=1, max_length=20)
    rules: list[ActionPlanRule] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def valid(self):
        if not self.query.metrics or self.query.join_relationships or self.query.offset or self.query.sort:
            raise ValueError("Pilih metrik satu produk, tanpa join, offset, atau sort")
        if set(self.query.metrics) & set(self.query.dimensions):
            raise ValueError("Nama metrik dan dimension harus berbeda")
        codes = [f.formula_code for f in self.formulas]
        if len(set(codes)) != len(codes) or set(codes) & set(self.query.metrics + self.query.dimensions):
            raise ValueError("Kode formula harus unik dan berbeda dari field query")
        if len({r.rule_code for r in self.rules}) != len(self.rules):
            raise ValueError("Kode aturan harus unik")
        if any(r.formula_code not in codes for r in self.rules):
            raise ValueError("Aturan harus merujuk formula yang tersedia")
        from app.services.analytics_expression_service import validate_formulas

        validate_formulas(self.formulas, self.query.metrics)
        return self


class AnalyticsRulesImport(StrictModel):
    source_id: UUID
    name: str = Field(min_length=1, max_length=200)
    product_code: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,62}$")
    query: QueryPlan


class AnalyticsRulesDecision(StrictModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    expected_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: Literal["APPROVE", "REJECT", "REVOKE"]
    reason: str = Field(min_length=1, max_length=1000)
