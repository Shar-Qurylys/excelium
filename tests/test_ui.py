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
                    files={"uploads": ("устав.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf")},
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


def test_typst_pages_and_editing(client):
    _login(client)
    r = client.get("/ui/typst")
    assert r.status_code == 200 and "primer" in r.text  # засеян из templates/typst/
    r = client.post("/ui/typst/create", data={"name": "akt_sverki"}, follow_redirects=True)
    assert "akt_sverki" in r.text
    r = client.post("/ui/typst/akt_sverki/save", data={"source": "= Акт сверки v2"})
    assert "Сохранено" in r.text
    client.post("/ui/typst/akt_sverki/save", data={"source": "= Акт сверки v3"})
    hist = client.app.state.typst_store.history("akt_sverki")
    assert len(hist) == 2
    client.post(f"/ui/typst/akt_sverki/restore/{hist[0]['id']}")
    assert client.app.state.typst_store.get("akt_sverki") == "= Акт сверки v2"
    r = client.post("/ui/typst/akt_sverki/delete", follow_redirects=True)
    assert "akt_sverki" not in r.text


def test_typst_asset_upload_delete(client):
    _login(client)
    r = client.post("/ui/typst/assets/upload",
                    files={"uploads": ("logo.png", io.BytesIO(b"\x89PNG"), "image/png")},
                    follow_redirects=True)
    assert "assets/logo.png" in r.text
    r = client.post("/ui/typst/assets/upload",
                    files={"uploads": ("hack.sh", io.BytesIO(b"#!"), "text/plain")},
                    follow_redirects=True)
    assert "расширение" in r.text
    client.post("/ui/typst/assets/delete/logo.png")
    assert client.app.state.typst_store.list_assets() == []


def test_dashboard_heartbeat_card(client):
    _login(client)
    r = client.get("/ui")
    assert "Связь с Doc-V" in r.text and "ещё не было" in r.text
    client.get("/jobs/pending", headers={"Authorization": "Bearer test-docv-token"})
    r = client.get("/ui")
    assert "с назад" in r.text


def test_asset_raw_and_thumbnails(client):
    _login(client)
    client.app.state.typst_store.save_asset("logo.png", b"\x89PNG-data")
    r = client.get("/ui/typst/assets/raw/logo.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert client.get("/ui/typst/assets/raw/net.png").status_code == 404
    r = client.get("/ui/typst")
    assert "/ui/typst/assets/raw/logo.png" in r.text  # миниатюра в списке
    r = client.get("/ui/typst/primer")
    assert '#image(&#34;assets/logo.png&#34;)' in r.text or 'assets/logo.png' in r.text


def test_file_to_assets_one_click(client):
    _login(client)
    store = client.app.state.filestore
    token = store.save_bytes(b"\x89PNG-blank", ".png", "blank_shar.png")
    r = client.get("/ui/files")
    assert f"/ui/files/to_assets/{token}" in r.text  # кнопка есть у картинки
    r = client.post(f"/ui/files/to_assets/{token}", follow_redirects=True)
    assert "доступна шаблонам" in r.text
    assert client.app.state.typst_store.assets_bytes()["blank_shar.png"] == b"\x89PNG-blank"
    # не-картинка кнопки не имеет
    t2 = store.save_bytes(b"x", ".xlsx", "реестр.xlsx")
    assert f"/ui/files/to_assets/{t2}" not in client.get("/ui/files").text


def test_file_to_assets_translit_name(client):
    _login(client)
    token = client.app.state.filestore.save_bytes(b"\x89PNG", ".png", "логотип шар.png")
    r = client.post(f"/ui/files/to_assets/{token}", follow_redirects=True)
    assert "assets/logotip_shar.png" in r.text  # кириллица транслитерирована
    assert "logotip_shar.png" in client.app.state.typst_store.assets_bytes()


def test_files_multi_upload(client):
    _login(client)
    r = client.post("/ui/files/upload", files=[
        ("uploads", ("а.txt", io.BytesIO(b"1"), "text/plain")),
        ("uploads", ("б.txt", io.BytesIO(b"2"), "text/plain")),
    ], follow_redirects=True)
    assert "Загружено файлов: 2" in r.text
    assert len(client.app.state.filestore.list_files()) == 2


def test_files_rename_keeps_extension(client):
    _login(client)
    token = client.app.state.filestore.save_bytes(b"x", ".xlsx", "реестр.xlsx")
    r = client.post(f"/ui/files/rename/{token}", data={"new_name": "реестр август"},
                    follow_redirects=True)
    assert "Переименовано" in r.text
    _, name = client.app.state.filestore.resolve(token)
    assert name == "реестр август.xlsx"


def test_files_download_zip(client):
    import zipfile
    _login(client)
    store = client.app.state.filestore
    t1 = store.save_bytes("один".encode(), ".txt", "документ.txt")
    t2 = store.save_bytes("два".encode(), ".txt", "документ.txt")  # дубль имени
    r = client.post("/ui/files/download_zip", data={"tokens": [t1, t2]})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert sorted(zf.namelist()) == ["документ.txt", "документ_1.txt"]
    assert zf.read("документ.txt") == "один".encode()
    # пустой выбор — просто возврат на страницу
    r = client.post("/ui/files/download_zip", data={}, follow_redirects=True)
    assert "Ничего не выбрано" in r.text
