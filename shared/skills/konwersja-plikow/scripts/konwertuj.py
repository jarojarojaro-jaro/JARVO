#!/usr/bin/env python3
"""Konwerter plików Jarva: plik → inny format na serwerze, bez wysyłania gdziekolwiek (wzór: convt, kod własny).

    python3 konwertuj.py <plik…|katalog> --na <format> [-o wynik | --katalog DIR] [--jakosc 1-100]
                         [--rozmiar 1080|720p|50%|1920x1080] [--strony 1-3,5] [--dpi 150] [--polacz] [-r]
    python3 konwertuj.py <plik> --cele          # na co można zamienić ten plik (JSON)
    python3 konwertuj.py <plik…> --metadane     # co plik mówi o człowieku: miejsce GPS, telefon, data, autor, firma (JSON)
    python3 konwertuj.py <plik…|katalog> --usun-metadane [-o wynik | --katalog DIR]   # ten sam plik bez metadanych
    python3 konwertuj.py --formaty              # formaty i silniki dostępne tutaj (JSON)

Silniki (co jest w instalacji, to działa; bez silnika trasa znika): Pillow (zdjęcia, HEIC z iPhone'a, AVIF, PSD,
zdjęcia → PDF), FFmpeg (wideo, audio, GIF, SVG → PNG z librsvg), PDFium przez pypdfium2 (PDF → obrazy stron i tekst),
pikepdf (mniejszy PDF: obrazy zmniejszone do dpi jakości i przeliczone na JPEG), qpdf (łączenie PDF, mniejszy PDF:
obrazy przeliczone na JPEG w jakości --jakosc, gdy wychodzi mniej, bez zmiany liczby pikseli), Ghostscript tylko
tam, gdzie już jest (obraz Jarva: mniejszy PDF), pandoc (Word, ODT, Markdown, HTML, EPUB, RTF), Chromium (HTML → PDF
i SVG → PNG, bez sieci), LibreOffice (Excel, PowerPoint, stare .doc/.xls/.ppt: w obrazie dodatek `office`, natywnie
LibreOffice zainstalowany na tym komputerze).
Trasa: najtańsza przez najwyżej 3 kroki (np. DOCX → HTML → PDF, XLSX → PDF → PNG).
Natywnie (docs/NATYWNIE.md E04, E07, E09): programy z instalacji Jarva pełną ścieżką z PATH procesów Jarva (pandoc,
qpdf, exiftool, ffmpeg; Chromium z CHROME_PATH), na Windows bez okna konsoli. Venv narzędzi floty ma Pillow,
pillow-heif, pypdfium2 i pikepdf; w Pythonie bez Pillow (np. starszy venv) skrypt sam przechodzi do Pythona Hermesa
z instalacji, a gdzie brak pypdfium2 albo pikepdf (Konwerter panelu w Pythonie Hermesa), strony PDF renderuje Python
venvu OCR (JARVO_OCR_PYTHON, w obrazie /opt/jarvo/venvs/ocr), a mniejszy PDF robi Python venvu narzędzi
(JARVO_TOOLS_PYTHON), ten sam skrypt z zadaniem JSON na wejściu. Domyślne ścieżki obrazu tylko na Linuksie i macOS.
Wynik obok pliku (albo -o / --katalog); istniejącego pliku nie nadpisuje: nazwa-2.ext.
--rozmiar: 1080 = dłuższy bok najwyżej 1080 px, 720p = krótszy bok 720, 50% = połowa, 1920x1080 = zmieść w polu;
nigdy nie powiększa. --jakosc: zdjęcia (domyślnie 85), film (domyślnie 75), audio (kb/s ≈ 3,2 × jakość),
PDF → PDF (mniejszy plik). Ten sam format z --rozmiar albo --jakosc = zmniejszenie pliku.
--polacz: kilka plików (zdjęcia, PDF, dokumenty) → jeden PDF. --strony: strony PDF do obrazów i tekstu („1-3,5”, „4-”).
Metadane (miejsce GPS, telefon, daty, autor, opisy) nie przechodzą do wyniku zamiany zdjęcia, filmu ani dźwięku;
profil koloru i obrót zostają. --usun-metadane (exiftool, FFmpeg, qpdf): ten sam format bez przekodowania, a wynik
jest sprawdzany (coś zostało = błąd, nie plik); bez -o wynik obok: <nazwa>-bez-metadanych.<ext>. Dokumenty: PDF
(exiftool + qpdf przepisuje plik, więc stare wersje metadanych nie zostają w środku) oraz DOCX, XLSX, PPTX, ODT, ODS,
ODP (właściwości dokumentu: autor, firma, program, szablon, daty, historia zmian, własne pola; treść bez zmian).
Komentarze i śledzone zmiany z nazwiskami to treść: skrypt je wskazuje (`uwagi`), ale nie usuwa.
Wynik: JSON {pliki, trasa, rozmiar_przed, rozmiar_po, sek}; kod 1 = błąd z opisem po polsku.
"""

from __future__ import annotations

import argparse
import functools
import heapq
import http.server
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

WINDOWS = os.name == "nt"
# programy bez okna konsoli: konwerter działa też w procesie panelu, który na Windows nie ma konsoli (każdy
# program konsolowy otworzyłby wtedy własne okno)
BEZ_OKNA = getattr(subprocess, "CREATE_NO_WINDOW", 0) if WINDOWS else 0
# venv OCR w obrazie (pypdfium2, numpy, opencv); na Windows żadnej domyślnej ścieżki: `\opt\…` w głównym katalogu dysku
# może założyć każdy zalogowany użytkownik, a CreateProcess uruchomi plik PE o nazwie `python` bez rozszerzenia
OCR_PYTHON_OBRAZU = None if WINDOWS else "/opt/jarvo/venvs/ocr/bin/python"

# --------------------------------------------------------------------------- formaty

# format → (grupa, nazwa, opis)
FORMATY: dict[str, tuple[str, str, str]] = {
    "jpg": ("obraz", "JPG", "zdjęcia, mały plik"),
    "png": ("obraz", "PNG", "bez strat, przezroczystość"),
    "webp": ("obraz", "WebP", "mały, na strony"),
    "avif": ("obraz", "AVIF", "najmniejszy"),
    "heic": ("obraz", "HEIC", "zdjęcia z iPhone'a"),
    "gif": ("obraz", "GIF", "animacja"),
    "tiff": ("obraz", "TIFF", "do druku"),
    "bmp": ("obraz", "BMP", "bez kompresji"),
    "ico": ("obraz", "ICO", "ikona strony"),
    "tga": ("obraz", "TGA", "grafika gier"),
    "ppm": ("obraz", "PPM", "surowy obraz"),
    "qoi": ("obraz", "QOI", "szybki, bez strat"),
    "psd": ("obraz", "PSD", "Photoshop"),
    "svg": ("obraz", "SVG", "grafika wektorowa"),
    "mp4": ("wideo", "MP4", "działa wszędzie"),
    "mov": ("wideo", "MOV", "Apple"),
    "webm": ("wideo", "WebM", "na strony"),
    "mkv": ("wideo", "MKV", "kontener"),
    "avi": ("wideo", "AVI", "stary format"),
    "mp3": ("audio", "MP3", "działa wszędzie"),
    "wav": ("audio", "WAV", "bez kompresji"),
    "m4a": ("audio", "M4A", "Apple"),
    "aac": ("audio", "AAC", "sam dźwięk AAC"),
    "ogg": ("audio", "OGG", "Vorbis"),
    "opus": ("audio", "Opus", "najmniejszy"),
    "flac": ("audio", "FLAC", "bez strat"),
    "pdf": ("pdf", "PDF", "do druku i wysyłki"),
    "docx": ("dokument", "DOCX", "Word"),
    "doc": ("dokument", "DOC", "stary Word"),
    "odt": ("dokument", "ODT", "LibreOffice"),
    "rtf": ("dokument", "RTF", "prosty edytor"),
    "epub": ("dokument", "EPUB", "e-book"),
    "md": ("tekst", "Markdown", "notatki"),
    "html": ("tekst", "HTML", "strona"),
    "txt": ("tekst", "TXT", "sam tekst"),
    "xlsx": ("arkusz", "XLSX", "Excel"),
    "xls": ("arkusz", "XLS", "stary Excel"),
    "ods": ("arkusz", "ODS", "LibreOffice"),
    "csv": ("arkusz", "CSV", "tabela tekstem"),
    "pptx": ("prezentacja", "PPTX", "PowerPoint"),
    "ppt": ("prezentacja", "PPT", "stary PowerPoint"),
    "odp": ("prezentacja", "ODP", "LibreOffice"),
}
ALIASY = {"jpeg": "jpg", "jpe": "jpg", "jfif": "jpg", "tif": "tiff", "heif": "heic", "htm": "html",
          "markdown": "md", "m4v": "mp4", "text": "txt", "oga": "ogg"}
GRUPY = ("obraz", "wideo", "audio", "pdf", "dokument", "tekst", "arkusz", "prezentacja")
PRZEJSCIOWE = {"html", "pdf", "png", "docx"}   # formaty pośrednie tras wielokrokowych
TYLKO_PIERWSZY = {("pdf", "txt")}   # tekst z PDF tylko z prawdziwego PDF (z obrazu wyszedłby pusty)
MAX_KROKOW = 3
MAX_STRON = 200          # PDF → obrazy bez --strony
WIDEO = {"mp4", "mov", "webm", "mkv", "avi"}
AUDIO = {"mp3", "wav", "m4a", "aac", "ogg", "opus", "flac"}
# bez miejsca, telefonu, dat, tytułów i rozdziałów; bitexact: bez dopisku „Lavf…” (obrót obrazu zostaje: to nie metadane)
FF_BEZ_METADANYCH = ["-map_metadata", "-1", "-map_chapters", "-1", "-fflags", "+bitexact"]


class Blad(Exception):
    """Błąd konwersji z opisem dla człowieka."""


def norm(fmt: str) -> str:
    f = str(fmt or "").strip().lower().lstrip(".")
    return ALIASY.get(f, f)


def format_pliku(p: Path) -> str:
    f = norm(p.suffix)
    if f not in FORMATY:
        raise Blad(f"Nie znam formatu „{p.suffix or p.name}”. Formaty: python3 konwertuj.py --formaty")
    return f


@dataclass
class Opcje:
    jakosc: int | None = None
    rozmiar: str | None = None
    strony: str | None = None
    dpi: int = 150
    zasoby: Path | None = None        # katalog pliku źródłowego: obrazki obok HTML/Markdown przy druku do PDF

    def zmienia(self) -> bool:
        return self.jakosc is not None or bool(self.rozmiar)


# --------------------------------------------------------------------------- rozmiar

def parse_rozmiar(s: str | None) -> tuple | None:
    """„1080” (dłuższy bok), „720p” (krótszy bok), „50%”, „1920x1080” (pole) → krotka; None bez rozmiaru."""
    if not s:
        return None
    t = str(s).strip().lower().replace(" ", "").replace("×", "x")
    if m := re.fullmatch(r"(\d{1,5})", t):
        return ("dluzszy", int(m[1]))
    if m := re.fullmatch(r"(\d{1,5})p", t):
        return ("krotszy", int(m[1]))
    if m := re.fullmatch(r"(\d{1,3}(?:[.,]\d+)?)%", t):
        return ("proc", min(100.0, float(m[1].replace(",", "."))))
    if m := re.fullmatch(r"(\d{1,5})x(\d{1,5})", t):
        return ("pole", int(m[1]), int(m[2]))
    raise Blad(f"Zły --rozmiar „{s}”: 1080 (dłuższy bok), 720p (krótszy bok), 50% albo 1920x1080.")


def nowy_rozmiar(w: int, h: int, spec: tuple | None) -> tuple[int, int]:
    """Docelowe wymiary (bez powiększania, proporcje zachowane)."""
    if not spec or w <= 0 or h <= 0:
        return w, h
    if spec[0] == "dluzszy":
        k = spec[1] / max(w, h)
    elif spec[0] == "krotszy":
        k = spec[1] / min(w, h)
    elif spec[0] == "proc":
        k = spec[1] / 100
    else:
        k = min(spec[1] / w, spec[2] / h)
    k = min(1.0, k)
    return max(1, round(w * k)), max(1, round(h * k))


def skala_ffmpeg(spec: tuple | None, parzyste: bool = True) -> str:
    """Filtr scale z --rozmiar (wyrażenia ffmpeg liczone po obrocie z telefonu); pusty bez rozmiaru."""
    if not spec:
        return "scale=trunc(iw/2)*2:trunc(ih/2)*2" if parzyste else ""
    ev = (lambda e: f"trunc(({e})/2)*2") if parzyste else (lambda e: e)
    if spec[0] == "dluzszy":
        n = spec[1]
        return (f"scale='if(gte(iw,ih),{ev(f'min({n},iw)')},-2)':'if(gte(iw,ih),-2,{ev(f'min({n},ih)')})'"
                ":flags=lanczos")
    if spec[0] == "krotszy":
        n = spec[1]
        return (f"scale='if(gte(iw,ih),-2,{ev(f'min({n},iw)')})':'if(gte(iw,ih),{ev(f'min({n},ih)')},-2)'"
                ":flags=lanczos")
    if spec[0] == "proc":
        p = spec[1] / 100
        return f"scale='{ev(f'iw*{p:g}')}':'{ev(f'ih*{p:g}')}':flags=lanczos"
    w, h = spec[1], spec[2]
    div = ":force_divisible_by=2" if parzyste else ""
    return f"scale='min({w},iw)':'min({h},ih)':force_original_aspect_ratio=decrease{div}:flags=lanczos"


# --------------------------------------------------------------------------- narzędzia

def program(nazwa: str) -> str | None:
    """Pełna ścieżka programu z PATH tego procesu albo None. Natywnie PATH procesów Jarva zaczyna się od programów
    z instalacji (jarvo/srodowisko.py: bin-floty, pandoc, qpdf, exiftool, ffmpeg…); pełna ścieżka, bo CreateProcess
    na Windows szuka gołej nazwy najpierw w katalogu Pythona i w System32, a nie w PATH."""
    return shutil.which(nazwa)


def _argv(cmd: list) -> list[str]:
    """Polecenie z programem pełną ścieżką (goła nazwa → program(); brak programu zostawia nazwę: błąd mówi co)."""
    cmd = [str(x) for x in cmd]
    if cmd and not os.path.dirname(cmd[0]):
        cmd[0] = program(cmd[0]) or cmd[0]
    return cmd


