from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantEntity


class Taxonomy(TenantEntity, Base):
    __tablename__ = "taxonomy"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_taxonomy_code"), {"schema": "platform"})
    code: Mapped[str] = mapped_column(String(63))
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    definition_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))


class TaxonomyTerm(TenantEntity, Base):
    __tablename__ = "taxonomy_term"
    __table_args__ = (UniqueConstraint("tenant_id", "taxonomy_id", "code", name="uq_taxonomy_term_code"), {"schema": "platform"})
    taxonomy_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.taxonomy.id"))
    parent_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.taxonomy_term.id"))
    code: Mapped[str] = mapped_column(String(63))
    label: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
