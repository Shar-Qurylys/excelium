"""Настройки шлюза. Источник — переменные окружения (префикс GW_) и .env."""
import json
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GW_", env_file=APP_DIR / ".env", env_file_encoding="utf-8"
    )

    # Безопасность. allowlist — API (сервер Doc-V и продюсеры);
    # ui_allowlist — ДОПОЛНИТЕЛЬНО для /ui, /health и /files/*
    # (машины администраторов, офисная подсеть). Оба принимают
    # адреса и подсети (CIDR).
    # NoDecode: разбираем сами (см. _parse_list) — иначе pydantic требует
    # строгий JSON и падает на списке, из которого systemd снял кавычки
    allowlist: Annotated[list[str], NoDecode] = ["192.168.30.29", "127.0.0.1", "::1"]
    ui_allowlist: Annotated[list[str], NoDecode] = []
    token_docv: str = ""
    token_ops: str = ""
    token_admin: str = ""  # вход в веб-интерфейс /ui
    verify_secret: str = ""  # HMAC-код подлинности на печатных формах
    producer_tokens: dict[str, str] = {}

    # Адрес, по которому Doc-V скачивает файлы (не берём из Host-заголовка)
    base_url: str = "http://192.168.30.19:25353"

    # Внешние программы. Пусто/"typst" — искать в PATH и типичных
    # каталогах; можно указать абсолютный путь.
    typst_bin: str = "typst"

    # Хранилище
    var_dir: Path = APP_DIR / "var"
    file_ttl_hours: int = 72
    jobs_keep_days: int = 30

    # Очередь заданий
    lease_seconds: int = 60  # 2 x интервал опроса планировщика (30 с)
    jobs_payload_limit: int = 64 * 1024

    # Rate limit (fixed window, на процесс)
    rate_limit_per_min: int = 60
    ops_rate_limit_per_min: int = 10

    @field_validator("allowlist", "ui_allowlist", mode="before")
    @classmethod
    def _parse_list(cls, v):
        """Список адресов принимается и JSON-ом, и просто через запятую.

        systemd в EnvironmentFile умеет снимать кавычки, превращая
        ["a","b"] в [a,b] — строгий JSON на этом ломался, и сервис падал
        при старте вместо того, чтобы прочитать настройку.
        """
        if not isinstance(v, str):
            return v
        v = v.strip()
        if not v:
            return []
        if v.startswith("["):
            try:
                return json.loads(v)
            except ValueError:
                v = v[1:-1]  # кавычки съедены — разберём как список через запятую
        return [x.strip().strip('"').strip("'") for x in v.split(",") if x.strip()]

    @property
    def db_path(self) -> Path:
        return self.var_dir / "gateway.db"

    @property
    def files_dir(self) -> Path:
        return self.var_dir / "files"
