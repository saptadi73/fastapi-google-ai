from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantEntity


class AITaskPolicy(TenantEntity, Base):
    __tablename__ = "ai_task_policy"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code"),
        ForeignKeyConstraint(
            ["tenant_id", "data_product_code"],
            ["platform.data_product.tenant_id", "platform.data_product.code"],
            name="fk_ai_task_policy_data_product_tenant",
            ondelete="CASCADE",
        ),
        {"schema": "platform"},
    )
    code: Mapped[str] = mapped_column(String(63))
    purpose: Mapped[str] = mapped_column(String(40))
    prompt_version: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(100))
    allowed_models: Mapped[list] = mapped_column(JSONB, default=list)
    data_product_code: Mapped[str | None] = mapped_column(String(63))
    max_context_chars: Mapped[int] = mapped_column(Integer, default=200_000)
    daily_budget_usd: Mapped[float | None] = mapped_column(Float)
    fallback_model: Mapped[str | None] = mapped_column(String(100))
    revision_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
