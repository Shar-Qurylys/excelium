"""Настройки шлюза. Источник — переменные окружения (префикс GW_) и .env."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GW_", env_file=APP_DIR / ".env", env_file_encoding="utf-8"
    )

    # Безопасность
    allowlist: list[str] = ["192.168.30.29", "127.0.0.1", "::1"]
    token_docv: str = ""
    token_ops: str = ""
    token_admin: str = ""  # вход в веб-интерфейс /ui
    producer_tokens: dict[str, str] = {}

    # Адрес, по которому Doc-V скачивает файлы (не берём из Host-заголовка)
    base_url: str = "http://192.168.30.19:25353"

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

    @property
    def db_path(self) -> Path:
        return self.var_dir / "gateway.db"

    @property
    def files_dir(self) -> Path:
        return self.var_dir / "files"
