"""Reviewed, non-destructive evolution of NON_MASTER tables and their own view."""

import hashlib

from sqlalchemy import inspect, text

from app.core.exceptions import AppError
from app.services.profiling_service import canonical_json, digest


def column_changes(existing, proposed, rows, dialect):
    actual = {c["name"]: c for c in existing}
    operations, blockers = [], []
    for name in actual.keys() - proposed.c.keys():
        blockers.append(f"Penghapusan/rename kolom {name} tidak didukung; pertahankan data lama.")
    for col in proposed.c:
        old = actual.get(col.name)
        kind = str(col.type.compile(dialect=dialect)).lower()
        if old is None:
            if rows and not col.nullable:
                blockers.append(
                    f"Kolom baru {col.name} wajib tetapi {rows} record lama belum memiliki nilai."
                )
            else:
                operations.append(
                    {"action": "ADD_COLUMN", "column": col.name, "type": kind, "nullable": col.nullable}
                )
            continue
        previous = str(old["type"].compile(dialect=dialect)).lower()
        if previous != kind:
            if not rows:
                operations.append(
                    {"action": "ALTER_TYPE", "column": col.name, "from": previous, "type": kind}
                )
            elif previous == "bigint" and kind == "date":
                operations.append(
                    {"action": "SERIAL_TO_DATE", "column": col.name, "from": previous, "type": kind}
                )
            else:
                blockers.append(
                    f"Konversi {col.name}: {previous} ke {kind} pada tabel berisi data belum didukung."
                )
        if bool(old["nullable"]) != bool(col.nullable):
            operations.append({"action": "NULLABILITY", "column": col.name, "nullable": col.nullable})
    return operations, blockers


def _grants(conn, obj):
    return [
        dict(r)
        for r in conn.execute(
            text(
                "SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END grantee,"
                "a.privilege_type,a.is_grantable,pg_get_userbyid(a.grantor) grantor "
                "FROM pg_class c CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a "
                "WHERE c.oid=to_regclass(:obj) ORDER BY 1,2,3,4"
            ),
            {"obj": obj},
        ).mappings()
    ]