def _proc(cmd: list, timeout: float | None = None, **kw) -> subprocess.CompletedProcess:
    """Program z przechwyconym wyjściem w UTF-8, bez wejścia i bez okna konsoli (Windows)."""
    kw.setdefault("stdin", subprocess.DEVNULL)
    return subprocess.run(_argv(cmd), capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, creationflags=BEZ_OKNA, **kw)


def _run(cmd: list, silnik: str, timeout: int, cwd: Path | None = None,
         ok: tuple[int, ...] = (0,), wejscie: str | None = None) -> subprocess.CompletedProcess:
    """Program silnika; kod spoza `ok` (qpdf: 3 = ostrzeżenia, plik jest dobry) = Blad z ostatnimi liniami wyjścia.
    `wejscie`: tekst na wejście programu (UTF-8)."""
    try:
        r = (_proc(cmd, timeout=timeout, cwd=cwd) if wejscie is None
             else _proc(cmd, timeout=timeout, cwd=cwd, input=wejscie, stdin=None))
    except subprocess.TimeoutExpired:
        raise Blad(f"{silnik}: przekroczony czas ({timeout // 60} min)") from None
    except OSError as exc:
        raise Blad(f"{silnik}: nie da się uruchomić ({exc})") from None
    if r.returncode not in ok:
        lines = [x for x in (r.stderr or r.stdout or "").strip().splitlines() if x.strip()]
        tail = "\n".join(dict.fromkeys(lines[:4] + lines[-4:]))
        raise Blad(f"{silnik} zakończył się błędem ({r.returncode}):\n{tail}")
    return r


def _w_kontenerze() -> bool:
    """Kontener Dockera (obraz Jarva). Na Windows zawsze nie: `\\.dockerenv` w głównym katalogu dysku może założyć
    każdy."""
    return not WINDOWS and Path("/.dockerenv").exists()


def natywnie() -> bool:
    """Instalacja natywna (JARVO_ROOT w procesach Jarva), a nie obraz Jarva: inne rady w komunikatach."""
    return bool(os.environ.get("JARVO_ROOT")) and not _w_kontenerze()


def chromium() -> str | None:
    """Chromium skryptów: CHROME_PATH (natywnie chrome-headless-shell z instalacji, w obrazie /usr/local/bin/chromium),
    potem PATH."""
    for cand in (os.environ.get("CHROME_PATH"), program("chromium"), program("chromium-browser"),
                 program("chrome-headless-shell"), program("google-chrome")):
        if cand and os.path.isfile(cand):
            return cand
    return None


# przestrzenie nazw użytkownika, bez których piaskownica Chromium nie ruszy (chrome-headless-shell nie ma programu
# chrome-sandbox): AppArmor Ubuntu 23.10+ (1 = zakaz bez profilu), limit 0 i łatka Debiana unprivileged_userns_clone
# (0 = zakaz)
USERNS_APPARMOR = Path("/proc/sys/kernel/apparmor_restrict_unprivileged_userns")
USERNS_LIMIT = Path("/proc/sys/user/max_user_namespaces")
USERNS_CLONE = Path("/proc/sys/kernel/unprivileged_userns_clone")
PIASKOWNICA_BLAD = re.compile(r"sandbox|namespace|zygote", re.I)   # Chromium bez działającej piaskownicy


def _linux() -> bool:
    return sys.platform.startswith("linux")


def _sysctl(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def bez_piaskownicy() -> bool:
    """Czy Chromium potrzebuje --no-sandbox (jak audit.py Weba): tylko Linux jako root, w kontenerze albo bez przestrzeni
    nazw użytkownika (zakaz AppArmor w Ubuntu 23.10+, user.max_user_namespaces=0, kernel.unprivileged_userns_clone=0).
    Windows i macOS: piaskownica zawsze działa. Na innym Linuksie, gdzie piaskownica jednak nie ruszy, Chromium.zamien
    próbuje drugi raz bez niej."""
    if not _linux():
        return False
    if os.geteuid() == 0 or _w_kontenerze():
        return True
    return _sysctl(USERNS_APPARMOR) == "1" or _sysctl(USERNS_LIMIT) == "0" or _sysctl(USERNS_CLONE) == "0"


# LibreOffice (E07): dziś program właściciela; dodatek Jarva `libreoffice` (MSI, DMG i paczki deb TDF przy pierwszym
# użyciu) czeka na pobieracz z tymi formatami i `jarvo narzedzia dodaj` (M08), a kod już czyta jego wpis w
# narzedzia.json. W katalogu programu Windows ma soffice.com (konsolowy: czeka na koniec i oddaje wyjście)
# i soffice.exe; macOS w pakiecie .app; Linux soffice z pakietu systemu albo z /opt/libreofficeX.Y (paczki TDF).
# Pierwszy istniejący wygrywa.
WZGLEDNE_SOFFICE = ("program/soffice.com", "program/soffice.exe", "LibreOffice.app/Contents/MacOS/soffice",
                    "Contents/MacOS/soffice", "program/soffice")
WZOR_SOFFICE_DEB = "opt/libreoffice*/program/soffice"       # paczki deb TDF rozpakowane bez dpkg (dodatek na Linuksie)


def _soffice_w(katalog: Path) -> str | None:
    for rel in WZGLEDNE_SOFFICE:
        p = katalog / rel
        if p.is_file():
            return str(p)
    return next((str(p) for p in sorted(katalog.glob(WZOR_SOFFICE_DEB), reverse=True) if p.is_file()), None)


def ze_snapa(sciezka: str) -> bool:
    """LibreOffice ze snapa (Ubuntu: /snap/bin/libreoffice → /usr/bin/snap). Piaskownica snapa nie widzi ukrytych
    katalogów domowych (~/.local/share/jarvo) ani /tmp tego procesu, więc konwersja by padła: takiego nie bierzemy."""
    if not _linux():
        return False
    prawdziwa = os.path.realpath(sciezka)
    return sciezka.startswith("/snap/") or prawdziwa.startswith("/snap/") or os.path.basename(prawdziwa) == "snap"


def _soffice_z_path() -> str | None:
    for nazwa in ("soffice", "libreoffice"):
        if (p := program(nazwa)) and not ze_snapa(p):
            return p
    return None


def _soffice_dodatku() -> str | None:
    """Wpis `libreoffice` w `<JARVO_ROOT>/stan/narzedzia.json` (zmienna JARVO_SOFFICE wpisu albo jego katalog), także
    gdy proces wystartował przed instalacją dodatku (jego środowisko nie ma jeszcze zmiennej). Dziś nic go nie zapisuje:
    to miejsce na dodatek E07 (vendor/natywne.yaml, `kiedy: dodatek`)."""
    root = os.environ.get("JARVO_ROOT")
    if not root:
        return None
    try:
        narz = json.loads((Path(root) / "stan" / "narzedzia.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    wpis = narz.get("libreoffice") if isinstance(narz, dict) else None
    if not isinstance(wpis, dict):
        return None
    sciezka = (wpis.get("env") or {}).get("JARVO_SOFFICE")
    if sciezka and os.path.isfile(sciezka):
        return sciezka
    return _soffice_w(Path(wpis["katalog"])) if wpis.get("katalog") else None


def _soffice_systemu() -> str | None:
    """LibreOffice zainstalowany przez właściciela w typowym miejscu (poza PATH: na Windows i macOS tak jest zawsze)."""
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
        kandydaci += sorted(Path("/opt").glob("libreoffice*"), reverse=True)
        kandydaci.append(Path("/usr/lib/libreoffice"))
    for k in kandydaci:
        if p := _soffice_w(k):
            return p
    return None


def soffice() -> str | None:
    """Program LibreOffice: JARVO_SOFFICE (zmienna procesów Jarva z wpisu dodatku; testy), dodatek z narzedzia.json,
    PATH (obraz z dodatkiem `office`, pakiet systemu; bez snapa), na końcu instalacja właściciela w typowym miejscu."""
    jawny = os.environ.get("JARVO_SOFFICE")
    if jawny and os.path.isfile(jawny):
        return jawny
    return _soffice_dodatku() or _soffice_z_path() or _soffice_systemu()


def _poczatek(p: Path, n: int) -> bytes:
    """Pierwsze `n` bajtów pliku (b"" bez pliku)."""
    try:
        with open(p, "rb") as f:
            return f.read(n)
    except OSError:
        return b""


def wolna_sciezka(p: Path) -> Path:
    """p albo p-2, p-3… (nigdy nie nadpisujemy istniejącego pliku)."""
    if not p.exists():
        return p
    n = 2
    while (q := p.with_name(f"{p.stem}-{n}{p.suffix}")).exists():
        n += 1
    return q


def strony_lista(spec: str | None, liczba: int | None) -> list[int] | None:
    """„1-3,5,8-” → [1, 2, 3, 5, 8, …]; None = wszystkie."""
    if not spec:
        return None
    out: list[int] = []
    for part in str(spec).replace(" ", "").split(","):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)(?:-(\d*))?", part)
        if not m:
            raise Blad(f"Złe --strony „{spec}”: np. 1-3,5 albo 4-")
        a = int(m[1])
        b = a if m[2] is None else (int(m[2]) if m[2] else max(a, liczba or a))
        if a < 1 or b < a:
            raise Blad(f"Złe --strony „{part}”: od 1, koniec nie przed początkiem")
        out.extend(range(a, b + 1))
    if liczba:
        out = [x for x in out if x <= liczba]
        if not out:
            raise Blad(f"PDF ma {liczba} stron: --strony {spec} nie wybiera żadnej")
    return sorted(dict.fromkeys(out))


def liczba_stron(pdf: Path) -> int | None:
    if program("qpdf"):
        try:
            r = _proc(["qpdf", "--show-npages", os.path.abspath(pdf)], timeout=120)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if r.returncode in (0, 3) and r.stdout.strip().isdigit():
            return int(r.stdout.strip())
    return None


# --------------------------------------------------------------------------- silniki

class Silnik:
    nazwa = ""

    def dostepny(self) -> bool:
        return True

    def krawedzie(self) -> list[tuple[str, str, float]]:
        """(z, na, koszt); z == na = zmniejszenie w tym samym formacie (tylko z --rozmiar/--jakosc)."""
        return []

    def zamien(self, src: Path, dst: Path, z: str, na: str, opt: Opcje, tmp: Path) -> list[Path]:
        raise NotImplementedError


PIL_NAZWY = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP", "avif": "AVIF", "gif": "GIF", "tiff": "TIFF",
             "bmp": "BMP", "ico": "ICO", "tga": "TGA", "ppm": "PPM", "qoi": "QOI", "psd": "PSD", "heic": "HEIF",
             "pdf": "PDF"}
ANIMOWANE = {"gif", "webp", "png"}
ICC = {"jpg", "png", "webp", "avif", "tiff", "heic"}


class Pillow(Silnik):
    nazwa = "pillow"

    @functools.cached_property
    def _formaty(self) -> tuple[set[str], set[str]]:
        try:
            from PIL import Image
        except ImportError:
            return set(), set()
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except Exception:        # brak pillow_heif albo stara wersja: HEIC znika z listy
            pass
        Image.init()
        wej = {f for f, n in PIL_NAZWY.items() if n in Image.OPEN and f != "pdf"}
        wyj = {f for f, n in PIL_NAZWY.items() if n in Image.SAVE and f != "psd"}
        return wej, wyj

    def dostepny(self) -> bool:
        return bool(self._formaty[0])

    def krawedzie(self):
        wej, wyj = self._formaty
        return [(a, b, 1.0) for a in wej for b in wyj]

    def zamien(self, src, dst, z, na, opt, tmp):
        if na == "pdf":
            obrazy_do_pdf([src], dst, opt)
        else:
            zapisz_obraz(src, dst, na, opt)
        return [dst]


def _klatki(src: Path, na: str, spec: tuple | None):
    from PIL import Image, ImageOps, ImageSequence
    im = Image.open(src)
    anim = getattr(im, "is_animated", False) and na in ANIMOWANE
    zrodla = [f.copy() for f in ImageSequence.Iterator(im)] if anim else [im]
    czasy = []
    klatki = []
    for f in zrodla:
        czasy.append(f.info.get("duration", im.info.get("duration", 100)))
        f = ImageOps.exif_transpose(f) or f
        w, h = nowy_rozmiar(f.width, f.height, spec)
        if (w, h) != f.size:
            if f.mode == "P":
                f = f.convert("RGBA")
            f = f.resize((w, h), Image.LANCZOS)
        klatki.append(f)
    return im, klatki, czasy, anim


def _tryb(f, na: str):
    from PIL import Image
    alfa = f.mode in ("RGBA", "LA", "PA") or (f.mode == "P" and "transparency" in f.info)
    if na in ("jpg", "bmp", "ppm", "pdf") or (na == "heic" and not alfa):
        if alfa:
            f = f.convert("RGBA")
            tlo = Image.new("RGB", f.size, (255, 255, 255))
            tlo.paste(f, mask=f.split()[-1])
            return tlo
        return f if f.mode in ("RGB", "L") and na != "heic" else f.convert("RGB")
    if na == "gif":
        return f
    if f.mode not in ("RGB", "RGBA", "L", "LA") or (na in ("qoi", "heic", "avif") and f.mode not in ("RGB", "RGBA")):
        return f.convert("RGBA" if alfa else "RGB")
    return f


def zapisz_obraz(src: Path, dst: Path, na: str, opt: Opcje) -> None:
    from PIL import Image
    spec = parse_rozmiar(opt.rozmiar)
    im, klatki, czasy, anim = _klatki(src, na, spec)
    klatki = [_tryb(f, na) for f in klatki]
    q = opt.jakosc or 85
    kw: dict = {}
    icc = im.info.get("icc_profile")
    if icc and na in ICC:
        kw["icc_profile"] = icc
    if na == "jpg":
        kw.update(quality=q, optimize=True, progressive=True)
    elif na in ("webp", "avif", "heic"):
        kw.update(quality=q)
        if na == "heic":   # pillow_heif sam przepisałby EXIF i XMP źródła (z GPS)
            kw.update(exif=None, xmp=None, metadata=[])
    elif na == "png":
        kw.update(optimize=True)
    elif na == "tiff":
        kw.update(compression="tiff_lzw")
    elif na == "ico":
        f = klatki[0].convert("RGBA")
        bok = max(f.size)
        kwadrat = Image.new("RGBA", (bok, bok), (0, 0, 0, 0))   # ikona jest kwadratowa: dopełnienie przezroczystym
        kwadrat.paste(f, ((bok - f.width) // 2, (bok - f.height) // 2))
        klatki = [kwadrat]
        kw.update(sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256) if s <= bok] or [(bok, bok)])
    if anim and len(klatki) > 1:
        kw.update(save_all=True, append_images=klatki[1:], duration=czasy, loop=im.info.get("loop", 0))
        if na == "gif":
            kw.update(disposal=2)
    klatki[0].save(dst, PIL_NAZWY[na], **kw)


def obrazy_do_pdf(srcs: list[Path], dst: Path, opt: Opcje) -> None:
    spec = parse_rozmiar(opt.rozmiar)
    strony = []
    for s in srcs:
        _, klatki, _, _ = _klatki(s, "pdf", spec)
        strony.append(_tryb(klatki[0], "pdf"))
    strony[0].save(dst, "PDF", save_all=True, append_images=strony[1:], resolution=float(opt.dpi))


class FFmpeg(Silnik):
    nazwa = "ffmpeg"

    def dostepny(self) -> bool:
        return bool(program("ffmpeg"))

    @functools.cached_property
    def _kodeki(self) -> tuple[str, str]:
        try:
            enc = _proc(["ffmpeg", "-hide_banner", "-encoders"], timeout=60).stdout
            dec = _proc(["ffmpeg", "-hide_banner", "-decoders"], timeout=60).stdout
        except (OSError, subprocess.TimeoutExpired):
            return "", ""
        return enc, dec

    def ma(self, enc: str) -> bool:
        return re.search(rf"^\s*\S+\s+{re.escape(enc)}\s", self._kodeki[0], re.M) is not None

    def krawedzie(self):
        k = []
        wid = {f for f in WIDEO if f != "webm" or self.ma("libvpx-vp9") or self.ma("libsvtav1")}
        aud = {f for f in AUDIO if (f != "mp3" or self.ma("libmp3lame")) and (f != "opus" or self.ma("libopus"))}
        wej_aud = set(AUDIO)
        for a in WIDEO | {"gif"}:
            for b in wid:
                k.append((a, b, 1.0))
            if a != "gif":
                k.append((a, "gif", 1.0))
                k.extend((a, b, 1.0) for b in aud)
        for a in wej_aud:
            k.extend((a, b, 1.0) for b in aud)
        if re.search(r"^\s*\S+\s+librsvg\s", self._kodeki[1], re.M):
            k.append(("svg", "png", 1.0))
        return k

    def _probe(self, src: Path) -> dict:
        if not program("ffprobe"):
            return {}
        try:
            r = _proc(["ffprobe", "-v", "error", "-show_entries",
                       "stream=codec_type,codec_name,color_transfer,color_primaries,color_space",
                       "-of", "json", str(src)], timeout=300)
        except (OSError, subprocess.TimeoutExpired):
            return {}
        try:
            streams = json.loads(r.stdout or "{}").get("streams", [])
        except ValueError:
            return {}
        return {"v": next((s for s in streams if s.get("codec_type") == "video"), None),
                "a": next((s for s in streams if s.get("codec_type") == "audio"), None), "ok": True}

    def polecenia(self, src: Path, dst: Path, z: str, na: str, opt: Opcje, info: dict) -> list[list[str]]:
        """Polecenia ffmpeg do wykonania po kolei aż do pierwszego udanego (szybkie przepakowanie, potem kodowanie)."""
        v, a = info.get("v"), info.get("a")
        spec = parse_rozmiar(opt.rozmiar)
        wej = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src)]
        if z == "svg":   # librsvg rysuje SVG w jego wymiarach; --rozmiar zmniejsza (bez powiększania, jak w Chromium)
            sk = skala_ffmpeg(spec, parzyste=False)
            return [[*wej, "-frames:v", "1", *(["-vf", sk] if sk else []), "-update", "1", str(dst)]]
        wej += FF_BEZ_METADANYCH
        if na in AUDIO:
            if info.get("ok") and a is None:
                raise Blad("Ten plik nie ma dźwięku: nie ma czego zapisać jako audio.")
            return [[*wej, "-vn", "-map", "0:a:0", *self._audio(na, opt.jakosc), str(dst)]]
        if na == "gif":
            fps = 12
            skala = skala_ffmpeg(spec or ("dluzszy", 480), parzyste=False)
            vf = ",".join(x for x in (_hdr_vf(v), f"fps={fps}", skala) if x)
            return [[*wej, "-an", "-vf", f"{vf},split[a][b];[a]palettegen=stats_mode=diff[p];"
                     "[b][p]paletteuse=dither=bayer:bayer_scale=4", "-loop", "0", str(dst)]]
        out = []
        hdr = _hdr_vf(v)
        kopiuj = (opt.jakosc is None and not spec and not hdr and na in ("mp4", "mov", "mkv")
                  and (v or {}).get("codec_name") == "h264" and (a or {}).get("codec_name") in (None, "aac", "mp3"))
        start = ["-movflags", "+faststart"] if na in ("mp4", "mov") else []
        mapy = ["-map", "0:v:0", "-map", "0:a:0?"]
        if kopiuj:   # ten sam obraz i dźwięk w innym pudełku: sekundy zamiast minut
            out.append([*wej, *mapy, "-c", "copy", *start, str(dst)])
        vf = ",".join(x for x in (hdr, skala_ffmpeg(spec)) if x)
        out.append([*wej, *mapy, "-vf", vf, *self._wideo(na, opt.jakosc), *start, str(dst)])
        return out

    def _wideo(self, na: str, jakosc: int | None) -> list[str]:
        q = 75 if jakosc is None else max(1, min(100, jakosc))
        if na == "webm":
            aud = ["-c:a", "libopus", "-b:a", "128k"] if self.ma("libopus") else ["-c:a", "libvorbis", "-q:a", "5"]
            if self.ma("libvpx-vp9"):
                return ["-c:v", "libvpx-vp9", "-crf", str(round(50 - q * 0.25)), "-b:v", "0", "-row-mt", "1",
                        "-deadline", "good", "-cpu-used", "4", "-pix_fmt", "yuv420p", *aud]
            return ["-c:v", "libsvtav1", "-crf", str(round(50 - q * 0.2)), "-preset", "8", "-pix_fmt", "yuv420p", *aud]
        if na == "avi":
            aud = ["-c:a", "libmp3lame", "-q:a", "3"] if self.ma("libmp3lame") else ["-c:a", "pcm_s16le"]
            return ["-c:v", "mpeg4", "-q:v", str(round(2 + (100 - q) / 12)), *aud]
        return ["-c:v", "libx264", "-preset", "medium", "-crf", str(round(35 - q * 0.18)), "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k"]

    def _audio(self, na: str, jakosc: int | None) -> list[str]:
        kbps = None if jakosc is None else max(64, min(320, round(jakosc * 3.2)))
        if na == "wav":
            return ["-c:a", "pcm_s16le"]
        if na == "flac":
            return ["-c:a", "flac"]
        if na == "mp3":
            return ["-c:a", "libmp3lame", *(["-b:a", f"{kbps}k"] if kbps else ["-q:a", "2"])]
        if na == "ogg":
            return ["-c:a", "libvorbis", *(["-b:a", f"{kbps}k"] if kbps else ["-q:a", "5"])]
        if na == "opus":
            return ["-c:a", "libopus", "-b:a", f"{kbps or 128}k"]
        return ["-c:a", "aac", "-b:a", f"{kbps or 192}k"]          # m4a, aac

    def zamien(self, src, dst, z, na, opt, tmp):
        cmds = self.polecenia(src, dst, z, na, opt, self._probe(src) if z != "svg" else {})
        for i, cmd in enumerate(cmds):
            try:
                _run(cmd, "FFmpeg", 3 * 3600)
                break
            except Blad:
                dst.unlink(missing_ok=True)
                if i == len(cmds) - 1:
                    raise
        return [dst]


