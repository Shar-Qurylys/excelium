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