def inspect_migration(conn, table, view_name, config):
    from app.services.schema_compiler_service import validate_semantic_view_columns

    inspector = inspect(conn)
    quote = conn.dialect.identifier_preparer.quote
    target = f"trusted.{quote(table.name)}"
    view = f"semantic.{quote(view_name)}"
    exists = inspector.has_table(table.name, schema="trusted")
    columns = inspector.get_columns(table.name, schema="trusted") if exists else []
    rows = conn.scalar(text(f"SELECT count(*) FROM {target}")) if exists else 0
    operations, blockers = (
        column_changes(columns, table, rows, conn.dialect)
        if exists
        else ([{"action": "CREATE_TABLE", "column": table.name}], [])
    )
    uniques = inspector.get_unique_constraints(table.name, schema="trusted") if exists else []
    from sqlalchemy import UniqueConstraint

    expected_keys = {
        tuple(c.name for c in u.columns) for u in table.constraints if isinstance(u, UniqueConstraint)
    }
    if exists and {tuple(u["column_names"]) for u in uniques} != expected_keys:
        blockers.append("Perubahan business/primary key tidak didukung pada migrasi otomatis.")
    if exists and operations:
        owner = conn.scalar(
            text("SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid=to_regclass(:target)"),
            {"target": target},
        )
        if owner != conn.scalar(text("SELECT current_user")):
            blockers.append("Tabel harus dimiliki role DDL aplikasi sebelum evolusi schema.")
    if exists and conn.scalar(
        text(f"SELECT count(*) FROM {target} WHERE _tenant_id<>CAST(:tenant AS uuid)"),
        {"tenant": str(config["tenant_id"])},
    ):
        blockers.append("Tabel berisi tenant lain; migrasi dihentikan.")
    mapping = {c.target_column: c for c in config["parsed"].columns}
    for op in operations:
        name = op["column"]
        if op["action"] == "SERIAL_TO_DATE":
            column = mapping[name]
            if "parse_date_id" not in column.transformation_codes:
                blockers.append(f"{name}: pilih parse_date_id untuk menyatakan konversi angka serial Sheets.")
            invalid = conn.scalar(
                text(
                    f"SELECT count(*) FROM {target} WHERE {quote(name)} IS NOT NULL "
                    f"AND ({quote(name)}<1 OR {quote(name)}>2958465)"
                )
            )
            if invalid:
                blockers.append(f"{name}: {invalid} nilai di luar rentang serial tanggal 1..2958465.")
            op["conversion"] = "GOOGLE_SHEETS_SERIAL_1899_12_30"
            if column.pii_classification in ("NONE", "LOW") and not invalid:
                from app.services.etl_compiler_service import date_id

                sample = conn.execute(
                    text(
                        f"SELECT DISTINCT {quote(name)} value FROM {target} "
                        f"WHERE {quote(name)} IS NOT NULL ORDER BY {quote(name)} LIMIT 3"
                    )
                ).scalars()
                op["examples"] = [{"before": value, "after": str(date_id(value))} for value in sample]
        if op["action"] == "NULLABILITY" and not op["nullable"]:
            invalid = conn.scalar(text(f"SELECT count(*) FROM {target} WHERE {quote(name)} IS NULL"))
            if invalid:
                blockers.append(f"{name}: {invalid} record NULL; perbaiki sebelum menjadikan wajib.")
    public = [c.target_column for c in config["parsed"].columns if c.pii_classification in ("NONE", "LOW")]
    if not public:
        blockers.append("Minimal satu kolom non-sensitif diperlukan.")
    view_exists = view_name in inspector.get_view_names(schema="semantic")
    view_columns = inspector.get_columns(view_name, schema="semantic") if view_exists else []
    recreate = False
    if view_exists:
        try:
            validate_semantic_view_columns(
                view_columns, [table.c._tenant_id, *(table.c[n] for n in public)], conn.dialect
            )
        except AppError as error:
            if error.code != "SEMANTIC_SCHEMA_MIGRATION_REQUIRED":
                raise
            recreate = True
    type_columns = {op["column"] for op in operations if op["action"] in ("ALTER_TYPE", "SERIAL_TO_DATE")}
    if type_columns & {c["name"] for c in view_columns}:
        recreate = True
    info = None
    grants = []
    if view_exists:
        info = dict(
            conn.execute(
                text(
                    "SELECT pg_get_userbyid(c.relowner) owner,c.reloptions,"
                    "pg_get_viewdef(c.oid,true) definition,obj_description(c.oid,'pg_class') comment "
                    "FROM pg_class c WHERE c.oid=to_regclass(:view)"
                ),
                {"view": view},
            )
            .mappings()
            .one()
        )
        grants = _grants(conn, view)
        previous_targets = (
            conn.execute(
                text(
                    "SELECT DISTINCT n.nspname||'.'||t.relname FROM pg_rewrite r "
                    "JOIN pg_depend d ON d.objid=r.oid JOIN pg_class t ON t.oid=d.refobjid "
                    "JOIN pg_namespace n ON n.oid=t.relnamespace "
                    "WHERE r.ev_class=to_regclass(:view) AND n.nspname='trusted'"
                ),
                {"view": view},
            )
            .scalars()
            .all()
        )
        if previous_targets and table.fullname not in previous_targets:
            operations.append(
                {
                    "action": "RETARGET_VIEW",
                    "column": view_name,
                    "from": ", ".join(previous_targets),
                    "type": table.fullname,
                }
            )
    if recreate:
        if info["owner"] != conn.scalar(text("SELECT current_user")):
            blockers.append("View dimiliki role lain; owner harus sesuai role DDL aplikasi.")
        if info["reloptions"]:
            blockers.append("View memakai opsi khusus yang belum didukung migrasi.")
        if any(g["grantor"] != info["owner"] for g in grants):
            blockers.append("Grant view berasal dari role lain; tidak dapat dipertahankan otomatis.")
        dependent = (
            conn.execute(
                text(
                    "SELECT DISTINCT n.nspname||'.'||c.relname dependent FROM pg_depend d "
                    "JOIN pg_rewrite r ON r.oid=d.objid JOIN pg_class c ON c.oid=r.ev_class "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE d.refobjid=to_regclass(:view) AND c.oid<>d.refobjid"
                ),
                {"view": view},
            )
            .scalars()
            .all()
        )
        blockers.extend(
            f"View turunan {name} perlu direvisi melalui workflow tersendiri." for name in dependent
        )
        if conn.scalar(
            text(
                "SELECT count(*) FROM pg_attribute WHERE attrelid=to_regclass(:view) AND attacl IS NOT NULL"
            ),
            {"view": view},
        ):
            blockers.append("View memiliki grant per-kolom; migrasi otomatis belum mendukungnya.")
    if type_columns and exists:
        others = (
            conn.execute(
                text(
                    "SELECT DISTINCT n.nspname||'.'||c.relname dependent FROM pg_depend d "
                    "JOIN pg_rewrite r ON r.oid=d.objid JOIN pg_class c ON c.oid=r.ev_class "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE d.refobjid=to_regclass(:target) AND c.oid<>coalesce(to_regclass(:view),0)"
                ),
                {"target": target, "view": view},
            )
            .scalars()
            .all()
        )
        blockers.extend(f"Tabel dirujuk view lain {name}; perubahan tipe ditahan." for name in others)
        constraints = (
            conn.execute(
                text(
                    "SELECT conname FROM pg_constraint WHERE contype='f' "
                    "AND (conrelid=to_regclass(:target) OR confrelid=to_regclass(:target))"
                ),
                {"target": target},
            )
            .scalars()
            .all()
        )
        blockers.extend(
            f"Foreign key {name} memerlukan rencana dependency tersendiri." for name in constraints
        )
    if recreate:
        operations.append({"action": "RECREATE_VIEW", "column": view_name})
    column_state = [
        {
            "name": c["name"],
            "type": str(c["type"].compile(dialect=conn.dialect)).lower(),
            "nullable": c["nullable"],
        }
        for c in columns
    ]
    data_hash = None
    if exists and rows:
        hasher = hashlib.sha256()
        offset = 0
        # A type change invalidates SELECT * prepared statements on this connection.
        # Use a distinct statement for each inspected schema, including the post-DDL audit.
        schema_key = digest(column_state)
        while True:
            batch = (
                conn.execute(
                    text(f"SELECT * FROM {target} ORDER BY _tenant_id,_row_hash LIMIT 500 OFFSET :offset /* {schema_key} */"),
                    {"offset": offset},
                )
                .mappings()
                .all()
            )
            if not batch:
                break
            for row in batch:
                hasher.update(canonical_json(dict(row)).encode("utf-8"))
            offset += len(batch)
        data_hash = hasher.hexdigest()
    state = {
        "target": table.fullname,
        "view": view_name,
        "rows": rows,
        "columns": column_state,
        "unique": sorted([list(u["column_names"]) for u in uniques]),
        "view_columns": [{"name": c["name"], "type": str(c["type"])} for c in view_columns],
        "view_info": info,
        "grants": grants,
        "configuration": config["parsed"].model_dump(mode="json"),
        "operations": operations,
        "blockers": blockers,
        "data_hash": data_hash,
    }
    return {
        "fingerprint": digest(state),
        "allowed": not blockers,
        "requires_migration": bool(operations),
        "rows_existing": rows,
        "operations": operations,
        "blockers": blockers,
        "policy": "REVIEWED_NON_DESTRUCTIVE_EVOLUTION",
    }, state


