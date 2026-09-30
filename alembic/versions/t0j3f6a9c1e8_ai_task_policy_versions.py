"""add immutable AI task policy versions"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "t0j3f6a9c1e8"
down_revision = "s9i2e5f8a0d7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_task_policy_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name="fk_ai_task_policy_version_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "policy_id"],
            ["platform.ai_task_policy.tenant_id", "platform.ai_task_policy.id"],
            name="fk_ai_policy_version_policy_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "actor_user_id"],
            ["platform.app_user.tenant_id", "platform.app_user.id"],
            name="fk_ai_policy_version_actor_tenant",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_task_policy_version"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ai_task_policy_version_tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "policy_id", "revision_no", name="uq_ai_policy_version_revision"
        ),
        schema="platform",
    )
    op.create_index(
        "ix_platform_ai_task_policy_version_tenant_id",
        "ai_task_policy_version",
        ["tenant_id"],
        schema="platform",
    )
    op.execute(
        """
        INSERT INTO platform.ai_task_policy_version (
            id, tenant_id, created_at, policy_id, revision_no, action, snapshot_json, actor_user_id
        )
        SELECT id, tenant_id, created_at, id, revision_no, 'BASELINE',
               jsonb_build_object(
                   'code', code,
                   'purpose', purpose,
                   'prompt_version', prompt_version,
                   'model', model,
                   'allowed_models', allowed_models,
                   'data_product_code', data_product_code,
                   'max_context_chars', max_context_chars,
                   'daily_budget_usd', daily_budget_usd,
                   'fallback_model', fallback_model,
                   'status', status,
                   'approved_by', approved_by,
                   'approved_at', approved_at
               ),
               created_by
        FROM platform.ai_task_policy
        """
    )


def downgrade():
    op.drop_table("ai_task_policy_version", schema="platform")