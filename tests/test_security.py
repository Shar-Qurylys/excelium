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


def test_ui_allowlist_opens_ui_but_not_api(settings):
    """Машина из ui_allowlist видит /ui, /health и /files, но не API."""
    s = settings.model_copy(update={"allowlist": ["10.0.0.1"],
                                    "ui_allowlist": ["testclient"]})
    app = create_app(s)
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
        assert c.get("/ui/login").status_code == 200
        assert c.get("/files/" + "a" * 24).status_code == 404  # IP прошёл, токена нет
        r = c.post("/render/registry/inner", json={"request": [{}]},
                   headers=docv_headers())
        assert r.status_code == 403  # API из ui_allowlist закрыт


def test_api_allowlist_still_covers_ui(client):
    """Сервер Doc-V (allowlist) при желании тоже открывает /ui."""
    assert client.get("/ui/login").status_code == 200


def test_ip_denial_names_the_ip(settings):
    """Отрезанный по IP админ должен узнать причину из ответа."""
    s = settings.model_copy(update={"allowlist": ["10.0.0.1"], "ui_allowlist": []})
    app = create_app(s)
    with TestClient(app) as c:
        body = c.get("/ui").json()
        assert body["reason"] == "ip_not_allowed"
        assert body["client_ip"] == "testclient"
        assert "GW_UI_ALLOWLIST" in body["hint"]


def test_token_denial_stays_opaque(client):
    body = client.post("/render/registry/inner", json={"request": [{}]}).json()
    assert body == {"error": "forbidden"}  # причина только в audit


def test_allowlist_accepts_any_env_form(monkeypatch):
    """JSON, JSON без кавычек (systemd их снимает) и просто через запятую."""
    from gateway.config import Settings
    for raw, expected in (
        ('["192.168.26.0/23","172.16.0.0/12"]', ["192.168.26.0/23", "172.16.0.0/12"]),
        ("[192.168.26.0/23,172.16.0.0/12]", ["192.168.26.0/23", "172.16.0.0/12"]),
        ("172.16.0.0/12, 192.168.26.0/23", ["172.16.0.0/12", "192.168.26.0/23"]),
        ("", []),
    ):
        monkeypatch.setenv("GW_UI_ALLOWLIST", raw)
        assert Settings(_env_file=None).ui_allowlist == expected


def test_vpn_subnet_reaches_ui(settings):
    """Адрес из пула VPN (172.16.0.0/12) открывает интерфейс, но не API."""
    from gateway.security import _ip_allowed, _parse_allowlist
    allowed = _parse_allowlist(["192.168.26.0/23", "172.16.0.0/12"])
    assert _ip_allowed("172.16.10.1", allowed)
    assert _ip_allowed("172.31.255.254", allowed)
    assert not _ip_allowed("172.32.0.1", allowed)
    assert not _ip_allowed("10.0.0.1", allowed)
