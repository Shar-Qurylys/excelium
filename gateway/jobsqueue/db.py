"""Одна sqlite-база шлюза: очередь заданий + реестр выданных файлов."""
import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  consumer TEXT NOT NULL DEFAULT 'docv',
  producer TEXT NOT NULL,
  idempotency_key TEXT,
  type TEXT NOT NULL,
  payload TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','leased','acked')),
  attempts INTEGER NOT NULL DEFAULT 0,
  leased_until TEXT,
  created_at TEXT NOT NULL,
  acked_at TEXT,
  UNIQUE (producer, idempotency_key)
);
CREATE INDEX IF NOT EXISTS ix_jobs_lease ON jobs(consumer, status, leased_until);
CREATE TABLE IF NOT EXISTS files (
  token TEXT PRIMARY KEY,
  orig_name TEXT NOT NULL,
  suffix TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.executescript(_SCHEMA)
