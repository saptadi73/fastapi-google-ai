import hashlib
import json
import time
from datetime import date, datetime, timedelta, timezone

from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy import Column, MetaData, Table, Uuid, and_, case, func, literal, select, text
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings
from app.core.database import make_engine
from app.core.exceptions import AppError
from app.repositories.semantic_repository import SemanticRepository
from app.schemas.configuration import MetricFilter
from app.services.audit_service import audit
from app.services.etl_compiler_service import cast_value
from app.services.profiling_service import digest
from app.services.schema_compiler_service import TYPE_MAP
from app.services.sql_guard_service import validate_readonly_sql


def cache_key(
    user, product, plan, default_period=None, joined_products=(), relationships=(), authorization_revisions=()
):
    return "query:" + digest(
        [
            user.tenant_id,
            user.role,
            getattr(user, "token_version", 0),
            user.row_scope,
            product.code,
            product.version,
            product.freshness_version,
            [(item.code, item.version, item.freshness_version) for item in joined_products],
            [(item.code, item.revision_no) for item in relationships],
            sorted(authorization_revisions),
            plan.model_dump(mode="json", exclude={"visualization"}),
            default_period,
        ]
    )


def resolve_default_period(product, plan, today=None):
    today = today or datetime.now(timezone.utc).date()
    explicit = {item.field for item in plan.filters}
    periods = {}
    for code in plan.metrics:
        period = next((m.get("default_period") for m in product.metrics if m["code"] == code), None)
        if period and period["dimension"] not in explicit:
            periods[(period["dimension"], period["days"])] = period
    if len(periods) > 1:
        raise AppError(
            "QUERY_DEFAULT_PERIOD_CONFLICT",
            "Metrik terpilih memiliki periode default berbeda; tambahkan filter tanggal eksplisit.",
            422,
        )
    if not periods:
        return None
    period = next(iter(periods.values()))
    return {**period, "start": (today - timedelta(days=period["days"] - 1)).isoformat(), "end": today.isoformat()}


def _policy_controls(product, user, decision):
    columns = {c["target_column"]: c for c in product.columns}
    row_scope = dict(user.row_scope.get(product.code, {}))
    visibility = {}
    if decision:
        for field, values in decision.get("row_scope", {}).items():
            if field in row_scope:
                row_scope[field] = sorted(set(row_scope[field]) & set(values))
            else:
                row_scope[field] = values
        visibility = decision.get("columns", {})
        for field, column in columns.items():
            if column.get("pii_classification") in ("MEDIUM", "HIGH"):
                visibility.setdefault(field, "HIDDEN")
    for field, values in row_scope.items():
        column = columns.get(field)
        if column is None or column.get("pii_classification") in ("MEDIUM", "HIGH"):
            raise AppError("SCOPE_INVALID", "Scope policy tidak kompatibel dengan data product.", 403)
        if not isinstance(values, list) or not values:
            raise AppError("SCOPE_INVALID", "Scope policy harus berisi daftar nilai.", 403)
    for field, rule in visibility.items():
        if field not in columns or rule not in ("VISIBLE", "MASKED", "HIDDEN"):
            raise AppError("COLUMN_POLICY_INVALID", "Policy kolom tidak kompatibel dengan data product.", 403)
    return columns, row_scope, visibility


def _require_visible(field, visibility, *, purpose):
    if visibility.get(field, "VISIBLE") != "VISIBLE":
        raise AppError("QUERY_FIELD_FORBIDDEN", f"Field '{field}' tidak tersedia untuk {purpose}.", 403)