def _hdr_vf(v: dict | None) -> str:
    """Film HDR z telefonu (HLG, PQ) → zwykły obraz BT.709 (jak edytor.sdr_filter); "" dla zwykłego filmu."""
    trc = (v or {}).get("color_transfer")
    if trc not in ("arib-std-b67", "smpte2084"):
        return ""
    prim = (v or {}).get("color_primaries") or "bt2020"
    mat = (v or {}).get("color_space") or "bt2020nc"
    return (f"zscale=tin={trc}:pin={prim}:min={mat}:rin=tv:t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
            "tonemap=tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")


def _strony_do_wyniku(pary: list[tuple[int, Path]], dst: Path) -> list[Path]:
    """Obrazy stron (numer strony, plik) → dst (jedna strona) albo dst-03.png… z numerem strony w nazwie."""
    if not pary:
        raise Blad("Nie powstała żadna strona (PDF uszkodzony albo zaszyfrowany?).")
    if len(pary) == 1:
        shutil.move(str(pary[0][1]), dst)
        return [dst]
    szer = max(2, len(str(max(nr for nr, _ in pary))))
    out = []
    for nr, p in pary:
        q = dst.with_name(f"{dst.stem}-{nr:0{szer}d}{dst.suffix}")
        shutil.move(str(p), q)
        out.append(q)
    return out


# --- PDF bez Ghostscriptu (docs/NATYWNIE.md E04): strony i tekst przez PDFium (pypdfium2), mniejszy PDF przez pikepdf
# z Pillow (obrazy zmniejszone do dpi jakości i przeliczone) albo qpdf (obrazy przeliczone na JPEG bez zmiany liczby
# pikseli). Ghostscript (AGPL) zostaje tylko tam, gdzie już jest (obraz Jarva z OCRmyPDF), jako zapas i do mniejszego
# PDF, gdy pikepdf brak. Gdy biblioteki nie ma w tym Pythonie (Konwerter panelu w Pythonie Hermesa), zadanie robi ten
# sam skrypt w Pythonie venvu, który ją ma (_zadanie_w): pypdfium2 w venvie OCR, pikepdf w venvie narzędzi.
MAX_PIKSELI = 100e6     # strona większa niż tyle pikseli w podanym dpi renderuje się w niższym (plakaty, plany)
CZAS_ZADANIA = 1800     # s na zadanie w Pythonie venvu (duży PDF)


def _jest_modul(*nazwy: str) -> bool:
    try:
        return all(importlib.util.find_spec(n) is not None for n in nazwy)
    except (ImportError, ValueError):
        return False


def _pdfium_tutaj() -> bool:
    """pypdfium2 w tym Pythonie i czym zapisać obraz strony (Pillow albo OpenCV z numpy)."""
    return _jest_modul("pypdfium2") and (_jest_modul("PIL") or _jest_modul("cv2", "numpy"))


def _ten_python(sciezka: str) -> bool:
    return os.path.normcase(os.path.abspath(sciezka)) == os.path.normcase(os.path.abspath(sys.executable))


def python_pdfium() -> str | None:
    """Python ze stronami PDF: "" = ten proces (pypdfium2 jest tutaj), ścieżka = Python venvu OCR (JARVO_OCR_PYTHON,
    w obrazie /opt/jarvo/venvs/ocr: pypdfium2, numpy, OpenCV z locka), None = nie ma czym."""
    if _pdfium_tutaj():
        return ""
    for k in (os.environ.get("JARVO_OCR_PYTHON"), OCR_PYTHON_OBRAZU):
        if k and os.path.isfile(k) and not _ten_python(k):
            return k
    return None


def _zapisz_strone(bitmapa, cel: Path, na: str, jakosc: int) -> None:
    """Bitmapa PDFium → PNG albo JPG: Pillow, a bez niego OpenCV (venv OCR). Zapis bajtów przez Pythona, bo
    cv2.imwrite nie otworzy na Windows ścieżki z polskimi znakami."""
    try:
        obraz = bitmapa.to_pil()
    except ImportError:
        obraz = None
    if obraz is not None:
        if na == "jpg":
            obraz.convert("RGB").save(cel, "JPEG", quality=jakosc, optimize=True)
        else:
            obraz.save(cel, "PNG")
        return
    import cv2
    import numpy as np
    tab = np.ascontiguousarray(bitmapa.to_numpy())          # BGR(A) albo szarość: kolejność kanałów OpenCV
    if na == "jpg" and tab.ndim == 3 and tab.shape[2] == 4:
        tab = cv2.cvtColor(tab, cv2.COLOR_BGRA2BGR)
    ok, dane = cv2.imencode(".jpg" if na == "jpg" else ".png", tab,
                            [cv2.IMWRITE_JPEG_QUALITY, jakosc] if na == "jpg" else [])
    if not ok:
        raise Blad(f"Nie zapiszę strony jako {na.upper()}.")
    cel.write_bytes(dane.tobytes())


def wykonaj_pdfium(z: dict) -> dict:
    """Zadanie PDFium w tym procesie: {"rodzaj": "tekst"|"strony", "pdf", "strony" (np. "1-3,5" albo None),
    tekst: "wyjscie"; strony: "katalog", "na" (png|jpg), "dpi", "jakosc"}. Wynik {"liczba", "pliki": [[nr, plik]…]}
    albo {"blad": opis po polsku}."""
    import pypdfium2 as pdfium
    try:
        doc = pdfium.PdfDocument(z["pdf"])          # pypdfium2 5 otwiera też ścieżki z polskimi znakami (Windows)
    except pdfium.PdfiumError as exc:
        if "password" in str(exc).lower():
            return {"blad": "PDF jest zabezpieczony hasłem: zdejmij zabezpieczenie i spróbuj jeszcze raz."}
        return {"blad": f"Nie otworzę PDF (uszkodzony albo to nie PDF): {exc}"}
    try:
        liczba = len(doc)
        try:
            lista = strony_lista(z.get("strony"), liczba)
        except Blad as exc:
            return {"blad": str(exc)}
        if z["rodzaj"] == "tekst":
            teksty = []
            for nr in lista or range(1, liczba + 1):
                strona = doc[nr - 1]
                tp = strona.get_textpage()
                teksty.append(tp.get_text_bounded().replace("\r\n", "\n").replace("\r", "\n").strip("\n"))
                tp.close()
                strona.close()
            Path(z["wyjscie"]).write_text("\n\n".join(teksty) + "\n", encoding="utf-8")
            return {"liczba": liczba, "pliki": [[0, z["wyjscie"]]]}
        if lista is None and liczba > MAX_STRON:
            return {"blad": f"PDF ma {liczba} stron: wybierz strony (--strony 1-20)."}
        doc.init_forms()                            # pola formularzy jak w czytniku (przed pierwszą stroną)
        dpi = max(36.0, min(600.0, float(z.get("dpi") or 150)))
        jakosc = int(z.get("jakosc") or 90)
        katalog, na, pliki = Path(z["katalog"]), z["na"], []
        for nr in lista or range(1, liczba + 1):
            strona = doc[nr - 1]
            w, h = strona.get_size()
            skala = min(dpi / 72.0, (MAX_PIKSELI / max(w * h, 1.0)) ** 0.5)
            bitmapa = strona.render(scale=skala, may_draw_forms=True)
            cel = katalog / f"s-{nr:04d}.{na}"
            _zapisz_strone(bitmapa, cel, na, jakosc)
            bitmapa.close()
            strona.close()
            pliki.append([nr, str(cel)])
        return {"liczba": liczba, "pliki": pliki}
    finally:
        doc.close()


