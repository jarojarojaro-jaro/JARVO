"""Start aplikacji Jarvo (docs/HQ.md „Ekran startu”): właściciel z USER.md i gotowość do `GET /app`.

- **Właściciel**: `knowledge/user/USER.md` (szablon skillu `onboarding-interview`): „Imię / jak się zwracać” i nazwa
  firmy (tekst przed „→” w „Firma / marki”). Pusty plik albo pola = pusty napis; ekran startu mówi wtedy „Cześć,
  jestem Jarvo” i pokazuje „Poznajmy się”.
- **Gotowość**: `{model: {dostawca, polaczony, sposob}, brama, profil_wlasciciela}`. Same nazwy i wartości logiczne:
  żadna wartość klucza ani tokenu nie wychodzi z tego modułu (ani do odpowiedzi, ani do dziennika).
  - `model.dostawca` z `config.yaml` profilu Jarva (`model.provider`).
  - `model.polaczony`: status logowania Hermesa (`hermes_cli.auth.get_auth_status`, z założenia tylko do odczytu:
    nie odświeża ani nie zapisuje poświadczeń) liczony w osobnym procesie z `HERMES_HOME` = katalog profilu, więc
    nie przełącza procesu dashboardu w tryb wielu profili i nie dotyka jego zmiennych. Proces drukuje tylko dwie
    wartości logiczne. Dostawca na klucz: także nazwa zmiennej klucza obecna i niepusta w `.env` profilu albo w
    środowisku (wartości nie czytamy na zewnątrz). Dostawca własny (`custom`): adres `model.base_url` w configu.
    Bez Hermesa (testy na hoście) dla OAuth zostaje obecność pliku `auth.json` profilu. Wynik w pamięci 30 s;
    starszy wynik wraca od razu, a nowy liczy się w tle (`GET /app` nie czeka na proces statusu).
  - `brama`: `ok`, gdy `GET {API_BASE}/health` odpowiada 200; inaczej `startuje`, gdy widać, że brama właśnie wstaje:
    ostatni start mniej niż 2 min temu (`gateway-starts.log`), ostatnia udana próba mniej niż 60 s temu (restart),
    albo `gateway_state.json` mówi „ma działać” (`desired_state: running`) i zmienił się mniej niż 2 min temu, albo
    stan to `starting`/`restarting`; w pozostałych przypadkach `niedostepna`.
  - `profil_wlasciciela`: w USER.md jest imię.
Testy: tests/test_aplikacja.py.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

BRAMA_MLODA_S = 120.0
BRAMA_PO_OK_S = 60.0
MODEL_CACHE_S = 30.0
BRAMA_CACHE_S = 3.0
STATUS_TIMEOUT_S = 12.0
FIRMA_MAKS = 60
IMIE_MAKS = 40

# zmienne kluczy dostawców spoza rejestru Hermesa (local-up.sh: openrouter, commandcode); rejestr ma resztę
KLUCZE_DOSTAWCOW = {
    "openrouter": ("OPENROUTER_API_KEY",),
    "commandcode": ("COMMANDCODE_API_KEY",),
    "commandcode-anthropic": ("COMMANDCODE_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN"),
    "openai": ("OPENAI_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "xai": ("XAI_API_KEY",),
}
OAUTH_ZNANI = ("openai-codex", "nous", "xai-oauth", "qwen-oauth", "google-gemini-cli", "copilot", "spotify")

# osobny proces z HERMES_HOME profilu: tylko dwie wartości logiczne i rodzaj logowania na wyjściu
SKRYPT_STATUSU = r"""
import json, sys
p = sys.argv[1]
out = {"sposob": "brak", "polaczony": False, "zmienne": []}
try:
    from hermes_cli import auth
    c = auth._registry_lookup(p)
    typ = getattr(c, "auth_type", "") or ""
    if p in getattr(auth, "OAUTH_PROVIDER_FLOWS", {}) or typ.startswith("oauth"):
        out["sposob"] = "oauth"
    elif typ == "api_key":
        out["sposob"] = "klucz"
        out["zmienne"] = [str(z) for z in (getattr(c, "api_key_env_vars", ()) or ())][:6]
    s = auth.get_auth_status(p) or {}
    out["polaczony"] = bool(s.get("logged_in") or s.get("configured"))
except Exception as e:
    out["blad"] = type(e).__name__
