import argparse
import asyncio
import json

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.database import SessionFactory, engine
from app.core.security import password_hasher
from app.domain.source_compatibility import classify_source_compatibility
from app.models.auth import Tenant, User
from app.models.semantic import DataProduct
from app.models.source import DataSource, SourceSheet
from app.services.audit_service import system_audit
from app.services.numeric_metric_service import (
    backfill_data_product_numeric_metrics,
    default_numeric_metric_definitions,
)


def source_access_backfill_row(source):
    """Classify legacy source access state without changing or exposing metadata values."""
    compatibility = classify_source_compatibility(
        access_metadata=source.access_metadata,
        access_status=source.access_status,
        review_status=source.access_review_status,
        reviewed_by=getattr(source, "access_reviewed_by", None),
        reviewed_at=getattr(source, "access_reviewed_at", None),
        owner_managed=get_settings().etl_owner_workflow_enabled,
    )
    return {
        "tenant_id": str(source.tenant_id),
        "source_id": str(source.id),
        "source_code": source.source_code,
        "access_status": source.access_status,
        "review_status": source.access_review_status,
        **compatibility,
    }


async def source_access_backfill_report():
    async with SessionFactory() as session:
        sources = list((await session.scalars(
            select(DataSource)
            .where(DataSource.unlinked_at.is_(None))
            .order_by(DataSource.tenant_id, DataSource.source_code)
        )).all())
    rows = [source_access_backfill_row(source) for source in sources]
    counts = {}
    for row in rows:
        counts[row["action"]] = counts.get(row["action"], 0) + 1
    print(
        json.dumps(
            {"mode": "READ_ONLY_DRY_RUN", "total": len(rows), "counts": counts, "sources": rows},
            indent=2,
        )
    )


async def semantic_numeric_metric_backfill(*, apply: bool = False):
    """Add missing default numeric metrics to active NON_MASTER products."""
    async with SessionFactory() as session, session.begin():
        if apply:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext('semantic-numeric-metric-backfill'))")
            )
        query = (
            select(DataProduct, SourceSheet.dataset_kind)
            .join(
                SourceSheet,
                (SourceSheet.id == DataProduct.source_sheet_id)
                & (SourceSheet.tenant_id == DataProduct.tenant_id),
            )
            .where(DataProduct.status == "ACTIVE")
            .order_by(DataProduct.tenant_id, DataProduct.code)
        )
        if apply:
            query = query.with_for_update(of=DataProduct)
        rows = (await session.execute(query)).all()
        results = []
        totals = {"eligible": 0, "master_skipped": 0, "unclassified_skipped": 0, "changed": 0}
        for product, dataset_kind in rows:
            if dataset_kind == "MASTER":
                totals["master_skipped"] += 1
                continue
            if dataset_kind != "NON_MASTER":
                totals["unclassified_skipped"] += 1
                continue
            totals["eligible"] += 1
            generated = default_numeric_metric_definitions(
                product.columns or [], product.metrics or [], dataset_kind
            )
            if not generated:
                continue
            added_columns = [metric.column for metric in generated]
            previous_version = product.version
            if apply:
                added_columns = backfill_data_product_numeric_metrics(product, dataset_kind)
                system_audit(
                    session,
                    product.tenant_id,
                    "data_product.numeric_metrics_backfilled",
                    product.id,
                    data_product_code=product.code,
                    added_columns=added_columns,
                    previous_semantic_version=previous_version,
                    semantic_version=product.version,
                )
                totals["changed"] += 1
            results.append(
                {
                    "tenant_id": str(product.tenant_id),
                    "product_code": product.code,
                    "added_columns": added_columns,
                    "previous_semantic_version": previous_version,
                    "semantic_version": previous_version + 1 if apply else previous_version,
                }
            )
    print(
        json.dumps(
            {
                "mode": "APPLY" if apply else "READ_ONLY_DRY_RUN",
                "products_scanned": len(rows),
                "counts": totals,
                "changes": results,
            },
            indent=2,
        )
    )


async def reconcile_bootstrap_admin(session, settings, *, password: str, username: str, reset_password: bool):
    tenant = await session.scalar(select(Tenant).where(Tenant.code == settings.bootstrap_tenant))
    if not tenant:
        tenant = Tenant(code=settings.bootstrap_tenant)
        session.add(tenant)
        await session.flush()
    user = await session.scalar(select(User).where(User.tenant_id == tenant.id, User.username == username))
    if not user:
        session.add(
            User(
                tenant_id=tenant.id,
                username=username,
                full_name=settings.bootstrap_full_name,
                role="PLATFORM_ADMIN",
                password_hash=password_hasher.hash(password),
            )
        )
        return "created"

    changed = False
    if user.role != "PLATFORM_ADMIN":
        user.role = "PLATFORM_ADMIN"
        changed = True
    if not user.is_active:
        user.is_active = True
        changed = True
    if settings.bootstrap_full_name and user.full_name != settings.bootstrap_full_name:
        user.full_name = settings.bootstrap_full_name
        changed = True
    if reset_password:
        user.password_hash = password_hasher.hash(password)
        changed = True
    if changed:
        user.token_version += 1
    return "reset" if reset_password else "unchanged"


async def bootstrap(*, reset_existing_password: bool = False):
    s = get_settings()
    password = s.bootstrap_password.get_secret_value()
    username = s.bootstrap_username.strip().lower()
    if len(password) < 12:
        raise SystemExit("Set BOOTSTRAP_PASSWORD (at least 12 characters) in .env first.")
    if not username:
        raise SystemExit("Set BOOTSTRAP_USERNAME in .env first.")
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT pg_advisory_xact_lock(hashtext('platform-bootstrap'))"))
        result = await reconcile_bootstrap_admin(
            session,
            s,
            password=password,
            username=username,
            reset_password=reset_existing_password,
        )
        if result == "created":
            print("Bootstrap admin created. Read credentials from BOOTSTRAP_* in .env.")
        else:
            print(f"Bootstrap admin reconciled; password {result}.")


async def main_async(command, *, reset_existing_password: bool = False, apply: bool = False):
    if command == "bootstrap":
        await bootstrap(reset_existing_password=reset_existing_password)
    elif command == "check-db":
        async with engine.connect() as conn:
            row = (await conn.execute(text("SELECT current_database(), current_user, version()"))).one()
            print(f"Connected: database={row[0]}, user={row[1]}, {row[2].split(',')[0]}")
    elif command == "worker-once":
        from app.workers.runner import run_pending

        print(await run_pending())
    elif command == "source-access-backfill-report":
        await source_access_backfill_report()
    elif command == "semantic-numeric-metric-backfill":
        await semantic_numeric_metric_backfill(apply=apply)
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=[
            "bootstrap",
            "check-db",
            "worker-once",
            "source-access-backfill-report",
            "semantic-numeric-metric-backfill",
        ],
    )
    parser.add_argument(
        "--reset-existing-password",
        action="store_true",
        help="Reset the configured bootstrap account password and revoke its existing tokens.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the semantic numeric metric backfill; without it the command is read-only.",
    )
    args = parser.parse_args()
    if args.reset_existing_password and args.command != "bootstrap":
        parser.error("--reset-existing-password is only valid with the bootstrap command")
    if args.apply and args.command != "semantic-numeric-metric-backfill":
        parser.error("--apply is only valid with semantic-numeric-metric-backfill")
    asyncio.run(
        main_async(
            args.command,
            reset_existing_password=args.reset_existing_password,
            apply=args.apply,
        )
    )


if __name__ == "__main__":
    main()
