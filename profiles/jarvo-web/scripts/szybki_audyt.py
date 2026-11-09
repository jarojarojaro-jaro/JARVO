#!/usr/bin/env python3
"""Szybki audyt strony z lokalnej kopii (pierwszy audyt, podstawy): wynik w kilkadziesiąt sekund, raport na stronę.

    python3 szybki_audyt.py <katalog strony> [--out DIR] [--domena D] [--bez-zrzutow] [--json]

Bez sieci i bez Lighthouse/axe. Sprawdza:
  SEO      `seo_check.check_dir` (bez --base-url, bez sieci): title, description, H1, alt, canonical, lang, viewport,
           noindex, Open Graph, robots.txt, sitemap; długości title i description według progów niżej,
  obrazy   pliki obrazów w katalogu: liczba, waga, > 300 KB, stare formaty (JPEG/PNG/GIF) > 100 KB, 5 najcięższych,
  waga     strony głównej: index.html + lokalne CSS, JS i obrazy z niej (zastępczo za szybkość),
  linki    wewnętrzne <a href> wskazujące plik, którego nie ma w katalogu,
  telefon  `screenshots.cjs` na 390 i 1440 px (strona główna z serwera 127.0.0.1 na wolnym porcie): poziome
           przewijanie z `screenshots.json` i montaż obu zrzutów w jednym `zrzuty.jpg` (Pillow, a bez niego
           `screenshots.cjs --montaz`). Bez node, przeglądarki albo z --bez-zrzutow: pominięte z powodem w raporcie.
Domena: --domena, potem `domena` z `.strona.json`, potem nazwa katalogu.
Wynik w --out (domyślnie out/szybki-audyt): raport.md, audyt.json (wszystkie liczby), zrzuty/ i zrzuty.jpg.
Kod wyjścia 0, gdy raport powstał (znaleziska to nie błąd); 1 przy błędzie odczytu/zapisu, 2 przy złych argumentach.
"""
from __future__ import annotations

import argparse
import datetime
import functools
import http.server
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import seo_check  # noqa: E402
from audit import chrome_path, utf8  # noqa: E402

# ------------------------------------------------------------------------------------------------ progi
TITLE_MIN, TITLE_MAX = 30, 60                 # znaków
DESC_MIN, DESC_MAX = 70, 160                  # znaków
H1_NA_STRONE = 1
KB = 1024
OBRAZ_BLAD = 300 * KB                         # każdy obraz cięższy = ❌
OBRAZ_STARY_UWAGA = 100 * KB                  # JPEG/PNG/GIF/BMP/TIFF cięższy (nie WebP/AVIF) = ⚠️
GLOWNA_UWAGA = 1024 * KB                      # waga strony głównej > 1 MB = ⚠️
GLOWNA_BLAD = 2048 * KB                       # > 2 MB = ❌
SZER_TELEFON, SZER_KOMPUTER = 390, 1440       # przewijanie w bok na telefonie = ❌, na komputerze = ⚠️
MONTAZ_SZER = 1600                            # zrzuty.jpg: oba zrzuty obok siebie, razem tyle pikseli (hero czytelne bez przybliżenia)
ZRZUTY_LIMIT_S = 90
POPRAWEK = 5

OBRAZY = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".svg", ".bmp", ".tif", ".tiff", ".ico"}
STARE_RASTRY = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff"}
POMIJANE_KATALOGI = {"node_modules", "cgi-bin"}
ZNAK = {"ok": "✅", "uwaga": "⚠️", "blad": "❌"}


class Strona(seo_check.PageParser):
    """Parser seo_check plus `<script src>` (waga strony głównej)."""

    def __init__(self):
        super().__init__()
        self.skrypty: list[str] = []

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if tag == "script":
            src = dict(attrs).get("src")
            if src:
                self.skrypty.append(src)


def kb(n: int | float) -> str:
    return f"{round(n / KB)} KB" if n < 1024 * KB else f"{n / KB / KB:.1f} MB".replace(".", ",")


def widoczne_pliki(katalog: Path):
    for root, dirs, files in os.walk(katalog):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in POMIJANE_KATALOGI)
        for f in sorted(files):
            if not f.startswith("."):
                yield Path(root) / f


