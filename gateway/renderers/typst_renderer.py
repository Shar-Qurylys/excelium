"""Рендер PDF по Typst-шаблонам из templates/typst/.

Данные попадают в шаблон только через JSON-файл: тело запроса пишется
в data.json рабочей директории, шаблон читает его через
`json(sys.inputs.data)`. Typst-код из данных не собирается никогда.

Каждому рендеру передаётся второй вход meta (json(sys.inputs.meta)):
время формирования (Астана) и код проверки — HMAC-SHA256 от данных на
секрете GW_VERIFY_SECRET: без секрета код не подделать, проверить можно
повторным формированием того же документа. Если данные содержат ключ
"qr" (строка-ссылка), шлюз сам собирает qr.png в рабочей директории —
шаблон подключает его как #image("qr.png").

Поиск бинаря. Процесс под systemd стартует с урезанным PATH
(/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin), поэтому
typst, поставленный через cargo в ~/.cargo/bin, в PATH не виден, хотя
`which typst` в консоли его находит. Отсюда три источника пути, по
порядку: настройка GW_TYPST_BIN (можно абсолютный путь), PATH процесса,
типичные каталоги установки.
"""
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TIMEOUT_SEC = 30
STDERR_LIMIT = 4000

FALLBACK_DIRS = (
    "~/.cargo/bin",      # cargo install typst-cli
    "/usr/local/bin",
    "/usr/bin",
    "/opt/typst",
    "/snap/bin",
)

_binary_setting = "typst"


class TypstError(Exception):
    def __init__(self, message: str):
        super().__init__(message[:STDERR_LIMIT])


def configure(binary: str | None) -> None:
    """Задать имя или абсолютный путь бинаря (вызывается при старте)."""
    global _binary_setting
    _binary_setting = (binary or "typst").strip() or "typst"


def typst_binary() -> str | None:
    """Абсолютный путь к бинарю или None, если его нет."""
    name = _binary_setting
    if os.path.isabs(name):
        return name if _executable(name) else None
    found = shutil.which(name)
    if found:
        return found
    for directory in FALLBACK_DIRS:
        candidate = str(Path(directory).expanduser() / name)
        if _executable(candidate):
            return candidate
    return None


def typst_available() -> bool:
    return typst_binary() is not None


def _executable(path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)


ALMATY = timezone(timedelta(hours=5))  # Казахстан един с 2024 года
QR_LIMIT = 500


def verify_code(data: dict, secret: str) -> str:
    """Код подлинности: ХХХХ-ХХХХ-ХХХХ от канонического JSON данных."""
    if not secret:
        return ""
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    raw = digest[:12].upper()
    return f"{raw[0:4]}-{raw[4:8]}-{raw[8:12]}"


def render_typst(name: str, source: str, data: dict,
                 assets: dict[str, bytes] | None = None,
                 *, verify_secret: str = "") -> bytes:
    """Компилирует шаблон source (имя нужно для сообщений об ошибках).

    Картинки assets кладутся в подпапку assets/ рабочей директории —
    шаблон подключает их как #image("assets/имя.png").
    """
    binary = typst_binary()
    if binary is None:
        raise TypstError(f"typst не найден (искали {_binary_setting!r}); "
                         "укажите GW_TYPST_BIN в .env")
    with tempfile.TemporaryDirectory(prefix="typst-") as workdir:
        work = Path(workdir)
        (work / "data.json").write_text(json.dumps(data, ensure_ascii=False),
                                        encoding="utf-8")
        (work / f"{name}.typ").write_text(source, encoding="utf-8")
        meta = {
            "generated_at": datetime.now(ALMATY).strftime("%d.%m.%Y %H:%M"),
            "verify_code": verify_code(data, verify_secret),
        }
        (work / "meta.json").write_text(json.dumps(meta, ensure_ascii=False),
                                        encoding="utf-8")
        qr_text = str(data.get("qr") or "")[:QR_LIMIT] if isinstance(data, dict) else ""
        if qr_text:
            import qrcode
            qr = qrcode.QRCode(border=1, box_size=8)
            qr.add_data(qr_text)
            qr.make(fit=True)
            qr.make_image(fill_color="black", back_color="white").save(work / "qr.png")
        if assets:
            (work / "assets").mkdir()
            for asset_name, blob in assets.items():
                (work / "assets" / asset_name).write_bytes(blob)
        out = work / "out.pdf"
        try:
            proc = subprocess.run(
                [binary, "compile", "--root", str(work),
                 "--input", "data=data.json", "--input", "meta=meta.json",
                 f"{name}.typ", out.name],
                cwd=work, capture_output=True, text=True, timeout=TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            raise TypstError("typst: превышен таймаут компиляции")
        if proc.returncode != 0 or not out.is_file():
            raise TypstError(f"typst: ошибка компиляции\n{proc.stderr}")
        return out.read_bytes()
