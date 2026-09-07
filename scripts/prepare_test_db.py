"""Create the dedicated PostgreSQL test database and run migrations; never drop/reset databases."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from dotenv import set_key
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def prepare():
    from app.core.config import get_settings
    from app.core.test_database import validate_test_database

    settings = get_settings()
    application_url = settings.database_url.get_secret_value()
    application = make_url(application_url)
    configured = settings.test_database_url.get_secret_value()
    target = validate_test_database(
        application_url,
        configured
        or application.set(database=application.database + "_test").render_as_string(hide_password=False),
    )
    if (target.host, target.port, target.username) != (
        application.host,
        application.port,
        application.username,
    ):
        raise ValueError("Test provisioning requires the same PostgreSQL server and account as DATABASE_URL")
    engine = create_async_engine(
        application, poolclass=NullPool, isolation_level="AUTOCOMMIT", hide_parameters=True
    )
    try:
        async with engine.connect() as conn:
            role = (
                await conn.execute(
                    text(
                        "SELECT current_user, rolsuper, rolcreatedb FROM pg_roles WHERE rolname=current_user"
                    )
                )
            ).one()
            print(f"PostgreSQL role: {role[0]}, superuser={role[1]}, createdb={role[2]}")
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": target.database}
            )
            if not exists:
                quote = conn.dialect.identifier_preparer.quote
                await conn.execute(text(f"CREATE DATABASE {quote(target.database)} OWNER {quote(role[0])}"))
                print(f"Created test database: {target.database}")
            else:
                print(f"Using existing test database: {target.database}")
    finally:
        await engine.dispose()
    test_url = target.render_as_string(hide_password=False)
    # Set only the test connection; preserve the application's other settings and credentials.
    set_key(ROOT / ".env", "TEST_DATABASE_URL", test_url)
    environment = dict(os.environ, DATABASE_URL=test_url, DATABASE_DDL_URL="", DATABASE_NL2SQL_URL="")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=environment, check=True
    )
    subprocess.run([sys.executable, "-m", "alembic", "check"], cwd=ROOT, env=environment, check=True)
    print(f"Test database ready: {target.database}. Application database: {application.database}.")


if __name__ == "__main__":
    asyncio.run(prepare())
