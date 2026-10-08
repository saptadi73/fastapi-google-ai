"""Track reversible unlink of duplicate spreadsheet registrations."""

import sqlalchemy as sa
from alembic import op

revision = "y5o8k1f4h6j3"
down_revision = "x4n7j0e3g5i2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("data_source", sa.Column("unlinked_at", sa.DateTime(timezone=True)), schema="platform")
    op.add_column("data_source", sa.Column("unlinked_by", sa.Uuid()), schema="platform")
    op.add_column("data_source", sa.Column("unlinked_to_source_id", sa.Uuid()), schema="platform")
    op.add_column("data_source", sa.Column("unlink_reason", sa.String(500)), schema="platform")
    op.add_column("data_source", sa.Column("paused_before_unlink", sa.Boolean()), schema="platform")
    op.create_foreign_key("fk_source_unlinked_by", "data_source", "app_user", ["unlinked_by"], ["id"], source_schema="platform", referent_schema="platform")
    op.create_foreign_key("fk_source_unlinked_to", "data_source", "data_source", ["unlinked_to_source_id"], ["id"], source_schema="platform", referent_schema="platform")


def downgrade():
    op.drop_constraint("fk_source_unlinked_to", "data_source", schema="platform", type_="foreignkey")
    op.drop_constraint("fk_source_unlinked_by", "data_source", schema="platform", type_="foreignkey")
    for column in ("paused_before_unlink", "unlink_reason", "unlinked_to_source_id", "unlinked_by", "unlinked_at"):
        op.drop_column("data_source", column, schema="platform")
