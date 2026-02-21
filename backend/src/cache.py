"""
QUALISYS API — Redis Client
Story: 1-1-user-account-creation
AC: AC6 — Redis-backed rate limiting
"""

from redis.asyncio import Redis

from src.config import get_settings

settings = get_settings()

_redis: Redis | None = None


def get_redis_client() -> Redis:
    """Returns (or creates) the module-level Redis client."""
    global _redis
    if _redis is None:
        _redis = Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def check_redis() -> dict:
    """Health check for /ready endpoint."""
    client = get_redis_client()
    await client.ping()
    return {"status": "ok"}
