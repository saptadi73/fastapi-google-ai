from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from pydantic import ValidationError

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.analytics_rules import AnalyticsRuleBundle
from app.models.source import DataSource, SourceSheet
from app.repositories.base import TenantRepository, record
from app.schemas.analytics_rules import AnalyticsRuleDefinition
from app.services.analytics_expression_service import calculate
from app.services.audit_service import audit
from app.services.etl_compiler_service import cast_value
from app.services.google_sheets_service import GoogleSheetsService
from app.services.profiling_service import digest
from app.services.query_execution_service import QueryExecutionService
from app.services.source_approver_service import require_source_approver
from app.services.workflow_policy_service import require_source_manager

FORMULA_HEADERS = ["formula_code", "expression", "output_unit", "description"]
RULE_HEADERS = [
    "rule_code",
    "formula_code",
    "operator",
    "threshold",
    "threshold_upper",
    "action_description",
    "owner_team_code",
    "priority",
    "due_days",
]


def table_records(values, headers):
    if not values or [str(v).strip() for v in values[0]] != headers:
        raise AppError("ANALYTICS_RULES_INVALID", "Header tab aturan/formula tidak sesuai template.", 422)
    records = []
    for row in values[1:]:
        if not any(value not in (None, "") for value in row):
            continue
        if len(row) > len(headers):
            raise AppError("ANALYTICS_RULES_INVALID", "Kolom tambahan tidak dikenali.", 422)
        normalized = [v.strip() if isinstance(v, str) else v for v in row]
        records.append({key: value for key, value in zip(headers, normalized) if value not in (None, "")})
    return records


def definition_from_tables(request, tables):
    try:
        return AnalyticsRuleDefinition(
            name=request.name,
            product_code=request.product_code,
            query=request.query,
            formulas=table_records(tables[0], FORMULA_HEADERS),
            rules=table_records(tables[1], RULE_HEADERS),
        )
    except ValidationError:
        raise AppError(
            "ANALYTICS_RULES_INVALID",
            "Periksa kode, formula, operator, ambang dan pemilik pada tab kontrol.",
            422,
        ) from None


def semantic_hash(product):
    return digest([product.id, product.version, product.columns, product.metrics, product.dimensions])


def evaluate_rows(definition, rows, *, today=None):
    today = today or datetime.now(timezone.utc).date()
    results = []
    for row in rows:
        values = {code: row.get(code) for code in definition.query.metrics}
        calculations, actions = [], []
        for formula in definition.formulas:
            number, blocker = calculate(formula.expression, values)
            values[formula.formula_code] = number
            calculations.append(
                {
                    "formula_code": formula.formula_code,
                    "expression": formula.expression,
                    "value": str(number) if number is not None else None,
                    "unit": formula.output_unit,
                    "blocker": blocker,
                }
            )
        for rule in definition.rules:
            number = values[rule.formula_code]
            if number is None:
                continue
            matched = {
                "gt": lambda: number > rule.threshold,
                "gte": lambda: number >= rule.threshold,
                "lt": lambda: number < rule.threshold,
                "lte": lambda: number <= rule.threshold,
                "eq": lambda: number == rule.threshold,
                "between": lambda: rule.threshold <= number <= rule.threshold_upper,
            }[rule.operator]()
            if matched:
                actions.append(
                    {
                        **rule.model_dump(mode="json"),
                        "observed_value": str(number),
                        "due_date": (today + timedelta(days=rule.due_days)).isoformat(),
                        "status": "PROPOSED",
                        "cause_status": "UNVERIFIED",
                    }
                )
        results.append(
            {
                "dimensions": {code: row.get(code) for code in definition.query.dimensions},
                "evidence_metrics": {code: row.get(code) for code in definition.query.metrics},
                "formulas": calculations,
                "action_plans": actions,
            }
        )
    return results


