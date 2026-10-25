"""`jarvo komputer rece on|off|status`: ręce Operatora na ekranie właściciela (docs/KOMPUTER.md, etap K6;
docs/NATYWNIE.md J14, J15, N13; decyzja I19). Domyślnie wyłączone.

  on --aplikacje A,B [--na 30m] [--profil jarvo-ekran] [--bezczynnosc 10m] [--bez-pobierania]
        tylko właściciel, w swoim terminalu (bez terminala i z procesu floty: odmowa), po wpisaniu TAK.
        Sprawdza prawa (nie administrator), ekran (Linux: X11 albo XWayland), aplikacje (bez terminali, narzędzi
        systemu, menedżerów haseł i samego Jarva) i sterownik cua-driver-rs 0.38.0 (suma programu, podpis; brak =
        pobranie z sumą z manifestu, na macOS instrukcja kopii do /Applications). Domyślny profil rąk `jarvo-ekran`
        zakłada albo odświeża sam (komputer/rece/profil.py: bounded z manifestem zgody, approvals manual, bez
        terminala i plików, model z jarvo-operator); nowy powstaje w całości obok i dopiero gotowy dostaje swoją
        nazwę, a po zmianie profilu działająca brama Jarva restartuje się przez nadzorcę (bez nadzorcy: rada, jak
        ją zrestartować). Inny --profil musi już być profilem rąk: bramka czyta go tak jak Hermes (approvals.mode
        manual, tryby bez człowieka deny, bez stałych zgód cua:*). Zapisuje zgodę podpisaną kluczem HMAC
        z <stan>/rece.klucz i manifest bounded sterownika.
  off   wyłącza od razu: usuwa zgodę, zatrzymuje działające sterowniki rąk (także z innego okna); może każdy.
        Profil rąk zostaje, ale bez zgody nic nie zrobi.
  status [--json]   zgoda, czas, aplikacje, sterownik, działające demony, profil i ostatnie wpisy dziennika.

Podpięcie w jarvo/cli.py: `jarvo komputer rece …` → `rece.main(reszta_po_słowie_rece, env=…)`; kod wyjścia jak
tutaj (0 dobrze, 1 błąd, 2 złe argumenty, profil, którego bramka nie wpuści, albo brak wpisu sterownika
w manifeście, 3 potrzebny krok właściciela na macOS).

Kod rąk (zgoda, bramka, sterownik) leży w `komputer/rece/` obok tego katalogu; bramka `komputer/jarvo_cua.py`
woła ten sam kod przy każdym `serve` i `mcp` sterownika.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Callable

from . import sciezki

KOMPUTER = Path(__file__).resolve().parents[1] / "komputer"
ZNACZNIKI_FLOTY = ("HERMES_GATEWAY_LOCK_DIR", "HERMES_WRITE_SAFE_ROOT", "JARVO_DATA_DIR", "JARVO_KNOWLEDGE_DIR",
                   "HERMES_KANBAN_TASK", "HERMES_KANBAN_WORKSPACE", "HERMES_CRON_SESSION",
                   "HERMES_SINGLE_QUERY_SESSION")
KOD_KROK_WLASCICIELA = 3


def pakiet(katalog: Path = KOMPUTER):
    """Pakiet `komputer/rece` (import `rece` z katalogu komputer/, jak w bramce jarvo_cua.py)."""
    if str(katalog) not in sys.path:
        sys.path.insert(0, str(katalog))
    return importlib.import_module("rece")


def _modul(nazwa: str):
    pakiet()
    return importlib.import_module(f"rece.{nazwa}")


def proces_floty(env: dict, dane: Path) -> str | None:
    """Zmienna, po której widać, że polecenie wywołał proces Jarva (agent z terminalem, rutyna, karta kanbana),
    a nie właściciel w swoim terminalu. Prywatny Hermes właściciela (inny HERMES_HOME) nie przeszkadza."""
    for nazwa in ZNACZNIKI_FLOTY:
        if str(env.get(nazwa) or "").strip():
            return nazwa
    dom = str(env.get("HERMES_HOME") or "").strip()
    if dom:
        d = os.path.normcase(os.path.abspath(dom))
        k = os.path.normcase(os.path.abspath(dane))
        if d == k or d.startswith(k.rstrip("\\/") + os.sep):
            return "HERMES_HOME"
    return None


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jarvo komputer rece", description="Ręce Operatora na Twoim ekranie: domyślnie "
                                "wyłączone, włączasz je sam, na czas i w wybranych aplikacjach.")
    sub = p.add_subparsers(dest="akcja", metavar="on|off|status", title="polecenia")
    s = sub.add_parser("on", help="włącz ręce na czas w wybranych aplikacjach (tylko właściciel, w swoim terminalu)")
    s.add_argument("--aplikacje", action="append", required=True, metavar="LISTA",
                   help="aplikacje po przecinku (np. notatnik,mspaint; macOS: TextEdit albo com.apple.TextEdit)")
    s.add_argument("--na", default="30m", metavar="CZAS", help="na jak długo: 30m (domyślnie), 1h, 90s; najwyżej 8h")
    s.add_argument("--profil", default=None, metavar="PROFIL",
                   help="profil rąk (domyślnie jarvo-ekran: zakładany i odświeżany sam)")
    s.add_argument("--bezczynnosc", default="10m", metavar="CZAS",
                   help="ręce gasną same po tym czasie bez działań (domyślnie 10m)")
    s.add_argument("--bez-pobierania", action="store_true", help="nie pobieraj sterownika, gdy go nie ma")
    sub.add_parser("off", help="wyłącz ręce od razu (zatrzymuje też działające sterowniki rąk)")
    s = sub.add_parser("status", help="czy ręce są włączone, do kiedy, w czym i czy sterownik jest gotowy")
    s.add_argument("--json", action="store_true", help="wynik w JSON")
    return p


@contextlib.contextmanager
def _po_polsku():
    try:
        from .cli import _po_polsku as polski
    except ImportError:                                   # bez cli (np. sam moduł w testach): angielskie napisy
        yield
        return
    with polski():
        yield


class Wyjscie:
    def __init__(self, strumien=None):
        self.strumien = strumien

    def __call__(self, tekst: str = "") -> None:
        s = self.strumien or sys.stdout
        s.write(tekst + "\n")
        s.flush()


def main(argv: list[str] | None = None, *, env: dict | None = None, wejscie: Callable[[str], str] | None = None,
         tty: bool | None = None, teraz: Callable[[], float] | None = None, sprawdz_sterownik=None,
         podwyzszone: Callable[[], bool] | None = None, zainstaluj=None, rozpoznaj=None, wyjscie=None,
         platforma: str | None = None, restart_bramy: Callable | None = None) -> int:
    """`jarvo komputer rece <akcja>`. Parametry poza `argv` podstawiają testy (atrapa sterownika, terminal, zegar,
    restart bramy)."""
    argv = list(sys.argv[1:] if argv is None else argv)
    env = dict(os.environ if env is None else env)
    pisz = Wyjscie(wyjscie)
    with contextlib.suppress(AttributeError, ValueError, OSError):
        sys.stdout.reconfigure(errors="replace")
    try:
        with _po_polsku():
            a = _parser().parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 2)
    if not a.akcja:
        _parser().print_help()
        return 2
    try:
        u = sciezki.uklad(env)
        plat = platforma or sciezki.platforma()
    except sciezki.BladUkladu as e:
        pisz(f"BŁĄD: {e}")
        return 1
    zg = _modul("zgoda")
    pliki = zg.Pliki(u.stan)
    if a.akcja == "off":
        return wylacz(u, pliki, pisz)
    if a.akcja == "status":
        return pokaz_status(u, pliki, plat, env, pisz, json_=a.json, teraz=teraz, sprawdz_sterownik=sprawdz_sterownik,
                            podwyzszone=podwyzszone)
    return wlacz(a, u, pliki, plat, env, pisz, wejscie=wejscie, tty=tty, teraz=teraz,
                 sprawdz_sterownik=sprawdz_sterownik, podwyzszone=podwyzszone, zainstaluj=zainstaluj,
                 rozpoznaj=rozpoznaj, restart_bramy=restart_bramy)


# ---------------------------------------------------------------- off

def wylacz(u, pliki, pisz) -> int:
    zg, proc, dz = _modul("zgoda"), _modul("procesy"), _modul("dziennik")
    bylo = zg.odwolaj(pliki)
    zatrzymane = proc.Rejestr(pliki.procesy).zatrzymaj_wszystko()
    if bylo or zatrzymane:
        dz.zapisz(pliki.dziennik, "off", zatrzymane=zatrzymane)
    pisz("Ręce wyłączone." if bylo else "Ręce były wyłączone.")
    if zatrzymane:
        pisz(f"Zatrzymałem działające sterowniki rąk: {zatrzymane}.")
    return 0


# ---------------------------------------------------------------- on

def _profil(nazwa: str | None) -> str:
    """Nazwa profilu jak w Hermesie (małe litery, cyfry, - i _): bez ścieżek, więc config zawsze w <dane>/profiles."""
    import re
    wynik = (nazwa or pakiet().PROFIL).strip().casefold()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", wynik):
        raise ValueError(f"{nazwa!r} to nie nazwa profilu (małe litery, cyfry, - i _)")
    return wynik


def config_profilu(u, profil: str) -> Path:
    return u.dane / "profiles" / profil / "config.yaml"


def ustawienia_profilu(tekst: str, manifest: Path) -> list[str]:
    """Czego brakuje w configu profilu rąk (Hermes w trybie bounded z manifestem rąk), czytanym tak jak przez bramkę
    (komputer/rece/konfig.py)."""
    kf = _modul("konfig")
    try:
        m = kf.czytaj(tekst)
    except kf.Niepewne as e:
        return [f"config.yaml, który da się przeczytać bez zgadywania ({e})"]
    brak = []
    if (kf.napis(m, "computer_use", "permission_mode") or "").strip().lower() != "bounded":
        brak.append("computer_use.permission_mode: bounded")
    wpis = kf.napis(m, "computer_use", "capability_manifest")
    # Hermes: os.path.abspath(os.path.expanduser(...)), tools/computer_use/cua_backend_daemon.py
    if not wpis or os.path.normcase(os.path.abspath(os.path.expanduser(wpis.strip()))) != \
            os.path.normcase(os.path.abspath(manifest)):
        brak.append(f"computer_use.capability_manifest: {manifest}")
    return brak


def zrestartuj_brame(u) -> str:
    """Brama Jarva widzi zmieniony profil dopiero po restarcie (docs/NATYWNIE.md, ryzyko Z39): restart przez nadzorcę,
    gdy brama działa pod nim. Wynik: "zrestartowana", "nie_dziala", "bez_nadzorcy" (brama odpowiada, a nadzorcy
    nie ma) albo "blad: <powód>"."""
    from . import instalator, nadzorca
    stan, _ = instalator.stan_serwisu(u)
    if stan is not None:
        brama = instalator.usluga_nadzorcy(stan, "brama")
        if brama.get("stan") in (None, "zatrzymana") and not brama.get("pid"):
            return "nie_dziala"
        try:
            nadzorca.polacz(u).restart("brama")
        except nadzorca.BladNadzorcy as e:
            return f"blad: {e}"
        return "zrestartowana"
    return "bez_nadzorcy" if nadzorca.brama_gotowa(u.dane) else "nie_dziala"


def _opis_restartu(wynik: str, profil: str) -> str | None:
    if wynik == "zrestartowana":
        return f"Brama Jarva zrestartowana przez nadzorcę: widzi już profil rąk {profil}."
    if wynik == "bez_nadzorcy":
        return (f"Brama Jarva działa bez nadzorcy i nie widzi jeszcze zmian profilu {profil}: zrestartuj ją "
                "(jarvo serwis --restart brama albo zatrzymaj i uruchom ją od nowa). `jarvo chat --profil "
                f"{profil}` działa od razu.")
    if wynik.startswith("blad"):
        return (f"Bramy Jarva nie udało się zrestartować ({wynik[5:].strip()}): zrób to sam (jarvo serwis --restart "
                f"brama), zanim użyjesz profilu {profil} przez bramę (HQ, Telegram).")
    return None


def _odrzuc_profil(pisz, profil: str, plik: Path, problemy: list, domyslny: str) -> int:
    pisz(f"Profil {profil}: bramka nie wpuści rąk z tym profilem ({plik}):")
    for o in problemy:
        pisz(f"  - {o.powod}")
    pisz(f"Bez --profil ręce działają w profilu {domyslny}, który `jarvo komputer rece on` zakłada sam.")
    return 2


def wlacz(a, u, pliki, plat: str, env: dict, pisz, *, wejscie, tty, teraz, sprawdz_sterownik, podwyzszone,
          zainstaluj, rozpoznaj, restart_bramy=None) -> int:
    pk, zg, apl, st_mod, bramka, dz, prof = (pakiet(), _modul("zgoda"), _modul("aplikacje"), _modul("sterownik"),
                                            _modul("bramka"), _modul("dziennik"), _modul("profil"))
    if (znak := proces_floty(env, u.dane)) is not None:
        pisz(f"Ręce włącza tylko właściciel, w swoim terminalu. To polecenie wywołał proces Jarva ({znak}): odmowa.")
        return 1
    if not (sys.stdin.isatty() if tty is None else tty):
        pisz("Ręce włącza tylko właściciel w terminalu (potrzebne potwierdzenie z klawiatury): odmowa.")
        return 1
    if (podwyzszone or st_mod.podwyzszone)():
        pisz("Ten terminal ma prawa administratora: ręce nie startują (sterownik sięgałby do okien administratora). "
             "Otwórz zwykły terminal i spróbuj jeszcze raz.")
        return 1
    if plat.startswith("linux"):
        if (powod := st_mod.ekran_linux(env)) is not None:
            pisz(powod)
            return 1
        for uwaga in st_mod.uwagi_linux(env):
            pisz(f"Uwaga: {uwaga}.")
    try:
        sekundy = zg.czas(a.na)
        bezczynnosc = zg.czas(a.bezczynnosc)
        profil = _profil(a.profil)
    except ValueError as e:
        pisz(f"BŁĄD: {e}")
        return 2
    nazwy = [n.strip() for grupa in a.aplikacje for n in grupa.split(",") if n.strip()]
    try:
        lista = (rozpoznaj or (lambda n: apl.rozpoznaj(n, system=st_mod.system_platformy(plat), env=env)))(nazwy)
    except apl.BladAplikacji as e:
        pisz(f"BŁĄD: {e}")
        return 2
    plik_profilu = config_profilu(u, profil)
    plan = None
    if profil == pk.PROFIL:                      # profil rąk Jarva: zakładamy go albo odświeżamy sami
        try:
            plan = prof.zaplanuj(u.dane, pliki.manifest, profil)
        except prof.BladProfilu as e:
            pisz(f"BŁĄD: {e}")
            return 2
        tekst = plan.config
    else:
        try:
            tekst = plik_profilu.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            pisz(f"Nie ma profilu {profil} ({plik_profilu}). Bez --profil ręce działają w profilu {pk.PROFIL}, "
                 "który to polecenie zakłada samo (docs/KOMPUTER.md, K6).")
            return 2
    if problemy := bramka.problemy_profilu(tekst, plik=plik_profilu):
        return _odrzuc_profil(pisz, profil, plik_profilu, problemy, pk.PROFIL)
    sterownik = _sterownik(u, plat, pisz, a.bez_pobierania, sprawdz_sterownik, zainstaluj)
    if isinstance(sterownik, int):
        return sterownik
    do = (teraz or time.time)() + sekundy
    pisz("Oddajesz Operatorowi ręce na Twoim ekranie:")
    pisz(f"  aplikacje:  {', '.join(x.nazwa for x in lista)}")
    for x in lista:
        pisz(f"              {x.nazwa}: {next(iter(x.tozsamosc.values()))}")
    pisz(f"  na:         {zg.opis_czasu(sekundy)} (do {zg.iso(do)}), po {zg.opis_czasu(bezczynnosc)} bez działań gasną same")
    pisz(f"  profil:     {profil}; każde działanie zatwierdzasz w rozmowie (approvals manual, bez stałych zgód)")
    if plan is not None:
        stan = "nowy" if plan.nowy else ("odświeżony: " + ", ".join(plan.zmiany)) if plan.zmiany else "bez zmian"
        pisz(f"              {stan}; model z {plan.model_z}; bez terminala, plików i innych agentów")
        if plan.zmiany:
            pisz("              działająca brama Jarva zrestartuje się, żeby zobaczyć profil (rozmowy w toku "
                 "przerwą się na kilka sekund)")
    pisz(f"  sterownik:  cua-driver-rs {pk.WERSJA} ({sterownik.podpis or 'suma z przeglądu'}), telemetria wyłączona")
    pisz("  poza zasięgiem: pełny ekran, inne aplikacje, okna administratora, terminale, schowek, zrzut ekranu, "
         "zamykanie programów, logowanie, płatności i wysyłka")
    try:
        odp = (wejscie or input)("Wpisz TAK, żeby włączyć ręce: ")
    except EOFError:
        odp = ""
    if odp.strip().casefold() != "tak":
        pisz("Nie włączyłem rąk.")
        return 1
    if plan is not None:
        try:
            prof.zapisz(plan, u.dane)
            tekst = plik_profilu.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            pisz(f"BŁĄD: nie zapisałem profilu rąk {profil} ({e}).")
            return 1
        if problemy := bramka.problemy_profilu(tekst, plik=plik_profilu):  # zapisany profil czytamy tak jak bramka
            return _odrzuc_profil(pisz, profil, plik_profilu, problemy, pk.PROFIL)
    try:
        z = zg.utworz(pliki, lista, sekundy, platforma=plat, profil=profil, bezczynnosc=bezczynnosc,
                      teraz=teraz() if teraz else None)
    except zg.BladZgody as e:
        pisz(f"BŁĄD: {e}")
        return 1
    brama = None
    if plan is not None and plan.zmiany:
        try:
            brama = (restart_bramy or zrestartuj_brame)(u)
        except Exception as e:                    # noqa: BLE001 - kanał nadzorcy, moduł: rada zamiast awarii
            brama = f"blad: {e}"
    dz.zapisz(pliki.dziennik, "on", zgoda=z.id, profil=profil, aplikacje=z.nazwy(), do=zg.iso(z.wygasa),
              na=sekundy, platforma=plat, sterownik=pk.WERSJA, brama=brama.split(":")[0] if brama else None)
    pisz(f"Ręce włączone do {zg.iso(z.wygasa)} ({zg.opis_czasu(sekundy)}). Wyłączysz je od razu: jarvo komputer rece off")
    if brama and (opis := _opis_restartu(brama, profil)):
        pisz(opis)
    pisz(f"Rozmowa z rękami: jarvo chat --profil {profil}")
    if plan is None and (brak := ustawienia_profilu(tekst, pliki.manifest)):
        pisz(f"Uwaga: profil {profil} nie jest jeszcze ustawiony na ręce. W {plik_profilu} potrzebne: "
             + "; ".join(brak) + " (docs/KOMPUTER.md, K6).")
    if plat.startswith("macos"):
        pisz(st_mod.INSTRUKCJA_MACOS)
    return 0


def _sterownik(u, plat: str, pisz, bez_pobierania: bool, sprawdz_sterownik, zainstaluj):
    """Sprawdzony sterownik albo kod wyjścia (int). Brak programu: pobranie z sumą z manifestu natywnego (Windows,
    Linux) albo pobranie i instrukcja kopii CuaDriver.app do /Applications (macOS)."""
    st_mod, pk = _modul("sterownik"), pakiet()
    sprawdz = sprawdz_sterownik or (lambda: st_mod.sprawdz(u.program, plat))
    try:
        return sprawdz()
    except st_mod.BladSterownika as e:
        if e.kod != "brak_sterownika" or bez_pobierania:
            pisz(f"BŁĄD: {e}")
            return 1
    from . import manifest
    from .instalator import katalog_aplikacji
    try:
        narzedzia = manifest.wczytaj(katalog_aplikacji(u))
        wpis = manifest.plik(narzedzia, st_mod.NAZWA, plat)
        wersja = manifest.wersja(narzedzia, st_mod.NAZWA)
    except (OSError, ValueError, manifest.BrakNarzedzia) as e:
        pisz(f"Sterownika rąk nie ma w manifeście tej wersji Jarva ({e}). Ręce wymagają wpisu cua-driver "
             f"{pk.WERSJA} w vendor/natywne.yaml (przegląd w vendor/zrodla.yaml).")
        return 2
    if wersja != pk.WERSJA:
        pisz(f"Manifest ma cua-driver {wersja}, a bramka zna {pk.WERSJA} (sumy programu z przeglądu): odmowa.")
        return 2
    pisz(f"Pobieram sterownik rąk cua-driver-rs {wersja} ({wpis.get('rozmiar', 0) / 1e6:.0f} MB) z sumą sha256…")
    if zainstaluj is None:
        from . import pobieracz
        zainstaluj = lambda: pobieracz.zainstaluj(st_mod.NAZWA, wersja, wpis, u.program / "narzedzia",  # noqa: E731
                                                  u.cache / "pobrane")
    katalog = Path(zainstaluj())
    if plat.startswith("macos"):
        app = katalog / "CuaDriver.app"
        try:
            st_mod.sprawdz(u.program, plat, aplikacja_macos=app)
        except st_mod.BladSterownika as e:
            shutil.rmtree(katalog, ignore_errors=True)
            pisz(f"BŁĄD: pobrany sterownik nie przeszedł sprawdzenia ({e}); usunąłem go.")
            return 1
        pisz(st_mod.instrukcja_kopii_macos(app))
        return KOD_KROK_WLASCICIELA
    try:
        return sprawdz()
    except st_mod.BladSterownika as e:
        shutil.rmtree(katalog, ignore_errors=True)
        pisz(f"BŁĄD: pobrany sterownik nie przeszedł sprawdzenia ({e}); usunąłem go.")
        return 1


# ---------------------------------------------------------------- status

def zbierz_status(u, pliki, plat: str, env: dict, *, teraz=None, sprawdz_sterownik=None, podwyzszone=None) -> dict:
    zg, st_mod, proc, dz, bramka, pk = (_modul("zgoda"), _modul("sterownik"), _modul("procesy"), _modul("dziennik"),
                                        _modul("bramka"), pakiet())
    t = teraz() if teraz else None
    wynik: dict = {"platforma": plat, "wersja_sterownika": pk.WERSJA}
    try:
        z = zg.wczytaj(pliki, platforma=plat, teraz=t)
        wynik["zgoda"] = {"wlaczone": True, "id": z.id, "profil": z.profil, "aplikacje": z.nazwy(),
                          "do": zg.iso(z.wygasa), "pozostalo_s": z.pozostalo(t)}
        profil = z.profil
    except zg.BladZgody as e:
        wynik["zgoda"] = {"wlaczone": False, "kod": e.kod, "powod": str(e)}
        profil = pk.PROFIL
    try:
        st = (sprawdz_sterownik or (lambda: st_mod.sprawdz(u.program, plat)))()
        wynik["sterownik"] = {"gotowy": True, "program": str(st.program), "podpis": st.podpis or None}
    except st_mod.BladSterownika as e:
        wynik["sterownik"] = {"gotowy": False, "kod": e.kod, "powod": str(e)}
    wpisy = proc.Rejestr(pliki.procesy).wpisy(sprzataj=False)
    wynik["demony"] = [{"pid": w["bramka"]["pid"], "gotowy": bool(w.get("gotowy")), "zgoda": w.get("zgoda"),
                        "profil": w.get("profil")} for w in wpisy]
    plik_profilu = config_profilu(u, profil)
    try:
        tekst = plik_profilu.read_text(encoding="utf-8")
        problemy = bramka.problemy_profilu(tekst, plik=plik_profilu)
        wynik["profil"] = {"nazwa": profil, "rak_jarva": profil == pk.PROFIL, "plik": str(plik_profilu),
                           "stale_zgody": bramka.stale_zgody(tekst),
                           "zgody_wylaczone": any(o.kod != "stala_zgoda" for o in problemy),
                           "problemy": [{"kod": o.kod, "powod": o.powod} for o in problemy],
                           "brakuje": ustawienia_profilu(tekst, pliki.manifest),
                           "wtyczka_zgod": (plik_profilu.parent / "plugins" / "jarvo-zgody").exists()}
    except (OSError, UnicodeDecodeError):
        wynik["profil"] = {"nazwa": profil, "rak_jarva": profil == pk.PROFIL, "brak": str(plik_profilu)}
    wynik["administrator"] = bool((podwyzszone or st_mod.podwyzszone)())
    if plat.startswith("linux"):
        wynik["ekran"] = st_mod.ekran_linux(env)
    wynik["dziennik"] = dz.ostatnie(pliki.dziennik, 5)
    return wynik


def opis_statusu(s: dict) -> str:
    z = s["zgoda"]
    if z["wlaczone"]:
        minuty = max(0, z["pozostalo_s"]) // 60
        w = [f"Ręce: włączone do {z['do']} (zostało {minuty} min), profil {z['profil']}, aplikacje: "
             f"{', '.join(z['aplikacje'])}"]
    else:
        w = [f"Ręce: wyłączone ({z['powod']})"]
    st = s["sterownik"]
    w.append(f"Sterownik: cua-driver-rs {s['wersja_sterownika']} " + (
        f"gotowy ({st['podpis'] or 'suma zgodna'})" if st["gotowy"] else f"niegotowy: {st['powod']}"))
    if s["demony"]:
        w.append(f"Działające demony rąk: {len(s['demony'])} ({sum(d['gotowy'] for d in s['demony'])} gotowe)")
    p = s["profil"]
    if p.get("brak"):
        w.append(f"Profil {p['nazwa']}: nie ma go jeszcze ({p['brak']})"
                 + ("; jarvo komputer rece on założy go sam" if p.get("rak_jarva") else ""))
    elif p["problemy"]:
        w.append(f"Profil {p['nazwa']}: bramka nie wpuści rąk:")
        w += [f"  - {o['powod']}" for o in p["problemy"]]
    elif p["brakuje"]:
        w.append(f"Profil {p['nazwa']}: brakuje w config.yaml: {'; '.join(p['brakuje'])}")
    else:
        w.append(f"Profil {p['nazwa']}: gotowy (bounded, approvals manual, bez stałych zgód"
                 + (", wtyczka zgód" if p.get("wtyczka_zgod") else "") + "); rozmowa: jarvo chat --profil "
                 + p["nazwa"] + ("" if s["zgoda"]["wlaczone"] else " (bez zgody nic nie zrobi)"))
    if s.get("administrator"):
        w.append("Uwaga: ten proces ma prawa administratora, ręce nie wystartują.")
    if s.get("ekran"):
        w.append(f"Uwaga: {s['ekran']}")
    if s["platforma"].startswith("macos"):
        w.append("macOS: Dostępność i Nagrywanie ekranu dla „Cua Driver” włączasz sam w Ustawieniach systemowych.")
    for wpis in s["dziennik"]:
        w.append(f"  {wpis.get('czas', '')} {wpis.get('zdarzenie', '')} "
                 + " ".join(f"{k}={v}" for k, v in wpis.items() if k not in ("czas", "zdarzenie")))
    return "\n".join(w)


def pokaz_status(u, pliki, plat: str, env: dict, pisz, *, json_: bool, teraz=None, sprawdz_sterownik=None,
                 podwyzszone=None) -> int:
    s = zbierz_status(u, pliki, plat, env, teraz=teraz, sprawdz_sterownik=sprawdz_sterownik, podwyzszone=podwyzszone)
    pisz(json.dumps(s, ensure_ascii=False, indent=2) if json_ else opis_statusu(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
