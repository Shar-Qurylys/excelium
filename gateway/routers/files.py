"""GET /files/{token} — выдача сгенерированных файлов."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

router = APIRouter()


@router.get("/files/{token}")
def download(token: str, request: Request):
    resolved = request.app.state.filestore.resolve(token)
    if resolved is None:
        raise HTTPException(status_code=404)
    path, orig_name = resolved
    return FileResponse(path, filename=orig_name)
