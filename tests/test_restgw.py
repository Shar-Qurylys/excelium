"""Забор справочников из restgw. Сеть подменяется: _http_get отдаёт
заготовленные ответы, в restgw тесты не ходят."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from gateway import restgw
from gateway.main import create_app

from conftest import TOKEN_ADMIN, docv_headers

KEY = "secret-restgw-key-1234567890"
STAFF = [
    {"uid": "u1", "display_name": "Абдрахманова Х.М.", "position": "Гл. бухгалтер",
     "department": "Бухгалтерия", "department_uid": "d1"},
    {"uid": "u2", "display_name": "Иванов И.И.", "position": "Директор",
     "department": "Дирекция", "department_uid": "d2"},
]
POSITIONS = [{"uid": "p1", "name": "Директор", "deleted": "0"}]
DEPARTMENTS = [{"uid": "d1", "name": "Бухгалтерия", "deleted": "0", "parent_uid": ""}]


class FakeRestgw:
    """Подмена restgw: name -> (код, тело) либо исключение."""

    def __init__(self):
        self.answers = {}
        self.calls = []

    def ok(self, name, items, updated_at="2026-11-25T13:57:53+05:00"):
        self.answers[name] = (200, json.dumps(
            {"name": name, "updated_at": updated_at, "count": len(items),
             "items": items}, ensure_ascii=False).encode())

    def __call__(self, url, key, timeout):
        self.calls.append((url, key, timeout))
        name = url.rsplit("/", 1)[-1]
        answer = self.answers.get(name, (404, b'{"error": "dataset not found"}'))
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture()
def fake(monkeypatch):
    f = FakeRestgw()
    monkeypatch.setattr(restgw, "_http_get", f)
    return f


@pytest.fixture()
def rg_client(settings, fake):
    """Клиент с настроенным restgw; при старте restgw отвечает 404 на всё,
    чтобы стартовый забор ничего не положил."""
    s = settings.model_copy(update={"restgw_url": "http://192.168.30.29:8080/",
                                    "restgw_key": KEY})
    with TestClient(create_app(s)) as c:
        _wait_startup(c)
        fake.calls.clear()
        yield c


def _wait_startup(client, timeout=5):
    task = client.app.state.directory_startup
    deadline = time.monotonic() + timeout
    while not task.done() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert task.done()


def _audit(client) -> str:
    path = client.app.state.settings.var_dir / "audit.log"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def test_refresh_success(rg_client, fake):
    fake.ok("structura", STAFF)
    r = rg_client.post("/directory/structura/refresh", headers=docv_headers())
    assert r.status_code == 200
    assert r.json() == {"directory": "structura", "items": 2,
                        "updated_at": "2026-11-25T13:57:53+05:00"}
    url, key, timeout = fake.calls[0]
    assert url == "http://192.168.30.29:8080/v1/data/structura"
    assert key == KEY and timeout == 30
    entry = rg_client.app.state.directory.all()["structura"]["u1"]
    # формат тот же, что и у приёма POST /directory/structura
    assert entry["name"] == "Абдрахманова Х.М." and entry["department_uid"] == "d1"
    assert "directory_refreshed" in _audit(rg_client)
    assert KEY not in _audit(rg_client)


@pytest.mark.parametrize("status,body,needle", [
    (404, b'{"error": "dataset not found"}', "нет набора"),
    (502, b'{"error": "docv timeout"}', "Doc-V не ответил"),
    (401, b'{"error": "unknown key"}', "GW_RESTGW_KEY"),
])
def test_refresh_error_keeps_directory(rg_client, fake, status, body, needle):
    rg_client.app.state.directory.replace("structura", STAFF)
    fake.answers["structura"] = (status, body)
    r = rg_client.post("/directory/structura/refresh", headers=docv_headers())
    assert r.status_code == 502
    assert needle in r.json()["error"] and r.json()["directory"] == "structura"
    assert rg_client.app.state.directory.stats() == {"structura": 2}
    log = _audit(rg_client)
    assert "directory_refresh_failed" in log and needle in log
    assert KEY not in log


def test_refresh_502_detail_passed_through(rg_client, fake):
    fake.answers["positions"] = (502, b'{"error": "dataset not built yet"}')
    r = rg_client.post("/directory/positions/refresh", headers=docv_headers())
    assert "dataset not built yet" in r.json()["error"]


def test_refresh_unreachable(rg_client, fake):
    import urllib.error
    rg_client.app.state.directory.replace("structura", STAFF)
    fake.answers["structura"] = urllib.error.URLError(ConnectionRefusedError(61, "refused"))
    r = rg_client.post("/directory/structura/refresh", headers=docv_headers())
    assert r.status_code == 502 and "restgw недоступен" in r.json()["error"]
    assert rg_client.app.state.directory.stats() == {"structura": 2}
    assert "directory_refresh_failed" in _audit(rg_client)


def test_refresh_timeout(rg_client, fake):
    fake.answers["structura"] = TimeoutError("timed out")
    r = rg_client.post("/directory/structura/refresh", headers=docv_headers())
    assert r.status_code == 502 and "недоступен" in r.json()["error"]


def test_empty_items_do_not_wipe(rg_client, fake):
    rg_client.app.state.directory.replace("structura", STAFF)
    fake.ok("structura", [])
    r = rg_client.post("/directory/structura/refresh", headers=docv_headers())
    assert r.status_code == 502 and "пустой набор" in r.json()["error"]
    assert rg_client.app.state.directory.stats() == {"structura": 2}
    # записи без uid — тоже «пусто»
    fake.ok("structura", [{"display_name": "без uid"}])
    assert rg_client.post("/directory/structura/refresh",
                          headers=docv_headers()).status_code == 502
    assert rg_client.app.state.directory.stats() == {"structura": 2}


def test_empty_items_into_empty_directory_ok(rg_client, fake):
    fake.ok("departments", [])
    r = rg_client.post("/directory/departments/refresh", headers=docv_headers())
    assert r.status_code == 200 and r.json()["items"] == 0


def test_bad_json_keeps_directory(rg_client, fake):
    rg_client.app.state.directory.replace("structura", STAFF)
    fake.answers["structura"] = (200, b"<html>oops</html>")
    r = rg_client.post("/directory/structura/refresh", headers=docv_headers())
    assert r.status_code == 502 and "не JSON" in r.json()["error"]
    assert rg_client.app.state.directory.stats() == {"structura": 2}


def test_refresh_requires_docv_token(rg_client, fake):
    fake.ok("structura", STAFF)
    assert rg_client.post("/directory/structura/refresh").status_code == 403
    assert rg_client.post("/directory/structura/refresh",
                          headers={"Authorization": "Bearer wrong-token"}).status_code == 403
    assert fake.calls == []
    assert rg_client.app.state.directory.stats() == {}


def test_refresh_bad_name(rg_client, fake):
    r = rg_client.post("/directory/КИРИЛЛИЦА/refresh", headers=docv_headers())
    assert r.status_code == 422 and fake.calls == []


def test_refresh_not_configured(client, fake):
    r = client.post("/directory/structura/refresh", headers=docv_headers())
    assert r.status_code == 503 and "GW_RESTGW_URL" in r.json()["error"]
    assert fake.calls == []


def test_startup_fetches_all_datasets(settings, fake):
    fake.ok("structura", STAFF)
    fake.ok("positions", POSITIONS)
    fake.ok("departments", DEPARTMENTS)
    s = settings.model_copy(update={"restgw_url": "http://rg", "restgw_key": KEY})
    with TestClient(create_app(s)) as c:
        _wait_startup(c)
        assert c.app.state.directory_startup.result() == {
            "structura": "ok", "positions": "ok", "departments": "ok"}
        assert c.app.state.directory.stats() == {
            "structura": 2, "positions": 1, "departments": 1}
        assert c.app.state.directory.all()["positions"]["p1"]["deleted"] == "0"


def test_startup_failure_does_not_block(settings, fake):
    """Один набор недоступен — остальные всё равно забираются, сервис живёт."""
    fake.ok("structura", STAFF)
    fake.answers["positions"] = OSError("no route to host")
    s = settings.model_copy(update={"restgw_url": "http://rg", "restgw_key": KEY})
    with TestClient(create_app(s)) as c:
        _wait_startup(c)
        result = c.app.state.directory_startup.result()
        assert result["structura"] == "ok" and "недоступен" in result["positions"]
        assert c.get("/health").json() == {"status": "ok"}


def test_legacy_post_still_works(rg_client):
    r = rg_client.post("/directory/structura", headers=docv_headers(), json=STAFF)
    assert r.status_code == 200 and r.json() == {"directory": "structura", "items": 2}


def test_ui_refresh_button(rg_client, fake):
    rg_client.post("/ui/login", data={"token": TOKEN_ADMIN})
    fake.ok("structura", STAFF)
    r = rg_client.post("/ui/directory/structura/refresh", follow_redirects=True)
    assert "обновлён из Doc-V: 2 записей" in r.text
    fake.answers["structura"] = (502, b'{"error": "x"}')
    r = rg_client.post("/ui/directory/structura/refresh", follow_redirects=True)
    assert "не обновлён" in r.text and "Doc-V не ответил" in r.text
    assert rg_client.app.state.directory.stats() == {"structura": 2}
    assert "Обновить из Doc-V" in rg_client.get("/ui").text