def _zadanie_w(py: str, flaga: str, zadanie: dict, silnik: str, venv: str) -> dict:
    """Ten skrypt w Pythonie `py` z flagą pomocnika (--pdfium-zadanie, --pikepdf-zadanie): zadanie JSON na wejściu,
    wynik JSON w ostatniej linii wyjścia, -I -X utf8 (bez PYTHONPATH, wyjście w UTF-8 także na Windows), bez okna
    konsoli. Blad z opisem, gdy pomocnik nie ruszy albo padnie bez opisu."""
    try:
        r = subprocess.run([py, "-I", "-X", "utf8", os.path.abspath(__file__), flaga],
                           input=json.dumps(zadanie, ensure_ascii=False), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=CZAS_ZADANIA, creationflags=BEZ_OKNA)
    except subprocess.TimeoutExpired:
        raise Blad(f"{silnik}: przekroczony czas ({CZAS_ZADANIA // 60} min)") from None
    except OSError as exc:
        raise Blad(f"{silnik}: nie da się uruchomić Pythona {venv} ({exc})") from None
    linie = (r.stdout or "").strip().splitlines()
    try:
        wynik = json.loads(linie[-1]) if linie else {}
    except ValueError:
        wynik = {}
    wynik = wynik if isinstance(wynik, dict) else {}
    if r.returncode != 0 and not wynik.get("blad"):
        ogon = [x for x in (r.stderr or "").strip().splitlines() if x.strip()][-4:]
        raise Blad(f"{silnik} zakończył się błędem ({r.returncode}):\n" + "\n".join(ogon))
    return wynik


def _pdfium(zadanie: dict) -> dict:
    """Zadanie PDFium tutaj albo w Pythonie venvu OCR (ten sam skrypt z --pdfium-zadanie). Blad z opisem, gdy się nie
    da."""
    py = python_pdfium()
    if py is None:
        raise Blad("Strony i tekst z PDF czyta PDFium (pypdfium2 z venvu OCR instalacji Jarva), a tu go nie ma.")
    wynik = wykonaj_pdfium(zadanie) if py == "" else _zadanie_w(py, "--pdfium-zadanie", zadanie, "PDFium",
                                                                "venvu OCR")
    if wynik.get("blad"):
        raise Blad(wynik["blad"])
    return wynik


class Pdfium(Silnik):
    nazwa = "pdfium"

    def dostepny(self) -> bool:
        return python_pdfium() is not None

    def krawedzie(self):
        return [("pdf", "png", 1.0), ("pdf", "jpg", 1.0), ("pdf", "txt", 1.0)]

    def zamien(self, src, dst, z, na, opt, tmp):
        if na == "txt":
            _pdfium({"rodzaj": "tekst", "pdf": os.path.abspath(src), "strony": opt.strony,
                     "wyjscie": os.path.abspath(dst)})
            return [dst]
        wyj = tmp / f"pdfium-{dst.stem}"
        wyj.mkdir(exist_ok=True)
        w = _pdfium({"rodzaj": "strony", "pdf": os.path.abspath(src), "strony": opt.strony, "katalog": str(wyj),
                     "na": na, "dpi": opt.dpi, "jakosc": opt.jakosc or 90})
        return _strony_do_wyniku([(int(nr), Path(p)) for nr, p in w.get("pliki") or []], dst)


class Qpdf(Silnik):
    """Mniejszy PDF bez Ghostscriptu i bez pikepdf: strumienie od nowa (Flate 9, strumienie obiektów), a obrazy
    (także już w JPEG) przeliczone na JPEG w jakości --jakosc, gdy wychodzi mniej (qpdf 12 --optimize-images
    --jpeg-quality; sprawdzone: skan A4 300 dpi w JPEG 95 przy --jakosc 30 z 1,5 MB do 0,34 MB). Liczby pikseli qpdf
    nie zmienia, więc skan w dużej rozdzielczości zmniejsza bardziej pikepdf albo Ghostscript."""
    nazwa = "qpdf"

    def dostepny(self) -> bool:
        return program("qpdf") is not None

    def krawedzie(self):
        return [("pdf", "pdf", 1.3)]

    def zamien(self, src, dst, z, na, opt, tmp):
        q = 75 if opt.jakosc is None else opt.jakosc
        _run(["qpdf", "--object-streams=generate", "--compression-level=9", "--recompress-flate",
              "--optimize-images", f"--jpeg-quality={q}", os.path.abspath(src), os.path.abspath(dst)],
             "qpdf", 1800, ok=(0, 3))
        return [dst]


# obrazy w PDF, które pikepdf przelicza: 8 bitów, RGB albo szarość, bez maski i własnej tablicy Decode
PIKEPDF_FILTRY = {"/DCTDecode", "/FlateDecode", "/LZWDecode", "/RunLengthDecode"}


def _dpi_jakosci(q: int) -> int:
    """Jakość 1–100 → największe dpi obrazu (jak /screen, /ebook i /printer Ghostscriptu)."""
    return 72 if q <= 40 else 150 if q <= 80 else 300


def mniejszy_pdf(src: Path, dst: Path, jakosc: int | None) -> int:
    """Mniejszy PDF przez pikepdf i Pillow: obrazy większe niż strona w dpi jakości zmniejszone i zapisane jako JPEG,
    gdy wychodzi mniej bajtów. Tekst, wektory i układ bez zmian. Zwraca liczbę przeliczonych obrazów."""
    import pikepdf
    from PIL import Image
    q = 75 if jakosc is None else jakosc
    dpi = _dpi_jakosci(q)
    zmienione, widziane = 0, set()
    with pikepdf.open(src) as pdf:
        for strona in pdf.pages:
            x0, y0, x1, y1 = (float(v) for v in strona.mediabox)
            maks_w, maks_h = abs(x1 - x0) / 72 * dpi, abs(y1 - y0) / 72 * dpi
            # get_images() (pikepdf 10.9+) widzi też obrazy w formularzach XObject; starsze pikepdf: images
            obrazy = strona.get_images() if hasattr(strona, "get_images") else strona.images
            for _, obraz in obrazy.items():
                if obraz.objgen in widziane or obraz.objgen == (0, 0):
                    continue
                widziane.add(obraz.objgen)
                filtry = obraz.get("/Filter")
                filtry = [str(f) for f in (filtry if isinstance(filtry, pikepdf.Array) else [filtry])] if filtry else []
                if (obraz.get("/BitsPerComponent") != 8 or obraz.get("/ImageMask") or "/SMask" in obraz
                        or "/Mask" in obraz or "/Decode" in obraz or not set(filtry) <= PIKEPDF_FILTRY):
                    continue
                try:
                    pil = pikepdf.PdfImage(obraz).as_pil_image()
                except Exception:       # nietypowa przestrzeń barw albo dane: obraz zostaje jak był
                    continue
                if pil.mode not in ("RGB", "L"):
                    continue
                k = min(1.0, maks_w / pil.width, maks_h / pil.height)
                if k < 1.0:
                    pil = pil.resize((max(1, round(pil.width * k)), max(1, round(pil.height * k))), Image.LANCZOS)
                bufor = io.BytesIO()
                pil.save(bufor, "JPEG", quality=q, optimize=True)
                if bufor.tell() >= len(obraz.read_raw_bytes()):
                    continue
                obraz.write(bufor.getvalue(), filter=pikepdf.Name.DCTDecode)
                obraz.Width, obraz.Height = pil.width, pil.height
                obraz.ColorSpace = pikepdf.Name.DeviceRGB if pil.mode == "RGB" else pikepdf.Name.DeviceGray
                obraz.BitsPerComponent = 8
                for klucz in ("/DecodeParms", "/Interpolate"):
                    if klucz in obraz:
                        del obraz[klucz]
                zmienione += 1
        pdf.save(dst, compress_streams=True, recompress_flate=True,
                 object_stream_mode=pikepdf.ObjectStreamMode.generate)
    return zmienione


def wykonaj_pikepdf(z: dict) -> dict:
    """Zadanie pikepdf w tym procesie: {"pdf", "wyjscie", "jakosc"} → {"obrazy": liczba przeliczonych obrazów} albo
    {"blad": opis po polsku}."""
    try:
        return {"obrazy": mniejszy_pdf(Path(z["pdf"]), Path(z["wyjscie"]), z.get("jakosc"))}
    except Blad as exc:
        return {"blad": str(exc)}
    except Exception as exc:          # pikepdf.PasswordError, PdfError: opis po polsku zamiast śladu
        if "password" in type(exc).__name__.lower() or "password" in str(exc).lower():
            return {"blad": "PDF jest zabezpieczony hasłem: zdejmij zabezpieczenie i spróbuj jeszcze raz."}
        return {"blad": f"pikepdf: nie zmniejszę tego PDF ({exc})"}


@functools.lru_cache(maxsize=4)
def _ma_pikepdf(py: str) -> bool:
    """Czy Python `py` importuje pikepdf i Pillow (raz na proces: Konwerter panelu pyta przy każdej trasie)."""
    try:
        return subprocess.run([py, "-I", "-c", "import pikepdf, PIL"], capture_output=True, timeout=60,
                              stdin=subprocess.DEVNULL, creationflags=BEZ_OKNA).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def python_pikepdf() -> str | None:
    """Python z pikepdf i Pillow: "" = ten proces (natywnie venv narzędzi floty), ścieżka = Python venvu narzędzi
    (JARVO_TOOLS_PYTHON; Konwerter panelu działa w Pythonie Hermesa, który pikepdf nie ma), None = nie ma czym (wtedy
    mniejszy PDF robi Ghostscript albo qpdf)."""
    if _jest_modul("pikepdf", "PIL"):
        return ""
    k = os.environ.get("JARVO_TOOLS_PYTHON")
    if k and os.path.isfile(k) and not _ten_python(k) and _ma_pikepdf(os.path.abspath(k)):
        return k
    return None


class Pikepdf(Silnik):
    nazwa = "pikepdf"

    def dostepny(self) -> bool:
        return python_pikepdf() is not None

    def krawedzie(self):
        return [("pdf", "pdf", 1.0)]

    def zamien(self, src, dst, z, na, opt, tmp):
        py = python_pikepdf()
        if py is None:
            raise Blad("Mniejszy PDF z przeliczonymi obrazami robi pikepdf (venv narzędzi Jarva), a tu go nie ma.")
        zadanie = {"pdf": os.path.abspath(src), "wyjscie": os.path.abspath(dst), "jakosc": opt.jakosc}
        wynik = wykonaj_pikepdf(zadanie) if py == "" else _zadanie_w(py, "--pikepdf-zadanie", zadanie, "pikepdf",
                                                                     "venvu narzędzi")
        if wynik.get("blad"):
            raise Blad(wynik["blad"])
        return [dst]


