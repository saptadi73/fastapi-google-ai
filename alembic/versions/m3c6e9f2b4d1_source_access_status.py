"""track BE16 source access status separately from ETL status"""

import sqlalchemy as sa

from alembic import op

revision = "m3c6e9f2b4d1"
down_revision = "l2b5d8e1a3c0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "data_source",
        sa.Column(
            "access_status",
            sa.String(40),
            nullable=False,
            server_default="ACCESS_POLICY_REQUIRED",
        ),
        schema="platform",
    )
    op.create_check_constraint(
        "ck_source_access_status",
        "data_source",
        "access_status IN ('ACCESS_POLICY_REQUIRED', 'POLICY_APPROVED')",
        schema="platform",
    )


def downgrade():
    op.drop_constraint("ck_source_access_status", "data_source", schema="platform", type_="check")
    op.drop_column("data_source", "access_status", schema="platform")