def lokalny(katalog: Path, rel: str, href: str, domeny: set[str]) -> Path | None | bool:
    """Plik w katalogu, na który wskazuje href ze strony `rel`. None = zewnętrzny albo nie plik (mailto, #)."""
    href = href.strip()
    if not href or href.startswith(("#", "data:")):
        return None
    sp = urllib.parse.urlsplit(href)
    if sp.scheme and sp.scheme not in ("http", "https"):
        return None
    if sp.netloc and sp.netloc.lower().removeprefix("www.") not in domeny:
        return None
    sciezka = urllib.parse.unquote(sp.path)
    if not sciezka:
        return None
    baza = katalog if sciezka.startswith("/") else (katalog / rel).parent
    cel = (baza / sciezka.lstrip("/")).resolve()
    try:
        cel.relative_to(katalog.resolve())
    except ValueError:
        return False                                    # wychodzi poza katalog strony = martwy
    return cel


def istnieje(cel: Path, href: str) -> bool:
    """Plik, katalog z index.html albo czysty adres (/kontakt → kontakt.html)."""
    if cel.is_file():
        return True
    if cel.is_dir():
        return any((cel / n).is_file() for n in ("index.html", "index.php", "index.htm"))
    return not href.rstrip().endswith("/") and cel.with_name(cel.name + ".html").is_file()


# ---------------------------------------------------------------------------------------- pomiary

def strony_i_seo(katalog: Path) -> tuple[dict, dict[str, Strona]]:
    wynik = seo_check.check_dir(katalog)
    parsery = {}
    for s in wynik["strony"]:
        p = Strona()
        p.feed((katalog / s["plik"]).read_text(encoding="utf-8", errors="replace"))
        parsery[s["plik"]] = p
    return wynik, parsery


def ocen_tytuly(parsery: dict[str, Strona]) -> dict:
    t = {"bez_title": [], "title_dlugosc": [], "bez_description": [], "description_dlugosc": []}
    for rel, p in parsery.items():
        if rel == "404.html":
            continue
        title = " ".join(p.title.split())
        desc = " ".join((seo_check.meta_content(p, "description") or "").split())
        if not title:
            t["bez_title"].append(rel)
        elif not TITLE_MIN <= len(title) <= TITLE_MAX:
            t["title_dlugosc"].append({"plik": rel, "znakow": len(title)})
        if not desc:
            t["bez_description"].append(rel)
        elif not DESC_MIN <= len(desc) <= DESC_MAX:
            t["description_dlugosc"].append({"plik": rel, "znakow": len(desc)})
    return t


def ocen_naglowki(parsery: dict[str, Strona]) -> dict:
    n = {"bez_h1": [], "wiele_h1": [], "bez_h2": []}
    for rel, p in parsery.items():
        h1 = sum(1 for h in p.headings if h[0] == "h1")
        if h1 == 0:
            n["bez_h1"].append(rel)
        elif h1 > H1_NA_STRONE:
            n["wiele_h1"].append({"plik": rel, "h1": h1})
        if not any(h[0] == "h2" for h in p.headings):
            n["bez_h2"].append(rel)
    return n


def ocen_alt(parsery: dict[str, Strona]) -> dict:
    a = {"obrazow": 0, "bez_alt": 0, "alt_todo": 0, "strony": []}
    for rel, p in parsery.items():
        a["obrazow"] += len(p.imgs)
        bez = [i.get("src", "?") for i in p.imgs if "alt" not in i]
        todo = [i.get("src", "?") for i in p.imgs if i.get("alt", "").strip().lower() == "todo"]
        a["bez_alt"] += len(bez)
        a["alt_todo"] += len(todo)
        if bez or todo:
            a["strony"].append({"plik": rel, "bez_alt": len(bez), "alt_todo": len(todo), "np": (bez + todo)[0]})
    return a


def obrazy_udostepniania(katalog: Path, parsery: dict[str, Strona], domeny: set[str]) -> set[str]:
    """Obrazy OG/Twittera i ikony: JPEG/PNG to dla nich właściwy format (serwisy nie czytają AVIF)."""
    hrefy = [(rel, seo_check.meta_content(p, k, a) or "") for rel, p in parsery.items()
             for k, a in (("og:image", "property"), ("twitter:image", "name"), ("twitter:image", "property"))]
    hrefy += [(rel, x.get("href", "")) for rel, p in parsery.items() for x in p.links if "icon" in x.get("rel", "").lower()]
    wynik = set()
    for rel, href in hrefy:
        cel = lokalny(katalog, rel, href, domeny)
        if cel and cel.is_file():
            wynik.add(cel.relative_to(katalog.resolve()).as_posix())
    return wynik


