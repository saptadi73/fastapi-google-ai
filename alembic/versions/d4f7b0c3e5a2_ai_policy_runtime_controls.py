"""add AI policy runtime limits, budget and fallback"""

import sqlalchemy as sa

from alembic import op

revision = "d4f7b0c3e5a2"
down_revision = "c3e6a9b2d4f1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ai_task_policy",
        sa.Column("max_context_chars", sa.Integer(), server_default="200000", nullable=False),
        schema="platform",
    )
    op.add_column(
        "ai_task_policy",
        sa.Column("daily_budget_usd", sa.Float(), nullable=True),
        schema="platform",
    )
    op.add_column(
        "ai_task_policy",
        sa.Column("fallback_model", sa.String(length=100), nullable=True),
        schema="platform",
    )
    op.add_column(
        "ai_usage_log",
        sa.Column("policy_id", sa.Uuid(as_uuid=False), nullable=True),
        schema="audit",
    )
    op.create_foreign_key(
        "fk_ai_usage_policy",
        "ai_usage_log",
        "ai_task_policy",
        ["policy_id"],
        ["id"],
        source_schema="audit",
        referent_schema="platform",
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        "fk_ai_usage_policy", "ai_usage_log", schema="audit", type_="foreignkey"
    )
    op.drop_column("ai_usage_log", "policy_id", schema="audit")
    op.drop_column("ai_task_policy", "fallback_model", schema="platform")
    op.drop_column("ai_task_policy", "daily_budget_usd", schema="platform")
    op.drop_column("ai_task_policy", "max_context_chars", schema="platform")
