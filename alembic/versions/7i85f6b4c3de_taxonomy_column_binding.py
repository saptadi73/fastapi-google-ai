"""add taxonomy column bindings"""
from alembic import op
import sqlalchemy as sa

revision = "7i85f6b4c3de"
down_revision = "7h74f5b2c3de"
branch_labels = None
depends_on = None


def upgrade():
    # TenantEntity audit columns were added to the ORM after the initial registry migration.
    for table in ("taxonomy", "taxonomy_term"):
        op.add_column(table, sa.Column("fingerprint", sa.String(64), nullable=True), schema="platform")
        op.add_column(table, sa.Column("snapshot_hash", sa.String(64), nullable=True), schema="platform")
        op.add_column(table, sa.Column("approved_by", sa.Uuid(as_uuid=False), nullable=True), schema="platform")
        op.add_column(table, sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True), schema="platform")
        op.execute(sa.text(f"UPDATE platform.{table} SET fingerprint = repeat('0',64), snapshot_hash = repeat('0',64) WHERE fingerprint IS NULL"))
        op.alter_column(table, "fingerprint", nullable=False, schema="platform")
        op.alter_column(table, "snapshot_hash", nullable=False, schema="platform")
        op.create_foreign_key(f"fk_{table}_approved_by", table, "app_user", ["approved_by"], ["id"], source_schema="platform", referent_schema="platform")
    op.add_column("taxonomy_term", sa.Column("created_by", sa.Uuid(as_uuid=False), nullable=True), schema="platform")
    op.execute(sa.text("UPDATE platform.taxonomy_term SET created_by = (SELECT created_by FROM platform.taxonomy WHERE platform.taxonomy.id = platform.taxonomy_term.taxonomy_id) WHERE created_by IS NULL"))
    op.alter_column("taxonomy_term", "created_by", nullable=False, schema="platform")
    op.create_foreign_key("fk_taxonomy_term_created_by", "taxonomy_term", "app_user", ["created_by"], ["id"], source_schema="platform", referent_schema="platform")
    op.create_table(
        "taxonomy_column_binding",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("approved_by", sa.Uuid(as_uuid=False)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("source_sheet_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("source_column", sa.String(200), nullable=False),
        sa.Column("taxonomy_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("taxonomy_version", sa.Integer(), nullable=False),
        sa.Column("required", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("normalization", sa.String(40), server_default="TRIM_CASEFOLD", nullable=False),
        sa.Column("revision_no", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(20), server_default="DRAFT", nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["platform.tenant.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["source_sheet_id"], ["platform.source_sheet.id"]),
        sa.ForeignKeyConstraint(["taxonomy_id"], ["platform.taxonomy.id"]),
        sa.UniqueConstraint("tenant_id", "source_sheet_id", "source_column", name="uq_taxonomy_column_binding"),
        schema="platform",
    )


def downgrade():
    op.drop_table("taxonomy_column_binding", schema="platform")
    for table in ("taxonomy_term", "taxonomy"):
        op.drop_constraint(f"fk_{table}_approved_by", table, schema="platform", type_="foreignkey")
        for column in ("approved_at", "approved_by", "snapshot_hash", "fingerprint"):
            op.drop_column(table, column, schema="platform")
    op.drop_constraint("fk_taxonomy_term_created_by", "taxonomy_term", schema="platform", type_="foreignkey")
    op.drop_column("taxonomy_term", "created_by", schema="platform")