def ocen_obrazy(katalog: Path, udostepniane: set[str]) -> dict:
    pliki = [(f.relative_to(katalog).as_posix(), f.stat().st_size, f.suffix.lower())
             for f in widoczne_pliki(katalog) if f.suffix.lower() in OBRAZY]
    pliki.sort(key=lambda x: -x[1])
    return {
        "liczba": len(pliki),
        "bajty": sum(x[1] for x in pliki),
        "ponad_300kb": [{"plik": r, "bajty": b} for r, b, _ in pliki if b > OBRAZ_BLAD],
        "stary_format_ponad_100kb": [{"plik": r, "bajty": b} for r, b, e in pliki
                                     if e in STARE_RASTRY and b > OBRAZ_STARY_UWAGA and r not in udostepniane],
        "udostepniania_i_ikony": sorted(udostepniane),
        "najciezsze": [{"plik": r, "bajty": b} for r, b, _ in pliki[:5]],
    }


META_REFRESH = re.compile(r"""<meta[^>]+http-equiv\s*=\s*["']?refresh["']?[^>]*content\s*=\s*["']?\s*\d+\s*;\s*url\s*=\s*([^"'>\s]+)""",
                          re.I)


def strona_glowna(katalog: Path, parsery: dict[str, Strona]) -> str | None:
    """Plik strony głównej: index.html, a gdy to tylko przekierowanie meta refresh (seo_check go pomija, np. `/` →
    `/pl/`), cel przekierowania; bez index.html pierwszy z pl/ i en/."""
    if "index.html" in parsery:
        return "index.html"
    korzen = katalog / "index.html"
    if korzen.is_file():
        m = META_REFRESH.search(korzen.read_text(encoding="utf-8", errors="replace")[:20000])
        if m:
            cel = m.group(1).split("#")[0].split("?")[0]
            if not re.match(r"^[a-z]+:", cel, re.I):
                rel = posixpath.normpath(cel.lstrip("./") if not cel.startswith("/") else cel.lstrip("/")).lstrip("/")
                for kandydat in (f"{rel}/index.html", rel, f"{rel}.html"):
                    if kandydat in parsery:
                        return kandydat
    return next((k for k in ("pl/index.html", "en/index.html") if k in parsery), None)


def ocen_glowna(katalog: Path, parsery: dict[str, Strona], domeny: set[str]) -> dict | None:
    plik = strona_glowna(katalog, parsery)
    if plik is None:
        return None
    p = parsery[plik]
    zasoby = {"css": [x.get("href", "") for x in p.links if "stylesheet" in x.get("rel", "").lower()],
              "js": p.skrypty, "obrazy": [i.get("src", "") for i in p.imgs]}
    w = {"plik": plik, "html": (katalog / plik).stat().st_size, "css": 0, "js": 0, "obrazy": 0, "zewnetrzne": 0}
    widziane: set[Path] = set()
    for typ, hrefy in zasoby.items():
        for href in hrefy:
            cel = lokalny(katalog, plik, href, domeny)
            if cel is None and href.strip() and not href.startswith("data:"):
                w["zewnetrzne"] += 1
            elif cel and cel.is_file() and cel not in widziane:
                widziane.add(cel)
                w[typ] += cel.stat().st_size
    w["razem"] = w["html"] + w["css"] + w["js"] + w["obrazy"]
    return w


def ocen_linki(katalog: Path, parsery: dict[str, Strona], domeny: set[str]) -> dict:
    martwe, sprawdzone = [], 0
    for rel, p in parsery.items():
        for href in dict.fromkeys(p.anchors):
            cel = lokalny(katalog, rel, href, domeny)
            if cel is None:
                continue
            sprawdzone += 1
            if cel is False or not istnieje(cel, href):
                martwe.append({"plik": rel, "href": href})
    return {"sprawdzone": sprawdzone, "martwe": martwe}


