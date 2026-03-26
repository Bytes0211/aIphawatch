"""Redis async connection pool."""

import redis.asyncio as aioredis

from alphawatch.config import get_settings

_pool: aioredis.Redis | None = None


async def init_redis() -> aioredis.Redis:
    """Initialize the Redis connection pool.

    Returns:
        The shared Redis client instance.
    """
    global _pool
    settings = get_settings()
    _pool = aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    return _pool


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


def get_redis_pool() -> aioredis.Redis:
    """Return the current Redis client.

    Raises:
        RuntimeError: If the pool has not been initialized.
    """
    if _pool is None:
        raise RuntimeError("Redis pool not initialized. Call init_redis() first.")
    return _pool
