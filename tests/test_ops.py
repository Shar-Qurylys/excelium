import textwrap

import pytest
from fastapi.testclient import TestClient

from gateway.main import create_app
from gateway.opsrunner.registry import OpsConfigError, load_registry

from conftest import docv_headers, ops_headers

TEST_OPS = textwrap.dedent("""
operations:
  echo:
    description: эхо
    argv: ["/bin/echo", "{text}"]
    params:
      text: {pattern: "^[-\\\\w\\\\s.,]{1,100}$"}
  slow:
    argv: ["{python}", "-c", "import time; time.sleep(30)"]
    timeout_sec: 1
  makefile:
    argv: ["{python}", "-c", "open('out.txt','w').write('готово')"]
    collect: "*.txt"
  pack:
    argv: ["{python}", "{app_dir}/scripts/zip_bundle.py", "{files...}"]
    params:
      files: {type: file_list, max_items: 3}
    collect: "*.zip"
""")


@pytest.fixture()
def ops_client(settings, tmp_path, monkeypatch):
    ops_file = tmp_path / "ops.yaml"
    ops_file.write_text(TEST_OPS, encoding="utf-8")
    app = create_app(settings)
    with TestClient(app) as c:
        c.app.state.ops = load_registry(ops_file)
        c.settings = settings
        yield c


def test_echo_ok(ops_client):
    r = ops_client.post("/ops/echo", json={"params": {"text": "привет мир"}},
                        headers=ops_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and body["exit_code"] == 0
    assert body["stdout"].strip() == "привет мир"


def test_unknown_op_404(ops_client):
    assert ops_client.post("/ops/rm_rf", json={}, headers=ops_headers()).status_code == 404


def test_injection_rejected(ops_client):
    r = ops_client.post("/ops/echo", json={"params": {"text": "x; rm -rf /"}},
                        headers=ops_headers())
    assert r.status_code == 422


def test_undeclared_param_rejected(ops_client):
    r = ops_client.post("/ops/echo", json={"params": {"text": "ok", "extra": "1"}},
                        headers=ops_headers())
    assert r.status_code == 422


def test_missing_param_rejected(ops_client):
    assert ops_client.post("/ops/echo", json={}, headers=ops_headers()).status_code == 422


def test_timeout(ops_client):
    r = ops_client.post("/ops/slow", json={}, headers=ops_headers())
    body = r.json()
    assert r.status_code == 200 and not body["ok"] and body["error"] == "timeout"


def test_collect_files(ops_client):
    r = ops_client.post("/ops/makefile", json={}, headers=ops_headers())
    body = r.json()
    assert body["ok"] and len(body["files"]) == 1
    token = body["files"][0]["download_url"].rsplit("/", 1)[1]
    assert ops_client.get(f"/files/{token}").content.decode() == "готово"


def test_file_list_param(ops_client):
    store = ops_client.app.state.filestore
    tokens = [store.save_bytes(b"a", ".txt", "устав.txt"),
              store.save_bytes(b"b", ".txt", "приказ.txt")]
    r = ops_client.post("/ops/pack", json={"params": {"files": tokens}},
                        headers=ops_headers())
    body = r.json()
    assert body["ok"], body
    assert body["files"] and body["files"][0]["name"] == "bundle.zip"
    r = ops_client.post("/ops/pack", json={"params": {"files": ["не-токен"]}},
                        headers=ops_headers())
    assert r.status_code == 422


def test_docv_token_has_no_ops_access(ops_client):
    r = ops_client.post("/ops/echo", json={"params": {"text": "x"}}, headers=docv_headers())
    assert r.status_code == 403


def test_bad_config_fails_fast(tmp_path):
    bad = tmp_path / "ops.yaml"
    bad.write_text('operations:\n  x:\n    argv: ["/bin/sh", "-c", "echo {cmd}"]\n'
                   '    params:\n      cmd: {pattern: ".*"}\n', encoding="utf-8")
    with pytest.raises(OpsConfigError):
        load_registry(bad)


def test_blank_to_png_from_pdf(client):
    """Реальная операция из ops.yaml: PDF-бланк -> фоновый PNG."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # A4
    page.draw_rect(pymupdf.Rect(0, 0, 595, 80), color=None, fill=(0, 0.6, 0.55))
    pdf_bytes = doc.tobytes()
    token = client.app.state.filestore.save_bytes(pdf_bytes, ".pdf", "бланк.pdf")
    r = client.post("/ops/blank_to_png", json={"params": {"file": token}},
                    headers=ops_headers())
    body = r.json()
    assert r.status_code == 200 and body["ok"], body
    assert body["files"] and body["files"][0]["name"] == "blank.png"
    png_token = body["files"][0]["download_url"].rsplit("/", 1)[1]
    png = client.get(f"/files/{png_token}").content
    assert png.startswith(b"\x89PNG")
