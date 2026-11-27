"""Wspólne funkcje narzędzi floty Jarvo (build, validate, deploy, evals).

Tylko biblioteka standardowa + YAML. Działa z PyYAML albo z ruamel.yaml (który jest
w środowisku Hermesa), więc skrypty można uruchamiać zarówno lokalnie, jak i w kontenerze.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
PROFILES_DIR = REPO_ROOT / "profiles"
SHARED_DIR = REPO_ROOT / "shared"
VENDOR_LOCK = REPO_ROOT / "vendor" / "skills.lock.yaml"
FLEET_FILE = REPO_ROOT / "fleet.yaml"
# nakładka prywatna (docs/FLEET.md „Agenci biznesowi”): katalog z agentami jednej instalacji, poza publicznym repo,
# w układzie repo (fleet.yaml z samą listą `agents:`, profiles/, evals/, security/redteam/testy.yaml, skills.lock.yaml,
# wzorce.md). Skrypty widzą ją tylko przez tę zmienną; domyślne `<root>/nakladka` instalacji podaje jarvo/flota.py.
NAKLADKA_ENV = "JARVO_NAKLADKA"
NAKLADKA_WZORCE = "wzorce.md"                 # wzorce misji agentów nakładki, doklejane do dispatch-playbook Jarva
NAKLADKA_REDTEAM = Path("security") / "redteam" / "testy.yaml"
_Z_ENV: Any = object()                         # domyślny argument: nakładka z JARVO_NAKLADKA
# wzorce misji Jarva (dispatch-playbook) w profilu orkiestratora; validate sprawdza, build dokleja wzorce nakładki
PATTERNS_FILE = "skills/fleet/dispatch-playbook/references/patterns.md"

CALIBRATION_DIR = SHARED_DIR / "calibration"
# prefiks identyfikatora modelu (bez dostawcy) → plik kalibracji w shared/calibration/
MODEL_FAMILIES = (("gpt-", "gpt"), ("chatgpt", "gpt"), ("o3", "gpt"), ("o4", "gpt"), ("claude", "claude"),
                  ("deepseek", "deepseek"), ("kimi", "kimi"))
PROTOCOL_MARKER = "<!-- Jarvo:PROTOCOL -->"
SWIEZOSC_DNI = 120        # skill sprawdzony dawniej = do przejrzenia (walidator, rutyna profiles/jarvo/scripts/swiezosc.py)
ROSTER_MARKER = "<!-- Jarvo:ROSTER -->"
# SOUL.md to sama postać agenta (kim jest, charakter, głos); jak pracuje (zasady, mapa skilli, formaty, protokół floty)
# leży obok w ZASADY.md (decyzja właściciela 19.11: „w SOUL.md sam charakter i zajebistość”). Hermes czyta jeden
# plik SOUL.md, więc build składa prompt: SOUL.md + ZASADY.md; profil bez ZASADY.md ma wszystko w SOUL.md.
ZASADY_FILE = "ZASADY.md"


def soul_zrodlo(katalog: Path) -> str:
    """Tekst promptu agenta ze źródeł profilu: SOUL.md, a po nim ZASADY.md, gdy istnieje."""
    soul = katalog / "SOUL.md"
    zasady = katalog / ZASADY_FILE
    tekst = soul.read_text(encoding="utf-8") if soul.exists() else ""
    if zasady.exists():
        tekst = tekst.rstrip() + "\n\n" + zasady.read_text(encoding="utf-8").lstrip()
    return tekst


KRYTYCZNE_FILE = "KRYTYCZNE.md"     # w zbudowanym profilu: zamykający <critical>, który wtyczka jarvo-wiedza kładzie na końcu


def wydziel_koniec(soul: str) -> tuple[str, str]:
    """(SOUL bez zamykającego bloku `<critical>`, ten blok) gdy SOUL kończy się blokiem `<critical>…</critical>`
    i ma też inny wcześniej (powtórka zasad z początku); inaczej (SOUL, "")."""
    tekst = soul.rstrip()
    if not tekst.endswith("</critical>") or tekst.count("<critical>") < 2:
        return soul, ""
    start = tekst.rindex("<critical>")
    return tekst[:start].rstrip() + "\n", tekst[start:]


# Mapa agenta (docs/WIEDZA.md §2b, wiedza/mapa.py): profiles/<agent>/MAPA.md z repo albo nakładki (orkiestrator repo ma
# też drugi plik w nakładce). Rdzeń mapy (bloki RDZEN; u orkiestratora też zwarte ścieżki i harmonogram) build wstawia
# w miejsce znacznika w ZASADY.md agenta; pełna mapa idzie do skarbca (build/wiedza/tozsamosc → `wiedza.py zasiej` →
# notatka `jarvo/jak działa jarvo` albo `agenci/<agent>/jak działa <krótka nazwa>`), nie do profilu Hermesa.
MAPA_MARKER = "<!-- Jarvo:MAPA -->"
MAPA_FILE = "MAPA.md"


def _modul_mapy():
    """wiedza/mapa.py (biblioteka standardowa): ten sam generator dla buildu, walidatora i zasiewu. Kod obok tego pliku,
    nie z REPO_ROOT (to katalog danych floty: testy i build z kopii podmieniają go na kopię bez `wiedza/`); nieudany
    import nie zostaje w sys.modules jako pół-moduł."""
    import importlib.util
    import sys
    mod = sys.modules.get("jarvo_wiedza_mapa")
    if mod is None:
        sciezka = Path(__file__).resolve().parent.parent / "wiedza" / "mapa.py"
        spec = importlib.util.spec_from_file_location("jarvo_wiedza_mapa", sciezka)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["jarvo_wiedza_mapa"] = mod
        try:
            spec.loader.exec_module(mod)
        except BaseException:
            sys.modules.pop("jarvo_wiedza_mapa", None)
            raise
    return mod


def render_roster_summary(fleet: "Fleet") -> str:
    """Zespół w SOUL orkiestratora (znacznik ROSTER_MARKER, zarazem „Zespół” rdzenia mapy): linia na specjalistę, emoji,
    nazwa profilu (assignee karty), @uchwyt, krótka nazwa, tytuł i kiedy mu oddaję (`oddaj_gdy` z fleet.yaml)."""
    linie = []
    for a in fleet.active():
        if a.name == fleet.orchestrator:
            continue
        nazwa = a.hq_short or a.name
        tytul = a.title if a.title.startswith(f"{nazwa}:") else f"{nazwa}: {a.title}"   # tytuł z nazwą (nakładka) bez dubla
        linia = " ".join(x for x in (f"- {a.emoji}", f"`{a.name}`", f"@{a.handle}" if a.handle else "", tytul) if x)
        linie.append(linia + (f"; oddaję, gdy: {a.oddaj_gdy}" if a.oddaj_gdy else ""))
    return "\n".join(linie)


def mapa_zrodla(fleet: "Fleet", agent: str = "") -> tuple[str, str]:
    """(MAPA.md agenta, domyślnie orkiestratora, z jego katalogu; ten sam plik z nakładki floty albo ""). Agent nakładki
    ma MAPA.md już w nakładce, więc drugiego pliku nie ma."""
    a = fleet.agent(agent or fleet.orchestrator)
    repo = a.dir / MAPA_FILE
    n = fleet.nakladka                                       # ta sama nakładka, z którą wczytano flotę (load_fleet)
    nakl = n / "profiles" / a.name / MAPA_FILE if n and not a.root else None
    return (repo.read_text(encoding="utf-8") if repo.is_file() else "",
            nakl.read_text(encoding="utf-8") if nakl and nakl.is_file() else "")


def zadania_cron_floty(fleet: "Fleet") -> list[dict]:
    """Rutyny aktywnych agentów z ich cron/jobs.yaml (repo albo nakładka) w kształcie wiedza/mapa.py: agent biznesowy
    instaluje je wstrzymane (docs/FLEET.md), więc u niego `wlaczona` = False; `enabled: false` w pliku tak samo."""
    out = []
    for a in fleet.active():
        dane = load_yaml(a.dir / "cron" / "jobs.yaml") if (a.dir / "cron" / "jobs.yaml").is_file() else {}
        for z in (dane or {}).get("jobs") or []:
            if isinstance(z, dict) and z.get("schedule"):
                out.append({"nazwa": str(z.get("name") or z.get("id") or ""), "kiedy": str(z["schedule"]), "agent": a.name,
                            "wlaczona": z.get("enabled", True) is not False and not a.marka, "dostarczanie": ""})
    return out


def sciezki_mapy(tokeny: dict[str, str], agent: str) -> dict[str, str]:
    """Ścieżki rdzenia mapy z tokenów ścieżek buildu (DATA_DIR, JARVO_DIR, KNOWLEDGE_DIR, MISSIONS_DIR, WORKSPACES_DIR,
    INBOX_DIR); kolejność = kolejność w rdzeniu (baza raz, podkatalogi względnie: wiedza/mapa.render_sciezki)."""
    profil = f"{tokeny['DATA_DIR'].rstrip('/')}/profiles/{agent}"
    return {"dane Jarva": tokeny["JARVO_DIR"], "skarbiec": tokeny["KNOWLEDGE_DIR"], "misje": tokeny["MISSIONS_DIR"],
            "robocze": tokeny["WORKSPACES_DIR"], "od właściciela": tokeny["INBOX_DIR"], "mój profil": profil,
            "pamięć (MEMORY.md, USER.md)": f"{profil}/memories", "skrypty": f"{profil}/scripts"}


def rdzen_mapy(fleet: "Fleet", sciezki: dict[str, str], agent: str = "") -> str:
    """Rdzeń mapy do ZASADY.md agenta (MAPA_MARKER): wiedza/mapa.rdzen z MAPA.md repo i nakładki. Orkiestrator (domyślnie)
    dostaje też zwarte rutyny floty i `sciezki` (sciezki_mapy; walidator podaje ścieżki zastępcze o średniej długości);
    inny agent tylko swoje bloki RDZEN (krótki prompt: ścieżki, które musi znać od razu, pisze w RDZEN tokenami).
    Tokeny @@…@@ zostają (build podstawia je w całym SOUL)."""
    agent = agent or fleet.orchestrator
    repo, nakl = mapa_zrodla(fleet, agent)
    if agent != fleet.orchestrator:
        return _modul_mapy().rdzen(repo, nakl, [], {})
    return _modul_mapy().rdzen(repo, nakl, zadania_cron_floty(fleet), sciezki)


# tabela „komu oddać” generowana z fleet.yaml (pole `oddaj_gdy` każdego specjalisty): roster Jarva i każdy, kto routuje
ODDAJ_MARKER = "<!-- Jarvo:ODDAJ -->"
COMPOSE_FILE = Path(__file__).resolve().parent.parent / "infra" / "docker-compose.yml"
AGENT_KINDS = {"orchestrator", "specialist", "generalist"}
AUTONOMY_LEVELS = {"A0", "A1", "A2", "A3"}
# uchwyt agenta w rozmowie aplikacji (`@web`): ASCII, unikalny, nie słowo zarezerwowane (te same zasady co
# hq/plugin/wzmianki.py, którego aliasy porównujemy po złożeniu: bez polskich znaków, małe litery)
UCHWYT_RE = re.compile(r"^[a-z][a-z0-9]{1,15}$")
UCHWYTY_ZAREZERWOWANE = frozenset({"all", "everyone", "wszyscy", "here", "diff", "staged", "file", "folder", "git", "url"})
HQ_ROOMS = {"bridge", "study", "devlab", "atelier", "filmstudio", "workshop", "office", "radar", "apps", "control"}   # pokoje w Jarvo HQ (hq/web/src/20-art.js)
# Hermes ucina opis skilla w indeksie promptu do 60 znaków (agent/skill_utils.py).
SKILL_PROMPT_DESC_LIMIT = 60
# krój figur skilla `izometria` (JetBrains Mono, OFL, z krojów HQ): build skilla i plugin HQ kładą go obok iso.py
ISO_KROJE = ("jetbrains-mono-latin-wght-normal.woff2", "jetbrains-mono-latin-ext-wght-normal.woff2", "OFL-JetBrainsMono.txt")

# --------------------------------------------------------------------------- YAML

def _yaml_backend():
    try:
        import yaml  # type: ignore

        return "pyyaml", yaml
    except ImportError:  # pragma: no cover - zależy od środowiska
        from ruamel.yaml import YAML  # type: ignore

        return "ruamel", YAML(typ="safe", pure=True)


def rt_yaml():
    """(load, dump) dla plików konfiguracji Hermesa: ruamel zachowuje komentarze i cudzysłowy (środowisko Hermesa),
    bez niego PyYAML. load(ścieżka) zwraca None dla brakującego pliku."""
    try:
        from ruamel.yaml import YAML  # type: ignore
    except ImportError:  # pragma: no cover - lokalnie bez ruamel
        import yaml  # type: ignore

        def load(p: Path):
            return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None

        def dump(data, p: Path) -> None:
            p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return load, dump
    y = YAML()
    y.preserve_quotes = True

    def load(p: Path):
        return y.load(p.read_text(encoding="utf-8")) if p.exists() else None

    def dump(data, p: Path) -> None:
        with p.open("w", encoding="utf-8") as f:
            y.dump(data, f)
    return load, dump


def load_yaml(path: Path | str) -> Any:
    text = Path(path).read_text(encoding="utf-8")
    return loads_yaml(text)


def loads_yaml(text: str) -> Any:
    kind, backend = _yaml_backend()
    if kind == "pyyaml":
        return backend.safe_load(text)
    return backend.load(io.StringIO(text))


def dump_yaml(data: Any) -> str:
    kind, backend = _yaml_backend()
    if kind == "pyyaml":
        return backend.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)
    buf = io.StringIO()  # pragma: no cover
    backend.default_flow_style = False
    backend.dump(data, buf)
    return buf.getvalue()


# --------------------------------------------------------------------- frontmatter

_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.S)


def split_frontmatter(text: str) -> tuple[dict, str]:
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    data = loads_yaml(m.group(1)) or {}
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    return data, text[m.end():]


def read_skill(path: Path) -> tuple[dict, str]:
    return split_frontmatter(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- fleet

@dataclass
class Agent:
    name: str
    kind: str
    title: str
    description: str
    model_tier: str
    delegation_tier: str
    autonomy_max: str
    telegram_topic: str
    status: str
    emoji: str = ""
    pin_skills: list[str] = field(default_factory=list)
    hq_room: str = "office"
    hq_label: str = ""
    hq_short: str = ""
    rola: str = ""                            # krótka rola w aplikacji (do 8 słów), docs/FLEET.md „Pola agenta”
    handle: str = ""                          # uchwyt w rozmowie aplikacji (`@web`), docs/FLEET.md „Uchwyty”
    aliasy_extra: list[str] = field(default_factory=list)   # dodatkowe aliasy wzmianki (pole `aliasy` we fleet.yaml)
    en: dict = field(default_factory=dict)   # angielskie title / hq_label / description (HQ po angielsku)
    oddaj_gdy: str = ""                       # kiedy Jarvo oddaje zadanie temu agentowi (roster w prompcie); tabela generowana
    komputer: bool = False                    # agent z narzędziem computer_use (Komputer Jarva, docs/KOMPUTER.md)
    pulpit: bool = False                      # agent z narzędziem `pulpit` (programy na ekranie serwera, docs/PULPIT.md)
    # agent biznesowy: slug marki = katalog brands/<marka>/ w skarbcu; widzi w wiedzy tylko swoją markę
    # (docs/FLEET.md „Agenci biznesowi”); "" = bez marki, widzi wszystko
    marka: str = ""
    root: Path | None = None                  # katalog nakładki prywatnej, z której jest agent; None = publiczne repo

    @property
    def dir(self) -> Path:
        return self.root / "profiles" / self.name if self.root else PROFILES_DIR / self.name

    @property
    def korzen(self) -> Path:
        """Repo (publiczne albo nakładka), w którym agent ma profiles/, evals/ i resztę."""
        return self.root or REPO_ROOT

    @property
    def evals_file(self) -> Path:
        return self.korzen / "evals" / self.name / "scenarios.yaml"

    @property
    def aliasy(self) -> list[str]:
        """Złożone aliasy wzmianki `@…`: uchwyt, nazwa profilu, krótka nazwa z HQ i pole `aliasy` (bez powtórek,
        tylko znaki, które da się wpisać po `@`). fleet.json niesie je do aplikacji i parsera (wzmianki.py)."""
        surowe = [self.handle, self.name, self.hq_short, *self.aliasy_extra]
        return list(dict.fromkeys(a for a in (zloz(x) for x in surowe) if a and re.fullmatch(r"[\w-]+", a)))


@dataclass
class Fleet:
    raw: dict
    agents: list[Agent]
    nakladka: Path | None = None              # nakładka prywatna, z której doszli agenci (load_fleet)
    wlasciciel: dict[str, str] = field(default_factory=dict)   # kim jest właściciel (nakładka; repo jest publiczne)

    @property
    def orchestrator(self) -> str:
        return self.raw["orchestrator"]

    @property
    def reviewer(self) -> str:
        return self.raw.get("reviewer", self.raw["orchestrator"])

    @property
    def tiers(self) -> dict[str, str]:
        return self.raw["models"]["tiers"]

    @property
    def provider(self) -> str:
        return self.raw["models"]["provider"]

    @property
    def fallback(self) -> dict | None:
        """Model zapasowy wybranego zestawu (fallback_providers Hermesa) albo None."""
        fb = (self.raw["models"].get("fallback") or {}).get(self.provider)
        return dict(fb) if isinstance(fb, dict) and fb.get("provider") and fb.get("model") else None

    def apply_model_overrides(self, env: dict[str, str]) -> None:
        """Wybór dostawcy bez edycji repo: JARVO_MODEL_PROVIDER=<zestaw z models.presets> i opcjonalnie
        JARVO_MODEL_FRONTIER / _STRONG / _FAST / _FALLBACK (np. z compose/jarvo.env)."""
        models = self.raw["models"]
        chosen = (env.get("JARVO_MODEL_PROVIDER") or "").strip()
        if chosen and chosen != models["provider"]:
            presets = models.get("presets") or {}
            if chosen not in presets:
                raise ValueError(f"JARVO_MODEL_PROVIDER={chosen}: brak zestawu w fleet.yaml (models.presets: "
                                 f"{', '.join(sorted(presets)) or 'pusto'})")
            models["provider"] = chosen
            models["tiers"] = dict(presets[chosen])
        for tier in list(models["tiers"]):
            value = (env.get(f"JARVO_MODEL_{tier.upper()}") or "").strip()
            if value:
                models["tiers"][tier] = value
        # model zapasowy: JARVO_MODEL_FALLBACK=<model u tego samego dostawcy> albo „off” (bez zapasowego)
        fb = (env.get("JARVO_MODEL_FALLBACK") or "").strip()
        if fb:
            table = models.setdefault("fallback", {}) or {}
            models["fallback"] = table
            if fb.lower() == "off":
                table.pop(models["provider"], None)
            else:
                prov = (table.get(models["provider"]) or {}).get("provider") or models["provider"]
                table[models["provider"]] = {"provider": prov, "model": fb}

    def apply_app_choice(self, env: dict[str, str], choice: dict | None) -> bool:
        """Dostawca wybrany w aplikacji (klucz API albo ChatGPT w pierwszym spotkaniu, hq/plugin/mozg.py) trafia do
        `env` jako JARVO_MODEL_PROVIDER, jeśli JARVO_MODEL_PROVIDER w jarvo.env jest taki sam jak przy wyborze (`nad`);
        zmiana w jarvo.env po wyborze (local-up.sh) wygrywa. Nieznany zestaw albo zły plik = bez zmian. True = użyty."""
        if not isinstance(choice, dict):
            return False
        chosen = str(choice.get("dostawca") or "").strip()
        models = self.raw["models"]
        if not chosen or (chosen != models["provider"] and chosen not in (models.get("presets") or {})):
            return False
        nad = choice.get("nad")
        if nad is not None and str(nad).strip() != (env.get("JARVO_MODEL_PROVIDER") or "").strip():
            return False
        env["JARVO_MODEL_PROVIDER"] = chosen
        return True

    def agent(self, name: str) -> Agent:
        for a in self.agents:
            if a.name == name:
                return a
        raise KeyError(name)

    def active(self) -> list[Agent]:
        return [a for a in self.agents if a.status == "active"]

    def model_for(self, tier: str) -> str:
        return self.tiers[tier]


def katalog_nakladki() -> Path | None:
    """Nakładka prywatna z JARVO_NAKLADKA (pusto albo brak = bez nakładki); zmienna wskazująca nie-katalog to błąd."""
    wartosc = os.environ.get(NAKLADKA_ENV, "").strip()
    if not wartosc:
        return None
    p = Path(wartosc).expanduser().resolve()
    if not p.is_dir():
        raise SystemExit(f"{NAKLADKA_ENV}={wartosc}: nie ma takiego katalogu (nakładka prywatna, docs/FLEET.md)")
    return p


def _nakladka(nakladka: Any) -> Path | None:
    return katalog_nakladki() if nakladka is _Z_ENV else (Path(nakladka).resolve() if nakladka else None)


def _plik_nakladki(n: Path, nazwa: str, klucze: set[str]) -> dict:
    """YAML nakładki (fleet.yaml, skills.lock.yaml) tylko z kluczami `klucze`; brak pliku = pusto."""
    plik = n / nazwa
    if not plik.is_file():
        return {}
    dane = load_yaml(plik) or {}
    obce = sorted(set(dane) - klucze) if isinstance(dane, dict) else ["(to nie mapa)"]
    if obce:
        raise SystemExit(f"nakładka {n}: {nazwa} ma tylko {', '.join(sorted(klucze))}, a ma też {', '.join(map(str, obce))} "
                         "(reszta konfiguracji floty jest w publicznym repo)")
    return dane


# Tożsamość właściciela w SOUL (@@WLASCICIEL@@…): imię, marka i to, za co agent odpowiada, przychodzą z nakładki
# prywatnej (`wlasciciel:` w jej fleet.yaml), bo publiczne repo nie zna właściciela. Bez nakładki: słowo ogólne.
WLASCICIEL_DOMYSLNIE = {"imie": "właściciel", "marka": "", "cel": "jego firma ma rosnąć"}


def tokeny_wlasciciela(fleet: "Fleet") -> dict[str, str]:
    w = {**WLASCICIEL_DOMYSLNIE, **{k: " ".join(str(v).split()) for k, v in fleet.wlasciciel.items() if v}}
    return {"WLASCICIEL": w["imie"], "WLASCICIEL_MARKA": f" (marka {w['marka']})" if w["marka"] else "",
            "WLASCICIEL_CEL": w["cel"]}


def _agent(entry: dict, root: Path | None = None) -> Agent:
    return Agent(
        name=entry["name"],
        kind=entry["kind"],
        title=entry.get("title", ""),
        description=" ".join(str(entry.get("description", "")).split()),
        model_tier=entry.get("model_tier", "strong"),
        delegation_tier=entry.get("delegation_tier", "fast"),
        autonomy_max=entry.get("autonomy_max", "A1"),
        telegram_topic=entry.get("telegram_topic", ""),
        status=entry.get("status", "planned"),
        emoji=entry.get("emoji", ""),
        pin_skills=list(entry.get("pin_skills", []) or []),
        hq_room=entry.get("hq_room", "office"),
        hq_label=entry.get("hq_label", "") or entry.get("title", ""),
        hq_short=entry.get("hq_short", "") or entry["name"].removeprefix("jarvo-").capitalize(),
        rola=" ".join(str(entry.get("rola", "") or "").split()),
        handle=str(entry.get("handle", "") or ""),
        aliasy_extra=[str(x) for x in (entry.get("aliasy") or [])],
        en={k: " ".join(str(v).split()) for k, v in (entry.get("en") or {}).items() if v},
        oddaj_gdy=" ".join(str(entry.get("oddaj_gdy", "") or "").split()),
        komputer=entry.get("komputer") is True,
        pulpit=entry.get("pulpit") is True,
        marka=str(entry.get("marka") or ""),
        root=root,
    )


def load_fleet(path: Path | None = None, nakladka: Path | None = _Z_ENV) -> Fleet:
    """Flota z fleet.yaml i agenci nakładki prywatnej (`nakladka`, domyślnie z JARVO_NAKLADKA; None = bez nakładki).
    Agent nakładki dochodzi na koniec listy (też do `raw["agents"]`) i zna swój katalog (`Agent.root`); nazwa jak
    u agenta publicznego to błąd, nie podmiana."""
    raw = load_yaml(path or FLEET_FILE)
    agents = [_agent(entry) for entry in raw.get("agents", [])]
    n = _nakladka(nakladka)
    if n is not None:
        dane = _plik_nakladki(n, "fleet.yaml", {"agents", "wlasciciel"})
        wpisy = list(dane.get("agents") or [])
        wlasciciel = {str(k): str(v) for k, v in (dane.get("wlasciciel") or {}).items()}
        if set(wlasciciel) - set(WLASCICIEL_DOMYSLNIE):
            raise SystemExit(f"nakładka {n}: wlasciciel ma tylko {', '.join(WLASCICIEL_DOMYSLNIE)}")
        publiczni = {a.name for a in agents}
        for entry in wpisy:
            if entry.get("name") in publiczni:
                raise SystemExit(f"nakładka {n}: agent {entry['name']} jest już we flocie publicznej (fleet.yaml); "
                                 "agent nakładki potrzebuje własnej nazwy")
        raw["agents"] = [*(raw.get("agents") or []), *wpisy]
        agents += [_agent(entry, n) for entry in wpisy]
        return Fleet(raw=raw, agents=agents, nakladka=n, wlasciciel=wlasciciel)
    return Fleet(raw=raw, agents=agents, nakladka=n)


def w_repo_albo_nakladce(rel: str | Path, repo: Path | None = None) -> Path:
    """Plik `rel` (np. evals/<agent>/scenarios.yaml) w repo, a gdy go tam nie ma, w nakładce z JARVO_NAKLADKA."""
    p = (repo or REPO_ROOT) / rel
    n = katalog_nakladki()
    if not p.exists() and n is not None and (n / rel).exists():
        return n / rel
    return p


def sciezka_w_repo(path: Path) -> str:
    """Ścieżka pliku floty względem jego repo (publicznego albo nakładki), z „/”: ten sam układ w obu."""
    path = path.resolve()
    for korzen in (REPO_ROOT, katalog_nakladki()):
        if korzen is not None and path.is_relative_to(korzen.resolve()):
            return path.relative_to(korzen.resolve()).as_posix()
    return path.as_posix()


def bash() -> str | None:
    """Ścieżka prawdziwego basha albo None. Na POSIX `bash` z PATH. Na Windows tylko Git Bash (obok git.exe albo
    w standardowym katalogu instalacji): goły `bash` trafia tam do System32\\bash.exe, a ten uruchamia WSL
    (u właściciela budzi to starą flotę w Ubuntu, docs/NATYWNIE.md f2)."""
    import os
    if os.name != "nt":
        return shutil.which("bash")
    kandydaci = []
    git = shutil.which("git")
    if git:                                     # Git\cmd\git.exe albo Git\mingw64\bin\git.exe
        for przodek in list(Path(git).resolve().parents)[:3]:
            kandydaci += [przodek / "bin" / "bash.exe", przodek / "usr" / "bin" / "bash.exe"]
    for zmienna, podkatalog in (("ProgramFiles", "Git"), ("ProgramW6432", "Git"), ("LOCALAPPDATA", "Programs/Git")):
        if os.environ.get(zmienna):
            kandydaci.append(Path(os.environ[zmienna]) / podkatalog / "bin" / "bash.exe")
    for k in kandydaci:
        if k.is_file() and "system32" not in str(k).lower():
            return str(k)
    return None


def zloz(s: str) -> str:
    """Postać do porównań uchwytów i aliasów: NFKD bez znaków łączących, ł→l, małe litery („Łowca” → „lowca”).
    Ta sama funkcja co hq/plugin/wzmianki.py `zloz` (tests/test_wzmianki.py pilnuje zgodności)."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.category(c).startswith("M"))
    return s.replace("ł", "l").replace("Ł", "L").lower()


