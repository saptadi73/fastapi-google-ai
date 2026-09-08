"""Master definition registry and source bindings"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "d83a5f12c906"
down_revision = "b762af03e219"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "master_definition",
        sa.Column("code", sa.String(length=63), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("aliases", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("definition_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("approved_definition_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("approved_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("submitted_by", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("approved_by", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["platform.app_user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["platform.app_user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by"],
            ["platform.app_user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "approved_by"],
            ["platform.app_user.tenant_id", "platform.app_user.id"],
            name="fk_tenant_master_definition_approved_by_f7a5f70c",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["platform.app_user.tenant_id", "platform.app_user.id"],
            name="fk_tenant_master_definition_created_by_9e3f7331",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "submitted_by"],
            ["platform.app_user.tenant_id", "platform.app_user.id"],
            name="fk_tenant_master_definition_submitted_by_ca7d76e4",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["platform.tenant.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_master_definition_code"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_master_definition_tenant_id"),
        schema="platform",
    )
    op.create_index(
        op.f("ix_platform_master_definition_tenant_id"),
        "master_definition",
        ["tenant_id"],
        unique=False,
        schema="platform",
    )
    op.create_table(
        "master_source_binding",
        sa.Column("source_sheet_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("master_definition_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("master_version", sa.Integer(), nullable=False),
        sa.Column("classification_revision", sa.Integer(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("columns_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("approved_by", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["platform.app_user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["platform.app_user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["master_definition_id"],
            ["platform.master_definition.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_sheet_id"],
            ["platform.source_sheet.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "approved_by"],
            ["platform.app_user.tenant_id", "platform.app_user.id"],
            name="fk_tenant_master_source_bind_approved_by_026217c0",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["platform.app_user.tenant_id", "platform.app_user.id"],
            name="fk_tenant_master_source_bind_created_by_8de235b4",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "master_definition_id"],
            ["platform.master_definition.tenant_id", "platform.master_definition.id"],
            name="fk_tenant_master_source_bind_master_definitio_b82f4931",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_sheet_id"],
            ["platform.source_sheet.tenant_id", "platform.source_sheet.id"],
            name="fk_tenant_master_source_bind_source_sheet_id_de7327c2",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["platform.tenant.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_sheet_id", name="uq_master_binding_sheet"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_master_source_binding_tenant_id"),
        schema="platform",
    )
    op.create_index(
        op.f("ix_platform_master_source_binding_tenant_id"),
        "master_source_binding",
        ["tenant_id"],
        unique=False,
        schema="platform",
    )


def downgrade():
    op.drop_index(
        op.f("ix_platform_master_source_binding_tenant_id"),
        table_name="master_source_binding",
        schema="platform",
    )
    op.drop_table("master_source_binding", schema="platform")
    op.drop_index(
        op.f("ix_platform_master_definition_tenant_id"), table_name="master_definition", schema="platform"
    )
    op.drop_table("master_definition", schema="platform")
