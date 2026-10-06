"""Add explicit reviewers for each source approval workflow."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "w3m6i9d2f4h1"
down_revision = "v2l5h8c1e3g0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("data_source", sa.Column("approval_assignees", JSONB(), nullable=True), schema="platform")
    op.add_column(
        "data_source",
        sa.Column("approval_revision", sa.Integer(), server_default="1", nullable=False),
        schema="platform",
    )


def downgrade():
    op.drop_column("data_source", "approval_revision", schema="platform")
    op.drop_column("data_source", "approval_assignees", schema="platform")