print(json.dumps(out))
"""


# ----------------------------------------------------------------------------------------------- właściciel
def _pole(tekst: str, etykieta: str) -> str | None:
    """Wartość pola „- <etykieta>: …”; None = nie ma takiej linii, "" = linia jest, pole puste."""
    for linia in tekst.splitlines():
        s = linia.strip()
        if s.startswith("-") and s[1:].lstrip().lower().startswith(etykieta.lower()):
            wartosc = s[1:].lstrip()[len(etykieta):].lstrip(" :").strip()
            if wartosc.startswith("<") and wartosc.endswith(">"):     # niewypełniony znacznik szablonu
                return ""
            return wartosc
    return None


def _czysty(s: str, maks: int) -> str:
    s = re.sub(r"[\x00-\x1f\x7f*_`#<>\[\]]", "", s).strip(" .,;")
    return s[:maks].strip()


def wlasciciel(sciezka: Path | str) -> dict:
    """{imie, firma} z USER.md; brak pliku albo puste pola = puste napisy."""
    try:
        tekst = Path(sciezka).read_text(encoding="utf-8", errors="replace")[:20_000]
    except OSError:
        return {"imie": "", "firma": ""}
    imie = _czysty((_pole(tekst, "Imię / jak się zwracać") or "").split(",")[0].split("(")[0], IMIE_MAKS)
    firma = _pole(tekst, "Firma / marki (nazwa → strona → brand kit)")
    if firma is None:
        firma = _pole(tekst, "Firma / marki") or ""
    firma = _czysty(re.split(r"\s*(?:→|->|\||;)\s*", firma)[0], FIRMA_MAKS)
    return {"imie": imie, "firma": firma}


# ----------------------------------------------------------------------------------------------- model
def _config(profil: Path) -> dict:
    try:
        import yaml
        dane = yaml.safe_load((profil / "config.yaml").read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return dane if isinstance(dane, dict) else {}


def dostawca(profil: Path | str) -> tuple[str, str]:
    """(model.provider, model.base_url) z config.yaml profilu; brak = ("", "")."""
    m = _config(Path(profil)).get("model")
    if not isinstance(m, dict):
        return "", ""
    return str(m.get("provider") or "").strip().lower(), str(m.get("base_url") or "").strip()


def zmienna_obecna(profil: Path | str, nazwy) -> bool:
    """Czy któraś ze zmiennych `nazwy` ma niepustą wartość w `.env` profilu albo w środowisku (wartość zostaje tu)."""
    nazwy = [n for n in nazwy if n]
    if any((os.environ.get(n) or "").strip() for n in nazwy):
        return True
    try:
        linie = (Path(profil) / ".env").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    for linia in linie:
        s = linia.strip()
        if s.startswith("export "):
            s = s[7:].lstrip()
        if "=" not in s or s.startswith("#"):
            continue
        k, v = s.split("=", 1)
        if k.strip() in nazwy and v.strip().strip("'\"").strip():
            return True
    return False


def status_hermesa(profil: Path | str, dostawca_: str, *, python: str | None = None,
                   timeout: float = STATUS_TIMEOUT_S) -> dict | None:
    """Status logowania dostawcy z Hermesa w osobnym procesie (HERMES_HOME = profil); None = Hermesa nie ma."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH",)}
    env["HERMES_HOME"] = str(profil)
    try:
        r = subprocess.run([python or sys.executable, "-I", "-c", SKRYPT_STATUSU, dostawca_], capture_output=True,
                           text=True, timeout=timeout, env=env, cwd=str(profil) if Path(profil).is_dir() else None)
        out = json.loads((r.stdout or "").strip().splitlines()[-1])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None
    if out.get("blad") == "ModuleNotFoundError":
        return None
    return {"sposob": out.get("sposob") or "brak", "polaczony": bool(out.get("polaczony")),
            "zmienne": [z for z in out.get("zmienne") or [] if isinstance(z, str)]}


def stan_modelu(profil: Path | str, *, status: Callable[[Path, str], dict | None] = status_hermesa) -> dict:
    """{dostawca, polaczony, sposob} dla profilu Jarva (spec §13.10)."""
    profil = Path(profil)
    d, base_url = dostawca(profil)
    if not d:
        return {"dostawca": "", "polaczony": False, "sposob": "brak"}
    if d == "custom":
        return {"dostawca": d, "polaczony": bool(base_url), "sposob": "klucz"}
    h = status(profil, d)
    zmienne = list(KLUCZE_DOSTAWCOW.get(d, ())) + list((h or {}).get("zmienne") or [])
    if h is not None and h["sposob"] == "oauth":
        return {"dostawca": d, "polaczony": h["polaczony"], "sposob": "oauth"}
    if h is None and d in OAUTH_ZNANI:
        return {"dostawca": d, "polaczony": (profil / "auth.json").is_file(), "sposob": "oauth"}
    polaczony = bool(h and h["polaczony"]) or zmienna_obecna(profil, zmienne or [d.upper().replace("-", "_") + "_API_KEY"])
    return {"dostawca": d, "polaczony": polaczony, "sposob": "klucz"}


