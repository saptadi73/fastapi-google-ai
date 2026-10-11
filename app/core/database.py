from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.exceptions import AppError


def make_engine(url: str | None = None):
    return create_async_engine(
        url or get_settings().database_url.get_secret_value(),
        pool_pre_ping=True,
        hide_parameters=True,
        # Celery tasks use separate asyncio.run loops; do not share pooled connections across loops.
        poolclass=NullPool,
    )


engine = make_engine()
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session():
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def transaction():
    async with SessionFactory() as session, session.begin():
        yield session


@asynccontextmanager
async def deployment_transaction():
    """One transaction for registry, DDL, audit and the successful job status.

    The DDL login may SET ROLE to the runtime role; the runtime login never
    receives membership in the DDL role. Only deployment jobs use this connection.
    """
    settings = get_settings()
    ddl_url = settings.database_ddl_url.get_secret_value()
    if not ddl_url:
        async with transaction() as session:
            yield session
        return
    runtime = make_url(settings.database_url.get_secret_value())
    ddl = make_url(ddl_url)
    def destination(url):
        host = url.query.get("host") or url.host or "localhost"
        if host in ("localhost", "127.0.0.1", "::1"):
            host = "localhost"
        return host, url.port or 5432, url.database

    if destination(ddl) != destination(runtime) or not runtime.username:
        raise AppError("DEPLOY_DATABASE_MISMATCH", "Koneksi DDL dan aplikasi harus menuju server dan database yang sama.", 409)
    deployment_engine = make_engine(ddl_url)
    try:
        async with SessionFactory(bind=deployment_engine) as session, session.begin():
            conn = await session.connection()
            quote = conn.dialect.identifier_preparer.quote
            await conn.execute(text(f"SET LOCAL ROLE {quote(runtime.username)}"))
            yield session
    finally:
        await deployment_engine.dispose()
