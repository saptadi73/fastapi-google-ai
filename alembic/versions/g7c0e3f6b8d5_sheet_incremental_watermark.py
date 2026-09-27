"""add sheet incremental watermark"""

import sqlalchemy as sa

from alembic import op

revision = "g7c0e3f6b8d5"
down_revision = "f6b9d2e5a7c4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("source_sheet", sa.Column("watermark_source_column", sa.String(200)), schema="platform")
    op.add_column("source_sheet", sa.Column("watermark_kind", sa.String(20)), schema="platform")
    op.add_column("source_sheet", sa.Column("watermark_value", sa.String(200)), schema="platform")
    op.add_column("source_sheet", sa.Column("watermark_updated_at", sa.DateTime(timezone=True)), schema="platform")
    op.add_column(
        "source_sheet",
        sa.Column("watermark_revision", sa.Integer(), server_default="1", nullable=False),
        schema="platform",
    )
    op.create_check_constraint(
        "ck_sheet_watermark_revision",
        "source_sheet",
        "watermark_revision >= 1",
        schema="platform",
    )
    op.create_check_constraint(
        "ck_sheet_watermark_complete",
        "source_sheet",
        "(watermark_source_column IS NULL AND watermark_kind IS NULL "
        "AND watermark_value IS NULL AND watermark_updated_at IS NULL) OR "
        "(watermark_source_column IS NOT NULL AND watermark_kind IN "
        "('INTEGER', 'DECIMAL', 'DATE', 'DATETIME'))",
        schema="platform",
    )


def downgrade():
    op.drop_constraint("ck_sheet_watermark_complete", "source_sheet", schema="platform", type_="check")
    op.drop_constraint("ck_sheet_watermark_revision", "source_sheet", schema="platform", type_="check")
    op.drop_column("source_sheet", "watermark_revision", schema="platform")
    op.drop_column("source_sheet", "watermark_updated_at", schema="platform")
    op.drop_column("source_sheet", "watermark_value", schema="platform")
    op.drop_column("source_sheet", "watermark_kind", schema="platform")
    op.drop_column("source_sheet", "watermark_source_column", schema="platform")
