import asyncio
import time
from pathlib import Path

import google_auth_httplib2
import httplib2
from google.oauth2.service_account import Credentials
from openai import AsyncOpenAI
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import ROOT, get_settings
from app.core.database import engine
from app.core.exceptions import AppError
from app.schemas.health import DatabaseHealth, DependencyCheck, DependencyHealth, Liveness, Readiness


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

    async def dependencies(self) -> DependencyHealth:
        checks = await asyncio.gather(
            self._database_dependency(),
            self._redis_dependency(),
            self._google_dependency(),
            self._openai_dependency(),
        )
        result = dict(zip(("database", "redis", "google_api", "openai"), checks, strict=True))
        return DependencyHealth(
            status="ready" if all(item.status == "ready" for item in checks) else "degraded",
            **result,
        )

    async def _database_dependency(self) -> DependencyCheck:
        return await self._timed_check(self._check_database, "Koneksi PostgreSQL gagal.")

    async def _check_database(self):
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def _redis_dependency(self) -> DependencyCheck:
        redis = Redis.from_url(
            self.settings.redis_url.get_secret_value(),
            socket_connect_timeout=self.settings.health_check_timeout_seconds,
            socket_timeout=self.settings.health_check_timeout_seconds,
        )

        async def check():
            try:
                if not await redis.ping():
                    raise ConnectionError("Redis tidak merespons PING.")
            finally:
                await redis.aclose()

        return await self._timed_check(check, "Koneksi Redis gagal.")

    async def _google_dependency(self) -> DependencyCheck:
        path = Path(self.settings.google_service_account_file)
        path = path if path.is_absolute() else ROOT / path
        if not path.is_file():
            return DependencyCheck(
                status="not_configured",
                latency_ms=0,
                message="Service account belum dikonfigurasi.",
            )

        def check():
            credentials = Credentials.from_service_account_file(
                str(path), scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
            )
            request = google_auth_httplib2.Request(
                http=httplib2.Http(timeout=self.settings.health_check_timeout_seconds)
            )
            credentials.refresh(request)

        async def async_check():
            await asyncio.to_thread(check)

        return await self._timed_check(async_check, "Autentikasi Google API gagal.")

    async def _openai_dependency(self) -> DependencyCheck:
        api_key = self.settings.openai_api_key.get_secret_value()
        models = list(
            dict.fromkeys(
                model
                for model in (self.settings.openai_model_etl_config, self.settings.openai_model_nl2sql)
                if model
            )
        )
        if not api_key or not models:
            return DependencyCheck(
                status="not_configured",
                latency_ms=0,
                message="API key atau model OpenAI belum dikonfigurasi.",
            )

        async def check():
            async with AsyncOpenAI(
                api_key=api_key,
                timeout=self.settings.health_check_timeout_seconds,
                max_retries=0,
            ) as client:
                for model in models:
                    await client.models.retrieve(model)

        return await self._timed_check(check, "Koneksi atau akses model OpenAI gagal.")

    async def _timed_check(self, check, failure_message) -> DependencyCheck:
        started = time.monotonic()
        try:
            async with asyncio.timeout(self.settings.health_check_timeout_seconds):
                await check()
        except Exception:
            return DependencyCheck(
                status="unavailable",
                latency_ms=round((time.monotonic() - started) * 1000, 2),
                message=failure_message,
            )
        return DependencyCheck(
            status="ready",
            latency_ms=round((time.monotonic() - started) * 1000, 2),
        )
