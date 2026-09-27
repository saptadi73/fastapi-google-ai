"""add BE16 access jurisdiction foundation"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "j0f3b6c9e1a8"
down_revision = "i9e2a5b8d0f7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "access_attribute",
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("attribute_data", postgresql.JSONB(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('DEPARTMENT','BUSINESS_DOMAIN','JURISDICTION','CLEARANCE')",
            name="ck_access_attribute_kind",
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["platform.access_attribute.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["platform.tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_access_attribute_tenant_id"),
        sa.UniqueConstraint("tenant_id", "kind", "code"),
        schema="platform",
    )
    op.create_index("ix_platform_access_attribute_kind", "access_attribute", ["kind"], schema="platform")
    op.create_index(
        "ix_platform_access_attribute_tenant_id", "access_attribute", ["tenant_id"], schema="platform"
    )
    op.create_foreign_key(
        "fk_tenant_access_attribute_parent_id_222c9ce5",
        "access_attribute",
        "access_attribute",
        ["tenant_id", "parent_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
    )
    op.create_table(
        "user_assignment",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("attribute_id", sa.Uuid(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("granted_by", sa.Uuid(), nullable=False),
        sa.Column("revoked_by", sa.Uuid(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(500), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_user_assignment_period"),
        sa.CheckConstraint("status IN ('ACTIVE','REVOKED')", name="ck_user_assignment_status"),
        sa.ForeignKeyConstraint(["attribute_id"], ["platform.access_attribute.id"]),
        sa.ForeignKeyConstraint(["granted_by"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["revoked_by"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["platform.tenant.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["platform.app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_user_assignment_tenant_id"),
        schema="platform",
    )
    for column in ("tenant_id", "user_id", "attribute_id", "valid_from", "valid_to", "status"):
        op.create_index(f"ix_platform_user_assignment_{column}", "user_assignment", [column], schema="platform")
    for column, table, name in (
        ("user_id", "app_user", "fk_tenant_user_assignment_user_id_7d4d0a4a"),
        ("attribute_id", "access_attribute", "fk_tenant_user_assignment_attribute_id_4bb6deac"),
        ("granted_by", "app_user", "fk_tenant_user_assignment_granted_by_894dd25e"),
        ("revoked_by", "app_user", "fk_tenant_user_assignment_revoked_by_75475be5"),
    ):
        op.create_foreign_key(
            name,
            "user_assignment",
            table,
            ["tenant_id", column],
            ["tenant_id", "id"],
            source_schema="platform",
            referent_schema="platform",
        )


def downgrade():
    op.drop_table("user_assignment", schema="platform")
    op.drop_table("access_attribute", schema="platform")
