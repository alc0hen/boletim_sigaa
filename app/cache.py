import os
import json
import logging
from typing import Any, Optional
import redis.asyncio as aioredis
logger = logging.getLogger(__name__)
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
client: aioredis.Redis = aioredis.from_url(REDIS_URL, decode_responses=True, max_connections=30, socket_timeout=3, socket_connect_timeout=1, socket_keepalive=True, health_check_interval=30, retry_on_timeout=True)
_DEFAULT_TTLS: dict[str, int] = {'profile': 600, 'history': 600, 'historico': 30, 'notas': 30}
_FALLBACK_TTL = 30
import time
_local_cache: dict[str, tuple[Any, float]] = {}

def _make_key(namespace: str, identifier: str) -> str:
    return f'{namespace}:{identifier}'

def _resolve_ttl(namespace: str, ttl: Optional[int]=None) -> int:
    if ttl is not None:
        return ttl
    return _DEFAULT_TTLS.get(namespace, _FALLBACK_TTL)

async def get(namespace: str, identifier: str) -> Optional[Any]:
    key = _make_key(namespace, identifier)
    try:
        raw = await client.get(key)
    except Exception as exc:
        logger.warning('Redis GET failed for %s: %s', key, exc)
        if key in _local_cache:
            val, exp = _local_cache[key]
            if time.time() < exp:
                return val
            else:
                del _local_cache[key]
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None

async def set(namespace: str, identifier: str, value: Any, ttl: Optional[int]=None) -> None:
    key = _make_key(namespace, identifier)
    resolved_ttl = _resolve_ttl(namespace, ttl)
    try:
        await client.set(key, json.dumps(value), ex=resolved_ttl)
    except Exception as exc:
        logger.warning('Redis SET failed for %s: %s', key, exc)
        _local_cache[key] = (value, time.time() + resolved_ttl)

async def delete(namespace: str, identifier: str) -> None:
    key = _make_key(namespace, identifier)
    try:
        await client.delete(key)
    except Exception as exc:
        logger.warning('Redis DEL failed for %s: %s', key, exc)
    _local_cache.pop(key, None)
_TEMP_PWD_NS = 'sigaa_pwd'

def temp_password_ttl() -> int:
    try:
        return int(os.getenv('SIGAA_TEMP_PWD_TTL', '600'))
    except ValueError:
        logger.warning('SIGAA_TEMP_PWD_TTL inválido; usando 600 segundos.')
        return 600

async def set_temp_password(ref: str, password: str) -> None:
    from .models import get_cipher_suite
    try:
        encrypted = get_cipher_suite().encrypt(password.encode('utf-8')).decode('utf-8')
    except Exception as exc:
        logger.warning('Falha ao cifrar a senha temporária: %s', exc)
        return
    await set(_TEMP_PWD_NS, ref, encrypted, ttl=temp_password_ttl())

async def get_temp_password(ref: str) -> Optional[str]:
    encrypted = await get(_TEMP_PWD_NS, ref)
    if not encrypted:
        return None
    from .models import get_cipher_suite
    try:
        return get_cipher_suite().decrypt(encrypted.encode('utf-8')).decode('utf-8')
    except Exception as exc:
        logger.warning('Falha ao decifrar a senha temporária: %s', exc)
        return None

async def clear_temp_password(ref: str) -> None:
    if ref:
        await delete(_TEMP_PWD_NS, ref)