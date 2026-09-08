"""add approved alias map to column bindings"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "7f52e3c9d1ab"
down_revision = "7e41d2b9c8aa"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("master_column_binding", sa.Column("aliases_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), schema="platform")


def downgrade():
    op.drop_column("master_column_binding", "aliases_json", schema="platform")
