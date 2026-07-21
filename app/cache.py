# app/cache.py
import os
import json
from typing import Any, Optional

import redis

# Initialize Redis client using environment variable or default localhost
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
client = redis.from_url(REDIS_URL, decode_responses=True)

def _make_key(namespace: str, identifier: str) -> str:
    """Construct a namespaced Redis key."""
    return f"{namespace}:{identifier}"

def get(namespace: str, identifier: str) -> Optional[Any]:
    """Retrieve a cached value, deserialized from JSON, or ``None`` if missing."""
    key = _make_key(namespace, identifier)
    raw = client.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None

def set(namespace: str, identifier: str, value: Any, ttl: int = 30) -> None:
    """Cache ``value`` under ``namespace``/``identifier`` for ``ttl`` seconds.

    ``value`` must be JSON‑serializable.
    """
    key = _make_key(namespace, identifier)
    client.set(key, json.dumps(value), ex=ttl)
