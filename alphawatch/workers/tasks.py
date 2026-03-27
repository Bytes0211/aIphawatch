"""Celery task app and task definitions for AIphaWatch."""

from __future__ import annotations

import os

from celery import Celery


def _redis_url_from_env(prefix: str) -> str:
    """Build a Redis URL from ECS-injected env vars.

    Args:
        prefix: Prefix of the Redis env var set (``REDIS_BROKER`` or
            ``REDIS_CACHE``).

    Returns:
        Redis connection string.
    """
    host = os.getenv(f"{prefix}_HOST", "localhost")
    port = os.getenv(f"{prefix}_PORT", "6379")
    password = os.getenv("REDIS_PASSWORD", "")
    auth = f":{password}@" if password else ""
    return f"redis://{auth}{host}:{port}/0"


broker_url = _redis_url_from_env("REDIS_BROKER")
backend_url = _redis_url_from_env("REDIS_CACHE")

celery_app = Celery("alphawatch", broker=broker_url, backend=backend_url)


@celery_app.task(name="alphawatch.health.ping")
def ping() -> str:
    """Simple worker health task used for smoke checks."""
    return "pong"