def ocen_indeksowanie(seo: dict) -> dict:
    w = seo["witryna"]["errors"]
    i = {"brak_robots": any("brak robots.txt" in m for m in w),
         "brak_sitemap": any("brak sitemap" in m for m in w),
         "bez_canonical": [], "zly_canonical": [], "bez_lang": [], "bez_viewport": [], "noindex": []}
    for s in seo["strony"]:
        for m in s["head"]["errors"]:
            klucz = ("bez_canonical" if m.startswith("brak link rel=canonical") else
                     "zly_canonical" if m.startswith("canonical") else
                     "bez_lang" if m.startswith("brak atrybutu lang") else
                     "bez_viewport" if m.startswith("brak meta viewport") else
                     "noindex" if "noindex" in m else None)
            if klucz:
                i[klucz].append(s["plik"])
    return i


def ocen_og(seo: dict) -> dict:
    strony = [{"plik": s["plik"], "braki": s["og"]["errors"]} for s in seo["strony"]
              if s["og"]["errors"] and s["plik"] != "404.html"]
    return {"strony_z_bledami": len(strony), "np": strony[:3]}


# ---------------------------------------------------------------------------------------- zrzuty

class _Cichy(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def montaz_pil(pliki: list[Path], cel: Path) -> bool:
    try:
        from PIL import Image
    except ImportError:
        return False
    obrazy = [Image.open(f).convert("RGB") for f in pliki]
    odstep = 12
    wys = round((MONTAZ_SZER - odstep * (len(obrazy) - 1)) / sum(o.width / o.height for o in obrazy))
    male = [o.resize((max(1, round(o.width * wys / o.height)), wys), Image.LANCZOS) for o in obrazy]
    plotno = Image.new("RGB", (sum(m.width for m in male) + odstep * (len(male) - 1), wys), "#999999")
    x = 0
    for m in male:
        plotno.paste(m, (x, 0))
        x += m.width + odstep
    plotno.save(cel, "JPEG", quality=80, optimize=True)
    return True


def zrzuty(katalog: Path, out: Path) -> dict:
    node = shutil.which("node")
    if not node:
        return {"pominiete": "brak node w PATH (zrzuty i przewijanie w bok nie sprawdzone)"}
    chrome = chrome_path()
    env = dict(os.environ, **({"CHROME_PATH": chrome} if chrome else {}))
    try:
        import PIL  # noqa: F401
        pil = True
    except ImportError:
        pil = False
    katalog_zrzutow = out / "zrzuty"
    serwer = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                             functools.partial(_Cichy, directory=str(katalog)))
    threading.Thread(target=serwer.serve_forever, daemon=True).start()
    try:
        cmd = [node, str(HERE / "screenshots.cjs"), f"http://127.0.0.1:{serwer.server_address[1]}/",
               str(katalog_zrzutow), "--widths", f"{SZER_TELEFON},{SZER_KOMPUTER}"]
        if not pil:
            cmd += ["--montaz", str(out / "zrzuty.jpg"), "--montaz-szer", str(MONTAZ_SZER)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=ZRZUTY_LIMIT_S, env=env)
        except subprocess.TimeoutExpired:
            return {"pominiete": f"przeglądarka nie skończyła w {ZRZUTY_LIMIT_S} s"}
    finally:
        serwer.shutdown()
        serwer.server_close()
    if r.returncode != 0:
        blad = (r.stderr.strip().splitlines() or ["bez komunikatu"])[0][:200]
        return {"pominiete": f"przeglądarka niedostępna ({blad})"}
    dane = json.loads((katalog_zrzutow / "screenshots.json").read_text(encoding="utf-8"))
    wynik = {"szerokosci": {}, "pliki": []}
    for x in dane.get("results", []):
        plik = Path(x["file"])
        wynik["pliki"].append(plik.relative_to(out).as_posix() if plik.is_relative_to(out) else plik.name)
        wynik["szerokosci"][str(x["width"])] = {
            "status_http": x.get("status"), "przewijanie_w_bok": bool(x.get("horizontal_scroll")),
            "szerokosc_tresci": x.get("scroll_width"), "wystajace": x.get("overflowing_elements") or []}
    if pil:
        montaz_pil([out / p for p in wynik["pliki"]], out / "zrzuty.jpg")
    wynik["montaz"] = "zrzuty.jpg" if (out / "zrzuty.jpg").is_file() else None
    if not wynik["montaz"]:
        wynik["montaz_brak"] = "montaż nie powstał (ani Pillow, ani --montaz screenshots.cjs)"
    return wynik


