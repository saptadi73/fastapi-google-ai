"""Reconcile registry tenant constraints without dropping historical metadata.

Older installations ran an earlier form of the master binding migration. Inspect
constraint definitions so both those installations and fresh databases can upgrade.
This additive repair deliberately retains tenant protection on downgrade.
"""

import hashlib

import sqlalchemy as sa

from alembic import op

revision = "8a96b7c5d4ef"
down_revision = "7i85f6b4c3de"
branch_labels = None
depends_on = None

SCHEMA = "platform"
# Frozen migration specification: do not import the current ORM metadata.
REFERENCES = {
    "master_column_binding": {
        "source_sheet_id": "source_sheet", "master_definition_id": "master_definition",
        "created_by": "app_user", "approved_by": "app_user",
    },
    "taxonomy": {"created_by": "app_user", "approved_by": "app_user"},
    "taxonomy_term": {
        "taxonomy_id": "taxonomy", "parent_id": "taxonomy_term",
        "created_by": "app_user", "approved_by": "app_user",
    },
    "taxonomy_column_binding": {
        "source_sheet_id": "source_sheet", "taxonomy_id": "taxonomy",
        "created_by": "app_user", "approved_by": "app_user",
    },
}


def upgrade():
    connection = op.get_bind()
    # Every referenced composite identity must exist before adding any FK.
    for table in REFERENCES:
        inspector = sa.inspect(connection)
        unique = inspector.get_unique_constraints(table, schema=SCHEMA)
        if not any(c["column_names"] == ["tenant_id", "id"] for c in unique):
            op.create_unique_constraint(f"uq_{table}_tenant_id", table, ["tenant_id", "id"], schema=SCHEMA)
        indexes = inspector.get_indexes(table, schema=SCHEMA)
        name = f"ix_platform_{table}_tenant_id"
        existing = next((i for i in indexes if i["name"] == name), None)
        if existing is None:
            op.create_index(name, table, ["tenant_id"], schema=SCHEMA)
        elif existing["column_names"] != ["tenant_id"] or existing["unique"]:
            raise ValueError(f"Unexpected definition for index {name}")
    for table, references in REFERENCES.items():
        foreign_keys = sa.inspect(connection).get_foreign_keys(table, schema=SCHEMA)
        for column, parent in references.items():
            if any(
                fk["constrained_columns"] == ["tenant_id", column]
                and fk["referred_schema"] == SCHEMA and fk["referred_table"] == parent
                and fk["referred_columns"] == ["tenant_id", "id"]
                for fk in foreign_keys
            ):
                continue
            suffix = hashlib.sha256(f"platform.{table}:{column}".encode()).hexdigest()[:8]
            name = f"fk_tenant_{table[:18]}_{column[:16]}_{suffix}"
            op.create_foreign_key(
                name, table, parent, ["tenant_id", column], ["tenant_id", "id"],
                source_schema=SCHEMA, referent_schema=SCHEMA,
            )


def downgrade():
    # There is no data/column transformation to undo. Some constraints may predate
    # this revision; removing them would weaken tenant isolation on older installs.
    # Downgrade only moves the revision marker, retaining this compatible repair.
    pass
