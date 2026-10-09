"""Narzędzie `schemat`: SVG od agenta → PNG w rozmowie (pomysł Karpathy'ego: schemat rozumie się szybciej niż tekst).

Jarvo na Telegramie i w czacie HQ nie ma terminala, więc rysunek renderuje serwer: SVG trafia do strony z polityką
CSP bez sieci i skryptów (`default-src 'none'`), headless Chromium robi zrzut w rozmiarze rysunku (×2 dla ostrości),
a PNG ląduje w `<dane>/jarvo/workspaces/jarvo/schematy/` (podgląd w czacie HQ; Telegram wysyła świeży plik). Wynik ma
linię `MEDIA:<ścieżka>`, którą agent dokleja do odpowiedzi.
"""

from __future__ import annotations

import base64
import json
import os
import re
import select
import shutil
import subprocess
import tempfile
import time
import unicodedata
from pathlib import Path

MAX_ZNAKOW = 200_000
BOK = (200, 2400)                    # najmniejszy i największy bok rysunku w pikselach CSS
DOMYSLNY = (1200, 800)
CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:"
CHROMIUM = ("chromium", "chromium-browser", "google-chrome")

SCHEMA = {
    "name": "schemat",
    "description": ("Rysuje schemat dla właściciela: podajesz kod SVG, dostajesz PNG i linię MEDIA:<ścieżka> do wklejenia "
                    "w odpowiedź (obraz w rozmowie). Zasady rysunku: skill `schemat`. Bez sieci: obrazy tylko jako data:."),
    "parameters": {"type": "object", "properties": {
        "svg": {"type": "string", "description": "pełny element <svg> z width/height albo viewBox; podpisy po polsku"},
        "tytul": {"type": "string", "description": "krótki tytuł (nazwa pliku i podpis), np. „Jak działa skarbiec”"},
    }, "required": ["svg", "tytul"]},
}


def _liczba(v: str | None) -> float | None:
    m = re.match(r"\s*([\d.]+)\s*(px)?\s*$", v or "")
    return float(m.group(1)) if m else None


def _atrybuty(svg: str) -> dict:
    tag = re.search(r"<svg\b[^>]*>", svg, re.I | re.S)
    return dict(re.findall(r'([\w:-]+)\s*=\s*"([^"]*)"', tag.group(0))) if tag else {}


def rozmiar(svg: str) -> tuple[float, float]:
    """Rozmiar logiczny rysunku z width/height (px) albo viewBox; brak obu = 1200×800."""
    atr = _atrybuty(svg)
    w, h = _liczba(atr.get("width")), _liczba(atr.get("height"))
    vb = [float(x) for x in re.split(r"[\s,]+", atr.get("viewBox", "").strip()) if re.match(r"^-?[\d.]+$", x)]
    if (not w or not h) and len(vb) == 4 and vb[2] > 0 and vb[3] > 0:
        w, h = (w, w * vb[3] / vb[2]) if w else (h * vb[2] / vb[3], h) if h else (vb[2], vb[3])
    return (w, h) if w and h else DOMYSLNY


def wymiary(svg: str) -> tuple[int, int]:
    """Rozmiar zrzutu: rozmiar logiczny, za duży zmniejszony z zachowaniem proporcji, boki w granicach BOK."""
    w, h = rozmiar(svg)
    k = min(1.0, BOK[1] / max(w, h))                     # za duży: w dół; za mały: w górę, proporcje bez zmian
    k = k if k < 1 else max(1.0, BOK[0] / min(w, h))
    return tuple(int(min(BOK[1], max(BOK[0], round(x * k)))) for x in (w, h))


def strona(svg: str, w: int, h: int) -> str:
    """Strona do zrzutu: tylko rysunek, białe tło, CSP bez sieci i skryptów, SVG rozciągnięty na całe okno."""
    w0, h0 = rozmiar(svg)
    vb = "" if "viewBox" in _atrybuty(svg) else f' viewBox="0 0 {w0:g} {h0:g}"'   # skala bez przycinania

    def otwarcie(m: re.Match) -> str:
        tag = re.sub(r'\s(?:width|height)\s*=\s*"[^"]*"', "", m.group(0))
        return re.sub(r"^<svg", f'<svg width="{w}" height="{h}"{vb}', tag, count=1, flags=re.I)
    svg = re.sub(r"<script\b.*?</script\s*>", "", svg, flags=re.I | re.S)
    svg = re.sub(r"<svg\b[^>]*>", otwarcie, svg, count=1, flags=re.I | re.S)
    return (f'<!doctype html><html lang="pl"><head><meta charset="utf-8">'
            f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
            f"<style>html,body{{margin:0;background:#fff}}svg{{display:block}}"
            f"body{{font-family:'Inter','Segoe UI',system-ui,sans-serif}}</style></head><body>{svg}</body></html>")


