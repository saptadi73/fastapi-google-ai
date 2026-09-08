"""Persist configuration review evidence and question resolutions."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "9c32a61d740e"
down_revision = "8224fc00c7af"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "configuration_version",
        sa.Column("review_state", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        schema="platform",
    )


def downgrade():
    op.drop_column("configuration_version", "review_state", schema="platform")