def build_query(product, user, plan, *, today=None, access_decision=None):
    columns = {c["target_column"]: c for c in product.columns}
    columns, policy_scope, visibility = _policy_controls(product, user, access_decision)
    table = Table(
        product.view_name,
        MetaData(),
        Column("_tenant_id", Uuid(as_uuid=False)),
        *(Column(name, TYPE_MAP[c["target_type"]]()) for name, c in columns.items()),
        schema="semantic",
    )

    def convert(field, value):
        if field not in columns:
            raise AppError("QUERY_INVALID", "Filter tidak tersedia.")
        try:
            return cast_value(value, columns[field]["target_type"])
        except (ValueError, TypeError, ArithmeticError):
            raise AppError("QUERY_INVALID", "Tipe nilai filter tidak valid.") from None

    def predicate(item):
        col = table.c[item.field]
        if item.operator == "in":
            return col.in_([convert(item.field, value) for value in item.value])
        if item.operator == "between":
            return col.between(convert(item.field, item.value[0]), convert(item.field, item.value[1]))
        value = convert(item.field, item.value)
        if value is None and item.operator != "eq":
            raise AppError("QUERY_INVALID", "Null hanya didukung untuk operator eq.")
        operations = {
            "eq": lambda: col == value,
            "gte": lambda: col >= value,
            "lte": lambda: col <= value,
            "gt": lambda: col > value,
            "lt": lambda: col < value,
        }
        return operations[item.operator]()

    metrics = {m["code"]: m for m in product.metrics}
    allowed_aggregations = {"sum", "avg", "min", "max", "count", "count_distinct"}
    for code, metric in metrics.items():
        if metric.get("aggregation") not in allowed_aggregations or metric.get("column") not in columns:
            raise AppError("SEMANTIC_METRIC_INVALID", f"Definisi metric '{code}' tidak valid.")
        policy = metric.get("null_handling", "PRESERVE")
        if policy not in ("PRESERVE", "ZERO_RESULT") or (
            policy == "ZERO_RESULT" and metric["aggregation"] not in ("count", "count_distinct")
            and columns[metric["column"]]["target_type"] not in ("integer", "bigint", "numeric")
        ):
            raise AppError("SEMANTIC_METRIC_INVALID", f"Null handling metric '{code}' tidak valid.")
        period = metric.get("default_period")
        if period is not None and (
            not isinstance(period, dict)
            or set(period) != {"dimension", "days"}
            or period["dimension"] not in product.dimensions
            or period["dimension"] not in columns
            or columns[period["dimension"]]["target_type"] not in ("date", "timestamp", "timestamptz")
            or not isinstance(period["days"], int)
            or isinstance(period["days"], bool)
            or not 1 <= period["days"] <= 3660
        ):
            raise AppError("SEMANTIC_METRIC_INVALID", f"Default period metric '{code}' tidak valid.")
        try:
            metric_filters = [MetricFilter.model_validate(item) for item in metric.get("filters", [])]
        except (ValidationError, TypeError):
            raise AppError("SEMANTIC_METRIC_INVALID", f"Filter metric '{code}' tidak valid.") from None
        if any(item.field not in columns for item in metric_filters):
            raise AppError("SEMANTIC_METRIC_INVALID", f"Filter metric '{code}' tidak valid.")
        _require_visible(metric["column"], visibility, purpose="metric")
        # Metric expressions are intentionally limited to a column plus an allowlisted aggregation.
        if set(metric) - {"code", "name", "label", "column", "aggregation", "description", "unit", "synonyms", "default_period", "filters", "null_handling"}:
            raise AppError("SEMANTIC_METRIC_INVALID", f"Expression metric '{code}' tidak diizinkan.")
    if len(set(plan.dimensions)) != len(plan.dimensions) or len(set(plan.metrics)) != len(plan.metrics):
        raise AppError("QUERY_INVALID", "Metric/dimension duplikat.")
    if not set(plan.dimensions).issubset(product.dimensions) or not set(plan.metrics).issubset(metrics):
        raise AppError("QUERY_INVALID", "Metric atau dimension tidak tersedia.")
    selected, groups, outputs = [], [], {}
    dimensions = plan.dimensions
    if not dimensions and not plan.metrics:
        dimensions = [field for field in product.dimensions if visibility.get(field, "VISIBLE") != "HIDDEN"]
    for name in dimensions:
        if visibility.get(name, "VISIBLE") == "HIDDEN":
            raise AppError("QUERY_FIELD_FORBIDDEN", f"Field '{name}' tidak tersedia untuk dimension.", 403)
        expression = table.c[name]
        if plan.time_grain != "none" and columns[name]["target_type"] in ("date", "timestamp", "timestamptz"):
            expression = func.date_trunc(plan.time_grain, expression)
        if visibility.get(name) == "MASKED":
            expression = case((expression.is_not(None), literal("[MASKED]")), else_=None)
        selected.append(expression.label(name))
        groups.append(expression)
        outputs[name] = expression
    for name in plan.metrics:
        metric = metrics[name]
        expression = table.c[metric["column"]]
        if metric["aggregation"] == "count_distinct":
            expression = func.count(expression.distinct())
        else:
            expression = getattr(func, metric["aggregation"])(expression)
        for metric_filter in metric.get("filters", []):
            expression = expression.filter(predicate(MetricFilter.model_validate(metric_filter)))
        if metric.get("null_handling", "PRESERVE") == "ZERO_RESULT":
            expression = func.coalesce(expression, 0)
        selected.append(expression.label(name))
        outputs[name] = expression
    if not selected:
        raise AppError("QUERY_INVALID", "Pilih setidaknya satu dimension atau metric.")
    conditions = [table.c._tenant_id == user.tenant_id]

    for f in plan.filters:
        if f.field not in product.dimensions:
            raise AppError("QUERY_INVALID", "Filter harus menggunakan dimension yang diizinkan.")
        _require_visible(f.field, visibility, purpose="filter")
        conditions.append(predicate(f))
    default_period = resolve_default_period(product, plan, today)
    if default_period:
        field = default_period["dimension"]
        col = table.c[field]
        start = default_period["start"]
        end = default_period["end"]
        if columns[field]["target_type"] == "date":
            conditions.extend((col >= date.fromisoformat(start), col <= date.fromisoformat(end)))
        else:
            start_value = datetime.fromisoformat(start)
            end_value = datetime.fromisoformat(end) + timedelta(days=1)
            if columns[field]["target_type"] == "timestamptz":
                start_value = start_value.replace(tzinfo=timezone.utc)
                end_value = end_value.replace(tzinfo=timezone.utc)
            conditions.extend((col >= start_value, col < end_value))
    # Scope is taken from the current database user, never from a model or token payload.
    for field, allowed in user.row_scope.get(product.code, {}).items():
        if field not in columns:
            raise AppError("SCOPE_INVALID", "Scope akun tidak kompatibel dengan data product.", 403)
        conditions.append(table.c[field].in_([convert(field, v) for v in allowed]))
    for field, allowed in policy_scope.items():
        conditions.append(table.c[field].in_([convert(field, v) for v in allowed]))
    stmt = select(*selected).where(and_(*conditions))
    if plan.metrics and groups:
        stmt = stmt.group_by(*groups)
    for sort in plan.sort:
        if sort.field not in outputs:
            raise AppError("QUERY_INVALID", "Sorting harus memakai field output.")
        _require_visible(sort.field, visibility, purpose="sorting")
        stmt = stmt.order_by(
            outputs[sort.field].desc() if sort.direction == "desc" else outputs[sort.field].asc()
        )
    if not plan.sort:
        for expression in groups or selected:
            stmt = stmt.order_by(expression)
    return stmt.limit(min(plan.limit, get_settings().nl2sql_max_rows)).offset(plan.offset)


