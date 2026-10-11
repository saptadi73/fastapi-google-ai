"""Allow the configured DDL role to persist atomic schema migration audits."""

from sqlalchemy import text
from sqlalchemy.engine import make_url

from alembic import op
from app.core.config import get_settings

revision = "a7q0d3n6u9w2"
down_revision = "z6p9c2m5t8v1"
branch_labels = None
depends_on = None


def upgrade():
    url = get_settings().database_ddl_url.get_secret_value()
    role = make_url(url).username if url else None
    if role:
        quoted = op.get_bind().dialect.identifier_preparer.quote(role)
        op.execute(text(f"GRANT USAGE ON SCHEMA audit TO {quoted}"))
        op.execute(text(f"GRANT INSERT ON audit.event_log TO {quoted}"))


def downgrade():
    # Retain the limited grant for retries and historical migration audits.
    pass
