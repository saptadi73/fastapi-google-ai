from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantEntity


class DataSource(TenantEntity, Base):
    __tablename__ = "data_source"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_code"),
        UniqueConstraint("tenant_id", "id", name="uq_data_source_tenant_id"),
        CheckConstraint(
            "concurrency_policy IN ('QUEUE_LATEST', 'SKIP_IF_RUNNING')",
            name="ck_source_concurrency_policy",
        ),
        CheckConstraint(
            "access_status IN ('ACCESS_POLICY_REQUIRED', 'POLICY_APPROVED')",
            name="ck_source_access_status",
        ),
        CheckConstraint("access_revision >= 1", name="ck_source_access_revision"),
        CheckConstraint(
            "access_review_status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="ck_source_access_review_status",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "access_metadata_editor_id"],
            ["platform.app_user.tenant_id", "platform.app_user.id"],
            name="fk_source_access_editor_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "access_reviewed_by"],
            ["platform.app_user.tenant_id", "platform.app_user.id"],
            name="fk_source_access_reviewer_tenant",
        ),
        {"schema": "platform"},
    )
    source_code: Mapped[str] = mapped_column(String(63))
    name: Mapped[str] = mapped_column(String(200))
    spreadsheet_id: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    owner_user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    credential_ref: Mapped[str] = mapped_column(String(100), default="default")
    status: Mapped[str] = mapped_column(String(40), default="DISCOVERED")
    access_status: Mapped[str] = mapped_column(
        String(40), default="ACCESS_POLICY_REQUIRED", server_default="ACCESS_POLICY_REQUIRED"
    )
    access_revision: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    access_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    approval_assignees: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    approval_revision: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    release_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    release_policy_revision: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    access_metadata_editor_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)
    access_review_status: Mapped[str] = mapped_column(
        String(20), default="PENDING", server_default="PENDING"
    )
    access_reviewed_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)
    access_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    access_review_reason: Mapped[str] = mapped_column(String(40), default="", server_default="")
    sync_schedule: Mapped[str | None] = mapped_column(String(100))
    schedule_timezone: Mapped[str] = mapped_column(String(100), default="UTC")
    concurrency_policy: Mapped[str] = mapped_column(String(30), default="QUEUE_LATEST")
    schedule_revision: Mapped[int] = mapped_column(Integer, default=1)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    last_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unlinked_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    unlinked_to_source_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.data_source.id"))
    unlink_reason: Mapped[str | None] = mapped_column(String(500))
    paused_before_unlink: Mapped[bool | None] = mapped_column(Boolean)


class SourceSheet(TenantEntity, Base):
    __tablename__ = "source_sheet"
    __table_args__ = (
        UniqueConstraint("source_id", "sheet_id"),
        CheckConstraint("classification_revision >= 1", name="ck_sheet_classification_revision"),
        CheckConstraint("watermark_revision >= 1", name="ck_sheet_watermark_revision"),
        CheckConstraint(
            "(watermark_source_column IS NULL AND watermark_kind IS NULL "
            "AND watermark_value IS NULL AND watermark_updated_at IS NULL) OR "
            "(watermark_source_column IS NOT NULL AND watermark_kind IN "
            "('INTEGER', 'DECIMAL', 'DATE', 'DATETIME'))",
            name="ck_sheet_watermark_complete",
        ),
        CheckConstraint(
            "(classification_status = 'CLASSIFICATION_REQUIRED' AND dataset_kind IS NULL "
            "AND classification_confirmed_by IS NULL AND classification_confirmed_at IS NULL) OR "
            "(classification_status = 'CONFIRMED' AND dataset_kind IS NOT NULL "
            "AND dataset_kind IN ('MASTER', 'NON_MASTER') "
            "AND classification_confirmed_by IS NOT NULL AND classification_confirmed_at IS NOT NULL)",
            name="ck_sheet_classification_state",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "classification_confirmed_by"],
            ["platform.app_user.tenant_id", "platform.app_user.id"],
            name="fk_sheet_classification_actor_tenant",
            use_alter=True,
        ),
        {"schema": "platform"},
    )
    source_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.data_source.id"))
    sheet_id: Mapped[int] = mapped_column(Integer)
    sheet_name: Mapped[str] = mapped_column(String(200))
    range_a1: Mapped[str] = mapped_column(String(100), default="A:CV")
    header_row: Mapped[int] = mapped_column(Integer, default=1)
    data_start_row: Mapped[int] = mapped_column(Integer, default=2)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_present: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    last_fingerprint: Mapped[str | None] = mapped_column(String(64))
    dataset_kind: Mapped[str | None] = mapped_column(String(20))
    classification_status: Mapped[str] = mapped_column(
        String(32), default="CLASSIFICATION_REQUIRED", server_default="CLASSIFICATION_REQUIRED"
    )
    classification_revision: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    classification_confirmed_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    classification_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    watermark_source_column: Mapped[str | None] = mapped_column(String(200))
    watermark_kind: Mapped[str | None] = mapped_column(String(20))
    watermark_value: Mapped[str | None] = mapped_column(String(200))
    watermark_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    watermark_revision: Mapped[int] = mapped_column(Integer, default=1)
    active_configuration_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("platform.configuration_version.id", use_alter=True, name="fk_sheet_active_configuration"),
    )


class ProfilingRun(TenantEntity, Base):
    __tablename__ = "profiling_run"
    __table_args__ = {"schema": "platform"}
    source_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.data_source.id"))
    source_sheet_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.source_sheet.id"))
    fingerprint: Mapped[str] = mapped_column(String(64))
    profile_json: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(40), default="SUCCEEDED")


class SourceDependency(TenantEntity, Base):
    __tablename__ = "source_dependency"
    __table_args__ = (
        UniqueConstraint("tenant_id", "downstream_source_id", "upstream_source_id"),
        CheckConstraint(
            "downstream_source_id <> upstream_source_id", name="ck_source_dependency_distinct"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "downstream_source_id"],
            ["platform.data_source.tenant_id", "platform.data_source.id"],
            name="fk_source_dependency_downstream_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "upstream_source_id"],
            ["platform.data_source.tenant_id", "platform.data_source.id"],
            name="fk_source_dependency_upstream_tenant",
            ondelete="CASCADE",
        ),
        {"schema": "platform"},
    )
    downstream_source_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    upstream_source_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
