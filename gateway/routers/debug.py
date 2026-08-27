"""POST /debug/echo — зеркало для отладки интеграций.

Возвращает присланное тело как есть и сохраняет его в хранилище файлов
(видно на странице «Файлы»): так видно ровно то, что Doc-V отправляет,
без пересборки JSON руками. Токен — тот же, что у render.
"""
from datetime import datetime

from fastapi import APIRouter, Request

router = APIRouter()

ECHO_LIMIT = 2 * 1024 * 1024


@router.post("/debug/echo")
async def echo(request: Request):
    body = await request.body()
    stamp = datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
    token = request.app.state.filestore.save_bytes(
        body[:ECHO_LIMIT], ".json", f"echo_{stamp}.json")
    return {
        "size_bytes": len(body),
        "truncated": len(body) > ECHO_LIMIT,
        "saved_as": request.app.state.filestore.download_url(token),
        "content_type": request.headers.get("content-type", ""),
        "received": body[:ECHO_LIMIT].decode("utf-8", "replace"),
    }
