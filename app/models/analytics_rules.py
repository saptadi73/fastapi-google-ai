from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantEntity


class AnalyticsRuleBundle(TenantEntity, Base):
    __tablename__ = "analytics_rule_bundle"
    __table_args__ = {"schema": "platform"}
    product_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.data_product.id"))
    source_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.data_source.id"))
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    definition: Mapped[dict] = mapped_column(JSONB)
    review_hash: Mapped[str] = mapped_column(String(64))
    semantic_hash: Mapped[str] = mapped_column(String(64))
    sheet_hash: Mapped[str | None] = mapped_column(String(64))
    decision_reason: Mapped[str | None] = mapped_column(String(1000))
