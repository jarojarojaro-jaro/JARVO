"""Aktualizacja Jarva natywnie: `jarvo update` i pomocnik aktualizacji dla panelu (docs/NATYWNIE.md: N09, c4
„jarvo update”, S09, H16, D07, N15, I30, I40 „wersje obok siebie”).

  jarvo update [--sprawdz] [--ref REF] [--json]
        1. sprawdzenie wydania: GitHub API `commits/<ref>` (Accept: application/vnd.github.sha) z refem instalacji
           (`--ref`, JARVO_REF, `<stan>/aktualizacja.json`, `.jarvo-ref` kodu z bootstrapu, inaczej main). Publiczne
           repo bez niczego; prywatna kopia: JARVO_TOKEN ze zmiennej albo z magazynu systemu (Menedżer poświadczeń
           Windows, pęk kluczy macOS, libsecret na Linuksie, zapasowo plik 0600 `<dane>/jarvo/konfig/github-token`;
           wpis zapisze `jarvo klucz`, N15), tylko w nagłówku do api.github.com (add_unredirected_header: po
           przekierowaniu na codeload już bez niego), nigdy na ekranie, w logu, w update.json ani w otoczeniu
           programów, które stąd startują. Ta sama wersja = koniec bez zmian (poza sprzątaniem starych wersji),
        2. kod nowej wersji do `<program>/app/<sha12>` obok starej: archiwum codeload jak w bootstrapie (prywatna kopia:
           `tarball` przez API), rozpakowane bezpiecznie (jarvo/pobieracz.rozpakuj) do `<sha12>.new`, potem zmiana
           nazwy; `.jarvo-wersja` (pełny SHA) i `.jarvo-ref`,
        3. instalator NOWEJ wersji (`python -I -u -X utf8 <nowa>/jarvo/start.py instaluj` z opcjami tej instalacji:
           --bez-path, gdy polecenie nie trafiło do PATH, --bez-autostartu, gdy autostart jest wyłączony,
           --bez-startu, gdy serwis nie działał): narzędzia i venvy po sumach, Hermes przy zmianie pinu, front,
           flota; sam przełącza current.json (poprzedni zostaje jako current.poprzedni.json) i uruchamia serwis od
           nowa przez nadzorcę,
        4. `jarvo doctor --json` nowej wersji wobec przebiegu sprzed aktualizacji: błąd w sprawdzeniu, które przed nią
           przechodziło, to regresja, ale dopiero gdy trwa po rozgrzewce (do 120 s, co 10 s: instalator czeka na
           panel, a API bramy wstaje chwilę później; sprawdzone na Windows 11),
        5. przy błędzie instalatora albo regresji: powrót do current.poprzedni.json instalatorem POPRZEDNIEJ wersji
           (z jej katalogu, te same opcje: przywraca też narzędzia, programy floty, polecenie jarvo, autostart
           i serwis); gdy i on zawiedzie, sam current.json sprzed aktualizacji i start serwisu,
        6. po udanej: stare wersje (kod, checkouty Hermesa, front panelu w `<program>/web-dist`, venvy, narzędzia:
           wszystko, czego ścieżek nie ma w current.json ani w narzedzia.json, resztki `.new`, `.stary-*`, `.usun-*`,
           stare archiwa w `<cache>/pobrane`) znikają,
           gdy żaden proces z nich nie korzysta (program albo wiersz polecenia, jarvo/odinstalowanie.uzywaja; na
           Windows dodatkowo zmiana nazwy katalogu przed usunięciem: zajęty katalog jej nie przejdzie). Zajęte
           zostają do następnej aktualizacji (np. pracownicy kanbana kończą kartę na starej wersji, H07).
        Jedna aktualizacja naraz (`<stan>/aktualizacja.lock`), dziennik `<logi>/aktualizacja.log`, stan bez sekretów
        w `<stan>/aktualizacja.json`. Kod 0: aktualne, zaktualizowane albo (--sprawdz) sprawdzone; 1: błąd albo
        wycofanie. Limity: JARVO_UPDATE_TIMEOUT (instalator, domyślnie 3600 s), JARVO_UPDATE_ROZGRZEWKA (120 s).

  jarvo update --pomocnik [--raz]
        rola pomocnika aktualizacji (S09; uruchamia go nadzorca, docs/NATYWNIE.md c2): kontrakt plików z panelem bez
        zmian (hq/plugin/plugin_api.py). Co 3 s prośba `<dane>/jarvo/state/update-request` („check” albo „update”),
        co JARVO_UPDATE_CHECK s (domyślnie 3600: limit API bez klucza to 60 zapytań na godzinę) sprawdzenie, co 60 s
        puls. Stan dla panelu: `<dane>/jarvo/state/update.json` (state idle|updating|done|failed, behind, commits,
        branch, current, latest, checked_at, beat, started_at, finished_at, log, error). „update” uruchamia
        `jarvo update` jako osobny, odłączony proces (w jednostce systemd --user Jarva przez `systemd-run --user
        --scope`, bo KillMode=mixed zabiłby go razem z nadzorcą): instalator nowej wersji zatrzymuje nadzorcę razem
        z pomocnikiem, a wyjście tego procesu idzie do `<logi>/aktualizacja-panel.log`.

Zmienna tylko dla prób: JARVO_FAKE_KOD = katalog z kodem Jarva udający wersję z GitHuba (wersja z jego
`.jarvo-wersja` albo HEAD gita; bez sieci). Testy podmieniają też adresy API i KOD (serwer na 127.0.0.1).
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from . import instalator, manifest, pobieracz, przenosne, srodowisko, zmiany_hosta
from .instalator import Otoczenie
from .odinstalowanie import Zaplecze, env_podprocesu, rozmiar, uklad_instalacji, usun_drzewo, uzywaja
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
MAGAZYN = "jarvo-github"                      # nazwa klucza GitHuba w magazynie systemu (N15)
PLIK_KLUCZA = Path("konfig") / "github-token"  # w <dane>/jarvo: zapas na Linuksie bez libsecret (plik 0600)
CZAS_INSTALATORA = 3600.0                     # s; JARVO_UPDATE_TIMEOUT
CZAS_DOCTORA = 600.0
CZAS_ROZGRZEWKI = 120.0                       # s, przez które regresja doctora może być rozgrzewką usług
CO_ILE_ROZGRZEWKA = 10.0
CO_ILE_SPRAWDZAC = 3600                       # s; JARVO_UPDATE_CHECK
CO_ILE_PULS = 60.0
CO_ILE_PROSBA = 3.0
CO_ILE_STAN = 15.0                            # s między zapisami update.json w trakcie aktualizacji
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


def ustal_ref(u: Uklad, env: dict, jawny: str | None = None) -> str:
    """Ref aktualizacji: --ref, JARVO_REF, zapamiętany w `<stan>/aktualizacja.json`, `.jarvo-ref` bieżącego kodu
    (bootstrap), inaczej main. Zły zapis (spacje, „..”) to błąd tylko dla jawnego; zapamiętany pomijamy."""
    for kandydat, zrodlo in ((jawny, "--ref"), (env.get("JARVO_REF"), "JARVO_REF")):
        if kandydat:
            kandydat = kandydat.strip()
            if not _REF.fullmatch(kandydat) or ".." in kandydat:
                raise BladAktualizacji(f"{zrodlo}={kandydat!r}: to nie nazwa gałęzi, tagu ani SHA.")
            return kandydat
    zapisany = str(stan(u).get("ref") or "")
    if _REF.fullmatch(zapisany) and ".." not in zapisany:
        return zapisany
    return ref_kodu(srodowisko.biezace(u).get("app")) or REF_DOMYSLNY


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
    """JARVO_TOKEN ze zmiennej albo z magazynu systemu; publiczne repo działa bez niego."""
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
    except (urllib.error.URLError, OSError, ValueError) as e:
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
    except (urllib.error.URLError, OSError, ValueError):
        return 1, [], False
    zmiany = []
    for c in lista if isinstance(lista, list) else []:
        sha = str((c or {}).get("sha") or "")
        if sha == baza:
            return len(zmiany), zmiany[:20], True
        temat = str(((c or {}).get("commit") or {}).get("message") or "").split("\n", 1)[0][:200]
        zmiany.append({"sha": sha[:7], "subject": temat})
    return max(len(zmiany), 1), zmiany[:20], False


def pobierz_kod(u: Uklad, sha: str, ref: str, klucz: str | None, env: dict, log: Callable[[str], None]) -> Path:
    """Kod wersji `sha` w `<program>/app/<sha12>` (gotowy zostaje). Archiwum commitu z codeload (prywatna kopia:
    `tarball` przez API z kluczem) albo kopia katalogu JARVO_FAKE_KOD; najpierw do `<sha12>.new`."""
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
            log(f"pobieram kod {sha[:12]} ({adres})")
            _pobierz_plik(adres, archiwum, klucz, log)
            try:
                pobieracz.rozpakuj(archiwum, nowy, "tar.gz", 1)
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
    """Archiwum kodu strumieniem do pliku (bez sumy, jak w bootstrapie: HTTPS i SHA z API wystarczą), 3 próby."""
    cel.parent.mkdir(parents=True, exist_ok=True)
    czesc = cel.with_name(cel.name + ".czesc")
    ostatni: Exception | None = None
    for proba in range(3):
        try:
            with _otworz(adres, klucz=klucz, accept="application/octet-stream", czas=60) as odp, \
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
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            ostatni = e
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


def _stan_po_sprawdzeniu(u: Uklad) -> str:
    """„done” i „failed” zostają do następnej aktualizacji (panel pokazuje „Odśwież” albo błąd), reszta to „idle”."""
    s = stan_panelu(u).get("state")
    return s if s in ("done", "failed") else "idle"


# ---------------------------------------------------------------- sprzątanie starych wersji

def _katalogi_w(katalog: Path) -> list[Path]:
    try:
        return sorted(Path(e.path) for e in os.scandir(katalog) if e.is_dir(follow_symlinks=False))
    except OSError:
        return []


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


def sprzataj(u: Uklad, z: Zaplecze, log: Callable[[str], None], *, app: Path | None = None) -> dict:
    """Usuwa stare wersje (do_sprzatniecia), których żaden proces nie używa, i stare archiwa. Katalog najpierw zmienia
    nazwę na `<nazwa>.usun-<czas>` (na Windows zajęty katalog jej nie przejdzie, a niepełny nie wygląda jak gotowa
    wersja), potem znika. {"usuniete", "w_uzyciu", "bledy", "zwolnione_mb"}."""
    wynik: dict = {"usuniete": [], "w_uzyciu": [], "bledy": [], "zwolnione_mb": 0.0}
    kandydaci = do_sprzatniecia(u)
    if not kandydaci and not u.cache.is_dir():
        return wynik
    lista = z.procesy() if kandydaci else []
    pomin = set()                                 # ten proces też się liczy: jego kod i Python zostają
    zwolnione = 0
    for k in kandydaci:
        uzywajacy = uzywaja(k, lista, pomin)
        if uzywajacy:
            wynik["w_uzyciu"].append({"katalog": str(k), "procesy": [p.opis() for p in uzywajacy[:5]]})
            log(f"zostaje {k} (używa go {', '.join(p.opis() for p in uzywajacy[:3])})")
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

def _wypisz(tekst: str) -> None:
    print(tekst, flush=True)


def _na_stderr(tekst: str) -> None:
    print(tekst, file=sys.stderr, flush=True)


class _Aktualizacja:
    def __init__(self, u: Uklad, ot: Otoczenie, z: Zaplecze, log: Callable[[str], None], *, ref: str | None,
                 tylko_sprawdz: bool, magazyn: Callable[[Uklad], str | None]):
        self.u, self.ot, self.z, self._log = u, ot, z, log
        self.ref_jawny, self.tylko_sprawdz, self.magazyn = ref, tylko_sprawdz, magazyn
        self.wynik: dict = {"root": str(u.root), "wynik": None, "ref": None, "wersja_przed": None, "wersja_po": None,
                            "zdalna": None, "behind": 0, "zmiany": [], "regresje": [], "nowe_bledy": [],
                            "sprzatanie": None, "opis": "", "czas_s": None}
        self.ogon: list[str] = []
        self.klucz: str | None = None
        self.biez = srodowisko.biezace(u)
        self.dzialal = False                  # serwis działał przed aktualizacją (start po awaryjnym powrocie)
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
        self.wynik["zdalna"] = zdalna[:12]
        aktualne = zdalna == przed or (przed is None and str(self.biez.get("wersja") or "") == zdalna[:12])
        behind, zmiany, pelna = (0, [], True) if aktualne else nowe_zmiany(przed, zdalna, self.klucz, self.ot.env)
        self.wynik.update(behind=behind, zmiany=zmiany)
        zapisz_panel(u, branch=ref, current=self.wynik["wersja_przed"][:7], latest=zdalna[:7], behind=behind,
                     commits=zmiany, checked_at=time.time(), error=None, state=_stan_po_sprawdzeniu(u))
        zapisz_stan(u, ref=ref, repo=REPO_GH, sprawdzono=time.strftime("%Y-%m-%dT%H:%M:%S"), zdalna=zdalna)
        zrodlo = f"{FAKE} (próba)" if self.ot.env.get(FAKE) else "GitHub"
        if aktualne:
            self.podlog(f"{zrodlo}: {ref} = {zdalna[:12]}, to ta sama wersja")
            if not self.tylko_sprawdz:
                self._sprzatanie()
            return self._koniec("aktualne", f"Jarvo jest aktualne ({zdalna[:12]}, ref {ref}): nic do zrobienia.",
                                kod=0)
        opis_zmian = f"{behind}{'' if pelna else '+'} nowych zmian" if przed else "inna wersja"
        self.podlog(f"{zrodlo}: {ref} = {zdalna[:12]} ({opis_zmian})")
        for c in zmiany[:10]:
            self.podlog(f"  {c['sha']} {c['subject']}")
        if self.tylko_sprawdz:
            return self._koniec("dostepna", f"Jest nowa wersja {zdalna[:12]} ({opis_zmian}). Aktualizacja: "
                                "jarvo update", kod=0)
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
        finally:
            self._stop_pulsu()

    def _kroki(self, stara: Path, zdalna: str, ref: str) -> int:
        u = self.u
        opcje, self.dzialal = self._opcje()
        self.podlog(f"opcje instalacji: {' '.join(opcje) or 'domyślne'}"
                    + ("" if self.dzialal else " (serwis nie działał: zostaje zatrzymany)"))
        przed_doctor = self._doctor(stara, "przed aktualizacją")
        migawka = {p: p.read_bytes() if p.is_file() else None
                   for p in (u.program / "current.json", u.stan / "narzedzia.json")}
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
        zapisz_stan(u, wynik="zaktualizowano", kiedy=time.strftime("%Y-%m-%dT%H:%M:%S"),
                    wersja=self.wynik["wersja_po"], poprzednia=self.wynik["wersja_przed"], opcje=opcje)
        self.log("[Sprzątanie starych wersji]")
        self._sprzatanie(app=nowa)
        self._stop_pulsu()
        zapisz_panel(u, state="done", finished_at=time.time(), current=self.wynik["wersja_po"][:7], behind=0,
                     commits=[], latest=zdalna[:7], log="\n".join(self.ogon), error=None)
        return self._koniec("zaktualizowano", f"Gotowe: Jarvo {self.wynik['wersja_po']} (było "
                            f"{self.wynik['wersja_przed']}).", kod=0)

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
            kod = self._instalator(stara, opcje)
            if kod == 0 and instalator.ten_sam_katalog(str(srodowisko.biezace(u).get("app") or ""), stara):
                wynik, opis = "wycofano", (f"Aktualizacja się nie udała ({powod}), więc wróciła poprzednia wersja "
                                           f"{self.wynik['wersja_przed']} (current.poprzedni.json, jej instalatorem).")
            else:
                self._awaryjnie(migawka)
                opis = (f"Aktualizacja się nie udała ({powod}), a instalator poprzedniej wersji też (kod {kod}). "
                        f"Wróciłem do current.json sprzed aktualizacji. Sprawdź `jarvo doctor` i uruchom polecenie "
                        f"instalacji jeszcze raz.")
        elif not zmienione:
            opis += f" Działa dalej wersja {self.wynik['wersja_przed']} (nic się nie przełączyło)."
        zapisz_stan(u, wynik=wynik, kiedy=time.strftime("%Y-%m-%dT%H:%M:%S"), opis=opis[:500])
        self._stop_pulsu()
        zapisz_panel(u, state="failed", finished_at=time.time(), log="\n".join(self.ogon), error=powod[:300])
        return self._koniec(wynik, opis, kod=1)

    def _awaryjnie(self, migawka: dict) -> None:
        """Ostatnia deska: current.json i narzedzia.json sprzed aktualizacji, potem start serwisu, jeśli działał."""
        for p, tresc in migawka.items():
            if tresc is not None:
                with contextlib.suppress(OSError):
                    przenosne.zapisz_atomowo(p, tresc)
        if self.dzialal and instalator.stan_serwisu(self.u, self.ot)[0] is None:
            with contextlib.suppress(Exception):
                instalator.uruchom_serwis(self.u, self.ot, self.podlog)

    def _sprzatanie(self, app: Path | None = None) -> None:
        wynik = sprzataj(self.u, self.z, self.podlog, app=app)
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
               magazyn: Callable[[Uklad], str | None] = czytaj_magazyn) -> tuple[int, dict]:
    """`jarvo update`: (kod wyjścia, raport). Jedna aktualizacja naraz (blokada `<stan>/aktualizacja.lock`)."""
    ot = ot or Otoczenie()
    z = zaplecze or Zaplecze()
    u = instalator.bezwzgledny(uklad_instalacji(u, ot.env))
    przebieg = _Aktualizacja(u, ot, z, log or _wypisz, ref=ref, tylko_sprawdz=tylko_sprawdz, magazyn=magazyn)
    if not u.stan.is_dir():
        return przebieg.uruchom(), przebieg.wynik
    zamek = przenosne.Zamek(u.stan / ZAMEK, czekaj=False)
    try:
        zamek.__enter__()
    except BlockingIOError:
        kod = przebieg._koniec("trwa", "Aktualizacja już trwa (z panelu albo z innego okna): poczekaj na jej koniec "
                                       "(jarvo logs aktualizacja).", kod=1)
        return kod, przebieg.wynik
    try:
        with instalator._katalog_biezacy(u.root):
            return przebieg.uruchom(), przebieg.wynik
    finally:
        zamek.__exit__(None, None, None)


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
                 checked_at=time.time(), error=None, state=_stan_po_sprawdzeniu(u), updater_pid=os.getpid())
    zapisz_stan(u, ref=ref, repo=REPO_GH, sprawdzono=time.strftime("%Y-%m-%dT%H:%M:%S"), zdalna=zdalna)
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
        return ot.uruchom_w_tle(argv_aktualizacji(u, ot.env), env, u.logi / LOG_PANELU)
    except OSError as e:
        zapisz_panel(u, state="failed", finished_at=time.time(), error=f"jarvo update nie wystartował ({e})"[:300])
        return None


def pomocnik(u: Uklad, ot: Otoczenie | None = None, *, raz: bool = False, log: Callable[[str], None] | None = None,
             magazyn: Callable[[Uklad], str | None] = czytaj_magazyn) -> int:
    """`jarvo update --pomocnik`: pętla pomocnika aktualizacji (docstring modułu). `raz`: jeden obieg (testy)."""
    ot = ot or Otoczenie()
    u = instalator.bezwzgledny(uklad_instalacji(u, ot.env))
    log = log or _wypisz
    co_ile = max(60.0, float(ot.env.get("JARVO_UPDATE_CHECK") or CO_ILE_SPRAWDZAC))
    nastepne = ot.zegar()                     # pierwsze sprawdzenie od razu
    puls = -1e9
    log(f"pomocnik aktualizacji: {u.root} (sprawdzenie co {int(co_ile)} s)")
    while True:
        teraz = ot.zegar()
        prosba = _wez_prosbe(u)
        if prosba == "update":
            pid = zlec_aktualizacje(u, ot)
            log("aktualizacja z panelu: " + (f"jarvo update w tle (PID {pid})" if pid else "już trwa albo nie "
                                             "wystartowała"))
            nastepne = teraz + co_ile
        elif (prosba == "check" or teraz >= nastepne) and not trwa(u):
            if prosba:
                _usun_prosbe(u)
            s = sprawdz_dla_panelu(u, ot, magazyn)
            log(f"sprawdzenie: {s.get('current')} → {s.get('latest')}, brakuje {s.get('behind')}"
                + (f", błąd: {s.get('error')}" if s.get("error") else ""))
            nastepne = teraz + co_ile
            puls = teraz
        if teraz - puls >= CO_ILE_PULS and not trwa(u):
            zapisz_panel(u, beat=time.time(), updater_pid=os.getpid())
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
                             log=_na_stderr if jako_json else _wypisz, zaplecze=zaplecze, magazyn=magazyn)
    if jako_json:
        print(json.dumps(raport, ensure_ascii=False, indent=2), flush=True)
    return kod
