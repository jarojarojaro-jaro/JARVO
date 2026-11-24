"""Aktualizacja Jarva natywnie: `jarvo update` i pomocnik aktualizacji dla panelu (docs/NATYWNIE.md: N09, c4
„jarvo update”, S09, H16, D07, N15, I30, I40 „wersje obok siebie”).

  jarvo update [--sprawdz] [--ref REF] [--json]
        1. sprawdzenie wydania: GitHub API `commits/<ref>` (Accept: application/vnd.github.sha) z refem instalacji:
           `--ref` (zapamiętany w `<stan>/aktualizacja.json` dla następnych aktualizacji), JARVO_REF, potem nowszy
           z dwóch: `.jarvo-ref` bieżącego kodu (zapisują go bootstrap i każda aktualizacja) albo zapamiętany --ref,
           inaczej main; ponowna instalacja z innym JARVO_REF wygrywa więc ze starszym --ref. Publiczne
           repo bez niczego; prywatna kopia: JARVO_TOKEN ze zmiennej albo z magazynu systemu (Menedżer poświadczeń
           Windows, pęk kluczy macOS, libsecret na Linuksie, zapasowo plik 0600 `<dane>/jarvo/konfig/github-token`;
           wpis zapisze `jarvo klucz`, N15), tylko w nagłówku do api.github.com (add_unredirected_header: po
           przekierowaniu na codeload już bez niego), nigdy na ekranie, w logu, w update.json ani w otoczeniu
           programów, które stąd startują. Ta sama wersja = koniec bez zmian (poza sprzątaniem starych wersji),
        2. kod nowej wersji do `<program>/app/<sha12>` obok starej: archiwum codeload jak w bootstrapie (prywatna kopia:
           `tarball` przez API), rozpakowane bezpiecznie (jarvo/pobieracz.rozpakuj) do `<sha12>.new`, potem zmiana
           nazwy; `.jarvo-wersja` (pełny SHA) i `.jarvo-ref`. Urwane pobieranie (także IncompleteRead) ponawiamy
           3 razy, a uszkodzone archiwum pobieramy jeszcze raz,
        3. instalator NOWEJ wersji (`python -I -u -X utf8 <nowa>/jarvo/start.py instaluj` z opcjami tej instalacji:
           --bez-path, gdy polecenie nie trafiło do PATH, --bez-autostartu, gdy autostart jest wyłączony,
           --bez-startu, gdy serwis nie działał): narzędzia i venvy po sumach, Hermes przy zmianie pinu, front,
           flota; sam przełącza current.json (poprzedni zostaje jako current.poprzedni.json) i uruchamia serwis od
           nowa przez nadzorcę. Nowy Python przy tym samym pinie Hermesa albo locku venvu też nie przebudowuje
           niczego w miejscu: checkout i venvy tej wersji powstają obok (jarvo/hermes.katalog_dla, venvy.katalog_dla),
           bo z gotowych działa jeszcze serwis poprzedniej wersji, a powrót przy błędzie ich potrzebuje,
        4. `jarvo doctor --json` nowej wersji wobec przebiegu sprzed aktualizacji: błąd w sprawdzeniu, które przed nią
           przechodziło, to regresja, ale dopiero gdy trwa po rozgrzewce (do 120 s, co 10 s: instalator czeka na
           panel, a API bramy wstaje chwilę później; sprawdzone na Windows 11),
        5. przy błędzie instalatora albo regresji: powrót do current.poprzedni.json instalatorem POPRZEDNIEJ wersji
           (z jej katalogu, te same opcje: przywraca też narzędzia, programy floty, polecenie jarvo, autostart
           i serwis); gdy i on zawiedzie, sam current.json sprzed aktualizacji i start serwisu; po powrocie stałe
           ścieżki `<program>/app/current` i `<program>/venvs/narzedzia` znowu wskazują poprzednią wersję
           (srodowisko.uzgodnij_stale, także gdy jej instalator ich nie zna),
        6. po udanej: stare wersje (kod, checkouty Hermesa, front panelu w `<program>/web-dist`, venvy, narzędzia:
           wszystko, czego ścieżek nie ma w current.json ani w narzedzia.json, resztki `.new`, `.stary-*`, `.usun-*`,
           stare archiwa w `<cache>/pobrane`) znikają, gdy żaden proces z nich nie korzysta (program albo wiersz
           polecenia, jarvo/odinstalowanie.uzywaja: to jedyna ochrona, bo na Windows katalog z działającym python.exe
           i załadowanym .dll przechodzi zmianę nazwy; proces ze stałą ścieżką w wierszu polecenia chroni każdą wersję
           za nią, bo nie wiadomo, którą wskazywała przy jego starcie; samych stałych ścieżek sprzątanie nie rusza).
           Kod (`app`) i venv zostają też wtedy, gdy ich ścieżkę ma wpisaną plik poza buildem (odwolania: konfig
           Jarva *.json i *.yaml, pamięć profili, ~/.local/bin, jednostki systemd użytkownika, crontab, LaunchAgents
           na macOS, Autostart i Harmonogram zadań na Windows; nigdy *.env ani pliki o nazwach sekretów): log podaje
           plik i linię i radzi stałą ścieżkę (20.11: sesje.json Kernela z usuniętym venvem, pobieranie linków padało
           całą noc).
           Katalog najpierw dostaje nazwę `<nazwa>.usun-<czas>` (niepełny
           nie wygląda jak gotowa wersja; nie przejdzie jej tylko plik otwarty bez FILE_SHARE_DELETE albo katalog
           bieżący procesu). Na Windows proces w tej samej sesji, którego ścieżki ani wiersza polecenia nie da się
           odczytać (np. `jarvo chat` uruchomiony jako administrator), a ma nazwę programu z wersji Jarva (python.exe,
           node.exe…), wstrzymuje całe sprzątanie. Zajęte zostają do następnej aktualizacji (np. pracownicy kanbana
           kończą kartę na starej wersji, H07).
        Jedna aktualizacja naraz (`<stan>/aktualizacja.lock`), dziennik `<logi>/aktualizacja.log` (ekran to jego kopia:
        zniknięty czytelnik wyjścia, np. przerwany potok, nie przerywa przebiegu), stan bez sekretów w
        `<stan>/aktualizacja.json`: wynik przebiegu zawsze w komplecie (wynik, kiedy, opis, wersja, poprzednia, cel),
        a sprawdzenie, które widzi najnowszą wersję, zastępuje nieaktualny wynik wynikiem „aktualne”. Każdy błąd, także
        nieprzewidziany (np. uszkodzone archiwum), kończy się komunikatem po polsku, powrotem do poprzedniej wersji
        (gdy coś się przełączyło) i stanem „failed” dla panelu. Karta kanbana w toku: odmowa z opisem także w
        update.json (`error`). Kod 0: aktualne, zaktualizowane albo (--sprawdz) sprawdzone; 1: błąd albo wycofanie.
        Limity: JARVO_UPDATE_TIMEOUT (instalator, domyślnie 3600 s), JARVO_UPDATE_ROZGRZEWKA (120 s).

  jarvo update --pomocnik [--raz]
        pomocnik aktualizacji (S09): usługa `aktualizacje` nadzorcy (jarvo/nadzorca.uslugi_jarva, docs/NATYWNIE.md c2)
        dla przycisku w panelu; kontrakt plików z panelem bez zmian (hq/plugin/plugin_api.py). Co 3 s prośba
        `<dane>/jarvo/state/update-request` („check” albo „update”; „Zaktualizuj, gdy skończą” to ta sama prośba,
        którą obserwator panelu zapisuje po 30 s bez pracy), co JARVO_UPDATE_CHECK s (domyślnie 3600: limit API bez
        klucza to 60 zapytań na godzinę) sprawdzenie, co 60 s puls. Pierwsze sprawdzenie od razu, chyba że ostatnie
        udane dla tej wersji było niedawno (restart serwisu nie pyta GitHuba za każdym razem). Stan dla panelu:
        `<dane>/jarvo/state/update.json` (state idle|updating|done|failed, behind, commits, branch, current, latest,
        checked_at, beat, started_at, finished_at, log, error; „failed” zostaje tylko przy wersji starszej niż na
        GitHubie, każde sprawdzenie najnowszej zamienia go na „idle”). „update” uruchamia `jarvo update` jako osobny,
        odłączony proces (w jednostce systemd --user Jarva przez `systemd-run --user --scope`, bo KillMode=mixed
        zabiłby go razem z nadzorcą): instalator nowej wersji zatrzymuje nadzorcę razem z pomocnikiem, a wyjście tego
        procesu idzie do `<logi>/aktualizacja-panel.log`. Stan „updating”, którego żaden `jarvo update` nie trzyma
        (blokada wolna od CZAS_STARTU s: proces zabity albo nie wystartował), pomocnik zamienia na „failed”. Błąd
        jednego obiegu (np. sieci) nie kończy pętli; SIGTERM i Ctrl+Break od nadzorcy kończą ją kodem 0.

Zmienna tylko dla prób: JARVO_FAKE_KOD = katalog z kodem Jarva udający wersję z GitHuba (wersja z jego
`.jarvo-wersja` albo HEAD gita; bez sieci). Testy podmieniają też adresy API i KOD (serwer na 127.0.0.1).
"""
from __future__ import annotations

import contextlib
import gzip
import http.client
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path
from typing import Callable

from . import instalator, manifest, pobieracz, przenosne, srodowisko, venvy, zmiany_hosta
from .instalator import Otoczenie
from .odinstalowanie import (MAGAZYN_KLUCZA, Proces, Zaplecze, env_podprocesu, rozmiar, uklad_instalacji, usun_drzewo,
                             uzywaja, zawiera_sciezke)
from .sciezki import LINUX, MACOS, WINDOWS, Uklad

REPO_GH = "jarojarojaro-jaro/JARVO"           # jak $JarvoRepo w jarvo/bootstrap/install.ps1 i REPO_GH w install.sh
API = "https://api.github.com"
KOD = "https://codeload.github.com"
REF_DOMYSLNY = "main"
PLIK_WERSJI = ".jarvo-wersja"                 # w katalogu kodu: pełny SHA (bootstrap i update)
PLIK_REFU = ".jarvo-ref"                      # w katalogu kodu: ref, z którego kod pobrano
STAN = "aktualizacja.json"                    # <stan>: ref, ostatnie sprawdzenie i wynik, bez sekretów
ZAMEK = "aktualizacja.lock"
LOG = "aktualizacja.log"
LOG_PANELU = "aktualizacja-panel.log"         # wyjście `jarvo update` uruchomionego przez pomocnika
STAN_PANELU = Path("state") / "update.json"   # w <dane>/jarvo (hq/plugin/plugin_api.py UPDATE_FILE)
PROSBA_PANELU = Path("state") / "update-request"
MAGAZYN = MAGAZYN_KLUCZA                      # nazwa klucza GitHuba w magazynie systemu (N15): jarvo-github
PLIK_KLUCZA = Path("konfig") / "github-token"  # w <dane>/jarvo: zapas na Linuksie bez libsecret (plik 0600)
CZAS_INSTALATORA = 3600.0                     # s; JARVO_UPDATE_TIMEOUT
CZAS_DOCTORA = 600.0
CZAS_ROZGRZEWKI = 120.0                       # s, przez które regresja doctora może być rozgrzewką usług
CO_ILE_ROZGRZEWKA = 10.0
CO_ILE_SPRAWDZAC = 3600                       # s; JARVO_UPDATE_CHECK
CO_ILE_PULS = 60.0
CO_ILE_PROSBA = 3.0
CO_ILE_STAN = 15.0                            # s między zapisami update.json w trakcie aktualizacji
CZAS_STARTU = 120.0                           # s na wzięcie blokady przez `jarvo update` z panelu (wolny dysk, antywirus)
PROBY_ARCHIWUM = 2                            # pobranie i rozpakowanie kodu: uszkodzone archiwum = jeszcze raz
# programy z wersji Jarva (narzędzia, venvy, Hermes): proces o takiej nazwie bez widocznej ścieżki wstrzymuje sprzątanie
PROGRAMY_JARVA = frozenset({"python.exe", "pythonw.exe", "hermes.exe", "node.exe", "uv.exe", "uvx.exe", "git.exe",
                            "bash.exe", "sh.exe"})
