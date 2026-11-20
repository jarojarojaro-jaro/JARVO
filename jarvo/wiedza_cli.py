"""Skarbiec, rutyny i Telegram natywnie: `jarvo wiedza`, `jarvo rutyny`, `jarvo telegram` (docs/NATYWNIE.md, etap E7:
K02, K03, K07, K08, H06, H11, decyzja I36).

  jarvo wiedza kompiluj [--na-sucho] [--limit N] [--json]
        kompilacja skrzynki (wiedza/kompilacja.py) Pythonem venvu Hermesa, w środowisku Jarva (jarvo/srodowisko.py),
        z HERMES_HOME profilu jarvo (model zadania jarvo_wiedza) i w katalogu Hermesa; bez basha (zastępuje
        scripts/wiedza-kompiluj.sh z kontenera). Jeden piszący: wiedza.Blokada (blokada systemu + znacznik
        state/wiedza.lock, który widzi też zasiew przy wdrożeniu); lint przed i po przebiegu (K02)
  jarvo wiedza lint [--json] [--strict] | indeksuj [--pelny] | status [--json]
        lint z regułami nazw przenośnych (K07), indeks FTS5 z INDEX.md i listami hubów (pod blokadą) i wektory nowych
        notatek z usługi `wektory` (po blokadzie), liczby (także wektorów i stanu usługi)
  jarvo wiedza doctor [--json]
        sprawdzenia skarbca (z wektorami: model e5-small, usługa, liczba wektorów), rutyn i Telegrama (K08), te same,
        które dostaje `jarvo doctor`
  jarvo rutyny [status|on|off] [--json]
        rutyny Jarva (cron Hermesa w bramie): stan z cron/jobs.json profilu jarvo, włączenie i wstrzymanie przez
        `hermes -p jarvo cron resume|pause` (H06). Po instalacji są wstrzymane; włącza je udana próbna wiadomość
        na Telegram (`jarvo telegram test`, I36), a `jarvo rutyny off` wyłącza je na stałe, aż `jarvo rutyny on`
  jarvo telegram ustaw [--wlasciciel ID] [--grupa ID] [--token-ze-stdin] [--bez-wdrozenia] [--bez-sprawdzenia]
        token bota, lista dozwolonych i kanał domowy bramy (TELEGRAM_HOME_CHANNEL = dom Jarva) do `<dane>/.env`
        (wartości nigdy na ekran ani do logu), trasy z pliku Jarva `<dane>/jarvo/konfig/jarvo.env` (TELEGRAM_OWNER_ID:
        DM → Jarvo, TELEGRAM_HQ_CHAT_ID); potem wdrożenie floty (jarvo/flota.py: trasy w configu bramy, rutyny do domu
        Jarva) i restart bramy przez nadzorcę.
        ID właściciela: --wlasciciel albo z pierwszej wiadomości do bota (getUpdates, gdy nikt inny bota nie czyta)
  jarvo telegram test [--bez-rutyn] | status [--json] [--sprawdz] | wyslij [--czat ID] [--watek ID]
        próbna wiadomość do domu Jarva (udana włącza rutyny, I36) / układ grupy i tematów, dom Jarva, co jest ustawione
        (bez wartości) i konflikt 409 w logach bramy (dwie bramy na jednym tokenie, H11) / tekst z wejścia do domu
        Jarva albo do wątku grupy, długi w kilku wiadomościach (odpowiedzi sesji zewnętrznych ze skrzynki „<dopisek>”,
        sesje/plugin/__init__.py). Dom Jarva (17.11): temat General „JARVO” grupy Jarvo HQ, bez grupy DM właściciela;
        DM to wejście zapasowe (Jarvo odpowiada tam na Twoje wiadomości, sam nic tam nie wysyła)
  jarvo telegram tematy [--grupa ID] [--bez-wdrozenia] [--usun-zbedne]
        grupa „Jarvo HQ” z tematami: grupa z --grupa albo z wiadomości właściciela (wtyczka jarvo-sesje zapisuje ją
        w state/telegram-grupy.json), wątek na każdego aktywnego agenta z telegram_topic (Jarvo: General) i na sesję
        zewnętrzną z sesje.json (Kernel); brakujące zakłada createForumTopic, nazwy tematów wielkimi literami
        (General → „JARVO” przez editGeneralForumTopic, JARODEV, KERNEL; powtórka niczego nie zmienia), potem
        TELEGRAM_HQ_CHAT_ID i TELEGRAM_TOPIC_* do jarvo.env, czat i wątek sesji do sesje.json, kanał domowy bramy na
        grupę (dom Jarva) i wdrożenie tras jak w `ustaw`

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
import sqlite3
import subprocess
import sys
import time
import unicodedata
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
    """Błąd Bot API: kod HTTP albo z odpowiedzi (0 = brak sieci) i opis bez tokenu; `nowy_czat` = ID supergrupy
    z `parameters.migrate_to_chat_id` (grupa przeniesiona po włączeniu tematów), inaczej pusty."""

    def __init__(self, kod: int, opis: str, nowy_czat: str = ""):
        super().__init__(opis)
        self.kod = kod
        self.nowy_czat = nowy_czat


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


def archiwizuj_briefy(u: Uklad) -> list[str]:
    """Brakujące notatki `briefy/` z wysłanych porannych briefów i przeglądów tygodnia (skrypt profilu `briefy.py`,
    0 tokenów; nadzorca co minutę). Zwraca nowe numery. Plik zmieniony po aktualizacji ładuje się od nowa."""
    plik = profil(u) / "scripts" / "briefy.py"
    if not (plik.is_file() and skarbiec(u).is_dir()):
        return []
    znacznik = (str(plik.resolve()), plik.stat().st_mtime_ns)
    mod = sys.modules.get("jarvo_briefy")
    if mod is None or getattr(mod, "_jarvo_znacznik", None) != znacznik:
        spec = importlib.util.spec_from_file_location("jarvo_briefy", plik)
        if spec is None or spec.loader is None:
            return []
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod._jarvo_znacznik = znacznik
        sys.modules["jarvo_briefy"] = mod
    return list(mod.synchronizuj(skarbiec(u), profil(u) / "cron" / "output"))


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


def pora_kompilacji(u: Uklad, teraz: float | None = None) -> bool:
    """Czy nadzorca ma puścić kompilację skarbca: Jarvo zainstalowane z Hermesem i profilem jarvo (model kompilacji),
    skarbiec jest, a wiedza.pora_kompilacji (szkice odstane 5 min albo najstarszy 15 min, noc 03:10, przerwa po
    awarii modelu) mówi „tak”. Bez szkiców nic nie czyta poza katalogiem skrzynki."""
    if not (skarbiec(u).is_dir() and profil(u).is_dir() and _zainstalowane(u) and _python_hermesa(u)):
        return False
    return bool(wiedza_lib(_app(u)).pora_kompilacji(skarbiec(u), stan_skarbca(u),
                                                    time.time() if teraz is None else teraz))


def opis_kompilacji(u: Uklad, kod: int) -> str:
    """Jedna linia do dziennika nadzorcy o skończonym przebiegu kompilacja.py (bez --json): kod 1 = skarbiec zajęty,
    2 = brak modelu, 0 = raport z state/wiedza-kompilacja.json."""
    if kod == 1:
        return "skarbiec zajęty (inny przebieg albo zasiew), następna próba za minutę"
    if kod:
        return f"nieudana (kod {kod}); szczegóły: jarvo wiedza kompiluj"
    r = (_json(stan_skarbca(u) / "wiedza-kompilacja.json") or {}).get("raport") or {}
    return (f"{r.get('szkice', 0)} szkiców → {r.get('nowe', 0)} nowych, {r.get('aktualizacje', 0)} aktualizacji, "
            f"{r.get('sprzeczne', 0)} sprzecznych, {r.get('odrzucone', 0)} odrzuconych, {r.get('bledy', 0)} błędów"
            + (f"; przerwana: {r['przerwana']}" if r.get("przerwana") else ""))


def _na_pierwszym_planie(argv: list[str], env: dict, cwd: Path | None) -> int:
    """Proces w tym terminalu (wyjście wprost na ekran), bez okna na Windows."""
    return subprocess.call(argv, env=env, cwd=str(cwd) if cwd else None, stdin=subprocess.DEVNULL,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if not sys.stdout.isatty() else 0)


def polecenie_wiedza_kompiluj(u: Uklad, a, _reszta, ot, *, uruchom: Callable | None = None) -> int:
    if not _zainstalowane(u):
        return _brak_instalacji(u)
    obcy = getattr(a, "skarbiec", "")
    if obcy and Path(obcy).resolve() != skarbiec(u).resolve():
        print(f"`jarvo wiedza kompiluj` kompiluje tylko skarbiec Jarva ({skarbiec(u)}), a nie {obcy}. Inny skarbiec: "
              "kompilacja.py --skarbiec … Pythonem z venvu Hermesa (HERMES_HOME z modelem jarvo_wiedza) albo --na-sucho. "
              "Nic nie zmieniłem.", file=sys.stderr)
        return 2
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


def polecenie_wiedza_porzadki(u: Uklad, a, _reszta, _ot) -> int:
    """`jarvo wiedza archiwizuj|przenies|streszczenie|pamiec`: to samo co `wiedza.py` tej wersji Jarva na skarbcu tej
    instalacji (blokada, punkt zapisu, LOG, indeks i huby robi wiedza.porzadki; pamięć: profil Jarva tej instalacji)."""
    if not skarbiec(u).is_dir():
        print(f"Brak skarbca {skarbiec(u)} (zasiew robi instalacja floty).", file=sys.stderr)
        return 1
    lib = wiedza_lib(_app(u))
    argv = ["--skarbiec", str(skarbiec(u)), "--stan", str(stan_skarbca(u)), a.wiedza_polecenie]
    if a.wiedza_polecenie == "archiwizuj":
        argv += [*a.sciezki, "--powod", a.powod] + (["--zastapiona-przez", a.zastapiona_przez] if a.zastapiona_przez else [])
    elif a.wiedza_polecenie == "przenies":
        argv += [a.sciezka, a.folder]
    elif a.wiedza_polecenie == "streszczenie":
        argv += [a.hub, *(["--plik", a.plik] if a.plik else ["--tekst", a.tekst])]
    else:
        argv += ["--profil", str(profil(u))]
    return lib.main(argv)


def polecenie_wiedza_indeksuj(u: Uklad, a, _reszta, _ot) -> int:
    """Indeks FTS5, INDEX.md i listy w hubach (bloki GEN w notatkach), więc pod blokadą jednego piszącego; potem,
    już bez blokady (to tylko state/wiedza.db), wektory nowych i zmienionych notatek z usługi `wektory`."""
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
          f"INDEX.md: {n} notatek, huby odświeżone: {h}", flush=True)
    ix = lib.Indeks(sk)
    try:
        print(lib.opis_wektorow(ix.odswiez_wektory(lib.KlientWektorow(sk.stan, lib.WEKTORY_CZAS_ZAPISU_S))))
    finally:
        ix.zamknij()
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
    wek = r.get("wektory") or {}
    print(f"Wektory: {wek.get('wektorow', 0)}/{wek.get('notatek', 0)} notatek · usługa: "
          + (f"działa ({wek.get('model')})" if wek.get("usluga") else "nie działa (przypomnienia słowami)"))
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
                      "Kompilację odpala brama (przy szkicach odstanych 5 min albo najstarszym 15 min i co noc o 03:10, po uśpieniu nadrabia): "
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


def _liczby_wektorow(stan: Path, model: str, poza: tuple[str, ...]) -> tuple[int, int]:
    """(wektorów modelu `model`, notatek w wyszukiwaniu) z state/wiedza.db, tylko do odczytu; (0, 0) bez bazy. `poza`:
    foldery bez wektorów (wiedza.POZA_WYSZUKIWANIEM: źródła, szkice, archiwum)."""
    try:
        db = sqlite3.connect((stan / "wiedza.db").as_uri() + "?mode=ro", uri=True, timeout=2)
    except sqlite3.Error:
        return 0, 0
    try:
        notatek = sum(1 for (s,) in db.execute("SELECT sciezka FROM pliki") if not s.startswith(poza))
        wektorow = db.execute("SELECT count(*) FROM wektory WHERE model = ?", (model,)).fetchone()[0] if model else 0
        return wektorow, notatek
    except sqlite3.Error:                                # indeks sprzed wektorów albo pusty
        return 0, 0
    finally:
        db.close()


def sprawdz_wektory(u: Uklad, ot) -> dict:
    """Model e5-small (narzedzia.json), usługa `wektory` nadzorcy (stan i /zdrowie z tokenem ze state/wektory.json)
    i wektory notatek w indeksie. Bez nich przypomnienia działają słowami, więc najwyżej uwaga."""
    nazwa = "wektory skarbca"
    narz = srodowisko.narzedzia(u)
    model = narz.get("model-e5-small") or {}
    if not model.get("katalog") or not Path(str(model["katalog"])).is_dir():
        return _wynik(nazwa, "uwaga", "model e5-small nie jest zainstalowany: przypomnienia skarbca szukają słowami",
                      "Uruchom instalację jeszcze raz (polecenie z README) albo jarvo update.")
    if not (narz.get("venv-narzedzia") or {}).get("python"):
        return _wynik(nazwa, "uwaga", "brak venvu narzędzi: usługa wektorów nie ma czym działać",
                      "Uruchom instalację jeszcze raz (polecenie z README).")
    stan, powod = instalator.stan_serwisu(u, ot)
    usluga = instalator.usluga_nadzorcy(stan, "wektory")
    if stan is None:
        return _wynik(nazwa, "uwaga", f"serwis nie działa ({powod or 'brak nadzorcy'}): przypomnienia szukają słowami",
                      "jarvo up")
    if not usluga:
        return _wynik(nazwa, "uwaga", "nadzorca nie prowadzi usługi wektorów (serwis sprzed tej wersji)",
                      "jarvo down, potem jarvo up")
    lib = wiedza_lib(_app(u))
    klient = lib.KlientWektorow(stan_skarbca(u), 2.0)
    zdrowie = klient.zdrowie() if klient.dostepny else None
    if usluga.get("stan") != "dziala" or zdrowie is None:
        opis = f"usługa {usluga.get('stan') or 'nie działa'}" + (f" ({usluga['powod']})" if usluga.get("powod") else "")
        return _wynik(nazwa, "uwaga", f"{opis}; {klient.blad or 'brak odpowiedzi'}: przypomnienia szukają słowami",
                      "jarvo logs wektory; jarvo status")
    wektorow, notatek = _liczby_wektorow(stan_skarbca(u), klient.model, lib.POZA_WYSZUKIWANIEM)
    opis = f"{klient.model}, usługa działa (PID {zdrowie.get('pid')}), wektory: {wektorow}/{notatek} notatek"
    if wektorow < notatek:
        return _wynik(nazwa, "uwaga", opis + " (część notatek szukana tylko słowami)",
                      "jarvo wiedza indeksuj (osadza brakujące; robi to też każda kompilacja i start usługi)")
    return _wynik(nazwa, "ok", opis)


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
        dom = dom_jarva(k)
        if dom and (k["dom"] != dom or k["dom_watek"]):
            wyniki.append(_wynik("Telegram: dom Jarva", "uwaga",
                                 "kanał domowy bramy (TELEGRAM_HOME_CHANNEL) to nie " + opis_domu(dom),
                                 "Powiadomienia bramy i rutyny z `deliver: telegram` idą gdzie indziej: jarvo telegram "
                                 + ("tematy" if k["grupa"] else "ustaw") + " (samo zrestartuje bramę)."))
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
    """Wyniki dla `jarvo doctor` (K08): skarbiec (poza chmurą, FTS5 Hermesa, git, długie ścieżki, kompilacja, lint,
    wektory: model, usługa i liczba wektorów), brama, rutyny i Telegram (konfiguracja, 409). Nic nie zapisuje."""
    ot = ot or instalator.Otoczenie()
    wyniki = [sprawdz_skarbiec(u, ot.env), sprawdz_fts5_hermesa(u), sprawdz_git_skarbca(u, ot)]
    dlugie = sprawdz_dlugie_sciezki(u)
    if dlugie:
        wyniki.append(dlugie)
    wyniki += [sprawdz_kompilacje(u), sprawdz_lint(u), sprawdz_wektory(u, ot), sprawdz_brame(u, ot), *sprawdz_rutyny(u, ot),
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


def zapisz_env(p: Path, zmiany: dict[str, str | None]) -> list[str]:
    """Scala `zmiany` z plikiem .env (inne linie i komentarze zostają), zapis atomowy z LF, plik tylko dla właściciela
    (POSIX 0600, Windows ACL); wartość None usuwa klucz. Zwraca nazwy zmienionych kluczy; wartości nigdzie nie wypisujemy."""
    try:
        linie = p.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        linie = []
    stare = czytaj_env(p)
    zmienione = [k for k, v in zmiany.items() if (k in stare if v is None else stare.get(k) != v)]
    if not zmienione and p.exists():
        return []
    widziane = set()
    for i, linia in enumerate(linie):
        m = LINIA_ENV.match(linia)
        if m and not linia.lstrip().startswith("#") and m.group(1) in zmiany:
            if m.group(1) in widziane or zmiany[m.group(1)] is None:
                linie[i] = None            # klucz do usunięcia albo druga linia z tym samym kluczem: zostaje jedna
                continue
            linie[i] = f"{m.group(1)}={zmiany[m.group(1)]}"
            widziane.add(m.group(1))
    linie = [x for x in linie if x is not None] + [f"{k}={v}" for k, v in zmiany.items()
                                                   if k not in widziane and v is not None]
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
            "dom": (env.get("TELEGRAM_HOME_CHANNEL") or "").strip(),
            "dom_watek": (env.get("TELEGRAM_HOME_CHANNEL_THREAD_ID") or "").strip()}


def dom_jarva(k: dict) -> str:
    """Dom Jarva: czat wszystkiego, co Jarvo wysyła sam (rutyny, karty kanbana, próbna wiadomość, `wyslij` bez --czat;
    decyzja 17.11): grupa Jarvo HQ, czyli jej temat General „JARVO” (wiadomość bez wątku), a bez grupy DM właściciela.
    DM zostaje wejściem zapasowym: Jarvo odpowiada tam na Twoje wiadomości, ale sam do niego nie pisze."""
    return k["grupa"] or k["wlasciciel"] or (k["dozwoleni"][0] if k["dozwoleni"] else "")


def zmiany_domu(dom: str) -> dict[str, str | None]:
    """Kanał domowy bramy w `<dane>/.env` (Hermes: TELEGRAM_HOME_CHANNEL, cel `deliver: telegram`, powiadomień bramy
    i kart; wątek pusty = General, bo sendMessage z message_thread_id=1 Telegram odrzuca)."""
    return {"TELEGRAM_HOME_CHANNEL": dom, "TELEGRAM_HOME_CHANNEL_THREAD_ID": None} if dom else {}


def opis_domu(dom: str) -> str:
    return (f"grupa Jarvo HQ {dom}, temat General „{NAZWA_OGOLNEGO}”" if dom.startswith("-")
            else f"DM {dom} (bez grupy: jarvo telegram tematy)" if dom else "brak")


def cel_rutyn(u: Uklad, dom: str) -> str:
    """`deliver` rutyn Jarva przy domu `dom` (jak ROUTINE_DELIVER w scripts/build.py): grupa = jej General jako wątek 1
    (cel bez wątku z attach_to_session zakłada co przebieg temat „Hermes — <rutyna>”) i kopia w temacie UPDATES,
    gdy jarvo.env go ma; DM = sam czat."""
    if not dom.startswith("-"):
        return f"telegram:{dom}"
    env = czytaj_env(konfig(u) / "jarvo.env")
    aktualizacje = (env.get(f"TELEGRAM_TOPIC_{NAZWA_AKTUALIZACJI}") or "").strip()
    ta_grupa = (env.get("TELEGRAM_HQ_CHAT_ID") or "").strip() == dom
    return f"telegram:{dom}:{WATEK_OGOLNY}" + (f",telegram:{dom}:{aktualizacje}" if aktualizacje and ta_grupa else "")


def rutyny_do_domu(u: Uklad, dom: str) -> bool:
    """Czy rutyny Jarva dostarczają do jego domu (`deliver` ustawia build przy wdrożeniu floty, ROUTINE_DELIVER);
    bez zainstalowanych rutyn nie ma czego wdrażać."""
    rutyny = stan_rutyn(u)
    cel = cel_rutyn(u, dom)
    return not rutyny["zainstalowane"] or all(str(r.get("deliver")) == cel for r in rutyny["lista"] if r.get("jest"))


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
        nowy = str((odp.get("parameters") or {}).get("migrate_to_chat_id") or "") if isinstance(odp.get("parameters"), dict) else ""
        raise BladTelegrama(int(odp.get("error_code") or 0), _bez_tokenu(str(odp.get("description") or "błąd API"), token),
                            nowy)
    return odp.get("result")


def rada_telegrama(e: BladTelegrama, grupa: bool = False) -> str:
    """Rada po polsku do błędu Bot API; `grupa` = wołanie dotyczyło grupy Jarvo HQ (tematy, wysyłka do wątku)."""
    opis = str(e).lower()
    if e.kod == 401:
        return "Telegram nie zna tego tokenu: skopiuj go jeszcze raz z @BotFather (/token) i uruchom jarvo telegram ustaw."
    if e.kod == 409:
        return ("Ten bot jest już czytany przez inny program (409): stara flota Jarva z Dockerem/WSL, prywatny Hermes "
                "albo OpenClaw z tym tokenem. Wyłącz go albo załóż nowego bota w @BotFather.")
    if "not a forum" in opis:
        return ("W tej grupie tematy są wyłączone: w Telegramie otwórz grupę → Edytuj → Tematy (Topics) → włącz, "
                "napisz w niej „start” i uruchom jarvo telegram tematy jeszcze raz.")
    if "upgraded to a supergroup" in opis or "migrate" in opis:
        return ("Grupa dostała nowe ID (-100…) po włączeniu tematów: napisz w niej „start” i uruchom jarvo telegram "
                "tematy bez --grupa.")
    if "not enough rights" in opis or ("rights" in opis and "topic" in opis) or "chat_admin_required" in opis:
        return ("Bot nie ma uprawnień do tematów: w grupie Jarvo HQ zrób go administratorem z prawem „Zarządzanie "
                "tematami” (Manage topics) i uruchom polecenie jeszcze raz.")
    if "thread not found" in opis or "topic_id_invalid" in opis or "topic_deleted" in opis:
        return "Tego wątku już nie ma (usunięty?): uruchom jarvo telegram tematy, założę brakujące od nowa."
    if grupa and (e.kod == 403 or e.kod == 400 and "chat not found" in opis):
        return ("Bota nie ma w tej grupie (albo ID grupy jest złe): dodaj go do Jarvo HQ jako administratora z prawem "
                "„Zarządzanie tematami”, napisz w grupie „start” i spróbuj ponownie.")
    if e.kod == 403:
        return "Bot nie może do Ciebie pisać (zablokowany?): odblokuj go w Telegramie i napisz do niego /start."
    if e.kod == 400 and "chat not found" in opis:
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
    wynik["serwis_dziala"] = stan is not None
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
    instalator.czekaj_na_tury(u)
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
    dom = dom_jarva({**k, "grupa": a.grupa or k["grupa"], "wlasciciel": wlasciciel})
    zmiany = {"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_ALLOWED_USERS": ",".join(dict.fromkeys([*dozwoleni, wlasciciel])),
              **zmiany_domu(dom)}
    zmienione = zapisz_env(u.dane / ".env", zmiany)
    if (konfig(u) / "host.env").is_file():        # źródło sekretów przy wdrożeniu (merge_env): to samo, żeby nie cofnęło
        zapisz_env(konfig(u) / "host.env", zmiany)
    trasy = {"TELEGRAM_OWNER_ID": wlasciciel, **({"TELEGRAM_HQ_CHAT_ID": a.grupa} if a.grupa else {})}
    zmienione_trasy = zapisz_env(konfig(u) / "jarvo.env", trasy)
    print(f"Zapisane w {u.dane / '.env'} (wartości nie pokazuję): {', '.join(zmienione) or 'bez zmian'}.")
    print(f"Trasy w {konfig(u) / 'jarvo.env'}: DM → Jarvo (ID {wlasciciel})"
          + (f", grupa Jarvo HQ {a.grupa}" if a.grupa else "") + ("" if zmienione_trasy else " (bez zmian)") + ".")
    print("Dom Jarva (rutyny, karty, próbna wiadomość): " + opis_domu(dom) + ".")
    wdrozenie = bool(zmienione_trasy) or not rutyny_do_domu(u, dom)
    if not (zmienione or wdrozenie):
        print("Nic się nie zmieniło: wdrożenie i restart bramy niepotrzebne.")
    elif wdroz_trasy(u, ot, zmienione_bramy=bool(zmienione), wdrozenie=wdrozenie, bez_wdrozenia=a.bez_wdrozenia,
                     token=token):
        return 1
    print("Teraz próbna wiadomość: jarvo telegram test (po udanej rutyny Jarva się włączą).")
    return 0


def wdroz_trasy(u: Uklad, ot, *, zmienione_bramy: bool, wdrozenie: bool, bez_wdrozenia: bool, token: str = "") -> int:
    """Po zmianie ustawień Telegrama: wdrożenie floty (trasy w configu bramy, rutyny na Telegram) i restart bramy,
    gdy zmienił się jej `.env`. Bez wdrożenia (albo bez floty) tylko restart i informacja. 1 = wdrożenie nie wyszło."""
    if bez_wdrozenia or not (profil(u) / "distribution.yaml").is_file():
        if zmienione_bramy and restart_bramy(u, ot):
            print("Brama uruchamia się ponownie z nowym tokenem.")
        if wdrozenie:
            print("Trasy i dostarczanie rutyn na Telegram wejdą przy następnym wdrożeniu floty (jarvo instaluj).")
        return 0
    print("Wdrażam flotę z nowymi trasami (build i instalacja, zwykle około minuty)…", flush=True)
    try:
        wynik = wdroz_flote(u, ot, log=lambda s: None)
    except Exception as e:                   # noqa: BLE001 - wdrożenie można powtórzyć; ustawienia już są
        print(f"BŁĄD wdrożenia floty: {_bez_tokenu(str(e), token)}\nUstawienia są zapisane; powtórz: jarvo instaluj.",
              file=sys.stderr)
        return 1
    restarty = wynik.get("zrestartowane") or []
    if "brama" not in restarty and zmienione_bramy and restart_bramy(u, ot):
        restarty.append("brama")
    print("Flota wdrożona" + (f"; restart: {', '.join(restarty)}" if restarty else
                              "; bez restartu: w działających usługach nic się nie zmieniło" if wynik.get("serwis_dziala")
                              else "; serwis nie działa: zmiany wejdą przy jarvo up") + ".")
    return 0


# -- grupa „Jarvo HQ” z tematami: wątek na agenta (14.11)

PLIK_GRUP = "telegram-grupy.json"          # w stanie Jarva; pisze go wtyczka jarvo-sesje (zapamietaj_grupe)
WATEK_OGOLNY = "1"                         # temat General forum: trasa całej grupy (Jarvo), bez TELEGRAM_TOPIC_*
# nazwy tematów w grupie: krótka nazwa wielkimi literami (17.11: JARVO w General, JARODEV, KERNEL)
NAZWA_OGOLNEGO = "JARVO"
# temat archiwum raportów rutyn (18.11): kopia każdego raportu (build.py ROUTINE_DELIVER), panel: kanał Aktualizacje
NAZWA_AKTUALIZACJI = "UPDATES"
ID_GRUPY_RE = re.compile(r"^-\d{3,20}$")
ID_WATKU_RE = re.compile(r"^\d{1,12}$")


def _klucz_tematu(tekst: str) -> str:
    """Część nazwy TELEGRAM_TOPIC_<KLUCZ> dla sesji zewnętrznej: litery i cyfry ASCII wielkimi (Kernel → KERNEL)."""
    ascii_ = unicodedata.normalize("NFKD", tekst).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Z0-9]+", "_", ascii_.upper()).strip("_")


def _porownywalna(nazwa: str) -> str:
    return re.sub(r"[\W_]+", "", str(nazwa or "").casefold())


def grupy_telegrama(u: Uklad) -> dict:
    """Grupy i wątki z wiadomości właściciela (wtyczka jarvo-sesje): {"-100…": {"nazwa", "forum", "watki"}}."""
    grupy = _json(stan_skarbca(u) / PLIK_GRUP).get("grupy")
    return {str(k): v for k, v in grupy.items() if isinstance(v, dict)} if isinstance(grupy, dict) else {}


def wybierz_grupe(u: Uklad, podana: str | None) -> tuple[str | None, str]:
    """(ID grupy, komunikat błędu): --grupa, jedyna zapisana grupa z tematami, TELEGRAM_HQ_CHAT_ID, jedyna grupa."""
    if podana:
        podana = podana.strip()
        return (podana, "") if ID_GRUPY_RE.match(podana) else (None, "ID grupy Jarvo HQ zaczyna się od „-100…”.")
    grupy = grupy_telegrama(u)
    fora = [g for g, w in grupy.items() if w.get("forum")]
    zapisana = konfiguracja_telegrama(u)["grupa"]
    if len(fora) == 1:
        return fora[0], ""
    if zapisana:
        return zapisana, ""
    if len(grupy) == 1:
        return next(iter(grupy)), ""
    if not grupy:
        return None, ("Nie znam jeszcze grupy Jarvo HQ: dodaj bota do grupy jako administratora, napisz w niej „start” "
                      "(bot zapisze jej ID) albo podaj --grupa -100….")
    lista = "; ".join(f"{g} „{w.get('nazwa') or '?'}”" + (" (tematy)" if w.get("forum") else "") for g, w in grupy.items())
    return None, f"Bot zna kilka grup: {lista}. Wybierz jedną: jarvo telegram tematy --grupa <ID>."


def nowy_numer_grupy(token: str, grupa: str) -> str:
    """ID supergrupy, gdy zwykła grupa `grupa` została przeniesiona (włączenie tematów zmienia ją w supergrupę z nowym
    ID -100…, a getChat pod starym ID dalej mówi „bez tematów”: 15.11 właściciel włączył tematy, bot znał stary numer).
    Telegram podaje nowy numer tylko w błędzie wysyłki, więc pytamy wskaźnikiem „pisze…” (bez wiadomości w grupie).
    "" = grupa nieprzeniesiona albo już supergrupa."""
    if grupa.startswith("-100"):
        return ""
    try:
        api_telegrama(token, "sendChatAction", {"chat_id": grupa, "action": "typing"})
    except BladTelegrama as e:
        return e.nowy_czat if ID_GRUPY_RE.match(e.nowy_czat) else ""
    return ""


def tytul_tematu(nazwa: str) -> str:
    """Nazwa tematu w Telegramie (do 128 znaków): krótka nazwa agenta albo sesji wielkimi literami."""
    return str(nazwa).strip().upper()[:128]


def tematy_do_zalozenia(u: Uklad, sesje: dict) -> list[dict]:
    """Wątki grupy: aktywni agenci floty z `telegram_topic` (zbudowana flota, <build>/wiedza/fleet.json; „general” =
    temat General, bez zakładania), sesje zewnętrzne ze skrzynką z sesje.json (Kernel) i temat UPDATES (archiwum
    raportów rutyn, bez rozmówcy). `tytul` = nazwa tematu, `kto` = opis dla `jarvo telegram status`."""
    wynik = []
    for a in _json(u.build / "wiedza" / "fleet.json").get("agents") or []:
        temat = str((a or {}).get("telegram_topic") or "").strip() if isinstance(a, dict) else ""
        if temat and temat != "general" and a.get("name"):
            nazwa = str(a.get("short") or a.get("title") or a["name"])
            wynik.append({"klucz": temat.upper(), "nazwa": nazwa, "tytul": tytul_tematu(nazwa), "temat": temat,
                          "sesja": None, "profil": str(a["name"]), "kto": f"agent {a['name']}"})
    for dopisek, w in sesje.items():
        if isinstance(w, dict) and w.get("skrzynka"):
            nazwa = str(w.get("nazwa") or dopisek)
            wynik.append({"klucz": _klucz_tematu(nazwa) or _klucz_tematu(dopisek), "nazwa": nazwa,
                          "tytul": tytul_tematu(nazwa), "temat": dopisek, "sesja": dopisek, "profil": None,
                          "kto": f"sesja {nazwa} (skrzynka)"})
    wynik.append({"klucz": NAZWA_AKTUALIZACJI, "nazwa": NAZWA_AKTUALIZACJI, "tytul": NAZWA_AKTUALIZACJI,
                  "temat": NAZWA_AKTUALIZACJI.lower(), "sesja": None, "profil": None,
                  "kto": "archiwum raportów rutyn (kopia; rozmowa z Jarvem zostaje w JARVO)"})
    return wynik


def _bez_zmian(e: BladTelegrama) -> bool:
    """Nazwa tematu już taka sama (MTProto TOPIC_NOT_MODIFIED w opisie Bot API): zmiana nazwy jest powtarzalna."""
    return "not_modified" in str(e).lower() or "not modified" in str(e).lower()


def nazwij_temat(token: str, grupa: str, watek: str, tytul: str) -> str:
    """Nazwa tematu: General przez editGeneralForumTopic, inne przez editForumTopic. "zmieniona" / "bez zmian";
    BladTelegrama (np. brak prawa „Zarządzanie tematami”) idzie dalej."""
    try:
        if watek == WATEK_OGOLNY:
            api_telegrama(token, "editGeneralForumTopic", {"chat_id": grupa, "name": tytul})
        else:
            api_telegrama(token, "editForumTopic", {"chat_id": grupa, "message_thread_id": int(watek), "name": tytul})
    except BladTelegrama as e:
        if _bez_zmian(e):
            return "bez zmian"
        raise
    return "zmieniona"


def _zly_watek(e: BladTelegrama) -> bool:
    opis = str(e).lower()
    return "thread not found" in opis or "topic_id_invalid" in opis or "topic_deleted" in opis


def polecenie_telegram_tematy(u: Uklad, a, _reszta, ot) -> int:
    """Tematy grupy Jarvo HQ: wątek na agenta i na sesję zewnętrzną (brakujące zakłada createForumTopic, istniejące
    bierze z jarvo.env, sesje.json albo po nazwie z wiadomości właściciela), potem TELEGRAM_HQ_CHAT_ID i
    TELEGRAM_TOPIC_* do jarvo.env, wątek sesji do sesje.json i wdrożenie tras jak `jarvo telegram ustaw`."""
    if not _zainstalowane(u):
        return _brak_instalacji(u)
    token = _token(u)
    if not token:
        print("Bot nie jest ustawiony: najpierw jarvo telegram ustaw.", file=sys.stderr)
        return 1
    grupa, blad = wybierz_grupe(u, a.grupa)
    if not grupa:
        print(f"{blad} Nic nie zmieniłem.", file=sys.stderr)
        return 2
    plik_sesji = konfig(u) / "sesje.json"
    sesje = _json(plik_sesji)
    tematy = tematy_do_zalozenia(u, sesje)
    if not _json(u.build / "wiedza" / "fleet.json").get("agents"):   # bez agentów biznesowych wątek ma tylko Kernel
        print("Nie widzę zbudowanej floty (<build>/wiedza/fleet.json): najpierw jarvo instaluj.", file=sys.stderr)
        return 1
    try:
        czat = api_telegrama(token, "getChat", {"chat_id": grupa}) or {}
        nowa = "" if czat.get("is_forum") else nowy_numer_grupy(token, grupa)
        if nowa:
            print(f"Grupa {grupa} dostała nowy numer {nowa} po włączeniu tematów: biorę nowy.")
            grupa = nowa
            czat = api_telegrama(token, "getChat", {"chat_id": grupa}) or {}
        if not czat.get("is_forum"):
            raise BladTelegrama(400, "Bad Request: the chat is not a forum")
        ja = api_telegrama(token, "getMe") or {}
        rola = api_telegrama(token, "getChatMember", {"chat_id": grupa, "user_id": ja.get("id")}) or {}
    except BladTelegrama as e:
        print(f"BŁĄD: grupa {grupa}: {e}. {rada_telegrama(e, grupa=True)} Nic nie zmieniłem.", file=sys.stderr)
        return 1
    print(f"Grupa Jarvo HQ: {czat.get('title') or grupa} ({grupa}).")
    if rola.get("status") not in ("administrator", "creator"):
        print("UWAGA: bot nie jest administratorem grupy: bez tego nie widzi wiadomości bez @wzmianki (tryb "
              "prywatności) i nie założy tematów. Zrób go administratorem z prawem „Zarządzanie tematami”.")
    env = czytaj_env(konfig(u) / "jarvo.env")
    ta_sama = (env.get("TELEGRAM_HQ_CHAT_ID") or "").strip() == grupa
    nagrane = (grupy_telegrama(u).get(grupa) or {}).get("watki") or {}
    zmiany_env = {"TELEGRAM_HQ_CHAT_ID": grupa}
    wiersze, blad_tg, bledy_nazw = [], None, []
    for t in tematy:
        znane = []
        w = sesje.get(t["sesja"]) if t["sesja"] else None
        if isinstance(w, dict) and str(w.get("czat") or "") == grupa and ID_WATKU_RE.match(str(w.get("watek") or "")):
            znane.append(str(w["watek"]))
        if ta_sama and ID_WATKU_RE.match((env.get(f"TELEGRAM_TOPIC_{t['klucz']}") or "").strip()):
            znane.append(env[f"TELEGRAM_TOPIC_{t['klucz']}"].strip())
        szukane = {_porownywalna(t["nazwa"]), _porownywalna(t["temat"])}
        znane += [str(n) for n, x in nagrane.items() if isinstance(x, dict) and ID_WATKU_RE.match(str(n))
                  and str(n) != WATEK_OGOLNY and _porownywalna(x.get("nazwa", "")) in szukane]
        watek, skad = None, ""
        try:
            for kandydat in dict.fromkeys(znane):
                try:                          # czy wątek jeszcze jest: „pisze…” na chwilę w tym wątku
                    api_telegrama(token, "sendChatAction", {"chat_id": grupa, "message_thread_id": int(kandydat),
                                                             "action": "typing"})
                except BladTelegrama as e:
                    if _zly_watek(e):
                        continue
                    if "closed" not in str(e).lower():
                        raise
                    skad = " (temat zamknięty: otwórz go w Telegramie)"
                watek, skad = kandydat, "był" + skad
                break
            if watek is None:
                nowy = api_telegrama(token, "createForumTopic", {"chat_id": grupa, "name": t["tytul"]}) or {}
                watek, skad = str(nowy.get("message_thread_id") or ""), "nowy"
                if not ID_WATKU_RE.match(watek):
                    raise BladTelegrama(0, "Telegram nie podał numeru nowego wątku")
        except BladTelegrama as e:
            blad_tg = (t, e)
            break
        if skad.startswith("był"):
            try:
                if nazwij_temat(token, grupa, watek, t["tytul"]) == "zmieniona":
                    skad += f", nazwa „{t['tytul']}”"
            except BladTelegrama as e:
                bledy_nazw.append((t["tytul"], e))
        t["watek"] = watek
        zmiany_env[f"TELEGRAM_TOPIC_{t['klucz']}"] = watek
        if isinstance(w, dict):
            w.update(czat=grupa, watek=watek)
        dopisek = (", wiadomości w nim idą do skrzynki bez dopisku" if t["sesja"]
                   else ": kopia raportów rutyn (archiwum)" if t["klucz"] == NAZWA_AKTUALIZACJI else "")
        wiersze.append(f"  {t['tytul']}: wątek {watek} ({skad})" + dopisek)
    try:
        ogolny = nazwij_temat(token, grupa, WATEK_OGOLNY, NAZWA_OGOLNEGO)
    except BladTelegrama as e:
        ogolny = "nazwy nie zmieniłem"
        bledy_nazw.append((NAZWA_OGOLNEGO, e))
    print(f"  {NAZWA_OGOLNEGO}: temat General ({ogolny}): Jarvo, jego dom (rutyny, karty, powiadomienia bramy)")
    for wiersz in wiersze:
        print(wiersz)
    # wątki, których już nie ma mieć nikt (16.11: specjaliści pracują przez Jarva, bez własnych wątków): trasa z
    # jarvo.env zawsze wypada; sam wątek w Telegramie kasujemy tylko na --usun-zbedne (może mieć rozmowę właściciela)
    potrzebne = {f"TELEGRAM_TOPIC_{t['klucz']}" for t in tematy}
    for klucz in sorted(k for k in env if k.startswith("TELEGRAM_TOPIC_") and k not in potrzebne):
        zmiany_env[klucz] = None
        watek = (env.get(klucz) or "").strip()
        if not getattr(a, "usun_zbedne", False) or not ta_sama or not ID_WATKU_RE.match(watek):
            print(f"  {klucz[len('TELEGRAM_TOPIC_'):].lower()}: trasa usunięta, wątek {watek or '?'} zostaje w grupie "
                  "(usunie go --usun-zbedne)")
            continue
        try:
            api_telegrama(token, "deleteForumTopic", {"chat_id": grupa, "message_thread_id": int(watek)})
            print(f"  {klucz[len('TELEGRAM_TOPIC_'):].lower()}: wątek {watek} usunięty z grupy (agent pracuje przez Jarva)")
        except BladTelegrama as e:
            print(f"  {klucz[len('TELEGRAM_TOPIC_'):].lower()}: wątku {watek} nie usunąłem ({e}); trasa usunięta")
    zmienione = zapisz_env(konfig(u) / "jarvo.env", zmiany_env)
    if json.dumps(_json(plik_sesji), sort_keys=True) != json.dumps(sesje, sort_keys=True):
        przenosne.zapisz_atomowo(plik_sesji, json.dumps(sesje, ensure_ascii=False, indent=1) + "\n")
    print(f"Trasy w {konfig(u) / 'jarvo.env'}: " + (", ".join(zmienione) if zmienione else "bez zmian") + ".")
    # dom Jarva = ta grupa (General): kanał domowy bramy w <dane>/.env (i host.env, źródle przy wdrożeniu)
    zmienione_bramy = zapisz_env(u.dane / ".env", zmiany_domu(grupa))
    if (konfig(u) / "host.env").is_file():
        zapisz_env(konfig(u) / "host.env", zmiany_domu(grupa))
    print(f"Dom Jarva: {opis_domu(grupa)}" + (" (kanał domowy bramy ustawiony)" if zmienione_bramy else "") + ".")
    for tytul, e in bledy_nazw:
        print(f"UWAGA: nazwy tematu „{tytul}” nie zmieniłem: {e}. {rada_telegrama(e, grupa=True)}", file=sys.stderr)
    if blad_tg:
        t, e = blad_tg
        print(f"BŁĄD: temat „{t['tytul']}”: {e}. {rada_telegrama(e, grupa=True)} Zapisałem gotowe wątki; po poprawce "
              "uruchom jarvo telegram tematy jeszcze raz.", file=sys.stderr)
        return 1
    wdrozenie = bool(zmienione) or not rutyny_do_domu(u, grupa)
    if not (wdrozenie or zmienione_bramy):
        print("Wątki bez zmian: wdrożenie niepotrzebne.")
        return 1 if bledy_nazw else 0
    wynik = wdroz_trasy(u, ot, zmienione_bramy=bool(zmienione_bramy), wdrozenie=wdrozenie,
                        bez_wdrozenia=a.bez_wdrozenia, token=token)
    return wynik or (1 if bledy_nazw else 0)



def polecenie_telegram_test(u: Uklad, a, _reszta, ot, *, uruchom: Callable | None = None) -> int:
    if not _zainstalowane(u):
        return _brak_instalacji(u)
    token = _token(u)
    k = konfiguracja_telegrama(u)
    cel = dom_jarva(k)                     # grupa Jarvo HQ (General, bez wątku), bez grupy DM właściciela
    if not token or not cel:
        print("Telegram nie jest ustawiony (token i ID właściciela): jarvo telegram ustaw.", file=sys.stderr)
        return 1
    try:
        ja = api_telegrama(token, "getMe") or {}
        api_telegrama(token, "sendMessage", {"chat_id": cel, "text": "Jarvo: próbna wiadomość z Twojego komputera. "
                                                                     "Jeśli ją widzisz, Telegram działa."})
    except BladTelegrama as e:
        print(f"BŁĄD: nie wysłałem próbnej wiadomości ({e}). {rada_telegrama(e, grupa=cel.startswith('-'))}",
              file=sys.stderr)
        return 1
    bot = f"@{ja.get('username')}" if ja.get("username") else "bot"
    print(f"Próbna wiadomość wysłana przez {bot} do domu Jarva: {opis_domu(cel)}. Sprawdź Telegram.")
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


LIMIT_WIADOMOSCI = 4000                 # Telegram przyjmuje 4096 znaków; zapas na podział po liniach


def kawalki_wiadomosci(tekst: str, limit: int = LIMIT_WIADOMOSCI) -> list[str]:
    """Długi tekst → wiadomości ≤ limit, cięte po liniach (linia dłuższa niż limit: twardo)."""
    wynik, biezacy = [], ""
    for linia in tekst.splitlines(keepends=True):
        while len(linia) > limit:
            if biezacy:
                wynik.append(biezacy)
                biezacy = ""
            wynik.append(linia[:limit])
            linia = linia[limit:]
        if len(biezacy) + len(linia) > limit:
            wynik.append(biezacy)
            biezacy = ""
        biezacy += linia
    if biezacy.strip():
        wynik.append(biezacy)
    return [w.rstrip("\n") for w in wynik if w.strip()]


def polecenie_telegram_wyslij(u: Uklad, a, _reszta, _ot) -> int:
    """Tekst z wejścia do domu Jarva (zwykły tekst, długi w kilku wiadomościach): temat General grupy Jarvo HQ, bez
    grupy DM właściciela (dom_jarva); skrypty na serwerze i odpowiedzi sesji zewnętrznych (skrzynka `<dopisek>`
    z sesje/plugin/__init__.py). `--watek` (z `--czat` albo grupą Jarvo HQ z jarvo.env) pisze do wątku grupy, np.
    odpowiedź Kernela w jego wątku; `--czat <ID właściciela>` do DM. Token nigdy nie trafia na ekran."""
    if not _zainstalowane(u):
        return _brak_instalacji(u)
    czat = (getattr(a, "czat", None) or "").strip()
    watek = (getattr(a, "watek", None) or "").strip()
    if (czat and not ID_RE.match(czat)) or (watek and not ID_WATKU_RE.match(watek)):
        print("Zły --czat albo --watek (liczby; grupa: -100…).", file=sys.stderr)
        return 2
    token = _token(u)
    k = konfiguracja_telegrama(u)
    cel = czat or (k["grupa"] if watek else dom_jarva(k))
    if watek and not cel:
        print("Wątek bez grupy: podaj --czat -100… albo ustaw grupę (jarvo telegram tematy).", file=sys.stderr)
        return 1
    if not token or not cel:
        print("Telegram nie jest ustawiony (token i ID właściciela): jarvo telegram ustaw.", file=sys.stderr)
        return 1
    tekst = sys.stdin.read().strip()
    if not tekst:
        print("Pusta wiadomość: podaj tekst na wejściu.", file=sys.stderr)
        return 1
    dane = {"chat_id": cel, "disable_web_page_preview": True}
    if watek and watek != WATEK_OGOLNY:        # General: Telegram odrzuca message_thread_id=1 w sendMessage
        dane["message_thread_id"] = int(watek)
    try:
        for kawalek in kawalki_wiadomosci(tekst):
            api_telegrama(token, "sendMessage", {**dane, "text": kawalek})
    except BladTelegrama as e:
        print(f"BŁĄD: nie wysłałem wiadomości ({e}). {rada_telegrama(e, grupa=cel.startswith('-'))}", file=sys.stderr)
        return 1
    return 0


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


def uklad_grupy(u: Uklad, k: dict) -> list[dict]:
    """Tematy grupy Jarvo HQ z ustawień (bez sieci): General = Jarvo, potem wątki agentów (TELEGRAM_TOPIC_* w jarvo.env),
    sesji zewnętrznych (sesje.json) i UPDATES. {"tytul", "watek" ("1" = General, "" = brak), "kto"}."""
    if not k["grupa"]:
        return []
    env, sesje = czytaj_env(konfig(u) / "jarvo.env"), _json(konfig(u) / "sesje.json")
    wynik = [{"tytul": NAZWA_OGOLNEGO, "watek": WATEK_OGOLNY, "kto": "Jarvo (dom: rutyny, karty, powiadomienia)"}]
    for t in tematy_do_zalozenia(u, sesje):
        w = sesje.get(t["sesja"]) if t["sesja"] else None
        watek = (str(w.get("watek") or "") if isinstance(w, dict) and str(w.get("czat") or "") == k["grupa"]
                 else (env.get(f"TELEGRAM_TOPIC_{t['klucz']}") or "").strip())
        wynik.append({"tytul": t["tytul"], "watek": watek, "kto": t["kto"]})
    return wynik


def polecenie_telegram_status(u: Uklad, a, _reszta, ot) -> int:
    k = konfiguracja_telegrama(u)
    dom = dom_jarva(k)
    wynik = {**k, "dom_jarva": dom, "tematy": uklad_grupy(u, k), "test": _json(stan_skarbca(u) / "telegram.json"),
             "konflikt_409": konflikt_409(u),
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
    print(f"Dom Jarva: {opis_domu(dom)}")
    if k["grupa"]:
        print(f"Grupa Jarvo HQ {k['grupa']}, tematy (kogo wybierasz tematem):")
        for t in wynik["tematy"]:
            gdzie = "General" if t["watek"] == WATEK_OGOLNY else f"wątek {t['watek']}" if t["watek"] else \
                "brak wątku (jarvo telegram tematy)"
            print(f"  {t['tytul']} ({gdzie}): {t['kto']}")
    print(f"DM {k['wlasciciel'] or '(brak TELEGRAM_OWNER_ID)'}: "
          + ("wejście zapasowe do Jarva (odpowiedź w DM; sam do DM nie pisze), „… gpu” → Kernel"
             if k["grupa"] else "rozmowa z Jarvem i jego dom"))
    if k["token"] and dom and (k["dom"] != dom or k["dom_watek"]):
        print(f"UWAGA: kanał domowy bramy (TELEGRAM_HOME_CHANNEL w {u.dane / '.env'}) to nie dom Jarva: "
              "powiadomienia bramy i `deliver: telegram` idą gdzie indziej. Popraw: jarvo telegram "
              + ("tematy." if k["grupa"] else "ustaw."))
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
    k.add_argument("--skarbiec", default="", help="tylko sprawdzenie: inny skarbiec niż Jarva = odmowa (przekazanie z kompilacja.py)")
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
    k = w.add_parser("archiwizuj", help="notatki albo katalogi do archiwum/ (linki do następcy albo do archiwum)")
    k.add_argument("sciezki", nargs="+")
    k.add_argument("--powod", required=True)
    k.add_argument("--zastapiona-przez", default="", help="notatka-następca: linki i stara ścieżka prowadzą do niej")
    k.set_defaults(funkcja=polecenie_wiedza_porzadki)
    k = w.add_parser("przenies", help="notatka do innego folderu (ten sam tytuł), linki przepisane wszędzie")
    k.add_argument("sciezka")
    k.add_argument("folder")
    k.set_defaults(funkcja=polecenie_wiedza_porzadki)
    k = w.add_parser("streszczenie", help="blok „najważniejsze” huba (do 1500 znaków), zasiew go nie rusza")
    k.add_argument("hub", help="ścieżka huba albo folder (user, agenci/jarvo-web)")
    g = k.add_mutually_exclusive_group(required=True)
    g.add_argument("--plik")
    g.add_argument("--tekst")
    k.set_defaults(funkcja=polecenie_wiedza_porzadki)
    k = w.add_parser("pamiec", help="lustro pamięci Jarva (MEMORY.md, USER.md) w skarbcu i szkic nowych wpisów")
    k.set_defaults(funkcja=polecenie_wiedza_porzadki)
    k = w.add_parser("doctor", help="diagnoza skarbca, rutyn i Telegrama (część jarvo doctor)")
    k.add_argument("--json", action="store_true")
    k.set_defaults(funkcja=polecenie_wiedza_doctor)

    s = sub.add_parser("rutyny", help="rutyny Jarva (patrol, brief, przegląd, świeżość): status, on, off",
                       description="Rutyny Jarva działają w bramie. Po instalacji są wstrzymane; włącza je udana "
                       "próbna wiadomość (jarvo telegram test) albo `jarvo rutyny on`.")
    s.add_argument("akcja", nargs="?", choices=("status", "on", "off"), default="status", metavar="status|on|off")
    s.add_argument("--json", action="store_true")
    s.set_defaults(funkcja=polecenie_rutyny)

    s = sub.add_parser("telegram", help="bot Telegram: ustaw, test, tematy, wyslij, status",
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
    k = t.add_parser("test", help="próbna wiadomość do domu Jarva (temat JARVO grupy, bez grupy DM); udana włącza rutyny")
    k.add_argument("--bez-rutyn", action="store_true", help="nie włączaj rutyn po udanej wiadomości")
    k.set_defaults(funkcja=polecenie_telegram_test)
    k = t.add_parser("wyslij", help="tekst z wejścia do domu Jarva albo do wątku grupy (długi: kilka wiadomości)")
    k.add_argument("--czat", metavar="ID", help="czat zamiast domu Jarva (Twoje ID: DM; grupa: -100…)")
    k.add_argument("--watek", metavar="ID", help="wątek grupy (bez --czat: grupa Jarvo HQ z jarvo.env)")
    k.set_defaults(funkcja=polecenie_telegram_wyslij)
    k = t.add_parser("tematy", help="tematy grupy Jarvo HQ: JARVO (General, dom Jarva), agenci biznesowi, KERNEL; "
                     "nazwy, trasy, kanał domowy bramy i wdrożenie floty")
    k.add_argument("--grupa", metavar="ID", help="ID supergrupy Jarvo HQ (-100…); bez niego: grupa, w której pisałeś")
    k.add_argument("--bez-wdrozenia", action="store_true", help="tylko zapis wątków (trasy przy następnym wdrożeniu)")
    k.add_argument("--usun-zbedne", action="store_true",
                   help="usuń z grupy wątki agentów, którzy nie mają już wątku (trasy wypadają zawsze)")
    k.set_defaults(funkcja=polecenie_telegram_tematy)
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
