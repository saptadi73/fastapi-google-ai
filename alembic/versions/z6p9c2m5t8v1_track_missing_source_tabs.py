"""Track source tabs removed from their Google spreadsheet."""

import sqlalchemy as sa

from alembic import op

revision = "z6p9c2m5t8v1"
down_revision = "y5o8k1f4h6j3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "source_sheet",
        sa.Column("is_present", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema="platform",
    )


def downgrade():
    op.drop_column("source_sheet", "is_present", schema="platform")
