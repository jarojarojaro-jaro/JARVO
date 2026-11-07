#!/usr/bin/env python3
"""Skarbiec wiedzy floty Jarvo (drugi mózg): narzędzie bez zależności poza biblioteką standardową.

Skarbiec to katalog zwykłych plików Markdown (projekt: docs/WIEDZA.md). Ten skrypt:
  zasiej      katalogi, SCHEMA.md, huby (z fleet.json), INDEX, LOG, orzeczenia, docs repo i pliki profili (SOUL, README,
              CHANGELOG, rubryka, materiały skilli, spis źródeł) → zrodla/jarvo-repo, git init, indeks i wektory
  indeksuj    indeks FTS5 (state/wiedza.db), INDEX.md i listy w hubach z plików (0 tokenów, deterministycznie), wektory
              nowych i zmienionych notatek (gdy działa usługa wiedza/wektory.py)
  szukaj      wyszukiwanie po polsku (ogonki bez znaczenia, aliasy notatek): wektory (albo hybryda z BM25, --silnik),
              a bez usługi wektorów same słowa (BM25); wynik: ścieżka · streszczenie
  czytaj      cała notatka
  zapisz      szkic do skrzynka/ (agent nie pisze notatek sam: zasada 9 schematu)
  orzeczenie  jedna datowana linia w orzeczenia/<kogo>.md (tylko od człowieka)
  lint        raport LINT.md (martwe linki, sieroty, brak źródła, sekrety, duplikaty, przeterminowane…)
  graf        węzły i linki jako JSON (zakładka „Wiedza”)
  cofnij      cofa ostatni punkt zapisu git
  status      liczby (także wektory i stan usługi)
  ocena       trafność przypomnień na zestawie pytań (hit@5, MRR, ms) dla silnika hybryda | wektory | slowa

Używane przez wtyczkę jarvo-wiedza (import), rutyny (CLI), `jarvo wiedza` (jarvo/wiedza_cli.py), testy
(tests/test_wiedza.py). Domyślne ścieżki: JARVO_KNOWLEDGE_DIR, a bez niej <dane>/jarvo/knowledge, gdzie <dane> to
HERMES_HOME (profil: dwa katalogi wyżej), bez HERMES_HOME domyślny korzeń Jarva (docs/NATYWNIE.md c1; w kontenerze
/opt/data), i JARVO_STATE_DIR (albo <skarbiec>/../state).
Przenośność (docs/NATYWNIE.md K01, K07): notatki zawsze z LF, git w UTF-8 bez zamiany końców linii, zamiana pliku
ponawiana, gdy na Windows trzyma go inny program, na Windows nazwy bez „:”, „\\” i nazw urządzeń (CON, NUL…), na macOS
ścieżki w NFC. Lint zgłasza nazwy, które nie przejdą na inny system (nazwy urządzeń Windows, kropka albo spacja na
końcu, zapis spoza NFC, ta sama nazwa inną wielkością liter, ścieżka dłuższa niż 240 znaków) i zapisuje podsumowanie
w state/wiedza-lint.json (czyta je `jarvo doctor`, który sam niczego nie zapisuje).
Jeden piszący (§6): `Blokada` = blokada systemu (msvcrt na Windows, fcntl na POSIX) na state/wiedza.zamek i znacznik
state/wiedza.lock z PID-em i czasem (ten sam format czyta i stawia scripts/install_fleet.py przy zasiewie).
Wektory (docs/WIEDZA.md §7, W4): model e5-small działa w osobnej usłudze (wiedza/wektory.py, venv narzędzi), a ten
plik zostaje przy bibliotece standardowej: KlientWektorow pyta ją po HTTP na 127.0.0.1 z tokenem ze state/wektory.json,
wektory notatek leżą w tabeli `wektory` w state/wiedza.db, iloczyn skalarny liczy czysty Python.
"""
from __future__ import annotations

import argparse
import array
import base64
import contextlib
import datetime as dt
import hashlib
import http.client
import json
import math
import operator
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

WINDOWS = os.name == "nt"
MACOS = sys.platform == "darwin"


def _domyslny_skarbiec() -> str:
    """JARVO_KNOWLEDGE_DIR; bez niej <dane>/jarvo/knowledge, gdzie <dane> to HERMES_HOME (profil: dwa katalogi wyżej),
    a bez HERMES_HOME domyślny korzeń Jarva: %LOCALAPPDATA%\\Jarvo\\dane, ~/.jarvo/dane, w kontenerze /opt/data,
    na Linuksie natywnie ${XDG_DATA_HOME:-~/.local/share}/jarvo/dane (jarvo/sciezki.py)."""
    if os.environ.get("JARVO_KNOWLEDGE_DIR"):
        return os.environ["JARVO_KNOWLEDGE_DIR"]
    if os.environ.get("HERMES_HOME"):
        dane = Path(os.environ["HERMES_HOME"])
        dane = dane.parent.parent if dane.parent.name == "profiles" else dane
    elif os.environ.get("JARVO_ROOT"):
        dane = Path(os.environ["JARVO_ROOT"]).expanduser() / "dane"
    elif WINDOWS:
        dane = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Jarvo" / "dane"
    elif MACOS:
        dane = Path.home() / ".jarvo" / "dane"
    elif Path("/opt/data").is_dir():
        return "/opt/data/jarvo/knowledge"
    else:
        dane = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "jarvo" / "dane"
    return str(dane / "jarvo" / "knowledge")


DOMYSLNY_SKARBIEC = _domyslny_skarbiec()

FOLDERY = ("zrodla/rozmowy", "zrodla/karty", "zrodla/pliki", "zrodla/jarvo-repo", "skrzynka/zrobione", "agenci",
           "projekty", "brands", "inspiracje/strony", "user", "podmioty", "pojecia", "orzeczenia/marki", "rozmowy", "fleet")
# folder → (nazwa pliku huba, tytuł)
HUBY = {"": ("_hub-skarbiec", "Skarbiec wiedzy"), "agenci": ("_hub-agenci", "Agenci"), "projekty": ("_hub-projekty", "Projekty"),
        "brands": ("_hub-marki", "Marki"), "inspiracje": ("_hub-inspiracje", "Inspiracje"), "user": ("_hub-ty", "Ty"),
        "podmioty": ("_hub-podmioty", "Podmioty"), "pojecia": ("_hub-pojecia", "Pojęcia"), "orzeczenia": ("_hub-orzeczenia", "Orzeczenia"),
        "rozmowy": ("_hub-rozmowy", "Rozmowy")}
OPISY_FOLDEROW = {
    "agenci": "Jeden katalog na agenta: hub (rola, skille, skrypty z `fleet.yaml`) i notatki o tym, czego się nauczył.",
    "projekty": "Jedna notatka na misję albo projekt: stan, decyzje, wyniki (linki do plików), marka, agenci.",
    "brands": "Brand kity (`brands/<marka>/`): kolory, fonty, ton. Orzeczenia marki: `orzeczenia/marki/<marka>.md`.",
    "inspiracje": ("Strony referencyjne branż słabo pokrytych w katalogu Inspo (`inspiracje/strony/<branża>/<domena>`): układ, "
                   "paleta, fonty, zrzuty; pisze Web skillem `inspiracje-stron`. Inspiracja, nie wzór do kopiowania."),
    "user": "Kim jesteś, czym się zajmujesz, oferta, klienci, głos marki (`user/USER.md` z wywiadu Jarva).",
    "podmioty": "Firmy, ludzie w rolach publicznych, narzędzia, konkurenci, dostawcy: jedna notatka na rzecz.",
    "pojecia": "Metody, wzorce, definicje, lekcje ogólne: jedna notatka na pojęcie.",
    "orzeczenia": "Korekty od człowieka, jedna datowana linia każda. Agent dostaje swoje orzeczenia przed każdą turą.",
    "rozmowy": "Skompilowane ustalenia z rozmów i kart: decyzje, fakty, pliki. Surowe wyciągi leżą w `zrodla/rozmowy/`.",
}
POZA_WYSZUKIWANIEM = ("zrodla/", "skrzynka/")          # domyślnie nie wracają w wynikach (surowe i szkice)
LUSTRO_REPO = "zrodla/jarvo-repo"                     # kopia repo przy wdrożeniu: poza wyszukiwaniem, ale w grafie
LUSTRO_KATALOGI = ("profiles", "shared", "vendor")     # podkatalogi z `--repo` (płaskie *.md obok to docs/)
PLIKI_SPECJALNE = {"INDEX.md", "LOG.md", "LINT.md", "SCHEMA.md"}
# własne formaty (brand kit, karta strony referencyjnej z DESIGN.md dembrandta, USER.md, źródła, szkice)
BEZ_FRONTMATTERU = ("brands/", "inspiracje/", "user/", "zrodla/", "skrzynka/")
TYPY = {"hub", "agent", "projekt", "podmiot", "pojecie", "fakt", "decyzja", "lekcja", "zrodlo", "rozmowa", "orzeczenia", "skill"}
STATUSY = {"aktualna", "do-sprawdzenia", "sprzeczna", "przestarzala", "generowane"}
WYMAGANE = ("typ", "utworzono", "zmieniono", "status")
BEZ_ZRODLA = {"hub", "agent", "orzeczenia", "skill"}         # generowane z repo i floty (linki robi zasiew)
SKILLE = "fleet/skille"                                       # skill floty = węzeł grafu (zasiew z fleet.json)
# notatki o samej flocie (nie o klientach): ich odwołania do skryptów lint porównuje z repo (state/wiedza-kod.json)
O_FLOCIE = ("agenci/", "pojecia/", "fleet/", "orzeczenia/")
SKRYPT_RE = re.compile(r"`(?:[^`\s]*/)?([\w-]+\.(?:py|sh|js|cjs|mjs))\b[^`]*`")
MAX_SLOW = {"hub": 400, "agent": 600, "projekt": 400}
DOMYSLNY_MAX_SLOW = 250
GEN_RE = re.compile(r"<!-- Jarvo:GEN (\w+) -->.*?<!-- /Jarvo:GEN \1 -->", re.S)
LISTA_RE = re.compile(r"<!-- Jarvo:GEN lista -->.*?<!-- /Jarvo:GEN lista -->", re.S)   # same linki: poza indeksem
# limit długości (lint) liczy tylko treść pisaną: bloki GEN (lista notatek, rejestr floty) robi zasiew, nie autor
LINK_RE = re.compile(r"\[\[([^\]\|#]+)(#[^\]\|]*)?(?:\|([^\]]*))?\]\]")
ZAKAZANE_W_NAZWIE = set('*"\\/<>:|?#^[]')            # Obsidian i Windows nie przyjmą takiej nazwy
DATA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STOPSLOWA = {"i", "a", "w", "z", "na", "do", "to", "że", "ze", "się", "sie", "nie", "jak", "co", "czy", "dla", "od", "po",
             "przez", "jest", "są", "sa", "the", "and", "or", "of", "for", "mi", "mnie", "ten", "ta", "te", "ale", "oraz", "o",
             "kto", "we", "gdzie", "kiedy", "czym", "który", "która", "które", "ktory", "ktora", "ktore", "jaki", "jaka", "jakie",
             "ma", "mam", "masz", "być", "byc", "był", "była", "było", "będzie", "bedzie", "ich", "jego", "jej", "nam", "nas", "moja", "mój", "moje"}
