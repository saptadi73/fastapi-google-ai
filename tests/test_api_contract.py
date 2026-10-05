import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.main import app, configure_cors


def test_cors_is_owned_by_nginx_in_production():
    production_app = FastAPI()
    enabled = configure_cors(
        production_app,
        type(
            "Settings",
            (),
            {"app_env": "production", "cors_origins": ["https://google.kanjabung.web.id"]},
        )(),
    )

    assert enabled is False
    assert not any(middleware.cls is CORSMiddleware for middleware in production_app.user_middleware)


def test_cors_remains_available_for_local_development():
    development_app = FastAPI()
    enabled = configure_cors(
        development_app,
        type("Settings", (), {"app_env": "development", "cors_origins": ["http://localhost:5173"]})(),
    )

    assert enabled is True
    assert any(middleware.cls is CORSMiddleware for middleware in development_app.user_middleware)


async def test_health_and_auth_envelopes():
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/health/live")
        assert response.status_code == 200
        assert set(response.json()) == {"status", "data", "meta", "errors"}
        assert response.headers["x-request-id"]
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401
        assert response.json()["errors"][0]["code"] == "AUTHENTICATION_REQUIRED"
        response = await client.post("/api/v1/auth/login", json={"password": "never-echo-me"})
        assert response.status_code == 422
        assert "never-echo-me" not in response.text
        response = await client.get("/not-found")
        assert response.json()["status"] == "error"


def test_openapi():
    spec = app.openapi()
    assert "/api/v1/data-products/{code}/query" in spec["paths"]
    assert "/api/v1/auth/login" in spec["paths"]
    assert "HTTPBearer" in spec["components"]["securitySchemes"]
    assert "/api/v1/operations/summary" in spec["paths"]
    assert "/api/v1/notifications" in spec["paths"]
    assert "/api/v1/notifications/{notification_id}/acknowledge" in spec["paths"]
    assert "/api/v1/jobs/{job_id}/events" in spec["paths"]
    assert "/api/v1/help/ask" in spec["paths"]
    assert "/api/v1/help/articles" in spec["paths"]
