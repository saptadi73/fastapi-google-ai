"""add approved master column relation registry"""

from alembic import op
import sqlalchemy as sa

revision = "7e41d2b9c8aa"
down_revision = "6d1305460956"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "master_column_binding",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("source_sheet_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("source_column", sa.String(200), nullable=False),
        sa.Column("master_definition_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("master_field", sa.String(63), nullable=False),
        sa.Column("master_version", sa.Integer(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("normalization", sa.String(40), nullable=False, server_default="TRIM_CASEFOLD"),
        sa.Column("cardinality", sa.String(20), nullable=False, server_default="MANY_TO_ONE"),
        sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("created_by", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("approved_by", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["platform.tenant.id"]),
        sa.ForeignKeyConstraint(["source_sheet_id"], ["platform.source_sheet.id"]),
        sa.ForeignKeyConstraint(["master_definition_id"], ["platform.master_definition.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["platform.app_user.id"]),
        sa.UniqueConstraint("tenant_id", "source_sheet_id", "source_column", name="uq_master_column_binding"),
        schema="platform",
    )


def downgrade():
    op.drop_table("master_column_binding", schema="platform")
