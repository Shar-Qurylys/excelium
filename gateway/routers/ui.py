"""Веб-интерфейс администратора: /ui.

Server-rendered Jinja2 без внешних ресурсов. Вход — админ-токен
(GW_TOKEN_ADMIN), после входа кладётся в HttpOnly-cookie SameSite=Strict;
её проверяет security-middleware. Все страницы работают поверх тех же
внутренних объектов, что и API, — отдельной логики здесь нет.
"""
import json
import logging
import os
import shutil
from datetime import date

from fastapi import APIRouter, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import APP_DIR
from ..logging_setup import audit_log
from ..opsrunner.runner import OpsValidationError, run_operation
from ..renderers.registry_inner import render_inner
from ..renderers.registry_outer import render_outer
from ..renderers.registry_priority import render_priority
from ..renderers.typst_renderer import (TypstError, render_typst, typst_available,
                                        typst_binary)
from ..security import ADMIN_COOKIE, _match
from .render import _deliver, _sorted

log = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=APP_DIR / "gateway" / "webui")

AUDIT_TAIL = 50
SAMPLE = json.dumps({"request": [{
    "registry_name": "РЕЕСТР ПЛАТЕЖЕЙ №1", "organization": "ТОО «Шар-Кұрылыс»",
    "object_name": "Администрация", "counteragent": "ТОО «Пример»",
    "zatraty": "Прочее", "payment_sum": "100000.00", "payment_type": "Оплата",
    "payment_objective": "по счету", "doctype": "Заявка на оплату",
    "payment_number": 1, "status": "На исполнении",
}]}, ensure_ascii=False, indent=1)


def _page(request: Request, template: str, page: str, **ctx) -> HTMLResponse:
    return templates.TemplateResponse(
        request, template, {"page": page, **ctx})


# --- вход/выход -----------------------------------------------------------

@router.get("/ui/login")
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/ui/login")
def login(request: Request, token: str = Form(default="")):
    settings = request.app.state.settings
    if not settings.token_admin:
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "Интерфейс выключен: задайте GW_TOKEN_ADMIN в .env"})
    if not _match(token, settings.token_admin):
        audit_log("ui_login_failed", ip=request.client.host if request.client else "")
        return templates.TemplateResponse(
            request, "login.html", {"error": "Неверный токен"})
    response = RedirectResponse("/ui", status_code=302)
    response.set_cookie(ADMIN_COOKIE, token, httponly=True, samesite="strict",
                        max_age=12 * 3600)
    audit_log("ui_login", ip=request.client.host if request.client else "")
    return response


@router.get("/ui/logout")
def logout():
    response = RedirectResponse("/ui/login", status_code=302)
    response.delete_cookie(ADMIN_COOKIE)
    return response


# --- обзор ----------------------------------------------------------------

@router.get("/ui")
def dashboard(request: Request):
    state = request.app.state
    files = state.filestore.list_files()
    events = []
    audit_path = state.settings.var_dir / "audit.log"
    if audit_path.is_file():
        for line in audit_path.read_text(encoding="utf-8").splitlines()[-AUDIT_TAIL:][::-1]:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            details = {k: v for k, v in e.items()
                       if k not in ("ts", "level", "logger", "message")}
            events.append({"ts": e.get("ts", ""), "message": e.get("message", ""),
                           "details": json.dumps(details, ensure_ascii=False)})
    beats = []
    for kind, info in state.heartbeat.snapshot().items():
        age = info["age_sec"]
        if age is None:
            status, text = "none", "ещё не было"
        elif age < 120:
            status, text = "ok", f"{age} с назад"
        elif age < 3600:
            status, text = "warn", f"{age // 60} мин назад"
        else:
            status, text = "warn", f"{age // 3600} ч назад"
        beats.append({"kind": kind, "label": info["label"], "status": status,
                      "text": text, "seen_at": info["seen_at"] or ""})
    return _page(request, "dashboard.html", "dash", beats=beats,
                 directories=state.directory.info(),
                 typst=typst_available(), typst_path=typst_binary(),
                 libreoffice=shutil.which("libreoffice") is not None,
                 libreoffice_path=shutil.which("libreoffice"),
                 path_env=os.environ.get("PATH", ""),
                 files_count=len(files),
                 files_mb=round(sum(f["size"] for f in files) / 1024 / 1024, 1),
                 jobs=state.jobs.stats(), events=events)


