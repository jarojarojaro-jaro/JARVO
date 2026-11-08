"""Telefony właściciela dla floty przez serwer MCP PHONEUSE: `jarvo telefon on|off|status` (docs/MOBILE.md
„Telefon przez PHONEUSE”).

PHONEUSE (osobne repo właściciela) steruje telefonem z Androidem przez usługę dostępności na telefonie; jego serwer
MCP `tools/phone_mcp.py` (stdio) daje narzędzia list_phones, ping, screen, act, shot, wait i batch. Jarvo dopisuje
go jako serwer `phone` w configu dwóch profili: `jarvo-operator` dostaje wszystkie narzędzia, `jarvo` (szef) tylko
odczyt (list_phones, ping, screen, shot, wait), więc w Hermesie są `mcp__phone__screen` itd. Bez `jarvo telefon on`
w żadnym configu nie ma wpisu `phone` (repo go nie zawiera).

  jarvo telefon on --phoneuse KATALOG [--python PYTHON] [--telefon NAZWA]
        serwer KATALOG/tools/phone_mcp.py, Python z MCP SDK 2.x (domyślnie ~/.phoneuse/mcp-venv, zakłada go
        `python3 KATALOG/tools/mcp_setup.py`); sprawdza oba pliki i import SDK, zapisuje <stan>/telefon.json, od razu
        ustawia wpis w zainstalowanych profilach (ten sam kod co install_fleet.ustaw_klucze_profilu) i restartuje
        bramę, gdy żadna karta kanbana nie jest w toku
  jarvo telefon off
        wlaczony=false w <stan>/telefon.json i mcp_servers.phone.enabled: false w zainstalowanych profilach (ta sama
        zasada restartu); następna instalacja albo `jarvo update` nie dopisze już wpisu
  jarvo telefon status [--json]
        stan, pliki, SDK, adb, wpis w zainstalowanych profilach

Wpis przeżywa `jarvo update`: `flota.ustawienia_profili` bierze go z `klucze_profili` (jeden wzór, ten moduł), a
install_fleet.py ustawia go w tym samym przebiegu co `profile update --force-config`. `env` serwera: ADB = adb
z platform-tools Jarva (jarvo/android.py), żeby działał jeden serwer adb jednej wersji; PHONEUSE_PHONE = --telefon.
`trust: full`, bo narzędzia PHONEUSE nie mają readOnlyHint: przy `untrusted` każde wywołanie czekałoby na zgodę,
a na karcie kanbana (bez człowieka) zawsze by odpadło; tryb tylko do odczytu szefa daje `tools.include`.
Zgoda: `confirm=true` w act albo batch (bramka needs_confirm telefonu) przechodzi tylko przez prośbę o zgodę
wtyczki jarvo-zgody, a bez człowieka jest zablokowane. Pod YOLO wtyczka blokuje narzędzia jarvo-operator (także
telefon), tak jak computer_use.

`on` i `off` robi tylko właściciel w swoim terminalu: wywołane przez proces Jarva (agent, rutyna, karta kanbana;
znaczniki jak w jarvo/rece.py) kończą się odmową. `status` może każdy. Restart bramy przerwałby pracę kart, więc przy
karcie w toku (status `running` w kanban.db którejkolwiek tablicy, hq/plugin/prace.py karty_w_toku) zmiana czeka
na następny restart bramy albo `jarvo update`.

YAML profili czyta i pisze Python Hermesa (ruamel, fleetlib.rt_yaml) z kodu aktywnej wersji Jarva; ten moduł działa
na bibliotece standardowej.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if __package__ in (None, ""):                         # `python jarvo/telefon.py`: pakiet jarvo z katalogu wyżej
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvo import android, flota, przenosne, przy_uzyciu, sciezki, srodowisko  # noqa: E402
from jarvo.rece import proces_floty, zrestartuj_brame  # noqa: E402
from jarvo.sciezki import WINDOWS, Uklad  # noqa: E402

STAN = "telefon.json"                                  # <stan>/telefon.json
SERWER = "phone"                                       # nazwa serwera MCP: narzędzia mcp__phone__<narzędzie>
KLUCZ = f"mcp_servers.{SERWER}"
NARZEDZIA_ODCZYTU = ("list_phones", "ping", "screen", "shot", "wait")     # bez act i batch: nic nie stuka ani nie pisze
PROFILE = {"jarvo": NARZEDZIA_ODCZYTU, "jarvo-operator": None}           # None = wszystkie narzędzia serwera
SDK = "mcp>=2.3,<3"
NAZWA_TELEFONU = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")         # jak NAME w phone_mcp.py
CZAS_SDK = 60.0
CZAS_HERMESA = 300.0
APP = Path(__file__).resolve().parent.parent
# import SDK jak phone_mcp.load_sdk (MCPServer jest od 2.0) i jego wersja
KOD_SDK = "import importlib.metadata as m, mcp.server.mcpserver; print(m.version('mcp'))"
# YAML profili Pythonem Hermesa: argv = katalog scripts/, <dane>, tryb ("czytaj" albo plik ustawień), agenci
KOD_KONFIGU = r'''
import json, sys
from pathlib import Path
skrypty, dane, tryb, agenci = sys.argv[1], Path(sys.argv[2]), sys.argv[3], sys.argv[4:]
sys.path.insert(0, skrypty)
if tryb == "czytaj":
    import fleetlib
    load, _ = fleetlib.rt_yaml()
    wynik = {}
    for agent in agenci:
        p = dane / "profiles" / agent / "config.yaml"
        cfg = load(p) if p.is_file() else None
        serwery = cfg.get("mcp_servers") if isinstance(cfg, dict) else None
        wpis = serwery.get("phone") if isinstance(serwery, dict) else None
        wynik[agent] = None if cfg is None else (wpis if isinstance(wpis, dict) else False)
    print(json.dumps(wynik, default=str))
else:
    import install_fleet
    a = install_fleet.parser().parse_args(["--dane", str(dane), "--bez-sekretow", "--ustawienia-profili", tryb])
    f = install_fleet.Flota(a, wypisz=lambda t: print(t.strip()))
    for agent in agenci:
        f.ustaw_klucze_profilu(agent, dane / "profiles" / agent / "config.yaml")
'''


class BladTelefonu(RuntimeError):
    """Krok `jarvo telefon` się nie udał (komunikat po polsku z radą)."""


def _wynik(nazwa: str, stan: str, opis: str, rada: str = "") -> dict:
    return {"nazwa": nazwa, "stan": stan, "opis": opis, "rada": rada}


# ---------------------------------------------------------------- stan i wzór wpisu

def stan_telefonu(u: Uklad) -> dict:
    """`<stan>/telefon.json`: {"wlaczony", "python", "serwer", "telefon", "kiedy"}."""
    return srodowisko.wczytaj_json(u.stan / STAN)


def zapisz_stan(u: Uklad, dane: dict) -> None:
    przenosne.zapisz_atomowo(u.stan / STAN, json.dumps(dane, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def python_domyslny() -> Path:
    """Venv, który zakłada PHONEUSE tools/mcp_setup.py: ~/.phoneuse/mcp-venv."""
    venv = Path.home() / ".phoneuse" / "mcp-venv"
    return venv / ("Scripts/python.exe" if WINDOWS else "bin/python")


def adb_floty(u: Uklad) -> Path | None:
    """adb serwera telefonu: ten sam co `jarvo android` (platform-tools Jarva), żeby działał jeden serwer adb jednej
    wersji; None = PHONEUSE weźmie swój (body.adb_binary)."""
    return android.adb(u)


def wpis_serwera(st: dict, agent: str, adb: Path | str | None) -> dict:
    """Wpis `mcp_servers.phone` profilu `agent` (jeden wzór dla `jarvo telefon on` i flota.ustawienia_profili)."""
    wpis: dict = {"command": str(st["python"]), "args": [str(st["serwer"])],
                  # jak inspo (profiles/jarvo-web/config.yaml): bez readOnlyHint `untrusted` pytałby o każde wywołanie
                  "trust": "full",
                  "timeout": 360,          # samonaprawa łącza w body.py trwa do 300 s (PHONEUSE mcp_setup.HEAL_S)
                  "connect_timeout": 60, "lazy": True, "idle_timeout_seconds": 900,
                  "resources": False, "prompts": False}
    env = {}
    if adb:
        env["ADB"] = str(adb)
    if st.get("telefon"):
        env["PHONEUSE_PHONE"] = str(st["telefon"])
    if env:
        wpis["env"] = env
    if PROFILE[agent] is not None:
        wpis["tools"] = {"include": list(PROFILE[agent])}
    return wpis


def klucze_profili(u: Uklad, agenci=PROFILE) -> dict[str, dict]:
    """{agent: {"mcp_servers.phone": wpis}} dla install_fleet.py --ustawienia-profili, gdy telefon jest włączony;
    wyłączony albo bez <stan>/telefon.json: {} (instalacja bez PHONEUSE bez zmian)."""
    st = stan_telefonu(u)
    if not st.get("wlaczony") or not st.get("python") or not st.get("serwer"):
        return {}
    adb = adb_floty(u)
    return {a: {KLUCZ: wpis_serwera(st, a, adb)} for a in PROFILE if a in agenci}


# ---------------------------------------------------------------- sprawdzenia plików i SDK

def wersja_sdk(python: Path) -> tuple[str | None, str]:
    """(wersja mcp, błąd): import MCP SDK 2.x tym Pythonem (-I: bez zmiennych i katalogu bieżącego, jak w bramie)."""
    try:
        w = subprocess.run([str(python), "-I", "-c", KOD_SDK], stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=CZAS_SDK)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"{python} się nie uruchamia ({e})"
    wersja = w.stdout.strip().splitlines()[-1].strip() if w.stdout.strip() else ""
    if w.returncode or not wersja:
        ogon = (w.stderr.strip().splitlines() or ["brak wyjścia"])[-1]
        return None, f"ten Python nie importuje MCP SDK 2.x ({ogon[:200]})"
    if wersja.split(".")[0] != "2":
        return None, f"ten Python ma mcp {wersja}, a phone_mcp.py potrzebuje {SDK}"
    return wersja, ""


def sprawdz_pliki(python: Path, serwer: Path, phoneuse: Path | None = None) -> str | None:
    """Błąd z radą albo None, gdy serwer jest, a Python ma MCP SDK 2.x."""
    katalog = phoneuse or serwer.parent.parent
    rada = f"Załóż venv z SDK: python3 {katalog / 'tools' / 'mcp_setup.py'} (albo podaj --python z {SDK})."
    if not serwer.is_file():
        return f"Nie ma serwera MCP PHONEUSE: {serwer}. Podaj katalog repo PHONEUSE w --phoneuse."
    if not python.is_file():
        return f"Nie ma Pythona serwera: {python}. {rada}"
    _wersja, blad = wersja_sdk(python)
    return f"{blad}. {rada}" if blad else None


# ---------------------------------------------------------------- config zainstalowanych profili

def _python_hermesa(u: Uklad) -> Path:
    return flota.python_hermesa(u)[1]


def _konfig_hermesem(u: Uklad, tryb: str, agenci: list[str]) -> str:
    """KOD_KONFIGU Pythonem Hermesa ze scripts/ aktywnej wersji Jarva; wyjście albo BladTelefonu."""
    try:
        python = _python_hermesa(u)
    except flota.BladFloty as e:
        raise BladTelefonu(str(e)) from None
    skrypty = flota.katalog_kodu(u) / "scripts"
    argv = [str(python), "-c", KOD_KONFIGU, str(skrypty), str(u.dane), tryb, *agenci]
    try:
        w = subprocess.run(argv, cwd=str(u.dane), env=flota._env(u, os.environ, python), stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=CZAS_HERMESA)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise BladTelefonu(f"Python Hermesa ({python}): {e}") from None
    if w.returncode:
        ogon = " / ".join(x for x in (w.stdout + w.stderr).splitlines()[-3:] if x.strip())
        raise BladTelefonu(f"config profili: kod {w.returncode}: {ogon}")
    return w.stdout


def config_profilu(u: Uklad, agent: str) -> Path:
    return u.dane / "profiles" / agent / "config.yaml"


def zainstalowane(u: Uklad) -> list[str]:
    return [a for a in PROFILE if config_profilu(u, a).is_file()]


def wpisy_w_profilach(u: Uklad) -> dict[str, dict | bool | None]:
    """{agent: wpis phone (dict), False = profil bez wpisu, None = brak profilu}."""
    wynik = json.loads(_konfig_hermesem(u, "czytaj", list(PROFILE)).strip().splitlines()[-1])
    return {a: wynik.get(a) for a in PROFILE}


def ustaw_w_profilach(u: Uklad, klucze: dict[str, dict]) -> list[str]:
    """Klucze w config.yaml zainstalowanych profili kodem install_fleet.ustaw_klucze_profilu; zwraca profile, których
    plik się zmienił."""
    agenci = [a for a in klucze if config_profilu(u, a).is_file()]
    if not agenci:
        return []
    przed = {a: config_profilu(u, a).read_bytes() for a in agenci}
    u.stan.mkdir(parents=True, exist_ok=True)
    fd, nazwa = tempfile.mkstemp(prefix=".telefon-klucze.", suffix=".json", dir=str(u.stan))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"wersja": 1, "wszystkie": {}, "profile": {a: klucze[a] for a in agenci}}, f, ensure_ascii=False)
        _konfig_hermesem(u, nazwa, agenci)
    finally:
        Path(nazwa).unlink(missing_ok=True)
    return [a for a in agenci if config_profilu(u, a).read_bytes() != przed[a]]


# ---------------------------------------------------------------- restart bramy

def _prace():
    """hq/plugin/prace.py tej wersji Jarva (karty_w_toku: to samo zapytanie co praca.json aktualizacji)."""
    sciezka = APP / "hq" / "plugin" / "prace.py"
    spec = importlib.util.spec_from_file_location("jarvo_hq_prace", sciezka)
    if spec is None or spec.loader is None:
        raise BladTelefonu(f"nie wczytam {sciezka}")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def karty_w_toku(u: Uklad) -> list[dict]:
    """Karty `running` wszystkich tablic: `<dane>/kanban.db` (default) i `<dane>/kanban/boards/<tablica>/kanban.db`."""
    prace = _prace()
    bazy = [u.dane / "kanban.db", *sorted((u.dane / "kanban" / "boards").glob("*/kanban.db"))]
    return [k for b in bazy for k in prace.karty_w_toku(b)]


def restart_gdy_wolno(u: Uklad, co: str) -> int:
    """Restart bramy jak w `jarvo komputer rece` (nadzorca), ale tylko bez kart w toku: inaczej zmiana czeka."""
    try:
        karty = karty_w_toku(u)
    except (OSError, BladTelefonu, ImportError) as e:
        print(f"Nie sprawdzę kart kanbana w toku ({e}), więc nie restartuję bramy. {co} zadziała po następnym "
              "restarcie bramy albo po jarvo update; restart teraz: jarvo serwis --restart brama.")
        return 0
    if karty:
        opis = ", ".join(f"„{k['tytul']}” ({k['wykonawca'] or '?'})" for k in karty[:3])
        print(f"Brama Jarva bez restartu: w toku {len(karty)} kart(y) kanbana ({opis}), restart przerwałby ich "
              f"pracę. {co} zadziała po następnym restarcie bramy albo po jarvo update. Gdy karty się skończą: "
              "jarvo serwis --restart brama.")
        return 0
    wynik = zrestartuj_brame(u)
    if wynik == "zrestartowana":
        print(f"Brama Jarva zrestartowana przez nadzorcę: {co} działa.")
    elif wynik == "nie_dziala":
        print(f"Brama Jarva nie działa: {co} zadziała przy jej starcie (jarvo up).")
    elif wynik == "bez_nadzorcy":
        print(f"Brama Jarva działa bez nadzorcy: {co} zadziała po jej restarcie (jarvo serwis --restart brama albo "
              "zatrzymaj i uruchom ją od nowa).")
    else:
        print(f"Bramy Jarva nie udało się zrestartować ({wynik[5:].strip()}): zrób to sam, jarvo serwis --restart "
              "brama.", file=sys.stderr)
        return 1
    return 0


# ---------------------------------------------------------------- polecenia

def _odmowa_floty(u: Uklad, co: str) -> int | None:
    """Kod 1 z komunikatem, gdy polecenie wywołał proces Jarva (agent, rutyna, karta kanbana), a nie właściciel."""
    znak = proces_floty(dict(os.environ), u.dane)
    if znak is None:
        return None
    print(f"{co} tylko właściciel, w swoim terminalu. To polecenie wywołał proces Jarva ({znak}): odmowa. Poproś "
          "właściciela o to polecenie.", file=sys.stderr)
    return 1


def _bez_instalacji(u: Uklad) -> int:
    print(f"Jarvo nie jest zainstalowane natywnie w {u.root}: telefon przez PHONEUSE działa w instalacji natywnej.",
          file=sys.stderr)
    return 1


def polecenie_on(u: Uklad, a, _reszta=(), _ot=None) -> int:
    if not przy_uzyciu.natywnie(u):
        return _bez_instalacji(u)
    if (kod := _odmowa_floty(u, "Telefon dla floty włącza")) is not None:
        return kod
    if a.telefon is not None and not NAZWA_TELEFONU.fullmatch(a.telefon):
        print(f"--telefon {a.telefon!r}: nazwa telefonu z PHONEUSE (litery, cyfry, - i _; lista: list_phones).",
              file=sys.stderr)
        return 2
    phoneuse = Path(a.phoneuse).expanduser().absolute()
    serwer = phoneuse / "tools" / "phone_mcp.py"
    python = Path(a.python).expanduser().absolute() if a.python else python_domyslny()
    if (blad := sprawdz_pliki(python, serwer, phoneuse)) is not None:
        print(f"BŁĄD: {blad}", file=sys.stderr)
        return 1
    st = {"wlaczony": True, "python": str(python), "serwer": str(serwer), "telefon": a.telefon,
          "kiedy": time.strftime("%Y-%m-%dT%H:%M:%S")}
    zapisz_stan(u, st)
    print(f"Telefon dla floty włączony: serwer MCP {serwer} ({python}).")
    try:
        zmienione = ustaw_w_profilach(u, klucze_profili(u))
    except BladTelefonu as e:
        print(f"BŁĄD: stan zapisany, ale profili nie zmieniłem: {e}. Wpis dopisze następne jarvo update albo "
              "jarvo telefon on jeszcze raz.", file=sys.stderr)
        return 1
    if not zainstalowane(u):
        print("Profile jarvo i jarvo-operator nie są jeszcze zainstalowane: wpis dopisze instalacja floty.")
        return 0
    if not zmienione:
        print("Profile jarvo i jarvo-operator miały już ten wpis: bez restartu bramy.")
        return 0
    print(f"Wpis mcp_servers.{SERWER} w profilach: {', '.join(zmienione)} (jarvo: tylko odczyt ekranu).")
    return restart_gdy_wolno(u, "telefon w profilach")


def polecenie_off(u: Uklad, a, _reszta=(), _ot=None) -> int:
    if not przy_uzyciu.natywnie(u):
        return _bez_instalacji(u)
    if (kod := _odmowa_floty(u, "Telefon dla floty wyłącza")) is not None:
        return kod
    st = stan_telefonu(u)
    st.update(wlaczony=False, kiedy=time.strftime("%Y-%m-%dT%H:%M:%S"))
    zapisz_stan(u, st)
    print("Telefon dla floty wyłączony: następna instalacja floty nie dopisze serwera phone. Włączenie: "
          "jarvo telefon on --phoneuse KATALOG.")
    if not zainstalowane(u):
        return 0
    try:
        z_wpisem = [ag for ag, w in wpisy_w_profilach(u).items() if isinstance(w, dict)]
        zmienione = ustaw_w_profilach(u, {ag: {f"{KLUCZ}.enabled": False} for ag in z_wpisem})
    except BladTelefonu as e:
        print(f"BŁĄD: profili nie zmieniłem: {e}. Serwer phone zniknie z nich przy następnym jarvo update.",
              file=sys.stderr)
        return 1
    if not zmienione:
        return 0
    print(f"mcp_servers.{SERWER}.enabled: false w profilach: {', '.join(zmienione)}.")
    return restart_gdy_wolno(u, "wyłączenie telefonu")


def opis_stanu(u: Uklad) -> dict:
    st = stan_telefonu(u)
    python = Path(st["python"]) if st.get("python") else python_domyslny()
    serwer = Path(st["serwer"]) if st.get("serwer") else None
    wersja, blad_sdk = wersja_sdk(python) if python.is_file() else (None, "brak pliku")
    adb = adb_floty(u)
    try:
        profile, blad_profili = wpisy_w_profilach(u), None
    except (BladTelefonu, ValueError, IndexError) as e:
        profile, blad_profili = None, str(e)
    return {"wlaczony": bool(st.get("wlaczony")), "wlaczano": bool(st), "kiedy": st.get("kiedy"),
            "python": str(python), "python_jest": python.is_file(), "sdk": wersja, "blad_sdk": blad_sdk or None,
            "serwer": str(serwer) if serwer else None, "serwer_jest": bool(serwer and serwer.is_file()),
            "telefon": st.get("telefon"), "adb": str(adb) if adb else None,
            "profile": profile, "blad_profili": blad_profili}


def _opis_wpisu(w) -> str:
    if w is None:
        return "profil niezainstalowany"
    if w is False:
        return "bez serwera phone"
    stan = "wyłączony (enabled: false)" if w.get("enabled") is False else "włączony"
    include = (w.get("tools") or {}).get("include") if isinstance(w.get("tools"), dict) else None
    return f"serwer phone {stan}, " + (f"narzędzia: {', '.join(include)}" if include else "wszystkie narzędzia")


def polecenie_status(u: Uklad, a, _reszta=(), _ot=None) -> int:
    if not przy_uzyciu.natywnie(u):
        return _bez_instalacji(u)
    s = opis_stanu(u)
    if getattr(a, "json", False):
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0
    stan = ("włączony" if s["wlaczony"] else "wyłączony (jarvo telefon on --phoneuse KATALOG)" if s["wlaczano"]
            else "jeszcze nie włączony (jarvo telefon on --phoneuse KATALOG)")
    print(f"Telefon dla floty (PHONEUSE, serwer MCP {SERWER}): {stan}")
    if s["serwer"]:
        print(f"  serwer: {s['serwer']}" + ("" if s["serwer_jest"] else " (BRAK PLIKU)"))
    print(f"  python: {s['python']}" + (f", mcp {s['sdk']}" if s["sdk"] else f" ({s['blad_sdk']})"))
    print("  adb: " + (f"{s['adb']} (ten sam co jarvo android)" if s["adb"] else
                       "platform-tools Jarva nie ma (jarvo android on): PHONEUSE weźmie swój adb"))
    if s["telefon"]:
        print(f"  telefon domyślny: {s['telefon']}")
    if s["profile"] is None:
        print(f"  profile: nie sprawdzę ({s['blad_profili']})")
    else:
        for agent, w in s["profile"].items():
            print(f"  {agent}: {_opis_wpisu(w)}")
    return 0


# ---------------------------------------------------------------- jarvo doctor

def sprawdzenia(u: Uklad, ot=None) -> list[dict]:
    """Wyniki dla `jarvo doctor` (niczego nie zapisują). Telefon nie jest wymagany."""
    if not przy_uzyciu.natywnie(u):
        return []
    st = stan_telefonu(u)
    if not st.get("wlaczony"):
        return [_wynik("telefon (PHONEUSE)", "ok", "nie włączony (opcjonalny): jarvo telefon on --phoneuse "
                       "<katalog PHONEUSE>")]
    python, serwer = Path(str(st.get("python") or "")), Path(str(st.get("serwer") or ""))
    blad = sprawdz_pliki(python, serwer)
    if blad:
        return [_wynik("telefon (PHONEUSE)", "uwaga", blad, "Potem jarvo telefon on --phoneuse <katalog PHONEUSE> "
                       "albo jarvo telefon off.")]
    return [_wynik("telefon (PHONEUSE)", "ok", f"serwer MCP {SERWER} włączony: jarvo-operator pełny, jarvo tylko "
                   "odczyt ekranu")]


# ---------------------------------------------------------------- parser

def dodaj_polecenia(sub) -> None:
    """Polecenie `telefon` w parserze jarvo (cli._parser); funkcje biorą (u, a, reszta, ot). Samo `jarvo telefon` =
    status."""
    s = sub.add_parser("telefon", help="telefon przez PHONEUSE dla Operatora (i podgląd dla Jarva): status, on, off",
                       description="Serwer MCP PHONEUSE (phone_mcp.py) w profilach jarvo-operator (wszystkie "
                       "narzędzia) i jarvo (tylko odczyt ekranu).")
    s.set_defaults(funkcja=polecenie_status, json=False)
    t = s.add_subparsers(dest="telefon_polecenie", metavar="polecenie", title="polecenia")
    k = t.add_parser("status", help="stan, pliki, SDK, adb, wpis w profilach")
    k.add_argument("--json", action="store_true")
    k.set_defaults(funkcja=polecenie_status)
    k = t.add_parser("on", help="włącz: sprawdza PHONEUSE i SDK, wpis w profilach, restart bramy bez kart w toku")
    k.add_argument("--phoneuse", required=True, metavar="KATALOG", help="katalog repo PHONEUSE (z tools/phone_mcp.py)")
    k.add_argument("--python", metavar="PYTHON", help=f"Python z {SDK} (domyślnie ~/.phoneuse/mcp-venv)")
    k.add_argument("--telefon", metavar="NAZWA", help="domyślny telefon serwera (PHONEUSE_PHONE; domyślnie pierwszy)")
    k.set_defaults(funkcja=polecenie_on)
    k = t.add_parser("off", help="wyłącz: enabled: false w profilach, restart bramy bez kart w toku")
    k.set_defaults(funkcja=polecenie_off)


def main(argv: list[str] | None = None) -> int:
    """`python -I -X utf8 jarvo/telefon.py <status|on|off> …` bez reszty CLI."""
    for strumien in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            strumien.reconfigure(errors="replace")
    p = argparse.ArgumentParser(prog="jarvo", description="Telefon przez PHONEUSE (docs/MOBILE.md).")
    sub = p.add_subparsers(dest="polecenie", metavar="polecenie", title="polecenia")
    sub.required = True
    dodaj_polecenia(sub)
    a = p.parse_args(["telefon", *(sys.argv[1:] if argv is None else argv)])
    try:
        u = przy_uzyciu.uklad()
    except sciezki.BladUkladu as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 1
    try:
        return int(a.funkcja(u, a, [], None) or 0)
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    sys.exit(main())
