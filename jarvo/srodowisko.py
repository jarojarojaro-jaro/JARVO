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

from .sciezki import WINDOWS, Uklad, krotka_sciezka

SEKRET = re.compile(r"TOKEN|KEY|SECRET|PASS|HASLO|KLUCZ|AUTH|COOKIE", re.I)   # takie nazwy nie trafiają do pliku

# zmienne, których nie przenosimy z otoczenia właściciela do procesów floty (inny Hermes, inny Python, cudze cache,
# konfiguracja ripgrepa właściciela w search_files Hermesa); porównanie bez wielkości liter, bo na Windows klucze
# os.environ są wielkimi literami (NPM_CONFIG_PREFIX)
OBCE = ("HERMES_HOME", "HERMES_GATEWAY_LOCK_DIR", "PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "CONDA_PREFIX",
        "UV_PROJECT_ENVIRONMENT", "NODE_OPTIONS", "NODE_PATH", "npm_config_prefix", "HERMES_YOLO_MODE",
        "TIRITH_ENABLED", "UV_INDEX_URL", "UV_EXTRA_INDEX_URL", "PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL",
        "RIPGREP_CONFIG_PATH", "JARVO_HERMES_BIN")
# zmienne otoczenia, które wyglądają na sekrety właściciela (klucze, tokeny, agent ssh), też nie przechodzą: flota dostaje
# swoje klucze z .env Jarva (mózg, Telegram), a nie z powłoki właściciela; wyjątki to zmienne pulpitu bez sekretu
POTRZEBNE_MIMO_NAZWY = ("XAUTHORITY",)
# srodowisko.json: część Jarva po przedrostku albo nazwie, do tego każdy klucz `env` narzędzi z narzedzia.json
PRZEDROSTKI_PLIKU = ("HERMES_", "JARVO_", "PYTHON", "UV_", "PLAYWRIGHT_", "PUPPETEER_", "npm_config_", "PIP_", "HF_",
                     "XDG_")
NAZWY_PLIKU = ("PATH", "NODE_PATH", "CHROME_PATH", "INDRA_OCR_MODEL_DIR", "TESSDATA_PREFIX")
# katalogi modeli w <dane>/jarvo/models (vendor/natywne.yaml, modele.<nazwa>.katalog) dla programów, które je czytają:
# jarvo-tts (Paradee, Matcha) i ocr.py (Indra); Tesseract osobno, bo bez swoich danych nie wraca do domyślnych
MODELE = {"JARVO_TTS_MODEL_DIR": "paradee", "JARVO_TTS_MATCHA_DIR": "matcha-pl",
          "INDRA_OCR_MODEL_DIR": "indra-ocr"}
TESSDATA = "tessdata-fast"

_OBCE = frozenset(o.upper() for o in OBCE)
_POTRZEBNE = frozenset(z.upper() for z in POTRZEBNE_MIMO_NAZWY)


def wczytaj_json(p: Path) -> dict:
    try:
        dane = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return dane if isinstance(dane, dict) else {}


def biezace(u: Uklad) -> dict:
    """`<program>/current.json`: {"app": <katalog kodu Jarva>, "hermes": <checkout Hermesa>, "wersja": …,
    "web_dist": <front panelu>}; z `web_dist` nadzorca ustawia panelowi HERMES_WEB_DIST, gdy jest w nim index.html."""
    return wczytaj_json(u.program / "current.json")


def narzedzia(u: Uklad) -> dict:
    """`<stan>/narzedzia.json`: {nazwa: {"wersja", "katalog", "bin": [katalogi do PATH], "env": {zmienna: wartość}}}."""
    return wczytaj_json(u.stan / "narzedzia.json")


def hermes_python(checkout: Path) -> Path:
    """Python środowiska Hermesa w checkoucie (uv sync zakłada .venv w katalogu projektu)."""
    return checkout / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")


def przechodzi(nazwa: str) -> bool:
    """Czy zmienna otoczenia właściciela przechodzi do procesów Jarva: nie jest obca (OBCE) ani nie wygląda na sekret
    (SEKRET, poza POTRZEBNE_MIMO_NAZWY). Bez wielkości liter."""
    n = nazwa.upper()
    return n not in _OBCE and (not SEKRET.search(nazwa) or n in _POTRZEBNE)