OGON = 40                                     # wierszy logu w update.json
ZMIANY_NAJWYZEJ = 50                          # tyle commitów pytamy o listę zmian (behind > 50 = „50+”)
FAKE = "JARVO_FAKE_KOD"
_SHA = re.compile(r"[0-9a-f]{40}")
_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/+-]{0,199}")
_POMIN_KOPII = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".pytest_cache", "node_modules")
_RESZTKI = re.compile(r"\.(?:new|stary-\d+|usun-\d+)$")


class BladAktualizacji(RuntimeError):
    """Aktualizacja się nie udała (komunikat po polsku z radą, bez sekretów)."""


# ---------------------------------------------------------------- wersja, ref, stan

def wersja_kodu(app: Path | str | None) -> str | None:
    """Pełny SHA kodu: `.jarvo-wersja` (bootstrap, update) albo HEAD gita (kopia repo); None, gdy nie wiadomo."""
    if not app:
        return None
    try:
        sha = (Path(app) / PLIK_WERSJI).read_text(encoding="utf-8").split()[0].lower()
    except (OSError, IndexError):
        sha = (instalator.head_gita(Path(app)) or "").lower()
    return sha if _SHA.fullmatch(sha) else None


def ref_kodu(app: Path | str | None) -> str | None:
    try:
        ref = (Path(app) / PLIK_REFU).read_text(encoding="utf-8").strip() if app else ""
    except OSError:
        return None
    return ref if _REF.fullmatch(ref) and ".." not in ref else None


def stan(u: Uklad) -> dict:
    """`<stan>/aktualizacja.json`."""
    return srodowisko.wczytaj_json(u.stan / STAN)


def zapisz_stan(u: Uklad, **pola) -> None:
    dane = {**stan(u), **pola}
    with contextlib.suppress(OSError):
        przenosne.zapisz_atomowo(u.stan / STAN, json.dumps(dane, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _dobry_ref(ref: str) -> bool:
    return bool(_REF.fullmatch(ref)) and ".." not in ref


def ustal_ref(u: Uklad, env: dict, jawny: str | None = None) -> str:
    """Ref aktualizacji: --ref, JARVO_REF, potem nowszy z dwóch zapisów: `.jarvo-ref` bieżącego kodu (bootstrap
    i każda aktualizacja; czas zapisu pliku) albo --ref zapamiętany przez zapamietaj_ref (`ref_jawny`, `ref_kiedy`
    w `<stan>/aktualizacja.json`), inaczej main. Ref, który tylko przyszedł z kodu albo z domyślnego main, nie jest
    zapamiętywany, więc ponowna instalacja bootstrapem z innym JARVO_REF go zmienia. Zły zapis (spacje, „..”) to błąd
    tylko dla jawnego; zapisany pomijamy."""
    for kandydat, zrodlo in ((jawny, "--ref"), (env.get("JARVO_REF"), "JARVO_REF")):
        if kandydat:
            kandydat = kandydat.strip()
            if not _dobry_ref(kandydat):
                raise BladAktualizacji(f"{zrodlo}={kandydat!r}: to nie nazwa gałęzi, tagu ani SHA.")
            return kandydat
    app = srodowisko.biezace(u).get("app")
    z_kodu = ref_kodu(app)
    s = stan(u)
    zapamietany = str(s.get("ref_jawny") or "").strip()
    if not _dobry_ref(zapamietany):
        return z_kodu or REF_DOMYSLNY
    if not z_kodu:
        return zapamietany
    try:
        kiedy_kodu = (Path(str(app)) / PLIK_REFU).stat().st_mtime
        kiedy_jawnego = float(s.get("ref_kiedy") or 0)
    except (OSError, TypeError, ValueError):
        return z_kodu
    return zapamietany if kiedy_jawnego > kiedy_kodu else z_kodu


def zapamietaj_ref(u: Uklad, ref: str) -> None:
    """`jarvo update --ref REF`: REF zostaje refem instalacji także wtedy, gdy wersja się nie zmieniła (wtedy kod nie
    dostaje nowego `.jarvo-ref`) albo aktualizacja wróciła do poprzedniej wersji."""
    zapisz_stan(u, ref_jawny=ref, ref_kiedy=time.time())


# ---------------------------------------------------------------- klucz do prywatnej kopii (N15)

def _klucz_dobry(k: str | None) -> str | None:
    k = (k or "").strip()
    return k if 8 <= len(k) <= 512 and k.isascii() and k.isprintable() and " " not in k else None


def _magazyn_windows() -> str | None:
    """Menedżer poświadczeń Windows: poświadczenie ogólne `jarvo-github` (CredReadW), hasło jako UTF-16 albo UTF-8."""
    import ctypes
    from ctypes import wintypes

    class _Cred(ctypes.Structure):           # CREDENTIALW
        _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
                    ("Comment", wintypes.LPWSTR), ("LastWritten", wintypes.FILETIME),
                    ("CredentialBlobSize", wintypes.DWORD), ("CredentialBlob", ctypes.c_void_p),
                    ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
                    ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
                    ("UserName", wintypes.LPWSTR)]
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    adv.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                              ctypes.POINTER(ctypes.POINTER(_Cred))]
    adv.CredReadW.restype = wintypes.BOOL
    adv.CredFree.argtypes = [ctypes.c_void_p]
    wsk = ctypes.POINTER(_Cred)()
    if not adv.CredReadW(MAGAZYN, 1, 0, ctypes.byref(wsk)):           # CRED_TYPE_GENERIC
        return None
    try:
        c = wsk.contents
        dane = ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize) if c.CredentialBlob else b""
    finally:
        adv.CredFree(wsk)
    if len(dane) % 2 == 0 and b"\x00" in dane:
        with contextlib.suppress(UnicodeDecodeError):
            return dane.decode("utf-16-le")
    return dane.decode("utf-8", "replace")


def _magazyn_polecenie(argv: list[str]) -> str | None:
    """Klucz z programu systemu (security na macOS, secret-tool na Linuksie): samo wyjście, bez logowania."""
    if not os.path.isabs(argv[0]) or not os.path.exists(argv[0]):
        return None
    try:
        r = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.decode("utf-8", "replace").strip() if r.returncode == 0 else None


def czytaj_magazyn(u: Uklad) -> str | None:
    """Klucz GitHuba z magazynu systemu (N15) albo None. Tylko odczyt; zapisze go `jarvo klucz`."""
    try:
        if WINDOWS:
            return _klucz_dobry(_magazyn_windows())
        if MACOS:
            return _klucz_dobry(_magazyn_polecenie(["/usr/bin/security", "find-generic-password", "-s", MAGAZYN,
                                                    "-w"]))
        narzedzie = shutil.which("secret-tool", path="/usr/bin:/bin:/usr/local/bin")
        if narzedzie:
            k = _klucz_dobry(_magazyn_polecenie([narzedzie, "lookup", "service", MAGAZYN]))
            if k:
                return k
        plik = u.jarvo_dane / PLIK_KLUCZA
        if plik.is_file() and (WINDOWS or plik.stat().st_mode & 0o077 == 0):    # tylko plik 0600 właściciela
            return _klucz_dobry(plik.read_text(encoding="utf-8").splitlines()[0] if plik.stat().st_size else "")
    except (OSError, ValueError, IndexError):
        return None
    return None


def klucz_github(u: Uklad, env: dict, magazyn: Callable[[Uklad], str | None] = czytaj_magazyn) -> str | None:
    """JARVO_TOKEN ze zmiennej albo z magazynu systemu; publiczne repo działa bez niego. Próba z JARVO_FAKE_KOD nie
    łączy się z GitHubem, więc magazynu nie czyta."""
    if env.get(FAKE):
        return None
    return _klucz_dobry(env.get("JARVO_TOKEN")) or magazyn(u)


# ---------------------------------------------------------------- GitHub

def _bez_klucza(tekst: str, klucz: str | None) -> str:
    return tekst.replace(klucz, "<ukryty>") if klucz else tekst


def _otworz(url: str, *, klucz: str | None = None, accept: str = "application/vnd.github+json",
            czas: float = 30.0):
    """Odpowiedź HTTP (do użycia w `with`). Tylko https (pętla zwrotna: testy). Klucz tylko w nagłówku do API, jako
    nieprzenoszony przy przekierowaniu (codeload dostaje tymczasowy adres bez nagłówka Authorization)."""
    if not url.startswith(("https://", "http://127.0.0.1:")):
        raise BladAktualizacji(f"tylko adresy https (dostałem {url[:40]}…)")
    zadanie = urllib.request.Request(url, headers={"User-Agent": "jarvo-aktualizacja", "Accept": accept})
    if url.startswith(API + "/"):
        zadanie.add_header("X-GitHub-Api-Version", "2022-11-28")
        if klucz:
            zadanie.add_unredirected_header("Authorization", f"Bearer {klucz}")
    return urllib.request.urlopen(zadanie, timeout=czas)


def _blad_http(e: Exception, co: str, klucz: str | None) -> BladAktualizacji:
    if isinstance(e, urllib.error.HTTPError):
        limit = e.headers.get("X-RateLimit-Remaining") if e.headers else None
        if e.code in (403, 429) and limit == "0":
            return BladAktualizacji(f"{co}: GitHub odmówił, bo skończył się limit zapytań (bez klucza 60 na godzinę "
                                    "z jednego adresu). Spróbuj za godzinę.")
        if e.code == 401:
            return BladAktualizacji(f"{co}: GitHub odrzucił klucz (JARVO_TOKEN albo magazyn systemu: wygasł albo "
                                    "nie ma prawa Contents: read).")
        if e.code == 404:
            return BladAktualizacji(f"{co}: GitHub nie zna tej wersji (HTTP 404). Zły ref albo prywatna kopia repo "
                                    "bez klucza: ustaw JARVO_TOKEN.")
        return BladAktualizacji(f"{co}: HTTP {e.code} od GitHuba.")
    if isinstance(e, http.client.HTTPException):          # IncompleteRead, RemoteDisconnected: urwane w trakcie
        return BladAktualizacji(f"{co}: połączenie z GitHubem urwało się w trakcie ({type(e).__name__}). Spróbuj "
                                "jeszcze raz.")
    powod = getattr(e, "reason", e)
    return BladAktualizacji(_bez_klucza(f"{co}: brak połączenia z GitHubem ({powod}). Sprawdź sieć i spróbuj "
                                        "jeszcze raz.", klucz))


def zdalna_wersja(ref: str, klucz: str | None, env: dict) -> str:
    """Pełny SHA refu: z JARVO_FAKE_KOD (próby), wprost (ref to pełny SHA) albo z API `commits/<ref>`."""
    fake = env.get(FAKE)
    if fake:
        sha = wersja_kodu(Path(fake))
        if not sha or not (Path(fake) / "jarvo" / "start.py").is_file():
            raise BladAktualizacji(f"{FAKE}={fake}: to nie katalog kodu Jarva z wersją (.jarvo-wersja albo git).")
        return sha
    if _SHA.fullmatch(ref.lower()):
        return ref.lower()
    adres = f"{API}/repos/{REPO_GH}/commits/{urllib.parse.quote(ref, safe='/')}"
    try:
        with _otworz(adres, klucz=klucz, accept="application/vnd.github.sha") as odp:
            sha = odp.read(200).decode("ascii", "replace").strip().lower()
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as e:
        raise _blad_http(e, f"sprawdzenie wersji {ref}", klucz) from None
    if not _SHA.fullmatch(sha):
        raise BladAktualizacji(f"API GitHuba nie podało SHA dla {ref!r}.")
    return sha


