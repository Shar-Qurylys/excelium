"""Выдача файлов по непере­бираемым токенам с TTL.

Файл лежит в var/files/<token><suffix>; человекочитаемое имя (то, под
которым файл скачает Doc-V) — в таблице files той же базы шлюза.
"""
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import Settings
from ..jobsqueue.db import connect

log = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,50}$")
_SUFFIX_RE = re.compile(r"^\.[A-Za-z0-9.]{1,10}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class FileStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.files_dir = settings.files_dir
        self.files_dir.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, data: bytes, suffix: str, orig_name: str) -> str:
        if not _SUFFIX_RE.fullmatch(suffix):
            raise ValueError(f"bad suffix: {suffix!r}")
        token = secrets.token_urlsafe(24)
        (self.files_dir / f"{token}{suffix}").write_bytes(data)
        with connect(self.settings.db_path) as conn:
            conn.execute(
                "INSERT INTO files (token, orig_name, suffix, created_at) VALUES (?,?,?,?)",
                (token, orig_name, suffix, _now()),
            )
        return token

    def save_file(self, path: Path, orig_name: str | None = None) -> str:
        return self.save_bytes(path.read_bytes(), path.suffix, orig_name or path.name)

    def resolve(self, token: str) -> tuple[Path, str] | None:
        """token -> (путь на диске, имя для скачивания) либо None."""
        if not TOKEN_RE.fullmatch(token):
            return None
        with connect(self.settings.db_path) as conn:
            row = conn.execute(
                "SELECT orig_name, suffix FROM files WHERE token = ?", (token,)
            ).fetchone()
        if row is None:
            return None
        path = self.files_dir / f"{token}{row['suffix']}"
        if not path.is_file():
            return None
        return path, row["orig_name"]

    def download_url(self, token: str) -> str:
        return f"{self.settings.base_url}/files/{token}"

    def list_files(self) -> list[dict]:
        with connect(self.settings.db_path) as conn:
            rows = conn.execute(
                "SELECT token, orig_name, suffix, created_at FROM files"
                " ORDER BY created_at DESC").fetchall()
        out = []
        for row in rows:
            path = self.files_dir / f"{row['token']}{row['suffix']}"
            out.append({"token": row["token"], "orig_name": row["orig_name"],
                        "suffix": row["suffix"], "created_at": row["created_at"],
                        "size": path.stat().st_size if path.is_file() else 0})
        return out

    def delete(self, token: str) -> bool:
        if not TOKEN_RE.fullmatch(token):
            return False
        with connect(self.settings.db_path) as conn:
            row = conn.execute("SELECT suffix FROM files WHERE token = ?", (token,)).fetchone()
            if row is None:
                return False
            conn.execute("DELETE FROM files WHERE token = ?", (token,))
        (self.files_dir / f"{token}{row['suffix']}").unlink(missing_ok=True)
        return True

    def sweep(self) -> int:
        """Удаляет файлы старше TTL и осиротевшие файлы без записи."""
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=self.settings.file_ttl_hours)
        ).isoformat(timespec="seconds")
        removed = 0
        with connect(self.settings.db_path) as conn:
            rows = conn.execute(
                "SELECT token, suffix FROM files WHERE created_at < ?", (cutoff,)
            ).fetchall()
            for row in rows:
                (self.files_dir / f"{row['token']}{row['suffix']}").unlink(missing_ok=True)
                removed += 1
            conn.execute("DELETE FROM files WHERE created_at < ?", (cutoff,))
            known = {r["token"] + r["suffix"] for r in conn.execute(
                "SELECT token, suffix FROM files").fetchall()}
        for f in self.files_dir.iterdir():
            if f.is_file() and f.name not in known:
                f.unlink(missing_ok=True)
                removed += 1
        if removed:
            log.info("filestore sweep", extra={"data": {"removed": removed}})
        return removed
