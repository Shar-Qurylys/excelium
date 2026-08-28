"""Настройки, правимые на лету (var/settings.json).

Правится только то, что безопасно менять из интерфейса: сроки хранения,
аренда заданий, лимиты частоты. Токены и списки адресов живут в .env и
здесь только показываются: смена их из веба может закрыть доступ самому
администратору или открыть его чужим.
"""
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# поле -> (подпись, единица, минимум, максимум)
EDITABLE = {
    "file_ttl_hours": ("Хранить файлы", "часов", 1, 24 * 30),
    "jobs_keep_days": ("Хранить подтверждённые задания", "дней", 1, 365),
    "lease_seconds": ("Аренда задания", "секунд", 10, 3600),
    "rate_limit_per_min": ("Лимит запросов", "в минуту", 10, 10000),
    "ops_rate_limit_per_min": ("Лимит запуска операций", "в минуту", 1, 1000),
    "jobs_payload_limit": ("Лимит payload задания", "байт", 1024, 8 * 1024 * 1024),
}


class SettingsStore:
    def __init__(self, settings, path: Path):
        self.settings = settings
        self.path = path

    def load(self) -> None:
        """Накладывает сохранённые значения на настройки процесса."""
        if not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except ValueError:
            log.warning("settings.json повреждён — пропущен")
            return
        for key, value in data.items():
            if key in EDITABLE and isinstance(value, int):
                setattr(self.settings, key, value)

    def save(self, values: dict[str, int]) -> dict[str, int]:
        """Проверяет границы, применяет к живому процессу и записывает."""
        applied = {}
        for key, raw in values.items():
            if key not in EDITABLE:
                continue
            _, _, low, high = EDITABLE[key]
            try:
                value = int(raw)
            except (TypeError, ValueError):
                raise ValueError(f"{key}: нужно целое число")
            if not low <= value <= high:
                raise ValueError(f"{EDITABLE[key][0]}: допустимо от {low} до {high}")
            applied[key] = value
        for key, value in applied.items():
            setattr(self.settings, key, value)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(applied, ensure_ascii=False, indent=1),
                             encoding="utf-8")
        return applied

    def current(self) -> list[dict]:
        out = []
        for key, (label, unit, low, high) in EDITABLE.items():
            out.append({"key": key, "label": label, "unit": unit,
                        "min": low, "max": high, "value": getattr(self.settings, key)})
        return out