def load_lock(path: Path | None = None, nakladka: Path | None = _Z_ENV) -> dict:
    """Lock skilli z `agents:` nakładki prywatnej (skills.lock.yaml w nakładce, opcjonalny; źródła tylko z repo)."""
    lock = load_yaml(path or VENDOR_LOCK)
    n = _nakladka(nakladka)
    wpisy = _plik_nakladki(n, "skills.lock.yaml", {"agents"}).get("agents") or {} if n is not None else {}
    agenci = lock.setdefault("agents", {}) if wpisy else {}
    for agent, entries in wpisy.items():
        if agent in agenci:
            raise SystemExit(f"nakładka {n}: skills.lock.yaml: agent {agent} ma już wpisy w vendor/skills.lock.yaml")
        agenci[agent] = [{**e, "z_nakladki": True} if isinstance(e, dict) else e for e in entries or []]
    return lock


def wzorce_nakladki(n: Path | None) -> str:
    """Wzorce misji Jarva dla agentów nakładki (wzorce.md), pusto bez nakładki albo pliku."""
    plik = n / NAKLADKA_WZORCE if n else None
    return plik.read_text(encoding="utf-8") if plik and plik.is_file() else ""


def w_nakladce(dest: str) -> bool:
    """Wpis locka z `dest` <kategoria>/<nazwa>/<podkatalog>: dane cudzego skilla w podkatalogu skilla własnego
    (nakładki), nie osobny skill."""
    return str(dest).count("/") == 2