def nowe_zmiany(baza: str | None, cel: str, klucz: str | None, env: dict) -> tuple[int, list[dict], bool]:
    """(ile commitów brakuje, do 20 najnowszych {"sha", "subject"}, czy liczba jest pełna) między `baza` a `cel`.
    Bez bazy albo przy błędzie: (1, [], False)."""
    if env.get(FAKE):
        return 1, [{"sha": cel[:7], "subject": f"wersja z {FAKE}"}], True
    if not baza:
        return 1, [], False
    adres = f"{API}/repos/{REPO_GH}/commits?sha={cel}&per_page={ZMIANY_NAJWYZEJ}"
    try:
        with _otworz(adres, klucz=klucz) as odp:
            lista = json.loads(odp.read(8 << 20).decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException):
        return 1, [], False
    zmiany = []
    for c in lista if isinstance(lista, list) else []:
        sha = str((c or {}).get("sha") or "")
        if sha == baza:
            return len(zmiany), zmiany[:20], True
        temat = str(((c or {}).get("commit") or {}).get("message") or "").split("\n", 1)[0][:200]
        zmiany.append({"sha": sha[:7], "subject": temat})
    return max(len(zmiany), 1), zmiany[:20], False


_ZLE_ARCHIWUM = (tarfile.TarError, EOFError, zlib.error, gzip.BadGzipFile)


def pobierz_kod(u: Uklad, sha: str, ref: str, klucz: str | None, env: dict, log: Callable[[str], None]) -> Path:
    """Kod wersji `sha` w `<program>/app/<sha12>` (gotowy zostaje). Archiwum commitu z codeload (prywatna kopia:
    `tarball` przez API z kluczem) albo kopia katalogu JARVO_FAKE_KOD; najpierw do `<sha12>.new`. Uszkodzone
    archiwum (urwany gzip, zły tar) pobieramy jeszcze raz, potem BladAktualizacji po polsku."""
    cel = u.program / "app" / sha[:12]
    if (cel / "jarvo" / "start.py").is_file() and wersja_kodu(cel) == sha:
        log(f"kod {sha[:12]}: już jest ({cel})")
        return cel
    nowy = cel.with_name(cel.name + ".new")
    if os.path.lexists(nowy):
        usun_drzewo(nowy)
    fake = env.get(FAKE)
    try:
        if fake:
            log(f"kod {sha[:12]}: kopia z {fake} ({FAKE}, tylko próby)")
            shutil.copytree(fake, nowy, ignore=_POMIN_KOPII, symlinks=not WINDOWS)
        else:
            adres = (f"{API}/repos/{REPO_GH}/tarball/{sha}" if klucz else f"{KOD}/{REPO_GH}/tar.gz/{sha}")
            archiwum = u.cache / "pobrane" / f"jarvo-{sha}.tar.gz"
            for proba in range(1, PROBY_ARCHIWUM + 1):
                log(f"pobieram kod {sha[:12]} ({adres})")
                _pobierz_plik(adres, archiwum, klucz, log)
                try:
                    pobieracz.rozpakuj(archiwum, nowy, "tar.gz", 1)
                    break
                except _ZLE_ARCHIWUM as e:
                    usun_drzewo(nowy)
                    opis = f"{type(e).__name__}: {str(e)[:160]}"
                    if proba == PROBY_ARCHIWUM:
                        raise BladAktualizacji(f"archiwum kodu wersji {sha[:12]} jest uszkodzone ({opis}) także po "
                                               "ponownym pobraniu. Spróbuj później jeszcze raz (jarvo update).") \
                            from None
                    log(f"    archiwum uszkodzone ({opis}): pobieram jeszcze raz")
                finally:
                    archiwum.unlink(missing_ok=True)
        if not (nowy / "jarvo" / "start.py").is_file():
            raise BladAktualizacji(f"w kodzie wersji {sha[:12]} nie ma jarvo/start.py (zły ref?).")
        (nowy / PLIK_WERSJI).write_text(sha + "\n", encoding="utf-8")
        (nowy / PLIK_REFU).write_text(ref + "\n", encoding="utf-8")
        if os.path.lexists(cel):
            usun_drzewo(cel)                      # niepełny katalog po przerwanej próbie
        os.replace(nowy, cel)
    except BaseException:
        with contextlib.suppress(OSError):
            usun_drzewo(nowy)
        raise
    return cel


def _pobierz_plik(adres: str, cel: Path, klucz: str | None, log: Callable[[str], None]) -> None:
    """Archiwum kodu strumieniem do pliku (bez sumy, jak w bootstrapie: HTTPS i SHA z API wystarczą), 3 próby: także
    po urwanym strumieniu (http.client.IncompleteRead, gdy codeload zamknie połączenie przed końcem chunked)."""
    cel.parent.mkdir(parents=True, exist_ok=True)
    czesc = cel.with_name(cel.name + ".czesc")
    ostatni: Exception | None = None
    for proba in range(3):
        try:
            # API `tarball` przyjmuje tylko typy GitHuba (octet-stream = HTTP 415) i przekierowuje na codeload
            accept = "application/vnd.github+json" if adres.startswith(API + "/") else "application/octet-stream"
            with _otworz(adres, klucz=klucz, accept=accept, czas=60) as odp, \
                    open(czesc, "wb") as f:
                razem, nastepny = 0, 10 << 20
                for kawalek in iter(lambda: odp.read(1 << 16), b""):
                    f.write(kawalek)
                    razem += len(kawalek)
                    if razem >= nastepny:
                        log(f"    {razem / 1e6:.0f} MB")
                        nastepny += 10 << 20
            os.replace(czesc, cel)
            return
        except urllib.error.HTTPError as e:
            ostatni = e
            if e.code in (401, 403, 404):
                break
        except (urllib.error.URLError, OSError, TimeoutError, http.client.HTTPException) as e:
            ostatni = e
            log(f"    pobieranie przerwane ({type(e).__name__}), próba {proba + 2} z 3" if proba < 2 else
                f"    pobieranie przerwane ({type(e).__name__})")
        time.sleep(min(2 ** proba, 10))
    czesc.unlink(missing_ok=True)
    raise _blad_http(ostatni or OSError("?"), "pobranie kodu Jarva", klucz)


# ---------------------------------------------------------------- stan dla panelu (kontrakt z HQ)

def plik_panelu(u: Uklad) -> Path:
    return u.jarvo_dane / STAN_PANELU


def stan_panelu(u: Uklad) -> dict:
    return srodowisko.wczytaj_json(plik_panelu(u))


def zapisz_panel(u: Uklad, **pola) -> None:
    """`<dane>/jarvo/state/update.json` dla panelu (pola jak w scripts/updater.py, czasy jako sekundy epoki)."""
    if not u.jarvo_dane.is_dir():
        return
    dane = {**stan_panelu(u), **pola, "mode": "natywny", "auto": False}
    with contextlib.suppress(OSError):
        przenosne.zapisz_atomowo(plik_panelu(u), json.dumps(dane, ensure_ascii=False) + "\n")


def _stan_po_sprawdzeniu(u: Uklad, aktualne: bool = False) -> str:
    """„done” zostaje do następnej aktualizacji (panel pokazuje „Odśwież”), „failed” tylko przy wersji starszej niż
    na GitHubie: gdy działa już najnowsza, porażka nikogo nie dotyczy (20.11: udana aktualizacja z CLI po przerwanej
    zostawiła w panelu „Aktualizacja nieudana” i „Spróbuj ponownie”). Reszta to „idle”."""
    s = stan_panelu(u).get("state")
    return s if s == "done" or (s == "failed" and not aktualne) else "idle"


def uzgodnij_wynik(u: Uklad, obecna: str, ref: str) -> None:
    """Sprawdzenie pokazało, że działa najnowsza wersja refu: wynik w aktualizacja.json, który mówi o innej wersji
    albo o porażce, już jej nie opisuje (przełączył ją instalator, bootstrap albo przebieg przerwany po przełączeniu),
    więc zastępuje go komplet „aktualne”. Pola z wcześniejszych przebiegów nie zostają."""
    s = stan(u)
    if s.get("wynik") in ("zaktualizowano", "aktualne") and s.get("wersja") == obecna:
        return
    zapisz_stan(u, wynik="aktualne", kiedy=time.strftime("%Y-%m-%dT%H:%M:%S"), wersja=obecna,
                poprzednia=s.get("wersja"), cel=None, opis=f"Działa wersja {obecna}, najnowsza na {ref}.")


# ---------------------------------------------------------------- sprzątanie starych wersji

def _katalogi_w(katalog: Path) -> list[Path]:
    """Podkatalogi bez dowiązań i junction (stałe ścieżki `app/current`, `venvs/narzedzia` nie są wersjami)."""
    try:
        return sorted(Path(e.path) for e in os.scandir(katalog)
                      if e.is_dir(follow_symlinks=False) and not przenosne.jest_dowiazaniem(Path(e.path)))
    except OSError:
        return []


def _przez_stala(link: Path, lista: list[Proces], pomin: set[int]) -> list[Proces]:
    """Procesy, które mają stałą ścieżkę `link` (dosłownie, bez rozwijania dowiązania: odinstalowanie.uzywaja
    rozwinęłoby ją do bieżącej wersji) w programie albo wierszu polecenia, z separatorem, cudzysłowem, spacją albo
    końcem za nią."""
    postaci = {os.path.abspath(link), os.path.join(os.path.realpath(link.parent), link.name)}
    if WINDOWS:
        postaci |= {x.replace("\\", "/") for x in postaci}
    if WINDOWS or MACOS:
        postaci = {x.casefold() for x in postaci}

    def jest(tekst: str) -> bool:
        t = tekst.casefold() if WINDOWS or MACOS else tekst
        for x in postaci:
            i = t.find(x)
            while i >= 0:
                if i + len(x) == len(t) or t[i + len(x)] in "\\/\"' \t":
                    return True
                i = t.find(x, i + 1)
        return False
    return [p for p in lista if p.pid not in pomin and (jest(p.program or "") or jest(p.polecenie or ""))]


def _sciezki_w(dane) -> set[str]:
    """Wszystkie ścieżki bezwzględne z wartości (słowniki i listy w głąb), znormalizowane do porównań."""
    wynik: set[str] = set()
    if isinstance(dane, dict):
        for v in dane.values():
            wynik |= _sciezki_w(v)
    elif isinstance(dane, list):
        for v in dane:
            wynik |= _sciezki_w(v)
    elif isinstance(dane, str) and dane.strip() and os.path.isabs(dane):
        wynik.add(os.path.normcase(os.path.abspath(dane)))
    return wynik