# ---------------------------------------------------------------------------------------- ocena i raport

def gdzie(lista: list, co: str = "stron") -> str:
    """„stron: 3, np. oferta.html” (liczba po dwukropku: bez odmiany liczebników)."""
    x = lista[0]
    return f"{co}: {len(lista)}, np. {x['plik'] if isinstance(x, dict) else x}"


def wiersze_i_poprawki(a: dict) -> tuple[list[dict], list[dict]]:
    """Wiersze tabeli (status + jedna linia) i poprawki uszeregowane według wpływu (waga), najwyżej POPRAWEK."""
    w, p = [], []
    n = a["strony"]

    def wiersz(nazwa, status, opis):
        w.append({"obszar": nazwa, "status": status, "opis": opis})

    def popraw(waga, tekst):
        p.append({"waga": waga, "tekst": tekst})

    t = a["tytuly"]
    czesci = []
    if t["bez_title"]:
        czesci.append(f"bez title ({gdzie(t['bez_title'])})")
        popraw(88, f"Dodaj `<title>` ({TITLE_MIN}–{TITLE_MAX} znaków) ({gdzie(t['bez_title'])}).")
    if t["bez_description"]:
        czesci.append(f"bez description ({gdzie(t['bez_description'])})")
        popraw(70, f"Dopisz meta description ({DESC_MIN}–{DESC_MAX} znaków, zachęta do kliknięcia) "
                   f"({gdzie(t['bez_description'])}).")
    for klucz, nazwa, (od, do) in (("title_dlugosc", "title", (TITLE_MIN, TITLE_MAX)),
                                   ("description_dlugosc", "description", (DESC_MIN, DESC_MAX))):
        if t[klucz]:
            x = t[klucz][0]
            czesci.append(f"{nazwa} poza {od}–{do} znaków (stron: {len(t[klucz])}, np. {x['plik']}: {x['znakow']})")
    dl = t["title_dlugosc"] + t["description_dlugosc"]
    if dl:
        popraw(35, f"Dopasuj długość: title {TITLE_MIN}–{TITLE_MAX}, description {DESC_MIN}–{DESC_MAX} znaków "
                   f"(stron: {len({x['plik'] for x in dl})}, np. {dl[0]['plik']}: {dl[0]['znakow']} znaków).")
    if t["duplikaty"]:
        czesci.append(f"powtórzone między stronami: {len(t['duplikaty'])}")
        popraw(40, f"Nadaj każdej stronie własny title i description ({t['duplikaty'][0][:90]}).")
    status = "blad" if t["bez_title"] or t["bez_description"] else "uwaga" if dl or t["duplikaty"] else "ok"
    wiersz("Title i description", status, "; ".join(czesci) or f"w normie na wszystkich stronach ({n})")

    h = a["naglowki"]
    czesci = []
    if h["bez_h1"]:
        czesci.append(f"bez H1 ({gdzie(h['bez_h1'])})")
        popraw(65, f"Dodaj jeden H1 z głównym tematem strony ({gdzie(h['bez_h1'])}).")
    if h["wiele_h1"]:
        x = h["wiele_h1"][0]
        czesci.append(f"więcej niż jeden H1 (stron: {len(h['wiele_h1'])}, np. {x['plik']}: {x['h1']})")
        popraw(50, f"Zostaw jeden H1 na stronie, pozostałe zamień na H2 (stron: {len(h['wiele_h1'])}, "
                   f"np. {x['plik']}: H1 × {x['h1']}).")
    czesci.append(f"bez H2: {len(h['bez_h2'])}/{n}")
    wiersz("Nagłówki H1/H2", "blad" if h["bez_h1"] else "uwaga" if h["wiele_h1"] else "ok", "; ".join(czesci))

    al = a["alt"]
    if al["bez_alt"] or al["alt_todo"]:
        x = al["strony"][0]
        wiersz("Alt w obrazkach", "blad", f"bez alt: {al['bez_alt']}, alt=\"TODO\": {al['alt_todo']} z {al['obrazow']} "
                                          f"(stron: {len(al['strony'])}, np. {x['plik']}: {x['np']})")
        popraw(60, f"Opisz obrazy w `alt` (obrazów: {al['bez_alt'] + al['alt_todo']}, np. {x['plik']}: {x['np']}); "
                   "ozdobniki: `alt=\"\"`.")
    else:
        wiersz("Alt w obrazkach", "ok", f"obrazów w `<img>`: {al['obrazow']}, wszystkie z alt")

    o = a["obrazy"]
    opis = (f"plików: {o['liczba']}, razem {kb(o['bajty'])}; > 300 KB: {len(o['ponad_300kb'])}; "
            f"JPEG/PNG > 100 KB: {len(o['stary_format_ponad_100kb'])}")
    if o["najciezsze"]:
        opis += f"; najcięższy {o['najciezsze'][0]['plik']} ({kb(o['najciezsze'][0]['bajty'])})"
    wiersz("Obrazy (waga i format)",
           "blad" if o["ponad_300kb"] else "uwaga" if o["stary_format_ponad_100kb"] else "ok", opis)
    if o["ponad_300kb"]:
        x = o["ponad_300kb"][0]
        popraw(75, f"Zmniejsz obrazy > 300 KB do szerokości wyświetlania i skompresuj (zdjęcia WebP/AVIF, obraz OG "
                   f"JPEG), skill `optymalizacja-obrazow` (plików: {len(o['ponad_300kb'])}, np. {x['plik']}: "
                   f"{kb(x['bajty'])}).")
    elif o["stary_format_ponad_100kb"]:
        x = o["stary_format_ponad_100kb"][0]
        popraw(45, f"Zamień JPEG/PNG > 100 KB na WebP/AVIF (plików: {len(o['stary_format_ponad_100kb'])}, "
                   f"np. {x['plik']}: {kb(x['bajty'])}).")

    g = a["waga_glownej"]
    if g is None:
        wiersz("Waga strony głównej", "uwaga", "nie znalazłem strony głównej (index.html ani pl/, en/)")
    else:
        opis = f"{kb(g['razem'])}: HTML {kb(g['html'])}, CSS {kb(g['css'])}, JS {kb(g['js'])}, obrazy {kb(g['obrazy'])}"
        if g["zewnetrzne"]:
            opis += f"; zasoby z innych domen (niewliczone): {g['zewnetrzne']}"
        status = "blad" if g["razem"] > GLOWNA_BLAD else "uwaga" if g["razem"] > GLOWNA_UWAGA else "ok"
        wiersz("Waga strony głównej", status, opis)
        if status != "ok":
            najw = max(("css", "js", "obrazy"), key=lambda k: g[k])
            popraw(85 if status == "blad" else 55, f"Odchudź stronę główną ({g['plik']}: {kb(g['razem'])}, cel < 1 MB); "
                                                   f"najwięcej ważą {najw.upper() if najw != 'obrazy' else najw}: {kb(g[najw])}.")

    z = a["responsywnosc"]
    if "pominiete" in z:
        wiersz("Telefon i komputer (przewijanie w bok)", "uwaga", f"nie sprawdzone, zrzuty pominięte: {z['pominiete']}")
    else:
        tel = z["szerokosci"].get(str(SZER_TELEFON), {})
        kom = z["szerokosci"].get(str(SZER_KOMPUTER), {})
        czesci = []
        for szer, x in ((SZER_TELEFON, tel), (SZER_KOMPUTER, kom)):
            if x.get("przewijanie_w_bok"):
                czesci.append(f"{szer} px: przewija się w bok (treść {x['szerokosc_tresci']} px"
                              + (f", np. `{x['wystajace'][0]}`" if x["wystajace"] else "") + ")")
            else:
                czesci.append(f"{szer} px: bez przewijania w bok")
        wiersz("Telefon i komputer (przewijanie w bok)",
               "blad" if tel.get("przewijanie_w_bok") else "uwaga" if kom.get("przewijanie_w_bok") else "ok",
               "; ".join(czesci))
        for szer, x, waga in ((SZER_TELEFON, tel, 100), (SZER_KOMPUTER, kom, 55)):
            if x.get("przewijanie_w_bok"):
                popraw(waga, f"Usuń przewijanie w bok na {szer} px (index.html, treść {x['szerokosc_tresci']} px): "
                             f"wystaje {', '.join(f'`{e}`' for e in x['wystajace'][:3]) or 'element szerszy niż ekran'}; "
                             "`max-width: 100%`, zawijanie długich słów.")

    i = a["indeksowanie"]
    braki = [k for k, b in (("robots.txt", i["brak_robots"]), ("sitemap", i["brak_sitemap"])) if b]
    czesci = [f"brak {' i '.join(braki)}"] if braki else []
    for klucz, etykieta in (("noindex", "noindex"), ("bez_viewport", "bez viewport"), ("bez_lang", "bez lang"),
                            ("bez_canonical", "bez canonical"), ("zly_canonical", "zły canonical")):
        if i[klucz]:
            czesci.append(f"{etykieta} ({gdzie(i[klucz])})")
    glowna = (a["waga_glownej"] or {}).get("plik", "index.html")
    glowna_noindex = glowna in i["noindex"]
    status = "blad" if glowna_noindex or i["bez_viewport"] else "uwaga" if czesci else "ok"
    wiersz("Indeksowanie (robots.txt, sitemap, canonical, lang, viewport)", status,
           "; ".join(czesci) or "robots.txt, sitemap, canonical, lang i viewport w porządku")
    if glowna_noindex:
        popraw(95, f"Usuń `noindex` ze strony głównej ({glowna}): Google jej nie pokaże.")
    elif i["noindex"]:
        popraw(20, f"Sprawdź, czy `noindex` jest celowy ({gdzie(i['noindex'])}): te strony nie trafią do Google.")
    if i["bez_viewport"]:
        popraw(90, f"Dodaj `<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">` "
                   f"({gdzie(i['bez_viewport'])}).")
    if braki:
        popraw(40, f"Dodaj {' i '.join(braki)} w katalogu głównym (sitemap z adresami wszystkich stron: {n}).")
    if i["bez_lang"] or i["bez_canonical"] or i["zly_canonical"]:
        zle = sorted(set(i["bez_lang"]) | set(i["bez_canonical"]) | set(i["zly_canonical"]))
        co = [t for t, b in (("`<html lang=\"pl\">`", i["bez_lang"]),
                             ("bezwzględny `<link rel=\"canonical\">` na adres tej strony",
                              i["bez_canonical"] or i["zly_canonical"])) if b]
        popraw(30, f"Uzupełnij {' i '.join(co)} ({gdzie(zle)}).")

    og = a["udostepnianie"]
    if og["strony_z_bledami"]:
        x = og["np"][0]
        wiersz("Udostępnianie (Open Graph)", "uwaga", f"stron z brakami: {og['strony_z_bledami']}/{n} "
                                                      f"(np. {x['plik']}: {', '.join(x['braki'][:3])})")
        popraw(25, f"Dodaj og:title, og:image (1200×630) i twitter:card dla podglądu linku w Messengerze i na "
                   f"Facebooku (stron: {og['strony_z_bledami']}, np. {x['plik']}).")
    else:
        wiersz("Udostępnianie (Open Graph)", "ok", "og:title, og:image i twitter:card na każdej stronie")

    li = a["linki"]
    if li["martwe"]:
        x = li["martwe"][0]
        wiersz("Linki wewnętrzne", "blad",
               f"martwe: {len(li['martwe'])} z {li['sprawdzone']} (np. {x['plik']} → {x['href']})")
        popraw(80, f"Popraw albo usuń martwe linki wewnętrzne (linków: {len(li['martwe'])}, "
                   f"np. {x['plik']} → `{x['href']}`).")
    else:
        wiersz("Linki wewnętrzne", "ok", f"sprawdzonych: {li['sprawdzone']}, wszystkie prowadzą do plików")

    p.sort(key=lambda x: -x["waga"])
    return w, p[:POPRAWEK]


