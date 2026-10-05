from types import SimpleNamespace

import pytest

from app.cli import reconcile_bootstrap_admin
from app.models.auth import Tenant, User


class FakeSession:
    def __init__(self, results):
        self.results = iter(results)
        self.added = []

    async def scalar(self, _statement):
        return next(self.results)

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        for item in self.added:
            if isinstance(item, Tenant) and item.id is None:
                item.id = "11111111-1111-4111-8111-111111111111"


def bootstrap_settings():
    return SimpleNamespace(
        bootstrap_tenant="default",
        bootstrap_full_name="ETL Administrator",
    )


@pytest.mark.asyncio
async def test_reconcile_bootstrap_admin_creates_platform_admin(monkeypatch):
    session = FakeSession([None, None])
    monkeypatch.setattr("app.cli.password_hasher.hash", lambda value: f"hashed:{value}")

    result = await reconcile_bootstrap_admin(
        session,
        bootstrap_settings(),
        password="strong-password",
        username="admin_etl@kanjabung.com",
        reset_password=False,
    )

    user = next(item for item in session.added if isinstance(item, User))
    assert result == "created"
    assert user.username == "admin_etl@kanjabung.com"
    assert user.role == "PLATFORM_ADMIN"
    assert user.password_hash == "hashed:strong-password"


@pytest.mark.asyncio
async def test_reconcile_bootstrap_admin_repairs_access_without_resetting_password():
    tenant = Tenant(id="11111111-1111-4111-8111-111111111111", code="default")
    user = User(
        tenant_id=tenant.id,
        username="admin_etl@kanjabung.com",
        full_name="",
        role="VIEWER",
        is_active=False,
        token_version=4,
        password_hash="existing-hash",
    )
    session = FakeSession([tenant, user])

    result = await reconcile_bootstrap_admin(
        session,
        bootstrap_settings(),
        password="strong-password",
        username=user.username,
        reset_password=False,
    )

    assert result == "unchanged"
    assert user.role == "PLATFORM_ADMIN"
    assert user.is_active is True
    assert user.full_name == "ETL Administrator"
    assert user.password_hash == "existing-hash"
    assert user.token_version == 5


@pytest.mark.asyncio
async def test_reconcile_bootstrap_admin_can_reset_password_and_revoke_tokens(monkeypatch):
    tenant = Tenant(id="11111111-1111-4111-8111-111111111111", code="default")
    user = User(
        tenant_id=tenant.id,
        username="admin_etl@kanjabung.com",
        full_name="Nama Admin Lama",
        role="PLATFORM_ADMIN",
        is_active=True,
        token_version=2,
        password_hash="old-hash",
    )
    session = FakeSession([tenant, user])
    monkeypatch.setattr("app.cli.password_hasher.hash", lambda value: f"hashed:{value}")

    result = await reconcile_bootstrap_admin(
        session,
        bootstrap_settings(),
        password="new-strong-password",
        username=user.username,
        reset_password=True,
    )

    assert result == "reset"
    assert user.full_name == "ETL Administrator"
    assert user.password_hash == "hashed:new-strong-password"
    assert user.token_version == 3
