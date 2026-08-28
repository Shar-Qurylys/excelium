"""Журнал вызовов API-консоли: что отправляли и что вернулось.

Кольцевой буфер в памяти процесса — истории на перезапуск не нужно,
задача журнала показать последние пробы администратора.
"""
import threading
from collections import deque
from datetime import datetime, timedelta, timezone

ALMATY = timezone(timedelta(hours=5))
LIMIT = 30


class ApiLog:
    def __init__(self):
        self._lock = threading.Lock()
        self._items: deque = deque(maxlen=LIMIT)

    def add(self, method: str, path: str, status: int, duration_ms: int,
            size: int) -> None:
        with self._lock:
            self._items.appendleft({
                "time": datetime.now(ALMATY).strftime("%H:%M:%S"),
                "method": method, "path": path, "status": status,
                "duration_ms": duration_ms, "size": size,
                "tone": ("success" if status < 300 else
                         "warn" if status < 500 else "danger"),
            })

    def items(self) -> list[dict]:
        with self._lock:
            return list(self._items)
