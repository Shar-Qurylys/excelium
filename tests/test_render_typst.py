import pytest

from gateway.renderers.typst_renderer import typst_available

from conftest import docv_headers

DATA = {"title": "Справка №1", "fields": {"Контрагент": "ТОО «Тест»", "Сумма": "1 000 тг"}}


def test_unknown_template_404(client):
    r = client.post("/render/typst/net_takogo", json=DATA, headers=docv_headers())
    assert r.status_code == 404
    r = client.post("/render/typst/..%2Fetc", json=DATA, headers=docv_headers())
    assert r.status_code == 404


@pytest.mark.skipif(not typst_available(), reason="нет бинаря typst")
def test_render_pdf(client):
    r = client.post("/render/typst/primer", json=DATA, headers=docv_headers())
    assert r.status_code == 200, r.text
    token = r.json()["download_url"].rsplit("/", 1)[1]
    pdf = client.get(f"/files/{token}").content
    assert pdf.startswith(b"%PDF")


@pytest.mark.skipif(not typst_available(), reason="нет бинаря typst")
def test_compile_error_400(client):
    client.app.state.typst_store.save(
        "primer_bad_test", "#let data = json(sys.inputs.data)\n#nosuchfunc()")
    r = client.post("/render/typst/primer_bad_test", json=DATA, headers=docv_headers())
    assert r.status_code == 400


@pytest.mark.skipif(not typst_available(), reason="нет бинаря typst")
def test_render_with_asset(client):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buf, format="PNG")
    store = client.app.state.typst_store
    store.save_asset("dot.png", buf.getvalue())
    store.save("with_logo",
               '#let data = json(sys.inputs.data)\n#image("assets/dot.png")\n= Ок')
    r = client.post("/render/typst/with_logo", json={}, headers=docv_headers())
    assert r.status_code == 200, r.text
    token = r.json()["download_url"].rsplit("/", 1)[1]
    assert client.get(f"/files/{token}").content.startswith(b"%PDF")


def test_verify_code_deterministic():
    from gateway.renderers.typst_renderer import verify_code
    a = verify_code({"x": 1, "y": "а"}, "s")
    assert a == verify_code({"y": "а", "x": 1}, "s")  # порядок ключей не влияет
    assert a != verify_code({"x": 2, "y": "а"}, "s")
    assert a != verify_code({"x": 1, "y": "а"}, "другой-секрет")
    assert len(a) == 14 and a.count("-") == 2
    assert verify_code({"x": 1}, "") == ""


@pytest.mark.skipif(not typst_available(), reason="нет бинаря typst")
def test_meta_and_qr_available_in_template(client):
    store = client.app.state.typst_store
    store.save("verify_probe",
               '#let meta = json(sys.inputs.meta)\n'
               '#let data = json(sys.inputs.data)\n'
               '#meta.verify_code #meta.generated_at\n'
               '#if data.at("qr", default: "") != "" { image("qr.png", width: 2cm) }')
    r = client.post("/render/typst/verify_probe",
                    json={"qr": "http://192.168.30.29/doc/1"}, headers=docv_headers())
    assert r.status_code == 200, r.text
    token = r.json()["download_url"].rsplit("/", 1)[1]
    assert client.get(f"/files/{token}").content.startswith(b"%PDF")


@pytest.mark.skipif(not typst_available(), reason="нет бинаря typst")
def test_list_soglasovaniya_full(client):
    r = client.post("/render/typst/list_soglasovaniya", json={
        "org": {"name": "ТОО «Шар-Кұрылыс»", "bin": "000940001102"},
        "document_number": "12", "document_date": "01.08.2026",
        "subject": "СМР", "counteragent": "ТОО «Подрядчик»",
        "sum": "1 000 000", "currency": "KZT", "vat": "с НДС",
        "rows": [{"position": "Гл. бухгалтер", "fio": "Абдрахманова Х.М.",
                  "decision": "Согласовано", "date": "25.08.2026"}],
        "lawyer": "Бекмуратов Е.И.",
        "qr": "http://192.168.30.29/documents/view/1",
    }, headers=docv_headers())
    assert r.status_code == 200, r.text


