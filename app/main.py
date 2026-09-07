import time
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from sqlalchemy import text

from app.api.v1.router import router
from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import AppError, install_handlers, success

settings = get_settings()
structlog.configure(
    processors=[structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()]
)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app):
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    description="Google Sheets ingestion, reviewed ETL, dashboard API, and controlled AI query plans.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Request-ID"],
)
install_handlers(app)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
    start = time.monotonic()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    logger.info(
        "http.request",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round((time.monotonic() - start) * 1000),
    )
    return response


app.include_router(router, prefix=settings.api_v1_prefix)


@app.get("/health/live", tags=["Health"])
async def live():
    return success({"alive": True})


@app.get("/health/ready", tags=["Health"])
async def ready():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1 FROM platform.tenant LIMIT 1"))
    except Exception:
        raise AppError("DATABASE_UNAVAILABLE", "Database atau migration belum siap.", 503) from None
    redis = Redis.from_url(
        settings.redis_url.get_secret_value(), socket_connect_timeout=0.5, socket_timeout=0.5
    )
    try:
        redis_ok = await redis.ping()
    except Exception:
        redis_ok = False
    finally:
        await redis.aclose()
    if settings.redis_required and not redis_ok:
        raise AppError("REDIS_UNAVAILABLE", "Redis belum siap.", 503)
    return success(
        {
            "database": "ready",
            "redis": "ready" if redis_ok else "unavailable",
            "background_jobs": "celery" if redis_ok else "manual_worker_only",
        }
    )
