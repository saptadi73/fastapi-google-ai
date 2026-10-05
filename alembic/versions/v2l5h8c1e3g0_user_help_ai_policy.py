"""allow USER_HELP AI task policies"""

from alembic import op

revision = "v2l5h8c1e3g0"
down_revision = "u1k4g7b0d2f9"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "ck_ai_task_policy_purpose", "ai_task_policy", schema="platform", type_="check"
    )
    op.create_check_constraint(
        "ck_ai_task_policy_purpose",
        "ai_task_policy",
        "purpose IN ('ETL_CONFIG','TAXONOMY_RECOMMEND','NL2SQL','USER_HELP')",
        schema="platform",
    )


def downgrade():
    op.execute("DELETE FROM platform.ai_task_policy WHERE purpose = 'USER_HELP'")
    op.drop_constraint(
        "ck_ai_task_policy_purpose", "ai_task_policy", schema="platform", type_="check"
    )
    op.create_check_constraint(
        "ck_ai_task_policy_purpose",
        "ai_task_policy",
        "purpose IN ('ETL_CONFIG','TAXONOMY_RECOMMEND','NL2SQL')",
        schema="platform",
    )

