"""Рендер PDF по Typst-шаблонам из templates/typst/.

Данные попадают в шаблон только через JSON-файл: тело запроса пишется
в data.json рабочей директории, шаблон читает его через
`json(sys.inputs.data)`. Typst-код из данных не собирается никогда.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

TIMEOUT_SEC = 30
STDERR_LIMIT = 4000


class TypstError(Exception):
    def __init__(self, message: str):
        super().__init__(message[:STDERR_LIMIT])


def typst_available() -> bool:
    return shutil.which("typst") is not None


def render_typst(template_path: Path, data: dict) -> bytes:
    with tempfile.TemporaryDirectory(prefix="typst-") as workdir:
        work = Path(workdir)
        (work / "data.json").write_text(json.dumps(data, ensure_ascii=False),
                                        encoding="utf-8")
        shutil.copy(template_path, work / template_path.name)
        out = work / "out.pdf"
        try:
            proc = subprocess.run(
                ["typst", "compile", "--root", str(work),
                 "--input", "data=data.json", template_path.name, out.name],
                cwd=work, capture_output=True, text=True, timeout=TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            raise TypstError("typst: превышен таймаут компиляции")
        if proc.returncode != 0 or not out.is_file():
            raise TypstError(f"typst: ошибка компиляции\n{proc.stderr}")
        return out.read_bytes()
