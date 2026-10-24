"""Narzędzie `schemat`: SVG od agenta → PNG w rozmowie (pomysł Karpathy'ego: schemat rozumie się szybciej niż tekst).

Jarvo na Telegramie i w czacie HQ nie ma terminala, więc rysunek renderuje serwer: SVG trafia do strony z polityką
CSP bez sieci i skryptów (`default-src 'none'`), headless Chromium robi zrzut w rozmiarze rysunku (×2 dla ostrości),
a PNG ląduje w `<dane>/jarvo/workspaces/jarvo/schematy/` (podgląd w czacie HQ; Telegram wysyła świeży plik). Wynik ma
linię `MEDIA:<ścieżka>`, którą agent dokleja do odpowiedzi. Na Windows (docs/NATYWNIE.md K05) przeglądarka to
JARVO_CHROMIUM, CHROME_PATH (chrome-headless-shell instalatora) albo zainstalowany Chrome lub Edge, a potok DevTools
idzie przez uchwyty z `--remote-debugging-io-pipes`, bo fd 3/4 i preexec_fn tam nie istnieją.
"""

from __future__ import annotations

import base64
import json
import os
import queue
import re
import select
import shutil
import subprocess
import tempfile
import threading
import time
import unicodedata
from pathlib import Path

MAX_ZNAKOW = 200_000
BOK = (200, 2400)                    # najmniejszy i największy bok rysunku w pikselach CSS
DOMYSLNY = (1200, 800)
CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:"
CHROMIUM = ("chromium", "chromium-browser", "google-chrome")
WINDOWS = os.name == "nt"
CHROMIUM_WINDOWS = ("chrome", "msedge", "chromium")          # nazwy w PATH na Windows, potem typowe miejsca instalacji
INSTALACJE_WINDOWS = (("PROGRAMFILES", "Google", "Chrome", "Application", "chrome.exe"),
                      ("PROGRAMFILES(X86)", "Google", "Chrome", "Application", "chrome.exe"),
                      ("LOCALAPPDATA", "Google", "Chrome", "Application", "chrome.exe"),
                      ("PROGRAMFILES(X86)", "Microsoft", "Edge", "Application", "msedge.exe"),
                      ("PROGRAMFILES", "Microsoft", "Edge", "Application", "msedge.exe"))

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
    """JARVO_CHROMIUM albo przeglądarka z PATH; na Windows także CHROME_PATH i Chrome lub Edge z typowych miejsc."""
    if os.environ.get("JARVO_CHROMIUM"):
        return os.environ["JARVO_CHROMIUM"]
    if not WINDOWS:
        return next((p for p in map(shutil.which, CHROMIUM) if p), None)
    kandydaci = [os.environ.get("CHROME_PATH"), *map(shutil.which, CHROMIUM_WINDOWS)]
    kandydaci += [os.path.join(os.environ[z], *czesci) for z, *czesci in INSTALACJE_WINDOWS if os.environ.get(z)]
    return next((k for k in kandydaci if k and os.path.isfile(k)), None)


def renderuj(svg: str, tytul: str, katalog: Path, przegladarka: str | None = None) -> Path:
    przegladarka = przegladarka or chromium()
    if not przegladarka:
        raise RuntimeError("brak Chrome, Edge ani chrome-headless-shell (ustaw JARVO_CHROMIUM)" if WINDOWS
                           else "brak Chromium w kontenerze")
    w, h = wymiary(svg)
    katalog.mkdir(parents=True, exist_ok=True)
    out = katalog / f"{time.strftime('%Y%m%d-%H%M%S')}-{slug(tytul)}.png"
    # Chromium potrafi jeszcze dopisywać do profilu po wyjściu: resztki w /tmp nie mogą wywrócić gotowego zrzutu
    with tempfile.TemporaryDirectory(prefix="jarvo-schemat-", ignore_cleanup_errors=True) as tmp:
        src = Path(tmp) / "schemat.html"
        src.write_text(strona(svg, w, h), encoding="utf-8", newline="\n")
        bledy = Path(tmp) / "stderr.txt"
        try:
            with bledy.open("wb") as err:
                png = _zrzut_cdp(przegladarka, src.as_uri(), w, h, f"{tmp}/profil", err, limit=60)
        except (OSError, RuntimeError, ValueError) as e:
            raise RuntimeError(f"Chromium nie zrobił zrzutu: {e}; "
                               f"{bledy.read_text(encoding='utf-8', errors='replace').strip()[-300:]}")
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


def _potok_posix(argv: list, err):
    """POSIX: potoki jako fd 3 (polecenia) i 4 (odpowiedzi) w procesie potomnym, odpowiedzi przez select.
    Zwraca (proces, pisz(bajty), kawalek(limit) → bajty | b"" koniec | None nic w tym czasie, zamknij())."""
    do_chrome, my_pisz = os.pipe()
    my_czyt, od_chrome = os.pipe()

    def potoki() -> None:   # w procesie potomnym, przed exec: potoki jako fd 3 i 4
        os.dup2(do_chrome, 3)
        os.dup2(od_chrome, 4)

    try:
        p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=err,
                             preexec_fn=potoki, close_fds=False)
    except BaseException:
        for fd in (do_chrome, my_pisz, my_czyt, od_chrome):
            os.close(fd)
        raise
    os.close(do_chrome)
    os.close(od_chrome)

    def kawalek(zostalo: float) -> bytes | None:
        if not select.select([my_czyt], [], [], zostalo)[0]:
            return None
        return os.read(my_czyt, 1 << 20)

    def zamknij() -> None:
        os.close(my_pisz)
        os.close(my_czyt)
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:   # nie zamknęła się sama: zamykamy
            p.kill()
            p.wait()

    return p, lambda dane: os.write(my_pisz, dane), kawalek, zamknij


