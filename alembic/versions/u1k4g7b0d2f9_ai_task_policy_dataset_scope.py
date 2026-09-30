"""add dataset scopes for ETL and taxonomy AI task policies"""

import sqlalchemy as sa

from alembic import op

revision = "u1k4g7b0d2f9"
down_revision = "t0j3f6a9c1e8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ai_task_policy", sa.Column("data_source_id", sa.Uuid(), nullable=True), schema="platform"
    )
    op.add_column(
        "ai_task_policy", sa.Column("taxonomy_id", sa.Uuid(), nullable=True), schema="platform"
    )
    op.create_foreign_key(
        "fk_ai_task_policy_data_source_tenant",
        "ai_task_policy",
        "data_source",
        ["tenant_id", "data_source_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_ai_task_policy_taxonomy_tenant",
        "ai_task_policy",
        "taxonomy",
        ["tenant_id", "taxonomy_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        ondelete="CASCADE",
    )
    op.execute(
        sa.text(
            "UPDATE platform.ai_task_policy_version "
            "SET snapshot_json = snapshot_json || "
            "jsonb_build_object('data_source_id', NULL, 'taxonomy_id', NULL) "
            "WHERE action = 'BASELINE'"
        )
    )


def downgrade():
    op.drop_column("ai_task_policy", "taxonomy_id", schema="platform")
    op.drop_column("ai_task_policy", "data_source_id", schema="platform")