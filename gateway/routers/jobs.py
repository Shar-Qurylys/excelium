"""Очередь заданий: POST /jobs (продюсеры) -> GET /jobs/pending (Doc-V)
-> POST /jobs/ack (Doc-V)."""
import json

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..logging_setup import audit_log

router = APIRouter()

MAX_ATTEMPTS_WARN = 50


class NewJob(BaseModel):
    type: str = Field(min_length=1, max_length=64)
    payload: dict
    idempotency_key: str | None = Field(default=None, max_length=200)


class AckBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


@router.post("/jobs")
def enqueue(body: NewJob, request: Request):
    settings = request.app.state.settings
    if len(json.dumps(body.payload, ensure_ascii=False).encode()) > settings.jobs_payload_limit:
        raise HTTPException(status_code=413, detail="payload больше лимита")
    producer = getattr(request.state, "producer", None) or "unknown"
    job_id, created = request.app.state.jobs.enqueue(
        producer=producer, job_type=body.type, payload=body.payload,
        idempotency_key=body.idempotency_key)
    audit_log("job_enqueued", job_id=job_id, producer=producer,
              type=body.type, created=created)
    return {"job_id": job_id, "created": created}


@router.get("/jobs/pending")
def pending(request: Request, consumer: str = "docv",
            limit: int = Query(default=20, ge=1, le=100)):
    jobs = request.app.state.jobs.lease(consumer=consumer, limit=limit)
    for job in jobs:
        if job["attempts"] > MAX_ATTEMPTS_WARN:
            audit_log("job_many_attempts", job_id=job["job_id"], attempts=job["attempts"])
    # пустой случай — буквально [], дёшево и байт-в-байт одинаково
    return JSONResponse(content=jobs)


@router.post("/jobs/ack")
def ack(body: AckBody, request: Request):
    result = request.app.state.jobs.ack(body.ids)
    audit_log("jobs_acked", **{k: len(v) for k, v in result.items()})
    return result
