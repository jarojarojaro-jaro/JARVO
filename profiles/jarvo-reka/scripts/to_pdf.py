#!/usr/bin/env python3
"""Konwersja do PDF lokalnie, bez sidecarów: pandoc + Chromium z instalacji Jarva (+ LibreOffice, jeśli jest).

    python3 to_pdf.py <wejście.(md|html|docx|odt|xlsx|pptx|...)> <wyjście.pdf>

- Markdown/TXT: pandoc → HTML (z prostym stylem i osadzonymi obrazkami) → Chromium drukuje do PDF.
- HTML: Chromium drukuje plik bezpośrednio (względne ścieżki do obrazków działają).
- DOCX/ODT: LibreOffice, jeśli jest; inaczej pandoc → HTML → Chromium (treść, tabele i obrazki zostają, układ strony
  jest uproszczony).
- XLSX/PPTX/ODS/ODP/DOC/XLS/PPT: tylko LibreOffice.
Programy (docs/NATYWNIE.md F05, E07, E09): Chromium z CHROME_PATH (natywnie chrome-headless-shell z instalacji, w obrazie
/usr/local/bin/chromium), pandoc z PATH procesów Jarva, LibreOffice: JARVO_SOFFICE i wpis `libreoffice` w narzedzia.json
(miejsce na dodatek E07, dziś pusty), PATH (w obrazie dodatek `office`; bez snapa, który nie widzi plików Jarva), a
natywnie LibreOffice właściciela (Program Files, Aplikacje, /opt). Na Windows programy bez okna konsoli. Na Linuksie,
gdzie piaskownica Chromium nie ruszy mimo wszystko, druga próba bez niej (jak konwertuj.py). Proces Chromium żyje tylko
na czas konwersji (~150–250 MB RAM).
"""

from __future__ import annotations

import json
import os
import re
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
WINDOWS = os.name == "nt"
BEZ_OKNA = getattr(subprocess, "CREATE_NO_WINDOW", 0) if WINDOWS else 0
# przestrzenie nazw użytkownika, bez których piaskownica Chromium nie ruszy (jak w konwertuj.py): zakaz AppArmor
# Ubuntu 23.10+ (1), limit 0 i łatka Debiana unprivileged_userns_clone (0)
USERNS_APPARMOR = Path("/proc/sys/kernel/apparmor_restrict_unprivileged_userns")
USERNS_LIMIT = Path("/proc/sys/user/max_user_namespaces")
USERNS_CLONE = Path("/proc/sys/kernel/unprivileged_userns_clone")
PIASKOWNICA_BLAD = re.compile(r"sandbox|namespace|zygote", re.I)   # Chromium bez działającej piaskownicy
# LibreOffice w katalogu instalacji: Windows soffice.com (konsolowy, czeka na koniec) i soffice.exe, macOS pakiet .app,
# Linux program/soffice (pakiet systemu, /opt/libreofficeX.Y z paczek TDF albo dodatek Jarva z deb bez dpkg)
WZGLEDNE_SOFFICE = ("program/soffice.com", "program/soffice.exe", "LibreOffice.app/Contents/MacOS/soffice",
                    "Contents/MacOS/soffice", "program/soffice")


def _linux() -> bool:
    return sys.platform.startswith("linux")


def _w_kontenerze() -> bool:
    """Kontener Dockera; na Windows zawsze nie (`\\.dockerenv` w głównym katalogu dysku może założyć każdy)."""
    return not WINDOWS and Path("/.dockerenv").exists()


def natywnie() -> bool:
    return bool(os.environ.get("JARVO_ROOT")) and not _w_kontenerze()


def chromium() -> str:
    for cand in (os.environ.get("CHROME_PATH"), shutil.which("chromium"), shutil.which("chromium-browser"),
                 shutil.which("chrome-headless-shell"), shutil.which("google-chrome")):
        if cand and os.path.isfile(cand):
            return cand
    raise SystemExit("Brak Chromium (CHROME_PATH: natywnie chrome-headless-shell z instalacji Jarva, "
                     "w obrazie /usr/local/bin/chromium).")


