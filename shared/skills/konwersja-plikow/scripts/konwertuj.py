#!/usr/bin/env python3
"""Konwerter plików Jarva: plik → inny format na serwerze, bez wysyłania gdziekolwiek (wzór: convt, kod własny).

    python3 konwertuj.py <plik…|katalog> --na <format> [-o wynik | --katalog DIR] [--jakosc 1-100]
                         [--rozmiar 1080|720p|50%|1920x1080] [--strony 1-3,5] [--dpi 150] [--polacz] [-r]
    python3 konwertuj.py <plik> --cele          # na co można zamienić ten plik (JSON)
    python3 konwertuj.py --formaty              # formaty i silniki dostępne tutaj (JSON)

Silniki (co jest w obrazie, to działa; bez silnika trasa znika): Pillow (zdjęcia, HEIC z iPhone'a, AVIF, PSD,
zdjęcia → PDF), FFmpeg (wideo, audio, GIF, SVG → PNG), Ghostscript (PDF → obrazy i tekst, mniejszy PDF), qpdf
(łączenie PDF), pandoc (Word, ODT, Markdown, HTML, EPUB, RTF), Chromium (HTML → PDF, bez sieci), LibreOffice
(Excel, PowerPoint, stare .doc/.xls/.ppt; tylko z dodatkiem obrazu `office`).
Trasa: najtańsza przez najwyżej 3 kroki (np. DOCX → HTML → PDF, XLSX → PDF → PNG).
Wynik obok pliku (albo -o / --katalog); istniejącego pliku nie nadpisuje: nazwa-2.ext.
--rozmiar: 1080 = dłuższy bok najwyżej 1080 px, 720p = krótszy bok 720, 50% = połowa, 1920x1080 = zmieść w polu;
nigdy nie powiększa. --jakosc: zdjęcia (domyślnie 85), film (domyślnie 75), audio (kb/s ≈ 3,2 × jakość),
PDF → PDF (mniejszy plik). Ten sam format z --rozmiar albo --jakosc = zmniejszenie pliku.
--polacz: kilka plików (zdjęcia, PDF, dokumenty) → jeden PDF. --strony: strony PDF do obrazów („1-3,5”, „4-”).
Metadane zdjęć (np. GPS) nie przechodzą do wyniku; profil koloru zostaje.
Wynik: JSON {pliki, trasa, rozmiar_przed, rozmiar_po, sek}; kod 1 = błąd z opisem po polsku.
"""

from __future__ import annotations

import argparse
import functools
import heapq
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

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

def _run(cmd: list[str], silnik: str, timeout: int, cwd: Path | None = None) -> subprocess.CompletedProcess:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise Blad(f"{silnik}: przekroczony czas ({timeout // 60} min)") from None
    except OSError as exc:
        raise Blad(f"{silnik}: nie da się uruchomić ({exc})") from None
    if r.returncode != 0:
        lines = [x for x in (r.stderr or r.stdout or "").strip().splitlines() if x.strip()]
        tail = "\n".join(dict.fromkeys(lines[:4] + lines[-4:]))
        raise Blad(f"{silnik} zakończył się błędem ({r.returncode}):\n{tail}")
    return r


def chromium() -> str | None:
    for cand in (os.environ.get("CHROME_PATH"), shutil.which("chromium"), shutil.which("chromium-browser"),
                 shutil.which("google-chrome")):
        if cand and os.path.exists(cand):
            return cand
    return None


def soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


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
    if shutil.which("qpdf"):
        r = subprocess.run(["qpdf", "--show-npages", str(pdf)], capture_output=True, text=True)
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
        return bool(shutil.which("ffmpeg"))

    @functools.cached_property
    def _kodeki(self) -> tuple[str, str]:
        enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
        dec = subprocess.run(["ffmpeg", "-hide_banner", "-decoders"], capture_output=True, text=True).stdout
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
        if not shutil.which("ffprobe"):
            return {}
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "stream=codec_type,codec_name,color_transfer,color_primaries,color_space",
                            "-of", "json", str(src)], capture_output=True, text=True)
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
        if z == "svg":
            return [[*wej, "-frames:v", "1", "-update", "1", str(dst)]]
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


