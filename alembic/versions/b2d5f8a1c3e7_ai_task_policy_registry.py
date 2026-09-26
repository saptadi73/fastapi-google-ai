"""add tenant-scoped AI task policy registry"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b2d5f8a1c3e7"
down_revision = "a1c4e7f9b2d0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_task_policy",
        sa.Column("code", sa.String(length=63), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("prompt_version", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("allowed_models", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("approved_by", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("purpose IN ('ETL_CONFIG','TAXONOMY_RECOMMEND','NL2SQL')", name="ck_ai_task_policy_purpose"),
        sa.CheckConstraint("status IN ('DRAFT','APPROVED','REJECTED')", name="ck_ai_task_policy_status"),
        sa.CheckConstraint("revision_no >= 1", name="ck_ai_task_policy_revision"),
        sa.ForeignKeyConstraint(["created_by"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["platform.tenant.id"]),
        sa.ForeignKeyConstraint(["tenant_id", "created_by"], ["platform.app_user.tenant_id", "platform.app_user.id"], name="fk_ai_task_policy_created_by_tenant"),
        sa.ForeignKeyConstraint(["tenant_id", "approved_by"], ["platform.app_user.tenant_id", "platform.app_user.id"], name="fk_ai_task_policy_approved_by_tenant"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ai_task_policy_tenant_id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_ai_task_policy_code"),
        schema="platform",
    )
    op.create_index("ix_platform_ai_task_policy_tenant_id", "ai_task_policy", ["tenant_id"], schema="platform")


def downgrade():
    op.drop_index("ix_platform_ai_task_policy_tenant_id", table_name="ai_task_policy", schema="platform")
    op.drop_table("ai_task_policy", schema="platform")
