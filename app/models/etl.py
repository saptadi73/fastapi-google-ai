from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantEntity


class Job(TenantEntity, Base):
    __tablename__ = "job"
    __table_args__ = {"schema": "platform"}
    kind: Mapped[str] = mapped_column(String(30))
    source_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.data_source.id"))
    requested_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Snapshot(TenantEntity, Base):
    __tablename__ = "snapshot"
    __table_args__ = {"schema": "raw"}
    source_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.data_source.id"))
    source_sheet_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.source_sheet.id"))
    content_hash: Mapped[str] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(Integer)
    values: Mapped[list] = mapped_column(JSONB)


class ETLRun(TenantEntity, Base):
    __tablename__ = "etl_run"
    __table_args__ = (UniqueConstraint("tenant_id", "run_key"), {"schema": "platform"})
    source_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.data_source.id"))
    source_sheet_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.source_sheet.id"))
    configuration_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.configuration_version.id")
    )
    snapshot_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("raw.snapshot.id"))
    run_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(40), default="RUNNING")
    rows_extracted: Mapped[int] = mapped_column(Integer, default=0)
    rows_loaded: Mapped[int] = mapped_column(Integer, default=0)
    rows_quarantined: Mapped[int] = mapped_column(Integer, default=0)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StagingRow(TenantEntity, Base):
    __tablename__ = "row"
    __table_args__ = {"schema": "staging"}
    etl_run_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.etl_run.id"))
    source_row: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSONB)


class QualityIssue(TenantEntity, Base):
    __tablename__ = "row_issue"
    __table_args__ = {"schema": "quarantine"}
    etl_run_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.etl_run.id"))
    source_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.data_source.id"))
    source_row: Mapped[int] = mapped_column(Integer)
    data: Mapped[list] = mapped_column(JSONB)
    errors: Mapped[list] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default="OPEN")
    resolution: Mapped[str | None] = mapped_column(Text)
