#!/usr/bin/env python3
"""Panel Jarva na instalacji natywnej, na żywo w przeglądarce (docs/NATYWNIE.md etap E6, docs/HQ.md §2c i §2f).

    <python z Playwrightem> natywnie_panel.py --wyniki <katalog> [--korzen <JARVO_ROOT>] [--przegladarka <plik>]
        [--kanal chrome|msedge] [--atrapa-port N] [--prawdziwy-chatgpt] [--folder] [--restart-panelu] [--zostaw]
        [--punkty 1,2,3]

Python z paczką playwright (venv narzędzi instalacji: playwright 1.62 z locka infra/python/natywne/narzedzia.lock,
albo osobny venv z tymi samymi sumami); przeglądarka: --przegladarka, potem CHROME_PATH z `<stan>/narzedzia.json`
(chrome-headless-shell z manifestu), potem Chromium Playwrighta, na końcu Chrome albo Edge z systemu (--kanal).
Panel: http://127.0.0.1:<port> z JARVO_PANEL_PORT, `<stan>/ustawienia.json` albo 9119; korzeń jak w poleceniu
jarvo (--korzen, JARVO_ROOT, domyślny katalog systemu). Uruchamia go CI na instalacji od zera (artefakty z --wyniki).

Punkty:
  1. wejście bez hasła: http://127.0.0.1:<port>/ prowadzi na /jarvo (powłoka Jarva z łatki dista), tytuł „Jarvo”,
     index.html z tokenem sesji (`__HERMES_AUTH_REQUIRED__ === false`), żadnej strony logowania i żadnej odpowiedzi
     401; strumień aplikacji idzie przez fetch z nagłówkiem tokenu (EventSource by go nie wysłał, I11, W11);
     klasyczny panel (/sessions) ma w menu „Jarvo” i „Restart gatewaya”, a nie ma „Aktualizuj Hermesa” (H16)
  2. pierwsze spotkanie od pustego USER.md: imię, firma, linki, cel → pola w USER.md skarbca, ekran „mózg”
  3. karta mózgu: dwa kupony; ChatGPT kodem urządzenia do ekranu z kodem (atrapa serwera OAuth: Playwright podstawia
     odpowiedzi tras Hermesa /api/providers/oauth/openai-codex/…; z --prawdziwy-chatgpt zapytanie idzie naprawdę do
     OpenAI, bez logowania i bez konta); klucz API z rozpoznaniem dostawcy (sk-or-, sk-ant-, sk-, nieznany) i klucz
     odrzucony (atrapa trasy /app/klucz: 422 klucz_odrzucony z komunikatem pod polem)
  4. mózg z atrapy modelu (scripts/atrapa_modelu.py; profil jarvo: provider custom przez `hermes config set`) →
     „Mam mózg. Zaczynam pierwszą sesję.” → wątek „Pierwsza sesja” z wpisem systemowym i odpowiedzią Jarva, a tura
     w dzienniku atrapy pod /p/jarvo/
  5. zrzuty: jasny i ciemny, 1440 i 390 px: pierwsze spotkanie, ekran startu i wątek „Pierwsza sesja”
     (poznanie-<motyw>-<szerokość>.jpg, start-…, sesja-…), z punktów 2–4 poznanie-witaj, poznanie-zdanie,
     mozg-karta, mozg-chatgpt, mozg-klucz i pierwsza-sesja (ciemny, 1440 px)
  6. pliki bez logowania (W10, W11, W13): odpowiedź atrapy z liniami „Plik:” (SVG, PDF, HTML z inbox/jarvo-e2e-natywnie);
     miniatura SVG jako data: (nie /file i nie blob:), „Odpal” i „Otwórz w nowej karcie” na serwerze podglądu
     127.0.0.1, PDF w ramce z linku podglądu, „Pokaż w folderze” w menu wtedy, gdy host je ma (--folder: klik,
     czyli prawdziwe okno Eksploratora, Findera albo menedżera plików)
  7. (--restart-panelu) restart panelu przez nadzorcę: nowy token sesji, otwarta karta dostaje 401 i sama przeładowuje
     się raz (bez strony logowania), potem działa dalej
Sprzątanie także po błędzie i Ctrl+C: USER.md, config.yaml profilu jarvo, state/pierwsza-sesja.json i nawyki.db
wracają do stanu sprzed testu, wątki testu i pliki z inbox znikają, atrapa kończy pracę (--zostaw: stan zostaje do
obejrzenia). Kod 0 = wszystkie punkty przeszły; raport JSON na stdout i w <wyniki>/raport.json (bez tokenu i kodu).
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from jarvo import hermes, sciezki, srodowisko  # noqa: E402

GLOS_CICHO = json.dumps({"glos": "meski", "tempo": "normalnie", "cisza": True})
STRUMIEN = re.compile(r"/api/plugins/jarvo-hq/strumien\?")
TOKEN = re.compile(r'window\.__HERMES_SESSION_TOKEN__="([^"]+)"')
OSOBA = {"imie": "Ola", "firma": "Piekarnia Złoty Kłos", "zajecie": "chleb na zakwasie",
         "linki": "zlotyklos.pl @zloty.klos", "strona": "zlotyklos.pl"}
# odpowiedź atrapy na prośbę „[Pierwsza sesja]” (aplikacja.PIERWSZA_PROSBA): treść do zrzutów zamiast echa prośby
ODPOWIEDZ = ("Cześć, Ola! Mam już Twój profil, więc zaczynamy pierwszą sesję.\n\n"
             "Zlecam trzy karty naraz:\n\n"
             "1. **Web**: szybki audyt strony zlotyklos.pl (szybkość, telefon, SEO).\n"
             "2. **Sherlock**: 3 piekarnie, które konkurują z Tobą w okolicy.\n"
             "3. **Łowca**: 10 firm z okolicy, które mogą kupować pieczywo (kawiarnie, hotele, sklepy).\n\n"
             "Gdy wyniki wrócą, podsumuję **3 najważniejsze ruchy na ten tydzień**.")
# atrapa serwera OAuth (trasy Hermesa kodu urządzenia ChatGPT, hermes_cli/web_routers/oauth.py w f97608f)
KOD_ATRAPY = "JRVO-TEST"
OAUTH_START = {"session_id": "atrapa-e2e", "flow": "device_code", "user_code": KOD_ATRAPY,
               "verification_url": "https://auth.openai.com/codex/device", "poll_interval": 5, "expires_in": 900}
KLUCZE = (("sk-ant-api03-" + "a" * 40, "Anthropic"), ("sk-or-v1-" + "b" * 40, "OpenRouter"),
          ("sk-proj-" + "c" * 40, "OpenAI"))


class Niepowodzenie(Exception):
    pass


def musi(warunek, opis: str) -> None:
    if not warunek:
        raise Niepowodzenie(opis)


def _argumenty(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--wyniki", required=True, help="katalog zrzutów, raportu i dziennika atrapy (CI: artefakty)")
    ap.add_argument("--korzen", help="korzeń instalacji (jak JARVO_ROOT)")
    ap.add_argument("--przegladarka", help="plik Chromium/Chrome (domyślnie CHROME_PATH instalacji)")
    ap.add_argument("--kanal", choices=("chrome", "msedge"), help="przeglądarka z systemu, gdy nie ma innej")
    ap.add_argument("--atrapa-port", type=int, default=0, help="port atrapy modelu (0 = wolny od systemu)")
    ap.add_argument("--prawdziwy-chatgpt", action="store_true",
                    help="start logowania ChatGPT naprawdę u OpenAI (tylko do ekranu z kodem, bez konta)")
    ap.add_argument("--zostaw", action="store_true", help="bez sprzątania (stan po teście do obejrzenia)")
    ap.add_argument("--folder", action="store_true",
                    help="punkt 6 klika też „Pokaż w folderze” (otwiera prawdziwe okno menedżera plików)")
    ap.add_argument("--restart-panelu", action="store_true",
                    help="punkt 7: restart panelu przez nadzorcę i samodzielne przeładowanie karty (nowy token)")
    ap.add_argument("--punkty", default="", help="np. 1,5: tylko te punkty (zrzuty 5 potrzebują wątku z punktu 4)")
    return ap.parse_args(argv)


# ----------------------------------------------------------------------------------------------- instalacja

def uklad(a) -> sciezki.Uklad:
    env = dict(os.environ)
    if a.korzen:
        env["JARVO_ROOT"] = a.korzen
    return sciezki.uklad(env)


def port_panelu(u: sciezki.Uklad) -> int:
    tekst = os.environ.get("JARVO_PANEL_PORT") or srodowisko.wczytaj_json(u.stan / "ustawienia.json").get(
        "JARVO_PANEL_PORT") or "9119"
    return int(str(tekst).strip())


def przegladarka_instalacji(u: sciezki.Uklad) -> str | None:
    """CHROME_PATH z `<stan>/narzedzia.json` (chrome-headless-shell z manifestu, env narzędzia)."""
    for wpis in srodowisko.narzedzia(u).values():
        sciezka = ((wpis or {}).get("env") or {}).get("CHROME_PATH") if isinstance(wpis, dict) else None
        if sciezka and Path(sciezka).is_file():
            return sciezka
    return None


def zadanie(base: str, token: str, metoda: str, sciezka: str, cialo=None, czas: float = 20) -> tuple[int, object]:
    """Trasa wtyczki z tokenem sesji (bez logowania) i nagłówkiem panelu (ochrona zapisu)."""
    dane = None if cialo is None else json.dumps(cialo).encode("utf-8")
    req = urllib.request.Request(base + sciezka, data=dane, method=metoda, headers={
        "X-Hermes-Session-Token": token, "X-Jarvo-Request": "1", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=czas) as r:      # noqa: S310 (127.0.0.1)
            tresc = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        tresc, status = e.read(), e.code
    try:
        return status, json.loads(tresc or b"null")
    except ValueError:
        return status, tresc[:300].decode("utf-8", "replace")


def token_sesji(base: str) -> str:
    with urllib.request.urlopen(base + "/", timeout=20) as r:      # noqa: S310 (127.0.0.1)
        html = r.read().decode("utf-8", "replace")
    m = TOKEN.search(html)
    musi(m, "index.html bez tokenu sesji: panel nie działa w trybie bez logowania (127.0.0.1)")
    return m.group(1)


class Stan:
    """Pliki, które test zmienia: kopia przed testem i powrót po nim (USER.md, config.yaml profilu jarvo,
    state/pierwsza-sesja.json; nawyki.db przez API kopii SQLite, bo panel trzyma ją otwartą)."""

    def __init__(self, u: sciezki.Uklad, katalog: Path):
        jd = u.jarvo_dane
        self.pliki = {"user_md": jd / "knowledge" / "user" / "USER.md",
                      "config_jarvo": u.dane / "profiles" / "jarvo" / "config.yaml",
                      "pierwsza": jd / "state" / "pierwsza-sesja.json"}
        self.kopie = {k: (p.read_bytes() if p.is_file() else None) for k, p in self.pliki.items()}
        self.nawyki = jd / "state" / "nawyki.db"
        self.nawyki_kopia = katalog / "nawyki-przed-testem.db"
        self.nawyki_bylo = self.nawyki.is_file()
        if self.nawyki_bylo:
            with closing(sqlite3.connect(self.nawyki)) as z, closing(sqlite3.connect(self.nawyki_kopia)) as do:
                z.backup(do)

    def przywroc(self) -> list[str]:
        bledy = []
        for k, p in self.pliki.items():
            try:
                if self.kopie[k] is None:
                    p.unlink(missing_ok=True)
                else:
                    tmp = p.with_name(p.name + ".e2e.tmp")
                    tmp.write_bytes(self.kopie[k])
                    os.replace(tmp, p)
            except OSError as e:
                bledy.append(f"{k}: {e}")
        try:
            if self.nawyki_bylo and self.nawyki_kopia.is_file():
                with closing(sqlite3.connect(self.nawyki_kopia)) as z, closing(sqlite3.connect(self.nawyki, timeout=10)) as do:
                    z.backup(do)
                self.nawyki_kopia.unlink()
            elif not self.nawyki_bylo and self.nawyki.is_file():
                with closing(sqlite3.connect(self.nawyki, timeout=10)) as c:
                    for t in ("reakcje", "zakazy"):
                        try:
                            c.execute(f"DELETE FROM {t}")
                        except sqlite3.Error:
                            pass
                    c.commit()
        except (OSError, sqlite3.Error) as e:
            bledy.append(f"nawyki.db: {e}")
        return bledy


class Atrapa:
    """scripts/atrapa_modelu.py na 127.0.0.1 z dziennikiem i gotową odpowiedzią na prośbę „[Pierwsza sesja]”."""

    def __init__(self, port: int, katalog: Path):
        if not port:
            with closing(socket.socket()) as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
        self.port = port
        self.dziennik = katalog / "atrapa.jsonl"
        odp = katalog / "atrapa-odpowiedzi.json"
        odp.write_text(json.dumps({"[Pierwsza sesja]": ODPOWIEDZ}, ensure_ascii=False), encoding="utf-8")
        self.proc = subprocess.Popen(
            [sys.executable, "-I", "-X", "utf8", str(REPO / "scripts" / "atrapa_modelu.py"), "--port", str(port),
             "--dziennik", str(self.dziennik), "--odpowiedzi", str(odp)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
        for _ in range(100):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=1):   # noqa: S310
                    return
            except OSError:
                time.sleep(0.1)
        self.stop()
        raise Niepowodzenie(f"atrapa modelu nie wstała na porcie {port}")

    def adres(self, profil: str) -> str:
        return f"http://127.0.0.1:{self.port}/p/{profil}/v1"

    def sciezki(self) -> list[str]:
        try:
            linie = self.dziennik.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for linia in linie:
            try:
                out.append(json.loads(linia).get("_sciezka") or "")
            except ValueError:
                pass
        return out

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait(timeout=10)


def mozg_z_atrapy(u: sciezki.Uklad, atrapa: Atrapa) -> None:
    """Profil jarvo na atrapie: `hermes -p jarvo config set` (to samo CLI, którym instalator ustawia profile)."""
    checkout = Path(srodowisko.biezace(u).get("hermes") or "")
    musi(srodowisko.hermes_python(checkout).is_file(), f"brak Pythona Hermesa w {checkout}")
    env = srodowisko.srodowisko(u)
    for klucz, wartosc in (("model.provider", "custom"), ("model.base_url", atrapa.adres("jarvo")),
                           ("model.default", "atrapa")):
        r = subprocess.run(hermes.argv_hermesa(checkout, "-p", "jarvo", "config", "set", klucz, wartosc), env=env,
                           cwd=str(u.dane), capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
        musi(r.returncode == 0, f"hermes -p jarvo config set {klucz}: kod {r.returncode} {r.stderr[-300:]}")


# ----------------------------------------------------------------------------------------------- przeglądarka

def _env_przegladarki_testu() -> dict | None:
    """Linux: przeglądarka TESTU (nie Jarva) z katalogami XDG w katalogu tymczasowym, usuwanym na końcu. Chromium
    zakłada w XDG cache fontconfig, bazę NSS i raporty awarii: bez tego migawka po odinstalowaniu (CI natywnie)
    widziałaby ślady narzędzia testowego jako ślady Jarva. Tylko proces przeglądarki: reszta testu (jarvo, Hermes)
    widzi prawdziwe XDG, więc korzeń i układ katalogów instalacji się nie zmieniają."""
    if not sys.platform.startswith("linux"):
        return None
    tmp = tempfile.mkdtemp(prefix="jarvo-e2e-chromium-")
    atexit.register(shutil.rmtree, tmp, True)
    return {**os.environ, "XDG_CONFIG_HOME": os.path.join(tmp, "config"), "XDG_CACHE_HOME": os.path.join(tmp, "cache"),
            "XDG_DATA_HOME": os.path.join(tmp, "data")}


def przegladarka(p, a, u):
    """Chromium do testu: --przegladarka, CHROME_PATH instalacji, Chromium Playwrighta, Chrome albo Edge systemu."""
    plik = a.przegladarka or os.environ.get("JARVO_E2E_PRZEGLADARKA") or przegladarka_instalacji(u)
    env = _env_przegladarki_testu()
    if plik:
        return p.chromium.launch(executable_path=plik, headless=True, env=env), plik
    if not a.kanal:
        try:
            return p.chromium.launch(headless=True, env=env), "chromium Playwrighta"
        except Exception:                      # noqa: BLE001 - brak pobranej przeglądarki Playwrighta
            pass
    for kanal in [a.kanal] if a.kanal else ["chrome", "msedge"]:
        try:
            return p.chromium.launch(channel=kanal, headless=True, env=env), f"kanał {kanal}"
        except Exception:                      # noqa: BLE001
            continue
    raise Niepowodzenie("nie ma przeglądarki: podaj --przegladarka albo zainstaluj Chrome")


def kontekst(browser, szer: int, wys: int, schemat: str, stan=None):
    c = browser.new_context(viewport={"width": szer, "height": wys}, locale="pl-PL", color_scheme=schemat,
                            storage_state=stan)
    # lektor wyciszony (bez speechSynthesis w tle); okna OpenAI z karty ChatGPT nie wychodzą do sieci
    c.add_init_script(f"try {{ localStorage.setItem('jarvo.glos.v1', {json.dumps(GLOS_CICHO)}); }} catch (_) {{}}")
    c.route("https://auth.openai.com/**", lambda r: r.fulfill(status=200, content_type="text/html",
                                                              body="<p>atrapa strony OpenAI</p>"))
    return c


def zrzut(strona, katalog: Path, nazwa: str) -> str:
    plik = katalog / f"{nazwa}.jpg"
    strona.screenshot(path=str(plik), type="jpeg", quality=85)
    return plik.name


# ----------------------------------------------------------------------------------------------- punkty

def punkt_wejscie(ctx, strona, base: str, sledz: dict) -> dict:
    strona.goto(base + "/")
    strona.wait_for_selector("[data-jarvo-korzen]", timeout=30000)
    stan = strona.evaluate("""() => ({sciezka: location.pathname, tytul: document.title,
        auth: window.__HERMES_AUTH_REQUIRED__, token: !!window.__HERMES_SESSION_TOKEN__,
        app: document.documentElement.hasAttribute('data-jarvo-app')})""")
    musi(stan["sciezka"] == "/jarvo", f"„/” nie prowadzi na /jarvo: {stan['sciezka']}")
    musi(stan["tytul"] == "Jarvo" and stan["auth"] is False and stan["token"] and stan["app"], f"wejście: {stan}")
    for _ in range(80):                              # strumień: lider otwiera go zaraz po starcie aplikacji
        if any(s["status"] == 200 for s in sledz["strumien"]):
            break
        strona.wait_for_timeout(250)
    musi(sledz["strumien"], "aplikacja nie otworzyła strumienia")
    musi(all(s["token"] for s in sledz["strumien"]), "strumień bez nagłówka X-Hermes-Session-Token (EventSource?)")
    musi(any(s["status"] == 200 for s in sledz["strumien"]), f"strumień bez odpowiedzi 200: {sledz['strumien']}")
    musi(not any("/login" in u for u in sledz["adresy"]), f"przejście na logowanie: {sledz['adresy']}")
    # klasyczny panel: Jarvo w menu, „Restart gatewaya” jest, przycisku aktualizacji Hermesa nie ma (H16)
    strona.goto(base + "/sessions")
    strona.wait_for_selector("#app-sidebar", timeout=30000)
    strona.wait_for_timeout(1500)
    menu = strona.inner_text("#app-sidebar")
    jarvo = strona.locator('#app-sidebar a[href="/jarvo"]').count()
    musi(jarvo >= 1, "w menu klasycznego panelu nie ma zakładki Jarvo")
    musi(re.search(r"Restart gateway", menu, re.I), "w menu nie ma „Restart gatewaya” (sekcja System)")
    musi(not re.search(r"Aktualizuj Hermesa|Update Hermes", menu), "w menu jest „Aktualizuj Hermesa” (H16)")
    return {**stan, "strumien": len(sledz["strumien"]), "menu_jarvo": jarvo, "bez_aktualizacji_hermesa": True}


def punkt_poznanie(strona, base: str, token: str, stan: Stan, wyniki: Path, zrzuty: list) -> dict:
    przed = (stan.kopie["user_md"] or b"").decode("utf-8", "replace")
    musi(not re.search(r"Imię / jak się zwracać:[ \t]*[^\s<]", przed),
         "USER.md ma już imię: test pierwszego spotkania potrzebuje świeżej instalacji")
    stan.pliki["pierwsza"].unlink(missing_ok=True)       # wraca przy sprzątaniu, jeśli był
    # gotowość modelu panel trzyma 30 s, a po nich podaje raz starą wartość i liczy nową w tle (aplikacja.Gotowosc):
    # pytamy, aż przyjdzie świeża, zanim strona ją pobierze (po poprzednim przebiegu testu bywa jeszcze „podłączony”)
    polaczony = True
    for _ in range(25):
        status, d = zadanie(base, token, "GET", "/api/plugins/jarvo-hq/app")
        polaczony = status == 200 and bool((((d or {}).get("gotowosc") or {}).get("model") or {}).get("polaczony"))
        if not polaczony:
            break
        time.sleep(2)
    musi(not polaczony, "profil jarvo ma już podłączony model: pierwsze spotkanie zaczęłoby prawdziwą pierwszą sesję "
                        "(test potrzebuje świeżej instalacji bez mózgu)")
    strona.goto(base + "/jarvo#/")
    strona.wait_for_selector('.j-poz[data-krok="witaj"]', timeout=30000)
    strona.wait_for_timeout(600)
    zrzuty.append(zrzut(strona, wyniki, "poznanie-witaj"))
    strona.click('.j-poz button[type="submit"]')
    strona.wait_for_selector('.j-poz[data-krok="imie"]', timeout=10000)
    strona.fill(".j-poz-pole input", OSOBA["imie"])
    strona.click('.j-poz button[type="submit"]')
    strona.wait_for_selector('.j-poz[data-krok="firma"]', timeout=10000)
    strona.locator(".j-poz-pole input").nth(0).fill(OSOBA["firma"])
    strona.locator(".j-poz-pole input").nth(1).fill(OSOBA["zajecie"])
    strona.click('.j-poz button[type="submit"]')
    strona.wait_for_selector('.j-poz[data-krok="linki"]', timeout=10000)
    strona.fill(".j-poz-pole textarea", OSOBA["linki"])
    strona.wait_for_selector(".j-poz-znacznik", timeout=10000)
    strona.click('.j-poz button[type="submit"]')
    strona.wait_for_selector('.j-poz[data-krok="cele"]', timeout=10000)
    strona.click(".j-poz-cel >> nth=0")
    strona.wait_for_timeout(400)
    zrzuty.append(zrzut(strona, wyniki, "poznanie-zdanie"))
    strona.click('.j-poz button[type="submit"]')
    strona.wait_for_selector('.j-poz[data-krok="mozg"]', timeout=15000)
    plik = stan.pliki["user_md"].read_text(encoding="utf-8")
    brak = [x for x in (f"Imię / jak się zwracać: {OSOBA['imie']}", f"Czym się zajmuję: {OSOBA['zajecie']}",
                        f"{OSOBA['firma']} → {OSOBA['strona']}", "Instagram: @zloty.klos") if x not in plik]
    musi(not brak, f"USER.md po pierwszym spotkaniu bez: {brak}")
    musi(re.search(r"\n## Cele[^\n]*\n- \S", plik), "USER.md bez celu z listy")
    zdanie = strona.inner_text(".j-poz-zd")
    musi(OSOBA["firma"] in zdanie, f"zdanie pierwszego spotkania: {zdanie[:200]}")
    return {"user_md": "imię, firma, zajęcie, strona, Instagram, cel", "zdanie": zdanie[:160]}


def punkt_mozg(ctx, strona, wyniki: Path, zrzuty: list, prawdziwy: bool) -> dict:
    musi(strona.locator(".j-poz-kupon").count() == 2, "karta mózgu bez dwóch kuponów (ChatGPT, klucz API)")
    zrzuty.append(zrzut(strona, wyniki, "mozg-karta"))
    out = {}
    # ChatGPT kodem urządzenia: do ekranu z kodem; atrapa tras Hermesa albo (--prawdziwy-chatgpt) prawdziwe OpenAI
    if not prawdziwy:
        ctx.route("**/api/providers/oauth/openai-codex/start", lambda r: r.fulfill(
            status=200, content_type="application/json", body=json.dumps(OAUTH_START)))
        ctx.route("**/api/providers/oauth/openai-codex/poll/**", lambda r: r.fulfill(
            status=200, content_type="application/json", body=json.dumps({"status": "pending"})))
        ctx.route("**/api/providers/oauth/sessions/**", lambda r: r.fulfill(
            status=200, content_type="application/json", body=json.dumps({"ok": True})))
    strona.locator(".j-poz-kupon").nth(0).click()
    strona.click(".j-mozg-tresc .j-btn-glowny")
    strona.wait_for_selector(".j-mozg-kod", timeout=30000)
    kod = strona.inner_text(".j-mozg-kod").strip()
    musi(len(kod) >= 4, "karta ChatGPT bez kodu urządzenia")
    musi(strona.locator(".j-mozg-czeka").count() == 1, "karta ChatGPT nie czeka na zalogowanie")
    for s in ctx.pages:                           # okno strony OpenAI otwarte przez kartę (blokada okien w teście)
        if s is not strona:
            s.close()
    zrzuty.append(zrzut(strona, wyniki, "mozg-chatgpt"))
    out["chatgpt"] = "kod urządzenia na ekranie" + (" (prawdziwe OpenAI)" if prawdziwy else " (atrapa OAuth)")
    # klucz API: dostawca po przedrostku od razu pod polem, nieznany kształt, odrzucony klucz z komunikatem
    strona.locator(".j-poz-kupon").nth(1).click()
    pole = strona.locator("[data-klucz]")
    pole.wait_for(timeout=10000)
    rozpoznane = {}
    for klucz, nazwa in KLUCZE:
        pole.fill(klucz)
        rozpoznane[nazwa] = strona.inner_text(".j-mozg-o").strip()
        musi(nazwa in rozpoznane[nazwa], f"klucz {klucz[:7]}…: pod polem „{rozpoznane[nazwa]}”, oczekiwane {nazwa}")
    pole.fill("abc-" + "d" * 30)
    musi(strona.locator(".j-mozg-o .j-poz-znacznik").count() == 0, "nieznany klucz rozpoznany jako dostawca")
    musi(strona.locator(".j-poz-akcje .j-btn-glowny").is_disabled(), "„Podłącz” aktywne przy nieznanym kluczu")
    ctx.route("**/api/plugins/jarvo-hq/app/klucz", lambda r: r.fulfill(
        status=422, content_type="application/json", body=json.dumps({"blad": {
            "kod": "klucz_odrzucony", "komunikat": "OpenRouter nie przyjął tego klucza. Sprawdź, czy wkleiłeś go "
            "w całości i czy jest aktywny.", "komunikat_en": "OpenRouter did not accept this key."}})))
    pole.fill(KLUCZE[1][0])
    strona.click(".j-poz-akcje .j-btn-glowny")
    strona.wait_for_selector(".j-mozg .j-poz-blad", timeout=15000)
    blad = strona.inner_text(".j-mozg .j-poz-blad")
    musi("nie przyjął" in blad, f"odrzucony klucz: {blad}")
    musi(pole.input_value() == KLUCZE[1][0], "pole klucza wyczyszczone po odrzuceniu (ma zostać do poprawy)")
    zrzuty.append(zrzut(strona, wyniki, "mozg-klucz"))
    ctx.unroute("**/api/plugins/jarvo-hq/app/klucz")
    pole.fill("")
    out["klucz"] = {"rozpoznane": sorted(rozpoznane), "odrzucony": blad[:80]}
    return out


def punkt_pierwsza_sesja(strona, u, atrapa: Atrapa, wyniki: Path, zrzuty: list) -> dict:
    mozg_z_atrapy(u, atrapa)
    # aplikacja odpytuje gotowość co 5 s; model liczy serwer najwyżej co 30 s (aplikacja.Gotowosc)
    strona.wait_for_function("() => /^#\\/r\\/w_[0-9a-f]{21}/.test(location.hash)", timeout=120000)
    watek = re.search(r"w_[0-9a-f]{21}", strona.evaluate("() => location.hash")).group(0)
    strona.wait_for_selector(".j-msg-sys", timeout=30000)
    systemowy = strona.inner_text(".j-msg-sys")
    musi("Mózg podłączony" in systemowy or "Brain connected" in systemowy, f"wpis systemowy: {systemowy}")
    strona.wait_for_selector("article.j-msg-ag[data-pozycja]", timeout=180000)
    odp = strona.inner_text("article.j-msg-ag[data-pozycja]")
    musi("pierwszą sesję" in odp and "Łowca" in odp, f"odpowiedź Jarva: {odp[:200]}")
    tytul = strona.evaluate("() => (document.querySelector('[data-jarvo-korzen] h1, [data-jarvo-korzen] header') || {}).innerText || ''")
    sciezki_atrapy = atrapa.sciezki()
    musi(any("/p/jarvo/" in s for s in sciezki_atrapy), f"tura Jarva nie poszła do atrapy: {sciezki_atrapy[-3:]}")
    strona.wait_for_timeout(800)
    zrzuty.append(zrzut(strona, wyniki, "pierwsza-sesja"))
    return {"watek": watek, "tytul": tytul[:60], "wpis_systemowy": systemowy[:80], "tury_atrapy": len(sciezki_atrapy)}


SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80" viewBox="0 0 120 80">'
       '<rect width="120" height="80" rx="10" fill="#D4213D"/><text x="60" y="50" font-size="26" fill="#fff" '
       'text-anchor="middle" font-family="sans-serif">Jarvo</text></svg>')
HTML = "<!doctype html><meta charset=utf-8><title>Strona testowa</title><h1>Strona testowa Jarva</h1>"


def _pdf() -> bytes:
    """Najmniejszy poprawny PDF z jedną stroną i tabelą xref (offsety liczone)."""
    obiekty = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 100] >>"]
    out, offsety = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(obiekty, 1):
        offsety.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(obiekty) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{x:010d} 00000 n \n".encode() for x in offsety)
    out += f"trailer\n<< /Size {len(obiekty) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def punkt_pliki(ctx, strona, base: str, u, wyniki: Path, zrzuty: list, sprzatanie: list, folder: bool) -> dict:
    """Pliki bez logowania (W11): karta SVG z obrazem data: (nie /file, które dostałoby 401), PDF w ramce z linku
    podglądu :9120, „Odpal” HTML i „Otwórz w nowej karcie” na :9120 (127.0.0.1), „Pokaż w folderze” w menu, gdy
    host je ma (W13). Pliki w inbox/jarvo-e2e-natywnie, wątek z wiadomością do atrapy, która odpisuje liniami Plik:."""
    katalog = u.jarvo_dane / "inbox" / "jarvo-e2e-natywnie"
    katalog.mkdir(parents=True, exist_ok=True)
    sprzatanie.append(lambda: shutil.rmtree(katalog, ignore_errors=True))
    pliki = {"svg": katalog / "logo.svg", "pdf": katalog / "raport.pdf", "html": katalog / "strona.html"}
    pliki["svg"].write_text(SVG, encoding="utf-8")
    pliki["pdf"].write_bytes(_pdf())
    pliki["html"].write_text(HTML, encoding="utf-8")
    tekst = "Pliki do testu " + " ".join(f"[plik:{p.as_posix()}]" for p in pliki.values())
    r = strona.evaluate("""async (tekst) => { const r = await fetch('/api/plugins/jarvo-hq/rozmowy', {method: 'POST',
        headers: {'X-Hermes-Session-Token': window.__HERMES_SESSION_TOKEN__, 'X-Jarvo-Request': '1',
        'Content-Type': 'application/json'}, body: JSON.stringify({tytul: '[E2E] pliki', koordynator: 'jarvo',
        wiadomosc: {tekst, klucz: 'e2e-pliki-' + Date.now()}})}); return {s: r.status, d: await r.json()}; }""", tekst)
    musi(r["s"] == 201, f"POST /rozmowy: {r['s']} {str(r['d'])[:200]}")
    watek = r["d"]["watek"]["id"]
    sprzatanie.append(lambda: strona.evaluate("""async (w) => fetch(`/api/plugins/jarvo-hq/rozmowy/${w}?trwale=1`, {
        method: 'DELETE', headers: {'X-Hermes-Session-Token': window.__HERMES_SESSION_TOKEN__,
        'X-Jarvo-Request': '1'}})""", watek))
    strona.evaluate("(w) => { location.hash = `#/r/${w}`; }", watek)
    strona.wait_for_selector('.j-msg-ag .j-plik[data-plik$="strona.html"]', timeout=120000)
    out = {}
    host = strona.evaluate("""async () => (await fetch('/api/plugins/jarvo-hq/host', {headers: {
        'X-Hermes-Session-Token': window.__HERMES_SESSION_TOKEN__, 'X-Jarvo-Request': '1'}})).json()""")
    podglad = f"http://127.0.0.1:{host.get('preview_port')}/"
    # SVG: miniatura z data:, nigdy /file (bez tokenu 401) ani blob: (pochodzenie panelu)
    karta_svg = strona.locator('.j-msg-ag .j-plik[data-plik$="logo.svg"]')
    karta_svg.locator("img").wait_for(timeout=15000)
    src = karta_svg.locator("img").get_attribute("src") or ""
    musi(src.startswith("data:image/svg+xml"), f"miniatura SVG: {src[:60]}")
    out["svg"] = "data:image/svg+xml"
    # „Odpal” HTML: nowa karta z serwera podglądu na 127.0.0.1
    with ctx.expect_page(timeout=15000) as nowa:
        strona.locator('.j-msg-ag .j-plik[data-plik$="strona.html"] .j-plik-akcje button').first.click()
    s = nowa.value                              # karta otwiera się pusta (blokada okien), adres dostaje po POST /site
    s.wait_for_url(re.compile(r"^http://127\.0\.0\.1:\d+/"), timeout=15000)
    s.wait_for_load_state()
    musi(s.url.startswith(podglad), f"„Odpal” poza podglądem 127.0.0.1: {s.url[:80]}")
    musi("Strona testowa Jarva" in s.content(), "„Odpal”: strona bez treści")
    s.close()
    out["odpal"] = "127.0.0.1:" + str(host.get("preview_port"))
    # „Otwórz w nowej karcie” (SVG): też przez :9120, bo /file w nowej karcie nie dostanie tokenu
    karta_svg.locator(".j-plik-akcje button").nth(1).click()
    strona.wait_for_selector('.j-menu [role="menuitem"]', timeout=10000)
    pozycje = strona.locator('.j-menu [role="menuitem"]').all_inner_texts()
    musi(any("folderze" in p for p in pozycje) == bool(host.get("explorer")),
         f"„Pokaż w folderze” w menu: {pozycje}, host.explorer={host.get('explorer')}")
    with ctx.expect_page(timeout=15000) as nowa:
        strona.locator('.j-menu [role="menuitem"]', has_text="nowej karcie").click()
    s = nowa.value
    s.wait_for_url(re.compile(r"^http://127\.0\.0\.1:\d+/"), timeout=15000)
    s.wait_for_load_state()
    musi(s.url.startswith(podglad) and s.url.endswith("logo.svg"), f"nowa karta SVG: {s.url[:80]}")
    s.close()
    out["nowa_karta"] = "link podglądu :9120"
    # PDF w oknie podglądu: ramka i link zapasowy z serwera podglądu
    strona.locator('.j-msg-ag .j-plik[data-plik$="raport.pdf"] .j-plik-otworz').click()
    strona.wait_for_selector(".j-podglad iframe.j-podglad-pdf", timeout=15000)
    ramka = strona.locator(".j-podglad iframe.j-podglad-pdf").get_attribute("src") or ""
    musi(ramka.startswith(podglad) and ramka.endswith("raport.pdf"), f"PDF w ramce: {ramka[:80]}")
    # inne pochodzenie z CSP sandbox z serwera: ramka bez atrybutu sandbox (z nim Chrome blokuje przeglądarkę PDF)
    musi(strona.locator(".j-podglad iframe.j-podglad-pdf").get_attribute("sandbox") is None,
         "ramka PDF z :9120 ma atrybut sandbox (Chrome nie pokaże w niej PDF)")
    strona.wait_for_timeout(800)
    zrzuty.append(zrzut(strona, wyniki, "pliki-pdf"))
    strona.keyboard.press("Escape")
    out["pdf"] = "ramka z linku podglądu"
    if folder and host.get("explorer"):          # otwiera prawdziwe okno menedżera plików na pulpicie
        karta_svg.locator(".j-plik-akcje button").nth(1).click()
        strona.locator('.j-menu [role="menuitem"]', has_text="folderze").click()
        strona.wait_for_selector(".j-plik-uwaga", timeout=10000)
        out["folder"] = strona.inner_text(".j-plik-uwaga")
    out["folder_w_menu"] = bool(host.get("explorer"))
    return out


def punkt_restart(strona, base: str, u) -> dict:
    """Restart panelu (nowy token sesji): otwarta karta dostaje 401, przeładowuje się sama raz i działa dalej (W11)."""
    from jarvo import nadzorca
    przed = strona.evaluate("() => window.__HERMES_SESSION_TOKEN__")
    strona.goto(base + "/jarvo#/")
    strona.wait_for_selector("[data-jarvo-korzen]", timeout=30000)
    nadzorca.polacz(u).restart("panel")
    koniec, nowy = time.monotonic() + 180, None
    while time.monotonic() < koniec:             # przeładowanie niszczy kontekst strony: pytamy w pętli
        try:
            nowy = strona.evaluate("() => window.__HERMES_SESSION_TOKEN__ || null")
        except Exception:                          # noqa: BLE001 - strona właśnie się przeładowuje
            nowy = None
        if nowy and nowy != przed:
            break
        time.sleep(1)
    musi(nowy and nowy != przed, "po restarcie panelu karta nie przeładowała się sama z nowym tokenem")
    strona.wait_for_selector("[data-jarvo-korzen]", timeout=60000)
    strona.wait_for_timeout(3000)
    po = strona.evaluate("() => ({hash: location.hash, sciezka: location.pathname})")
    musi(po["sciezka"] == "/jarvo", f"po restarcie panelu: {po}")
    return {"nowy_token": True, **po}


def punkt_zrzuty(browser, ctx, base: str, watek: str | None, wyniki: Path, zrzuty: list,
                 stan_plikow: Stan | None = None) -> dict:
    stan = ctx.storage_state()
    for o in stan.get("origins") or []:            # motyw aplikacji „Jak w systemie” (rozstrzyga color_scheme)
        o["localStorage"] = [x for x in o.get("localStorage") or [] if x.get("name") != "jarvo.ustawienia.v1"]
    # pierwsze spotkanie w każdym motywie i szerokości: na chwilę USER.md sprzed testu (bez imienia), potem z powrotem
    user_md = stan_plikow.pliki["user_md"] if stan_plikow else None
    pusty = stan_plikow.kopie["user_md"] if stan_plikow else None
    po_tescie = user_md.read_bytes() if user_md is not None and user_md.is_file() else None
    for motyw, schemat in (("jasny", "light"), ("ciemny", "dark")):
        for szer, wys in ((1440, 900), (390, 844)):
            c = kontekst(browser, szer, wys, schemat, stan)
            try:
                s = c.new_page()
                if pusty is not None and po_tescie is not None:
                    user_md.write_bytes(pusty)
                    try:
                        s.goto(base + "/jarvo#/")
                        s.wait_for_selector('.j-poz[data-krok="witaj"]', timeout=30000)
                        s.wait_for_timeout(800)
                        zrzuty.append(zrzut(s, wyniki, f"poznanie-{motyw}-{szer}"))
                    finally:
                        user_md.write_bytes(po_tescie)
                s.goto(base + "/jarvo#/")
                s.wait_for_selector("[data-jarvo-korzen] .j-witaj", timeout=30000)
                s.wait_for_timeout(1200)
                zrzuty.append(zrzut(s, wyniki, f"start-{motyw}-{szer}"))
                if watek:
                    s.evaluate("(w) => { location.hash = `#/r/${w}`; }", watek)
                    s.wait_for_selector("article.j-msg-ag[data-pozycja]", timeout=30000)
                    s.wait_for_timeout(1000)
                    zrzuty.append(zrzut(s, wyniki, f"sesja-{motyw}-{szer}"))
            finally:
                c.close()
    return {"zestaw": "jasny i ciemny, 1440 i 390 px"}


# ----------------------------------------------------------------------------------------------- całość

def main(argv=None) -> int:
    a = _argumenty(argv)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(json.dumps({"ok": False, "blad": "brak paczki playwright w tym Pythonie (venv narzędzi instalacji)"},
                         ensure_ascii=False))
        return 2
    u = uklad(a)
    base = f"http://127.0.0.1:{port_panelu(u)}"
    wyniki = Path(a.wyniki).resolve()
    wyniki.mkdir(parents=True, exist_ok=True)
    wybrane = {p.strip() for p in a.punkty.split(",") if p.strip()}
    raport: dict = {"panel": base, "korzen": str(u.root), "punkty": [], "zrzuty": []}
    stan = atrapa = None
    watek = None
    token = ""

    def krok(nr: str, opis: str, f):
        if wybrane and nr not in wybrane:
            return None
        start = time.monotonic()
        try:
            wynik = f()
            raport["punkty"].append({"punkt": nr, "opis": opis, "ok": True, "s": round(time.monotonic() - start, 1),
                                     "wynik": wynik})
            return wynik
        except Exception as e:                    # noqa: BLE001 - każdy punkt w raporcie, test idzie dalej
            raport["punkty"].append({"punkt": nr, "opis": opis, "ok": False, "s": round(time.monotonic() - start, 1),
                                     "blad": f"{type(e).__name__}: {e}"[:600]})
            if not isinstance(e, Niepowodzenie):
                (wyniki / f"punkt-{nr}-slad.txt").write_text(traceback.format_exc(), encoding="utf-8")
            return None

    try:
        token = token_sesji(base)
        stan = Stan(u, wyniki)
        with sync_playwright() as p:
            browser, skad = przegladarka(p, a, u)
            raport["przegladarka"] = skad
            ctx = kontekst(browser, 1440, 900, "dark")
            sledz = {"strumien": [], "adresy": [], "401": [], "bledy": []}

            def zapytanie(r):
                if STRUMIEN.search(r.url):
                    sledz["strumien"].append({"token": bool(r.headers.get("x-hermes-session-token")), "status": None})
            ctx.on("request", zapytanie)

            def odpowiedz(r):
                if STRUMIEN.search(r.url):
                    for s in sledz["strumien"]:
                        if s["status"] is None:
                            s["status"] = r.status
                            break
                if r.status == 401:
                    sledz["401"].append(r.url.split("?")[0])
            ctx.on("response", odpowiedz)
            strona = ctx.new_page()
            strona.on("framenavigated", lambda f: f == strona.main_frame and sledz["adresy"].append(f.url))
            strona.on("pageerror", lambda e: sledz["bledy"].append(str(e)[:200]))

            krok("1", "wejście bez hasła, /jarvo, strumień z tokenem, bez „Aktualizuj Hermesa”",
                 lambda: punkt_wejscie(ctx, strona, base, sledz))
            krok("2", "pierwsze spotkanie → USER.md, ekran „mózg”",
                 lambda: punkt_poznanie(strona, base, token, stan, wyniki, raport["zrzuty"]))
            krok("3", "karta mózgu: ChatGPT kodem urządzenia, klucz API z rozpoznaniem dostawcy",
                 lambda: punkt_mozg(ctx, strona, wyniki, raport["zrzuty"], a.prawdziwy_chatgpt))
            if not wybrane or "4" in wybrane:
                atrapa = Atrapa(a.atrapa_port, wyniki)
            w = krok("4", "mózg z atrapy → „Pierwsza sesja” z odpowiedzią Jarva",
                     lambda: punkt_pierwsza_sesja(strona, u, atrapa, wyniki, raport["zrzuty"]))
            watek = (w or {}).get("watek")
            krok("5", "zrzuty: jasny i ciemny, 1440 i 390 px",
                 lambda: punkt_zrzuty(browser, ctx, base, watek, wyniki, raport["zrzuty"], stan))
            sprzatanie: list = []
            if atrapa is not None:
                krok("6", "pliki bez logowania: SVG jako data:, PDF i nowa karta przez :9120, „Odpal”, folder",
                     lambda: punkt_pliki(ctx, strona, base, u, wyniki, raport["zrzuty"], sprzatanie, a.folder))
            for f in reversed(sprzatanie):
                try:
                    f()
                except Exception:                  # noqa: BLE001 - sprzątanie nie przerywa raportu
                    pass
            raport["401"] = sorted(set(sledz["401"]))     # 401 z restartu panelu (punkt 7) są oczekiwane
            if a.restart_panelu:
                krok("7", "restart panelu: karta przeładowuje się sama z nowym tokenem",
                     lambda: punkt_restart(strona, base, u))
            raport["bledy_js"] = sledz["bledy"][:20]
            ctx.close()
            browser.close()
    except Exception as e:                        # noqa: BLE001 - raport zamiast śladu na ekranie
        raport["blad"] = f"{type(e).__name__}: {e}"[:600]
    finally:
        if atrapa is not None:
            atrapa.stop()
        if stan is not None and not a.zostaw:
            if watek:
                try:                              # token od nowa: po restarcie panelu (punkt 7) stary już nie działa
                    status, _d = zadanie(base, token_sesji(base), "DELETE",
                                         f"/api/plugins/jarvo-hq/rozmowy/{watek}?trwale=1")
                except (OSError, Niepowodzenie) as e:
                    status = f"{type(e).__name__}"
                raport["sprzatanie_watku"] = status
            raport["sprzatanie_bledy"] = stan.przywroc()
    if raport.get("401"):
        raport["punkty"].append({"punkt": "401", "ok": False, "blad": f"odpowiedzi 401: {raport['401'][:5]}"})
    raport["ok"] = bool(raport["punkty"]) and all(p["ok"] for p in raport["punkty"]) and "blad" not in raport
    tekst = json.dumps(raport, ensure_ascii=False, indent=1)
    (wyniki / "raport.json").write_text(tekst + "\n", encoding="utf-8")
    print(tekst)
    return 0 if raport["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
