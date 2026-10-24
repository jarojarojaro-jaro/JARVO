#!/usr/bin/env python3
"""Odczyt tekstu z obrazu (OCR) floty Jarva: zrzut ekranu, skan, zdjęcie, PDF albo klatka filmu → tekst i ramki.

    python3 ocr.py <plik…>                          # sam tekst (strony oddziela linia „--- strona N ---”)
    python3 ocr.py <plik…> --format json            # linie z ramką [x0, y0, x1, y1] w pikselach obrazu i pewnością
    python3 ocr.py <plik…> --format md              # Markdown (nagłówki, listy, tabele) z układu strony
    python3 ocr.py zrzut.png --szukaj "Zapisz"      # gdzie na obrazie jest ten napis: ramka i środek (do kliknięcia)
    python3 ocr.py film.mp4 --czas 12.5             # klatka filmu w 12,5 s
    python3 ocr.py skan.pdf --strony 3 --silnik tesseract --jezyk pol
    python3 ocr.py --stan                           # który silnik działa tutaj (JSON)

Silniki: Indra OCR (datalab-to; modele ONNX na CPU, w obrazie: /opt/jarvo/models/indra-ocr) jest główny:
zrzut ekranu w ~0,3–0,5 s, czyta też obrócone strony, kolumny, tabele i chińskie znaki. Tesseract (pol+eng)
jest zapasem: gdy Indry brak, gdy padnie albo na życzenie (--silnik tesseract). Bez sieci: modele leżą
w obrazie, a paczki do pobierania modeli nie ma; gniazda są dodatkowo zablokowane w czasie odczytu.
Skrypt uruchomiony zwykłym python3 sam przechodzi do venvu OCR (/opt/jarvo/venvs/ocr, albo JARVO_OCR_PYTHON).
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

OCR_PYTHON = "/opt/jarvo/venvs/ocr/bin/python"
MODELE = "/opt/jarvo/models/indra-ocr"
FILMY = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".gif"}
MAKS_STRON = 50


class Blad(Exception):
    pass


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


def _do_venvu(argv: list[str]) -> None:
    """Zwykły python3 bez Indry → ten sam skrypt w venvie OCR (w venvie już bez przeskoku, więc bez pętli).
    Nowy proces z tym samym wyjściem i kodem wyjścia (os.execv na Windows odpina proces od rodzica); na Windows
    z -X utf8, bo -I pomija PYTHONUTF8, a wyjście do potoku byłoby w stronie kodowej ANSI."""
    if _indra() is not None:
        return
    py = os.environ.get("JARVO_OCR_PYTHON") or OCR_PYTHON
    if not os.access(py, os.X_OK) or Path(sys.executable).resolve() == Path(py).resolve():
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
    """Z „pol+eng” zostają języki, które Tesseract tu ma; nic z listy → pierwszy dostępny."""
    try:
        out = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return chce
    sa = {x.strip() for x in out.splitlines()[1:] if x.strip()}
    jest = [j for j in chce.split("+") if j in sa]
    return "+".join(jest) or next(iter(sorted(sa - {"osd"})), "eng")


def stan() -> dict:
    ind = _indra()
    modele, tesseract = katalog_modeli(), shutil.which("tesseract")
    return {                                   # ścieżki z „/” także na Windows (JSON dla agenta)
        "indra": getattr(ind, "__version__", None),
        "modele": modele.as_posix() if modele else None,
        "tesseract": Path(tesseract).as_posix() if tesseract else None,
        "jezyki_tesseracta": jezyki_tesseracta("pol+eng") if tesseract else None,
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
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{czas}", "-i", str(film), "-frames:v", "1", str(out)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if r.returncode or not out.is_file():
        raise Blad(f"nie wyjąłem klatki {czas:g} s z {film.name}: {(r.stderr or '').strip()[:200]}")
    return out


def _linia(ramka, tekst: str, pewnosc: float | None) -> dict:
    return {"tekst": tekst, "ramka": [round(float(v)) for v in ramka],
            "pewnosc": None if pewnosc is None else round(float(pewnosc), 3)}


def czytaj_indra(plik: Path, strony: str | None, dpi: float, watki: int, wzory: bool) -> list[dict]:
    ind = _indra()
    if ind is None:
        raise Blad("brak Indry OCR (venv /opt/jarvo/venvs/ocr z obrazu Jarva)")
    md = katalog_modeli()
    if md is None:
        raise Blad("brak modeli Indry (/opt/jarvo/models/indra-ocr albo INDRA_OCR_MODEL_DIR)")
    zablokuj_siec()
    conv = ind.load(str(md), threads=watki, dpi=dpi, mode="auto", math=wzory)
    if strony and plik.read_bytes()[:5] == b"%PDF-":
        import pypdfium2 as pdfium  # type: ignore[import-not-found]
        doc = pdfium.PdfDocument(str(plik))
        try:
            pary = [(i, conv.pdf_page(str(plik), doc, i)) for i in zakres_stron(strony, len(doc))]
        finally:
            doc.close()
    else:
        pary = conv.convert(plik, max_pages=MAKS_STRON)
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


def czytaj_tesseract(plik: Path, strony: str | None, dpi: float, jezyk: str, tmp: Path) -> list[dict]:
    if not shutil.which("tesseract"):
        raise Blad("brak Tesseracta (apt tesseract-ocr w obrazie Jarva)")
    obrazy: list[tuple[int, Path]]
    if plik.read_bytes()[:5] == b"%PDF-":
        if not shutil.which("gs"):
            raise Blad("PDF przez Tesseract wymaga Ghostscripta (gs)")
        ile = subprocess.run(["qpdf", "--show-npages", str(plik)], capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=120).stdout.strip() if shutil.which("qpdf") else ""
        n = int(ile) if ile.isdigit() else MAKS_STRON
        obrazy = []
        for i in zakres_stron(strony, n):
            out = tmp / f"s{i + 1}.png"
            subprocess.run(["gs", "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=pnggray", f"-r{int(dpi)}",
                            f"-dFirstPage={i + 1}", f"-dLastPage={i + 1}", f"-sOutputFile={out}", str(plik)],
                           capture_output=True, timeout=300, check=True)
            if out.is_file() and out.stat().st_size:
                obrazy.append((i + 1, out))
    else:
        obrazy = [(1, plik)]
    lang = jezyki_tesseracta(jezyk)
    wynik = []
    for nr, obraz in obrazy:
        r = subprocess.run(["tesseract", str(obraz), "stdout", "-l", lang, "--psm", "3", "tsv"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        if r.returncode:
            raise Blad(f"Tesseract: {(r.stderr or '').strip()[:200]}")
        wynik.append({"strona": nr, "zrodlo": "ocr", "obrot": 0, "linie": _tsv_linie(r.stdout), "markdown": None})
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
