import httpx

from app.main import app


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
