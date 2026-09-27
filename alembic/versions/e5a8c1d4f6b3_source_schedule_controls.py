"""add editable source schedule controls"""

import sqlalchemy as sa

from alembic import op

revision = "e5a8c1d4f6b3"
down_revision = "d4f7b0c3e5a2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "data_source",
        sa.Column("schedule_timezone", sa.String(length=100), server_default="UTC", nullable=False),
        schema="platform",
    )
    op.add_column(
        "data_source",
        sa.Column(
            "concurrency_policy",
            sa.String(length=30),
            server_default="QUEUE_LATEST",
            nullable=False,
        ),
        schema="platform",
    )
    op.add_column(
        "data_source",
        sa.Column("schedule_revision", sa.Integer(), server_default="1", nullable=False),
        schema="platform",
    )
    op.create_check_constraint(
        "ck_source_concurrency_policy",
        "data_source",
        "concurrency_policy IN ('QUEUE_LATEST', 'SKIP_IF_RUNNING')",
        schema="platform",
    )


def downgrade():
    op.drop_constraint(
        "ck_source_concurrency_policy", "data_source", schema="platform", type_="check"
    )
    op.drop_column("data_source", "schedule_revision", schema="platform")
    op.drop_column("data_source", "concurrency_policy", schema="platform")
    op.drop_column("data_source", "schedule_timezone", schema="platform")