def do_sprzatniecia(u: Uklad) -> list[Path]:
    """Katalogi wersji, których nie używa bieżąca instalacja: kod, checkout Hermesa i front panelu spoza current.json
    (każda ścieżka z niego: app, hermes, web_dist), venvy i wersje narzędzi spoza narzedzia.json (katalog, bin,
    python, program) oraz resztki (`.new`, `.stary-*`, `.usun-*`)."""
    zostaja = _sciezki_w(srodowisko.biezace(u))
    for wpis in srodowisko.narzedzia(u).values():
        if isinstance(wpis, dict):
            zostaja |= _sciezki_w(wpis)
    kandydaci: list[Path] = []
    poziomy = [u.program / "app", u.program / "hermes", u.program / "venvs", u.program / "web-dist"]
    poziomy += _katalogi_w(u.program / "narzedzia")             # <program>/narzedzia/<nazwa>/<wersja>
    for poziom in poziomy:
        for k in _katalogi_w(poziom):
            klucz = os.path.normcase(os.path.abspath(str(k)))
            if klucz in zostaja or any(z.startswith(klucz + os.sep) for z in zostaja):
                continue
            kandydaci.append(k)
    return kandydaci


def stare_archiwa(u: Uklad, app: Path) -> list[Path]:
    """Pliki w `<cache>/pobrane`, których nie zna manifest bieżącej wersji (`<16 znaków sumy>-<nazwa>`), archiwa kodu
    `jarvo-<sha>.tar.gz` i niedokończone `.czesc`."""
    try:
        lock = json.loads((Path(app) / manifest.LOCK).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    sumy = set(re.findall(r'"sha256":\s*"([0-9a-f]{64})"', json.dumps(lock)))
    znane = {s[:16] for s in sumy}
    wynik = []
    katalog = u.cache / "pobrane"
    try:
        wpisy = list(os.scandir(katalog))
    except OSError:
        return []
    for e in wpisy:
        if not e.is_file(follow_symlinks=False):
            continue
        m = re.match(r"([0-9a-f]{16})-", e.name)
        if (m and m.group(1) not in znane) or re.fullmatch(r"jarvo-[0-9a-f]{40}\.tar\.gz", e.name) \
                or e.name.endswith(".czesc"):
            wynik.append(Path(e.path))
    return wynik


def programy_wersji(u: Uklad) -> set[str]:
    """Nazwy programów (.exe, bez wielkości liter), które dają wersje Jarva: PROGRAMY_JARVA i pliki .exe z katalogów
    `bin` i z katalogów narzędzi w narzedzia.json (stara wersja ma te same nazwy)."""
    nazwy = set(PROGRAMY_JARVA)
    for wpis in srodowisko.narzedzia(u).values():
        if not isinstance(wpis, dict):
            continue
        for k in [wpis.get("katalog"), *(wpis.get("bin") or [])]:
            if not k:
                continue
            with contextlib.suppress(OSError):
                nazwy |= {e.name.casefold() for e in os.scandir(str(k)) if e.name.casefold().endswith(".exe")}
    return nazwy


def niewidoczne(u: Uklad, lista: list[Proces], z: Zaplecze) -> list[Proces]:
    """Windows: procesy w sesji tego procesu (ten sam pulpit użytkownika, także uruchomione jako administrator),
    których ścieżki programu i wiersza polecenia nie da się odczytać (OpenProcess bez prawa), a nazwa to program
    z wersji Jarva. uzywaja() ich nie widzi, a mogą działać ze starej wersji (np. podniesiony `jarvo chat`). Procesy
    innych sesji (usługi systemu, inni użytkownicy) nie liczą się. Poza Windows pusto (/proc i ps podają ścieżki)."""
    if not WINDOWS:
        return []
    nasza = z.sesja(z.pid)
    if nasza is None:
        return []
    nazwy = programy_wersji(u)
    return [p for p in lista if p.pid != z.pid and not os.path.isabs(p.program) and not p.polecenie
            and p.program.casefold() in nazwy and z.sesja(p.pid) == nasza]


# Odwołania do katalogów wersji poza buildem (20.11: `<dane>/jarvo/konfig/sesje.json` Kernela miał
# `venvs/narzedzia-bcc37257827c/bin/python`, sprzątanie po aktualizacji 19.11 usunęło ten venv i pobieranie linków
# padało całą noc „No such file or directory”). Czytamy tylko zwykłe pliki tekstowe do MAX_PLIKU z tych miejsc; pliki
# *.env, auth.json, *.token i o nazwach sekretów nigdy nie są otwierane, a w logu jest tylko plik, linia i sama ścieżka.
MAX_PLIKU = 1 << 20
_NIE_CZYTAJ = re.compile(r"(^|\.)env$|\.token$|^auth\.json$|credential|sejf|" + srodowisko.SEKRET.pattern, re.I)
_GRANICA = "\"'` \t,;=()[]{}<>"


def wolno_czytac(p: Path) -> bool:
    """Czy skaner odwołań może otworzyć plik o tej nazwie (nigdy .env, *.env, *.token, auth.json, nazwy sekretów)."""
    return not _NIE_CZYTAJ.search(Path(p).name)


def miejsca_odwolan(u: Uklad, dom: Path) -> list[tuple[Path, bool]]:
    """Pliki, w których może stać bezwzględna ścieżka wersji: (plik, tylko czytelne dla innych). Konfig Jarva
    (*.json, *.yaml, *.yml), pamięć profili (memories/*.md), ~/.local/bin (bez plików tylko dla właściciela: tam
    leżą pomocnicy poświadczeń), na Linuksie jednostki systemd użytkownika (*.service, *.timer), na macOS
    ~/Library/LaunchAgents/*.plist, na Windows Autostart (*.cmd, *.bat, *.ps1, *.vbs)."""
    konfig = u.jarvo_dane / "konfig"
    pliki = [(p, False) for wzor in ("*.json", "*.yaml", "*.yml") for p in sorted(konfig.glob(wzor))]
    pliki += [(p, False) for p in sorted(u.dane.glob("profiles/*/memories/*.md"))]
    pliki += [(p, True) for p in sorted((dom / ".local" / "bin").glob("*"))]
    if LINUX:
        jednostki = dom / ".config" / "systemd" / "user"
        pliki += [(p, False) for wzor in ("*.service", "*.timer") for p in sorted(jednostki.glob(wzor))]
    if MACOS:
        pliki += [(p, False) for p in sorted((dom / "Library" / "LaunchAgents").glob("*.plist"))]
    if WINDOWS and os.environ.get("APPDATA"):
        start = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        pliki += [(p, False) for wzor in ("*.cmd", "*.bat", "*.ps1", "*.vbs") for p in sorted(start.glob(wzor))]
    return [(p, publiczne) for p, publiczne in pliki if wolno_czytac(p)]


def _linie_pliku(p: Path, publiczne: bool) -> list[str]:
    """Linie zwykłego pliku tekstowego (bez bajtu 0, do MAX_PLIKU); dowiązanie: sam jego cel (bez otwierania)."""
    if not wolno_czytac(p):
        return []
    try:
        st = os.lstat(p)
        if stat.S_ISLNK(st.st_mode):
            return [os.readlink(p)]
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_PLIKU or (publiczne and not WINDOWS
                                                                       and not st.st_mode & 0o044):
            return []
        with open(p, "rb") as f:
            dane = f.read(MAX_PLIKU)
    except OSError:
        return []
    if b"\0" in dane[:8192]:
        return []
    return dane.decode("utf-8", "replace").splitlines()


def odwolania(u: Uklad, z: Zaplecze, dom: Path | None = None) -> list[tuple[str, int, str]]:
    """(źródło, numer linii, linia) z miejsc_odwolan i z harmonogramów: `crontab -l` (macOS, Linux) albo
    `schtasks /Query /XML` (Windows). Linii nie zapisujemy w logu (mogą mieć coś poza ścieżką)."""
    wynik: list[tuple[str, int, str]] = []
    for p, publiczne in miejsca_odwolan(u, Path.home() if dom is None else dom):
        wynik += [(str(p), nr, linia) for nr, linia in enumerate(_linie_pliku(p, publiczne), 1)]
    for argv, opis in ((["schtasks", "/Query", "/XML"], "Harmonogram zadań"),) if WINDOWS else \
            ((["crontab", "-l"], "crontab"),):
        with contextlib.suppress(Exception):
            kod, tekst = z.wykonaj(argv)
            if kod == 0:
                wynik += [(opis, nr, linia) for nr, linia in enumerate(str(tekst).splitlines(), 1)]
    return wynik


def odwolanie_do(k: Path, linie: list[tuple[str, int, str]]) -> tuple[str, int, str] | None:
    """Pierwsze odwołanie do katalogu `k` (lub czegoś w nim): (źródło, linia, sama ścieżka z linii). Windows: także
    ścieżka z ukośnikami podwojonymi przez JSON."""
    nazwa = k.name.casefold()
    for zrodlo, nr, linia in linie:
        niska = linia.casefold()
        if nazwa not in niska:
            continue
        warianty = (linia, linia.replace("\\\\", "\\")) if "\\\\" in linia else (linia,)
        if any(zawiera_sciezke(w, k) for w in warianty):
            i = niska.index(nazwa)
            a = i
            while a > 0 and linia[a - 1] not in _GRANICA:
                a -= 1
            b = i + len(nazwa)
            while b < len(linia) and linia[b] not in _GRANICA:
                b += 1
            return zrodlo, nr, linia[a:b]
    return None


def rada_odwolania(u: Uklad, k: Path) -> str:
    """Jak naprawić odwołanie do wersji `k`: stała ścieżka (app/current, venvs/narzedzia) albo zmienna venvu."""
    stala = srodowisko.stala_wersji(u, k)
    if stala is not None:
        return f"wpisz tam stałą ścieżkę {stala} zamiast {k}"
    m = re.fullmatch(r"(.+)-[0-9a-f]{12}(?:-[0-9a-f]{8})?", k.name)
    zmienna = venvy.ZMIENNE.get(m.group(1)) if m and k.parent.name == venvy.KATALOG else None
    if zmienna:
        return f"wpisz tam zmienną ${zmienna} procesów Jarva (Python bieżącego venvu) zamiast {k}"
    return "wpisz tam ścieżkę bieżącej wersji z <program>/current.json albo <stan>/narzedzia.json"


def sprzataj(u: Uklad, z: Zaplecze, log: Callable[[str], None], *, app: Path | None = None,
             dom: Path | None = None) -> dict:
    """Usuwa stare wersje (do_sprzatniecia), których żaden proces nie używa, i stare archiwa. Jedyna ochrona to lista
    procesów (uzywaja: program albo wiersz polecenia w katalogu): na Windows katalog z działającym python.exe
    i załadowanym .dll przechodzi zmianę nazwy, więc ta jej nie zastąpi. Katalog najpierw dostaje nazwę
    `<nazwa>.usun-<czas>` (niepełny nie wygląda jak gotowa wersja; nie przejdzie jej tylko plik otwarty bez
    FILE_SHARE_DELETE albo katalog bieżący procesu), potem znika. Proces z niewidoczne() wstrzymuje całe sprzątanie
    katalogów do następnej aktualizacji. Kod i venvy, do których odwołuje się plik spoza buildu (odwolania, `dom` =
    katalog domowy, domyślnie Path.home()), zostają z radą w logu.
    {"usuniete", "w_uzyciu", "bledy", "zwolnione_mb", "wstrzymane"}."""
    wynik: dict = {"usuniete": [], "w_uzyciu": [], "bledy": [], "zwolnione_mb": 0.0, "wstrzymane": []}
    kandydaci = do_sprzatniecia(u)
    if not kandydaci and not u.cache.is_dir():
        return wynik
    lista = z.procesy() if kandydaci else []
    nieznane = niewidoczne(u, lista, z) if kandydaci else []
    if nieznane:
        wynik["wstrzymane"] = [p.opis() for p in nieznane[:5]]
        log(f"stare wersje zostają: działa {', '.join(wynik['wstrzymane'][:3])}, a nie widzę, z którego katalogu "
            "(np. uruchomiony jako administrator); usunie je następna aktualizacja")
        kandydaci = []
    pomin = set()                                 # ten proces też się liczy: jego kod i Python zostają
    zwolnione = 0
    wersje = [k for k in kandydaci if k.parent.name in ("app", venvy.KATALOG) and k.parent.parent == u.program]
    linie = odwolania(u, z, dom) if wersje else []
    for k in kandydaci:
        stala = srodowisko.stala_wersji(u, k)
        uzywajacy = uzywaja(k, lista, pomin) or (_przez_stala(stala, lista, pomin) if stala else [])
        if uzywajacy:
            wynik["w_uzyciu"].append({"katalog": str(k), "procesy": [p.opis() for p in uzywajacy[:5]]})
            log(f"zostaje {k} (używa go {', '.join(p.opis() for p in uzywajacy[:3])})")
            continue
        odw = odwolanie_do(k, linie) if k in wersje else None
        if odw is not None:
            zrodlo, nr, sciezka = odw
            wynik["w_uzyciu"].append({"katalog": str(k), "procesy": [], "odwolanie": f"{zrodlo}:{nr}"})
            log(f"zostaje {k}: odwołuje się do niego {zrodlo}:{nr} ({sciezka}); {rada_odwolania(u, k)}, a po poprawce "
                "usunie go następna aktualizacja")
            continue
        bajty = rozmiar(k)
        cel = k if _RESZTKI.search(k.name) else k.with_name(f"{k.name}.usun-{int(time.time())}")
        if cel != k:
            try:
                os.replace(k, cel)
            except OSError as e:
                wynik["w_uzyciu"].append({"katalog": str(k), "procesy": [f"zajęty ({e.strerror or e})"]})
                log(f"zostaje {k}: zajęty ({e.strerror or e})")
                continue
        bledy: list[str] = []
        if usun_drzewo(cel, bledy):
            wynik["usuniete"].append(str(k))
            zwolnione += bajty
            log(f"usunięty {k} ({bajty / 1e6:.0f} MB)")
            if k.parent.name == "web-dist":            # opis frontu `<skrót>.json` obok katalogu (hermes.dist_jarva)
                with contextlib.suppress(OSError):
                    k.with_name(k.name + ".json").unlink()
        else:
            wynik["bledy"] += bledy[:5]
            log(f"nie cały {k}: {'; '.join(bledy[:2])} (dokończy następna aktualizacja)")
    for p in stare_archiwa(u, app or instalator.katalog_aplikacji(u)):
        with contextlib.suppress(OSError):
            bajty = p.stat().st_size
            p.unlink()
            zwolnione += bajty
            wynik["usuniete"].append(str(p))
    wynik["zwolnione_mb"] = round(zwolnione / 1e6, 1)
    return wynik


# ---------------------------------------------------------------- doctor

def _json_z(tekst: str) -> dict | None:
    i = tekst.find("{")
    while i >= 0:
        with contextlib.suppress(ValueError):
            d = json.JSONDecoder().raw_decode(tekst[i:])[0]
            if isinstance(d, dict):
                return d
        i = tekst.find("{", i + 1)
    return None


def opis_liczby_zmian(n: int, pelna: bool = True) -> str:
    """„1 nowa zmiana”, „3 nowe zmiany”, „12 nowych zmian”; niepełna lista: „co najmniej 50 nowych zmian”."""
    if n == 1:
        rzeczownik = "nowa zmiana"
    elif 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        rzeczownik = "nowe zmiany"
    else:
        rzeczownik = "nowych zmian"
    return f"{'' if pelna else 'co najmniej '}{n} {rzeczownik}"


def regresje(przed: dict | None, po: dict | None) -> tuple[list[str], list[str]]:
    """(regresje, nowe błędy): sprawdzenia `jarvo doctor`, które przed aktualizacją nie były błędem, a teraz są /
    błędy w sprawdzeniach, których przed nią nie było (nowe sprawdzenie nowej wersji: uwaga, bez wycofania)."""
    def stany(d: dict | None) -> dict[str, str]:
        return {str(w.get("nazwa")): str(w.get("stan")) for w in (d or {}).get("wyniki") or [] if isinstance(w, dict)}
    a, b = stany(przed), stany(po)
    reg = sorted(n for n, s in b.items() if s == "blad" and n in a and a[n] != "blad")
    nowe = sorted(n for n, s in b.items() if s == "blad" and n not in a)
    return reg, nowe


# ---------------------------------------------------------------- przebieg aktualizacji

def _pisz(strumien, tekst: str) -> None:
    """Wiersz na ekran. Ekran to tylko kopia dziennika (`<logi>/aktualizacja.log`): gdy czytelnik zniknął (przerwany
    potok `| tail`, zamknięte okno), strumień idzie do os.devnull i przebieg trwa dalej. 20.11 BrokenPipeError
    w diagnozie nowej wersji przerwał `jarvo update` po przełączeniu, bez wyniku w aktualizacja.json, a panel został
    z „Aktualizacja nieudana”. Devnull, a nie samo pominięcie: bufor z niewysłanym wierszem opróżni się przy wyjściu."""
    try:
        print(tekst, file=strumien, flush=True)
    except (OSError, ValueError):             # BrokenPipeError, EIO; ValueError: strumień zamknięty
        with contextlib.suppress(OSError, ValueError, AttributeError):
            devnull = os.open(os.devnull, os.O_WRONLY)
            try:
                os.dup2(devnull, strumien.fileno())
            finally:
                os.close(devnull)


def _wypisz(tekst: str) -> None:
    _pisz(sys.stdout, tekst)


def _na_stderr(tekst: str) -> None:
    _pisz(sys.stderr, tekst)


CZEKAJ_NA_KARTY_S = 30          # `--po-kartach`: odstęp lokalnego sprawdzania tablicy (bez sieci)
_spij = time.sleep              # testy podmieniają (bez prawdziwego czekania)


PRZEBIEGI_W_TOKU = ("kolejka", "wysylanie", "przyjety", "pracuje", "czeka_na_ture", "zatrzymywanie", "dopisany")
PRZEBIEG_SWIEZY_S = 1800      # przebieg bez zdarzenia dłużej = zawieszony, nie blokuje aktualizacji


def karty_w_toku(u: Uklad) -> list[str]:
    """Praca, którą restart bramy by przerwał: karty kanbana w toku (status `running`), tury rozmów panelu
    (przebiegi ze zdarzeniem w ostatnich 30 min; 24.11 wgranie przerwało turę Jarva z odpowiedzią dla właściciela)
    i podagenci w tle `delegate_task` (24.11 13:22 wgranie zabiło trzech podagentów zakładających konta, bo tura Jarva
    już się skończyła). „<id> <agent>: <tytuł>”. Brak bazy = []."""
    import sqlite3
    wynik: list[str] = []
    for db, zapytanie, arg in (
            (u.dane / "kanban.db", "SELECT id, assignee, title FROM tasks WHERE status = 'running' ORDER BY id", ()),
            (u.dane / "jarvo" / "state" / "rozmowy.db",
             f"SELECT id, agent, 'tura rozmowy w panelu' FROM przebiegi WHERE stan IN "
             f"({','.join('?' * len(PRZEBIEGI_W_TOKU))}) AND COALESCE(ostatnie_zdarzenie_at, utworzony_at) > ? "
             "ORDER BY id", (*PRZEBIEGI_W_TOKU, time.time() - PRZEBIEG_SWIEZY_S))):
        if not db.is_file():
            continue
        try:
            conn = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True, timeout=3)
            try:
                wynik += [f"{i} {a or '?'}: {(t or '')[:70]}" for i, a, t in conn.execute(zapytanie, arg)]
            finally:
                conn.close()
        except Exception:                     # noqa: BLE001 - odczyt pomocniczy; brak odpowiedzi bazy nie blokuje
            continue
    return wynik + podagenci_w_toku(u)


