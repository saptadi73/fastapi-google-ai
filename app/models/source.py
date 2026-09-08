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
    __table_args__ = (UniqueConstraint("tenant_id", "source_code"), {"schema": "platform"})
    source_code: Mapped[str] = mapped_column(String(63))
    name: Mapped[str] = mapped_column(String(200))
    spreadsheet_id: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    owner_user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    credential_ref: Mapped[str] = mapped_column(String(100), default="default")
    status: Mapped[str] = mapped_column(String(40), default="DISCOVERED")
    sync_schedule: Mapped[str | None] = mapped_column(String(100))
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    last_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceSheet(TenantEntity, Base):
    __tablename__ = "source_sheet"
    __table_args__ = (
        UniqueConstraint("source_id", "sheet_id"),
        CheckConstraint("classification_revision >= 1", name="ck_sheet_classification_revision"),
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
    last_fingerprint: Mapped[str | None] = mapped_column(String(64))
    dataset_kind: Mapped[str | None] = mapped_column(String(20))
    classification_status: Mapped[str] = mapped_column(
        String(32), default="CLASSIFICATION_REQUIRED", server_default="CLASSIFICATION_REQUIRED"
    )
    classification_revision: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    classification_confirmed_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    classification_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
