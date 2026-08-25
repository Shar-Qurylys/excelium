from fastapi.testclient import TestClient

from gateway.main import create_app

from conftest import docv_headers, ops_headers


def test_health_needs_no_token(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_foreign_ip_denied(settings):
    settings = settings.model_copy(update={"allowlist": ["192.168.30.29"]})
    app = create_app(settings)
    with TestClient(app) as c:
        assert c.get("/health").status_code == 403


def test_missing_token_denied(client):
    assert client.post("/render/registry/inner", json={"request": [{}]}).status_code == 403


def test_wrong_scope_denied(client):
    # ops-токен не открывает render
    r = client.post("/render/registry/inner", json={"request": [{}]}, headers=ops_headers())
    assert r.status_code == 403


def test_ops_rate_limit(client):
    for _ in range(client.settings.ops_rate_limit_per_min):
        client.post("/ops/nonexistent", json={}, headers=ops_headers())
    r = client.post("/ops/nonexistent", json={}, headers=ops_headers())
    assert r.status_code == 429


def test_empty_request_rejected(client):
    r = client.post("/render/registry/inner", json={"request": []}, headers=docv_headers())
    assert r.status_code == 422