def _potok_windows(argv: list, err):
    """Windows: bez fd 3/4 i preexec_fn. Przeglądarka dostaje uchwyty potoków w --remote-debugging-io-pipes=<odczyt>,<zapis>
    i dziedziczy tylko je (handle_list); select nie działa na potokach, więc odpowiedzi czyta wątek. To samo co _potok_posix."""
    import msvcrt
    do_chrome, my_pisz = os.pipe()
    my_czyt, od_chrome = os.pipe()
    uchwyty = [msvcrt.get_osfhandle(do_chrome), msvcrt.get_osfhandle(od_chrome)]
    si = subprocess.STARTUPINFO()
    si.lpAttributeList = {"handle_list": uchwyty}
    try:
        for u in uchwyty:
            os.set_handle_inheritable(u, True)
        p = subprocess.Popen([*argv[:-1], f"--remote-debugging-io-pipes={uchwyty[0]},{uchwyty[1]}", argv[-1]],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=err, startupinfo=si,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    except BaseException:
        os.close(my_pisz)
        os.close(my_czyt)
        raise
    finally:
        os.close(do_chrome)                 # przeglądarka ma własne kopie uchwytów
        os.close(od_chrome)
    kawalki: queue.Queue = queue.Queue()

    def czytnik() -> None:                  # do końca potoku (przeglądarka zakończyła pracę), potem zamyka swój koniec
        try:
            while True:
                try:
                    dane = os.read(my_czyt, 1 << 20)
                except OSError:
                    dane = b""
                kawalki.put(dane)
                if not dane:
                    return
        finally:
            os.close(my_czyt)

    watek = threading.Thread(target=czytnik, name="jarvo-schemat-cdp", daemon=True)
    watek.start()

    def kawalek(zostalo: float) -> bytes | None:
        try:
            return kawalki.get(timeout=zostalo)
        except queue.Empty:
            return None

    def zamknij() -> None:
        os.close(my_pisz)                   # koniec poleceń: przeglądarka zamyka się sama
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:   # nie zamknęła się sama: całe drzewo procesów, jak Puppeteer na Windows
            _zabij_drzewo(p)
        watek.join(timeout=5)

    return p, lambda dane: os.write(my_pisz, dane), kawalek, zamknij


def _zabij_drzewo(p: subprocess.Popen) -> None:
    """Windows: proces przeglądarki z potomnymi (renderer, a w testach Python za nakładką .cmd); taskkill /T tylko tu."""
    taskkill = os.path.join(os.environ.get("SystemRoot") or r"C:\Windows", "System32", "taskkill.exe")
    try:
        subprocess.run([taskkill, "/PID", str(p.pid), "/T", "/F"], stdin=subprocess.DEVNULL, capture_output=True,
                       timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        pass
    p.kill()
    p.wait()


def _zrzut_cdp(przegladarka: str, url: str, w: int, h: int, profil: str, err, limit: float) -> bytes:
    """Zrzut strony przez protokół DevTools na potoku (--remote-debugging-pipe, JSON zakończony bajtem 0): na POSIX
    polecenia na fd 3 i odpowiedzi na fd 4, na Windows uchwyty potoków z --remote-debugging-io-pipes. Działa
    z chrome-headless-shell i z pełnym Chrome; sama flaga --screenshot w pełnym Chrome od wersji 15x nic nie zapisuje
    i wisi. Bez sieci i bez portu: tylko potok do własnego procesu. --no-sandbox tylko na POSIX (kontener); na Windows
    piaskownica działa bez uprawnień administratora i zostaje (renderer dostaje SVG od modelu)."""
    argv = [przegladarka, "--headless=new", "--remote-debugging-pipe", *([] if WINDOWS else ["--no-sandbox"]), "--disable-gpu",
            "--hide-scrollbars", "--no-first-run", "--disable-extensions",
            "--disable-background-networking", "--disable-component-update", "--disable-sync",
            f"--window-size={w},{h}", f"--user-data-dir={profil}", "about:blank"]
    p, pisz, kawalek, zamknij = (_potok_windows if WINDOWS else _potok_posix)(argv, err)
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
            dane = kawalek(zostalo)
            if dane is None:
                continue
            if not dane:
                raise RuntimeError(f"przeglądarka zakończyła pracę (kod {p.poll()})")
            bufor.extend(dane)

    def wyslij(metoda: str, sesja: str | None = None, **params) -> int:
        nonlocal numer
        numer += 1
        wiad = {"id": numer, "method": metoda, "params": params}
        if sesja:
            wiad["sessionId"] = sesja
        pisz(json.dumps(wiad).encode() + b"\0")
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
        zamknij()


def _hermes_home() -> str:
    """HERMES_HOME procesu; bez zmiennej katalog domowy Hermesa (hermes_constants), poza Hermesem /opt/data (kontener)."""
    if os.environ.get("HERMES_HOME"):
        return os.environ["HERMES_HOME"]
    try:
        from hermes_constants import get_hermes_home
        return str(get_hermes_home())
    except Exception:
        return "/opt/data"


def katalog_schematow() -> Path:
    h = Path(_hermes_home())
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
    sciezka = png.as_posix()              # na Windows C:/… zamiast C:\…: agent przepisuje linię MEDIA: bez ucieczek „\”
    return json.dumps({"ok": True, "plik": sciezka, "rozmiar": "×".join(map(str, wymiary(svg))),
                       "media": f"MEDIA:{sciezka}", "dalej": f"Wklej do odpowiedzi linię MEDIA:{sciezka} i jedno zdanie, "
                       f"co pokazuje „{tytul}”. Popraw rysunek, jeśli tekst wychodzi poza ramki."},
                      ensure_ascii=False)