# ----------------------------------------------------------------------------------------------- brama
def wiek_bramy(home: Path | str, teraz: float | None = None) -> float | None:
    """Sekundy od ostatniego startu bramy (ostatnia liczba w `gateway-starts.log`); None = nie wiadomo."""
    p = Path(home) / "gateway-starts.log"
    try:
        with p.open("rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 512))
            ogon = f.read().decode("ascii", "replace").split()
    except OSError:
        return None
    for s in reversed(ogon):
        try:
            t = float(s)
        except ValueError:
            continue
        return max(0.0, (time.time() if teraz is None else teraz) - t)
    return None


def brama_mloda(home: Path | str, teraz: float | None = None) -> bool:
    w = wiek_bramy(home, teraz)
    return w is not None and w < BRAMA_MLODA_S


def stan_bramy_wstaje(home: Path | str, teraz: float | None = None) -> bool:
    """`gateway_state.json` Hermesa: brama ma działać i plik zmienił się niedawno (restart w toku) albo stan
    to starting/restarting. Zły albo brakujący plik = False."""
    p = Path(home) / "gateway_state.json"
    try:
        if p.stat().st_size > 65536:
            return False
        d = json.loads(p.read_text(encoding="utf-8"))
        wiek = (time.time() if teraz is None else teraz) - p.stat().st_mtime
    except (OSError, ValueError):
        return False
    if not isinstance(d, dict):
        return False
    if str(d.get("gateway_state") or "") in ("starting", "restarting"):
        return True
    return d.get("desired_state") == "running" and -5 <= wiek < BRAMA_MLODA_S   # -5: zegar pliku


def zdrowie_bramy(api_base: str, timeout: float = 1.5) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"{api_base.rstrip('/')}/health", timeout=timeout) as r:   # noqa: S310 (localhost)
            return r.status == 200
    except Exception:
        return False


# ----------------------------------------------------------------------------------------------- całość
class Gotowosc:
    """Gotowość do `GET /app` z pamięcią podręczną (model 30 s, brama 3 s). Wołać przez asyncio.to_thread."""

    def __init__(self, *, home: Path | str, profil: Path | str, user_md: Path | str, api_base: str,
                 status: Callable[[Path, str], dict | None] = status_hermesa,
                 zdrowie: Callable[[str], bool] = zdrowie_bramy, zegar: Callable[[], float] = time.time):
        self.home, self.profil, self.user_md, self.api_base = Path(home), Path(profil), Path(user_md), api_base
        self.status, self.zdrowie, self.zegar = status, zdrowie, zegar
        self._lock = threading.Lock()
        self._model: tuple[float, dict] | None = None
        self._brama: tuple[float, str] | None = None
        self._brama_ok_at: float | None = None          # ostatnia udana próba /health
        self._model_liczy = False
        self._pokolenie = 0                              # odswiez() unieważnia wynik liczony w tle
        self.brama_wymuszona: str | None = None        # tylko test E2E (POST /e2e/gotowosc)

    def odswiez(self) -> None:
        with self._lock:
            self._model = self._brama = None
            self._pokolenie += 1

    def _licz_model(self) -> dict:
        with self._lock:
            pok = self._pokolenie
        try:
            m = stan_modelu(self.profil, status=self.status)
            with self._lock:
                if pok == self._pokolenie:
                    self._model = (self.zegar(), m)
            return m
        finally:
            with self._lock:
                self._model_liczy = False

    def model(self) -> dict:
        """Stan modelu; po 30 s zwraca jeszcze stary wynik i liczy nowy w tle (status Hermesa to osobny proces,
        do 12 s), żeby `GET /app` nie czekał. Pierwsze pytanie (albo po `odswiez`) liczy od razu."""
        with self._lock:
            jest = self._model
            w_tle = bool(jest) and self.zegar() - jest[0] >= MODEL_CACHE_S and not self._model_liczy
            if w_tle or not jest:
                self._model_liczy = True
        if jest and not w_tle:
            return dict(jest[1])
        if w_tle:
            threading.Thread(target=self._licz_model, name="jarvo-gotowosc-model", daemon=True).start()
            return dict(jest[1])
        return dict(self._licz_model())

    def brama(self) -> str:
        if self.brama_wymuszona:
            return self.brama_wymuszona
        with self._lock:
            jest = self._brama
        if jest and self.zegar() - jest[0] < BRAMA_CACHE_S:
            return jest[1]
        teraz = self.zegar()
        if self.zdrowie(self.api_base):
            b = "ok"
            self._brama_ok_at = teraz
        else:
            po_ok = self._brama_ok_at is not None and teraz - self._brama_ok_at < BRAMA_PO_OK_S
            wstaje = po_ok or brama_mloda(self.home, teraz) or stan_bramy_wstaje(self.home, teraz)
            b = "startuje" if wstaje else "niedostepna"
        with self._lock:
            self._brama = (self.zegar(), b)
        return b

    def wlasciciel(self) -> dict:
        return wlasciciel(self.user_md)

    def calosc(self) -> tuple[dict, dict]:
        """(wlasciciel, gotowosc)."""
        w = self.wlasciciel()
        return w, {"model": self.model(), "brama": self.brama(), "profil_wlasciciela": bool(w["imie"])}
