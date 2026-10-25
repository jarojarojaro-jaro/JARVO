"""Migracja ze starej instalacji z Dockerem i WSL: `jarvo migruj` (docs/NATYWNIE.md: sekcja f, N14, I33, etap E12).

Jedno polecenie przenosi dane starej floty do instalacji natywnej i nic po drodze nie ginie (f1):
  1. wykrycie, tylko odczyt i bez startu WSL ani Dockera (f3 p.1, f4):
       Windows: Startup\\Jarvo.vbs, %LOCALAPPDATA%\\Jarvo\\bin\\jarvo.cmd wołający wsl.exe, dystrybucje
                z HKCU\\...\\Lxss, wpis RunOnce i .wslconfig od Jarva, kontenery jarvo-* w Docker Desktop (gdy
                działa); plik ~/jarvo-local/compose/.env w dystrybucji sprawdza dopiero start rozbrojenia (każdy start
                budzi flotę),
       macOS:   ~/jarvo-local/compose/.env (wolumen jarvo-hermes-data), Colima albo Docker Desktop, pl.jarvo.updater,
       Linux:   ~/jarvo-local z danymi uid 10000, kontenery jarvo-*, jarvo-updater (systemd --user), linger,
  2. raport i pytanie o zgodę przed każdą zmianą (`--tak`: zgoda na wszystko poza wyłączeniem Dockera w dystrybucji
     i lingera, które mają własne przełączniki),
  3. rozbrojenie starej floty, zanim cokolwiek skopiujemy: nigdy dwie floty naraz (jeden token Telegrama to jedna
     brama, a token odświeżania OpenAI jest jednorazowy). Windows W1–W4 bez startu WSL, potem jeden start dystrybucji
     jako root (U1–U5 w SKRYPT_ROZBROJENIA; bez ~/jarvo-local skrypt kończy się po inspekcji i niczego nie zmienia)
     i `wsl --terminate` (U6); Linux ten sam skrypt przez sudo; macOS i wolumeny: LaunchAgent albo jednostka w dół,
     `docker stop`, kopia, `docker compose -p jarvo down`. Klucz prywatnej kopii repo (f3 p.4) tylko wykrywamy:
     przeniesie go `jarvo klucz` (N15),
  4. kopia strumieniem tar (`wsl --export <dystrybucja> -`, `sudo tar`, `docker cp jarvo-hermes:/opt/data -`) do
     `tarfile` w trybie `r|` z filtrem f3 p.6 (bazy razem z -wal, .git skarbca, auth.json, .env, pairing, cron,
     memories, sessions; bez cache, node_modules, venvów, binarek Linuksa, stanu chwilowego, wtyczek i skórek floty).
     Kopia to jeden plik tar z sumą sha256 i spisem: to też kopia do wycofania. Nazwy niedozwolone w systemie
     docelowym i kolizje wielkości liter: raport i stop przed importem. Dane w wolumenie Dockera w WSL
     (JARVO_VOLUMES=1) eksport ma w katalogu Dockera, więc ta sama droga,
  5. próba na kopii bez sekretów (bez auth.json, .env, skarbców kluczy i innych poświadczeń: sekretny()) w
     `<katalog>/proba`: przepisanie ścieżek, integrity_check, liczby sesji, wiadomości, kart, wpisów i rutyn przed
     i po, polecenia Hermesa tylko do odczytu; potem katalog próby znika,
  6. import do `<dane>` (zatrzymany serwis natywny, natywne pliki o tych samych nazwach do `natywne-przed-importem`),
     przepisanie ścieżek (najdłuższy prefiks najpierw, tylko na granicy ścieżki) w bazach Hermesa i HQ w ich miejscach
     (baza_hermesa: transakcja, integrity_check przed i po, wal_checkpoint(TRUNCATE); tabeli messages nie ruszamy;
     tylko na SQLite 3.51.3+, Z14) i w plikach (.env, distribution.yaml, cron/jobs.json, board.json), sekrety przez
     scalenie (jak merge_env.py) do `<dane>/jarvo/konfig`, rutyny wstrzymane do próbnej wiadomości na Telegram (I36),
     manifest po imporcie zgodny ze spisem kopii, raport resztek „/opt/” (same liczby), bezpieczne ustawienia Hermesa
     (I13) i indeks skarbca,
  7. unieszkodliwienie starych logowań: auth.json i .env w starej kopii dostają nazwę `*.przeniesione-<data>`,
  8. kontrola przed startem (stara dystrybucja nie działa, porty Jarva wolne, żaden kontener jarvo-* nie działa),
  9. odtworzenie floty (build i install_fleet: config.yaml, SOUL i skille, f3 p.8) i pierwszy start z `jarvo doctor`.
`--wycofaj` (f3 p.12: natywna flota stoi, stara wraca), `--sprzatanie` (f3 p.13: tylko za zgodą, po okresie
przejściowym), `--wznow-rutyny`, `--tylko-wykryj`, `--manifest` i `--porownaj` (test migracji w CI, f5).

Stan: `<stan>/migracja.json` (etapy, źródło, kopia z sumą, wstrzymane rutyny), dziennik zmian `<stan>/migracja.jsonl`
(do wycofania, bez sekretów), log `<logi>/migracja.log`. Przerwana migracja rusza od pierwszego niezrobionego etapu,
a zakończona przy drugim przebiegu niczego nie zmienia. Wszystko, co dotyka WSL, Dockera, sudo, rejestru, procesów
i Harmonogramu, idzie przez SystemMigracji, a instalacja natywna przez Natywne: testy (tests/test_migracja.py)
podstawiają atrapy i żadnego z tych programów nie uruchamiają.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime
import hashlib
import io
import json
import os
import posixpath
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, BinaryIO, Callable, Iterable, Iterator

from . import przenosne, sciezki, srodowisko
from .sciezki import MACOS, WINDOWS, Uklad

WERSJA = 1
PLIK_STANU = "migracja.json"            # <stan>/migracja.json
PLIK_DZIENNIKA = "migracja.jsonl"       # <stan>/migracja.jsonl: każda zmiana poza <dane> (do wycofania)
PLIK_LOGU = "migracja.log"              # <logi>/migracja.log
KATALOG = "migracja"                    # <root>/migracja: kopia, kopie zapasowe, raport (zmienia --katalog)
OKRES_PRZEJSCIOWY_DNI = 14              # sprzątanie starej instalacji najwcześniej po tylu dniach od importu
MIN_WOLNE_GB = 2.0
POWOD_ZATRZYMANIA = "migracja z Dockera (jarvo migruj)"
POWOD_RUTYN = "jarvo migruj: wstrzymane do próbnej wiadomości na Telegram (I36)"
ZNACZNIK_NATYWNY = "Jarvo natywnie (jarvo instaluj)"      # jak instalator.ZNACZNIK: jarvo.cmd jest już nasz
KONTENER = "jarvo-hermes"
WOLUMEN = "jarvo-hermes-data"
OBRAZ = "jarvo-hermes:local"
STARE_OBRAZY = ("jarvo-hermes:local", "tars-hermes:local")
PROJEKT = "jarvo"                       # docker compose -p jarvo (name: jarvo w infra/docker-compose.yml)
AGENT_MACOS = "pl.jarvo.updater"
JEDNOSTKA = "jarvo-updater.service"
LXSS = r"Software\Microsoft\Windows\CurrentVersion\Lxss"
RUNONCE = r"Software\Microsoft\Windows\CurrentVersion\RunOnce"
WPIS_RUNONCE = "JarvoInstall"
DYSTRYBUCJE_DOCKERA = ("docker-desktop", "docker-desktop-data")
RESZTKI_STAREGO = ("install.ps1", "install.ps1.new", "install.sh", "token.dat", "przygotuj.sh", "SHA256SUMS",
                   "po-restarcie")
NATYWNE_ZOSTAJA = frozenset({"install_id"})   # identyfikator tej instalacji: panel rozpoznaje po nim swój port
PORTY = (8642, 9120, 9122)              # + port panelu (JARVO_PANEL_PORT, domyślnie 9119)
ZNACZNIK_WYNIKU = "JARVO|"
CZAS_HERMESA = 180.0
# bazy w WAL tylko na SQLite bez błędu WAL-reset (Z14; jak cli.SQLITE_MIN i hermes_cli/doctor_platform.py w f97608f)
SQLITE_MIN = (3, 51, 3)
NAGLOWEK_SQLITE = b"SQLite format 3\x00"

# --- filtr kopii (f3 p.6; zasady katalogów Hermesa jak w hermes_cli/backup.py w f97608f) ---------------------------
# gateway.sock to gniazdo sterujące bramy (POSIX, gateway/control_socket.py), a gateway.sock.path wskazanie na gniazdo
# w katalogu tymczasowym starego systemu: stan chwilowy jak gateway.pid
POMIJANE_PLIKI = frozenset({"gateway_state.json", "gateway.pid", "cron.pid", "gateway.lock", "processes.json",
                            "gateway.sock", "gateway.sock.path"})
# na każdej głębokości: cache narzędzi, zależności i venvy (linuksowe binarki, odtwarzalne)
POMIJANE_KATALOGI = frozenset({"lazy-packages", "node_modules", "__pycache__", ".npm", ".cache", ".venv", "venv",
                               "site-packages", ".tox", ".nox", ".pytest_cache", ".mypy_cache", ".ruff_cache"})
# tylko w korzeniu <dane> i w profiles/<profil>/: binarki i środowiska Linuksa, piaskownice, skórki floty (odtwarza
# build), build, profile przeglądarek (Chromium z Linuksa: ciasteczka szyfrowane kluczem tamtego systemu)
POMIJANE_W_KORZENIU = frozenset({"bin", "runtime", "runtimes", "node", "sandboxes", "skins", "build",
                                 "browser-profiles", "browser-profile", "browser_profiles"})
CACHE_ZOSTAJE = frozenset({"images", "audio", "videos", "documents", "screenshots", "citations"})
STAN_CHWILOWY = re.compile(r"(update|praca|preview[^/]*)\.json")      # <dane>/jarvo/state/
INDEKS_SKARBCA = ("wiedza.db", "wiedza.db-wal", "wiedza.db-shm", "wiedza.db-journal")   # odtwarza indeksuj --pelny
# drzewa właściciela: tu *.lock to pliki projektów (uv.lock, Cargo.lock), nie blokady procesów
DRZEWA_WLASCICIELA = ("jarvo/workspaces", "jarvo/missions", "jarvo/inbox", "jarvo/knowledge", "kanban/workspaces",
                      "kanban/attachments", "home")
SEKRETNE = frozenset({".env", "auth.json", "vault.key", "vault.json.enc"})
# inne logowania i klucze (katalogi domowe agentów `<profil>/home`, terminal agenta): nie ma ich w próbie (f3 p.7),
# a po imporcie są tylko dla właściciela; nowej nazwy w starej kopii nie dostają (nie są jednorazowe jak token OpenAI)
SEKRETNE_INNE = frozenset({".git-credentials", ".netrc", ".npmrc", ".pypirc"})
SEKRETNE_KATALOGI = frozenset({".ssh", ".gnupg"})
SEKRETNE_SCIEZKI = (".config/gh/hosts.yml", ".docker/config.json")
SIDECARY = ("-wal", "-shm", "-journal")
BOCZNE_BAZ = tuple(f".db{s}" for s in SIDECARY)
# --- przepisanie ścieżek w SQLite (f3 p.8): kolumny, w których cała wartość jest ścieżką ---------------------------
KOLUMNY_SCIEZEK: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "state.db": (("sessions", ("cwd", "git_repo_root")),),
    "kanban.db": (("tasks", ("workspace_path",)), ("task_attachments", ("stored_path",))),
    "projects.db": (("projects", ("primary_path",)), ("project_folders", ("path",)), ("discovered_repos", ("root",))),
}
KOLUMNY_JSON: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "rozmowy.db": (("wpisy", ("zalaczniki", "obrazy")), ("przekazy", ("pliki",))),
}
DUPLIKATY_USUWAMY = frozenset({"project_folders", "discovered_repos"})   # dwie stare nazwy tej samej ścieżki
_ZLE_NTFS = frozenset('<>:"|?*\\') | frozenset(chr(i) for i in range(32))
_ZASTRZEZONE = frozenset({"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in "123456789"),
                          *(f"LPT{i}" for i in "123456789")})
_LINIA_ENV = re.compile(r"^(?P<przed>\s*(?:export\s+)?(?P<klucz>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*)(?P<w>.*?)(?P<po>\s*)$")
_LINIA_YAML = re.compile(r"^(?P<przed>\s*(?:-\s+)?(?:[A-Za-z0-9_.\-]+:\s+)?)(?P<w>(?:\"[^\"]*\"|'[^']*'|[^#\s][^#]*?))"
                         r"(?P<po>\s*(?:#.*)?)$")
_PROFIL = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
_FLAGI = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class BladMigracji(RuntimeError):
    """Krok migracji się nie udał (komunikat po polsku z radą, bez sekretów). Dane starej instalacji są nietknięte."""


class Odmowa(RuntimeError):
    """Właściciel nie zgodził się na krok, bez którego migracja nie pójdzie dalej."""


def _teraz_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _sha_pliku(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for porcja in iter(lambda: f.read(1 << 20), b""):
            h.update(porcja)
    return h.hexdigest()


def _json(dane: Any) -> str:
    return json.dumps(dane, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# ================================================================ filtr kopii i nazwy

def _drzewo_wlasciciela(czesci: list[str]) -> bool:
    if czesci[:1] == ["profiles"] and len(czesci) > 2:
        czesci = czesci[2:]
    tekst = "/".join(czesci)
    if any(tekst == d or tekst.startswith(d + "/") for d in DRZEWA_WLASCICIELA):
        return True
    return czesci[:2] == ["kanban", "boards"] and len(czesci) > 3 and czesci[3] in ("workspaces", "attachments")


def pomin(rel: str, katalog: bool = False) -> str | None:
    """Powód pominięcia ścieżki `rel` (z „/”, względem katalogu danych Hermesa) w kopii albo None, gdy zostaje (f3 p.6).
    `katalog=True` dla samego katalogu (pominięty katalog to pominięta cała jego zawartość)."""
    czesci = [c for c in rel.split("/") if c]
    if not czesci:
        return None
    nazwa = czesci[-1]
    for c in (czesci if katalog else czesci[:-1]):
        if c in POMIJANE_KATALOGI:
            return f"{c}/"
    poziom = czesci[2:] if len(czesci) >= 2 and czesci[0] == "profiles" else czesci
    if poziom:
        glowa = poziom[0]
        if glowa in POMIJANE_W_KORZENIU and (katalog or len(poziom) > 1):
            return f"{glowa}/"
        if glowa == "cache" and len(poziom) > 1 and poziom[1] not in CACHE_ZOSTAJE:
            return "cache/ (poza mediami)"
        if glowa == "plugins" and len(poziom) > 1 and poziom[1].startswith("jarvo-"):
            return "plugins/jarvo-* (odtwarza instalacja floty)"
    if czesci[:2] == ["jarvo", "narzedzia"]:
        return "jarvo/narzedzia (narzędzia Linuksa)"
    if katalog:
        return None
    if len(czesci) == 3 and czesci[:2] == ["jarvo", "state"]:
        if STAN_CHWILOWY.fullmatch(nazwa):
            return "jarvo/state (stan chwilowy)"
        if nazwa in INDEKS_SKARBCA:
            return "indeks skarbca (odtwarza indeksuj --pelny)"
    if nazwa in POMIJANE_PLIKI:
        return nazwa
    if nazwa.endswith((".pyc", ".pyo")):
        return "*.pyc"
    if nazwa.endswith("-shm") and nazwa[:-4].endswith((".db", ".sqlite", ".sqlite3")):
        return "*-shm (SQLite odtworzy)"
    if nazwa.endswith(".lock") and (".git" in czesci or not _drzewo_wlasciciela(czesci)):
        return "*.lock"
    return None


def sekretny(rel: str) -> bool:
    """Plik z kluczami albo logowaniem (bez nich robimy próbę, f3 p.7): auth.json, .env i skarbce kluczy Hermesa
    (SEKRETNE), poświadczenia gita, npm i pip, katalogi .ssh i .gnupg, logowanie gh i dockera."""
    p = PurePosixPath(rel)
    if p.name in SEKRETNE or p.name in SEKRETNE_INNE or any(c in SEKRETNE_KATALOGI for c in p.parts):
        return True
    return any(rel == s or rel.endswith("/" + s) for s in SEKRETNE_SCIEZKI)


def baza_hermesa(rel: str) -> str | None:
    """Nazwa bazy z KOLUMNY_SCIEZEK albo KOLUMNY_JSON, gdy `rel` to baza Hermesa albo HQ w jej miejscu: state.db
    i projects.db w korzeniu i w profiles/<profil>/, kanban.db w korzeniu (tablica default) i w
    kanban/boards/<tablica>/, rozmowy.db w jarvo/state/. Plik o tej samej nazwie gdzie indziej (np. w katalogu
    roboczym) należy do właściciela: nie przepisujemy go i nie liczymy."""
    czesci = rel.split("/")
    nazwa = czesci[-1]
    if nazwa in ("state.db", "projects.db"):
        return nazwa if len(czesci) == 1 or (len(czesci) == 3 and czesci[0] == "profiles") else None
    if nazwa == "kanban.db":
        return nazwa if len(czesci) == 1 or (len(czesci) == 4 and czesci[:2] == ["kanban", "boards"]) else None
    if nazwa == "rozmowy.db":
        return nazwa if czesci == ["jarvo", "state", "rozmowy.db"] else None
    return None


def jest_sqlite(p: Path) -> bool:
    """Plik zaczyna się nagłówkiem SQLite (albo jest pusty: sqlite3 otwiera go jak pustą bazę)."""
    try:
        with open(p, "rb") as f:
            naglowek = f.read(len(NAGLOWEK_SQLITE))
    except OSError:
        return False
    return naglowek in (b"", NAGLOWEK_SQLITE)


def zla_nazwa(nazwa: str, system: str) -> str | None:
    """Powód, dla którego nazwy nie da się utworzyć w systemie docelowym, albo None."""
    if system != "linux" and any("\udc80" <= z <= "\udcff" for z in nazwa):
        return "nazwa spoza UTF-8"
    if system == "windows":
        zle = sorted({z for z in nazwa if z in _ZLE_NTFS})
        if zle:
            return "znak niedozwolony w Windows: " + " ".join(repr(z) for z in zle)
        if nazwa.endswith((" ", ".")):
            return "spacja albo kropka na końcu nazwy (Windows ją utnie)"
        if nazwa.split(".")[0].rstrip(" ").upper() in _ZASTRZEZONE:
            return "nazwa zastrzeżona w Windows (CON, NUL, COM1…)"
    return None


def klucz_kolizji(rel: str, system: str) -> str | None:
    """Klucz, pod którym system docelowy widzi ścieżkę: Windows i macOS (APFS) bez wielkości liter, macOS też bez
    różnic normalizacji Unicode. Linux rozróżnia wszystko (None)."""
    if system == "windows":
        return rel.casefold()
    if system == "macos":
        return unicodedata.normalize("NFC", rel).casefold()
    return None


def _normalna(nazwa: str) -> str | None:
    """Nazwa członka tar bez `./` i `/` z przodu; None, gdy wychodzi wyżej (`..`)."""
    czesci = [c for c in nazwa.split("/") if c not in ("", ".")]
    if ".." in czesci:
        return None
    return "/".join(czesci)


# ================================================================ ścieżki: stare → natywne

@dataclass(frozen=True)
class Mapa:
    """Stare prefiksy ścieżek (kontener i stary host, z „/”) → katalogi natywne (f3 p.8). Najdłuższy prefiks
    najpierw, tylko na granicy ścieżki (`/opt/database` nie pasuje do `/opt/data`). `windows`: nowe ścieżki
    w postaci Windows (bazy i JSON: z „\\”; pliki tekstowe: `posix=True`, z „/”, bo w YAML i .env „\\” to ucieczka)."""
    pary: tuple[tuple[str, str], ...]
    windows: bool = WINDOWS

    def zamien(self, wartosc: Any, *, posix: bool = False) -> str | None:
        """Nowa wartość, gdy CAŁA wartość to ścieżka pod jednym z prefiksów; inaczej None."""
        if not isinstance(wartosc, str) or not wartosc.startswith("/"):
            return None
        for stary, nowy in self.pary:
            if wartosc == stary or wartosc.startswith(stary + "/"):
                reszta = wartosc[len(stary):]
                if self.windows:
                    baza = PureWindowsPath(nowy)
                    if posix:
                        return baza.as_posix().rstrip("/") + reszta
                    return str(baza).rstrip("\\") + reszta.replace("/", "\\")
                return nowy.rstrip("/") + reszta
        return None

    def slownik(self) -> dict[str, str]:
        return dict(self.pary)


def mapa_sciezek(u: Uklad, zrodlo: "Zrodlo", *, dane: Path | None = None, biez: dict | None = None,
                 narz: dict | None = None, windows: bool = WINDOWS) -> Mapa:
    """Mapa ścieżek tej instalacji: /opt/data i stary katalog danych → `dane` (domyślnie <dane>), /opt/jarvo/build →
    <root>/build, /opt/jarvo/repo i ~/jarvo → kod Jarva, /opt/jarvo/bin → bin-floty, /opt/jarvo/node → Node z narzędzi,
    /opt/hermes → checkout Hermesa, /opt/data/jarvo/narzedzia → narzedzia-floty (instalacje w locie, D06)."""
    biez = srodowisko.biezace(u) if biez is None else biez
    narz = srodowisko.narzedzia(u) if narz is None else narz
    dane = u.dane if dane is None else dane
    pary: dict[str, Path] = {"/opt/data": dane, "/opt/data/jarvo/narzedzia": u.program / "narzedzia-floty",
                             "/opt/jarvo/build": u.build, "/opt/jarvo/bin": u.bin_floty}
    if zrodlo.dane:
        pary[zrodlo.dane] = dane
        pary[zrodlo.dane.rstrip("/") + "/jarvo/narzedzia"] = u.program / "narzedzia-floty"
    if biez.get("app"):
        pary["/opt/jarvo/repo"] = Path(biez["app"])
        if zrodlo.repo:
            pary[zrodlo.repo] = Path(biez["app"])
    if biez.get("hermes"):
        pary["/opt/hermes"] = Path(biez["hermes"])
    node = (narz.get("node") or {}).get("katalog") if isinstance(narz.get("node"), dict) else None
    if node:
        pary["/opt/jarvo/node"] = Path(node)
    czyste = {k.rstrip("/"): str(v) for k, v in pary.items() if k and k.startswith("/") and k.rstrip("/")}
    return Mapa(tuple(sorted(czyste.items(), key=lambda kv: (-len(kv[0]), kv[0]))), windows=windows)


def _zamien_w_json(obj: Any, mapa: Mapa, *, posix: bool = False) -> tuple[Any, int]:
    """Każdy tekst, który w całości jest starą ścieżką, dostaje nową (słowniki i listy rekurencyjnie)."""
    if isinstance(obj, str):
        nowa = mapa.zamien(obj, posix=posix)
        return (nowa, 1) if nowa is not None and nowa != obj else (obj, 0)
    if isinstance(obj, list):
        n = 0
        wynik = []
        for x in obj:
            y, k = _zamien_w_json(x, mapa, posix=posix)
            wynik.append(y)
            n += k
        return wynik, n
    if isinstance(obj, dict):
        n = 0
        wynik = {}
        for klucz, x in obj.items():
            y, k = _zamien_w_json(x, mapa, posix=posix)
            wynik[klucz] = y
            n += k
        return wynik, n
    return obj, 0


# ================================================================ pliki .env (sekrety bez wypisywania)

def czytaj_env(tekst: str) -> dict[str, str]:
    """KLUCZ=wartość z pliku .env (wartość surowa, z cudzysłowami, jak w merge_env.py); komentarze pomijamy."""
    wynik = {}
    for linia in tekst.splitlines():
        if linia.lstrip().startswith("#"):
            continue
        m = _LINIA_ENV.match(linia)
        if m:
            wynik[m["klucz"]] = m["w"]
    return wynik


def wartosc_env(surowa: str) -> str:
    """Wartość bez cudzysłowów na brzegach."""
    if len(surowa) >= 2 and surowa[0] == surowa[-1] and surowa[0] in "\"'":
        return surowa[1:-1]
    return surowa


def scal_env(zrodlo: dict[str, str], cel: Path) -> tuple[list[str], bool]:
    """Scalenie jak scripts/merge_env.py (D02): niepusta wartość ze źródła nadpisuje cel, pusta nie kasuje, reszta linii
    celu zostaje. Zwraca (nazwy ustawionych kluczy, czy plik się zmienił); wartości nigdy nie trafiają do komunikatów.
    Plik tylko dla właściciela (POSIX 0600, Windows ACL)."""
    zmiany = {k: v for k, v in zrodlo.items() if v not in ("", '""', "''")}
    stary = cel.read_text(encoding="utf-8") if cel.is_file() else None
    linie = stary.splitlines() if stary else []
    widziane = set()
    for i, linia in enumerate(linie):
        m = _LINIA_ENV.match(linia)
        if m and not linia.lstrip().startswith("#") and m["klucz"] in zmiany:
            linie[i] = f"{m['klucz']}={zmiany[m['klucz']]}"
            widziane.add(m["klucz"])
    linie += [f"{k}={v}" for k, v in zmiany.items() if k not in widziane]
    nowy = "\n".join(linie) + "\n" if linie else ""
    if stary == nowy:
        return sorted(zmiany), False
    przenosne.zapisz_atomowo(cel, nowy, tryb=0o600)
    przenosne.chron(cel, katalog=False)
    return sorted(zmiany), True


def _klucze_tars(env: dict[str, str]) -> dict[str, str]:
    """Stare nazwy TARS_* → JARVO_* (jak scripts/migrate_jarvo.py host)."""
    return {("JARVO_" + k[5:] if k.startswith("TARS_") else k): v for k, v in env.items()}


def _nazwa_jarvo(nazwa: str) -> str:
    """tars.env → jarvo.env, tars-web.env → jarvo-web.env (migrate_jarvo.new_name)."""
    if nazwa == "tars" or nazwa.startswith(("tars-", "tars.", "tars_")):
        return "jarvo" + nazwa[4:]
    return nazwa


# ================================================================ przepisanie ścieżek: pliki tekstowe

def _cytat_yaml(tekst: str, cud: str) -> str:
    if cud == "'":
        return "'" + tekst.replace("'", "''") + "'"
    return '"' + tekst.replace("\\", "\\\\").replace('"', '\\"') + '"'


def przepisz_env_tekst(tekst: str, mapa: Mapa) -> tuple[str, int]:
    """Wartości .env, które są starą ścieżką (np. IMPECCABLE_HOME=/opt/data/jarvo/narzedzia/impeccable), z „/”."""
    linie = tekst.split("\n")
    n = 0
    for i, linia in enumerate(linie):
        if linia.lstrip().startswith("#"):
            continue
        m = _LINIA_ENV.match(linia.rstrip("\r"))
        if not m:
            continue
        w = m["w"]
        cud = w[0] if len(w) >= 2 and w[0] == w[-1] and w[0] in "\"'" else ""
        nowa = mapa.zamien(w[1:-1] if cud else w, posix=True)
        if nowa is None:
            continue
        if not cud and re.search(r"[\s#\"'$`\\]", nowa):
            cud = '"'
        if cud == '"':
            nowa = nowa.replace("\\", "\\\\").replace('"', '\\"')
        koniec = "\r" if linia.endswith("\r") else ""
        linie[i] = f"{m['przed']}{cud}{nowa}{cud}{m['po']}{koniec}"
        n += 1
    return "\n".join(linie), n


def przepisz_yaml_tekst(tekst: str, mapa: Mapa) -> tuple[str, int]:
    """Wiersze `klucz: /stara/ścieżka` i `- /stara/ścieżka` (distribution.yaml: `source:`), z „/” i w cudzysłowie,
    gdy nowa ścieżka tego wymaga."""
    linie = tekst.split("\n")
    n = 0
    for i, linia in enumerate(linie):
        koniec = "\r" if linia.endswith("\r") else ""
        m = _LINIA_YAML.match(linia.rstrip("\r"))
        if not m or linia.lstrip().startswith("#"):
            continue
        w = m["w"].strip()
        cud = w[0] if len(w) >= 2 and w[0] == w[-1] and w[0] in "\"'" else ""
        srodek = w[1:-1] if cud else w
        if cud == '"' and "\\" in srodek:
            continue                                       # ucieczki YAML: zostawiamy (raport resztek je policzy)
        nowa = mapa.zamien(srodek, posix=True)
        if nowa is None:
            continue
        if not cud and (": " in nowa or " #" in nowa or nowa[:1] in "[]{}&*!|>'\"%@`,?-" or nowa.endswith(":")):
            cud = '"'
        wartosc = _cytat_yaml(nowa, cud) if cud else nowa
        linie[i] = f"{m['przed']}{wartosc}{m['po']}{koniec}"
        n += 1
    return "\n".join(linie), n


def przepisz_json_plik(p: Path, mapa: Mapa) -> int:
    """Plik JSON (cron/jobs.json: workdir, board.json: default_workdir): każdy tekst, który w całości jest starą
    ścieżką. Zapis jak u Hermesa (wcięcie 2, UTF-8 bez ucieczek), tylko przy zmianie."""
    try:
        dane = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return 0
    nowe, n = _zamien_w_json(dane, mapa)
    if n:
        przenosne.zapisz_atomowo(p, json.dumps(nowe, ensure_ascii=False, indent=2) + "\n")
    return n


def _zwykly(p: Path) -> bool:
    """Zwykły plik (bez dowiązań, gniazd, potoków i urządzeń: otwarcie potoku czekałoby bez końca)."""
    try:
        return stat.S_ISREG(os.lstat(p).st_mode)
    except OSError:
        return False


def _pliki(katalog: Path, nazwa: str | None = None, wzorzec: str | None = None) -> Iterator[Path]:
    """Zwykłe pliki w drzewie bez wchodzenia w dowiązania, junction i .git."""
    for korzen, katalogi, pliki in os.walk(katalog, followlinks=False):
        katalogi[:] = [d for d in katalogi if d != ".git" and not _dowiazanie_katalogu(Path(korzen) / d)]
        for f in pliki:
            if (nazwa is None or f == nazwa) and (wzorzec is None or re.fullmatch(wzorzec, f)):
                p = Path(korzen) / f
                if _zwykly(p):
                    yield p


def _dowiazanie_katalogu(p: Path) -> bool:
    if p.is_symlink():
        return True
    sprawdz = getattr(os.path, "isjunction", None)
    if sprawdz is not None:
        return sprawdz(p)
    return WINDOWS and p.is_dir() and os.path.realpath(p) != os.path.abspath(p)


def przepisz_pliki(katalog: Path, mapa: Mapa) -> dict[str, int]:
    """Ścieżki w plikach tekstowych danych (f3 p.8): .env (bez wypisywania wartości), distribution.yaml,
    cron/jobs.json i board.json tablic kanbana. Zwraca {ścieżka względna: liczba zmian}."""
    wynik: dict[str, int] = {}
    for p in _pliki(katalog, ".env"):
        tekst = p.read_text(encoding="utf-8", errors="surrogateescape")
        nowy, n = przepisz_env_tekst(tekst, mapa)
        if n:
            przenosne.zapisz_atomowo(p, nowy.encode("utf-8", "surrogateescape"), tryb=0o600)
            wynik[p.relative_to(katalog).as_posix()] = n
    for p in _pliki(katalog, "distribution.yaml"):
        tekst = p.read_text(encoding="utf-8", errors="surrogateescape")
        nowy, n = przepisz_yaml_tekst(tekst, mapa)
        if n:
            przenosne.zapisz_atomowo(p, nowy.encode("utf-8", "surrogateescape"))
            wynik[p.relative_to(katalog).as_posix()] = n
    for p in [*_pliki(katalog, "jobs.json"), *_pliki(katalog, "board.json")]:
        if p.name == "jobs.json" and p.parent.name != "cron":
            continue
        n = przepisz_json_plik(p, mapa)
        if n:
            wynik[p.relative_to(katalog).as_posix()] = n
    return wynik


# ================================================================ SQLite

def _tabele(con: sqlite3.Connection) -> dict[str, set[str]]:
    wynik: dict[str, set[str]] = {}
    for (nazwa,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        try:
            wynik[nazwa] = {r[1] for r in con.execute(f'PRAGMA table_info("{nazwa}")').fetchall()}
        except sqlite3.Error:
            wynik[nazwa] = set()
    return wynik


def _integralnosc(con: sqlite3.Connection, db: Path, kiedy: str) -> None:
    wynik = [tuple(r) for r in con.execute("PRAGMA integrity_check").fetchall()]
    if wynik != [("ok",)]:
        opis = "; ".join(str(r[0]) for r in wynik[:3])
        raise BladMigracji(f"{db}: integrity_check {kiedy} przepisaniem: {opis}. Dane starej instalacji są nietknięte; "
                           "zgłoś to (plik zostaje w kopii).")


def przepisz_baze(db: Path, mapa: Mapa) -> dict[str, int]:
    """Ścieżki w bazie SQLite (f3 p.8) w jednej transakcji, integrity_check przed i po, na końcu
    wal_checkpoint(TRUNCATE). Kolumny ścieżek z KOLUMNY_SCIEZEK, pola JSON z KOLUMNY_JSON; tabeli messages nie
    ruszamy (wyzwalacze FTS). Zwraca {tabela.kolumna: liczba zmienionych wierszy}."""
    kolumny = KOLUMNY_SCIEZEK.get(db.name, ())
    kolumny_json = KOLUMNY_JSON.get(db.name, ())
    if not kolumny and not kolumny_json:
        return {}
    con = sqlite3.connect(str(db), timeout=30, isolation_level=None)
    zmiany: dict[str, int] = {}
    try:
        _integralnosc(con, db, "przed")
        tabele = _tabele(con)
        con.execute("BEGIN IMMEDIATE")
        try:
            for tabela, kol in kolumny:
                for k in kol:
                    if k not in tabele.get(tabela, ()):
                        continue
                    n = 0
                    stare = [r[0] for r in con.execute(f'SELECT DISTINCT "{k}" FROM "{tabela}" WHERE "{k}" LIKE ?',
                                                      ("/%",)).fetchall()]
                    for wartosc in stare:
                        nowa = mapa.zamien(wartosc)
                        if nowa is None or nowa == wartosc:
                            continue
                        lub = " OR IGNORE" if tabela in DUPLIKATY_USUWAMY else ""
                        n += con.execute(f'UPDATE{lub} "{tabela}" SET "{k}" = ? WHERE "{k}" = ?',
                                         (nowa, wartosc)).rowcount
                        if lub:
                            if tabela == "project_folders" and "is_primary" in tabele.get(tabela, ()):
                                # folder główny projektu pod starą nazwą: znacznik przechodzi na wiersz, który zostaje
                                con.execute('UPDATE "project_folders" SET is_primary = 1 WHERE path = ? AND '
                                            'project_id IN (SELECT project_id FROM "project_folders" WHERE path = ? '
                                            'AND is_primary = 1)', (nowa, wartosc))
                            usuniete = con.execute(f'DELETE FROM "{tabela}" WHERE "{k}" = ?', (wartosc,)).rowcount
                            if usuniete:
                                klucz = f"{tabela}.{k} (duplikaty)"
                                zmiany[klucz] = zmiany.get(klucz, 0) + usuniete
                    if n:
                        zmiany[f"{tabela}.{k}"] = n
            for tabela, kol in kolumny_json:
                for k in kol:
                    if k not in tabele.get(tabela, ()):
                        continue
                    n = 0
                    for rowid, tekst in con.execute(f'SELECT rowid, "{k}" FROM "{tabela}" WHERE "{k}" LIKE ?',
                                                    ('%"/%',)).fetchall():
                        try:
                            obiekt = json.loads(tekst)
                        except (TypeError, ValueError):
                            continue
                        nowy, ile = _zamien_w_json(obiekt, mapa)
                        if ile:
                            con.execute(f'UPDATE "{tabela}" SET "{k}" = ? WHERE rowid = ?',
                                        (json.dumps(nowy, ensure_ascii=False, separators=(",", ":")), rowid))
                            n += 1
                    if n:
                        zmiany[f"{tabela}.{k}"] = n
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        _integralnosc(con, db, "po")
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        con.close()
    return zmiany


def liczby_bazy(db: Path) -> dict[str, int | None]:
    """Liczba wierszy każdej tabeli bazy, liczona na kopii w katalogu tymczasowym (baza razem z -wal i -journal), więc
    oryginał zostaje nietknięty także przy WAL bez -shm. Tabela wirtualna z obcym tokenizerem daje None."""
    with tempfile.TemporaryDirectory(prefix="jarvo-migracja-") as tmp:
        kopia = Path(tmp) / db.name
        shutil.copyfile(db, kopia)
        for s in ("-wal", "-journal"):
            boczny = db.with_name(db.name + s)
            if boczny.is_file():
                shutil.copyfile(boczny, kopia.with_name(kopia.name + s))
        con = sqlite3.connect(str(kopia))
        try:
            wynik: dict[str, int | None] = {}
            nazwy = [n for (n,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE "
                                                "'sqlite_%' ORDER BY name").fetchall()]
            for t in nazwy:
                try:
                    wynik[t] = int(con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0])
                except sqlite3.Error:
                    wynik[t] = None
        finally:
            con.close()
    return wynik


def _bazy_hermesa(katalog: Path) -> Iterator[tuple[Path, str]]:
    """(plik, nazwa) baz Hermesa i HQ w drzewie (baza_hermesa), które są plikami SQLite."""
    for p in _pliki(katalog, wzorzec=r".+\.db"):
        nazwa = baza_hermesa(p.relative_to(katalog).as_posix())
        if nazwa and jest_sqlite(p):
            yield p, nazwa


def przepisz_bazy(katalog: Path, mapa: Mapa) -> dict[str, dict[str, int]]:
    """Bazy Hermesa i HQ w drzewie (state.db i projects.db w korzeniu i profilach, kanban.db także tablic,
    jarvo/state/rozmowy.db): {ścieżka względna: zmiany}."""
    wynik: dict[str, dict[str, int]] = {}
    for p, _nazwa in _bazy_hermesa(katalog):
        zmiany = przepisz_baze(p, mapa)
        if zmiany:
            wynik[p.relative_to(katalog).as_posix()] = zmiany
    return wynik


def liczby_danych(katalog: Path) -> dict[str, int]:
    """Liczby do porównania przed i po (f3 p.7): sesje i wiadomości, karty kanbana, wpisy rozmów, rutyny."""
    wynik = {"sesje": 0, "wiadomosci": 0, "karty": 0, "wpisy": 0, "rutyny": 0}
    for p, nazwa in _bazy_hermesa(katalog):
        if nazwa == "projects.db":
            continue
        try:
            liczby = liczby_bazy(p)
        except sqlite3.Error as e:
            raise BladMigracji(f"{p}: nie odczytam bazy ({e})") from None
        if nazwa == "state.db":
            wynik["sesje"] += liczby.get("sessions") or 0
            wynik["wiadomosci"] += liczby.get("messages") or 0
        elif nazwa == "kanban.db":
            wynik["karty"] += liczby.get("tasks") or 0
        else:
            wynik["wpisy"] += liczby.get("wpisy") or 0
    for p in _pliki(katalog, "jobs.json"):
        if p.parent.name == "cron":
            try:
                dane = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError, UnicodeDecodeError):
                continue
            prace = dane.get("jobs", []) if isinstance(dane, dict) else dane
            wynik["rutyny"] += len(prace) if isinstance(prace, list) else 0
    return wynik


# ================================================================ rutyny (I36)

def wstrzymaj_rutyny(katalog: Path, powod: str = POWOD_RUTYN) -> list[dict]:
    """Włączone rutyny w cron/jobs.json (korzeń i profile) dostają pauzę jak `hermes cron pause` (enabled false, state
    paused, paused_at, paused_reason). Serwis stoi, więc zapis wprost jest bezpieczny. Zwraca [{"plik", "id"}]."""
    wstrzymane = []
    for p in _pliki(katalog, "jobs.json"):
        if p.parent.name != "cron":
            continue
        try:
            dane = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        prace = dane.get("jobs") if isinstance(dane, dict) else dane
        if not isinstance(prace, list):
            continue
        zmiana = False
        for praca in prace:
            if not isinstance(praca, dict) or not praca.get("enabled", True) or praca.get("state") == "paused":
                continue
            # jak cron/jobs.py pause_job: znacznik czasu ISO ze strefą (datetime.isoformat)
            praca.update(enabled=False, state="paused", paused_reason=powod,
                         paused_at=datetime.datetime.now().astimezone().isoformat(timespec="seconds"))
            wstrzymane.append({"plik": p.relative_to(katalog).as_posix(), "id": str(praca.get("id") or "")})
            zmiana = True
        if zmiana:
            przenosne.zapisz_atomowo(p, json.dumps(dane, ensure_ascii=False, indent=2) + "\n")
    return wstrzymane


# ================================================================ kopia: strumień tar → kopia z filtrem

class _Licznik:
    """Strumień wejściowy z licznikiem bajtów i postępem co `co` sekund (eksport WSL to cały system plików)."""

    def __init__(self, strumien: BinaryIO, log: Callable[[str], None] | None, co: float = 15.0):
        self.s, self.log, self.co = strumien, log, co
        self.bajty = 0
        self._t = time.monotonic()

    def read(self, n: int = -1) -> bytes:
        dane = self.s.read(n)
        self.bajty += len(dane)
        if self.log and time.monotonic() - self._t >= self.co:
            self._t = time.monotonic()
            self.log(f"    kopia: przeczytane {self.bajty / 1e9:.2f} GB strumienia…")
        return dane


class _Skrot:
    """Plik z członka tar czytany przez addfile, z sumą sha256 i początkiem pliku (nagłówek SQLite) po drodze."""

    def __init__(self, f: BinaryIO):
        self.f = f
        self.h = hashlib.sha256()
        self.poczatek = b""

    def read(self, n: int = -1) -> bytes:
        dane = self.f.read(n)
        self.h.update(dane)
        if len(self.poczatek) < len(NAGLOWEK_SQLITE):
            self.poczatek += dane[:len(NAGLOWEK_SQLITE) - len(self.poczatek)]
        return dane


def _regula(nazwa: str, reguly: list[tuple[str, str]]) -> tuple[str, str] | None:
    for prefiks, grupa in reguly:
        if nazwa == prefiks:
            return grupa, ""
        if nazwa.startswith(prefiks + "/"):
            return grupa, nazwa[len(prefiks) + 1:]
    return None


def _czytelne_env(katalog: Path) -> bool:
    """Czy ten użytkownik przeczyta katalog i każdy plik *.env w nim (secrets/ starej instalacji ma grupę 10000,
    a pliki tryb 640: zwykle są właściciela, ale po ręcznym chown już nie)."""
    if not os.access(katalog, os.R_OK | os.X_OK):
        return False
    try:
        return all(os.access(p, os.R_OK) for p in katalog.iterdir() if p.name.endswith(".env"))
    except OSError:
        return False


def _info(nazwa: str, wzor: tarfile.TarInfo, typ: bytes | None = None) -> tarfile.TarInfo:
    info = tarfile.TarInfo(nazwa)
    info.type = typ if typ is not None else wzor.type
    info.mode, info.mtime, info.uid, info.gid = wzor.mode, wzor.mtime, wzor.uid, wzor.gid
    info.size = wzor.size if info.type in (tarfile.REGTYPE, tarfile.AREGTYPE) else 0
    return info


def kopiuj(strumien: BinaryIO, reguly: list[tuple[str, str]], cel: Path, *, system_docelowy: str,
           log: Callable[[str], None] | None = None, z_dysku: Iterable[tuple[Path, str]] = ()) -> dict:
    """Strumień tar starego systemu (wsl --export, sudo tar, docker cp) → `cel`: tar z samymi danymi Jarva
    (grupy dane/, compose/, secrets/ z `reguly` = [(prefiks w strumieniu, grupa)]) po filtrze f3 p.6, i spis: sumy
    plików, dowiązania, twarde dowiązania, pominięte (liczby wg powodu) i problemy (nazwy i kolizje w systemie
    docelowym). `z_dysku`: pliki .env z dysku tego komputera [(katalog, grupa)] (macOS: compose i secrets obok
    wolumenu). Zapis do `<cel>.part` i zmiana nazwy dopiero na końcu."""
    reguly = sorted(((p.strip("/"), g) for p, g in reguly if p.strip("/")), key=lambda r: -len(r[0]))
    tmp = cel.with_name(cel.name + ".part")
    cel.parent.mkdir(parents=True, exist_ok=True)
    spis: dict[str, Any] = {"wersja": WERSJA, "pliki": {}, "dowiazania": {}, "twarde": {}, "katalogi": [],
                            "pominiete": {}, "problemy": [], "ostrzezenia": [], "przeczytane": 0}
    kolizje: dict[str, str] = {}
    zgloszone: set[str] = set()

    def pominiete(powod: str, rozmiar: int) -> None:
        w = spis["pominiete"].setdefault(powod, {"pliki": 0, "bajty": 0})
        w["pliki"] += 1
        w["bajty"] += rozmiar

    def sprawdz_nazwe(nowa: str, plik: bool) -> bool:
        czesci = nowa.split("/")[1:]
        for i, c in enumerate(czesci):
            powod = zla_nazwa(c, system_docelowy)
            if powod:                                    # zła nazwa katalogu: cała jego zawartość też odpada
                sciezka = "/".join(czesci[:i + 1])
                if sciezka not in zgloszone:
                    zgloszone.add(sciezka)
                    spis["problemy"].append({"sciezka": nowa.split("/")[0] + "/" + sciezka, "powod": powod})
                return False
        klucz = klucz_kolizji(nowa, system_docelowy) if plik else None
        if klucz is not None:
            inna = kolizje.setdefault(klucz, nowa)
            if inna != nowa:
                spis["problemy"].append({"sciezka": nowa, "powod": f"kolizja wielkości liter z {inna}"})
                return False
        return True

    with open(tmp, "wb") as f_out:
        # strumień czytamy porcjami po 1 MB (eksport WSL to cały system plików, także warstwy obrazów Dockera)
        with tarfile.open(fileobj=f_out, mode="w|", format=tarfile.PAX_FORMAT, encoding="utf-8",
                          errors="surrogateescape", bufsize=1 << 20) as out:
            licznik = _Licznik(strumien, log)
            with tarfile.open(fileobj=licznik, mode="r|*", encoding="utf-8", errors="surrogateescape",
                              bufsize=1 << 20) as wej:
                for m in wej:
                    nazwa = _normalna(m.name)
                    if nazwa is None:
                        if any(_normalna(p) and m.name.lstrip("./").startswith(p) for p, _ in reguly):
                            spis["ostrzezenia"].append({"sciezka": m.name[:200], "powod": "nazwa z „..”, pominięta"})
                        continue
                    trafienie = _regula(nazwa, reguly)
                    if trafienie is None:
                        continue
                    grupa, rel = trafienie
                    if not rel:
                        continue
                    if grupa == "dane":
                        powod = pomin(rel, katalog=m.isdir())
                        if powod:
                            pominiete(powod, m.size if m.isreg() else 0)
                            continue
                    elif not (m.isreg() and "/" not in rel and rel.endswith(".env")):
                        continue                    # compose/ i secrets/: tylko pliki .env (bez .example i znaczników)
                    else:
                        rel = _nazwa_jarvo(rel)
                    nowa = f"{grupa}/{rel}"
                    if m.isdir():
                        if sprawdz_nazwe(nowa, False):
                            out.addfile(_info(nowa, m, tarfile.DIRTYPE))
                            spis["katalogi"].append(rel)
                        continue
                    if m.issym():
                        if sprawdz_nazwe(nowa, True):
                            info = _info(nowa, m, tarfile.SYMTYPE)
                            info.linkname = m.linkname
                            out.addfile(info)
                            spis["dowiazania"][rel] = m.linkname
                        continue
                    if m.islnk():
                        cel_linku = _normalna(m.linkname)
                        trafiony = _regula(cel_linku, reguly) if cel_linku else None
                        if trafiony and trafiony[0] == grupa and f"{grupa}/{trafiony[1]}" in spis["pliki"]:
                            if sprawdz_nazwe(nowa, True):
                                info = _info(nowa, m, tarfile.LNKTYPE)
                                info.linkname = f"{grupa}/{trafiony[1]}"
                                out.addfile(info)
                                spis["twarde"][rel] = trafiony[1]
                        else:
                            spis["ostrzezenia"].append({"sciezka": nowa, "powod": "twarde dowiązanie do pliku spoza "
                                                                                  "kopii, pominięte"})
                        continue
                    if not m.isreg():
                        pominiete("plik specjalny (gniazdo, potok, urządzenie)", 0)
                        continue
                    if not sprawdz_nazwe(nowa, True):
                        continue
                    zrodlo = wej.extractfile(m)
                    skrot = _Skrot(zrodlo)
                    out.addfile(_info(nowa, m, tarfile.REGTYPE), skrot)
                    spis["pliki"][nowa] = {"sha256": skrot.h.hexdigest(), "rozmiar": m.size, "tryb": m.mode & 0o7777,
                                           "uid": m.uid}
                    if nowa.endswith(".db"):            # baza SQLite (jak jest_sqlite): w manifeście liczby wierszy
                        spis["pliki"][nowa]["sqlite"] = skrot.poczatek in (b"", NAGLOWEK_SQLITE)
                # koniec archiwum: reszta strumienia (bloki zerowe) do końca, żeby program-źródło skończył się sam
                while licznik.read(1 << 20):
                    pass
            spis["przeczytane"] = licznik.bajty
            for katalog, grupa in z_dysku:
                katalog = Path(katalog)
                if not katalog.is_dir():
                    continue
                for p in sorted(katalog.iterdir()):
                    if not p.is_file() or p.is_symlink() or not p.name.endswith(".env"):
                        continue
                    nowa = f"{grupa}/{_nazwa_jarvo(p.name)}"
                    if nowa in spis["pliki"]:
                        continue
                    dane = p.read_bytes()
                    info = tarfile.TarInfo(nowa)
                    info.size, info.mode, info.mtime = len(dane), 0o600, int(p.stat().st_mtime)
                    out.addfile(info, io.BytesIO(dane))
                    spis["pliki"][nowa] = {"sha256": hashlib.sha256(dane).hexdigest(), "rozmiar": len(dane),
                                           "tryb": 0o600, "uid": None}
        f_out.flush()
        os.fsync(f_out.fileno())
    os.replace(tmp, cel)
    spis["sha256"] = _sha_pliku(cel)
    spis["rozmiar"] = cel.stat().st_size
    return spis


# ================================================================ rozpakowanie: próba i import

def _dlugi(p: Path) -> str:
    """Na Windows ścieżka z przedrostkiem \\\\?\\ powyżej 240 znaków (MAX_PATH bez LongPathsEnabled)."""
    s = os.path.abspath(str(p))
    if WINDOWS and len(s) > 240 and not s.startswith("\\\\?\\"):
        return "\\\\?\\" + s
    return s


def _w_srodku(katalog: Path, rel: str) -> Path:
    czesci = [c for c in rel.split("/") if c not in ("", ".")]
    if ".." in czesci or not czesci:
        raise BladMigracji(f"kopia: zła ścieżka {rel!r}")
    return katalog.joinpath(*czesci)


def _usun(p: Path) -> None:
    """Plik, dowiązanie albo junction (bez wchodzenia do celu)."""
    if _dowiazanie_katalogu(p) and not p.is_symlink():
        os.rmdir(_dlugi(p))                       # junction na Windows
    elif p.is_symlink() or p.is_file():
        os.unlink(_dlugi(p))


def _zapisz_z_tar(zrodlo: BinaryIO, docel: Path, m: tarfile.TarInfo) -> None:
    os.makedirs(_dlugi(docel.parent), exist_ok=True)
    if docel.is_dir() and not _dowiazanie_katalogu(docel):
        raise BladMigracji(f"{docel}: w miejscu pliku z kopii jest katalog")
    if docel.is_symlink() or _dowiazanie_katalogu(docel):
        _usun(docel)
    fd, tmp = tempfile.mkstemp(prefix=f".{docel.name[:40]}.", suffix=".migracja", dir=_dlugi(docel.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            shutil.copyfileobj(zrodlo, f, 1 << 20)
        if not WINDOWS:
            tryb = 0o600 if (docel.name in SEKRETNE or docel.name.endswith((".db", *SIDECARY))) else \
                (m.mode & 0o755) | 0o600
            os.chmod(tmp, tryb)
        os.utime(tmp, (m.mtime, m.mtime))
        os.replace(tmp, _dlugi(docel))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _utworz_dowiazanie(korzen: Path, rel: str, cel_linku: str, mapa: Mapa | None, *, junction: bool) -> str | None:
    """Dowiązanie z kopii odtworzone natywnie: bezwzględne przez mapę ścieżek, względne tylko w obrębie `korzen`.
    Windows: katalog = junction (bez administratora), plik = kopia celu. Zwraca opis problemu albo None."""
    link = _w_srodku(korzen, rel)
    if cel_linku.startswith("/"):
        nowy = mapa.zamien(cel_linku) if mapa else None
        if nowy is None:
            return f"{rel} → {cel_linku}: cel poza danymi Jarva, dowiązania nie odtwarzam"
        docel = Path(nowy)
        tekst = nowy
    else:
        polaczony = posixpath.normpath(posixpath.join(posixpath.dirname(rel), cel_linku))
        if polaczony == ".." or polaczony.startswith("../") or polaczony.startswith("/"):
            return f"{rel} → {cel_linku}: wychodzi poza dane, dowiązania nie odtwarzam"
        docel = _w_srodku(korzen, polaczony) if polaczony not in ("", ".") else korzen
        tekst = cel_linku
    if link.is_symlink() or _dowiazanie_katalogu(link):
        _usun(link)
    elif link.exists():
        return f"{rel}: w miejscu dowiązania jest plik albo katalog, zostawiam go"
    link.parent.mkdir(parents=True, exist_ok=True)
    if junction:
        if docel.is_dir():
            import _winapi
            _winapi.CreateJunction(str(docel), str(link))
            return None
        if docel.is_file():
            shutil.copy2(docel, link)
            return None
        return f"{rel} → {cel_linku}: celu nie ma w kopii, dowiązania nie odtwarzam"
    os.symlink(tekst, link, target_is_directory=docel.is_dir())
    return None


def rozpakuj(kopia: Path, cel: Path, *, mapa: Mapa | None, bez_sekretow: bool = False,
             junction: bool = WINDOWS, pomijaj: Iterable[str] = ()) -> dict:
    """Część dane/ kopii do `cel` (katalog próby albo <dane>). Przed zapisem każda baza z kopii traci w `cel` stare
    pliki -wal, -shm i -journal (inaczej stary -wal z poprzedniej próby zepsułby świeżą bazę). Dowiązania na końcu
    (_utworz_dowiazanie). `bez_sekretow`: bez auth.json, .env i skarbców kluczy (próba). `pomijaj`: ścieżki
    względne, które zostają natywne (install_id)."""
    pomijaj = set(pomijaj)
    wynik: dict[str, Any] = {"pliki": 0, "bajty": 0, "katalogi": 0, "dowiazania": 0, "pominiete_sekrety": 0,
                             "problemy": [], "pominiete_dowiazania": []}
    cel.mkdir(parents=True, exist_ok=True)
    with tarfile.open(kopia, "r:", encoding="utf-8", errors="surrogateescape") as t:
        czlonkowie = [m for m in t.getmembers() if m.name.startswith("dane/")]
        for m in czlonkowie:
            if m.isreg() and m.name.endswith(".db"):
                for s in ("", *SIDECARY):
                    p = _w_srodku(cel, m.name[5:] + s)
                    if p.is_file() or p.is_symlink():
                        _usun(p)
        linki, twarde = [], []
        for m in czlonkowie:
            rel = m.name[5:]
            if rel in pomijaj:
                continue
            if bez_sekretow and sekretny(rel):
                wynik["pominiete_sekrety"] += 1
                continue
            if m.isdir():
                os.makedirs(_dlugi(_w_srodku(cel, rel)), exist_ok=True)
                wynik["katalogi"] += 1
            elif m.issym():
                linki.append((rel, m.linkname))
            elif m.islnk():
                twarde.append((rel, m.linkname[5:] if m.linkname.startswith("dane/") else m.linkname))
            elif m.isreg():
                zrodlo = t.extractfile(m)
                _zapisz_z_tar(zrodlo, _w_srodku(cel, rel), m)
                wynik["pliki"] += 1
                wynik["bajty"] += m.size
    for rel, cel_rel in twarde:
        z, do = _w_srodku(cel, cel_rel), _w_srodku(cel, rel)
        if z.is_file():
            do.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(_dlugi(z), _dlugi(do))
            wynik["pliki"] += 1
    for rel, cel_linku in sorted(linki):
        problem = _utworz_dowiazanie(cel, rel, cel_linku, mapa, junction=junction)
        if problem:
            wynik["problemy"].append(problem)
            wynik["pominiete_dowiazania"].append(rel)
        else:
            wynik["dowiazania"] += 1
    return wynik


def chron_sekrety(katalog: Path) -> int:
    """Pliki z sekretami (sekretny: auth.json, .env, skarbce kluczy, poświadczenia) tylko dla właściciela (POSIX 0600,
    Windows ACL). Zwraca liczbę plików."""
    n = 0
    for p in _pliki(katalog):
        if sekretny(p.relative_to(katalog).as_posix()):
            przenosne.chron(p, katalog=False)
            n += 1
    return n


# ================================================================ manifest (test migracji, f5) i resztki

def _cel_dowiazania(p: Path) -> str:
    tekst = os.readlink(p)
    if tekst.startswith("\\\\?\\"):
        tekst = tekst[4:]
    return tekst


def manifest(katalog: Path, *, filtr: bool = False, bez: Iterable[str] = ()) -> dict:
    """Manifest danych: {"pliki": {ścieżka: sha256}, "bazy": {ścieżka: {tabela: wiersze}}, "git": {katalog: HEAD},
    "dowiazania": {ścieżka: cel}}. Bazy SQLite (*.db z nagłówkiem SQLite) liczymy na kopii (liczby_bazy), ich pliki
    boczne pomijamy; inny plik *.db to zwykły plik z sumą. Gniazda, potoki i urządzenia pomijamy jak kopia. `filtr`:
    te same reguły co kopia (manifest starego katalogu przed migracją)."""
    from .instalator import head_gita
    katalog = Path(katalog)
    bez = set(bez)
    wynik: dict[str, Any] = {"wersja": WERSJA, "pliki": {}, "bazy": {}, "git": {}, "dowiazania": {}}
    for korzen, katalogi, pliki in os.walk(katalog, followlinks=False):
        rel_k = Path(korzen).relative_to(katalog).as_posix()
        rel_k = "" if rel_k == "." else rel_k
        zostaja = []
        for d in katalogi:
            p = Path(korzen) / d
            rel = f"{rel_k}/{d}" if rel_k else d
            if _dowiazanie_katalogu(p):
                if not (filtr and pomin(rel, katalog=True)):
                    wynik["dowiazania"][rel] = _cel_dowiazania(p)
                continue
            if filtr and pomin(rel, katalog=True):
                continue
            if d == ".git":
                wynik["git"][rel_k or "."] = head_gita(Path(korzen))
            zostaja.append(d)
        katalogi[:] = zostaja
        for f in pliki:
            p = Path(korzen) / f
            rel = f"{rel_k}/{f}" if rel_k else f
            if rel in bez:
                continue
            if p.is_symlink():
                if not (filtr and pomin(rel)):
                    wynik["dowiazania"][rel] = _cel_dowiazania(p)
                continue
            if filtr and pomin(rel):
                continue
            if not _zwykly(p):
                continue
            if f.endswith(BOCZNE_BAZ) and jest_sqlite(p.with_name(f.rsplit(".db", 1)[0] + ".db")):
                continue
            if f.endswith(".db") and jest_sqlite(p):
                try:
                    wynik["bazy"][rel] = liczby_bazy(p)
                except sqlite3.Error as e:
                    wynik["bazy"][rel] = {"blad": str(e)[:200]}
                continue
            wynik["pliki"][rel] = _sha_pliku(p)
    return wynik


def manifest_spisu(spis: dict) -> dict[str, str]:
    """Pliki danych ze spisu kopii {ścieżka względem <dane>: sha256} tak jak liczy je manifest(): bez baz SQLite
    (w manifeście mają liczby wierszy) i bez ich plików bocznych; plik *.db bez nagłówka SQLite zostaje z sumą.
    Wpis spisu bez pola "sqlite" (spis sprzed tego pola) traktujemy jak bazę."""
    pliki = {k: v for k, v in (spis.get("pliki") or {}).items() if k.startswith("dane/")}
    bazy = {k for k, v in pliki.items() if k.endswith(".db") and v.get("sqlite", True)}
    return {k[5:]: v["sha256"] for k, v in pliki.items()
            if k not in bazy and not (k.endswith(BOCZNE_BAZ) and k.rsplit(".db", 1)[0] + ".db" in bazy)}


def _norm_cel(tekst: str) -> str:
    return tekst.replace("\\", "/").rstrip("/").casefold() if WINDOWS else tekst.rstrip("/")


def porownaj(przed: dict, po: dict, *, przepisane: Iterable[str] = (), mapa: dict | None = None,
             bez: Iterable[str] = NATYWNE_ZOSTAJA, duplikaty: dict | None = None) -> list[str]:
    """Różnice między manifestem starych danych (`przed`, z filtrem kopii) a <dane> po imporcie (`po`): brakujący albo
    inny plik (poza `przepisane`, w których migracja zmieniła ścieżki), inne liczby wierszy w bazach, inny HEAD gita,
    dowiązanie, które po mapie ścieżek nie wskazuje tego samego. `bez`: pliki i dowiązania pominięte celowo (install_id
    zostaje natywny, dowiązanie do celu spoza danych). `duplikaty`: {baza: {tabela: wiersze}} usunięte przy
    przepisaniu (ta sama ścieżka pod nazwą z kontenera i ze starego hosta). Pusta lista = zgodne."""
    przepisane = set(przepisane)
    bez = set(bez)
    duplikaty = duplikaty or {}
    roznice = []
    for rel, sha in sorted(przed.get("pliki", {}).items()):
        if rel in bez:
            continue
        if rel not in po.get("pliki", {}):
            roznice.append(f"brak pliku {rel}")
        elif rel not in przepisane and po["pliki"][rel] != sha:
            roznice.append(f"inna treść {rel}")
    for rel, tabele in sorted(przed.get("bazy", {}).items()):
        if rel not in po.get("bazy", {}):
            roznice.append(f"brak bazy {rel}")
            continue
        for tabela, n in sorted(tabele.items()):
            m = po["bazy"][rel].get(tabela)
            if tabela == "blad":                        # baza nieczytelna przed migracją: po niej też ma być tak samo
                if m != n:
                    roznice.append(f"{rel}: przed migracją nieczytelna ({n}), po: {m if m is not None else 'czytelna'}")
                continue
            if isinstance(n, int):
                n -= (duplikaty.get(rel) or {}).get(tabela, 0)
            if n is not None and m != n:
                roznice.append(f"{rel}: tabela {tabela} ma {m} wierszy zamiast {n}")
    for rel, head in sorted(przed.get("git", {}).items()):
        if po.get("git", {}).get(rel) != head:
            roznice.append(f"git {rel}: HEAD {str(po.get('git', {}).get(rel))[:12]} zamiast {str(head)[:12]}")
    m = Mapa(tuple(sorted((mapa or {}).items(), key=lambda kv: -len(kv[0]))))
    for rel, cel in sorted(przed.get("dowiazania", {}).items()):
        if rel in bez:
            continue
        jest = po.get("dowiazania", {}).get(rel)
        if jest is None:
            if rel not in po.get("pliki", {}):         # Windows: dowiązanie do pliku zostaje kopią celu
                roznice.append(f"brak dowiązania {rel}")
            continue
        oczekiwany = (m.zamien(cel) or cel) if cel.startswith("/") else cel
        if _norm_cel(jest) != _norm_cel(oczekiwany) and not (not cel.startswith("/") and WINDOWS):
            roznice.append(f"dowiązanie {rel}: {jest} zamiast {oczekiwany}")
    return roznice


def resztki(katalog: Path, szukane: str = "/opt/") -> dict[str, dict[str, int]]:
    """Ile razy `szukane` zostało w kolumnach tekstowych baz i w plikach tekstowych (same liczby, f3 p.8)."""
    bazy: dict[str, int] = {}
    pliki: dict[str, int] = {}
    for p in _pliki(katalog):
        rel = p.relative_to(katalog).as_posix()
        if p.name.endswith(".db"):
            try:
                con = sqlite3.connect(f"{p.as_uri()}?mode=ro", uri=True, timeout=10)
            except sqlite3.Error:
                continue
            try:
                for tabela, kolumny in _tabele(con).items():
                    if tabela.startswith("sqlite_") or re.search(r"_(fts|data|idx|content|docsize|config)", tabela):
                        continue
                    for k in kolumny:
                        try:
                            n = con.execute(f'SELECT count(*) FROM "{tabela}" WHERE typeof("{k}") = \'text\' AND '
                                            f'instr("{k}", ?) > 0', (szukane,)).fetchone()[0]
                        except sqlite3.Error:
                            continue
                        if n:
                            bazy[f"{rel}:{tabela}.{k}"] = int(n)
            except sqlite3.Error:
                pass
            finally:
                con.close()
            continue
        if p.name.endswith(SIDECARY) or p.stat().st_size > 2_000_000:
            continue
        try:
            tekst = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        n = tekst.count(szukane)
        if n:
            gora = rel.split("/")[0] if "/" in rel else rel
            pliki[gora] = pliki.get(gora, 0) + n
    return {"bazy": bazy, "pliki": pliki}


# ================================================================ skrypty dla starego systemu (root)

SKRYPT_ROZBROJENIA = r"""# Jarvo: rozbrojenie starej floty (jarvo migruj, docs/NATYWNIE.md f3 p.3 i f4). Uruchamia go
# root: w WSL `wsl.exe -d <dystrybucja> -u root -e sh -s`, na Linuksie `sudo sh -s`. Jeden start dystrybucji: najpierw
# inspekcja (ścieżki i stany, nigdy wartości z plików .env), potem U1–U5. Bez ~/jarvo-local/compose/.env (zła
# dystrybucja albo użytkownik) kończy się po inspekcji („koniec brak”) i niczego nie zmienia. Wynik: wiersze
# JARVO|klucz|wartość.
# Argumenty: 1 użytkownik (pusty: pierwszy katalog domowy z jarvo-local), 2 rozbrojenie (tak|nie),
#            3 wyłączenie Dockera w systemie (tak|nie, U5), 4 linger (auto|tak|nie),
#            5 przyrostek nazw (.przeniesione-…),
#            6 katalog starej instalacji, gdy znany (JARVO_LOCAL; „-” = szukaj ~/jarvo-local i ~/tars-local)
set -u
UZ="${1:-}"; ROZBROJ="${2:-tak}"; DOCKER_OFF="${3:-nie}"; LINGER="${4:-auto}"; PRZYROSTEK="${5:-.przeniesione}"
ZNANY="${6:-}"
[ "$UZ" = "-" ] && UZ=""          # „-” zamiast pustego argumentu: wsl.exe potrafi zgubić pusty argument
[ "$ZNANY" = "-" ] && ZNANY=""
p() { printf 'JARVO|%s|%s\n' "$1" "$2"; }
# katalog instalacji: ~/jarvo-local, ~/tars-local albo zapisany przez install.sh w ~/jarvo/.jarvo-local (JARVO_LOCAL)
znajdz() {
  z=""
  [ -f "$1/jarvo/.jarvo-local" ] && z="$(head -n 1 "$1/jarvo/.jarvo-local" 2>/dev/null)"
  for d in "$z" "$1/jarvo-local" "$1/tars-local"; do
    [ -n "$d" ] && [ -f "$d/compose/.env" ] && { echo "$d"; return 0; }
  done
  return 1
}
cd / || exit 1
H=""
if [ -n "$UZ" ]; then
  H="$(getent passwd "$UZ" 2>/dev/null | cut -d: -f6)"