def build_join_query(root, products, relationships, user, plan, *, today=None, access_decisions=None):
    """Compile an explicit approved join path. Secondary fields use PRODUCT.field names."""
    today = today or datetime.now(timezone.utc).date()
    product_map = {item.code: item for item in products}
    if root.code not in product_map:
        product_map[root.code] = root
    tables, columns_by_product, metrics_by_product = {}, {}, {}
    controls_by_product = {}
    for product in product_map.values():
        columns = {item["target_column"]: item for item in product.columns}
        columns_by_product[product.code] = columns
        metrics_by_product[product.code] = {item["code"]: item for item in product.metrics}
        _, policy_scope, visibility = _policy_controls(
            product, user, (access_decisions or {}).get(product.code)
        )
        controls_by_product[product.code] = (policy_scope, visibility)
        tables[product.code] = Table(
            product.view_name,
            MetaData(),
            Column("_tenant_id", Uuid(as_uuid=False)),
            *(Column(name, TYPE_MAP[item["target_type"]]()) for name, item in columns.items()),
            schema="semantic",
        ).alias(product.code.lower())

    included = {root.code}
    for relationship in relationships:
        if relationship.left_product_code not in included or relationship.right_product_code in included:
            raise AppError(
                "QUERY_JOIN_PATH_INVALID",
                "Join harus berupa graf terarah dari produk utama tanpa siklus atau produk duplikat.",
                422,
            )
        if relationship.right_product_code not in product_map:
            raise AppError("QUERY_JOIN_PATH_INVALID", "Produk join tidak tersedia.", 422)
        left_columns = columns_by_product[relationship.left_product_code]
        right_columns = columns_by_product[relationship.right_product_code]
        if relationship.left_column not in left_columns or relationship.right_column not in right_columns:
            raise AppError("QUERY_JOIN_STALE", "Kolom join tidak lagi tersedia.", 409)
        _require_visible(
            relationship.left_column,
            controls_by_product[relationship.left_product_code][1],
            purpose="join",
        )
        _require_visible(
            relationship.right_column,
            controls_by_product[relationship.right_product_code][1],
            purpose="join",
        )
        if any(
            columns.get(column, {}).get("pii_classification") in ("MEDIUM", "HIGH")
            for columns, column in (
                (left_columns, relationship.left_column),
                (right_columns, relationship.right_column),
            )
        ):
            raise AppError("QUERY_JOIN_FORBIDDEN", "Join pada kolom sensitif tidak diizinkan.", 403)
        included.add(relationship.right_product_code)
    if included != set(product_map):
        raise AppError("QUERY_JOIN_PATH_INVALID", "Produk join tidak terhubung penuh.", 422)

    def resolve(identifier, kind):
        if "." in identifier:
            code, name = identifier.split(".", 1)
        else:
            code, name = root.code, identifier
        if code not in product_map:
            raise AppError("QUERY_INVALID", f"Produk field '{identifier}' tidak tersedia.")
        allowed = product_map[code].dimensions if kind == "dimension" else metrics_by_product[code]
        if name not in allowed:
            raise AppError("QUERY_INVALID", f"{kind.title()} '{identifier}' tidak tersedia.")
        column_name = name if kind == "dimension" else metrics_by_product[code][name]["column"]
        column = columns_by_product[code].get(column_name)
        if column is None or column.get("pii_classification") in ("MEDIUM", "HIGH"):
            raise AppError("QUERY_FIELD_FORBIDDEN", f"Field '{identifier}' tidak tersedia.", 403)
        rule = controls_by_product[code][1].get(column_name, "VISIBLE")
        if rule == "HIDDEN" or (kind != "dimension" and rule != "VISIBLE"):
            raise AppError("QUERY_FIELD_FORBIDDEN", f"Field '{identifier}' tidak tersedia.", 403)
        return code, name, column

    def convert(code, field, value):
        try:
            return cast_value(value, columns_by_product[code][field]["target_type"])
        except (KeyError, ValueError, TypeError, ArithmeticError):
            raise AppError("QUERY_INVALID", "Tipe nilai filter tidak valid.") from None

    def predicate(item, *, default_code=None):
        if "." in item.field:
            code, field = item.field.split(".", 1)
        else:
            code, field = default_code or root.code, item.field
        if code not in product_map or field not in product_map[code].dimensions:
            raise AppError("QUERY_INVALID", "Filter harus menggunakan dimension yang diizinkan.")
        column = columns_by_product[code].get(field)
        if column is None or column.get("pii_classification") in ("MEDIUM", "HIGH"):
            raise AppError("QUERY_FIELD_FORBIDDEN", "Filter sensitif tidak diizinkan.", 403)
        _require_visible(field, controls_by_product[code][1], purpose="filter")
        expression = tables[code].c[field]
        if item.operator == "in":
            return expression.in_([convert(code, field, value) for value in item.value])
        if item.operator == "between":
            return expression.between(
                convert(code, field, item.value[0]), convert(code, field, item.value[1])
            )
        value = convert(code, field, item.value)
        if value is None and item.operator != "eq":
            raise AppError("QUERY_INVALID", "Null hanya didukung untuk operator eq.")
        operations = {
            "eq": lambda: expression == value,
            "gte": lambda: expression >= value,
            "lte": lambda: expression <= value,
            "gt": lambda: expression > value,
            "lt": lambda: expression < value,
        }
        return operations[item.operator]()

    if len(set(plan.dimensions)) != len(plan.dimensions) or len(set(plan.metrics)) != len(plan.metrics):
        raise AppError("QUERY_INVALID", "Metric/dimension duplikat.")
    resolved_metrics = [(identifier, *resolve(identifier, "metric")) for identifier in plan.metrics]
    if len(relationships) > 1 and resolved_metrics and any(r.cardinality != "ONE_TO_ONE" for r in relationships):
        raise AppError("QUERY_AGGREGATION_AMBIGUOUS", "Agregasi lintas beberapa join memerlukan relasi one-to-one.", 422)
    for relationship in relationships:
        metric_products = {code for _, code, _, _ in resolved_metrics}
        if relationship.cardinality == "MANY_TO_ONE" and relationship.right_product_code in metric_products:
            raise AppError("QUERY_AGGREGATION_AMBIGUOUS", "Metrik sisi many-to-one dapat terhitung ganda.", 422)
        if relationship.cardinality == "ONE_TO_MANY" and metric_products:
            if relationship.duplicate_policy != "AGGREGATE_RIGHT" or metric_products != {relationship.right_product_code}:
                raise AppError("QUERY_AGGREGATION_AMBIGUOUS", "Metrik one-to-many tidak sesuai duplicate policy.", 422)

    selected, groups, outputs = [], [], {}
    dimensions = plan.dimensions or ([] if plan.metrics else list(root.dimensions))
    for identifier in dimensions:
        code, name, column = resolve(identifier, "dimension")
        expression = tables[code].c[name]
        if plan.time_grain != "none" and column["target_type"] in ("date", "timestamp", "timestamptz"):
            expression = func.date_trunc(plan.time_grain, expression)
        if controls_by_product[code][1].get(name) == "MASKED":
            expression = case((expression.is_not(None), literal("[MASKED]")), else_=None)
        selected.append(expression.label(identifier))
        groups.append(expression)
        outputs[identifier] = expression
    for identifier, code, name, _ in resolved_metrics:
        metric = metrics_by_product[code][name]
        if metric.get("aggregation") not in {"sum", "avg", "min", "max", "count", "count_distinct"}:
            raise AppError("SEMANTIC_METRIC_INVALID", f"Definisi metric '{identifier}' tidak valid.")
        period = metric.get("default_period")
        period_field = (
            f"{code}.{period['dimension']}" if period and code != root.code else period and period["dimension"]
        )
        if period and period_field not in {item.field for item in plan.filters}:
            raise AppError(
                "QUERY_JOIN_DEFAULT_PERIOD_REQUIRED",
                "Query join dengan default period memerlukan filter periode eksplisit.",
                422,
            )
        expression = tables[code].c[metric["column"]]
        _require_visible(metric["column"], controls_by_product[code][1], purpose="metric")
        expression = (
            func.count(expression.distinct())
            if metric["aggregation"] == "count_distinct"
            else getattr(func, metric["aggregation"])(expression)
        )
        for item in metric.get("filters", []):
            expression = expression.filter(predicate(MetricFilter.model_validate(item), default_code=code))
        if metric.get("null_handling", "PRESERVE") == "ZERO_RESULT":
            expression = func.coalesce(expression, 0)
        selected.append(expression.label(identifier))
        outputs[identifier] = expression
    if not selected:
        raise AppError("QUERY_INVALID", "Pilih setidaknya satu dimension atau metric.")

    root_table = tables[root.code]
    stmt = select(*selected).select_from(root_table)
    for relationship in relationships:
        left, right = tables[relationship.left_product_code], tables[relationship.right_product_code]
        join_conditions = [
            left.c[relationship.left_column] == right.c[relationship.right_column],
            left.c._tenant_id == right.c._tenant_id,
        ]
        right_code = relationship.right_product_code
        for field, allowed in user.row_scope.get(right_code, {}).items():
            if field not in columns_by_product[right_code]:
                raise AppError("SCOPE_INVALID", "Scope akun tidak kompatibel dengan data product.", 403)
            join_conditions.append(
                right.c[field].in_([convert(right_code, field, value) for value in allowed])
            )
        for field, allowed in controls_by_product[right_code][0].items():
            join_conditions.append(
                right.c[field].in_([convert(right_code, field, value) for value in allowed])
            )
        on_clause = and_(*join_conditions)
        stmt = stmt.join(right, on_clause, isouter=relationship.join_type == "LEFT")
    conditions = [root_table.c._tenant_id == user.tenant_id]
    conditions.extend(predicate(item) for item in plan.filters)
    for field, allowed in user.row_scope.get(root.code, {}).items():
        if field not in columns_by_product[root.code]:
            raise AppError("SCOPE_INVALID", "Scope akun tidak kompatibel dengan data product.", 403)
        conditions.append(
            root_table.c[field].in_([convert(root.code, field, value) for value in allowed])
        )
    for field, allowed in controls_by_product[root.code][0].items():
        conditions.append(
            root_table.c[field].in_([convert(root.code, field, value) for value in allowed])
        )
    stmt = stmt.where(and_(*conditions))
    if plan.metrics and groups:
        stmt = stmt.group_by(*groups)
    for sort in plan.sort:
        if sort.field not in outputs:
            raise AppError("QUERY_INVALID", "Sorting harus memakai field output.")
        if "." in sort.field:
            sort_code, sort_field = sort.field.split(".", 1)
        else:
            sort_code, sort_field = root.code, sort.field
        _require_visible(sort_field, controls_by_product[sort_code][1], purpose="sorting")
        stmt = stmt.order_by(outputs[sort.field].desc() if sort.direction == "desc" else outputs[sort.field].asc())
    if not plan.sort:
        for expression in groups or selected:
            stmt = stmt.order_by(expression)
    return stmt.limit(min(plan.limit, get_settings().nl2sql_max_rows)).offset(plan.offset)


