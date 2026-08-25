"""Middleware безопасности: IP-allowlist -> bearer-токен по скоупу -> rate limit.

Провал любой проверки — единообразный 403 (429 для rate limit); причина
пишется только в audit-лог. Rate limit — fixed window на процесс: клиент
один (сервер Doc-V), точность между воркерами не требуется.
"""
import secrets
import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import Settings
from .logging_setup import audit_log

_FORBIDDEN = JSONResponse({"error": "forbidden"}, status_code=403)
_RATE_LIMITED = JSONResponse({"error": "rate_limited"}, status_code=429)


class _Window:
    """Счётчик запросов в минутном окне, потокобезопасный."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counts: dict[tuple, int] = {}
        self._minute = 0

    def hit(self, key: tuple, limit: int) -> bool:
        minute = int(time.time() // 60)
        with self._lock:
            if minute != self._minute:
                self._minute = minute
                self._counts.clear()
            n = self._counts.get(key, 0) + 1
            self._counts[key] = n
            return n <= limit


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
        self.window = _Window()

    async def dispatch(self, request: Request, call_next):
        s = self.settings
        ip = request.client.host if request.client else ""
        path = request.url.path
        method = request.method

        if ip not in s.allowlist:
            audit_log("deny_ip", ip=ip, path=path)
            return _FORBIDDEN

        # Пути только с IP-проверкой: health и выдача файлов (токен файла — сам секрет)
        exempt = (method == "GET" and (path == "/health" or path.startswith("/files/")))

        if not exempt:
            supplied = ""
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer "):
                supplied = auth[len("Bearer "):].strip()

            if path.startswith("/ops/"):
                ok = _match(supplied, s.token_ops)
            elif path == "/jobs" and method == "POST":
                producer = _match_producer(supplied, s.producer_tokens)
                ok = producer is not None
                request.state.producer = producer
            else:
                # /render/*, /jobs/pending, /jobs/ack и всё прочее — токен Doc-V
                ok = _match(supplied, s.token_docv)
            if not ok:
                audit_log("deny_token", ip=ip, path=path)
                return _FORBIDDEN

        limit = s.ops_rate_limit_per_min if path.startswith("/ops/") else s.rate_limit_per_min
        bucket = "ops" if path.startswith("/ops/") else "default"
        if not self.window.hit((ip, bucket), limit):
            audit_log("rate_limited", ip=ip, path=path)
            return _RATE_LIMITED

        return await call_next(request)


def _match(supplied: str, expected: str) -> bool:
    return bool(expected) and secrets.compare_digest(supplied, expected)


def _match_producer(supplied: str, producers: dict[str, str]) -> str | None:
    for name, token in producers.items():
        if _match(supplied, token):
            return name
    return None
