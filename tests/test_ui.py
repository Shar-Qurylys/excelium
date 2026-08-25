import io
import json
import textwrap
from pathlib import Path

from gateway.opsrunner.registry import load_registry

from conftest import TOKEN_ADMIN

MODEL = json.loads((Path(__file__).parent / "data" / "model.json").read_text(encoding="utf-8"))


def _login(client):
    r = client.post("/ui/login", data={"token": TOKEN_ADMIN}, follow_redirects=False)
    assert r.status_code == 302
    return client


def test_ui_requires_login(client):
    r = client.get("/ui", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/ui/login"
    assert client.post("/ui/jobs/ack/1", follow_redirects=False).status_code == 403


def test_wrong_token_stays_on_login(client):
    r = client.post("/ui/login", data={"token": "мимо"})
    assert r.status_code == 200 and "Неверный токен" in r.text
    assert client.get("/ui", follow_redirects=False).status_code == 302


def test_dashboard_after_login(client):
    _login(client)
    r = client.get("/ui")
    assert r.status_code == 200 and "Обзор" in r.text


def test_jobs_roundtrip(client):
    _login(client)
    r = client.post("/ui/jobs/new",
                    data={"type": "тест", "payload": '{"a": 1}'},
                    follow_redirects=True)
    assert "в очереди" in r.text and "тест" in r.text
    r = client.post("/ui/jobs/ack/1", follow_redirects=True)
    assert "подтверждено" in r.text
    assert client.app.state.jobs.stats() == {"acked": 1}


def test_jobs_bad_payload(client):
    _login(client)
    r = client.post("/ui/jobs/new", data={"type": "т", "payload": "не json"})
    assert "не JSON-объект" in r.text


def test_files_upload_and_delete(client):
    _login(client)
    r = client.post("/ui/files/upload",
                    files={"upload": ("устав.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf")},
                    follow_redirects=True)
    assert "устав.pdf" in r.text
    token = client.app.state.filestore.list_files()[0]["token"]
    r = client.post(f"/ui/files/delete/{token}", follow_redirects=True)
    assert "устав.pdf" not in r.text
    assert client.app.state.filestore.list_files() == []


def test_ops_run_via_ui(client, tmp_path):
    _login(client)
    ops_file = tmp_path / "ops.yaml"
    ops_file.write_text(textwrap.dedent("""
    operations:
      echo:
        argv: ["/bin/echo", "{text}"]
        params:
          text: {pattern: "^[-\\\\w\\\\s.,]{1,100}$"}
    """), encoding="utf-8")
    client.app.state.ops = load_registry(ops_file)
    r = client.get("/ui/ops")
    assert "echo" in r.text
    r = client.post("/ui/ops/echo", data={"text": "привет"})
    assert r.status_code == 200 and "привет" in r.text
    r = client.post("/ui/ops/echo", data={"text": "x; rm -rf /"})
    assert "Параметры не приняты" in r.text


def test_render_registry_via_ui(client):
    _login(client)
    r = client.post("/ui/render/registry",
                    data={"kind": "inner", "data": json.dumps(MODEL, ensure_ascii=False)},
                    follow_redirects=True)
    assert r.status_code == 200 and "скачать" in r.text
    files = client.app.state.filestore.list_files()
    assert files and files[0]["suffix"] == ".xlsx"


def test_render_bad_json_flash(client):
    _login(client)
    r = client.post("/ui/render/registry", data={"kind": "inner", "data": "мусор"})
    assert "Нужен JSON" in r.text
