"""Skarbiec, rutyny i Telegram natywnie: `jarvo wiedza`, `jarvo rutyny`, `jarvo telegram` (docs/NATYWNIE.md, etap E7:
K02, K03, K07, K08, H06, H11, decyzja I36).

  jarvo wiedza kompiluj [--na-sucho] [--limit N] [--json]
        kompilacja skrzynki (wiedza/kompilacja.py) Pythonem venvu Hermesa, w środowisku Jarva (jarvo/srodowisko.py),
        z HERMES_HOME profilu jarvo (model zadania jarvo_wiedza) i w katalogu Hermesa; bez basha (zastępuje
        scripts/wiedza-kompiluj.sh z kontenera). Jeden piszący: wiedza.Blokada (blokada systemu + znacznik
        state/wiedza.lock, który widzi też zasiew przy wdrożeniu); lint przed i po przebiegu (K02)
  jarvo wiedza lint [--json] [--strict] | indeksuj [--pelny] | status [--json]
        lint z regułami nazw przenośnych (K07), indeks FTS5 z INDEX.md i listami hubów (pod blokadą), liczby
  jarvo wiedza doctor [--json]
        sprawdzenia skarbca, rutyn i Telegrama (K08), te same, które dostaje `jarvo doctor`
  jarvo rutyny [status|on|off] [--json]
        rutyny Jarva (cron Hermesa w bramie): stan z cron/jobs.json profilu jarvo, włączenie i wstrzymanie przez
        `hermes -p jarvo cron resume|pause` (H06). Po instalacji są wstrzymane; włącza je udana próbna wiadomość
        na Telegram (`jarvo telegram test`, I36), a `jarvo rutyny off` wyłącza je na stałe, aż `jarvo rutyny on`
  jarvo telegram ustaw [--wlasciciel ID] [--grupa ID] [--token-ze-stdin] [--bez-wdrozenia] [--bez-sprawdzenia]
        token bota i lista dozwolonych do `<dane>/.env` (wartości nigdy na ekran ani do logu), trasy z pliku Jarva
        `<dane>/jarvo/konfig/jarvo.env` (TELEGRAM_OWNER_ID: DM → Jarvo i cel rutyn, TELEGRAM_HQ_CHAT_ID); potem
        wdrożenie floty (jarvo/flota.py: trasy w configu bramy, rutyny na Telegram) i restart bramy przez nadzorcę.
        ID właściciela: --wlasciciel albo z pierwszej wiadomości do bota (getUpdates, gdy nikt inny bota nie czyta)
  jarvo telegram test [--bez-rutyn] | status [--json] [--sprawdz]
        próbna wiadomość do właściciela (udana włącza rutyny, I36) / co jest ustawione (bez wartości) i konflikt 409
        w logach bramy (dwie bramy na jednym tokenie, H11)

Integracja z jarvo/cli.py: `dodaj_polecenia(sub)` dopisuje te trzy polecenia do parsera, `sprawdzenia(u, ot)` daje
wyniki dla `jarvo doctor` (format cli._wynik: nazwa, stan ok|uwaga|blad, opis, rada). Moduł działa też sam:
`python -X utf8 -m jarvo.wiedza_cli wiedza kompiluj` w katalogu kodu albo `python -I -X utf8 jarvo/wiedza_cli.py …`.
Sprawdzenia niczego nie zapisują. Adres Bot API: JARVO_TELEGRAM_API (lokalny serwer telegram-bot-api albo atrapa
w testach), domyślnie https://api.telegram.org.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import datetime as dt
import getpass
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

if __package__ in (None, ""):                         # `python jarvo/wiedza_cli.py`: pakiet jarvo z katalogu wyżej
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvo import instalator, przenosne, sciezki, srodowisko  # noqa: E402
from jarvo.sciezki import LINUX, WINDOWS, Uklad  # noqa: E402

PROFIL = "jarvo"                                       # profil z rutynami i modelem kompilacji (zadanie jarvo_wiedza)
RUTYNY = ("jarvo-patrol", "jarvo-daily-brief", "jarvo-weekly-review", "jarvo-knowledge-freshness")   # zapas bez jobs.yaml
TELEGRAM_API = "https://api.telegram.org"
TOKEN_RE = re.compile(r"^\d{5,16}:[A-Za-z0-9_-]{30,64}$")
TOKEN_W_TEKSCIE = re.compile(r"\d{5,16}:[A-Za-z0-9_-]{30,64}")
ID_RE = re.compile(r"^-?\d{3,20}$")
LINIA_ENV = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
ID_RUTYNY = re.compile(r"^\s*-\s*id:\s*[\"']?([A-Za-z0-9_.-]+)", re.M)
# 409 Conflict z adaptera Telegrama Hermesa (plugins/platforms/telegram/adapter.py) i z samego API
KONFLIKT_RE = re.compile(r"Telegram polling conflict|telegram_polling_conflict|terminated by other getUpdates|"
                         r"polling could not recover|409[^\n]{0,40}Conflict|Conflict: terminated", re.I)
CZAS_W_LINII = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})")
OKNO_LOGU_B = 4 * 2 ** 20                              # tyle końcówki każdego logu przegląda szukanie 409
OKNO_409_S = 24 * 3600
KOMPILACJA_STARA_S = 26 * 3600                         # szkice czekają dłużej niż doba z hakiem: kompilacja nie biegnie
SYNCHRONIZOWANE = ("onedrive", "dropbox", "google drive", "googledrive", "my drive", "mobile documents", "icloud",
                   "cloudstorage")
SCIEZKA_KORZENIA_MAKS = 100                            # Z25: dłuższy korzeń przy LongPathsEnabled=0 to ryzyko MAX_PATH
CZAS_HERMESA = 120.0


class BladTelegrama(RuntimeError):
    """Błąd Bot API: kod HTTP albo z odpowiedzi (0 = brak sieci) i opis bez tokenu."""

    def __init__(self, kod: int, opis: str):
        super().__init__(opis)
        self.kod = kod


def _wynik(nazwa: str, stan: str, opis: str, rada: str = "") -> dict:
    return {"nazwa": nazwa, "stan": stan, "opis": opis, "rada": rada}


# ---------------------------------------------------------------- miejsca i moduł skarbca

def _app(u: Uklad) -> Path:
    """Kod aktywnej wersji Jarva (current.json), a bez instalacji katalog tego modułu (kopia repo)."""
    return instalator.katalog_aplikacji(u)


def _checkout(u: Uklad) -> Path | None:
    h = srodowisko.biezace(u).get("hermes")
    return Path(h) if h else None


def _python_hermesa(u: Uklad) -> Path | None:
    c = _checkout(u)
    p = srodowisko.hermes_python(c) if c else None
    return p if p and p.is_file() else None


def skarbiec(u: Uklad) -> Path:
    return u.jarvo_dane / "knowledge"


def stan_skarbca(u: Uklad) -> Path:
    return u.jarvo_dane / "state"


def konfig(u: Uklad) -> Path:
    """`<dane>/jarvo/konfig` (D02): jarvo.env (trasy Telegrama, wybór dostawcy) i źródłowe sekrety (host.env)."""
    return u.jarvo_dane / "konfig"


def profil(u: Uklad) -> Path:
    return u.dane / "profiles" / PROFIL


def wiedza_lib(app: Path):
    """wiedza/wiedza.py tej wersji Jarva (biblioteka standardowa) pod nazwą modułu, której używają też wtyczka
    i kompilacja.py; ten sam plik ładujemy raz."""
    plik = Path(app) / "wiedza" / "wiedza.py"
    mod = sys.modules.get("jarvo_wiedza_lib")
    if mod is not None and Path(getattr(mod, "__file__", "")).resolve() == plik.resolve():
        return mod
    spec = importlib.util.spec_from_file_location("jarvo_wiedza_lib", plik)
    if spec is None or spec.loader is None:
        raise ImportError(f"brak {plik}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["jarvo_wiedza_lib"] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop("jarvo_wiedza_lib", None)
        raise
    return mod


def _szkice(u: Uklad) -> int:
    kat = skarbiec(u) / "skrzynka"
    return sum(1 for p in kat.glob("*.md") if p.is_file()) if kat.is_dir() else 0


def _zainstalowane(u: Uklad) -> bool:
    return bool(srodowisko.biezace(u).get("app"))


def _brak_instalacji(u: Uklad) -> int:
    print(f"Jarvo nie jest zainstalowane w {u.root}.\n{instalator_rada()}", file=sys.stderr)
    return 1


def instalator_rada() -> str:
    return ("Zainstaluj Jarvo jednym poleceniem (README, „Instalacja”); w kopii repo: python -m jarvo instaluj. "
            "Inny katalog: ustaw JARVO_ROOT.")


# ---------------------------------------------------------------- kompilacja i reszta poleceń skarbca

def polecenie_kompilacji(u: Uklad, env: dict, argumenty: list[str]) -> tuple[list[str], dict[str, str], Path | None]:
    """(argv, środowisko, katalog) procesu kompilacji: Python venvu Hermesa w trybie izolowanym (-I: bez PYTHONPATH
    i katalogu skryptu; -X utf8), kompilacja.py tej wersji, skarbiec i stan z `<dane>/jarvo`, profil jarvo.
    Środowisko: srodowisko.srodowisko(u) (bez sekretów i zmiennych obcych z powłoki właściciela; klucze modelu Hermes
    czyta sam z .env i auth.json) + HERMES_HOME profilu, HERMES_SRC i UTF-8. Bez Hermesa (tylko --na-sucho):
    bieżący Python."""
    app = _app(u)
    python = _python_hermesa(u) or Path(sys.executable)
    argv = [str(python), "-I", "-X", "utf8", str(app / "wiedza" / "kompilacja.py"), "--skarbiec", str(skarbiec(u)),
            "--stan", str(stan_skarbca(u)), "--profil", PROFIL, *argumenty]
    e = srodowisko.srodowisko(u, env)
    e.pop("HERMES_YOLO_MODE", None)
    if profil(u).is_dir():
        e["HERMES_HOME"] = str(profil(u))
    checkout = _checkout(u)
    if checkout:
        e["HERMES_SRC"] = str(checkout)
    e.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "JARVO_WIEDZA_PROFIL": PROFIL})
    return argv, e, (checkout if checkout and checkout.is_dir() else None)


def _na_pierwszym_planie(argv: list[str], env: dict, cwd: Path | None) -> int:
    """Proces w tym terminalu (wyjście wprost na ekran), bez okna na Windows."""
    return subprocess.call(argv, env=env, cwd=str(cwd) if cwd else None, stdin=subprocess.DEVNULL,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if not sys.stdout.isatty() else 0)


def polecenie_wiedza_kompiluj(u: Uklad, a, _reszta, ot, *, uruchom: Callable | None = None) -> int:
    if not _zainstalowane(u):
        return _brak_instalacji(u)
    if not skarbiec(u).is_dir():
        print(f"Skarbiec {skarbiec(u)} jeszcze nie istnieje: zakłada go instalacja floty (zasiew). Uruchom instalację "
              "ponownie.", file=sys.stderr)
        return 1
    if not a.na_sucho:
        if _python_hermesa(u) is None:
            print("Brak środowiska Hermesa (model kompilacji): uruchom instalację ponownie.", file=sys.stderr)
            return 1
        if not profil(u).is_dir():
            print(f"Profil {PROFIL} nie jest zainstalowany ({profil(u)}): kompilacja nie ma modelu (zadanie "
                  "jarvo_wiedza). Najpierw instalacja floty; podgląd bez modelu: jarvo wiedza kompiluj --na-sucho",
                  file=sys.stderr)
            return 1
    z = wiedza_lib(_app(u)).znacznik_blokady(stan_skarbca(u))
    if z and z["aktualny"] and not a.na_sucho:          # na sucho niczego nie zapisuje, więc blokady nie potrzebuje
        print(f"Skarbiec jest zajęty: kompilacja albo zasiew trwa (proces {z['pid']}, od {int(z['wiek_s'] // 60)} min). "
              "Spróbuj za chwilę; stan: jarvo wiedza status", file=sys.stderr)
        return 1
    argumenty = [*(["--na-sucho"] if a.na_sucho else []), *(["--limit", str(a.limit)] if a.limit else []),
                 *(["--json"] if a.json else [])]
    argv, env, cwd = polecenie_kompilacji(u, ot.env, argumenty)
    if not a.json:
        jak = "na sucho (bez modelu i bez zapisu)" if a.na_sucho else f"modelem profilu {PROFIL}"
        print(f"Skrzynka: {_szkice(u)} szkiców. Kompilacja {jak}…", flush=True)
    return int((uruchom or _na_pierwszym_planie)(argv, env, cwd))


def _sk_ix(u: Uklad):
    lib = wiedza_lib(_app(u))
    sk = lib.Skarbiec(skarbiec(u), stan_skarbca(u))
    return lib, sk


def polecenie_wiedza_lint(u: Uklad, a, _reszta, _ot) -> int:
    if not skarbiec(u).is_dir():
        print(f"Brak skarbca {skarbiec(u)} (zasiew robi instalacja floty).", file=sys.stderr)
        return 1
    lib, sk = _sk_ix(u)
    ix = lib.Indeks(sk)
    try:
        r = lib.lint(sk, ix)
    finally:
        ix.zamknij()
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(f"Lint skarbca: {r['notatek']} notatek · błędy: {len(r['bledy'])} · ostrzeżenia: {len(r['ostrzezenia'])} · "
              f"informacje: {len(r['informacje'])} → {sk.root / 'LINT.md'}")
        for b in r["bledy"][:20]:
            print(f"  ✗ {b}")
        for o in [x for x in r["ostrzezenia"] if x.startswith(("nazwa nieprzenośna", "ścieżka dłuższa", "nazwy różnią"))][:10]:
            print(f"  ! {o}")
    return 1 if a.strict and r["bledy"] else 0


def polecenie_wiedza_indeksuj(u: Uklad, a, _reszta, _ot) -> int:
    """Indeks FTS5, INDEX.md i listy w hubach (bloki GEN w notatkach), więc pod blokadą jednego piszącego."""
    if not skarbiec(u).is_dir():
        print(f"Brak skarbca {skarbiec(u)} (zasiew robi instalacja floty).", file=sys.stderr)
        return 1
    lib, sk = _sk_ix(u)
    blokada = lib.Blokada(sk.stan, czekaj_s=30.0)
    if not blokada.wez():
        print(f"Skarbiec zajęty ({blokada.powod}): spróbuj za chwilę.", file=sys.stderr)
        return 1
    try:
        ix = lib.Indeks(sk)
        try:
            r = ix.odswiez(pelny=a.pelny)
            n = lib.zbuduj_index(sk, ix)
            h = lib.odswiez_listy_hubow(sk, ix)
            ix.odswiez()
        finally:
            ix.zamknij()
    finally:
        blokada.zwolnij()
    print(f"Indeks: {r['pliki']} plików ({r['nowe']} nowych, {r['zmienione']} zmienionych, {r['usuniete']} usuniętych), "
          f"INDEX.md: {n} notatek, huby odświeżone: {h}")
    return 0


def _kiedy(t: float) -> str:
    if not t:
        return "nigdy"
    return dt.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M")


def polecenie_wiedza_status(u: Uklad, a, _reszta, _ot) -> int:
    if not skarbiec(u).is_dir():
        print(f"Brak skarbca {skarbiec(u)} (zasiew robi instalacja floty).", file=sys.stderr)
        return 1
    lib, sk = _sk_ix(u)
    ix = lib.Indeks(sk)
    try:
        r = lib.status(sk, ix)
    finally:
        ix.zamknij()
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    komp, lint, blok = r.get("kompilacja") or {}, r.get("lint") or {}, r.get("blokada")
    print(f"Skarbiec: {r['skarbiec']} · notatek: {sum(r['wg_folderu'].values())} · linków: {r['linki']} · szkiców: "
          f"{r['szkice']} · git: {'tak' if r['git'] else 'nie'}")
    raport = komp.get("raport") or {}
    print(f"Ostatnia kompilacja: {_kiedy(komp.get('ostatnia') or 0)}"
          + (f" (nowe: {raport.get('nowe', 0)}, aktualizacje: {raport.get('aktualizacje', 0)}, błędy: "
             f"{raport.get('bledy', 0)})" if raport else ""))
    print(f"Ostatni lint: {lint.get('data') or 'nigdy'}" + (f" (błędy: {lint.get('bledy', 0)}, ostrzeżenia: "
                                                            f"{lint.get('ostrzezenia', 0)})" if lint else ""))
    if blok and blok.get("aktualny"):
        print(f"Teraz: kompilacja albo zasiew trwa (proces {blok['pid']}, od {int(blok['wiek_s'] // 60)} min)")
    return 0


def polecenie_wiedza_doctor(u: Uklad, a, _reszta, ot) -> int:
    wyniki = sprawdzenia(u, ot)
    if a.json:
        print(json.dumps({"root": str(u.root), "wyniki": wyniki}, ensure_ascii=False, indent=2))
    else:
        znak = {"ok": "[ok]   ", "uwaga": "[uwaga]", "blad": "[błąd] "}
        print(f"Skarbiec, rutyny i Telegram: {u.root}")
        for r in wyniki:
            print(f"  {znak[r['stan']]} {r['nazwa']}: {r['opis']}")
            if r["rada"] and r["stan"] != "ok":
                print(f"          rada: {r['rada']}")
    return 1 if any(r["stan"] == "blad" for r in wyniki) else 0


# ---------------------------------------------------------------- sprawdzenia (K08): niczego nie zapisują

def synchronizowany(p: Path, env: dict | None = None) -> str | None:
    """Nazwa usługi synchronizacji, w której folderze leży `p` (OneDrive, iCloud, Dropbox, Dysk Google), albo None.
    SQLite w trybie WAL i git psują się przy synchronizacji (docs/WIEDZA.md §6: żadnej synchronizacji chmurowej)."""
    env = os.environ if env is None else env
    tekst = str(p).replace("\\", "/").lower()
    for zmienna in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        katalog = str(env.get(zmienna) or "").replace("\\", "/").lower().rstrip("/")
        if katalog and (tekst == katalog or tekst.startswith(katalog + "/")):
            return "OneDrive"
    czesci = tekst.split("/")
    for wzor, nazwa in (("onedrive", "OneDrive"), ("dropbox", "Dropbox"), ("google drive", "Dysk Google"),
                        ("googledrive", "Dysk Google"), ("my drive", "Dysk Google"), ("mobile documents", "iCloud"),
                        ("icloud", "iCloud"), ("cloudstorage", "folder chmury (CloudStorage)")):
        if any(c.startswith(wzor) for c in czesci):
            return nazwa
    return None


def _dysk_sieciowy(p: Path) -> bool:
    """Windows: ścieżka UNC albo litera dysku sieciowego (GetDriveTypeW = DRIVE_REMOTE)."""
    if not WINDOWS:
        return False
    s = str(p)
    if s.startswith("\\\\") and not s.startswith("\\\\?\\"):
        return True
    import ctypes
    korzen = os.path.splitdrive(os.path.abspath(s))[0] + "\\"
    try:
        return ctypes.windll.kernel32.GetDriveTypeW(korzen) == 4
    except (AttributeError, OSError):
        return False


def sprawdz_skarbiec(u: Uklad, env: dict | None = None) -> dict:
    k = skarbiec(u)
    if not k.is_dir():
        return _wynik("skarbiec", "uwaga", f"{k} nie istnieje (zasiew robi instalacja floty)",
                      "Uruchom instalację ponownie; skarbiec powstanie przy wdrożeniu floty.")
    sync = synchronizowany(k, env)
    if sync:
        return _wynik("skarbiec", "blad", f"{k} leży w folderze {sync}",
                      "Synchronizacja chmury psuje bazę indeksu i historię git skarbca: przenieś Jarvo poza ten folder "
                      "(JARVO_ROOT na lokalny dysk) i zainstaluj ponownie.")
    if _dysk_sieciowy(k):
        return _wynik("skarbiec", "uwaga", f"{k} leży na dysku sieciowym",
                      "SQLite (indeks skarbca) potrzebuje lokalnego dysku: przenieś Jarvo na dysk lokalny.")
    if not (k / "SCHEMA.md").is_file():
        return _wynik("skarbiec", "uwaga", f"{k}: brak SCHEMA.md (zasiew niepełny)",
                      "Uruchom instalację ponownie (zasiew skarbca w kroku floty).")
    notatek = sum(1 for p in k.rglob("*.md") if not any(c.startswith(".") for c in p.relative_to(k).parts)
                  and p.relative_to(k).parts[0] not in ("zrodla", "skrzynka"))
    return _wynik("skarbiec", "ok", f"{k} ({notatek} notatek)")


def sprawdz_fts5_hermesa(u: Uklad, uruchom: Callable | None = None) -> dict:
    """FTS5 z remove_diacritics w Pythonie Hermesa: indeks skarbca czyta wtyczka w bramie, nie Python polecenia jarvo."""
    python = _python_hermesa(u)
    if python is None:
        return _wynik("FTS5 w Pythonie Hermesa", "uwaga", "nie sprawdzone (brak środowiska Hermesa)",
                      "Uruchom instalację ponownie.")
    kod = ("import sqlite3;c=sqlite3.connect(':memory:');"
           "c.execute(\"CREATE VIRTUAL TABLE t USING fts5(x, tokenize='unicode61 remove_diacritics 2')\");"
           "c.execute(\"INSERT INTO t VALUES ('Gęś')\");"
           "print('ok' if c.execute(\"SELECT count(*) FROM t WHERE t MATCH 'ges'\").fetchone()[0]==1 else 'zle')")
    try:
        r = (uruchom or instalator._uruchom)([python, "-I", "-X", "utf8", "-c", kod])
        wyjscie = (r.stdout or "").strip()
    except (OSError, subprocess.SubprocessError) as e:
        wyjscie = f"błąd: {e}"
    if wyjscie == "ok":
        return _wynik("FTS5 w Pythonie Hermesa", "ok", "remove_diacritics działa („ges” znajduje „Gęś”)")
    return _wynik("FTS5 w Pythonie Hermesa", "blad", f"{python}: {wyjscie or 'brak odpowiedzi'}",
                  "Wyszukiwanie w skarbcu bez polskich znaków nie zadziała: zainstaluj ponownie (Python z instalacji).")


def _git(u: Uklad, ot) -> str | None:
    """git, którego używa skarbiec w procesach Jarva: z PATH środowiska Jarva (PortableGit z manifestu, I05),
    potem z PATH właściciela; tylko pełna ścieżka."""
    sciezka = srodowisko.srodowisko(u, ot.env).get("PATH")
    for kandydat in (shutil.which("git", path=sciezka), instalator.program_bezwzgledny(ot, "git")):
        if kandydat and os.path.isabs(kandydat):
            return kandydat
    return None


def sprawdz_git_skarbca(u: Uklad, ot) -> dict:
    git = _git(u, ot)
    if git is None:
        return _wynik("git skarbca", "uwaga", "brak gita: punkty zapisu i `wiedza.py cofnij` nie działają",
                      "Zainstaluj Git (Windows: Git for Windows, macOS: xcode-select --install, Linux: pakiet git); "
                      "PortableGit Jarva przyjdzie z manifestem (I05).")
    if skarbiec(u).is_dir() and not (skarbiec(u) / ".git").is_dir():
        return _wynik("git skarbca", "uwaga", f"{git}; skarbiec bez historii (brak .git)",
                      "Zasiew zakłada repozytorium git: uruchom instalację ponownie.")
    return _wynik("git skarbca", "ok", f"{git}" + ("; historia notatek: tak" if (skarbiec(u) / ".git").is_dir() else ""))


def long_paths(rejestr: Any = None) -> int | None:
    """Windows: HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem\\LongPathsEnabled (1, 0 albo None = brak wpisu)."""
    if rejestr is not None:
        return rejestr()
    if not WINDOWS:
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem") as k:
            return int(winreg.QueryValueEx(k, "LongPathsEnabled")[0])
    except (OSError, ValueError):
        return None


def najdluzsza_sciezka(k: Path) -> int:
    dl = 0
    for katalog, podkatalogi, pliki in os.walk(k):
        podkatalogi[:] = [d for d in podkatalogi if not d.startswith(".")]
        for nazwa in pliki:
            dl = max(dl, len(os.path.join(katalog, nazwa)))
    return dl


def sprawdz_dlugie_sciezki(u: Uklad, rejestr: Any = None) -> dict | None:
    """Windows (K08, Z25): bez LongPathsEnabled ścieżka ponad 260 znaków się nie otworzy; korzeń dłuższy niż ok. 100
    znaków albo plik bliżej limitu to ostrzeżenie. Na macOS i Linuksie None (nie dotyczy)."""
    if not WINDOWS and rejestr is None:
        return None
    wartosc = long_paths(rejestr)
    k = skarbiec(u)
    if wartosc == 1:
        return _wynik("długie ścieżki", "ok", "LongPathsEnabled = 1 (ścieżki ponad 260 znaków działają)")
    dl = najdluzsza_sciezka(k) if k.is_dir() else 0
    opis = (f"LongPathsEnabled = {wartosc if wartosc is not None else 'brak wpisu'}; korzeń {len(str(u.root))} znaków, "
            f"najdłuższa ścieżka w skarbcu {dl}")
    rada = ("Włącz długie ścieżki (raz, jako administrator: Edytor zasad grupy → Włącz długie ścieżki Win32, albo "
            "LongPathsEnabled=1 w rejestrze) albo przenieś Jarvo do krótszego katalogu (JARVO_ROOT, np. D:\\Jarvo).")
    wiedza = wiedza_lib(_app(u))
    if dl > wiedza.MAX_SCIEZKI or len(str(u.root)) > SCIEZKA_KORZENIA_MAKS:
        return _wynik("długie ścieżki", "uwaga", opis, rada)
    return _wynik("długie ścieżki", "ok", opis + " (w limicie 260)")


def _json(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def sprawdz_kompilacje(u: Uklad, teraz: float | None = None) -> dict:
    teraz = time.time() if teraz is None else teraz
    if not skarbiec(u).is_dir():
        return _wynik("kompilacja skarbca", "uwaga", "nie sprawdzona (brak skarbca)", "")
    komp = _json(stan_skarbca(u) / "wiedza-kompilacja.json")
    ostatnia = float(komp.get("ostatnia") or 0)
    raport = komp.get("raport") if isinstance(komp.get("raport"), dict) else {}
    szkice = _szkice(u)
    z = wiedza_lib(_app(u)).znacznik_blokady(stan_skarbca(u))
    if z and z.get("aktualny"):
        return _wynik("kompilacja skarbca", "ok", f"trwa teraz (proces {z['pid']}, od {int(z['wiek_s'] // 60)} min); "
                      f"szkiców: {szkice}")
    kiedy = _kiedy(ostatnia)
    if szkice and (not ostatnia or teraz - ostatnia > KOMPILACJA_STARA_S):
        return _wynik("kompilacja skarbca", "uwaga", f"{szkice} szkiców czeka, ostatnia kompilacja: {kiedy}",
                      "Kompilację odpala brama (co godzinę przy szkicach i co noc o 03:10, po uśpieniu nadrabia): "
                      "sprawdź `jarvo status` i model profilu jarvo; ręcznie: jarvo wiedza kompiluj.")
    if raport.get("bledy"):
        return _wynik("kompilacja skarbca", "uwaga", f"ostatnia ({kiedy}) z błędami: {raport.get('bledy')}",
                      "Szczegóły w LOG.md skarbca (zakładka Wiedza → Dziennik); szkic po 3 nieudanych próbach odpada.")
    return _wynik("kompilacja skarbca", "ok", f"ostatnia: {kiedy}; szkiców w skrzynce: {szkice}")


def sprawdz_lint(u: Uklad) -> dict:
    if not skarbiec(u).is_dir():
        return _wynik("lint skarbca", "uwaga", "nie sprawdzony (brak skarbca)", "")
    lint = _json(stan_skarbca(u) / "wiedza-lint.json")
    if not lint:                                   # skarbiec sprzed tej wersji: tylko LINT.md
        try:
            naglowek = (skarbiec(u) / "LINT.md").read_text(encoding="utf-8", errors="replace")[:600]
        except OSError:
            naglowek = ""
        m = re.search(r"Notatek: (\d+) · błędy: (\d+) · ostrzeżenia: (\d+)", naglowek)
        if not m:
            return _wynik("lint skarbca", "uwaga", "jeszcze nie biegł", "jarvo wiedza lint (robi go też każda "
                          "kompilacja i wdrożenie)")
        data = re.search(r"^# Lint skarbca \((\d{4}-\d{2}-\d{2})\)", naglowek, re.M)
        lint = {"notatek": int(m.group(1)), "bledy": int(m.group(2)), "ostrzezenia": int(m.group(3)),
                "data": data.group(1) if data else "?"}
    opis = (f"{lint.get('data', '?')}: {lint.get('notatek', 0)} notatek, błędy: {lint.get('bledy', 0)}, "
            f"ostrzeżenia: {lint.get('ostrzezenia', 0)}")
    if lint.get("bledy"):
        pierwszy = (lint.get("pierwsze_bledy") or [""])[0]
        return _wynik("lint skarbca", "uwaga", opis + (f" (np. {pierwszy[:120]})" if pierwszy else ""),
                      "Zakładka Wiedza → Lint albo `jarvo wiedza lint`; część naprawi kompilacja, resztę orzeczenie.")
    return _wynik("lint skarbca", "ok", opis)


def sprawdz_brame(u: Uklad, ot) -> dict:
    stan, powod = instalator.stan_serwisu(u, ot)
    if stan is None:
        return _wynik("brama", "uwaga", f"serwis nie działa ({powod or 'brak nadzorcy'}): rutyny, Telegram i "
                      "kompilacja skarbca stoją", "jarvo up")
    b = instalator.usluga_nadzorcy(stan, "brama")
    if b.get("stan") == "dziala":
        return _wynik("brama", "ok", f"działa (PID {b.get('pid')})" + ("" if b.get("gotowa", True) else ", wstaje"))
    if b.get("stan") == "postoj":
        return _wynik("brama", "blad", f"postój: {b.get('powod') or 'kod 78'}", "jarvo logs brama; potem jarvo up")
    return _wynik("brama", "uwaga", f"{b.get('stan') or 'brak'}" + (f" ({b['powod']})" if b.get("powod") else ""),
                  "jarvo status; jarvo logs brama")


def linger(uzytkownik: str | None = None, uruchom: Callable | None = None) -> bool | None:
    """Linux: czy systemd trzyma usługi użytkownika bez logowania (loginctl Linger); None = nie wiadomo."""
    loginctl = instalator.systemowy("loginctl")
    if not loginctl:
        return None
    try:
        r = (uruchom or instalator._uruchom)([loginctl, "show-user", uzytkownik or getpass.getuser(),
                                              "--property=Linger"])
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"Linger=(yes|no)", r.stdout or "")
    return None if not m else m.group(1) == "yes"


def sprawdz_rutyny(u: Uklad, ot, *, linux: bool = LINUX, uruchom: Callable | None = None) -> list[dict]:
    wyniki = []
    rutyny = stan_rutyn(u)
    if not rutyny["zainstalowane"]:
        wyniki.append(_wynik("rutyny", "uwaga", "brak rutyn Jarva (flota nie zainstalowana)",
                             "Uruchom instalację ponownie (krok floty instaluje profil jarvo z rutynami)."))
    else:
        wlaczone = [r for r in rutyny["lista"] if r.get("wlaczona")]
        brak = [r["id"] for r in rutyny["lista"] if not r.get("jest")]
        reczne = _json(stan_skarbca(u) / "rutyny.json")
        if brak:
            wyniki.append(_wynik("rutyny", "uwaga", f"brak {', '.join(brak)}", "Uruchom instalację ponownie."))
        elif not wlaczone:
            if reczne.get("reczne") and reczne.get("wlaczone") is False:
                wyniki.append(_wynik("rutyny", "ok", "wyłączone przez Ciebie (jarvo rutyny off)"))
            else:
                wyniki.append(_wynik("rutyny", "uwaga", "wstrzymane od instalacji",
                                     "Włączy je udana próbna wiadomość: jarvo telegram test (najpierw jarvo telegram "
                                     "ustaw); bez Telegrama: jarvo rutyny on."))
        else:
            lokalnie = [r["id"] for r in wlaczone if not str(r.get("deliver") or "").startswith("telegram")]
            opis = f"włączone {len(wlaczone)}/{len(rutyny['lista'])}"
            if lokalnie and konfiguracja_telegrama(u)["token"]:
                wyniki.append(_wynik("rutyny", "uwaga", opis + f"; piszą lokalnie: {', '.join(lokalnie)}",
                                     "Trasa do Ciebie wchodzi przy wdrożeniu floty: jarvo telegram ustaw (bez "
                                     "--bez-wdrozenia) albo jarvo instaluj."))
            else:
                wyniki.append(_wynik("rutyny", "ok", opis + ("; dostarczanie: Telegram" if not lokalnie else
                                                            "; dostarczanie: lokalnie (bez Telegrama)")))
        if catch_up_wylaczony(u):
            wyniki.append(_wynik("rutyny po uśpieniu", "uwaga", "cron.catch_up_missed: false w configu",
                                 "Bez tego komputer uśpiony w porze rutyny nie nadrobi jej po wybudzeniu: usuń tę linię."))
    if linux:
        jest = linger(uruchom=uruchom)
        if jest is not None:
            wyniki.append(_wynik("praca bez logowania", "ok", "linger włączony: rutyny i Telegram działają też bez "
                                 "zalogowania" if jest else "linger wyłączony: rutyny i Telegram działają po zalogowaniu "
                                 "(praca 24/7: loginctl enable-linger, za Twoją zgodą)"))
    return wyniki


def catch_up_wylaczony(u: Uklad) -> bool:
    """Czy config hosta albo profilu jarvo wyłącza nadrabianie rutyn po uśpieniu (cron.catch_up_missed: false)."""
    for p in (u.dane / "config.yaml", profil(u) / "config.yaml"):
        try:
            tekst = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(r"^\s+catch_up_missed:\s*(false|no|off)\b", tekst, re.M | re.I):
            return True
    return False


def sprawdz_telegram(u: Uklad, ot=None, teraz: float | None = None) -> list[dict]:
    k = konfiguracja_telegrama(u)
    wyniki = []
    if not k["token"]:
        wyniki.append(_wynik("Telegram", "uwaga", "bot nie jest ustawiony",
                             "jarvo telegram ustaw (token od @BotFather), potem jarvo telegram test."))
    else:
        opis = f"bot ustawiony; dozwolonych osób: {len(k['dozwoleni'])}"
        if not k["dozwoleni"] and not k["wszyscy"]:
            wyniki.append(_wynik("Telegram", "uwaga", opis + " (brak listy dozwolonych)",
                                 "Bez listy dozwolonych obcy dostają kod parowania: jarvo telegram ustaw --wlasciciel <ID>."))
        elif not k["wlasciciel"]:
            wyniki.append(_wynik("Telegram", "uwaga", opis + "; brak trasy DM → Jarvo (TELEGRAM_OWNER_ID)",
                                 "jarvo telegram ustaw --wlasciciel <Twoje ID>: DM trafi do Jarva, rutyny do Ciebie."))
        else:
            ostatni = _json(stan_skarbca(u) / "telegram.json").get("test_ok")
            wyniki.append(_wynik("Telegram", "ok", opis + "; trasa DM → Jarvo" + (f"; próbna wiadomość {_kiedy(ostatni)}"
                                                                               if ostatni else "")))
    konf = konflikt_409(u, teraz)
    if konf:
        wyniki.append(_wynik("Telegram: jedna brama na token", "blad",
                             f"409 Conflict w logu {konf['plik']} ({konf['kiedy'] or 'czas nieznany'}): drugi program "
                             "czyta tego samego bota",
                             "Wyłącz drugą bramę z tym tokenem: starą flotę Jarva z Dockerem/WSL (w Ubuntu: docker stop "
                             "jarvo-hermes; migracja: jarvo migruj, etap E12), prywatnego Hermesa albo OpenClaw z tym "
                             "botem; potem jarvo up. Inaczej wiadomości i rutyny idą raz tu, raz tam."))
    return wyniki


def sprawdzenia(u: Uklad, ot=None) -> list[dict]:
    """Wyniki dla `jarvo doctor` (K08): skarbiec (poza chmurą, FTS5 Hermesa, git, długie ścieżki, kompilacja, lint),
    brama, rutyny i Telegram (konfiguracja, 409). Nic nie zapisuje."""
    ot = ot or instalator.Otoczenie()
    wyniki = [sprawdz_skarbiec(u, ot.env), sprawdz_fts5_hermesa(u), sprawdz_git_skarbca(u, ot)]
    dlugie = sprawdz_dlugie_sciezki(u)
    if dlugie:
        wyniki.append(dlugie)
    wyniki += [sprawdz_kompilacje(u), sprawdz_lint(u), sprawdz_brame(u, ot), *sprawdz_rutyny(u, ot),
               *sprawdz_telegram(u, ot)]
    return wyniki


# ---------------------------------------------------------------- rutyny (H06, I36)

def rutyny_ids(app: Path) -> list[str]:
    """Identyfikatory rutyn Jarva z profiles/jarvo/cron/jobs.yaml tej wersji (stałe `id`), a bez pliku lista RUTYNY."""
    try:
        ids = ID_RUTYNY.findall((Path(app) / "profiles" / PROFIL / "cron" / "jobs.yaml").read_text(encoding="utf-8"))
    except OSError:
        ids = []
    return list(dict.fromkeys(ids)) or list(RUTYNY)


def _uruchamialna(job: dict) -> bool:
    """Jak cron.jobs.is_job_runnable Hermesa: `enabled` i bez znacznika wstrzymania."""
    return bool(job.get("enabled", True)) and str(job.get("state") or "").strip() != "paused" and not job.get("paused_at")


def stan_rutyn(u: Uklad) -> dict:
    """{"zainstalowane": bool, "lista": [{"id", "jest", "nazwa", "wlaczona", "stan", "deliver", "harmonogram",
    "nastepny"}]} z `<dane>/profiles/jarvo/cron/jobs.json` (tylko odczyt)."""
    plik = profil(u) / "cron" / "jobs.json"
    dane = _json(plik)
    zadania = {str(j.get("id")): j for j in (dane.get("jobs") or []) if isinstance(j, dict)}
    lista = []
    for i in rutyny_ids(_app(u)):
        j = zadania.get(i)
        if j is None:
            lista.append({"id": i, "jest": False})
            continue
        sched = j.get("schedule")
        harm = j.get("schedule_display") or ((sched.get("expr") or sched.get("display")) if isinstance(sched, dict)
                                             else sched)
        lista.append({"id": i, "jest": True, "nazwa": j.get("name") or i, "wlaczona": _uruchamialna(j),
                      "stan": j.get("state") or "", "deliver": j.get("deliver") or "", "harmonogram": harm or "",
                      "nastepny": j.get("next_run_at") or ""})
    return {"zainstalowane": plik.is_file(), "plik": str(plik), "lista": lista}


def _hermes_cron(u: Uklad, env: dict, akcja: str, ident: str, uruchom: Callable | None = None) -> tuple[int, str]:
    from jarvo import hermes
    checkout = _checkout(u)
    argv = hermes.argv_hermesa(checkout, "-p", PROFIL, "cron", akcja, ident)
    try:
        r = (uruchom or _uruchom_hermesa)(argv, env, checkout)
    except (OSError, subprocess.SubprocessError) as e:
        return 1, str(e)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def _uruchom_hermesa(argv: list[str], env: dict, cwd: Path | None) -> subprocess.CompletedProcess:
    return subprocess.run([str(x) for x in argv], env=env, cwd=str(cwd) if cwd else None, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=CZAS_HERMESA, stdin=subprocess.DEVNULL,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def przelacz_rutyny(u: Uklad, env: dict, wlacz: bool, powod: str, *, reczne: bool,
                    uruchom: Callable | None = None) -> dict:
    """`hermes -p jarvo cron resume|pause <id>` dla każdej rutyny Jarva (równolegle: jobs.json ma blokadę między
    procesami, a wątek crona bramy czyta go przy każdym tyknięciu, więc restart bramy nie jest potrzebny). Zapis
    w `<dane>/jarvo/state/rutyny.json`: kto i kiedy (reczne=True: decyzja właściciela, której próbna wiadomość
    nie zmienia)."""
    if _checkout(u) is None or _python_hermesa(u) is None:
        raise RuntimeError("brak środowiska Hermesa: uruchom instalację ponownie")
    rutyny = [r["id"] for r in stan_rutyn(u)["lista"] if r.get("jest")]
    if not rutyny:
        raise RuntimeError("brak rutyn Jarva (flota nie zainstalowana)")
    e = srodowisko.srodowisko(u, env)
    e.pop("HERMES_YOLO_MODE", None)
    akcja = "resume" if wlacz else "pause"
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(rutyny)) as pula:
        kody = dict(zip(rutyny, pula.map(lambda i: _hermes_cron(u, e, akcja, i, uruchom), rutyny)))
    wyniki = {i: "ok" if kod == 0 else f"błąd (kod {kod}): {_bez_tokenu(tekst)[-160:]}" for i, (kod, tekst) in kody.items()}
    stan = {"wlaczone": wlacz, "kiedy": time.strftime("%Y-%m-%dT%H:%M:%S"), "powod": powod, "reczne": reczne,
            "wyniki": wyniki}
    przenosne.zapisz_atomowo(stan_skarbca(u) / "rutyny.json", json.dumps(stan, ensure_ascii=False, indent=1) + "\n")
    return stan


def opis_rutyn(u: Uklad) -> list[str]:
    r = stan_rutyn(u)
    if not r["zainstalowane"]:
        return [f"Rutyn jeszcze nie ma ({r['plik']}): instaluje je krok floty."]
    w = []
    for x in r["lista"]:
        if not x.get("jest"):
            w.append(f"  {x['id']}: brak")
            continue
        dokad = "Telegram" if str(x["deliver"]).startswith("telegram") else \
            "lokalnie" if str(x["deliver"] or "local") == "local" else x["deliver"]
        w.append(f"  {x['nazwa']} ({x['id']}): {'włączona' if x['wlaczona'] else 'wstrzymana'} · {x['harmonogram']} · "
                 f"dostarczanie: {dokad}" + (f" · następnie {x['nastepny']}" if x["wlaczona"] and x["nastepny"] else ""))
    return w


def polecenie_rutyny(u: Uklad, a, _reszta, ot, *, uruchom: Callable | None = None) -> int:
    if not _zainstalowane(u):
        return _brak_instalacji(u)
    if a.akcja == "status":
        if a.json:
            print(json.dumps({**stan_rutyn(u), "zapis": _json(stan_skarbca(u) / "rutyny.json")}, ensure_ascii=False,
                             indent=1))
            return 0
        print("Rutyny Jarva (cron w bramie; działają, gdy działa serwis):")
        for linia in opis_rutyn(u):
            print(linia)
        b = sprawdz_brame(u, ot)
        if b["stan"] != "ok":
            print(f"Uwaga: brama {b['opis']}.")
        return 0
    wlacz = a.akcja == "on"
    print(("Włączam" if wlacz else "Wstrzymuję") + " rutyny Jarva…", flush=True)
    try:
        stan = przelacz_rutyny(u, ot.env, wlacz, f"jarvo rutyny {a.akcja}", reczne=True, uruchom=uruchom)
    except RuntimeError as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 1
    for i, w in stan["wyniki"].items():
        print(f"  {i}: {w}")
    if wlacz and not konfiguracja_telegrama(u)["wlasciciel"]:
        print("Telegram nie jest ustawiony: rutyny zapiszą wyniki lokalnie (jarvo telegram ustaw, żeby pisały do Ciebie).")
    return 0 if all(w == "ok" for w in stan["wyniki"].values()) else 1


# ---------------------------------------------------------------- Telegram (H11)

def _bez_tokenu(tekst: str, token: str = "") -> str:
    tekst = tekst.replace(token, "***") if token else tekst
    return TOKEN_W_TEKSCIE.sub("***", tekst)


def czytaj_env(p: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        linie = p.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return out
    for linia in linie:
        m = LINIA_ENV.match(linia)
        if m and not linia.lstrip().startswith("#"):
            v = m.group(2).strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
                v = v[1:-1]
            out[m.group(1)] = v
    return out


def zapisz_env(p: Path, zmiany: dict[str, str]) -> list[str]:
    """Scala `zmiany` z plikiem .env (inne linie i komentarze zostają), zapis atomowy z LF, plik tylko dla właściciela
    (POSIX 0600, Windows ACL). Zwraca nazwy zmienionych kluczy; wartości nigdzie nie wypisujemy."""
    try:
        linie = p.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        linie = []
    stare = czytaj_env(p)
    zmienione = [k for k, v in zmiany.items() if stare.get(k) != v]
    if not zmienione and p.exists():
        return []
    widziane = set()
    for i, linia in enumerate(linie):
        m = LINIA_ENV.match(linia)
        if m and not linia.lstrip().startswith("#") and m.group(1) in zmiany:
            if m.group(1) in widziane:
                linie[i] = None            # druga linia z tym samym kluczem: zostaje jedna
                continue
            linie[i] = f"{m.group(1)}={zmiany[m.group(1)]}"
            widziane.add(m.group(1))
    linie = [x for x in linie if x is not None] + [f"{k}={v}" for k, v in zmiany.items() if k not in widziane]
    przenosne.zapisz_atomowo(p, "\n".join(linie) + "\n", tryb=0o600)
    with contextlib.suppress(OSError):
        przenosne.chron(p)
    return zmienione


def konfiguracja_telegrama(u: Uklad) -> dict:
    """Co jest ustawione (bez wartości tokenu): `<dane>/.env` bramy i trasy z `<dane>/jarvo/konfig/jarvo.env`."""
    env = czytaj_env(u.dane / ".env")
    trasy = czytaj_env(konfig(u) / "jarvo.env")
    dozwoleni = [x.strip() for x in (env.get("TELEGRAM_ALLOWED_USERS") or "").split(",") if x.strip()]
    return {"token": bool((env.get("TELEGRAM_BOT_TOKEN") or "").strip()), "dozwoleni": dozwoleni,
            "wszyscy": (env.get("TELEGRAM_ALLOW_ALL_USERS") or "").strip().lower() in ("1", "true", "yes"),
            "wlasciciel": (trasy.get("TELEGRAM_OWNER_ID") or "").strip(),
            "grupa": (trasy.get("TELEGRAM_HQ_CHAT_ID") or "").strip(),
            "dom": (env.get("TELEGRAM_HOME_CHANNEL") or "").strip()}


def _token(u: Uklad) -> str:
    return (czytaj_env(u.dane / ".env").get("TELEGRAM_BOT_TOKEN") or "").strip()


def api_telegrama(token: str, metoda: str, dane: dict | None = None, *, czas: float = 20.0,
                  baza: str | None = None) -> Any:
    """Bot API (JSON przez POST). BladTelegrama z kodem i opisem bez tokenu; adres w BladTelegrama nie trafia, bo
    zawiera token. Adres lokalny (atrapa, własny serwer Bot API) bez proxy z otoczenia."""
    baza = (baza or os.environ.get("JARVO_TELEGRAM_API") or TELEGRAM_API).rstrip("/")
    url = f"{baza}/bot{token}/{metoda}"
    zapytanie = urllib.request.Request(url, data=json.dumps(dane or {}).encode("utf-8"), method="POST",
                                       headers={"Content-Type": "application/json", "User-Agent": "jarvo"})
    host = urllib.parse.urlsplit(baza).hostname or ""
    otwieracz = urllib.request.build_opener(urllib.request.ProxyHandler({})) if host in ("127.0.0.1", "localhost", "::1") \
        else urllib.request.build_opener()
    try:
        with otwieracz.open(zapytanie, timeout=czas) as r:
            odp = json.loads(r.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        try:
            odp = json.loads(e.read().decode("utf-8", errors="replace"))
        except ValueError:
            odp = {"ok": False, "error_code": e.code, "description": str(e.reason)}
    except (urllib.error.URLError, OSError, ValueError) as e:
        powod = getattr(e, "reason", e)
        raise BladTelegrama(0, _bez_tokenu(f"brak połączenia z Telegramem ({powod})", token)) from None
    if not isinstance(odp, dict) or not odp.get("ok"):
        odp = odp if isinstance(odp, dict) else {}
        raise BladTelegrama(int(odp.get("error_code") or 0), _bez_tokenu(str(odp.get("description") or "błąd API"), token))
    return odp.get("result")


def rada_telegrama(e: BladTelegrama) -> str:
    if e.kod == 401:
        return "Telegram nie zna tego tokenu: skopiuj go jeszcze raz z @BotFather (/token) i uruchom jarvo telegram ustaw."
    if e.kod == 409:
        return ("Ten bot jest już czytany przez inny program (409): stara flota Jarva z Dockerem/WSL, prywatny Hermes "
                "albo OpenClaw z tym tokenem. Wyłącz go albo załóż nowego bota w @BotFather.")
    if e.kod == 403:
        return "Bot nie może do Ciebie pisać (zablokowany?): odblokuj go w Telegramie i napisz do niego /start."
    if e.kod == 400 and "chat not found" in str(e).lower():
        return "Bot nie może zacząć rozmowy sam: napisz do niego w Telegramie /start i spróbuj ponownie."
    if e.kod == 0:
        return "Sprawdź połączenie z internetem (i czy zapora nie blokuje api.telegram.org)."
    return "Spróbuj ponownie za chwilę; szczegóły wyżej."


def wykryj_wlasciciela(token: str, *, limit_s: float = 120.0, wypisz: Callable = print, pytaj: Callable = input,
                       zegar: Callable = time.monotonic) -> str | None:
    """ID właściciela z pierwszej wiadomości do bota (getUpdates z długim odpytywaniem), z potwierdzeniem; wiadomość
    jest potem potwierdzona (offset), żeby brama jej nie przetworzyła. 409 = bota czyta już inny program."""
    koniec = zegar() + limit_s
    offset = None
    while zegar() < koniec:
        dane = {"timeout": int(max(1, min(25, koniec - zegar()))), "allowed_updates": ["message"]}
        if offset is not None:
            dane["offset"] = offset
        aktualizacje = api_telegrama(token, "getUpdates", dane, czas=dane["timeout"] + 10) or []
        for akt in aktualizacje:
            offset = int(akt.get("update_id", 0)) + 1
            nadawca = ((akt.get("message") or {}).get("from") or {})
            ident = str(nadawca.get("id") or "")
            if not ID_RE.match(ident) or nadawca.get("is_bot"):
                continue
            kto = " ".join(x for x in (nadawca.get("first_name"), f"@{nadawca['username']}" if nadawca.get("username")
                                       else "") if x)
            odp = pytaj(f"Widzę wiadomość od {kto or 'kogoś'} (ID {ident}). To Ty? [T/n] ").strip().lower()
            if odp in ("", "t", "tak", "y", "yes"):
                with contextlib.suppress(BladTelegrama):
                    api_telegrama(token, "getUpdates", {"offset": offset, "timeout": 0}, czas=10)
                return ident
    if offset is not None:
        with contextlib.suppress(BladTelegrama):
            api_telegrama(token, "getUpdates", {"offset": offset, "timeout": 0}, czas=10)
    wypisz("Nie dostałem wiadomości do bota w wyznaczonym czasie.")
    return None


def _czytaj_token(u: Uklad, a, interaktywnie: bool, pytaj_ukryte: Callable = getpass.getpass) -> str | None:
    """Token z wejścia (--token-ze-stdin, jedna linia), z ukrytego pytania (Enter = zostaje zapisany) albo zapisany.
    None = bez terminala i bez zapisanego tokenu (trzeba --token-ze-stdin). Token nigdy nie idzie w argumentach,
    bo trafiłby do historii powłoki i listy procesów."""
    stary = _token(u)
    if a.token_ze_stdin:
        return (sys.stdin.readline() or "").strip()
    if interaktywnie:
        tekst = "Token bota od @BotFather (nie pokażę go; Enter = bez zmiany): " if stary else \
            "Token bota od @BotFather (nie pokażę go na ekranie): "
        return pytaj_ukryte(tekst).strip() or stary
    return stary or None


def wdroz_flote(u: Uklad, ot, log: Callable = print) -> dict:
    """Build i instalacja floty (jarvo/flota.py), potem restart usług, które tego wymagają, przez nadzorcę (gdy
    działa). Trasy Telegrama trafiają do configu bramy, a `deliver` rutyn na Telegram właściciela."""
    flota = ot.modul("flota")
    wynik = flota.zainstaluj_flote(u, srodowisko.srodowisko(u, ot.env), log=log)
    stan, _ = instalator.stan_serwisu(u, ot)
    wynik["zrestartowane"] = []
    if stan is not None:
        klient = ot.modul("nadzorca").polacz(u)
        for nazwa in flota.uslugi_do_restartu(wynik):
            klient.restart(nazwa)
            wynik["zrestartowane"].append(nazwa)
        if "panel" in wynik["zrestartowane"]:
            flota.potwierdz_restart_panelu(u, wynik.get("odcisk_panelu") or "")
    return wynik


def restart_bramy(u: Uklad, ot) -> bool:
    stan, _ = instalator.stan_serwisu(u, ot)
    if stan is None:
        return False
    ot.modul("nadzorca").polacz(u).restart("brama")
    return True


def polecenie_telegram_ustaw(u: Uklad, a, _reszta, ot, *, pytaj: Callable = input,
                             pytaj_ukryte: Callable = getpass.getpass, interaktywnie: bool | None = None) -> int:
    if not _zainstalowane(u):
        return _brak_instalacji(u)
    interaktywnie = sys.stdin.isatty() if interaktywnie is None else interaktywnie
    token = _czytaj_token(u, a, interaktywnie, pytaj_ukryte)
    if token is None:
        print("Bez terminala podaj token przez wejście: jarvo telegram ustaw --token-ze-stdin (token w argumentach "
              "trafiłby do historii powłoki). Nic nie zmieniłem.", file=sys.stderr)
        return 2
    if not TOKEN_RE.match(token or ""):
        print("To nie wygląda na token bota (liczba, dwukropek i długi ciąg znaków z @BotFather). Nic nie zmieniłem.",
              file=sys.stderr)
        return 2
    bot = ""
    if not a.bez_sprawdzenia:
        try:
            ja = api_telegrama(token, "getMe") or {}
            bot = f"@{ja.get('username')}" if ja.get("username") else "bot"
            print(f"Token działa: {bot}.")
        except BladTelegrama as e:
            print(f"BŁĄD: Telegram odrzucił token ({e}). {rada_telegrama(e)} Nic nie zmieniłem.", file=sys.stderr)
            return 1
    k = konfiguracja_telegrama(u)
    wlasciciel = (a.wlasciciel or "").strip() or k["wlasciciel"]
    if not wlasciciel and interaktywnie:
        print(f"Napisz teraz do {bot or 'swojego bota'} w Telegramie dowolną wiadomość (np. /start). Czekam do 2 minut…",
              flush=True)
        try:
            wlasciciel = wykryj_wlasciciela(token, pytaj=pytaj) or ""
        except BladTelegrama as e:
            print(f"Nie umiem odczytać wiadomości do bota ({e}). {rada_telegrama(e)}")
        if not wlasciciel:
            wlasciciel = pytaj("Podaj swoje ID w Telegramie (liczba, np. z @userinfobot): ").strip()
    if not ID_RE.match(wlasciciel or "") or wlasciciel.startswith("-"):
        print("Brak poprawnego ID właściciela (liczba). Podaj je: jarvo telegram ustaw --wlasciciel <ID>. Nic nie "
              "zmieniłem.", file=sys.stderr)
        return 2
    if a.grupa and not (ID_RE.match(a.grupa) and a.grupa.startswith("-")):
        print("ID grupy Jarvo HQ zaczyna się od „-100…”. Nic nie zmieniłem.", file=sys.stderr)
        return 2
    env_bramy = czytaj_env(u.dane / ".env")
    dozwoleni = [x.strip() for x in (env_bramy.get("TELEGRAM_ALLOWED_USERS") or "").split(",") if x.strip()]
    zmiany = {"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_ALLOWED_USERS": ",".join(dict.fromkeys([*dozwoleni, wlasciciel]))}
    if not (env_bramy.get("TELEGRAM_HOME_CHANNEL") or "").strip():
        zmiany["TELEGRAM_HOME_CHANNEL"] = wlasciciel
    zmienione = zapisz_env(u.dane / ".env", zmiany)
    if (konfig(u) / "host.env").is_file():        # źródło sekretów przy wdrożeniu (merge_env): to samo, żeby nie cofnęło
        zapisz_env(konfig(u) / "host.env", zmiany)
    trasy = {"TELEGRAM_OWNER_ID": wlasciciel, **({"TELEGRAM_HQ_CHAT_ID": a.grupa} if a.grupa else {})}
    zmienione_trasy = zapisz_env(konfig(u) / "jarvo.env", trasy)
    print(f"Zapisane w {u.dane / '.env'} (wartości nie pokazuję): {', '.join(zmienione) or 'bez zmian'}.")
    print(f"Trasy w {konfig(u) / 'jarvo.env'}: DM → Jarvo (ID {wlasciciel})"
          + (f", grupa Jarvo HQ {a.grupa}" if a.grupa else "") + ("" if zmienione_trasy else " (bez zmian)") + ".")
    rutyny = stan_rutyn(u)
    rutyny_do_mnie = all(str(r.get("deliver")) == f"telegram:{wlasciciel}" for r in rutyny["lista"] if r.get("jest"))
    wdrozenie = bool(zmienione_trasy) or (rutyny["zainstalowane"] and not rutyny_do_mnie)
    if not (zmienione or wdrozenie):
        print("Nic się nie zmieniło: wdrożenie i restart bramy niepotrzebne.")
    elif a.bez_wdrozenia or not (profil(u) / "distribution.yaml").is_file():
        if zmienione and restart_bramy(u, ot):
            print("Brama uruchamia się ponownie z nowym tokenem.")
        if wdrozenie:
            print("Trasy i dostarczanie rutyn na Telegram wejdą przy następnym wdrożeniu floty (jarvo instaluj).")
    else:
        print("Wdrażam flotę z nowymi trasami (build i instalacja, zwykle około minuty)…", flush=True)
        try:
            wynik = wdroz_flote(u, ot, log=lambda s: None)
        except Exception as e:                   # noqa: BLE001 - wdrożenie można powtórzyć; ustawienia już są
            print(f"BŁĄD wdrożenia floty: {_bez_tokenu(str(e), token)}\nUstawienia są zapisane; powtórz: jarvo instaluj.",
                  file=sys.stderr)
            return 1
        restarty = wynik.get("zrestartowane") or []
        if "brama" not in restarty and zmienione and restart_bramy(u, ot):
            restarty.append("brama")
        print("Flota wdrożona" + (f"; restart: {', '.join(restarty)}" if restarty else
                                  "; serwis nie działa: zmiany wejdą przy jarvo up") + ".")
    print("Teraz próbna wiadomość: jarvo telegram test (po udanej rutyny Jarva się włączą).")
    return 0


def polecenie_telegram_test(u: Uklad, a, _reszta, ot, *, uruchom: Callable | None = None) -> int:
    if not _zainstalowane(u):
        return _brak_instalacji(u)
    token = _token(u)
    k = konfiguracja_telegrama(u)
    cel = k["wlasciciel"] or (k["dozwoleni"][0] if k["dozwoleni"] else "")
    if not token or not cel:
        print("Telegram nie jest ustawiony (token i ID właściciela): jarvo telegram ustaw.", file=sys.stderr)
        return 1
    try:
        ja = api_telegrama(token, "getMe") or {}
        api_telegrama(token, "sendMessage", {"chat_id": cel, "text": "Jarvo: próbna wiadomość z Twojego komputera. "
                                                                     "Jeśli ją widzisz, Telegram działa."})
    except BladTelegrama as e:
        print(f"BŁĄD: nie wysłałem próbnej wiadomości ({e}). {rada_telegrama(e)}", file=sys.stderr)
        return 1
    bot = f"@{ja.get('username')}" if ja.get("username") else "bot"
    print(f"Próbna wiadomość wysłana przez {bot} do ID {cel}: sprawdź Telegram.")
    with contextlib.suppress(OSError):
        przenosne.zapisz_atomowo(stan_skarbca(u) / "telegram.json",
                                 json.dumps({"test_ok": time.time(), "bot": bot, "do": cel}, ensure_ascii=False) + "\n")
    if a.bez_rutyn:
        return 0
    zapis = _json(stan_skarbca(u) / "rutyny.json")
    if zapis.get("reczne") and zapis.get("wlaczone") is False:
        print("Rutyny zostają wyłączone, bo wyłączyłeś je sam (włączenie: jarvo rutyny on).")
        return 0
    if not stan_rutyn(u)["zainstalowane"]:
        print("Rutyn jeszcze nie ma (flota nie zainstalowana).")
        return 0
    if all(r.get("wlaczona") for r in stan_rutyn(u)["lista"] if r.get("jest")):
        print("Rutyny już są włączone.")
        return 0
    print("Włączam rutyny Jarva (I36: po udanej próbnej wiadomości)…", flush=True)
    try:
        stan = przelacz_rutyny(u, ot.env, True, "próbna wiadomość Telegram", reczne=False, uruchom=uruchom)
    except RuntimeError as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 1
    bledy = {i: w for i, w in stan["wyniki"].items() if w != "ok"}
    print("Rutyny włączone." if not bledy else "Nie wszystkie rutyny się włączyły: " +
          "; ".join(f"{i}: {w}" for i, w in bledy.items()))
    lokalnie = [r["id"] for r in stan_rutyn(u)["lista"] if r.get("jest") and not str(r.get("deliver")).startswith("telegram")]
    if lokalnie:
        print("Uwaga: rutyny nadal piszą lokalnie (" + ", ".join(lokalnie) + "): trasa do Ciebie wejdzie przy wdrożeniu "
              "floty (jarvo instaluj).")
    return 0 if not bledy else 1


POLACZONY_RE = re.compile(r"Connected to Telegram \(polling", re.I)   # adapter Hermesa po (ponownym) starcie bramy


def konflikt_409(u: Uklad, teraz: float | None = None, okno_s: float = OKNO_409_S) -> dict | None:
    """Ostatni ślad 409 Conflict (drugi program czyta tego samego bota) w logach bramy z ostatnich `okno_s` sekund:
    `<logi>/brama.log` (+ .1) i logi Hermesa w `<dane>/logs`; czyta tylko końcówki. Linia bez czasu (ślad wyjątku)
    dostaje czas ostatniej linii z czasem przed nią, a gdy takiej nie ma, czas zmiany pliku. Konflikt, po którym brama
    połączyła się z Telegramem od nowa (start po wyłączeniu drugiej bramy), już nie jest aktualny."""
    teraz = time.time() if teraz is None else teraz
    pliki = [u.logi / "brama.log", u.logi / "brama.log.1", u.dane / "logs" / "gateway.log",
             u.dane / "logs" / "errors.log", u.dane / "logs" / "agent.log"]
    znaleziony, polaczony = None, 0.0
    for p in pliki:
        try:
            with open(p, "rb") as f:
                f.seek(0, os.SEEK_END)
                rozmiar = f.tell()
                f.seek(max(0, rozmiar - OKNO_LOGU_B))
                tekst = f.read().decode("utf-8", errors="replace")
            czas_pliku = p.stat().st_mtime
        except OSError:
            continue
        ostatni: tuple[float, str] | None = None
        for linia in tekst.splitlines():
            m = CZAS_W_LINII.search(linia[:40])
            if m:
                with contextlib.suppress(ValueError):
                    kiedy = f"{m.group(1)} {m.group(2)}"
                    ostatni = (dt.datetime.strptime(kiedy, "%Y-%m-%d %H:%M:%S").timestamp(), kiedy)
            chwila, kiedy = ostatni or (czas_pliku, "")
            if POLACZONY_RE.search(linia):
                polaczony = max(polaczony, chwila)
                continue
            if not KONFLIKT_RE.search(linia) or teraz - chwila > okno_s:
                continue
            if znaleziony is None or chwila >= znaleziony["_t"]:
                znaleziony = {"plik": str(p), "kiedy": kiedy, "linia": _bez_tokenu(linia.strip())[:200], "_t": chwila}
    if znaleziony is None or polaczony > znaleziony["_t"]:
        return None
    znaleziony.pop("_t")
    return znaleziony


def polecenie_telegram_status(u: Uklad, a, _reszta, ot) -> int:
    k = konfiguracja_telegrama(u)
    wynik = {**k, "test": _json(stan_skarbca(u) / "telegram.json"), "konflikt_409": konflikt_409(u),
             "rutyny": [{x: r.get(x) for x in ("id", "wlaczona", "deliver")} for r in stan_rutyn(u)["lista"]]}
    if getattr(a, "sprawdz", False) and k["token"]:
        try:
            ja = api_telegrama(_token(u), "getMe") or {}
            wynik["bot"] = f"@{ja.get('username')}"
        except BladTelegrama as e:
            wynik["bot_blad"] = f"{e} ({rada_telegrama(e)})"
    if a.json:
        print(json.dumps(wynik, ensure_ascii=False, indent=1))
        return 0
    print(f"Bot: {'ustawiony' if k['token'] else 'brak'}" + (f" ({wynik['bot']})" if wynik.get("bot") else "")
          + (f"; sprawdzenie: {wynik['bot_blad']}" if wynik.get("bot_blad") else ""))
    print(f"Dozwolone osoby: {len(k['dozwoleni'])}" + ("; wszyscy (TELEGRAM_ALLOW_ALL_USERS)" if k["wszyscy"] else ""))
    print(f"Trasa DM → Jarvo: {k['wlasciciel'] or 'brak (TELEGRAM_OWNER_ID)'}; grupa Jarvo HQ: {k['grupa'] or 'brak'}")
    test = wynik["test"]
    print(f"Ostatnia próbna wiadomość: {_kiedy(test.get('test_ok') or 0)}")
    for linia in opis_rutyn(u):
        print(linia)
    if wynik["konflikt_409"]:
        print(f"UWAGA: 409 Conflict w {wynik['konflikt_409']['plik']} ({wynik['konflikt_409']['kiedy'] or '?'}): "
              "drugi program czyta tego samego bota (szczegóły: jarvo doctor).")
    return 0


# ---------------------------------------------------------------- parser

def dodaj_polecenia(sub) -> None:
    """Polecenia `wiedza`, `rutyny` i `telegram` w parserze jarvo (cli._parser); funkcje biorą (u, a, reszta, ot)."""
    s = sub.add_parser("wiedza", help="skarbiec wiedzy: kompilacja, lint, indeks, stan i diagnoza",
                       description="Skarbiec wiedzy floty (docs/WIEDZA.md) w tej instalacji.")
    w = s.add_subparsers(dest="wiedza_polecenie", metavar="polecenie", title="polecenia")
    w.required = True
    k = w.add_parser("kompiluj", help="kompilacja szkiców ze skrzynki modelem profilu jarvo (jak przycisk w panelu)")
    k.add_argument("--na-sucho", action="store_true", help="tylko szkice i kandydaci, bez modelu i bez zapisu")
    k.add_argument("--limit", type=int, default=0, help="najwięcej szkiców w tym przebiegu (domyślnie 40)")
    k.add_argument("--json", action="store_true", help="raport w JSON")
    k.set_defaults(funkcja=polecenie_wiedza_kompiluj)
    k = w.add_parser("lint", help="raport zdrowia skarbca (LINT.md), także nazwy nieprzenośne")
    k.add_argument("--json", action="store_true")
    k.add_argument("--strict", action="store_true", help="kod 1 przy błędach")
    k.set_defaults(funkcja=polecenie_wiedza_lint)
    k = w.add_parser("indeksuj", help="indeks wyszukiwania, INDEX.md i listy w hubach")
    k.add_argument("--pelny", action="store_true", help="przebuduj indeks od zera")
    k.set_defaults(funkcja=polecenie_wiedza_indeksuj)
    k = w.add_parser("status", help="liczby, ostatnia kompilacja i lint")
    k.add_argument("--json", action="store_true")
    k.set_defaults(funkcja=polecenie_wiedza_status)
    k = w.add_parser("doctor", help="diagnoza skarbca, rutyn i Telegrama (część jarvo doctor)")
    k.add_argument("--json", action="store_true")
    k.set_defaults(funkcja=polecenie_wiedza_doctor)

    s = sub.add_parser("rutyny", help="rutyny Jarva (patrol, brief, przegląd, świeżość): status, on, off",
                       description="Rutyny Jarva działają w bramie. Po instalacji są wstrzymane; włącza je udana "
                       "próbna wiadomość (jarvo telegram test) albo `jarvo rutyny on`.")
    s.add_argument("akcja", nargs="?", choices=("status", "on", "off"), default="status", metavar="status|on|off")
    s.add_argument("--json", action="store_true")
    s.set_defaults(funkcja=polecenie_rutyny)

    s = sub.add_parser("telegram", help="bot Telegram: ustaw, test, status",
                       description="Bot Telegram floty: token i lista dozwolonych w <dane>/.env (nigdy na ekranie), "
                       "trasy w <dane>/jarvo/konfig/jarvo.env.")
    t = s.add_subparsers(dest="telegram_polecenie", metavar="polecenie", title="polecenia")
    t.required = True
    k = t.add_parser("ustaw", help="token bota, Twoje ID, trasy; potem wdrożenie floty")
    k.add_argument("--wlasciciel", metavar="ID", help="Twoje ID w Telegramie (bez niego: z wiadomości do bota)")
    k.add_argument("--grupa", metavar="ID", help="ID supergrupy Jarvo HQ (-100…), opcjonalnie")
    k.add_argument("--token-ze-stdin", action="store_true", help="token z wejścia (jedna linia), bez pytania")
    k.add_argument("--bez-wdrozenia", action="store_true", help="tylko zapis ustawień (trasy przy następnym wdrożeniu)")
    k.add_argument("--bez-sprawdzenia", action="store_true", help="bez getMe (bez sieci; token sprawdzi test)")
    k.set_defaults(funkcja=polecenie_telegram_ustaw)
    k = t.add_parser("test", help="próbna wiadomość do Ciebie; udana włącza rutyny")
    k.add_argument("--bez-rutyn", action="store_true", help="nie włączaj rutyn po udanej wiadomości")
    k.set_defaults(funkcja=polecenie_telegram_test)
    k = t.add_parser("status", help="co jest ustawione (bez wartości) i konflikt 409")
    k.add_argument("--json", action="store_true")
    k.add_argument("--sprawdz", action="store_true", help="sprawdź token w Telegramie (getMe)")
    k.set_defaults(funkcja=polecenie_telegram_status)


def main(argv: list[str] | None = None) -> int:
    """`python -m jarvo.wiedza_cli <wiedza|rutyny|telegram> …` bez reszty CLI (do czasu wpięcia w jarvo/cli.py)."""
    for strumien in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            strumien.reconfigure(errors="replace")
    p = argparse.ArgumentParser(prog="jarvo", description="Skarbiec, rutyny i Telegram (docs/NATYWNIE.md, etap E7).")
    sub = p.add_subparsers(dest="polecenie", metavar="polecenie", title="polecenia")
    sub.required = True
    dodaj_polecenia(sub)
    a = p.parse_args(argv)
    ot = instalator.Otoczenie()
    try:
        u = sciezki.uklad(ot.env)
    except sciezki.BladUkladu as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 1
    for klucz, wartosc in instalator.ustawienia(u).items():
        if not str(ot.env.get(klucz) or "").strip():
            ot.env[klucz] = wartosc
            os.environ[klucz] = wartosc
    try:
        return int(a.funkcja(u, a, [], ot) or 0)
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    sys.exit(main())