def _sysctl(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def bez_piaskownicy() -> bool:
    """--no-sandbox tylko tam, gdzie piaskownica Chromium nie ruszy: Linux jako root, w kontenerze albo bez przestrzeni
    nazw użytkownika (zakaz AppArmor w Ubuntu 23.10+, user.max_user_namespaces=0, kernel.unprivileged_userns_clone=0).
    Windows i macOS: zawsze z piaskownicą."""
    if not _linux():
        return False
    if os.geteuid() == 0 or _w_kontenerze():
        return True
    return _sysctl(USERNS_APPARMOR) == "1" or _sysctl(USERNS_LIMIT) == "0" or _sysctl(USERNS_CLONE) == "0"


def ze_snapa(sciezka: str) -> bool:
    """LibreOffice ze snapa (/snap/bin/libreoffice → /usr/bin/snap) nie widzi ukrytych katalogów domowych ani /tmp
    tego procesu (piaskownica snapa): konwersja by padła, więc takiego nie bierzemy."""
    if not _linux():
        return False
    prawdziwa = os.path.realpath(sciezka)
    return sciezka.startswith("/snap/") or prawdziwa.startswith("/snap/") or os.path.basename(prawdziwa) == "snap"


def _soffice_w(katalog: Path) -> str | None:
    for rel in WZGLEDNE_SOFFICE:
        if (katalog / rel).is_file():
            return str(katalog / rel)
    return next((str(p) for p in sorted(katalog.glob("opt/libreoffice*/program/soffice"), reverse=True)
                 if p.is_file()), None)


def soffice() -> str | None:
    """LibreOffice: JARVO_SOFFICE, wpis `libreoffice` w `<JARVO_ROOT>/stan/narzedzia.json` (miejsce na dodatek E07;
    dziś nic go nie zapisuje), PATH bez snapa, a na końcu instalacja właściciela w typowym miejscu (na Windows
    i macOS LibreOffice nie trafia do PATH)."""
    jawny = os.environ.get("JARVO_SOFFICE")
    if jawny and os.path.isfile(jawny):
        return jawny
    if root := os.environ.get("JARVO_ROOT"):
        try:
            wpis = json.loads((Path(root) / "stan" / "narzedzia.json").read_text(encoding="utf-8-sig")).get(
                "libreoffice")
        except (OSError, ValueError, AttributeError):
            wpis = None
        if isinstance(wpis, dict):
            sciezka = (wpis.get("env") or {}).get("JARVO_SOFFICE")
            if sciezka and os.path.isfile(sciezka):
                return sciezka
            if wpis.get("katalog") and (p := _soffice_w(Path(wpis["katalog"]))):
                return p
    for nazwa in ("soffice", "libreoffice"):
        if (p := shutil.which(nazwa)) and not ze_snapa(p):
            return p
    kandydaci: list[Path] = []
    if WINDOWS:
        for zm in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
            if katalog := os.environ.get(zm):
                kandydaci.append(Path(katalog) / "LibreOffice")
        if katalog := os.environ.get("LOCALAPPDATA"):
            kandydaci.append(Path(katalog) / "Programs" / "LibreOffice")
    elif sys.platform == "darwin":
        kandydaci += [Path("/Applications/LibreOffice.app"), Path.home() / "Applications" / "LibreOffice.app"]
    else:
        kandydaci += [*sorted(Path("/opt").glob("libreoffice*"), reverse=True), Path("/usr/lib/libreoffice")]
    return next((p for k in kandydaci if (p := _soffice_w(k))), None)


def _uruchom(cmd: list, opis: str, **kw) -> None:
    """Program bez okna konsoli; błąd = SystemExit z ostatnimi liniami wyjścia (bez śladu stosu). Chromium i LibreOffice
    idą pełną ścieżką, pandoc z PATH procesów Jarva (na Windows nie ma go w System32, więc CreateProcess bierze ten
    z PATH)."""
    cmd = [str(x) for x in cmd]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT,
                           stdin=subprocess.DEVNULL, creationflags=BEZ_OKNA, **kw)
    except subprocess.TimeoutExpired:
        raise SystemExit(f"{opis}: przekroczony czas ({TIMEOUT} s)") from None
    except OSError as exc:
        raise SystemExit(f"{opis}: nie da się uruchomić ({exc})") from None
    if r.returncode != 0:
        ogon = [x for x in (r.stderr or r.stdout or "").strip().splitlines() if x.strip()][-4:]
        raise SystemExit(f"{opis} zakończył się błędem ({r.returncode}):\n" + "\n".join(ogon))