class Ghostscript(Silnik):
    """Zapas tam, gdzie Ghostscript już jest (obraz Jarva z OCRmyPDF): mniejszy PDF z przeliczonymi obrazami bez
    pikepdf, strony i tekst bez PDFium. Natywnie Jarvo go nie instaluje (AGPL, E04)."""
    nazwa = "ghostscript"

    def dostepny(self) -> bool:
        return bool(program("gs"))

    def krawedzie(self):
        return [("pdf", "png", 1.5), ("pdf", "jpg", 1.5), ("pdf", "txt", 1.5), ("pdf", "pdf", 1.1)]

    def zamien(self, src, dst, z, na, opt, tmp):
        gs = ["gs", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-dQUIET"]
        if na == "txt":
            _run([*gs, "-sDEVICE=txtwrite", f"-sOutputFile={dst}", str(src)], "Ghostscript", 600)
            return [dst]
        if na == "pdf":     # mniejszy PDF: obrazy w środku przeliczone, jakość wybiera ustawienie Ghostscriptu
            q = 75 if opt.jakosc is None else opt.jakosc
            ust = "/screen" if q <= 40 else "/ebook" if q <= 80 else "/printer"
            _run([*gs, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.6", f"-dPDFSETTINGS={ust}",
                  f"-sOutputFile={dst}", str(src)], "Ghostscript", 1800)
            return [dst]
        liczba = liczba_stron(src)
        lista = strony_lista(opt.strony, liczba)
        if lista is None and liczba and liczba > MAX_STRON:
            raise Blad(f"PDF ma {liczba} stron: wybierz strony (--strony 1-20).")
        dev = ["-sDEVICE=png16m"] if na == "png" else ["-sDEVICE=jpeg", f"-dJPEGQ={opt.jakosc or 90}"]
        wyj = tmp / f"gs-{dst.stem}"
        wyj.mkdir(exist_ok=True)
        _run([*gs, *dev, f"-r{max(36, min(600, opt.dpi))}", "-dTextAlphaBits=4", "-dGraphicsAlphaBits=4",
              *([f"-sPageList={','.join(map(str, lista))}"] if lista else []),
              f"-sOutputFile={wyj / ('s-%04d.' + na)}", str(src)], "Ghostscript", 1800)
        pliki = sorted(wyj.glob(f"s-*.{na}"))
        if not pliki:
            raise Blad("Ghostscript nie utworzył stron (PDF uszkodzony albo zaszyfrowany?).")
        numery = lista if lista and len(lista) == len(pliki) else list(range(1, len(pliki) + 1))
        return _strony_do_wyniku(list(zip(numery, pliki)), dst)


PANDOC_CZYTA = {"md": "markdown", "html": "html", "docx": "docx", "odt": "odt", "epub": "epub", "rtf": "rtf",
                "txt": "markdown+hard_line_breaks"}
PANDOC_PISZE = {"md": "gfm", "html": "html5", "docx": "docx", "odt": "odt", "epub": "epub3", "rtf": "rtf",
                "txt": "plain"}
PANDOC_MEDIA = {"docx", "odt", "epub"}     # obrazki w środku pliku: wypakowane obok wyniku HTML/Markdown
STYL = """<style>
body{font-family:Inter,"DejaVu Sans",sans-serif;font-size:11pt;line-height:1.5;max-width:780px;margin:32px auto;
padding:0 16px;color:#111}h1,h2,h3{line-height:1.2}table{border-collapse:collapse}td,th{border:1px solid #ccc;
padding:4px 8px}code,pre{font-family:"DejaVu Sans Mono",monospace;font-size:9.5pt}img{max-width:100%}
</style>"""
# Obrazki i surowy HTML z adresem (http, file:), ze ścieżką absolutną albo z „..” wypadają: pandoc wciągnąłby do
# wyniku dowolny plik z dysku (EPUB, DOCX) albo sięgnął do sieci. Jego --sandbox w 3.1 tego nie chroni
# (--embed-resources czyta dalej) i psuje zapis DOCX, więc go nie używamy.
FILTR_LUA = """local function zly(s)
  if s:match("^data:") then return false end
  return s:match("^%a[%w+.-]*:") or s:sub(1, 1) == "/" or s:sub(1, 1) == "\\\\" or s:match("%.%.")
end

function Image(el)
  if zly(el.src) then return pandoc.Str("") end
  return el
end

local function surowy(el)
  if not el.format:match("html") then return el end
  local t = el.text
  for war in t:gmatch("[%w:-]+%s*=%s*[\\"']([^\\"']*)[\\"']") do
    if zly(war) then return {} end
  end
  for war in t:gmatch("[%w:-]+%s*=%s*([^\\"'%s>]+)") do
    if zly(war) then return {} end
  end
  for war in t:gmatch("url%(%s*[\\"']?([^\\"')]+)") do
    if zly(war) then return {} end
  end
  return el
end
RawInline = surowy
RawBlock = surowy
"""


class Pandoc(Silnik):
    nazwa = "pandoc"

    def dostepny(self) -> bool:
        return bool(program("pandoc"))

    def krawedzie(self):
        return [(a, b, 1.0) for a in PANDOC_CZYTA for b in PANDOC_PISZE if a != b]

    def polecenie(self, src: Path, dst: Path, z: str, na: str, opt: Opcje, filtr: Path,
                  dane: Path | None = None) -> list[str]:
        zasoby = os.pathsep.join(dict.fromkeys(str(x.resolve()) for x in (src.parent, opt.zasoby or src.parent)))
        cmd = ["pandoc", "-f", PANDOC_CZYTA[z], "-t", PANDOC_PISZE[na], "-s", "--lua-filter", str(filtr),
               f"--resource-path={zasoby}", "--metadata", f"pagetitle={src.stem}"]
        if dane is not None:
            # pusty katalog danych: bez niego pandoc bierze szablony i init.lua (kod Lua uruchamiany przed filtrem)
            # z katalogu danych użytkownika (%APPDATA%\pandoc, ~/.local/share/pandoc), czyli właściciela albo agenta
            cmd.append(f"--data-dir={dane}")
        if z in PANDOC_MEDIA and na in ("html", "md"):
            cmd.append(f"--extract-media={dst.stem}-media")      # względnie: obok wyniku (cwd = katalog wyniku)
        return [*cmd, "-o", str(dst.resolve()), str(src.resolve())]

    def zamien(self, src, dst, z, na, opt, tmp):
        filtr = tmp / "bezpieczne-obrazki.lua"
        filtr.write_text(FILTR_LUA, encoding="utf-8")
        dane = tmp / "pandoc-dane"
        dane.mkdir(exist_ok=True)
        _run(self.polecenie(src, dst, z, na, opt, filtr, dane), "pandoc", 600, cwd=dst.parent)
        if na == "html":
            t = dst.read_text(encoding="utf-8", errors="replace")
            dst.write_text(t.replace("</head>", STYL + "</head>", 1), encoding="utf-8")
        return [dst]


class _Zasoby(http.server.SimpleHTTPRequestHandler):
    """Serwer druku: /__strona.html = drukowany HTML, reszta tylko z katalogów `korzenie` (katalog HTML i pliku
    źródłowego), więc strona nie sięga po resztę dysku."""
    strona: Path
    korzenie: tuple[Path, ...] = ()
    # SVG zawsze jako image/svg+xml: <img> bez tego typu go nie pokaże, a na Windows mimetypes bierze typy z rejestru
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".svg": "image/svg+xml"}

    def translate_path(self, path: str) -> str:
        rel = unquote(urlsplit(path).path).lstrip("/")
        if rel == "__strona.html":
            return str(self.strona)
        for root in self.korzenie:
            cel = (root / rel).resolve()
            try:
                cel.relative_to(root)
            except ValueError:
                continue
            if cel.is_file():
                return str(cel)
        return str(self.korzenie[0] / "__brak__") if self.korzenie else "/__brak__"

    def log_message(self, *a):  # cicho
        pass


# SVG → PNG w Chromium (docs/NATYWNIE.md E09: FFmpeg z macOS, Martin Riedl, nie ma librsvg): SVG jako <img>, więc bez
# skryptów i bez zasobów spoza pliku (tryb statyczny przeglądarki), zrzut okna w wymiarach SVG
SVG_JEDNOSTKI = {"": 1.0, "px": 1.0, "pt": 4 / 3, "pc": 16.0, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96.0,
                 "q": 96 / 101.6}
SVG_DOMYSLNY = (300, 150)        # <img> z SVG bez wymiarów i bez viewBox (jak w przeglądarce)
PNG = b"\x89PNG\r\n\x1a\n"
# PNG z SVG najwyżej tyle pikseli na bok i w sumie: „plakat” z width="100000" nie zajmie gigabajtów pamięci
MAX_BOK_SVG = 16384
MAX_PIKSELI_SVG = 64e6
_SVG_KORZEN = re.compile(r"<svg\b([^>]*)>", re.I | re.S)
_ATRYBUT = re.compile(r"([\w:.-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')")


def _dlugosc_svg(v: str | None) -> float | None:
    """„210mm”, „800”, „12.5pt” → piksele CSS; procenty, em i „auto” → None (wymiar z viewBox)."""
    m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+(?:e[-+]?\d+)?)\s*(px|pt|pc|mm|cm|in|q)?\s*", v or "", re.I)
    if not m:
        return None
    x = float(m[1]) * SVG_JEDNOSTKI[(m[2] or "").lower()]
    return x if x > 0 else None


def rozmiar_svg(src: Path) -> tuple[float, float]:
    """Wymiary SVG w pikselach CSS z atrybutów width i height korzenia, brakujący z proporcji viewBox, bez obu:
    viewBox, a bez niczego 300×150. Czyta tylko początek pliku (do znacznika <svg>), bez parsera XML."""
    with open(src, "rb") as f:
        poczatek = f.read(1 << 16).decode("utf-8", "replace")
    m = _SVG_KORZEN.search(poczatek)
    if not m:
        raise Blad(f"{src.name}: to nie wygląda na SVG (brak znacznika <svg>).")
    atr = {k.lower(): a if a or not b else b for k, a, b in _ATRYBUT.findall(m[1])}
    w, h = _dlugosc_svg(atr.get("width")), _dlugosc_svg(atr.get("height"))
    vb = [float(x) for x in re.split(r"[\s,]+", atr.get("viewbox", "").strip())
          if re.fullmatch(r"-?(?:\d+\.?\d*|\.\d+)", x)]
    proporcja = vb[2] / vb[3] if len(vb) == 4 and vb[2] > 0 and vb[3] > 0 else None
    if w and h:
        return w, h
    if proporcja:
        if w:
            return w, w / proporcja
        if h:
            return h * proporcja, h
        return vb[2], vb[3]
    return w or SVG_DOMYSLNY[0], h or SVG_DOMYSLNY[1]


def wymiary_zrzutu(src: Path, opt: Opcje) -> tuple[int, int]:
    """Piksele PNG z SVG: wymiary SVG, --rozmiar (bez powiększania, jak dla zdjęć), najwyżej MAX_BOK_SVG
    i MAX_PIKSELI_SVG."""
    w, h = rozmiar_svg(src)
    w, h = nowy_rozmiar(max(1, round(w)), max(1, round(h)), parse_rozmiar(opt.rozmiar))
    k = min(1.0, MAX_BOK_SVG / max(w, h), (MAX_PIKSELI_SVG / (w * h)) ** 0.5)
    return max(1, round(w * k)), max(1, round(h * k))


class Chromium(Silnik):
    nazwa = "chromium"

    def dostepny(self) -> bool:
        return chromium() is not None

    def krawedzie(self):
        # SVG → PNG drożej niż FFmpeg z librsvg (obraz, Windows, Linux): Chromium tylko tam, gdzie librsvg brak (macOS)
        return [("html", "pdf", 1.0), ("svg", "png", 1.2)]

    @staticmethod
    def _wspolne(profil: str, bez: bool) -> list[str]:
        """Strona z http://127.0.0.1 nie sięga po file://, a martwe proxy odcina internet (127.0.0.1 omija proxy);
        --no-sandbox tylko tam, gdzie piaskownica nie ruszy (bez_piaskownicy)."""
        return [chromium() or "chromium", "--headless", *(["--no-sandbox"] if bez else []), "--disable-gpu",
                "--disable-extensions", "--no-first-run", f"--user-data-dir={profil}", "--proxy-server=127.0.0.1:9"]

    @staticmethod
    def polecenie(dst: Path, adres: str, profil: str, bez: bool) -> list[str]:
        """Druk strony do PDF."""
        return [*Chromium._wspolne(profil, bez), "--no-pdf-header-footer", "--virtual-time-budget=5000",
                f"--print-to-pdf={dst.resolve()}", adres]

    @staticmethod
    def polecenie_zrzutu(dst: Path, adres: str, profil: str, bez: bool, w: int, h: int) -> list[str]:
        """Zrzut okna w × h px z przezroczystym tłem (SVG → PNG)."""
        return [*Chromium._wspolne(profil, bez), "--hide-scrollbars", "--force-device-scale-factor=1",
                "--default-background-color=00000000", f"--window-size={w},{h}", "--virtual-time-budget=5000",
                f"--screenshot={dst.resolve()}", adres]

    def _drukuj(self, dst: Path, adres: str, bez: bool) -> None:
        with tempfile.TemporaryDirectory(prefix="konwertuj-chrome-", ignore_cleanup_errors=True) as profil:
            _run(self.polecenie(dst, adres, profil, bez), "Chromium", 300)

    def _zrzut(self, dst: Path, adres: str, bez: bool, w: int, h: int) -> None:
        with tempfile.TemporaryDirectory(prefix="konwertuj-chrome-", ignore_cleanup_errors=True) as profil:
            _run(self.polecenie_zrzutu(dst, adres, profil, bez, w, h), "Chromium", 300)

    @staticmethod
    def _z_serwerem(strona: Path, korzenie: tuple[Path, ...], wykonaj) -> None:
        """`wykonaj(adres, bez)` ze stroną z lokalnego serwera (tylko `korzenie`). Linux, na którym piaskownica jednak
        nie ruszyła (np. przestrzenie nazw wyłączone inaczej, niż widzi bez_piaskownicy): drugi raz bez niej."""
        handler = type("H", (_Zasoby,), {"strona": strona, "korzenie": korzenie})
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        bez = bez_piaskownicy()
        try:
            while True:
                try:
                    wykonaj(f"http://127.0.0.1:{srv.server_address[1]}/__strona.html", bez)
                    break
                except Blad as exc:
                    if bez or not _linux() or not PIASKOWNICA_BLAD.search(str(exc)):
                        raise
                    bez = True
        finally:
            srv.shutdown()
            srv.server_close()

    def _svg(self, src: Path, dst: Path, opt: Opcje, tmp: Path) -> list[Path]:
        w, h = wymiary_zrzutu(src, opt)
        strona = tmp / f"svg-{dst.stem}.html"
        strona.write_text('<!doctype html><meta charset="utf-8"><style>html,body{margin:0;padding:0;'
                          'background:transparent;overflow:hidden}img{display:block;width:%dpx;height:%dpx}</style>'
                          '<img alt="" src="/%s">' % (w, h, quote(src.name)), encoding="utf-8")
        self._z_serwerem(strona.resolve(), (src.parent.resolve(),),
                         lambda adres, bez: self._zrzut(dst, adres, bez, w, h))
        if _poczatek(dst, 8) != PNG:
            dst.unlink(missing_ok=True)
            raise Blad("Chromium nie utworzył PNG z tego SVG.")
        return [dst]

    def zamien(self, src, dst, z, na, opt, tmp):
        if z == "svg":
            return self._svg(src, dst, opt, tmp)
        korzenie = tuple(dict.fromkeys(x.resolve() for x in (src.parent, opt.zasoby or src.parent)))
        self._z_serwerem(src.resolve(), korzenie, lambda adres, bez: self._drukuj(dst, adres, bez))
        if not dst.exists() or dst.stat().st_size == 0:
            raise Blad("Chromium nie utworzył PDF.")
        return [dst]


LO_TEKST, LO_ARKUSZ, LO_SLAJDY = {"doc", "docx", "odt", "rtf"}, {"xls", "xlsx", "ods", "csv"}, {"ppt", "pptx", "odp"}
LO_FILTR = {"csv": "csv:Text - txt - csv (StarCalc):44,34,76,1"}


class LibreOffice(Silnik):
    nazwa = "libreoffice"

    def dostepny(self) -> bool:
        return soffice() is not None

    def krawedzie(self):
        k = []
        for grupa, wyj in ((LO_TEKST, {"pdf", "docx", "odt", "rtf"}), (LO_ARKUSZ, {"pdf", "xlsx", "ods", "csv"}),
                           (LO_SLAJDY, {"pdf", "pptx", "odp"})):
            k.extend((a, b, 0.9) for a in grupa for b in wyj if a != b)   # wierniejszy niż pandoc: wygrywa remis
        return k

    def zamien(self, src, dst, z, na, opt, tmp):
        wyj = tmp / f"lo-{dst.stem}"
        wyj.mkdir(exist_ok=True)
        _run([soffice(), f"-env:UserInstallation={(tmp / 'lo-profil').as_uri()}", "--headless", "--norestore",
              *(["--infilter=CSV:44,34,76,1"] if z == "csv" else []),
              "--convert-to", LO_FILTR.get(na, na), "--outdir", str(wyj), str(src)], "LibreOffice", 600)
        gotowe = wyj / f"{src.stem}.{na}"
        if not gotowe.exists():
            raise Blad(f"LibreOffice nie utworzył {na.upper()} z {src.name}.")
        shutil.move(str(gotowe), dst)
        return [dst]


