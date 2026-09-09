import re

from sqlalchemy import Text, UniqueConstraint, cast, inspect, or_, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateColumn, CreateTable

from app.core.config import get_settings
from app.core.database import make_engine
from app.core.exceptions import AppError
from app.domain.enums import DATA_ROLES, EDIT_ROLES, REVIEW_ROLES
from app.schemas.master import MasterSchema
from app.services.audit_service import audit
from app.services.master_service import MasterService
from app.services.schema_compiler_service import compile_master_table


def check_storage(sync, table, *, deploy=False):
    inspector = inspect(sync)
    if not inspector.has_table(table.name, schema=table.schema):
        if deploy:
            table.create(sync)
            return
        raise AppError("MASTER_STORAGE_REQUIRED", "Siapkan storage master terlebih dahulu.", 409)
    actual = {c["name"]: c for c in inspector.get_columns(table.name, schema=table.schema)}
    expected = set(table.c.keys())
    missing = expected - set(actual)
    unsafe = set(actual) - expected or any(
        table.c[name].name.startswith("_") or not table.c[name].nullable for name in missing
    )
    for name in expected & set(actual):
        column = table.c[name]
        unsafe = unsafe or (
            str(column.type.compile(dialect=sync.dialect)).lower()
            != str(actual[name]["type"].compile(dialect=sync.dialect)).lower()
            or column.nullable != actual[name]["nullable"]
        )
    unique = {
        tuple(c["column_names"]) for c in inspector.get_unique_constraints(table.name, schema=table.schema)
    }
    required = {
        tuple(c.name for c in u.columns) for u in table.constraints if isinstance(u, UniqueConstraint)
    }
    checks = {
        c["name"]: c["sqltext"] for c in inspector.get_check_constraints(table.name, schema=table.schema)
    }

    def normalize(value):
        return re.sub(r"[\s()]+", "", value.replace("::uuid", ""))

    for constraint in table.constraints:
        if constraint.name in ("master_tenant_scope", "master_positive_metadata"):
            unsafe = unsafe or normalize(checks.get(constraint.name, "")) != normalize(
                str(constraint.sqltext)
            )
    if unsafe or unique != required:
        raise AppError(
            "MASTER_SCHEMA_MIGRATION_REQUIRED", "Schema fisik master berbeda; diperlukan migrasi khusus.", 409
        )
    if missing and not deploy:
        raise AppError("MASTER_STORAGE_STALE", "Deploy storage untuk versi master terbaru.", 409)
    quote = sync.dialect.identifier_preparer.quote
    for name in sorted(missing):
        column_sql = str(CreateColumn(table.c[name]).compile(dialect=sync.dialect))
        sync.execute(text(f"ALTER TABLE trusted.{quote(table.name)} ADD COLUMN {column_sql}"))


