"""Capture the tested dependency closure without unrelated packages in the developer venv."""

import sys
from importlib.metadata import distribution
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = [
    "fastapi",
    "uvicorn[standard]",
    "pydantic",
    "pydantic-settings",
    "sqlalchemy[asyncio]",
    "asyncpg",
    "alembic",
    "google-api-python-client",
    "google-auth",
    "google-auth-httplib2",
    "httplib2",
    "openai",
    "sqlglot",
    "redis",
    "celery[redis]",
    "tenacity",
    "httpx",
    "PyJWT",
    "pwdlib[argon2]",
    "structlog",
    "openpyxl",
    "PyYAML",
    "python-dotenv",
]
DEVELOPMENT = ["pytest", "pytest-asyncio", "pytest-cov", "ruff"]


def pin(spec):
    req = Requirement(spec)
    extras = "[" + ",".join(sorted(req.extras)) + "]" if req.extras else ""
    return f"{req.name}{extras}=={distribution(req.name).version}"


def main():
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    (ROOT / "requirements.txt").write_text(
        f"# Tested runtime dependencies (Python {python_version}).\n" + "\n".join(map(pin, RUNTIME)) + "\n"
    )
    (ROOT / "requirements-dev.txt").write_text(
        "-r requirements.txt\n" + "\n".join(map(pin, DEVELOPMENT)) + "\n"
    )
    versions, visited, pending = {}, set(), list(map(Requirement, RUNTIME + DEVELOPMENT))
    while pending:
        req = pending.pop()
        key = canonicalize_name(req.name)
        visit = (key, tuple(sorted(req.extras)))
        if visit in visited:
            continue
        visited.add(visit)
        dist = distribution(req.name)
        versions[key] = dist.version
        for child_text in dist.requires or []:
            child = Requirement(child_text)
            if child.marker is None or any(
                child.marker.evaluate({"extra": extra}) for extra in ["", *req.extras]
            ):
                pending.append(child)
    (ROOT / "requirements.lock").write_text(
        f"# Tested complete dependency closure for Windows / Python {python_version}.\n"
        "# Runtime-only installations may use requirements.txt; CI reproduces this lock.\n"
        + "\n".join(f"{name}=={versions[name]}" for name in sorted(versions))
        + "\n"
    )
    print(f"Pinned {len(versions)} dependencies.")


if __name__ == "__main__":
    main()
