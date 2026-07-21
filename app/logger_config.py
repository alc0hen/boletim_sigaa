"""
app/logger_config.py
────────────────────
Configuração centralizada de logging para o projeto boletim_sigaa.

• Dev  → RichHandler (colorido, legível no terminal)
• Prod → JSON handler (compatível com Render / serviços de log)

Uso:
    from app.logger_config import setup_logging
    setup_logging(is_prod=False)
"""

import logging
import sys
import time
import traceback


# ──────────────────────────────────────────────────────────────
# Formatters
# ──────────────────────────────────────────────────────────────

class _DevFormatter(logging.Formatter):
    """Fallback colorido simples, caso o pacote `rich` não esteja instalado."""

    LEVEL_COLORS = {
        logging.DEBUG:    "\033[36m",   # cyan
        logging.INFO:     "\033[32m",   # green
        logging.WARNING:  "\033[33m",   # yellow
        logging.ERROR:    "\033[31m",   # red
        logging.CRITICAL: "\033[35m",   # magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, "")
        level = f"{color}{record.levelname:<8}{self.RESET}"
        name  = f"\033[2m{record.name}\033[0m"          # dim
        msg   = record.getMessage()

        # Inclui traceback se houver
        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)

        ts = time.strftime("%H:%M:%S", time.localtime(record.created))
        return f"[{ts}] {level} {msg}  ({name})"


class _JsonFormatter(logging.Formatter):
    """Saída JSON — um objeto por linha para produção."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        doc = {
            "ts":      self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level":   record.levelname,
            "logger":  record.name,
            "msg":     record.getMessage(),
        }
        if record.exc_info:
            doc["traceback"] = self.formatException(record.exc_info)
        return json.dumps(doc, ensure_ascii=False)


# ──────────────────────────────────────────────────────────────
# setup_logging()
# ──────────────────────────────────────────────────────────────

def setup_logging(is_prod: bool = False) -> None:
    """
    Configura o logging global do projeto.

    Deve ser chamado UMA vez, antes de create_app().
    Remove handlers duplicados do basicConfig anterior.
    """
    root = logging.getLogger()

    # Remove quaisquer handlers herdados de basicConfig
    root.handlers.clear()

    # ── Escolhe o handler/formatter de acordo com o ambiente ──
    if is_prod:
        handler: logging.Handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
    else:
        try:
            from rich.logging import RichHandler
            handler = RichHandler(
                show_time=True,
                show_path=True,
                rich_tracebacks=True,
                tracebacks_show_locals=True,
                markup=True,
            )
        except ImportError:
            # Sem o pacote rich: usa o formatter colorido simples
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(_DevFormatter())

    root.setLevel(logging.DEBUG)
    root.addHandler(handler)

    # ── Níveis por logger ──────────────────────────────────────
    _configure_levels(is_prod)


def _configure_levels(is_prod: bool) -> None:
    """Ajusta níveis individuais para silenciar loggers barulhentos."""

    levels: dict[str, int] = {
        # Projeto
        "app":                   logging.DEBUG if not is_prod else logging.INFO,
        "__main__":              logging.DEBUG,

        # Hypercorn — access log: deixamos INFO para ver as requisições HTTP
        "hypercorn.access":      logging.INFO,
        # Hypercorn — error: só erros reais
        "hypercorn.error":       logging.WARNING,

        # SQLAlchemy — muito barulhento por padrão
        "sqlalchemy.engine":     logging.WARNING,
        "sqlalchemy.pool":       logging.WARNING,
        "sqlalchemy.dialects":   logging.WARNING,
        "sqlalchemy.orm":        logging.WARNING,

        # Asyncio — warnings já suficientes
        "asyncio":               logging.WARNING,

        # Websockets
        "websockets":            logging.WARNING,
        "websockets.server":     logging.WARNING,
        "websockets.client":     logging.WARNING,

        # aiohttp
        "aiohttp":               logging.WARNING,
        "aiohttp.access":        logging.WARNING,
    }

    for name, level in levels.items():
        logging.getLogger(name).setLevel(level)


# ──────────────────────────────────────────────────────────────
# Helpers para uso no middleware do __init__.py
# ──────────────────────────────────────────────────────────────

def format_http_start(method: str, path: str, remote_addr: str) -> str:
    """Linha de log no início de cada requisição."""
    return f"▶ {method} {path}  [{remote_addr}]"


def format_http_end(
    method: str,
    path: str,
    status: int,
    elapsed_ms: float,
    user_id: object = None,
) -> str:
    """Linha de log no fim de cada requisição com status e latência."""
    status_color = _status_color(status)
    user_tag = f"  [user_id={user_id}]" if user_id is not None else ""
    return (
        f"◀ {method} {path} "
        f"{status_color}{status}\033[0m "
        f"{elapsed_ms:.0f}ms"
        f"{user_tag}"
    )


def _status_color(status: int) -> str:
    if status < 300:
        return "\033[32m"   # green
    if status < 400:
        return "\033[36m"   # cyan
    if status < 500:
        return "\033[33m"   # yellow
    return "\033[31m"       # red
