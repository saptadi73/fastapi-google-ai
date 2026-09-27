"""reconcile BE15 tenant constraints"""

from alembic import op

revision = "i9e2a5b8d0f7"
down_revision = "h8d1f4a7c9e6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_platform_source_dependency_tenant_id",
        "source_dependency",
        ["tenant_id"],
        schema="platform",
    )
    op.create_unique_constraint(
        "uq_source_dependency_tenant_id",
        "source_dependency",
        ["tenant_id", "id"],
        schema="platform",
    )
    op.create_foreign_key(
        "fk_tenant_ai_usage_log_policy_id_d2b2d437",
        "ai_usage_log",
        "ai_task_policy",
        ["tenant_id", "policy_id"],
        ["tenant_id", "id"],
        source_schema="audit",
        referent_schema="platform",
    )


def downgrade():
    op.drop_constraint(
        "fk_tenant_ai_usage_log_policy_id_d2b2d437",
        "ai_usage_log",
        schema="audit",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_source_dependency_tenant_id",
        "source_dependency",
        schema="platform",
        type_="unique",
    )
    op.drop_index(
        "ix_platform_source_dependency_tenant_id",
        table_name="source_dependency",
        schema="platform",
    )