class MasterStorageService(MasterService):
    async def target(self, master_id):
        self.require_role((*EDIT_ROLES, *REVIEW_ROLES))
        master = await self.lock_master(master_id)
        if not master.is_active or not master.approved_definition_json:
            raise AppError("MASTER_NOT_APPROVED", "Master harus aktif dan mempunyai versi approved.", 409)
        definition = MasterSchema.model_validate(master.approved_definition_json)
        return master, definition, compile_master_table(definition, master.id, master.tenant_id)

    async def plan(self, master_id):
        master, _, table = await self.target(master_id)
        return {
            "target": table.fullname,
            "master_version": master.approved_version,
            "revision_no": master.revision_no,
            "ddl": str(CreateTable(table).compile(dialect=postgresql.dialect())),
            "schema_policy": "IDENTICAL_OR_ADD_NULLABLE_ATTRIBUTES",
            "execution_ready": False,
        }

    async def deploy(self, master_id, request):
        self.require_role(REVIEW_ROLES)
        master, _, table = await self.target(master_id)
        self.check_revision(master, request.revision_no)
        settings = get_settings()
        engine = make_engine(
            settings.database_ddl_url.get_secret_value() or settings.database_url.get_secret_value()
        )
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:name))"), {"name": table.fullname}
                )
                await connection.run_sync(lambda sync: check_storage(sync, table, deploy=True))
                operator = make_url(settings.database_url.get_secret_value()).username
                quote = connection.dialect.identifier_preparer.quote
                if operator:
                    await connection.execute(
                        text(
                            f"GRANT SELECT, INSERT, UPDATE ON trusted.{quote(table.name)} TO {quote(operator)}"
                        )
                    )
        finally:
            await engine.dispose()
        audit(
            self.session,
            self.user,
            "master.storage_deployed",
            master.id,
            master_version=master.approved_version,
            target=table.fullname,
            comment=request.comment,
        )
        return {
            "target": table.fullname,
            "master_version": master.approved_version,
            "storage_ready": True,
            "execution_ready": False,
        }

    async def records(self, master_id, search="", offset=0, limit=50, active_only=True, record_id=None, as_of=None):
        _, definition, table = await self.target(master_id)
        connection = await self.session.connection()
        await connection.run_sync(lambda sync: check_storage(sync, table))
        sensitive = {f.name for f in definition.fields if f.pii_classification in ("MEDIUM", "HIGH")}
        masked = sensitive if self.user.role not in DATA_ROLES else set()
        # Mask at SELECT time, and never filter by a field hidden from this role.
        visible = [c for c in table.c if c.name not in masked]
        query = select(*visible).where(table.c._tenant_id == self.user.tenant_id)
        if as_of is not None:
            from app.services.effective_dating_service import effective_at_condition

            query = query.where(effective_at_condition(definition, table, as_of, masked_fields=masked))
        if active_only:
            query = query.where(table.c._is_active.is_(True))
        if record_id:
            query = query.where(table.c._record_id == str(record_id))
        if search:
            names = set(definition.business_key + [definition.label_field]) - masked
            pattern = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            query = query.where(
                or_(*(cast(table.c[n], Text).ilike(pattern, escape="\\") for n in sorted(names)))
                if names
                else False
            )
        rows = (
            (await self.session.execute(query.order_by(table.c._record_id).offset(offset).limit(limit + 1)))
            .mappings()
            .all()
        )
        items = [{**dict(row), **{name: "***" for name in sorted(masked)}} for row in rows[:limit]]
        return {"items": items, "has_more": len(rows) > limit, "masked_fields": sorted(masked)}

    async def update_attributes(self, master_id, record_id, revision_no, values):
        """Internal primitive for the future approved batch applier; no public write route."""
        self.require_role(DATA_ROLES)
        _, definition, table = await self.target(master_id)
        if definition.policy.effective_dating:
            raise AppError("MASTER_VERSION_IMMUTABLE", "Versi bermasa berlaku tidak boleh diubah lewat update atribut.", 409)
        allowed = {f.name for f in definition.fields} - set(definition.business_key)
        if not values or not set(values).issubset(allowed):
            raise AppError(
                "MASTER_ATTRIBUTE_UPDATE_INVALID",
                "Update atribut tidak boleh mengubah key, identitas, status, atau metadata.",
            )
        connection = await self.session.connection()
        await connection.run_sync(lambda sync: check_storage(sync, table))
        result = await self.session.execute(
            table.update()
            .where(
                table.c._tenant_id == self.user.tenant_id,
                table.c._record_id == str(record_id),
                table.c._revision_no == revision_no,
                table.c._is_active.is_(True),
            )
            .values(**values, _revision_no=table.c._revision_no + 1, _updated_at=text("now()"))
        )
        if result.rowcount != 1:
            raise AppError(
                "MASTER_RECORD_REVISION_CONFLICT",
                "Record tidak tersedia, nonaktif, atau revisi berubah.",
                409,
            )
        audit(
            self.session,
            self.user,
            "master.record_attributes_updated",
            record_id,
            master_id=str(master_id),
            fields=sorted(values),
            revision_no=revision_no + 1,
        )
