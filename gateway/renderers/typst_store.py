"""Шаблоны Typst и их картинки в базе шлюза.

Шаблон правится в веб-интерфейсе; каждое сохранение кладёт прежний
текст в историю (хранится 20 последних версий). Картинки (логотипы,
печати) — общий набор для всех шаблонов: в шаблоне их подключают как
`#image("assets/имя.png")`, при рендере они материализуются в папку
assets/ рядом с шаблоном.

При старте база засевается файлами из templates/typst/ — файл с новым
именем появляется в базе автоматически, но правки дальше живут в базе,
файл на диске больше не читается.
"""
import re
from datetime import datetime, timezone
from pathlib import Path

from ..jobsqueue.db import connect

NAME_RE = re.compile(r"^[a-z0-9_-]{1,64}$")
ASSET_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}\.(png|jpg|jpeg|gif|svg)$")
HISTORY_KEEP = 20
ASSET_LIMIT = 5 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class TypstStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    # --- шаблоны ---------------------------------------------------------

    def list_templates(self) -> list[dict]:
        with connect(self.db_path) as conn:
            return [dict(r) for r in conn.execute(
                "SELECT name, updated_at, length(source) AS size"
                " FROM typst_templates ORDER BY name").fetchall()]

    def get(self, name: str) -> str | None:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT source FROM typst_templates WHERE name = ?",
                               (name,)).fetchone()
        return row["source"] if row else None

    def save(self, name: str, source: str) -> None:
        if not NAME_RE.fullmatch(name):
            raise ValueError("имя шаблона — только [a-z0-9_-], до 64 знаков")
        with connect(self.db_path) as conn:
            prev = conn.execute("SELECT source FROM typst_templates WHERE name = ?",
                                (name,)).fetchone()
            if prev and prev["source"] != source:
                conn.execute(
                    "INSERT INTO typst_template_history (name, source, saved_at)"
                    " VALUES (?,?,?)", (name, prev["source"], _now()))
                conn.execute(
                    "DELETE FROM typst_template_history WHERE name = ? AND id NOT IN"
                    " (SELECT id FROM typst_template_history WHERE name = ?"
                    "  ORDER BY id DESC LIMIT ?)", (name, name, HISTORY_KEEP))
            conn.execute(
                "INSERT INTO typst_templates (name, source, updated_at) VALUES (?,?,?)"
                " ON CONFLICT(name) DO UPDATE SET source=excluded.source,"
                " updated_at=excluded.updated_at", (name, source, _now()))

    def delete(self, name: str) -> bool:
        with connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM typst_templates WHERE name = ?", (name,))
        return cur.rowcount > 0

    def history(self, name: str) -> list[dict]:
        with connect(self.db_path) as conn:
            return [dict(r) for r in conn.execute(
                "SELECT id, saved_at, length(source) AS size"
                " FROM typst_template_history WHERE name = ? ORDER BY id DESC",
                (name,)).fetchall()]

    def restore(self, name: str, history_id: int) -> bool:
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT source FROM typst_template_history WHERE id = ? AND name = ?",
                (history_id, name)).fetchone()
        if row is None:
            return False
        self.save(name, row["source"])
        return True

    def rename(self, old: str, new: str) -> bool:
        """Переносит шаблон под новым именем вместе с историей."""
        source = self.get(old)
        if source is None or self.get(new) is not None:
            return False
        with connect(self.db_path) as conn:
            conn.execute("UPDATE typst_templates SET name = ? WHERE name = ?", (new, old))
            conn.execute("UPDATE typst_template_history SET name = ? WHERE name = ?",
                         (new, old))
        return True

    def seed_from_dir(self, directory: Path) -> int:
        """Импортирует .typ-файлы, которых ещё нет в базе."""
        added = 0
        for path in sorted(directory.glob("*.typ")):
            if NAME_RE.fullmatch(path.stem) and self.get(path.stem) is None:
                self.save(path.stem, path.read_text(encoding="utf-8"))
                added += 1
        return added

    # --- картинки --------------------------------------------------------

    def list_assets(self) -> list[dict]:
        with connect(self.db_path) as conn:
            return [dict(r) for r in conn.execute(
                "SELECT name, length(data) AS size, updated_at"
                " FROM typst_assets ORDER BY name").fetchall()]

    def save_asset(self, name: str, data: bytes) -> None:
        if not ASSET_RE.fullmatch(name):
            raise ValueError("имя картинки: буквы/цифры/-/_ и расширение png/jpg/jpeg/gif/svg")
        if len(data) > ASSET_LIMIT:
            raise ValueError("картинка больше 5 МБ")
        with connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO typst_assets (name, data, updated_at) VALUES (?,?,?)"
                " ON CONFLICT(name) DO UPDATE SET data=excluded.data,"
                " updated_at=excluded.updated_at", (name, data, _now()))

    def delete_asset(self, name: str) -> bool:
        with connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM typst_assets WHERE name = ?", (name,))
        return cur.rowcount > 0

    def assets_bytes(self) -> dict[str, bytes]:
        with connect(self.db_path) as conn:
            return {r["name"]: r["data"] for r in
                    conn.execute("SELECT name, data FROM typst_assets").fetchall()}