def skille_z_locka(lock: dict, agent: str) -> list[str]:
    """Nazwy skilli zewnętrznych agenta z locka (bez wpisów w nakładkach)."""
    return [Path(e["dest"]).name for e in (lock.get("agents") or {}).get(agent) or [] if not w_nakladce(e["dest"])]


# -------------------------------------------------------------------------- skills

def iter_skill_files(root: Path):
    """Wszystkie SKILL.md pod root (bez katalogów ukrytych)."""
    if not root.exists():
        return
    for path in sorted(root.rglob("SKILL.md")):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        yield path


def compose_services(path: Path | None = None) -> set[str]:
    """Usługi zdefiniowane w infra/docker-compose.yml: to, co instalacja naprawdę uruchamia."""
    data = load_yaml(path or COMPOSE_FILE) or {}
    return set((data.get("services") or {}).keys())


def skill_requires(fm: dict) -> list[str]:
    """Usługi, bez których skill nie działa (`metadata.jarvo.wymaga`). Brak usługi = skill nie trafia do profilu."""
    jarvo = ((fm.get("metadata") or {}).get("jarvo") or {})
    return [str(x) for x in (jarvo.get("wymaga") or [])]


def available_skills(root: Path, services: set[str] | None = None) -> tuple[dict[str, Path], dict[str, list[str]]]:
    """Skille, których wymagania są spełnione, oraz pominięte → brakujące usługi."""
    services = compose_services() if services is None else services
    ok, pominiete = {}, {}
    for name, path in skill_names(root).items():
        fm, _ = read_skill(path)
        brak = [s for s in skill_requires(fm) if s not in services]
        if brak:
            pominiete[name] = brak
        else:
            ok[name] = path
    return ok, pominiete


