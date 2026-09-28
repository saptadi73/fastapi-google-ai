"""add BE16 delegated access request subject"""

import sqlalchemy as sa

from alembic import op

revision = "r8h1d4e7f9c6"
down_revision = "q7g0c3d6e8b5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("access_request", sa.Column("subject_user_id", sa.Uuid(), nullable=True), schema="platform")
    op.execute(
        "UPDATE platform.access_request SET subject_user_id = requester_id WHERE subject_user_id IS NULL"
    )
    op.alter_column("access_request", "subject_user_id", nullable=False, schema="platform")
    op.create_index(
        "ix_platform_access_request_subject_user_id",
        "access_request",
        ["subject_user_id"],
        schema="platform",
    )
    op.create_foreign_key(
        "fk_access_request_subject_user",
        "access_request",
        "app_user",
        ["subject_user_id"],
        ["id"],
        source_schema="platform",
        referent_schema="platform",
    )
    op.create_foreign_key(
        "fk_access_request_subject_tenant",
        "access_request",
        "app_user",
        ["tenant_id", "subject_user_id"],
        ["tenant_id", "id"],
        source_schema="platform",
        referent_schema="platform",
    )


def downgrade():
    op.drop_column("access_request", "subject_user_id", schema="platform")
