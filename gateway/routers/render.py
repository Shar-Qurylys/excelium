"""POST /render/registry/{вид} — Excel-реестры платежей.

Контракт совместим со старым сервисом: тело {"request": [...]},
ответ {"download_url": "..."}. Файл выдаётся через /files/{token}.
"""
import io
import logging
import re
from datetime import date

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, Field

from ..config import APP_DIR
from ..renderers.registry_inner import render_inner
from ..renderers.registry_outer import render_outer
from ..renderers.registry_priority import render_priority
from ..renderers.typst_renderer import TypstError, render_typst, typst_available

TYPST_DIR = APP_DIR / "templates" / "typst"
TEMPLATE_NAME_RE = re.compile(r"^[a-z0-9_-]{1,64}$")

log = logging.getLogger(__name__)
router = APIRouter()

REGISTRY_PREFIX = "РЕЕСТР ПЛАТЕЖЕЙ №"


class RegistryPayload(BaseModel):
    request: list[dict] = Field(min_length=1)


def _sorted(entries: list[dict]) -> list[dict]:
    return sorted(entries, key=lambda x: x.get("object_name") or "")


def _regnum(entries: list[dict]) -> str:
    name = str(entries[0].get("registry_name") or "")
    return name.removeprefix(REGISTRY_PREFIX).strip()


def _sanitize(value: str) -> str:
    return re.sub(r"\s+", "_", re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)).strip("_")


def _deliver(request: Request, workbook, orig_name: str) -> dict:
    request.app.state.heartbeat.touch("render")
    buf = io.BytesIO()
    workbook.save(buf)
    workbook.close()
    token = request.app.state.filestore.save_bytes(buf.getvalue(), ".xlsx", orig_name)
    return {"download_url": request.app.state.filestore.download_url(token)}


@router.post("/render/registry/inner")
def registry_inner(payload: RegistryPayload, request: Request):
    entries = _sorted(payload.request)
    workbook = render_inner(entries, request.app.state.template_inner,
                            request.app.state.approvers)
    name = f"reestr_{_sanitize(_regnum(entries))}_ot_{date.today()}.xlsx"
    return _deliver(request, workbook, name)


@router.post("/render/registry/outer")
def registry_outer(payload: RegistryPayload, request: Request):
    workbook = render_outer(payload.request, request.app.state.template_outer,
                            request.app.state.banks)
    return _deliver(request, workbook, f"vneshny_reestr_ot_{date.today()}.xlsx")


@router.post("/render/registry/priority")
def registry_priority(payload: RegistryPayload, request: Request):
    entries = _sorted(payload.request)
    workbook = render_priority(entries, request.app.state.template_priority)
    name = f"reestr_prioritetov_{_sanitize(_regnum(entries))}_ot_{date.today()}.xlsx"
    return _deliver(request, workbook, name)


@router.post("/render/typst/{name}")
def render_typst_endpoint(name: str, request: Request, data: dict = Body(...)):
    if not TEMPLATE_NAME_RE.fullmatch(name):
        raise HTTPException(status_code=404)
    store = request.app.state.typst_store
    source = store.get(name)
    if source is None:
        raise HTTPException(status_code=404, detail="нет такого шаблона")
    if not typst_available():
        raise HTTPException(status_code=503, detail="typst не установлен на сервере")
    request.app.state.heartbeat.touch("render")
    try:
        pdf = render_typst(name, source, data, store.assets_bytes(),
                           verify_secret=request.app.state.settings.verify_secret,
                           directory=request.app.state.directory.all())
    except TypstError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    token = request.app.state.filestore.save_bytes(pdf, ".pdf", f"{name}_{date.today()}.pdf")
    return {"download_url": request.app.state.filestore.download_url(token)}
