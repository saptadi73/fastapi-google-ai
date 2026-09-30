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
        ForeignKeyConstraint(
            ["tenant_id", "data_source_id"],
            ["platform.data_source.tenant_id", "platform.data_source.id"],
            name="fk_ai_task_policy_data_source_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "taxonomy_id"],
            ["platform.taxonomy.tenant_id", "platform.taxonomy.id"],
            name="fk_ai_task_policy_taxonomy_tenant",
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
    data_source_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    taxonomy_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    max_context_chars: Mapped[int] = mapped_column(Integer, default=200_000)
    daily_budget_usd: Mapped[float | None] = mapped_column(Float)
    fallback_model: Mapped[str | None] = mapped_column(String(100))
    revision_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AITaskPolicyVersion(TenantEntity, Base):
    __tablename__ = "ai_task_policy_version"
    __table_args__ = (
        UniqueConstraint("tenant_id", "policy_id", "revision_no", name="uq_ai_policy_version_revision"),
        ForeignKeyConstraint(
            ["tenant_id", "policy_id"],
            ["platform.ai_task_policy.tenant_id", "platform.ai_task_policy.id"],
            name="fk_ai_policy_version_policy_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "actor_user_id"],
            ["platform.app_user.tenant_id", "platform.app_user.id"],
            name="fk_ai_policy_version_actor_tenant",
        ),
        {"schema": "platform"},
    )
    policy_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    revision_no: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(20))
    snapshot_json: Mapped[dict] = mapped_column(JSONB)
    actor_user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