@pytest.mark.skipif(not typst_available(), reason="нет бинаря typst")
def test_list_soglasovaniya_minimal(client):
    # почти пустые данные не должны ронять компиляцию
    r = client.post("/render/typst/list_soglasovaniya", json={"rows": []},
                    headers=docv_headers())
    assert r.status_code == 200, r.text


@pytest.mark.skipif(not typst_available(), reason="нет бинаря typst")
def test_list_soglasovaniya_on_blank(client):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (827, 1169), "white").save(buf, format="PNG")
    client.app.state.typst_store.save_asset("blank_test.png", buf.getvalue())
    r = client.post("/render/typst/list_soglasovaniya", json={
        "org": {"name": "ТОО «Тест»", "blank": "blank_test.png", "top_margin": 5},
        "document_number": "1", "rows": [],
    }, headers=docv_headers())
    assert r.status_code == 200, r.text


def test_directory_upload_and_stats(client):
    r = client.post("/directory/structura", headers=docv_headers(), json={"items": [
        {"uid": "aaa-1", "name": "Абдрахманова Х.М.", "position": "Главный бухгалтер"},
        {"uid": "bbb-2", "name": "Бекмуратов Е.И."},
        {"без-uid": True},
    ]})
    assert r.status_code == 200 and r.json() == {"directory": "structura", "items": 2}
    assert client.get("/directory", headers=docv_headers()).json() == {"structura": 2}
    # полная замена
    client.post("/directory/structura", headers=docv_headers(),
                json=[{"uid": "ccc-3", "name": "Новый"}])
    assert client.get("/directory", headers=docv_headers()).json() == {"structura": 1}
    assert client.post("/directory/КИРИЛЛИЦА", headers=docv_headers(),
                       json=[]).status_code == 422


@pytest.mark.skipif(not typst_available(), reason="нет бинаря typst")
def test_approved_by_resolved_via_directory(client):
    client.post("/directory/structura", headers=docv_headers(),
                json=[{"uid": "p-1", "name": "Абдрахманова Х.М."}])
    client.post("/directory/dolzhnosti", headers=docv_headers(),
                json=[{"uid": "d-1", "name": "Главный бухгалтер"}])
    r = client.post("/render/typst/list_soglasovaniya", json={
        "document_number": "1",
        "approved_by": [[["1", "1", "p-1", "d-1", "2026-08-20T14:48:47+05:00", "", "1"]]],
    }, headers=docv_headers())
    assert r.status_code == 200, r.text


def test_directory_sweep_stale(client):
    from datetime import datetime, timedelta, timezone
    from gateway.jobsqueue.db import connect
    store = client.app.state.directory
    store.replace("structura", [{"uid": "x", "name": "Тест"}])
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat(timespec="seconds")
    with connect(client.settings.db_path) as conn:
        conn.execute("UPDATE directories SET updated_at = ?", (old,))
    assert store.sweep() == 1
    assert store.stats() == {}


def test_db_file_permissions(client):
    assert oct(client.settings.db_path.stat().st_mode & 0o777) == "0o600"


def test_directory_display_name_normalized(client):
    client.post("/directory/structura", headers=docv_headers(), json=[
        {"uid": "u1", "display_name": "Абдрахманова Х.М.",
         "position": "Главный бухгалтер", "department": "Бухгалтерия"}])
    entry = client.app.state.directory.all()["structura"]["u1"]
    assert entry["name"] == "Абдрахманова Х.М."
    assert entry["position"] == "Главный бухгалтер"
    assert entry["department"] == "Бухгалтерия"


@pytest.mark.skipif(not typst_available(), reason="нет бинаря typst")
def test_approved_by_position_from_structura_entry(client):
    """Должность берётся из записи сотрудника — справочник должностей не нужен."""
    client.post("/directory/structura", headers=docv_headers(), json=[
        {"uid": "p-9", "display_name": "Омарова Г.А.", "position": "Финансовый директор",
         "department": "Финансы"}])
    r = client.post("/render/typst/list_soglasovaniya", json={
        "document_number": "1",
        "approved_by": [[["1", "1", "p-9", "d-неизвестен-uid-длинный", "2026-08-20T14:48:47+05:00", "", "1"]]],
    }, headers=docv_headers())
    assert r.status_code == 200, r.text
