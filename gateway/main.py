"""Doc-V Gateway: FastAPI-приложение."""
import asyncio
import contextlib
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .filestore.store import FileStore
from .jobsqueue.db import init_db
from .logging_setup import setup_logging
from .config import APP_DIR, Settings
from .renderers.approvers import ApproverMatrix
from .renderers.registry_outer import load_banks
from .renderers.typst_renderer import typst_available
from .opsrunner.registry import load_registry
from .jobsqueue.service import JobQueue
from .routers import files, jobs, ops, render
from .security import SecurityMiddleware

log = logging.getLogger(__name__)

SWEEP_INTERVAL_SEC = 15 * 60


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    setup_logging(settings.var_dir)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(settings.db_path)
        app.state.settings = settings
        app.state.filestore = FileStore(settings)
        app.state.approvers = ApproverMatrix(APP_DIR / "data" / "approvers.yaml")
        app.state.banks = load_banks(APP_DIR / "data" / "banks.yaml")
        app.state.template_inner = APP_DIR / "templates" / "excel" / "template.xlsx"
        app.state.template_outer = APP_DIR / "templates" / "excel" / "template_outer.xlsx"
        app.state.template_priority = APP_DIR / "templates" / "excel" / "template_priority_registry.xlsx"
        app.state.ops = load_registry(APP_DIR / "ops.yaml")
        app.state.jobs = JobQueue(settings.db_path, lease_seconds=settings.lease_seconds,
                                  keep_days=settings.jobs_keep_days)
        task = asyncio.create_task(_sweep_loop(app))
        if not typst_available():
            log.warning("бинарь typst не найден — /render/typst будет отвечать 503")
        log.info("gateway started")
        yield
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    app = FastAPI(title="Doc-V Gateway", lifespan=lifespan)
    app.add_middleware(SecurityMiddleware, settings=settings)
    app.include_router(files.router)
    app.include_router(render.router)
    app.include_router(ops.router)
    app.include_router(jobs.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.exception_handler(Exception)
    async def unhandled(request, exc):
        log.exception("unhandled error at %s", request.url.path)
        return JSONResponse({"error": "internal", "detail": str(exc)}, status_code=500)

    return app


async def _sweep_loop(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(SWEEP_INTERVAL_SEC)
        try:
            await asyncio.to_thread(app.state.filestore.sweep)
            await asyncio.to_thread(app.state.jobs.sweep)
        except Exception:
            log.exception("sweep failed")


app = create_app()
