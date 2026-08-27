"""Операция blank_to_png: фирменный бланк (PDF или DOCX) -> PNG первой
страницы для подложки печатных форм. PDF рендерится pymupdf; DOCX
сначала конвертируется LibreOffice (нужен на сервере)."""
import shutil
import subprocess
import sys
from pathlib import Path

import pymupdf

src = Path(sys.argv[1])
pdf = src
if src.suffix.lower() in (".docx", ".doc"):
    soffice = shutil.which("libreoffice") or shutil.which("soffice")
    if not soffice:
        sys.exit("для DOCX-бланков нужен libreoffice на сервере")
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", ".",
                    str(src)], check=True, timeout=90, capture_output=True)
    pdf = Path(f"{src.stem}.pdf")

page = pymupdf.open(pdf)[0]
pix = page.get_pixmap(dpi=200)
pix.save("blank.png")
print(f"blank.png: {pix.width}x{pix.height}, {pdf.name}, страница 1 из {pymupdf.open(pdf).page_count}")
