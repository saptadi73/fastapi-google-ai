from sqlalchemy import Float, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantEntity


class AuditEvent(TenantEntity, Base):
    __tablename__ = "event_log"
    __table_args__ = {"schema": "audit"}
    user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    event: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)


class AIUsage(TenantEntity, Base):
    __tablename__ = "ai_usage_log"
    __table_args__ = {"schema": "audit"}
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    purpose: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(100))
    response_id: Mapped[str | None] = mapped_column(String(200))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))
