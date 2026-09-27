"""scope NL2SQL AI task policies to an optional data product"""

import sqlalchemy as sa

from alembic import op

revision = "c3e6a9b2d4f1"
down_revision = "b2d5f8a1c3e7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ai_task_policy",
        sa.Column("data_product_code", sa.String(length=63), nullable=True),
        schema="platform",
    )
    op.create_foreign_key(
        "fk_ai_task_policy_data_product_tenant",
        "ai_task_policy",
        "data_product",
        ["tenant_id", "data_product_code"],
        ["tenant_id", "code"],
        source_schema="platform",
        referent_schema="platform",
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint(
        "fk_ai_task_policy_data_product_tenant",
        "ai_task_policy",
        schema="platform",
        type_="foreignkey",
    )
    op.drop_column("ai_task_policy", "data_product_code", schema="platform")
