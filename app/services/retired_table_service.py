"""Read-only inventory of physical tables retained by superseded ETL revisions."""

from sqlalchemy import bindparam, select, text

from app.core.config import get_settings
from app.core.database import make_engine
from app.models.configuration import Configuration
from app.models.source import DataSource, SourceSheet
from app.schemas.access import AccessEvaluationRequest
from app.services.access_service import AccessService


def physical_table_name(target_table, sheet_id):
    return f"{target_table}_{str(sheet_id).replace('-', '')}"


def collect_retired_tables(rows):
    """Group historical config versions by table and omit the currently active table."""
    active = {}
    for config, sheet, _source in rows:
        if config.status == "ACTIVE":
            active[sheet.id] = {
                "configuration_id": config.id,
                "version_no": config.version_no,
                "table_name": physical_table_name(
                    config.configuration_json["target_table"], sheet.id
                ),
            }

    candidates = {}
    for config, sheet, source in rows:
        if config.status != "SUPERSEDED":
            continue
        old_name = physical_table_name(config.configuration_json["target_table"], sheet.id)
        current = active.get(sheet.id)
        if current and current["table_name"] == old_name:
            continue
        key = (source.id, sheet.id, old_name)
        candidate = candidates.setdefault(
            key,
            {
                "source_id": source.id,
                "source_code": source.source_code,
                "source_name": source.name,
                "source_sheet_id": sheet.id,
                "sheet_name": sheet.sheet_name,
                "schema_name": "trusted",
                "table_name": old_name,
                "qualified_name": f"trusted.{old_name}",
                "current_configuration": current,
                "superseded_configurations": [],
                "cleanup_candidate": True,
                "delete_ready": False,
                "cleanup_status": "REVIEW_REQUIRED",
                "delete_blocker": (
                    "Versi lama masih dapat dipakai untuk rollback. Inventaris ini tidak menghapus tabel."
                ),
            },
        )
        candidate["superseded_configurations"].append(
            {
                "configuration_id": config.id,
                "version_no": config.version_no,
                "created_at": config.created_at,
            }
        )
    return list(candidates.values())


class RetiredTableService:
    def __init__(self, session, tenant_id):
        self.session = session
        self.tenant_id = str(tenant_id)

    async def list(self, *, search="", offset=0, limit=50, user=None):
        rows = (
            await self.session.execute(
                select(Configuration, SourceSheet, DataSource)
                .join(
                    SourceSheet,
                    (SourceSheet.id == Configuration.source_sheet_id)
                    & (SourceSheet.tenant_id == Configuration.tenant_id),
                )
                .join(
                    DataSource,
                    (DataSource.id == Configuration.source_id)
                    & (DataSource.tenant_id == Configuration.tenant_id),
                )
                .where(
                    Configuration.tenant_id == self.tenant_id,
                    Configuration.status.in_(("ACTIVE", "SUPERSEDED")),
                )
                .order_by(Configuration.created_at.desc())
            )
        ).all()
        candidates = collect_retired_tables(rows)
        names = [item["table_name"] for item in candidates]
        if names:
            engine = make_engine(get_settings().database_url.get_secret_value())
            try:
                async with engine.connect() as conn:
                    existing = set(
                        (
                            await conn.execute(
                                text(
                                    "SELECT c.relname::text FROM pg_catalog.pg_class c "
                                    "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
                                    "WHERE n.nspname='trusted' AND c.relkind IN ('r','p') "
                                    "AND c.relname::text IN :names"
                                ).bindparams(bindparam("names", expanding=True)),
                                {"names": names},
                            )
                        ).scalars()
                    )
            finally:
                await engine.dispose()
            candidates = [item for item in candidates if item["table_name"] in existing]

        query = search.strip().casefold()
        if user is not None:
            access = AccessService(self.session, user)
            decisions = {}
            for item in candidates:
                source_code = item["source_code"]
                if source_code not in decisions:
                    result = await access.evaluate(
                        AccessEvaluationRequest(
                            action="DISCOVER",
                            resource_type="SOURCE",
                            resource_id=source_code,
                        )
                    )
                    decisions[source_code] = result["allowed"]
            candidates = [item for item in candidates if decisions[item["source_code"]]]
        if query:
            candidates = [
                item
                for item in candidates
                if query
                in " ".join(
                    (
                        item["source_code"],
                        item["source_name"],
                        item["sheet_name"],
                        item["qualified_name"],
                    )
                ).casefold()
            ]
        candidates.sort(key=lambda item: (item["source_name"].casefold(), item["sheet_name"].casefold(), item["table_name"]))
        total = len(candidates)
        items = candidates[offset : offset + limit]
        return {"items": items, "total": total, "offset": offset, "limit": limit}