class AnalyticsRulesService:
    def __init__(self, session, user, google=None):
        self.session, self.user = session, user
        self.repo = TenantRepository(session, user.tenant_id)
        self.queries = QueryExecutionService(session, user)
        self.google = google or GoogleSheetsService()

    async def read_tables(self, source):
        if source.paused or source.unlinked_at is not None:
            raise AppError(
                "ANALYTICS_RULES_STALE",
                "Sumber aturan tidak aktif; gunakan sumber aktif dan review ulang.",
                409,
            )
        metadata = await self.google.metadata(source.spreadsheet_id)
        properties = {s["properties"]["title"]: s["properties"] for s in metadata.get("sheets", [])}
        sheets = []
        for name in ("Formula_Analitik", "Aturan_Action_Plan"):
            props = properties.get(name)
            if not props or props.get("sheetType") != "GRID":
                raise AppError(
                    "ANALYTICS_RULES_INVALID",
                    "Kedua tab kontrol GRID harus tersedia sesuai nama template.",
                    422,
                )
            count = props.get("gridProperties", {}).get("columnCount", 0)
            if not isinstance(count, int) or not 1 <= count <= 18278:
                raise AppError("ANALYTICS_RULES_INVALID", "Ukuran tab kontrol tidak valid.", 422)
            letters = ""
            while count:
                count, remainder = divmod(count - 1, 26)
                letters = chr(65 + remainder) + letters
            # Include all allocated columns so unsupported extra headers are not silently discarded.
            sheets.append(SimpleNamespace(sheet_name=name, range_a1="A:" + letters))
        return await self.google.read_sheets(source.spreadsheet_id, sheets)

    async def validate_product(self, definition):
        product, *_ = await self.queries.compile(definition.product_code, definition.query)
        columns = {c["target_column"]: c for c in product.columns}
        period_filters = [
            f
            for f in definition.query.filters
            if f.operator == "between"
            and columns[f.field]["target_type"] in ("date", "timestamp", "timestamptz")
        ]
        if not period_filters:
            raise AppError(
                "ANALYTICS_PERIOD_REQUIRED",
                "Gunakan filter between dengan awal/akhir periode waktu eksplisit.",
                422,
            )
        for period in period_filters:
            kind = columns[period.field]["target_type"]
            start, end = (cast_value(value, kind) for value in period.value)
            if start is None or end is None or start > end:
                raise AppError("ANALYTICS_PERIOD_REQUIRED", "Urutan awal/akhir periode tidak valid.", 422)
        metrics = {m["code"]: m for m in product.metrics}
        if any(
            metrics[code]["aggregation"] not in ("count", "count_distinct")
            and columns[metrics[code]["column"]]["target_type"] not in ("numeric", "integer", "bigint")
            for code in definition.query.metrics
        ):
            raise AppError("ANALYTICS_RULES_INVALID", "Formula memerlukan metrik numerik.", 422)
        return product

    async def create(self, definition, *, source=None, tables=None):
        product = await self.validate_product(definition)
        sheet = await self.repo.get(SourceSheet, product.source_sheet_id)
        if get_settings().etl_owner_workflow_enabled:
            await require_source_manager(self.session, self.user, sheet.source_id)
        if source is not None and sheet.source_id != source.id:
            raise AppError(
                "ANALYTICS_RULES_INVALID",
                "Tab kontrol harus berasal dari sumber data product yang sama.",
                422,
            )
        data = definition.model_dump(mode="json")
        contract_hash = semantic_hash(product)
        sheet_hash = digest(tables) if tables is not None else None
        review_hash = digest([data, contract_hash, sheet_hash])
        bundle = await self.repo.add(
            AnalyticsRuleBundle,
            product_id=product.id,
            source_id=source.id if source else None,
            created_by=self.user.id,
            definition=data,
            semantic_hash=contract_hash,
            sheet_hash=sheet_hash,
            review_hash=review_hash,
        )
        audit(self.session, self.user, "analytics_rules.drafted", bundle.id, review_hash=review_hash)
        return record(bundle)

    async def import_sheet(self, request):
        # Authorize product AND verify source identity before using service-account access.
        product = await self.queries.repo.product(request.product_code, self.user)
        sheet = await self.repo.get(SourceSheet, product.source_sheet_id)
        if str(request.source_id) != sheet.source_id:
            raise AppError("ANALYTICS_RULES_INVALID", "Sumber tidak sesuai data product.", 422)
        source = await self.repo.get(DataSource, request.source_id)
        tables = await self.read_tables(source)
        definition = definition_from_tables(request, tables)
        return await self.create(definition, source=source, tables=tables)

    async def get(self, bundle_id, *, lock=False):
        bundle = await self.repo.get(AnalyticsRuleBundle, bundle_id, lock=lock)
        definition = AnalyticsRuleDefinition.model_validate(bundle.definition)
        await self.validate_product(definition)
        return bundle, definition

    async def assert_current(self, bundle, definition):
        product = await self.validate_product(definition)
        # Hold the semantic contract stable until this request commits. ETL/metadata
        # updates to the product wait rather than changing a reviewed query mid-run.
        await self.session.refresh(product, with_for_update=True)
        if product.id != bundle.product_id or semantic_hash(product) != bundle.semantic_hash:
            raise AppError(
                "ANALYTICS_RULES_STALE", "Definisi semantic berubah; impor/buat draft dan review ulang.", 409
            )
        if bundle.source_id:
            source = await self.repo.get(DataSource, bundle.source_id)
            if digest(await self.read_tables(source)) != bundle.sheet_hash:
                raise AppError(
                    "ANALYTICS_RULES_STALE", "Tab formula/aturan berubah; impor dan review ulang.", 409
                )
        return product

    async def decide(self, bundle_id, decision):
        bundle, definition = await self.get(bundle_id, lock=True)
        product = await self.queries.repo.product(definition.product_code, self.user)
        sheet = await self.repo.get(SourceSheet, product.source_sheet_id)
        await require_source_approver(self.session, self.user, sheet.source_id, "configuration")
        if bundle.created_by == self.user.id and not get_settings().etl_owner_workflow_enabled:
            raise AppError("ANALYTICS_SELF_APPROVAL", "Reviewer harus berbeda dari pembuat draft.", 403)
        expected_status = "APPROVED" if decision.decision == "REVOKE" else "DRAFT"
        if bundle.status != expected_status or decision.expected_hash != bundle.review_hash:
            raise AppError("ANALYTICS_RULES_STALE", "Draft/status berubah; muat ulang review.", 409)
        if decision.decision == "APPROVE":
            await self.assert_current(bundle, definition)
            if get_settings().etl_owner_workflow_enabled:
                await require_source_manager(self.session, self.user, sheet.source_id)
                await self.evaluate(bundle_id, preview=True)
        bundle.status = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "REVOKE": "REVOKED"}[decision.decision]
        bundle.approved_by = self.user.id
        bundle.decision_reason = decision.reason
        audit(
            self.session,
            self.user,
            "analytics_rules.decided",
            bundle.id,
            decision=decision.decision,
            reason=decision.reason,
            review_hash=bundle.review_hash,
        )
        return record(bundle)

    async def evaluate(self, bundle_id, *, preview=False):
        bundle, definition = await self.get(bundle_id, lock=True)
        if not preview and bundle.status != "APPROVED":
            raise AppError("ANALYTICS_APPROVAL_REQUIRED", "Aturan belum disetujui reviewer.", 409)
        await self.assert_current(bundle, definition)
        result = await self.queries.execute(
            definition.product_code, definition.query, query_source="ANALYTICS_RULES", preserve_numeric=True
        )
        if len(result["rows"]) >= min(definition.query.limit, get_settings().nl2sql_max_rows):
            raise AppError(
                "ANALYTICS_RESULT_TRUNCATED",
                "Hasil mencapai batas baris; persempit periode/dimension lalu review ulang.",
                422,
            )
        rows = evaluate_rows(definition, result["rows"])
        count = sum(len(row["action_plans"]) for row in rows)
        audit(
            self.session,
            self.user,
            "analytics_rules.previewed" if preview else "analytics_rules.evaluated",
            bundle.id,
            review_hash=bundle.review_hash,
            result_hash=digest(rows),
            action_count=count,
            query=definition.query.model_dump(mode="json"),
            **result["meta"],
        )
        return {
            "bundle_id": bundle.id,
            "review_hash": bundle.review_hash,
            "mode": "PREVIEW" if preview else "APPROVED_RULES",
            "query": definition.query.model_dump(mode="json"),
            "rows": rows,
            "meta": result["meta"],
        }