else
  for h in /home/* /root; do
    [ -d "$h" ] || continue
    if znajdz "$h" >/dev/null 2>&1; then H="$h"; UZ="$(stat -c %U "$h" 2>/dev/null)"; break; fi
  done
fi
p uzytkownik "$UZ"
p dom "$H"
L=""
if [ -n "$ZNANY" ] && [ -f "$ZNANY/compose/.env" ]; then L="$ZNANY"
elif [ -n "$H" ]; then L="$(znajdz "$H" 2>/dev/null || true)"; fi
p lokalny "$L"
if [ -z "$L" ]; then p koniec brak; exit 0; fi
for k in JARVO_DATA JARVO_SECRETS JARVO_BUILD JARVO_REPO JARVO_VOL_HERMES; do
  p "env:$k" "$(sed -n "s/^$k=//p" "$L/compose/.env" 2>/dev/null | tail -n 1)"
done
[ -f "$L/.colima" ] && p colima tak
if [ -n "$H" ] && [ -f "$H/jarvo/.git/config" ] && grep -qi 'extraheader' "$H/jarvo/.git/config" 2>/dev/null; then
  p klucz_repo jest
fi
# Docker wstaje razem z dystrybucją (docker.service), a kontenery z restart: unless-stopped zaraz po nim: czekamy na
# demona, żeby żaden kontener nie wstał już po rozbrojeniu
DOCKER=nie
if command -v docker >/dev/null 2>&1; then
  i=0
  while [ "$i" -lt 90 ]; do
    if docker info >/dev/null 2>&1; then DOCKER=tak; break; fi
    if [ "$i" -ge 5 ] && command -v systemctl >/dev/null 2>&1 \
       && ! systemctl is-active -q docker.service docker.socket 2>/dev/null; then break; fi
    sleep 1; i=$((i + 1))
  done
fi
p docker "$DOCKER"
# JARVO_VOLUMES=1: dane w wolumenie Dockera (eksport WSL i sudo tar widzą go w katalogu danych Dockera)
V="$(sed -n 's/^JARVO_VOL_HERMES=//p' "$L/compose/.env" 2>/dev/null | tail -n 1)"
if [ -n "$V" ] && [ "$DOCKER" = tak ]; then
  p wolumen "$(docker volume inspect -f '{{.Mountpoint}}' "$V" 2>/dev/null)"
fi
if [ "$DOCKER" = tak ]; then
  for f in 'name=^jarvo-' 'name=^tars-'; do
    docker ps -a --filter "$f" --format '{{.Names}}|{{.State}}' 2>/dev/null | while IFS= read -r w; do
      p kontener "$w"
    done
  done
fi
J="$H/.config/systemd/user"
[ -n "$H" ] && [ -f "$J/jarvo-updater.service" ] && p updater jednostka
[ -n "$UZ" ] && [ -f "/var/lib/systemd/linger/$UZ" ] && p linger tak
[ -L /usr/local/bin/jarvo ] && p polecenie "$(readlink /usr/local/bin/jarvo)"
if [ "$ROZBROJ" != tak ]; then p koniec inspekcja; exit 0; fi
# U1: brama starej floty w dół jako pierwsza (Telegram, rutyny); restart=no, żeby demon jej nie podniósł
if [ "$DOCKER" = tak ]; then
  for c in $(docker ps -aq --filter 'name=^jarvo-' 2>/dev/null); do
    docker update --restart=no "$c" >/dev/null 2>&1 || true
  done
  if docker ps -q --filter 'name=^jarvo-hermes$' 2>/dev/null | grep -q .; then
    if docker stop -t 70 jarvo-hermes >/dev/null 2>&1; then p krok "U1 zatrzymany"; else p krok "U1 blad"; fi
  else
    p krok "U1 nie-dzialal"
  fi
fi
# U2: pomocnik aktualizacji (na prośbę z panelu uruchomiłby deploy.sh, czyli compose up) i linger
if [ -n "$UZ" ] && [ -n "$H" ]; then
  if [ -f "$J/jarvo-updater.service" ]; then
    systemctl --user -M "$UZ@" disable --now jarvo-updater.service >/dev/null 2>&1 || true
    rm -f "$J/default.target.wants/jarvo-updater.service"
    mv -f "$J/jarvo-updater.service" "$J/jarvo-updater.service$PRZYROSTEK"
    systemctl --user -M "$UZ@" daemon-reload >/dev/null 2>&1 || true
    p krok "U2 jednostka"
  fi
  if [ -n "$L" ] && [ -f "$L/updater.pid" ]; then
    kill "$(cat "$L/updater.pid")" 2>/dev/null && p krok "U2 proces"
  fi
  pkill -u "$UZ" -f 'scripts/updater.py' >/dev/null 2>&1 || true
  if [ -f "/var/lib/systemd/linger/$UZ" ] && [ "$LINGER" != nie ]; then
    inne="$(ls "$J"/*.wants/ 2>/dev/null | grep -v '^jarvo-updater' | grep -c . || true)"
    if [ "$LINGER" = tak ] || [ "${inne:-0}" = 0 ]; then
      loginctl disable-linger "$UZ" >/dev/null 2>&1 && p krok "U2 linger"
    else
      p krok "U2 linger-zostaje $inne"
    fi
  fi
fi
# U3: reszta stosu w dół (kontenery i sieć; wolumeny zostają)
if [ "$DOCKER" = tak ]; then
  if docker compose -p jarvo down >/dev/null 2>&1; then
    p krok "U3 compose"
  else
    ids="$(docker ps -aq --filter label=com.docker.compose.project=jarvo 2>/dev/null)"
    ids="$ids $(docker ps -aq --filter 'name=^jarvo-' 2>/dev/null)"
    # shellcheck disable=SC2086
    [ -n "$(echo $ids)" ] && docker rm -f $ids >/dev/null 2>&1
    p krok "U3 rm"
  fi
  p zostalo "$(docker ps -aq --filter 'name=^jarvo-' 2>/dev/null | grep -c . || true)"
fi
# U4: stare polecenie jarvo (dowiązanie do ~/jarvo/bin/jarvo; bez katalogu domowego nie wiadomo, czyje jest)
if [ -n "$H" ] && [ -L /usr/local/bin/jarvo ]; then
  cel="$(readlink /usr/local/bin/jarvo)"
  case "$cel" in
    "$H"/*/bin/jarvo|"$H"/jarvo/bin/jarvo) rm -f /usr/local/bin/jarvo && p krok "U4 $cel" ;;
    *) p krok "U4 obce $cel" ;;
  esac
