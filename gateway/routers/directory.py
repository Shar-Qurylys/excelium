"""POST /directory/{имя} — приём справочника соответствий из Doc-V.

Тело: {"items": [{"uid": "...", "name": "...", ...}]} либо сразу массив.
Полная замена справочника. Токен — docv.
"""
from fastapi import APIRouter, HTTPException, Request

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


@router.get("/directory")
def stats(request: Request):
    return request.app.state.directory.stats()
