import logging
import os
import secrets
import time
logger = logging.getLogger(__name__)
_FALSY = {'', '0', 'false', 'no', 'off', 'none', 'null'}
_PRODUCTION_FLAGS = ('RENDER', 'IS_PRODUCTION', 'PRODUCTION')
_PRODUCTION_ENVS = {'production', 'prod'}

def _truthy(value) -> bool:
    return bool(value) and str(value).strip().lower() not in _FALSY

def is_production() -> bool:
    for flag in _PRODUCTION_FLAGS:
        if _truthy(os.environ.get(flag)):
            return True
    env = os.environ.get('FLASK_ENV') or os.environ.get('ENV') or ''
    return env.strip().lower() in _PRODUCTION_ENVS

def load_secret_key() -> str:
    key = os.environ.get('SECRET_KEY')
    if key:
        return key
    if is_production():
        raise ValueError('SECRET_KEY é obrigatória em produção. Defina-a nas variáveis de ambiente.')
    logger.warning('⚠️ SECRET_KEY ausente: gerando uma chave aleatória só para esta execução. As sessões serão invalidadas a cada reinício. Defina SECRET_KEY no .env.')
    return secrets.token_hex(32)

def is_dev_emulation() -> bool:
    if is_production():
        return False
    return _truthy(os.environ.get('IS_DEV'))

def sanitize_for_log(value, max_length: int=200) -> str:
    text = str(value)
    cleaned = ''.join((ch if ch.isprintable() else ' ' for ch in text))
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length] + '…'
    return cleaned

class RateLimiter:

    def __init__(self, max_attempts: int, window_seconds: float):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._last_prune = 0.0

    def _redis_key(self, key: str) -> str:
        return f'ratelimit:{int(self.window_seconds)}:{key}'

    def _prune(self, now: float):
        if now - self._last_prune < self.window_seconds:
            return
        self._last_prune = now
        cutoff = now - self.window_seconds
        for key in [k for k, v in self._hits.items() if not v or v[-1] < cutoff]:
            self._hits.pop(key, None)

    def _check_local(self, key: str) -> float:
        now = time.monotonic()
        self._prune(now)
        cutoff = now - self.window_seconds
        attempts = [t for t in self._hits.get(key, []) if t > cutoff]
        if len(attempts) >= self.max_attempts:
            self._hits[key] = attempts
            return max(0.0, attempts[0] + self.window_seconds - now)
        attempts.append(now)
        self._hits[key] = attempts
        return 0.0

    async def check(self, key: str) -> float:
        from .cache import client
        rkey = self._redis_key(key)
        try:
            pipe = client.pipeline()
            pipe.incr(rkey)
            pipe.ttl(rkey)
            count, ttl = await pipe.execute()
            if ttl is None or ttl < 0:
                await client.expire(rkey, int(self.window_seconds))
                ttl = int(self.window_seconds)
            if count > self.max_attempts:
                return float(max(ttl, 1))
            return 0.0
        except Exception as exc:
            logger.warning('Rate limit via Redis indisponível (%s); usando contagem local.', exc)
            return self._check_local(key)

    async def reset(self, key: str):
        from .cache import client
        self._hits.pop(key, None)
        try:
            await client.delete(self._redis_key(key))
        except Exception as exc:
            logger.warning('Falha ao resetar rate limit no Redis: %s', exc)