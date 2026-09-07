import asyncio
import time

from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import AppError
from app.schemas.health import DatabaseHealth, Liveness, Readiness


class HealthService:
    def __init__(self, database_engine=None):
        self.engine = engine if database_engine is None else database_engine
        self.settings = get_settings()

    def live(self) -> Liveness:
        return Liveness()

    async def database(self, *, check_schema=False) -> DatabaseHealth:
        started = time.monotonic()
        try:
            async with asyncio.timeout(self.settings.health_check_timeout_seconds):
                async with self.engine.connect() as connection:
                    name = await connection.scalar(text("SELECT current_database()"))
                    if check_schema:
                        await connection.execute(text("SELECT 1 FROM platform.tenant LIMIT 1"))
        except Exception:
            message = (
                "Database atau migration belum siap."
                if check_schema
                else "Koneksi PostgreSQL gagal atau melewati batas waktu."
            )
            raise AppError("DATABASE_UNAVAILABLE", message, 503) from None
        return DatabaseHealth(name=name, latency_ms=round((time.monotonic() - started) * 1000, 2))

    async def ready(self) -> Readiness:
        await self.database(check_schema=True)
        redis = Redis.from_url(
            self.settings.redis_url.get_secret_value(), socket_connect_timeout=0.5, socket_timeout=0.5
        )
        try:
            async with asyncio.timeout(self.settings.health_check_timeout_seconds):
                redis_ok = bool(await redis.ping())
        except Exception:
            redis_ok = False
        finally:
            await redis.aclose()
        if self.settings.redis_required and not redis_ok:
            raise AppError("REDIS_UNAVAILABLE", "Redis belum siap.", 503)
        return Readiness(
            redis="ready" if redis_ok else "unavailable",
            background_jobs="celery" if redis_ok else "manual_worker_only",
        )
