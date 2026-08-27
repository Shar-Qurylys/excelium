"""Справочники соответствий из Doc-V (uid -> данные для печати).

Doc-V сериализует табличные и ссылочные поля сырыми UID-ами; шлюз
данных Doc-V не видит, поэтому Doc-V периодически выгружает сюда
соответствия (POST /directory/{имя}), а рендер подкладывает их шаблонам
третьим входом sys.inputs.dir. Замена полная: каждый POST замещает
справочник целиком (устаревшие записи не копятся).
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .jobsqueue.db import connect

NAME_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
MAX_ITEMS = 20000


class DirectoryStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def replace(self, name: str, items: list[dict]) -> int:
        """items: [{"uid": "...", ...остальные ключи как есть}]."""
        if not NAME_RE.fullmatch(name):
            raise ValueError("имя справочника: [a-z0-9_-], до 32 знаков")
        if len(items) > MAX_ITEMS:
            raise ValueError(f"больше {MAX_ITEMS} записей")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        rows = []
        for item in items:
            if not isinstance(item, dict) or not str(item.get("uid") or "").strip():
                continue
            uid = str(item["uid"]).strip()
            payload = {k: v for k, v in item.items() if k != "uid"}
            rows.append((name, uid, json.dumps(payload, ensure_ascii=False), now))
        with connect(self.db_path) as conn:
            conn.execute("DELETE FROM directories WHERE name = ?", (name,))
            conn.executemany(
                "INSERT INTO directories (name, uid, data, updated_at) VALUES (?,?,?,?)",
                rows)
        return len(rows)

    def all(self) -> dict[str, dict[str, dict]]:
        """-> {имя: {uid: {...}}} — целиком, для входа dir рендера."""
        out: dict[str, dict[str, dict]] = {}
        with connect(self.db_path) as conn:
            for r in conn.execute("SELECT name, uid, data FROM directories").fetchall():
                out.setdefault(r["name"], {})[r["uid"]] = json.loads(r["data"])
        return out

    def sweep(self, keep_days: int = 30) -> int:
        """Удаляет справочники, которые не обновлялись keep_days дней:
        заброшенная выгрузка не должна оставлять данные лежать вечно."""
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).isoformat(
            timespec="seconds")
        with connect(self.db_path) as conn:
            stale = [r["name"] for r in conn.execute(
                "SELECT name FROM directories GROUP BY name"
                " HAVING MAX(updated_at) < ?", (cutoff,)).fetchall()]
            for name in stale:
                conn.execute("DELETE FROM directories WHERE name = ?", (name,))
        return len(stale)

    def stats(self) -> dict[str, int]:
        with connect(self.db_path) as conn:
            return {r["name"]: r["n"] for r in conn.execute(
                "SELECT name, COUNT(*) AS n FROM directories GROUP BY name").fetchall()}
