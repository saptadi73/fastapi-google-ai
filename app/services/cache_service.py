import json

from fastapi.encoders import jsonable_encoder
from redis.asyncio import Redis

from app.core.config import get_settings
from app.services.profiling_service import digest

SIMILARITY_ALGORITHM_VERSION = "sequence-matcher-v1"


def similarity_cache_key(*, tenant_id, taxonomy_id, taxonomy_version, values, limit):
    return "similarity:" + digest(
        [
            tenant_id,
            str(taxonomy_id),
            taxonomy_version,
            SIMILARITY_ALGORITHM_VERSION,
            [" ".join(value.strip().casefold().split()) for value in values],
            limit,
        ]
    )


async def get_cached_json(key):
    settings = get_settings()
    redis = Redis.from_url(
        settings.redis_url.get_secret_value(), socket_connect_timeout=0.3, socket_timeout=0.3
    )
    try:
        value = await redis.get(key)
        return json.loads(value) if value else None
    except Exception:
        return None
    finally:
        await redis.aclose()


async def set_cached_json(key, value, *, ttl_seconds):
    settings = get_settings()
    redis = Redis.from_url(
        settings.redis_url.get_secret_value(), socket_connect_timeout=0.3, socket_timeout=0.3
    )
    try:
        await redis.setex(key, ttl_seconds, json.dumps(jsonable_encoder(value)))
    except Exception:
        pass
    finally:
        await redis.aclose()
