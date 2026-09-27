"""add BE16 source access metadata and purpose registry kind"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "n4d7f0a3c5e2"
down_revision = "m3c6e9f2b4d1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "data_source",
        sa.Column("access_metadata", postgresql.JSONB(), nullable=True),
        schema="platform",
    )
    op.drop_constraint("ck_access_attribute_kind", "access_attribute", schema="platform", type_="check")
    op.create_check_constraint(
        "ck_access_attribute_kind",
        "access_attribute",
        "kind IN ('DEPARTMENT','BUSINESS_DOMAIN','JURISDICTION','CLEARANCE','PURPOSE')",
        schema="platform",
    )


def downgrade():
    exists = op.get_bind().scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM platform.access_attribute WHERE kind = 'PURPOSE')")
    )
    if exists:
        raise RuntimeError("Hapus atau migrasikan atribut PURPOSE sebelum downgrade BE16.")
    op.drop_constraint("ck_access_attribute_kind", "access_attribute", schema="platform", type_="check")
    op.create_check_constraint(
        "ck_access_attribute_kind",
        "access_attribute",
        "kind IN ('DEPARTMENT','BUSINESS_DOMAIN','JURISDICTION','CLEARANCE')",
        schema="platform",
    )
    op.drop_column("data_source", "access_metadata", schema="platform")