# kolejność rozstrzyga tylko remis kosztów (pierwszy wygrywa)
SILNIKI: list[Silnik] = [Pillow(), FFmpeg(), Pdfium(), Pikepdf(), Ghostscript(), Qpdf(), Pandoc(), Chromium(),
                         LibreOffice()]


# --------------------------------------------------------------------------- trasy

@functools.lru_cache(maxsize=4)
def _graf_z(libreoffice: bool) -> dict[str, list[tuple[str, float, str]]]:
    g: dict[str, list[tuple[str, float, str]]] = {}
    for s in SILNIKI:
        if not s.dostepny():
            continue
        for a, b, koszt in s.krawedzie():
            g.setdefault(a, []).append((b, koszt, s.nazwa))
    return g


def _graf() -> dict[str, list[tuple[str, float, str]]]:
    """Krawędzie dostępnych silników, liczone raz na proces, ale od nowa, gdy pojawi się albo zniknie LibreOffice:
    Konwerter panelu żyje długo, a właściciel instaluje LibreOffice po radzie z komunikatu."""
    return _graf_z(soffice() is not None)


_graf.cache_clear = _graf_z.cache_clear       # type: ignore[attr-defined]  (testy i proces panelu po zmianie silników)


def silnik(nazwa: str) -> Silnik:
    return next(s for s in SILNIKI if s.nazwa == nazwa)


def trasy(z: str) -> dict[str, list[tuple[str, str, str]]]:
    """Najtańsze trasy z formatu `z` do każdego osiągalnego formatu (najwyżej MAX_KROKOW kroków)."""
    g = _graf()
    best: dict[str, list] = {}
    kolejka = [(0.0, 0, z, [])]
    widziane: dict[tuple[str, int], float] = {}
    while kolejka:
        koszt, n, f, droga = heapq.heappop(kolejka)
        if f != z and f not in best:
            best[f] = droga
        if n == MAX_KROKOW or (f != z and f not in PRZEJSCIOWE):
            continue
        for b, k, sil in g.get(f, []):
            if b == f or b == z or (n > 0 and (f, b) in TYLKO_PIERWSZY):
                continue
            klucz = (b, n + 1)
            nowy = koszt + k
            if widziane.get(klucz, 1e9) <= nowy:
                continue
            widziane[klucz] = nowy
            heapq.heappush(kolejka, (nowy, n + 1, b, droga + [(f, b, sil)]))
    return best


def trasa(z: str, na: str, opt: Opcje | None = None) -> list[tuple[str, str, str]] | None:
    if z == na:
        if not (opt and opt.zmienia()):
            return None
        # najtańszy silnik zmniejszenia w tym formacie (PDF: pikepdf, potem Ghostscript, na końcu qpdf)
        sil = min(((k, i, s) for i, (b, k, s) in enumerate(_graf().get(z, [])) if b == z), default=None)
        return [(z, z, sil[2])] if sil else None
    return trasy(z).get(na)


def rada_libreoffice() -> str:
    """Skąd wziąć LibreOffice (dokończenie zdania „… wymagają LibreOffice: ”): w obrazie dodatek `office`, natywnie
    zwykła instalacja na tym komputerze, którą Jarvo znajduje sam (bez zmiennych i bez restartu)."""
    if not natywnie():
        return "dodatek obrazu `office` (JARVO_EXTRAS)."
    if any((p := program(n)) and ze_snapa(p) for n in ("soffice", "libreoffice")):
        return ("ten ze snapa nie widzi plików Jarva (piaskownica snapa), więc zainstaluj LibreOffice z pakietów "
                "systemu (np. apt install libreoffice) albo z libreoffice.org.")
    return ("zainstaluj go na tym komputerze zwykłym instalatorem z libreoffice.org; Jarvo znajdzie go sam "
            "(Program Files, Aplikacje, pakiet systemu albo /opt), bez żadnych ustawień.")


def podpowiedz(z: str, na: str) -> str:
    if (na in LO_ARKUSZ | LO_SLAJDY | {"doc"} or z in LO_ARKUSZ | LO_SLAJDY | {"doc"}) and not soffice():
        return f" Arkusze, prezentacje i stare pliki Office wymagają LibreOffice: {rada_libreoffice()}"
    if z == "pdf" and FORMATY[na][0] in ("dokument", "tekst", "arkusz", "prezentacja"):
        return (" Z PDF nie zrobisz Worda ani arkusza: sam tekst daje --na txt (skan bez tekstu: skill odczyt-ekranu, "
                "ocr.py).")
    if FORMATY[z][0] in ("wideo", "audio") and FORMATY[na][0] in ("obraz", "pdf", "dokument", "tekst"):
        return " Z filmu i dźwięku da się zrobić tylko inny film, GIF albo dźwięk."
    return ""


# --------------------------------------------------------------------------- konwersja

def _rozmiar(pliki: list[Path]) -> int:
    return sum(p.stat().st_size for p in pliki if p.exists())


def cel_sciezka(src: Path, na: str, dst: Path | None, katalog: Path | None) -> Path:
    if dst:
        return wolna_sciezka(dst if norm(dst.suffix) == na else dst.with_suffix(f".{na}"))
    return wolna_sciezka((katalog or src.parent) / f"{src.stem}.{na}")


def _baza(p: Path) -> str:
    return re.sub(r"^krok\d+-\d+-", "", p.stem)


def konwertuj(src: Path, na: str, dst: Path | None = None, katalog: Path | None = None,
              opt: Opcje | None = None) -> dict:
    """Jeden plik → format `na`. Zwraca {wejscie, na, trasa, pliki, rozmiar_przed, rozmiar_po, sek}."""
    t0 = time.monotonic()
    src = Path(src)
    if not src.is_file():
        raise Blad(f"Nie ma pliku: {src}")
    opt = opt or Opcje()
    if opt.zasoby is None:
        opt.zasoby = src.parent
    z, na = format_pliku(src), norm(na)
    if na not in FORMATY:
        raise Blad(f"Nie znam formatu „{na}”. Formaty: python3 konwertuj.py --formaty")
    parse_rozmiar(opt.rozmiar)
    kroki = trasa(z, na, opt)
    if not kroki:
        if z == na:
            raise Blad(f"Plik już jest w formacie {FORMATY[na][1]}. Żeby go zmniejszyć, podaj --rozmiar albo --jakosc.")
        raise Blad(f"Nie umiem zamienić {FORMATY[z][1]} na {FORMATY[na][1]}.{podpowiedz(z, na)}")
    out = cel_sciezka(src, na, Path(dst) if dst else None, Path(katalog) if katalog else None)
    if out.resolve() == src.resolve():
        raise Blad("Wynik nadpisałby plik źródłowy: podaj inną nazwę (-o).")
    out.parent.mkdir(parents=True, exist_ok=True)
    # ignore_cleanup_errors: na Windows proces potomny (Chromium, soffice.bin) bywa przez chwilę jeszcze przy pliku
    with tempfile.TemporaryDirectory(prefix="konwertuj-", ignore_cleanup_errors=True) as t:
        tmp = Path(t)
        biezace = [src]
        for i, (a, b, sil) in enumerate(kroki):
            nastepne = []
            for nr, plik in enumerate(biezace):   # strony PDF idą dalej każda osobno, z numerem w nazwie
                baza = out.stem if i == 0 else _baza(plik)
                nastepne.extend(silnik(sil).zamien(plik, tmp / f"krok{i}-{nr}-{baza}.{b}", a, b, opt, tmp))
            biezace = nastepne
        wyniki = []
        for p in biezace:
            q = out if len(biezace) == 1 else wolna_sciezka(out.with_name(f"{_baza(p)}{out.suffix}"))
            shutil.move(str(p), q)
            wyniki.append(q)
    if FORMATY[z][0] in ("obraz", "wideo", "audio"):
        _dopilnuj(wyniki)
    przed, po = src.stat().st_size, _rozmiar(wyniki)
    wynik = {"wejscie": src.as_posix(), "na": na, "trasa": [f"{a}→{b} ({s})" for a, b, s in kroki],   # „/” też na Windows
             "pliki": [p.as_posix() for p in wyniki], "rozmiar_przed": przed, "rozmiar_po": po,
             "sek": round(time.monotonic() - t0, 2)}
    if z == na and po >= przed:
        wynik["uwaga"] = "wynik nie jest mniejszy od oryginału: zostaw oryginał"
    return wynik


def polacz(srcs: list[Path], dst: Path, opt: Opcje | None = None) -> dict:
    """Kilka plików (zdjęcia, PDF, dokumenty) → jeden PDF w podanej kolejności."""
    t0 = time.monotonic()
    opt = opt or Opcje()
    srcs = [Path(s) for s in srcs]
    if len(srcs) < 2:
        raise Blad("Do łączenia potrzeba co najmniej dwóch plików.")
    for s in srcs:
        if not s.is_file():
            raise Blad(f"Nie ma pliku: {s}")
    dst = wolna_sciezka(Path(dst).with_suffix(".pdf"))
    dst.parent.mkdir(parents=True, exist_ok=True)
    formaty = [format_pliku(s) for s in srcs]
    pil = silnik("pillow")
    if all(f in pil._formaty[0] for f in formaty) and pil.dostepny():
        obrazy_do_pdf(srcs, dst, opt)
    else:
        if not program("qpdf"):
            raise Blad("Łączenie PDF wymaga qpdf (jest w instalacji Jarva).")
        with tempfile.TemporaryDirectory(prefix="polacz-", ignore_cleanup_errors=True) as t:
            czesci = []
            for i, (s, f) in enumerate(zip(srcs, formaty)):
                if f == "pdf":
                    czesci.append(s)
                    continue
                r = konwertuj(s, "pdf", dst=Path(t) / f"{i:03d}.pdf", opt=Opcje(dpi=opt.dpi, zasoby=s.parent))
                czesci.extend(Path(p) for p in r["pliki"])
            _run(["qpdf", "--empty", "--pages", *(os.path.abspath(c) for c in czesci), "--", os.path.abspath(dst)],
                 "qpdf", 600, ok=(0, 3))
    return {"wejscie": [s.as_posix() for s in srcs], "na": "pdf", "trasa": ["połączenie w jeden PDF"], "pliki": [dst.as_posix()],
            "rozmiar_przed": _rozmiar(srcs), "rozmiar_po": _rozmiar([dst]), "sek": round(time.monotonic() - t0, 2)}


def cele(src_fmt: str) -> list[dict]:
    """Na co można zamienić format: [{format, grupa, nazwa, opis, kroki, trasa}] pogrupowane jak FORMATY."""
    z = norm(src_fmt)
    if z not in FORMATY:
        raise Blad(f"Nie znam formatu „{src_fmt}”.")
    t = trasy(z)
    kolej = list(FORMATY)
    out = []
    for f in sorted(t, key=lambda f: (GRUPY.index(FORMATY[f][0]), kolej.index(f))):
        g, n, o = FORMATY[f]
        out.append({"format": f, "grupa": g, "nazwa": n, "opis": o, "kroki": len(t[f]),
                    "trasa": [f"{a}→{b} ({s})" for a, b, s in t[f]]})
    return out


def _gdzie(py: str | None) -> str | None:
    return None if py is None else "ten Python" if py == "" else Path(py).as_posix()


def formaty() -> dict:
    """Silniki i formaty dostępne tutaj; `pomocnicy`: gdzie biegną PDFium i pikepdf (ten Python albo Python venvu)."""
    g = _graf()
    wej = {a for a in g}
    wyj = {b for kr in g.values() for b, _, _ in kr}
    return {"silniki": {s.nazwa: s.dostepny() for s in SILNIKI},
            "python": Path(sys.executable).as_posix(),
            "pomocnicy": {"pdfium": _gdzie(python_pdfium()), "pikepdf": _gdzie(python_pikepdf())},
            "formaty": [{"format": f, "grupa": g_, "nazwa": n, "opis": o, "odczyt": f in wej, "zapis": f in wyj}
                        for f, (g_, n, o) in FORMATY.items()],
            "rozszerzenia": sorted({*FORMATY, *ALIASY})}


# --------------------------------------------------------------------------- metadane

FOTO_META = {"jpg", "png", "webp", "heic", "avif", "tiff", "gif"}   # exiftool czyści je bez ponownego kodowania
PAKIETY = {"docx", "xlsx", "pptx", "odt", "ods", "odp"}   # ZIP z XML: właściwości czytamy i czyścimy sami
DOKUMENTY_META = {"pdf"} | PAKIETY
BEZ_KONTROLI = re.compile(r"^(System|File|Composite|ExifTool|ICC.*)$")   # spoza pliku, wyliczone albo celowo zostaje
ZAWSZE = {"File:Comment"}   # komentarz JPG/GIF exiftool podaje w grupie File
WRAZLIWE = (   # (klucz, opis, nazwy tagów exiftool); pierwsza pasująca kategoria wygrywa
    ("miejsce", "miejsce (GPS)", r"GPS\w*|\w*Location\w*|\w*Coordinates|\w*ISO6709|City|Country\w*|State|"
                                r"Province-State|Sub-?location"),
    ("urzadzenie", "telefon albo aparat", r"Make|Model|LensMake|LensModel|LensInfo|LensID|Software|HostComputer|"
                                         r"CameraModelName|UniqueCameraModel|Android\w+|\w*SerialNumber\w*"),
    ("czas", "data i godzina", r"DateTimeOriginal|CreateDate|CreationDate|CreationTime|ModifyDate|DateTimeDigitized|"
                               r"DateCreated|DateTimeCreated|DigitalCreation\w+|TimeCreated|MetadataDate|DateTime|"
                               r"SubSec\w+|OffsetTime\w*|Track(Create|Modify)Date|Media(Create|Modify)Date|"
                               r"ContentCreateDate|RecordingTime|Date|LastPrinted|PrintDate"),
    ("firma", "firma, program albo szablon", r"Company|Manager|Application|AppVersion|Template|CreatorTool|Generator|"
                                            r"HyperlinkBase"),
    ("historia", "historia zmian (wersje, czas edycji)", r"RevisionNumber|TotalEditTime|EditingCycles|EditingDuration"),
    ("osoba", "autor albo właściciel", r"Artist|Author|Creator|InitialCreator|PrintedBy|Creator(Address|City|Country|WorkEmail|WorkTelephone|"
                                     r"WorkURL)|By-line|Copyright|CopyrightNotice|Rights|OwnerName|CameraOwnerName|"
                                     r"XPAuthor|LastModifiedBy|Credit|Publisher|PersonInImage|"
                                     r"Region(Name|PersonDisplayName)|AlbumArtist|Composer|Performer|Band|"
                                     r"Writer-Editor|Director|Producer"),
    ("opis", "opis, tytuł albo komentarz", r"ImageDescription|Description|Title|Subject|Keywords|Comment|UserComment|"
                                          r"XP(Comment|Keywords|Subject|Title)|Caption-Abstract|Headline|Label|Album|"
                                          r"ObjectName|SpecialInstructions|Notes|Lyrics\w*"),
    ("identyfikator", "identyfikatory zdjęcia", r"\w*(UUID|UniqueID|DocumentID|InstanceID|ContentIdentifier|RequestID)\w*"),
    ("miniatura", "miniatura w środku pliku", r"Thumbnail\w*|PreviewImage\w*|OtherImage\w*|MPImage\d*|CoverArt|Picture"),
    ("wlasne", "własne pola dokumentu", r"(?!)"),   # tylko przez grupę Custom (niżej)
)
# kategoria po grupie i nazwie, przed wzorami: w PDF Creator i Producer to program, a nie osoba
PO_GRUPIE = {("PDF", "Creator"): "firma", ("PDF", "Producer"): "firma", ("XMP-pdf", "Producer"): "firma"}
GRUPA_KATEGORIA = {"Custom": "wlasne"}
_WRAZLIWE = [(k, o, re.compile(rf"^(?:{w})$")) for k, o, w in WRAZLIWE]
_DATA = re.compile(r"^(\d{4})[:-](\d\d)[:-](\d\d)(?:[ T](\d\d):(\d\d))?")


