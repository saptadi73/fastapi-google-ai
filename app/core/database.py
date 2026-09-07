from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


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
