from typing import Literal

from pydantic import Field

from app.schemas.common import Envelope, StrictModel


class Liveness(StrictModel):
    alive: Literal[True] = True


class DatabaseHealth(StrictModel):
    database: Literal["postgresql"] = "postgresql"
    connected: Literal[True] = True
    name: str
    latency_ms: float = Field(ge=0)


class Readiness(StrictModel):
    database: Literal["ready"] = "ready"
    redis: Literal["ready", "unavailable"]
    background_jobs: Literal["celery", "manual_worker_only"]


class DependencyCheck(StrictModel):
    status: Literal["ready", "unavailable", "not_configured"]
    latency_ms: float = Field(ge=0)
    message: str | None = None


class DependencyHealth(StrictModel):
    status: Literal["ready", "degraded"]
    database: DependencyCheck
    redis: DependencyCheck
    google_api: DependencyCheck
    openai: DependencyCheck


class LivenessResponse(Envelope):
    data: Liveness


class DatabaseHealthResponse(Envelope):
    data: DatabaseHealth


class ReadinessResponse(Envelope):
    data: Readiness


class DependencyHealthResponse(Envelope):
    data: DependencyHealth
