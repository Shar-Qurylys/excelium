"""Справочники соответствий из Doc-V. Токен — docv.

POST /directory/{имя} — приём справочника, который Doc-V шлёт сам
(тип «Шлюз»). Тело: {"items": [{"uid": "...", "name": "...", ...}]} либо
сразу массив. Полная замена справочника.

POST /directory/{имя}/refresh — сигнал от Doc-V «набор пересобран»:
шлюз сам забирает его из restgw (gateway/restgw.py).
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from .. import restgw
from ..logging_setup import audit_log

router = APIRouter()


@router.post("/directory/{name}")
async def upload(name: str, request: Request):
    body = await request.json()
    items = body.get("items") if isinstance(body, dict) else body
    if not isinstance(items, list):
        raise HTTPException(status_code=422, detail='нужен массив или {"items": [...]}')
    try:
        count = request.app.state.directory.replace(name, items)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    audit_log("directory_replaced", name=name, count=count)
    return {"directory": name, "items": count}


@router.post("/directory/{name}/refresh")
async def refresh(name: str, request: Request):
    state = request.app.state
    try:
        return await run_in_threadpool(restgw.refresh, state.directory, state.settings,
                                       name, "docv")
    except restgw.RestgwError as exc:
        return JSONResponse({"error": str(exc), "directory": name},
                            status_code=exc.status)


@router.get("/directory")
def stats(request: Request):
    return request.app.state.directory.stats()
