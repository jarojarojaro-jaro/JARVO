#!/usr/bin/env python3
"""Ostrożna przeglądarka: jedna publiczna strona przez Camoufox, gdy zwykła przeglądarka dostała odmowę.

    ostrozna.py <url>                         # Markdown głównej treści (trafilatura, z linkami) na stdout
    ostrozna.py <url> -o strona.md            # to samo do pliku
    ostrozna.py <url> --html -o strona.html   # HTML po wykonaniu JavaScriptu
    ostrozna.py <url> --zrzut strona.png      # zrzut całej strony (PNG)
    ostrozna.py <url> --json                  # wynik i metadane jako JSON
    ostrozna.py --sprawdz                     # czy przeglądarka jest w obrazie (bez sieci; healthcheck)

Tylko po blokadzie zwykłej drogi (extract.py, strona.py, browser_* z Lightpandą albo Chromium): 403/429,
„Just a moment…”, „Human Verification”, captcha. Nigdy domyślnie. Camoufox to Firefox z podmienionym odciskiem
przeglądarki (MPL-2.0, `/opt/jarvo/camoufox`); RAM ok. 800 MB na czas jednej strony.

Zasady pilnowane w kodzie, nie tylko w skillu:
- jedna strona na wywołanie, jedna przeglądarka naraz na serwerze (blokada pliku), co najmniej 20 s między
  stronami jednej domeny i najwyżej 30 stron jednej domeny na dobę,
- tylko http(s) i adresy publiczne (bez localhost i sieci prywatnych),
- robots.txt sprawdzany tą samą przeglądarką: zakaz albo robots.txt niedostępny (401/403/429/5xx) = blokada,
- strona „sprawdzamy, czy jesteś człowiekiem” może sama przepuścić zwykłą przeglądarkę: skrypt czeka do 15 s, ale
  niczego nie klika i nie rozwiązuje captchy; captcha, kod 401/403/429 albo formularz logowania = blokada,
- czysty profil przy każdym uruchomieniu: bez ciasteczek, kont, proxy i dodatków; nie próbuje drugi raz.

Kody wyjścia: 0 strona przeczytana, 1 błąd (sieć, 404, awaria przeglądarki), 2 zły adres, 3 blokada (koniec,
zgłoś ją; zasada 16), 4 limit (odstęp, dzienny limit domeny albo przeglądarka zajęta zbyt długo).
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import html as htmlmod
import ipaddress
import json
import os
import re
import socket
import sys
import time
import urllib.parse
import urllib.robotparser
from pathlib import Path

TOOLS_PY = "/opt/jarvo/venv/bin/python"
EXE = os.environ.get("JARVO_CAMOUFOX", "/opt/jarvo/camoufox/camoufox-bin")
STAN = Path(os.environ.get("JARVO_OSTROZNA_STAN", str(Path.home() / ".cache" / "jarvo-ostrozna")))
ODSTEP_S = 20.0            # minimum między stronami jednej domeny
DZIENNIE = 30              # stron jednej domeny na dobę
CZEKAJ_NA_ZAJETA_S = 180   # ile czekać, aż inna kopia skryptu zwolni przeglądarkę
CZEKAJ_NA_STRAZNIKA_S = 15  # strona „Just a moment…” może sama przepuścić przeglądarkę
TIMEOUT_MS = 45_000
ROBOT = "jarvo"            # nazwa w robots.txt; obowiązują też reguły dla „*”

TYTULY_BLOKADY = re.compile(
    r"just a moment|attention required|human verification|verify you are human|checking your browser|"
    r"are you a robot|robot check|access denied|pardon our interruption|security check|captcha|"
    r"jeste[śs] robotem|weryfikacja|dost[ęe]p zablokowany|sprawdzamy", re.I)
ZNACZNIKI_BLOKADY = ("cf-chl", "challenge-platform", "/cdn-cgi/challenge", "_Incapsula_Resource", "px-captcha",
                     "captcha-delivery.com", "geo.captcha", "Request unsuccessful", "cf-turnstile", "g-recaptcha",
                     "h-captcha", "hcaptcha.com", "unusual traffic", "Human Verification")
KROTKA_STRONA = 1500       # znaczniki captchy liczą się tylko na stronie bez treści (formularz z reCAPTCHA to nie blokada)


class ZlyAdres(Exception):
    """Kod 2."""


class Blokada(Exception):
    """Kod 3: źródło odmówiło. Koniec, nie zagadka."""


class Limit(Exception):
    """Kod 4."""


# ------------------------------------------------------------------ adres i robots.txt

def sprawdz_adres(url: str) -> str:
    """Publiczny adres http(s) albo ZlyAdres. Bez schematu dopisuje https://."""
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    u = urllib.parse.urlsplit(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ZlyAdres(f"{url}: tylko adresy http(s) stron publicznych")
    if u.username or u.password:
        raise ZlyAdres(f"{url}: adres z loginem albo hasłem; logowanie nie wchodzi w grę (zasada 16)")
    host = u.hostname.lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".lan")):
        raise ZlyAdres(f"{host}: adres wewnętrzny, nie strona publiczna")
    try:
        adresy = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            adresy = {ipaddress.ip_address(a[4][0].split("%")[0]) for a in socket.getaddrinfo(host, None)}
        except (socket.gaierror, UnicodeError, ValueError):
            adresy = set()             # nieznana nazwa: przeglądarka sama zgłosi błąd sieci
    for ip in adresy:
        if not ip.is_global:
            raise ZlyAdres(f"{host}: adres {ip} nie jest publiczny")
    return url


