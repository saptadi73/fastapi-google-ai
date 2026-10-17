from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantEntity


class DataProduct(TenantEntity, Base):
    __tablename__ = "data_product"
    __table_args__ = (UniqueConstraint("tenant_id", "code"), {"schema": "platform"})
    source_sheet_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.source_sheet.id"), unique=True
    )
    code: Mapped[str] = mapped_column(String(63))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    view_name: Mapped[str] = mapped_column(String(63))
    columns: Mapped[list] = mapped_column(JSONB)
    metrics: Mapped[list] = mapped_column(JSONB, default=list)
    dimensions: Mapped[list] = mapped_column(JSONB, default=list)
    allowed_roles: Mapped[list] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    version: Mapped[int] = mapped_column(Integer, default=1)
    freshness_version: Mapped[int] = mapped_column(Integer, default=0)


class SavedQuery(TenantEntity, Base):
    __tablename__ = "validated_query_template"
    __table_args__ = (UniqueConstraint("tenant_id", "code"), {"schema": "platform"})
    code: Mapped[str] = mapped_column(String(63))
    data_product_code: Mapped[str] = mapped_column(String(63))
    plan: Mapped[dict] = mapped_column(JSONB)
    examples: Mapped[list] = mapped_column(JSONB, default=list)
    allowed_roles: Mapped[list] = mapped_column(JSONB)
    semantic_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))


class JoinRelationship(TenantEntity, Base):
    __tablename__ = "join_relationship"
    __table_args__ = (UniqueConstraint("tenant_id", "code"), {"schema": "platform"})
    code: Mapped[str] = mapped_column(String(63))
    left_product_code: Mapped[str] = mapped_column(String(63))
    left_column: Mapped[str] = mapped_column(String(63))
    right_product_code: Mapped[str] = mapped_column(String(63))
    right_column: Mapped[str] = mapped_column(String(63))
    cardinality: Mapped[str] = mapped_column(String(20))
    join_type: Mapped[str] = mapped_column(String(20), default="LEFT")
    duplicate_policy: Mapped[str] = mapped_column(String(30), default="REJECT_AMBIGUOUS")
    revision_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))


class QueryRequest(TenantEntity, Base):
    __tablename__ = "nl2sql_request_log"
    __table_args__ = {"schema": "platform"}
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    question_hash: Mapped[str] = mapped_column(String(64))
    route: Mapped[str] = mapped_column(String(40))
    plan: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="SUCCEEDED")
    clarification_question: Mapped[str | None] = mapped_column(Text)
    feedback: Mapped[str | None] = mapped_column(Text)


class SavedNL2SQLQuery(TenantEntity, Base):
    __tablename__ = "saved_nl2sql_query"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "source_request_id", name="uq_saved_nl2sql_request_owner"),
        Index("ix_saved_nl2sql_query_owner_created", "tenant_id", "user_id", "created_at"),
        {"schema": "platform"},
    )
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    source_request_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.nl2sql_request_log.id")
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    question: Mapped[str] = mapped_column(Text)
    data_product_code: Mapped[str] = mapped_column(String(63))
    plan: Mapped[dict] = mapped_column(JSONB)
    sql_preview: Mapped[str] = mapped_column(Text)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
