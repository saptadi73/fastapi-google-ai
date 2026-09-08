from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantEntity


class MasterDefinition(TenantEntity, Base):
    __tablename__ = "master_definition"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_master_definition_code"),
        {"schema": "platform"},
    )
    code: Mapped[str] = mapped_column(String(63))
    name: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list] = mapped_column(JSONB, default=list)
    definition_json: Mapped[dict] = mapped_column(JSONB)
    approved_definition_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    revision_no: Mapped[int] = mapped_column(Integer, default=1)
    approved_version: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    submitted_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MasterSourceBinding(TenantEntity, Base):
    __tablename__ = "master_source_binding"
    __table_args__ = (
        UniqueConstraint("source_sheet_id", name="uq_master_binding_sheet"),
        {"schema": "platform"},
    )
    source_sheet_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.source_sheet.id"))
    master_definition_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.master_definition.id")
    )
    master_version: Mapped[int] = mapped_column(Integer)
    classification_revision: Mapped[int] = mapped_column(Integer)
    revision_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    columns_json: Mapped[list] = mapped_column(JSONB)
    fingerprint: Mapped[str] = mapped_column(String(64))
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MasterColumnBinding(TenantEntity, Base):
    __tablename__ = "master_column_binding"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_sheet_id", "source_column", name="uq_master_column_binding"),
        {"schema": "platform"},
    )
    source_sheet_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.source_sheet.id"))
    source_column: Mapped[str] = mapped_column(String(200))
    master_definition_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.master_definition.id"))
    master_field: Mapped[str] = mapped_column(String(63))
    master_version: Mapped[int] = mapped_column(Integer)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    normalization: Mapped[str] = mapped_column(String(40), default="TRIM_CASEFOLD")
    cardinality: Mapped[str] = mapped_column(String(20), default="MANY_TO_ONE")
    revision_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
