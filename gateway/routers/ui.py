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
from .render import TYPST_DIR, _deliver, _sorted

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
    return _page(request, "dashboard.html", "dash",
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
    return _page(request, "files.html", "files",
                 rows=request.app.state.filestore.list_files(),
                 ttl_hours=request.app.state.settings.file_ttl_hours, flash=flash)


@router.post("/ui/files/upload")
async def files_upload(request: Request, upload: UploadFile):
    data = await upload.read()
    name = upload.filename or "file"
    suffix = "." + name.rsplit(".", 1)[1].lower() if "." in name else ".bin"
    try:
        request.app.state.filestore.save_bytes(data, suffix, name)
    except ValueError:
        request.app.state.filestore.save_bytes(data, ".bin", name)
    audit_log("ui_file_uploaded", name=name, size=len(data))
    return RedirectResponse("/ui/files?flash=Файл загружен", status_code=302)


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
                 typst=typst_available(), typst_templates=_typst_templates(),
                 link=link, link_name=link_name)


@router.post("/ui/render/registry")
def render_registry(request: Request, kind: str = Form(...), data: str = Form(...)):
    state = request.app.state
    try:
        entries = json.loads(data).get("request") or []
        assert entries
    except (ValueError, AttributeError, AssertionError):
        return _page(request, "render.html", "render", sample=data,
                     typst=typst_available(), typst_templates=_typst_templates(),
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
                     typst=typst_available(), typst_templates=_typst_templates(),
                     flash=f"Ошибка рендера: {exc}", flash_err=True)
    delivered = _deliver(request, workbook, name)
    return RedirectResponse(
        f"/ui/render?link={delivered['download_url']}&link_name={name}",
        status_code=302)


@router.post("/ui/render/typst")
def render_typst_ui(request: Request, template: str = Form(...), data: str = Form(...)):
    ctx = dict(sample=SAMPLE, typst=typst_available(),
               typst_templates=_typst_templates())
    try:
        parsed = json.loads(data)
    except ValueError:
        return _page(request, "render.html", "render",
                     flash="Данные — не JSON", flash_err=True, **ctx)
    path = TYPST_DIR / f"{template}.typ"
    if "/" in template or not path.is_file():
        return _page(request, "render.html", "render",
                     flash="Нет такого шаблона", flash_err=True, **ctx)
    try:
        pdf = render_typst(path, parsed)
    except TypstError as exc:
        return _page(request, "render.html", "render",
                     flash=f"Ошибка компиляции: {exc}", flash_err=True, **ctx)
    name = f"{template}_{date.today()}.pdf"
    token = request.app.state.filestore.save_bytes(pdf, ".pdf", name)
    url = request.app.state.filestore.download_url(token)
    return RedirectResponse(f"/ui/render?link={url}&link_name={name}", status_code=302)


def _typst_templates() -> list[str]:
    return sorted(p.stem for p in TYPST_DIR.glob("*.typ"))
