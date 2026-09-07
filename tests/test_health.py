import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.exc import OperationalError

from app.api.health import get_health_service
from app.core.config import get_settings
from app.main import app
from app.services import health_service
from app.services.health_service import HealthService


def fake_engine(connection=None, error=None):
    @asynccontextmanager
    async def connect():
        if error:
            raise error
        yield connection

    return SimpleNamespace(connect=connect)


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_health_service, None)


async def test_database_health_reports_actual_connection(client):
    connection = SimpleNamespace(scalar=AsyncMock(return_value="googleai_test"))
    app.dependency_overrides[get_health_service] = lambda: HealthService(fake_engine(connection))
    response = await client.get("/health/database")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["connected"] is True
    assert data["name"] == "googleai_test" and data["database"] == "postgresql"
    assert data["latency_ms"] >= 0
    assert str(connection.scalar.call_args.args[0]) == "SELECT current_database()"


async def test_liveness_survives_database_outage(client):
    error = OperationalError("SELECT", {}, Exception("password=never-expose-this"))
    app.dependency_overrides[get_health_service] = lambda: HealthService(fake_engine(error=error))
    for path in ("/health", "/health/live"):
        response = await client.get(path)
        assert response.status_code == 200
        assert response.json()["data"] == {"alive": True}
    response = await client.get("/health/database")
    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "DATABASE_UNAVAILABLE"
    assert "never-expose-this" not in response.text


async def test_database_timeout(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "health_check_timeout_seconds", 0.1)

    async def slow_query(*args):
        await asyncio.sleep(10)

    connection = SimpleNamespace(scalar=slow_query)
    app.dependency_overrides[get_health_service] = lambda: HealthService(fake_engine(connection))
    response = await asyncio.wait_for(client.get("/health/database"), timeout=2)
    assert response.status_code == 503


@pytest.mark.parametrize("required,expected", [(False, 200), (True, 503)])
async def test_readiness_redis_policy(client, monkeypatch, required, expected):
    monkeypatch.setattr(get_settings(), "redis_required", required)
    connection = SimpleNamespace(scalar=AsyncMock(return_value="googleai_test"), execute=AsyncMock())
    redis = SimpleNamespace(ping=AsyncMock(side_effect=OSError("offline")), aclose=AsyncMock())
    monkeypatch.setattr(health_service.Redis, "from_url", lambda *args, **kwargs: redis)
    app.dependency_overrides[get_health_service] = lambda: HealthService(fake_engine(connection))
    response = await client.get("/health/ready")
    assert response.status_code == expected
    connection.execute.assert_awaited_once()
    redis.aclose.assert_awaited_once()
    if required:
        assert response.json()["errors"][0]["code"] == "REDIS_UNAVAILABLE"
    else:
        assert response.json()["data"]["database"] == "ready"
        assert response.json()["data"]["redis"] == "unavailable"


async def test_readiness_requires_migration(client):
    connection = SimpleNamespace(
        scalar=AsyncMock(return_value="googleai_test"),
        execute=AsyncMock(side_effect=OperationalError("SELECT", {}, Exception("missing table"))),
    )
    app.dependency_overrides[get_health_service] = lambda: HealthService(fake_engine(connection))
    assert (await client.get("/health/database")).status_code == 200
    response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "DATABASE_UNAVAILABLE"
