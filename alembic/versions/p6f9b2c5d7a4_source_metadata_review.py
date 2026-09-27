"""add BE16 source metadata review lifecycle"""

import sqlalchemy as sa

from alembic import op

revision = "p6f9b2c5d7a4"
down_revision = "o5e8a1b4d6f3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("data_source", sa.Column("access_metadata_editor_id", sa.Uuid(), nullable=True), schema="platform")
    op.add_column(
        "data_source",
        sa.Column("access_review_status", sa.String(20), nullable=False, server_default="PENDING"),
        schema="platform",
    )
    op.add_column("data_source", sa.Column("access_reviewed_by", sa.Uuid(), nullable=True), schema="platform")
    op.add_column("data_source", sa.Column("access_reviewed_at", sa.DateTime(timezone=True), nullable=True), schema="platform")
    op.add_column(
        "data_source",
        sa.Column("access_review_reason", sa.String(40), nullable=False, server_default=""),
        schema="platform",
    )
    op.create_check_constraint(
        "ck_source_access_review_status",
        "data_source",
        "access_review_status IN ('PENDING', 'APPROVED', 'REJECTED')",
        schema="platform",
    )
    for field, name in (
        ("access_metadata_editor_id", "fk_source_access_editor_tenant"),
        ("access_reviewed_by", "fk_source_access_reviewer_tenant"),
    ):
        op.create_foreign_key(
            name, "data_source", "app_user", ["tenant_id", field], ["tenant_id", "id"],
            source_schema="platform", referent_schema="platform",
        )


def downgrade():
    op.drop_constraint("fk_source_access_reviewer_tenant", "data_source", schema="platform", type_="foreignkey")
    op.drop_constraint("fk_source_access_editor_tenant", "data_source", schema="platform", type_="foreignkey")
    op.drop_constraint("ck_source_access_review_status", "data_source", schema="platform", type_="check")
    for field in (
        "access_review_reason", "access_reviewed_at", "access_reviewed_by",
        "access_review_status", "access_metadata_editor_id",
    ):
        op.drop_column("data_source", field, schema="platform")