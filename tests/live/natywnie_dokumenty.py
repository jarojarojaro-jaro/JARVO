#!/usr/bin/env python3
"""Dokumenty i OCR na instalacji natywnej, na żywo (docs/NATYWNIE.md etap E8: E01–E07, E09, E10, F05).

    python -X utf8 -B tests/live/natywnie_dokumenty.py --wyniki <katalog> [--korzen <JARVO_ROOT>] [--zostaw]
        [--punkty 1,2,7] [--bez-panelu]

Sprawdza skrypty floty tak, jak wołają je agenci na zainstalowanym korzeniu (--korzen, JARVO_ROOT albo domyślny
katalog systemu, jak polecenie jarvo): kopie z profilu jarvo-reka w `<dane>/profiles/jarvo-reka` (skille
`pliki/konwersja-plikow` i `pliki/odczyt-ekranu`, skrypty `to_pdf.py` i `pack.py`), uruchamiane Pythonem skryptów
floty (@@PY@@ = Python venvu narzędzi z `<stan>/narzedzia.json`) w środowisku procesów Jarva (jarvo/srodowisko.py: PATH
z bin-floty i programami z instalacji, CHROME_PATH, JARVO_OCR_PYTHON, TESSDATA_PREFIX…). Pliki próby leżą w
`<dane>/jarvo/workspaces/test-dokumenty-<czas>/Michał Żółć/` i znikają po teście (także po błędzie; --zostaw: zostają).
Działa na samej bibliotece standardowej (dowolny Python 3.11+); pakiet jarvo/ bierze z tego repo.

Punkty:
  1. programy z instalacji: pandoc, qpdf, exiftool, ffmpeg, ffprobe, tesseract (bin-floty) i CHROME_PATH są w
     `<program>` (nie z PATH właściciela); `konwertuj.py --formaty`: pillow, ffmpeg, pdfium, qpdf, pandoc i chromium
     dostępne (ghostscript, pikepdf i libreoffice tylko w raporcie); `ocr.py --stan`: Indra z modelami, Tesseract
     z językiem pol, strony PDF dla Tesseracta przez pypdfium2
  2. md → pdf (pandoc + Chromium) z polskim tekstem i tabelą; ten PDF → txt (PDFium) ma „Zażółć gęślą jaźń”
  3. docx → pdf: DOCX z pandoca, potem PDF trasą pandoc → Chromium (bez LibreOffice), a z LibreOffice właściciela
     jego trasą; tekst PDF z polskimi znakami
  4. to_pdf.py (jarvo-reka): md → pdf i docx → pdf
  5. metadane zdjęcia w „Michał Żółć”: JPG z GPS i telefonem (exiftool), `--metadane` je pokazuje, `--usun-metadane`
     daje plik bez nich (sprawdzone też samym exiftoolem), a zamiana PNG → JPG (Pillow) wychodzi bez metadanych
  6. PDF: qpdf --linearize i --check-linearization, `--polacz` (liczba stron), PDF → PNG stron (PDFium), mniejszy
     PDF (`--na pdf --jakosc 40`)
  7. OCR: zrzut ekranu (Chromium) z polskim tekstem i przyciskiem „Zapisz zmiany”: Indra i Tesseract czytają polskie
     litery, `--szukaj Zapisz` daje środek napisu; „faktura_październik.png” w „Michał Żółć”: oba silniki czytają
     fakturę; PDF z punktu 2: Indra z warstwy tekstu, Tesseract ze strony wyrenderowanej przez pypdfium2
  8. pack.py: pakiet misji z polskimi nazwami, MANIFEST.json ze ścieżkami z „/”, pakiet.zip z nazwami UTF-8
  9. Centrala → Konwerter w panelu (zamiana w procesie panelu: Pillow w Pythonie Hermesa, PDFium przez venv OCR):
     PNG → JPG i PDF → PNG przez trasy wtyczki HQ z tokenem sesji; pominięty, gdy panel nie odpowiada (--bez-panelu)
Kod 0 = wszystkie punkty przeszły; raport JSON na stdout i w <wyniki>/raport.json. Do pełnej macierzy CI na instalacji
od zera (.github/workflows/natywnie.yml: krok po teście na żywo natywnie_e2e.py, który podnosi serwis) i ręcznie na
komputerze z instalacją natywną.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from jarvo import sciezki, srodowisko  # noqa: E402

WINDOWS = os.name == "nt"
BEZ_OKNA = getattr(subprocess, "CREATE_NO_WINDOW", 0) if WINDOWS else 0
POLSKI = "Zażółć gęślą jaźń"
POLSKIE_LITERY = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
KATALOG = "Michał Żółć"
FAKTURA = "faktura_październik.png"
TOKEN = re.compile(r'window\.__HERMES_SESSION_TOKEN__="([^"]+)"')
WYMAGANE_SILNIKI = ("pillow", "ffmpeg", "pdfium", "qpdf", "pandoc", "chromium")
PROGRAMY = ("pandoc", "qpdf", "exiftool", "ffmpeg", "ffprobe", "tesseract")


class Niepowodzenie(Exception):
    pass


def musi(warunek, opis: str) -> None:
    if not warunek:
        raise Niepowodzenie(opis)


def bez_ogonkow(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.casefold().replace("ł", "l"))
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c)))


def _argumenty(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--wyniki", required=True, help="katalog raportu i plików z próby (CI: artefakty)")
    ap.add_argument("--korzen", help="korzeń instalacji (jak JARVO_ROOT)")
    ap.add_argument("--zostaw", action="store_true", help="bez sprzątania plików próby")
    ap.add_argument("--punkty", default="", help="np. 1,7: tylko te punkty")
    ap.add_argument("--bez-panelu", action="store_true", help="bez punktu 9 (Konwerter w panelu)")
    return ap.parse_args(argv)


# ----------------------------------------------------------------------------------------------- instalacja

class Instalacja:
    """Układ, środowisko procesów Jarva i skrypty floty z profilu jarvo-reka."""

    def __init__(self, a: argparse.Namespace):
        env = dict(os.environ)
        if a.korzen:
            env["JARVO_ROOT"] = a.korzen
        self.u = sciezki.uklad(env)
        musi((self.u.program / "current.json").is_file(), f"brak {self.u.program / 'current.json'}: Jarvo nie jest "
                                                          "tu zainstalowane (najpierw jarvo instaluj)")
        self.env = srodowisko.srodowisko(self.u, env)
        if a.korzen:
            self.env["JARVO_ROOT"] = a.korzen
        narz = srodowisko.narzedzia(self.u)
        self.narz = narz
        self.py = (narz.get("venv-narzedzia") or {}).get("python")
        musi(self.py and Path(self.py).is_file(), "brak Pythona venvu narzędzi (venv-narzedzia w narzedzia.json)")
        profil = self.u.dane / "profiles" / "jarvo-reka"
        self.konwertuj = profil / "skills" / "pliki" / "konwersja-plikow" / "scripts" / "konwertuj.py"
        self.ocr = profil / "skills" / "pliki" / "odczyt-ekranu" / "scripts" / "ocr.py"
        self.to_pdf = profil / "scripts" / "to_pdf.py"
        self.pack = profil / "scripts" / "pack.py"
        for p in (self.konwertuj, self.ocr, self.to_pdf, self.pack):
            musi(p.is_file(), f"brak {p}: flota nie jest zainstalowana (krok „Flota” instalatora)")
        self.chrome = self.env.get("CHROME_PATH")
        self.port = int(str(os.environ.get("JARVO_PANEL_PORT") or srodowisko.wczytaj_json(
            self.u.stan / "ustawienia.json").get("JARVO_PANEL_PORT") or "9119").strip())

    def program(self, nazwa: str) -> str | None:
        return shutil.which(nazwa, path=self.env.get("PATH", ""))

    def w_programie(self, sciezka: str | None) -> bool:
        if not sciezka:
            return False
        a, b = os.path.normcase(os.path.abspath(sciezka)), os.path.normcase(os.path.abspath(self.u.program))
        return a.startswith(b.rstrip("\\/") + os.sep)

    def uruchom(self, argv: list, cwd: Path, czas: float = 600, wejscie: bytes | None = None
                ) -> subprocess.CompletedProcess:
        """Program jak w terminalu agenta: środowisko Jarva, katalog roboczy próby, bez okna konsoli."""
        argv = [str(x) for x in argv]
        if not os.path.dirname(argv[0]):
            argv[0] = self.program(argv[0]) or argv[0]
        r = subprocess.run(argv, cwd=str(cwd), env=self.env, capture_output=True, timeout=czas, creationflags=BEZ_OKNA,
                           input=wejscie, stdin=None if wejscie is not None else subprocess.DEVNULL)
        r.stdout = r.stdout.decode("utf-8", "replace")
        r.stderr = r.stderr.decode("utf-8", "replace")
        return r

    def skrypt(self, skrypt: Path, *argumenty, cwd: Path, czas: float = 600, ok: bool = True
               ) -> subprocess.CompletedProcess:
        r = self.uruchom([self.py, str(skrypt), *argumenty], cwd, czas)
        if ok:
            musi(r.returncode == 0, f"{skrypt.name} {' '.join(map(str, argumenty))[:160]}: kod {r.returncode}: "
                                    f"{(r.stderr or r.stdout).strip()[-600:]}")
        return r

    def json(self, skrypt: Path, *argumenty, cwd: Path, czas: float = 600):
        r = self.skrypt(skrypt, *argumenty, cwd=cwd, czas=czas)
        try:
            return json.loads(r.stdout)
        except ValueError:
            raise Niepowodzenie(f"{skrypt.name}: wynik to nie JSON: {r.stdout[:300]!r}") from None

    def exiftool(self, argumenty: list[str], cwd: Path) -> subprocess.CompletedProcess:
        """exiftool z argumentami z wejścia w UTF-8 (jak konwertuj.py: wiersz poleceń Perla na Windows jest w ANSI)."""
        wejscie = "\n".join(["-charset", "filename=utf8", *argumenty]) + "\n"
        return self.uruchom(["exiftool", "-@", "-"], cwd, 300, wejscie.encode("utf-8"))


def _konwertuj_modul(i: Instalacja):
    """konwertuj.py z profilu jako moduł (bez main); w sys.modules przed wykonaniem, bo @dataclass go tam szuka."""
    nazwa = "jarvo_live_konwertuj"
    if nazwa not in sys.modules:
        spec = importlib.util.spec_from_file_location(nazwa, i.konwertuj)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[nazwa] = mod
        spec.loader.exec_module(mod)
    return sys.modules[nazwa]


def zrzut(i: Instalacja, html: str, cel: Path, tmp: Path, szer: int = 1200, wys: int = 500) -> Path:
    """Zrzut ekranu strony z dysku przez Chromium z instalacji (jak agent: `"$CHROME_PATH" --headless --screenshot`)."""
    strona = tmp / f"strona-{cel.stem}.html"
    strona.write_text(html, encoding="utf-8")
    bez = _konwertuj_modul(i).bez_piaskownicy()
    with tempfile.TemporaryDirectory(prefix="zrzut-", ignore_cleanup_errors=True) as profil:
        r = i.uruchom([i.chrome, "--headless", *(["--no-sandbox"] if bez else []), "--disable-gpu", "--no-first-run",
                       "--hide-scrollbars", f"--user-data-dir={profil}", f"--window-size={szer},{wys}",
                       f"--screenshot={cel}", strona.resolve().as_uri()], tmp, 120)
    musi(cel.is_file() and cel.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n",
         f"Chromium nie zrobił zrzutu {cel.name}: kod {r.returncode}: {r.stderr.strip()[-300:]}")
    return cel


def tekst_ocr(w: dict) -> str:
    return "\n".join(ln["tekst"] for s in w["strony"] for ln in s["linie"])


# ----------------------------------------------------------------------------------------------- punkty

def p1_programy(i: Instalacja, kat: Path, ctx: dict) -> dict:
    sciezki_ = {n: i.program(n) for n in PROGRAMY}
    zle = {n: p for n, p in sciezki_.items() if not i.w_programie(p)}
    musi(not zle, f"programy spoza instalacji Jarva albo brak: {zle}")
    musi(i.chrome and Path(i.chrome).is_file() and i.w_programie(i.chrome), f"CHROME_PATH spoza instalacji: {i.chrome}")
    fm = i.json(i.konwertuj, "--formaty", cwd=kat)
    brak = [s for s in WYMAGANE_SILNIKI if not fm["silniki"].get(s)]
    musi(not brak, f"konwertuj.py --formaty: niedostępne silniki {brak} ({fm['silniki']})")
    st = i.json(i.ocr, "--stan", cwd=kat, czas=120)
    musi(st.get("indra") and st.get("modele"), f"ocr.py --stan: bez Indry albo modeli ({st})")
    musi("pol" in (st.get("jezyki_tesseracta") or "") and i.w_programie(st.get("tesseract")),
         f"ocr.py --stan: Tesseract bez polskiego albo spoza instalacji ({st})")
    musi(str(st.get("pdf_dla_tesseracta") or "").startswith("pypdfium2"), f"ocr.py --stan: PDF bez pypdfium2 ({st})")
    ctx["libreoffice"] = bool(fm["silniki"].get("libreoffice"))
    return {"programy": {n: Path(p).as_posix() for n, p in sciezki_.items()}, "silniki": fm["silniki"],
            "ocr": {k: st.get(k) for k in ("indra", "jezyki_tesseracta", "pdf_dla_tesseracta")}}


MARKDOWN = (f"# {POLSKI}\n\nFaktura nr 7/2026 za październik dla firmy Łódzkie Żurawie.\n\n"
            "| Pozycja | Kwota |\n|---|---|\n| Usługa | 1 234,56 zł |\n")


def _pdf_proby(i: Instalacja, kat: Path, ctx: dict) -> Path:
    """PDF z punktu 2, a gdy go nie było (--punkty): ten sam PDF zrobiony teraz (md → pdf)."""
    if ctx.get("pdf") is None:
        md = kat / "notatka_źdźbło.md"
        md.write_text(MARKDOWN, encoding="utf-8")
        ctx["pdf"] = Path(i.json(i.konwertuj, str(md), "--na", "pdf", cwd=kat)["pliki"][0])
    return ctx["pdf"]


def _tekst_pdf(i: Instalacja, pdf: Path, kat: Path) -> str:
    w = i.json(i.konwertuj, str(pdf), "--na", "txt", "-o", str(kat / f"{pdf.stem}-tekst.txt"), cwd=kat)
    musi(w["trasa"] == ["pdf→txt (pdfium)"], f"PDF → txt nie przez PDFium: {w['trasa']}")
    return Path(w["pliki"][0]).read_text(encoding="utf-8")


def p2_md_pdf(i: Instalacja, kat: Path, ctx: dict) -> dict:
    md = kat / "notatka_źdźbło.md"
    md.write_text(MARKDOWN, encoding="utf-8")
    w = i.json(i.konwertuj, str(md), "--na", "pdf", cwd=kat)
    pdf = Path(w["pliki"][0])
    musi(w["trasa"] == ["md→html (pandoc)", "html→pdf (chromium)"], f"trasa md → pdf: {w['trasa']}")
    musi(pdf.name == "notatka_źdźbło.pdf" and pdf.read_bytes()[:5] == b"%PDF-", f"zły PDF: {pdf}")
    tekst = _tekst_pdf(i, pdf, kat)
    musi(POLSKI in tekst and "1 234,56 zł" in tekst, f"PDF bez polskiego tekstu: {tekst[:200]!r}")
    ctx["pdf"] = pdf
    return {"pdf": pdf.name, "bajty": pdf.stat().st_size, "sek": w["sek"]}


def p3_docx_pdf(i: Instalacja, kat: Path, ctx: dict) -> dict:
    md = kat / "umowa_ż.md"
    md.write_text(MARKDOWN, encoding="utf-8")
    docx = Path(i.json(i.konwertuj, str(md), "--na", "docx", cwd=kat)["pliki"][0])
    musi(zipfile.is_zipfile(docx), f"DOCX z pandoca to nie ZIP: {docx}")
    w = i.json(i.konwertuj, str(docx), "--na", "pdf", cwd=kat)
    oczekiwana = (["docx→pdf (libreoffice)"] if ctx.get("libreoffice")
                  else ["docx→html (pandoc)", "html→pdf (chromium)"])
    musi(w["trasa"] == oczekiwana, f"trasa docx → pdf: {w['trasa']} (oczekiwana {oczekiwana})")
    tekst = _tekst_pdf(i, Path(w["pliki"][0]), kat)
    musi(POLSKI in tekst, f"PDF z DOCX bez polskiego tekstu: {tekst[:200]!r}")
    meta = i.json(i.konwertuj, str(docx), "--metadane", cwd=kat)
    ctx["docx"] = docx
    return {"trasa": w["trasa"], "libreoffice": bool(ctx.get("libreoffice")), "metadane_docx": sorted(meta["wrazliwe"])}


def p4_to_pdf(i: Instalacja, kat: Path, ctx: dict) -> dict:
    wyniki = {}
    md = kat / "raport_ż.md"
    md.write_text(MARKDOWN, encoding="utf-8")
    zrodla = [md] + ([ctx["docx"]] if ctx.get("docx") else [])
    for src in zrodla:
        cel = kat / "to_pdf" / f"{src.stem}.pdf"
        r = i.skrypt(i.to_pdf, str(src), str(cel), cwd=kat)
        musi(cel.is_file() and cel.read_bytes()[:5] == b"%PDF-" and r.stdout.startswith("PDF: "),
             f"to_pdf.py {src.name}: {r.stdout.strip()[:200]}")
        musi(POLSKI in _tekst_pdf(i, cel, kat), f"to_pdf.py {src.name}: PDF bez polskiego tekstu")
        wyniki[src.name] = cel.stat().st_size
    return {"pdf": wyniki}


def p5_metadane(i: Instalacja, kat: Path, ctx: dict) -> dict:
    jpg = kat / "zdjęcie_ż.jpg"
    r = i.uruchom(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x480",
                   "-frames:v", "1", str(jpg)], kat, 120)
    musi(r.returncode == 0 and jpg.is_file(), f"ffmpeg nie zrobił zdjęcia: {r.stderr[-300:]}")
    r = i.exiftool(["-q", "-overwrite_original", "-Make=Apple", "-Model=iPhone 15 Pro", "-GPSLatitude=50.0614",
                    "-GPSLatitudeRef=N", "-GPSLongitude=19.9366", "-GPSLongitudeRef=E", "-Artist=Michał Żółć",
                    "-DateTimeOriginal=2026:10:05 14:31:00", str(jpg)], kat)
    musi(r.returncode == 0, f"exiftool nie zapisał metadanych: {r.stderr[-300:]}")
    m = i.json(i.konwertuj, str(jpg), "--metadane", cwd=kat)
    musi({"miejsce", "urzadzenie", "osoba"} <= set(m["wrazliwe"]), f"--metadane nie widzi GPS i telefonu: {m}")
    musi(m["wrazliwe"]["miejsce"]["wartosc"] == "50.0614, 19.9366", f"zła pozycja: {m['wrazliwe']['miejsce']}")
    w = i.json(i.konwertuj, str(jpg), "--usun-metadane", cwd=kat)
    czysty = Path(w["pliki"][0])
    musi(czysty.name == "zdjęcie_ż-bez-metadanych.jpg", f"zła nazwa wyniku: {czysty.name}")
    musi(i.json(i.konwertuj, str(czysty), "--metadane", cwd=kat)["czysty"], "po --usun-metadane coś zostało")
    r = i.exiftool(["-j", "-G1", "-n", "-GPS:all", "-Make", "-Model", "-Artist", str(czysty)], kat)
    tagi = json.loads(r.stdout or "[{}]")[0]
    zostalo = sorted(k for k in tagi if k not in ("SourceFile",))
    musi(r.returncode == 0 and not zostalo, f"exiftool widzi jeszcze: {zostalo}")
    png = kat / "obraz_ż.png"
    r = i.uruchom(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=800x600",
                   "-frames:v", "1", str(png)], kat, 120)
    musi(r.returncode == 0, f"ffmpeg nie zrobił PNG: {r.stderr[-300:]}")
    z = i.json(i.konwertuj, str(png), "--na", "jpg", "--rozmiar", "200", cwd=kat)
    wynik = Path(z["pliki"][0])
    musi(z["trasa"] == ["png→jpg (pillow)"] and wynik.read_bytes()[:3] == b"\xff\xd8\xff", f"PNG → JPG: {z}")
    return {"usuniete": sorted(w["usuniete"]), "wpisow": w["wpisow_usunietych"], "png_jpg": z["rozmiar_po"]}


def p6_pdf(i: Instalacja, kat: Path, ctx: dict) -> dict:
    pdf = _pdf_proby(i, kat, ctx)
    lin = kat / "zlinearyzowany_ż.pdf"
    r = i.uruchom(["qpdf", "--linearize", str(pdf), str(lin)], kat, 120)
    musi(r.returncode in (0, 3) and lin.is_file(), f"qpdf --linearize: {r.returncode} {r.stderr[-300:]}")
    r = i.uruchom(["qpdf", "--check-linearization", str(lin)], kat, 120)
    musi(r.returncode == 0 and "no linearization errors" in r.stdout, f"qpdf --check-linearization: {r.stdout[-300:]}")
    razem = kat / "razem_ż.pdf"
    w = i.json(i.konwertuj, str(pdf), str(lin), "--polacz", "-o", str(razem), cwd=kat)
    r = i.uruchom(["qpdf", "--show-npages", w["pliki"][0]], kat, 60)
    musi(r.stdout.strip() == "2", f"--polacz: {r.stdout.strip()} stron zamiast 2")
    s = i.json(i.konwertuj, str(razem), "--na", "png", "--dpi", "100", "--katalog", str(kat / "strony"), cwd=kat)
    musi(s["trasa"] == ["pdf→png (pdfium)"] and len(s["pliki"]) == 2, f"PDF → PNG: {s}")
    musi(all(Path(p).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" for p in s["pliki"]), "strony to nie PNG")
    m = i.json(i.konwertuj, str(pdf), "--na", "pdf", "--jakosc", "40", "-o", str(kat / "mniejszy_ż.pdf"), cwd=kat)
    musi(Path(m["pliki"][0]).read_bytes()[:5] == b"%PDF-" and m["trasa"][0].startswith("pdf→pdf ("),
         f"mniejszy PDF: {m}")
    return {"linearyzacja": True, "strony_png": [Path(p).name for p in s["pliki"]], "mniejszy": m["trasa"],
            "przed_po": [m["rozmiar_przed"], m["rozmiar_po"]]}


def _ocr(i: Instalacja, plik: Path, kat: Path, *argumenty) -> dict:
    return i.json(i.ocr, str(plik), "--format", "json", *argumenty, cwd=kat, czas=600)


def p7_ocr(i: Instalacja, kat: Path, ctx: dict) -> dict:
    tmp = kat / "html"
    tmp.mkdir(exist_ok=True)
    styl = "<style>body{margin:40px;font:44px 'Segoe UI','DejaVu Sans',Arial,sans-serif;color:#111;background:#fff}"
    styl += "button{font:inherit;padding:8px 24px}</style>"
    ekran = zrzut(i, f"<!doctype html><meta charset=utf-8>{styl}<p>{POLSKI}</p><p>Źródło: Łódź, ul. Żółta 5</p>"
                     "<button>Zapisz zmiany</button>", kat / "zrzut_ekranu.png", tmp)
    faktura = zrzut(i, f"<!doctype html><meta charset=utf-8>{styl}<p>Faktura VAT 10/2026</p>"
                       "<p>Sprzedawca: Michał Żółć</p><p>Razem: 1 234,56 zł</p>", kat / FAKTURA, tmp)
    wynik = {}
    for silnik in ("indra", "tesseract"):
        w = _ocr(i, ekran, kat, "--silnik", silnik)
        tekst = tekst_ocr(w)
        musi(w["silnik"] == silnik, f"{silnik}: czytał {w['silnik']} ({w.get('uwagi')})")
        musi("zazolc gesla jazn" in bez_ogonkow(tekst), f"{silnik}: zrzut bez „{POLSKI}”: {tekst!r}")
        litery = sorted(set(tekst) & POLSKIE_LITERY)
        musi(len(litery) >= 5, f"{silnik}: za mało polskich liter ({litery}) w {tekst!r}")
        s = i.json(i.ocr, str(ekran), "--silnik", silnik, "--szukaj", "Zapisz", cwd=kat, czas=600)
        musi(s["trafienia"] and len(s["trafienia"][0]["srodek"]) == 2, f"{silnik}: --szukaj Zapisz bez trafienia: {s}")
        f = _ocr(i, faktura, kat, "--silnik", silnik)
        ft = bez_ogonkow(tekst_ocr(f))
        musi("faktura" in ft and "2026" in ft and "1234,56" in ft.replace(" ", ""),
             f"{silnik}: faktura: {tekst_ocr(f)!r}")
        wynik[silnik] = {"litery": "".join(litery), "sek": w["sek"], "szukaj": s["trafienia"][0]["srodek"],
                         "faktura": f["plik"].rsplit("/", 2)[-2:]}
    pdf = _pdf_proby(i, kat, ctx)
    w = _ocr(i, pdf, kat, "--silnik", "indra")
    musi(w["strony"][0]["zrodlo"] in ("text", "hybrid") and POLSKI in tekst_ocr(w),
         f"Indra: PDF nie z warstwy tekstu: {w['strony'][0]['zrodlo']} {tekst_ocr(w)[:120]!r}")
    t = _ocr(i, pdf, kat, "--silnik", "tesseract", "--strony", "1")
    musi("zazolc gesla jazn" in bez_ogonkow(tekst_ocr(t)), f"Tesseract: strona PDF: {tekst_ocr(t)[:200]!r}")
    wynik["pdf"] = {"indra": w["strony"][0]["zrodlo"], "tesseract_sek": t["sek"]}
    return wynik


def p8_pack(i: Instalacja, kat: Path, ctx: dict) -> dict:
    misja = kat / "misja-ż"
    (misja / "rynek" / "out").mkdir(parents=True)
    (misja / "rynek" / "out" / "RAPORT_źródła.md").write_text(f"# {POLSKI}\n", encoding="utf-8")
    (misja / "grafika" / "out" / "podkatalog").mkdir(parents=True)
    (misja / "grafika" / "out" / "podkatalog" / "baner_łódź.txt").write_text("x", encoding="utf-8")
    (misja / "pusta").mkdir()
    out = misja / "zlozenie" / "out"
    r = i.skrypt(i.pack, str(misja), "--out", str(out), cwd=kat)
    w = json.loads(r.stdout)
    musi(w["plikow"] == 2 and w["brak_out"] == ["pusta"], f"pack.py: {w}")
    manifest = json.loads((out / "pakiet" / "MANIFEST.json").read_text(encoding="utf-8"))
    sciezki_ = sorted(f["path"] for rola in manifest["roles"].values() for f in rola["files"])
    musi(sciezki_ == ["grafika/podkatalog/baner_łódź.txt", "rynek/RAPORT_źródła.md"], f"MANIFEST: {sciezki_}")
    with zipfile.ZipFile(out / "pakiet.zip") as z:
        nazwy = sorted(z.namelist())
        musi("pakiet/rynek/RAPORT_źródła.md" in nazwy and all(z.getinfo(n).flag_bits & 0x800 or n.isascii()
                                                                for n in nazwy), f"pakiet.zip: {nazwy}")
    r = i.skrypt(i.pack, str(misja), "--out", str(out), cwd=kat)        # drugi raz: stary pakiet roli znika
    musi(json.loads(r.stdout)["plikow"] == 2, "pack.py drugi raz: inna liczba plików")
    return {"manifest": sciezki_, "zip": len(nazwy)}


def _panel(i: Instalacja, metoda: str, sciezka: str, token: str, cialo=None, czas: float = 30):
    dane = None if cialo is None else json.dumps(cialo).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{i.port}/api/plugins/jarvo-hq{sciezka}", data=dane, method=metoda,
                                 headers={"X-Hermes-Session-Token": token, "X-Jarvo-Request": "1",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=czas) as r:      # noqa: S310 (127.0.0.1)
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300].decode("utf-8", "replace")


def p9_panel(i: Instalacja, kat: Path, ctx: dict) -> dict:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{i.port}/", timeout=10) as r:   # noqa: S310 (127.0.0.1)
            html = r.read().decode("utf-8", "replace")
    except OSError as e:
        return {"pominiety": f"panel na 127.0.0.1:{i.port} nie odpowiada ({e})"}
    m = TOKEN.search(html)
    musi(m, "index.html panelu bez tokenu sesji (tryb bez logowania na 127.0.0.1)")
    token = m.group(1)
    skrzynka = i.u.jarvo_dane / "inbox" / kat.parent.name / KATALOG
    skrzynka.mkdir(parents=True, exist_ok=True)
    ctx.setdefault("sprzatanie", []).append(skrzynka.parent)
    png = skrzynka / "obraz_ż.png"
    r = i.uruchom(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x480",
                   "-frames:v", "1", str(png)], kat, 120)
    musi(r.returncode == 0, f"ffmpeg: {r.stderr[-200:]}")
    pdf = skrzynka / "faktura_ż.pdf"
    shutil.copyfile(_pdf_proby(i, kat, ctx), pdf)
    wynik = {}
    for nazwa, src, cialo in (("png→jpg", png, {"na": "jpg", "rozmiar": "200"}), ("pdf→png", pdf, {"na": "png"})):
        kod, cele = _panel(i, "GET", "/konwerter/cele?path=" + urllib.parse.quote(src.as_posix()), token)
        musi(kod == 200 and isinstance(cele, dict), f"/konwerter/cele {src.name}: {kod} {cele}")
        kod, job = _panel(i, "POST", "/konwerter", token, {"paths": [src.as_posix()], **cialo})
        musi(kod == 200 and isinstance(job, dict) and job.get("id"), f"/konwerter {nazwa}: {kod} {job}")
        koniec = time.monotonic() + 300
        while job.get("state") not in ("done", "error") and time.monotonic() < koniec:
            time.sleep(0.5)
            kod, job = _panel(i, "GET", f"/konwerter/job/{job['id']}", token)
        musi(job.get("state") == "done", f"Konwerter w panelu {nazwa}: {job.get('state')} {job.get('error')}")
        pliki = [Path(f["path"]) for f in job.get("files") or []]
        musi(pliki and all(p.is_file() for p in pliki), f"Konwerter w panelu {nazwa}: brak plików {job}")
        ctx["sprzatanie"].extend(pliki + ([Path(job["zip"]["path"])] if job.get("zip") else []))
        wynik[nazwa] = {"trasa": job.get("route"), "pliki": [p.name for p in pliki]}
    musi(wynik["png→jpg"]["trasa"] == ["png→jpg (pillow)"], f"panel: PNG → JPG nie przez Pillow: {wynik}")
    musi(wynik["pdf→png"]["trasa"] == ["pdf→png (pdfium)"], f"panel: PDF → PNG nie przez PDFium: {wynik}")
    return wynik


PUNKTY = [(1, "programy z instalacji i silniki", p1_programy), (2, "md → pdf z polskim tekstem", p2_md_pdf),
          (3, "docx → pdf (pandoc + Chromium albo LibreOffice)", p3_docx_pdf), (4, "to_pdf.py jarvo-reka", p4_to_pdf),
          (5, "metadane zdjęcia (exiftool) i Pillow", p5_metadane), (6, "qpdf i PDFium", p6_pdf),
          (7, "OCR: zrzut, faktura_październik.png, PDF", p7_ocr), (8, "pack.py jarvo-reka", p8_pack),
          (9, "Konwerter w panelu", p9_panel)]


def _sprzatnij(sciezki_: list[Path], skrzynka: Path | None = None) -> list[str]:
    """Pliki i katalogi próby; potem puste katalogi wyników panelu w skrzynce (`inbox/<data>/konwerter`)."""
    bledy = []
    for p in sciezki_:
        try:
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()
        except OSError as e:
            bledy.append(f"{p}: {e}")
    if skrzynka is not None:
        for p in sciezki_:
            for kat in (p.parent, p.parent.parent):
                try:
                    if kat != skrzynka and skrzynka in kat.parents and kat.is_dir() and not any(kat.iterdir()):
                        kat.rmdir()
                except OSError:
                    pass
    return bledy


def main(argv=None) -> int:
    a = _argumenty(argv)
    wyniki = Path(a.wyniki)
    wyniki.mkdir(parents=True, exist_ok=True)
    wybrane = {int(x) for x in a.punkty.split(",") if x.strip()} or {nr for nr, *_ in PUNKTY}
    if a.bez_panelu:
        wybrane.discard(9)
    raport: dict = {"test": "natywnie_dokumenty", "system": sys.platform, "start": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "punkty": []}
    try:
        i = Instalacja(a)
    except Niepowodzenie as e:
        raport["blad"] = str(e)
        (wyniki / "raport.json").write_text(json.dumps(raport, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(raport, ensure_ascii=False, indent=2))
        return 1
    raport["korzen"] = Path(i.u.root).as_posix()
    proba = i.u.jarvo_dane / "workspaces" / f"test-dokumenty-{time.strftime('%Y%m%d-%H%M%S')}"
    kat = proba / KATALOG
    kat.mkdir(parents=True)
    ctx: dict = {"sprzatanie": [proba]}
    try:
        for nr, nazwa, funkcja in PUNKTY:
            if nr not in wybrane:
                continue
            t0 = time.monotonic()
            wpis = {"nr": nr, "nazwa": nazwa}
            try:
                wpis.update(ok=True, wynik=funkcja(i, kat, ctx))
            except Niepowodzenie as e:
                wpis.update(ok=False, blad=str(e))
            except Exception as e:   # noqa: BLE001  (raport zamiast przerwania: kolejne punkty też biegną)
                wpis.update(ok=False, blad=f"{type(e).__name__}: {e}", slad=traceback.format_exc()[-1500:])
            wpis["sek"] = round(time.monotonic() - t0, 1)
            raport["punkty"].append(wpis)
            print(f"{'✓' if wpis['ok'] else '✗'} {nr}. {nazwa} ({wpis['sek']} s)"
                  + ("" if wpis["ok"] else f": {wpis['blad'][:300]}"), file=sys.stderr)
    finally:
        if a.zostaw:
            raport["zostawione"] = Path(proba).as_posix()
        else:
            if bledy := _sprzatnij(ctx.get("sprzatanie", []), i.u.jarvo_dane / "inbox"):
                raport["sprzatanie"] = bledy
    raport["ok"] = bool(raport["punkty"]) and all(p["ok"] for p in raport["punkty"])
    tekst = json.dumps(raport, ensure_ascii=False, indent=2, default=str)
    (wyniki / "raport.json").write_text(tekst, encoding="utf-8")
    print(tekst)
    return 0 if raport["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