def apply_migration(
    conn, table, view_name, parsed, tenant_id, expected_fingerprint, *, completed_fingerprint=None,
    compatible_rollback=False,
):
    plan, state = inspect_migration(conn, table, view_name, {"parsed": parsed, "tenant_id": tenant_id})
    if not plan["allowed"]:
        raise AppError("SCHEMA_MIGRATION_BLOCKED", " ".join(plan["blockers"]), 409)
    # Rolling back an already deployed version may follow successful data loads.
    # It can reuse the target only when it needs no schema/view operations.
    reviewed = expected_fingerprint == plan["fingerprint"] or (
        compatible_rollback and not plan["requires_migration"]
    )
    completed = (
        not plan["requires_migration"]
        and completed_fingerprint is not None
        and completed_fingerprint == plan["fingerprint"]
    )
    if (expected_fingerprint or plan["requires_migration"]) and not (reviewed or completed):
        code = "SCHEMA_MIGRATION_STALE" if expected_fingerprint else "SCHEMA_REVIEW_REQUIRED"
        raise AppError(
            code,
            "Schema/data target berubah atau rencana belum direview. Clone/ajukan review ulang dari aplikasi.",
            409,
        )
    quote = conn.dialect.identifier_preparer.quote
    target = f"trusted.{quote(table.name)}"
    view = f"semantic.{quote(view_name)}"
    recreate = any(op["action"] == "RECREATE_VIEW" for op in plan["operations"])
    comments = []
    if recreate:
        comments = (
            conn.execute(
                text(
                    "SELECT attname,col_description(attrelid,attnum) comment FROM pg_attribute "
                    "WHERE attrelid=to_regclass(:view) AND attnum>0 AND NOT attisdropped"
                ),
                {"view": view},
            )
            .mappings()
            .all()
        )
        conn.execute(text(f"DROP VIEW {view} RESTRICT"))
    business_change = False
    for op in plan["operations"]:
        name = quote(op["column"])
        action = op["action"]
        if action == "CREATE_TABLE":
            table.create(conn)
        elif action == "ADD_COLUMN":
            col = table.c[op["column"]]
            kind = str(col.type.compile(dialect=conn.dialect))
            conn.execute(
                text(f"ALTER TABLE {target} ADD COLUMN {name} {kind}" + ("" if col.nullable else " NOT NULL"))
            )
            business_change = True
        elif action in ("ALTER_TYPE", "SERIAL_TO_DATE"):
            kind = str(table.c[op["column"]].type.compile(dialect=conn.dialect))
            using = (
                f"(DATE '1899-12-30' + CAST({name} AS integer))"
                if action == "SERIAL_TO_DATE"
                else f"CAST(NULL AS {kind})"
            )
            conn.execute(text(f"ALTER TABLE {target} ALTER COLUMN {name} TYPE {kind} USING {using}"))
            business_change = True
        elif action == "NULLABILITY":
            conn.execute(
                text(
                    f"ALTER TABLE {target} ALTER COLUMN {name} "
                    + ("DROP" if op["nullable"] else "SET")
                    + " NOT NULL"
                )
            )
    if business_change and plan["rows_existing"]:
        _rehash(conn, table, parsed, plan["fingerprint"])
    return plan, state["grants"] if recreate else None, comments, state["view_info"]


