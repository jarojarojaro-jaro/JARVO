#!/usr/bin/env python3
"""Konwersja do PDF przez Gotenberg (sidecar; LibreOffice + Chromium).

    python3 to_pdf.py <wejście.(md|html|docx|xlsx|pptx|odt)> <wyjście.pdf>

Markdown najpierw przez pandoc do HTML (z prostym stylem), potem Chromium → PDF.
Wymaga GOTENBERG_URL (np. http://gotenberg:3000).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import urllib.request
import uuid
from pathlib import Path

STYLE = """<style>
body{font-family:Inter,DejaVu Sans,sans-serif;font-size:11pt;line-height:1.5;max-width:780px;margin:32px auto;color:#111}
h1,h2,h3{line-height:1.2} table{border-collapse:collapse} td,th{border:1px solid #ccc;padding:4px 8px}
code,pre{font-family:DejaVu Sans Mono,monospace;font-size:9.5pt} img{max-width:100%}
</style>"""


def multipart(fields: dict[str, tuple[str, bytes, str]]) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = b""
    for name, (filename, data, ctype) in fields.items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
                 f"Content-Type: {ctype}\r\n\r\n").encode() + data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def post(url: str, fields: dict) -> bytes:
    body, ctype = multipart(fields)
    req = urllib.request.Request(url, data=body, headers={"Content-Type": ctype}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:  # noqa: S310 (adres z konfiguracji)
        return resp.read()


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 2:
        print(__doc__)
        return 2
    src, dst = Path(argv[0]), Path(argv[1])
    base = os.environ.get("GOTENBERG_URL")
    if not base:
        print("Brak GOTENBERG_URL. Alternatywa: pandoc in.md -o out.pdf (wymaga silnika PDF).")
        return 2
    ext = src.suffix.lower()
    if ext in {".md", ".markdown", ".html", ".htm"}:
        if ext in {".md", ".markdown"}:
            with tempfile.TemporaryDirectory() as tmp:
                html_path = Path(tmp) / "index.html"
                subprocess.run(["pandoc", str(src), "-s", "-o", str(html_path), "--metadata", f"title={src.stem}"], check=True)
                html = html_path.read_text(encoding="utf-8").replace("</head>", STYLE + "</head>")
        else:
            html = src.read_text(encoding="utf-8")
        pdf = post(base.rstrip("/") + "/forms/chromium/convert/html",
                   {"files": ("index.html", html.encode("utf-8"), "text/html")})
    else:
        pdf = post(base.rstrip("/") + "/forms/libreoffice/convert",
                   {"files": (src.name, src.read_bytes(), "application/octet-stream")})
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(pdf)
    print(f"PDF: {dst} ({len(pdf) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
