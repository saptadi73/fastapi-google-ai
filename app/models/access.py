from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantEntity


class AccessAttribute(TenantEntity, Base):
    __tablename__ = "access_attribute"
    __table_args__ = (
        UniqueConstraint("tenant_id", "kind", "code"),
        CheckConstraint(
            "kind IN ('DEPARTMENT','BUSINESS_DOMAIN','JURISDICTION','CLEARANCE','PURPOSE')",
            name="ck_access_attribute_kind",
        ),
        {"schema": "platform"},
    )
    kind: Mapped[str] = mapped_column(String(30), index=True)
    code: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(200))
    parent_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.access_attribute.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    attribute_data: Mapped[dict] = mapped_column(JSONB, default=dict)


class UserAssignment(TenantEntity, Base):
    __tablename__ = "user_assignment"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','REVOKED')", name="ck_user_assignment_status"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_user_assignment_period"),
        {"schema": "platform"},
    )
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"), index=True)
    attribute_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.access_attribute.id"), index=True
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    granted_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    revoked_by: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.app_user.id"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str] = mapped_column(String(500), default="")


class PermissionBundle(TenantEntity, Base):
    __tablename__ = "permission_bundle"
    __table_args__ = (UniqueConstraint("tenant_id", "code"), {"schema": "platform"})
    code: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(500), default="")
    actions: Mapped[list] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class UserPermissionGrant(TenantEntity, Base):
    __tablename__ = "user_permission_grant"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','REVOKED')", name="ck_user_permission_grant_status"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_user_permission_grant_period"),
        {"schema": "platform"},
    )
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"), index=True)
    bundle_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.permission_bundle.id"), index=True
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    granted_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    revoked_by: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.app_user.id"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str] = mapped_column(String(500), default="")


class AccessPolicy(TenantEntity, Base):
    __tablename__ = "access_policy"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code"),
        CheckConstraint("effect IN ('ALLOW','DENY')", name="ck_access_policy_effect"),
        CheckConstraint(
            "status IN ('DRAFT','IN_REVIEW','APPROVED','REVOKED')", name="ck_access_policy_status"
        ),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_access_policy_period"),
        {"schema": "platform"},
    )
    code: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(500), default="")
    effect: Mapped[str] = mapped_column(String(10))
    actions: Mapped[list] = mapped_column(JSONB)
    required_attribute_ids: Mapped[list] = mapped_column(JSONB, default=list)
    row_scope: Mapped[dict] = mapped_column(JSONB, default=dict)
    column_rules: Mapped[dict] = mapped_column(JSONB, default=dict)
    export_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("platform.app_user.id"))
    submitted_by: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.app_user.id"), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.app_user.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.app_user.id"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str] = mapped_column(String(500), default="")


class AccessPolicyBinding(TenantEntity, Base):
    __tablename__ = "access_policy_binding"
    __table_args__ = (
        UniqueConstraint("tenant_id", "policy_id", "resource_type", "resource_id"),
        CheckConstraint(
            "resource_type IN ('DATA_PRODUCT','SOURCE','MASTER','TAXONOMY')",
            name="ck_access_policy_binding_resource_type",
        ),
        {"schema": "platform"},
    )
    policy_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("platform.access_policy.id"), index=True
    )
    resource_type: Mapped[str] = mapped_column(String(30), index=True)
    resource_id: Mapped[str] = mapped_column(String(100), index=True)
