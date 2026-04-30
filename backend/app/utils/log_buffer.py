from collections import deque
from datetime import datetime, timezone
import logging

_MAX = 500


class _LogBuffer:
    def __init__(self):
        self._entries = deque(maxlen=_MAX)

    def add(self, level: str, source: str, message: str):
        self._entries.appendleft({
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "level": level,
            "source": source,
            "message": message,
        })

    def get(self, limit: int = 200):
        return list(self._entries)[:limit]


log_buffer = _LogBuffer()


class _BufferHandler(logging.Handler):
    _SOURCE_MAP = {
        "app.services.health_monitor": "health",
        "app.services.sync_engine": "sync",
        "app.services.qubic_client": "client",
        "app.services.coingecko": "coingecko",
        "app.services.balance_service": "balance",
        "app.services.scheduler": "scheduler",
        "app.websocket.manager": "websocket",
        "app.api.v1.ws": "websocket",
    }

    def emit(self, record: logging.LogRecord):
        source = self._SOURCE_MAP.get(record.name, record.name.rsplit(".", 1)[-1])
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        log_buffer.add(record.levelname, source, msg)


def install_buffer_handler():
    """Attach the buffer handler to the root logger once at startup."""
    handler = _BufferHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.setLevel(logging.DEBUG)
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    app_logger.addHandler(handler)
