"""add tenant-scoped semantic join relationship registry"""

import sqlalchemy as sa

from alembic import op

revision = "a1c4e7f9b2d0"
down_revision = "9b07c8d6e5fa"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "join_relationship",
        sa.Column("code", sa.String(length=63), nullable=False),
        sa.Column("left_product_code", sa.String(length=63), nullable=False),
        sa.Column("left_column", sa.String(length=63), nullable=False),
        sa.Column("right_product_code", sa.String(length=63), nullable=False),
        sa.Column("right_column", sa.String(length=63), nullable=False),
        sa.Column("cardinality", sa.String(length=20), nullable=False),
        sa.Column("join_type", sa.String(length=20), nullable=False),
        sa.Column("duplicate_policy", sa.String(length=30), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("approved_by", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cardinality IN ('ONE_TO_ONE','MANY_TO_ONE','ONE_TO_MANY')", name="ck_join_relationship_cardinality"),
        sa.CheckConstraint("join_type IN ('LEFT','INNER')", name="ck_join_relationship_type"),
        sa.CheckConstraint("duplicate_policy IN ('REJECT_AMBIGUOUS','AGGREGATE_RIGHT')", name="ck_join_relationship_duplicates"),
        sa.CheckConstraint("status IN ('DRAFT','APPROVED','REJECTED')", name="ck_join_relationship_status"),
        sa.ForeignKeyConstraint(["created_by"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["platform.tenant.id"]),
        sa.ForeignKeyConstraint(["tenant_id", "created_by"], ["platform.app_user.tenant_id", "platform.app_user.id"], name="fk_join_relationship_created_by_tenant"),
        sa.ForeignKeyConstraint(["tenant_id", "approved_by"], ["platform.app_user.tenant_id", "platform.app_user.id"], name="fk_join_relationship_approved_by_tenant"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_join_relationship_tenant_id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_join_relationship_code"),
        schema="platform",
    )
    op.create_index("ix_platform_join_relationship_tenant_id", "join_relationship", ["tenant_id"], schema="platform")


def downgrade():
    op.drop_index("ix_platform_join_relationship_tenant_id", table_name="join_relationship", schema="platform")
    op.drop_table("join_relationship", schema="platform")
