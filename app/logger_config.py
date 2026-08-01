import logging
import sys
import time
import traceback

class _DevFormatter(logging.Formatter):
    LEVEL_COLORS = {logging.DEBUG: '\x1b[36m', logging.INFO: '\x1b[32m', logging.WARNING: '\x1b[33m', logging.ERROR: '\x1b[31m', logging.CRITICAL: '\x1b[35m'}
    RESET = '\x1b[0m'

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, '')
        level = f'{color}{record.levelname:<8}{self.RESET}'
        name = f'\x1b[2m{record.name}\x1b[0m'
        msg = record.getMessage()
        if record.exc_info:
            msg += '\n' + self.formatException(record.exc_info)
        ts = time.strftime('%H:%M:%S', time.localtime(record.created))
        return f'[{ts}] {level} {msg}  ({name})'

class _JsonFormatter(logging.Formatter):

    def format(self, record: logging.LogRecord) -> str:
        import json
        doc = {'ts': self.formatTime(record, '%Y-%m-%dT%H:%M:%S'), 'level': record.levelname, 'logger': record.name, 'msg': record.getMessage()}
        if record.exc_info:
            doc['traceback'] = self.formatException(record.exc_info)
        return json.dumps(doc, ensure_ascii=False)

def setup_logging(is_prod: bool=False) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    if is_prod:
        handler: logging.Handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
    else:
        try:
            from rich.logging import RichHandler
            handler = RichHandler(show_time=True, show_path=True, rich_tracebacks=True, tracebacks_show_locals=True, markup=True)
        except ImportError:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(_DevFormatter())
    root.setLevel(logging.INFO if is_prod else logging.DEBUG)
    root.addHandler(handler)
    _configure_levels(is_prod)

def _configure_levels(is_prod: bool) -> None:
    levels: dict[str, int] = {'app': logging.DEBUG if not is_prod else logging.INFO, '__main__': logging.DEBUG, 'hypercorn.access': logging.INFO, 'hypercorn.error': logging.WARNING, 'sqlalchemy.engine': logging.WARNING, 'sqlalchemy.pool': logging.WARNING, 'sqlalchemy.dialects': logging.WARNING, 'sqlalchemy.orm': logging.WARNING, 'aiosqlite': logging.WARNING, 'asyncio': logging.WARNING, 'websockets': logging.WARNING, 'websockets.server': logging.WARNING, 'websockets.client': logging.WARNING, 'aiohttp': logging.WARNING, 'aiohttp.access': logging.WARNING}
    for name, level in levels.items():
        logging.getLogger(name).setLevel(level)

def format_http_start(method: str, path: str, remote_addr: str) -> str:
    return f'▶ {method} {path}  [{remote_addr}]'

def format_http_end(method: str, path: str, status: int, elapsed_ms: float, user_id: object=None) -> str:
    status_color = _status_color(status)
    user_tag = f'  [user_id={user_id}]' if user_id is not None else ''
    return f'◀ {method} {path} {status_color}{status}\x1b[0m {elapsed_ms:.0f}ms{user_tag}'

def _status_color(status: int) -> str:
    if status < 300:
        return '\x1b[32m'
    if status < 400:
        return '\x1b[36m'
    if status < 500:
        return '\x1b[33m'
    return '\x1b[31m'