fi
# U5: Docker w tej dystrybucji, tylko za osobną zgodą (docker.socket sam uruchomiłby demona przy pierwszym poleceniu)
if [ "$DOCKER_OFF" = tak ] && command -v systemctl >/dev/null 2>&1; then
  if systemctl disable --now docker.service docker.socket containerd.service >/dev/null 2>&1; then
    p krok "U5 ok"
  else
    p krok "U5 blad"
  fi
fi
p koniec ok
"""

SKRYPT_NAZW = r"""# Jarvo: nazwy starych logowań i kluczy w starej kopii danych (f3 p.9, wycofanie f3 p.12).
# Argumenty: 1 katalog danych Hermesa, 2 przyrostek (.przeniesione-RRRRMMDD), 3 kierunek (ukryj|przywroc).
set -u
D="$1"; S="$2"; KIER="${3:-ukryj}"
p() { printf 'JARVO|%s|%s\n' "$1" "$2"; }
[ -d "$D" ] || { p blad "brak katalogu $D"; exit 1; }
# przy przywracaniu wzorce szukają plików z przyrostkiem (oryginałów już nie ma, więc ich wzorzec nic by nie dał)
if [ "$KIER" = ukryj ]; then K=""; else K="$S"; fi
for f in "$D/auth.json$K" "$D/.env$K" "$D"/profiles/*/"auth.json$K" "$D"/profiles/*/".env$K" \
         "$D/.codex/auth.json$K" "$D/home/.codex/auth.json$K" "$D"/profiles/*/home/.codex/"auth.json$K"; do
  [ -f "$f" ] || continue
  if [ "$KIER" = ukryj ]; then
    if mv "$f" "$f$S"; then p przeniesiony "${f#"$D"/}"; else p blad "${f#"$D"/}"; fi
  else
    o="${f%"$S"}"
    [ -e "$o" ] && { p zostaje "${o#"$D"/}"; continue; }
    if mv "$f" "$o"; then p przywrocony "${o#"$D"/}"; else p blad "${o#"$D"/}"; fi
  fi
done
p koniec ok
"""

SKRYPT_WYCOFANIA = r"""# Jarvo: wycofanie migracji w starym systemie (jarvo migruj --wycofaj, f3 p.12). Root.
# Argumenty: 1 użytkownik, 2 przyrostek nazw, 3 Docker włączyć (tak|nie), 4 linger włączyć (tak|nie),
#            5 dowiązanie /usr/local/bin/jarvo (cel albo pusty), 6 jarvo up (tak|nie)
set -u
UZ="$1"; S="$2"; DOCKER_ON="${3:-nie}"; LINGER_ON="${4:-nie}"; POLECENIE="${5:-}"; UP="${6:-nie}"
[ "$POLECENIE" = "-" ] && POLECENIE=""
p() { printf 'JARVO|%s|%s\n' "$1" "$2"; }
cd / || exit 1
H="$(getent passwd "$UZ" 2>/dev/null | cut -d: -f6)"
J="$H/.config/systemd/user"
if [ "$DOCKER_ON" = tak ]; then
  systemctl enable --now containerd.service docker.socket docker.service >/dev/null 2>&1 && p krok "docker"
fi
if [ -f "$J/jarvo-updater.service$S" ] && [ ! -e "$J/jarvo-updater.service" ]; then
  mv "$J/jarvo-updater.service$S" "$J/jarvo-updater.service"
  mkdir -p "$J/default.target.wants"
  ln -sf ../jarvo-updater.service "$J/default.target.wants/jarvo-updater.service"
  chown -h "$UZ" "$J/jarvo-updater.service" "$J/default.target.wants/jarvo-updater.service" 2>/dev/null || true
  systemctl --user -M "$UZ@" daemon-reload >/dev/null 2>&1 || true
  p krok "jednostka"
fi
[ "$LINGER_ON" = tak ] && loginctl enable-linger "$UZ" >/dev/null 2>&1 && p krok "linger"
if [ -n "$POLECENIE" ] && [ ! -e /usr/local/bin/jarvo ]; then
  ln -s "$POLECENIE" /usr/local/bin/jarvo && p krok "polecenie"
fi
if [ "$UP" = tak ]; then
  if runuser -l "$UZ" -c 'bash "$HOME/jarvo/bin/jarvo" up' >/dev/null 2>&1; then p krok "up"; else p krok "up-blad"; fi
fi
p koniec ok
"""


SKRYPT_SPRZATANIA = r"""# Jarvo: sprzątanie starego systemu po okresie przejściowym (--sprzatanie, f3 p.13). Root.
# Argumenty: 1 co (obrazy|dane|wolumen), 2 katalog ~/jarvo-local (dla „dane”) albo nazwa wolumenu (dla „wolumen”).
set -u
CO="$1"; L="${2:-}"
p() { printf 'JARVO|%s|%s\n' "$1" "$2"; }
if [ "$CO" = obrazy ]; then
  for o in jarvo-hermes:local tars-hermes:local; do docker image rm "$o" >/dev/null 2>&1 && p krok "$o"; done
  for o in $(docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep ':src-'); do
    docker image rm "$o" >/dev/null 2>&1 && p krok "$o"
  done
elif [ "$CO" = dane ]; then
  # tylko katalog starej instalacji: jarvo-local albo tars-local z compose/.env
  case "$L" in */jarvo-local|*/tars-local) ;; *) p blad "to nie katalog starej instalacji: $L"; exit 1 ;; esac
  [ -f "$L/compose/.env" ] || { p blad "brak $L/compose/.env"; exit 1; }
  rm -rf -- "$L" && p krok usuniete
