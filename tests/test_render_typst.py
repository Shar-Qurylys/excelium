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
def test_compile_error_400(client, tmp_path):
    from gateway.routers import render
    bad = render.TYPST_DIR / "primer_bad_test.typ"
    bad.write_text("#let data = json(sys.inputs.data)\n#nosuchfunc()", encoding="utf-8")
    try:
        r = client.post("/render/typst/primer_bad_test", json=DATA, headers=docv_headers())
        assert r.status_code == 400
    finally:
        bad.unlink()
