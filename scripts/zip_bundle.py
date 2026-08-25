"""Операция zip_bundle: пакует переданные файлы в bundle.zip в cwd."""
import sys
import zipfile
from pathlib import Path

paths = [Path(p) for p in sys.argv[1:]]
with zipfile.ZipFile("bundle.zip", "w", zipfile.ZIP_DEFLATED) as zf:
    for path in paths:
        zf.write(path, arcname=path.name)
print(f"файлов в архиве: {len(paths)}")
