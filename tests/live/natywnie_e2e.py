#!/usr/bin/env python3
"""Test instalacji natywnej na żywo: pełna macierz CI (.github/workflows/natywnie.yml) i próba ręczna na komputerze
z instalacją natywną (docs/NATYWNIE.md: T08, T14, T18, etapy E3, E4 i E13, (l) „Kiedy całość jest gotowa”).

Instalację robi workflow dokładnie poleceniem z README (bootstrap z commitu pod testem, JARVO_REF = SHA); ten
skrypt sprawdza ją z zewnątrz, tak jak właściciel: przez polecenie `jarvo`, panel w przeglądarce i API bramy.
Działa na samej bibliotece standardowej (dowolny Python 3.11+); układ katalogów i środowisko procesów Jarva bierze
z pakietu jarvo/ tego repo, YAML profili testowych pisze Pythonem Hermesa z instalacji.

Podpolecenia (każde dopisuje punkty do <artefakty>/raport.json; kod 1 = któryś punkt nie przeszedł):

  migawka --wyjscie PLIK   stan komputera poza katalogiem Jarva, tylko odczyt: nazwy plików i katalogów w katalogu
                           domowym i katalogach aplikacji (do ustalonej głębokości), treść plików startowych powłoki,
                           LaunchAgentów i jednostek systemd, odciski katalogów cache, których Jarvo nie może ruszać
                           (uv, npm, pip, Hugging Face, Playwright, ~/.hermes), Windows: zmienne użytkownika
                           (HKCU\\Environment; PATH wprost, reszta jako skrót, sekrety tylko „jest”), Run, RunOnce,
                           wpis w „Aplikacje”; zadania Harmonogramu, LaunchAgenty i jednostki systemd z „jarvo” albo
                           „hermes” w nazwie; korzeń Jarva
  roznica PRZED PO         różnica dwóch migawek; pusta poza wyjątkami (WYJATKI: szum systemu i runnera z powodem,
                           --wyjatek "WZÓR[=kiedy]|POWÓD"), inaczej kod 1; wynik w <artefakty>/roznica.json
  sprawdz                  po instalacji: `jarvo doctor --json` (zielony poza --dopusc), `jarvo status --json`
                           (serwis, który nie działa, to błąd; potem `jarvo up`, żeby sprawdzić resztę), panel (/,
                           /api/status z hermes_home = <dane>, /jarvo przy wtyczce HQ), flota z fleet.yaml;
                           bez --tylko-odczyt także: atrapa modelu (scripts/atrapa_modelu.py w wątku, port od
                           systemu), profile testowe, `jarvo chat -q` (odpowiedź), /v1/runs bramy (odpowiedź, prośba
                           o zgodę wtyczki jarvo-zgody, zgoda „raz”, odmowa) i karta kanbana dla specjalisty
                           (pracownik bramy na atrapie woła kanban_complete); na końcu profile testowe znikają
  drugi-przebieg LOG       log drugiego przebiegu polecenia instalacji: „Zmiany w tym przebiegu: brak.”, nic nie
                           pobrane ponownie, „Gotowe”
  prawdziwy-model          (opcjonalnie) jedna tura z prawdziwym modelem przez OpenRouter; klucz tylko
                           z JARVO_TEST_OPENROUTER_KEY, nigdy na ekranie ani w artefaktach; bez klucza: pominięte
  zbierz-logi              logi nadzorcy, usług, Hermesa i pracowników kanbana oraz pliki stanu do artefaktów (przed
                           odinstalowaniem); znane sekrety z plików .env zamaskowane (ich obecność to błąd), skróty
                           sekretów (sha256, nie wartości) obok katalogu artefaktów dla skanu
  odinstaluj               `jarvo uninstall --all --yes`; potem procesy Jarva, porty, korzeń i polecenie jarvo znikają
  skan KATALOG             sekrety w artefaktach przed wysyłką: wzorce kluczy i tokenów, skróty znanych sekretów,
                           wartości zmiennych z --z-otoczenia; plik z trafieniem znika (zostaje opis bez sekretu),
                           kod 1; `gotowe=tak` w $GITHUB_OUTPUT dopiero po przejrzeniu całego katalogu
  podsumowanie             tabela punktów, doctor, różnica migawek i skan w $GITHUB_STEP_SUMMARY (albo na ekranie)

Zasady: porty tylko na 127.0.0.1 (atrapa na porcie od systemu, brama i panel z instalacji); żadnych sekretów na
ekranie (każdy cytowany fragment wyjścia przechodzi przez `bez_sekretow`); profile testowe `test-e2e-*` tworzy
i usuwa sam test (bez aliasów w ~/.local/bin); polecenia Hermesa zawsze z `-p default` w środowisku Jarva.
Zrzuty panelu (obszar e6) kładzie się do <artefakty>/zrzuty: skan pomija pliki binarne, wysyłka bierze cały katalog.

    python -X utf8 -B tests/live/natywnie_e2e.py migawka --wyjscie przed.json
    python -X utf8 -B tests/live/natywnie_e2e.py sprawdz --dopusc "wolne miejsce=uwaga:mały dysk runnera"
    python -X utf8 -B tests/live/natywnie_e2e.py sprawdz --tylko-odczyt     # na działającej instalacji właściciela
"""
from __future__ import annotations

import argparse
import contextlib
import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from jarvo import hermes as jhermes  # noqa: E402  (pakiet jarvo: sama biblioteka standardowa)
from jarvo import instalator, sciezki, srodowisko  # noqa: E402
from jarvo.sciezki import Uklad  # noqa: E402

WINDOWS = os.name == "nt"
MACOS = sys.platform == "darwin"
LINUX = sys.platform.startswith("linux")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

PROFIL_CZAT = "test-e2e-czat"          # rozmowa i zgody (wtyczka jarvo-zgody, tryb „pytaj”)
PROFIL_SPEC = "test-e2e-spec"          # specjalista: pracownik kanbana na atrapie
PROFIL_OR = "test-e2e-or"              # prawdziwy model przez OpenRouter (opcjonalny krok)
WTYCZKA_ZGOD = "jarvo-zgody"
PORT_API = 8642                        # API bramy Hermesa (H05); inny: API_SERVER_PORT
STATUSY_KONCOWE = {"completed", "failed", "cancelled", "interrupted"}
ZMIANY_BRAK = "Zmiany w tym przebiegu: brak"
BEZ_CZLOWIEKA = re.compile(r"runs without a user present")
# prośba pracownika kanbana (hermes_cli/kanban_db_dispatch.py: `chat -q "work kanban task <id>"`); także w dłuższej
# wiadomości, gdyby Hermes coś do niej dopisał (prośba o tytuł z tym tekstem dostanie wywołanie narzędzia, które
# generator tytułów po prostu pominie)
PRACA_KANBAN = re.compile(r"\bwork kanban task ([A-Za-z0-9_.-]+)")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")
SEKRET_NAZWA = srodowisko.SEKRET       # TOKEN|KEY|SECRET|PASS|HASLO|KLUCZ|AUTH|COOKIE
ZMIENNE_SEKRETOW = ("JARVO_TEST_OPENROUTER_KEY", "GITHUB_TOKEN", "JARVO_TOKEN", "ACTIONS_RUNTIME_TOKEN",
                    "ACTIONS_ID_TOKEN_REQUEST_TOKEN")
MODEL_OPENROUTER = "anthropic/claude-haiku-4.5"     # gdy fleet.yaml nie poda zestawu openrouter (tier fast)
MAKS_LOGU = 5 * 2 ** 20                # z dłuższego logu do artefaktów idzie koniec

