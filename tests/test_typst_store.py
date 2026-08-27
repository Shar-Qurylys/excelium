import pytest

from gateway.renderers.typst_store import HISTORY_KEEP, TypstStore


@pytest.fixture()
def store(settings):
    from gateway.jobsqueue.db import init_db
    init_db(settings.db_path)
    return TypstStore(settings.db_path)


def test_save_get_delete(store):
    store.save("akt", "= Акт")
    assert store.get("akt") == "= Акт"
    assert [t["name"] for t in store.list_templates()] == ["akt"]
    assert store.delete("akt") and store.get("akt") is None


def test_bad_name_rejected(store):
    for bad in ("С кириллицей", "a/b", "..", "A" * 65):
        with pytest.raises(ValueError):
            store.save(bad, "x")


def test_history_and_restore(store):
    store.save("t", "версия 1")
    store.save("t", "версия 2")
    store.save("t", "версия 2")  # без изменений — истории не прибавляет
    history = store.history("t")
    assert len(history) == 1
    assert store.restore("t", history[0]["id"])
    assert store.get("t") == "версия 1"
    # откат сам ушёл в историю
    assert len(store.history("t")) == 2


def test_history_keep_limit(store):
    for i in range(HISTORY_KEEP + 5):
        store.save("t", f"v{i}")
    assert len(store.history("t")) == HISTORY_KEEP


def test_seed_only_missing(store, tmp_path):
    d = tmp_path / "typ"
    d.mkdir()
    (d / "one.typ").write_text("= 1", encoding="utf-8")
    (d / "two.typ").write_text("= 2", encoding="utf-8")
    store.save("one", "правленый")
    assert store.seed_from_dir(d) == 1
    assert store.get("one") == "правленый"  # правку из базы файл не затирает
    assert store.get("two") == "= 2"


def test_assets(store):
    store.save_asset("logo.png", b"\x89PNG data")
    assert store.assets_bytes() == {"logo.png": b"\x89PNG data"}
    with pytest.raises(ValueError):
        store.save_asset("логотип.png", b"x")
    with pytest.raises(ValueError):
        store.save_asset("hack.sh", b"x")
    with pytest.raises(ValueError):
        store.save_asset("big.png", b"x" * (5 * 1024 * 1024 + 1))
    assert store.delete_asset("logo.png")