def robots_url(url: str) -> str:
    u = urllib.parse.urlsplit(url)
    return f"{u.scheme}://{u.netloc}/robots.txt"


def ocen_robots(kod: int | None, tresc: str, url: str) -> None:
    """Blokada, gdy robots.txt zabrania strony albo nie da się go przeczytać (nie wiemy, czy wolno)."""
    if kod in (404, 410):
        return
    if kod != 200 or tresc.lstrip()[:1] == "<" or any(z in tresc[:4000] for z in ZNACZNIKI_BLOKADY):
        raise Blokada(f"robots.txt niedostępny (kod {kod}): nie wiadomo, czy wolno czytać stronę")
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(tresc.splitlines())
    if not (rp.can_fetch(ROBOT, url) and rp.can_fetch("*", url)):
        raise Blokada("robots.txt zabrania tej strony")


# ------------------------------------------------------------------ rozpoznanie blokady

def oznaka_blokady(kod: int | None, tytul: str, tekst: str, html: str) -> str | None:
    """Powód blokady albo None. `tekst` to widoczny tekst strony."""
    if kod in (401, 407):
        return f"strona wymaga logowania (kod {kod})"
    if kod in (403, 429):
        return f"serwis odmówił (kod {kod})"
    if TYTULY_BLOKADY.search(tytul or ""):
        return f"strona sprawdzania automatów („{(tytul or '').strip()[:60]}”)"
    if len(tekst.strip()) < KROTKA_STRONA:
        for z in ZNACZNIKI_BLOKADY:
            if z.lower() in html.lower():
                return f"strona sprawdzania automatów albo captcha ({z})"
    if kod is not None and kod >= 500 and any(z.lower() in html.lower() for z in ZNACZNIKI_BLOKADY):
        return f"serwis odmówił (kod {kod}, ochrona przed automatami)"
    return None


# ------------------------------------------------------------------ limity

