"""add targeted notification recipients"""

import sqlalchemy as sa

from alembic import op

revision = "s9i2e5f8a0d7"
down_revision = "r8h1d4e7f9c6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "operational_notification",
        sa.Column("recipient_user_id", sa.Uuid(), nullable=True),
        schema="platform",
    )
    op.create_index(
        "ix_platform_operational_notification_recipient_user_id",
        "operational_notification",
        ["recipient_user_id"],
        schema="platform",
    )
    op.create_foreign_key(
        "fk_operational_notification_recipient_user",
        "operational_notification",
        "app_user",
        ["recipient_user_id"],
        ["id"],
        source_schema="platform",
        referent_schema="platform",
    )
    op.create_foreign_key(
        "fk_operational_notification_recipient_tenant",
        "operational_notification",
        "app_user",
        ["tenant_id", "recipient_user_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
    )


def downgrade():
    op.drop_column("operational_notification", "recipient_user_id", schema="platform")
