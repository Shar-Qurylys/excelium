"""Рендер PDF по Typst-шаблонам из templates/typst/.

Данные попадают в шаблон только через JSON-файл: тело запроса пишется
в data.json рабочей директории, шаблон читает его через
`json(sys.inputs.data)`. Typst-код из данных не собирается никогда.

Поиск бинаря. Процесс под systemd стартует с урезанным PATH
(/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin), поэтому
typst, поставленный через cargo в ~/.cargo/bin, в PATH не виден, хотя
`which typst` в консоли его находит. Отсюда три источника пути, по
порядку: настройка GW_TYPST_BIN (можно абсолютный путь), PATH процесса,
типичные каталоги установки.
"""
import json
import os
import shutil
import subprocess
import tempfile
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


def render_typst(template_path: Path, data: dict) -> bytes:
    binary = typst_binary()
    if binary is None:
        raise TypstError(f"typst не найден (искали {_binary_setting!r}); "
                         "укажите GW_TYPST_BIN в .env")
    with tempfile.TemporaryDirectory(prefix="typst-") as workdir:
        work = Path(workdir)
        (work / "data.json").write_text(json.dumps(data, ensure_ascii=False),
                                        encoding="utf-8")
        shutil.copy(template_path, work / template_path.name)
        out = work / "out.pdf"
        try:
            proc = subprocess.run(
                [binary, "compile", "--root", str(work),
                 "--input", "data=data.json", template_path.name, out.name],
                cwd=work, capture_output=True, text=True, timeout=TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            raise TypstError("typst: превышен таймаут компиляции")
        if proc.returncode != 0 or not out.is_file():
            raise TypstError(f"typst: ошибка компиляции\n{proc.stderr}")
        return out.read_bytes()