@contextlib.contextmanager
def jedna_naraz(katalog: Path = None, czekaj_s: float = None):
    """Jedna przeglądarka naraz na serwerze (subagenci Sherlocka nie odpalą trzech Firefoksów po 800 MB)."""
    katalog = katalog or STAN
    czekaj_s = CZEKAJ_NA_ZAJETA_S if czekaj_s is None else czekaj_s
    katalog.mkdir(parents=True, exist_ok=True)
    with open(katalog / "przegladarka.lock", "w", encoding="utf-8") as f:
        koniec = time.monotonic() + czekaj_s
        while True:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= koniec:
                    raise Limit(f"przeglądarka zajęta przez inne zadanie dłużej niż {int(czekaj_s)} s; spróbuj później")
                time.sleep(1)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def rezerwuj(host: str, teraz: float | None = None, katalog: Path = None) -> float:
    """Zapisuje wizytę w domenie; zwraca, ile sekund poczekać przed nią. Limit przy przekroczeniu doby."""
    katalog = katalog or STAN
    teraz = time.time() if teraz is None else teraz
    plik = katalog / "domeny.json"
    try:
        stan = json.loads(plik.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stan = {}
    stan = {h: [t for t in ts if teraz - t < 86400] for h, ts in stan.items() if isinstance(ts, list)}
    wizyty = sorted(stan.get(host, []))
    if len(wizyty) >= DZIENNIE:
        raise Limit(f"{host}: {DZIENNIE} stron na dobę już przeczytane tą przeglądarką; zgłoś to zamiast szukać innej drogi")
    start = max(teraz, (wizyty[-1] + ODSTEP_S) if wizyty else teraz)
    stan[host] = wizyty + [start]
    katalog.mkdir(parents=True, exist_ok=True)
    tmp = plik.with_suffix(".tmp")
    tmp.write_text(json.dumps({h: ts for h, ts in stan.items() if ts}), encoding="utf-8")
    tmp.replace(plik)
    return start - teraz


# ------------------------------------------------------------------ treść

def na_markdown(html: str, url: str) -> str:
    """Główna treść jako Markdown (trafilatura); bez niej prosty tekst strony."""
    try:
        import trafilatura  # type: ignore
    except ImportError:
        trafilatura = None
    if trafilatura is not None:
        md = trafilatura.extract(html, url=url, output_format="markdown", include_links=True, include_tables=True,
                                 include_comments=False, with_metadata=False)
        if md and md.strip():
            return md.strip() + "\n"
    body = re.sub(r"<(script|style|noscript|template)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    tekst = htmlmod.unescape(re.sub(r"<[^>]+>", " ", body))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", tekst)).strip() + "\n"


# ------------------------------------------------------------------ przeglądarka

def ma_camoufox() -> bool:
    import importlib.util

    return importlib.util.find_spec("camoufox") is not None


def _przelacz_na_venv_narzedzi() -> None:
    """camoufox i trafilatura żyją w /opt/jarvo/venv; uruchomieni innym Pythonem przełączamy się."""
    if os.path.exists(TOOLS_PY) and os.path.realpath(sys.executable) != os.path.realpath(TOOLS_PY):
        os.execv(TOOLS_PY, [TOOLS_PY, os.path.abspath(__file__), *sys.argv[1:]])


def wersja_firefoksa(katalog: Path | None = None) -> int:
    """Główna wersja Firefoksa z application.ini paczki (camoufox szuka jej tylko we własnym katalogu pobrań)."""
    ini = (katalog or Path(EXE).parent) / "application.ini"
    m = re.search(r"^Version=(\d+)\.", ini.read_text(encoding="utf-8", errors="replace"), re.M)
    if not m:
        raise RuntimeError(f"{ini}: brak wersji przeglądarki")
    return int(m.group(1))


def opcje_camoufox(zrzut: bool) -> dict:
    from camoufox import DefaultAddons  # type: ignore

    return {
        "executable_path": EXE,
        "ff_version": wersja_firefoksa(),     # zgodna z binarką, więc odcisk pasuje do prawdziwej wersji
        "headless": True,                      # bez Xvfb i bez okna
        "os": "linux",                         # w obrazie są tylko fonty Linuksa z paczki Camoufoxa
        "locale": "pl-PL",
        "geoip": False,
        "humanize": False,                     # skrypt nie rusza myszą i niczego nie klika
        "block_webrtc": True,
        "block_images": not zrzut,
        "exclude_addons": [DefaultAddons.UBO],  # bez pobierania dodatków z sieci przy starcie
        "i_know_what_im_doing": True,
    }


