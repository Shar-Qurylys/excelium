"""Логирование: json-строки в stderr (подхватывает systemd) + отдельный audit-лог."""
import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        extra = getattr(record, "data", None)
        if extra:
            entry.update(extra)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(var_dir: Path) -> None:
    root = logging.getLogger()
    if any(getattr(h, "_gateway", False) for h in root.handlers):
        return  # повторный вызов (тесты, воркеры) — не дублировать хендлеры
    root.setLevel(logging.INFO)
    stream = logging.StreamHandler()
    stream.setFormatter(JsonFormatter())
    stream._gateway = True
    root.addHandler(stream)

    var_dir.mkdir(parents=True, exist_ok=True)
    audit = logging.getLogger("audit")
    audit.setLevel(logging.INFO)
    audit.propagate = False
    fh = logging.handlers.WatchedFileHandler(var_dir / "audit.log", encoding="utf-8")
    fh.setFormatter(JsonFormatter())
    fh._gateway = True
    audit.addHandler(fh)


def audit_log(event: str, **data) -> None:
    logging.getLogger("audit").info(event, extra={"data": data})
