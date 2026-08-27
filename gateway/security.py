"""Middleware безопасности: IP-allowlist -> авторизация -> rate limit.

API-пути закрыты bearer-токенами по скоупам; веб-интерфейс /ui — cookie
с админ-токеном (ставится формой входа). Провал любой проверки — 403
(429 для rate limit); причина пишется только в audit-лог. Rate limit —
fixed window на процесс: клиентов единицы, точность между воркерами
не требуется.

Allowlist принимает и адреса, и подсети: ["192.168.30.29",
"192.168.30.0/24", "127.0.0.1", "::1"].
"""
import ipaddress
import secrets
import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from .config import Settings
from .logging_setup import audit_log

_FORBIDDEN = JSONResponse({"error": "forbidden"}, status_code=403)
_RATE_LIMITED = JSONResponse({"error": "rate_limited"}, status_code=429)

ADMIN_COOKIE = "gw_admin"


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
        self.api_allowed = _parse_allowlist(settings.allowlist)
        self.ui_allowed = _parse_allowlist(settings.allowlist + settings.ui_allowlist)

    async def dispatch(self, request: Request, call_next):
        s = self.settings
        ip = request.client.host if request.client else ""
        path = request.url.path
        method = request.method

        # Три класса путей:
        #  browser — интерфейс, корень и документация: IP из ui_allowlist,
        #            дальше cookie администратора;
        #  open    — health, favicon, выдача файлов: только IP (токен файла
        #            сам себе секрет);
        #  api     — всё остальное: строгий allowlist + bearer по скоупу.
        browser_path = (path in ("/", "/ui", "/docs", "/redoc", "/openapi.json")
                        or path.startswith("/ui/"))
        open_path = (method == "GET" and (path in ("/health", "/favicon.ico")
                                          or path.startswith("/files/")))
        ui_path = browser_path or open_path
        if not _ip_allowed(ip, self.ui_allowed if ui_path else self.api_allowed):
            audit_log("deny_ip", ip=ip, path=path)
            # Свой IP клиенту и так известен, а без этой подсказки админ,
            # отрезанный по IP, не может зайти в /ui и увидеть причину.
            return JSONResponse({"error": "forbidden", "reason": "ip_not_allowed",
                                 "client_ip": ip,
                                 "hint": "добавьте адрес в GW_UI_ALLOWLIST (интерфейс)"
                                         " или GW_ALLOWLIST (API) в .env и перезапустите юнит"},
                                status_code=403)

        if not open_path:
            if browser_path:
                verdict = self._check_ui(request, path)
                if verdict is not None:
                    return verdict
            else:
                supplied = ""
                auth = request.headers.get("authorization", "")
                if auth.startswith("Bearer "):
                    supplied = auth[len("Bearer "):].strip()

                if path.startswith("/ops/") or path == "/ops":
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

    def _check_ui(self, request: Request, path: str):
        """None — пропустить; иначе готовый ответ."""
        if path == "/ui/login":
            return None
        cookie = request.cookies.get(ADMIN_COOKIE, "")
        if _match(cookie, self.settings.token_admin):
            return None
        audit_log("deny_ui", ip=request.client.host if request.client else "", path=path)
        if request.method == "GET":
            return RedirectResponse("/ui/login", status_code=302)
        return _FORBIDDEN


def _parse_allowlist(entries: list[str]):
    """-> (множество сырых имён вроде "testclient", список сетей)."""
    names, networks = set(), []
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            names.add(entry)  # не-адрес (клиент тестов)
    return names, networks


def _ip_allowed(ip: str, allowed) -> bool:
    names, networks = allowed
    if ip in names:
        return True
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in networks)


def _match(supplied: str, expected: str) -> bool:
    # compare_digest не принимает не-ASCII строки — сравниваем байты
    return bool(expected) and secrets.compare_digest(
        supplied.encode("utf-8"), expected.encode("utf-8"))


def _match_producer(supplied: str, producers: dict[str, str]) -> str | None:
    for name, token in producers.items():
        if _match(supplied, token):
            return name
    return None
