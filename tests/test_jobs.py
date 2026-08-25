from datetime import datetime, timedelta, timezone

from gateway.jobsqueue.db import connect

from conftest import docv_headers, producer_headers


def _put(client, payload=None, key=None, jtype="создай_контрагента"):
    body = {"type": jtype, "payload": payload or {"bin": "123"}}
    if key:
        body["idempotency_key"] = key
    return client.post("/jobs", json=body, headers=producer_headers())


def test_enqueue_lease_ack_cycle(client):
    job_id = _put(client).json()["job_id"]

    r = client.get("/jobs/pending", headers=docv_headers())
    jobs = r.json()
    assert [j["job_id"] for j in jobs] == [job_id]
    assert jobs[0]["payload"] == {"bin": "123"} and jobs[0]["attempts"] == 1

    # в пределах аренды повторная выдача пуста — и это буквально []
    r2 = client.get("/jobs/pending", headers=docv_headers())
    assert r2.content == b"[]"

    ack = client.post("/jobs/ack", json={"ids": [job_id]}, headers=docv_headers()).json()
    assert ack == {"acked": [job_id], "already_acked": [], "unknown": []}
    assert client.get("/jobs/pending", headers=docv_headers()).json() == []


def test_expired_lease_redelivered(client):
    job_id = _put(client).json()["job_id"]
    client.get("/jobs/pending", headers=docv_headers())
    expired = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(timespec="seconds")
    with connect(client.settings.db_path) as conn:
        conn.execute("UPDATE jobs SET leased_until = ? WHERE id = ?", (expired, job_id))
    jobs = client.get("/jobs/pending", headers=docv_headers()).json()
    assert jobs[0]["job_id"] == job_id and jobs[0]["attempts"] == 2


def test_double_ack_and_unknown(client):
    job_id = _put(client).json()["job_id"]
    client.get("/jobs/pending", headers=docv_headers())
    client.post("/jobs/ack", json={"ids": [job_id]}, headers=docv_headers())
    ack = client.post("/jobs/ack", json={"ids": [job_id, 777]}, headers=docv_headers()).json()
    assert ack == {"acked": [], "already_acked": [job_id], "unknown": [777]}


def test_ack_after_redelivery_still_ok(client):
    """ack от «первого» потребителя после пере-выдачи — успех (at-least-once)."""
    job_id = _put(client).json()["job_id"]
    client.get("/jobs/pending", headers=docv_headers())
    expired = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(timespec="seconds")
    with connect(client.settings.db_path) as conn:
        conn.execute("UPDATE jobs SET leased_until = ? WHERE id = ?", (expired, job_id))
    client.get("/jobs/pending", headers=docv_headers())  # пере-выдано
    ack = client.post("/jobs/ack", json={"ids": [job_id]}, headers=docv_headers()).json()
    assert ack["acked"] == [job_id]


def test_idempotency_key(client):
    first = _put(client, key="1c-doc-42").json()
    second = _put(client, key="1c-doc-42").json()
    assert first == {"job_id": first["job_id"], "created": True}
    assert second == {"job_id": first["job_id"], "created": False}


def test_payload_limit_413(client):
    big = {"x": "а" * (client.settings.jobs_payload_limit + 1)}
    assert _put(client, payload=big).status_code == 413


def test_producer_token_required(client):
    r = client.post("/jobs", json={"type": "t", "payload": {}}, headers=docv_headers())
    assert r.status_code == 403


def test_docv_token_required_for_pending(client):
    assert client.get("/jobs/pending", headers=producer_headers()).status_code == 403


def test_lease_limit(client):
    for _ in range(5):
        _put(client)
    jobs = client.get("/jobs/pending?limit=2", headers=docv_headers()).json()
    assert len(jobs) == 2
