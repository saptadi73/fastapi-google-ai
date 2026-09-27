"""add operational notifications"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "h8d1f4a7c9e6"
down_revision = "g7c0e3f6b8d5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "operational_notification",
        sa.Column("event_key", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("resource_type", sa.String(40), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("acknowledged_by", sa.Uuid(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("severity IN ('INFO','WARN','ERROR')", name="ck_notification_severity"),
        sa.ForeignKeyConstraint(["acknowledged_by"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["platform.tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "event_key"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_operational_notification_tenant_id"),
        schema="platform",
    )
    op.create_index(
        op.f("ix_platform_operational_notification_tenant_id"),
        "operational_notification",
        ["tenant_id"],
        schema="platform",
    )
    op.create_index(
        op.f("ix_platform_operational_notification_kind"),
        "operational_notification",
        ["kind"],
        schema="platform",
    )
    op.create_index(
        op.f("ix_platform_operational_notification_resource_id"),
        "operational_notification",
        ["resource_id"],
        schema="platform",
    )
    op.create_index(
        op.f("ix_platform_operational_notification_acknowledged_at"),
        "operational_notification",
        ["acknowledged_at"],
        schema="platform",
    )
    op.create_foreign_key(
        "fk_tenant_operational_notif_acknowledged_by_8cc163ca",
        "operational_notification",
        "app_user",
        ["tenant_id", "acknowledged_by"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
    )


def downgrade():
    op.drop_table("operational_notification", schema="platform")