def raport_md(a: dict) -> str:
    czas = f"{a['czas_s']:.1f}".replace(".", ",")
    linie = [f"# Szybki audyt: {a['domena']}", "",
             f"Data: {a['data']} · stron: {a['strony']} · czas skryptu: {czas} s",
             "", "| Obszar | Wynik | Szczegóły |", "|---|---|---|"]
    for w in a["wiersze"]:
        linie.append(f"| {w['obszar']} | {ZNAK[w['status']]} | {w['opis'].replace('|', '/')} |")
    linie += ["", f"## {POPRAWEK} najważniejszych poprawek", ""]
    if a["poprawki"]:
        linie += [f"{k}. {x['tekst']}" for k, x in enumerate(a["poprawki"], 1)]
    else:
        linie.append("Brak poprawek z podstawowej listy.")
    z = a["responsywnosc"]
    linie.append("")
    if "pominiete" in z:
        linie.append(f"Zrzuty pominięte: {z['pominiete']}.")
    else:
        linie.append(f"Zrzuty: {', '.join(z['pliki'])}" + (f", montaż {z['montaz']}." if z.get("montaz")
                                                          else f"; {z.get('montaz_brak')}."))
    return "\n".join(linie) + "\n"


def audyt(katalog: Path, out: Path, domena: str | None, bez_zrzutow: bool) -> dict:
    t0 = time.monotonic()
    if not domena:
        try:
            domena = json.loads((katalog / ".strona.json").read_text(encoding="utf-8")).get("domena")
        except (OSError, ValueError, AttributeError):
            domena = None
    domena = (domena or katalog.resolve().name).lower().removeprefix("www.")
    seo, parsery = strony_i_seo(katalog)
    domeny = {domena}
    tytuly = ocen_tytuly(parsery)
    tytuly["duplikaty"] = [m for m in seo["witryna"]["errors"]
                           if m.startswith(("ten sam title", "ten sam description"))]
    a = {
        "domena": domena,
        "data": datetime.date.today().isoformat(),
        "strony": len(parsery),
        "progi": {"title": [TITLE_MIN, TITLE_MAX], "description": [DESC_MIN, DESC_MAX], "h1_na_strone": H1_NA_STRONE,
                  "obraz_blad_b": OBRAZ_BLAD, "obraz_stary_format_uwaga_b": OBRAZ_STARY_UWAGA,
                  "glowna_uwaga_b": GLOWNA_UWAGA, "glowna_blad_b": GLOWNA_BLAD,
                  "szerokosci": [SZER_TELEFON, SZER_KOMPUTER]},
        "tytuly": tytuly,
        "naglowki": ocen_naglowki(parsery),
        "alt": ocen_alt(parsery),
        "obrazy": ocen_obrazy(katalog, obrazy_udostepniania(katalog, parsery, domeny)),
        "waga_glownej": ocen_glowna(katalog, parsery, domeny),
        "indeksowanie": ocen_indeksowanie(seo),
        "udostepnianie": ocen_og(seo),
        "linki": ocen_linki(katalog, parsery, domeny),
        "responsywnosc": ({"pominiete": "uruchomione z --bez-zrzutow"} if bez_zrzutow else zrzuty(katalog, out)),
        "seo_check": {"summary": seo["summary"], "witryna": seo["witryna"]},
    }
    a["wiersze"], a["poprawki"] = wiersze_i_poprawki(a)
    a["czas_s"] = round(time.monotonic() - t0, 1)
    return a


