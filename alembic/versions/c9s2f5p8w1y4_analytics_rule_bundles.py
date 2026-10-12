"""Tenant-scoped immutable reviewed analytics formulas and action rules."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import make_url

from alembic import op
from app.core.config import get_settings

revision = "c9s2f5p8w1y4"
down_revision = "b8r1e4o7v0x3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analytics_rule_bundle",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), sa.ForeignKey("platform.tenant.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "product_id", sa.Uuid(as_uuid=False), sa.ForeignKey("platform.data_product.id"), nullable=False
        ),
        sa.Column("source_id", sa.Uuid(as_uuid=False), sa.ForeignKey("platform.data_source.id")),
        sa.Column(
            "created_by", sa.Uuid(as_uuid=False), sa.ForeignKey("platform.app_user.id"), nullable=False
        ),
        sa.Column("approved_by", sa.Uuid(as_uuid=False), sa.ForeignKey("platform.app_user.id")),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("definition", JSONB, nullable=False),
        sa.Column("review_hash", sa.String(64), nullable=False),
        sa.Column("semantic_hash", sa.String(64), nullable=False),
        sa.Column("sheet_hash", sa.String(64)),
        sa.Column("decision_reason", sa.String(1000)),
        sa.UniqueConstraint("tenant_id", "id", name="uq_analytics_rule_bundle_tenant_id"),
        schema="platform",
    )
    op.create_index(
        "ix_platform_analytics_rule_bundle_tenant_id",
        "analytics_rule_bundle",
        ["tenant_id"],
        schema="platform",
    )
    for field, target, suffix in (
        ("product_id", "data_product", "0c709498"),
        ("source_id", "data_source", "988a6f91"),
        ("created_by", "app_user", "cb20bd2f"),
        ("approved_by", "app_user", "17525f1c"),
    ):
        op.create_foreign_key(
            f"fk_tenant_analytics_rule_bun_{field}_{suffix}",
            "analytics_rule_bundle",
            target,
            ["tenant_id", field],
            ["tenant_id", "id"],
            source_schema="platform",
            referent_schema="platform",
        )
    # Reconcile tenant links introduced with source unlinking but absent in older databases.
    names = {
        fk["name"] for fk in sa.inspect(op.get_bind()).get_foreign_keys("data_source", schema="platform")
    }
    for field, target, name in (
        ("unlinked_by", "app_user", "fk_tenant_data_source_unlinked_by_650f74fc"),
        ("unlinked_to_source_id", "data_source", "fk_tenant_data_source_unlinked_to_sour_3e2a6ec5"),
    ):
        if name not in names:
            op.create_foreign_key(
                name,
                "data_source",
                target,
                ["tenant_id", field],
                ["tenant_id", "id"],
                source_schema="platform",
                referent_schema="platform",
            )
    role = make_url(get_settings().database_url.get_secret_value()).username
    if role:
        quoted = op.get_bind().dialect.identifier_preparer.quote(role)
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON platform.analytics_rule_bundle TO {quoted}")


def downgrade():
    op.drop_table("analytics_rule_bundle", schema="platform")
    # Keep reconciled source tenant constraints, which predate this feature in model metadata.