class Ghostscript(Silnik):
    nazwa = "ghostscript"

    def dostepny(self) -> bool:
        return bool(shutil.which("gs"))

    def krawedzie(self):
        return [("pdf", "png", 1.0), ("pdf", "jpg", 1.0), ("pdf", "txt", 1.0), ("pdf", "pdf", 1.0)]

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
        if len(pliki) == 1:
            shutil.move(str(pliki[0]), dst)
            return [dst]
        numery = lista if lista and len(lista) == len(pliki) else list(range(1, len(pliki) + 1))
        szer = max(2, len(str(max(numery))))
        out = []
        for nr, p in zip(numery, pliki):
            q = dst.with_name(f"{dst.stem}-{nr:0{szer}d}{dst.suffix}")
            shutil.move(str(p), q)
            out.append(q)
        return out


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
        return bool(shutil.which("pandoc"))

    def krawedzie(self):
        return [(a, b, 1.0) for a in PANDOC_CZYTA for b in PANDOC_PISZE if a != b]

    def polecenie(self, src: Path, dst: Path, z: str, na: str, opt: Opcje, filtr: Path) -> list[str]:
        zasoby = os.pathsep.join(dict.fromkeys(str(x.resolve()) for x in (src.parent, opt.zasoby or src.parent)))
        cmd = ["pandoc", "-f", PANDOC_CZYTA[z], "-t", PANDOC_PISZE[na], "-s", "--lua-filter", str(filtr),
               f"--resource-path={zasoby}", "--metadata", f"pagetitle={src.stem}"]
        if z in PANDOC_MEDIA and na in ("html", "md"):
            cmd.append(f"--extract-media={dst.stem}-media")      # względnie: obok wyniku (cwd = katalog wyniku)
        return [*cmd, "-o", str(dst.resolve()), str(src.resolve())]

    def zamien(self, src, dst, z, na, opt, tmp):
        filtr = tmp / "bezpieczne-obrazki.lua"
        filtr.write_text(FILTR_LUA, encoding="utf-8")
        _run(self.polecenie(src, dst, z, na, opt, filtr), "pandoc", 600, cwd=dst.parent)
        if na == "html":
            t = dst.read_text(encoding="utf-8", errors="replace")
            dst.write_text(t.replace("</head>", STYL + "</head>", 1), encoding="utf-8")
        return [dst]


class _Zasoby(http.server.SimpleHTTPRequestHandler):
    """Serwer druku: /__strona.html = drukowany HTML, reszta tylko z katalogów `korzenie` (katalog HTML i pliku
    źródłowego), więc strona nie sięga po resztę dysku."""
    strona: Path
    korzenie: tuple[Path, ...] = ()

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


class Chromium(Silnik):
    nazwa = "chromium"

    def dostepny(self) -> bool:
        return chromium() is not None

    def krawedzie(self):
        return [("html", "pdf", 1.0)]

    def zamien(self, src, dst, z, na, opt, tmp):
        korzenie = tuple(dict.fromkeys(x.resolve() for x in (src.parent, opt.zasoby or src.parent)))
        handler = type("H", (_Zasoby,), {"strona": src.resolve(), "korzenie": korzenie})
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory(prefix="konwertuj-chrome-") as profil:
                # strona z http://127.0.0.1 nie sięga po file://, a martwe proxy odcina internet (127.0.0.1 omija proxy)
                _run([chromium(), "--headless", "--no-sandbox", "--disable-gpu", "--disable-extensions",
                      "--no-first-run", f"--user-data-dir={profil}", "--proxy-server=127.0.0.1:9",
                      "--no-pdf-header-footer", "--virtual-time-budget=5000", f"--print-to-pdf={dst.resolve()}",
                      f"http://127.0.0.1:{srv.server_address[1]}/__strona.html"], "Chromium", 300)
        finally:
            srv.shutdown()
            srv.server_close()
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


