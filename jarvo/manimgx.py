"""ManimGX w Jarvie natywnie: program `manimgx` z instalacją przy pierwszym użyciu (docs/NATYWNIE.md M04, etap E11).

Odpowiednik nakładki sh z obrazu (infra/bin/manimgx); tu, a nie w infra/bin, bo jest tylko dla instalacji natywnej
(infra/bin trafia do obrazu i do jego klucza). Skille Wideografa wołają `manimgx inspect|render …`
(profiles/jarvo-wideo/skills/wideo/film-z-kodu/references/manimgx.md). W obrazie venv /opt/jarvo/venvs/manimgx
przychodzi z dodatkiem obrazu `manim` (JARVO_EXTRAS). Natywnie venv `manimgx` z manifestu (vendor/natywne.yaml,
`kiedy: przy-uzyciu`: ManimGX 0.1.1 na Pythonie 3.13 z locka infra/python/requirements-manimgx.txt z sumami sha256)
instaluje jarvo/przy_uzyciu.py, z postępem na stderr (ok. 85 MB pobrania na Windows, 64 MB na macOS, ok. 230 MB na
dysku; próba na Windows 11: 12 s), ale dopiero za zgodą (docs/NATYWNIE.md c3 pkt 9: „z paskiem i pytaniem”): w
terminalu właściciela pierwsze wywołanie pyta „Pobrać teraz? [t/N]”, a proces floty (agent, rutyna, karta kanbana;
znaczniki jak w jarvo/rece.py) albo wywołanie bez terminala dostaje kod 127 z tym, ile pobierze i jak zainstalować:
agent pyta właściciela w rozmowie i za jego zgodą woła `manimgx --jarvo-zainstaluj`. Także `--version` przed
instalacją niczego nie pobiera. Potem program przekazuje argumenty do `Scripts\\manimgx.exe` (macOS i Linux:
bin/manimgx) venvu, z MANIMGX_CACHE_DIR w `<dane>/jarvo/cache/manimgx` (układy tekstu i kroje, jak
/opt/data/jarvo/cache/manimgx w obrazie), i zwraca jego kod wyjścia. Katalog pliku z `render -o` zakłada przed
renderem (ManimGX sam tego nie robi).

Program w `<program>/bin-floty` zakłada `zainstaluj(bin_floty, python)`, jak infra/bin/agent_browser.zainstaluj
(krok „Programy floty” instalatora, Python 3.13 z instalacji): na Windows `manimgx.exe` = launcher distlib z koła
pip tego Pythona, wiersz #! i ten moduł w zipie jako __main__.py; na macOS i Linuksie dwa wiersze sh i ten sam zip
(agent_browser.program). Bez .cmd: cmd.exe przetwarzałby argumenty po swojemu. Program w zipie nie importuje pakietu
jarvo z siebie: kod Jarva bierze z JARVO_REPO albo `<program>/current.json`. Sama biblioteka standardowa.

    manimgx --version | inspect scena.py Scena | render scena.py Scena -r 1280x720 --fps 30 -o out/scena.mp4
    manimgx --jarvo-stan          # JSON: gdzie venv, czy gotowy, ile pobierze (bez instalacji i bez uruchamiania)
    manimgx --jarvo-zainstaluj    # instalacja przy pierwszym użyciu (za zgodą właściciela), pasek na stderr
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

WINDOWS = os.name == "nt"
VENV = "manimgx"                                  # wpis venvy.manimgx w vendor/natywne.yaml
VENV_KONTENER = Path("/opt/jarvo/venvs/manimgx")
NAGLOWEK_SH = "# Jarvo: ManimGX (jarvo/manimgx.py); plik pisze instalacja Jarva, zmiany znikną"


class BladManimgx(RuntimeError):
    """`do_instalacji`: instalacja natywna bez venvu, który da się teraz zainstalować (za zgodą); `opis` = co pobierze,
    `rada` = jak zainstalować bez terminala właściciela."""

    def __init__(self, opis: str, rada: str = "", *, do_instalacji: bool = False):
        super().__init__(f"{opis} {rada}".strip())
        self.opis, self.rada, self.do_instalacji = opis, rada, do_instalacji


def _czytaj_json(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def korzen_instalacji(env: dict) -> Path | None:
    """Korzeń instalacji natywnej: JARVO_ROOT (procesy floty), a bez niego katalog nad `<program>/bin-floty`, z którego
    uruchomiono program (sys.argv[0]); musi mieć `program/current.json`. Bez resolve(): krótka nazwa 8.3 (c1)."""
    kandydaci = []
    if env.get("JARVO_ROOT"):
        kandydaci.append(Path(env["JARVO_ROOT"]))
    if sys.argv and sys.argv[0]:
        kandydaci.append(Path(os.path.abspath(sys.argv[0])).parent.parent.parent)
    for k in kandydaci:
        if (k / "program" / "current.json").is_file():
            return k
    return None


def przy_uzyciu(env: dict):
    """(jarvo/przy_uzyciu.py aktywnej wersji Jarva, układ) w instalacji natywnej, inaczej (None, None)."""
    korzen = korzen_instalacji(env)
    if korzen is None:
        return None, None
    sciezka_app = str(env.get("JARVO_REPO") or _czytaj_json(korzen / "program" / "current.json").get("app") or "")
    app = Path(sciezka_app)
    if not os.path.isabs(sciezka_app) or not (app / "jarvo" / "przy_uzyciu.py").is_file():
        return None, None                         # nigdy kod z katalogu bieżącego (pusta albo względna ścieżka)
    if "jarvo" not in sys.modules:                # pakiet z kodu instalacji, bez dopisywania go do sys.path
        spec = importlib.util.spec_from_file_location("jarvo", app / "jarvo" / "__init__.py",
                                                      submodule_search_locations=[str(app / "jarvo")])
        modul = importlib.util.module_from_spec(spec)
        sys.modules["jarvo"] = modul
        spec.loader.exec_module(modul)
    try:
        pu = importlib.import_module("jarvo.przy_uzyciu")
    except ImportError:
        return None, None
    return pu, pu.uklad({**env, "JARVO_ROOT": str(korzen)})


def program_venvu(katalog: Path) -> Path:
    return Path(katalog) / ("Scripts/manimgx.exe" if WINDOWS else "bin/manimgx")


def _log(tekst: str) -> None:
    print(f"manimgx: {tekst}", file=sys.stderr, flush=True)


def _przed_instalacja(pu, u) -> BladManimgx:
    """Błąd „jeszcze nie zainstalowany” z tym, ile pobierze pierwsza instalacja (manifest tej wersji, bez sieci)."""
    try:
        o = pu.opis_venvu(u, VENV)
    except pu.BladPrzyUzyciu:
        o = {}
    opis = ("ManimGX nie jest jeszcze zainstalowany na tym komputerze: pierwsza instalacja pobierze ok. "
            f"{o.get('pobranie_mb') or '?'} MB (ok. {o.get('venv_mb') or '?'} MB na dysku, zwykle 1–2 min).")
    rada = ("Zapytaj właściciela, czy pobrać; za jego zgodą: manimgx --jarvo-zainstaluj (limit czasu polecenia co "
            "najmniej 300 s), potem to samo polecenie jeszcze raz. Bez zgody wybierz inny silnik.")
    return BladManimgx(opis, rada, do_instalacji=True)


def znajdz(env: dict, instaluj: bool = False) -> Path:
    """Program manimgx venvu. Instalacja natywna: venv dla locka tej wersji Jarva (po aktualizacji nowy, a nie stary
    ze zmiennej sprzed restartu bramy); brak venvu = BladManimgx(do_instalacji=True), a z `instaluj` (zgoda już
    jest) instalacja teraz. Poza nią: JARVO_MANIMGX_VENV, obok JARVO_MANIMGX_PYTHON, obraz Jarva."""
    pu, u = przy_uzyciu(env)
    if pu is not None:
        gotowy = pu.gotowy_venv(u, VENV)
        if gotowy is None:
            if not instaluj:
                raise _przed_instalacja(pu, u)
            try:
                gotowy = pu.venv(u, VENV, log=_log)
            except pu.BladPrzyUzyciu as e:
                raise BladManimgx(str(e)) from None
        p = program_venvu(Path(gotowy["katalog"]))
        if not p.is_file():
            raise BladManimgx(f"w venvie {gotowy['katalog']} nie ma programu manimgx (uruchom instalację Jarva jeszcze "
                              "raz)")
        return p
    kandydaci = []
    if env.get("JARVO_MANIMGX_VENV"):
        kandydaci.append(program_venvu(Path(env["JARVO_MANIMGX_VENV"])))
    if env.get("JARVO_MANIMGX_PYTHON"):
        kandydaci.append(Path(env["JARVO_MANIMGX_PYTHON"]).with_name("manimgx.exe" if WINDOWS else "manimgx"))
    kandydaci.append(VENV_KONTENER / "bin" / "manimgx")
    for p in kandydaci:
        if p.is_file():
            return p
    raise BladManimgx("brak ManimGX: w obrazie to dodatek `manim` (JARVO_EXTRAS=\"manim\" w compose/.env, potem "
                      "deploy.sh --rebuild); w instalacji natywnej instaluje go za zgodą właściciela program manimgx "
                      "(manimgx --jarvo-zainstaluj)")


def katalog_cache(env: dict) -> Path:
    """MANIMGX_CACHE_DIR: z otoczenia, `<dane>/jarvo/cache/manimgx` (JARVO_DATA_DIR albo instalacja), w obrazie
    zapisywalny /opt/data/jarvo, w ostateczności ~/.cache/manimgx."""
    if env.get("MANIMGX_CACHE_DIR"):
        return Path(env["MANIMGX_CACHE_DIR"])
    if env.get("JARVO_DATA_DIR"):
        return Path(env["JARVO_DATA_DIR"]) / "cache" / "manimgx"
    _pu, u = przy_uzyciu(env)
    if u is not None:
        return u.jarvo_dane / "cache" / "manimgx"
    if Path("/opt/data/jarvo").is_dir() and os.access("/opt/data/jarvo", os.W_OK):
        return Path("/opt/data/jarvo/cache/manimgx")
    return Path(env.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "manimgx"


def katalog_wyniku(args: list[str]) -> Path | None:
    """Katalog pliku z `render … -o out/szkic/scena.mp4`: ManimGX go nie zakłada (Windows: „os error 3”), a skille
    podają ścieżki z podkatalogami out/."""
    if not args or args[0] != "render":
        return None
    for i, a in enumerate(args):
        if a in ("-o", "--output") and i + 1 < len(args):
            return Path(args[i + 1]).parent
        if a.startswith("--output="):
            return Path(a.split("=", 1)[1]).parent
    return None


def stan(env: dict) -> dict:
    """Bez instalacji i bez uruchamiania: program albo co pobierze pierwsze wywołanie."""
    try:
        return {"program": str(znajdz(env, instaluj=False)), "gotowy": True, "cache": str(katalog_cache(env))}
    except BladManimgx as e:
        wynik = {"program": None, "gotowy": False, "powod": str(e), "cache": str(katalog_cache(env))}
        pu, u = przy_uzyciu(env)
        if pu is not None:
            try:
                wynik["przy_uzyciu"] = pu.opis_venvu(u, VENV)
            except pu.BladPrzyUzyciu:
                pass
        return wynik


def zgoda_w_terminalu(env: dict, blad: BladManimgx, wejscie=None, wyjscie=None) -> bool:
    """Pytanie przed pobraniem (c3 pkt 9), tylko w terminalu właściciela. Bez terminala albo w procesie floty (agent,
    rutyna, karta kanbana: jarvo/rece.py proces_floty) bez pytania: wtedy pyta agent w rozmowie i woła
    `manimgx --jarvo-zainstaluj`."""
    wejscie = sys.stdin if wejscie is None else wejscie
    wyjscie = sys.stderr if wyjscie is None else wyjscie
    pu, u = przy_uzyciu(env)
    if pu is None or u is None or not pu.terminal(wejscie):    # NUL na Windows też „isatty”: tylko prawdziwa konsola
        return False
    try:
        flota = importlib.import_module("jarvo.rece").proces_floty(env, u.dane)
    except (ImportError, AttributeError):
        return False                              # bez znaczników floty nie wiemy, kto pyta: bez pytania
    if flota is not None:
        return False
    print(f"manimgx: {blad.opis} Pobrać teraz? [t/N] ", end="", file=wyjscie, flush=True)
    return (wejscie.readline() or "").strip().lower() in ("t", "tak", "y", "yes")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    env = dict(os.environ)
    if args[:1] == ["--jarvo-stan"]:
        print(json.dumps(stan(env), ensure_ascii=False, indent=2))
        return 0
    if args[:1] == ["--jarvo-zainstaluj"]:        # zgoda właściciela już jest (agent zapytał w rozmowie)
        try:
            program = znajdz(env, instaluj=True)
        except BladManimgx as e:
            print(f"manimgx: {e}", file=sys.stderr)
            return 127
        print(f"ManimGX gotowy: {program}")
        return 0
    try:
        program = znajdz(env)
    except BladManimgx as e:
        if not (e.do_instalacji and zgoda_w_terminalu(env, e)):
            print(f"manimgx: {e}", file=sys.stderr)
            return 127
        try:
            program = znajdz(env, instaluj=True)
        except BladManimgx as e2:
            print(f"manimgx: {e2}", file=sys.stderr)
            return 127
    cache = katalog_cache(env)
    env["MANIMGX_CACHE_DIR"] = str(cache)
    for katalog in (cache, katalog_wyniku(args)):
        if katalog is not None and str(katalog) not in ("", "."):
            try:
                katalog.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
    return uruchom(program, args, env)


def uruchom(program: Path, args: list[str], env: dict) -> int:
    """POSIX: exec (sygnały i kod wyjścia wprost). Windows: proces potomny i jego kod; Ctrl+C dostaje cała konsola,
    a decyduje manimgx."""
    if not WINDOWS:
        sys.stdout.flush()
        sys.stderr.flush()
        os.execve(str(program), [str(program), *args], env)
    stary = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        return subprocess.call([str(program), *args], env=env)
    except OSError as e:
        print(f"manimgx: nie uruchomię {program}: {e.strerror or e}", file=sys.stderr)
        return 126
    finally:
        signal.signal(signal.SIGINT, stary)


# ------------------------------------------------------------------ program w bin-floty

def _agent_browser():
    """infra/bin/agent_browser.py tej wersji (launcher distlib, zapis programu): ten sam sposób budowy programu."""
    app = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    spec = importlib.util.spec_from_file_location("jarvo_agent_browser_program",
                                                  app / "infra" / "bin" / "agent_browser.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def tresc_programu(python: Path, *, windows: bool = WINDOWS) -> bytes:
    return _agent_browser().program(python, Path(__file__).read_bytes(), windows=windows, opis=NAGLOWEK_SH)


def zainstaluj(bin_floty: Path, python: Path) -> list[Path]:
    """Program `manimgx` (Windows: manimgx.exe) w bin-floty dla Pythona `python` z instalacji (python313, bez venvu).
    Zwraca zmienione pliki; ta sama treść = bez zapisu (drugi przebieg instalacji niczego nie zmienia)."""
    ab = _agent_browser()
    cel = Path(bin_floty) / ("manimgx.exe" if WINDOWS else "manimgx")
    tresc = ab.program(python, Path(__file__).read_bytes(), opis=NAGLOWEK_SH)
    return [cel] if ab._zapisz(cel, tresc, 0o755) else []


if __name__ == "__main__":
    sys.exit(main())
