import json
import logging
import os
import time
import uuid
from .errors import RemoteApiError, RemoteInvalidCredentials, RemoteQuestionnaireError, RemoteSessionExpired, RemoteUnavailable

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 45
HISTORY_TIMEOUT = 240
DETAILS_TIMEOUT = 90

def is_configured() -> bool:
    return bool(os.environ.get('SIGAA_REDIS_WORKERS'))

class SigaaRemoteClient:
    def __init__(self):
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            from ..cache import client as redis_client
            self._redis = redis_client
        return self._redis

    async def _request(self, action: str, payload: dict = None, timeout: float = None, session_id: str = None):
        redis = self._get_redis()
        task_id = uuid.uuid4().hex
        task = {
            'task_id': task_id,
            'action': action,
            'payload': payload or {},
            'timestamp': int(time.time())
        }
        
        # Route to specific worker if we know which worker owns this session
        queue = 'sigaa:tasks'
        if session_id:
            worker_id = await redis.get(f'sigaa:session:{session_id}:worker')
            if worker_id:
                queue = f'sigaa:worker:{worker_id}:tasks'
        
        # Push task to queue
        await redis.lpush(queue, json.dumps(task))
        
        # Wait for result via BLPOP
        result_key = f'sigaa:result:{task_id}'
        timeout_seconds = int(timeout or DEFAULT_TIMEOUT)
        result = await redis.blpop(result_key, timeout=timeout_seconds)
        
        if result is None:
            raise RemoteUnavailable('Nenhum worker SIGAA respondeu a tempo.')
        
        _, raw_response = result
        response = json.loads(raw_response)
        
        if not response.get('success'):
            error = response.get('error', {})
            self._raise_for_error(error)
        
        return response.get('data', {})

    @staticmethod
    def _raise_for_error(error: dict):
        code = error.get('code')
        detail = error.get('detail')
        status_code = error.get('status_code', 500)
        if code in ('session_not_found', 'sigaa_session_expired'):
            raise RemoteSessionExpired(status_code, code, detail)
        if code == 'questionnaire':
            raise RemoteQuestionnaireError(status_code, code, detail)
        if code == 'invalid_credentials':
            raise RemoteInvalidCredentials(status_code, code, detail)
        raise RemoteApiError(status_code, code, detail)

    async def healthy(self, force: bool = False) -> bool:
        try:
            redis = self._get_redis()
            cursor = 0
            while True:
                cursor, keys = await redis.scan(cursor, match='sigaa:worker:*:heartbeat', count=10)
                if keys:
                    return True
                if cursor == 0:
                    break
            return False
        except Exception as e:
            logger.warning('Health check dos workers SIGAA falhou: %s', e)
            return False

    async def create_session(self, url, institution, username, password):
        return await self._request('create_session', {
            'url': url, 'institution': institution,
            'username': username, 'password': password
        })

    async def list_bonds(self, session_id):
        return await self._request('list_bonds', {'session_id': session_id}, session_id=session_id)

    async def list_courses(self, session_id, bond_id):
        return await self._request('list_courses', {'session_id': session_id, 'bond_id': bond_id},
                                    timeout=DETAILS_TIMEOUT, session_id=session_id)

    async def course_details(self, session_id, bond_id, course_id):
        return await self._request('course_details', {
            'session_id': session_id, 'bond_id': bond_id, 'course_id': course_id
        }, timeout=DETAILS_TIMEOUT, session_id=session_id)

    async def history(self, session_id, bond_id, cached_history=None, parallel=True):
        return await self._request('history', {
            'session_id': session_id, 'bond_id': bond_id,
            'cached_history': cached_history, 'parallel': parallel
        }, timeout=HISTORY_TIMEOUT, session_id=session_id)

    async def enrollment_disciplines(self, session_id, bond_id):
        return await self._request('enrollment', {
            'session_id': session_id, 'bond_id': bond_id
        }, timeout=DETAILS_TIMEOUT, session_id=session_id)

    async def enrollment_selection(self, session_id, bond_id, selected_class_ids):
        return await self._request('enrollment_selection', {
            'session_id': session_id, 'bond_id': bond_id,
            'selected_class_ids': [str(c) for c in selected_class_ids]
        }, timeout=DETAILS_TIMEOUT, session_id=session_id)

    async def enrollment_confirm(self, session_id, bond_id, password):
        return await self._request('enrollment_confirm', {
            'session_id': session_id, 'bond_id': bond_id,
            'password': password
        }, timeout=DETAILS_TIMEOUT, session_id=session_id)

    async def close_session(self, session_id):
        return await self._request('close_session', {'session_id': session_id}, session_id=session_id)

    async def aclose(self):
        pass  # Redis client is shared via cache module, don't close it

_client = None

def get_client():
    global _client
    if not is_configured():
        return None
    if _client is None:
        _client = SigaaRemoteClient()
    return _client

async def close_client():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None