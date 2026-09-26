from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantEntity


class AITaskPolicy(TenantEntity, Base):
    __tablename__ = "ai_task_policy"
    __table_args__ = (UniqueConstraint("tenant_id", "code"), {"schema": "platform"})
    code: Mapped[str] = mapped_column(String(63))
    purpose: Mapped[str] = mapped_column(String(40))
    prompt_version: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(100))
    allowed_models: Mapped[list] = mapped_column(JSONB, default=list)
    revision_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
