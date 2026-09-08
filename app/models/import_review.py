from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantEntity


class ImportReview(TenantEntity, Base):
    __tablename__ = "import_review"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key"),
        CheckConstraint("revision_no >= 1 AND generation >= 1", name="ck_import_review_revision"),
        CheckConstraint(
            "status IN ('VALIDATING','AI_REVIEWING','NEEDS_INPUT','READY_FOR_APPROVAL','APPROVED','APPLYING','SUCCEEDED','FAILED','CANCELLED','STALE_REVIEW')",
            name="ck_import_review_status",
        ),
        {"schema": "platform"},
    )
    source_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.data_source.id"))
    source_sheet_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.source_sheet.id"))
    snapshot_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("raw.snapshot.id"))
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    idempotency_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="VALIDATING", index=True)
    revision_no: Mapped[int] = mapped_column(Integer, default=1)
    generation: Mapped[int] = mapped_column(Integer, default=1)
    dependencies: Mapped[dict] = mapped_column(JSONB)
    configuration_json: Mapped[dict] = mapped_column(JSONB)
    checkpoint: Mapped[dict] = mapped_column(JSONB, default=dict)
    findings: Mapped[list] = mapped_column(JSONB, default=list)
    job_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.job.id"))
