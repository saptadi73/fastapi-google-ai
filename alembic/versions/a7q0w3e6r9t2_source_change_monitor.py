"""Add Drive metadata checkpoints for source change monitoring."""

import sqlalchemy as sa

from alembic import op

revision = "a7q0w3e6r9t2"
down_revision = ("z6p9c2m5t8v1", "c9s2f5p8w1y4")
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "data_source", sa.Column("drive_modified_at", sa.DateTime(timezone=True), nullable=True),
        schema="platform",
    )
    op.add_column(
        "data_source", sa.Column("change_checked_at", sa.DateTime(timezone=True), nullable=True),
        schema="platform",
    )
    op.create_index(
        "ix_data_source_change_checked_at", "data_source", ["change_checked_at"], schema="platform"
    )


def downgrade():
    op.drop_index("ix_data_source_change_checked_at", table_name="data_source", schema="platform")
    op.drop_column("data_source", "change_checked_at", schema="platform")
    op.drop_column("data_source", "drive_modified_at", schema="platform")
