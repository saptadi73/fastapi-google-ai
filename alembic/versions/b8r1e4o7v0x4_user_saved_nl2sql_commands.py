"""Store user-owned NL2SQL commands for safe replay without calling AI."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "b8r1e4o7v0x4"
down_revision = "a7q0w3e6r9t3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "saved_nl2sql_query",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("source_request_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("data_product_code", sa.String(63), nullable=False),
        sa.Column("plan", postgresql.JSONB(), nullable=False),
        sa.Column("sql_preview", sa.Text(), nullable=False),
        sa.Column("run_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["platform.tenant.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["platform.app_user.id"]),
        sa.ForeignKeyConstraint(["source_request_id"], ["platform.nl2sql_request_log.id"]),
        sa.UniqueConstraint(
            "tenant_id", "user_id", "source_request_id", name="uq_saved_nl2sql_request_owner"
        ),
        schema="platform",
    )
    op.create_index(
        "ix_saved_nl2sql_query_owner_created",
        "saved_nl2sql_query",
        ["tenant_id", "user_id", "created_at"],
        schema="platform",
    )


def downgrade():
    op.drop_index("ix_saved_nl2sql_query_owner_created", table_name="saved_nl2sql_query", schema="platform")
    op.drop_table("saved_nl2sql_query", schema="platform")
