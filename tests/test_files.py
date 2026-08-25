from datetime import datetime, timedelta, timezone

from gateway.jobsqueue.db import connect


def test_roundtrip(client):
    store = client.app.state.filestore
    token = store.save_bytes(b"hello", ".txt", "отчет.txt")
    r = client.get(f"/files/{token}")
    assert r.status_code == 200
    assert r.content == b"hello"
    assert "otchet" in r.headers["content-disposition"] or "%D0" in r.headers["content-disposition"]


def test_unknown_token_404(client):
    assert client.get("/files/" + "a" * 24).status_code == 404
    assert client.get("/files/short").status_code == 404


def test_sweep_removes_expired(client):
    store = client.app.state.filestore
    token = store.save_bytes(b"old", ".txt", "old.txt")
    old = (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat(timespec="seconds")
    with connect(client.settings.db_path) as conn:
        conn.execute("UPDATE files SET created_at = ? WHERE token = ?", (old, token))
    assert store.sweep() >= 1
    assert client.get(f"/files/{token}").status_code == 404