# --- задания --------------------------------------------------------------

@router.get("/ui/jobs")
def jobs_page(request: Request, status: str = "", flash: str = ""):
    rows = request.app.state.jobs.list_jobs(status=status or None)
    return _page(request, "jobs.html", "jobs", rows=rows,
                 status_filter=status, flash=flash)


@router.post("/ui/jobs/ack/{job_id}")
def jobs_ack(request: Request, job_id: int):
    result = request.app.state.jobs.ack([job_id])
    audit_log("ui_job_ack", job_id=job_id, result=result)
    return RedirectResponse("/ui/jobs?flash=Задание подтверждено", status_code=302)


@router.post("/ui/jobs/new")
def jobs_new(request: Request, type: str = Form(...), payload: str = Form(...)):
    try:
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError
    except ValueError:
        rows = request.app.state.jobs.list_jobs()
        return _page(request, "jobs.html", "jobs", rows=rows, status_filter="",
                     flash="Payload — не JSON-объект", flash_err=True)
    job_id, _ = request.app.state.jobs.enqueue(
        producer="ui", job_type=type.strip() or "тест", payload=data,
        idempotency_key=None)
    audit_log("ui_job_enqueued", job_id=job_id)
    return RedirectResponse(f"/ui/jobs?flash=Задание {job_id} в очереди", status_code=302)


# --- файлы ----------------------------------------------------------------

@router.get("/ui/files")
def files_page(request: Request, flash: str = ""):
    rows = request.app.state.filestore.list_files()
    for f in rows:
        f["is_image"] = f["suffix"].lower() in IMAGE_SUFFIXES
    return _page(request, "files.html", "files", rows=rows,
                 ttl_hours=request.app.state.settings.file_ttl_hours, flash=flash)


@router.post("/ui/files/upload")
async def files_upload(request: Request, uploads: list[UploadFile]):
    count = 0
    for upload in uploads:
        data = await upload.read()
        if not data and not upload.filename:
            continue
        name = upload.filename or "file"
        suffix = "." + name.rsplit(".", 1)[1].lower() if "." in name else ".bin"
        try:
            request.app.state.filestore.save_bytes(data, suffix, name)
        except ValueError:
            request.app.state.filestore.save_bytes(data, ".bin", name)
        audit_log("ui_file_uploaded", name=name, size=len(data))
        count += 1
    word = "Файл загружен" if count == 1 else f"Загружено файлов: {count}"
    return RedirectResponse(f"/ui/files?flash={word}", status_code=302)


@router.post("/ui/files/rename/{token}")
def files_rename(request: Request, token: str, new_name: str = Form(...)):
    store = request.app.state.filestore
    resolved = store.resolve(token)
    if resolved is None:
        return RedirectResponse("/ui/files?flash=Файл не найден", status_code=302)
    path, _ = resolved
    name = new_name.strip()
    if name and not name.lower().endswith(path.suffix.lower()):
        name += path.suffix  # расширение не теряем
    if not store.rename(token, name):
        return RedirectResponse("/ui/files?flash=Не переименован", status_code=302)
    audit_log("ui_file_renamed", token=token, name=name)
    return RedirectResponse("/ui/files?flash=Переименовано", status_code=302)