def _zero_data(v) -> bool:
    """„0000:00:00 00:00:00” (pusta data w nagłówku filmu) to brak daty."""
    return not re.search(r"[1-9]", str(v))


def _tekst(v, n: int = 60) -> str:
    t = re.sub(r"\s+", " ", ", ".join(map(str, v)) if isinstance(v, list) else str(v)).strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def _exiftool(argumenty: list, timeout: int = 600) -> subprocess.CompletedProcess:
    """exiftool z argumentami z wejścia (`-@ -`, jeden w wierszu, UTF-8) i `-charset filename=utf8`. Na Windows
    exiftool.exe (Perl) dostaje wiersz poleceń w stronie kodowej ANSI: ścieżka ze znakiem spoza niej (np. „ł”
    przy stronie 1252) zamienia się w „?”, a plik „nie istnieje” (sprawdzone na Windows 11 z exiftool 13.59).
    Z wejścia czyta UTF-8 na każdym systemie, bez pliku tymczasowego (jego ścieżka też mogłaby mieć polskie znaki)."""
    argumenty = [str(a) for a in argumenty]
    if any("\n" in a or "\r" in a for a in argumenty):
        raise Blad("exiftool: nazwa pliku ze znakiem końca linii")
    return _run(["exiftool", "-@", "-"], "exiftool", timeout,
                wejscie="\n".join(["-charset", "filename=utf8", *argumenty]) + "\n")


def _exiftool_json(p: Path) -> dict:
    r = _exiftool(["-j", "-G1", "-a", "-s", "-n", "-m", "-api", "LargeFileSupport=1", os.path.abspath(p)])
    try:
        dane = json.loads(r.stdout or "[]")
    except ValueError:
        raise Blad("exiftool: nieczytelny wynik") from None
    return dane[0] if dane else {}


# --- dokumenty Office i LibreOffice: właściwości w XML wewnątrz ZIP-a (bez exiftoola i bez dodatkowych paczek)
OOXML_META = ("docProps/core.xml", "docProps/app.xml", "docProps/custom.xml")
ODF_META = ("meta.xml",)
MAX_XML = 8 << 20   # część z właściwościami większa niż 8 MB to nie dokument, tylko pułapka
NAZWY_XML = {"creator": "Creator", "lastModifiedBy": "LastModifiedBy", "created": "CreateDate",
             "modified": "ModifyDate", "revision": "RevisionNumber", "lastPrinted": "LastPrinted",
             "TotalTime": "TotalEditTime", "keywords": "Keywords", "keyword": "Keywords",
             "creation-date": "CreationDate", "print-date": "PrintDate", "printed-by": "PrintedBy",
             "initial-creator": "InitialCreator", "editing-cycles": "EditingCycles",
             "editing-duration": "EditingDuration", "generator": "Generator", "date": "Date"}
PUSTE_XML = {
    "docProps/core.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<cp:coreProperties xmlns:cp='
                         '"http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc='
                         '"http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype='
                         '"http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                         '</cp:coreProperties>',
    "docProps/app.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Properties xmlns='
                        '"http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt='
                        '"http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"></Properties>',
    "docProps/custom.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Properties xmlns='
                           '"http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" xmlns:vt='
                           '"http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"></Properties>',
}
# komentarze i śledzone zmiany: treść z nazwiskami, której nie usuwamy (tylko mówimy, że jest)
TRESC_Z_NAZWISKAMI = (
    (re.compile(r"^(word/comments\w*\.xml|xl/comments\d*\.xml|xl/threadedComments/.+|ppt/comments/.+|"
                r"ppt/commentAuthors\.xml)$"), re.compile(rb"<(\w+:)?(comment|threadedComment|cm|cmAuthor)[ >]"),
     "komentarze z nazwiskami autorów"),   # pusty comments.xml (pandoc dodaje go zawsze) się nie liczy
    (re.compile(r"^word/document\.xml$"), re.compile(rb"<w:(ins|del) "), "śledzone zmiany z nazwiskami autorów"),
    (re.compile(r"^content\.xml$"), re.compile(rb"<office:annotation[ >]"), "komentarze z nazwiskami autorów"),
    (re.compile(r"^content\.xml$"), re.compile(rb"<text:changed-region[ >]"), "śledzone zmiany z nazwiskami autorów"),
)


def _lokalna(tag: str) -> str:
    return tag.rpartition("}")[2]


def _czytaj_xml(z: zipfile.ZipFile, nazwa: str):
    import xml.etree.ElementTree as ET
    try:
        info = z.getinfo(nazwa)
    except KeyError:
        return None
    if info.file_size > MAX_XML:
        raise Blad(f"{nazwa} w dokumencie ma {info.file_size >> 20} MB: to nie wygląda na zwykły dokument.")
    try:
        return ET.fromstring(z.read(info))
    except ET.ParseError:
        raise Blad(f"Uszkodzony dokument: nieczytelny {nazwa}.") from None


def _pakiet_json(p: Path) -> dict:
    """Właściwości DOCX/XLSX/PPTX/ODT/ODS/ODP w kształcie wyniku exiftoola: {"XML:Creator": …, "Custom:Klient": …}."""
    tagi: dict = {}
    try:
        with zipfile.ZipFile(p) as z:
            for nazwa in (*OOXML_META, *ODF_META):
                root = _czytaj_xml(z, nazwa)
                if root is None:
                    continue
                if nazwa == "meta.xml":
                    root = next((x for x in root if _lokalna(x.tag) == "meta"), root)
                for el in root:
                    loc = _lokalna(el.tag)
                    atr = {_lokalna(k): v for k, v in el.attrib.items()}
                    if loc in ("property", "user-defined"):           # własne pola (OOXML, ODF)
                        wart = "".join(el.itertext()).strip()
                        if atr.get("name") and wart:
                            tagi[f"Custom:{atr['name']}"] = wart
                    elif loc == "template" and atr.get("href"):        # szablon ODF w atrybucie
                        tagi["XML:Template"] = atr["href"]
                    elif len(el) == 0 and (el.text or "").strip():
                        tagi[f"XML:{NAZWY_XML.get(loc, loc[:1].upper() + loc[1:])}"] = el.text.strip()
            if z.comment:
                tagi["ZIP:Comment"] = z.comment.decode("utf-8", "replace")
    except (zipfile.BadZipFile, zlib.error, EOFError, OSError) as exc:
        raise Blad(f"Uszkodzony dokument ({p.name}): {exc}") from None
    return tagi


def _uwagi_tresci(p: Path) -> list[str]:
    """Co z nazwiskami zostaje w treści dokumentu (komentarze, śledzone zmiany): mówimy, nie ruszamy."""
    out: list[str] = []
    try:
        with zipfile.ZipFile(p) as z:
            for info in z.infolist():
                for nazwa, wzor, opis in TRESC_Z_NAZWISKAMI:
                    if opis in out or not nazwa.match(info.filename):
                        continue
                    with z.open(info) as f:      # po kawałku: duży dokument nie trafia cały do pamięci
                        ogon = b""
                        while blok := f.read(1 << 20):
                            if wzor.search(ogon + blok):
                                out.append(opis)
                                break
                            ogon = blok[-64:]
    except (zipfile.BadZipFile, zlib.error, EOFError, OSError):
        return []
    kolejnosc = [o for *_, o in TRESC_Z_NAZWISKAMI]
    return sorted(out, key=kolejnosc.index)


def _odczyt(p: Path) -> dict:
    return _pakiet_json(p) if format_pliku(p) in PAKIETY else _exiftool_json(p)


def _wpisy(tagi: dict) -> set[str]:
    """Wpisy z samego pliku (bez nazwy i dat pliku na dysku, wyliczonych i profilu kolorów)."""
    return {k for k in tagi if k in ZAWSZE or (":" in k and not BEZ_KONTROLI.match(k.rpartition(":")[0]))}


def kategorie(tagi: dict) -> dict[str, list[str]]:
    """Wrażliwe wpisy z wyniku exiftool (-j -G1 -n) pogrupowane: {miejsce: [tagi], urzadzenie: […], …}."""
    out: dict[str, list[str]] = {}
    for klucz in sorted(_wpisy(tagi)):
        v = tagi[klucz]
        if v is None or not _tekst(v).strip(" ,"):
            continue
        grupa, _, nazwa = klucz.rpartition(":")
        if k := PO_GRUPIE.get((grupa, nazwa)) or GRUPA_KATEGORIA.get(grupa):
            out.setdefault(k, []).append(klucz)
            continue
        for k, _, wzor in _WRAZLIWE:
            if wzor.match(nazwa):
                if k != "czas" or not _zero_data(v):
                    out.setdefault(k, []).append(klucz)
                break
    return out


def _pokaz(k: str, tagi: dict, klucze: list[str]) -> str:
    """Krótko, co jest w pliku: „50.0614, 19.9366”, „Apple iPhone 15 Pro”, „2026-10-05 14:31”."""
    def wart(*nazwy):
        for n in nazwy:
            for x in klucze:
                if x.rpartition(":")[2] == n and not (k == "czas" and _zero_data(tagi[x])):
                    return tagi[x]
        return None
    if k == "miejsce":
        lat, lon = tagi.get("Composite:GPSLatitude"), tagi.get("Composite:GPSLongitude")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            return f"{lat:.4f}, {lon:.4f}"
    elif k == "urzadzenie":
        marka, model = _tekst(wart("Make") or ""), _tekst(wart("Model") or "")
        if model:
            return model if marka and model.lower().startswith(marka.lower()) else f"{marka} {model}".strip()
    elif k == "firma":
        return _tekst(wart("Company", "Manager", "Application", "Generator", "CreatorTool", "Creator", "Producer",
                           "Template") or tagi[klucze[0]])
    elif k == "czas":
        v = wart("DateTimeOriginal", "CreationDate", "DateCreated", "CreateDate", "DateTime", "ModifyDate") \
            or tagi[klucze[0]]
        m = _DATA.match(str(v))
        if m:
            return f"{m[1]}-{m[2]}-{m[3]}" + (f" {m[4]}:{m[5]}" if m[4] else "")
    elif k == "wlasne":
        return ", ".join(x.rpartition(":")[2] for x in klucze[:3]) + ("…" if len(klucze) > 3 else "")
    elif k in ("identyfikator", "miniatura"):
        return ""
    elif k == "opis":
        return _tekst(wart("Description", "ImageDescription", "Title", "Caption-Abstract", "Headline", "Comment",
                           "UserComment") or tagi[klucze[0]])
    return _tekst(tagi[klucze[0]])


def _opisz(tagi: dict) -> dict:
    kat = kategorie(tagi)
    return {k: {"opis": o, "wartosc": _pokaz(k, tagi, kat[k]), "wpisy": len(kat[k])} for k, o, _ in WRAZLIWE if k in kat}


def metadane(src: Path) -> dict:
    """Co plik mówi o człowieku: {plik, format, wrazliwe: {miejsce: {opis, wartosc, wpisy}, …}, czysty}."""
    src = Path(src)
    if not src.is_file():
        raise Blad(f"Nie ma pliku: {src}")
    z = format_pliku(src)
    if z not in PAKIETY and not program("exiftool"):
        raise Blad("Odczyt metadanych wymaga exiftool (jest w instalacji Jarva).")
    w = _opisz(_odczyt(src))
    wynik = {"plik": src.as_posix(), "format": z, "wrazliwe": w, "czysty": not w}
    if z in PAKIETY and (u := _uwagi_tresci(src)):
        wynik["uwagi"] = u
    return wynik


def _wyczysc(src: Path, dst: Path, z: str) -> None:
    """Kopia bez metadanych. Zdjęcie: exiftool (piksele bez zmian; profil kolorów i obrót zostają).
    Film i dźwięk: ffmpeg przepakowuje strumienie bez kodowania (bez okładki, ścieżek danych i rozdziałów).
    PDF: exiftool kasuje Info i XMP, a qpdf przepisuje plik tylko z żywych obiektów (exiftool dopisuje zmiany na końcu,
    więc bez qpdf stare metadane dałoby się odzyskać). Pakiety Office/ODF: puste części z właściwościami."""
    if z in PAKIETY:
        _wyczysc_pakiet(src, dst)
        return
    if z == "pdf":
        with tempfile.TemporaryDirectory(prefix="pdf-meta-", ignore_cleanup_errors=True) as t:
            posredni = Path(t) / "bez-info.pdf"
            _exiftool(["-m", "-q", "-q", "-all:all=", "-o", str(posredni), os.path.abspath(src)])
            _run(["qpdf", "--deterministic-id", str(posredni), os.path.abspath(dst)], "qpdf", 600, ok=(0, 3))
        return
    if z in FOTO_META:
        _exiftool(["-m", "-q", "-q", "-all=", "-trailer:all=", "-tagsFromFile", "@", "-ColorSpaceTags",
                   "-Orientation", "-o", os.path.abspath(dst), os.path.abspath(src)])
        return
    mapy = ["-map", "0:a"] if z in AUDIO else ["-map", "0:V", "-map", "0:a?", "-map", "0:s?"]
    dalej = ["-movflags", "+faststart"] if z in ("mp4", "mov", "m4a") else []
    if z in ("mp4", "mov"):
        dalej += ["-strict", "unofficial"]       # zostaje opis Dolby Vision z iPhone'a
    _run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), *mapy, "-c", "copy",
          *FF_BEZ_METADANYCH, *dalej, str(dst)], "FFmpeg", 3 * 3600)


