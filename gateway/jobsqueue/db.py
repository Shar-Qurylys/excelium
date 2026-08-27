"""SQLite база шлюза: 
Функции: 
  1. Ведение очереди заданий.
  2. Ведение реестра выданных файлов.
"""
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
CREATE TABLE IF NOT EXISTS typst_templates (
  name TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS typst_template_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  source TEXT NOT NULL,
  saved_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_typst_history ON typst_template_history(name, id);
CREATE TABLE IF NOT EXISTS typst_assets (
  name TEXT PRIMARY KEY,
  data BLOB NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS directories (
  name TEXT NOT NULL,
  uid TEXT NOT NULL,
  data TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (name, uid)
);
CREATE TABLE IF NOT EXISTS heartbeat (
  kind TEXT PRIMARY KEY,
  seen_at TEXT NOT NULL
);
"""

# default: PRAGMA journal_mode=WAL
# - 
# default: PRAGMA foreign_keys=ON
#
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
    path.chmod(0o600)