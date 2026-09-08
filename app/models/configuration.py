from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
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


class Configuration(TenantEntity, Base):
    __tablename__ = "configuration_version"
    __table_args__ = (
        UniqueConstraint("source_sheet_id", "version_no"),
        Index(
            "uq_active_configuration",
            "source_sheet_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        {"schema": "platform"},
    )
    source_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.data_source.id"))
    source_sheet_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.source_sheet.id"))
    version_no: Mapped[int] = mapped_column(Integer)
    revision_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(40), default="NEEDS_REVIEW")
    based_on_fingerprint: Mapped[str] = mapped_column(String(64))
    configuration_json: Mapped[dict] = mapped_column(JSONB)
    review_state: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ai_response_id: Mapped[str | None] = mapped_column(String(200))
    ai_model: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(40))


class Artifact(TenantEntity, Base):
    __tablename__ = "configuration_artifact"
    __table_args__ = (
        Index(
            "uq_runtime_artifact",
            "configuration_version_id",
            unique=True,
            postgresql_where=text("artifact_type = 'RUNTIME_CONFIG' AND is_current"),
        ),
        {"schema": "platform"},
    )
    configuration_version_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.configuration_version.id")
    )
    artifact_type: Mapped[str] = mapped_column(String(30))
    file_name: Mapped[str] = mapped_column(String(200))
    storage_uri: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(120))
    content_hash: Mapped[str] = mapped_column(String(64))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)


class Approval(TenantEntity, Base):
    __tablename__ = "approval"
    __table_args__ = {"schema": "platform"}
    configuration_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.configuration_version.id")
    )
    reviewer_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    decision: Mapped[str] = mapped_column(String(30))
    comment: Mapped[str] = mapped_column(Text, default="")
