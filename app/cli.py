import argparse
import asyncio

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.database import SessionFactory, engine
from app.core.security import password_hasher
from app.models.auth import Tenant, User


async def bootstrap():
    s = get_settings()
    if len(s.bootstrap_password.get_secret_value()) < 12:
        raise SystemExit("Set BOOTSTRAP_PASSWORD (at least 12 characters) in .env first.")
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT pg_advisory_xact_lock(hashtext('platform-bootstrap'))"))
        tenant = await session.scalar(select(Tenant).where(Tenant.code == s.bootstrap_tenant))
        if not tenant:
            tenant = Tenant(code=s.bootstrap_tenant)
            session.add(tenant)
            await session.flush()
        user = await session.scalar(
            select(User).where(User.tenant_id == tenant.id, User.username == s.bootstrap_username)
        )
        if user:
            print("Bootstrap account already exists; password unchanged.")
            return
        session.add(
            User(
                tenant_id=tenant.id,
                username=s.bootstrap_username,
                full_name="Platform Administrator",
                role="PLATFORM_ADMIN",
                password_hash=password_hasher.hash(s.bootstrap_password.get_secret_value()),
            )
        )
        print("Bootstrap admin created. Read credentials from BOOTSTRAP_* in .env.")


async def main_async(command):
    if command == "bootstrap":
        await bootstrap()
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
    args = parser.parse_args()
    asyncio.run(main_async(args.command))


if __name__ == "__main__":
    main()
