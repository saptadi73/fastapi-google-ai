"""normalize alias map to JSONB"""
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "7g63f4a1e2bc"
down_revision = "7f52e3c9d1ab"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("master_column_binding", "aliases_json", schema="platform", type_=postgresql.JSONB(), existing_type=postgresql.JSONB())


def downgrade():
    op.alter_column("master_column_binding", "aliases_json", schema="platform", type_=postgresql.JSONB(), existing_type=postgresql.JSONB())
