"""Очередь заданий для Doc-V: pull-модель, at-least-once с арендой.

Doc-V спрашивает через HTTP-Request /jobs/pending точкой на планировщике (N seconds, Настройте!) 

Создаёт документы из полученного JSON (Настройте точки маршрута)

Для подтверждения работы: /jobs/ack. Подробно:

Дубль при повторной выдаче обязана гаситься на стороне Doc-V выборкой по job_id перед
«Созданием» — поэтому ack просроченной аренды здесь считается успехом?
"""
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .db import connect


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


class JobQueue:
    def __init__(self, db_path: Path, *, lease_seconds: int, keep_days: int):
        self.db_path = db_path
        self.lease_seconds = lease_seconds
        self.keep_days = keep_days

    def enqueue(self, *, producer: str, job_type: str, payload: dict,
                idempotency_key: str | None) -> tuple[int, bool]:
        """-> (job_id, created). Повтор idempotency_key возвращает прежний id."""
        payload_json = json.dumps(payload, ensure_ascii=False)
        with connect(self.db_path) as conn:
            try:
                cur = conn.execute(
                    "INSERT INTO jobs (producer, idempotency_key, type, payload, created_at)"
                    " VALUES (?,?,?,?,?)",
                    (producer, idempotency_key, job_type, payload_json, _iso(_now())),
                )
                return cur.lastrowid, True
            except sqlite3.IntegrityError:
                row = conn.execute(
                    "SELECT id FROM jobs WHERE producer = ? AND idempotency_key = ?",
                    (producer, idempotency_key),
                ).fetchone()
                return row["id"], False

    def lease(self, *, consumer: str, limit: int) -> list[dict]:
        now = _now()
        until = _iso(now + timedelta(seconds=self.lease_seconds))
        with connect(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                "SELECT id, type, payload, attempts, created_at FROM jobs"
                " WHERE consumer = ? AND (status = 'pending'"
                "   OR (status = 'leased' AND leased_until < ?))"
                " ORDER BY id LIMIT ?",
                (consumer, _iso(now), limit),
            ).fetchall()
            if not rows:
                conn.execute("COMMIT")
                return []
            ids = [r["id"] for r in rows]
            marks = ",".join("?" * len(ids))
            conn.execute(
                f"UPDATE jobs SET status = 'leased', leased_until = ?,"
                f" attempts = attempts + 1 WHERE id IN ({marks})",
                [until, *ids],
            )
            conn.execute("COMMIT")
        return [
            {"job_id": r["id"], "type": r["type"], "payload": json.loads(r["payload"]),
             "attempts": r["attempts"] + 1, "created_at": r["created_at"]}
            for r in rows
        ]

    def ack(self, ids: list[int]) -> dict:
        acked, already, unknown = [], [], []
        with connect(self.db_path) as conn:
            for job_id in ids:
                row = conn.execute(
                    "SELECT status FROM jobs WHERE id = ?", (job_id,)
                ).fetchone()
                if row is None:
                    unknown.append(job_id)
                elif row["status"] == "acked":
                    already.append(job_id)
                else:
                    conn.execute(
                        "UPDATE jobs SET status = 'acked', acked_at = ?,"
                        " leased_until = NULL WHERE id = ?",
                        (_iso(_now()), job_id),
                    )
                    acked.append(job_id)
        return {"acked": acked, "already_acked": already, "unknown": unknown}

    def list_jobs(self, *, status: str | None = None, search: str = "",
                  producer: str = "", limit: int = 200) -> list[dict]:
        """search ищет по номеру, типу и содержимому payload."""
        query = ("SELECT id, consumer, producer, type, status, attempts,"
                 " leased_until, created_at, acked_at, payload FROM jobs")
        where, args = [], []
        if status:
            where.append("status = ?")
            args.append(status)
        if producer:
            where.append("producer = ?")
            args.append(producer)
        if search:
            where.append("(CAST(id AS TEXT) = ? OR type LIKE ? OR payload LIKE ?)")
            args += [search, f"%{search}%", f"%{search}%"]
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with connect(self.db_path) as conn:
            return [dict(r) for r in conn.execute(query, args).fetchall()]

    def producers(self) -> list[str]:
        with connect(self.db_path) as conn:
            return [r["producer"] for r in conn.execute(
                "SELECT DISTINCT producer FROM jobs ORDER BY producer").fetchall()]

    def stats(self) -> dict[str, int]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM jobs GROUP BY status").fetchall()
        return {r["status"]: r["n"] for r in rows}

    def sweep(self) -> int:
        cutoff = _iso(_now() - timedelta(days=self.keep_days))
        with connect(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM jobs WHERE status = 'acked' AND acked_at < ?", (cutoff,))
        return cur.rowcount
