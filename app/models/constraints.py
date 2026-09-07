"""Database-enforced tenant consistency, in addition to repository access checks."""

import hashlib

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint


def install_tenant_constraints(metadata):
    tables = [table for table in metadata.tables.values() if "tenant_id" in table.c]
    for table in tables:
        table.append_constraint(UniqueConstraint("tenant_id", "id", name=f"uq_{table.name}_tenant_id"))
    for table in tables:
        for fk in list(table.foreign_key_constraints):
            if len(fk.elements) != 1:
                continue
            element = fk.elements[0]
            parent = element.column.table
            if "tenant_id" not in parent.c:
                continue
            column = element.parent.name
            suffix = hashlib.sha256(f"{table.fullname}:{column}".encode()).hexdigest()[:8]
            name = f"fk_tenant_{table.name[:18]}_{column[:16]}_{suffix}"
            table.append_constraint(
                ForeignKeyConstraint(
                    ["tenant_id", column],
                    [f"{parent.fullname}.tenant_id", f"{parent.fullname}.id"],
                    name=name,
                    use_alter=True,
                )
            )
    sheet = metadata.tables["platform.source_sheet"]
    config = metadata.tables["platform.configuration_version"]
    sheet.append_constraint(UniqueConstraint("tenant_id", "source_id", "id", name="uq_sheet_source_tenant"))
    config.append_constraint(
        UniqueConstraint("tenant_id", "source_sheet_id", "id", name="uq_config_sheet_tenant")
    )
    sheet.append_constraint(
        ForeignKeyConstraint(
            ["tenant_id", "id", "active_configuration_id"],
            [
                "platform.configuration_version.tenant_id",
                "platform.configuration_version.source_sheet_id",
                "platform.configuration_version.id",
            ],
            name="fk_active_config_same_sheet",
            use_alter=True,
        )
    )
    for table in tables:
        if all(name in table.c for name in ("tenant_id", "source_id", "source_sheet_id")):
            table.append_constraint(
                ForeignKeyConstraint(
                    ["tenant_id", "source_id", "source_sheet_id"],
                    [
                        "platform.source_sheet.tenant_id",
                        "platform.source_sheet.source_id",
                        "platform.source_sheet.id",
                    ],
                    name=f"fk_{table.name}_same_source_sheet",
                    use_alter=True,
                )
            )
