from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    inspect,
    select,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.core.config import get_settings
from app.core.database import make_engine
from app.core.exceptions import AppError

TYPE_MAP = {
    "text": Text,
    "varchar": Text,
    "integer": Integer,
    "bigint": BigInteger,
    "numeric": Numeric,
    "boolean": Boolean,
    "date": Date,
    "timestamp": lambda: DateTime(timezone=False),
    "timestamptz": lambda: DateTime(timezone=True),
    "uuid": lambda: Uuid(as_uuid=False),
}


def compile_master_table(definition, master_id, tenant_id, load_strategy="UPSERT"):
    """Canonical identity belongs to the master, never to a source tab."""
    if load_strategy != "UPSERT":
        raise AppError("MASTER_LOAD_STRATEGY_INVALID", "Master hanya mendukung UPSERT.")
    master_id, tenant_id = str(UUID(str(master_id))), str(UUID(str(tenant_id)))
    return Table(
        "master_" + UUID(master_id).hex,
        MetaData(),
        Column("_tenant_id", Uuid(as_uuid=False), nullable=False),
        Column("_record_id", Uuid(as_uuid=False), nullable=False),
        Column("_is_active", Boolean, nullable=False, server_default=text("true")),
        Column("_revision_no", Integer, nullable=False, server_default=text("1")),
        Column("_created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
        Column("_updated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
        Column("_source_sheet_id", Uuid(as_uuid=False), nullable=False),
        Column("_source_row", Integer, nullable=False),
        Column("_source_snapshot_hash", String(64), nullable=False),
        *(Column(f.name, TYPE_MAP[f.type](), nullable=f.nullable) for f in definition.fields),
        UniqueConstraint("_tenant_id", "_record_id"),
        UniqueConstraint("_tenant_id", *definition.business_key),
        CheckConstraint(f"_tenant_id = '{tenant_id}'::uuid", name="master_tenant_scope"),
        CheckConstraint("_revision_no > 0 AND _source_row > 0", name="master_positive_metadata"),
        schema="trusted",
    )


def validate_master_evolution(previous, proposed):
    """Only metadata edits and new nullable attributes are compatible in BE-04."""
    old = {f.name: f for f in previous.fields}
    new = {f.name: f for f in proposed.fields}
    if (
        previous.business_key != proposed.business_key
        or any(
            name not in new or (f.type, f.nullable) != (new[name].type, new[name].nullable)
            for name, f in old.items()
        )
        or any(not f.nullable for name, f in new.items() if name not in old)
    ):
        raise AppError(
            "MASTER_SCHEMA_MIGRATION_REQUIRED",
            "Perubahan key, tipe, nullability, penghapusan field, atau field wajib baru memerlukan migrasi khusus.",
            409,
        )


def physical_name(config, sheet_id):
    # UUID suffix prevents two sheets/tenants from writing to the same business table.
    return f"{config.target_table}_{str(sheet_id).replace('-', '')}"


def compile_table(config, sheet_id):
    columns = [
        Column("_tenant_id", Uuid(as_uuid=False), nullable=False),
        Column("_source_sheet_id", Uuid(as_uuid=False), nullable=False),
        Column("_source_row", Integer, nullable=False),
        Column("_etl_run_id", Uuid(as_uuid=False), nullable=False),
        Column("_row_hash", String(64), nullable=False),
    ]
    for col in config.columns:
        columns.append(Column(col.target_column, TYPE_MAP[col.target_type](), nullable=col.nullable))
    keys = [c.target_column for c in config.columns if c.is_business_key or c.is_primary_key]
    constraints = [UniqueConstraint("_tenant_id", *keys)] if keys else []
    if not keys:
        constraints.append(UniqueConstraint("_tenant_id", "_row_hash"))
    return Table(physical_name(config, sheet_id), MetaData(), *columns, *constraints, schema="trusted")


def schema_plan(config, sheet_id, tenant_id):
    table = compile_table(config, sheet_id)
    return {
        "target": f"trusted.{table.name}",
        "semantic_view": "semantic.v_" + str(sheet_id).replace("-", ""),
        "ddl": str(CreateTable(table).compile(dialect=postgresql.dialect())),
        "policy": "CREATE_ONLY_OR_IDENTICAL; schema changes require a reviewed migration",
    }


async def deploy_schema(config, sheet_id, tenant_id):
    s = get_settings()
    engine = make_engine(s.database_ddl_url.get_secret_value() or s.database_url.get_secret_value())
    table = compile_table(config, sheet_id)
    view_name = "v_" + str(sheet_id).replace("-", "")
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:name))"), {"name": table.fullname}
            )

            def create_or_check(sync):
                inspector = inspect(sync)
                if not inspector.has_table(table.name, schema="trusted"):
                    table.create(sync)
                    return
                existing = inspector.get_columns(table.name, schema="trusted")
                actual = {c["name"]: c for c in existing}
                if set(actual) != set(table.c.keys()):
                    raise AppError(
                        "SCHEMA_CHANGE_UNSAFE", "Perubahan kolom memerlukan migration manual yang direview."
                    )
                for c in table.c:
                    expected = str(c.type.compile(dialect=sync.dialect)).lower()
                    found = str(actual[c.name]["type"].compile(dialect=sync.dialect)).lower()
                    if expected != found or bool(actual[c.name]["nullable"]) != bool(c.nullable):
                        raise AppError(
                            "SCHEMA_CHANGE_UNSAFE", "Perubahan tipe/nullability memerlukan migration manual."
                        )
                unique_sets = {
                    tuple(u["column_names"])
                    for u in inspector.get_unique_constraints(table.name, schema="trusted")
                }
                expected_sets = {
                    tuple(c.name for c in u.columns)
                    for u in table.constraints
                    if isinstance(u, UniqueConstraint)
                }
                if unique_sets != expected_sets:
                    raise AppError(
                        "SCHEMA_CHANGE_UNSAFE", "Perubahan business key memerlukan migration manual."
                    )

            await conn.run_sync(create_or_check)
            public = [c.target_column for c in config.columns if c.pii_classification in ("NONE", "LOW")]
            if not public:
                raise AppError("SEMANTIC_INVALID", "Setidaknya satu kolom non-sensitif diperlukan.")
            stmt = select(table.c._tenant_id, *(table.c[n] for n in public)).where(
                table.c._tenant_id == tenant_id
            )
            query = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
            quote = conn.dialect.identifier_preparer.quote
            # Identifier generated exclusively from UUID; data values quoted by SQLAlchemy.
            await conn.execute(text(f"CREATE OR REPLACE VIEW semantic.{quote(view_name)} AS {query}"))
            await conn.execute(text(f"SELECT * FROM semantic.{quote(view_name)} LIMIT 0"))
            if s.database_nl2sql_url.get_secret_value():
                from sqlalchemy.engine import make_url

                reader = make_url(s.database_nl2sql_url.get_secret_value()).username
                await conn.execute(text(f"GRANT SELECT ON semantic.{quote(view_name)} TO {quote(reader)}"))
    finally:
        await engine.dispose()
    return table, view_name