def polecenie_druku(html: Path, dst: Path, profil: Path, bez: bool) -> list[str]:
    return [chromium(), "--headless", *(["--no-sandbox"] if bez else []), "--disable-gpu", "--disable-extensions",
            "--no-first-run", f"--user-data-dir={profil}", "--no-pdf-header-footer", "--print-to-pdf-no-header",
            "--virtual-time-budget=5000", f"--print-to-pdf={dst}", html.resolve().as_uri()]


def print_html(html: Path, dst: Path, tmp: Path) -> None:
    """Druk do PDF. Linux, na którym piaskownica nie ruszyła mimo bez_piaskownicy() (np. przestrzenie nazw wyłączone
    w sposób, którego nie widać w /proc/sys): druga próba z --no-sandbox, z nowym profilem."""
    bez = bez_piaskownicy()
    for proba in (1, 2):
        try:
            _uruchom(polecenie_druku(html, dst, tmp / f"chrome-{proba}", bez), "Chromium")
            return
        except SystemExit as exc:
            if bez or not _linux() or not PIASKOWNICA_BLAD.search(str(exc)):
                raise
            bez = True


def pandoc_html(src: Path, tmp: Path) -> Path:
    out = tmp / "index.html"
    dane = tmp / "pandoc-dane"     # pusty katalog danych: bez szablonów i init.lua z katalogu użytkownika (E01)
    dane.mkdir(exist_ok=True)
    fmt = ["-f", "markdown"] if src.suffix.lower() == ".txt" else []
    _uruchom(["pandoc", str(src), *fmt, "-s", "--embed-resources", f"--resource-path={src.parent}",
              f"--data-dir={dane}", "--metadata", f"title={src.stem}", "-o", str(out)], "pandoc")
    out.write_text(out.read_text(encoding="utf-8").replace("</head>", STYLE + "</head>", 1), encoding="utf-8")
    return out


def libreoffice(src: Path, dst: Path, tmp: Path, office: str) -> None:
    _uruchom([office, f"-env:UserInstallation={(tmp / 'lo').as_uri()}", "--headless", "--norestore",
              "--convert-to", "pdf", "--outdir", str(tmp), str(src)], "LibreOffice")
    produced = tmp / (src.stem + ".pdf")
    if not produced.exists():
        raise SystemExit(f"LibreOffice nie utworzył PDF z {src.name}")
    shutil.move(str(produced), dst)


def rada_office(ext: str) -> str:
    """Jedno zdanie dla człowieka (jak rada w konwertuj.py): natywnie zwykła instalacja LibreOffice, którą skrypt
    znajduje sam, w obrazie dodatek `office`."""
    if not natywnie():
        return f"{ext} → PDF wymaga LibreOffice: zbuduj obraz z JARVO_EXTRAS=\"office\" albo zapisz plik jako DOCX/HTML."
    if any((p := shutil.which(n)) and ze_snapa(p) for n in ("soffice", "libreoffice")):
        return (f"{ext} → PDF wymaga LibreOffice, a ten ze snapa nie widzi plików Jarva (piaskownica snapa): zainstaluj "
                "go z pakietów systemu (np. apt install libreoffice) albo z libreoffice.org, albo zapisz plik jako "
                "DOCX/HTML.")
    return (f"{ext} → PDF wymaga LibreOffice: zainstaluj go na tym komputerze zwykłym instalatorem z libreoffice.org "
            "(Jarvo znajdzie go sam, bez żadnych ustawień) albo zapisz plik jako DOCX/HTML.")


def convert(src: Path, dst: Path) -> None:
    ext = src.suffix.lower()
    dst = dst.resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    # ignore_cleanup_errors: na Windows Chromium albo soffice.bin bywa przez chwilę jeszcze przy plikach profilu
    with tempfile.TemporaryDirectory(prefix="to-pdf-", ignore_cleanup_errors=True) as t:
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
                raise SystemExit(rada_office(ext))
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
    print(f"PDF: {dst.as_posix()} ({dst.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
