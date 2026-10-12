import argparse
import asyncio
import json

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.database import SessionFactory, engine
from app.core.security import password_hasher
from app.models.auth import Tenant, User
from app.models.source import DataSource

SOURCE_ACCESS_METADATA_FIELDS = (
    "owner_unit_id",
    "business_domain_id",
    "jurisdiction_id",
    "purpose_id",
    "data_owner_user_id",
    "data_steward_user_id",
    "sensitivity",
)


def source_access_backfill_row(source):
    """Classify legacy source access state without changing or exposing metadata values."""
    metadata = source.access_metadata or {}
    missing = [field for field in SOURCE_ACCESS_METADATA_FIELDS if not metadata.get(field)]
    if missing:
        action = "OWNER_METADATA_REQUIRED"
    elif source.access_review_status == "REJECTED":
        action = "SOURCE_REVIEW_REJECTED"
    elif source.access_review_status != "APPROVED":
        action = "SOURCE_REVIEW_REQUIRED"
    elif source.access_status != "POLICY_APPROVED":
        action = "OWNER_ACCESS_ACTIVATION_REQUIRED"
    else:
        action = "READY_NO_BACKFILL"
    return {
        "tenant_id": str(source.tenant_id),
        "source_id": str(source.id),
        "source_code": source.source_code,
        "access_status": source.access_status,
        "review_status": source.access_review_status,
        "action": action,
        "missing_metadata_fields": missing,
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


async def main_async(command, *, reset_existing_password: bool = False):
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
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["bootstrap", "check-db", "worker-once", "source-access-backfill-report"],
    )
    parser.add_argument(
        "--reset-existing-password",
        action="store_true",
        help="Reset the configured bootstrap account password and revoke its existing tokens.",
    )
    args = parser.parse_args()
    if args.reset_existing_password and args.command != "bootstrap":
        parser.error("--reset-existing-password is only valid with the bootstrap command")
    asyncio.run(main_async(args.command, reset_existing_password=args.reset_existing_password))


if __name__ == "__main__":
    main()
