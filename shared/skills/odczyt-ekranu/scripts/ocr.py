#!/usr/bin/env python3
"""Odczyt tekstu z obrazu (OCR) floty Jarva: zrzut ekranu, skan, zdjęcie, PDF albo klatka filmu → tekst i ramki.

    python3 ocr.py <plik…>                          # sam tekst (strony oddziela linia „--- strona N ---”)
    python3 ocr.py <plik…> --format json            # linie z ramką [x0, y0, x1, y1] w pikselach obrazu i pewnością
    python3 ocr.py <plik…> --format md              # Markdown (nagłówki, listy, tabele) z układu strony
    python3 ocr.py zrzut.png --szukaj "Zapisz"      # gdzie na obrazie jest ten napis: ramka i środek (do kliknięcia)
    python3 ocr.py film.mp4 --czas 12.5             # klatka filmu w 12,5 s
    python3 ocr.py skan.pdf --strony 3 --silnik tesseract --jezyk pol
    python3 ocr.py --stan                           # który silnik działa tutaj (JSON)

Silniki: Indra OCR (datalab-to; modele ONNX na CPU z INDRA_OCR_MODEL_DIR: w obrazie /opt/jarvo/models/indra-ocr,
natywnie <dane>/jarvo/models/indra-ocr) jest główny: zrzut ekranu w ~0,3–0,5 s, czyta też obrócone strony, kolumny,
tabele i chińskie znaki. Tesseract (pol+eng) jest zapasem: gdy Indry brak, gdy padnie albo na życzenie
(--silnik tesseract). Bez sieci: modele leżą w instalacji, a paczki do pobierania modeli nie ma; gniazda są
dodatkowo zablokowane w czasie odczytu.
Skrypt uruchomiony zwykłym python3 sam przechodzi do venvu OCR (JARVO_OCR_PYTHON, w obrazie /opt/jarvo/venvs/ocr;
domyślne ścieżki obrazu tylko na Linuksie i macOS: na Windows `\\opt\\…` na bieżącym dysku mógłby założyć każdy).
Natywnie (docs/NATYWNIE.md E05, E10, B13): obraz z polskimi znakami w ścieżce Indra dostaje przez np.fromfile
i cv2.imdecode (cv2.imread go nie otworzy), Tesseract przez wejście (stdin), a strony PDF renderuje mu pypdfium2
(bez Ghostscriptu); Tesseract z PATH floty (natywnie bin-floty), języki z TESSDATA_PREFIX, TSV przez
`-c tessedit_create_tsv=1`. PDF poznaje po „%PDF-” w pierwszych 1024 bajtach (jak Indra i PDFium: przed nagłówkiem
bywają śmieci, np. puste linie z poczty), a nie po rozszerzeniu.
Ramki są w pikselach pliku (PDF: strona wyrenderowana w --dpi); zrzut ekranu 2× → podziel przez 2 przed kliknięciem.
--szukaj: bez wielkości liter i polskich znaków („zrodlo” znajdzie „Źródło”); ramka napisu wyliczona z ramki linii.
Wynik --szukaj i --format json: JSON; kod 1 = błąd z opisem po polsku.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

WINDOWS = os.name == "nt"
BEZ_OKNA = getattr(subprocess, "CREATE_NO_WINDOW", 0) if WINDOWS else 0   # programy bez okna konsoli (Windows)
# ścieżki obrazu Jarva (natywnie JARVO_OCR_PYTHON i INDRA_OCR_MODEL_DIR z jarvo/srodowisko.py); na Windows żadnych:
# katalog `\opt` w głównym katalogu dysku może założyć każdy zalogowany użytkownik, a CreateProcess uruchomi plik PE
# o nazwie `python` bez rozszerzenia
OCR_PYTHON = None if WINDOWS else "/opt/jarvo/venvs/ocr/bin/python"
MODELE = None if WINDOWS else "/opt/jarvo/models/indra-ocr"
FILMY = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".gif"}
MAKS_STRON = 50
MAKS_PIKSELI = 100e6        # strona PDF większa niż tyle pikseli w --dpi renderuje się w niższym (jak w Indrze)
NAGLOWEK_PDF = 1024         # „%PDF-” gdzieś w pierwszych 1024 bajtach = PDF (Indra is_pdf, PDFium, Acrobat)


class Blad(Exception):
    pass


def _proc(cmd: list, timeout: float, **kw) -> subprocess.CompletedProcess:
    """Program z przechwyconym wyjściem, bez okna konsoli; goła nazwa → pełna ścieżka z PATH (CreateProcess na
    Windows szukałby jej najpierw w katalogu Pythona i w System32)."""
    cmd = [str(x) for x in cmd]
    if cmd and not os.path.dirname(cmd[0]):
        cmd[0] = shutil.which(cmd[0]) or cmd[0]
    if "input" not in kw:
        kw["stdin"] = subprocess.DEVNULL
    return subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=BEZ_OKNA, **kw)


def _tekst(dane: bytes | str | None) -> str:
    return dane.decode("utf-8", "replace") if isinstance(dane, bytes) else (dane or "")


def _odmow(*_a, **_k):
    raise PermissionError("OCR działa bez sieci (odczyt nie łączy się z internetem)")


def zablokuj_siec() -> None:
    socket.socket.connect = _odmow          # type: ignore[method-assign]
    socket.socket.connect_ex = _odmow       # type: ignore[method-assign]
    socket.create_connection = _odmow       # type: ignore[assignment]
    socket.getaddrinfo = _odmow             # type: ignore[assignment]


def _indra():
    try:
        import indra_ocr  # type: ignore[import-not-found]
        return indra_ocr
    except ImportError:
        return None


def bez_telemetrii() -> None:
    """onnxruntime (silnik Indry) bez zdarzeń telemetrii: oficjalne koło Windows ma dostawcę ETW Microsoft.ML.ONNXRuntime
    (przegląd źródła w vendor/zrodla.yaml); na Linuksie i macOS to nic nie zmienia."""
    try:
        import onnxruntime  # type: ignore[import-not-found]
        onnxruntime.disable_telemetry_events()
    except Exception:  # noqa: BLE001  (bez onnxruntime albo starsze API: odczyt i tak działa)
        pass


def _do_venvu(argv: list[str]) -> None:
    """Zwykły python3 bez Indry → ten sam skrypt w venvie OCR (w venvie już bez przeskoku, więc bez pętli).
    Nowy proces z tym samym wyjściem i kodem wyjścia (os.execv na Windows odpina proces od rodzica); na Windows
    z -X utf8, bo -I pomija PYTHONUTF8, a wyjście do potoku byłoby w stronie kodowej ANSI."""
    if _indra() is not None:
        return
    py = os.environ.get("JARVO_OCR_PYTHON") or OCR_PYTHON
    if not py or not os.path.isfile(py) or not os.access(py, os.X_OK) \
            or Path(sys.executable).resolve() == Path(py).resolve():
        return
    if os.name != "nt":                              # POSIX: jak dotąd ten sam proces
        os.execv(py, [py, "-I", str(Path(__file__).resolve()), *argv])
    sys.exit(subprocess.run([py, "-I", "-X", "utf8", str(Path(__file__).resolve()), *argv]).returncode)


def katalog_modeli() -> Path | None:
    for k in (os.environ.get("INDRA_OCR_MODEL_DIR"), MODELE):
        if k and (Path(k) / "det.onnx").is_file() and (Path(k) / "rec.onnx").is_file():
            return Path(k)
    return None


def jezyki_tesseracta(chce: str) -> str:
    """Z „pol+eng” zostają języki, które Tesseract tu ma (TESSDATA_PREFIX); nic z listy → pierwszy dostępny."""
    try:
        out = _tekst(_proc(["tesseract", "--list-langs"], timeout=30).stdout)
    except (OSError, subprocess.TimeoutExpired):
        return chce
    sa = {x.strip() for x in out.splitlines()[1:] if x.strip()}
    jest = [j for j in chce.split("+") if j in sa]
    return "+".join(jest) or next(iter(sorted(sa - {"osd"})), "eng")


def _pdfium():
    try:
        import pypdfium2 as pdfium  # type: ignore[import-not-found]
        return pdfium
    except ImportError:
        return None


def stan() -> dict:
    ind = _indra()
    modele, tesseract = katalog_modeli(), shutil.which("tesseract")
    pdfium = _pdfium()
    return {                                   # ścieżki z „/” także na Windows (JSON dla agenta)
        "indra": getattr(ind, "__version__", None),
        "modele": modele.as_posix() if modele else None,
        "tesseract": Path(tesseract).as_posix() if tesseract else None,
        "jezyki_tesseracta": jezyki_tesseracta("pol+eng") if tesseract else None,
        # czym strony PDF idą do Tesseracta: pypdfium2 (venv OCR), a bez niego Ghostscript, jeśli jest
        "pdf_dla_tesseracta": (f"pypdfium2 {getattr(pdfium, 'PYPDFIUM_INFO', '')}".strip() if pdfium
                               else "ghostscript" if shutil.which("gs") else None),
        "python": Path(sys.executable).as_posix(),
    }


def zakres_stron(spec: str | None, ile: int) -> list[int]:
    """„1-3,5” / „4-” → indeksy od zera; bez spec: wszystkie (najwyżej MAKS_STRON)."""
    if not spec:
        return list(range(min(ile, MAKS_STRON)))
    wynik: list[int] = []
    for kaw in spec.split(","):
        kaw = kaw.strip()
        m = re.fullmatch(r"(\d+)(?:-(\d*))?", kaw)
        if not m:
            raise Blad(f"--strony: nie rozumiem „{kaw}” (przykład: 1-3,5)")
        a = int(m.group(1))
        b = a if m.group(2) is None else (int(m.group(2)) if m.group(2) else ile)
        wynik += [i - 1 for i in range(a, min(b, ile) + 1) if i >= 1]
    return sorted(set(wynik))


def klatka(film: Path, czas: float, tmp: Path) -> Path:
    if not shutil.which("ffmpeg"):
        raise Blad("klatka filmu wymaga ffmpeg")
    out = tmp / f"klatka-{czas:g}.png"
    r = _proc(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{czas}", "-i", str(film), "-frames:v", "1",
               str(out)], timeout=120)
    if r.returncode or not out.is_file():
        raise Blad(f"nie wyjąłem klatki {czas:g} s z {film.name}: {_tekst(r.stderr).strip()[:200]}")
    return out


OBRAZY_NA_POCZATKU = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"II*\x00", b"MM\x00*", b"BM")   # sygnatury obrazów


def _pdf(plik: Path) -> bool:
    """PDF po treści: „%PDF-” w pierwszych 1024 bajtach (jak `is_pdf` Indry i PDFium, które czytają też PDF z bajtami
    przed nagłówkiem, np. z pustymi liniami albo nagłówkiem MIME z poczty), chyba że plik zaczyna się sygnaturą obrazu
    (napis „%PDF-” w metadanych PNG to dalej obraz)."""
    with open(plik, "rb") as f:
        poczatek = f.read(NAGLOWEK_PDF)
    if poczatek.startswith(OBRAZY_NA_POCZATKU) or poczatek[:4] == b"RIFF" and poczatek[8:12] == b"WEBP":
        return False
    return b"%PDF-" in poczatek


def obrazy_pliku(plik: Path) -> list:
    """Strony obrazu w szarości (każda klatka wielostronicowego TIFF): np.fromfile + cv2.imdecode, bo cv2.imread
    (tak czyta Indra) nie otworzy na Windows pliku z polskimi znakami w ścieżce („faktura_październik.png”)."""
    import cv2  # type: ignore[import-not-found]
    import numpy as np  # type: ignore[import-not-found]
    dane = np.fromfile(str(plik), dtype=np.uint8)
    klatki: list = []
    if hasattr(cv2, "imdecodemulti"):
        ok, wiele = cv2.imdecodemulti(dane, cv2.IMREAD_GRAYSCALE)
        klatki = list(wiele) if ok and wiele else []
    if not klatki:
        jedna = cv2.imdecode(dane, cv2.IMREAD_GRAYSCALE)
        klatki = [jedna] if jedna is not None else []
    if not klatki:
        raise Blad(f"{plik.name}: to nie jest PDF ani obraz, który da się odczytać")
    return [np.ascontiguousarray(k) for k in klatki[:MAKS_STRON]]


def _linia(ramka, tekst: str, pewnosc: float | None) -> dict:
    return {"tekst": tekst, "ramka": [round(float(v)) for v in ramka],
            "pewnosc": None if pewnosc is None else round(float(pewnosc), 3)}


def _strona_indry(conv, obraz):
    """Jedna strona obrazu przez Indrę; awaria = pusta strona z opisem (jak Converter.convert w indra_ocr)."""
    try:
        return conv.ocr(obraz)
    except Exception as e:  # noqa: BLE001  (opis trafia do błędu strony niżej)
        return type("Strona", (), {"source": "error", "note": f"{type(e).__name__}: {e}", "lines": [],
                                   "markdown": "", "rotation": 0})()


def czytaj_indra(plik: Path, strony: str | None, dpi: float, watki: int, wzory: bool) -> list[dict]:
    ind = _indra()
    if ind is None:
        raise Blad("brak Indry OCR (venv OCR z instalacji Jarva: JARVO_OCR_PYTHON, w obrazie /opt/jarvo/venvs/ocr)")
    md = katalog_modeli()
    if md is None:
        raise Blad("brak modeli Indry (INDRA_OCR_MODEL_DIR; w obrazie /opt/jarvo/models/indra-ocr)")
    zablokuj_siec()
    bez_telemetrii()
    conv = ind.load(str(md), threads=watki, dpi=dpi, mode="auto", math=wzory)
    if _pdf(plik):
        if strony:
            import pypdfium2 as pdfium  # type: ignore[import-not-found]
            doc = pdfium.PdfDocument(str(plik))         # pypdfium2 otwiera też ścieżki z polskimi znakami
            try:
                pary = [(i, conv.pdf_page(str(plik), doc, i)) for i in zakres_stron(strony, len(doc))]
            finally:
                doc.close()
        else:
            pary = conv.convert(plik, max_pages=MAKS_STRON)
    else:
        pary = [(i, _strona_indry(conv, obraz)) for i, obraz in enumerate(obrazy_pliku(plik))]
    wynik = []
    for i, p in pary:
        if p.source == "error":
            raise Blad(f"strona {i + 1}: {p.note or 'błąd odczytu'}")
        wynik.append({"strona": i + 1, "zrodlo": p.source, "obrot": p.rotation,
                      "linie": [_linia(ln.box, ln.text, ln.conf) for ln in p.lines],
                      "markdown": p.markdown})
    return wynik


def _tsv_linie(tsv: str) -> list[dict]:
    """TSV Tesseracta (słowa) → linie: tekst, ramka z sumy słów, średnia pewność."""
    grupy: dict[tuple, list] = {}
    for w in tsv.splitlines()[1:]:
        k = w.split("\t")
        if len(k) < 12 or k[0] != "5" or not k[11].strip():
            continue
        x, y, s, h, conf = int(k[6]), int(k[7]), int(k[8]), int(k[9]), float(k[10])
        grupy.setdefault((int(k[2]), int(k[3]), int(k[4])), []).append((x, y, x + s, y + h, conf, k[11]))
    linie = []
    for slowa in grupy.values():
        ramka = (min(s[0] for s in slowa), min(s[1] for s in slowa), max(s[2] for s in slowa), max(s[3] for s in slowa))
        linie.append(_linia(ramka, " ".join(s[5] for s in slowa), sum(s[4] for s in slowa) / len(slowa) / 100))
    return linie


def _pgm(szarosc) -> bytes:
    """Tablica szarości (numpy, wiersze × kolumny) → PGM (P5): format, który Tesseract (Leptonica) czyta z wejścia."""
    h, w = szarosc.shape[:2]
    return b"P5\n%d %d\n255\n" % (w, h) + szarosc.tobytes()


def strony_pdf_pypdfium(plik: Path, strony: str | None, dpi: float) -> list[tuple[int, bytes]]:
    """Strony PDF w szarości jako PGM dla Tesseracta, renderowane przez pypdfium2 (venv OCR; bez Ghostscriptu)."""
    import numpy as np  # type: ignore[import-not-found]
    pdfium = _pdfium()
    try:
        doc = pdfium.PdfDocument(str(plik))
    except pdfium.PdfiumError as e:
        if "password" in str(e).lower():
            raise Blad("PDF jest zabezpieczony hasłem: zdejmij zabezpieczenie i spróbuj jeszcze raz") from None
        raise Blad(f"nie otworzę PDF {plik.name}: {e}") from None
    try:
        out = []
        for i in zakres_stron(strony, len(doc)):
            strona = doc[i]
            w, h = strona.get_size()
            skala = min(dpi / 72.0, (MAKS_PIKSELI / max(w * h, 1.0)) ** 0.5)
            tab = strona.render(scale=skala, grayscale=True).to_numpy()
            tab = np.ascontiguousarray(tab[..., 0] if tab.ndim == 3 else tab)
            out.append((i + 1, _pgm(tab)))
            strona.close()
        return out
    finally:
        doc.close()


def strony_pdf_gs(plik: Path, strony: str | None, dpi: float, tmp: Path) -> list[tuple[int, bytes]]:
    """Zapas bez pypdfium2 (Ghostscript tam, gdzie już jest, np. w obrazie Jarva z OCRmyPDF)."""
    ile = _tekst(_proc(["qpdf", "--show-npages", str(plik)], timeout=120).stdout).strip() if shutil.which("qpdf") else ""
    n = int(ile) if ile.isdigit() else MAKS_STRON
    out = []
    for i in zakres_stron(strony, n):
        png = tmp / f"s{i + 1}.png"
        _proc(["gs", "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=pnggray", f"-r{int(dpi)}",
               f"-dFirstPage={i + 1}", f"-dLastPage={i + 1}", f"-sOutputFile={png}", str(plik)],
              timeout=300, check=True)
        if png.is_file() and png.stat().st_size:
            out.append((i + 1, png.read_bytes()))
    return out


def czytaj_tesseract(plik: Path, strony: str | None, dpi: float, jezyk: str, tmp: Path) -> list[dict]:
    if not shutil.which("tesseract"):
        raise Blad("brak Tesseracta (program tesseract z instalacji Jarva: natywnie bin-floty, w obrazie apt)")
    obrazy: list[tuple[int, bytes]]
    rozdzielczosc: list[str] = []
    if _pdf(plik):
        rozdzielczosc = ["--dpi", str(int(dpi))]       # strona wyrenderowana w --dpi (PGM nie niesie rozdzielczości)
        if _pdfium() is not None:
            obrazy = strony_pdf_pypdfium(plik, strony, dpi)
        elif shutil.which("gs"):
            obrazy = strony_pdf_gs(plik, strony, dpi, tmp)
        else:
            raise Blad("PDF przez Tesseract wymaga pypdfium2 (venv OCR z instalacji Jarva) albo Ghostscripta")
    else:
        obrazy = [(1, plik.read_bytes())]
    lang = jezyki_tesseracta(jezyk)
    wynik = []
    for nr, dane in obrazy:
        # obraz przez wejście (stdin): Tesseract ma wąskie API ścieżek (polskie znaki na Windows); TSV przez -c, bo
        # konfiguracja `tsv` bywa nie do znalezienia (TESSDATA_PREFIX bez katalogu configs)
        r = _proc(["tesseract", "stdin", "stdout", "-l", lang, "--psm", "3", *rozdzielczosc,
                   "-c", "tessedit_create_tsv=1"], timeout=600, input=dane)
        if r.returncode:
            raise Blad(f"Tesseract: {_tekst(r.stderr).strip()[:200]}")
        wynik.append({"strona": nr, "zrodlo": "ocr", "obrot": 0, "linie": _tsv_linie(_tekst(r.stdout)),
                      "markdown": None})
    return wynik


def _bez_ogonkow(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.casefold().replace("ł", "l"))
    return "".join(c for c in s if not unicodedata.combining(c))


def _norm(s: str) -> tuple[str, list[int]]:
    """Tekst do porównań (małe litery, bez ogonków, pojedyncze spacje) i mapa: znak wyniku → znak oryginału."""
    out, mapa, spacja = [], [], False
    for i, c in enumerate(s):
        z = _bez_ogonkow(c)
        if not z:
            continue
        if z.isspace():
            if out and not spacja:
                out.append(" ")
                mapa.append(i)
            spacja = True
            continue
        spacja = False
        for zz in z:
            out.append(zz)
            mapa.append(i)
    return "".join(out).strip(), mapa


def szukaj(strony: list[dict], fraza: str) -> list[dict]:
    cel, _ = _norm(fraza)
    if not cel:
        raise Blad("--szukaj: pusty tekst")
    trafienia = []
    for s in strony:
        for ln in s["linie"]:
            tekst = ln["tekst"]
            n, mapa = _norm(tekst)
            start = n.find(cel)
            while start >= 0:
                a, b = mapa[start], mapa[start + len(cel) - 1] + 1
                x0, y0, x1, y1 = ln["ramka"]
                szer = (x1 - x0) / max(len(tekst), 1)
                ramka = [round(x0 + a * szer), y0, round(x0 + b * szer), y1]
                trafienia.append({"strona": s["strona"], "tekst": tekst[a:b], "linia": tekst, "ramka": ramka,
                                  "srodek": [round((ramka[0] + ramka[2]) / 2), round((y0 + y1) / 2)],
                                  "pewnosc": ln["pewnosc"]})
                start = n.find(cel, start + 1)
    return trafienia


def odczytaj(plik: Path, a: argparse.Namespace, tmp: Path) -> dict:
    if not plik.is_file():
        raise Blad(f"nie ma pliku {plik}")
    zrodlo = plik
    if plik.suffix.lower() in FILMY:
        zrodlo = klatka(plik, a.czas or 0.0, tmp)
    t0, uwagi, silnik = time.monotonic(), [], a.silnik
    strony: list[dict] | None = None
    if silnik in ("auto", "indra"):
        try:
            strony, silnik = czytaj_indra(zrodlo, a.strony, a.dpi, a.watki, a.wzory), "indra"
        except Exception as e:  # noqa: BLE001  (każda awaria Indry → zapas, z powodem w uwagach)
            if a.silnik == "indra":
                raise Blad(f"Indra OCR: {e}") from e
            uwagi.append(f"Indra niedostępna ({str(e)[:160]}), czytał Tesseract")
    if strony is None:
        strony, silnik = czytaj_tesseract(zrodlo, a.strony, a.dpi, a.jezyk, tmp), "tesseract"
    r = {"plik": plik.as_posix(), "silnik": silnik, "sek": round(time.monotonic() - t0, 2), "strony": strony}
    if zrodlo != plik:
        r["klatka_s"] = a.czas or 0.0
    if uwagi:
        r["uwagi"] = uwagi
    return r


def tekst_strony(s: dict, md: bool) -> str:
    if md and s.get("markdown"):
        return s["markdown"].strip()
    return "\n".join(ln["tekst"] for ln in s["linie"])


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(description="Tekst z obrazu, skanu, PDF albo klatki filmu (Indra OCR, zapas: Tesseract).")
    ap.add_argument("pliki", nargs="*", type=Path)
    ap.add_argument("--format", choices=("tekst", "json", "md"), default="tekst")
    ap.add_argument("--szukaj", help="gdzie jest ten napis (JSON: ramka i środek; bez wielkości liter i ogonków)")
    ap.add_argument("--silnik", choices=("auto", "indra", "tesseract"), default="auto")
    ap.add_argument("--strony", help="strony PDF, np. 1-3,5 (bez: najwyżej %d)" % MAKS_STRON)
    ap.add_argument("--czas", type=float, help="film: klatka w tej sekundzie (domyślnie 0)")
    ap.add_argument("--dpi", type=float, default=200.0, help="PDF: rozdzielczość renderu strony (domyślnie 200)")
    ap.add_argument("--jezyk", default="pol+eng", help="języki Tesseracta (Indra rozpoznaje pismo sama)")
    ap.add_argument("--watki", type=int, default=min(4, os.cpu_count() or 1))
    ap.add_argument("--wzory", action="store_true", help="Indra: wzory matematyczne jako LaTeX (wolniej)")
    ap.add_argument("--stan", action="store_true", help="który silnik działa tutaj (JSON)")
    _do_venvu(argv)
    a = ap.parse_args(argv)
    try:
        if a.stan:
            r = stan()
            print(json.dumps(r, ensure_ascii=False, indent=2))
            return 0 if (r["indra"] and r["modele"]) or r["tesseract"] else 1
        if not a.pliki:
            raise Blad("podaj plik (zrzut ekranu, skan, zdjęcie, PDF albo film z --czas)")
        with tempfile.TemporaryDirectory(prefix="jarvo-ocr-") as t:
            wyniki = [odczytaj(p, a, Path(t)) for p in a.pliki]
        if a.szukaj is not None:
            out = [{"plik": w["plik"], "silnik": w["silnik"], "szukane": a.szukaj,
                    "trafienia": szukaj(w["strony"], a.szukaj), **({"uwagi": w["uwagi"]} if "uwagi" in w else {})}
                   for w in wyniki]
            print(json.dumps(out[0] if len(out) == 1 else out, ensure_ascii=False, indent=2))
        elif a.format == "json":
            print(json.dumps(wyniki[0] if len(wyniki) == 1 else wyniki, ensure_ascii=False, indent=2))
        else:
            kawalki = []
            for w in wyniki:
                if len(wyniki) > 1:
                    kawalki.append(f"=== {w['plik']} ===")
                for s in w["strony"]:
                    if len(w["strony"]) > 1:
                        kawalki.append(f"--- strona {s['strona']} ---")
                    kawalki.append(tekst_strony(s, a.format == "md"))
                for u in w.get("uwagi", []):
                    print(f"! {u}", file=sys.stderr)
            print("\n".join(kawalki))
        return 0
    except Blad as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