def missing_section(pominiete: dict[str, list[str]], fleet: "Fleet") -> str:
    """Sekcja SOUL dopisywana przez build: workflowy pominięte w tej instalacji, bo brakuje usług, których wymagają
    (`metadata.jarvo.wymaga`). Walidator liczy ją do budżetu SOUL, bo agent dostaje ją przy każdym wywołaniu."""
    planowane = (fleet.raw.get("infra") or {}).get("uslugi_planowane") or {}
    rows = ["## Czego w tej instalacji nie zrobisz (generowane przez build)", "",
            "Te workflowy wymagają usług, których ta instalacja nie uruchamia, więc nie ma ich w Twoim profilu. Gdy ktoś",
            "o nie poprosi, powiedz wprost, czego brakuje, i zaproponuj to, co działa. Nie udawaj, że je wykonałeś.", "",
            "| Workflow | Brakuje usługi |", "|---|---|"]
    for name, brak in sorted(pominiete.items()):
        rows.append(f"| `{name}` | " + ", ".join(f"{u} ({planowane[u]})" if u in planowane else u for u in brak) + " |")
    return "\n".join(rows) + "\n"


def skill_names(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for path in iter_skill_files(root):
        fm, _ = read_skill(path)
        name = str(fm.get("name") or path.parent.name)
        out[name] = path
    return out


_ROLA_RE = re.compile(r"<!-- (wykonawca|jarvo) -->\n(.*?)<!-- /\1 -->\n", re.S)


def protocol_for(text: str, orchestrator: bool) -> str:
    """Protokół floty dla roli: bloki `<!-- wykonawca -->…<!-- /wykonawca -->` (jak pracować nad kartą i ją oddać)
    dostają tylko agenci, `<!-- jarvo -->…` tylko Jarvo. Jarvo pisze karty i ocenia wyniki, więc dostaje kształt
    karty i wyniku oraz zasady wspólne; tekst agentów jest taki sam jak bez znaczników."""
    rola = "jarvo" if orchestrator else "wykonawca"
    return _ROLA_RE.sub(lambda m: m.group(2) if m.group(1) == rola else "", text)


def approx_tokens(text: str) -> int:
    return int(len(text) / 3.5) + 1


def kopiuj_kroje_izometrii(scripts: Path) -> None:
    """Krój figur obok iso.py (`<skill>/scripts/kroje/`): strona figur bez Google Fonts, z polskimi znakami."""
    kroje = scripts / "kroje"
    kroje.mkdir(parents=True, exist_ok=True)
    for name in ISO_KROJE:
        shutil.copy2(REPO_ROOT / "hq" / "web" / "fonts" / "kroje" / name, kroje / name)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


# ------------------------------------------------------------------ kalibracja pod rodzinę modelu

def model_family(model_id: str | None) -> str:
    """Rodzina modelu z identyfikatora (`openrouter/anthropic/claude-opus-5.5` → `claude`); nieznana → `generic`."""
    name = str(model_id or "").strip().lower().rsplit("/", 1)[-1]
    for prefix, family in MODEL_FAMILIES:
        if name.startswith(prefix):
            return family
    return "generic"


CALIBRATION_RE = re.compile(r"<!-- Jarvo:CALIBRATION (orkiestrator|wykonawca) -->.*?<!-- /JARVO:CALIBRATION -->", re.S)


def calibration_section(model_id: str | None, orchestrator: bool, root: Path | None = None) -> str:
    """Blok kalibracji w znacznikach: install-fleet (profile_model.py) podmienia go, gdy w panelu wybrano inny model."""
    role = "orkiestrator" if orchestrator else "wykonawca"
    body = calibration_block(model_id, orchestrator, root)
    return f"<!-- Jarvo:CALIBRATION {role} -->\n{body}\n<!-- /JARVO:CALIBRATION -->" if body else \
        f"<!-- Jarvo:CALIBRATION {role} -->\n<!-- /JARVO:CALIBRATION -->"


def recalibrate_soul(soul: str, model_id: str | None, root: Path | None = None) -> str | None:
    """SOUL z blokiem kalibracji dla innego modelu (ta sama rola); None, gdy SOUL nie ma znaczników."""
    m = CALIBRATION_RE.search(soul)
    if not m:
        return None
    return soul[:m.start()] + calibration_section(model_id, m.group(1) == "orkiestrator", root) + soul[m.end():]


def calibration_block(model_id: str | None, orchestrator: bool, root: Path | None = None) -> str:
    """Sekcja SOUL z kalibracją: część „Wszyscy” + część roli z shared/calibration/<rodzina>.md."""
    family = model_family(model_id)
    path = (root or CALIBRATION_DIR) / f"{family}.md"
    if not path.exists():
        return ""
    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S)
    sections: dict[str, str] = {}
    for part in re.split(r"^### ", text, flags=re.M)[1:]:
        head, _, body = part.partition("\n")
        sections[head.strip().lower()] = body.strip()
    role = "orkiestrator" if orchestrator else "wykonawca"
    body = "\n".join(b for b in (sections.get("wszyscy"), sections.get(role)) if b)
    if not body:
        return ""
    return f"## Jak pracuję na tym modelu ({model_id})\n{body}"