async def assert_reader(conn):
    privileged = await conn.scalar(
        text(
            "SELECT rolsuper OR rolcreaterole OR rolcreatedb OR rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
    )
    writable = await conn.scalar(
        text("""
        SELECT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('platform','raw','staging','trusted','semantic','quarantine','audit')
          AND c.relkind IN ('r','v','m','p') AND (
          has_table_privilege(current_user,c.oid,'INSERT') OR has_table_privilege(current_user,c.oid,'UPDATE')
          OR has_table_privilege(current_user,c.oid,'DELETE') OR has_table_privilege(current_user,c.oid,'TRUNCATE')))
    """)
    )
    if privileged or writable:
        raise AppError("NL2SQL_READER_UNSAFE", "DATABASE_NL2SQL_URL wajib memakai role SELECT-only.", 503)


class QueryExecutionService:
    def __init__(self, session, user):
        self.session, self.user = session, user
        self.repo = SemanticRepository(session, user.tenant_id)

    async def compile(self, product_code, plan, *, today=None, action="QUERY"):
        root = await self.repo.product(product_code, self.user, action=action)
        relationships, joined, included = [], [], {root.code}
        for code in plan.join_relationships:
            relationship = await self.repo.join_relationship(code)
            if relationship.left_product_code not in included or relationship.right_product_code in included:
                raise AppError(
                    "QUERY_JOIN_PATH_INVALID",
                    "Urutan relationship harus membentuk path dari produk utama.",
                    422,
                )
            product = await self.repo.product(relationship.right_product_code, self.user, action=action)
            relationships.append(relationship)
            joined.append(product)
            included.add(product.code)
        if relationships:
            return (
                root,
                joined,
                relationships,
                build_join_query(
                    root,
                    [root, *joined],
                    relationships,
                    self.user,
                    plan,
                    today=today,
                    access_decisions=self.repo.product_access_decisions,
                ),
                None,
            )
        return (
            root,
            joined,
            relationships,
            build_query(
                root,
                self.user,
                plan,
                today=today,
                access_decision=self.repo.product_access_decisions.get(root.code),
            ),
            resolve_default_period(root, plan, today),
        )

    async def execute(self, product_code, plan, *, ai=False, query_source="OPERATIONAL", action="QUERY"):
        today = datetime.now(timezone.utc).date()
        product, joined, relationships, stmt, default_period = await self.compile(
            product_code, plan, today=today, action=action
        )
        sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        validate_readonly_sql(
            sql,
            {"semantic." + item.view_name for item in [product, *joined]},
            {"_tenant_id", *(c["target_column"] for item in [product, *joined] for c in item.columns)},
            allow_joins=bool(relationships),
        )
        s = get_settings()
        if ai and not s.database_nl2sql_url.get_secret_value():
            raise AppError("NL2SQL_NOT_CONFIGURED", "Isi DATABASE_NL2SQL_URL dengan role read-only.", 503)
        key = cache_key(
            self.user,
            product,
            plan,
            default_period,
            joined,
            relationships,
            self.repo.authorization_revisions,
        )
        redis = Redis.from_url(s.redis_url.get_secret_value(), socket_connect_timeout=0.3, socket_timeout=0.3)
        try:
            cached = await redis.get(key)
        except Exception:
            cached = None
        started = time.monotonic()
        cached_result = bool(cached)
        if cached:
            rows = json.loads(cached)
        else:
            url = s.database_nl2sql_url.get_secret_value() if ai else s.database_url.get_secret_value()
            engine = make_engine(url)
            try:
                async with engine.connect() as conn, conn.begin():
                    await conn.execute(text("SET TRANSACTION READ ONLY"))
                    await conn.execute(
                        text("SELECT set_config('statement_timeout', :timeout, true)"),
                        {"timeout": str(s.nl2sql_statement_timeout_ms)},
                    )
                    if ai:
                        await assert_reader(conn)
                    explain = (await conn.exec_driver_sql("EXPLAIN (FORMAT JSON) " + sql)).scalar()
                    if isinstance(explain, str):
                        explain = json.loads(explain)
                    if explain[0]["Plan"]["Total Cost"] > s.nl2sql_max_estimated_cost:
                        raise AppError(
                            "QUERY_TOO_EXPENSIVE", "Query terlalu mahal; tambahkan filter periode."
                        )
                    result = await conn.execute(stmt)
                    rows = jsonable_encoder(
                        [dict(row) for row in result.mappings().fetchmany(s.nl2sql_max_rows)]
                    )
            finally:
                await engine.dispose()
            try:
                await redis.setex(key, s.query_cache_ttl_seconds, json.dumps(rows))
            except Exception:
                pass
        await redis.aclose()
        audit(
            self.session,
            self.user,
            "query.executed",
            product.id,
            query_source=query_source,
            row_count=len(rows),
            cached=cached_result,
            query_hash=hashlib.sha256(sql.encode()).hexdigest(),
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return {
            "rows": rows,
            "meta": {
                "data_product": product.code,
                "joined_products": [item.code for item in joined],
                "join_relationships": [item.code for item in relationships],
                "query_source": query_source,
                "row_count": len(rows),
                "cached": cached_result,
                "semantic_version": product.version,
                "freshness_version": product.freshness_version,
                "default_period_applied": default_period,
                "visualization": plan.visualization.model_dump(mode="json") if plan.visualization else None,
            },
        }
