from datetime import datetime, timezone

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select, text

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.configuration import Configuration
from app.models.etl import Snapshot
from app.models.source import DataSource, ProfilingRun, SourceDependency, SourceSheet
from app.repositories.base import record
from app.repositories.source_repository import SourceRepository
from app.schemas.import_review import ImportReviewCreate
from app.schemas.source import spreadsheet_id
from app.services.audit_service import audit
from app.services.google_sheets_service import GoogleSheetsService
from app.services.import_review_service import ImportReviewService
from app.services.job_service import enqueue
from app.services.profiling_service import digest, profile_values


async def source_records(session, sources):
    sources = list(sources)
    if not sources:
        return []
    rows = await session.execute(
        select(SourceDependency.downstream_source_id, SourceDependency.upstream_source_id)
        .where(SourceDependency.downstream_source_id.in_([source.id for source in sources]))
        .order_by(SourceDependency.upstream_source_id)
    )
    dependencies = {}
    for downstream_id, upstream_id in rows:
        dependencies.setdefault(str(downstream_id), []).append(str(upstream_id))
    return [
        {**record(source), "dependency_source_ids": dependencies.get(str(source.id), [])}
        for source in sources
    ]


def dependency_graph_has_cycle(edges):
    graph = {}
    for downstream, upstream in edges:
        graph.setdefault(str(downstream), set()).add(str(upstream))
    visiting, visited = set(), set()

    def visit(node):
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(parent) for parent in graph.get(node, ())):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