def _wyczysc_pakiet(src: Path, dst: Path) -> None:
    """Kopia ZIP-a: części z właściwościami puste, daty wpisów 1980-01-01, bez komentarzy ZIP; reszta bajt w bajt
    (kolejność i kompresja wpisów zostają, więc ODF z „mimetype” na początku dalej się otwiera)."""
    try:
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
            for info in zin.infolist():
                nowa = zipfile.ZipInfo(info.filename, date_time=(1980, 1, 1, 0, 0, 0))
                nowa.compress_type, nowa.external_attr = info.compress_type, info.external_attr
                if info.filename in PUSTE_XML:
                    zout.writestr(nowa, PUSTE_XML[info.filename])
                elif info.filename == "meta.xml":
                    stary = zin.read(info)[:4096]
                    v = re.search(rb'office:version="([0-9.]+)"', stary)
                    zout.writestr(nowa, '<?xml version="1.0" encoding="UTF-8"?>\n<office:document-meta xmlns:office='
                                        '"urn:oasis:names:tc:opendocument:xmlns:office:1.0" office:version="'
                                        f'{v[1].decode() if v else "1.2"}"><office:meta/></office:document-meta>')
                else:
                    with zin.open(info) as f, zout.open(nowa, "w") as g:
                        shutil.copyfileobj(f, g, 1 << 20)
    except (zipfile.BadZipFile, zlib.error, EOFError, OSError) as exc:
        raise Blad(f"Uszkodzony dokument ({src.name}): {exc}") from None


def _sprawdz(p: Path) -> dict:
    """Po czyszczeniu nic wrażliwego nie może zostać: inaczej błąd i brak pliku (lepiej niż fałszywe „czyste”)."""
    tagi = _odczyt(p)
    zostalo = _opisz(tagi)
    if zostalo:
        p.unlink(missing_ok=True)
        raise Blad("Nie udało się usunąć wszystkiego (" + ", ".join(v["opis"] for v in zostalo.values())
                   + "). Pliku nie oddaję.")
    return tagi


def usun_metadane(src: Path, dst: Path | None = None, katalog: Path | None = None) -> dict:
    """Ten sam plik bez metadanych (GPS, telefon, daty, autor, firma, opisy, miniatury); obraz, dźwięk i treść
    dokumentu bez zmian."""
    t0 = time.monotonic()
    src = Path(src)
    if not src.is_file():
        raise Blad(f"Nie ma pliku: {src}")
    z = format_pliku(src)
    if z not in FOTO_META | WIDEO | AUDIO | DOKUMENTY_META:
        stary = {"doc": "DOCX", "xls": "XLSX", "ppt": "PPTX"}.get(z)
        raise Blad(f"Metadane usuwam ze zdjęć (JPG, PNG, WebP, HEIC, AVIF, TIFF, GIF), filmów, dźwięku, PDF "
                   f"i dokumentów (DOCX, XLSX, PPTX, ODT, ODS, ODP), nie z {FORMATY[z][1]}."
                   + (f" Zamień go najpierw na {stary} (--na {stary.lower()})." if stary else ""))
    if z not in PAKIETY and not program("exiftool"):
        raise Blad("Usuwanie metadanych wymaga exiftool (jest w instalacji Jarva).")
    if z in WIDEO | AUDIO and not program("ffmpeg"):
        raise Blad("Film i dźwięk czyści FFmpeg (jest w instalacji Jarva).")
    if z == "pdf":
        if not program("qpdf"):
            raise Blad("PDF czyści qpdf (jest w instalacji Jarva).")
        if _proc(["qpdf", "--is-encrypted", os.path.abspath(src)], timeout=120).returncode == 0:
            raise Blad("PDF jest zabezpieczony hasłem albo blokadą edycji: zdejmij zabezpieczenie i spróbuj jeszcze raz.")
    if dst or katalog:
        out = cel_sciezka(src, z, Path(dst) if dst else None, Path(katalog) if katalog else None)
    else:
        out = wolna_sciezka(src.with_name(f"{src.stem}-bez-metadanych.{z}"))
    if out.resolve() == src.resolve():
        raise Blad("Wynik nadpisałby plik źródłowy: podaj inną nazwę (-o).")
    out.parent.mkdir(parents=True, exist_ok=True)
    przed = _odczyt(src)
    with tempfile.TemporaryDirectory(prefix="metadane-", ignore_cleanup_errors=True) as t:
        tmp = Path(t) / f"czysty.{z}"
        _wyczysc(src, tmp, z)
        po = _sprawdz(tmp)
        shutil.move(str(tmp), out)
    usuniete = _opisz(przed)
    silnik_ = ("exiftool" if z in FOTO_META else "exiftool + qpdf" if z == "pdf" else "Jarvo (XML w pliku)"
               if z in PAKIETY else "FFmpeg")
    wynik = {"wejscie": src.as_posix(), "na": z, "trasa": [f"bez metadanych ({silnik_})"],
             "pliki": [out.as_posix()], "usuniete": usuniete, "wpisow_usunietych": len(_wpisy(przed) - _wpisy(po)),
             "rozmiar_przed": src.stat().st_size, "rozmiar_po": out.stat().st_size,
             "sek": round(time.monotonic() - t0, 2)}
    if not usuniete and not wynik["wpisow_usunietych"]:
        wynik["uwaga"] = "w pliku nie było metadanych do usunięcia"
    if z in PAKIETY and (u := _uwagi_tresci(out)):
        wynik["uwagi"] = [f"zostało w treści: {x} (usuń je w edytorze, jeśli plik idzie do kogoś)" for x in u]
    return wynik


def _dopilnuj(pliki: list[Path]) -> None:
    """Zamiana zdjęcia, filmu albo dźwięku: wynik bez wrażliwych metadanych, nawet gdy biblioteka coś przepisała."""
    if not program("exiftool"):
        return
    for p in pliki:
        f = norm(p.suffix)
        if f not in FOTO_META | WIDEO | AUDIO or not kategorie(_exiftool_json(p)):
            continue
        tmp = p.with_name(f".{p.stem}-czysty.{f}")
        try:
            _wyczysc(p, tmp, f)
            _sprawdz(tmp)
            os.replace(tmp, p)
        finally:
            tmp.unlink(missing_ok=True)


# --------------------------------------------------------------------------- CLI

def python_z_pillow() -> str | None:
    """Python Hermesa z instalacji natywnej (Pillow i pillow-heif są w jego zależnościach; w obrazie to `python3`):
    `<HERMES_SRC>/.venv` albo katalog JARVO_HERMES_BIN (obie zmienne ustawia jarvo/srodowisko.py)."""
    kandydaci: list[Path] = []
    if src := os.environ.get("HERMES_SRC"):
        kandydaci.append(Path(src) / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python"))
    if hermes := os.environ.get("JARVO_HERMES_BIN"):
        kandydaci.append(Path(hermes).parent / ("python.exe" if WINDOWS else "python"))
    for k in kandydaci:
        if k.is_file() and not _ten_python(str(k)):
            return str(k)
    return None


POMOCNICY = ("--pdfium-zadanie", "--pikepdf-zadanie")     # zadania JSON w Pythonie venvu (_zadanie_w)


def _do_pythona_z_pillow(argv: list[str]) -> None:
    """Bez Pillow w tym Pythonie (np. venv narzędzi floty sprzed E8, @@PY@@) ten sam skrypt w Pythonie Hermesa
    z instalacji: zdjęcia, HEIC i zdjęcia → PDF działają jak w obrazie. Ten sam kod wyjścia i wyjście. Bez pętli:
    python_z_pillow() nie zwraca tego samego Pythona. POSIX: execv (ten sam proces), Windows: nowy proces (execv odpina
    tam proces od rodzica) z -X utf8, bo -I pomija PYTHONUTF8."""
    if argv[:1] and argv[0] in POMOCNICY or _jest_modul("PIL"):
        return
    py = python_z_pillow()
    if py is None:
        return
    skrypt = os.path.abspath(__file__)
    if not WINDOWS:
        os.execv(py, [py, "-I", skrypt, *argv])
    sys.exit(subprocess.run([py, "-I", "-X", "utf8", skrypt, *argv]).returncode)


def _main_zadanie(flaga: str) -> int:
    """Pomocnik w Pythonie venvu (--pdfium-zadanie: venv OCR z pypdfium2, --pikepdf-zadanie: venv narzędzi
    z pikepdf): zadanie JSON z wejścia, wynik JSON w ostatniej linii wyjścia."""
    wykonaj, silnik_ = (wykonaj_pdfium, "PDFium") if flaga == "--pdfium-zadanie" else (wykonaj_pikepdf, "pikepdf")
    try:
        wynik = wykonaj(json.loads(sys.stdin.read()))
    except Blad as exc:
        wynik = {"blad": str(exc)}
    except Exception as exc:   # noqa: BLE001  (każdy błąd pomocnika wraca jako opis, nie ślad stosu)
        wynik = {"blad": f"{silnik_}: {type(exc).__name__}: {exc}"}
    print(json.dumps(wynik, ensure_ascii=False))
    return 1 if wynik.get("blad") else 0


def _pliki(wejscia: list[str], rekursywnie: bool) -> list[Path]:
    out = []
    for w in wejscia:
        p = Path(w)
        if p.is_dir():
            it = p.rglob("*") if rekursywnie else p.iterdir()
            out.extend(sorted(x for x in it if x.is_file() and norm(x.suffix) in FORMATY and not x.name.startswith(".")))
        else:
            out.append(p)
    return out


def main(argv: list[str] | None = None) -> int:
    pierwszy = (sys.argv[1:] if argv is None else list(argv))[:1]
    if pierwszy and pierwszy[0] in POMOCNICY:
        return _main_zadanie(pierwszy[0])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pliki", nargs="*")
    ap.add_argument("--na", help="format wyniku, np. pdf, jpg, mp4, mp3, docx")
    ap.add_argument("-o", dest="wyjscie", help="plik wyniku (jeden plik albo --polacz)")
    ap.add_argument("--katalog", help="katalog wyników (domyślnie obok każdego pliku)")
    ap.add_argument("--jakosc", type=int, help="1–100")
    ap.add_argument("--rozmiar", help="1080 | 720p | 50%% | 1920x1080 (nie powiększa)")
    ap.add_argument("--strony", help="strony PDF do obrazów, np. 1-3,5")
    ap.add_argument("--dpi", type=int, default=150, help="PDF → obraz i zdjęcia → PDF (domyślnie 150)")
    ap.add_argument("--polacz", action="store_true", help="kilka plików → jeden PDF")
    ap.add_argument("-r", action="store_true", dest="rekursywnie", help="katalog z podkatalogami")
    ap.add_argument("--cele", action="store_true", help="na co można zamienić plik")
    ap.add_argument("--formaty", action="store_true", help="formaty i silniki dostępne tutaj")
    ap.add_argument("--metadane", action="store_true", help="co plik mówi o człowieku (GPS, telefon, data, autor)")
    ap.add_argument("--usun-metadane", action="store_true", help="ten sam plik bez metadanych (zdjęcia, filmy, dźwięk, PDF, Word, Excel, PowerPoint)")
    args = ap.parse_args(argv)
    dump = lambda d: print(json.dumps(d, ensure_ascii=False, indent=1))  # noqa: E731
    try:
        if args.formaty:
            dump(formaty())
            return 0
        if args.jakosc is not None and not 1 <= args.jakosc <= 100:
            raise Blad("--jakosc od 1 do 100")
        pliki = _pliki(args.pliki, args.rekursywnie)
        if not pliki:
            ap.error("podaj plik (albo --formaty)")
        if args.cele:
            dump({"plik": pliki[0].as_posix(), "format": format_pliku(pliki[0]), "cele": cele(format_pliku(pliki[0]))})
            return 0
        if args.metadane:
            m = [metadane(p) for p in pliki]
            dump(m[0] if len(m) == 1 else m)
            return 0
        if args.usun_metadane and (args.na or args.polacz):
            raise Blad("--usun-metadane zostawia format: bez --na i --polacz (zamiana na inny format też je usuwa).")
        if not args.na and not args.polacz and not args.usun_metadane:
            ap.error("podaj --na <format> (albo --cele, --polacz, --metadane, --usun-metadane)")
        opt = Opcje(jakosc=args.jakosc, rozmiar=args.rozmiar, strony=args.strony, dpi=args.dpi)
        if args.polacz:
            dst = Path(args.wyjscie) if args.wyjscie else wolna_sciezka(
                Path(args.katalog or pliki[0].parent) / f"{pliki[0].stem}-razem.pdf")
            dump(polacz(pliki, dst, opt))
            return 0
        if args.wyjscie and len(pliki) > 1:
            raise Blad("-o tylko dla jednego pliku; dla wielu użyj --katalog.")
        wyniki, bledy = [], []
        for p in pliki:
            try:
                dst, kat = Path(args.wyjscie) if args.wyjscie else None, Path(args.katalog) if args.katalog else None
                wyniki.append(usun_metadane(p, dst, kat) if args.usun_metadane else
                              konwertuj(p, args.na, dst, kat, Opcje(**{**opt.__dict__, "zasoby": None})))
            except Blad as exc:
                if len(pliki) == 1:
                    raise
                bledy.append({"plik": p.as_posix(), "blad": str(exc)})
        dump(wyniki[0] if len(pliki) == 1 else {"wyniki": wyniki, "bledy": bledy})
        return 1 if bledy and not wyniki else 0
    except Blad as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    _do_pythona_z_pillow(sys.argv[1:])
    sys.exit(main())
