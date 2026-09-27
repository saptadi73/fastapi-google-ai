"""add BE16 permission bundles"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "k1a4c7d0f2b9"
down_revision = "j0f3b6c9e1a8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "permission_bundle",
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("actions", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["platform.tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_permission_bundle_tenant_id"),
        schema="platform",
    )
    op.create_index(
        "ix_platform_permission_bundle_tenant_id", "permission_bundle", ["tenant_id"], schema="platform"
    )
    op.create_table(
        "user_permission_grant",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("bundle_id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="ck_user_permission_grant_period"
        ),
        sa.CheckConstraint("status IN ('ACTIVE','REVOKED')", name="ck_user_permission_grant_status"),
        sa.ForeignKeyConstraint(["bundle_id"], ["platform.permission_bundle.id"]),
        sa.ForeignKeyConstraint(["granted_by"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["revoked_by"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["platform.tenant.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["platform.app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_user_permission_grant_tenant_id"),
        schema="platform",
    )
    for column in ("tenant_id", "user_id", "bundle_id", "valid_from", "valid_to", "status"):
        op.create_index(
            f"ix_platform_user_permission_grant_{column}",
            "user_permission_grant",
            [column],
            schema="platform",
        )
    for column, table, name in (
        ("user_id", "app_user", "fk_tenant_user_permission_gr_user_id_aaef10e1"),
        ("bundle_id", "permission_bundle", "fk_tenant_user_permission_gr_bundle_id_a44ded16"),
        ("granted_by", "app_user", "fk_tenant_user_permission_gr_granted_by_242c3e30"),
        ("revoked_by", "app_user", "fk_tenant_user_permission_gr_revoked_by_9b0c994a"),
    ):
        op.create_foreign_key(
            name,
            "user_permission_grant",
            table,
            ["tenant_id", column],
            ["tenant_id", "id"],
            source_schema="platform",
            referent_schema="platform",
        )


def downgrade():
    op.drop_table("user_permission_grant", schema="platform")
    op.drop_table("permission_bundle", schema="platform")
