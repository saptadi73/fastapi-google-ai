"""add BE16 access policy registry"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "l2b5d8e1a3c0"
down_revision = "k1a4c7d0f2b9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "access_policy",
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("effect", sa.String(10), nullable=False),
        sa.Column("actions", postgresql.JSONB(), nullable=False),
        sa.Column("required_attribute_ids", postgresql.JSONB(), nullable=False),
        sa.Column("row_scope", postgresql.JSONB(), nullable=False),
        sa.Column("column_rules", postgresql.JSONB(), nullable=False),
        sa.Column("export_allowed", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("submitted_by", sa.Uuid(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Uuid(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.String(500), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("effect IN ('ALLOW','DENY')", name="ck_access_policy_effect"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_access_policy_period"),
        sa.CheckConstraint(
            "status IN ('DRAFT','IN_REVIEW','APPROVED','REVOKED')", name="ck_access_policy_status"
        ),
        sa.ForeignKeyConstraint(["approved_by"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["revoked_by"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["submitted_by"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["platform.tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_access_policy_tenant_id"),
        schema="platform",
    )
    for column in ("tenant_id", "status", "valid_from", "valid_to"):
        op.create_index(f"ix_platform_access_policy_{column}", "access_policy", [column], schema="platform")
    for column, name in (
        ("created_by", "fk_tenant_access_policy_created_by_9e655628"),
        ("submitted_by", "fk_tenant_access_policy_submitted_by_bfa21bb1"),
        ("approved_by", "fk_tenant_access_policy_approved_by_31c9b715"),
        ("revoked_by", "fk_tenant_access_policy_revoked_by_531f8c0a"),
    ):
        op.create_foreign_key(
            name,
            "access_policy",
            "app_user",
            ["tenant_id", column],
            ["tenant_id", "id"],
            source_schema="platform",
            referent_schema="platform",
        )
    op.create_table(
        "access_policy_binding",
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(30), nullable=False),
        sa.Column("resource_id", sa.String(100), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "resource_type IN ('DATA_PRODUCT','SOURCE','MASTER','TAXONOMY')",
            name="ck_access_policy_binding_resource_type",
        ),
        sa.ForeignKeyConstraint(["policy_id"], ["platform.access_policy.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["platform.tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_access_policy_binding_tenant_id"),
        sa.UniqueConstraint("tenant_id", "policy_id", "resource_type", "resource_id"),
        schema="platform",
    )
    for column in ("tenant_id", "policy_id", "resource_type", "resource_id"):
        op.create_index(
            f"ix_platform_access_policy_binding_{column}",
            "access_policy_binding",
            [column],
            schema="platform",
        )
    op.create_foreign_key(
        "fk_tenant_access_policy_bind_policy_id_0846838f",
        "access_policy_binding",
        "access_policy",
        ["tenant_id", "policy_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
    )


def downgrade():
    op.drop_table("access_policy_binding", schema="platform")
    op.drop_table("access_policy", schema="platform")