MAX_SLOW_ZAPYTANIA = 12          # słów w zapytaniu FTS5; dłuższe pytanie zostawia najrzadsze (Indeks.slowa_informacyjne)
MAX_SLOW_OCENIANYCH = 60         # tyle pierwszych słów długiego pytania liczymy w indeksie
# wektory (docs/WIEDZA.md §7, decyzja W4): jeden ciepły model e5-small na instalację w usłudze wiedza/wektory.py
WEKTORY_STAN = "wektory.json"     # state/: port, token, model i PID usługi (pisze ją usługa przy starcie, czytają klienci)
WEKTORY_CZAS_S = 0.3              # przypomnienie przed turą: tyle czeka na wektor pytania, potem same słowa (BM25)
WEKTORY_CZAS_NARZEDZIA_S = 2.0    # wiedza_szukaj i kandydaci kompilacji (poza turą rozmowy)
WEKTORY_CZAS_ZAPISU_S = 120.0     # osadzanie notatek (indeksuj, kompilacja, zasiew): jedna paczka
WEKTORY_PACZKA = 8                # notatek na jedno wywołanie usługi (zapytanie z tury nie czeka za długą paczką)
MAX_ZNAKOW_WEKTORA = 1200         # treści notatki w tekście wektora, po tytule i streszczeniu
DLUGIE_ZAPYTANIE = 25             # słów: dłuższe pytanie idzie zdaniami, wynik notatki = najlepsze zdanie
MAX_ZDAN = 8                      # zdań długiego pytania (pierwsze; każde to osobny wektor)
MIN_SLOW_ZDANIA = 3               # krótszy kawałek długiego pytania (nagłówek, „Tak.”) nie dostaje wektora
WEKTOROW_W_RANKINGU = 30
RRF_K = 60                        # miejsce na liście → punkty 1 / (k + pozycja) (Reciprocal Rank Fusion)
SILNIKI = ("wektory", "hybryda", "slowa")
# wybór pomiarem `wiedza.py ocena` na zestawie syntetycznym tests/data/wiedza-ocena.json (2026-11-08, 33 pytania):
# wektory hit@5 32/33, MRR 0,83; hybryda RRF 28/33, 0,77; słowa 25/33, 0,66 (docs/WIEDZA.md §7)
SILNIK = "wektory"
MAX_ALIASOW = 8                   # aliasów jednej notatki (frontmatter `aliasy:`)
MAX_DOPISKOW_ALIASOW = 5          # tytułów dopisanych do jednego zapytania
WERSJA_INDEKSU = "2"              # 2: aliasy i wektory; inna wersja w bazie = jedno pełne odświeżenie indeksu
HUB_AGENTA_RE = re.compile(r"^agenci/[^/]+/_hub-[^/]+$")
SEKRETY = [
    ("klucz Stripe", re.compile(r"\bsk_(live|test)_[A-Za-z0-9]{8,}")),
    ("klucz OpenAI/Anthropic", re.compile(r"\bsk-(ant-)?[A-Za-z0-9_-]{20,}")),
    ("klucz AWS", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("token GitHub", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("token Slack", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("klucz Google", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}")),
    ("klucz prywatny", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("hasło w tekście", re.compile(r"(?i)\b(has[łl]o|password|passwd)\s*[:=]\s*\S{4,}")),
    ("klucz API w tekście", re.compile(r"(?i)\b(api[_ -]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_\-]{16,}")),
]
GIT_TOZSAMOSC = ["-c", "user.name=Jarvo", "-c", "user.email=jarvo@localhost", "-c", "commit.gpgsign=false"]
# pliki w historii bajt w bajt jak na dysku (bez CRLF z core.autocrlf=true Git for Windows), długie ścieżki na Windows;
# automatyczne porządki gita po commicie od razu, nie w tle: nowy git (macOS) pakował obiekty w odłączonym procesie,
# który zostawał po poleceniu (zmieniał skarbiec po `jarvo doctor`, na Windows trzymałby pliki przy deinstalacji)
GIT_PRZENOSNIE = ["-c", "core.autocrlf=false", "-c", "core.longpaths=true", "-c", "gc.autoDetach=false",
                  "-c", "maintenance.autoDetach=false"]
# .gitignore skarbca: *.tmp (zapis atomowy) i śmieci menedżera plików tego systemu (Finder, Eksplorator)
GITIGNORE_SYSTEMU = (".DS_Store",) if MACOS else ("Thumbs.db", "desktop.ini") if WINDOWS else ()
BEZ_OKNA = getattr(subprocess, "CREATE_NO_WINDOW", 0)            # Windows: git bez migającego okna konsoli
ZAJETY_PLIK = (5, 32, 33)          # WinError: odmowa dostępu, plik otwarty przez inny proces, zablokowany fragment
PROBY_ZAMIANY = 10
# nazwy urządzeń Windows: „con.md” otwiera konsolę, „nul.md” połyka zapis (także z rozszerzeniem i spacją przed kropką)
ZAREZERWOWANE = frozenset({"con", "prn", "aux", "nul", "conin$", "conout$", *(f"com{i}" for i in range(1, 10)),
                           *(f"lpt{i}" for i in range(1, 10))})
MAX_SCIEZKI = 240                  # pełna ścieżka pliku: Windows bez LongPathsEnabled nie otworzy dłuższej niż 260 (K07)
# jeden piszący skarbca (docs/WIEDZA.md §6): znacznik z PID-em i czasem (czyta go też scripts/install_fleet.py, zasiew
# przy wdrożeniu) i osobny plik blokady systemu: na Windows bajt zablokowany przez msvcrt nie da się nawet przeczytać,
# więc znacznika samego nie blokujemy
ZNACZNIK_BLOKADY = "wiedza.lock"
PLIK_ZAMKA = "wiedza.zamek"
BLOKADA_STARA_S = 2 * 3600         # starszy znacznik to resztka po awarii (jak w install_fleet.py)
LINT_JSON = "wiedza-lint.json"     # state/: podsumowanie ostatniego lintu dla `jarvo doctor` i statusu


def dzis() -> str:
    return os.environ.get("WIEDZA_DZIS") or dt.date.today().isoformat()


def zamien_plik(zrodlo: str | Path, cel: str | Path) -> None:
    """os.replace, ponawiane przez ok. 2 s, gdy na Windows plik trzyma inny program (Obsidian, antywirus, indeksowanie:
    WinError 5, 32, 33). Na POSIX takiego błędu nie ma, więc to zwykłe os.replace."""
    for proba in range(PROBY_ZAMIANY):
        try:
            os.replace(zrodlo, cel)
            return
        except PermissionError as e:
            if getattr(e, "winerror", None) not in ZAJETY_PLIK or proba == PROBY_ZAMIANY - 1:
                raise
            time.sleep(0.05 * (proba + 1))


def pid_zyje(pid: int) -> bool:
    """Czy proces o tym PID-zie działa (znacznik blokady bez żywego właściciela to resztka po awarii), jak w
    scripts/install_fleet.py: POSIX kill(pid, 0), Windows OpenProcess + GetExitCodeProcess (STILL_ACTIVE)."""
    if pid <= 0:
        return False
    if not WINDOWS:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    uchwyt = k32.OpenProcess(0x1000, False, pid)              # PROCESS_QUERY_LIMITED_INFORMATION
    if not uchwyt:
        return ctypes.get_last_error() == 5                   # odmowa dostępu: proces jest, tylko cudzy
    try:
        kod = wintypes.DWORD()
        return bool(k32.GetExitCodeProcess(uchwyt, ctypes.byref(kod))) and kod.value == 259    # STILL_ACTIVE
    finally:
        k32.CloseHandle(uchwyt)


def znacznik_blokady(stan: str | Path) -> dict | None:
    """Znacznik state/wiedza.lock: {"pid", "wiek_s", "zywy", "aktualny"} albo None (brak). `aktualny` = blokuje: proces
    żyje, a znacznik jest młodszy niż BLOKADA_STARA_S; inaczej to resztka po awarii."""
    p = Path(stan) / ZNACZNIK_BLOKADY
    try:
        tresc = p.read_text(encoding="utf-8", errors="replace").split()
        wiek = max(0.0, time.time() - p.stat().st_mtime)
    except OSError:
        return None
    pid = int(tresc[0]) if tresc and tresc[0].isdigit() else 0
    zywy = pid_zyje(pid)
    return {"pid": pid, "wiek_s": round(wiek, 1), "zywy": zywy, "aktualny": zywy and wiek < BLOKADA_STARA_S}


def _sprobuj_zamek(f) -> bool | None:
    """Jedna próba blokady systemu bez czekania: True wzięta, False zajęta, None system plików bez blokad."""
    try:
        if WINDOWS:
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (BlockingIOError, PermissionError):     # POSIX: EWOULDBLOCK, Windows: EACCES
        return False
    except OSError:
        return None


class Blokada:
    """Jeden piszący skarbca (kompilacja: wątek bramy, przycisk w panelu, `jarvo wiedza kompiluj`). Blokada systemu
    (msvcrt.locking, fcntl.flock) na state/wiedza.zamek wyklucza drugi przebieg także w tym samym procesie (każde
    `wez()` ma własny uchwyt) i znika sama, gdy proces padnie. Znacznik state/wiedza.lock („PID czas”) widzi zasiew
    z scripts/install_fleet.py, który blokady systemu nie zna: czeka na żywy znacznik i stawia własny. Dlatego po
    wzięciu blokady żywy, świeży znacznik innego właściciela (wdrożenie w toku) też oznacza „zajęte”."""

    def __init__(self, stan: str | Path, czekaj_s: float = 0.0):
        self.stan = Path(stan)
        self.czekaj_s = czekaj_s
        self._f = None
        self._moj = ""
        self.powod = ""

    def wez(self) -> bool:
        try:
            self.stan.mkdir(parents=True, exist_ok=True)
            f = open(self.stan / PLIK_ZAMKA, "a+b")
        except OSError as e:
            self.powod = f"brak zapisu w {self.stan} ({e.strerror or e})"
            return False
        koniec = time.monotonic() + self.czekaj_s
        wynik = _sprobuj_zamek(f)
        if wynik is False and WINDOWS:
            # Windows zwalnia blokadę zakresu pliku zmarłego procesu z opóźnieniem („zależnie od dostępnych zasobów
            # systemu”, dokumentacja LockFileEx): przy znaczniku martwego właściciela chwilę czekamy, zamiast mówić
            # „inna kompilacja trwa” o procesie, którego już nie ma
            z = znacznik_blokady(self.stan)
            if z and z.get("zywy") is False:
                koniec = max(koniec, time.monotonic() + 5.0)
        while wynik is False and time.monotonic() < koniec:
            time.sleep(0.05)
            wynik = _sprobuj_zamek(f)
        if wynik is False:
            f.close()
            self.powod = "inna kompilacja trwa"
            return False
        self._f = f
        z = znacznik_blokady(self.stan)
        if z and z["aktualny"]:
            self._zwolnij_zamek()
            self.powod = f"skarbiec zajęty (proces {z['pid']}, np. zasiew przy wdrożeniu)"
            return False
        self._moj = f"{os.getpid()} {int(time.time())}\n"
        p = self.stan / ZNACZNIK_BLOKADY
        tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
        try:
            tmp.write_text(self._moj, encoding="utf-8", newline="\n")
            zamien_plik(tmp, p)
        except OSError as e:
            with contextlib.suppress(OSError):
                tmp.unlink()
            self._zwolnij_zamek()
            self.powod = f"nie zapiszę znacznika {p} ({e.strerror or e})"
            return False
        return True

    def zwolnij(self) -> None:
        p = self.stan / ZNACZNIK_BLOKADY
        if self._moj:
            with contextlib.suppress(OSError):
                if p.read_text(encoding="utf-8") == self._moj:     # cudzego znacznika (wdrożenie po awarii) nie ruszamy
                    p.unlink()
            self._moj = ""
        self._zwolnij_zamek()

    def _zwolnij_zamek(self) -> None:
        f, self._f = self._f, None
        if f is None:
            return
        try:
            if WINDOWS:
                import msvcrt
                with contextlib.suppress(OSError):
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            f.close()                                    # POSIX: zamknięcie zwalnia flock

    def __enter__(self) -> bool:
        return self.wez()

    def __exit__(self, *_exc) -> None:
        self.zwolnij()


def utf8_wyjscie() -> None:
    """Na Windows stdout i stderr w UTF-8 (✓, ✗, ogonki), także gdy wyjście idzie do pliku albo potoku, a nie do konsoli."""
    if not WINDOWS:
        return
    for strumien in (sys.stdout, sys.stderr):
        try:
            strumien.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


# ------------------------------------------------------------------------------------------------ frontmatter i tekst

def podziel(text: str) -> tuple[dict, str]:
    """Frontmatter (proste `klucz: wartość`, listy `[a, b]`, cudzysłowy) i treść. Bez YAML-a, bo schemat go nie potrzebuje."""
    if not text.startswith("---\n"):
        return {}, text
    koniec = text.find("\n---", 4)
    if koniec < 0:
        return {}, text
    naglowek, tresc = text[4:koniec], text[koniec + 4:]
    tresc = tresc[1:] if tresc.startswith("\n") else tresc
    fm: dict = {}
    for linia in naglowek.splitlines():
        if not linia.strip() or linia.lstrip().startswith("#") or linia[:1] in " \t":
            continue
        klucz, sep, wart = linia.partition(":")
        if sep:
            fm[klucz.strip()] = _wartosc(wart.strip())
    return fm, tresc


def _wartosc(v: str):
    if v.startswith("[") and v.endswith("]"):
        return [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1]
    if v in ("true", "false"):
        return v == "true"
    return v


def sklej(fm: dict, tresc: str) -> str:
    linie = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            linie.append(f"{k}: [{', '.join(str(x) for x in v)}]")
        elif isinstance(v, bool):
            linie.append(f"{k}: {'true' if v else 'false'}")
        else:
            s = str(v)
            if s == "" or any(c in s for c in ":#{}\"'") or s != s.strip():
                s = '"' + s.replace('"', '\\"') + '"'
            linie.append(f"{k}: {s}")
    linie.append("---")
    return "\n".join(linie) + "\n" + tresc.lstrip("\n")


def bez_ogonkow(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).replace("ł", "l").replace("Ł", "L")


def _nfc(rel: str) -> str:
    """Ścieżka z dysku w NFC na macOS: nazwa zapisana w NFD (stare HFS+, niektóre programy) ma pasować do linków w notatkach.
    APFS szuka plików bez względu na normalizację; na Linuksie i Windows NFC i NFD to różne nazwy, więc bez zmian."""
    return unicodedata.normalize("NFC", rel) if MACOS else rel


def nazwa_pliku(tytul: str) -> str:
    """Tytuł, jak się go mówi → nazwa pliku: małe litery, polskie znaki (w NFC) i spacje zostają, bez znaków
    zakazanych, kropki i spacji na końcu i bez nazw urządzeń Windows („con” → „con (notatka)”), więc plik przejdzie
    na każdy system (K07)."""
    s = unicodedata.normalize("NFC", tytul).strip().lower()
    s = "".join(c if (c.isalnum() or c in " ,-.()") else " " for c in s)
    s = re.sub(r"\s+", " ", s).strip(" .-")
    s = s[:70].rstrip(" .-") or "notatka"
    return f"{s} (notatka)" if urzadzenie_windows(s) else s


def urzadzenie_windows(nazwa: str) -> bool:
    """Nazwa urządzenia Windows (CON, NUL, COM1…), także z rozszerzeniem i spacją przed kropką („nul .md”)."""
    return nazwa.split(".", 1)[0].strip().lower() in ZAREZERWOWANE


def nieprzenosna(czesc: str) -> str | None:
    """Powód, dla którego ta część ścieżki (katalog albo plik z rozszerzeniem) nie przejdzie na każdy system, albo None."""
    if urzadzenie_windows(czesc):
        return "nazwa urządzenia Windows"
    if czesc != czesc.rstrip(". "):
        return "kropka albo spacja na końcu (Windows ją obetnie)"
    if unicodedata.normalize("NFC", czesc) != czesc:
        return "znaki zapisane spoza NFC (inny zapis polskich liter: link i nazwa się rozjadą)"
    return None


def slug_ascii(tytul: str, n: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", bez_ogonkow(tytul).lower()).strip("-")
    return s[:n].rstrip("-") or "szkic"


def zawiera_sekret(text: str) -> str | None:
    for nazwa, wzor in SEKRETY:
        if wzor.search(text):
            return nazwa
    return None


def bez_markdown(s: str) -> str:
    s = LINK_RE.sub(lambda m: (m.group(3) or m.group(1)).strip(), s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    return re.sub(r"[*_`]+", "", s).strip()


def zastap_blok(text: str, nazwa: str, tresc: str) -> str:
    """Wymienia blok `<!-- Jarvo:GEN nazwa -->…<!-- /Jarvo:GEN nazwa -->`; brak bloku = doklejony na końcu."""
    blok = f"<!-- Jarvo:GEN {nazwa} -->\n{tresc.strip()}\n<!-- /Jarvo:GEN {nazwa} -->"
    wzor = re.compile(rf"<!-- Jarvo:GEN {nazwa} -->.*?<!-- /Jarvo:GEN {nazwa} -->", re.S)
    if wzor.search(text):
        return wzor.sub(lambda _m: blok, text)
    return text.rstrip("\n") + "\n\n" + blok + "\n"


# ------------------------------------------------------------------------------------------------ notatka

@dataclass
class Notatka:
    sciezka: str                      # względem skarbca, bez `.md`, POSIX
    tytul: str
    streszczenie: str
    fm: dict
    tresc: str                        # bez frontmatteru
    linki: list = field(default_factory=list)   # (cel, etykieta, auto)
    slowa: int = 0
    mtime: float = 0.0
    rozmiar: int = 0

    @property
    def folder(self) -> str:
        return self.sciezka.split("/", 1)[0] if "/" in self.sciezka else ""

    @property
    def hub(self) -> bool:
        return self.sciezka.rsplit("/", 1)[-1].startswith("_hub-")

    @property
    def typ(self) -> str:
        return str(self.fm.get("typ") or ("hub" if self.hub else ""))


def _zwykly_cel(cel: str) -> bool:
    """Cel linku, który na pewno jest albo nie jest w `Skarbiec.pliki()` (bez sprawdzania dysku)."""
    czesci = cel.split("/")
    return (not cel.endswith(".md") and "\\" not in cel and cel + ".md" not in PLIKI_SPECJALNE
            and all(c and c not in (".", "..") and not c.startswith(".") and c != "_szablon" for c in czesci))


class Skarbiec:
    def __init__(self, root: str | Path, stan: str | Path | None = None):
        self.root = Path(root).resolve()
        self.stan = Path(stan).resolve() if stan else Path(os.environ.get("JARVO_STATE_DIR") or (self.root.parent / "state")).resolve()

    # ---- ścieżki
    def plik(self, rel: str) -> Path:
        """Bezpieczna ścieżka w skarbcu (bez `..`, bez symlinków na zewnątrz); `.md` dopisywane, gdy brak.
        Na Windows bez „:” (litera dysku, strumień NTFS zamiast pliku) i „\\” (drugi separator ścieżki)."""
        rel = rel.strip().lstrip("/")
        if WINDOWS and (":" in rel or "\\" in rel):
            raise ValueError(f"nazwa z „:” albo „\\” (Windows jej nie przyjmie): {rel}")
        if not rel.endswith(".md"):
            rel += ".md"
        if WINDOWS and any(urzadzenie_windows(c) for c in rel.split("/")):    # „nul.md” połknąłby zapis bez śladu
            raise ValueError(f"nazwa urządzenia Windows (CON, NUL, COM1…): {rel}")
        p = (self.root / rel).resolve()
        if p != self.root and self.root not in p.parents:
            raise ValueError(f"ścieżka poza skarbcem: {rel}")
        return p

    def rel(self, p: Path) -> str:
        return _nfc(p.relative_to(self.root).as_posix()[:-3])

    def pliki(self) -> list[str]:
        """Wszystkie notatki (bez katalogów z kropką i plików specjalnych), ścieżki bez `.md`."""
        out = []
        for p in self.root.rglob("*.md"):
            r = p.relative_to(self.root)
            if any(part.startswith(".") or part == "_szablon" for part in r.parts):   # katalogi z kropką i szablony (brands/_szablon)
                continue
            if len(r.parts) == 1 and r.name in PLIKI_SPECJALNE:
                continue
            if WINDOWS and any(urzadzenie_windows(part) for part in r.parts):   # „nul.md” ze skarbca z Linuksa: Win32
                continue                                                       # go nie otworzy; lint go zgłasza (K07)
            out.append(_nfc(r.as_posix()[:-3]))
        return sorted(out)

    def istnieje(self, rel: str) -> bool:
        try:
            return self.plik(rel).is_file()
        except ValueError:
            return False

    # ---- czytanie
    def wczytaj(self, rel: str) -> Notatka:
        p = self.plik(rel)
        text = p.read_text(encoding="utf-8", errors="replace")
        fm, tresc = podziel(text)
        m = re.search(r"^# (.+)$", tresc, re.M)
        tytul = bez_markdown(m.group(1)) if m else self.rel(p).rsplit("/", 1)[-1]
        streszczenie = ""
        if m:
            for linia in tresc[m.end():].splitlines():
                s = linia.strip()
                if not s and streszczenie:
                    break
                if s and not s.startswith(("#", "<!--", "|", "-", "```")):
                    streszczenie = (streszczenie + " " + bez_markdown(s)).strip()
        if not streszczenie:
            for linia in tresc.splitlines():
                s = linia.strip()
                if s and not s.startswith(("#", "<!--", "|", "-", "```", "---")):
                    streszczenie = bez_markdown(s)
                    break
        n = Notatka(sciezka=self.rel(p), tytul=tytul, streszczenie=streszczenie[:240], fm=fm, tresc=tresc,
                    slowa=len(re.findall(r"\w+", GEN_RE.sub("", tresc))), mtime=p.stat().st_mtime, rozmiar=p.stat().st_size)
        n.linki = self._linki(tresc)
        return n

    def _linki(self, tresc: str) -> list[tuple[str, str, bool]]:
        auto_zakresy = [(m.start(), m.end()) for m in GEN_RE.finditer(tresc)]
        out = []
        for m in LINK_RE.finditer(tresc):
            cel = m.group(1).strip()
            if cel.endswith(".md"):
                cel = cel[:-3]
            auto = any(a <= m.start() < b for a, b in auto_zakresy)
            out.append((cel, (m.group(3) or cel).strip(), auto))
        return out

    def mapa(self) -> tuple[set[str], dict[str, str]]:
        """Jedno przejście po dysku na wiele linków: zbiór ścieżek notatek i nazwa pliku → pierwsza ścieżka."""
        pliki = self.pliki()
        znane: dict[str, str] = {}
        for rel in pliki:
            znane.setdefault(rel.rsplit("/", 1)[-1], rel)
        return set(pliki), znane

    def rozwiaz(self, cel: str, znane: dict[str, str] | None = None, zbior: set[str] | None = None) -> str | None:
        """Cel linku → ścieżka notatki: pełna ścieżka albo (jak w Obsidianie) sama nazwa pliku, gdy jednoznaczna.

        Z `zbior` (z `mapa()`) zwykła ścieżka rozstrzyga się w pamięci; dysk tylko dla nietypowych celów
        (pliki specjalne, `.md` na końcu, katalogi z kropką, `..`)."""
        cel = cel.strip().lstrip("/")
        if zbior is not None and cel in zbior:
            return cel
        if (zbior is None or not _zwykly_cel(cel)) and self.istnieje(cel):
            return cel
        if "/" not in cel:
            return (znane if znane is not None else self.mapa()[1]).get(cel)
        return None

    # ---- pisanie
    def zapisz_plik(self, rel: str, text: str) -> Path:
        p = self.plik(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(text, encoding="utf-8", newline="\n")      # LF także na Windows (Obsidian, git, sumy)
        zamien_plik(tmp, p)
        return p

    def dopisz_log(self, rodzaj: str, tresc: str) -> None:
        p = self.root / "LOG.md"
        if not p.exists():
            p.write_text("# Dziennik skarbca\n\nTylko dopisywanie. Format: `## [data] rodzaj | co się stało`.\n",
                         encoding="utf-8", newline="\n")
        with p.open("a", encoding="utf-8", newline="\n") as f:
            f.write(f"\n## [{dzis()}] {rodzaj} | {tresc.strip()}\n")

    # ---- git (punkty zapisu)
    def git(self, *args: str) -> subprocess.CompletedProcess | None:
        """git w skarbcu; wyjście zawsze w UTF-8 (opisy z polskimi znakami, także na Windows z kodowaniem cp1250)."""
        try:
            return subprocess.run([shutil.which("git") or "git", *GIT_TOZSAMOSC, *GIT_PRZENOSNIE, "-C", str(self.root), *args],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=BEZ_OKNA)
        except FileNotFoundError:
            return None

    def git_init(self) -> bool:
        if (self.root / ".git").exists():
            self._gitignore_systemu()
            return True
        r = self.git("init", "-q")
        if r is None or r.returncode != 0:
            return False
        (self.root / ".gitignore").write_text("\n".join(("*.tmp", *GITIGNORE_SYSTEMU)) + "\n", encoding="utf-8", newline="\n")
        return True

    def _gitignore_systemu(self) -> None:
        """Skarbiec z innego systemu (np. przeniesiony z kontenera na Windows): brakujące śmieci tego systemu do .gitignore.
        Na Linuksie lista jest pusta, więc plik zostaje taki, jak go zostawił `git init`."""
        p = self.root / ".gitignore"
        try:
            stary = p.read_text(encoding="utf-8") if p.exists() else ""
            brak = [w for w in GITIGNORE_SYSTEMU if w not in stary.splitlines()]
            if brak:
                p.write_text(stary + ("" if not stary or stary.endswith("\n") else "\n") + "\n".join(brak) + "\n",
                             encoding="utf-8", newline="\n")
        except OSError:
            pass

    def punkt_zapisu(self, komunikat: str) -> bool:
        if not (self.root / ".git").exists():
            return False
        r = self.git("add", "-A")
        if r is None or r.returncode != 0:
            return False
        r = self.git("diff", "--cached", "--quiet")
        if r is not None and r.returncode == 0:
            return True   # nic nowego
        r = self.git("commit", "-q", "-m", komunikat)
        return r is not None and r.returncode == 0

    def cofnij(self) -> str:
        if not (self.root / ".git").exists():
            return "skarbiec nie ma punktów zapisu (brak git)"
        r = self.git("log", "-1", "--format=%s")
        ostatni = (r.stdout.strip() if r and r.returncode == 0 else "") or "?"
        r = self.git("revert", "--no-edit", "HEAD")
        if r is None or r.returncode != 0:
            return "nie udało się cofnąć: " + ((r.stderr or r.stdout).strip() if r else "brak git")
        return f"cofnięto punkt zapisu: {ostatni}"


# ------------------------------------------------------------------------------------------------ indeks FTS5

class Indeks:
    """SQLite poza skarbcem (state/wiedza.db): FTS5 z `remove_diacritics 2` (ogonki bez znaczenia), linki, metadane,
    aliasy notatek (frontmatter `aliasy:`) i wektory notatek (`wektory`: ścieżka, hash tekstu, id modelu, float32)."""

    def __init__(self, sk: Skarbiec):
        self.sk = sk
        sk.stan.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(sk.stan / "wiedza.db"), timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS pliki(sciezka TEXT PRIMARY KEY, mtime REAL, rozmiar INTEGER, tytul TEXT, streszczenie TEXT,
                typ TEXT, status TEXT, agent TEXT, folder TEXT, zmieniono TEXT, wazne_do TEXT, hub INTEGER, slowa INTEGER);
            CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(sciezka UNINDEXED, tytul, streszczenie, tresc, tagi,
                tokenize='unicode61 remove_diacritics 2');
            CREATE TABLE IF NOT EXISTS linki(z TEXT, do_ TEXT, etykieta TEXT, auto INTEGER, rozwiazany INTEGER);
            CREATE INDEX IF NOT EXISTS linki_do ON linki(do_);
            CREATE TABLE IF NOT EXISTS meta(klucz TEXT PRIMARY KEY, wartosc TEXT);
            CREATE TABLE IF NOT EXISTS aliasy(sciezka TEXT, alias TEXT, tytul TEXT);
            CREATE INDEX IF NOT EXISTS aliasy_sciezka ON aliasy(sciezka);
            CREATE TABLE IF NOT EXISTS wektory(sciezka TEXT PRIMARY KEY, hash TEXT, model TEXT, wektor BLOB, mtime REAL,
                rozmiar INTEGER);
        """)
        wersja = self.db.execute("SELECT wartosc FROM meta WHERE klucz = 'wersja'").fetchone()
        self._przebuduj = wersja is None or wersja[0] != WERSJA_INDEKSU      # indeks sprzed aliasów: raz od nowa
        self.silnik = "slowa"                   # silnik ostatniego szukaj(): hybryda | wektory | slowa (dziennik przypomnień)

    def zamknij(self) -> None:
        self.db.close()

    def odswiez(self, pelny: bool = False) -> dict:
        """Indeks przyrostowy po mtime i rozmiarze. Linki przeliczane w całości, ale tylko gdy coś się zmieniło
        (notatka, lista plików specjalnych) albo przy `pelny`; bez zmian odświeżenie to sam przegląd katalogów.
        Wektorów nie liczy (to robi odswiez_wektory przy indeksuj, kompilacji i zasiewie, poza turą rozmowy)."""
        pelny = pelny or self._przebuduj
        pliki = self.sk.pliki()
        zbior = set(pliki)
        specjalne = ",".join(sorted(n for n in PLIKI_SPECJALNE if (self.sk.root / n).is_file()))
        stare = {r["sciezka"]: (r["mtime"], r["rozmiar"]) for r in self.db.execute("SELECT sciezka, mtime, rozmiar FROM pliki")}
        nowe = zmienione = 0
        notatki: dict[str, Notatka] = {}
        with self.db:
            if pelny:                                    # DELETE po kolumnie UNINDEXED skanuje całe FTS: przy przebudowie raz
                self.db.execute("DELETE FROM fts")
                self.db.execute("DELETE FROM aliasy")
            for rel in pliki:
                p = self.sk.root / f"{rel}.md"           # z pliki(), więc w skarbcu: bez resolve() (na Windows otwiera plik)
                st = p.stat()
                if not pelny and rel in stare and stare[rel] == (st.st_mtime, st.st_size):
                    continue
                n = self.sk.wczytaj(rel)
                notatki[rel] = n
                nowe += rel not in stare
                zmienione += rel in stare
                if rel in stare and not pelny:           # nowa notatka nie ma wiersza w FTS (pliki i fts w jednej transakcji)
                    self.db.execute("DELETE FROM fts WHERE sciezka = ?", (rel,))
                self.db.execute("INSERT INTO fts(sciezka, tytul, streszczenie, tresc, tagi) VALUES (?,?,?,?,?)",
                                (rel, n.tytul, n.streszczenie, LISTA_RE.sub("", n.tresc), " ".join(n.fm.get("tagi") or []) if isinstance(n.fm.get("tagi"), list) else str(n.fm.get("tagi") or "")))
                self.db.execute("INSERT OR REPLACE INTO pliki VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (rel, n.mtime, n.rozmiar, n.tytul, n.streszczenie, n.typ, str(n.fm.get("status") or ""),
                                 str(n.fm.get("agent") or ""), n.folder, str(n.fm.get("zmieniono") or ""),
                                 str(n.fm.get("wazne_do") or ""), int(n.hub), n.slowa))
                if not pelny:
                    self.db.execute("DELETE FROM aliasy WHERE sciezka = ?", (rel,))
                for alias in aliasy_notatki(n):
                    self.db.execute("INSERT INTO aliasy VALUES (?,?,?)", (rel, alias, n.tytul))
            usuniete = [s for s in stare if s not in zbior]
            for s in usuniete:
                self.db.execute("DELETE FROM fts WHERE sciezka = ?", (s,))
                self.db.execute("DELETE FROM pliki WHERE sciezka = ?", (s,))
                self.db.execute("DELETE FROM aliasy WHERE sciezka = ?", (s,))
                self.db.execute("DELETE FROM wektory WHERE sciezka = ?", (s,))
            # linki: całość od nowa (potrzebne do lintu, grafu i rozszerzania wyników), gdy cokolwiek się zmieniło
            stan_linkow = self.db.execute("SELECT wartosc FROM meta WHERE klucz = 'linki'").fetchone()
            if pelny or nowe or zmienione or usuniete or stan_linkow is None or stan_linkow[0] != specjalne:
                znane: dict[str, str] = {}
                for rel in pliki:
                    znane.setdefault(rel.rsplit("/", 1)[-1], rel)
                self.db.execute("DELETE FROM linki")
                for rel in pliki:
                    n = notatki.get(rel) or self.sk.wczytaj(rel)
                    for cel, etykieta, auto in n.linki:
                        cel_r = self.sk.rozwiaz(cel, znane, zbior)
                        self.db.execute("INSERT INTO linki VALUES (?,?,?,?,?)", (rel, cel_r or cel, etykieta, int(auto), int(cel_r is not None)))
                self.db.execute("INSERT OR REPLACE INTO meta VALUES ('linki', ?)", (specjalne,))
            if self._przebuduj:
                self.db.execute("INSERT OR REPLACE INTO meta VALUES ('wersja', ?)", (WERSJA_INDEKSU,))
        self._przebuduj = False
        return {"pliki": len(pliki), "nowe": nowe, "zmienione": zmienione, "usuniete": len(usuniete)}

    @staticmethod
    def slowa(q: str) -> list[str]:
        """Słowa zapytania bez stopsłów i powtórzeń, w kolejności z pytania."""
        return list(dict.fromkeys(w for w in re.findall(r"\w+", q.lower()) if len(w) >= 2 and w not in STOPSLOWA))

    @staticmethod
    def zapytanie(q: str | list[str]) -> str:
        slowa = q if isinstance(q, list) else Indeks.slowa(q)[:MAX_SLOW_ZAPYTANIA]
        return " OR ".join(f'"{w}"*' for w in slowa)

    def slowa_informacyjne(self, q: str, n: int = MAX_SLOW_ZAPYTANIA) -> list[str]:
        """Do `n` słów zapytania. Dłuższe pytanie (zlecenie karty, prompt rutyny) zostawia słowa najrzadsze w skarbcu
        (liczba notatek z tym prefiksem w FTS5), w kolejności z pytania, zamiast pierwszych `n`; słowa bez żadnej
        notatki odpadają, bo nic nie znajdą."""
        slowa = self.slowa(q)
        if len(slowa) <= n:
            return slowa
        df = {w: self.db.execute("SELECT count(*) FROM fts WHERE fts MATCH ?", (f'"{w}"*',)).fetchone()[0]
              for w in slowa[:MAX_SLOW_OCENIANYCH]}
        trafne = [w for w in df if df[w]]
        if not trafne:
            return slowa[:n]
        wybrane = set(sorted(trafne, key=lambda w: df[w])[:n])       # sort stabilny: przy remisie wcześniejsze słowo
        return [w for w in slowa if w in wybrane]

    def rozszerz(self, q: str) -> str:
        """Zapytanie z tytułami notatek, których alias (frontmatter `aliasy:`) pada w pytaniu: „co lubi szefowa” →
        „co lubi szefowa Ola Wrona”. Ogonki i wielkość liter bez znaczenia, słowa aliasu pasują też w odmianie
        (_ma_fraze). Tytuł, który już jest w pytaniu, nie wraca."""
        slowa = _slowa_lista(q)
        if not slowa:
            return q
        w_pytaniu = " ".join(slowa)
        dopiski: list[str] = []
        for alias, tytul in self.db.execute("SELECT alias, tytul FROM aliasy ORDER BY sciezka, alias"):
            if tytul in dopiski or " ".join(_slowa_lista(tytul)) in w_pytaniu or not _ma_fraze(slowa, alias.split()):
                continue
            dopiski.append(tytul)
            if len(dopiski) >= MAX_DOPISKOW_ALIASOW:
                break
        return q + (" " + " ".join(dopiski) if dopiski else "")

    def szukaj_wektorami(self, osadzacz, q: str, n: int = WEKTOROW_W_RANKINGU) -> list[tuple[str, float]] | None:
        """[(ścieżka, kosinus)] najlepszych `n` notatek albo None (brak modelu, wektorów, usługi albo czasu: wołający
        zostaje przy słowach). Pytanie dłuższe niż DLUGIE_ZAPYTANIE słów idzie zdaniami (każde z aliasami), wynik notatki
        to najlepsze zdanie. Iloczyn skalarny w czystym Pythonie: wektory są znormalizowane, brama nie ma numpy."""
        model = getattr(osadzacz, "model", "") if osadzacz is not None else ""
        if not model:
            return None
        wiersze = self.db.execute("SELECT sciezka, wektor FROM wektory WHERE model = ?", (model,)).fetchall()
        if not wiersze:
            return None
        pytania = osadzacz.osadz([f"query: {self.rozszerz(z)}" for z in zdania_zapytania(q)])
        if not pytania:
            return None
        wymiar = len(pytania[0])
        wyniki = []
        for s, blob in wiersze:
            v = wektor_z_bajtow(blob)
            if len(v) == wymiar:
                wyniki.append((-max(_iloczyn(p, v) for p in pytania), s))
        wyniki.sort()
        return [(s, -w) for w, s in wyniki[:n]]

    def szukaj(self, q: str, limit: int = 5, folder: str | None = None, agent: str | None = None, zrodla: bool = False,
               wektory=None, silnik: str | None = None) -> list[dict]:
        """Notatki do pytania. `wektory` (KlientWektorow albo atrapa: `model`, `osadz(teksty)`) i `silnik` (SILNIKI,
        domyślnie SILNIK): wektory = lista wektorów (kosinus), a notatki jeszcze bez wektora (nowe od ostatniego
        osadzania, zrodla/ przy `zrodla`) wchodzą z miejscem z listy BM25; hybryda = fuzja RRF listy BM25 i listy
        wektorów; slowa = BM25. Bez wektorów (brak usługi, modelu, czasu) zawsze BM25; użyty silnik zostaje
        w `self.silnik`. Zapytanie rozszerzają aliasy notatek (rozszerz)."""
        silnik = silnik if silnik in SILNIKI else SILNIK
        wek = self.szukaj_wektorami(wektory, q) if wektory is not None and silnik != "slowa" else None
        self.silnik = silnik if wek is not None else "slowa"
        kolumny = "p.sciezka, p.tytul, p.streszczenie, p.typ, p.status, p.folder, p.agent, p.zmieniono"

        def dopuszczona(r) -> bool:
            s = r["sciezka"]
            if not zrodla and s.startswith(POZA_WYSZUKIWANIEM):
                return False
            if r["typ"] == "skill" and not folder:            # węzły grafu o flocie: tylko z folder="fleet"
                return False
            if folder and not s.startswith(folder.rstrip("/") + "/"):
                return False
            return not (agent and r["agent"] and r["agent"] != agent)

        bm = []
        zap = self.zapytanie(self.slowa_informacyjne(self.rozszerz(q)))
        if zap:
            bm = [r for r in self.db.execute(
                f"SELECT {kolumny}, bm25(fts, 0, 3.0, 2.0, 1.0, 1.5) AS w FROM fts f JOIN pliki p ON p.sciezka = f.sciezka "
                "WHERE fts MATCH ? ORDER BY w LIMIT ?", (zap, limit * 6)).fetchall() if dopuszczona(r)]
        if wek is None:
            ranking = [(r, round(-r["w"], 3)) for r in bm]
        else:
            meta = {r["sciezka"]: r for r in bm}
            brak = [s for s, _w in wek if s not in meta]
            for i in range(0, len(brak), 500):
                czesc = brak[i:i + 500]
                for r in self.db.execute(f"SELECT {kolumny} FROM pliki p WHERE p.sciezka IN ({','.join('?' * len(czesc))})", czesc):
                    meta[r["sciezka"]] = r
            lista_wek = [s for s, _w in wek if s in meta and dopuszczona(meta[s])]
            wynik: dict[str, float] = {}
            if self.silnik == "wektory":
                z_wektorem = {r[0] for r in self.db.execute("SELECT sciezka FROM wektory WHERE model = ?", (wektory.model,))}
                for lista in (lista_wek, [r["sciezka"] for r in bm if r["sciezka"] not in z_wektorem]):
                    for poz, s in enumerate(lista):
                        wynik.setdefault(s, 1.0 / (RRF_K + poz))
            else:
                for lista in ([r["sciezka"] for r in bm], lista_wek):
                    for poz, s in enumerate(lista):
                        wynik[s] = wynik.get(s, 0.0) + 1.0 / (RRF_K + poz)
            ranking = [(meta[s], round(wynik[s], 5)) for s in sorted(wynik, key=lambda s: (-wynik[s], s))]
        out, widziane = [], set()
        for r, punkty in ranking:
            s = r["sciezka"]
            if s in widziane:
                continue
            widziane.add(s)
            out.append({"sciezka": s, "tytul": r["tytul"], "streszczenie": r["streszczenie"], "typ": r["typ"],
                        "status": r["status"], "zmieniono": r["zmieniono"], "wynik": punkty})
            if len(out) >= limit:
                break
        # krok po linkach: trafienie w marce pociąga orzeczenia tej marki
        for r in list(out):
            if r["sciezka"].startswith("brands/") and "/" in r["sciezka"][7:]:
                marka = r["sciezka"].split("/")[1]
                orz = f"orzeczenia/marki/{marka}"
                if self.sk.istnieje(orz) and orz not in widziane:
                    widziane.add(orz)
                    out.append({"sciezka": orz, "tytul": f"Orzeczenia marki {marka}", "streszczenie": "korekty użytkownika dotyczące tej marki",
                                "typ": "orzeczenia", "status": "aktualna", "zmieniono": "", "wynik": 0.0})
        return out

    def odswiez_wektory(self, osadzacz, czas_s: float | None = None) -> dict:
        """Wektory notatek przyrostowo (po odswiez(): pliki i FTS aktualne). Tekst wektora jak w pomiarze: „passage: ”,
        tytuł, streszczenie, początek treści (tekst_wektora). Nowa albo zmieniona notatka (mtime, rozmiar) z innym hashem
        tekstu dostaje nowy wektor; ten sam hash = sam nowy mtime. Inny model niż w bazie = pełne przeliczenie (wektory
        starego modelu znikają). Zrodla/ i skrzynka/ bez wektorów (poza wyszukiwaniem). Paczki po WEKTORY_PACZKA, każda
        we własnej transakcji; usługa niedostępna w trakcie = przerwane, reszta przy następnym razie. Zwraca liczby."""
        model = getattr(osadzacz, "model", "") if osadzacz is not None else ""
        wynik = {"model": model, "nowe": 0, "usuniete": 0, "wektorow": 0, "notatek": 0, "przerwane": not model}
        if not model:
            return wynik
        with self.db:
            wynik["usuniete"] = self.db.execute("DELETE FROM wektory WHERE model != ? OR sciezka NOT IN (SELECT sciezka FROM pliki)",
                                                (model,)).rowcount
        stare = {r[0]: (r[1], r[2], r[3]) for r in self.db.execute("SELECT sciezka, mtime, rozmiar, hash FROM wektory")}
        szukane = [(r[0], r[1], r[2]) for r in self.db.execute("SELECT sciezka, mtime, rozmiar FROM pliki")
                   if not r[0].startswith(POZA_WYSZUKIWANIEM)]
        wynik["notatek"] = len(szukane)
        zmienione = {s: (m, n) for s, m, n in szukane if stare.get(s, (None, None, None))[:2] != (m, n)}
        kolejka = []
        if zmienione:
            teksty = {s: tekst_wektora(t, st, tr) for s, t, st, tr in
                      self.db.execute("SELECT sciezka, tytul, streszczenie, tresc FROM fts") if s in zmienione}
            with self.db:
                for s, (m, n) in zmienione.items():
                    if s not in teksty:
                        continue
                    h = hashlib.sha256(teksty[s].encode("utf-8")).hexdigest()[:16]
                    if s in stare and stare[s][2] == h:          # dotknięty plik bez zmiany tekstu: bez osadzania
                        self.db.execute("UPDATE wektory SET mtime = ?, rozmiar = ? WHERE sciezka = ?", (m, n, s))
                    else:
                        kolejka.append((s, h, m, n, teksty[s]))
        for i in range(0, len(kolejka), WEKTORY_PACZKA):
            paczka = kolejka[i:i + WEKTORY_PACZKA]
            wektory = osadzacz.osadz([x[4] for x in paczka], czas_s=czas_s)
            if not wektory or len(wektory) != len(paczka):
                wynik["przerwane"] = True
                break
            with self.db:
                for (s, h, m, n, _t), v in zip(paczka, wektory):
                    self.db.execute("INSERT OR REPLACE INTO wektory VALUES (?,?,?,?,?,?)", (s, h, model, wektor_do_bajtow(v), m, n))
            wynik["nowe"] += len(paczka)
        wynik["wektorow"] = self.db.execute("SELECT count(*) FROM wektory WHERE model = ?", (model,)).fetchone()[0]
        return wynik

    def notatki(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM pliki ORDER BY sciezka").fetchall()

    def linki(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM linki").fetchall()

    def graf(self) -> dict:
        we: dict[str, int] = {}
        wy: dict[str, int] = {}
        linki = []
        for l in self.linki():
            if not l["rozwiazany"]:
                continue
            we[l["do_"]] = we.get(l["do_"], 0) + 1
            wy[l["z"]] = wy.get(l["z"], 0) + 1
            linki.append({"z": l["z"], "do": l["do_"], "auto": bool(l["auto"])})
        def w_grafie(s: str) -> bool:                  # kopia repo (docs, zasady agentów, materiały skilli) też jest w grafie
            return not s.startswith(POZA_WYSZUKIWANIEM) or s.startswith(LUSTRO_REPO + "/")
        wezly = [{"id": r["sciezka"], "tytul": r["tytul"], "folder": r["folder"], "typ": r["typ"], "status": r["status"],
                  "hub": bool(r["hub"]), "agent": r["agent"], "zmieniono": r["zmieniono"], "we": we.get(r["sciezka"], 0),
                  "wy": wy.get(r["sciezka"], 0)} for r in self.notatki() if w_grafie(r["sciezka"])]
        return {"wezly": wezly, "linki": [l for l in linki if w_grafie(l["z"])]}


# ------------------------------------------------------------------------------------------------ wektory i aliasy

def _slowa_lista(s: str) -> list[str]:
    return re.findall(r"\w+", bez_ogonkow(s).lower())


def _ma_fraze(slowa: list[str], fraza: list[str]) -> bool:
    """Fraza aliasu w słowach pytania (oba bez ogonków, małymi literami), słowo po słowie. Słowo aliasu od 4 liter
    pasuje też do odmiany: słowo pytania zaczyna się od niego bez dwóch ostatnich liter, ale od co najmniej 4
    („szefowa” → „szefowej”, „właścicielka” → „właścicielce”); krótsze tylko dokładnie („Ola”)."""
    def pasuje(slowo: str, f: str) -> bool:
        return slowo == f or (len(f) >= 4 and slowo.startswith(f[:max(4, len(f) - 2)]))
    n = len(fraza)
    return n > 0 and any(all(pasuje(slowa[i + j], f) for j, f in enumerate(fraza)) for i in range(len(slowa) - n + 1))


def aliasy_notatki(n: Notatka) -> list[str]:
    """Aliasy z frontmattera `aliasy: [właściciel, szef]` (lista albo tekst z przecinkami) jako frazy bez ogonków,
    małymi literami, najwyżej MAX_ALIASOW."""
    surowe = n.fm.get("aliasy") or []
    lista = surowe if isinstance(surowe, list) else str(surowe).split(",")
    out = [" ".join(_slowa_lista(str(a)[:60])) for a in lista]
    return list(dict.fromkeys(a for a in out if a))[:MAX_ALIASOW]


def zdania_zapytania(q: str) -> list[str]:
    """Pytanie do osadzenia: krótkie (do DLUGIE_ZAPYTANIE słów) w całości, dłuższe (treść karty, prompt rutyny)
    zdaniami od MIN_SLOW_ZDANIA słów, najwyżej MAX_ZDAN pierwszych; bez takich zdań całe pytanie."""
    if len(q.split()) <= DLUGIE_ZAPYTANIE:
        return [q]
    czesci = [" ".join(c.split()) for c in re.split(r"(?<=[.!?])\s+|\n+| — ", q)]
    return [c for c in czesci if len(c.split()) >= MIN_SLOW_ZDANIA][:MAX_ZDAN] or [q]


def tekst_wektora(tytul: str, streszczenie: str, tresc: str) -> str:
    """Tekst notatki dla modelu e5 (prefiks „passage: ”): tytuł, streszczenie i początek treści z indeksu FTS."""
    return f"passage: {tytul}. {streszczenie or ''} {(tresc or '')[:MAX_ZNAKOW_WEKTORA]}"


def wektor_do_bajtow(v) -> bytes:
    """float32 little-endian (ten sam układ na każdym systemie i w odpowiedzi usługi)."""
    a = array.array("f", v)
    if sys.byteorder == "big":
        a.byteswap()
    return a.tobytes()


def wektor_z_bajtow(b: bytes) -> array.array:
    a = array.array("f")
    a.frombytes(b[:len(b) - len(b) % 4])
    if sys.byteorder == "big":
        a.byteswap()
    return a


_iloczyn = getattr(math, "sumprod", None) or (lambda a, b: sum(map(operator.mul, a, b)))   # sumprod od Pythona 3.12


class KlientWektorow:
    """Klient usługi wektorów (wiedza/wektory.py: jeden ciepły model e5-small na instalację w venvie narzędzi, docs/
    WIEDZA.md §7). Port, token, id modelu i PID z state/wektory.json (pisze je usługa przy starcie); HTTP tylko na
    127.0.0.1, z tokenem w nagłówku, bez proxy systemu (http.client). Sama biblioteka standardowa: brama Hermesa i
    `jarvo chat` nie mają numpy ani onnxruntime. Brak pliku, martwy PID, odmowa, zły token, inny model albo przekroczony
    `czas_s` = None, a powód w `blad`: wołający zostaje przy słowach (BM25), tura idzie dalej bez błędu."""

    MAX_ODPOWIEDZI = 32 << 20

    def __init__(self, stan: str | Path, czas_s: float = WEKTORY_CZAS_S):
        self.czas_s = czas_s
        self.blad = ""
        try:
            d = json.loads((Path(stan) / WEKTORY_STAN).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        d = d if isinstance(d, dict) else {}
        port, pid = d.get("port"), d.get("pid")
        self.port = port if isinstance(port, int) and 0 < port < 65536 else 0
        self.token = str(d.get("token") or "")
        self.model = str(d.get("model") or "")
        if self.port and isinstance(pid, int) and not pid_zyje(pid):     # resztka po awarii usługi: bez czekania na port
            self.port, self.blad = 0, f"usługa wektorów nie działa (PID {pid})"
        if not self.dostepny:
            self.model = ""
            self.blad = self.blad or "usługa wektorów nie działa (brak state/wektory.json)"

    @property
    def dostepny(self) -> bool:
        return bool(self.port and self.token and self.model)

    def _zapytaj(self, metoda: str, sciezka: str, cialo: dict | None = None, czas_s: float | None = None) -> dict | None:
        if not self.dostepny:
            return None
        polaczenie = http.client.HTTPConnection("127.0.0.1", self.port, timeout=self.czas_s if czas_s is None else czas_s)
        try:
            dane = json.dumps(cialo, ensure_ascii=False).encode("utf-8") if cialo is not None else None
            polaczenie.request(metoda, sciezka, body=dane, headers={"Authorization": f"Bearer {self.token}",
                                                                    "Content-Type": "application/json"})
            odp = polaczenie.getresponse()
            tresc = odp.read(self.MAX_ODPOWIEDZI)
            if odp.status != 200:
                self.blad = f"usługa wektorów: HTTP {odp.status}"
                return None
            wynik = json.loads(tresc.decode("utf-8"))
            return wynik if isinstance(wynik, dict) else None
        except (OSError, http.client.HTTPException, ValueError) as e:
            self.blad = f"usługa wektorów: {type(e).__name__}"           # TimeoutError, ConnectionRefusedError…
            return None
        finally:
            polaczenie.close()

    def zdrowie(self, czas_s: float | None = None) -> dict | None:
        """{"model", "wymiar", "pid", "od"} działającej usługi albo None."""
        w = self._zapytaj("GET", "/zdrowie", czas_s=czas_s)
        return w if w and w.get("model") == self.model else None

    def osadz(self, teksty: list[str], czas_s: float | None = None) -> list[array.array] | None:
        """Znormalizowane wektory tekstów (z prefiksami e5: „query: ”, „passage: ”) albo None."""
        if not teksty:
            return []
        w = self._zapytaj("POST", "/osadz", {"teksty": list(teksty)}, czas_s)
        if not w or w.get("model") != self.model:
            self.blad = self.blad or "usługa wektorów: inny model niż w state/wektory.json"
            return None
        try:
            wymiar = int(w["wymiar"])
            plaskie = wektor_z_bajtow(base64.b64decode(w["wektory"]))
        except (KeyError, TypeError, ValueError):
            self.blad = "usługa wektorów: zła odpowiedź"
            return None
        if wymiar <= 0 or len(plaskie) != wymiar * len(teksty):
            self.blad = "usługa wektorów: zła odpowiedź"
            return None
        return [plaskie[i * wymiar:(i + 1) * wymiar] for i in range(len(teksty))]


def _slowa_ascii(s: str) -> set[str]:
    return set(re.findall(r"\w+", bez_ogonkow(s).lower()))


def hub_agenta_nazwany(sciezka: str, slowa_pytania: set[str]) -> bool:
    """Pytanie nazywa agenta tego huba (`agenci/jarvo-web/_hub-web`: „web”, „jarvo-web”; ogonki bez znaczenia)."""
    katalog, _, plik = sciezka.rpartition("/_hub-")
    agent = katalog.split("/", 1)[-1]
    nazwy = [_slowa_ascii(plik), _slowa_ascii(agent.removeprefix("jarvo-"))]
    return any(n and n <= slowa_pytania for n in nazwy)


def notatki_przypomnienia(ix: Indeks, q: str, limit: int = 5, wektory=None, silnik: str | None = None) -> list[dict]:
    """Notatki „może się przydać” przed turą (wtyczka jarvo-wiedza) i w `ocena`: wyszukiwanie (Indeks.szukaj: wektory,
    gdy usługa odpowie w czasie, inaczej słowa) bez hubów folderów, orzeczeń (idą osobno) i hubów agentów
    `agenci/<agent>/_hub-*`, chyba że pytanie nazywa tego agenta (hub ma ogólne słowa o całej dziedzinie, więc bez
    tego zajmuje miejsca przy każdym pytaniu o pracę). Użyty silnik: `ix.silnik`."""
    slowa = _slowa_ascii(q)
    out = []
    for t in ix.szukaj(q, limit=limit + 8, wektory=wektory, silnik=silnik):
        if t["typ"] in ("orzeczenia", "hub"):
            continue
        if HUB_AGENTA_RE.match(t["sciezka"]) and not hub_agenta_nazwany(t["sciezka"], slowa):
            continue
        out.append(t)
        if len(out) >= limit:
            break
    return out


def ocena(ix: Indeks, zestaw: list, limit: int = 5, wektory=None, silnik: str | None = None) -> dict:
    """Pomiar przypomnień na zestawie `[{"pytanie": ..., "wzor": [ścieżki]}]` (zestaw właściciela leży poza repo):
    to samo wyszukiwanie co wtyczka przed turą (odświeżenie indeksu + notatki_przypomnienia, te same wektory i czas
    na nie). hit@k = jakakolwiek ścieżka wzorcowa w pierwszych k, MRR = średnia 1/pozycja pierwszej wzorcowej (0 bez
    trafienia), czas na pytanie w ms, silnik każdego pytania (hybryda, wektory albo slowa, gdy wektorów zabrakło)."""
    if not isinstance(zestaw, list) or not all(isinstance(p, dict) and str(p.get("pytanie") or "").strip() and isinstance(p.get("wzor"), list)
                                               for p in zestaw):
        raise ValueError('zestaw to lista [{"pytanie": "...", "wzor": ["ścieżka notatki", ...]}]')
    ix.odswiez()
    pytania, czasy = [], []
    for p in zestaw:
        wzor = [str(s).strip().strip("/").removesuffix(".md") for s in p["wzor"]]
        start = time.perf_counter()
        ix.odswiez()
        sciezki = [t["sciezka"] for t in notatki_przypomnienia(ix, str(p["pytanie"]), limit=limit, wektory=wektory, silnik=silnik)]
        ms = round((time.perf_counter() - start) * 1000, 1)
        pozycja = next((i + 1 for i, s in enumerate(sciezki) if s in wzor), 0)
        czasy.append(ms)
        pytania.append({"pytanie": p["pytanie"], "wzor": wzor, "wyniki": sciezki, "pozycja": pozycja, "ms": ms,
                        "silnik": ix.silnik})
    n = len(pytania)
    trafione = sum(1 for p in pytania if p["pozycja"])
    posortowane = sorted(czasy)
    mediana = (posortowane[(n - 1) // 2] + posortowane[n // 2]) / 2 if n else 0.0
    silniki: dict[str, int] = {}
    for p in pytania:
        silniki[p["silnik"]] = silniki.get(p["silnik"], 0) + 1
    return {"pytan": n, "k": limit, "trafione": trafione, "hit_at_k": round(trafione / n, 3) if n else 0.0,
            "mrr": round(sum(1 / p["pozycja"] for p in pytania if p["pozycja"]) / n, 3) if n else 0.0,
            "ms_mediana": round(mediana, 1), "ms_max": max(czasy, default=0.0), "silniki": silniki, "pytania": pytania}


# ------------------------------------------------------------------------------------------------ INDEX.md i listy hubów

def zbuduj_index(sk: Skarbiec, ix: Indeks) -> int:
    """INDEX.md z plików (deterministycznie): każda notatka jedną linią, sekcje po folderach."""
    grupy: dict[str, list] = {}
    for r in ix.notatki():
        grupy.setdefault(r["folder"], []).append(r)
    linie = ["# Indeks skarbca", "", f"Generowany przez `wiedza.py indeksuj` ({dzis()}). Jedna linia = jedna notatka: link · streszczenie · typ · zmieniono.", ""]
    n = 0
    for folder in sorted(grupy, key=lambda f: (f != "", f)):
        wiersze = grupy[folder]
        nazwa = HUBY.get(folder, (None, folder or "Skarbiec"))[1]
        if folder in ("zrodla", "skrzynka"):
            linie += [f"## {nazwa} ({len(wiersze)} plików, poza wyszukiwaniem)", ""]
            continue
        linie += [f"## {nazwa}", ""]
        skille = [r for r in wiersze if r["typ"] == "skill"]
        if skille:
            linie.append(f"- skille floty: {len(skille)} notatek w `{SKILLE}/` (węzły grafu; szukanie z `folder=fleet`)")
        for r in sorted((r for r in wiersze if r["typ"] != "skill"), key=lambda r: (not r["hub"], r["sciezka"])):
            s = (r["streszczenie"] or "").replace("\n", " ")
            s = s[:120].rstrip() + ("…" if len(s) > 120 else "")
            czesci = [f"[[{r['sciezka']}|{r['tytul']}]]"] + ([s] if s else []) + [r["typ"] or "?"] + ([r["zmieniono"]] if r["zmieniono"] else [])
            linie.append("- " + " · ".join(czesci))
            n += 1
        linie.append("")
    sk.zapisz_plik("INDEX", "\n".join(linie).rstrip("\n") + "\n")
    return n


def odswiez_listy_hubow(sk: Skarbiec, ix: Indeks) -> int:
    """Blok `lista` w hubie folderu (i w hubie agenta): linki do wszystkich notatek folderu, 0 tokenów."""
    notatki = [r for r in ix.notatki() if not r["hub"]]
    ile = 0
    for folder, (hub, _t) in HUBY.items():
        if folder == "":
            continue
        rel = f"{folder}/{hub}"
        if not sk.istnieje(rel):
            continue
        if folder == "agenci":
            wiersze = [f"- [[{r['sciezka']}|{r['tytul']}]]" for r in ix.notatki() if r["hub"] and r["sciezka"].startswith("agenci/") and r["sciezka"].count("/") == 2]
        else:
            wiersze = [f"- [[{r['sciezka']}|{r['tytul']}]]" + (f" · {r['streszczenie'][:90]}" if r["streszczenie"] else "")
                       for r in notatki if r["sciezka"].startswith(folder + "/")]
        ile += _wpisz_liste(sk, rel, wiersze)
    for r in ix.notatki():
        if r["hub"] and r["sciezka"].startswith("agenci/") and r["sciezka"].count("/") == 2:
            katalog = r["sciezka"].rsplit("/", 1)[0] + "/"
            wiersze = [f"- [[{n['sciezka']}|{n['tytul']}]]" + (f" · {n['streszczenie'][:90]}" if n["streszczenie"] else "")
                       for n in notatki if n["sciezka"].startswith(katalog)]
            ile += _wpisz_liste(sk, r["sciezka"], wiersze)
    return ile


def _wpisz_liste(sk: Skarbiec, rel: str, wiersze: list[str]) -> int:
    p = sk.plik(rel)
    stary = p.read_text(encoding="utf-8")
    tresc = "## Notatki (lista automatyczna)\n" + ("\n".join(wiersze) if wiersze else "_jeszcze pusto_")
    nowy = zastap_blok(stary, "lista", tresc)
    if nowy != stary:
        sk.zapisz_plik(rel, nowy)
        return 1
    return 0


# ------------------------------------------------------------------------------------------------ zasiew

def _hub_frontmatter(typ: str, zrodlo: str = "wiedza.py zasiej", **extra) -> dict:
    fm = {"typ": typ, "tagi": ["hub"], "utworzono": dzis(), "zmieniono": dzis(), "status": "aktualna", "zrodlo": zrodlo}
    fm.update(extra)
    return fm


def hub_agenta(a: dict) -> tuple[str, str]:
    """(ścieżka huba agenta, nazwa pliku orzeczeń) z wpisu fleet.json."""
    krotki = nazwa_pliku(a.get("short") or a["name"].replace("jarvo-", "") or a["name"]).replace(" ", "-")
    return f"agenci/{a['name']}/_hub-{krotki}", krotki


def lustro(rel_repo: str) -> str:
    """Ścieżka pliku repo w skarbcu (kopia z `zasiej --repo`), bez `.md`: cel linku."""
    return f"{LUSTRO_REPO}/{rel_repo[:-3] if rel_repo.endswith('.md') else rel_repo}"


def notatka_skilla(s: dict, agenci: list[tuple[str, str, str]], znane: set[str], w_lustrze: set[str] | None = None) -> str:
    """Notatka-węzeł skilla floty: opis, kto go ma, powiązane skille i skrypty (linki robi zasiew, nie autor);
    materiały skilla (references) linkują do ich kopii w `zrodla/jarvo-repo/`, gdy zasiew ją położył."""
    powiazane = [n for n in dict.fromkeys([*s.get("related", []), *s.get("mentions", [])]) if n in znane and n != s["name"]]
    obce = [n for n in s.get("related", []) if n not in znane]
    wiersze = ["- agent: " + ", ".join(f"[[{hub}|{nazwa}]]" for hub, nazwa, _a in agenci)]
    wersja = " · ".join(x for x in (f"wersja {s['version']}" if s.get("version") else "",
                                    f"przejrzany {s['reviewed']}" if s.get("reviewed") else "") if x)
    plik = f"plik w repo: `{s['path']}`" if s.get("path") else ""
    if wersja or plik:
        wiersze.append("- " + " · ".join(x for x in (wersja, plik) if x))
    if s.get("scripts"):
        wiersze.append("- skrypty: " + ", ".join(f"`{x}`" for x in s["scripts"]))
    if powiazane or obce:
        wiersze.append("- powiązane skille: " + ", ".join([f"[[{SKILLE}/{n}|{n}]]" for n in powiazane] + [f"`{n}`" for n in obce]))
    if s.get("sections"):
        wiersze.append("- sekcje: " + " · ".join(s["sections"]))
    katalog = s.get("path", "").rsplit("/", 1)[0]
    materialy = [r for r in s.get("references") or [] if lustro(f"{katalog}/references/{r}") in (w_lustrze or set())]
    if materialy:
        wiersze.append("- materiały (references): " + ", ".join(f"[[{lustro(f'{katalog}/references/{r}')}|{r}]]" for r in materialy))
    opis = s.get("description") or "(skill bez opisu)"
    return (f"# {s['name']}\n\n**{opis}**\n\n"
            + zastap_blok("", "skill", "## Z repo (SKILL.md i fleet.yaml)\n" + "\n".join(wiersze)).strip() + "\n")


def zasiej_skille(sk: Skarbiec, skille: dict[str, tuple[dict, list]], w_lustrze: set[str] | None = None) -> int:
    """`fleet/skille/<nazwa>.md` dla każdego skilla floty (własnego i wspólnego): węzeł grafu połączony z hubami agentów,
    powiązanymi skillami i skryptami. Plik zmienia się tylko, gdy zmienił się skill; skill usunięty z floty znika."""
    katalog = sk.root / SKILLE
    katalog.mkdir(parents=True, exist_ok=True)
    zmienione = 0
    for nazwa, (s, agenci) in sorted(skille.items()):
        rel = f"{SKILLE}/{nazwa}"
        tresc = notatka_skilla(s, agenci, set(skille), w_lustrze)
        stare_fm, stara = podziel(sk.plik(rel).read_text(encoding="utf-8")) if sk.istnieje(rel) else ({}, None)
        if stara is not None and stara.strip() == tresc.strip():
            continue
        fm = _hub_frontmatter("skill", s.get("path") or "fleet.yaml", status="generowane", tagi=["skill"],
                              utworzono=str(stare_fm.get("utworzono") or dzis()))
        if len(agenci) == 1:
            fm["agent"] = agenci[0][2]
        sk.zapisz_plik(rel, sklej(fm, tresc))
        zmienione += 1
    for stary in katalog.glob("*.md"):                 # skill usunięty z floty nie zostaje w grafie
        if stary.stem not in skille:
            stary.unlink()
            zmienione += 1
    return zmienione


def zasiej_lustro(sk: Skarbiec, repo: Path) -> tuple[int, set[str]]:
    """Pliki profili z buildu (`wiedza/repo`: SOUL, README, CHANGELOG, rubryka, materiały skilli, spis źródeł) do
    `zrodla/jarvo-repo/` w układzie repo. Plik zmieniony w repo jest nadpisywany, usunięty znika."""
    cel = sk.root / LUSTRO_REPO
    nowe: set[str] = set()
    zmienione = 0
    for src in sorted(repo.rglob("*.md")):
        rel = src.relative_to(repo).as_posix()
        if rel.split("/", 1)[0] not in LUSTRO_KATALOGI:
            continue
        nowe.add(rel)
        dst = cel / rel
        dane = src.read_bytes()
        if not dst.exists() or dst.read_bytes() != dane:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(dane)
            zmienione += 1
    for katalog in LUSTRO_KATALOGI:
        for stary in sorted((cel / katalog).rglob("*.md")) if (cel / katalog).is_dir() else []:
            if stary.relative_to(cel).as_posix() not in nowe:
                stary.unlink()
                zmienione += 1
        for d in sorted((cel / katalog).rglob("*"), reverse=True) if (cel / katalog).is_dir() else []:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
    return zmienione, {lustro(r) for r in nowe}


def zasiej(sk: Skarbiec, fleet: dict | None, docs: Path | None, schema: Path | None, repo: Path | None = None) -> dict:
    sk.root.mkdir(parents=True, exist_ok=True)
    for f in FOLDERY:
        (sk.root / f).mkdir(parents=True, exist_ok=True)
    raport = {"huby": 0, "agenci": 0, "skille": 0, "docs": 0, "repo": 0, "git": False}
    w_lustrze: set[str] = set()
    if repo and repo.is_dir():
        raport["repo"], w_lustrze = zasiej_lustro(sk, repo)
    if schema and schema.exists():
        shutil.copy2(schema, sk.root / "SCHEMA.md")
    # huby folderów (część ręczna zostaje: piszemy tylko, gdy pliku nie ma; bloki GEN odświeżane zawsze)
    for folder, (hub, tytul) in HUBY.items():
        rel = f"{folder}/{hub}" if folder else hub
        if not sk.istnieje(rel):
            opis = OPISY_FOLDEROW.get(folder, "Strona główna skarbca: huby folderów, liczby, ostatnie zmiany.")
            body = f"# {tytul}\n\n**{opis}**\n\n## Powiązane\n" + (f"- hub: [[_hub-skarbiec|Skarbiec wiedzy]]\n" if folder else "")
            sk.zapisz_plik(rel, sklej(_hub_frontmatter("hub"), body))
            raport["huby"] += 1
    # hub główny: linki do hubów folderów (blok GEN)
    linie = [f"- [[{f}/{h}|{t}]] · {OPISY_FOLDEROW.get(f, '')}" for f, (h, t) in HUBY.items() if f]
    linie += ["- [[INDEX|Indeks]] · każda notatka jedną linią", "- [[LOG|Dziennik]] · co się działo ze skarbcem", "- [[LINT|Lint]] · ostatni raport zdrowia",
              "- [[SCHEMA|Schemat]] · zasady skarbca"]
    p = sk.plik(HUBY[""][0])
    sk.zapisz_plik(HUBY[""][0], zastap_blok(p.read_text(encoding="utf-8"), "huby", "## Foldery\n" + "\n".join(linie)))
    # agenci z fleet.json
    agenci_meta: dict[str, dict] = {}
    try:   # opisy z poprzedniego zasiewu: pogrubiony opis huba idzie za fleet.yaml, dopóki człowiek go nie zmienił
        poprzednie = json.loads((sk.stan / "wiedza-agenci.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        poprzednie = {}
    skille_floty: dict[str, tuple[dict, list]] = {}
    if fleet:
        for a in fleet.get("agents", []):
            rel, krotki = hub_agenta(a)
            orz = f"orzeczenia/{krotki}"
            opis = " ".join(a.get("description", "").split())
            agenci_meta[a["name"]] = {"hub": rel, "orzeczenia": orz, "short": a.get("short") or krotki, "title": a.get("title", ""),
                                      "opis": opis}
            if a.get("komputer"):           # rozmowa agenta z ekranem to treść ekranu (dane osób): bez wyciągu do skarbca
                agenci_meta[a["name"]]["bez_wyciagu"] = True
            if not sk.istnieje(rel):
                body = (f"# {a.get('emoji', '')} {a.get('title', a['name'])} ({a['name']})\n\n**{a.get('description', '').strip()}**\n\n"
                        f"## Powiązane\n- hub: [[agenci/_hub-agenci|Agenci]]\n- [[{orz}|Orzeczenia: {a.get('short') or krotki}]]\n"
                        f"- [[fleet/lekcje|Księga lekcji floty]]\n").replace("#  ", "# ")
                sk.zapisz_plik(rel, sklej(_hub_frontmatter("agent", "fleet.yaml", agent=a["name"]), body))
                raport["agenci"] += 1
            skille = "\n".join(f"- [[{SKILLE}/{s['name']}|{s['name']}]]: {s.get('description', '').strip()}"
                               for s in a.get("skills", [])) or "_brak_"
            skrypty = ", ".join(f"`{s}`" for s in a.get("scripts", [])) or "_brak_"
            def serwer(m: dict) -> str:
                czesci = ([f"trust: {m['trust']}"] if m.get("trust") else []) + ([", ".join(m["tools"])] if m.get("tools") else [])
                return f"`{m['name']}`" + (f" ({' · '.join(czesci)})" if czesci else "")
            mcp = "; ".join(serwer(m) for m in a.get("mcp") or [])
            mcp_linia = f"\n- serwery MCP: {mcp}" if mcp else ""
            env = a.get("env") or []
            if env:
                mcp_linia += "\n- zmienne środowiska (same nazwy, wartości w .env): " + ", ".join(f"`{e}`" for e in env)
            if a.get("tools"):
                mcp_linia += f"\n- narzędzia (toolbox.yaml, {len(a['tools'])}): " + ", ".join(f"`{x}`" for x in a["tools"])
            if a.get("evals"):
                mcp_linia += f"\n- evals ({len(a['evals'])}): " + ", ".join(f"`{e['id']}`" for e in a["evals"])
            pliki_repo = [(f"profiles/{a['name']}/{r}", etykieta) for r, etykieta in
                          (("SOUL.md", "zasady (SOUL)"), ("README.md", "README"), ("quality/rubric.md", "rubryka"),
                           ("CHANGELOG.md", "wszystkie zmiany"))]
            z_repo = [f"[[{lustro(r)}|{etykieta}]]" for r, etykieta in pliki_repo if lustro(r) in w_lustrze]
            if z_repo:
                mcp_linia += "\n- z repo: " + " · ".join(z_repo)
            zewn = a.get("external_skills") or []
            zewn_linia = (f"\n- skille zewnętrzne ({len(zewn)}): " + ", ".join(f"`{s}`" for s in zewn)) if zewn else ""
            wsp = a.get("shared_skills") or []
            if wsp:
                zewn_linia = (f"\n- skille wspólne floty ({len(wsp)}): " + ", ".join(f"[[{SKILLE}/{s['name']}|{s['name']}]]" for s in wsp)
                              + zewn_linia)
            for s in [*a.get("skills", []), *wsp]:
                skille_floty.setdefault(s["name"], (s, []))[1].append((rel, a.get("short") or krotki, a["name"]))
            zmiany = "".join(f"\n  - {z}" for z in a.get("changes") or [])
            zmiany_linia = (f"\n- ostatnie zmiany (CHANGELOG profilu, {a.get('changes_section') or 'najnowsze'}):{zmiany}"
                            if zmiany else "")
            uchwyt = f"uchwyt: @{a['handle']} · " if a.get("handle") else ""   # @… w rozmowie aplikacji Jarvo
            gen = (f"## Z rejestru floty (fleet.yaml)\n- rola: {a.get('kind', '')} · autonomia: {a.get('autonomy_max', '')} · "
                   f"{uchwyt}pokój HQ: {a.get('label', a.get('room', ''))} (`{a.get('room', '')}`) · temat Telegrama: `{a.get('telegram_topic', '')}`\n"
                   f"- skille ({len(a.get('skills', []))}):\n{skille}{zewn_linia}\n- skrypty: {skrypty}{mcp_linia}{zmiany_linia}")
            pl = sk.plik(rel)
            tekst = pl.read_text(encoding="utf-8")
            m = re.search(r"^(# .+\n\n)\*\*(.+)\*\*$", tekst, re.M)
            stary = (poprzednie.get(a["name"]) or {}).get("opis")
            if m and opis and m.group(2) != opis and (stary is None or m.group(2) == stary):
                tekst = tekst[:m.start(2) - 2] + f"**{opis}**" + tekst[m.end(2) + 2:]
            sk.zapisz_plik(rel, zastap_blok(tekst, "fleet", gen))
            if not sk.istnieje(orz):
                sk.zapisz_plik(orz, sklej(_hub_frontmatter("orzeczenia", "człowiek", agent=a["name"]),
                                          f"# Orzeczenia: {a.get('short') or krotki}\n\n**Korekty od użytkownika dla `{a['name']}`, jedna datowana linia każda; agent czyta je przed każdą turą.**\n\n"
                                          f"## Powiązane\n- hub: [[orzeczenia/_hub-orzeczenia|Orzeczenia]]\n- [[{rel}|{a.get('short') or krotki}]]\n\n## Linie\n"))
        (sk.stan).mkdir(parents=True, exist_ok=True)
        (sk.stan / "wiedza-agenci.json").write_text(json.dumps(agenci_meta, ensure_ascii=False, indent=1), encoding="utf-8",
                                                    newline="\n")
        # skrypty, które naprawdę są w repo: lint wskazuje notatki floty odwołujące się do nieistniejących
        znane_skrypty = sorted({s for a in fleet.get("agents", []) for s in a.get("scripts", [])} | set(fleet.get("repo_scripts") or []))
        (sk.stan / "wiedza-kod.json").write_text(json.dumps({"skrypty": znane_skrypty}, ensure_ascii=False, indent=1), encoding="utf-8",
                                                 newline="\n")
        raport["skille"] = zasiej_skille(sk, skille_floty, w_lustrze)
    if not sk.istnieje("orzeczenia/wszyscy"):
        sk.zapisz_plik("orzeczenia/wszyscy", sklej(_hub_frontmatter("orzeczenia", "człowiek"),
                                                   "# Orzeczenia: wszyscy\n\n**Korekty od użytkownika dla całej floty, jedna datowana linia każda.**\n\n"
                                                   "## Powiązane\n- hub: [[orzeczenia/_hub-orzeczenia|Orzeczenia]]\n\n## Linie\n"))
    if not sk.istnieje("fleet/lekcje"):
        sk.zapisz_plik("fleet/lekcje", sklej(_hub_frontmatter("lekcja", "przegląd tygodnia (skill fleet-improvement)"),
                                             "# Księga lekcji floty\n\n**Obserwacje z recenzji sędziego: jedna linia = jedna sprawdzalna reguła z licznikiem potwierdzeń.**\n\n"
                                             "## Powiązane\n- hub: [[agenci/_hub-agenci|Agenci]]\n"))
    if docs and docs.is_dir():
        katalog_docs = sk.root / LUSTRO_REPO
        nazwy = set()
        for d in sorted(docs.glob("*.md")):
            shutil.copy2(d, katalog_docs / d.name)
            nazwy.add(d.name)
            raport["docs"] += 1
        for stara in katalog_docs.glob("*.md"):            # dokument usunięty z repo nie zostaje w skarbcu jako „źródło”
            if stara.name not in nazwy:
                stara.unlink()
    # hub główny: dokumenty repo i spis źródeł (kopie w zrodla/jarvo-repo/), żeby były w grafie przy skarbcu
    docs_w = sorted(p.stem for p in (sk.root / LUSTRO_REPO).glob("*.md"))
    linie_repo = [f"- [[{LUSTRO_REPO}/{n}|{n}]]" for n in docs_w]
    if f"{LUSTRO_REPO}/vendor/zrodla" in w_lustrze:
        linie_repo.append(f"- [[{LUSTRO_REPO}/vendor/zrodla|Źródła zewnętrzne]] · repo, z których bierzemy, i ich status")
    if linie_repo:
        p = sk.plik(HUBY[""][0])
        sk.zapisz_plik(HUBY[""][0], zastap_blok(p.read_text(encoding="utf-8"), "repo",
                                                "## Z repo (kopia przy wdrożeniu)\n" + "\n".join(linie_repo)))
    if not (sk.root / "INDEX.md").exists():
        (sk.root / "INDEX.md").write_text("# Indeks skarbca\n\n_Pusty do pierwszego `wiedza.py indeksuj`._\n", encoding="utf-8",
                                          newline="\n")
    if not (sk.root / "LINT.md").exists():
        (sk.root / "LINT.md").write_text("# Lint skarbca\n\n_Jeszcze nie uruchomiono `wiedza.py lint`._\n", encoding="utf-8",
                                         newline="\n")
    sk.dopisz_log("zasiew", f"huby: {raport['huby']} folderów, {raport['agenci']} agentów; skille: {raport['skille']} zmienionych; "
                            f"docs repo: {raport['docs']} plików; pliki profili: {raport['repo']} zmienionych")
    raport["git"] = sk.git_init() and sk.punkt_zapisu("zasiew skarbca")
    return raport


# ------------------------------------------------------------------------------------------------ szkice i orzeczenia

def zapisz_szkic(sk: Skarbiec, typ: str, tytul: str, tresc: str, zrodlo: str, agent: str = "", tagi: list | None = None,
                 linki: list | None = None, skad: str = "") -> str:
    if typ not in TYPY - {"hub", "orzeczenia"}:
        raise ValueError(f"typ spoza schematu: {typ} (dozwolone: {', '.join(sorted(TYPY - {'hub', 'orzeczenia'}))})")
    if not tytul.strip() or not tresc.strip():
        raise ValueError("szkic musi mieć tytuł i treść")
    if not zrodlo.strip():
        raise ValueError("szkic musi mieć źródło (karta, rozmowa, plik, adres)")
    sekret = zawiera_sekret(tytul + "\n" + tresc)
    if sekret:
        raise ValueError(f"szkic zawiera sekret ({sekret}); sekrety nigdy nie trafiają do skarbca")
    skrot = hashlib.sha1(f"{tytul}{tresc}{dzis()}".encode()).hexdigest()[:6]
    rel = f"skrzynka/{dzis()}-{slug_ascii(agent or 'agent', 16)}-{slug_ascii(tytul)}-{skrot}"
    fm = {"szkic": True, "typ": typ, "tytul": tytul.strip(), "agent": agent or "", "zrodlo": zrodlo.strip(), "utworzono": dzis(),
          "skad": skad or "", "tagi": tagi or [], "linki": linki or []}
    sk.zapisz_plik(rel, sklej(fm, f"# {tytul.strip()}\n\n{tresc.strip()}\n"))
    return rel


def dodaj_orzeczenie(sk: Skarbiec, kogo: str, tresc: str, zrodlo: str) -> str:
    tresc = " ".join(tresc.split())
    if not tresc or len(tresc) > 400:
        raise ValueError("orzeczenie to jedno zdanie do 400 znaków")
    sekret = zawiera_sekret(tresc)
    if sekret:
        raise ValueError(f"orzeczenie zawiera sekret ({sekret})")
    kogo = kogo.strip().lower()
    if kogo.startswith("marki/"):
        rel, etykieta = "orzeczenia/marki/" + nazwa_pliku(kogo[6:]).replace(" ", "-"), kogo[6:]
    else:
        meta = {}
        try:
            meta = json.loads((sk.stan / "wiedza-agenci.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        if kogo in meta:                       # pełna nazwa profilu (jarvo-web) → plik po krótkiej nazwie
            rel, etykieta = meta[kogo]["orzeczenia"], meta[kogo]["short"].lower()
        else:
            rel, etykieta = "orzeczenia/" + nazwa_pliku(kogo).replace(" ", "-"), kogo
    if not sk.istnieje(rel):
        sk.zapisz_plik(rel, sklej(_hub_frontmatter("orzeczenia", "człowiek"),
                                  f"# Orzeczenia: {etykieta}\n\n**Korekty od użytkownika, jedna datowana linia każda.**\n\n"
                                  f"## Powiązane\n- hub: [[orzeczenia/_hub-orzeczenia|Orzeczenia]]\n\n## Linie\n"))
    linia = f"- {dzis()} · [{etykieta}] {tresc.rstrip('.')}. (źródło: {' '.join(zrodlo.split()) or 'człowiek'})"
    p = sk.plik(rel)
    text = p.read_text(encoding="utf-8")
    fm, body = podziel(text)
    fm["zmieniono"] = dzis()
    sk.zapisz_plik(rel, sklej(fm, body.rstrip("\n") + "\n" + linia + "\n"))
    sk.dopisz_log("orzeczenie", f"{rel}: {tresc[:80]}")
    sk.punkt_zapisu(f"orzeczenie: {etykieta}")
    return linia


# ------------------------------------------------------------------------------------------------ lint

def lint(sk: Skarbiec, ix: Indeks) -> dict:
    """Zdrowie skarbca bez modelu. Błędy = do naprawy przez kompilację/człowieka; ostrzeżenia = warto; informacje = wiedzieć."""
    ix.odswiez()
    bledy, ostrz, info = [], [], []
    zbior, znane = sk.mapa()
    try:
        skrypty_repo = set(json.loads((sk.stan / "wiedza-kod.json").read_text(encoding="utf-8"))["skrypty"])
    except (OSError, ValueError, KeyError):
        skrypty_repo = None                        # skarbiec bez zasiewu z buildu: nie ma z czym porównać
    notatki = {r["sciezka"]: r for r in ix.notatki()}
    linki = ix.linki()
    we_reczne: dict[str, int] = {}
    for l in linki:
        if l["rozwiazany"] and not l["auto"]:
            we_reczne[l["do_"]] = we_reczne.get(l["do_"], 0) + 1
    for l in linki:
        if not l["rozwiazany"] and not l["z"].startswith(("zrodla/",)):
            bledy.append(f"martwy link `[[{l['do_']}]]` w [[{l['z']}]]")
    tytuly: dict[str, list[str]] = {}
    for rel, r in notatki.items():
        if rel.startswith(("zrodla/", "skrzynka/")):
            continue
        nazwa = rel.rsplit("/", 1)[-1]
        zle = sorted(set(nazwa) & ZAKAZANE_W_NAZWIE)
        if zle:
            bledy.append(f"nazwa pliku z zakazanymi znakami {''.join(zle)}: [[{rel}]]")
        n = sk.wczytaj(rel)
        sekret = zawiera_sekret(n.tresc)
        if sekret:
            bledy.append(f"sekret w treści ({sekret}): [[{rel}]]")
        if skrypty_repo is not None and rel.startswith(O_FLOCIE) and not r["hub"]:
            for nazwa_s in sorted({m.group(1) for m in SKRYPT_RE.finditer(n.tresc)} - skrypty_repo):
                ostrz.append(f"nieaktualna wobec repo: skryptu `{nazwa_s}` nie ma we flocie: [[{rel}]]")
        wlasny_format = rel.startswith(BEZ_FRONTMATTERU) and not r["hub"]
        if not wlasny_format:
            brak = [k for k in WYMAGANE if not n.fm.get(k)]
            if brak:
                bledy.append(f"brak kluczy {', '.join(brak)}: [[{rel}]]")
            if n.typ and n.typ not in TYPY:
                bledy.append(f"typ spoza schematu `{n.typ}`: [[{rel}]]")
            st = str(n.fm.get("status") or "")
            if st and st not in STATUSY:
                bledy.append(f"status spoza schematu `{st}`: [[{rel}]]")
            for k in ("utworzono", "zmieniono", "wazne_do"):
                v = n.fm.get(k)
                if v and not DATA_RE.match(str(v)):
                    bledy.append(f"data `{k}: {v}` nie jest RRRR-MM-DD: [[{rel}]]")
            if n.typ not in BEZ_ZRODLA and not n.fm.get("zrodlo"):
                bledy.append(f"brak źródła (`zrodlo:`): [[{rel}]]")
            if st == "sprzeczna":
                info.append(f"sprzeczność do rozstrzygnięcia: [[{rel}]]")
            if st == "do-sprawdzenia":
                info.append(f"do sprawdzenia: [[{rel}]]")
            wd = str(n.fm.get("wazne_do") or "")
            if wd and DATA_RE.match(wd) and wd < dzis():
                ostrz.append(f"przeterminowana (`wazne_do: {wd}`): [[{rel}]]")
            limit = MAX_SLOW.get(n.typ, DOMYSLNY_MAX_SLOW)
            if n.slowa > limit:
                ostrz.append(f"za długa ({n.slowa} słów, limit {limit}): [[{rel}]]")
            if not r["hub"] and not n.streszczenie:
                ostrz.append(f"bez streszczenia (pierwszy akapit po tytule): [[{rel}]]")
        if not r["hub"] and not wlasny_format and n.typ not in BEZ_ZRODLA and rel != "fleet/lekcje":
            reczne = [(c, a) for c, _e, a in n.linki if not a]
            cele = [sk.rozwiaz(c, znane, zbior) for c, _a in reczne]
            hub_folderu = f"{n.folder}/{HUBY.get(n.folder, ('', ''))[0]}" if n.folder in HUBY else ""
            if hub_folderu and hub_folderu not in cele and not any(c and c.startswith(n.folder + "/") and c.rsplit("/", 1)[-1].startswith("_hub-") for c in cele):
                ostrz.append(f"bez linku do huba folderu: [[{rel}]]")
            if not any(c and c.split("/", 1)[0] != n.folder for c in cele):
                ostrz.append(f"bez linku do innego folderu: [[{rel}]]")
            if we_reczne.get(rel, 0) == 0:
                ostrz.append(f"sierota (linkuje tylko lista huba): [[{rel}]]")
        if not r["hub"]:
            klucz = " ".join(sorted(set(re.findall(r"\w+", bez_ogonkow(n.tytul).lower())) - STOPSLOWA))
            if klucz:
                tytuly.setdefault(klucz, []).append(rel)
    for klucz, rels in tytuly.items():
        if len(rels) > 1:
            ostrz.append("duplikat tytułu: " + ", ".join(f"[[{r}]]" for r in rels))
    # duplikaty przybliżone: ≥ 80% wspólnych słów tytułu (≥ 3 słowa)
    slowa_t = {k: set(k.split()) for k in tytuly if len(k.split()) >= 3}
    odwrotny: dict[str, list[str]] = {}
    for k, ws in slowa_t.items():
        for w in ws:
            odwrotny.setdefault(w, []).append(k)
    pary = set()
    for k, ws in slowa_t.items():
        kand: dict[str, int] = {}
        for w in ws:
            for k2 in odwrotny[w]:
                if k2 != k:
                    kand[k2] = kand.get(k2, 0) + 1
        for k2, wspolne in kand.items():
            if wspolne >= 2 and wspolne / len(ws | slowa_t[k2]) >= 0.8:
                pary.add(tuple(sorted((k, k2))))
    for k, k2 in sorted(pary):
        ostrz.append(f"podobne tytuły: [[{tytuly[k][0]}]] i [[{tytuly[k2][0]}]]")
    for folder, (hub, tytul) in HUBY.items():
        if folder and folder not in ("orzeczenia",):
            ile = sum(1 for rel in notatki if rel.startswith(folder + "/") and not notatki[rel]["hub"])
            if ile < 3:
                info.append(f"cienki folder `{folder}/` ({ile} notatek)")
    szkice = [p for p in (sk.root / "skrzynka").glob("*.md")]
    stare = [p.name for p in szkice if (dt.datetime.now().timestamp() - p.stat().st_mtime) > 7 * 86400]
    if szkice:
        info.append(f"szkice w skrzynce: {len(szkice)}" + (f" (starsze niż 7 dni: {len(stare)})" if stare else ""))
    ostrz += nazwy_nieprzenosne(sk)
    raport = {"bledy": bledy, "ostrzezenia": ostrz, "informacje": info, "notatek": len([r for r in notatki if not r.startswith(POZA_WYSZUKIWANIEM)]),
              "data": dzis()}
    linie = [f"# Lint skarbca ({dzis()})", "", f"Notatek: {raport['notatek']} · błędy: {len(bledy)} · ostrzeżenia: {len(ostrz)} · informacje: {len(info)}", ""]
    for naglowek, lista in (("Błędy", bledy), ("Ostrzeżenia", ostrz), ("Informacje", info)):
        linie += [f"## {naglowek}", ""] + ([f"- {x}" for x in lista] or ["- brak"]) + [""]
    sk.zapisz_plik("LINT", "\n".join(linie))        # zapis atomowy: Obsidian może mieć LINT.md otwarty
    # podsumowanie dla `jarvo doctor` (doctor sam niczego nie zapisuje); ta sama treść = bez zapisu, więc drugi przebieg
    # wdrożenia niczego nie zmienia (data dnia zamiast znacznika czasu)
    tresc = json.dumps({"data": dzis(), "notatek": raport["notatek"], "bledy": len(bledy), "ostrzezenia": len(ostrz),
                        "informacje": len(info), "pierwsze_bledy": bledy[:5]}, ensure_ascii=False, indent=1) + "\n"
    with contextlib.suppress(OSError):
        cel = sk.stan / LINT_JSON
        if not cel.is_file() or cel.read_text(encoding="utf-8") != tresc:
            sk.stan.mkdir(parents=True, exist_ok=True)
            tmp = sk.stan / f"{LINT_JSON}.{os.getpid()}.tmp"
            tmp.write_text(tresc, encoding="utf-8", newline="\n")
            zamien_plik(tmp, cel)
    return raport


def nazwy_nieprzenosne(sk: Skarbiec) -> list[str]:
    """Ostrzeżenia K07 dla nazw, które nie przejdą na inny system (skarbiec przenosimy z kontenera na Windows i macOS,
    a Obsidian otwiera go na każdym): nazwy urządzeń Windows, kropka albo spacja na końcu, zapis spoza NFC, nazwy
    różniące się tylko wielkością liter w jednym katalogu i pełna ścieżka dłuższa niż MAX_SCIEZKI. Nazwy z dysku, nie
    z indeksu (na macOS indeks ma już NFC), bez katalogów z kropką (.git, .obsidian)."""
    out: list[str] = []
    for katalog, podkatalogi, pliki in os.walk(sk.root):
        podkatalogi[:] = sorted(d for d in podkatalogi if not d.startswith("."))
        baza = Path(katalog)
        rel_kat = baza.relative_to(sk.root).as_posix()
        wg_liter: dict[str, list[str]] = {}
        for nazwa in sorted([*podkatalogi, *(p for p in pliki if p.endswith(".md"))]):
            rel = nazwa if rel_kat == "." else f"{rel_kat}/{nazwa}"
            wg_liter.setdefault(unicodedata.normalize("NFC", nazwa).casefold(), []).append(rel)
            powod = nieprzenosna(nazwa)              # pełna nazwa z dysku (katalog albo plik z .md)
            if powod:
                out.append(f"nazwa nieprzenośna ({powod}): `{rel}`")
            elif nazwa.endswith(".md") and len(str(baza / nazwa)) > MAX_SCIEZKI:
                out.append(f"ścieżka dłuższa niż {MAX_SCIEZKI} znaków ({len(str(baza / nazwa))}; Windows bez długich ścieżek "
                           f"jej nie otworzy): `{rel}`")
        for rels in wg_liter.values():
            if len(rels) > 1:
                out.append("nazwy różnią się tylko wielkością liter (Windows i macOS widzą jeden plik): "
                           + ", ".join(f"`{r}`" for r in rels))
    return out


# ------------------------------------------------------------------------------------------------ status

def status(sk: Skarbiec, ix: Indeks) -> dict:
    ix.odswiez()
    wg_folderu: dict[str, int] = {}
    for r in ix.notatki():
        wg_folderu[r["folder"] or "/"] = wg_folderu.get(r["folder"] or "/", 0) + 1
    szkice = len(list((sk.root / "skrzynka").glob("*.md"))) if (sk.root / "skrzynka").is_dir() else 0
    log = sk.root / "LOG.md"
    ostatni = ""
    if log.exists():
        wpisy = re.findall(r"^## \[(\d{4}-\d{2}-\d{2})\] (\w+)", log.read_text(encoding="utf-8"), re.M)
        ostatni = " ".join(wpisy[-1]) if wpisy else ""
    def z_json(nazwa: str) -> dict:
        try:
            d = json.loads((sk.stan / nazwa).read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}
    komp = z_json("wiedza-kompilacja.json")
    return {"skarbiec": sk.root.as_posix(), "indeks": (sk.stan / "wiedza.db").as_posix(), "wg_folderu": wg_folderu, "szkice": szkice,
            "linki": ix.db.execute("SELECT COUNT(*) FROM linki WHERE rozwiazany = 1").fetchone()[0],
            "git": (sk.root / ".git").exists(), "ostatni_wpis": ostatni,
            "kompilacja": {"ostatnia": komp.get("ostatnia") or 0, "data": komp.get("data") or "",
                           "raport": komp.get("raport") or {}},
            "lint": z_json(LINT_JSON), "blokada": znacznik_blokady(sk.stan), "wektory": stan_wektorow(sk, ix)}


def stan_wektorow(sk: Skarbiec, ix: Indeks) -> dict:
    """Wektory w indeksie wg modelu i usługa (state/wektory.json, bez zapytania do niej): dla statusu i doctora."""
    klient = KlientWektorow(sk.stan)
    modele = {r[0]: r[1] for r in ix.db.execute("SELECT model, count(*) FROM wektory GROUP BY model")}
    notatek = sum(1 for r in ix.db.execute("SELECT sciezka FROM pliki") if not r[0].startswith(POZA_WYSZUKIWANIEM))
    return {"usluga": klient.dostepny, "model": klient.model, "powod": "" if klient.dostepny else klient.blad,
            "modele": modele, "wektorow": modele.get(klient.model, 0) if klient.model else sum(modele.values()),
            "notatek": notatek}


def opis_wektorow(w: dict) -> str:
    """Linia dla `indeksuj` i `zasiej` z wyniku Indeks.odswiez_wektory."""
    if not w["model"]:
        return "wektory: usługa wektorów nie działa, bez zmian (przypomnienia słowami; brakujące wektory nadrobi usługa po starcie)"
    return (f"✓ wektory: {w['wektorow']}/{w['notatek']} notatek ({w['nowe']} osadzonych, {w['usuniete']} usuniętych)"
            + (" · przerwane: usługa przestała odpowiadać, reszta następnym razem" if w["przerwane"] else ""))


# ------------------------------------------------------------------------------------------------ CLI

def main(argv: list[str] | None = None) -> int:
    utf8_wyjscie()
    ap = argparse.ArgumentParser(description="Skarbiec wiedzy floty Jarvo (docs/WIEDZA.md)")
    ap.add_argument("--skarbiec", default=DOMYSLNY_SKARBIEC, help="katalog skarbca (JARVO_KNOWLEDGE_DIR)")
    ap.add_argument("--stan", default=None, help="katalog na indeks (JARVO_STATE_DIR, domyślnie <skarbiec>/../state)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    z = sub.add_parser("zasiej", help="katalogi, huby, INDEX, LOG, orzeczenia, docs repo, git init")
    z.add_argument("--fleet", help="fleet.json z buildu (agenci, skille, skrypty)")
    z.add_argument("--docs", help="katalog docs/ repo → zrodla/jarvo-repo/")
    z.add_argument("--repo", help="wiedza/repo z buildu (pliki profili, materiały skilli, spis źródeł) → zrodla/jarvo-repo/")
    z.add_argument("--schema", default=str(Path(__file__).with_name("SCHEMA.md")), help="SCHEMA.md do skopiowania")
    i = sub.add_parser("indeksuj", help="indeks FTS5 + INDEX.md + listy hubów")
    i.add_argument("--pelny", action="store_true")
    s = sub.add_parser("szukaj", help="wyszukiwanie")
    s.add_argument("zapytanie")
    s.add_argument("--limit", type=int, default=5)
    s.add_argument("--folder")
    s.add_argument("--agent")
    s.add_argument("--zrodla", action="store_true", help="także zrodla/ i skrzynka/")
    s.add_argument("--silnik", choices=SILNIKI, default=SILNIK, help="wektory (domyślnie), hybryda (RRF z BM25) albo slowa")
    s.add_argument("--json", action="store_true")
    c = sub.add_parser("czytaj", help="cała notatka")
    c.add_argument("sciezka")
    c.add_argument("--json", action="store_true")
    w = sub.add_parser("zapisz", help="szkic do skrzynki")
    w.add_argument("--typ", required=True)
    w.add_argument("--tytul", required=True)
    w.add_argument("--tresc", help="treść (albo na stdin)")
    w.add_argument("--zrodlo", required=True)
    w.add_argument("--agent", default="")
    w.add_argument("--tagi", default="")
    w.add_argument("--linki", default="")
    w.add_argument("--skad", default="")
    o = sub.add_parser("orzeczenie", help="jedna datowana linia korekty od człowieka")
    o.add_argument("--kogo", required=True, help="wszyscy | <agent> | marki/<marka>")
    o.add_argument("--tresc", required=True)
    o.add_argument("--zrodlo", default="człowiek")
    l = sub.add_parser("lint", help="raport LINT.md")
    l.add_argument("--json", action="store_true")
    l.add_argument("--strict", action="store_true", help="kod 1 przy błędach")
    g = sub.add_parser("graf", help="węzły i linki jako JSON")
    sub.add_parser("cofnij", help="cofa ostatni punkt zapisu git")
    st = sub.add_parser("status")
    st.add_argument("--json", action="store_true")
    oc = sub.add_parser("ocena", help="trafność przypomnień na zestawie pytań: hit@5, MRR, czas (to samo szukanie co wtyczka)")
    oc.add_argument("plik", help='JSON: [{"pytanie": "...", "wzor": ["ścieżka notatki", ...]}]')
    oc.add_argument("--limit", type=int, default=5, help="ile notatek przypomnienia (k w hit@k)")
    oc.add_argument("--silnik", choices=SILNIKI, default=SILNIK,
                    help="wektory (domyślnie), hybryda (RRF słów i wektorów), slowa (BM25); bez usługi wektorów zawsze slowa")
    oc.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    sk = Skarbiec(a.skarbiec, a.stan)
    if a.cmd == "zasiej":
        fleet = json.loads(Path(a.fleet).read_text(encoding="utf-8")) if a.fleet else None
        r = zasiej(sk, fleet, Path(a.docs) if a.docs else None, Path(a.schema) if a.schema else None,
                   Path(a.repo) if a.repo else None)
        ix = Indeks(sk)
        ix.odswiez(pelny=True)
        n = zbuduj_index(sk, ix)
        odswiez_listy_hubow(sk, ix)
        ix.odswiez()
        sk.punkt_zapisu("zasiew skarbca: indeks")
        print(f"✓ zasiew: {r['huby']} hubów folderów, {r['agenci']} hubów agentów, {r['skille']} skilli zmienionych, {r['docs']} docs, "
              f"indeks {n} notatek, git: {'tak' if r['git'] else 'nie'}")
        print(opis_wektorow(ix.odswiez_wektory(KlientWektorow(sk.stan, WEKTORY_CZAS_ZAPISU_S))))
        ix.zamknij()
        return 0
    if not sk.root.is_dir():
        print(f"✗ brak skarbca {sk.root} (najpierw `zasiej`)", file=sys.stderr)
        return 2
    ix = Indeks(sk)
    try:
        if a.cmd == "indeksuj":
            r = ix.odswiez(pelny=a.pelny)
            n = zbuduj_index(sk, ix)
            h = odswiez_listy_hubow(sk, ix)
            ix.odswiez()
            print(f"✓ indeks: {r['pliki']} plików ({r['nowe']} nowych, {r['zmienione']} zmienionych, {r['usuniete']} usuniętych), INDEX.md: {n} notatek, huby odświeżone: {h}")
            print(opis_wektorow(ix.odswiez_wektory(KlientWektorow(sk.stan, WEKTORY_CZAS_ZAPISU_S))))
        elif a.cmd == "szukaj":
            ix.odswiez()
            wyn = ix.szukaj(a.zapytanie, limit=a.limit, folder=a.folder, agent=a.agent, zrodla=a.zrodla,
                            wektory=KlientWektorow(sk.stan, WEKTORY_CZAS_NARZEDZIA_S), silnik=a.silnik)
            if a.json:
                print(json.dumps(wyn, ensure_ascii=False, indent=1))
            elif not wyn:
                print("(nic nie znaleziono)")
            for r in ([] if a.json else wyn):
                print(f"- {r['sciezka']} · {r['tytul']}" + (f" · {r['streszczenie'][:110]}" if r["streszczenie"] else ""))
        elif a.cmd == "czytaj":
            try:
                n = sk.wczytaj(a.sciezka)
            except (ValueError, FileNotFoundError) as e:
                print(f"✗ {e}", file=sys.stderr)
                return 2
            if a.json:
                print(json.dumps({"sciezka": n.sciezka, "tytul": n.tytul, "fm": n.fm, "tresc": n.tresc}, ensure_ascii=False, indent=1))
            else:
                print(sk.plik(a.sciezka).read_text(encoding="utf-8"))
        elif a.cmd == "zapisz":
            tresc = a.tresc if a.tresc is not None else sys.stdin.read()
            try:
                rel = zapisz_szkic(sk, a.typ, a.tytul, tresc, a.zrodlo, a.agent, [t.strip() for t in a.tagi.split(",") if t.strip()],
                                   [x.strip() for x in a.linki.split(",") if x.strip()], a.skad)
            except ValueError as e:
                print(f"✗ {e}", file=sys.stderr)
                return 3
            print(f"✓ szkic: {rel}")
        elif a.cmd == "orzeczenie":
            try:
                linia = dodaj_orzeczenie(sk, a.kogo, a.tresc, a.zrodlo)
            except ValueError as e:
                print(f"✗ {e}", file=sys.stderr)
                return 3
            print(f"✓ orzeczenie: {linia}")
        elif a.cmd == "lint":
            r = lint(sk, ix)
            if a.json:
                print(json.dumps(r, ensure_ascii=False, indent=1))
            else:
                print(f"lint: {r['notatek']} notatek · błędy: {len(r['bledy'])} · ostrzeżenia: {len(r['ostrzezenia'])} · informacje: {len(r['informacje'])} → LINT.md")
                for b in r["bledy"][:20]:
                    print(f"  ✗ {b}")
            if a.strict and r["bledy"]:
                return 1
        elif a.cmd == "graf":
            ix.odswiez()
            print(json.dumps(ix.graf(), ensure_ascii=False))
        elif a.cmd == "cofnij":
            print(sk.cofnij())
        elif a.cmd == "status":
            r = status(sk, ix)
            if a.json:
                print(json.dumps(r, ensure_ascii=False, indent=1))
            else:
                print(f"skarbiec: {r['skarbiec']} · notatek: {sum(r['wg_folderu'].values())} · linków: {r['linki']} · szkiców: {r['szkice']} · git: {'tak' if r['git'] else 'nie'} · ostatni wpis: {r['ostatni_wpis'] or '-'}")
                for f, n in sorted(r["wg_folderu"].items()):
                    print(f"  {f:12} {n}")
                wek = r["wektory"]
                print(f"wektory: {wek['wektorow']}/{wek['notatek']} notatek · usługa: "
                      + (f"działa ({wek['model']})" if wek["usluga"] else f"nie działa ({wek['powod']}; przypomnienia słowami)"))
        elif a.cmd == "ocena":
            try:
                wektory = None if a.silnik == "slowa" else KlientWektorow(sk.stan)
                r = ocena(ix, json.loads(Path(a.plik).read_text(encoding="utf-8")), limit=a.limit, wektory=wektory,
                          silnik=a.silnik)
            except (OSError, ValueError) as e:
                print(f"✗ {e}", file=sys.stderr)
                return 2
            if a.json:
                print(json.dumps(r, ensure_ascii=False, indent=1))
            else:
                print(f"ocena: {r['pytan']} pytań · hit@{r['k']}: {r['trafione']}/{r['pytan']} ({r['hit_at_k']:.3f}) · MRR {r['mrr']:.3f} · "
                      f"ms: mediana {r['ms_mediana']}, max {r['ms_max']} · silnik: "
                      + ", ".join(f"{s} {n}" for s, n in sorted(r["silniki"].items())))
                for p in r["pytania"]:
                    if not p["pozycja"]:
                        print(f"  ✗ {p['pytanie'][:80]} → {', '.join(p['wyniki']) or '(nic)'}")
    finally:
        ix.zamknij()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
