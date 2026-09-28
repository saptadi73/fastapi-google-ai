from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantEntity


class OperationalNotification(TenantEntity, Base):
    __tablename__ = "operational_notification"
    __table_args__ = (
        UniqueConstraint("tenant_id", "event_key"),
        CheckConstraint("severity IN ('INFO','WARN','ERROR')", name="ck_notification_severity"),
        {"schema": "platform"},
    )
    event_key: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(50), index=True)
    severity: Mapped[str] = mapped_column(String(10))
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    recipient_user_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.app_user.id"), nullable=True, index=True
    )
    acknowledged_by: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.app_user.id")
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
