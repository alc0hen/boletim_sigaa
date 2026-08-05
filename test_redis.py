import asyncio
import logging
import uuid
import time
from app.cache import client
logger = logging.getLogger(__name__)

async def run_redis_test():
    try:
        await asyncio.sleep(2)
        test_key = f'startup_test:{uuid.uuid4().hex}'
        test_val = f'test_value_{time.time()}'
        logger.info('🔄 Iniciando teste de conectividade (SET e GET) no Redis...')
        await client.set(test_key, test_val, ex=10)
        retrieved_val = await client.get(test_key)
        if retrieved_val == test_val:
            logger.info('✅ Redis: Troca de informações concluída com sucesso! Conexão estável.')
        else:
            logger.error(f'❌ Redis: Falha de integridade. Esperado {test_val}, recebido {retrieved_val}')
        await client.delete(test_key)
    except Exception as e:
        logger.error(f'❌ Redis: Falha completa na comunicação durante o teste de startup: {e}')