def slug(tekst: str) -> str:
    s = unicodedata.normalize("NFKD", tekst.replace("ł", "l").replace("Ł", "L")).encode("ascii", "ignore").decode()
    return (re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "schemat")[:48]


def chromium() -> str | None:
    return os.environ.get("JARVO_CHROMIUM") or next((p for p in map(shutil.which, CHROMIUM) if p), None)


def renderuj(svg: str, tytul: str, katalog: Path, przegladarka: str | None = None) -> Path:
    przegladarka = przegladarka or chromium()
    if not przegladarka:
        raise RuntimeError("brak Chromium w kontenerze")
    w, h = wymiary(svg)
    katalog.mkdir(parents=True, exist_ok=True)
    out = katalog / f"{time.strftime('%Y%m%d-%H%M%S')}-{slug(tytul)}.png"
    # Chromium potrafi jeszcze dopisywać do profilu po wyjściu: resztki w /tmp nie mogą wywrócić gotowego zrzutu
    with tempfile.TemporaryDirectory(prefix="jarvo-schemat-", ignore_cleanup_errors=True) as tmp:
        src = Path(tmp) / "schemat.html"
        src.write_text(strona(svg, w, h), encoding="utf-8")
        bledy = Path(tmp) / "stderr.txt"
        try:
            with bledy.open("w") as err:
                png = _zrzut_cdp(przegladarka, src.as_uri(), w, h, f"{tmp}/profil", err, limit=60)
        except (OSError, RuntimeError, ValueError) as e:
            raise RuntimeError(f"Chromium nie zrobił zrzutu: {e}; {bledy.read_text(errors='replace').strip()[-300:]}")
    out.write_bytes(png)
    if not _pelny_png(out):
        out.unlink(missing_ok=True)
        raise RuntimeError("Chromium nie zrobił zrzutu: niepełny PNG")
    return out


def _pelny_png(plik: Path) -> bool:
    """Cały PNG: nagłówek i końcowy blok IEND (plik zapisany do końca)."""
    try:
        with plik.open("rb") as f:
            if f.read(8) != b"\x89PNG\r\n\x1a\n":
                return False
            f.seek(-12, 2)
            return f.read(12) == b"\x00\x00\x00\x00IEND\xaeB`\x82"
    except OSError:
        return False


