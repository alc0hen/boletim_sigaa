# app/cache.py
import os
import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# ── Connection Pool Configuration ──────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

client: aioredis.Redis = aioredis.from_url(
    REDIS_URL,
    decode_responses=True,
    max_connections=30,
    socket_timeout=3,
    socket_connect_timeout=1,
    socket_keepalive=True,
    health_check_interval=30,
    retry_on_timeout=True,
)

# ── Default TTLs by namespace (seconds) ───────────────────────────
_DEFAULT_TTLS: dict[str, int] = {
    "profile": 600,     # 10 minutes
    "history": 600,     # 10 minutes (alias used by academic_profile route)
    "historico": 30,    # 30 seconds
    "notas": 30,        # 30 seconds
}
_FALLBACK_TTL = 30  # seconds


def _make_key(namespace: str, identifier: str) -> str:
    """Construct a namespaced Redis key."""
    return f"{namespace}:{identifier}"


def _resolve_ttl(namespace: str, ttl: Optional[int] = None) -> int:
    """Return explicit ttl if given, otherwise namespace default, otherwise fallback."""
    if ttl is not None:
        return ttl
    return _DEFAULT_TTLS.get(namespace, _FALLBACK_TTL)


async def get(namespace: str, identifier: str) -> Optional[Any]:
    """Retrieve a cached value, deserialized from JSON, or ``None`` if missing."""
    key = _make_key(namespace, identifier)
    try:
        raw = await client.get(key)
    except Exception as exc:
        logger.warning("Redis GET failed for %s: %s", key, exc)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def set(namespace: str, identifier: str, value: Any, ttl: Optional[int] = None) -> None:
    """Cache ``value`` under ``namespace``/``identifier``.

    ``value`` must be JSON-serializable.
    If ``ttl`` is not provided, uses the namespace default (see ``_DEFAULT_TTLS``).
    """
    key = _make_key(namespace, identifier)
    resolved_ttl = _resolve_ttl(namespace, ttl)
    try:
        await client.set(key, json.dumps(value), ex=resolved_ttl)
    except Exception as exc:
        logger.warning("Redis SET failed for %s: %s", key, exc)