@router.post("/ui/files/download_zip")
def files_download_zip(request: Request, tokens: list[str] = Form(default=[])):
    import io as _io
    import zipfile
    from datetime import date as _date
    from fastapi import Response
    store = request.app.state.filestore
    buf = _io.BytesIO()
    used, count = set(), 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for token in tokens[:200]:
            resolved = store.resolve(token)
            if resolved is None:
                continue
            path, orig_name = resolved
            arcname, n = orig_name, 1
            while arcname in used:
                stem, _, ext = orig_name.rpartition(".")
                arcname = f"{stem}_{n}.{ext}" if ext else f"{orig_name}_{n}"
                n += 1
            used.add(arcname)
            zf.write(path, arcname=arcname)
            count += 1
    if not count:
        return RedirectResponse("/ui/files?flash=Ничего не выбрано", status_code=302)
    audit_log("ui_files_zip", count=count)
    fname = f"files_{_date.today()}.zip"
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.post("/ui/files/delete/{token}")
def files_delete(request: Request, token: str):
    ok = request.app.state.filestore.delete(token)
    audit_log("ui_file_deleted", token=token, ok=ok)
    return RedirectResponse("/ui/files?flash=Файл удалён", status_code=302)


# --- операции -------------------------------------------------------------

@router.get("/ui/ops")
def ops_page(request: Request):
    return _page(request, "ops.html", "ops", ops=request.app.state.ops,
                 files=request.app.state.filestore.list_files(), result=None)


@router.post("/ui/ops/{name}")
async def ops_run(request: Request, name: str):
    state = request.app.state
    op = state.ops.get(name)
    if op is None:
        return RedirectResponse("/ui/ops", status_code=302)
    form = await request.form()
    params = {}
    for pname, pdef in op.params.items():
        if pdef.type == "file_list":
            values = [v for v in form.getlist(pname) if v]
            if values:
                params[pname] = values
        else:
            value = str(form.get(pname) or "").strip()
            if value:
                params[pname] = value
    try:
        ip = request.client.host if request.client else ""
        result = await run_in_threadpool(run_operation, op, params,
                                         state.filestore, client_ip=ip)
        flash, flash_err = "", False
    except OpsValidationError as exc:
        result, flash, flash_err = None, f"Параметры не приняты: {exc}", True
    return _page(request, "ops.html", "ops", ops=state.ops,
                 files=state.filestore.list_files(), result=result,
                 flash=flash, flash_err=flash_err)


# --- рендер ---------------------------------------------------------------

@router.get("/ui/render")
def render_page(request: Request, link: str = "", link_name: str = ""):
    return _page(request, "render.html", "render", sample=SAMPLE,
                 typst=typst_available(), typst_templates=_typst_templates(request),
                 link=link, link_name=link_name)


@router.post("/ui/render/registry")
def render_registry(request: Request, kind: str = Form(...), data: str = Form(...)):
    state = request.app.state
    try:
        entries = json.loads(data).get("request") or []
        assert entries
    except (ValueError, AttributeError, AssertionError):
        return _page(request, "render.html", "render", sample=data,
                     typst=typst_available(), typst_templates=_typst_templates(request),
                     flash="Нужен JSON вида {\"request\": [...]}", flash_err=True)
    try:
        if kind == "outer":
            workbook = render_outer(entries, state.template_outer, state.banks)
            name = f"vneshny_reestr_ot_{date.today()}.xlsx"
        elif kind == "priority":
            workbook = render_priority(_sorted(entries), state.template_priority)
            name = f"reestr_prioritetov_ot_{date.today()}.xlsx"
        else:
            workbook = render_inner(_sorted(entries), state.template_inner,
                                    state.approvers)
            name = f"reestr_ot_{date.today()}.xlsx"
    except Exception as exc:
        log.exception("ui render failed")
        return _page(request, "render.html", "render", sample=data,
                     typst=typst_available(), typst_templates=_typst_templates(request),
                     flash=f"Ошибка рендера: {exc}", flash_err=True)
    delivered = _deliver(request, workbook, name)
    return RedirectResponse(
        f"/ui/render?link={delivered['download_url']}&link_name={name}",
        status_code=302)


