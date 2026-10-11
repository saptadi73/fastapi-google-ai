"""Allow the DDL login to switch to runtime privileges for one atomic deploy."""

from sqlalchemy import text
from sqlalchemy.engine import make_url

from alembic import op
from app.core.config import get_settings

revision = "b8r1e4o7v0x3"
down_revision = "a7q0d3n6u9w2"
branch_labels = None
depends_on = None


def upgrade():
    settings = get_settings()
    ddl_url = settings.database_ddl_url.get_secret_value()
    runtime = make_url(settings.database_url.get_secret_value()).username
    ddl = make_url(ddl_url).username if ddl_url else None
    if ddl and runtime and ddl != runtime:
        conn = op.get_bind()
        if conn.dialect.server_version_info < (16,):
            raise RuntimeError("Atomic deployments with separate roles require PostgreSQL 16 or newer")
        quote = conn.dialect.identifier_preparer.quote
        # Direction matters: the runtime login cannot assume the DDL role.
        op.execute(text(f"GRANT {quote(runtime)} TO {quote(ddl)} WITH INHERIT FALSE, SET TRUE"))


def downgrade():
    # Retain SET membership so historical workers remain usable during rollback.
    pass
