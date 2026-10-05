import time
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1.router import router
from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import install_handlers

settings = get_settings()
structlog.configure(
    processors=[structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()]
)
logger = structlog.get_logger()


def configure_cors(application: FastAPI, runtime_settings) -> bool:
    """Install application CORS outside production; Nginx owns it in production."""
    if runtime_settings.app_env.strip().casefold() == "production":
        return False
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-ID", "Content-Disposition"],
    )
    return True


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
configure_cors(app, settings)
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
app.include_router(health_router)
