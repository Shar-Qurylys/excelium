"""Отметки «Doc-V выходил на связь»: последний опрос очереди, последний
рендер, последняя операция. Пишутся в базу (переживают перезапуск и
видны из любого воркера); частые касания одного вида схлопываются —
запись не чаще раза в 5 секунд."""
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .jobsqueue.db import connect

KINDS = {"jobs_poll": "Опрос очереди", "render": "Рендер", "ops": "Операции"}
WRITE_EVERY_SEC = 5


class Heartbeat:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._last_write: dict[str, float] = {}

    def touch(self, kind: str) -> None:
        now = time.monotonic()
        with self._lock:
            if now - self._last_write.get(kind, 0) < WRITE_EVERY_SEC:
                return
            self._last_write[kind] = now
        with connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO heartbeat (kind, seen_at) VALUES (?,?)"
                " ON CONFLICT(kind) DO UPDATE SET seen_at=excluded.seen_at",
                (kind, datetime.now(timezone.utc).isoformat(timespec="seconds")))

    def snapshot(self) -> dict[str, dict]:
        with connect(self.db_path) as conn:
            rows = {r["kind"]: r["seen_at"] for r in
                    conn.execute("SELECT kind, seen_at FROM heartbeat").fetchall()}
        out = {}
        now = datetime.now(timezone.utc)
        for kind, label in KINDS.items():
            seen = rows.get(kind)
            age = None
            if seen:
                try:
                    age = int((now - datetime.fromisoformat(seen)).total_seconds())
                except ValueError:
                    pass
            out[kind] = {"label": label, "seen_at": seen, "age_sec": age}
        return out
