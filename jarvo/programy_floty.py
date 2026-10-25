"""Programy floty Jarva w `<program>/bin-floty` (docs/NATYWNIE.md: S01, F12, V01, V05, V11, E05).

W kontenerze jarvo-tts, jarvo-stt i jarvo-klucz to skrypty z infra/bin z shebangiem /opt/jarvo/venv/bin/python,
a python3 i tesseract są w PATH obrazu. Natywnie Windows nie uruchomi skryptu z shebangiem (WinError 193), a build
floty wpisuje do poleceń bramy pełną ścieżkę `<program>/bin-floty/jarvo-stt.exe` (HERMES_LOCAL_STT_COMMAND)
i `jarvo-tts.exe` (tts.providers.matcha.command). Ten moduł to wspólne wejście tych programów:

  Windows  instalator pakuje ten plik do koła `jarvo_programy_floty` i instaluje je w venvie narzędzi; uv robi
           z punktów wejścia programy .exe (trampoliny ze ścieżką Pythona venvu), a instalator kopiuje je do
           bin-floty (jarvo/bin_floty.py),
  POSIX    bin-floty dostaje kopię tego pliku (jarvo_programy_floty.py) i krótkie skrypty sh, które wołają go
           Pythonem venvu narzędzi (python3 i tesseract to samo `exec` do programu).

jarvo-tts, jarvo-stt i jarvo-klucz uruchamiają skrypt `<app>/infra/bin/<nazwa>` aktywnej wersji Jarva
(`<program>/current.json`) w tym samym procesie (runpy), więc lektor i rozpoznawanie mowy idą za aktualizacją bez
nowych programów. python3 (Windows) to Python venvu narzędzi z tymi samymi argumentami; tesseract to program
z instalacji pixi (`<stan>/narzedzia.json`, wpis tesseract, pole program). Uruchomione poza procesami Jarva (np.
z terminala właściciela pełną ścieżką) biorą brakujące zmienne z `<stan>/srodowisko.json` (modele, PATH narzędzi),
nigdy nie nadpisując tych, które już są. Moduł działa na bibliotece standardowej, bez importu pakietu jarvo.
"""
from __future__ import annotations

import json
import os
import runpy
import signal
import subprocess
import sys
from pathlib import Path

SKRYPTY = ("jarvo-tts", "jarvo-stt", "jarvo-klucz")       # skrypty z infra/bin aktywnej wersji
PROGRAMY = ("python3", "tesseract")                        # programy z instalacji wołane z tymi samymi argumentami
POZIOMY = 5                                                # tyle katalogów w górę szukamy current.json


class BladProgramu(RuntimeError):
    """Nie da się ustalić, co uruchomić (komunikat po polsku)."""


def _czytaj_json(p: Path) -> dict:
    try:
        dane = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return dane if isinstance(dane, dict) else {}


def katalog_programu(*poczatki: str) -> Path:
    """`<program>` instalacji: pierwszy katalog nad programem (sys.argv[0], potem ten plik) z current.json. Bez
    resolve(): krótka nazwa 8.3 `<program>` zostaje (c1)."""
    for start in (*poczatki, sys.argv[0] if sys.argv and sys.argv[0] else "", __file__):
        if not start:
            continue
        p = Path(os.path.abspath(start)).parent
        for _ in range(POZIOMY):
            if (p / "current.json").is_file():
                return p
            if p.parent == p:
                break
            p = p.parent
    raise BladProgramu("nie znalazłem <program>/current.json nad tym programem: Jarvo nie jest zainstalowane "
                       "w tym miejscu (uruchom instalację jeszcze raz)")


def uzupelnij_srodowisko(program: Path, env: dict | None = None) -> dict:
    """Zmienne Jarva z `<stan>/srodowisko.json`, których brak w `env` (domyślnie os.environ); katalogi z PATH Jarva,
    których nie ma w PATH, idą na początek. Zwraca `env`."""
    env = os.environ if env is None else env
    jarva = _czytaj_json(Path(program).parent / "stan" / "srodowisko.json")
    obecne_nazwy = {k.upper() if os.name == "nt" else k for k in env}      # Windows: bez wielkości liter
    for klucz, wartosc in jarva.items():
        if not isinstance(wartosc, str) or klucz.upper() == "PATH":
            continue
        if (klucz.upper() if os.name == "nt" else klucz) not in obecne_nazwy:
            env[klucz] = wartosc
    sciezka_jarva = next((v for k, v in jarva.items() if k.upper() == "PATH" and isinstance(v, str)), "")
    if sciezka_jarva:
        nazwa = next((k for k in env if k.upper() == "PATH"), "PATH")
        obecne = [x for x in str(env.get(nazwa) or "").split(os.pathsep) if x]
        klucze = {os.path.normcase(x) for x in obecne}
        brak = [x for x in sciezka_jarva.split(os.pathsep) if x and os.path.normcase(x) not in klucze]
        if brak:
            env[nazwa] = os.pathsep.join([*brak, *obecne])
    return env


