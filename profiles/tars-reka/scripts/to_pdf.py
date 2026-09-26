#!/usr/bin/env python3
"""Konwersja do PDF lokalnie, bez sidecarów: pandoc + Chromium z obrazu (+ LibreOffice, jeśli jest).

    python3 to_pdf.py <wejście.(md|html|docx|odt|xlsx|pptx|...)> <wyjście.pdf>

- Markdown/TXT: pandoc → HTML (z prostym stylem i osadzonymi obrazkami) → Chromium drukuje do PDF.
- HTML: Chromium drukuje plik bezpośrednio (względne ścieżki do obrazków działają).
- DOCX/ODT: LibreOffice, jeśli zainstalowany (TARS_EXTRAS="office"); inaczej pandoc → HTML → Chromium
  (treść, tabele i obrazki zostają, układ strony jest uproszczony).
- XLSX/PPTX/ODS/ODP/DOC/XLS/PPT: tylko LibreOffice (TARS_EXTRAS="office" przy budowie obrazu).
Proces Chromium żyje tylko na czas konwersji (~150–250 MB RAM).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

STYLE = """<style>
body{font-family:Inter,"DejaVu Sans",sans-serif;font-size:11pt;line-height:1.5;max-width:780px;margin:32px auto;color:#111}
h1,h2,h3{line-height:1.2} table{border-collapse:collapse} td,th{border:1px solid #ccc;padding:4px 8px}
code,pre{font-family:"DejaVu Sans Mono",monospace;font-size:9.5pt} img{max-width:100%}
header#title-block-header{display:none}
</style>"""

TEXT = {".md", ".markdown", ".txt"}
HTML = {".html", ".htm"}
PANDOC_OFFICE = {".docx", ".odt"}
OFFICE_ONLY = {".doc", ".rtf", ".xlsx", ".xls", ".ods", ".pptx", ".ppt", ".odp"}
TIMEOUT = 180


def chromium() -> str:
    for cand in (os.environ.get("CHROME_PATH"), shutil.which("chromium"), shutil.which("chromium-browser"),
                 shutil.which("google-chrome")):
        if cand and os.path.exists(cand):
            return cand
    raise SystemExit("Brak Chromium (obraz TARS: /usr/local/bin/chromium, CHROME_PATH).")


def soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def print_html(html: Path, dst: Path, tmp: Path) -> None:
    subprocess.run([chromium(), "--headless", "--no-sandbox", "--disable-gpu", "--disable-extensions",
                    "--no-first-run", f"--user-data-dir={tmp / 'chrome'}", "--no-pdf-header-footer",
                    "--print-to-pdf-no-header", "--virtual-time-budget=5000", f"--print-to-pdf={dst}",
                    html.resolve().as_uri()],
                   check=True, timeout=TIMEOUT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def pandoc_html(src: Path, tmp: Path) -> Path:
    out = tmp / "index.html"
    fmt = ["-f", "markdown"] if src.suffix.lower() == ".txt" else []
    subprocess.run(["pandoc", str(src), *fmt, "-s", "--embed-resources", f"--resource-path={src.parent}",
                    "--metadata", f"title={src.stem}", "-o", str(out)], check=True, timeout=TIMEOUT)
    out.write_text(out.read_text(encoding="utf-8").replace("</head>", STYLE + "</head>", 1), encoding="utf-8")
    return out


def libreoffice(src: Path, dst: Path, tmp: Path, office: str) -> None:
    subprocess.run([office, f"-env:UserInstallation={(tmp / 'lo').as_uri()}", "--headless", "--norestore",
                    "--convert-to", "pdf", "--outdir", str(tmp), str(src)],
                   check=True, timeout=TIMEOUT, stdout=subprocess.DEVNULL)
    produced = tmp / (src.stem + ".pdf")
    if not produced.exists():
        raise SystemExit(f"LibreOffice nie utworzył PDF z {src.name}")
    shutil.move(str(produced), dst)


def convert(src: Path, dst: Path) -> None:
    ext = src.suffix.lower()
    dst = dst.resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="to-pdf-") as t:
        tmp = Path(t)
        office = soffice()
        if ext in HTML:
            print_html(src, dst, tmp)
        elif ext in TEXT:
            print_html(pandoc_html(src, tmp), dst, tmp)
        elif ext in PANDOC_OFFICE:
            if office:
                libreoffice(src, dst, tmp, office)
            else:
                print_html(pandoc_html(src, tmp), dst, tmp)
        elif ext in OFFICE_ONLY:
            if not office:
                raise SystemExit(f"{ext} → PDF wymaga LibreOffice: zbuduj obraz z TARS_EXTRAS=\"office\" "
                                 "albo zapisz plik jako DOCX/HTML.")
            libreoffice(src, dst, tmp, office)
        else:
            raise SystemExit(f"Nieobsługiwany format: {ext}")
    if not dst.exists() or dst.stat().st_size == 0:
        raise SystemExit("Konwersja nie utworzyła PDF.")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 2:
        print(__doc__)
        return 2
    src, dst = Path(argv[0]), Path(argv[1])
    if not src.is_file():
        print(f"Brak pliku: {src}", file=sys.stderr)
        return 2
    convert(src, dst)
    print(f"PDF: {dst} ({dst.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
