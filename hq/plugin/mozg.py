"""Mózg floty z aplikacji (docs/HQ.md „Pierwsze spotkanie”): klucz API wklejony w karcie „Mózg” albo logowanie ChatGPT.

- **Rozpoznanie.** Dostawcę poznajemy po przedrostku klucza: `sk-or-` OpenRouter, `sk-ant-` Anthropic, inne `sk-` OpenAI.
  Klucz ma 20–300 znaków `[A-Za-z0-9_.-]`; inny kształt = nie zapisujemy.
- **Sprawdzenie.** Jedno zapytanie do dostawcy (lista modeli albo opis klucza): 200 i 429 = klucz działa, 401/403 = zły,
  reszta (brak sieci, 5xx) = nie wiadomo, więc nie zapisujemy.
- **Zapis.** Klucz idzie do głównego `.env` (`/opt/data/.env`, plik 600); share_keys.py rozdaje go agentom (wątek
  wtyczki i jednorazowe `sync` od razu). Wartość klucza nie trafia do dziennika, odpowiedzi ani wyjątku.
- **Przełączenie floty.** Każdy profil floty (fleet.json wtyczki) dostaje zestaw dostawcy z `fleet.yaml` (`modele`):
  `model.provider/default` (poziom agenta), `delegation.provider/model` (poziom delegacji), model kompilacji skarbca
  (`auxiliary.jarvo_wiedza`) i `fallback_providers` zestawu (brak = bez zapasowego); profil główny dostaje model `fast`.
  ruamel zachowuje komentarze; zapis atomowy.
- **Trwałość.** Wybór ląduje w `/opt/data/jarvo/state/dostawca-modeli.json` razem z `JARVO_MODEL_PROVIDER` ostatniego
  buildu (`nad`, z BUILD.json); build przy każdej aktualizacji stosuje go, dopóki jarvo.env się nie zmieni
  (fleetlib.Fleet.apply_app_choice). Kalibracja SOUL pod rodzinę modelu dochodzi przy najbliższej aktualizacji.
Testy: tests/test_mozg.py.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Callable

DOSTAWCY = {
    "openrouter": {"nazwa": "OpenRouter", "zmienna": "OPENROUTER_API_KEY", "przedrostek": "sk-or-",
                   "url": "https://openrouter.ai/api/v1/key", "naglowek": "bearer"},
    "anthropic": {"nazwa": "Anthropic", "zmienna": "ANTHROPIC_API_KEY", "przedrostek": "sk-ant-",
                  "url": "https://api.anthropic.com/v1/models", "naglowek": "x-api-key"},
    "openai-api": {"nazwa": "OpenAI", "zmienna": "OPENAI_API_KEY", "przedrostek": "sk-",
                   "url": "https://api.openai.com/v1/models", "naglowek": "bearer"},
}
CHATGPT = "openai-codex"
KLUCZ_RE = re.compile(r"^[A-Za-z0-9_.\-]{20,300}$")
LINIA_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
CZAS_S = 12.0


class BladMozgu(Exception):
    """kod: nieznany_klucz | klucz_odrzucony | brak_polaczenia | brak_zestawu | zapis."""

    def __init__(self, kod: str):
        super().__init__(kod)
        self.kod = kod


def rozpoznaj(klucz: str) -> str | None:
    """Nazwa dostawcy Hermesa dla klucza albo None (zły kształt, nieznany przedrostek)."""
    k = (klucz or "").strip()
    if not KLUCZ_RE.match(k):
        return None
    for nazwa in ("openrouter", "anthropic", "openai-api"):       # od najdłuższego przedrostka
        if k.startswith(DOSTAWCY[nazwa]["przedrostek"]):
            return nazwa
    return None


def _http_get(url: str, naglowki: dict) -> int:
    import httpx
    with httpx.Client(timeout=httpx.Timeout(CZAS_S, connect=6.0), follow_redirects=False) as c:
        return c.get(url, headers=naglowki).status_code


def sprawdz(dostawca: str, klucz: str, *, get: Callable[[str, dict], int] = _http_get) -> str:
    """"ok" | "zly" | "siec". Błąd połączenia nie niesie klucza (nagłówki nie trafiają do komunikatu)."""
    d = DOSTAWCY[dostawca]
    if d["naglowek"] == "x-api-key":
        naglowki = {"x-api-key": klucz, "anthropic-version": "2023-06-01"}
    else:
        naglowki = {"Authorization": f"Bearer {klucz}"}
    naglowki["User-Agent"] = "jarvo-mozg/1.0"
    try:
        kod = get(d["url"], naglowki)
    except Exception:
        return "siec"
    if kod in (200, 429):
        return "ok"
    if kod in (401, 403):
        return "zly"
    return "siec"


def _zapisz_atomowo(sciezka: Path, tekst: str, tryb: int) -> None:
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(sciezka.parent), prefix=f".{sciezka.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(tekst)
        os.chmod(tmp, tryb)
        os.replace(tmp, sciezka)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def ustaw_zmienna(env: Path | str, nazwa: str, wartosc: str) -> None:
    """`nazwa=wartosc` w pliku .env: pierwsze przypisanie zamienione, kolejne usunięte, brak = dopisane na końcu.
    Reszta pliku bez zmian; plik 600."""
    env = Path(env)
    try:
        linie = env.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        linie = []
    wynik, jest = [], False
    for linia in linie:
        m = LINIA_RE.match(linia)
        if m and m.group(1) == nazwa:
            if not jest:
                wynik.append(f"{nazwa}={wartosc}")
                jest = True
            continue
        wynik.append(linia)
    if not jest:
        wynik.append(f"{nazwa}={wartosc}")
    _zapisz_atomowo(env, "\n".join(wynik) + "\n", 0o600)


def _yaml():
    from ruamel.yaml import YAML
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    return y


def _ustaw_profil(cfg_path: Path, dostawca: str, zestaw: dict, poziom: str, poziom_delegacji: str | None,
                  zapasowy: dict | None, *, glowny: bool = False) -> bool:
    y = _yaml()
    try:
        cfg = y.load(cfg_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False
    if not isinstance(cfg, dict):
        return False
    model = cfg.get("model")
    if not isinstance(model, dict):
        if glowny:
            return False
        cfg["model"] = model = {}
    model["provider"] = dostawca
    model["default"] = zestaw.get(poziom) or zestaw.get("fast")
    model.pop("base_url", None)                       # adres poprzedniego dostawcy skierowałby zapytania nie tam
    if not glowny:
        deleg = cfg.get("delegation")
        if isinstance(deleg, dict) and "provider" in deleg:
            deleg["provider"] = dostawca
            deleg["model"] = zestaw.get(poziom_delegacji or "fast") or zestaw.get("fast")
        aux = cfg.get("auxiliary")
        if isinstance(aux, dict) and isinstance(aux.get("jarvo_wiedza"), dict) and "model" in aux["jarvo_wiedza"]:
            aux["jarvo_wiedza"]["model"] = zestaw.get("frontier") or model["default"]
        if zapasowy:
            cfg["fallback_providers"] = [{"provider": zapasowy["provider"], "model": zapasowy["model"]}]
        else:
            cfg.pop("fallback_providers", None)
    import io
    buf = io.StringIO()
    y.dump(cfg, buf)
    tryb = cfg_path.stat().st_mode & 0o777
    _zapisz_atomowo(cfg_path, buf.getvalue(), tryb)
    return True


def przelacz(home: Path | str, flota: dict, dostawca: str) -> list[str]:
    """Flota na zestaw `dostawca` (fleet.json → `modele`). Zwraca nazwy zmienionych profili ("default" = główny)."""
    home = Path(home)
    modele = flota.get("modele") or {}
    zestaw = (modele.get("zestawy") or {}).get(dostawca)
    if not isinstance(zestaw, dict) or not zestaw:
        raise BladMozgu("brak_zestawu")
    zapasowy = (modele.get("zapasowe") or {}).get(dostawca)
    zapasowy = zapasowy if isinstance(zapasowy, dict) and zapasowy.get("provider") and zapasowy.get("model") else None
    zmienione = []
    for a in flota.get("agents") or []:
        nazwa = str(a.get("name") or "")
        if not re.match(r"^[a-z0-9-]+$", nazwa):
            continue
        if _ustaw_profil(home / "profiles" / nazwa / "config.yaml", dostawca, zestaw, a.get("model_tier") or "strong",
                         a.get("delegation_tier"), zapasowy):
            zmienione.append(nazwa)
    if _ustaw_profil(home / "config.yaml", dostawca, zestaw, "fast", None, None, glowny=True):
        zmienione.append("default")
    return zmienione


def zapisz_wybor(stan: Path | str, dostawca: str, build_json: Path | str | None) -> dict:
    """Wybór dla następnego buildu: `nad` = JARVO_MODEL_PROVIDER z BUILD.json (None, gdy stary build bez `modele`)."""
    nad = None
    if build_json:
        try:
            nad = (json.loads(Path(build_json).read_text(encoding="utf-8")).get("modele") or {}).get("env")
        except (OSError, ValueError, AttributeError):
            nad = None
    wybor = {"dostawca": dostawca, "nad": nad, "kiedy": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    _zapisz_atomowo(Path(stan), json.dumps(wybor, ensure_ascii=False, indent=1) + "\n", 0o644)
    return wybor


def podlacz_klucz(klucz: str, *, home: Path | str, flota: dict, stan: Path | str, build_json: Path | str | None,
                  get: Callable[[str, dict], int] = _http_get, rozdaj: Callable[[Path], object] | None = None) -> dict:
    """Cały krok „Wklej klucz”: rozpoznanie, sprawdzenie, zapis, rozdanie agentom, przełączenie floty, trwały wybór.
    Zwraca {dostawca, nazwa, profile}; błąd = BladMozgu(kod)."""
    klucz = (klucz or "").strip()
    dostawca = rozpoznaj(klucz)
    if dostawca is None:
        raise BladMozgu("nieznany_klucz")
    if dostawca not in ((flota.get("modele") or {}).get("zestawy") or {}):
        raise BladMozgu("brak_zestawu")
    wynik = sprawdz(dostawca, klucz, get=get)
    if wynik == "zly":
        raise BladMozgu("klucz_odrzucony")
    if wynik != "ok":
        raise BladMozgu("brak_polaczenia")
    home = Path(home)
    try:
        ustaw_zmienna(home / ".env", DOSTAWCY[dostawca]["zmienna"], klucz)
        if rozdaj is not None:
            rozdaj(home)
        profile = przelacz(home, flota, dostawca)
        zapisz_wybor(stan, dostawca, build_json)
    except BladMozgu:
        raise
    except Exception:
        raise BladMozgu("zapis") from None
    return {"dostawca": dostawca, "nazwa": DOSTAWCY[dostawca]["nazwa"], "profile": profile}


def podlacz_chatgpt(*, home: Path | str, flota: dict, stan: Path | str, build_json: Path | str | None) -> dict:
    """Po zalogowaniu ChatGPT (Hermes, kod urządzenia): flota na openai-codex, jeśli jeszcze na nim nie jest."""
    try:
        profile = przelacz(home, flota, CHATGPT)
        zapisz_wybor(stan, CHATGPT, build_json)
    except BladMozgu:
        raise
    except Exception:
        raise BladMozgu("zapis") from None
    return {"dostawca": CHATGPT, "nazwa": "ChatGPT", "profile": profile}
