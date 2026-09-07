from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.etl import Snapshot
from app.models.source import DataSource, ProfilingRun, SourceSheet
from app.repositories.base import record
from app.repositories.source_repository import SourceRepository
from app.schemas.source import spreadsheet_id
from app.services.audit_service import audit
from app.services.google_sheets_service import GoogleSheetsService
from app.services.job_service import enqueue
from app.services.profiling_service import digest, profile_values


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
