"""add source job dependencies"""

import sqlalchemy as sa

from alembic import op

revision = "f6b9d2e5a7c4"
down_revision = "e5a8c1d4f6b3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "source_dependency",
        sa.Column("downstream_source_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("upstream_source_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "downstream_source_id <> upstream_source_id", name="ck_source_dependency_distinct"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["platform.tenant.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "downstream_source_id"],
            ["platform.data_source.tenant_id", "platform.data_source.id"],
            name="fk_source_dependency_downstream_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "upstream_source_id"],
            ["platform.data_source.tenant_id", "platform.data_source.id"],
            name="fk_source_dependency_upstream_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "downstream_source_id", "upstream_source_id"),
        schema="platform",
    )


def downgrade():
    op.drop_table("source_dependency", schema="platform")