class SourceService:
    def __init__(self, session, user, google=None):
        self.session, self.user = session, user
        self.repo = SourceRepository(session, user.tenant_id)
        self.google = google or GoogleSheetsService()

    async def register(self, data):
        if data.credential_ref != get_settings().google_credential_ref:
            raise AppError("UNKNOWN_CREDENTIAL_REF", "credential_ref belum dikonfigurasi pada server.")
        try:
            sid = spreadsheet_id(data.spreadsheet_url)
        except ValueError as exc:
            raise AppError("INVALID_SPREADSHEET_ID", str(exc)) from None
        source = await self.repo.add(
            DataSource,
            **data.model_dump(exclude={"spreadsheet_url"}),
            spreadsheet_id=sid,
            owner_user_id=self.user.id,
        )
        audit(self.session, self.user, "source.registered", source.id)
        job = await enqueue(self.session, self.user, "DISCOVER", source.id)
        return {"source": record(source), **job}

    async def discover(self, source_id):
        source = await self.repo.get(DataSource, source_id)
        metadata = await self.google.metadata(source.spreadsheet_id)
        existing = {s.sheet_id: s for s in await self.repo.sheets(source.id)}
        for tab in metadata.get("sheets", []):
            props = tab["properties"]
            if props.get("sheetType", "GRID") != "GRID":
                continue
            if props["sheetId"] not in existing:
                await self.repo.add(
                    SourceSheet, source_id=source.id, sheet_id=props["sheetId"], sheet_name=props["title"]
                )
            else:
                existing[props["sheetId"]].sheet_name = props["title"]
        return await self.profile(source.id)

    async def profile(self, source_id):
        source = await self.repo.get(DataSource, source_id)
        sheets = [s for s in await self.repo.sheets(source.id) if s.enabled]
        if not sheets:
            raise AppError("SOURCE_NOT_FOUND", "Belum ada tab aktif; jalankan discovery.", 404)
        results = []
        batches = await self.google.read_sheets(source.spreadsheet_id, sheets)
        drift = False
        for sheet, values in zip(sheets, batches):
            profile = profile_values(
                values,
                sheet.sheet_name,
                sheet.header_row,
                sheet.data_start_row,
                sheet.range_a1,
                get_settings().etl_sample_row_limit,
            )
            snapshot = await self.repo.add(
                Snapshot,
                source_id=source.id,
                source_sheet_id=sheet.id,
                content_hash=digest(values),
                row_count=profile["row_count"],
                values=values,
            )
            run = await self.repo.add(
                ProfilingRun,
                source_id=source.id,
                source_sheet_id=sheet.id,
                fingerprint=profile["fingerprint"],
                profile_json=profile,
            )
            drift = drift or bool(sheet.last_fingerprint and sheet.last_fingerprint != profile["fingerprint"])
            sheet.last_fingerprint = profile["fingerprint"]
            results.append(
                {"profiling_run_id": run.id, "source_sheet_id": sheet.id, "snapshot_id": snapshot.id}
            )
        source.status = (
            "CHANGE_DETECTED"
            if drift
            else ("ACTIVE" if all(s.active_configuration_id for s in sheets) else "NEEDS_REVIEW")
        )
        audit(self.session, self.user, "source.profiled", source.id, drift=drift)
        return {"profiles": results, "schema_drift": drift}

    async def sync_review(self, source_id):
        await self.profile(source_id)
        sheets = await self.repo.sheets(source_id)
        reviews = []
        for sheet in sheets:
            config_id = sheet.active_configuration_id if sheet.dataset_kind != "MASTER" else None
            try:
                result = await ImportReviewService(self.session, self.user).create(
                    ImportReviewCreate(source_sheet_id=sheet.id, configuration_id=config_id)
                )
                reviews.append(jsonable_encoder(result))
            except AppError as exc:
                reviews.append({"source_sheet_id": sheet.id, "status": "BLOCKED", "code": exc.code})
        return {"source_id": str(source_id), "reviews": reviews}

    async def update_sheet(self, sheet_id, data):
        sheet = await self.repo.get(SourceSheet, sheet_id, lock=True)
        if sheet.active_configuration_id:
            raise AppError(
                "CONFIGURATION_CONFLICT", "Range/header tab aktif tidak dapat diubah langsung.", 409
            )
        for name, value in data.model_dump(exclude_none=True).items():
            setattr(sheet, name, value)
        if sheet.data_start_row <= sheet.header_row:
            raise AppError("INVALID_RANGE", "data_start_row harus setelah header_row.")
        sheet.last_fingerprint = None
        audit(self.session, self.user, "sheet.updated", sheet.id)
        return record(sheet)

    async def update_watermark(self, sheet_id, data):
        sheet = await self.repo.get(SourceSheet, sheet_id, lock=True)
        if sheet.watermark_revision != data.revision_no:
            raise AppError("WATERMARK_REVISION_CONFLICT", "Watermark tab telah berubah; muat ulang.", 409)
        if data.source_column:
            profile = await self.repo.latest_profile(sheet.id)
            columns = {
                item["source_column"] for item in (profile.profile_json.get("columns", []) if profile else [])
            }
            if data.source_column not in columns:
                raise AppError("WATERMARK_COLUMN_INVALID", "Pilih kolom dari profil tab terbaru.")
            if sheet.active_configuration_id:
                config = await self.repo.get(Configuration, sheet.active_configuration_id)
                if config.configuration_json.get("load_strategy") == "FULL_REFRESH":
                    raise AppError(
                        "WATERMARK_STRATEGY_INVALID",
                        "Incremental watermark tidak didukung untuk FULL_REFRESH.",
                    )
        changed = (
            sheet.watermark_source_column != data.source_column
            or sheet.watermark_kind != data.kind
        )
        sheet.watermark_source_column = data.source_column
        sheet.watermark_kind = data.kind
        if changed or data.source_column is None:
            sheet.watermark_value = None
            sheet.watermark_updated_at = None
        sheet.watermark_revision += 1
        audit(
            self.session,
            self.user,
            "sheet.watermark_updated",
            sheet.id,
            revision_no=sheet.watermark_revision,
            source_column=sheet.watermark_source_column,
            kind=sheet.watermark_kind,
            reset=changed,
        )
        return record(sheet)

    async def update_schedule(self, source_id, data):
        source = await self.repo.get(DataSource, source_id, lock=True)
        if source.schedule_revision != data.revision_no:
            raise AppError("SOURCE_SCHEDULE_CONFLICT", "Jadwal sumber telah berubah; muat ulang.", 409)
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": "source-dependency:" + self.user.tenant_id},
        )
        dependency_ids = [str(item) for item in data.dependency_source_ids]
        if str(source.id) in dependency_ids:
            raise AppError("SOURCE_DEPENDENCY_INVALID", "Source tidak dapat bergantung pada dirinya sendiri.")
        for dependency_id in dependency_ids:
            await self.repo.get(DataSource, dependency_id)
        existing_edges = list(
            (
                await self.session.execute(
                    select(
                        SourceDependency.downstream_source_id,
                        SourceDependency.upstream_source_id,
                    ).where(SourceDependency.tenant_id == self.user.tenant_id)
                )
            ).all()
        )
        candidate_edges = [
            (str(downstream), str(upstream))
            for downstream, upstream in existing_edges
            if str(downstream) != str(source.id)
        ] + [(str(source.id), dependency_id) for dependency_id in dependency_ids]
        if dependency_graph_has_cycle(candidate_edges):
            raise AppError("SOURCE_DEPENDENCY_CYCLE", "Dependency source membentuk siklus.", 409)
        await self.session.execute(
            delete(SourceDependency).where(
                SourceDependency.tenant_id == self.user.tenant_id,
                SourceDependency.downstream_source_id == source.id,
            )
        )
        for dependency_id in dependency_ids:
            self.session.add(
                SourceDependency(
                    tenant_id=self.user.tenant_id,
                    downstream_source_id=source.id,
                    upstream_source_id=dependency_id,
                )
            )
        source.sync_schedule = data.sync_schedule
        source.schedule_timezone = data.schedule_timezone
        source.concurrency_policy = data.concurrency_policy
        source.schedule_revision += 1
        source.last_scheduled_at = datetime.now(timezone.utc) if data.sync_schedule else None
        audit(
            self.session,
            self.user,
            "source.schedule_updated",
            source.id,
            revision_no=source.schedule_revision,
            sync_schedule=source.sync_schedule,
            schedule_timezone=source.schedule_timezone,
            concurrency_policy=source.concurrency_policy,
            dependency_source_ids=dependency_ids,
        )
        return {**record(source), "dependency_source_ids": dependency_ids}