@contextlib.contextmanager
def otworz(zrzut: bool = False):
    """Przeglądarka z czystym profilem (testy podmieniają tę funkcję)."""
    # pliki przeglądarki (profil Firefoksa, cache fontów, „Downloads”) w katalogu skryptu, nie w katalogu domowym
    dom = STAN / "dom"
    dom.mkdir(parents=True, exist_ok=True)
    os.environ["HOME"] = str(dom)
    os.environ["XDG_CACHE_HOME"] = str(dom / ".cache")
    from camoufox.sync_api import Camoufox  # type: ignore

    with Camoufox(**opcje_camoufox(zrzut)) as przegladarka:
        yield przegladarka


def _stan_strony(page) -> tuple[str, str, str]:
    tytul = page.title() or ""
    html = page.content() or ""
    try:
        tekst = page.inner_text("body", timeout=5000) or ""
    except Exception:  # noqa: BLE001 (strona bez <body> albo w trakcie przeładowania)
        tekst = ""
    return tytul, tekst, html


def _ma_logowanie(page) -> bool:
    try:
        return page.locator("input[type=password]:visible").count() > 0
    except Exception:  # noqa: BLE001
        return False


def czytaj(url: str, tryb: str = "markdown", zrzut: str | None = None, czekaj_s: float = None) -> dict:
    """Jedna strona: robots.txt → strona → ocena blokady → treść. Wyjątki: Blokada, ConnectionError."""
    czekaj_s = CZEKAJ_NA_STRAZNIKA_S if czekaj_s is None else czekaj_s
    with otworz(zrzut=bool(zrzut)) as przegladarka:
        page = przegladarka.new_page()
        try:
            r = page.goto(robots_url(url), wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            ocen_robots(r.status if r else None, (r.text() if r else "") or "", url)
        except Blokada:
            raise
        except Exception as e:  # noqa: BLE001 (sieć, DNS, TLS)
            raise ConnectionError(f"robots.txt: {str(e).splitlines()[0][:200]}") from e
        nawigacja: dict = {}            # kod ostatniej odpowiedzi dokumentu głównego (strażnik przeładowuje stronę)

        def _odpowiedz(resp) -> None:
            with contextlib.suppress(Exception):
                if resp.request.is_navigation_request() and resp.frame == page.main_frame:
                    nawigacja["kod"] = resp.status

        page.on("response", _odpowiedz)
        try:
            r = page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        except Exception as e:  # noqa: BLE001
            raise ConnectionError(str(e).splitlines()[0][:200]) from e
        kod = r.status if r else None
        nawigacja["kod"] = kod
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=8000)
        tytul, tekst, html = _stan_strony(page)
        powod = oznaka_blokady(nawigacja.get("kod"), tytul, tekst, html)
        if powod and kod not in (401, 407, 429):
            # strażnik typu „Just a moment…” (zwykle kod 403 albo 503) bywa nieinteraktywny: zwykła przeglądarka
            # przechodzi sama po kilku sekundach, a strona przeładowuje się z nowym kodem. Czekamy bez klikania;
            # interaktywna captcha zostaje na ekranie i kończy się blokadą.
            koniec = time.monotonic() + czekaj_s
            while powod and time.monotonic() < koniec:
                page.wait_for_timeout(1000)
                tytul, tekst, html = _stan_strony(page)
                powod = oznaka_blokady(nawigacja.get("kod"), tytul, tekst, html)
        kod = nawigacja.get("kod", kod)
        if powod:
            raise Blokada(powod)
        if _ma_logowanie(page) and len(tekst.strip()) < KROTKA_STRONA:
            raise Blokada("strona pokazuje tylko formularz logowania; nie logujemy się (zasada 16)")
        if kod is not None and kod >= 400:
            raise ConnectionError(f"kod HTTP {kod}")
        wynik = {"url": url, "url_koncowy": page.url, "kod": kod, "tytul": tytul.strip(), "tryb": tryb}
        if zrzut:
            Path(zrzut).parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=zrzut, full_page=True)
            wynik["zrzut"] = str(zrzut)
        wynik["tresc"] = html if tryb == "html" else (na_markdown(html, page.url) if tryb == "markdown" else "")
        return wynik