KONIEC_PODAGENTA = re.compile(r"^\S+ final\s*\|\s*(?:end )?status=\w+", re.M)


def podagenci_w_toku(u: Uklad) -> list[str]:
    """Delegacje Hermesa (`<dane>/profiles/<agent>/cache/delegation/live/<id>`) z zadaniem bez końca w manifeście
    i w dzienniku, zapisane w ostatnich 30 min i po starcie bramy (starsze zabił już restart)."""
    try:
        start_bramy = (u.dane / "gateway.pid").stat().st_mtime
    except OSError:
        start_bramy = 0.0
    wynik = []
    for manifest in sorted(u.dane.glob("profiles/*/cache/delegation/live/*/manifest.json")):
        try:
            zadania = json.loads(manifest.read_text(encoding="utf-8")).get("tasks") or []
            ostatni = max([manifest.stat().st_mtime] + [p.stat().st_mtime for p in manifest.parent.glob("task-*.log")])
        except (OSError, ValueError, AttributeError):
            continue
        if ostatni < max(start_bramy, time.time() - PRZEBIEG_SWIEZY_S):
            continue
        trwa = 0
        for i, t in enumerate(zadania):
            if not isinstance(t, dict) or t.get("status") in ("completed", "failed", "error", "interrupted",
                                                              "cancelled", "timeout", "stopped"):
                continue
            dziennik = manifest.parent / f"task-{t.get('index', i)}.log"
            try:
                koniec = KONIEC_PODAGENTA.search(dziennik.read_bytes()[-8192:].decode("utf-8", "replace"))
            except OSError:
                koniec = None
            trwa += koniec is None
        if trwa:
            wynik.append(f"{manifest.parent.name} {manifest.parts[-6]}: podagenci w tle ({trwa} pracuje)")
    return wynik


