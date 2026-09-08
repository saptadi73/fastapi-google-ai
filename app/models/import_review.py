from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint, Uuid
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


class ImportReviewRow(TenantEntity, Base):
    __tablename__ = "import_review_row"
    __table_args__ = (
        UniqueConstraint("import_review_id", "source_row"),
        CheckConstraint("source_row > 0", name="ck_import_review_row_source_row"),
        {"schema": "staging"},
    )
    import_review_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.import_review.id")
    )
    source_row: Mapped[int] = mapped_column(Integer)
    raw_data: Mapped[dict] = mapped_column(JSONB)
    transformed_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    corrected_data: Mapped[dict] = mapped_column(JSONB, default=dict)


class ImportQuestion(TenantEntity, Base):
    __tablename__ = "import_question"
    __table_args__ = (
        UniqueConstraint("tenant_id", "import_review_id", "question_key"),
        CheckConstraint("revision_no >= 1", name="ck_import_question_revision"),
        CheckConstraint(
            "status IN ('OPEN','ANSWERED','PENDING_APPROVAL','CANCELLED')", name="ck_import_question_status"
        ),
        {"schema": "platform"},
    )
    import_review_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.import_review.id")
    )
    staging_row_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("staging.import_review_row.id")
    )
    source_row: Mapped[int | None] = mapped_column(Integer)
    source_column: Mapped[str | None] = mapped_column(String(63))
    target_column: Mapped[str | None] = mapped_column(String(63))
    question_key: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(40))
    prompt: Mapped[str] = mapped_column(String(2000))
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    allowed_actions: Mapped[list] = mapped_column(JSONB)
    candidates: Mapped[list] = mapped_column(JSONB, default=list)
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)
    revision_no: Mapped[int] = mapped_column(Integer, default=1)


class ImportDecision(TenantEntity, Base):
    __tablename__ = "import_decision"
    __table_args__ = (
        UniqueConstraint("tenant_id", "import_question_id", "revision_no"),
        {"schema": "platform"},
    )
    import_review_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.import_review.id")
    )
    import_question_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.import_question.id")
    )
    decided_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    revision_no: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(40))
    selected_candidate_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    proposed_master_definition_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.master_definition.id")
    )
    reason: Mapped[str] = mapped_column(String(2000), default="")
    before_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    after_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