def skrypt(nazwa: str, program: Path) -> Path:
    """`<app>/infra/bin/<nazwa>` aktywnej wersji Jarva."""
    app = _czytaj_json(Path(program) / "current.json").get("app")
    if not app:
        raise BladProgramu(f"{Path(program) / 'current.json'} nie wskazuje kodu Jarva (pole app)")
    p = Path(app) / "infra" / "bin" / nazwa
    if not p.is_file():
        raise BladProgramu(f"brak {p} w kodzie Jarva")
    return p


def program_narzedzia(nazwa: str, program: Path) -> str:
    """Program z instalacji: python3 = Python venvu narzędzi (venv-narzedzia), tesseract = wpis tesseract
    (`<stan>/narzedzia.json`, pole program)."""
    narz = _czytaj_json(Path(program).parent / "stan" / "narzedzia.json")
    wpis = narz.get("venv-narzedzia" if nazwa == "python3" else nazwa)
    sciezka = (wpis or {}).get("python" if nazwa == "python3" else "program") if isinstance(wpis, dict) else None
    if nazwa == "python3" and not sciezka:
        sciezka = sys.executable
    if not sciezka or not Path(sciezka).is_file():
        raise BladProgramu(f"{nazwa}: nie ma go w tej instalacji ({Path(program).parent / 'stan' / 'narzedzia.json'})")
    return str(sciezka)


def _blad(nazwa: str, e: Exception) -> int:
    print(f"{nazwa}: {e}", file=sys.stderr)
    return 1


def uruchom_skrypt(nazwa: str, argv: list[str]) -> int:
    """Skrypt infra/bin w tym procesie (ten sam Python venvu narzędzi), z argumentami `argv`."""
    try:
        program = katalog_programu()
        p = skrypt(nazwa, program)
    except BladProgramu as e:
        return _blad(nazwa, e)
    uzupelnij_srodowisko(program)
    sys.argv = [str(p), *argv]
    try:
        runpy.run_path(str(p), run_name="__main__")
    except SystemExit as e:                      # skrypty kończą się sys.exit(main())
        kod = e.code
        if kod is None:
            return 0
        if isinstance(kod, int):
            return kod
        print(kod, file=sys.stderr)
        return 1
    return 0


def uruchom_program(nazwa: str, argv: list[str]) -> int:
    """Program z instalacji jako proces potomny z tymi samymi argumentami, wejściem i wyjściem; kod wyjścia wraca.
    Ctrl+C dostaje cała konsola: ten proces czeka, aż program zdecyduje sam."""
    try:
        program = katalog_programu()
        cel = program_narzedzia(nazwa, program)
    except BladProgramu as e:
        return _blad(nazwa, e)
    env = uzupelnij_srodowisko(program, dict(os.environ))
    stary = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        return subprocess.call([cel, *argv], env=env)
    except OSError as e:
        return _blad(nazwa, e)
    finally:
        signal.signal(signal.SIGINT, stary)


def uruchom(nazwa: str, argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if nazwa in SKRYPTY:
        return uruchom_skrypt(nazwa, argv)
    if nazwa in PROGRAMY:
        return uruchom_program(nazwa, argv)
    return _blad(nazwa, BladProgramu(f"nieznany program floty (są: {', '.join(SKRYPTY + PROGRAMY)})"))


# punkty wejścia koła (Windows: trampoliny uv `<nazwa>.exe`)
def jarvo_tts() -> int:
    return uruchom("jarvo-tts")


def jarvo_stt() -> int:
    return uruchom("jarvo-stt")


def jarvo_klucz() -> int:
    return uruchom("jarvo-klucz")


def python3() -> int:
    return uruchom("python3")


def tesseract() -> int:
    return uruchom("tesseract")


# punkty wejścia koła → funkcje; program w bin-floty → punkt wejścia (uv odrzuca nazwę `python3`: „Scripts must not
# use the reserved name”, a w Scripts venvu narzędzi, który jest w PATH floty, nie chcemy drugiego python3 i tesseract)
PUNKTY_WEJSCIA = {"jarvo-tts": "jarvo_tts", "jarvo-stt": "jarvo_stt", "jarvo-klucz": "jarvo_klucz",
                  "jarvo-python3": "python3", "jarvo-tesseract": "tesseract"}
WEJSCIE_PROGRAMU = {"python3": "jarvo-python3", "tesseract": "jarvo-tesseract", "jarvo-tts": "jarvo-tts",
                    "jarvo-stt": "jarvo-stt", "jarvo-klucz": "jarvo-klucz"}


def main(argv: list[str] | None = None) -> int:
    """POSIX: `python jarvo_programy_floty.py <nazwa> [argumenty…]` (skrypty sh w bin-floty)."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(f"użycie: jarvo_programy_floty.py <{'|'.join(WEJSCIE_PROGRAMU)}> [argumenty…]", file=sys.stderr)
        return 2
    return uruchom(argv[0], argv[1:])


if __name__ == "__main__":
    sys.exit(main())
