from app.core.exceptions import AppError
from app.domain.enums import EDIT_ROLES
from app.models.base import now
from app.models.source import DataSource, SourceSheet
from app.repositories.source_repository import SourceRepository
from app.services.audit_service import audit


def classification_blocker(sheet):
    if sheet.classification_status != "CONFIRMED" or sheet.dataset_kind is None:
        return {
            "code": "CLASSIFICATION_REQUIRED",
            "message": "Konfirmasi master/non-master untuk tab ini terlebih dahulu.",
        }
    if sheet.dataset_kind == "MASTER":
        return {
            "code": "MASTER_RUNTIME_PENDING",
            "message": "Registry, binding, dan storage master tersedia, tetapi alur review/apply import belum tersedia. Jangan memuat master sebagai dataset mandiri.",
        }
    if sheet.dataset_kind != "NON_MASTER":
        return {"code": "CLASSIFICATION_INVALID", "message": "Jenis dataset tidak didukung."}
    return None


def require_classification(sheet):
    if blocker := classification_blocker(sheet):
        raise AppError(blocker["code"], f"Tab {sheet.sheet_name} ({sheet.id}): {blocker['message']}", 409)


def classification_record(sheet):
    blocker = classification_blocker(sheet)
    return {
        "schema_version": "1.0",
        "classification_scope": "SHEET",
        "source_sheet_id": sheet.id,
        "dataset_kind": sheet.dataset_kind,
        "status": sheet.classification_status,
        "revision_no": sheet.classification_revision,
        "confirmed_by": sheet.classification_confirmed_by,
        "confirmed_at": sheet.classification_confirmed_at,
        "execution_ready": blocker is None,
        "blocking_reason": blocker,
    }


class ClassificationService:
    def __init__(self, session, user):
        self.session, self.user = session, user
        self.repo = SourceRepository(session, user.tenant_id)

    async def locked_sheet(self, sheet_id):
        # Refresh objects already read earlier in this transaction after acquiring the lock.
        sheet = await self.session.scalar(
            self.repo.query(SourceSheet)
            .where(SourceSheet.id == str(sheet_id))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if sheet is None:
            raise AppError("RESOURCE_NOT_FOUND", "Tab tidak ditemukan.", 404)
        return sheet

    async def get(self, sheet_id):
        result = classification_record(await self.repo.get(SourceSheet, sheet_id))
        if result["dataset_kind"] == "MASTER":
            from app.services.master_service import MasterService

            binding = await MasterService(self.session, self.user).binding_detail(sheet_id)
            result["master_binding"] = {
                key: binding[key] for key in ("binding", "metadata_ready", "blocking_reason")
            }
        return result

    async def update(self, sheet_id, data):
        if self.user.role not in EDIT_ROLES:
            raise AppError("FORBIDDEN", "Peran tidak dapat mengubah klasifikasi.", 403)
        sheet = await self.locked_sheet(sheet_id)
        if data.revision_no != sheet.classification_revision:
            raise AppError("CLASSIFICATION_CONFLICT", "Revisi klasifikasi berubah; muat ulang tab.", 409)
        kind = data.dataset_kind.value
        if sheet.classification_status == "CONFIRMED" and sheet.dataset_kind == kind:
            return classification_record(sheet)
        if sheet.active_configuration_id and kind != "NON_MASTER":
            raise AppError(
                "CLASSIFICATION_ACTIVE_CONFLICT",
                "Tab dengan konfigurasi aktif tidak dapat diubah menjadi master tanpa migrasi target.",
                409,
            )
        before = classification_record(sheet)
        sheet.dataset_kind = kind
        sheet.classification_status = "CONFIRMED"
        sheet.classification_revision += 1
        sheet.classification_confirmed_by = self.user.id
        sheet.classification_confirmed_at = now()
        audit(
            self.session,
            self.user,
            "source_sheet.classified",
            sheet.id,
            before={"dataset_kind": before["dataset_kind"], "revision_no": before["revision_no"]},
            after={"dataset_kind": kind, "revision_no": sheet.classification_revision},
        )
        await self.session.flush()
        return classification_record(sheet)

    async def require_source_ready(self, source_id, *, lock=False):
        await self.repo.get(DataSource, source_id)
        query = (
            self.repo.query(SourceSheet)
            .where(SourceSheet.source_id == str(source_id), SourceSheet.enabled)
            .order_by(SourceSheet.id)
        )
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        sheets = list((await self.session.scalars(query)).all())
        if not sheets:
            raise AppError("SOURCE_NOT_FOUND", "Tidak ada tab aktif.", 404)
        for sheet in sheets:
            require_classification(sheet)
        return sheets