@router.post("/ui/render/typst")
def render_typst_ui(request: Request, template: str = Form(...), data: str = Form(...)):
    store = request.app.state.typst_store
    ctx = dict(sample=SAMPLE, typst=typst_available(),
               typst_templates=_typst_templates(request))
    try:
        parsed = json.loads(data)
    except ValueError:
        return _page(request, "render.html", "render",
                     flash="Данные — не JSON", flash_err=True, **ctx)
    source = store.get(template)
    if source is None:
        return _page(request, "render.html", "render",
                     flash="Нет такого шаблона", flash_err=True, **ctx)
    try:
        pdf = render_typst(template, source, parsed, store.assets_bytes(),
                           verify_secret=request.app.state.settings.verify_secret,
                           directory=request.app.state.directory.all())
    except TypstError as exc:
        return _page(request, "render.html", "render",
                     flash=f"Ошибка компиляции: {exc}", flash_err=True, **ctx)
    name = f"{template}_{date.today()}.pdf"
    token = request.app.state.filestore.save_bytes(pdf, ".pdf", name)
    url = request.app.state.filestore.download_url(token)
    return RedirectResponse(f"/ui/render?link={url}&link_name={name}", status_code=302)


def _typst_templates(request: Request) -> list[str]:
    return [t["name"] for t in request.app.state.typst_store.list_templates()]


# --- шаблоны Typst --------------------------------------------------------

NEW_TEMPLATE = '''// Новый шаблон. Данные приходят из POST-запроса:
#let data = if "data" in sys.inputs { json(sys.inputs.data) } else { (:) }
#let meta = if "meta" in sys.inputs { json(sys.inputs.meta) } else { (:) }

#set page(paper: "a4", margin: 2cm)
#set text(font: ("Liberation Sans", "Arial", "DejaVu Sans"), size: 11pt, lang: "ru")

= #data.at("title", default: "Документ")
'''

TEST_DATA_DEFAULT = '{"title": "Проба"}'


def _typst_edit_ctx(request: Request, name: str, **extra):
    from ..renderers.typst_store import HISTORY_KEEP
    store = request.app.state.typst_store
    ctx = dict(name=name, source=store.get(name) or "",
               history=store.history(name), history_keep=HISTORY_KEEP,
               typst=typst_available(), assets=store.list_assets(),
               test_data=extra.pop("test_data", TEST_DATA_DEFAULT))
    ctx.update(extra)
    return ctx


@router.get("/ui/typst")
def typst_list(request: Request, flash: str = ""):
    store = request.app.state.typst_store
    return _page(request, "typst_list.html", "typst",
                 rows=store.list_templates(), assets=store.list_assets(), flash=flash)


@router.post("/ui/typst/create")
def typst_create(request: Request, name: str = Form(...)):
    store = request.app.state.typst_store
    name = name.strip()
    try:
        if store.get(name) is None:
            store.save(name, NEW_TEMPLATE)
    except ValueError as exc:
        return _page(request, "typst_list.html", "typst",
                     rows=store.list_templates(), assets=store.list_assets(),
                     flash=str(exc), flash_err=True)
    return RedirectResponse(f"/ui/typst/{name}", status_code=302)


@router.post("/ui/typst/assets/upload")
async def typst_asset_upload(request: Request, uploads: list[UploadFile]):
    store = request.app.state.typst_store
    count = 0
    for upload in uploads:
        if not upload.filename:
            continue
        try:
            store.save_asset(upload.filename.strip(), await upload.read())
        except ValueError as exc:
            return RedirectResponse(f"/ui/typst?flash={upload.filename}: {exc}",
                                    status_code=302)
        audit_log("typst_asset_uploaded", name=upload.filename)
        count += 1
    word = "Картинка загружена" if count == 1 else f"Загружено картинок: {count}"
    return RedirectResponse(f"/ui/typst?flash={word}", status_code=302)


@router.post("/ui/typst/assets/delete/{name}")
def typst_asset_delete(request: Request, name: str):
    request.app.state.typst_store.delete_asset(name)
    audit_log("typst_asset_deleted", name=name)
    return RedirectResponse("/ui/typst?flash=Картинка удалена", status_code=302)


@router.get("/ui/typst/{name}")
def typst_edit(request: Request, name: str, link: str = ""):
    if request.app.state.typst_store.get(name) is None:
        return RedirectResponse("/ui/typst", status_code=302)
    return _page(request, "typst_edit.html", "typst",
                 **_typst_edit_ctx(request, name, link=link))


