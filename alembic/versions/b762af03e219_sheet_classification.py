"""Add explicit per-tab classification; existing tabs require confirmation."""

import sqlalchemy as sa

from alembic import op

revision = "b762af03e219"
down_revision = "9c32a61d740e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("source_sheet", sa.Column("dataset_kind", sa.String(20), nullable=True), schema="platform")
    op.add_column(
        "source_sheet",
        sa.Column(
            "classification_status", sa.String(32), nullable=False, server_default="CLASSIFICATION_REQUIRED"
        ),
        schema="platform",
    )
    op.add_column(
        "source_sheet",
        sa.Column("classification_revision", sa.Integer(), nullable=False, server_default=sa.text("1")),
        schema="platform",
    )
    op.add_column(
        "source_sheet", sa.Column("classification_confirmed_by", sa.Uuid(), nullable=True), schema="platform"
    )
    op.add_column(
        "source_sheet",
        sa.Column("classification_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        schema="platform",
    )
    op.create_check_constraint(
        "ck_sheet_classification_revision", "source_sheet", "classification_revision >= 1", schema="platform"
    )
    op.create_check_constraint(
        "ck_sheet_classification_state",
        "source_sheet",
        "(classification_status = 'CLASSIFICATION_REQUIRED' AND dataset_kind IS NULL "
        "AND classification_confirmed_by IS NULL AND classification_confirmed_at IS NULL) OR "
        "(classification_status = 'CONFIRMED' AND dataset_kind IS NOT NULL "
        "AND dataset_kind IN ('MASTER', 'NON_MASTER') "
        "AND classification_confirmed_by IS NOT NULL AND classification_confirmed_at IS NOT NULL)",
        schema="platform",
    )
    op.create_foreign_key(
        "fk_sheet_classification_actor_tenant",
        "source_sheet",
        "app_user",
        ["tenant_id", "classification_confirmed_by"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
        use_alter=True,
    )


def downgrade():
    op.drop_constraint(
        "fk_sheet_classification_actor_tenant", "source_sheet", schema="platform", type_="foreignkey"
    )
    op.drop_constraint("ck_sheet_classification_state", "source_sheet", schema="platform", type_="check")
    op.drop_constraint("ck_sheet_classification_revision", "source_sheet", schema="platform", type_="check")
    for column in (
        "classification_confirmed_at",
        "classification_confirmed_by",
        "classification_revision",
        "classification_status",
        "dataset_kind",
    ):
        op.drop_column("source_sheet", column, schema="platform")