def _rehash(conn, table, parsed, fingerprint):
    # Two-phase hashes prevent old/new hash collisions without dropping constraints.
    quote = conn.dialect.identifier_preparer.quote
    target = f"trusted.{quote(table.name)}"
    conn.execute(
        text(
            "CREATE TEMP TABLE schema_hashes (tenant uuid,old varchar(64),new varchar(64),"
            "temporary varchar(64),PRIMARY KEY(tenant,old),UNIQUE(tenant,temporary)) ON COMMIT DROP"
        )
    )
    names = [c.target_column for c in parsed.columns]
    offset = 0
    while True:
        rows = (
            conn.execute(
                text(
                    f"SELECT _tenant_id,_row_hash,{','.join(quote(n) for n in names)} FROM {target} "
                    "ORDER BY _tenant_id,_row_hash LIMIT 500 OFFSET :offset"
                ),
                {"offset": offset},
            )
            .mappings()
            .all()
        )
        if not rows:
            break
        values = [
            {
                "tenant": r["_tenant_id"],
                "old": r["_row_hash"],
                "new": digest({name: r[name] for name in names}),
                "temporary": digest({"migration": fingerprint, "old": r["_row_hash"]}),
            }
            for r in rows
        ]
        conn.execute(text("INSERT INTO schema_hashes VALUES (:tenant,:old,:new,:temporary)"), values)
        offset += len(rows)
    if conn.scalar(
        text(
            "SELECT count(*) FROM (SELECT tenant,new FROM schema_hashes GROUP BY tenant,new HAVING count(*)>1) duplicates"
        )
    ):
        raise AppError(
            "SCHEMA_MIGRATION_BLOCKED",
            "Konversi menghasilkan record identik; seluruh migrasi dibatalkan tanpa menghapus record.",
            409,
        )
    if conn.scalar(
        text(
            "SELECT count(*) FROM schema_hashes a JOIN schema_hashes b ON a.tenant=b.tenant AND a.new=b.temporary"
        )
    ):
        raise AppError(
            "SCHEMA_MIGRATION_BLOCKED",
            "Hash konversi bertabrakan dengan hash sementara; migrasi dibatalkan.",
            409,
        )
    collisions = conn.scalar(
        text(
            f"SELECT count(*) FROM schema_hashes h JOIN {target} t ON "
            "t._tenant_id=h.tenant AND t._row_hash=h.temporary"
        )
    )
    if collisions:
        raise AppError(
            "SCHEMA_MIGRATION_BLOCKED", "Hash sementara bertabrakan; seluruh migrasi dibatalkan.", 409
        )
    conn.execute(
        text(
            f"UPDATE {target} t SET _row_hash=h.temporary FROM schema_hashes h WHERE t._tenant_id=h.tenant AND t._row_hash=h.old"
        )
    )
    conn.execute(
        text(
            f"UPDATE {target} t SET _row_hash=h.new FROM schema_hashes h WHERE t._tenant_id=h.tenant AND t._row_hash=h.temporary"
        )
    )


