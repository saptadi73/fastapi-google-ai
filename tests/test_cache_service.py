from datetime import datetime, timezone

from app.services import cache_service


def test_similarity_cache_key_normalizes_values_and_tracks_taxonomy_version():
    first = cache_service.similarity_cache_key(
        tenant_id="tenant-a",
        taxonomy_id="taxonomy-a",
        taxonomy_version=3,
        values=["  Unit   Usaha ", "WILAYAH"],
        limit=5,
    )
    normalized = cache_service.similarity_cache_key(
        tenant_id="tenant-a",
        taxonomy_id="taxonomy-a",
        taxonomy_version=3,
        values=["unit usaha", "wilayah"],
        limit=5,
    )
    changed = cache_service.similarity_cache_key(
        tenant_id="tenant-a",
        taxonomy_id="taxonomy-a",
        taxonomy_version=4,
        values=["unit usaha", "wilayah"],
        limit=5,
    )

    assert first == normalized
    assert changed != first


async def test_json_cache_encodes_datetime_and_fails_open(monkeypatch):
    class FakeRedis:
        value = None

        async def get(self, key):
            return self.value

        async def setex(self, key, ttl, value):
            self.value = value

        async def aclose(self):
            pass

    fake = FakeRedis()
    monkeypatch.setattr(cache_service.Redis, "from_url", lambda *args, **kwargs: fake)
    timestamp = datetime(2026, 10, 4, tzinfo=timezone.utc)

    await cache_service.set_cached_json("cache-key", {"created_at": timestamp}, ttl_seconds=60)

    assert await cache_service.get_cached_json("cache-key") == {
        "created_at": "2026-10-04T00:00:00+00:00"
    }

    async def unavailable(key):
        raise ConnectionError("redis unavailable")

    fake.get = unavailable
    assert await cache_service.get_cached_json("cache-key") is None