SILNIKI: list[Silnik] = [Pillow(), FFmpeg(), Ghostscript(), Pandoc(), Chromium(), LibreOffice()]


# --------------------------------------------------------------------------- trasy

@functools.lru_cache(maxsize=1)
def _graf() -> dict[str, list[tuple[str, float, str]]]:
    g: dict[str, list[tuple[str, float, str]]] = {}
    for s in SILNIKI:
        if not s.dostepny():
            continue
        for a, b, koszt in s.krawedzie():
            g.setdefault(a, []).append((b, koszt, s.nazwa))
    return g


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
        sil = next((s for b, _, s in _graf().get(z, []) if b == z), None)
        return [(z, z, sil)] if sil else None
    return trasy(z).get(na)


def podpowiedz(z: str, na: str) -> str:
    if (na in LO_ARKUSZ | LO_SLAJDY | {"doc"} or z in LO_ARKUSZ | LO_SLAJDY | {"doc"}) and not soffice():
        return " Arkusze, prezentacje i stare pliki Office wymagają LibreOffice: dodatek obrazu `office` (JARVO_EXTRAS)."
    if z == "pdf" and FORMATY[na][0] in ("dokument", "tekst", "arkusz", "prezentacja"):
        return " Z PDF nie zrobisz Worda ani arkusza: sam tekst daje --na txt (skan bez tekstu: najpierw ocrmypdf)."
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
    with tempfile.TemporaryDirectory(prefix="konwertuj-") as t:
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
    przed, po = src.stat().st_size, _rozmiar(wyniki)
    wynik = {"wejscie": str(src), "na": na, "trasa": [f"{a}→{b} ({s})" for a, b, s in kroki],
             "pliki": [str(p) for p in wyniki], "rozmiar_przed": przed, "rozmiar_po": po,
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
        if not shutil.which("qpdf"):
            raise Blad("Łączenie PDF wymaga qpdf (jest w obrazie Jarva).")
        with tempfile.TemporaryDirectory(prefix="polacz-") as t:
            czesci = []
            for i, (s, f) in enumerate(zip(srcs, formaty)):
                if f == "pdf":
                    czesci.append(s)
                    continue
                r = konwertuj(s, "pdf", dst=Path(t) / f"{i:03d}.pdf", opt=Opcje(dpi=opt.dpi, zasoby=s.parent))
                czesci.extend(Path(p) for p in r["pliki"])
            _run(["qpdf", "--empty", "--pages", *map(str, czesci), "--", str(dst)], "qpdf", 600)
    return {"wejscie": [str(s) for s in srcs], "na": "pdf", "trasa": ["połączenie w jeden PDF"], "pliki": [str(dst)],
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


def formaty() -> dict:
    g = _graf()
    wej = {a for a in g}
    wyj = {b for kr in g.values() for b, _, _ in kr}
    return {"silniki": {s.nazwa: s.dostepny() for s in SILNIKI},
            "formaty": [{"format": f, "grupa": g_, "nazwa": n, "opis": o, "odczyt": f in wej, "zapis": f in wyj}
                        for f, (g_, n, o) in FORMATY.items()],
            "rozszerzenia": sorted({*FORMATY, *ALIASY})}


# --------------------------------------------------------------------------- CLI

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
            dump({"plik": str(pliki[0]), "format": format_pliku(pliki[0]), "cele": cele(format_pliku(pliki[0]))})
            return 0
        if not args.na and not args.polacz:
            ap.error("podaj --na <format> (albo --cele, --polacz)")
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
                wyniki.append(konwertuj(p, args.na, Path(args.wyjscie) if args.wyjscie else None,
                                        Path(args.katalog) if args.katalog else None,
                                        Opcje(**{**opt.__dict__, "zasoby": None})))
            except Blad as exc:
                if len(pliki) == 1:
                    raise
                bledy.append({"plik": str(p), "blad": str(exc)})
        dump(wyniki[0] if len(pliki) == 1 else {"wyniki": wyniki, "bledy": bledy})
        return 1 if bledy and not wyniki else 0
    except Blad as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