def restore_view_access(conn, view_name, grants, comments, info):
    if grants is None:
        return
    quote = conn.dialect.identifier_preparer.quote
    view = f"semantic.{quote(view_name)}"
    for role in {g["grantee"] for g in _grants(conn, view) if g["grantee"] != info["owner"]}:
        conn.execute(text(f"REVOKE ALL ON {view} FROM " + ("PUBLIC" if role == "PUBLIC" else quote(role))))
    for grant in grants:
        role = "PUBLIC" if grant["grantee"] == "PUBLIC" else quote(grant["grantee"])
        conn.execute(
            text(
                f"GRANT {grant['privilege_type']} ON {view} TO {role}"
                + (" WITH GRANT OPTION" if grant["is_grantable"] else "")
            )
        )

    def literal(value):
        return "'" + value.replace("'", "''") + "'"

    if info["comment"] is not None:
        conn.execute(text(f"COMMENT ON VIEW {view} IS {literal(info['comment'])}"))
    names = {c["name"] for c in inspect(conn).get_columns(view_name, schema="semantic")}
    for col in comments:
        if col["comment"] is not None and col["attname"] in names:
            conn.execute(
                text(f"COMMENT ON COLUMN {view}.{quote(col['attname'])} IS {literal(col['comment'])}")
            )
    if _grants(conn, view) != grants:
        raise AppError("SCHEMA_MIGRATION_BLOCKED", "Izin view tidak identik; migrasi dibatalkan.", 409)