def srodowisko(u: Uklad, baza: dict | None = None, *, biez: dict | None = None,
               narz: dict | None = None) -> dict[str, str]:
    """Pełne środowisko procesu Jarva: `baza` (domyślnie os.environ) bez zmiennych obcych + katalogi i narzędzia."""
    env = {k: v for k, v in dict(os.environ if baza is None else baza).items() if przechodzi(k)}
    biez = biezace(u) if biez is None else biez
    narz = narzedzia(u) if narz is None else narz
    jd = u.jarvo_dane
    modele = jd / "models"
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
        "JARVO_MODELS_DIR": str(modele),
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
    env.update({zmienna: str(modele / katalog) for zmienna, katalog in MODELE.items()})
    tessdata = modele / TESSDATA
    if any(tessdata.glob("*.traineddata")):
        # tylko z zainstalowanymi językami: z pustym TESSDATA_PREFIX Tesseract (także systemowy) nie zna żadnego;
        # ścieżka ASCII, bo Tesseract ma wąskie API ścieżek (B13)
        env["TESSDATA_PREFIX"] = str(krotka_sciezka(tessdata))
    if WINDOWS:
        # shutil.which i cmd.exe szukają programu najpierw w bieżącym katalogu: obcy git.bat w projekcie wygrałby
        # z prawdziwym gitem; ta zmienna wyłącza to w Pythonie 3.12+ i w cmd.exe
        env["NoDefaultCurrentDirectoryInExePath"] = "1"
    else:
        env["XDG_CACHE_HOME"] = str(u.cache / "xdg")
    if biez.get("app"):
        env["JARVO_REPO"] = str(biez["app"])
    if biez.get("hermes"):
        checkout = Path(biez["hermes"])
        env["HERMES_SRC"] = str(checkout)
        hermes = checkout / ".venv" / ("Scripts/hermes.exe" if WINDOWS else "bin/hermes")
        if hermes.is_file():
            # bez pliku skrypty floty i panel wołają `hermes` z PATH albo `python -m hermes_cli.main` (W16)
            env["JARVO_HERMES_BIN"] = str(hermes)
    sciezka = [str(u.bin_floty)]
    for nazwa in sorted(narz):
        wpis = narz[nazwa] if isinstance(narz[nazwa], dict) else {}
        sciezka += [str(Path(k)) for k in wpis.get("bin") or []]
        env.update({str(k): str(v) for k, v in (wpis.get("env") or {}).items()})
    env["PATH"] = os.pathsep.join([*dict.fromkeys(sciezka), env.get("PATH", "")]).rstrip(os.pathsep)
    return env


def zapisz(u: Uklad, env: dict[str, str], *, narz: dict | None = None) -> Path:
    """`<stan>/srodowisko.json` bez sekretów (ścieżki i przełączniki): część Jarva (PRZEDROSTKI_PLIKU, NAZWY_PLIKU)
    i każdy klucz `env` narzędzi z `narz` (domyślnie narzedzia.json), np. GIT_CONFIG_NOSYSTEM, EXIFTOOL_HOME,
    PIXI_NO_TELEMETRY. Instalator podaje `env` z bazą z samych ustawień instalacji (ustawienia.json), więc PATH
    i zmienne właściciela nie trafiają do pliku, a drugi przebieg z innego okna niczego nie zmienia."""
    from .przenosne import zapisz_atomowo
    narz = narzedzia(u) if narz is None else narz
    z_narzedzi = {str(k) for w in narz.values() if isinstance(w, dict) for k in (w.get("env") or {})}
    jawne = {k: v for k, v in env.items()
             if (k.startswith(PRZEDROSTKI_PLIKU) or k in NAZWY_PLIKU or k in z_narzedzi) and not SEKRET.search(k)}
    cel = u.stan / "srodowisko.json"
    zapisz_atomowo(cel, json.dumps(jawne, ensure_ascii=False, indent=2) + "\n")
    return cel
