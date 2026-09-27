"""add BE16 optimistic revision for source access metadata"""

import sqlalchemy as sa

from alembic import op

revision = "o5e8a1b4d6f3"
down_revision = "n4d7f0a3c5e2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "data_source",
        sa.Column("access_revision", sa.Integer(), nullable=False, server_default=sa.text("1")),
        schema="platform",
    )
    op.create_check_constraint(
        "ck_source_access_revision", "data_source", "access_revision >= 1", schema="platform"
    )


def downgrade():
    op.drop_constraint("ck_source_access_revision", "data_source", schema="platform", type_="check")
    op.drop_column("data_source", "access_revision", schema="platform")