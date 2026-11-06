"""Cliente Redis compartido (sesiones y control de intentos de login)."""

import redis.asyncio as redis

from app.core.config import settings

_client = None


def get_redis():
    global _client

    if _client is None:
        _client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )

    return _client