def sprawdz() -> int:
    """Healthcheck bez sieci i bez uruchamiania przeglądarki: pakiet, binarka, fonty i konfiguracja Linuksa."""
    braki = []
    if not ma_camoufox():
        braki.append("pakiet camoufox (venv /opt/jarvo/venv)")
    katalog = Path(EXE).parent
    if not os.access(EXE, os.X_OK):
        braki.append(f"binarka {EXE}")
    for p in ("fontconfig/linux/fonts.conf", "fonts/linux", "properties.json"):
        if not (katalog / p).exists():
            braki.append(str(katalog / p))
    if braki:
        print("✗ brak: " + ", ".join(braki), file=sys.stderr)
        return 1
    print(f"✓ Camoufox gotowy: {EXE}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?")
    tryb = ap.add_mutually_exclusive_group()
    tryb.add_argument("--markdown", action="store_true", help="główna treść jako Markdown (domyślnie)")
    tryb.add_argument("--html", action="store_true", help="HTML po wykonaniu JavaScriptu")
    tryb.add_argument("--zrzut", metavar="PLIK.png", help="zrzut całej strony")
    ap.add_argument("-o", "--wyjscie", metavar="PLIK", help="zapisz treść do pliku zamiast na stdout")
    ap.add_argument("--json", action="store_true", help="wynik jako JSON")
    ap.add_argument("--max-znakow", type=int, default=20000, help="limit treści na stdout (plik zawsze w całości)")
    ap.add_argument("--sprawdz", action="store_true", help="czy przeglądarka jest zainstalowana (bez sieci)")
    a = ap.parse_args(argv)
    if not ma_camoufox():
        _przelacz_na_venv_narzedzi()
    if a.sprawdz:
        return sprawdz()
    if not a.url:
        ap.error("podaj adres strony albo --sprawdz")
    tryb_ = "html" if a.html else ("zrzut" if a.zrzut else "markdown")
    try:
        url = sprawdz_adres(a.url)
        host = urllib.parse.urlsplit(url).hostname
        with jedna_naraz():
            pauza = rezerwuj(host)
            if pauza > 0:
                time.sleep(pauza)
            wynik = czytaj(url, tryb_, a.zrzut)
    except ZlyAdres as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    except Blokada as e:
        print(f"✗ blokada: {e}. Koniec próby: zapisz w risks i zgłoś (zasada 16); bez kolejnej drogi.", file=sys.stderr)
        if a.json:
            print(json.dumps({"url": a.url, "blokada": str(e)}, ensure_ascii=False))
        return 3
    except Limit as e:
        print(f"✗ limit: {e}", file=sys.stderr)
        return 4
    except ConnectionError as e:
        print(f"✗ {a.url}: {e}", file=sys.stderr)
        return 1
    except ImportError:
        print("✗ brak Camoufoxa: działa w obrazie Jarvo (ostrozna.py --sprawdz)", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 (awaria przeglądarki: bez śladu stosu w odpowiedzi agenta)
        print(f"✗ przeglądarka: {str(e).splitlines()[0][:300] if str(e) else type(e).__name__}", file=sys.stderr)
        return 1
    tresc = wynik.pop("tresc")
    wynik["znaki"] = len(tresc)
    if a.wyjscie:
        Path(a.wyjscie).parent.mkdir(parents=True, exist_ok=True)
        Path(a.wyjscie).write_text(tresc, encoding="utf-8")
        wynik["plik"] = a.wyjscie
        tresc = ""
    elif len(tresc) > a.max_znakow:
        tresc, wynik["uciete"] = tresc[:a.max_znakow], True
    if a.json:
        print(json.dumps({**wynik, "tresc": tresc}, ensure_ascii=False, indent=1))
        return 0
    print(f"# {wynik['tytul'] or '(bez tytułu)'}\nURL: {wynik['url_koncowy']} (kod {wynik['kod']}, Camoufox)")
    if wynik.get("plik"):
        print(f"zapisane: {wynik['plik']} ({wynik['znaki']} znaków)")
    if wynik.get("zrzut"):
        print(f"zrzut: {wynik['zrzut']}")
    if tresc:
        print()
        print(tresc.rstrip())
        if wynik.get("uciete"):
            print("\n[… ucięte, użyj -o PLIK albo --max-znakow]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
