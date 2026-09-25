import hashlib
import json
import time
from datetime import date, datetime, timedelta, timezone

from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy import Column, MetaData, Table, Uuid, and_, func, select, text
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


def cache_key(user, product, plan, default_period=None):
    return "query:" + digest(
        [
            user.tenant_id,
            user.role,
            user.row_scope,
            product.code,
            product.version,
            product.freshness_version,
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


def build_query(product, user, plan, *, today=None):
    columns = {c["target_column"]: c for c in product.columns}
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
        dimensions = list(product.dimensions)
    for name in dimensions:
        expression = table.c[name]
        if plan.time_grain != "none" and columns[name]["target_type"] in ("date", "timestamp", "timestamptz"):
            expression = func.date_trunc(plan.time_grain, expression)
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
    stmt = select(*selected).where(and_(*conditions))
    if plan.metrics and groups:
        stmt = stmt.group_by(*groups)
    for sort in plan.sort:
        if sort.field not in outputs:
            raise AppError("QUERY_INVALID", "Sorting harus memakai field output.")
        stmt = stmt.order_by(
            outputs[sort.field].desc() if sort.direction == "desc" else outputs[sort.field].asc()
        )
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

    async def execute(self, product_code, plan, *, ai=False, query_source="OPERATIONAL"):
        product = await self.repo.product(product_code, self.user)
        today = datetime.now(timezone.utc).date()
        stmt = build_query(product, self.user, plan, today=today)
        default_period = resolve_default_period(product, plan, today)
        sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        validate_readonly_sql(
            sql,
            {"semantic." + product.view_name},
            {"_tenant_id", *(c["target_column"] for c in product.columns)},
        )
        s = get_settings()
        if ai and not s.database_nl2sql_url.get_secret_value():
            raise AppError("NL2SQL_NOT_CONFIGURED", "Isi DATABASE_NL2SQL_URL dengan role read-only.", 503)
        key = cache_key(self.user, product, plan, default_period)
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
                "query_source": query_source,
                "row_count": len(rows),
                "cached": cached_result,
                "semantic_version": product.version,
                "freshness_version": product.freshness_version,
                "default_period_applied": default_period,
                "visualization": plan.visualization.model_dump(mode="json") if plan.visualization else None,
            },
        }