elif [ "$CO" = wolumen ]; then
  # tylko wolumen danych starej floty (JARVO_VOLUMES=1): jarvo-hermes-data albo tars-hermes-data
  case "$L" in jarvo-hermes-data|tars-hermes-data) ;; *) p blad "to nie wolumen starej floty: $L"; exit 1 ;; esac
  if docker volume rm "$L" >/dev/null 2>&1; then p krok "wolumen $L"; else p blad "docker volume rm $L"; fi
fi
p koniec ok
"""


def parsuj_wynik(tekst: str) -> dict[str, Any]:
    """Wiersze JARVO|klucz|wartość ze skryptów: wartości wielokrotne (kontener, krok, przeniesiony…) jako listy."""
    wynik: dict[str, Any] = {}
    wielokrotne = {"kontener", "krok", "przeniesiony", "przywrocony", "zostaje", "blad"}
    for linia in tekst.replace("\x00", "").splitlines():
        linia = linia.strip("\r")
        if not linia.startswith(ZNACZNIK_WYNIKU):
            continue
        reszta = linia[len(ZNACZNIK_WYNIKU):]
        klucz, _, wartosc = reszta.partition("|")
        if klucz in wielokrotne:
            wynik.setdefault(klucz, []).append(wartosc)
        else:
            wynik[klucz] = wartosc
    return wynik


# ================================================================ system: programy, strumienie, rejestr (atrapy)

def uruchom_domyslnie(argv: list, wejscie: bytes | None = None, czas: float = 600.0,
                      env: dict | None = None, cwd: str | None = None) -> tuple[int, str]:
    """Program z listy argv bez okna konsoli: (kod, stdout razem ze stderr). Tekst jak zmiany_hosta (UTF-8, potem
    strona OEM)."""
    from .zmiany_hosta import _dekoduj
    argv = [str(a) for a in argv]
    try:
        w = subprocess.run(argv, input=wejscie, stdin=None if wejscie is not None else subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=czas, env=env, cwd=cwd,
                           creationflags=_FLAGI)
    except FileNotFoundError:
        return 127, f"nie ma programu {argv[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"{Path(argv[0]).name}: brak odpowiedzi po {czas:.0f} s"
    except OSError as e:
        return 126, f"{Path(argv[0]).name}: {e}"
    return w.returncode, _dekoduj(w.stdout or b"")


@contextlib.contextmanager
def _zmienne_procesu(zmienne: dict[str, str]) -> Iterator[None]:
    """Zmienne os.environ tylko na czas bloku (potem stare wartości, a nowych nazw nie ma)."""
    stare = {k: os.environ.get(k) for k in zmienne}
    try:
        os.environ.update({k: v for k, v in zmienne.items() if v})
        yield
    finally:
        for k, v in stare.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@contextlib.contextmanager
def strumien_domyslny(argv: list, env: dict | None = None) -> Iterator[BinaryIO]:
    """Wyjście programu jako strumień bajtów (bez potoku PowerShella, który psuje dane binarne). Błędy programu do
    pliku tymczasowego; kod inny niż 0 = BladMigracji z końcówką komunikatu."""
    argv = [str(a) for a in argv]
    with tempfile.TemporaryFile() as bledy:
        try:
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=bledy, env=env,
                                    creationflags=_FLAGI)
        except OSError as e:
            raise BladMigracji(f"nie uruchomię {Path(argv[0]).name}: {e}") from None
        try:
            yield proc.stdout
        except BaseException:
            proc.kill()
            proc.wait()
            raise
        finally:
            with contextlib.suppress(OSError, ValueError):
                proc.stdout.close()
        kod = proc.wait()
        if kod:
            bledy.seek(0)
            from .zmiany_hosta import _dekoduj
            tekst = _dekoduj(bledy.read()[-2000:]).replace("\x00", "").strip()
            raise BladMigracji(f"{Path(argv[0]).name} {' '.join(argv[1:3])}: kod {kod}: {tekst[-400:]}")


class RejestrWindows:
    """HKEY_CURRENT_USER przez winreg (tylko Windows): odczyt Lxss i RunOnce, usunięcie wpisu RunOnce."""

    def podklucze(self, klucz: str) -> list[str]:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, klucz) as k:
                wynik, i = [], 0
                while True:
                    try:
                        wynik.append(winreg.EnumKey(k, i))
                    except OSError:
                        return wynik
                    i += 1
        except FileNotFoundError:
            return []

    def czytaj(self, klucz: str, nazwa: str) -> Any:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, klucz) as k:
                return winreg.QueryValueEx(k, nazwa)[0]
        except FileNotFoundError:
            return None

    def zapisz(self, klucz: str, nazwa: str, wartosc: str) -> None:
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, klucz, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, nazwa, 0, winreg.REG_SZ, wartosc)

    def usun(self, klucz: str, nazwa: str) -> None:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, klucz, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, nazwa)
        except FileNotFoundError:
            pass


def _systemowy(nazwa: str) -> str:
    """Program systemu pełną ścieżką (Windows: System32), a bez niego sama nazwa (atrapy w testach)."""
    from .instalator import systemowy
    return systemowy(nazwa) or (f"{nazwa}.exe" if WINDOWS else nazwa)


def procesy_wsl_domyslne() -> list[dict]:
    """Procesy wsl.exe z wierszem poleceń (Windows, CIM przez PowerShell): [{"pid", "wiersz"}]."""
    ps = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / "WindowsPowerShell" / "v1.0" / \
        "powershell.exe"
    kod, tekst = uruchom_domyslnie([ps, "-NoProfile", "-NonInteractive", "-Command",
                                    "Get-CimInstance Win32_Process -Filter \"Name='wsl.exe'\" | ForEach-Object "
                                    "{ \"$($_.ProcessId)|$($_.CommandLine)\" }"], czas=60)
    wynik = []
    for linia in tekst.splitlines() if kod == 0 else []:
        pid, _, wiersz = linia.strip().partition("|")
        if pid.isdigit():
            wynik.append({"pid": int(pid), "wiersz": wiersz})
    return wynik


def _pytaj_terminal(pytanie: str) -> bool:
    try:
        odp = input(f"{pytanie} [t/N] ")
    except EOFError:
        return False
    return odp.strip().lower() in ("t", "tak", "y", "yes")


def _folder_autostartu(env: dict) -> Path | None:
    appdata = env.get("APPDATA")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" if appdata else None


def _nazwa_systemu() -> str:
    return "windows" if WINDOWS else "macos" if MACOS else "linux"


@dataclass
class SystemMigracji:
    """Wszystko, co migracja robi poza plikami: programy (wsl.exe, docker, systemctl, launchctl, colima, sudo,
    taskkill), strumienie (eksport), rejestr Windows, procesy, pytania, wyjście i zegar. Testy podstawiają atrapy:
    na komputerze właściciela testy nie uruchamiają WSL, Dockera ani sudo."""
    nazwa: str = field(default_factory=_nazwa_systemu)            # windows | macos | linux
    env: dict = field(default_factory=lambda: dict(os.environ))
    dom: Path = field(default_factory=Path.home)
    uruchom: Callable[..., tuple[int, str]] = uruchom_domyslnie     # (argv, wejscie=None, czas=…) -> (kod, wyjście)
    strumien: Callable[[list], Any] = strumien_domyslny              # argv -> menedżer kontekstu ze strumieniem bajtów
    rejestr: Any = None                                              # RejestrWindows (Windows)
    procesy: Callable[[], list[dict]] = procesy_wsl_domyslne
    pytaj: Callable[[str], bool] = _pytaj_terminal
    wypisz: Callable[[str], None] = print
    teraz: Callable[[], float] = time.time
    program: Callable[[str], str | None] = lambda n: (lambda p: p if p and os.path.isabs(p) else None)(
        shutil.which(n))
    wsl: str = field(default_factory=lambda: _systemowy("wsl"))
    taskkill: str = field(default_factory=lambda: _systemowy("taskkill"))
    folder_autostartu: Callable[[], Path | None] | None = None
    # dowiązania polecenia jarvo poza katalogiem domowym, które mógł zostawić stary install.sh (link_cli)
    polecenia_systemowe: tuple[Path, ...] = (Path("/usr/local/bin/jarvo"), Path("/opt/homebrew/bin/jarvo"))
    sqlite: tuple[int, ...] = sqlite3.sqlite_version_info          # wersja SQLite tego procesu (bramka Z14)

    def __post_init__(self) -> None:
        if self.rejestr is None and self.nazwa == "windows" and WINDOWS:
            self.rejestr = RejestrWindows()
        if self.folder_autostartu is None:
            self.folder_autostartu = lambda: _folder_autostartu(self.env)

    def env_wsl(self) -> dict:
        return {**self.env, "WSL_UTF8": "1"}


@dataclass
class Natywne:
    """Instalacja natywna widziana z migracji (domyślnie natywne_domyslne: instalator, nadzorca, Hermes, flota, cli)."""
    zatrzymaj: Callable[[Uklad], None]                          # serwis stoi, znacznik zatrzymania (autostart też)
    uruchom: Callable[[Uklad], str]                             # start serwisu i czekanie na NASZ panel; adres
    konfiguracja: Callable[[Uklad, list[str]], None]            # bezpieczne ustawienia Hermesa, default i profile (I13)
    skarbiec: Callable[[Uklad], str]                            # indeks od nowa i punkt zapisu skarbca (D05)
    flota: Callable[[Uklad], dict]                              # build i install_fleet (config.yaml, SOUL, skille)
    hermes: Callable[[Uklad, list[str], Path], tuple[int, str]]  # polecenie CLI Hermesa z HERMES_HOME = trzeci argument
    doctor: Callable[[Uklad], dict]
    zajete_porty: Callable[[Uklad], list[str]]                  # porty Jarva zajęte teraz (opis: port i kto)
    polecenie_cmd: Callable[[Uklad], bytes]                     # treść natywnego jarvo.cmd (W2)


def natywne_domyslne(ot: Any = None, log: Callable[[str], None] = print) -> Natywne:
    """Natywne na prawdziwych modułach Jarva; `ot` = instalator.Otoczenie (polecenie jarvo podaje swoje)."""
    from . import instalator
    ot = ot or instalator.Otoczenie()

    def zatrzymaj(u: Uklad) -> None:
        instalator.oznacz_zatrzymanie(u, ot, POWOD_ZATRZYMANIA)
        instalator.zatrzymaj_serwis(u, ot, POWOD_ZATRZYMANIA)

    def uruchom(u: Uklad) -> str:
        sposob = instalator.uruchom_serwis(u, ot, log)
        log(f"    serwis uruchomiony {sposob}")
        return instalator.czekaj_na_panel(u, ot, log)

    def _checkout(u: Uklad) -> Path:
        biez = srodowisko.biezace(u)
        if not biez.get("hermes"):
            raise BladMigracji(f"brak Hermesa w {u.program / 'current.json'}: uruchom najpierw `jarvo instaluj`")
        return Path(biez["hermes"])

    def konfiguracja(u: Uklad, profile: list[str]) -> None:
        h = ot.modul("hermes")
        h.konfiguracja_bezpieczna(u, _checkout(u), srodowisko.srodowisko(u, ot.env), log=lambda t: log(f"    {t}"),
                                  profile=profile)

    def skarbiec(u: Uklad) -> str:
        import importlib.util
        app = instalator.katalog_aplikacji(u)
        plik = app / "wiedza" / "wiedza.py"
        root = u.jarvo_dane / "knowledge"
        if not plik.is_file() or not root.is_dir():
            return "pominięty (brak skarbca albo wiedza.py)"
        spec = importlib.util.spec_from_file_location("jarvo_migracja_wiedza", plik)
        w = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = w                      # dataclasses w wiedza.py szukają modułu w sys.modules
        spec.loader.exec_module(w)
        # git skarbca z narzędzi instalacji (Git for Windows z manifestu), nie z PATH właściciela: wiedza.py woła
        # shutil.which("git"), więc na czas tego kroku PATH i zmienne narzędzi (GIT_CONFIG_NOSYSTEM…) z otoczenia Jarva
        env = srodowisko.srodowisko(u, ot.env)
        zmienne = {"PATH": env.get("PATH", "")}
        for wpis in srodowisko.narzedzia(u).values():
            if isinstance(wpis, dict):
                zmienne.update({str(k): str(v) for k, v in (wpis.get("env") or {}).items()})
        with _zmienne_procesu(zmienne):
            sk = w.Skarbiec(root, u.jarvo_dane / "state")
            sk.git_init()                               # skarbiec z Linuksa: śmieci tego systemu do .gitignore
            ix = w.Indeks(sk)
            try:
                r = ix.odswiez(pelny=True)              # `wiedza.py indeksuj --pelny` (wiedza.db nie przechodzi, D05)
                w.zbuduj_index(sk, ix)
                w.odswiez_listy_hubow(sk, ix)
                ix.odswiez()
            finally:
                ix.zamknij()
            zapis = sk.punkt_zapisu("migracja z Dockera")
        return f"indeks {r.get('pliki', '?')} plików, punkt zapisu: {'tak' if zapis else 'nie'}"

    def flota(u: Uklad) -> dict:
        f = ot.modul("flota")
        return f.zainstaluj_flote(u, srodowisko.srodowisko(u, ot.env), log=log)

    def hermes(u: Uklad, argumenty: list[str], dom: Path) -> tuple[int, str]:
        h = ot.modul("hermes")
        checkout = _checkout(u)
        env = srodowisko.srodowisko(u, ot.env)
        dom = Path(dom)
        if not instalator.ten_sam_katalog(dom, u.dane):
            env.update(HERMES_HOME=str(dom), HERMES_WRITE_SAFE_ROOT=str(dom),
                       HERMES_GATEWAY_LOCK_DIR=str(dom / ".blokady-proby"), JARVO_DATA_DIR=str(dom / "jarvo"),
                       JARVO_KNOWLEDGE_DIR=str(dom / "jarvo" / "knowledge"),
                       JARVO_MISSIONS_DIR=str(dom / "jarvo" / "missions"))
        env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        # katalog roboczy: checkout (jak jarvo/hermes.py), nie katalog, w którym wpisano polecenie (Z36)
        return uruchom_domyslnie(h.argv_hermesa(checkout, *argumenty), czas=CZAS_HERMESA, env=env,
                                 cwd=str(checkout))

    def doctor(u: Uklad) -> dict:
        from . import cli
        return cli.zbierz_diagnoze(u, ot)

    def zajete_porty(u: Uklad) -> list[str]:
        wynik = []
        for port in (instalator.port_panelu(ot.env), *PORTY):
            if instalator.port_zajety(port):
                s = ot.sluchacz(port)
                wynik.append(f"{port} ({s[1]}, PID {s[0]})" if s else str(port))
        return wynik

    def polecenie_cmd(u: Uklad) -> bytes:
        # cmd.exe czyta plik w stronie OEM: ścieżki ASCII, w razie potrzeby krótka nazwa 8.3 (c1); bez niej
        # instalator.BladInstalacji, a rozbrojenie przenosi wtedy stary plik zamiast go podmienić
        python = sciezki.krotka_sciezka(instalator.python_jarva(u))
        start = sciezki.krotka_sciezka(instalator.katalog_aplikacji(u) / "jarvo" / "start.py")
        return instalator.tresc_jarvo_cmd(python, start, ["--korzen", str(sciezki.krotka_sciezka(u.root))])

    return Natywne(zatrzymaj=zatrzymaj, uruchom=uruchom, konfiguracja=konfiguracja, skarbiec=skarbiec, flota=flota,
                   hermes=hermes, doctor=doctor, zajete_porty=zajete_porty, polecenie_cmd=polecenie_cmd)


# ================================================================ wykrycie (tylko odczyt)

@dataclass
class Zrodlo:
    """Stara instalacja z danymi (ścieżki w starym systemie, z „/”)."""
    rodzaj: str                       # wsl | katalog (Linux: dane na dysku hosta) | wolumen (macOS, JARVO_VOLUMES)
    system: str
    dystrybucja: str = ""
    uzytkownik: str = ""
    dom: str = ""
    lokalny: str = ""                 # ~/jarvo-local (albo ~/tars-local)
    dane: str = ""                    # katalog danych Hermesa w starym systemie (…/data/hermes)
    compose: str = ""
    sekrety: str = ""
    repo: str = ""                    # ~/jarvo (repo starej instalacji)
    wolumen: str = ""
    kontener: str = ""
    sprawdzone: bool = False          # zajrzeliśmy do środka (WSL: dopiero start rozbrojenia)
    dziala: bool = False              # WSL: dystrybucja działa teraz
    klucz_repo: bool = False          # prywatna kopia repo z kluczem w .git/config (N15)

    @classmethod
    def z_slownika(cls, d: dict) -> "Zrodlo":
        pola = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in (d or {}).items() if k in pola})

    def reguly(self) -> list[tuple[str, str]]:
        """Prefiksy w strumieniu tar → grupy kopii. WSL: wszystko z eksportu; Linux: dane z `sudo tar` (compose
        i secrets czytamy z dysku, kopia() dokłada je do strumienia tylko bez prawa odczytu); wolumen: `docker cp`."""
        if self.rodzaj == "wolumen":
            return [("data", "dane")]
        if self.rodzaj == "katalog":
            return [(self.dane, "dane")]
        return [(self.dane, "dane"), (self.compose, "compose"), (self.sekrety, "secrets")]


@dataclass
class Wykrycie:
    system: str
    zrodla: list[Zrodlo] = field(default_factory=list)
    slady: list[dict] = field(default_factory=list)       # {"kod", "opis", "sciezka"?, "aktywny"}
    dystrybucje: list[dict] = field(default_factory=list)
    kontenery: list[dict] = field(default_factory=list)   # {"nazwa", "stan"}
    docker: str = "brak"                                   # dziala | nie-odpowiada | brak
    uwagi: list[str] = field(default_factory=list)

    @property
    def jest(self) -> bool:
        return bool(self.zrodla or self.kontenery or any(s.get("aktywny") for s in self.slady))

    @property
    def aktywne(self) -> list[dict]:
        return [s for s in self.slady if s.get("aktywny")]


def _tekst(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _docker_kontenery(s: SystemMigracji, docker: str | None) -> tuple[str, list[dict]]:
    """Stan Dockera i kontenery jarvo-* (tylko odczyt; niczego nie startuje)."""
    if not docker:
        return "brak", []
    kod, tekst = s.uruchom([docker, "ps", "-a", "--filter", "name=^jarvo-", "--format", "{{.Names}}|{{.State}}"],
                           czas=60)
    if kod != 0:
        return "nie-odpowiada", []
    kontenery = []
    for linia in tekst.splitlines():
        nazwa, _, stan = linia.strip().partition("|")
        if nazwa.startswith("jarvo-"):
            kontenery.append({"nazwa": nazwa, "stan": stan})
    return "dziala", kontenery


def _lxss(s: SystemMigracji) -> list[dict]:
    r = s.rejestr
    if r is None:
        return []
    domyslna = r.czytaj(LXSS, "DefaultDistribution")
    wynik = []
    for guid in r.podklucze(LXSS):
        klucz = f"{LXSS}\\{guid}"
        nazwa = r.czytaj(klucz, "DistributionName")
        if not nazwa:
            continue
        wynik.append({"nazwa": str(nazwa), "katalog": str(r.czytaj(klucz, "BasePath") or ""),
                      "domyslna": guid == domyslna, "wersja": r.czytaj(klucz, "Version")})
    return wynik


def _dzialajace(s: SystemMigracji) -> list[str]:
    """Działające dystrybucje WSL (`wsl -l --running -q` niczego nie uruchamia). WSL_UTF8=1: bez niej wsl.exe pisze
    do potoku w UTF-16 (zera między literami usuwamy i tak)."""
    kod, tekst = s.uruchom([s.wsl, "-l", "--running", "-q"], czas=60, env=s.env_wsl())
    if kod != 0:
        return []
    return [w.strip() for w in tekst.replace("\x00", "").splitlines() if w.strip() and " " not in w.strip()]


def wykryj(s: SystemMigracji, u: Uklad, *, dystrybucja: str = "", uzytkownik: str = "") -> Wykrycie:
    """Stara instalacja na tym komputerze: tylko odczyt, bez startu WSL i Dockera."""
    if s.nazwa == "windows":
        return _wykryj_windows(s, u, dystrybucja, uzytkownik)
    return _wykryj_posix(s, u, uzytkownik)


def _wykryj_windows(s: SystemMigracji, u: Uklad, dystrybucja: str, uzytkownik: str) -> Wykrycie:
    w = Wykrycie(system="windows")
    stary = Path(s.env.get("LOCALAPPDATA") or s.dom / "AppData" / "Local") / "Jarvo"
    kandydaci: list[str] = [dystrybucja] if dystrybucja else []
    folder = s.folder_autostartu()
    vbs = folder / "Jarvo.vbs" if folder else None
    if vbs is not None and vbs.is_file():
        m = re.search(r"wsl\.exe\s+-d\s+(\S+)", _tekst(vbs), re.I)
        if m:
            kandydaci.append(m.group(1))
        w.slady.append({"kod": "W1", "opis": f"autostart starej floty: {vbs}" + (f" (dystrybucja {m.group(1)})" if m
                        else ""), "sciezka": str(vbs), "aktywny": True})
    uz_cmd = ""
    cmd = stary / "bin" / "jarvo.cmd"
    if cmd.is_file():
        tekst = _tekst(cmd)
        if ZNACZNIK_NATYWNY in tekst:
            w.slady.append({"kod": "W2", "opis": f"{cmd} uruchamia już Jarvo natywnie", "sciezka": str(cmd),
                            "aktywny": False})
        elif "wsl.exe" in tekst.lower():
            m = re.search(r"wsl\.exe\s+-d\s+(\S+)(?:\s+-u\s+(\S+))?", tekst, re.I)
            if m:
                kandydaci.append(m.group(1))
                uz_cmd = m.group(2) or ""
            w.slady.append({"kod": "W2", "opis": f"polecenie jarvo starej instalacji (wsl.exe): {cmd}",
                            "sciezka": str(cmd), "aktywny": True})
    if s.rejestr is not None and s.rejestr.czytaj(RUNONCE, WPIS_RUNONCE):
        w.slady.append({"kod": "W4", "opis": f"wpis RunOnce {WPIS_RUNONCE} (dokończenie starej instalacji po "
                        "restarcie)", "aktywny": True})
    wslconfig = s.dom / ".wslconfig"
    if wslconfig.is_file() and "Jarvo" in _tekst(wslconfig)[:200]:
        w.slady.append({"kod": "W4", "opis": f"{wslconfig} od starego instalatora (pamięć WSL): zostaje, decyzja "
                        "przy sprzątaniu", "sciezka": str(wslconfig), "aktywny": False})
    for nazwa in RESZTKI_STAREGO:
        if (stary / nazwa).exists():
            w.slady.append({"kod": "R", "opis": f"resztka starego instalatora: {stary / nazwa} (sprzątanie)",
                            "sciezka": str(stary / nazwa), "aktywny": False})
    w.dystrybucje = _lxss(s)
    nazwy = {d["nazwa"] for d in w.dystrybucje}
    dzialajace = _dzialajace(s) if w.dystrybucje else []
    for d in w.dystrybucje:
        d["dziala"] = d["nazwa"] in dzialajace
        katalog = d.get("katalog", "").replace("\\\\?\\", "")
        if d["nazwa"] == "Jarvo" and katalog and Path(katalog).parent == stary:
            w.slady.append({"kod": "J", "opis": f"dystrybucja Jarvo z przerwanej instalacji ({katalog}): do "
                            "sprzątania po okresie przejściowym", "aktywny": False})
    docker = s.program("docker")
    w.docker, w.kontenery = _docker_kontenery(s, docker)
    if w.kontenery:
        w.slady.append({"kod": "W3", "opis": "kontenery w Docker Desktop: " + ", ".join(
            f"{k['nazwa']} ({k['stan']})" for k in w.kontenery), "aktywny": True})
    for nazwa in dict.fromkeys(k for k in kandydaci if k):
        if nazwa not in nazwy:
            w.uwagi.append(f"dystrybucji {nazwa} nie ma w WSL (z autostartu albo jarvo.cmd)")
            continue
        if nazwa in DYSTRYBUCJE_DOCKERA:
            continue
        w.zrodla.append(Zrodlo(rodzaj="wsl", system="windows", dystrybucja=nazwa, uzytkownik=uzytkownik or uz_cmd,
                               dziala=nazwa in dzialajace))
    if not w.zrodla:
        inne = [d["nazwa"] for d in w.dystrybucje if d["nazwa"] not in DYSTRYBUCJE_DOCKERA and d["nazwa"] != "Jarvo"]
        if inne and (w.aktywne or (stary / "wsl").is_dir()):
            w.uwagi.append("nie wiem, w której dystrybucji jest stara flota (" + ", ".join(inne) + "): podaj ją "
                           "przez --dystrybucja (sprawdzę ją jednym startem, od razu z rozbrojeniem)")
    return w


def _lokalny(s: SystemMigracji) -> Path | None:
    """~/jarvo-local starej instalacji (JARVO_LOCAL, plik ~/jarvo/.jarvo-local, ~/jarvo-local, ~/tars-local)."""
    kandydaci = []
    if s.env.get("JARVO_LOCAL"):
        kandydaci.append(Path(s.env["JARVO_LOCAL"]).expanduser())
    zapisany = _tekst(s.dom / "jarvo" / ".jarvo-local").strip()
    if zapisany:
        kandydaci.append(Path(zapisany))
    kandydaci += [s.dom / "jarvo-local", s.dom / "tars-local"]
    for k in kandydaci:
        if (k / "compose" / ".env").is_file():
            return k
    return None


def _wykryj_posix(s: SystemMigracji, u: Uklad, uzytkownik: str) -> Wykrycie:
    w = Wykrycie(system=s.nazwa)
    docker = s.program("docker")
    w.docker, w.kontenery = _docker_kontenery(s, docker)
    lokalny = _lokalny(s)
    if lokalny is not None:
        env = {k: wartosc_env(v) for k, v in czytaj_env(_tekst(lokalny / "compose" / ".env")).items()}
        dane = (env.get("JARVO_DATA") or str(lokalny / "data")).rstrip("/") + "/hermes"
        wolumen = env.get("JARVO_VOL_HERMES", "")
        z = Zrodlo(rodzaj="wolumen" if wolumen else "katalog", system=s.nazwa,
                   uzytkownik=uzytkownik or s.env.get("USER") or s.env.get("LOGNAME") or "", dom=str(s.dom),
                   lokalny=str(lokalny), dane="" if wolumen else dane, compose=str(lokalny / "compose"),
                   sekrety=env.get("JARVO_SECRETS") or str(lokalny / "secrets"),
                   repo=env.get("JARVO_REPO") or str(s.dom / "jarvo"), wolumen=wolumen,
                   kontener=KONTENER if any(k["nazwa"] == KONTENER for k in w.kontenery) else "", sprawdzone=True)
        w.zrodla.append(z)
        if (lokalny / ".colima").is_file():
            w.slady.append({"kod": "C", "opis": "Colimę postawił stary instalator (znacznik .colima)",
                            "aktywny": False})
    if w.kontenery:
        # także zatrzymane: restart: unless-stopped podniesie je z demonem Dockera
        w.slady.append({"kod": "U1", "opis": "kontenery starej floty: " + ", ".join(
            f"{k['nazwa']} ({k['stan']})" for k in w.kontenery), "aktywny": True})
    if s.nazwa == "macos":
        plist = s.dom / "Library" / "LaunchAgents" / f"{AGENT_MACOS}.plist"
        if plist.is_file():
            w.slady.append({"kod": "U2", "opis": f"LaunchAgent {AGENT_MACOS} (pomocnik aktualizacji i start Colimy)",
                            "sciezka": str(plist), "aktywny": True})
    else:
        jednostka = s.dom / ".config" / "systemd" / "user" / JEDNOSTKA
        if jednostka.is_file():
            w.slady.append({"kod": "U2", "opis": f"jednostka systemd --user {JEDNOSTKA}", "sciezka": str(jednostka),
                            "aktywny": True})
    for link in (*s.polecenia_systemowe, s.dom / ".local" / "bin" / "jarvo"):
        try:
            cel = os.readlink(link) if link.is_symlink() else ""
        except OSError:
            cel = ""
        if cel and cel.rstrip("/").endswith("/bin/jarvo") and ZNACZNIK_NATYWNY not in _tekst(link):
            w.slady.append({"kod": "U4", "opis": f"stare polecenie jarvo: {link} → {cel}", "sciezka": str(link),
                            "aktywny": True})
    log = Path(w.zrodla[0].lokalny) / "install.log" if w.zrodla else None
    if log is not None and log.is_file() and s.nazwa == "linux":
        tekst = _tekst(log)
        slady = [opis for wzor, opis in ((r"docker\.list|download\.docker\.com", "repozytorium Dockera w apt"),
                                         (r"usermod -aG docker|grupy docker", "grupa docker"),
                                         (r"iptables-legacy", "iptables-legacy"),
                                         (r"jarvo-android\.conf", "jarvo-android.conf")) if re.search(wzor, tekst)]
        if slady:
            w.slady.append({"kod": "R", "opis": "zmiany starego instalatora w systemie (zostają, decyzja przy "
                            "sprzątaniu): " + ", ".join(slady), "aktywny": False})
    return w


def opis_wykrycia(w: Wykrycie) -> str:
    linie = ["Stara instalacja z Dockerem:"]
    if not w.jest:
        linie.append("  nie znalazłem (ani danych, ani autostartu, ani kontenerów jarvo-*).")
    for z in w.zrodla:
        if z.rodzaj == "wsl":
            linie.append(f"  dane: dystrybucja WSL {z.dystrybucja} ({'działa' if z.dziala else 'nie działa'}), "
                         f"~/jarvo-local sprawdzę przy rozbrojeniu (jeden start jako root)")
        elif z.rodzaj == "wolumen":
            linie.append(f"  dane: wolumen Dockera {z.wolumen}, konfiguracja w {z.lokalny}")
        else:
            linie.append(f"  dane: {z.dane} (właściciel uid 10000: kopia przez sudo tar), konfiguracja w {z.lokalny}")
    for slad in w.slady:
        linie.append(f"  {'[aktywny]' if slad.get('aktywny') else '[info]   '} {slad['kod']}: {slad['opis']}")
    if w.system == "windows" and w.dystrybucje:
        linie.append("  dystrybucje WSL: " + ", ".join(
            f"{d['nazwa']}{' (domyślna)' if d.get('domyslna') else ''}{' (działa)' if d.get('dziala') else ''}"
            for d in w.dystrybucje))
    if w.docker == "nie-odpowiada":
        linie.append("  Docker: polecenie jest, ale demon nie odpowiada (kontenerów nie sprawdziłem)")
    for uwaga in w.uwagi:
        linie.append(f"  uwaga: {uwaga}")
    return "\n".join(linie)


# ================================================================ stan i dziennik

class Stan:
    """`<stan>/migracja.json`: etapy z czasem, źródło, katalog, kopia z sumą, wstrzymane rutyny, przepisane pliki."""

    def __init__(self, u: Uklad):
        self.u = u
        self.sciezka = u.stan / PLIK_STANU
        self.d: dict = srodowisko.wczytaj_json(self.sciezka)

    def zapisz(self) -> None:
        przenosne.zapisz_atomowo(self.sciezka, _json(self.d))

    def zrobione(self, etap: str) -> bool:
        return etap in (self.d.get("etapy") or {})

    def oznacz(self, etap: str, **szczegoly: Any) -> None:
        self.d.setdefault("etapy", {})[etap] = {"czas": _teraz_iso(), **szczegoly}
        self.zapisz()

    @property
    def zakonczona(self) -> bool:
        return bool(self.d.get("zakonczona")) and not self.d.get("wycofana")

    @property
    def aktywna(self) -> bool:
        return bool(self.d.get("rozpoczeta")) and not self.d.get("wycofana")


def dopisz_dziennik(u: Uklad, krok: str, akcja: str, *, migracja: str | None = None, **szczegoly: Any) -> None:
    """Wiersz JSON w `<stan>/migracja.jsonl`: co i gdzie zmieniła migracja (do wycofania), z identyfikatorem migracji
    (`migracja`: wycofanie cofa tylko swoje zmiany, a dziennik zostaje po wcześniejszych próbach). Bez sekretów: pola
    o nazwach jak TOKEN czy KLUCZ odrzuca zmiany_hosta._jawne."""
    from .zmiany_hosta import _jawne
    wpis = {"czas": _teraz_iso(), "krok": krok, "akcja": akcja, "szczegoly": _jawne(szczegoly)}
    if migracja:
        wpis["migracja"] = migracja
    u.stan.mkdir(parents=True, exist_ok=True)
    with open(u.stan / PLIK_DZIENNIKA, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(wpis, ensure_ascii=False) + "\n")


def wpisy_dziennika(u: Uklad) -> list[dict]:
    wynik = []
    for linia in _tekst(u.stan / PLIK_DZIENNIKA).split("\n"):
        with contextlib.suppress(ValueError):
            if linia.strip():
                w = json.loads(linia)
                if isinstance(w, dict):
                    wynik.append(w)
    return wynik


# ================================================================ przebieg

@dataclass
class Opcje:
    tak: bool = False
    katalog: str | None = None
    dystrybucja: str = ""
    uzytkownik: str = ""
    wylacz_docker: bool = False
    linger: str = "auto"                 # auto | tak | nie
    lan: bool = False
    bez_floty: bool = False
    bez_startu: bool = False
    json: bool = False


class Migracja:
    def __init__(self, u: Uklad, s: SystemMigracji, n: Natywne, o: Opcje):
        self.u, self.s, self.n, self.o = u, s, n, o
        self.stan = Stan(u)
        # trwająca migracja zostaje przy swoim katalogu (tam jest kopia), także gdy wznowienie poda inny --katalog
        zapisany = self.stan.d.get("katalog") if self.stan.aktywna else None
        self.katalog = Path(zapisany or o.katalog or (u.root / KATALOG))
        # po wycofaniu nowa migracja zaczyna od wykrycia; wycofanie samo potrzebuje źródła z tamtej migracji
        self.zrodlo = Zrodlo.z_slownika(self.stan.d["zrodlo"]) if self.stan.d.get("zrodlo") else None
        if self.stan.d.get("wycofana"):
            self._zrodlo_wycofane, self.zrodlo = self.zrodlo, None
        else:
            self._zrodlo_wycofane = None
        self.zmiany: list[str] = []
        self.raport: dict[str, Any] = {}

    # -- wyjście i zgody
    def wypisz(self, tekst: str) -> None:
        self.s.wypisz(tekst)
        if self.u.logi.is_dir() and self.stan.aktywna:
            with contextlib.suppress(OSError), open(self.u.logi / PLIK_LOGU, "a", encoding="utf-8") as f:
                f.write(f"{_teraz_iso()} {tekst}\n")

    def zgoda(self, pytanie: str) -> bool:
        if self.o.tak:
            self.wypisz(f"{pytanie} → tak (--tak)")
            return True
        return bool(self.s.pytaj(pytanie))

    def wymagaj(self, pytanie: str) -> None:
        if not self.zgoda(pytanie):
            raise Odmowa(pytanie)

    def zmiana(self, opis: str) -> None:
        self.zmiany.append(opis)
        self.wypisz(f"    {opis}")

    def _dziennik(self, krok: str, akcja: str, **szczegoly: Any) -> None:
        dopisz_dziennik(self.u, krok, akcja, migracja=self.stan.d.get("id"), **szczegoly)

    def _przyrostek(self) -> str:
        if not self.stan.d.get("przyrostek"):
            self.stan.d["przyrostek"] = ".przeniesione-" + time.strftime("%Y%m%d", time.localtime(self.s.teraz()))
            self.stan.zapisz()
        return self.stan.d["przyrostek"]

    @property
    def zapas(self) -> Path:
        return self.katalog / "kopia-zapasowa"

    # -- główny przebieg
    def migruj(self) -> int:
        if self.stan.zakonczona:
            return self._ponownie()
        w = wykryj(self.s, self.u, dystrybucja=self.o.dystrybucja, uzytkownik=self.o.uzytkownik)
        if self.stan.aktywna and self.zrodlo is not None:
            # wznowienie: ślady starej floty mogą już być rozbrojone, więc raport wykrycia nic by nie powiedział
            z = self.zrodlo
            gotowe = ", ".join(self.stan.d.get("etapy") or {}) or "żadne"
            skad = z.dystrybucja or z.lokalny or z.wolumen
            self.wypisz(f"Wznawiam migrację z {self.stan.d.get('rozpoczeta')} ({skad}; gotowe etapy: {gotowe}).")
        else:
            self.wypisz(opis_wykrycia(w))
        if self.zrodlo is None:
            if not w.zrodla:
                if w.jest:
                    self.wypisz("Nie wiem, gdzie są dane starej floty: " + "; ".join(w.uwagi or ["brak danych"]) + ".")
                    return 1
                self.wypisz("Nie ma czego migrować.")
                return 0
            if len(w.zrodla) > 1:
                self.wypisz("Stara flota jest w kilku miejscach: " + ", ".join(z.dystrybucja or z.lokalny
                            for z in w.zrodla) + ". Wskaż jedno (--dystrybucja albo JARVO_LOCAL).")
                return 1
            self.zrodlo = w.zrodla[0]
        self._wymagaj_instalacji()
        if not self.stan.aktywna:
            self.wymagaj(f"Migracja do {self.u.dane}: najpierw wyłączę starą flotę (nic nie usuwam), potem skopiuję "
                         f"dane do {self.katalog}, sprawdzę je na próbie i przeniosę. Zaczynamy?")
            self._przygotuj_katalog()
            self.stan.d = {"wersja": WERSJA, "id": uuid.uuid4().hex[:12], "rozpoczeta": _teraz_iso(),
                           "katalog": str(self.katalog), "zrodlo": asdict(self.zrodlo), "etapy": {}}
            self.stan.zapisz()
        for nazwa, opis, krok in self._kroki(w):
            if self.stan.zrobione(nazwa):
                continue
            self.wypisz(f"== {opis}")
            szczegoly = krok() or {}
            self.stan.oznacz(nazwa, **szczegoly)
        self.stan.d["zakonczona"] = _teraz_iso()
        self.stan.zapisz()
        self._zapisz_raport()
        self.wypisz(self._podsumowanie())
        return 0

    def _wymagaj_instalacji(self) -> None:
        biez = srodowisko.biezace(self.u)
        if not biez.get("app") or not biez.get("hermes"):
            raise BladMigracji(f"Jarvo natywnie nie jest zainstalowane w {self.u.root}. Najpierw instalacja w osobnym "
                               "katalogu (JARVO_ROOT, np. D:\\Jarvo albo ~/jarvo-natywnie), potem `jarvo migruj` "
                               "z tej instalacji.")
        if tuple(self.s.sqlite[:3]) < SQLITE_MIN:
            # przepisanie ścieżek pisze do baz w trybie WAL (state.db, kanban.db): tylko na SQLite bez błędu WAL-reset
            raise BladMigracji(f"ten Python ({sys.executable}) ma SQLite {'.'.join(map(str, self.s.sqlite[:3]))}, "
                               f"a migracja potrzebuje {'.'.join(map(str, SQLITE_MIN))}+ (błąd WAL-reset, Z14). "
                               "Uruchom ją poleceniem `jarvo migruj` (Python instalacji, SQLite 3.53).")

    def _przygotuj_katalog(self) -> None:
        self.katalog.mkdir(parents=True, exist_ok=True)
        przenosne.chron(self.katalog, katalog=True)     # kopia ma sekrety: tylko dla właściciela
        try:
            wolne = shutil.disk_usage(self.katalog).free / 1e9
        except OSError:
            wolne = MIN_WOLNE_GB
        if wolne < MIN_WOLNE_GB:
            raise BladMigracji(f"na dysku z {self.katalog} jest {wolne:.1f} GB wolnego: kopia potrzebuje co najmniej "
                               f"{MIN_WOLNE_GB:.0f} GB. Wskaż inny dysk: jarvo migruj --katalog D:\\JarvoMigracja")

    def _kroki(self, w: Wykrycie) -> list[tuple[str, str, Callable[[], dict | None]]]:
        z = self.zrodlo
        kroki: list[tuple[str, str, Callable[[], dict | None]]] = []
        if z.rodzaj == "wsl":
            kroki += [("rozbrojenie-windows", "Rozbrojenie po stronie Windows (W1–W4, bez startu WSL)",
                       lambda: self.rozbroj_windows(w)),
                      ("rozbrojenie", f"Rozbrojenie w dystrybucji {z.dystrybucja} (jeden start jako root, U1–U6)",
                       self.rozbroj_skryptem),
                      ("kopia", "Kopia danych (wsl --export strumieniem, filtr)", self.kopia)]
        elif z.rodzaj == "katalog":
            kroki += [("rozbrojenie", "Rozbrojenie starej floty (sudo: U1–U4)", self.rozbroj_skryptem),
                      ("kopia", "Kopia danych (sudo tar strumieniem, filtr)", self.kopia),
                      ("polecenie", "Stare polecenie jarvo w ~/.local/bin", self.stare_polecenie)]
        else:
            kroki += [("rozbrojenie", "Rozbrojenie starej floty (autostart, kontenery w dół)", self.rozbroj_docker),
                      ("kopia", "Kopia danych (docker cp strumieniem, filtr)", self.kopia),
                      ("kontenery", "Kontenery starej floty (docker compose down)", self.compose_down),
                      ("polecenie", "Stare polecenie jarvo", self.stare_polecenie)]
        kroki += [("proba", "Próba na kopii bez sekretów", self.proba),
                  ("import", f"Import do {self.u.dane}", self.import_),
                  ("konfiguracja", "Bezpieczne ustawienia Hermesa (I13)", self.konfiguracja),
                  ("skarbiec", "Skarbiec: indeks od nowa i punkt zapisu", self.skarbiec),
                  ("unieszkodliwienie", "Stare logowania: nowe nazwy w starej kopii (f3 p.9)", self.unieszkodliw),
                  ("kontrola", "Kontrola przed startem (f3 p.10)", self.kontrola)]
        if not self.o.bez_floty:
            kroki.append(("flota", "Flota: build i instalacja (config.yaml, SOUL, skille)", self.flota))
        if not self.o.bez_startu:
            kroki.append(("start", "Pierwszy start natywny", self.start))
        return kroki

    # -- rozbrojenie
    def rozbroj_windows(self, w: Wykrycie) -> dict:
        zrobione = []
        folder = self.s.folder_autostartu()
        vbs = folder / "Jarvo.vbs" if folder else None
        if vbs is not None and vbs.is_file():
            self.wymagaj(f"W1: przenieść {vbs} do kopii zapasowej (stara flota nie wstanie po zalogowaniu)?")
            cel = self.zapas / "Jarvo.vbs"
            self._dziennik("W1", "przeniesiony", z=str(vbs), do=str(cel))
            cel.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(vbs), str(cel))
            self.zmiana(f"W1: {vbs} → {cel}")
            zrobione.append("W1")
        for proc in self.s.procesy():
            if "sleep infinity" in proc.get("wiersz", "") and "wsl" in proc.get("wiersz", "").lower():
                kod, _ = self.s.uruchom([self.s.taskkill, "/PID", str(proc["pid"]), "/F"], czas=30)
                self.zmiana(f"W1: proces podtrzymujący dystrybucję (PID {proc['pid']}): "
                            f"{'zatrzymany' if kod == 0 else 'nie dał się zatrzymać'}")
        stary = Path(self.s.env.get("LOCALAPPDATA") or self.s.dom / "AppData" / "Local") / "Jarvo"
        cmd = stary / "bin" / "jarvo.cmd"
        if cmd.is_file() and ZNACZNIK_NATYWNY not in _tekst(cmd):
            self.wymagaj(f"W2: {cmd} (stare polecenie przez wsl.exe) podmienić na natywne? Wpis w PATH zostaje.")
            cel = self.zapas / "jarvo.cmd"
            cel.parent.mkdir(parents=True, exist_ok=True)
            if not cel.exists():
                shutil.copy2(cmd, cel)
            try:
                tresc = self.n.polecenie_cmd(self.u)
            except Exception as e:  # noqa: BLE001 - np. korzeń spoza ASCII: cmd.exe nie odczyta ścieżki (stron OEM)
                tresc = None
                powod = str(e).split(". ")[0][:200]
            if tresc is not None:
                self._dziennik("W2", "zastapiony", plik=str(cmd), kopia=str(cel),
                               sha256=hashlib.sha256(tresc).hexdigest())
                from . import zmiany_hosta
                zmiany_hosta.zapisz_plik(self.u, cmd, tresc, None)
                self.zmiana(f"W2: {cmd} uruchamia teraz Jarvo z {self.u.root} (stary w {cel})")
            else:
                # bez podmiany: stary plik znika z PATH, więc `jarvo` trafia do polecenia instalacji natywnej
                self._dziennik("W2", "przeniesiony", z=str(cmd), do=str(cel))
                cmd.unlink()
                self.zmiana(f"W2: {cmd} przeniesiony do {cel} (natywnego polecenia nie da się tu zapisać: {powod}); "
                            f"`jarvo` uruchamia teraz {self.u.root / 'bin' / 'jarvo.cmd'}")
            zrobione.append("W2")
        if w.kontenery:
            docker = self.s.program("docker")
            self.wymagaj("W3: kontenery jarvo-* w Docker Desktop usunąć (`docker compose -p jarvo down`)? Docker "
                         "Desktop i Twoje inne projekty zostają.")
            kod, tekst = self.s.uruchom([docker, "compose", "-p", PROJEKT, "down"], czas=300)
            if kod != 0:
                raise BladMigracji(f"docker compose -p jarvo down w Docker Desktop: kod {kod}: {tekst[-300:]}")
            self._dziennik("W3", "compose-down", kontenery=[k["nazwa"] for k in w.kontenery])
            self.zmiana("W3: kontenery jarvo-* w Docker Desktop usunięte")
            zrobione.append("W3")
        elif w.docker == "nie-odpowiada":
            self.wypisz("    W3: Docker Desktop nie działa, więc kontenerów nie sprawdziłem: kontrola przed startem "
                        "zrobi to jeszcze raz, a następne `jarvo migruj` dokończy, gdy go uruchomisz.")
        wartosc = self.s.rejestr.czytaj(RUNONCE, WPIS_RUNONCE) if self.s.rejestr is not None else None
        if wartosc:
            self.wymagaj(f"W4: usunąć wpis RunOnce {WPIS_RUNONCE} (po restarcie uruchomiłby stary instalator)?")
            self._dziennik("W4", "usuniety-wpis", rejestr=RUNONCE, nazwa=WPIS_RUNONCE, wartosc=str(wartosc))
            self.s.rejestr.usun(RUNONCE, WPIS_RUNONCE)
            self.zmiana(f"W4: wpis RunOnce {WPIS_RUNONCE} usunięty")
            zrobione.append("W4")
        return {"zrobione": zrobione}

    def _wykonaj_root(self, skrypt: str, argumenty: list[str], opis: str, czas: float = 900.0) -> dict:
        """Skrypt sh jako root w starym systemie: WSL przez wsl.exe (stdin, bez cytowania; WSL_UTF8=1, żeby
        komunikaty samego wsl.exe nie przychodziły w UTF-16), Linux przez sudo (hasło z terminala, nie z wejścia)."""
        z = self.zrodlo
        if z.rodzaj == "wsl":
            argv = [self.s.wsl, "-d", z.dystrybucja, "-u", "root", "-e", "sh", "-s", "--", *argumenty]
            kod, tekst = self.s.uruchom(argv, wejscie=skrypt.encode("utf-8"), czas=czas, env=self.s.env_wsl())
        else:
            argv = ["sudo", "sh", "-s", "--", *argumenty]
            kod, tekst = self.s.uruchom(argv, wejscie=skrypt.encode("utf-8"), czas=czas)
        wynik = parsuj_wynik(tekst)
        if kod != 0 or wynik.get("koniec") not in ("ok", "inspekcja", "brak"):
            koniec = "\n".join(x for x in tekst.replace("\x00", "").splitlines()
                               if not x.startswith(ZNACZNIK_WYNIKU))[-400:]
            raise BladMigracji(f"{opis}: kod {kod}{': ' + koniec if koniec else ''}")
        return wynik

    def _terminate(self) -> None:
        if self.zrodlo is not None and self.zrodlo.rodzaj == "wsl":
            kod, tekst = self.s.uruchom([self.s.wsl, "--terminate", self.zrodlo.dystrybucja], czas=120,
                                        env=self.s.env_wsl())
            if kod != 0:
                raise BladMigracji(f"wsl --terminate {self.zrodlo.dystrybucja}: kod {kod}: {tekst.strip()[-200:]}")

    def rozbroj_skryptem(self) -> dict:
        z = self.zrodlo
        gdzie = f"dystrybucji {z.dystrybucja} (WSL)" if z.rodzaj == "wsl" else "tym systemie (sudo)"
        self.wymagaj(f"Rozbrojenie w {gdzie}: U1 brama w dół, U2 pomocnik aktualizacji (jednostka dostaje nową nazwę), "
                     "U3 kontenery jarvo-* w dół (wolumeny zostają), U4 stare dowiązanie /usr/local/bin/jarvo. "
                     + ("To jeden start dystrybucji jako root: stara flota obudzi się na kilka sekund i od razu "
                        "stanie. " if z.rodzaj == "wsl" else "") + "Zgoda?")
        docker_off = "nie"
        if z.rodzaj == "wsl" and (self.o.wylacz_docker or (not self.o.tak and self.s.pytaj(
                "U5: wyłączyć też Dockera w tej dystrybucji (docker.service, docker.socket, containerd)? Gdy używasz "
                "go do innych projektów, odpowiedz nie."))):
            docker_off = "tak"
        linger = self.o.linger if z.rodzaj == "wsl" else ("tak" if self.o.linger == "tak" else "nie")
        self._dziennik("U", "start-rozbrojenia", gdzie=z.dystrybucja or "sudo", docker_off=docker_off,
                        linger=linger)
        wynik = self._wykonaj_root(SKRYPT_ROZBROJENIA, [z.uzytkownik or "-", "tak", docker_off, linger,
                                                        self._przyrostek(), z.lokalny or "-"],
                                   f"rozbrojenie w {gdzie}")
        if z.rodzaj == "wsl":
            self._terminate()
            self._dziennik("U6", "terminate", dystrybucja=z.dystrybucja)
        if wynik.get("koniec") == "brak" or not wynik.get("lokalny"):
            # skrypt niczego nie zmienił: bez ~/jarvo-local to nie ta dystrybucja albo nie ten użytkownik
            raise BladMigracji(f"w {gdzie} nie ma ~/jarvo-local/compose/.env (użytkownik "
                               f"{wynik.get('uzytkownik') or '?'}); niczego tam nie zmieniłem. Wskaż właściwą "
                               "dystrybucję (--dystrybucja) albo użytkownika (--uzytkownik).")
        if z.rodzaj == "wsl":
            # dopiero ten start pokazał, co jest w dystrybucji: ścieżki z compose/.env (bez wartości sekretów)
            lokalny = wynik.get("lokalny", "")
            z.uzytkownik = wynik.get("uzytkownik") or z.uzytkownik
            z.dom, z.lokalny = wynik.get("dom", ""), lokalny
            wolumen = wynik.get("env:JARVO_VOL_HERMES", "").strip("'\"")
            if wolumen:
                # JARVO_VOLUMES=1: dane w wolumenie Dockera w tej dystrybucji; eksport WSL ma go w katalogu Dockera
                z.wolumen = wolumen
                z.dane = (wynik.get("wolumen") or f"/var/lib/docker/volumes/{wolumen}/_data").rstrip("/")
            else:
                z.dane = (wynik.get("env:JARVO_DATA") or f"{lokalny}/data").strip("'\"").rstrip("/") + "/hermes"
            z.compose = f"{lokalny}/compose"
            z.sekrety = (wynik.get("env:JARVO_SECRETS") or f"{lokalny}/secrets").strip("'\"").rstrip("/")
            z.repo = (wynik.get("env:JARVO_REPO") or f"{z.dom}/jarvo").strip("'\"").rstrip("/")
        # Linux: ścieżki zna już wykrycie na tym samym komputerze (także spod JARVO_LOCAL)
        z.sprawdzone, z.klucz_repo = True, wynik.get("klucz_repo") == "jest"
        self.stan.d["zrodlo"] = asdict(z)
        kroki = wynik.get("krok", [])
        for k in kroki:
            self._dziennik(k.split()[0], "rozbrojenie", wynik=k)
            self.zmiana(f"{k}")
        if wynik.get("zostalo") not in (None, "", "0"):
            raise BladMigracji(f"po rozbrojeniu zostało {wynik['zostalo']} kontenerów jarvo-*: sprawdź `docker ps -a` "
                               "w starym systemie i uruchom `jarvo migruj` jeszcze raz.")
        if z.klucz_repo:
            self.wypisz("    klucz prywatnej kopii repo (nagłówek w ~/jarvo/.git/config): zostaje w starej instalacji; "
                        "przeniesie go `jarvo klucz` (N15).")
        return {"kroki": kroki, "kontenery": wynik.get("kontener", []), "docker_off": docker_off,
                "linger": "U2 linger" in kroki, "polecenie": next((k[3:] for k in kroki if k.startswith("U4 /")), "")}

    def _docker(self) -> str:
        docker = self.s.program("docker")
        if not docker:
            raise BladMigracji("brak polecenia docker: bez niego nie dostanę się do wolumenu ze starymi danymi.")
        return docker

    def rozbroj_docker(self) -> dict:
        """macOS (i Linux z wolumenami): autostart starej floty w dół, Docker raz w górę, kontenery stop."""
        z = self.zrodlo
        zrobione: list[str] = []
        if self.s.nazwa == "macos":
            self._wylacz_agenta(zrobione)
        else:
            self._wylacz_jednostke(zrobione)
        docker = self._docker()
        kod, _ = self.s.uruchom([docker, "info"], czas=60)
        if kod != 0:
            colima = self.s.program("colima")
            if not colima:
                raise BladMigracji("Docker nie działa. Uruchom Docker Desktop (albo Colimę) i wpisz `jarvo migruj` "
                                   "jeszcze raz: dane starej floty są w wolumenie Dockera.")
            self.wymagaj("Uruchomić Colimę raz, żeby skopiować wolumen (stara flota wstanie na chwilę i od razu ją "
                         "zatrzymam)?")
            kod, tekst = self.s.uruchom([colima, "start"], czas=600)
            if kod != 0:
                raise BladMigracji(f"colima start: kod {kod}: {tekst[-300:]}")
            self._dziennik("C", "colima-start")
            zrobione.append("colima")
        kod, tekst = self.s.uruchom([docker, "ps", "-aq", "--filter", "name=^jarvo-"], czas=60)
        for c in tekst.split() if kod == 0 else []:
            self.s.uruchom([docker, "update", "--restart=no", c], czas=60)
        kod, tekst = self.s.uruchom([docker, "ps", "-q", "--filter", f"name=^{KONTENER}$"], czas=60)
        if kod == 0 and tekst.strip():
            self.wymagaj(f"Zatrzymać {KONTENER} (brama starej floty: Telegram, rutyny)?")
            kod, tekst = self.s.uruchom([docker, "stop", "-t", "70", KONTENER], czas=180)
            if kod != 0:
                raise BladMigracji(f"docker stop {KONTENER}: kod {kod}: {tekst[-300:]}")
            self._dziennik("U1", "zatrzymany", kontener=KONTENER)
            self.zmiana(f"U1: {KONTENER} zatrzymany")
            zrobione.append("U1")
        kod, _ = self.s.uruchom([docker, "inspect", KONTENER], czas=60)
        z.kontener = KONTENER if kod == 0 else ""
        self.stan.d["zrodlo"] = asdict(z)
        return {"zrobione": zrobione}

    def _wylacz_agenta(self, zrobione: list[str]) -> None:
        """macOS: LaunchAgent pl.jarvo.updater (pomocnik aktualizacji, który po zalogowaniu startuje też Colimę) w dół
        i do kopii zapasowej."""
        plist = self.s.dom / "Library" / "LaunchAgents" / f"{AGENT_MACOS}.plist"
        if not plist.is_file():
            return
        self.wymagaj(f"LaunchAgent {AGENT_MACOS} (pomocnik aktualizacji, start Colimy po zalogowaniu) wyłączyć i "
                     "przenieść do kopii zapasowej?")
        uid = str(os.getuid()) if hasattr(os, "getuid") else "0"
        self.s.uruchom(["launchctl", "bootout", f"gui/{uid}/{AGENT_MACOS}"], czas=60)
        cel = self.zapas / plist.name
        cel.parent.mkdir(parents=True, exist_ok=True)
        self._dziennik("U2", "przeniesiony", z=str(plist), do=str(cel))
        shutil.move(str(plist), str(cel))
        self.zmiana(f"LaunchAgent {AGENT_MACOS} wyłączony ({cel})")
        zrobione.append("agent")

    def _wylacz_jednostke(self, zrobione: list[str]) -> None:
        jednostka = self.s.dom / ".config" / "systemd" / "user" / JEDNOSTKA
        if not jednostka.is_file():
            return
        self.wymagaj(f"Pomocnik aktualizacji {JEDNOSTKA} (systemd --user) wyłączyć? Jednostka dostaje nową nazwę.")
        self.s.uruchom(["systemctl", "--user", "disable", "--now", JEDNOSTKA], czas=120)
        cel = jednostka.with_name(jednostka.name + self._przyrostek())
        self._dziennik("U2", "przeniesiony", z=str(jednostka), do=str(cel))
        jednostka.replace(cel)
        self.s.uruchom(["systemctl", "--user", "daemon-reload"], czas=60)
        self.zmiana(f"U2: {JEDNOSTKA} wyłączony ({cel.name})")
        zrobione.append("U2")

    def compose_down(self) -> dict:
        docker = self._docker()
        self.wymagaj("Kontenery starej floty usunąć (`docker compose -p jarvo down`)? Wolumen z danymi zostaje "
                     "(to też kopia do wycofania).")
        kod, tekst = self.s.uruchom([docker, "compose", "-p", PROJEKT, "down"], czas=300)
        if kod != 0:
            raise BladMigracji(f"docker compose -p jarvo down: kod {kod}: {tekst[-300:]}")
        self._dziennik("U3", "compose-down")
        self.zmiana("U3: kontenery starej floty usunięte (wolumeny zostają)")
        return {}

    def stare_polecenie(self) -> dict:
        """~/.local/bin/jarvo, /usr/local/bin/jarvo i /opt/homebrew/bin/jarvo: dowiązania do ~/jarvo/bin/jarvo (stary
        install.sh, link_cli). Na Linuksie /usr/local/bin/jarvo usuwa już skrypt rozbrojenia (U4, root); gdzie brak
        prawa zapisu, sudo (tylko za zgodą)."""
        usuniete = []
        for link in [self.s.dom / ".local" / "bin" / "jarvo", *self.s.polecenia_systemowe]:
            try:
                cel = os.readlink(link) if link.is_symlink() else ""
            except OSError:
                cel = ""
            if not cel or not cel.rstrip("/").endswith("/bin/jarvo"):
                continue
            if not self.zgoda(f"Stare polecenie {link} → {cel} usunąć (`jarvo` ma uruchamiać instalację natywną)?"):
                continue
            self._dziennik("U4", "usuniete-dowiazanie", sciezka=str(link), cel=cel)
            try:
                link.unlink()
            except PermissionError:
                kod, tekst = self.s.uruchom(["sudo", "rm", "-f", str(link)], czas=120)
                if kod != 0:
                    raise BladMigracji(f"sudo rm {link}: kod {kod}: {tekst[-200:]}") from None
            self.zmiana(f"U4: {link} usunięty (było → {cel})")
            usuniete.append({"sciezka": str(link), "cel": cel})
        return {"usuniete": usuniete}

    # -- kopia
    @property
    def plik_kopii(self) -> Path:
        return self.katalog / "kopia.tar"

    def kopia(self) -> dict:
        z = self.zrodlo
        cel = self.plik_kopii
        cel.with_name(cel.name + ".part").unlink(missing_ok=True)
        z_dysku: list[tuple[Path, str]] = []
        reguly = z.reguly()
        if z.rodzaj == "wsl":
            argv = [self.s.wsl, "--export", z.dystrybucja, "-"]
            self.wypisz(f"    eksport całej dystrybucji {z.dystrybucja}; zapisuję tylko dane Jarva (to potrwa)")
        elif z.rodzaj == "katalog":
            # dane należą do uid 10000 (0700), więc tar przez sudo; compose i secrets są właściciela (secrets: grupa
            # 10000, 2750), więc czytamy je z dysku, a do strumienia idą tylko bez prawa odczytu
            sciezki_tar = [z.dane.lstrip("/")]
            for katalog, grupa in ((z.compose, "compose"), (z.sekrety, "secrets")):
                if not katalog:
                    continue
                if _czytelne_env(Path(katalog)):
                    z_dysku.append((Path(katalog), grupa))
                elif Path(katalog).exists() or not os.access(Path(katalog).parent, os.X_OK):
                    sciezki_tar.append(katalog.lstrip("/"))
                    reguly.append((katalog, grupa))
            argv = ["sudo", "tar", "-C", "/", "-cf", "-", *sciezki_tar]
        else:
            docker = self._docker()
            if z.kontener:
                argv = [docker, "cp", f"{z.kontener}:/opt/data", "-"]
            else:
                argv = [docker, "run", "--rm", "-v", f"{z.wolumen}:/opt/data:ro", "--entrypoint", "tar", OBRAZ,
                        "-C", "/opt", "-cf", "-", "data"]
            z_dysku = [(Path(z.compose), "compose"), (Path(z.sekrety), "secrets")]
        system_docelowy = self.s.nazwa
        with self.s.strumien(argv) as strumien:
            spis = kopiuj(strumien, reguly, cel, system_docelowy=system_docelowy, log=self.wypisz, z_dysku=z_dysku)
        przenosne.zapisz_atomowo(self.katalog / "spis.json", _json(spis))
        przenosne.zapisz_atomowo(self.katalog / "kopia.tar.sha256", f"{spis['sha256']}  kopia.tar\n")
        dane = [k for k in spis["pliki"] if k.startswith("dane/")]
        self.wypisz(f"    kopia: {len(dane)} plików danych, {spis['rozmiar'] / 1e6:.1f} MB, sha256 "
                    f"{spis['sha256'][:12]}… ({cel})")
        for powod, w in sorted(spis["pominiete"].items(), key=lambda kv: -kv[1]["bajty"])[:12]:
            self.wypisz(f"    pominięte {powod}: {w['pliki']} plików, {w['bajty'] / 1e6:.1f} MB")
        for o in spis["ostrzezenia"][:10]:
            self.wypisz(f"    uwaga: {o['sciezka']}: {o['powod']}")
        if not dane:
            raise BladMigracji("kopia nie ma żadnego pliku danych Hermesa: zła ścieżka danych? Stara instalacja jest "
                               "nietknięta, sprawdź raport wykrycia.")
        if spis["problemy"]:
            lista = "\n".join(f"      {p['sciezka']}: {p['powod']}" for p in spis["problemy"][:20])
            raise BladMigracji(f"{len(spis['problemy'])} nazw nie da się utworzyć w tym systemie (raport w "
                               f"{self.katalog / 'spis.json'}):\n{lista}\n    Zmień te nazwy w starej instalacji i "
                               "uruchom `jarvo migruj` jeszcze raz (zrobi nową kopię). Niczego nie zaimportowałem.")
        manifest_kopii = {"pliki": manifest_spisu(spis), "dowiazania": spis["dowiazania"]}
        przenosne.zapisz_atomowo(self.katalog / "manifest-kopii.json", _json(manifest_kopii))
        return {"sha256": spis["sha256"], "rozmiar": spis["rozmiar"], "pliki": len(dane)}

    def _sprawdz_kopie(self) -> None:
        zapis = (self.stan.d.get("etapy") or {}).get("kopia") or {}
        if not self.plik_kopii.is_file():
            raise BladMigracji(f"brak kopii {self.plik_kopii}: uruchom `jarvo migruj` jeszcze raz (zrobi nową).")
        if zapis.get("sha256") and _sha_pliku(self.plik_kopii) != zapis["sha256"]:
            raise BladMigracji(f"{self.plik_kopii} ma inną sumę niż po kopii: plik zmieniony albo uszkodzony.")

    # -- próba (f3 p.7)
    def proba(self) -> dict:
        self._sprawdz_kopie()
        katalog = self.katalog / "proba"
        if katalog.exists():
            shutil.rmtree(katalog, ignore_errors=True)
        try:
            rozpakuj(self.plik_kopii, katalog, mapa=None, bez_sekretow=True, junction=WINDOWS, pomijaj=NATYWNE_ZOSTAJA)
            sekrety = [p for p in _pliki(katalog) if p.name in SEKRETNE]
            if sekrety:
                raise BladMigracji("próba: w katalogu próby są pliki z sekretami (błąd filtra), przerywam")
            przed = liczby_danych(katalog)
            mapa = mapa_sciezek(self.u, self.zrodlo, dane=katalog)
            bazy = przepisz_bazy(katalog, mapa)
            pliki = przepisz_pliki(katalog, mapa)
            po = liczby_danych(katalog)
            if przed != po:
                raise BladMigracji(f"próba: liczby przed {przed} i po {po} przepisaniu się różnią. Niczego nie "
                                   "zaimportowałem.")
            polecenia = {}
            for argumenty in (["-p", "default", "sessions", "list"], ["kanban", "list"],
                              ["-p", "default", "cron", "list"], ["profile", "list"]):
                kod, tekst = self.n.hermes(self.u, argumenty, katalog)
                polecenia[" ".join(argumenty)] = kod
                if kod != 0:
                    koniec = " / ".join(x for x in tekst.splitlines()[-3:] if x.strip())[-300:]
                    raise BladMigracji(f"próba: `hermes {' '.join(argumenty)}` na kopii: kod {kod} ({koniec}). "
                                       "Niczego nie zaimportowałem.")
            self.wypisz(f"    próba: {przed['sesje']} sesji, {przed['wiadomosci']} wiadomości, {przed['karty']} kart, "
                        f"{przed['wpisy']} wpisów rozmów, {przed['rutyny']} rutyn: te same liczby po przepisaniu; "
                        f"polecenia Hermesa tylko do odczytu: kod 0")
            return {"liczby": przed, "bazy": {k: sum(v.values()) for k, v in bazy.items()}, "pliki": len(pliki),
                    "polecenia": polecenia}
        finally:
            shutil.rmtree(katalog, ignore_errors=True)

    # -- import (f3 p.8)
    @property
    def natywne_przed(self) -> Path:
        """Katalog na natywne pliki, które import zastępuje: `natywne-przed-importem`, a gdy został po migracji
        wycofanej wcześniej, nowa nazwa z datą i numerem (tamte pliki to jedyna kopia natywnych danych sprzed
        pierwszego importu)."""
        etap = self.stan.d.setdefault("import", {})
        if not etap.get("katalog_natywnych"):
            cel = self.katalog / "natywne-przed-importem"
            n = 1
            while cel.exists():
                n += 1
                cel = self.katalog / f"natywne-przed-importem-{time.strftime('%Y%m%d')}-{n}"
            etap["katalog_natywnych"] = str(cel)
            self.stan.zapisz()
        return Path(etap["katalog_natywnych"])

    def import_(self) -> dict:
        self._sprawdz_kopie()
        self.wymagaj(f"Import danych do {self.u.dane}: serwis Jarva stanie na czas importu, a natywne pliki o tych "
                     f"samych nazwach trafią do {self.natywne_przed}. Zgoda?")
        self.n.zatrzymaj(self.u)
        etap = self.stan.d.setdefault("import", {})
        if not etap.get("natywne_zapisane"):
            przeniesione = self._zapisz_natywne()
            etap["natywne_zapisane"] = len(przeniesione)
            self.stan.zapisz()
            if przeniesione:
                self.zmiana(f"natywne pliki zastąpione kopią: {len(przeniesione)} (są w {self.natywne_przed})")
        mapa = mapa_sciezek(self.u, self.zrodlo)
        wynik = rozpakuj(self.plik_kopii, self.u.dane, mapa=mapa, junction=WINDOWS, pomijaj=NATYWNE_ZOSTAJA)
        for problem in wynik["problemy"]:
            self.wypisz(f"    uwaga: {problem}")
        bazy = przepisz_bazy(self.u.dane, mapa)
        pliki = przepisz_pliki(self.u.dane, mapa)
        sekrety = self._sekrety()
        wstrzymane = wstrzymaj_rutyny(self.u.dane)
        przepisane = sorted({*pliki, *(r["plik"] for r in wstrzymane)})
        self.stan.d["przepisane"] = przepisane
        self.stan.d["wstrzymane_rutyny"] = wstrzymane
        self.stan.d["mapa"] = mapa.slownik()
        self.stan.d["pominiete_dowiazania"] = wynik["pominiete_dowiazania"]
        duplikaty = {rel: {k.split(".")[0]: n for k, n in zmiany.items() if k.endswith(" (duplikaty)")}
                     for rel, zmiany in bazy.items()}
        self.stan.d["duplikaty"] = {rel: d for rel, d in duplikaty.items() if d}
        self.stan.zapisz()
        chron_sekrety(self.u.dane)
        po = manifest(self.u.dane, bez=NATYWNE_ZOSTAJA)
        przenosne.zapisz_atomowo(self.katalog / "manifest-po.json", _json(po))
        kopii = srodowisko.wczytaj_json(self.katalog / "manifest-kopii.json")
        roznice = porownaj({"pliki": kopii.get("pliki", {}), "dowiazania": kopii.get("dowiazania", {})}, po,
                           przepisane=przepisane, mapa=mapa.slownik(),
                           bez={*NATYWNE_ZOSTAJA, *wynik["pominiete_dowiazania"]})
        if roznice:
            lista = "\n".join(f"      {r}" for r in roznice[:20])
            raise BladMigracji(f"po imporcie {len(roznice)} różnic względem kopii:\n{lista}\n    Kopia zostaje "
                               f"({self.plik_kopii}); serwis stoi. Uruchom `jarvo migruj` jeszcze raz.")
        reszta = resztki(self.u.dane)
        przenosne.zapisz_atomowo(self.katalog / "resztki.json", _json(reszta))
        ile_baz = sum(sum(v.values()) for v in bazy.values())
        self.zmiana(f"import: {wynik['pliki']} plików ({wynik['bajty'] / 1e6:.1f} MB), {wynik['dowiazania']} dowiązań, "
                    f"ścieżki: {ile_baz} wierszy w {len(bazy)} bazach i {len(pliki)} plików, sekrety: "
                    f"{len(sekrety)} plików w {self.u.jarvo_dane / 'konfig'}, wstrzymane rutyny: {len(wstrzymane)}")
        zostalo = sum(reszta["bazy"].values()) + sum(reszta["pliki"].values())
        if zostalo:
            self.wypisz(f"    resztki „/opt/”: {sum(reszta['bazy'].values())} w bazach (głównie historia rozmów, HQ "
                        f"ma alias), {sum(reszta['pliki'].values())} w plikach (config.yaml i SOUL odtworzy flota); "
                        f"liczby w {self.katalog / 'resztki.json'}")
        return {"pliki": wynik["pliki"], "bajty": wynik["bajty"], "dowiazania": wynik["dowiazania"],
                "bazy": {k: sum(v.values()) for k, v in bazy.items()}, "przepisane": len(przepisane),
                "sekrety": sekrety, "rutyny": len(wstrzymane), "problemy": wynik["problemy"]}

    def _zapisz_natywne(self) -> list[str]:
        """Natywne pliki w <dane> pod nazwami z kopii (i pliki boczne baz) → natywne_przed (raz na migrację)."""
        przeniesione = []
        cel = self.natywne_przed
        with tarfile.open(self.plik_kopii, "r:", encoding="utf-8", errors="surrogateescape") as t:
            nazwy = [m.name[5:] for m in t.getmembers() if m.name.startswith("dane/") and not m.isdir()]
        dodatkowe = [n + s for n in nazwy if n.endswith(".db") for s in SIDECARY]
        for rel in dict.fromkeys([*nazwy, *dodatkowe]):
            if rel in NATYWNE_ZOSTAJA:
                continue
            p = _w_srodku(self.u.dane, rel)
            if not (p.is_file() or p.is_symlink()):
                continue
            docel = _w_srodku(cel, rel)
            docel.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(_dlugi(p), _dlugi(docel))
            przeniesione.append(rel)
        return przeniesione

    def _sekrety(self) -> list[str]:
        """secrets/*.env i compose/jarvo.env → <dane>/jarvo/konfig (scalenie jak merge_env.py, D02); z compose/.env
        tylko DASHBOARD_* z --lan (panel.env na tryb LAN, I11); bez SEARXNG_SECRET i BESZEL_AGENT_KEY. secrets/jarvo.env
        (klucze agenta jarvo) i compose/jarvo.env (ustawienia floty: TELEGRAM_OWNER_ID, tematy, dostawca) trafiają do
        jednego konfig/jarvo.env: jarvo/flota.py podaje go buildowi jako --env-file (ustawienia), a install_fleet.py
        bierze z katalogu konfig host.env i <agent>.env (klucze). Zwraca nazwy plików (bez wartości)."""
        konfig = self.u.jarvo_dane / "konfig"
        konfig.mkdir(parents=True, exist_ok=True)
        przenosne.chron(konfig, katalog=True)
        zapisane = []
        with tarfile.open(self.plik_kopii, "r:", encoding="utf-8", errors="surrogateescape") as t:
            for m in t.getmembers():
                if not m.isreg():
                    continue
                grupa, _, nazwa = m.name.partition("/")
                if grupa == "secrets":
                    cel = konfig / nazwa
                elif grupa == "compose" and nazwa == "jarvo.env":
                    cel = konfig / "jarvo.env"
                elif grupa == "compose" and nazwa == ".env" and self.o.lan:
                    cel = konfig / "panel.env"
                else:
                    continue
                env = _klucze_tars(czytaj_env(t.extractfile(m).read().decode("utf-8", "replace")))
                if cel.name == "panel.env":
                    env = {k: v for k, v in env.items() if k.startswith("DASHBOARD_")}
                klucze, _zmieniony = scal_env(env, cel)
                zapisane.append(f"{cel.name} ({len(klucze)} kluczy)")
        return zapisane

    def konfiguracja(self) -> dict:
        profile = sorted(p.name for p in (self.u.dane / "profiles").iterdir()
                         if p.is_dir() and _PROFIL.fullmatch(p.name) and p.name != "default") \
            if (self.u.dane / "profiles").is_dir() else []
        self.n.konfiguracja(self.u, profile)
        przepisane = set(self.stan.d.get("przepisane") or [])
        przepisane |= {"config.yaml", *(f"profiles/{p}/config.yaml" for p in profile)}
        self.stan.d["przepisane"] = sorted(przepisane)
        self.stan.zapisz()
        return {"profile": profile}

    def skarbiec(self) -> dict:
        opis = self.n.skarbiec(self.u)
        self.wypisz(f"    skarbiec: {opis}")
        return {"opis": opis}

    # -- unieszkodliwienie (f3 p.9)
    def unieszkodliw(self) -> dict:
        z = self.zrodlo
        przyrostek = self._przyrostek()
        self.wymagaj(f"auth.json i .env w starej kopii danych dostaną nazwę *{przyrostek} (token odświeżania OpenAI "
                     "jest jednorazowy: dwie kopie wylogowałyby obie)" + (". To drugi start dystrybucji (stara flota "
                                                                         "już nie wstanie)" if z.rodzaj == "wsl"
                                                                         else "") + ". Zgoda?")
        if z.rodzaj == "wolumen":
            docker = self._docker()
            argv = [docker, "run", "-i", "--rm", "--user", "0", "-v", f"{z.wolumen}:/opt/data", "--entrypoint", "sh",
                    OBRAZ, "-s", "--", "/opt/data", przyrostek, "ukryj"]
            kod, tekst = self.s.uruchom(argv, wejscie=SKRYPT_NAZW.encode("utf-8"), czas=300)
            wynik = parsuj_wynik(tekst)
            if kod != 0 or wynik.get("koniec") != "ok":
                raise BladMigracji(f"nowe nazwy starych logowań w wolumenie {z.wolumen}: kod {kod}: {tekst[-300:]}")
        else:
            wynik = self._wykonaj_root(SKRYPT_NAZW, [z.dane, przyrostek, "ukryj"], "nowe nazwy starych logowań")
            if z.rodzaj == "wsl":
                self._terminate()
        if wynik.get("blad"):
            raise BladMigracji("nie zmieniłem nazw: " + ", ".join(wynik["blad"]))
        przeniesione = wynik.get("przeniesiony", [])
        self._dziennik("U9", "ukryte-logowania", pliki=przeniesione, przyrostek=przyrostek)
        self.zmiana(f"stare logowania i klucze z nową nazwą (*{przyrostek}): {len(przeniesione)} plików")
        return {"pliki": przeniesione}

    # -- kontrola (f3 p.10)
    def kontrola(self) -> dict:
        problemy = []
        if self.zrodlo.rodzaj == "wsl":
            dzialajace = _dzialajace(self.s)
            for d in dict.fromkeys([self.zrodlo.dystrybucja, "Jarvo"]):
                if d in dzialajace:
                    problemy.append(f"dystrybucja {d} działa (wsl --terminate {d})")
        porty = self.n.zajete_porty(self.u)
        if porty:
            problemy.append("zajęte porty Jarva: " + ", ".join(porty))
        docker = self.s.program("docker")
        if docker:
            kod, tekst = self.s.uruchom([docker, "ps", "-q", "--filter", "name=^jarvo-"], czas=60)
            if kod == 0 and tekst.strip():
                problemy.append("działają kontenery jarvo-* (docker ps)")
            elif kod != 0 and self.s.nazwa == "windows":
                self.wypisz("    uwaga: Docker Desktop nie odpowiada; gdy go uruchomisz, a zostały w nim kontenery "
                            "jarvo-*, wpisz `jarvo migruj` (usunie je)")
        if problemy:
            raise BladMigracji("przed startem: " + "; ".join(problemy) + ". Nowa flota nie wystartuje obok starej.")
        self.wypisz("    stara flota nie działa, porty wolne")
        return {}

    def flota(self) -> dict:
        wynik = self.n.flota(self.u) or {}
        ostrz = wynik.get("ostrzezenia") or []
        self.wypisz(f"    flota: {len(wynik.get('agenci') or [])} agentów" + (f", ostrzeżenia: {len(ostrz)}" if ostrz
                                                                               else ""))
        return {"agenci": len(wynik.get("agenci") or [])}

    def start(self) -> dict:
        adres = self.n.uruchom(self.u)
        # logowania przeniesione z auth.json (tylko odczyt; `auth status` chce nazwy dostawcy, `auth list` nie)
        kod, _ = self.n.hermes(self.u, ["-p", "default", "auth", "list"], self.u.dane)
        d = self.n.doctor(self.u)
        liczby = liczby_danych(self.u.dane)
        self.wypisz(f"    panel: {adres}; hermes auth list: kod {kod}; jarvo doctor: {d.get('bledy', '?')} błędów, "
                    f"{d.get('uwagi', '?')} uwag; w danych {liczby['sesje']} sesji i {liczby['karty']} kart. Napisz "
                    "do Jarva w panelu albo `jarvo chat`: pierwsze zapytanie do modelu sprawdza logowanie.")
        if d.get("bledy"):
            for r in d.get("wyniki") or []:
                if r.get("stan") == "blad":
                    self.wypisz(f"    [błąd] {r.get('nazwa')}: {r.get('opis')} (rada: {r.get('rada')})")
        return {"adres": adres, "auth_status": kod, "doctor_bledy": d.get("bledy"), "liczby": liczby}

    # -- drugi przebieg
    def _ponownie(self) -> int:
        w = wykryj(self.s, self.u, dystrybucja=self.o.dystrybucja, uzytkownik=self.o.uzytkownik)
        if not w.aktywne and not w.kontenery:
            self.s.wypisz(f"Migracja zakończona {self.stan.d.get('zakonczona')}: stara flota rozbrojona, dane w "
                          f"{self.u.dane}. Nic do zrobienia.")
            if self.stan.d.get("wstrzymane_rutyny") and not self.stan.d.get("rutyny_wznowione"):
                self.s.wypisz("Rutyny czekają na próbną wiadomość na Telegram; potem: jarvo migruj --wznow-rutyny")
            return 0
        self.s.wypisz(opis_wykrycia(w))
        self.s.wypisz("Po migracji wróciły ślady starej floty: rozbrajam je jeszcze raz.")
        kody = {s["kod"] for s in w.aktywne}
        if self.s.nazwa == "windows":
            wynik = self.rozbroj_windows(w)
        else:
            wynik = {}
            if w.kontenery:
                self.compose_down()
            if "U2" in kody and self.s.nazwa == "macos":
                self._wylacz_agenta([])
            elif "U2" in kody:
                self._wylacz_jednostke([])
            if "U4" in kody:
                wynik = self.stare_polecenie()
        self.stan.oznacz("rozbrojenie-ponowne", **(wynik or {}))
        return 0

    # -- raport
    def _zapisz_raport(self) -> None:
        raport = {"wersja": WERSJA, "zakonczona": self.stan.d.get("zakonczona"), "zrodlo": self.stan.d.get("zrodlo"),
                  "etapy": self.stan.d.get("etapy"), "przepisane": self.stan.d.get("przepisane"),
                  "wstrzymane_rutyny": len(self.stan.d.get("wstrzymane_rutyny") or []), "zmiany": self.zmiany,
                  "manifest_zgodny": True}
        przenosne.zapisz_atomowo(self.katalog / "raport.json", _json(raport))

    def _podsumowanie(self) -> str:
        linie = [f"Migracja gotowa: dane w {self.u.dane}, kopia i raport w {self.katalog}."]
        if self.o.bez_startu:
            linie.append("Serwis Jarva stoi (--bez-startu): uruchom go poleceniem `jarvo up`.")
        if self.o.bez_floty:
            linie.append("Flota bez odtworzenia (--bez-floty): config.yaml, SOUL i skille profili odtworzy "
                         "`jarvo instaluj`.")
        if self.stan.d.get("wstrzymane_rutyny"):
            linie.append("Rutyny są wstrzymane: po próbnej wiadomości na Telegram wpisz `jarvo migruj --wznow-rutyny`.")
        linie.append("Stara instalacja zostaje do sprzątania (najwcześniej za "
                     f"{OKRES_PRZEJSCIOWY_DNI} dni: `jarvo migruj --sprzatanie`); powrót: `jarvo migruj --wycofaj`.")
        return "\n".join(linie)

    # -- wznowienie rutyn (I36)
    def wznow_rutyny(self) -> int:
        wstrzymane = self.stan.d.get("wstrzymane_rutyny") or []
        if not wstrzymane:
            self.s.wypisz("Migracja nie wstrzymała żadnej rutyny.")
            return 0
        if self.stan.d.get("rutyny_wznowione"):
            self.s.wypisz(f"Rutyny wznowione już {self.stan.d['rutyny_wznowione']}.")
            return 0
        bledy = 0
        for r in wstrzymane:
            czesci = r["plik"].split("/")
            profil = czesci[1] if czesci[0] == "profiles" and len(czesci) > 2 else "default"
            kod, tekst = self.n.hermes(self.u, ["-p", profil, "cron", "resume", r["id"]], self.u.dane)
            if kod != 0:
                bledy += 1
                self.s.wypisz(f"  {profil}/{r['id']}: kod {kod} ({tekst.strip()[-200:]})")
        if bledy:
            return 1
        self.stan.d["rutyny_wznowione"] = _teraz_iso()
        self.stan.zapisz()
        self.s.wypisz(f"Wznowione rutyny: {len(wstrzymane)}.")
        return 0

    # -- wycofanie (f3 p.12)
    def wycofaj(self) -> int:
        if not self.stan.d.get("rozpoczeta"):
            self.s.wypisz("Nie było migracji: nie ma czego wycofać.")
            return 0
        if self.stan.d.get("wycofana"):
            self.s.wypisz(f"Migracja wycofana już {self.stan.d['wycofana']}.")
            return 0
        self.wymagaj("Wycofanie: natywny Jarvo stanie (dane w <dane> zostają), a stara flota wróci. Nigdy obie naraz. "
                     "Zgoda?")
        self.n.zatrzymaj(self.u)
        # tylko zmiany tej migracji: dziennik zostaje po wcześniejszych (wycofanych) próbach
        ta = self.stan.d.get("id")
        od = str(self.stan.d.get("rozpoczeta") or "")
        wpisy = [w for w in wpisy_dziennika(self.u)
                 if (w.get("migracja") == ta if ta else str(w.get("czas") or "") >= od)]
        z = self.zrodlo
        for wpis in reversed(wpisy):
            s = wpis.get("szczegoly") or {}
            if wpis.get("akcja") == "przeniesiony" and Path(s.get("do", "")).exists() and not Path(s["z"]).exists():
                Path(s["z"]).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(s["do"], s["z"])
                self.zmiana(f"przywrócony {s['z']}")
                if s["z"].endswith(f"{AGENT_MACOS}.plist"):
                    uid = str(os.getuid()) if hasattr(os, "getuid") else "0"
                    self.s.uruchom(["launchctl", "bootstrap", f"gui/{uid}", s["z"]], czas=60)
                elif s["z"].endswith(JEDNOSTKA):
                    self.s.uruchom(["systemctl", "--user", "daemon-reload"], czas=60)
                    self.s.uruchom(["systemctl", "--user", "enable", "--now", JEDNOSTKA], czas=120)
            elif wpis.get("akcja") == "usuniete-dowiazanie" and not Path(s.get("sciezka", "")).exists():
                with contextlib.suppress(OSError):
                    os.symlink(s["cel"], s["sciezka"])
                    self.zmiana(f"przywrócone dowiązanie {s['sciezka']} → {s['cel']}")
            elif wpis.get("akcja") == "zastapiony" and Path(s.get("kopia", "")).is_file():
                from . import zmiany_hosta
                shutil.copy2(s["kopia"], s["plik"])
                # wpis dziennika zmian hosta z chwili podmiany (ta sama suma), żeby uninstall nie ruszał starego pliku
                sha = s.get("sha256") or hashlib.sha256(self.n.polecenie_cmd(self.u)).hexdigest()
                zmiany_hosta.zapomnij(self.u, "plik", sciezka=s["plik"], sha256=sha)
                self.zmiana(f"przywrócony {s['plik']}")
            elif wpis.get("akcja") == "usuniety-wpis" and self.s.rejestr is not None:
                self.wypisz(f"    wpis RunOnce {s.get('nazwa')} nie wraca (uruchomiłby stary instalator po restarcie)")
        rozbr = (self.stan.d.get("etapy") or {}).get("rozbrojenie") or {}
        przyrostek = self.stan.d.get("przyrostek") or ".przeniesione"
        if z is not None and (z.dane or z.rodzaj == "wolumen"):
            if z.rodzaj == "wolumen":
                docker = self._docker()
                kod, tekst = self.s.uruchom([docker, "run", "-i", "--rm", "--user", "0", "-v", f"{z.wolumen}:/opt/data",
                                             "--entrypoint", "sh", OBRAZ, "-s", "--", "/opt/data", przyrostek,
                                             "przywroc"], wejscie=SKRYPT_NAZW.encode("utf-8"), czas=300)
                if kod != 0 or parsuj_wynik(tekst).get("koniec") != "ok":
                    raise BladMigracji(f"przywrócenie starych logowań w wolumenie {z.wolumen}: kod {kod}: "
                                       f"{tekst.strip()[-300:]}. Natywny Jarvo stoi; uruchom --wycofaj jeszcze raz.")
            elif z.sprawdzone:
                self._wykonaj_root(SKRYPT_NAZW, [z.dane, przyrostek, "przywroc"], "przywrócenie starych logowań")
        if z is not None and z.rodzaj in ("wsl", "katalog") and z.uzytkownik:
            up = "tak" if self.zgoda("Uruchomić starą flotę (`jarvo up` w starym systemie)?") else "nie"
            wynik = self._wykonaj_root(SKRYPT_WYCOFANIA, [z.uzytkownik, przyrostek,
                                                          "tak" if rozbr.get("docker_off") == "tak" else "nie",
                                                          "tak" if rozbr.get("linger") else "nie",
                                                          rozbr.get("polecenie") or "-", up],
                                       "wycofanie w starym systemie")
            for k in wynik.get("krok", []):
                self.zmiana(f"stary system: {k}")
            folder = self.s.folder_autostartu() if z.rodzaj == "wsl" else None
            vbs = folder / "Jarvo.vbs" if folder else None
            if up == "tak" and vbs is not None and vbs.is_file():
                # dystrybucja ze starą flotą żyje dzięki procesowi z autostartu (bez niego WSL ją uśpi)
                self.s.uruchom([_systemowy("wscript"), str(vbs)], czas=60)
            elif z.rodzaj == "wsl":
                self._terminate()
        elif z is not None and z.rodzaj == "wolumen" and z.repo:
            jarvo = Path(z.repo) / "bin" / "jarvo"
            if jarvo.is_file() and self.zgoda(f"Uruchomić starą flotę (`{jarvo} up`)?"):
                kod, tekst = self.s.uruchom(["bash", str(jarvo), "up"], czas=1800)
                self.zmiana(f"stara flota: jarvo up, kod {kod}")
        self.stan.d["wycofana"] = _teraz_iso()
        self.stan.zapisz()
        self.s.wypisz("Wycofane: stara flota wraca, natywny Jarvo stoi (`jarvo up` dopiero po rozbrojeniu starej, "
                      "czyli `jarvo migruj`).")
        return 0

    # -- sprzątanie (f3 p.13)
    def sprzataj(self, bez_okresu: bool = False) -> int:
        imp = (self.stan.d.get("etapy") or {}).get("import")
        if not imp or self.stan.d.get("wycofana"):
            self.s.wypisz("Sprzątanie dopiero po udanej migracji (bez wycofania).")
            return 1
        try:
            od = time.mktime(time.strptime(imp["czas"], "%Y-%m-%dT%H:%M:%S"))
        except (KeyError, ValueError):
            od = 0.0
        dni = (self.s.teraz() - od) / 86400
        if dni < OKRES_PRZEJSCIOWY_DNI and not bez_okresu:
            self.s.wypisz(f"Okres przejściowy: od importu minęło {dni:.0f} dni z {OKRES_PRZEJSCIOWY_DNI}. Sprzątanie "
                          "później (albo świadomie: --bez-okresu).")
            return 1
        z = self.zrodlo
        zrobione = []
        if self.s.nazwa == "windows":
            stary = Path(self.s.env.get("LOCALAPPDATA") or self.s.dom / "AppData" / "Local") / "Jarvo"
            for d in _lxss(self.s):
                katalog = d.get("katalog", "").replace("\\\\?\\", "")
                if d["nazwa"] == "Jarvo" and katalog and Path(katalog).parent == stary and \
                        (z is None or z.dystrybucja != "Jarvo"):
                    if self.zgoda("Wyrejestrować dystrybucję Jarvo (przerwana instalacja: tylko install.log i "
                                  "Docker)? `wsl --unregister Jarvo` usuwa jej dysk."):
                        kod, tekst = self.s.uruchom([self.s.wsl, "--unregister", "Jarvo"], czas=300,
                                                    env=self.s.env_wsl())
                        if kod != 0:
                            raise BladMigracji(f"wsl --unregister Jarvo: kod {kod}: {tekst[-200:]}")
                        zrobione.append("dystrybucja Jarvo")
            docker = self.s.program("docker")
            if docker and self.zgoda("Obrazy starej floty w Docker Desktop usunąć (jarvo-hermes:local, "
                                     "tars-hermes:local, src-*; ok. 25 GB)?"):
                kod, tekst = self.s.uruchom([docker, "images", "--format", "{{.Repository}}:{{.Tag}}"], czas=60)
                obrazy = [o for o in tekst.split() if o in STARE_OBRAZY or o.split(":")[-1].startswith("src-")]
                if obrazy:
                    self.s.uruchom([docker, "image", "rm", *obrazy], czas=600)
                    zrobione.append(f"obrazy Docker Desktop ({len(obrazy)})")
            resztki_plikow = [stary / n for n in RESZTKI_STAREGO if (stary / n).exists()]
            if resztki_plikow and self.zgoda("Resztki starego instalatora usunąć (" + ", ".join(
                    p.name for p in resztki_plikow) + ")?"):
                for p in resztki_plikow:
                    p.unlink(missing_ok=True)
                zrobione.append("resztki instalatora")
        if z is not None and z.rodzaj in ("wsl", "katalog") and z.lokalny:
            start = False
            if self.zgoda("Obrazy Dockera starej floty w starym systemie usunąć (ok. 10 GB)?"):
                self._wykonaj_root(SKRYPT_SPRZATANIA, ["obrazy", "-"], "obrazy w starym systemie")
                zrobione.append("obrazy w starym systemie")
                start = True
            if self.plik_kopii.is_file() and self.zgoda(
                    f"Stare dane {z.lokalny} usunąć na stałe? Kopia {self.plik_kopii} zostaje (to ostatnia kopia "
                    "starych danych)."):
                self._wykonaj_root(SKRYPT_SPRZATANIA, ["dane", z.lokalny], f"usunięcie {z.lokalny}")
                zrobione.append(z.lokalny)
                start = True
            if z.wolumen and self.plik_kopii.is_file() and self.zgoda(
                    f"Wolumen danych starej floty {z.wolumen} usunąć na stałe? Kopia {self.plik_kopii} zostaje."):
                wynik = self._wykonaj_root(SKRYPT_SPRZATANIA, ["wolumen", z.wolumen], f"usunięcie {z.wolumen}")
                if wynik.get("blad"):
                    self.s.wypisz(f"  Wolumen {z.wolumen} został: {', '.join(wynik['blad'])} (Docker w dystrybucji "
                                  "wyłączony albo wolumen w użyciu).")
                else:
                    zrobione.append(f"wolumen {z.wolumen}")
                start = True
            if z.rodzaj == "wsl":
                if start:
                    self._terminate()
                self.s.wypisz(f"  Dysk ext4.vhdx dystrybucji {z.dystrybucja} sam się nie zmniejszy: `wsl --manage "
                              f"{z.dystrybucja} --set-sparse true` albo Optimize-VHD. Repo ~/jarvo i ~/TARS to osobna "
                              "decyzja.")
        if z is not None and z.rodzaj == "wolumen":
            docker = self.s.program("docker")
            if docker and self.zgoda(f"Wolumeny starej floty usunąć ({WOLUMEN}, jarvo-build, jarvo-valkey-data)? "
                                     f"Kopia {self.plik_kopii} zostaje."):
                self.s.uruchom([docker, "volume", "rm", WOLUMEN, "jarvo-build", "jarvo-valkey-data"], czas=300)
                zrobione.append("wolumeny")
            colima = self.s.program("colima")
            if colima and (Path(z.lokalny) / ".colima").is_file() and self.zgoda(
                    "Maszynę wirtualną Colimy usunąć razem z dyskiem (`colima delete --data`, ok. 10 GB)?"):
                self.s.uruchom([colima, "delete", "--data", "-f"], czas=600)
                zrobione.append("Colima")
        self._dziennik("R", "sprzatanie", zrobione=zrobione)
        self.stan.d["sprzatanie"] = {"czas": _teraz_iso(), "zrobione": zrobione}
        self.stan.zapisz()
        self.s.wypisz("Sprzątanie: " + (", ".join(zrobione) if zrobione else "nic (bez zgody na żadną pozycję)") + ".")
        return 0


# ================================================================ polecenie

def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jarvo migruj", description="Migracja ze starej instalacji z Dockerem i WSL do "
                                "instalacji natywnej (docs/NATYWNIE.md, sekcja f). Przed każdą zmianą pyta o zgodę; "
                                "drugi przebieg niczego nie zmienia.")
    tryb = p.add_mutually_exclusive_group()
    tryb.add_argument("--tylko-wykryj", action="store_true", help="tylko raport o starej instalacji (bez zmian)")
    tryb.add_argument("--wycofaj", action="store_true", help="powrót do starej floty (natywny Jarvo stanie)")
    tryb.add_argument("--sprzatanie", action="store_true",
                      help=f"sprzątanie starej instalacji po okresie przejściowym ({OKRES_PRZEJSCIOWY_DNI} dni)")
    tryb.add_argument("--wznow-rutyny", action="store_true", help="wznów rutyny wstrzymane przez migrację")
    tryb.add_argument("--manifest", metavar="KATALOG", help="manifest katalogu danych (test migracji w CI)")
    tryb.add_argument("--porownaj", nargs=2, metavar=("PRZED", "PO"), help="porównanie dwóch manifestów")
    p.add_argument("--tak", action="store_true", help="zgoda na każdy krok (bez pytań)")
    p.add_argument("--katalog", help="kopia, kopia zapasowa i raport (domyślnie <korzeń>/migracja)")
    p.add_argument("--dystrybucja", default="", help="Windows: dystrybucja WSL ze starą flotą")
    p.add_argument("--uzytkownik", default="", help="użytkownik Linuksa ze starą instalacją")
    p.add_argument("--wylacz-docker", action="store_true", help="WSL: wyłącz też Dockera w dystrybucji (U5)")
    p.add_argument("--linger", choices=("auto", "tak", "nie"), default="auto",
                   help="linger użytkownika w WSL: auto = wyłącz, gdy nic innego go nie potrzebuje")
    p.add_argument("--lan", action="store_true", help="przenieś też DASHBOARD_* (tryb LAN panelu, I11)")
    p.add_argument("--bez-floty", action="store_true", help="bez buildu i instalacji floty po imporcie")
    p.add_argument("--bez-startu", action="store_true", help="bez pierwszego startu (serwis zostaje zatrzymany)")
    p.add_argument("--bez-okresu", action="store_true", help="--sprzatanie przed końcem okresu przejściowego")
    p.add_argument("--filtr", action="store_true", help="--manifest: z regułami kopii (stare dane)")
    p.add_argument("--wyjscie", help="--manifest: zapis do pliku zamiast na ekran")
    p.add_argument("--stan", help="--porownaj: <stan>/migracja.json (przepisane pliki i mapa ścieżek)")
    p.add_argument("--json", action="store_true", help="--tylko-wykryj: wynik w JSON")
    return p


def main(argv: list[str] | None = None, *, uklad: Uklad | None = None, otoczenie: Any = None,
         system: SystemMigracji | None = None, natywne: Natywne | None = None) -> int:
    """`jarvo migruj …`. Kod wyjścia: 0 gotowe albo nic do zrobienia, 1 błąd (dane starej instalacji nietknięte),
    2 złe argumenty, 3 brak zgody właściciela (można wznowić tym samym poleceniem)."""
    try:
        a = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    except SystemExit as e:                       # --help albo złe argumenty: argparse już wypisał komunikat
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 2)
    # polecenie jarvo podaje swoje Otoczenie: te same zmienne (np. JARVO_ROOT z --korzen) co reszta poleceń
    s = system or SystemMigracji(env=dict(getattr(otoczenie, "env", None) or os.environ))
    if a.manifest:
        dane = manifest(Path(a.manifest), filtr=a.filtr)
        tekst = _json(dane)
        if a.wyjscie:
            przenosne.zapisz_atomowo(Path(a.wyjscie), tekst)
        else:
            s.wypisz(tekst.rstrip("\n"))
        return 0
    if a.porownaj:
        przed, po = (json.loads(Path(x).read_text(encoding="utf-8")) for x in a.porownaj)
        stan = json.loads(Path(a.stan).read_text(encoding="utf-8")) if a.stan else {}
        roznice = porownaj(przed, po, przepisane=stan.get("przepisane") or [], mapa=stan.get("mapa") or {},
                           bez={*NATYWNE_ZOSTAJA, *(stan.get("pominiete_dowiazania") or [])},
                           duplikaty=stan.get("duplikaty") or {})
        for r in roznice:
            s.wypisz(f"  {r}")
        s.wypisz("Manifesty zgodne." if not roznice else f"Różnice: {len(roznice)}.")
        return 0 if not roznice else 1
    try:
        u = uklad or sciezki.uklad(s.env)
    except sciezki.BladUkladu as e:
        s.wypisz(f"BŁĄD: {e}")
        return 1
    if a.tylko_wykryj:
        w = wykryj(s, u, dystrybucja=a.dystrybucja, uzytkownik=a.uzytkownik)
        s.wypisz(json.dumps(asdict(w), ensure_ascii=False, indent=2) if a.json else opis_wykrycia(w))
        return 0
    n = natywne or natywne_domyslne(otoczenie, log=s.wypisz)
    o = Opcje(tak=a.tak or s.env.get("JARVO_YES") == "1", katalog=a.katalog, dystrybucja=a.dystrybucja,
              uzytkownik=a.uzytkownik, wylacz_docker=a.wylacz_docker, linger=a.linger, lan=a.lan,
              bez_floty=a.bez_floty, bez_startu=a.bez_startu)
    m = Migracja(u, s, n, o)
    try:
        if a.wycofaj:
            return m.wycofaj()
        if a.sprzatanie:
            return m.sprzataj(bez_okresu=a.bez_okresu)
        if a.wznow_rutyny:
            return m.wznow_rutyny()
        return m.migruj()
    except Odmowa as e:
        s.wypisz(f"Bez zgody na: {e}\nNic więcej nie zmieniłem. To samo polecenie wznowi migrację od tego miejsca.")
        return 3
    except BladMigracji as e:
        m.wypisz(f"BŁĄD: {e}")
        return 1
    except Exception as e:                        # noqa: BLE001 - jak cli.main: komunikat zamiast śladu stosu
        if s.env.get("JARVO_DEBUG") == "1":
            raise
        m.wypisz(f"BŁĄD: {type(e).__name__}: {e} (pełny ślad: JARVO_DEBUG=1). Stara instalacja i kopia zostają; "
                 "to samo polecenie wznowi migrację od przerwanego etapu.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
