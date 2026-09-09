from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantEntity


class TaxonomyMetadata:
    """Metadata already stored by migration 7i85f6b4c3de and written by the API."""

    fingerprint: Mapped[str] = mapped_column(String(64))
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Taxonomy(TaxonomyMetadata, TenantEntity, Base):
    __tablename__ = "taxonomy"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_taxonomy_code"), {"schema": "platform"})
    code: Mapped[str] = mapped_column(String(63))
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    definition_json: Mapped[dict] = mapped_column(JSONB, default=dict)


class TaxonomyTerm(TaxonomyMetadata, TenantEntity, Base):
    __tablename__ = "taxonomy_term"
    __table_args__ = (UniqueConstraint("tenant_id", "taxonomy_id", "code", name="uq_taxonomy_term_code"), {"schema": "platform"})
    taxonomy_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.taxonomy.id"))
    parent_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.taxonomy_term.id"))
    code: Mapped[str] = mapped_column(String(63))
    label: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TaxonomyColumnBinding(TaxonomyMetadata, TenantEntity, Base):
    __tablename__ = "taxonomy_column_binding"
    __table_args__ = (UniqueConstraint("tenant_id", "source_sheet_id", "source_column", name="uq_taxonomy_column_binding"), {"schema": "platform"})
    source_sheet_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.source_sheet.id"))
    source_column: Mapped[str] = mapped_column(String(200))
    taxonomy_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.taxonomy.id"))
    taxonomy_version: Mapped[int] = mapped_column(Integer)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    normalization: Mapped[str] = mapped_column(String(40), default="TRIM_CASEFOLD")
    revision_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")


class TaxonomyVersion(TenantEntity, Base):
    __tablename__ = "taxonomy_version"
    __table_args__ = (UniqueConstraint("tenant_id", "taxonomy_id", "version", name="uq_taxonomy_version"),
                      {"schema": "platform"})
    taxonomy_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.taxonomy.id"))
    version: Mapped[int] = mapped_column(Integer)
    base_version: Mapped[int | None] = mapped_column(Integer)
    revision_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    definition_json: Mapped[dict] = mapped_column(JSONB)
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