@router.post("/ui/typst/{name}/save")
def typst_save(request: Request, name: str, source: str = Form(...)):
    store = request.app.state.typst_store
    try:
        store.save(name, source)
    except ValueError as exc:
        return _page(request, "typst_edit.html", "typst",
                     **_typst_edit_ctx(request, name), flash=str(exc), flash_err=True)
    audit_log("typst_template_saved", name=name, size=len(source))
    return _page(request, "typst_edit.html", "typst",
                 **_typst_edit_ctx(request, name), flash="Сохранено")


@router.post("/ui/typst/{name}/test")
def typst_test(request: Request, name: str, data: str = Form(...)):
    store = request.app.state.typst_store
    source = store.get(name)
    if source is None:
        return RedirectResponse("/ui/typst", status_code=302)
    try:
        parsed = json.loads(data)
    except ValueError:
        return _page(request, "typst_edit.html", "typst",
                     **_typst_edit_ctx(request, name, test_data=data),
                     flash="Данные — не JSON", flash_err=True)
    try:
        pdf = render_typst(name, source, parsed, store.assets_bytes(),
                           verify_secret=request.app.state.settings.verify_secret,
                           directory=request.app.state.directory.all())
    except TypstError as exc:
        return _page(request, "typst_edit.html", "typst",
                     **_typst_edit_ctx(request, name, test_data=data, error=str(exc)))
    fname = f"{name}_{date.today()}.pdf"
    token = request.app.state.filestore.save_bytes(pdf, ".pdf", fname)
    url = request.app.state.filestore.download_url(token)
    return RedirectResponse(f"/ui/typst/{name}?link={url}", status_code=302)


@router.post("/ui/typst/{name}/restore/{history_id}")
def typst_restore(request: Request, name: str, history_id: int):
    request.app.state.typst_store.restore(name, history_id)
    audit_log("typst_template_restored", name=name, history_id=history_id)
    return RedirectResponse(f"/ui/typst/{name}", status_code=302)


@router.post("/ui/typst/{name}/delete")
def typst_delete(request: Request, name: str):
    request.app.state.typst_store.delete(name)
    audit_log("typst_template_deleted", name=name)
    return RedirectResponse("/ui/typst?flash=Шаблон удалён", status_code=302)


# --- картинки: отдача и перенос из «Файлов» -------------------------------

ASSET_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".gif": "image/gif", ".svg": "image/svg+xml"}
IMAGE_SUFFIXES = set(ASSET_MEDIA)


@router.get("/ui/typst/assets/raw/{name}")
def typst_asset_raw(request: Request, name: str):
    from fastapi import Response
    data = request.app.state.typst_store.assets_bytes().get(name)
    if data is None:
        return Response(status_code=404)
    suffix = "." + name.rsplit(".", 1)[-1].lower()
    return Response(content=data, media_type=ASSET_MEDIA.get(suffix, "application/octet-stream"),
                    headers={"Cache-Control": "private, max-age=300"})


def _asset_name(orig_name: str) -> str:
    """Имя файла -> допустимое имя картинки: транслитерация кириллицы,
    пробелы и прочее -> подчёркивание."""
    import re as _re
    stem, _, ext = orig_name.rpartition(".")
    try:
        from transliterate import translit
        stem = translit(stem, "ru", reversed=True)
    except Exception:
        pass
    stem = _re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or "img"
    return f"{stem[:60]}.{ext.lower()}"


@router.post("/ui/files/to_assets/{token}")
def file_to_assets(request: Request, token: str):
    """Файл-изображение из «Файлов» -> «Картинки» (доступно шаблонам)."""
    resolved = request.app.state.filestore.resolve(token)
    if resolved is None:
        return RedirectResponse("/ui/files?flash=Файл не найден", status_code=302)
    path, orig_name = resolved
    name = _asset_name(orig_name)
    try:
        request.app.state.typst_store.save_asset(name, path.read_bytes())
    except ValueError as exc:
        return RedirectResponse(f"/ui/files?flash=Не перенесён: {exc}", status_code=302)
    audit_log("file_to_assets", token=token, name=name)
    return RedirectResponse(f"/ui/typst?flash=Картинка доступна шаблонам: assets/{name}",
                            status_code=302)