class _Aktualizacja:
    def __init__(self, u: Uklad, ot: Otoczenie, z: Zaplecze, log: Callable[[str], None], *, ref: str | None,
                 tylko_sprawdz: bool, magazyn: Callable[[Uklad], str | None], mimo_kart: bool = False,
                 po_kartach: bool = False):
        self.u, self.ot, self.z, self._log = u, ot, z, log
        self.ref_jawny, self.tylko_sprawdz, self.magazyn, self.mimo_kart = ref, tylko_sprawdz, magazyn, mimo_kart
        self.po_kartach = po_kartach
        self.wynik: dict = {"root": str(u.root), "wynik": None, "ref": None, "wersja_przed": None, "wersja_po": None,
                            "zdalna": None, "behind": 0, "zmiany": [], "regresje": [], "nowe_bledy": [],
                            "sprzatanie": None, "opis": "", "czas_s": None}
        self.ogon: list[str] = []
        self.klucz: str | None = None
        self.biez = srodowisko.biezace(u)
        self.dzialal = False                  # serwis działał przed aktualizacją (start po awaryjnym powrocie)
        self.opcje: list[str] = []            # opcje instalatora i migawka plików stanu z _kroki: potrzebne do powrotu
        self.migawka: dict = {}               # także po nieprzewidzianym błędzie (_aktualizuj)
        self.t0 = time.monotonic()
        self._puls_stop = threading.Event()
        self._puls: threading.Thread | None = None

    # -- dziennik: ekran (albo stderr przy --json), <logi>/aktualizacja.log i ogon dla panelu, zawsze bez klucza
    def log(self, tekst: str) -> None:
        tekst = _bez_klucza(tekst, self.klucz)
        self._log(tekst)
        self.ogon = (self.ogon + [tekst])[-OGON:]
        if self.u.logi.is_dir():
            with contextlib.suppress(OSError), open(self.u.logi / LOG, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {tekst}\n")

    def podlog(self, tekst: str) -> None:
        self.log(f"    {tekst}")

    def slad(self) -> None:
        """Pełny ślad nieprzewidzianego błędu tylko do `<logi>/aktualizacja.log` (na ekranie wystarczy komunikat)."""
        if self.u.logi.is_dir():
            with contextlib.suppress(OSError), open(self.u.logi / LOG, "a", encoding="utf-8") as f:
                f.write(_bez_klucza(traceback.format_exc(), self.klucz))

    def _env(self) -> dict:
        return env_podprocesu(self.u, self.ot.env)

    def _argv(self, app: Path, *argumenty: str) -> list[str]:
        return [str(instalator.python_jarva(self.u)), "-I", "-u", "-X", "utf8", str(Path(app) / "jarvo" / "start.py"),
                *instalator.argumenty_korzenia(self.u, self.ot.env), *argumenty]

    # -- przebieg
    def uruchom(self) -> int:
        u = self.u
        app = self.biez.get("app")
        if not app:
            return self._koniec("brak instalacji", f"Jarvo nie jest zainstalowane w {u.root}. "
                                f"{instalator_rada()}", kod=1)
        try:
            ref = ustal_ref(u, self.ot.env, self.ref_jawny)
            self.wynik["ref"] = ref
            self.klucz = klucz_github(u, self.ot.env, self.magazyn)
            przed = wersja_kodu(app)
            self.wynik["wersja_przed"] = (przed or str(self.biez.get("wersja") or "dev"))[:12]
            self.log(f"Jarvo update: {u.root}")
            self.podlog(f"wersja {self.wynik['wersja_przed']} (ref {ref})" + (", klucz do prywatnej kopii: jest"
                                                                             if self.klucz else ""))
            zdalna = zdalna_wersja(ref, self.klucz, self.ot.env)
        except BladAktualizacji as e:
            zapisz_panel(u, error=str(e)[:300], checked_at=time.time(), state=_stan_po_sprawdzeniu(u))
            return self._koniec("blad", f"BŁĄD: {e}", kod=1)
        if self.ref_jawny:
            zapamietaj_ref(u, ref)
        self.wynik["zdalna"] = zdalna[:12]
        aktualne = zdalna == przed or (przed is None and str(self.biez.get("wersja") or "") == zdalna[:12])
        behind, zmiany, pelna = (0, [], True) if aktualne else nowe_zmiany(przed, zdalna, self.klucz, self.ot.env)
        self.wynik.update(behind=behind, zmiany=zmiany)
        zapisz_panel(u, branch=ref, current=self.wynik["wersja_przed"][:7], latest=zdalna[:7], behind=behind,
                     commits=zmiany, checked_at=time.time(), error=None, state=_stan_po_sprawdzeniu(u, aktualne))
        zapisz_stan(u, ref=ref, repo=REPO_GH, sprawdzono=time.strftime("%Y-%m-%dT%H:%M:%S"), zdalna=zdalna)
        if aktualne:
            uzgodnij_wynik(u, self.wynik["wersja_przed"], ref)
        zrodlo = f"{FAKE} (próba)" if self.ot.env.get(FAKE) else "GitHub"
        if aktualne:
            self.podlog(f"{zrodlo}: {ref} = {zdalna[:12]}, to ta sama wersja")
            if not self.tylko_sprawdz:
                self._sprzatanie()
            return self._koniec("aktualne", f"Jarvo jest aktualne ({zdalna[:12]}, ref {ref}): nic do zrobienia.",
                                kod=0)
        opis_zmian = opis_liczby_zmian(behind, pelna) if przed else "inna wersja"
        self.podlog(f"{zrodlo}: {ref} = {zdalna[:12]} ({opis_zmian})")
        for c in zmiany[:10]:
            self.podlog(f"  {c['sha']} {c['subject']}")
        if self.tylko_sprawdz:
            return self._koniec("dostepna", f"Jest nowa wersja {zdalna[:12]} ({opis_zmian}). Aktualizacja: "
                                "jarvo update", kod=0)
        karty = [] if self.mimo_kart else karty_w_toku(u)
        if karty and self.po_kartach:
            # 16.11: operator ponawiał `jarvo update` co 30 s, każde pytało GitHub o wersję i po 15 min skończył się
            # limit 60 zapytań na godzinę. Czekanie na karty idzie lokalnie (kanban.db), GitHub raz, przed nim.
            self.log(f"Czekam na koniec {len(karty)} kart (tablica lokalnie co {CZEKAJ_NA_KARTY_S} s, bez zapytań "
                     "do GitHuba)")
            while karty:
                _spij(CZEKAJ_NA_KARTY_S)
                karty = karty_w_toku(u)
        if karty:
            # 16.11: operator puścił `jarvo update` w trakcie karty Sherlocka; instalator tylko ostrzegł „restart bramy
            # ją przerwie” i zrestartował bramę. Aktualizacja w trakcie karty czeka, aż karta się skończy.
            for k in karty[:5]:
                self.podlog(f"  w toku: {k}")
            # odmowa widoczna także w panelu (prośba z panelu inaczej kończyła się bez śladu, jakby nic nie zlecono)
            odmowa = (f"Aktualizacja nie ruszyła, bo na tablicy pracuje agent ({'; '.join(karty[:3])}). Restart "
                      "przerwałby jego kartę. Wybierz „Zaktualizuj, gdy skończą”, a Jarvo zaktualizuje się sam po "
                      "końcu pracy.")
            zapisz_panel(u, error=odmowa[:300])
            return self._koniec("karty", f"Na tablicy pracuje agent ({len(karty)} kart): aktualizuję po ich końcu, bo "
                                "restart bramy przerywa kartę. Poczekaj na koniec: jarvo update --po-kartach; "
                                "teraz mimo to: jarvo update --mimo-kart.", kod=1)
        return self._aktualizuj(Path(app), zdalna, ref)

    def _aktualizuj(self, stara: Path, zdalna: str, ref: str) -> int:
        u = self.u
        zapisz_panel(u, state="updating", started_at=time.time(), beat=time.time(), finished_at=None,
                     updater_pid=os.getpid(), log="\n".join(self.ogon), error=None)
        self._start_pulsu()
        try:
            return self._kroki(stara, zdalna, ref)
        except KeyboardInterrupt:
            self._stop_pulsu()
            zapisz_panel(u, state="failed", finished_at=time.time(), log="\n".join(self.ogon),
                         error="aktualizację przerwano (Ctrl+C)")
            raise
        except Exception as e:            # noqa: BLE001 - nieprzewidziany błąd: powrót i „failed”, bez śladu na ekranie
            self.slad()
            return self._nieudana(f"nieprzewidziany błąd ({type(e).__name__}: {_bez_klucza(str(e), self.klucz)[:200]};"
                                  f" pełny opis w {u.logi / LOG})", stara, self.opcje, self.migawka)
        finally:
            self._stop_pulsu()

    def _kroki(self, stara: Path, zdalna: str, ref: str) -> int:
        u = self.u
        opcje, self.dzialal = self._opcje()
        self.opcje = opcje
        self.podlog(f"opcje instalacji: {' '.join(opcje) or 'domyślne'}"
                    + ("" if self.dzialal else " (serwis nie działał: zostaje zatrzymany)"))
        przed_doctor = self._doctor(stara, "przed aktualizacją")
        migawka = {p: p.read_bytes() if p.is_file() else None
                   for p in (u.program / "current.json", u.stan / "narzedzia.json")}
        self.migawka = migawka
        self.log(f"[Kod wersji {zdalna[:12]}]")
        try:
            nowa = pobierz_kod(u, zdalna, ref, self.klucz, self.ot.env, self.podlog)
        except (BladAktualizacji, pobieracz.BladPobierania, OSError) as e:
            return self._nieudana(f"kod nowej wersji: {e}", stara, opcje, migawka, wycofaj=False)
        self.log(f"[Instalator wersji {zdalna[:12]}]")
        kod = self._instalator(nowa, opcje)
        if kod != 0:
            return self._nieudana(f"instalator nowej wersji zakończył się kodem {kod} (opis wyżej, pełny w "
                                  f"{u.logi / 'instalacja.log'})", stara, opcje, migawka)
        self.biez = srodowisko.biezace(u)
        if not instalator.ten_sam_katalog(str(self.biez.get("app") or ""), nowa):
            return self._nieudana(f"instalator nie przełączył wersji (current.json: {self.biez.get('app')})", stara,
                                  opcje, migawka)
        self.log("[Diagnoza nowej wersji]")
        po, reg, nowe = self._doctor_po(nowa, przed_doctor)
        if po is None:
            return self._nieudana("jarvo doctor nowej wersji nie działa", stara, opcje, migawka)
        self.wynik.update(regresje=reg, nowe_bledy=nowe)
        if reg:
            return self._nieudana(f"po aktualizacji nie przechodzi: {', '.join(reg)} (wcześniej przechodziło)",
                                  stara, opcje, migawka)
        if nowe:
            self.podlog(f"uwaga: nowe sprawdzenia z błędem: {', '.join(nowe)} (zobacz jarvo doctor)")
        self.podlog(f"doctor: {po.get('bledy', '?')} błędów, {po.get('uwagi', '?')} uwag")
        self.wynik["wersja_po"] = (wersja_kodu(self.biez.get("app")) or str(self.biez.get("wersja") or "?"))[:12]
        opis = f"Gotowe: Jarvo {self.wynik['wersja_po']} (było {self.wynik['wersja_przed']})."
        self._zapisz_wynik("zaktualizowano", opis, self.wynik["wersja_po"], opcje=opcje)
        self.log("[Sprzątanie starych wersji]")
        self._sprzatanie(app=nowa)
        self._stop_pulsu()
        zapisz_panel(u, state="done", finished_at=time.time(), current=self.wynik["wersja_po"][:7], behind=0,
                     commits=[], latest=zdalna[:7], log="\n".join(self.ogon), error=None)
        return self._koniec("zaktualizowano", opis, kod=0)

    def _opcje(self) -> tuple[list[str], bool]:
        """Opcje instalatora jak przy instalacji: --bez-path, gdy polecenie jarvo nie trafiło do PATH (dziennik zmian
        hosta), --bez-autostartu, gdy autostart jest wyłączony, --bez-startu, gdy serwis nie działał."""
        u = self.u
        wpisy = zmiany_hosta.wpisy(u)
        if WINDOWS:
            w_path = any(w["rodzaj"] == "path-uzytkownika" for w in wpisy)
        else:
            dom = os.path.normcase(str(Path.home() / ".local" / "bin" / "jarvo"))
            w_path = any(w["rodzaj"] == "plik" and os.path.normcase(str(w["szczegoly"].get("sciezka"))) == dom
                         for w in wpisy)
        auto = instalator.stan_autostartu(u, self.ot)
        dzialal = instalator.stan_serwisu(u, self.ot)[0] is not None
        opcje = [] if w_path else ["--bez-path"]
        if not (auto.get("wlaczony") and auto.get("nasz")):
            opcje.append("--bez-autostartu")
        if not dzialal:
            opcje.append("--bez-startu")
        return opcje, dzialal

    def _instalator(self, app: Path, opcje: list[str]) -> int:
        czas = float(self.ot.env.get("JARVO_UPDATE_TIMEOUT") or CZAS_INSTALATORA)
        try:
            kod = self.z.strumien(self._argv(app, "instaluj", *opcje), env=self._env(), cwd=app, log=self.podlog,
                                  czas=czas)
        except OSError as e:
            self.podlog(f"BŁĄD: instalator się nie uruchomił ({e})")
            return 126
        if kod == 124:
            self.podlog(f"BŁĄD: instalator nie skończył w {int(czas)} s")
        return kod

    def _doctor(self, app: Path, kiedy: str) -> dict | None:
        kod, tekst = self.z.przechwyc(self._argv(app, "doctor", "--json"), env=self._env(), cwd=app,
                                      czas=CZAS_DOCTORA)
        d = _json_z(tekst)
        if d is None or "wyniki" not in d:
            self.podlog(f"doctor {kiedy}: brak wyniku (kod {kod})")
            return None
        bledy = [w.get("nazwa") for w in d["wyniki"] if isinstance(w, dict) and w.get("stan") == "blad"]
        self.podlog(f"doctor {kiedy}: {len(bledy)} błędów" + (f" ({', '.join(map(str, bledy[:6]))})" if bledy else ""))
        return d

    def _doctor_po(self, app: Path, przed: dict | None) -> tuple[dict | None, list[str], list[str]]:
        """Doctor nowej wersji z rozgrzewką: instalator czeka na panel, a API bramy (i inne usługi) mogą wstać kilka
        sekund później, więc regresję uznajemy dopiero wtedy, gdy trwa jeszcze po CZAS_ROZGRZEWKI sekundach
        (sprawdzenie co CO_ILE_ROZGRZEWKA s). (wynik, regresje, nowe błędy)."""
        koniec = self.ot.zegar() + float(self.ot.env.get("JARVO_UPDATE_ROZGRZEWKA") or CZAS_ROZGRZEWKI)
        while True:
            po = self._doctor(app, "po aktualizacji")
            reg, nowe = regresje(przed, po) if przed is not None and po is not None else ([], [])
            if po is not None and not reg:
                return po, reg, nowe
            if self.ot.zegar() >= koniec:
                return po, reg, nowe
            self.podlog(f"czekam, aż usługi nowej wersji wstaną ({', '.join(reg) or 'doctor bez wyniku'})…")
            self.ot.czekaj(CO_ILE_ROZGRZEWKA)

    def _nieudana(self, powod: str, stara: Path, opcje: list[str], migawka: dict, *, wycofaj: bool = True) -> int:
        u = self.u
        self.log(f"BŁĄD: {powod}")
        zmienione = any((p.read_bytes() if p.is_file() else None) != tresc for p, tresc in migawka.items())
        wynik, opis = "blad", f"Aktualizacja się nie udała: {powod}."
        if wycofaj and zmienione:
            self.log(f"[Powrót do wersji {self.wynik['wersja_przed']}]")
            try:
                kod = self._instalator(stara, opcje)
            except Exception as e:        # noqa: BLE001 - powrót też zawiódł: zostaje awaryjny current.json niżej
                self.slad()
                self.podlog(f"BŁĄD: instalator poprzedniej wersji: {type(e).__name__}: {str(e)[:200]}")
                kod = 1
            if kod == 0 and instalator.ten_sam_katalog(str(srodowisko.biezace(u).get("app") or ""), stara):
                self._stale_sciezki()
                wynik, opis = "wycofano", (f"Aktualizacja się nie udała ({powod}), więc wróciła poprzednia wersja "
                                           f"{self.wynik['wersja_przed']} (current.poprzedni.json, jej instalatorem).")
            else:
                self._awaryjnie(migawka)
                opis = (f"Aktualizacja się nie udała ({powod}), a instalator poprzedniej wersji też (kod {kod}). "
                        f"Wróciłem do current.json sprzed aktualizacji. Sprawdź `jarvo doctor` i uruchom polecenie "
                        f"instalacji jeszcze raz.")
        elif not zmienione:
            opis += f" Działa dalej wersja {self.wynik['wersja_przed']} (nic się nie przełączyło)."
        self._zapisz_wynik(wynik, opis, self.wynik["wersja_przed"])     # każda gałąź kończy się na wersji sprzed
        self._stop_pulsu()
        zapisz_panel(u, state="failed", finished_at=time.time(), log="\n".join(self.ogon), error=powod[:300])
        return self._koniec(wynik, opis, kod=1)

    def _zapisz_wynik(self, wynik: str, opis: str, wersja: str, **pola) -> None:
        """Wynik przebiegu w aktualizacja.json zawsze w komplecie (wynik, kiedy, opis, działająca wersja, poprzednia
        i cel), więc nic nie zostaje z wcześniejszego przebiegu (20.11: udana aktualizacja zostawiła obok „wynik:
        zaktualizowano” opis porażki sprzed 5 dni)."""
        zapisz_stan(self.u, wynik=wynik, kiedy=time.strftime("%Y-%m-%dT%H:%M:%S"), opis=opis[:500], wersja=wersja,
                    poprzednia=self.wynik["wersja_przed"], cel=self.wynik["zdalna"], **pola)

    def _awaryjnie(self, migawka: dict) -> None:
        """Ostatnia deska: current.json i narzedzia.json sprzed aktualizacji, stałe ścieżki na nie, potem start
        serwisu, jeśli działał."""
        for p, tresc in migawka.items():
            if tresc is not None:
                with contextlib.suppress(OSError):
                    przenosne.zapisz_atomowo(p, tresc)
        self._stale_sciezki()
        if self.dzialal and instalator.stan_serwisu(self.u, self.ot)[0] is None:
            with contextlib.suppress(Exception):
                instalator.uruchom_serwis(self.u, self.ot, self.podlog)

    def _stale_sciezki(self) -> None:
        """Stałe ścieżki (`app/current`, `venvs/narzedzia`) na wersję z current.json i narzedzia.json po powrocie:
        instalator poprzedniej wersji mógł ich nie znać (M5), więc zostałyby na nowej, wycofanej."""
        try:
            zmienione, bledy = srodowisko.uzgodnij_stale(self.u)
        except Exception as e:            # noqa: BLE001 - powrót nie może się wywrócić na dowiązaniu
            zmienione, bledy = [], [f"{type(e).__name__}: {str(e)[:160]}"]
        for opis in zmienione:
            self.podlog(f"stała ścieżka {opis}")
        for blad in bledy:
            self.podlog(f"uwaga: stała ścieżka {blad}")

    def _sprzatanie(self, app: Path | None = None) -> None:
        """Sprzątanie starych wersji; błąd to tylko uwaga (nigdy powód do wycofania udanej aktualizacji)."""
        try:
            wynik = sprzataj(self.u, self.z, self.podlog, app=app)
        except Exception as e:            # noqa: BLE001 - stare wersje zostają do następnej aktualizacji
            self.slad()
            self.podlog(f"uwaga: sprzątanie starych wersji nie przeszło ({type(e).__name__}: {str(e)[:160]}); "
                        "zostają do następnej aktualizacji")
            self.wynik["sprzatanie"] = {"blad": f"{type(e).__name__}: {str(e)[:160]}"}
            return
        self.wynik["sprzatanie"] = wynik
        if wynik["usuniete"]:
            self.podlog(f"sprzątanie: usunięte {len(wynik['usuniete'])}, zwolnione {wynik['zwolnione_mb']} MB")

    # -- puls dla panelu
    def _start_pulsu(self) -> None:
        def praca() -> None:
            while not self._puls_stop.wait(CO_ILE_STAN):
                zapisz_panel(self.u, state="updating", beat=time.time(), log="\n".join(self.ogon))
        self._puls = threading.Thread(target=praca, daemon=True)
        self._puls.start()

    def _stop_pulsu(self) -> None:
        self._puls_stop.set()
        if self._puls is not None:
            self._puls.join(timeout=5)
            self._puls = None

    def _koniec(self, wynik: str, opis: str, *, kod: int) -> int:
        self.wynik.update(wynik=wynik, opis=_bez_klucza(opis, self.klucz), kod=kod,
                          czas_s=round(time.monotonic() - self.t0, 1))
        self.log(opis)
        return kod


def instalator_rada() -> str:
    from .cli import RADA_INSTALACJI
    return RADA_INSTALACJI


def aktualizuj(u: Uklad, ot: Otoczenie | None = None, *, ref: str | None = None, tylko_sprawdz: bool = False,
               log: Callable[[str], None] | None = None, zaplecze: Zaplecze | None = None,
               magazyn: Callable[[Uklad], str | None] = czytaj_magazyn, mimo_kart: bool = False,
               po_kartach: bool = False) -> tuple[int, dict]:
    """`jarvo update`: (kod wyjścia, raport). Jedna aktualizacja naraz (blokada `<stan>/aktualizacja.lock`)."""
    ot = ot or Otoczenie()
    z = zaplecze or Zaplecze()
    u = instalator.bezwzgledny(uklad_instalacji(u, ot.env))
    przebieg = _Aktualizacja(u, ot, z, log or _wypisz, ref=ref, tylko_sprawdz=tylko_sprawdz, magazyn=magazyn,
                             mimo_kart=mimo_kart, po_kartach=po_kartach)
    if not u.stan.is_dir():
        return _bezpiecznie(przebieg), przebieg.wynik
    zamek = przenosne.Zamek(u.stan / ZAMEK, czekaj=False)
    for proba in range(6):                    # trwa() pomocnika bierze blokadę na chwilę: to jeszcze nie aktualizacja
        try:
            zamek.__enter__()
            break
        except BlockingIOError:
            if proba == 5:
                kod = przebieg._koniec("trwa", "Aktualizacja już trwa (z panelu albo z innego okna): poczekaj na jej "
                                               "koniec (jarvo logs aktualizacja).", kod=1)
                return kod, przebieg.wynik
            time.sleep(0.2)
    try:
        with instalator._katalog_biezacy(u.root):
            return _bezpiecznie(przebieg), przebieg.wynik
    finally:
        zamek.__exit__(None, None, None)


def _bezpiecznie(przebieg: "_Aktualizacja") -> int:
    """Przebieg bez surowego śladu stosu na ekranie: błąd spoza kroków (np. sprawdzenie wersji) = komunikat po polsku,
    ślad w `<logi>/aktualizacja.log`, update.json z błędem (stan „updating” nie zostaje)."""
    try:
        return przebieg.uruchom()
    except Exception as e:                # noqa: BLE001 - patrz docstring
        przebieg.slad()
        tekst = f"{type(e).__name__}: {_bez_klucza(str(e), przebieg.klucz)[:200]}"
        blad = f"nieprzewidziany błąd ({tekst})"[:300]
        if stan_panelu(przebieg.u).get("state") == "updating":
            zapisz_panel(przebieg.u, state="failed", finished_at=time.time(), error=blad, log="\n".join(przebieg.ogon))
            # błąd mógł przyjść po przełączeniu wersji: wynik mówi, która działa (sprawdzenie najnowszej go uzgodni)
            teraz = srodowisko.biezace(przebieg.u)
            dziala = (wersja_kodu(teraz.get("app")) or str(teraz.get("wersja") or "?"))[:12]
            przebieg._zapisz_wynik("blad", f"Aktualizacja przerwana: {blad}. Działa wersja {dziala}.", dziala)
        else:
            zapisz_panel(przebieg.u, error=blad, checked_at=time.time(), state=_stan_po_sprawdzeniu(przebieg.u))
        return przebieg._koniec("blad", f"BŁĄD: nieprzewidziany błąd aktualizacji ({tekst}). Pełny opis: "
                                        f"{przebieg.u.logi / LOG}.", kod=1)


def trwa(u: Uklad) -> bool:
    """Czy działa aktualizacja tej instalacji (blokada zajęta)."""
    if not u.stan.is_dir():
        return False
    try:
        with przenosne.Zamek(u.stan / ZAMEK, czekaj=False):
            return False
    except BlockingIOError:
        return True


# ---------------------------------------------------------------- pomocnik dla panelu (S09)

def _wez_prosbe(u: Uklad) -> str | None:
    """Treść `<dane>/jarvo/state/update-request` („check” albo „update”) albo None; inna treść znika bez skutku."""
    p = u.jarvo_dane / PROSBA_PANELU
    try:
        tekst = p.read_text(encoding="utf-8", errors="replace").strip().split()
    except OSError:
        return None
    slowo = tekst[0] if tekst else ""
    if slowo not in ("check", "update"):
        with contextlib.suppress(OSError):
            p.unlink()
        return None
    return slowo


def _usun_prosbe(u: Uklad) -> None:
    with contextlib.suppress(OSError):
        (u.jarvo_dane / PROSBA_PANELU).unlink()


def sprawdz_dla_panelu(u: Uklad, ot: Otoczenie, magazyn: Callable[[Uklad], str | None] = czytaj_magazyn) -> dict:
    """Sprawdzenie wersji dla panelu (bez aktualizacji): update.json z behind, commits, current, latest, branch."""
    biez = srodowisko.biezace(u)
    przed = wersja_kodu(biez.get("app"))
    obecna = (przed or str(biez.get("wersja") or "dev"))[:12]
    try:
        ref = ustal_ref(u, ot.env)
        klucz = klucz_github(u, ot.env, magazyn)
        zdalna = zdalna_wersja(ref, klucz, ot.env)
    except BladAktualizacji as e:
        zapisz_panel(u, error=str(e)[:300], checked_at=time.time(), state=_stan_po_sprawdzeniu(u),
                     updater_pid=os.getpid())
        return stan_panelu(u)
    aktualne = zdalna == przed or (przed is None and str(biez.get("wersja") or "") == zdalna[:12])
    behind, zmiany, _ = (0, [], True) if aktualne else nowe_zmiany(przed, zdalna, klucz, ot.env)
    zapisz_panel(u, branch=ref, current=obecna[:7], latest=zdalna[:7], behind=behind, commits=zmiany,
                 checked_at=time.time(), error=None, state=_stan_po_sprawdzeniu(u, aktualne), updater_pid=os.getpid())
    zapisz_stan(u, ref=ref, repo=REPO_GH, sprawdzono=time.strftime("%Y-%m-%dT%H:%M:%S"), zdalna=zdalna)
    if aktualne:
        uzgodnij_wynik(u, obecna, ref)
    return stan_panelu(u)


def w_jednostce_jarva(cgroup: str | None = None) -> bool:
    """Linux: czy ten proces działa w jednostce systemd --user Jarva (jarvo.service albo jarvo-<8>.service spod
    JARVO_ROOT, jarvo/autostart.py), czyli w jej grupie cgroup: `/proc/self/cgroup`."""
    if cgroup is None:
        try:
            cgroup = Path("/proc/self/cgroup").read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
    return bool(re.search(r"/user@\d+\.service/(?:.*/)?jarvo(?:-[0-9a-f]{8})?\.service$", cgroup, re.M))


def argv_aktualizacji(u: Uklad, env: dict) -> list[str]:
    """`jarvo update` tej instalacji do uruchomienia w tle; w jednostce systemd --user Jarva przez `systemd-run --user
    --scope` (własna grupa cgroup: KillMode=mixed nie zabije go razem z nadzorcą, którego zatrzyma instalator)."""
    argv = instalator.polecenie_jarva(u, "update", env=env)
    if LINUX and w_jednostce_jarva():
        systemd_run = shutil.which("systemd-run", path="/usr/bin:/bin")
        if systemd_run:
            argv = [systemd_run, "--user", "--scope", "--quiet", "--collect", "--", *argv]
    return argv


def zlec_aktualizacje(u: Uklad, ot: Otoczenie) -> int | None:
    """Prośba „update” z panelu: update.json „updating”, prośba znika, `jarvo update` startuje jako osobny proces
    (wyjście w `<logi>/aktualizacja-panel.log`). PID albo None, gdy aktualizacja już trwa albo start się nie udał."""
    if trwa(u):
        _usun_prosbe(u)
        return None
    zapisz_panel(u, state="updating", started_at=time.time(), beat=time.time(), finished_at=None, error=None,
                 log="Uruchamiam jarvo update…", updater_pid=os.getpid())
    _usun_prosbe(u)
    env = env_podprocesu(u, instalator.env_floty(ot.env))
    try:
        pid = ot.uruchom_w_tle(argv_aktualizacji(u, ot.env), env, u.logi / LOG_PANELU)
    except OSError as e:
        zapisz_panel(u, state="failed", finished_at=time.time(), error=f"jarvo update nie wystartował ({e})"[:300])
        return None
    if not trwa(u):                           # `jarvo update` jeszcze nie wziął blokady: PID do update.json
        zapisz_panel(u, updater_pid=pid)
    return pid


def _liczba(wartosc) -> float:
    try:
        return float(wartosc or 0)
    except (TypeError, ValueError):
        return 0.0


def przerwana_aktualizacja(u: Uklad, teraz: float | None = None) -> bool:
    """update.json „updating”, a blokady aktualizacji nikt nie trzyma od CZAS_STARTU s (proces `jarvo update` zabity,
    padł bez wyniku albo nie wystartował): stan „failed” z opisem, żeby panel nie pokazywał „trwa” (i nie odpowiadał
    409) do następnego sprawdzenia. Najpierw blokada, potem stan: `jarvo update` pisze wynik przed jej zwolnieniem,
    więc kończący się przebieg nie zostanie oznaczony jako przerwany."""
    if trwa(u):
        return False
    s = stan_panelu(u)
    teraz = time.time() if teraz is None else teraz
    if s.get("state") != "updating" or teraz - _liczba(s.get("started_at")) < CZAS_STARTU:
        return False
    zapisz_panel(u, state="failed", finished_at=teraz, error="aktualizacja przerwana: proces jarvo update skończył "
                 "się bez wyniku (zobacz jarvo logs aktualizacja i jarvo logs aktualizacja-panel); poprzednia wersja "
                 "działa dalej albo wróci przy następnej aktualizacji")
    return True


def pierwsze_sprawdzenie(u: Uklad, co_ile: float, teraz_wall: float | None = None) -> float:
    """Za ile sekund pierwsze sprawdzenie pomocnika: 0, chyba że update.json ma udane sprawdzenie tej samej wersji
    sprzed mniej niż `co_ile` s (restart serwisu nie pyta GitHuba za każdym razem: 60 zapytań na godzinę bez
    klucza)."""
    s = stan_panelu(u)
    teraz_wall = time.time() if teraz_wall is None else teraz_wall
    minelo = teraz_wall - _liczba(s.get("checked_at"))
    biez = srodowisko.biezace(u)
    obecna = (wersja_kodu(biez.get("app")) or str(biez.get("wersja") or "dev"))[:7]
    if s.get("error") or s.get("current") != obecna or not 0 <= minelo < co_ile:
        return 0.0
    return co_ile - minelo


@contextlib.contextmanager
def _sygnaly_konca(wlacz: bool = True):
    """SIGTERM (nadzorca i systemd na POSIX) i SIGBREAK (Ctrl+Break od nadzorcy na Windows) kończą pętlę pomocnika jak
    Ctrl+C, czyli kodem 0, a nie twardym końcem procesu. Tylko w głównym wątku; poprzednie obsługi wracają."""
    poprzednie = {}
    if wlacz and threading.current_thread() is threading.main_thread():
        def koniec(*_):
            raise KeyboardInterrupt
        for nazwa in ("SIGTERM", "SIGBREAK"):
            numer = getattr(signal, nazwa, None)
            if numer is not None:
                with contextlib.suppress(OSError, ValueError):
                    poprzednie[numer] = signal.signal(numer, koniec)
    try:
        yield
    finally:
        for numer, obsluga in poprzednie.items():
            with contextlib.suppress(OSError, ValueError, TypeError):
                signal.signal(numer, obsluga)


def pomocnik(u: Uklad, ot: Otoczenie | None = None, *, raz: bool = False, log: Callable[[str], None] | None = None,
             magazyn: Callable[[Uklad], str | None] = czytaj_magazyn) -> int:
    """`jarvo update --pomocnik`: pętla pomocnika aktualizacji (docstring modułu), usługa `aktualizacje` nadzorcy.
    `raz`: jeden obieg (testy, próby na żywo)."""
    ot = ot or Otoczenie()
    u = instalator.bezwzgledny(uklad_instalacji(u, ot.env))
    log = log or _wypisz
    co_ile = max(60.0, _liczba(ot.env.get("JARVO_UPDATE_CHECK")) or CO_ILE_SPRAWDZAC)
    za = pierwsze_sprawdzenie(u, co_ile)
    nastepne = ot.zegar() + za
    puls = -1e9
    log(f"pomocnik aktualizacji: {u.root} (sprawdzenie co {int(co_ile)} s, pierwsze "
        + (f"za {int(za)} s: ostatnie było niedawno)" if za else "od razu)"))
    with _sygnaly_konca(not raz):
        while True:
            teraz = ot.zegar()
            try:
                prosba = _wez_prosbe(u)
                if prosba == "update":
                    nastepne = teraz + co_ile
                    pid = zlec_aktualizacje(u, ot)
                    log("aktualizacja z panelu: " + (f"jarvo update w tle (PID {pid})" if pid else "już trwa albo "
                                                     "nie wystartowała"))
                elif (prosba == "check" or teraz >= nastepne) and not trwa(u):
                    nastepne = teraz + co_ile     # przed sprawdzeniem: błąd nie powtarza zapytania co 3 s
                    if prosba:
                        _usun_prosbe(u)
                    s = sprawdz_dla_panelu(u, ot, magazyn)
                    log(f"sprawdzenie: {s.get('current')} → {s.get('latest')}, brakuje {s.get('behind')}"
                        + (f", błąd: {s.get('error')}" if s.get("error") else ""))
                    puls = teraz
                if przerwana_aktualizacja(u):
                    log("aktualizacja przerwana: jarvo update skończył się bez wyniku (stan „failed” dla panelu)")
                if teraz - puls >= CO_ILE_PULS and not trwa(u):
                    zapisz_panel(u, beat=time.time(), updater_pid=os.getpid())
                    puls = teraz
            except Exception as e:        # noqa: BLE001 - usługa nadzorcy działa dalej, błąd trafia do panelu
                opis = f"{type(e).__name__}: {str(e)[:200]}"
                log(f"pomocnik: błąd obiegu ({opis})")
                with contextlib.suppress(Exception):
                    zapisz_panel(u, error=f"pomocnik aktualizacji: {opis}"[:300], beat=time.time(),
                                 updater_pid=os.getpid())
                puls = teraz
            if raz:
                return 0
            ot.czekaj(CO_ILE_PROSBA)


# ---------------------------------------------------------------- wejście z jarvo/cli.py

def polecenie(u: Uklad, a, ot: Otoczenie, *, zaplecze: Zaplecze | None = None,
              magazyn: Callable[[Uklad], str | None] = czytaj_magazyn) -> int:
    """`jarvo update [--sprawdz] [--ref REF] [--json] | --pomocnik [--raz]`."""
    if getattr(a, "pomocnik", False):
        try:
            return pomocnik(u, ot, raz=bool(getattr(a, "raz", False)), magazyn=magazyn)
        except KeyboardInterrupt:
            return 0
    jako_json = bool(getattr(a, "json", False))
    kod, raport = aktualizuj(u, ot, ref=getattr(a, "ref", None), tylko_sprawdz=bool(getattr(a, "sprawdz", False)),
                             log=_na_stderr if jako_json else _wypisz, zaplecze=zaplecze, magazyn=magazyn,
                             mimo_kart=bool(getattr(a, "mimo_kart", False)),
                             po_kartach=bool(getattr(a, "po_kartach", False)))
    if jako_json:
        _wypisz(json.dumps(raport, ensure_ascii=False, indent=2))
    return kod