# Wzorce sekretów w artefaktach (tekst logów jest publiczny jak logi CI repo publicznego, T18). Grupa 1, jeśli jest,
# to sama wartość: musi mieć literę i cyfrę, żeby „max_tokens: 1234567890123456” nie był trafieniem.
WZORY_SEKRETOW: list[tuple[str, re.Pattern]] = [
    ("klucz OpenRouter", re.compile(r"sk-or-v1-[0-9a-f]{20,}")),
    ("klucz Anthropic", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("klucz OpenAI", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}")),
    ("token GitHub", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("token GitHub (fine-grained)", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}")),
    ("token Slack", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("klucz AWS", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("klucz Google", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("token bota Telegram", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")),
    ("klucz prywatny", re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----")),
    ("nagłówek Authorization", re.compile(r"(?i)\bBearer\s+([A-Za-z0-9_\-.=+/]{20,})")),
    # wiersz z pliku .env albo `export` (np. API_SERVER_KEY=…): nazwa wielkimi literami jak SEKRET w srodowisko.py
    ("zmienna z sekretem", re.compile(r"^\s*(?:export\s+)?[A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|HASLO"
                                      r"|KLUCZ)[A-Z0-9_]*\s*=\s*[\"']?([A-Za-z0-9_\-./+=~]{12,})", re.M)),
    ("przypisanie sekretu", re.compile(r"(?i)\b[A-Z0-9_]*(?:API[_-]?KEY|SECRET|TOKEN|PASSWORD|PASSWD|HASLO|KLUCZ)"
                                       r"[A-Z0-9_]*[\"']?\s*[=:]\s*[\"']?([A-Za-z0-9_\-./+=]{16,})")),
]
KANDYDAT_SEKRETU = (re.compile(r"[A-Za-z0-9_\-]{16,}"), re.compile(r"[A-Za-z0-9_\-.~+/=]{16,}"))

# Różnice migawek, które nie są śladem Jarva: (wzór klucza bez wielkości liter, kiedy, powód). „kiedy”: dowolnie,
# pusty (wpis dodany jako pusty katalog), zmieniony. Klucz to `<miejsce>:<ścieżka względna>` z migawki.
WYJATKI: list[tuple[str, str, str]] = [
    ("localappdata:temp", "dowolnie", "katalog tymczasowy Windows (TEMP) zmienia się sam; odinstalowanie działa "
                                      "z kopii w %TEMP%"),
    ("localappdata:d3dscache", "dowolnie", "pamięć shaderów Windows (każdy program z grafiką)"),
    ("localappdata:crashdumps", "zmieniony", "zrzuty awarii innych programów runnera"),
    ("localappdata:connecteddevicesplatform", "dowolnie", "usługa Windows (CDP) zakłada go sama"),
    ("localappdata:packages", "zmieniony", "aplikacje Sklepu Windows"),
    # obraz windows-2025 i windows-11-arm ma Firefoksa (C:\ProgramData\Mozilla-1de4eec8-…, katalog jego aktualizatora):
    # zadanie w tle zakłada te katalogi samo (WARM: były już przed instalacją, W64: pojawiły się w trakcie); Jarvo nie
    # uruchamia przeglądarek Mozilli (Camoufox pobiera się dopiero przy pierwszym użyciu, CI go nie pobiera)
    ("appdata:mozilla", "dowolnie", "Firefox z obrazu runnera (zadanie aktualizatora w tle)"),
    ("localappdata:mozilla", "dowolnie", "Firefox z obrazu runnera (zadanie aktualizatora w tle)"),
    ("localappdata:microsoft", "zmieniony", "dane systemu Windows"),
    ("dom:ntuser*", "dowolnie", "pliki gałęzi rejestru użytkownika i ich dzienniki transakcji (system)"),
    ("dom:.bash_history", "dowolnie", "historia powłoki runnera"),
    ("dom:.zsh_history", "dowolnie", "historia powłoki runnera"),
    ("dom:.zsh_sessions", "dowolnie", "sesje Terminala macOS"),
    ("dom:.lesshst", "dowolnie", "historia programu less"),
    ("dom:.viminfo", "dowolnie", "historia edytora vim"),
    ("dom:.python_history", "dowolnie", "historia interaktywnego Pythona"),
    ("dom:.cfusertextencoding", "dowolnie", "macOS zakłada go przy pierwszym programie z interfejsem"),
    ("dom:.trash", "dowolnie", "kosz macOS"),
    ("library-caches:com.apple.*", "dowolnie", "pamięć podręczna usług macOS"),
    ("app-support:com.apple.*", "dowolnie", "dane usług macOS"),
    ("library-caches:cloudkit", "dowolnie", "usługa macOS"),
    ("dom:.local", "pusty", "pusty katalog XDG zostaje celowo (standardowe miejsce, inne programy też go używają)"),
    ("dom:.cache", "pusty", "pusty katalog XDG zostaje celowo"),
    ("dom:.config", "pusty", "pusty katalog XDG zostaje celowo"),
    ("local:bin", "pusty", "pusty ~/.local/bin zostaje celowo (katalog w PATH z ~/.profile Ubuntu)"),
    ("local:share", "pusty", "pusty katalog XDG zostaje celowo"),
    ("local:state", "pusty", "pusty katalog XDG zostaje celowo"),
    ("config:systemd", "pusty", "pusty katalog jednostek użytkownika zostaje celowo"),
    ("config:systemd/user", "pusty", "pusty katalog jednostek użytkownika zostaje celowo"),
    ("library:launchagents", "pusty", "pusty katalog LaunchAgentów macOS zostaje celowo"),
]


class BladE2E(RuntimeError):
    """Krok testu nie mógł się wykonać (komunikat po polsku, bez sekretów)."""


# ---------------------------------------------------------------- tekst, sekrety, raport

def teraz() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


BOM_UTF16 = {b"\xff\xfe": "utf-16-le", b"\xfe\xff": "utf-16-be"}


def czytaj_tekst(p: Path, limit: int | None = None) -> str:
    """Plik tekstowy niezależnie od kodowania: Tee-Object z Windows PowerShell 5.1 pisze UTF-16 z BOM, reszta UTF-8.
    `limit`: tylko ostatnie bajty (logi do 10 MB), w UTF-16 ucięte na granicy znaku."""
    with open(p, "rb") as f:
        bom = f.read(4)
        f.seek(0, os.SEEK_END)
        rozmiar = f.tell()
        start = 0 if limit is None or rozmiar <= limit else rozmiar - limit
        utf16 = BOM_UTF16.get(bom[:2])
        if utf16 and start % 2:
            start += 1
        f.seek(start)
        dane = f.read()
    if utf16:
        return (dane[2:] if start == 0 else dane).decode(utf16, errors="replace")
    if start == 0 and dane[:3] == b"\xef\xbb\xbf":
        dane = dane[3:]
    probka = dane[:4000]
    if probka and probka.count(b"\x00") > len(probka) // 4:          # UTF-16 LE bez BOM
        return dane.decode("utf-16-le", errors="replace")
    return dane.decode("utf-8", errors="replace")


def bez_ansi(tekst: str) -> str:
    return ANSI.sub("", tekst).replace("\r\n", "\n").replace("\r", "\n")


def _wartosci_z_otoczenia(nazwy: Iterable[str] = ZMIENNE_SEKRETOW) -> list[str]:
    return [os.environ[n] for n in nazwy if len(os.environ.get(n) or "") >= 8]


def _wyglada_na_sekret(wartosc: str) -> bool:
    return any(c.isalpha() for c in wartosc) and any(c.isdigit() for c in wartosc)


def _maskuj(m: re.Match) -> str:
    """Trafienie wzoru sekretu: z grupą wartości maskujemy samą wartość (nazwa zostaje), bez grupy całość."""
    if m.re.groups and m.group(1) is not None:
        if not _wyglada_na_sekret(m.group(1)):
            return m.group(0)
        poczatek, cale = m.start(0), m.group(0)
        return cale[: m.start(1) - poczatek] + "<ukryty>" + cale[m.end(1) - poczatek:]
    return "<ukryty>"


def bez_sekretow(tekst: str, wartosci: Iterable[str] = ()) -> str:
    """Tekst do pokazania na ekranie albo w raporcie: znane wartości i wszystko, co wygląda na sekret, zamaskowane."""
    for w in sorted({*wartosci, *_wartosci_z_otoczenia()}, key=len, reverse=True):
        if w:
            tekst = tekst.replace(w, "<ukryty>")
    for _nazwa, wzor in WZORY_SEKRETOW:
        tekst = wzor.sub(_maskuj, tekst)
    return tekst


def skrot(tekst: str, ile: int = 600) -> str:
    """Koniec tekstu bez kolorów i sekretów (do raportu i na ekran)."""
    t = bez_sekretow(bez_ansi(tekst or "")).strip()
    return t if len(t) <= ile else "…" + t[-ile:]


def zapisz_json(p: Path, dane: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(dane, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def wczytaj_json(p: Path) -> Any:
    try:
        return json.loads(czytaj_tekst(p))
    except (OSError, ValueError):
        return None


def katalog_artefaktow(wartosc: str | None = None) -> Path:
    d = (wartosc or os.environ.get("JARVO_E2E_ARTEFAKTY")
         or (str(Path(os.environ["RUNNER_TEMP"]) / "natywnie-artefakty") if os.environ.get("RUNNER_TEMP") else None)
         or str(Path(tempfile.gettempdir()) / "jarvo-natywnie-e2e"))
    p = Path(d)
    p.mkdir(parents=True, exist_ok=True)
    return p


def plik_sekretow(art: Path) -> Path:
    """Skróty sekretów do skanu: obok katalogu artefaktów, nigdy w nim (nie trafia do wysyłki)."""
    return Path(os.environ.get("JARVO_E2E_SEKRETY") or art.parent / f"{art.name}-sekrety.json")


class Raport:
    """Punkty testu w <artefakty>/raport.json; kolejne podpolecenia dopisują swoje (ten sam id = nowy wynik)."""

    def __init__(self, art: Path):
        self.plik = art / "raport.json"
        dane = wczytaj_json(self.plik)
        self.dane = dane if isinstance(dane, dict) and isinstance(dane.get("punkty"), list) else {"punkty": []}
        if not self.dane.get("noga"):
            self.dane["noga"] = os.environ.get("JARVO_E2E_NOGA") or sys.platform
        self.teraz: dict[str, bool | None] = {}       # punkty tego procesu: o kodzie wyjścia decydują tylko one

    def punkt(self, ident: str, nazwa: str, ok: bool | None, opis: str, **szczegoly: Any) -> bool:
        """ok: True = przeszedł, False = nie przeszedł, None = pominięty (z powodem w opisie)."""
        wpis = {"id": ident, "nazwa": nazwa, "ok": ok, "opis": skrot(opis, 2000), "czas": teraz()}
        wpis.update({k: v for k, v in szczegoly.items() if v is not None})
        self.dane["punkty"] = [p for p in self.dane["punkty"] if p.get("id") != ident] + [wpis]
        self.teraz[ident] = ok
        zapisz_json(self.plik, self.dane)
        znak = {True: "[ok]     ", False: "[BŁĄD]   ", None: "[pominięte]"}[ok]
        print(f"{znak} {nazwa}: {wpis['opis']}", flush=True)
        return ok is not False

    @property
    def bledy(self) -> list[str]:
        """Punkty, które w tym procesie nie przeszły."""
        return [i for i, ok in self.teraz.items() if ok is False]


# ---------------------------------------------------------------- procesy

@dataclass
class Wynik:
    kod: int
    out: str
    err: str
    sekundy: float

    @property
    def tekst(self) -> str:
        return self.out + (("\n" + self.err) if self.err else "")


def uruchom(argv: list, *, czas: float = 120, env: dict | None = None, cwd: str | Path | None = None,
            wejscie: str | None = None, bez_okna: bool = False) -> Wynik:
    """Program z przechwyconym wyjściem w UTF-8; limit czasu = kod -1 (bez wyjątku). Bez `wejscie` wejściem jest
    pusty strumień: pytanie programu (np. potwierdzenie Hermesa) nie zawiesi testu."""
    t0 = time.monotonic()
    wejscie_kw: dict[str, Any] = ({"input": wejscie.encode("utf-8")} if wejscie is not None
                                  else {"stdin": subprocess.DEVNULL})
    try:
        r = subprocess.run([str(x) for x in argv], capture_output=True, timeout=czas, env=env,
                           cwd=str(cwd) if cwd else None, creationflags=NO_WINDOW if (bez_okna and WINDOWS) else 0,
                           **wejscie_kw)
    except subprocess.TimeoutExpired as e:
        def _t(b: Any) -> str:
            return b.decode("utf-8", errors="replace") if isinstance(b, bytes) else (b or "")
        return Wynik(-1, _t(e.stdout), _t(e.stderr) + f"\n(limit czasu {czas:.0f} s)", time.monotonic() - t0)
    except OSError as e:
        return Wynik(-2, "", f"nie da się uruchomić {argv[0]}: {e}", time.monotonic() - t0)
    return Wynik(r.returncode, r.stdout.decode("utf-8", errors="replace"), r.stderr.decode("utf-8", errors="replace"),
                 time.monotonic() - t0)


def systemowy(nazwa: str) -> str | None:
    return instalator.systemowy(nazwa)


def json_z_wyjscia(tekst: str) -> Any:
    """Pierwszy obiekt JSON w wyjściu programu (ostrzeżenia przed nim nie przeszkadzają)."""
    i = tekst.find("{")
    while i >= 0:
        try:
            return json.JSONDecoder().raw_decode(tekst[i:])[0]
        except ValueError:
            i = tekst.find("{", i + 1)
    return None


# ---------------------------------------------------------------- instalacja pod testem

def _ta_sama(a: str | Path, b: str | Path) -> bool:
    if os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b))):
        return True
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def polecenie_jarvo(u: Uklad, jawne: str | None = None) -> Path | None:
    """Polecenie `jarvo` tej instalacji: Windows <root>\\bin\\jarvo.cmd, POSIX <root>/bin/jarvo (próby z --bez-path)
    albo ~/.local/bin/jarvo, jeśli to nasze polecenie dla tego korzenia."""
    if jawne:
        return Path(jawne)
    if WINDOWS:
        p = u.root / "bin" / "jarvo.cmd"
        return p if p.is_file() else None
    p = u.root / "bin" / "jarvo"
    if p.is_file():
        return p
    dom = Path.home() / ".local" / "bin" / "jarvo"
    if dom.is_file():
        tekst = dom.read_text(encoding="utf-8", errors="replace")
        if instalator.ZNACZNIK in tekst:
            k = instalator.korzen_polecenia(tekst)
            domyslny = sciezki.uklad({k2: v for k2, v in os.environ.items() if k2 != "JARVO_ROOT"}).root
            if _ta_sama(k or domyslny, u.root):
                return dom
    return None


class Instalacja:
    """Instalacja natywna pod testem: układ katalogów, polecenie jarvo, Hermes z current.json."""

    def __init__(self, korzen: str | None = None, jarvo: str | None = None):
        env = dict(os.environ)
        if korzen:
            env["JARVO_ROOT"] = os.path.abspath(os.path.expanduser(korzen))
            os.environ["JARVO_ROOT"] = env["JARVO_ROOT"]   # jarvo, Hermes i srodowisko() biorą korzeń z otoczenia
        try:
            self.u = sciezki.uklad(env)
        except sciezki.BladUkladu as e:
            raise BladE2E(str(e)) from None
        self.jarvo = polecenie_jarvo(self.u, jarvo)

    @property
    def biez(self) -> dict:
        return srodowisko.biezace(self.u)

    @property
    def checkout(self) -> Path | None:
        h = self.biez.get("hermes")
        return Path(h) if h else None

    @property
    def app(self) -> Path:
        a = self.biez.get("app")
        return Path(a) if a else REPO

    def env_terminala(self) -> dict:
        """Otoczenie „nowego okna terminala”: katalog polecenia jarvo na początku PATH (Windows: wpis z HKCU dochodzi
        dopiero w nowym oknie, POSIX: ~/.profile), bez proxy dla 127.0.0.1."""
        env = dict(os.environ)
        if self.jarvo is not None:
            env["PATH"] = os.pathsep.join([str(self.jarvo.parent), env.get("PATH", "")])
        env["NO_PROXY"] = ",".join(x for x in ("127.0.0.1", "localhost", env.get("NO_PROXY", "")) if x)
        return env

    def jarvo_cmd(self, *argumenty: str, czas: float = 180, cwd: str | Path | None = None) -> Wynik:
        if self.jarvo is None:
            return Wynik(-2, "", f"brak polecenia jarvo dla {self.u.root} (instalacja się nie udała?)", 0.0)
        return uruchom([self.jarvo, *argumenty], czas=czas, env=self.env_terminala(), cwd=cwd)

    def env_jarva(self) -> dict:
        env = srodowisko.srodowisko(self.u)
        env["NO_PROXY"] = "127.0.0.1,localhost"
        return env

    def hermes_python(self) -> Path:
        if self.checkout is None:
            raise BladE2E(f"brak Hermesa w {self.u.program / 'current.json'} (instalacja niepełna)")
        return srodowisko.hermes_python(self.checkout)

    def hermes(self, *argumenty: str, czas: float = 300, wejscie: str | None = None) -> Wynik:
        """`hermes -p default <argumenty>` Pythonem venvu Hermesa w środowisku Jarva (HERMES_HOME = <dane>)."""
        if self.checkout is None:
            return Wynik(-2, "", "brak Hermesa w current.json", 0.0)
        argv = jhermes.argv_hermesa(self.checkout, "-p", "default", *argumenty)
        return uruchom(argv, czas=czas, env=self.env_jarva(), cwd=self.u.dane, wejscie=wejscie, bez_okna=True)

    def scal_config(self, plik: Path, zmiany: dict, zastap: Iterable[str] = ()) -> None:
        """config.yaml profilu: głębokie scalenie `zmiany` Pythonem Hermesa (PyYAML jest w jego venvie); klucze
        z `zastap` (np. model) idą w całości, bez resztek domyślnej konfiguracji."""
        skrypt = ("import json, sys, yaml\nfrom pathlib import Path\n"
                  "p = Path(sys.argv[1]); z = json.loads(sys.stdin.read())\n"
                  "c = (yaml.safe_load(p.read_text(encoding='utf-8')) if p.is_file() else None) or {}\n"
                  "for k in z.pop('__zastap__', []):\n"
                  "    c[k] = z.pop(k)\n"
                  "def s(a, b):\n"
                  "    for k, v in b.items():\n"
                  "        if isinstance(v, dict) and isinstance(a.get(k), dict): s(a[k], v)\n"
                  "        else: a[k] = v\n"
                  "s(c, z)\n"
                  "p.write_text(yaml.safe_dump(c, allow_unicode=True, sort_keys=False), encoding='utf-8', "
                  "newline='\\n')\n")
        dane = {**zmiany, "__zastap__": [k for k in zastap if k in zmiany]}
        r = uruchom([self.hermes_python(), "-I", "-c", skrypt, plik], czas=60, wejscie=json.dumps(dane),
                     bez_okna=True)
        if r.kod != 0:
            raise BladE2E(f"zapis {plik.name} nie przeszedł (kod {r.kod}): {skrot(r.err, 300)}")

    def czytaj_yaml(self, plik: Path, klucz: str) -> Any:
        """Jedna wartość z pliku YAML (kropki = zagnieżdżenie) Pythonem Hermesa; None, gdy brak."""
        skrypt = ("import json, sys, yaml\nd = yaml.safe_load(open(sys.argv[1], encoding='utf-8')) or {}\n"
                  "for k in sys.argv[2].split('.'):\n    d = d.get(k) if isinstance(d, dict) else None\n"
                  "print(json.dumps(d))\n")
        try:
            r = uruchom([self.hermes_python(), "-I", "-c", skrypt, plik, klucz], czas=60, bez_okna=True)
        except BladE2E:
            return None
        try:
            return json.loads(r.out.strip() or "null") if r.kod == 0 else None
        except ValueError:
            return None

    def port_api(self) -> int:
        """API bramy: API_SERVER_PORT z otoczenia, potem z <dane>/.env, inaczej 8642."""
        wartosc = os.environ.get("API_SERVER_PORT") or czytaj_env(self.u.dane / ".env").get("API_SERVER_PORT")
        return int(wartosc) if str(wartosc or "").isdigit() else PORT_API

    def env_ustawien(self) -> dict:
        """Otoczenie z ustawieniami instalacji (<stan>/ustawienia.json, np. JARVO_PANEL_PORT), jak polecenie jarvo."""
        env = dict(os.environ)
        for klucz, wartosc in instalator.ustawienia(self.u).items():
            if not str(env.get(klucz) or "").strip():
                env[klucz] = wartosc
        return env

    def port_panelu(self) -> int:
        return instalator.port_panelu(self.env_ustawien())


def czytaj_env(p: Path) -> dict[str, str]:
    """Plik .env: KLUCZ=wartość (bez export, cudzysłowy zdjęte)."""
    wynik: dict[str, str] = {}
    try:
        linie = czytaj_tekst(p).splitlines()
    except OSError:
        return wynik
    for linia in linie:
        m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$", linia)
        if m:
            wynik[m.group(1)] = m.group(2).strip().strip("\"'")
    return wynik


# ---------------------------------------------------------------- HTTP na 127.0.0.1

def http(metoda: str, url: str, *, klucz: str | None = None, dane: Any = None, czas: float = 15) -> tuple[int, Any]:
    """(status, JSON albo początek tekstu); 0 = nikt nie odpowiada. Bez proxy z ustawień systemu, klucz tylko
    w nagłówku (nigdy w wyniku)."""
    otwieracz = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    cialo = json.dumps(dane).encode("utf-8") if dane is not None else None
    naglowki = {"User-Agent": "jarvo-e2e", "Accept": "application/json"}
    if klucz:
        naglowki["Authorization"] = "Bearer " + klucz
    if cialo is not None:
        naglowki["Content-Type"] = "application/json"
    zadanie = urllib.request.Request(url, data=cialo, method=metoda, headers=naglowki)
    try:
        with otwieracz.open(zadanie, timeout=czas) as odp:
            status, tekst = odp.status, odp.read(4 << 20).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status, tekst = e.code, e.read(1 << 20).decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError, ValueError) as e:
        return 0, type(e).__name__
    try:
        return status, json.loads(tekst)
    except ValueError:
        return status, tekst[:500]


def port_slucha(port: int) -> bool:
    return instalator.port_zajety(port, 0.5)


# ---------------------------------------------------------------- migawka komputera (tylko odczyt)

def _skrot_pliku(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for kawalek in iter(lambda: f.read(1 << 20), b""):
            h.update(kawalek)
    return h.hexdigest()[:16]


def _bez_plikow(katalog: str, limit: int = 500) -> bool:
    """Czy w drzewie katalogu nie ma żadnego pliku ani dowiązania (same puste katalogi); przy `limit` wpisów: nie."""
    n = 0
    stos = [katalog]
    while stos:
        try:
            with os.scandir(stos.pop()) as it:
                for e in it:
                    n += 1
                    if n > limit or e.is_symlink() or not e.is_dir(follow_symlinks=False):
                        return False
                    stos.append(e.path)
        except OSError:
            return False
    return True


def _wpisy(katalog: Path, glebokosc: int, tresc: bool) -> dict[str, str]:
    """Wpisy katalogu do `glebokosc` poziomów: d (katalog), d0 (katalog bez plików w całym drzewie, np. pusty
    katalog XDG), f (plik; przy `tresc` z rozmiarem i skrótem), l:<cel> (dowiązanie, bez wchodzenia), ? (brak
    dostępu)."""
    wynik: dict[str, str] = {}

    def idz(k: Path, rel: str, poziom: int) -> None:
        try:
            with os.scandir(k) as it:
                wpisy = sorted(it, key=lambda e: e.name)
        except OSError:
            wynik[rel or "."] = "?"
            return
        for e in wpisy:
            r = f"{rel}/{e.name}" if rel else e.name
            try:
                if e.is_symlink():
                    try:
                        wynik[r] = "l:" + os.readlink(e.path)
                    except OSError:
                        wynik[r] = "l"
                elif e.is_dir(follow_symlinks=False):
                    if poziom < glebokosc:
                        idz(Path(e.path), r, poziom + 1)
                    wynik[r] = "d0" if _bez_plikow(e.path) else "d"
                else:
                    wynik[r] = (f"f:{e.stat(follow_symlinks=False).st_size}:{_skrot_pliku(Path(e.path))}"
                                if tresc else "f")
            except OSError:
                wynik[r] = "?"

    idz(katalog, "", 1)
    return wynik


def _odcisk(katalog: Path, limit: int = 50_000) -> str:
    """Liczba plików i bajtów w całym drzewie (do `limit` wpisów): nowe pliki w cache, którego Jarvo nie rusza."""
    n = bajty = 0
    for korzen, katalogi, pliki in os.walk(katalog, onerror=lambda e: None):
        katalogi[:] = [k for k in katalogi if not os.path.islink(os.path.join(korzen, k))]
        for p in pliki:
            n += 1
            with contextlib.suppress(OSError):
                bajty += os.lstat(os.path.join(korzen, p)).st_size
            if n >= limit:
                return f"o:ponad {limit}"
    return f"o:{n}:{bajty}"


def miejsca(env: dict | None = None) -> list[tuple[str, Path, int, str]]:
    """(etykieta, katalog, głębokość, tryb) do migawki; tryb: nazwy, tresc (skróty plików), odcisk."""
    env = dict(os.environ if env is None else env)
    if WINDOWS:
        dom = Path(env.get("USERPROFILE") or Path.home())
        lad = Path(env.get("LOCALAPPDATA") or dom / "AppData" / "Local")
        rad = Path(env.get("APPDATA") or dom / "AppData" / "Roaming")
        pd = Path(env.get("ProgramData") or env.get("PROGRAMDATA") or r"C:\ProgramData")
        menu = rad / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        m = [("dom", dom, 1, "nazwy"), ("localappdata", lad, 1, "nazwy"), ("appdata", rad, 1, "nazwy"),
             ("programdata", pd, 1, "nazwy"), ("menu-start", menu, 2, "nazwy"),
             ("folder-autostartu", menu / "Startup", 1, "tresc"),
             ("profil-powershell", dom / "Documents" / "WindowsPowerShell", 1, "tresc"),
             ("profil-pwsh", dom / "Documents" / "PowerShell", 1, "tresc"),
             ("local", dom / ".local", 3, "nazwy"), ("config", dom / ".config", 2, "nazwy")]
        odciski = [lad / "uv", lad / "npm-cache", rad / "npm-cache", rad / "npm", lad / "pip", lad / "ms-playwright",
                   lad / "hermes", dom / ".hermes", dom / ".cache", dom / ".npm", rad / "uv", lad / "Programs"]
    else:
        dom = Path.home()
        m = [("dom", dom, 1, "nazwy"), ("local", dom / ".local", 3, "nazwy"), ("config", dom / ".config", 2, "nazwy"),
             ("cache", dom / ".cache", 2, "nazwy"), ("systemd-user", dom / ".config" / "systemd" / "user", 3, "tresc"),
             ("local-bin", dom / ".local" / "bin", 1, "tresc")]
        for zmienna, etykieta in (("XDG_DATA_HOME", "xdg-data"), ("XDG_STATE_HOME", "xdg-state"),
                                  ("XDG_CACHE_HOME", "xdg-cache"), ("XDG_CONFIG_HOME", "xdg-config")):
            if env.get(zmienna):
                m.append((etykieta, Path(env[zmienna]), 2, "nazwy"))
        odciski = [dom / ".npm", dom / ".cache" / "uv", dom / ".cache" / "pip", dom / ".cache" / "huggingface",
                   dom / ".cache" / "ms-playwright", dom / ".hermes", dom / ".local" / "share" / "uv",
                   dom / ".config" / "uv"]
        if MACOS:
            lib = dom / "Library"
            m += [("library", lib, 1, "nazwy"), ("launchagents", lib / "LaunchAgents", 1, "tresc"),
                  ("app-support", lib / "Application Support", 1, "nazwy"),
                  ("library-caches", lib / "Caches", 1, "nazwy")]
            odciski += [lib / "Caches" / "ms-playwright", lib / "Application Support" / "hermes"]
        if LINUX:
            m.append(("linger", Path("/var/lib/systemd/linger"), 1, "nazwy"))
    m += [(f"odcisk:{p}", p, 0, "odcisk") for p in odciski]
    return m


PLIKI_STARTOWE = (".profile", ".bash_profile", ".bash_login", ".bashrc", ".zprofile", ".zshrc", ".zshenv", ".zlogin",
                  ".config/fish/config.fish")


def _rejestr_windows() -> dict[str, str]:
    """HKCU: zmienne użytkownika (PATH wprost, sekrety tylko „jest”, reszta jako skrót), Run, RunOnce i wpis
    w „Aplikacje”. Tylko odczyt."""
    import winreg
    wynik: dict[str, str] = {}

    def wartosci(sciezka: str, przedrostek: str, jawne: tuple[str, ...] = ()) -> None:
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sciezka)
        except OSError:
            return
        with k:
            i = 0
            while True:
                try:
                    nazwa, wartosc, typ = winreg.EnumValue(k, i)
                except OSError:
                    break
                i += 1
                if nazwa.lower() in jawne:
                    wynik[f"{przedrostek}:{nazwa}"] = f"{typ}:{wartosc}"
                elif SEKRET_NAZWA.search(nazwa):
                    wynik[f"{przedrostek}:{nazwa}"] = f"{typ}:<sekret>"
                else:
                    wynik[f"{przedrostek}:{nazwa}"] = f"{typ}:" + hashlib.sha256(str(wartosc).encode()).hexdigest()[:16]

    wartosci("Environment", "zmienna", ("path",))
    wartosci(r"Software\Microsoft\Windows\CurrentVersion\Run", "run")
    wartosci(r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "runonce")
    try:
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Jarvo").Close()
        wynik["aplikacje:Jarvo"] = "jest"
    except OSError:
        pass
    return wynik


def _dekoduj(dane: bytes) -> str:
    """Wyjście narzędzi konsoli Windows (schtasks) przychodzi w stronie kodowej OEM, a nie w UTF-8."""
    try:
        return dane.decode("utf-8")
    except UnicodeDecodeError:
        pass
    if WINDOWS:
        import ctypes
        for strona in (f"cp{ctypes.windll.kernel32.GetOEMCP()}", "mbcs"):
            with contextlib.suppress(LookupError, UnicodeDecodeError):
                return dane.decode(strona)
    return dane.decode("utf-8", errors="replace")


def _autostart_systemu() -> dict[str, str]:
    """Zadania Harmonogramu, LaunchAgenty i jednostki systemd --user z „jarvo” albo „hermes” w nazwie."""
    wynik: dict[str, str] = {}
    nasze = re.compile(r"jarvo|hermes", re.I)
    if WINDOWS:
        schtasks = systemowy("schtasks")
        if schtasks:
            try:
                r = subprocess.run([schtasks, "/Query", "/FO", "CSV", "/NH"], capture_output=True, timeout=120,
                                   creationflags=NO_WINDOW)
                for linia in _dekoduj(r.stdout).splitlines():
                    nazwa = linia.split('","')[0].strip().strip('"')
                    if nazwa and nasze.search(nazwa):
                        wynik[f"zadanie:{nazwa}"] = "jest"
            except (OSError, subprocess.SubprocessError):
                wynik["zadanie:?"] = "schtasks nie odpowiada"
    elif MACOS:
        r = uruchom(["launchctl", "list"], czas=60)
        for linia in r.out.splitlines()[1:]:
            etykieta = linia.split()[-1] if linia.split() else ""
            if nasze.search(etykieta):
                wynik[f"launchd:{etykieta}"] = "wczytany"
    elif LINUX:
        systemctl = shutil.which("systemctl")
        if systemctl:
            for rodzaj in ("list-unit-files", "list-units"):
                r = uruchom([systemctl, "--user", rodzaj, "--all", "--no-legend", "--no-pager"], czas=60)
                if r.kod != 0:
                    wynik[f"systemd:{rodzaj}"] = "niedostępne (brak user busa)"
                    continue
                for linia in r.out.splitlines():
                    jednostka = (linia.split() or [""])[0]
                    if nasze.search(jednostka):
                        wynik[f"systemd:{rodzaj}:{jednostka}"] = " ".join(linia.split()[1:3])
    return wynik


def migawka(env: dict | None = None, *, u: Uklad | None = None) -> dict:
    """Migawka stanu komputera poza Jarvem (tylko odczyt): {"czas", "system", "wpisy": {klucz: wartość}}."""
    env = dict(os.environ if env is None else env)
    wpisy: dict[str, str] = {}
    for etykieta, katalog, glebokosc, tryb in miejsca(env):
        if not katalog.is_dir():
            continue
        if tryb == "odcisk":
            wpisy[f"{etykieta}"] = _odcisk(katalog)
            continue
        for rel, wartosc in _wpisy(katalog, glebokosc, tryb == "tresc").items():
            wpisy[f"{etykieta}:{rel}"] = wartosc
    dom = Path(env.get("USERPROFILE") or Path.home()) if WINDOWS else Path.home()
    for rel in PLIKI_STARTOWE:
        p = dom / rel
        if p.is_file():
            wpisy[f"plik-startowy:{rel}"] = _skrot_pliku(p)
    if WINDOWS:
        wpisy.update(_rejestr_windows())
    wpisy.update(_autostart_systemu())
    if u is None:
        try:
            u = sciezki.uklad(env)
        except sciezki.BladUkladu:
            u = None
    if u is not None:
        for nazwa, k in (("korzen", u.root), ("logi", u.logi), ("cache", u.cache)):
            if k.exists():
                wpisy[f"jarvo-{nazwa}:{k}"] = "jest"
    return {"czas": teraz(), "system": sciezki.platforma(), "wpisy": dict(sorted(wpisy.items()))}


def _pasuje(klucz: str, wzor: str) -> bool:
    return fnmatch.fnmatchcase(klucz.lower(), wzor.lower())


def roznica(przed: dict, po: dict, wyjatki: Iterable[tuple[str, str, str]] = ()) -> dict:
    """Różnica migawek: każdy dodany, usunięty i zmieniony wpis z wyjaśnieniem (wyjątek i powód) albo bez."""
    a, b = przed.get("wpisy") or {}, po.get("wpisy") or {}
    reguly = [*WYJATKI, *wyjatki]
    zmiany = []
    for klucz in sorted(set(a) | set(b)):
        if a.get(klucz) == b.get(klucz):
            continue
        rodzaj = "dodany" if klucz not in a else "usunięty" if klucz not in b else "zmieniony"
        powod = None
        for wzor, kiedy, uzasadnienie in reguly:
            if not _pasuje(klucz, wzor):
                continue
            if kiedy == "dowolnie" or (kiedy == "zmieniony" and rodzaj == "zmieniony") or (
                    kiedy == "pusty" and rodzaj == "dodany" and b.get(klucz) == "d0") or (
                    kiedy == "pusty" and rodzaj == "zmieniony" and {a.get(klucz), b.get(klucz)} <= {"d", "d0"}
                    and b.get(klucz) == "d0"):
                powod = uzasadnienie
                break
        zmiany.append({"klucz": klucz, "rodzaj": rodzaj, "przed": a.get(klucz), "po": b.get(klucz),
                       "wyjasnienie": powod})
    nie = [z for z in zmiany if not z["wyjasnienie"]]
    return {"czas": teraz(), "zmiany": zmiany, "niewyjasnione": len(nie), "wyjasnione": len(zmiany) - len(nie)}


KIEDY = ("dowolnie", "pusty", "zmieniony")


def parsuj_wyjatek(tekst: str) -> tuple[str, str, str]:
    """`WZÓR[=kiedy]|POWÓD` (kiedy: dowolnie, pusty, zmieniony). Klucze migawki mają „:” (`<miejsce>:<ścieżka>`),
    więc powód oddziela „|”."""
    wzor, _, powod = tekst.partition("|")
    reszta, _, kiedy = wzor.rpartition("=")
    if reszta and kiedy.strip() in KIEDY:
        wzor = reszta
    else:
        kiedy = "dowolnie"
    if not wzor.strip() or not powod.strip():
        raise argparse.ArgumentTypeError(f"wyjątek {tekst!r}: potrzebny WZÓR[=kiedy]|POWÓD")
    return wzor.strip(), kiedy.strip(), powod.strip()


# ---------------------------------------------------------------- doctor, status, panel

def parsuj_dopusc(teksty: Iterable[str]) -> list[tuple[str, set[str], str]]:
    """`NAZWA=stan[,stan][:powód]`, wiele naraz rozdzielone „;” (wiersz macierzy CI). NAZWA to wzór (fnmatch)."""
    wynik = []
    for tekst in teksty:
        for czesc in (tekst or "").split(";"):
            czesc = czesc.strip()
            if not czesc:
                continue
            nazwa, _, reszta = czesc.partition("=")
            stany, _, powod = reszta.partition(":")
            if not nazwa.strip() or not stany.strip():
                raise argparse.ArgumentTypeError(f"--dopusc {czesc!r}: potrzebne NAZWA=stan[:powód]")
            wynik.append((nazwa.strip(), {s.strip() for s in stany.split(",") if s.strip()},
                          powod.strip() or "jawny wyjątek runnera"))
    return wynik


def ocen_doctora(d: Any, dopusc: list[tuple[str, set[str], str]]) -> tuple[bool, list[dict], list[dict]]:
    """(zielony, problemy, użyte wyjątki): każdy wynik „ok”, a „uwaga” i „blad” tylko z jawnym wyjątkiem. Inne stany
    (np. pominięte z powodu braku platformy) są informacją, nie błędem."""
    if not isinstance(d, dict) or not isinstance(d.get("wyniki"), list):
        return False, [{"nazwa": "doctor", "stan": "blad", "opis": "brak wyniku JSON"}], []
    problemy, uzyte = [], []
    for w in d["wyniki"]:
        stan, nazwa = str(w.get("stan")), str(w.get("nazwa"))
        if stan not in ("uwaga", "blad"):
            continue
        wyjatek = next((x for x in dopusc if _pasuje(nazwa, x[0]) and stan in x[1]), None)
        if wyjatek:
            uzyte.append({"nazwa": nazwa, "stan": stan, "opis": w.get("opis"), "powod": wyjatek[2]})
        else:
            problemy.append({"nazwa": nazwa, "stan": stan, "opis": w.get("opis"), "rada": w.get("rada")})
    return not problemy, problemy, uzyte


def adres_panelu(inst: "Instalacja", status: Any) -> str:
    adres = status.get("panel") if isinstance(status, dict) else None
    return str(adres or instalator.adres_panelu(inst.env_ustawien()))


def sprawdz_panel(inst: Instalacja, adres: str, rap: Raport) -> None:
    baza = urllib.parse.urlsplit(adres)
    korzen_url = f"{baza.scheme}://{baza.netloc}"
    status, dane = 0, None
    koniec = time.monotonic() + 60
    while time.monotonic() < koniec:
        status, dane = http("GET", korzen_url + "/api/status", czas=5)
        if status == 200:
            break
        time.sleep(2)
    if status != 200 or not isinstance(dane, dict):
        rap.punkt("panel", "panel odpowiada", False, f"{korzen_url}/api/status: HTTP {status} {skrot(str(dane), 200)}")
        return
    home = str(dane.get("hermes_home") or "")
    nasz = bool(home) and _ta_sama(home, inst.u.dane)
    s_strony = http("GET", korzen_url + "/", czas=10)[0]
    hq = (inst.u.dane / "plugins" / "jarvo-hq").is_dir()
    s_hq = http("GET", korzen_url + "/jarvo", czas=10)[0] if hq else None
    ok = nasz and s_strony == 200 and (s_hq in (None, 200))
    opis = (f"{korzen_url}: /api/status {status} (hermes_home {'= <dane>' if nasz else repr(home)}, wersja "
            f"{dane.get('version') or dane.get('hermes_version') or '?'}), / {s_strony}"
            + (f", /jarvo {s_hq}" if hq else ", /jarvo pominięte (brak wtyczki jarvo-hq w <dane>/plugins)"))
    rap.punkt("panel", "panel odpowiada", ok, opis, adres=korzen_url)


def aktywni_agenci(fleet_yaml: Path) -> list[str]:
    """Aktywni agenci z fleet.yaml bez parsera YAML (bloki `  - name:` i `    status:`)."""
    try:
        tekst = fleet_yaml.read_text(encoding="utf-8")
    except OSError:
        return []
    sekcja = tekst.split("\nagents:", 1)[1] if "\nagents:" in tekst else ""
    wynik = []
    for blok in re.split(r"\n  - name: ", "\n" + sekcja)[1:]:
        nazwa = blok.split("\n", 1)[0].strip().strip("\"'")
        m = re.search(r"^    status:\s*(\S+)", blok, re.M)
        if nazwa and m and m.group(1).strip("\"'") == "active":
            wynik.append(nazwa)
    return wynik


# ---------------------------------------------------------------- atrapa modelu i profile testowe

def odpowiedz_e2e(wiadomosci: list[dict], model: str, dalej: Callable[[list[dict], str], dict]) -> dict:
    """Atrapa modelu z jednym dodatkiem: pracownik kanbana („work kanban task <id>”) woła kanban_complete, więc karta
    kończy się jak u prawdziwego specjalisty. Po wyniku narzędzia i w każdej innej rozmowie: zwykła atrapa."""
    ostatnia = wiadomosci[-1] if wiadomosci else {}
    if ostatnia.get("role") != "tool":
        tekst = next((w.get("content") for w in reversed(wiadomosci) if w.get("role") == "user"), "")
        if isinstance(tekst, list):
            tekst = " ".join(str(c.get("text", "")) for c in tekst if isinstance(c, dict))
        m = PRACA_KANBAN.search(str(tekst or ""))
        if m:
            karta = m.group(1).rstrip(".")
            return {"narzedzie": ("kanban_complete",
                                  {"summary": f"Test e2e: karta {karta} wykonana przez atrapę modelu."})}
    return dalej(wiadomosci, model)


def _zaladuj(nazwa: str, sciezka: Path) -> Any:
    spec = importlib.util.spec_from_file_location(nazwa, sciezka)
    if spec is None or spec.loader is None:
        raise BladE2E(f"nie da się wczytać {sciezka}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nazwa] = mod
    spec.loader.exec_module(mod)
    return mod


class Atrapa:
    """scripts/atrapa_modelu.py w wątku tego procesu, na 127.0.0.1 i porcie od systemu; dziennik zapytań w JSONL."""

    def __init__(self, dziennik: Path):
        self.mod = _zaladuj("jarvo_e2e_atrapa_modelu", REPO / "scripts" / "atrapa_modelu.py")
        oryginalna = self.mod.odpowiedz
        self.mod.odpowiedz = lambda w, m: odpowiedz_e2e(w, m, oryginalna)
        self.dziennik = dziennik
        dziennik.parent.mkdir(parents=True, exist_ok=True)
        self.mod.Obsluga.dziennik = str(dziennik)
        self.serwer = self.mod.Serwer(("127.0.0.1", 0), self.mod.Obsluga)
        self.port = int(self.serwer.server_address[1])
        self.watek = threading.Thread(target=self.serwer.serve_forever, name="atrapa-modelu", daemon=True)
        self.watek.start()

    def adres(self, profil: str) -> str:
        return f"http://127.0.0.1:{self.port}/p/{profil}/v1"

    def zapytania(self, profil: str) -> list[dict]:
        wynik = []
        with contextlib.suppress(OSError):
            for linia in self.dziennik.read_text(encoding="utf-8", errors="replace").splitlines():
                with contextlib.suppress(ValueError):
                    z = json.loads(linia)
                    if isinstance(z, dict) and str(z.get("_sciezka", "")).startswith(f"/p/{profil}/"):
                        wynik.append(z)
        return wynik

    def zamknij(self) -> None:
        with contextlib.suppress(Exception):
            self.serwer.shutdown()
            self.serwer.server_close()


def bezpieczne_ustawienia() -> dict:
    """Te same bezpieczne ustawienia co instalator w profilu hosta (I13, H23, H24): profil testowy nie pobiera tirith
    ani paczek w locie, nie pożycza logowań właściciela i nie pyta GitHuba o aktualizacje."""
    return {"security": {"tirith_enabled": False, "allow_lazy_installs": False},
            "auth": {"adopt_external_logins": False}, "updates": {"check": False},
            "terminal": {"home_mode": "profile", "auto_source_bashrc": False}}


def stan_bramy(inst: Instalacja) -> dict:
    """Usługa bramy z `jarvo status --json` (nadzorca: pid, gotowa, restarty); {} bez odpowiedzi."""
    s = json_z_wyjscia(inst.jarvo_cmd("status", "--json", czas=60).out) or {}
    return (((s.get("serwis") or {}).get("stan") or {}).get("uslugi") or {}).get("brama") or {}


def czekaj_na_brame(inst: Instalacja, *, inny_pid: int | None = None, czas: float = 120) -> dict:
    """Aż nadzorca zgłosi bramę gotową (identify i /health API), po restarcie: z innym pid niż `inny_pid`
    (stara brama odpowiada jeszcze chwilę po zleceniu restartu). Zwraca ostatni stan bramy."""
    koniec = time.monotonic() + czas
    b: dict = {}
    while time.monotonic() < koniec:
        b = stan_bramy(inst)
        if b.get("gotowa") and (inny_pid is None or (b.get("pid") and b.get("pid") != inny_pid)):
            return b
        time.sleep(3)
    return b


def usun_profil(inst: Instalacja, nazwa: str) -> str | None:
    """`hermes profile delete -y`; None = usunięty albo go nie było, inaczej opis (sprzątanie nie zatrzymuje testu)."""
    if not (inst.u.dane / "profiles" / nazwa).exists():
        return None
    r = inst.hermes("profile", "delete", "-y", nazwa, czas=180)
    if (inst.u.dane / "profiles" / nazwa).exists():
        return f"{nazwa}: profil został (kod {r.kod}: {skrot(r.tekst, 200)})"
    return None


def utworz_profil(inst: Instalacja, nazwa: str, model: dict, *, env: dict[str, str], zgody: bool = False,
                  toolsety: list[str] | None = None) -> Path:
    usun_profil(inst, nazwa)                      # resztka po przerwanym przebiegu
    r = inst.hermes("profile", "create", nazwa, "--no-alias", "--no-skills", czas=300)
    p = inst.u.dane / "profiles" / nazwa
    if r.kod != 0 or not p.is_dir():
        raise BladE2E(f"hermes profile create {nazwa}: kod {r.kod}: {skrot(r.tekst, 400)}")
    cfg: dict[str, Any] = {"model": model, "agent": {"api_max_retries": 1, "auto_recovery_cycles": 0},
                           "approvals": {"mode": "manual", "timeout": 120}, **bezpieczne_ustawienia()}
    if toolsety is not None:
        cfg["platform_toolsets"] = {"api_server": toolsety, "cli": toolsety}
    if zgody:
        zrodlo = inst.u.dane / "plugins" / WTYCZKA_ZGOD
        if not (zrodlo / "plugin.yaml").is_file():
            zrodlo = inst.app / "zgody" / "plugin"   # flota jej nie zainstalowała: kod tej wersji
        if not (zrodlo / "plugin.yaml").is_file():
            raise BladE2E(f"brak wtyczki {WTYCZKA_ZGOD} (ani w <dane>/plugins, ani w {inst.app / 'zgody'})")
        cel = p / "plugins" / WTYCZKA_ZGOD
        shutil.copytree(zrodlo, cel, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"), dirs_exist_ok=True)
        cfg["plugins"] = {"enabled": [WTYCZKA_ZGOD]}
        stan = p / "plugin-data" / WTYCZKA_ZGOD / "stan.json"      # tryb „pytaj”: pytanie o każdy zapis pliku
        stan.parent.mkdir(parents=True, exist_ok=True)
        stan.write_text(json.dumps({"tryb": "pytaj", "przez": "test e2e"}) + "\n", encoding="utf-8")
    inst.scal_config(p / "config.yaml", cfg, zastap=("model",))
    (p / "home").mkdir(exist_ok=True)              # terminal.home_mode: profile działa tylko z tym katalogiem
    plik_env = p / ".env"
    stare = [x for x in (czytaj_tekst(plik_env).splitlines() if plik_env.is_file() else [])
             if x.split("=", 1)[0].strip() not in env]
    plik_env.write_text("\n".join([*stare, *(f"{k}={v}" for k, v in env.items())]) + "\n", encoding="utf-8")
    if not WINDOWS:
        os.chmod(plik_env, 0o600)
    return p


@dataclass
class Brama:
    port: int

    def url(self, profil: str, sciezka: str) -> str:
        return f"http://127.0.0.1:{self.port}/p/{profil}{sciezka}"

    def gotowa(self, profil: str, klucz: str, czas: float = 90) -> tuple[bool, str]:
        """Brama słucha (/health) i obsługuje nowy profil bez restartu (/p/<profil>/v1/capabilities)."""
        koniec = time.monotonic() + czas
        st_h = st = 0
        while time.monotonic() < koniec:
            st_h = http("GET", f"http://127.0.0.1:{self.port}/health", czas=5)[0]
            if st_h:
                st = http("GET", self.url(profil, "/v1/capabilities"), klucz=klucz, czas=5)[0]
                if st == 200:
                    return True, "ok"
            time.sleep(2)
        if not st_h:
            return False, (f"brama nie słucha na 127.0.0.1:{self.port} (API_SERVER_KEY w <dane>/.env? brama działa? "
                           "zobacz jarvo logs brama)")
        return False, f"/p/{profil}/v1/capabilities: HTTP {st}"

    def przebieg(self, profil: str, klucz: str, tekst: str, *, zgoda: str | None = None, czas: float = 240) -> dict:
        """POST /v1/runs i odpytywanie stanu; przy `waiting_for_approval` odpowiedź `zgoda` (raz na każdą prośbę).
        Wynik: {"status", "output", "prosby": [...], "error"}."""
        st, d = http("POST", self.url(profil, "/v1/runs"), klucz=klucz, dane={"input": tekst}, czas=30)
        if st not in (200, 201, 202) or not isinstance(d, dict) or not d.get("run_id"):
            raise BladE2E(f"POST /p/{profil}/v1/runs: HTTP {st} {skrot(str(d), 300)}")
        run_id = str(d["run_id"])
        prosby: list[dict] = []
        odpowiedziane: set[str] = set()
        status = str(d.get("status") or "")
        koniec = time.monotonic() + czas
        while time.monotonic() < koniec:
            st, s = http("GET", self.url(profil, f"/v1/runs/{run_id}"), klucz=klucz, czas=15)
            if st != 200 or not isinstance(s, dict):
                time.sleep(1)
                continue
            status = str(s.get("status") or "")
            if status == "waiting_for_approval":
                ap = s.get("approval") if isinstance(s.get("approval"), dict) else {}
                rid = str(ap.get("request_id") or "")
                znak = rid or hashlib.sha256(json.dumps(ap, sort_keys=True, default=str).encode()).hexdigest()
                if znak not in odpowiedziane:
                    odpowiedziane.add(znak)
                    prosby.append({"request_id": rid or None,
                                   "opis": skrot(str(ap.get("description") or ap.get("command") or ""), 300),
                                   "wybory": ap.get("choices")})
                    if zgoda is None:
                        http("POST", self.url(profil, f"/v1/runs/{run_id}/approval"), klucz=klucz,
                             dane={"choice": "deny", **({"request_id": rid} if rid else {})})
                        raise BladE2E(f"nieoczekiwana prośba o zgodę: {prosby[-1]['opis']}")
                    st_z, d_z = http("POST", self.url(profil, f"/v1/runs/{run_id}/approval"), klucz=klucz,
                                     dane={"choice": zgoda, **({"request_id": rid} if rid else {})})
                    if st_z != 200:
                        raise BladE2E(f"odpowiedź na prośbę o zgodę: HTTP {st_z} {skrot(str(d_z), 300)}")
            elif status in STATUSY_KONCOWE:
                return {"run_id": run_id, "status": status, "output": str(s.get("output") or ""),
                        "prosby": prosby, "error": skrot(str(s.get("error") or ""), 500) or None}
            time.sleep(0.5)
        raise BladE2E(f"przebieg {run_id} nie skończył się w {czas:.0f} s (ostatni status {status or '?'})")


def czekaj_na_karte(inst: Instalacja, ident: str, czas: float) -> dict:
    """`hermes kanban show <id> --json` co 5 s, aż karta będzie done, blocked albo archived (albo minie czas)."""
    koniec = time.monotonic() + czas
    ostatni: dict = {}
    while time.monotonic() < koniec:
        r = inst.hermes("kanban", "show", ident, "--json", czas=120)
        d = json_z_wyjscia(r.out)
        if isinstance(d, dict) and isinstance(d.get("task"), dict):
            ostatni = d
            if d["task"].get("status") in ("done", "blocked", "archived"):
                return d
        time.sleep(5)
    return ostatni


def log_pracownika(inst: Instalacja, ident: str) -> Path | None:
    kanban = inst.u.dane / "kanban"
    if not kanban.is_dir():
        return None
    return next(iter(sorted(kanban.rglob(f"{ident}.log"))), None)


# ---------------------------------------------------------------- podpolecenia

def polecenie_migawka(a) -> int:
    inst_u = None
    with contextlib.suppress(sciezki.BladUkladu):
        inst_u = sciezki.uklad(dict(os.environ, **({"JARVO_ROOT": a.korzen} if a.korzen else {})))
    m = migawka(u=inst_u)
    zapisz_json(Path(a.wyjscie), m)
    print(f"Migawka: {len(m['wpisy'])} wpisów → {a.wyjscie}")
    return 0


def polecenie_roznica(a) -> int:
    art = katalog_artefaktow(a.artefakty)
    rap = Raport(art)
    przed, po = wczytaj_json(Path(a.przed)), wczytaj_json(Path(a.po))
    if not isinstance(przed, dict) or not isinstance(po, dict):
        rap.punkt("migawka", "komputer po odinstalowaniu jak przed instalacją", False,
                  f"brak migawki ({a.przed if not isinstance(przed, dict) else a.po})")
        return 1
    r = roznica(przed, po, a.wyjatek)
    zapisz_json(art / "roznica.json", r)
    nie = [z for z in r["zmiany"] if not z["wyjasnienie"]]
    opis = (f"{len(r['zmiany'])} różnic, w tym {len(nie)} bez wyjaśnienia"
            + (": " + "; ".join(f"{z['rodzaj']} {z['klucz']}" for z in nie[:12]) if nie else "")
            + (f" (+{len(nie) - 12} w roznica.json)" if len(nie) > 12 else ""))
    rap.punkt("migawka", "komputer po odinstalowaniu jak przed instalacją", not nie, opis)
    return 1 if nie else 0


def _status(inst: Instalacja, rap: Raport, art: Path, ident: str, nazwa: str) -> dict | None:
    """`jarvo status --json` jako punkt: zainstalowane, serwis działa, panel nasz; JSON w <artefakty>/<ident>.json."""
    r = inst.jarvo_cmd("status", "--json", czas=120)
    s = json_z_wyjscia(r.out)
    if not isinstance(s, dict):
        rap.punkt(ident, nazwa, False, f"kod {r.kod}: {skrot(r.tekst, 400)}")
        return None
    zapisz_json(art / f"{ident}.json", s)
    serwis = s.get("serwis") or {}
    panel = (s.get("panel_jarva") or {}).get("stan")
    auto = s.get("autostart") or {}
    ok = bool(s.get("zainstalowane")) and bool(serwis.get("dziala")) and panel == "nasz"
    stan_serwisu = "działa" if serwis.get("dziala") else f"nie działa ({serwis.get('powod')})"
    rap.punkt(ident, nazwa, ok, f"zainstalowane {s.get('zainstalowane')}, serwis {stan_serwisu}, panel {panel}, "
              f"autostart {auto.get('opis') or auto.get('wlaczony')}", kod=r.kod)
    return s


def _doctor_status_panel(inst: Instalacja, rap: Raport, art: Path, dopusc: list, tylko_odczyt: bool = False) -> dict:
    r = inst.jarvo_cmd("version", czas=120)
    rap.punkt("wersja", "jarvo version", r.kod == 0, skrot(r.tekst, 300))
    # po instalacji brama restartuje się z flotą i łączy platformy: doctor dopiero, gdy nadzorca widzi ją gotową
    # (brama_gotowa: identify i /health API), najwyżej 120 s
    czekaj_na_brame(inst)
    r = inst.jarvo_cmd("doctor", "--json", czas=300)
    d = json_z_wyjscia(r.out)
    if d is not None:
        zapisz_json(art / "doctor.json", d)
    else:
        (art / "doctor.txt").write_text(bez_sekretow(r.tekst), encoding="utf-8")
    zielony, problemy, uzyte = ocen_doctora(d, dopusc)
    ok_n = sum(1 for w in (d or {}).get("wyniki", []) if w.get("stan") == "ok") if isinstance(d, dict) else 0
    opis = (f"{ok_n} ok" + (f", dopuszczone: " + "; ".join(f"{x['nazwa']} ({x['stan']}: {x['powod']})"
                                                             for x in uzyte) if uzyte else "")
            + (f"; problemy: " + "; ".join(f"{x['nazwa']} [{x['stan']}] {x.get('opis') or ''}" for x in problemy)
               if problemy else ""))
    rap.punkt("doctor", "jarvo doctor --json zielony", zielony, opis, kod=r.kod, problemy=problemy or None,
              dopuszczone=uzyte or None)
    s = _status(inst, rap, art, "status", "jarvo status: serwis i panel działają po instalacji")
    if s is not None and not (s.get("serwis") or {}).get("dziala") and s.get("zainstalowane") and not tylko_odczyt:
        # serwis padł po kroku instalacji (albo go nie podniesiono): to już błąd wyżej; `jarvo up` daje szansę
        # sprawdzić resztę (czat, zgody, kanban), zamiast kończyć test na pierwszym punkcie
        r = inst.jarvo_cmd("up", czas=420)
        rap.punkt("jarvo-up", "jarvo up podnosi serwis", r.kod == 0, f"kod {r.kod}, {r.sekundy:.0f} s: "
                  + skrot(r.tekst, 300))
        s = _status(inst, rap, art, "status-po-up", "jarvo status po jarvo up") or s
    sprawdz_panel(inst, adres_panelu(inst, s), rap)
    agenci = aktywni_agenci(inst.app / "fleet.yaml")
    brak = [n for n in agenci if not (inst.u.dane / "profiles" / n).is_dir()]
    wtyczki = sorted(p.name for p in (inst.u.dane / "plugins").iterdir()
                     if p.is_dir()) if (inst.u.dane / "plugins").is_dir() else []
    rap.punkt("flota", "flota zainstalowana (profile z fleet.yaml)", bool(agenci) and not brak,
              f"{len(agenci) - len(brak)}/{len(agenci)} profili" + (f", brak: {', '.join(brak)}" if brak else "")
              + f"; wtyczki w <dane>/plugins: {', '.join(wtyczki) or 'brak'}")
    return s if isinstance(s, dict) else {}


def _test_czatu_i_floty(inst: Instalacja, rap: Raport, art: Path, czas_karty: float) -> None:
    atrapa = Atrapa(art / "atrapa.jsonl")
    projekt = Path(tempfile.mkdtemp(prefix="jarvo-e2e-projekt-"))
    klucz_czat, klucz_spec = secrets.token_hex(32), secrets.token_hex(32)
    zgody_dir = inst.u.jarvo_dane / "workspaces" / "test-e2e"
    brama = Brama(inst.port_api())
    karty: list[str] = []
    try:
        try:
            utworz_profil(inst, PROFIL_CZAT, {"provider": "custom", "base_url": atrapa.adres(PROFIL_CZAT),
                                              "default": "atrapa"},
                          env={"API_SERVER_KEY": klucz_czat}, zgody=True, toolsety=["file"])
            utworz_profil(inst, PROFIL_SPEC, {"provider": "custom", "base_url": atrapa.adres(PROFIL_SPEC),
                                              "default": "atrapa"},
                          env={"API_SERVER_KEY": klucz_spec}, toolsety=["file"])
        except BladE2E as e:
            rap.punkt("profile-testowe", "profile testowe na atrapie modelu", False, str(e))
            return
        # Hermes trzyma menedżera wtyczek dla każdego katalogu profilu i wypełnia go, gdy działająca brama zobaczy
        # nowy profil (zaraz po `hermes profile create`, zanim dojdzie wtyczka i config): bez restartu profil nie ma
        # jarvo-zgody i zapis przechodzi bez pytania (CI natywnie 14822a9). Flota tak samo: instalator restartuje
        # bramę po zmianach profili (install_fleet: restart_bramy), więc test robi to samo (ryzyko Z39).
        przed = stan_bramy(inst).get("pid")
        r = inst.jarvo_cmd("serwis", "--restart", "brama", czas=180)
        po = czekaj_na_brame(inst, inny_pid=przed) if r.kod == 0 else {}
        ok = r.kod == 0 and bool(po.get("gotowa")) and po.get("pid") != przed
        rap.punkt("profile-testowe", "profile testowe na atrapie modelu", ok,
                  f"{PROFIL_CZAT} (wtyczka {WTYCZKA_ZGOD}, tryb pytaj), {PROFIL_SPEC}; atrapa na "
                  f"127.0.0.1:{atrapa.port}; restart bramy: kod {r.kod}, "
                  + (f"nowa brama gotowa (pid {po.get('pid')})" if ok else
                     f"brama niegotowa: {json.dumps(po, ensure_ascii=False)[:200]} {skrot(r.tekst, 200)}"))
        if not ok:
            return

        # 1. jarvo chat -q: launcher (jarvo.cmd albo ~/.local/bin/jarvo) → Hermes → atrapa
        znak = "e2e-" + secrets.token_hex(4)
        r = inst.jarvo_cmd("chat", "--profil", PROFIL_CZAT, "--tryb", "projekt", "-q",
                           f"Cześć, tu test e2e {znak}", czas=300, cwd=projekt)
        (art / "czat-cli.txt").write_text(bez_sekretow(bez_ansi(r.tekst)), encoding="utf-8")
        trafila = any(znak in json.dumps(z, ensure_ascii=False) for z in atrapa.zapytania(PROFIL_CZAT))
        # `chat -q` bez -Q powtarza pytanie („Query: …”), więc liczy się wiersz odpowiedzi atrapy ze znacznikiem
        odpowiedzi = [w for w in bez_ansi(r.out).splitlines() if "Atrapa (" in w and znak in w]
        polskie = any("Cześć" in w for w in odpowiedzi)   # strona kodowa i -X utf8 w drodze jarvo → Hermes → ekran
        ok = r.kod == 0 and bool(odpowiedzi) and trafila and polskie
        rap.punkt("czat-cli", "jarvo chat -q: odpowiedź atrapy", ok,
                  f"kod {r.kod}, {r.sekundy:.0f} s, zapytanie do atrapy {'jest' if trafila else 'BRAK'}, odpowiedź "
                  f"{'jest' if odpowiedzi else 'BRAK'}, polskie znaki {'wróciły' if polskie else 'zgubione'}"
                  + ("" if ok else f": {skrot(r.tekst, 400)}"))

        # 2. API bramy (tak rozmawia panel HQ): odpowiedź, prośba o zgodę z wtyczki zgód, zgoda „raz”, odmowa
        gotowa, opis = brama.gotowa(PROFIL_CZAT, klucz_czat)
        rap.punkt("brama", "brama obsługuje nowy profil (/v1/capabilities)", gotowa, opis)
        if gotowa:
            znak = "e2e-" + secrets.token_hex(4)
            try:
                w = brama.przebieg(PROFIL_CZAT, klucz_czat, f"Odpowiedz krótko {znak}")
                rap.punkt("czat-api", "/v1/runs: odpowiedź atrapy", w["status"] == "completed" and znak in w["output"],
                          f"{w['status']}: {skrot(w['output'], 200)}" + (f" ({w['error']})" if w.get("error") else ""))
            except BladE2E as e:
                rap.punkt("czat-api", "/v1/runs: odpowiedź atrapy", False, str(e))
            zgody_dir.mkdir(parents=True, exist_ok=True)
            for wybor, ident, nazwa in (("once", "zgoda", "prośba o zgodę i zgoda „raz”: plik zapisany"),
                                        ("deny", "odmowa", "prośba o zgodę i odmowa: pliku nie ma")):
                cel = zgody_dir / f"{ident}-{secrets.token_hex(3)}.txt"
                tresc = f"{ident} {secrets.token_hex(4)}"
                polecenie = ("[narzedzie:write_file " + json.dumps({"path": cel.as_posix(), "content": tresc},
                                                                   ensure_ascii=False) + "]")
                try:
                    w = brama.przebieg(PROFIL_CZAT, klucz_czat, polecenie, zgoda=wybor)
                except BladE2E as e:
                    rap.punkt(f"zgody-{ident}", nazwa, False, str(e))
                    continue
                jest = cel.is_file() and czytaj_tekst(cel).strip() == tresc
                ok = (w["status"] == "completed" and len(w["prosby"]) >= 1
                      and (jest if wybor == "once" else not cel.exists()))
                rap.punkt(f"zgody-{ident}", nazwa, ok,
                          f"{w['status']}, próśb {len(w['prosby'])}"
                          + (f" ({w['prosby'][0]['opis']})" if w["prosby"] else " (wtyczka nie zapytała)")
                          + f", plik {'jest' if cel.exists() else 'nie istnieje'}"
                          + (f"; odpowiedź: {skrot(w['output'], 160)}" if not ok else ""),
                          prosby=w["prosby"] or None)
        else:
            for ident, nazwa in (("czat-api", "/v1/runs: odpowiedź atrapy"),
                                 ("zgody-zgoda", "prośba o zgodę i zgoda „raz”: plik zapisany"),
                                 ("zgody-odmowa", "prośba o zgodę i odmowa: pliku nie ma")):
                rap.punkt(ident, nazwa, False, f"brama niegotowa: {opis}")

        # 3. zlecenie specjaliście: karta kanbana → dyspozytor bramy → pracownik `-p test-e2e-spec` na atrapie
        znak = "e2e-" + secrets.token_hex(4)
        inst.hermes("kanban", "init", czas=180)          # tablica jest po instalacji floty; init nic wtedy nie zmienia
        r = inst.hermes("kanban", "create", f"Test e2e: zlecenie {znak}", "--assignee", PROFIL_SPEC,
                        "--body", "Karta testu instalacji natywnej (tests/live/natywnie_e2e.py).",
                        "--max-retries", "1", "--idempotency-key", znak, "--json", czas=180)
        karta = json_z_wyjscia(r.out)
        ident = str((karta or {}).get("id") or "") if isinstance(karta, dict) else ""
        if not ident:
            rap.punkt("kanban", "zlecenie specjaliście: karta kanbana zrobiona", False,
                      f"hermes kanban create: kod {r.kod}: {skrot(r.tekst, 400)}")
        else:
            karty.append(ident)
            d = czekaj_na_karte(inst, ident, czas_karty)
            zadanie = d.get("task") if isinstance(d.get("task"), dict) else {}
            zapisz_json(art / f"kanban-{ident}.json", json.loads(bez_sekretow(json.dumps(d, ensure_ascii=False))))
            log = log_pracownika(inst, ident)
            tekst_logu = czytaj_tekst(log, MAKS_LOGU) if log else ""
            bez_czl = bool(BEZ_CZLOWIEKA.search(tekst_logu))
            u_atrapy = any(f"work kanban task {ident}" in json.dumps(z, ensure_ascii=False)
                           for z in atrapa.zapytania(PROFIL_SPEC))
            ok = zadanie.get("status") == "done" and u_atrapy and not bez_czl
            bledy_przebiegow = [skrot(str(x.get("error") or x.get("outcome") or ""), 200)
                                for x in (d.get("runs") or []) if isinstance(x, dict)
                                and (x.get("error") or x.get("outcome") not in (None, "", "completed", "done"))]
            rap.punkt("kanban", "zlecenie specjaliście: karta kanbana zrobiona", ok,
                      f"karta {ident}: {zadanie.get('status') or 'brak stanu'}, pracownik u atrapy "
                      f"{'był' if u_atrapy else 'NIE był'}, log pracownika {'jest' if log else 'brak'}"
                      + (", w logu „runs without a user present”" if bez_czl else "")
                      + (f"; przebiegi: {' | '.join(bledy_przebiegow)}" if bledy_przebiegow and not ok else "")
                      + (f"; podsumowanie: {skrot(str(d.get('latest_summary') or ''), 160)}" if ok else ""))
    finally:
        if karty:                                   # dyspozytor nie będzie ponawiał karty profilu, który zaraz znika
            inst.hermes("kanban", "archive", *karty, czas=120)
        reszta = [x for x in (usun_profil(inst, p) for p in (PROFIL_CZAT, PROFIL_SPEC)) if x]
        uwaga = ""
        if reszta and WINDOWS:
            # brama, która obsłużyła przebieg profilu, trzyma jego logs/.__agent.lock (Hermes kieruje logi do profili
            # i zwalnia je tylko we własnym procesie); Windows nie usunie otwartego pliku, więc usuwamy przy
            # zatrzymanym serwisie, jak zrobiłby to właściciel
            inst.jarvo_cmd("down", czas=180)
            reszta = [x for x in (usun_profil(inst, p) for p in (PROFIL_CZAT, PROFIL_SPEC)) if x]
            r = inst.jarvo_cmd("up", czas=300)
            uwaga = f" (przy zatrzymanym serwisie: brama trzymała logi profilu; jarvo up: kod {r.kod})"
            if r.kod != 0:
                reszta.append(f"jarvo up po sprzątaniu: kod {r.kod}: {skrot(r.tekst, 200)}")
        shutil.rmtree(zgody_dir, ignore_errors=True)
        shutil.rmtree(projekt, ignore_errors=True)
        atrapa.zamknij()
        rap.punkt("sprzatanie", "profile testowe usunięte", not reszta,
                  "; ".join(reszta) or f"{PROFIL_CZAT} i {PROFIL_SPEC} usunięte (hermes profile delete){uwaga}")


def polecenie_sprawdz(a) -> int:
    art = katalog_artefaktow(a.artefakty)
    rap = Raport(art)
    inst = Instalacja(a.korzen, a.jarvo)
    if inst.jarvo is None:
        rap.punkt("instalacja", "polecenie jarvo jest", False,
                  f"brak polecenia jarvo dla {inst.u.root} (instalacja się nie udała? zobacz log instalacji)")
        return 1
    rap.punkt("instalacja", "polecenie jarvo jest", True, f"{inst.jarvo} (korzeń {inst.u.root})")
    _doctor_status_panel(inst, rap, art, parsuj_dopusc(a.dopusc), a.tylko_odczyt)
    if not a.tylko_odczyt:
        _test_czatu_i_floty(inst, rap, art, a.czas_karty)
    return 1 if rap.bledy else 0


def polecenie_drugi_przebieg(a) -> int:
    rap = Raport(katalog_artefaktow(a.artefakty))
    try:
        tekst = bez_ansi(czytaj_tekst(Path(a.log)))
    except OSError as e:
        rap.punkt("drugi-przebieg", "drugi przebieg instalatora niczego nie zmienia", False, f"brak logu: {e}")
        return 1
    zmiany = [w.strip() for w in tekst.splitlines() if "Zmiany w tym przebiegu:" in w]
    pobrane = [w.strip() for w in tekst.splitlines() if re.search(r"\bpobieram\b", w, re.I)]
    gotowe = bool(re.search(r"\[jarvo\] Gotowe\.", tekst))
    bledy = [w.strip() for w in tekst.splitlines() if re.search(r"\bBŁĄD\b|^JARVO:", w.strip())]
    ok = bool(zmiany) and ZMIANY_BRAK in zmiany[-1] and not pobrane and gotowe and not bledy
    opis = ((zmiany[-1] if zmiany else "brak wiersza „Zmiany w tym przebiegu”")
            + (f"; pobrane ponownie: {' | '.join(pobrane[:5])}" if pobrane else "")
            + ("" if gotowe else "; bez „[jarvo] Gotowe.” na końcu")
            + (f"; błędy: {' | '.join(bledy[:3])}" if bledy else ""))
    rap.punkt("drugi-przebieg", "drugi przebieg instalatora niczego nie zmienia", ok, opis)
    return 0 if ok else 1


def model_openrouter(inst: Instalacja, jawny: str | None) -> str:
    if jawny:
        return jawny
    with contextlib.suppress(BladE2E):
        m = inst.czytaj_yaml(inst.app / "fleet.yaml", "models.presets.openrouter.fast")
        if isinstance(m, str) and m.strip():
            return m.strip()
    return MODEL_OPENROUTER


def polecenie_prawdziwy_model(a) -> int:
    rap = Raport(katalog_artefaktow(a.artefakty))
    klucz = os.environ.get("JARVO_TEST_OPENROUTER_KEY") or ""
    nazwa = "prawdziwy model (OpenRouter): jedna tura jarvo chat"
    if len(klucz) < 8:
        rap.punkt("prawdziwy-model", nazwa, None, "brak sekretu JARVO_TEST_OPENROUTER_KEY")
        return 0
    inst = Instalacja(a.korzen, a.jarvo)
    model = model_openrouter(inst, a.model)
    projekt = Path(tempfile.mkdtemp(prefix="jarvo-e2e-model-"))
    try:
        utworz_profil(inst, PROFIL_OR, {"provider": "openrouter", "default": model},
                      env={"OPENROUTER_API_KEY": klucz})
        # -Q: na wyjściu sama odpowiedź modelu (id sesji i błędy idą na stderr), kod wyjścia mówi, czy tura przeszła
        r = inst.jarvo_cmd("chat", "--profil", PROFIL_OR, "--tryb", "projekt", "-Q", "-q",
                           "Odpowiedz jednym słowem po polsku: gotowe.", czas=300, cwd=projekt)
        tekst = bez_sekretow(bez_ansi(r.tekst), [klucz])
        (katalog_artefaktow(a.artefakty) / "prawdziwy-model.txt").write_text(tekst, encoding="utf-8")
        zle = re.search(r"\b(401|403|Unauthorized|invalid api key|No auth credentials)\b", tekst, re.I)
        ok = r.kod == 0 and bool(re.search(r"[A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,}", r.out)) and not zle
        rap.punkt("prawdziwy-model", nazwa, ok, f"model {model}, kod {r.kod}, {r.sekundy:.0f} s"
                  + ("" if ok else f": {skrot(tekst, 300)}"))
        return 0 if ok else 1
    except BladE2E as e:
        rap.punkt("prawdziwy-model", nazwa, False, bez_sekretow(str(e), [klucz]))
        return 1
    finally:
        usun_profil(inst, PROFIL_OR)
        shutil.rmtree(projekt, ignore_errors=True)


def sekrety_instalacji(u: Uklad) -> dict[str, str]:
    """Wartości sekretów z plików .env instalacji ({wartość: nazwa}): <dane>/.env, profile i <dane>/jarvo/konfig."""
    pliki = [u.dane / ".env", *sorted((u.dane / "profiles").glob("*/.env")),
             *sorted((u.jarvo_dane / "konfig").glob("*.env"))]
    wynik: dict[str, str] = {}
    for p in pliki:
        for nazwa, wartosc in czytaj_env(p).items():
            if SEKRET_NAZWA.search(nazwa) and len(wartosc) >= 8 and "<" not in wartosc:
                wynik[wartosc] = nazwa
    for nazwa in ZMIENNE_SEKRETOW:
        w = os.environ.get(nazwa) or ""
        if len(w) >= 8:
            wynik[w] = nazwa
    return wynik


def polecenie_zbierz_logi(a) -> int:
    art = katalog_artefaktow(a.artefakty)
    rap = Raport(art)
    inst = Instalacja(a.korzen, a.jarvo)
    u = inst.u
    cel = art / "logi"
    sekrety = sekrety_instalacji(u)
    zrodla: list[tuple[Path, str]] = []
    for p in sorted(u.logi.glob("*.log*")) if u.logi.is_dir() else []:
        zrodla.append((p, f"jarvo/{p.name}"))
    logi_hermesa = u.dane / "logs"
    if logi_hermesa.is_dir():
        zrodla += [(p, f"hermes/{p.relative_to(logi_hermesa).as_posix()}") for p in sorted(logi_hermesa.rglob("*"))
                   if p.is_file() and (p.suffix == ".log" or ".log." in p.name)]
    if (u.dane / "kanban").is_dir():
        zrodla += [(p, f"kanban/{p.relative_to(u.dane / 'kanban').as_posix()}")
                   for p in sorted((u.dane / "kanban").rglob("*.log"))]
    for p in (u.stan / "nadzorca.json", u.stan / "narzedzia.json", u.stan / "flota.json", u.stan / "ustawienia.json",
              u.stan / "srodowisko.json", u.stan / "zmiany-hosta.jsonl", u.program / "current.json"):
        if p.is_file():
            zrodla.append((p, f"stan/{p.name}"))
    trafienia: dict[str, int] = {}
    for p, nazwa in zrodla:
        try:
            tekst = czytaj_tekst(p, MAKS_LOGU)
        except OSError:
            continue
        n = 0
        for wartosc, zmienna in sorted(sekrety.items(), key=lambda x: len(x[0]), reverse=True):
            if wartosc in tekst:
                n += tekst.count(wartosc)
                tekst = tekst.replace(wartosc, f"<ukryty:{zmienna}>")
        if n:
            trafienia[nazwa] = n
        docelowy = cel / nazwa
        docelowy.parent.mkdir(parents=True, exist_ok=True)
        docelowy.write_text(tekst, encoding="utf-8")
    skroty = sorted({hashlib.sha256(w.encode("utf-8")).hexdigest() for w in sekrety})
    zapisz_json(plik_sekretow(art), {"sha256": skroty, "opis": "skróty sekretów instalacji dla skanu artefaktów"})
    rap.punkt("logi", "logi zebrane, bez znanych sekretów", not trafienia,
              f"{len(zrodla)} plików do {cel.name}/"
              + (f"; znane sekrety (zamaskowane): " + ", ".join(f"{k} ×{v}" for k, v in trafienia.items())
                 if trafienia else ""))
    return 1 if trafienia else 0


def procesy_jarva(u: Uklad) -> list[str]:
    """Procesy, których program albo wiersz polecenia leży w korzeniu Jarva (oprócz tego procesu)."""
    korzen = str(u.root).lower()
    wynik = []
    if WINDOWS:
        ps = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / "WindowsPowerShell" / "v1.0" / \
            "powershell.exe"
        r = uruchom([ps, "-NoProfile", "-NonInteractive", "-Command",
                     "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-CimInstance Win32_Process | "
                     "Select-Object ProcessId,Name,ExecutablePath,CommandLine | ConvertTo-Json -Compress"],
                    czas=120, bez_okna=True)
        dane: Any = None
        with contextlib.suppress(ValueError):
            dane = json.loads(r.out.lstrip("\ufeff").strip() or "[]")
        for p in dane if isinstance(dane, list) else [dane] if isinstance(dane, dict) else []:
            linia = f"{p.get('ExecutablePath') or ''} {p.get('CommandLine') or ''}"
            if korzen in linia.lower() and p.get("ProcessId") != os.getpid():
                wynik.append(f"{p.get('ProcessId')} {p.get('Name')}")
    else:
        r = uruchom(["ps", "-axww", "-o", "pid=,command="], czas=60)
        for linia in r.out.splitlines():
            pid, _, polecenie = linia.strip().partition(" ")
            if (korzen in polecenie.lower() if MACOS else str(u.root) in polecenie) and pid != str(os.getpid()):
                wynik.append(f"{pid} {polecenie[:160]}")
    return wynik


def polecenie_odinstaluj(a) -> int:
    art = katalog_artefaktow(a.artefakty)
    rap = Raport(art)
    inst = Instalacja(a.korzen, a.jarvo)
    u, cmd = inst.u, inst.jarvo
    porty = [inst.port_panelu(), inst.port_api(), 9120, 9122]
    r = inst.jarvo_cmd("uninstall", "--all", "--yes", czas=900)
    (art / "odinstalowanie.log").write_text(bez_sekretow(bez_ansi(r.tekst)), encoding="utf-8")
    w_budowie = r.kod == 2 and "w budowie" in r.tekst
    rap.punkt("uninstall", "jarvo uninstall --all --yes", r.kod == 0,
              ("polecenie jest jeszcze w budowie (etap E13): " if w_budowie else f"kod {r.kod}, {r.sekundy:.0f} s: ")
              + skrot(r.tekst, 400))
    koniec = time.monotonic() + 90
    zostaly, sluchaja = procesy_jarva(u), [p for p in porty if port_slucha(p)]
    while (zostaly or sluchaja) and time.monotonic() < koniec:
        time.sleep(3)
        zostaly, sluchaja = procesy_jarva(u), [p for p in porty if port_slucha(p)]
    rap.punkt("uninstall-procesy", "po odinstalowaniu: bez procesów Jarva i bez nasłuchu na portach", not zostaly
              and not sluchaja, ("procesy: " + "; ".join(zostaly[:8]) if zostaly else "procesów brak")
              + (f"; słuchają porty {sluchaja}" if sluchaja else f"; porty {porty} wolne"))
    reszta = [str(p) for p in (u.root, u.logi, u.cache) if p.exists()]
    if cmd is not None and cmd.exists():
        reszta.append(str(cmd))
    rap.punkt("uninstall-pliki", "po odinstalowaniu: korzeń, logi, cache i polecenie jarvo usunięte", not reszta,
              "zostały: " + ", ".join(reszta) if reszta else "nic nie zostało")
    return 1 if rap.bledy else 0


def skanuj_plik(p: Path, skroty: set[str], wartosci: list[str]) -> list[dict]:
    """Trafienia w jednym pliku: [{"rodzaj", "linia"}] (bez treści sekretu). Plik binarny (NUL w pierwszych 8 KB
    bez BOM UTF-16) pomijamy: zrzutów ekranu nie da się sprawdzić tekstowo."""
    try:
        with open(p, "rb") as f:
            poczatek = f.read(8192)
    except OSError:
        return []
    if b"\x00" in poczatek and poczatek[:2] not in (b"\xff\xfe", b"\xfe\xff"):
        return []
    tekst = czytaj_tekst(p)
    trafienia = []
    for nr, linia in enumerate(tekst.splitlines(), 1):
        for nazwa, wzor in WZORY_SEKRETOW:
            for m in wzor.finditer(linia):
                if m.groups() and m.group(1) and not _wyglada_na_sekret(m.group(1)):
                    continue
                trafienia.append({"rodzaj": nazwa, "linia": nr})
        for w in wartosci:
            if w and w in linia:
                trafienia.append({"rodzaj": "wartość sekretu z otoczenia", "linia": nr})
        if skroty:
            kandydaci = {k for wzor in KANDYDAT_SEKRETU for k in wzor.findall(linia)}
            if any(hashlib.sha256(k.encode("utf-8")).hexdigest() in skroty for k in kandydaci):
                trafienia.append({"rodzaj": "znany sekret instalacji (skrót)", "linia": nr})
    return trafienia


def polecenie_skan(a) -> int:
    katalog = Path(a.katalog)
    katalog.mkdir(parents=True, exist_ok=True)
    dane_skrotow = wczytaj_json(plik_sekretow(katalog)) or {}
    skroty = set(dane_skrotow.get("sha256") or []) if isinstance(dane_skrotow, dict) else set()
    wartosci = _wartosci_z_otoczenia(a.z_otoczenia or ZMIENNE_SEKRETOW)
    raport = {"czas": teraz(), "plikow": 0, "trafienia": [], "usuniete": []}
    for p in sorted(x for x in katalog.rglob("*") if x.is_file()):
        if p.name == "skan.json" or p.name.endswith(".usuniety.txt"):
            continue
        raport["plikow"] += 1
        trafienia = skanuj_plik(p, skroty, wartosci)
        if not trafienia:
            continue
        rel = p.relative_to(katalog).as_posix()
        rodzaje = sorted({t["rodzaj"] for t in trafienia})
        linie = sorted({t["linia"] for t in trafienia})[:20]
        p.unlink()
        p.with_name(p.name + ".usuniety.txt").write_text(
            f"Plik {rel} usunięty przed wysyłką: skan sekretów znalazł {len(trafienia)} trafień ({', '.join(rodzaje)}) "
            f"w liniach {linie}. Treść sekretu nie trafia do artefaktów.\n", encoding="utf-8")
        raport["trafienia"].append({"plik": rel, "rodzaje": rodzaje, "linie": linie, "ile": len(trafienia)})
        raport["usuniete"].append(rel)
    zapisz_json(katalog / "skan.json", raport)
    wyjscie = os.environ.get("GITHUB_OUTPUT")
    if wyjscie:
        with open(wyjscie, "a", encoding="utf-8") as f:
            f.write("gotowe=tak\n")
    if raport["trafienia"]:
        print(f"[BŁĄD]    skan sekretów: {len(raport['trafienia'])} plików z trafieniem usunięto z artefaktów: "
              + ", ".join(raport["usuniete"][:10]))
        return 1
    print(f"[ok]      skan sekretów: {raport['plikow']} plików bez trafień")
    return 0


def polecenie_podsumowanie(a) -> int:
    art = katalog_artefaktow(a.artefakty)
    rap = Raport(art)
    znak = {True: "ok", False: "**BŁĄD**", None: "pominięte"}
    w = [f"### Jarvo natywnie: {rap.dane.get('noga')}", "", "| Wynik | Punkt | Opis |", "|---|---|---|"]
    for p in rap.dane["punkty"]:
        opis = str(p.get("opis") or "").replace("|", "\\|").replace("\n", " ")
        w.append(f"| {znak[p.get('ok')]} | {p.get('nazwa')} | {opis[:400]} |")
    r = wczytaj_json(art / "roznica.json")
    if isinstance(r, dict) and r.get("zmiany"):
        w += ["", f"Różnica migawek: {r.get('niewyjasnione')} bez wyjaśnienia, {r.get('wyjasnione')} wyjaśnionych.", ""]
        w += [f"- {z['rodzaj']} `{z['klucz']}`"
              + (f" ({z['wyjasnienie']})" if z["wyjasnienie"] else " **bez wyjaśnienia**") for z in r["zmiany"][:40]]
    s = wczytaj_json(art / "skan.json")
    if isinstance(s, dict):
        w += ["", f"Skan sekretów: {s.get('plikow')} plików, usunięte: {', '.join(s.get('usuniete') or []) or 'brak'}."]
    tekst = "\n".join(w) + "\n"
    cel = os.environ.get("GITHUB_STEP_SUMMARY")
    if cel:
        with open(cel, "a", encoding="utf-8") as f:
            f.write(tekst)
    else:
        print(tekst)
    return 0


# ---------------------------------------------------------------- wejście

def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="natywnie_e2e.py", description="Test instalacji natywnej Jarva na żywo "
                                "(docs/NATYWNIE.md T08, T14, T18): migawka, sprawdzenie, odinstalowanie, skan.")
    sub = p.add_subparsers(dest="polecenie", required=True, metavar="polecenie")

    def wspolne(s: argparse.ArgumentParser, *, korzen: bool = True) -> None:
        s.add_argument("--artefakty", help="katalog artefaktów (domyślnie $JARVO_E2E_ARTEFAKTY albo "
                       "$RUNNER_TEMP/natywnie-artefakty)")
        if korzen:
            s.add_argument("--korzen", help="korzeń instalacji (jak JARVO_ROOT; domyślnie korzeń systemu)")
            s.add_argument("--jarvo", help="ścieżka polecenia jarvo (domyślnie z instalacji)")

    s = sub.add_parser("migawka", help="stan komputera poza Jarvem (tylko odczyt)")
    s.add_argument("--wyjscie", required=True, help="plik JSON migawki")
    s.add_argument("--korzen", help="korzeń instalacji (jak JARVO_ROOT)")
    s.set_defaults(funkcja=polecenie_migawka)

    s = sub.add_parser("roznica", help="różnica migawek przed i po (pusta poza wyjątkami)")
    s.add_argument("przed")
    s.add_argument("po")
    s.add_argument("--wyjatek", action="append", default=[], type=parsuj_wyjatek, metavar="WZÓR[=kiedy]|POWÓD",
                   help="dodatkowy wyjątek różnicy (wzór klucza migawki; kiedy: dowolnie, pusty, zmieniony)")
    wspolne(s, korzen=False)
    s.set_defaults(funkcja=polecenie_roznica)

    s = sub.add_parser("sprawdz", help="doctor, status, panel, flota, czat, zgody i kanban na żywo")
    s.add_argument("--dopusc", action="append", default=[], metavar="NAZWA=stan[:powód]",
                   help="jawny wyjątek doctora (np. „autostart=uwaga:runner bez user busa”); kilka przez „;”")
    s.add_argument("--tylko-odczyt", action="store_true", help="bez profili testowych i atrapy (doctor, status, panel)")
    s.add_argument("--czas-karty", type=float, default=600.0, help="ile sekund czekać na kartę kanbana")
    wspolne(s)
    s.set_defaults(funkcja=polecenie_sprawdz)

    s = sub.add_parser("drugi-przebieg", help="log drugiego przebiegu instalacji: bez zmian")
    s.add_argument("log")
    wspolne(s, korzen=False)
    s.set_defaults(funkcja=polecenie_drugi_przebieg)

    s = sub.add_parser("prawdziwy-model", help="jedna tura z OpenRouter (klucz z JARVO_TEST_OPENROUTER_KEY)")
    s.add_argument("--model", help="model OpenRouter (domyślnie zestaw openrouter, tier fast z fleet.yaml)")
    wspolne(s)
    s.set_defaults(funkcja=polecenie_prawdziwy_model)

    s = sub.add_parser("zbierz-logi", help="logi i stan instalacji do artefaktów (przed odinstalowaniem)")
    wspolne(s)
    s.set_defaults(funkcja=polecenie_zbierz_logi)

    s = sub.add_parser("odinstaluj", help="jarvo uninstall --all --yes i sprawdzenie, że nic nie zostało")
    wspolne(s)
    s.set_defaults(funkcja=polecenie_odinstaluj)

    s = sub.add_parser("skan", help="sekrety w katalogu artefaktów (plik z trafieniem znika)")
    s.add_argument("katalog")
    s.add_argument("--z-otoczenia", action="append", metavar="ZMIENNA",
                   help=f"zmienna z sekretem do szukania wprost (domyślnie {', '.join(ZMIENNE_SEKRETOW)})")
    s.set_defaults(funkcja=polecenie_skan)

    s = sub.add_parser("podsumowanie", help="tabela wyników do $GITHUB_STEP_SUMMARY")
    wspolne(s, korzen=False)
    s.set_defaults(funkcja=polecenie_podsumowanie)
    return p


def main(argv: list[str] | None = None) -> int:
    for strumien in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            strumien.reconfigure(errors="replace")
    a = parser().parse_args(argv)
    try:
        return int(a.funkcja(a) or 0)
    except BladE2E as e:
        print(f"BŁĄD: {bez_sekretow(str(e))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
