"""Record compatibility guidance for sources already in a partial workflow."""

from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.domain.source_compatibility import classify_source_compatibility

revision = "a7q0w3e6r9t3"
down_revision = "a7q0w3e6r9t2"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    source = sa.table(
        "data_source",
        sa.column("id", sa.Uuid(as_uuid=False)),
        sa.column("tenant_id", sa.Uuid(as_uuid=False)),
        sa.column("source_code", sa.String(63)),
        sa.column("status", sa.String(40)),
        sa.column("access_status", sa.String(40)),
        sa.column("access_review_status", sa.String(20)),
        sa.column("access_metadata", postgresql.JSONB()),
        sa.column("access_reviewed_by", sa.Uuid(as_uuid=False)),
        sa.column("access_reviewed_at", sa.DateTime(timezone=True)),
        sa.column("unlinked_at", sa.DateTime(timezone=True)),
        schema="platform",
    )
    event_log = sa.table(
        "event_log",
        sa.column("id", sa.Uuid(as_uuid=False)),
        sa.column("tenant_id", sa.Uuid(as_uuid=False)),
        sa.column("user_id", sa.Uuid(as_uuid=False)),
        sa.column("event", sa.String(100)),
        sa.column("resource_id", sa.String(100)),
        sa.column("details", postgresql.JSONB()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        schema="audit",
    )
    rows = connection.execute(
        sa.select(
            source.c.id,
            source.c.tenant_id,
            source.c.source_code,
            source.c.status,
            source.c.access_status,
            source.c.access_review_status,
            source.c.access_metadata,
            source.c.access_reviewed_by,
            source.c.access_reviewed_at,
        ).where(source.c.unlinked_at.is_(None))
    )
    audit_rows = []
    for row in rows.mappings():
        compatibility = classify_source_compatibility(
            access_metadata=row["access_metadata"],
            access_status=row["access_status"],
            review_status=row["access_review_status"],
            reviewed_by=row["access_reviewed_by"],
            reviewed_at=row["access_reviewed_at"],
        )
        metadata_fields_present = sorted(
            key for key, value in (row["access_metadata"] or {}).items() if value
        )
        audit_rows.append(
            {
                "id": str(uuid4()),
                "tenant_id": row["tenant_id"],
                "user_id": None,
                "event": "source.legacy_compatibility_classified",
                "resource_id": str(row["id"]),
                "details": {
                    "actor_type": "SYSTEM",
                    "migration_revision": revision,
                    "source_code": row["source_code"],
                    "legacy_etl_status": row["status"],
                    "access_status": row["access_status"],
                    "review_status": row["access_review_status"],
                    "metadata_fields_present": metadata_fields_present,
                    **compatibility,
                },
                "created_at": datetime.now(timezone.utc),
            }
        )
        if len(audit_rows) >= 500:
            connection.execute(sa.insert(event_log), audit_rows)
            audit_rows.clear()
    if audit_rows:
        connection.execute(sa.insert(event_log), audit_rows)


def downgrade():
    # Keep compatibility snapshots in the audit log even if schema migrations
    # are rolled back; deleting historical audit records would be misleading.
    pass