def main(argv: list[str] | None = None) -> int:
    utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("katalog", help="lokalna kopia strony (public_html, dist)")
    ap.add_argument("--out", default="out/szybki-audyt", help="katalog wyniku (domyślnie out/szybki-audyt)")
    ap.add_argument("--domena", help="domena strony (domyślnie z .strona.json)")
    ap.add_argument("--bez-zrzutow", action="store_true", help="bez przeglądarki: zrzuty i przewijanie pominięte")
    ap.add_argument("--json", action="store_true", help="audyt.json na stdout zamiast podsumowania")
    args = ap.parse_args(argv)
    katalog = Path(args.katalog)
    if not katalog.is_dir():
        print(f"Błąd: {katalog} nie jest katalogiem", file=sys.stderr)
        return 1
    out = Path(args.out)
    try:
        out.mkdir(parents=True, exist_ok=True)
        a = audyt(katalog, out, args.domena, args.bez_zrzutow)
        (out / "audyt.json").write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
        (out / "raport.md").write_text(raport_md(a), encoding="utf-8")
    except OSError as exc:
        print(f"Błąd odczytu/zapisu: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(a, ensure_ascii=False, indent=1))
    else:
        for w in a["wiersze"]:
            print(f"{ZNAK[w['status']]} {w['obszar']}: {w['opis']}")
        print(f"Raport: {out / 'raport.md'} · czas: {a['czas_s']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
