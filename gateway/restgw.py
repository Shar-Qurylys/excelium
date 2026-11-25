"""Забор справочников из Doc-V через REST-шлюз restgw.

restgw работает рядом с Doc-V и отдаёт наборы данных, которые Doc-V
собирает сам и пересобирает при каждом изменении справочника:

    GET <GW_RESTGW_URL>/v1/data/{имя}, заголовок X-API-Key
    200 -> {"name", "updated_at", "count", "items": [...]}
    401 — неизвестный ключ, 403 — у ключа нет области data,
    404 — нет такого набора, 502 — Doc-V не ответил или набор не собран.

Забранный набор кладётся в DirectoryStore.replace — тем же путём, что и
приём POST /directory/{имя}, поэтому формат справочника не меняется.
Когда забирать: при старте сервиса (все DATASETS), по сигналу Doc-V
POST /directory/{имя}/refresh и по кнопке на «Обзоре».

При любом сбое прежний справочник остаётся как был, причина пишется в
журнал. Ключ не попадает ни в журнал, ни в тексты ошибок.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from .directory import NAME_RE
from .logging_setup import audit_log

log = logging.getLogger(__name__)

DATASETS = ("structura", "positions", "departments")
TIMEOUT_SEC = 30

_STATUS_TEXT = {
    401: "restgw не принял ключ (401): проверьте GW_RESTGW_KEY",
    403: "у ключа restgw нет области data (403)",
    404: "в restgw нет набора «{name}» (404)",
    502: "restgw: Doc-V не ответил или набор «{name}» ещё не собран (502)",
}


class RestgwError(Exception):
    """Справочник не обновлён; текст — для человека. status — HTTP-код,
    которым отвечать вызвавшему refresh."""

    def __init__(self, text: str, status: int = 502):
        super().__init__(text)
        self.status = status


def _http_get(url: str, key: str, timeout: float) -> tuple[int, bytes]:
    """-> (HTTP-код, тело). Сетевой сбой — OSError (URLError, таймаут).
    Вынесено отдельно, чтобы тесты подменяли сеть."""
    req = urllib.request.Request(url, headers={"X-API-Key": key,
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def configured(settings) -> bool:
    return bool(settings.restgw_url.strip() and settings.restgw_key)


def fetch(settings, name: str) -> dict:
    """Забирает набор из restgw -> {"items": [...], "updated_at": ...}."""
    if not configured(settings):
        raise RestgwError("restgw не настроен: задайте GW_RESTGW_URL и GW_RESTGW_KEY"
                          " в .env и перезапустите сервис", status=503)
    url = (settings.restgw_url.strip().rstrip("/") + "/v1/data/"
           + urllib.parse.quote(name, safe=""))
    try:
        status, body = _http_get(url, settings.restgw_key, TIMEOUT_SEC)
    except (OSError, ValueError) as exc:  # нет связи, таймаут, кривой адрес
        reason = getattr(exc, "reason", None) or exc
        raise RestgwError(f"restgw недоступен ({settings.restgw_url}): {reason}")

    if status != 200:
        text = _STATUS_TEXT.get(status, "restgw ответил {status}").format(
            name=name, status=status)
        detail = _error_detail(body)
        raise RestgwError(text + (f": {detail}" if detail else ""))
    try:
        data = json.loads(body)
    except ValueError:
        raise RestgwError("restgw вернул не JSON")
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise RestgwError('restgw вернул ответ без массива "items"')
    return {"items": data["items"], "updated_at": data.get("updated_at")}


def _error_detail(body: bytes) -> str:
    try:
        data = json.loads(body)
    except ValueError:
        return ""
    if isinstance(data, dict):
        return str(data.get("error") or data.get("detail") or "")[:300]
    return ""


def refresh(store, settings, name: str, source: str) -> dict:
    """Забирает набор и замещает справочник. Сбой — RestgwError, событие
    directory_refresh_failed в журнале, прежний справочник не тронут.

    source: startup | docv | ui — кто попросил, для журнала.
    """
    try:
        if not NAME_RE.fullmatch(name):
            raise RestgwError("имя справочника: [a-z0-9_-], до 32 знаков", status=422)
        data = fetch(settings, name)
        items = data["items"]
        valid = [i for i in items
                 if isinstance(i, dict) and str(i.get("uid") or "").strip()]
        current = store.stats().get(name, 0)
        if not valid and current:
            raise RestgwError(f"restgw вернул пустой набор «{name}»; прежний"
                              f" справочник ({current} записей) оставлен")
        try:
            count = store.replace(name, items)
        except ValueError as exc:
            raise RestgwError(f"набор «{name}» не принят: {exc}", status=422)
    except RestgwError as exc:
        audit_log("directory_refresh_failed", name=name, source=source,
                  reason=str(exc))
        log.warning("справочник не обновлён из restgw",
                    extra={"data": {"name": name, "source": source, "reason": str(exc)}})
        raise
    audit_log("directory_refreshed", name=name, source=source, count=count,
              updated_at=data["updated_at"])
    return {"directory": name, "items": count, "updated_at": data["updated_at"]}


def refresh_all(store, settings, source: str = "startup") -> dict[str, str]:
    """Все DATASETS по очереди; сбой одного не мешает остальным.
    -> {имя: "ok" | причина}."""
    if not configured(settings):
        log.warning("restgw не настроен (GW_RESTGW_URL/GW_RESTGW_KEY) — справочники"
                    " при старте не забираются")
        return {}
    out = {}
    for name in DATASETS:
        try:
            refresh(store, settings, name, source)
            out[name] = "ok"
        except RestgwError as exc:
            out[name] = str(exc)
    return out
