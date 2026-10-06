"""Add version-bound technical and unit release approvals."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "x4n7j0e3g5i2"
down_revision = "w3m6i9d2f4h1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("data_source", sa.Column("release_policy", JSONB(), nullable=True), schema="platform")
    op.add_column("data_source", sa.Column("release_policy_revision", sa.Integer(),
                                           server_default="1", nullable=False), schema="platform")
    op.add_column("configuration_version", sa.Column("release_decisions", JSONB(),
                                                     server_default=sa.text("'{}'::jsonb"),
                                                     nullable=False), schema="platform")


def downgrade():
    op.drop_column("configuration_version", "release_decisions", schema="platform")
    op.drop_column("data_source", "release_policy_revision", schema="platform")
    op.drop_column("data_source", "release_policy", schema="platform")