def _zrzut_cdp(przegladarka: str, url: str, w: int, h: int, profil: str, err, limit: float) -> bytes:
    """Zrzut strony przez protokół DevTools na potoku (--remote-debugging-pipe: polecenia na fd 3, odpowiedzi na fd 4,
    JSON zakończony bajtem 0). Działa z chrome-headless-shell i z pełnym Chrome; sama flaga --screenshot w pełnym
    Chrome od wersji 15x nic nie zapisuje i wisi. Bez sieci i bez portu: tylko potok do własnego procesu."""
    do_chrome, my_pisz = os.pipe()
    my_czyt, od_chrome = os.pipe()

    def potoki() -> None:   # w procesie potomnym, przed exec: potoki jako fd 3 i 4
        os.dup2(do_chrome, 3)
        os.dup2(od_chrome, 4)

    p = subprocess.Popen([przegladarka, "--headless=new", "--remote-debugging-pipe", "--no-sandbox", "--disable-gpu",
                          "--hide-scrollbars", "--no-first-run", "--disable-extensions",
                          "--disable-background-networking", "--disable-component-update", "--disable-sync",
                          f"--window-size={w},{h}", f"--user-data-dir={profil}", "about:blank"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=err,
                         preexec_fn=potoki, close_fds=False)
    os.close(do_chrome)
    os.close(od_chrome)
    koniec = time.monotonic() + limit
    bufor = bytearray()
    numer = 0

    def czytaj() -> dict:
        while True:
            i = bufor.find(b"\0")
            if i >= 0:
                wiadomosc = bytes(bufor[:i])
                del bufor[:i + 1]
                return json.loads(wiadomosc)
            zostalo = koniec - time.monotonic()
            if zostalo <= 0:
                raise RuntimeError(f"brak odpowiedzi w {limit:g} s")
            if not select.select([my_czyt], [], [], zostalo)[0]:
                continue
            kawalek = os.read(my_czyt, 1 << 20)
            if not kawalek:
                raise RuntimeError(f"przeglądarka zakończyła pracę (kod {p.poll()})")
            bufor.extend(kawalek)

    def wyslij(metoda: str, sesja: str | None = None, **params) -> int:
        nonlocal numer
        numer += 1
        wiad = {"id": numer, "method": metoda, "params": params}
        if sesja:
            wiad["sessionId"] = sesja
        os.write(my_pisz, json.dumps(wiad).encode() + b"\0")
        return numer

    def wywolaj(metoda: str, sesja: str | None = None, **params) -> dict:
        nr = wyslij(metoda, sesja, **params)
        while True:
            m = czytaj()
            if m.get("id") == nr:
                if "error" in m:
                    raise RuntimeError(f"{metoda}: {m['error'].get('message')}")
                return m.get("result", {})

    try:
        cel = wywolaj("Target.createTarget", url="about:blank")["targetId"]
        sesja = wywolaj("Target.attachToTarget", targetId=cel, flatten=True)["sessionId"]
        wywolaj("Page.enable", sesja)
        wywolaj("Emulation.setDeviceMetricsOverride", sesja, width=w, height=h, deviceScaleFactor=2, mobile=False)
        nr = wyslij("Page.navigate", sesja, url=url)
        zaladowana = odpowiedz = False
        while not (zaladowana and odpowiedz):
            m = czytaj()
            if m.get("id") == nr:
                if "error" in m or m.get("result", {}).get("errorText"):
                    raise RuntimeError(f"Page.navigate: {m.get('error') or m['result']['errorText']}")
                odpowiedz = True
            elif m.get("method") == "Page.loadEventFired" and m.get("sessionId") == sesja:
                zaladowana = True
        dane = wywolaj("Page.captureScreenshot", sesja, format="png")["data"]
        try:
            wyslij("Browser.close")
        except OSError:
            pass
        return base64.b64decode(dane)
    finally:
        os.close(my_pisz)
        os.close(my_czyt)
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:   # nie zamknęła się sama: zamykamy
            p.kill()
            p.wait()


def katalog_schematow() -> Path:
    h = Path(os.environ.get("HERMES_HOME", "/opt/data"))
    korzen = h.parent.parent if h.parent.name == "profiles" else h
    return Path(os.environ.get("JARVO_SCHEMATY_DIR") or korzen / "jarvo" / "workspaces" / "jarvo" / "schematy")


def obsluz(args: dict, **_kw) -> str:
    """Handler narzędzia: walidacja, render, wynik JSON z linią MEDIA:."""
    svg, tytul = str((args or {}).get("svg") or ""), str((args or {}).get("tytul") or "schemat").strip()
    if not re.search(r"<svg\b", svg, re.I):
        return json.dumps({"error": "Podaj kod SVG (element <svg> … </svg>)."}, ensure_ascii=False)
    if len(svg) > MAX_ZNAKOW:
        return json.dumps({"error": f"SVG ma {len(svg)} znaków (maks. {MAX_ZNAKOW}): uprość rysunek."}, ensure_ascii=False)
    try:
        png = renderuj(svg, tytul, katalog_schematow())
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        return json.dumps({"error": f"Nie udało się narysować schematu: {exc}"}, ensure_ascii=False)
    return json.dumps({"ok": True, "plik": str(png), "rozmiar": "×".join(map(str, wymiary(svg))),
                       "media": f"MEDIA:{png}", "dalej": f"Wklej do odpowiedzi linię MEDIA:{png} i jedno zdanie, "
                       f"co pokazuje „{tytul}”. Popraw rysunek, jeśli tekst wychodzi poza ramki."},
                      ensure_ascii=False)
