"""add BE16 temporary access request workflow"""

import sqlalchemy as sa

from alembic import op

revision = "q7g0c3d6e8b5"
down_revision = "p6f9b2c5d7a4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "access_request",
        sa.Column("requester_id", sa.Uuid(), nullable=False),
        sa.Column("request_type", sa.String(30), nullable=False),
        sa.Column("attribute_id", sa.Uuid(), nullable=True),
        sa.Column("bundle_id", sa.Uuid(), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("business_reason", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.String(500), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=True),
        sa.Column("permission_grant_id", sa.Uuid(), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("valid_to > valid_from", name="ck_access_request_period"),
        sa.CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','CANCELLED','REVOKED')",
            name="ck_access_request_status",
        ),
        sa.CheckConstraint(
            "(request_type = 'ATTRIBUTE' AND attribute_id IS NOT NULL AND bundle_id IS NULL) OR "
            "(request_type = 'PERMISSION_BUNDLE' AND bundle_id IS NOT NULL AND attribute_id IS NULL)",
            name="ck_access_request_target",
        ),
        sa.CheckConstraint(
            "request_type IN ('ATTRIBUTE','PERMISSION_BUNDLE')",
            name="ck_access_request_type",
        ),
        sa.ForeignKeyConstraint(["assignment_id"], ["platform.user_assignment.id"]),
        sa.ForeignKeyConstraint(["attribute_id"], ["platform.access_attribute.id"]),
        sa.ForeignKeyConstraint(["bundle_id"], ["platform.permission_bundle.id"]),
        sa.ForeignKeyConstraint(["permission_grant_id"], ["platform.user_permission_grant.id"]),
        sa.ForeignKeyConstraint(["requester_id"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["platform.tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_access_request_tenant_id"),
        schema="platform",
    )
    for column in (
        "tenant_id",
        "requester_id",
        "request_type",
        "attribute_id",
        "bundle_id",
        "valid_from",
        "valid_to",
        "status",
    ):
        op.create_index(
            f"ix_platform_access_request_{column}",
            "access_request",
            [column],
            schema="platform",
        )
    for column, table, name in (
        ("requester_id", "app_user", "fk_access_request_requester_tenant"),
        ("reviewed_by", "app_user", "fk_access_request_reviewer_tenant"),
        ("attribute_id", "access_attribute", "fk_access_request_attribute_tenant"),
        ("bundle_id", "permission_bundle", "fk_access_request_bundle_tenant"),
        ("assignment_id", "user_assignment", "fk_access_request_assignment_tenant"),
        ("permission_grant_id", "user_permission_grant", "fk_access_request_grant_tenant"),
    ):
        op.create_foreign_key(
            name,
            "access_request",
            table,
            ["tenant_id", column],
            ["tenant_id", "id"],
            source_schema="platform",
            referent_schema="platform",
        )


def downgrade():
    op.drop_table("access_request", schema="platform")
