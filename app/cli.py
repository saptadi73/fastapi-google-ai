import argparse
import asyncio

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.database import SessionFactory, engine
from app.core.security import password_hasher
from app.models.auth import Tenant, User


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
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["bootstrap", "check-db", "worker-once"])
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
