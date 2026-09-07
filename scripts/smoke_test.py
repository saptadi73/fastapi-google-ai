"""Start a temporary local API process, verify real HTTP, then stop only that process."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from app.core.config import get_settings

    settings = get_settings()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    storage = ROOT / "storage"
    storage.mkdir(exist_ok=True)
    with (storage / "smoke-test.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5) as client:
                for _ in range(60):
                    if process.poll() is not None:
                        raise RuntimeError("API exited; see storage/smoke-test.log")
                    try:
                        response = client.get("/health/live")
                        if response.status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.25)
                else:
                    raise RuntimeError("API did not become ready")
                response = client.get("/health/ready")
                assert response.status_code == 200, response.text
                print("Readiness:", response.json()["data"])
                response = client.post(
                    settings.api_v1_prefix + "/auth/login",
                    json={
                        "tenant_code": settings.bootstrap_tenant,
                        "username": settings.bootstrap_username,
                        "password": settings.bootstrap_password.get_secret_value(),
                    },
                )
                assert response.status_code == 200, "Bootstrap login failed (password may have been changed)."
                token = response.json()["data"]["access_token"]
                response = client.get(
                    settings.api_v1_prefix + "/auth/me", headers={"Authorization": "Bearer " + token}
                )
                assert response.status_code == 200
                assert response.json()["data"]["role"] == "PLATFORM_ADMIN"
                spec = client.get("/openapi.json").json()
                print(f"HTTP smoke passed: login, JWT auth/me, health, {len(spec['paths'])} OpenAPI paths.")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
