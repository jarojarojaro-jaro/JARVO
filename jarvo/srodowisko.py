"""Środowisko procesów Jarva (docs/NATYWNIE.md, S11 i c1): jedno źródło zmiennych dla bramy, panelu, `jarvo chat`
i `jarvo doctor`, żeby żadna zmienna nie wychodziła dopiero w jednym narzędziu.

W kontenerze te zmienne ustawiał Dockerfile i compose. Natywnie instalator zapisuje stan narzędzi
(`<stan>/narzedzia.json`) i bieżącą wersję (`<program>/current.json`), a `srodowisko()` składa z nich słownik.
Zmienne ustawiamy tylko w procesach Jarva, nigdy w zmiennych użytkownika: odinstalowanie nie zostawia śladów,
a prywatny Hermes właściciela nie widzi Jarva.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .sciezki import WINDOWS, Uklad

SEKRET = re.compile(r"TOKEN|KEY|SECRET|PASS|HASLO|KLUCZ|AUTH|COOKIE", re.I)   # takie nazwy nie trafiają do pliku

# zmienne, których nie przenosimy z otoczenia właściciela do procesów floty (inny Hermes, inny Python, cudze cache)
OBCE = ("HERMES_HOME", "HERMES_GATEWAY_LOCK_DIR", "PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "CONDA_PREFIX",
        "UV_PROJECT_ENVIRONMENT", "NODE_OPTIONS", "NODE_PATH", "npm_config_prefix", "HERMES_YOLO_MODE")


def wczytaj_json(p: Path) -> dict:
    try:
        dane = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return dane if isinstance(dane, dict) else {}


def biezace(u: Uklad) -> dict:
    """`<program>/current.json`: {"app": <katalog kodu Jarva>, "hermes": <checkout Hermesa>, "wersja": …}."""
    return wczytaj_json(u.program / "current.json")


def narzedzia(u: Uklad) -> dict:
    """`<stan>/narzedzia.json`: {nazwa: {"wersja", "katalog", "bin": [katalogi do PATH], "env": {zmienna: wartość}}}."""
    return wczytaj_json(u.stan / "narzedzia.json")


def hermes_python(checkout: Path) -> Path:
    """Python środowiska Hermesa w checkoucie (uv sync zakłada .venv w katalogu projektu)."""
    return checkout / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")


def srodowisko(u: Uklad, baza: dict | None = None, *, biez: dict | None = None,
               narz: dict | None = None) -> dict[str, str]:
    """Pełne środowisko procesu Jarva: `baza` (domyślnie os.environ) bez zmiennych obcych + katalogi i narzędzia."""
    env = {k: v for k, v in dict(os.environ if baza is None else baza).items() if k not in OBCE}
    biez = biezace(u) if biez is None else biez
    narz = narzedzia(u) if narz is None else narz
    jd = u.jarvo_dane
    env.update({
        "HERMES_HOME": str(u.dane),
        "HERMES_GATEWAY_LOCK_DIR": str(u.stan / "gateway-locks"),      # jedna brama Jarva, osobno od prywatnego Hermesa
        "HERMES_WRITE_SAFE_ROOT": str(u.dane),
        "HERMES_DISABLE_LAZY_INSTALLS": "1",                           # nic bez pinu i sumy (H03)
        "JARVO_ROOT": str(u.root),
        "JARVO_BUILD_DIR": str(u.build),
        "JARVO_DATA_DIR": str(jd),
        "JARVO_KNOWLEDGE_DIR": str(jd / "knowledge"),
        "JARVO_MISSIONS_DIR": str(jd / "missions"),
        "JARVO_MODELS_DIR": str(jd / "models"),
        "JARVO_NARZEDZIA": str(u.program / "narzedzia-floty"),
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "1",
        "PUPPETEER_SKIP_DOWNLOAD": "1",
        "UV_CACHE_DIR": str(u.cache / "uv"),
        "UV_PYTHON_INSTALL_DIR": str(u.program / "python"),
        "npm_config_cache": str(u.cache / "npm"),
        "PIP_CACHE_DIR": str(u.cache / "pip"),
        "HF_HOME": str(u.cache / "huggingface"),
    })
    if not WINDOWS:
        env["XDG_CACHE_HOME"] = str(u.cache / "xdg")
    if biez.get("app"):
        env["JARVO_REPO"] = str(biez["app"])
    if biez.get("hermes"):
        checkout = Path(biez["hermes"])
        env["HERMES_SRC"] = str(checkout)
        hermes = checkout / ".venv" / ("Scripts/hermes.exe" if WINDOWS else "bin/hermes")
        env["JARVO_HERMES_BIN"] = str(hermes)
    sciezka = [str(u.bin_floty)]
    for nazwa in sorted(narz):
        wpis = narz[nazwa] if isinstance(narz[nazwa], dict) else {}
        sciezka += [str(Path(k)) for k in wpis.get("bin") or []]
        env.update({str(k): str(v) for k, v in (wpis.get("env") or {}).items()})
    env["PATH"] = os.pathsep.join([*dict.fromkeys(sciezka), env.get("PATH", "")]).rstrip(os.pathsep)
    return env


def zapisz(u: Uklad, env: dict[str, str]) -> Path:
    """`<stan>/srodowisko.json` (bez sekretów: tylko ścieżki i przełączniki) dla nadzorcy, `jarvo chat` i doctor."""
    from .przenosne import zapisz_atomowo
    jawne = {k: v for k, v in env.items() if (k.startswith(("HERMES_", "JARVO_", "PYTHON", "UV_", "PLAYWRIGHT_",
                                                             "PUPPETEER_", "npm_config_", "PIP_", "HF_", "XDG_"))
                                              or k in ("PATH", "NODE_PATH", "CHROME_PATH"))
             and not SEKRET.search(k)}
    cel = u.stan / "srodowisko.json"
    zapisz_atomowo(cel, json.dumps(jawne, ensure_ascii=False, indent=2) + "\n")
    return cel
