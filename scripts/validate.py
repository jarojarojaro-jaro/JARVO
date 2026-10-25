#!/usr/bin/env python3
"""Walidacja repo floty Jarvo. Uruchamiana lokalnie (`make validate`), w testach i przy każdym deployu.

Sprawdza: fleet.yaml ↔ profile, kompletność profilu (anatomia z docs/PROFILE-SPEC.md), budżet SOUL,
frontmatter i opisy skilli (≤ 60 znaków, bo tyle widzi model w indeksie), plik blokady skilli,
definicje crona, evals, składnię skryptów, pakiet aplikacji HQ (jednoznaczne nazwy globalne w hq/web/src, te same
klucze tekstów PL/EN), przypadkowe sekrety w repo i zgodność dokumentacji z kodem
(linki i kotwice w *.md, pełna lista floty w dokumentach przeglądowych, liczby skilli i evals w tabelach).
Kod wyjścia 1 przy błędach; ostrzeżenia nie blokują.
"""

from __future__ import annotations

import json
import datetime as dt
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleetlib as fl  # noqa: E402

REQUIRED_FILES = ["SOUL.md", "config.yaml", "distribution.yaml", "toolbox.yaml",
                  "quality/rubric.md", "README.md", "CHANGELOG.md"]
SOUL_REQUIRED = ["## Misja", "## Osobowość"]
# zasada bloku kontekstu (protokół floty, zasada 8; docs/HQ.md „Aplikacja”): każdy złożony SOUL nazywa znaczniki,
# które składa hq/plugin/kontekst.py
SOUL_KONTEKST = ["[Jarvo · kontekst rozmowy <kod>]", "[koniec kontekstu <kod>]", "[Wiadomość właściciela <kod>]"]
# tryb „bezpośrednio” (aplikacja Jarvo, docs/HQ.md §2f): @uchwyt kieruje do agenta tylko jedną wiadomość; ta sama zasada
# w BOSS.md (zasada 6) i w SOUL Jarva, bo inaczej szef i Jarvo opisują aplikację inaczej
TRYB_BEZPOSREDNI = {"docs/BOSS.md": "@ działa na jedną wiadomość: następna bez @ idzie znowu do Jarva.",
                    "profiles/jarvo/SOUL.md": "@ działa na jedną wiadomość."}
# szuflada w wersji minimalnej (spec §15.1): po schowaniu menu Hermesa każda z tych sekcji ma wejście w aplikacji
SZUFLADA_MINIMUM = ("polaczenia", "konto", "system", "stara-baza")
EVAL_TYPES = {"in_scope", "out_of_scope", "safety", "routing", "protocol"}
MIN_EVALS = 10
SECRET_PATTERNS = [
    (re.compile(r"sk-or-v1-[0-9a-f]{20,}"), "klucz OpenRouter"),
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "klucz Anthropic"),
    (re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"), "token bota Telegram"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "klucz AWS"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "klucz prywatny"),
]
# .claude: lokalny katalog Claude Code (robocze kopie agentów w worktrees), nie należy do repo;
# .tools: narzędzia deweloperskie spoza pip (scripts/dev-pwsh.sh), poza gitem
SKIP_DIRS = {".git", ".claude", ".tools", "build", "node_modules", "__pycache__", ".pytest_cache"}
# dokumenty z pełną listą floty: każdy aktywny agent musi w nich wystąpić jako `nazwa`
DOCS_WITH_FLEET = ["README.md", "docs/FLEET.md", "docs/JARVO-CALOSC.md", "docs/BOSS.md", "docs/TOOLBOX.md"]
# kolumny tabel w dokumentach, których liczba w wierszu agenta musi zgadzać się z repo
DOC_COUNT_COLUMNS = {"skille": "skille", "workflowy własne": "skille", "evals": "evals"}
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def w_repo(path: Path) -> str:
    """Ścieżka względem repo w komunikatach: z „/” na każdym systemie, tak jak w dokumentach i testach."""
    return path.relative_to(fl.REPO_ROOT).as_posix()


class Report:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, msg: str):
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)


def check_fleet(fleet: fl.Fleet, r: Report) -> None:
    names = [a.name for a in fleet.agents]
    if len(names) != len(set(names)):
        r.err("fleet.yaml: zduplikowane nazwy agentów")
    active = {a.name for a in fleet.active()}
    for key in ("orchestrator", "reviewer"):
        if fleet.raw.get(key, fleet.orchestrator) not in active:
            r.err(f"fleet.yaml: {key} nie jest aktywnym agentem")
    for a in fleet.agents:
        if a.kind not in fl.AGENT_KINDS:
            r.err(f"{a.name}: nieznany kind {a.kind!r}")
        for tier in (a.model_tier, a.delegation_tier):
            if tier not in fleet.tiers:
                r.err(f"{a.name}: nieznany poziom modelu {tier!r}")
        if a.autonomy_max not in fl.AUTONOMY_LEVELS:
            r.err(f"{a.name}: niepoprawne autonomy_max {a.autonomy_max!r}")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", a.name):
            r.err(f"{a.name}: nazwa profilu musi być [a-z0-9-]")
        if a.status == "active" and not a.dir.is_dir():
            r.err(f"{a.name}: brak katalogu profiles/{a.name}")
        if a.hq_room not in fl.HQ_ROOMS:
            r.err(f"{a.name}: hq_room {a.hq_room!r} spoza {sorted(fl.HQ_ROOMS)}")
        if len(a.description) < 40:
            r.warn(f"{a.name}: krótki opis (routing kanbana opiera się na opisie)")
        # krótka rola w aplikacji (Ustawienia › Zespół, podpowiedź kompozytora): po polsku i po angielsku, do 8 słów
        if a.status == "active":
            for jez, rola in (("rola", a.rola), ("en.rola", a.en.get("rola", ""))):
                if not rola:
                    r.err(f"{a.name}: brak pola {jez} (krótka rola w aplikacji, docs/FLEET.md)")
                elif len(rola.split()) > 8:
                    r.err(f"{a.name}: {jez} ma {len(rola.split())} słów (najwyżej 8)")
    check_uchwyty(fleet, r)
    for d in fl.PROFILES_DIR.iterdir():
        if d.is_dir() and not d.name.startswith("_") and d.name not in names:
            r.err(f"profiles/{d.name}: brak wpisu w fleet.yaml")


def check_uchwyty(fleet: fl.Fleet, r: Report) -> None:
    """Uchwyty `@…` rozmowy aplikacji (docs/FLEET.md „Uchwyty”): każdy aktywny agent ma swój, ASCII
    `^[a-z][a-z0-9]{1,15}$`, unikalny, nie słowo zarezerwowane, a żaden alias (uchwyt, nazwa profilu, hq_short
    i `aliasy` po złożeniu) nie wskazuje dwóch agentów: inaczej `@łowca` mógłby trafić nie tam."""
    wlasciciel: dict[str, str] = {}
    for a in fleet.agents:
        if a.status != "active" and not a.handle:
            continue
        if not a.handle:
            r.err(f"{a.name}: brak `handle` we fleet.yaml (uchwyt @… w rozmowie aplikacji)")
            continue
        if not fl.UCHWYT_RE.fullmatch(a.handle):
            r.err(f"{a.name}: handle {a.handle!r} musi pasować do {fl.UCHWYT_RE.pattern} (ASCII, 2–16 znaków)")
        if a.handle in fl.UCHWYTY_ZAREZERWOWANE:
            r.err(f"{a.name}: handle {a.handle!r} to słowo zarezerwowane ({', '.join(sorted(fl.UCHWYTY_ZAREZERWOWANE))})")
        for alias in a.aliasy:
            if alias in fl.UCHWYTY_ZAREZERWOWANE and alias != a.handle:
                r.err(f"{a.name}: alias {alias!r} to słowo zarezerwowane (zmień hq_short albo `aliasy`)")
            inny = wlasciciel.setdefault(alias, a.name)
            if inny != a.name:
                r.err(f"{a.name}: alias {alias!r} należy już do {inny} (uchwyty i aliasy muszą być jednoznaczne)")


def check_skill_gate(name: str, cfg: dict, r: Report) -> None:
    """Agent, który sam tworzy skille, zapisuje je do poczekalni, nie od razu do profilu (docs/RSI.md §R1)."""
    sk = cfg.get("skills") or {}
    if int(sk.get("creation_nudge_interval") or 0) > 0 and sk.get("write_approval") is not True:
        r.err(f"{name}: config.yaml skills.creation_nudge_interval > 0 bez skills.write_approval: true "
              "(skill agenta ma czekać na zgodę w poczekalni)")


def check_profile(fleet: fl.Fleet, a: fl.Agent, protocol: str, r: Report) -> set[str]:
    d = a.dir
    for rel in REQUIRED_FILES:
        if not (d / rel).exists():
            r.err(f"{a.name}: brak {rel}")
    dist = fl.load_yaml(d / "distribution.yaml") if (d / "distribution.yaml").exists() else {}
    if dist.get("name") != a.name:
        r.err(f"{a.name}: distribution.yaml name={dist.get('name')!r} ≠ nazwa katalogu")
    if dist.get("hermes_requires"):
        r.warn(f"{a.name}: hermes_requires ustawione. Obraz Hermesa może raportować wersję 0.0.0, sprawdź.")
    if a.kind != "generalist" and not (d / ".no-bundled-skills").exists():
        r.err(f"{a.name}: snajper/orkiestrator musi mieć .no-bundled-skills (izolacja skilli)")
    if a.kind == "generalist" and (d / ".no-bundled-skills").exists():
        r.warn(f"{a.name}: generalista z .no-bundled-skills nie dostanie katalogu Hermesa")

    soul = (d / "SOUL.md").read_text(encoding="utf-8") if (d / "SOUL.md").exists() else ""
    if fl.PROTOCOL_MARKER not in soul:
        r.err(f"{a.name}: SOUL.md bez znacznika {fl.PROTOCOL_MARKER}")
    for h in SOUL_REQUIRED:
        if h not in soul:
            r.err(f"{a.name}: SOUL.md bez sekcji {h!r}")
    zlozony = soul.replace(fl.PROTOCOL_MARKER, fl.protocol_for(protocol, a.name == fleet.orchestrator))
    for znacznik in SOUL_KONTEKST:
        if znacznik not in zlozony:
            r.err(f"{a.name}: SOUL z protokołem bez zasady bloku kontekstu (brak {znacznik!r}; protokół, zasada 8)")
    if a.name == fleet.orchestrator and fl.ROSTER_MARKER not in soul:
        r.err(f"{a.name}: SOUL.md orkiestratora bez {fl.ROSTER_MARKER}")
    # budżet z najdłuższą kalibracją, jaką agent może dostać (zmiana dostawcy albo modelu w panelu)
    orch = a.name == fleet.orchestrator
    calib = max((fl.calibration_section(f"{fam}-x", orch) for fam in CALIBRATION_FAMILIES), key=len)
    _, pominiete = fl.available_skills(d / "skills")        # sekcja „Czego nie zrobisz” z buildu też jest w prefiksie
    dopisek = "\n\n" + fl.missing_section(pominiete, fleet) if pominiete else ""
    tokens = fl.approx_tokens(soul.replace(fl.PROTOCOL_MARKER, f"{fl.protocol_for(protocol, orch)}\n\n{calib}") + dopisek)
    if tokens > fl.SOUL_TOKEN_BUDGET:
        r.err(f"{a.name}: SOUL ~{tokens} tokenów (z protokołem i kalibracją) > budżet {fl.SOUL_TOKEN_BUDGET}")

    cfg_text = (d / "config.yaml").read_text(encoding="utf-8") if (d / "config.yaml").exists() else ""
    try:
        cfg = fl.loads_yaml(cfg_text) or {}
    except Exception as exc:
        r.err(f"{a.name}: config.yaml nie parsuje się: {exc}")
        cfg = {}
    if (cfg.get("model") or {}).get("default") != "@@MODEL@@":
        r.err(f"{a.name}: config.yaml model.default musi być tokenem @@MODEL@@ (modele zarządza fleet.yaml)")
    if "cli" not in (cfg.get("platform_toolsets") or {}):
        r.err(f"{a.name}: config.yaml bez platform_toolsets.cli (pracownicy kanbana używają cli)")
    check_skill_gate(a.name, cfg, r)
    toolsets = cfg.get("platform_toolsets") or {}
    # czat Jarvo HQ idzie przez platformę api_server: bez wpisu Hermes daje jej domyślny zestaw (u orkiestratora
    # terminal bez kanbana), więc każdy profil ma ją jawnie, tak jak Telegram
    if "telegram" in toolsets and "api_server" not in toolsets:
        r.err(f"{a.name}: config.yaml bez platform_toolsets.api_server (czat HQ dostałby domyślne narzędzia Hermesa)")
    for plat, label in (("telegram", "Telegramie"), ("api_server", "czacie HQ (api_server)")):
        if a.name == fleet.orchestrator and plat in toolsets and "kanban" not in toolsets[plat]:
            r.err(f"{a.name}: orkiestrator bez toolsetu kanban na {label}")
        if a.name == fleet.orchestrator and "terminal" in (toolsets.get(plat) or []):
            r.err(f"{a.name}: orkiestrator nie powinien mieć terminala na {label} (nie wykonuje pracy)")
    if a.kind == "generalist":
        # prawa ręka czyta skille wszystkich snajperów (tylko do odczytu); nowy snajper musi tu trafić
        dirs = " ".join((cfg.get("skills") or {}).get("external_dirs") or [])
        for s in fleet.active():
            if s.kind == "specialist" and f"/profiles/{s.name}/skills" not in dirs:
                r.err(f"{a.name}: skills.external_dirs bez skilli {s.name} (generalista czyta skille wszystkich snajperów)")
    appr = cfg.get("approvals") or {}
    for key in ("cron_mode", "single_query_mode", "unattended_mode"):
        if appr.get(key) != "deny":
            r.err(f"{a.name}: approvals.{key} musi być 'deny' (pracownicy bez człowieka nie zatwierdzają A2)")
    check_komputer(a, cfg, r)

    names: set[str] = set()
    for skill_md in fl.iter_skill_files(d / "skills"):
        rel = skill_md.parent.relative_to(d / "skills").as_posix()
        try:
            fm, body = fl.read_skill(skill_md)
        except Exception as exc:
            r.err(f"{a.name}/{rel}: frontmatter nie parsuje się: {exc}")
            continue
        try:  # Hermes serializuje frontmatter do JSON: niecytowana data (2026-09-26) = skill „nieznany”
            json.dumps(fm)
        except TypeError as exc:
            r.err(f"{a.name}/{rel}: frontmatter nie jest zgodny z JSON ({exc}); daty w cudzysłowie")
        name = str(fm.get("name", ""))
        if name != skill_md.parent.name:
            r.err(f"{a.name}/{rel}: name={name!r} ≠ nazwa katalogu")
        if name in names:
            r.err(f"{a.name}: zduplikowana nazwa skilla {name!r}")
        names.add(name)
        desc = str(fm.get("description", ""))
        if not desc:
            r.err(f"{a.name}/{rel}: brak description")
        elif len(desc) > fl.SKILL_PROMPT_DESC_LIMIT:
            r.err(f"{a.name}/{rel}: description {len(desc)} > {fl.SKILL_PROMPT_DESC_LIMIT} znaków (Hermes ucina w indeksie)")
        jarvo = ((fm.get("metadata") or {}).get("jarvo") or {})
        if jarvo.get("agent") != a.name:
            r.err(f"{a.name}/{rel}: metadata.jarvo.agent={jarvo.get('agent')!r}")
        if jarvo.get("autonomy") not in fl.AUTONOMY_LEVELS:
            r.err(f"{a.name}/{rel}: metadata.jarvo.autonomy niepoprawne")
        reviewed = str(jarvo.get("reviewed", ""))
        try:
            age = (dt.date.today() - dt.date.fromisoformat(reviewed)).days
            if age > fl.SWIEZOSC_DNI:
                r.warn(f"{a.name}/{rel}: reviewed {reviewed} (> {fl.SWIEZOSC_DNI} dni)")
        except ValueError:
            r.err(f"{a.name}/{rel}: metadata.jarvo.reviewed musi być RRRR-MM-DD")
        if len(body.split()) < 80:
            r.warn(f"{a.name}/{rel}: bardzo krótki skill ({len(body.split())} słów)")
        for ref in re.findall(r"`(references/[^`\s]+)`", body):
            if "<" in ref or "{" in ref:   # wzorzec (np. rubric-<agent>.md generowane przy buildzie)
                continue
            if not (skill_md.parent / ref).exists():
                r.err(f"{a.name}/{rel}: odwołanie do nieistniejącego {ref}")
    for ref in re.findall(r"\$HERMES_HOME/scripts/([A-Za-z0-9_.-]+)", soul + "".join(
            p.read_text(encoding="utf-8") for p in (d / "skills").rglob("*.md"))):
        if not (d / "scripts" / ref).exists():
            r.err(f"{a.name}: odwołanie do nieistniejącego skryptu scripts/{ref}")
    return names



# computer_use (docs/KOMPUTER.md): klucze zgód Hermesa `cua:<akcja>:<background|foreground>`, porównywane dokładnie
# (bez gwiazdek); akcje zmieniające ekran z tools/computer_use/tool.py przypiętego Hermesa + zasięg bring_to_front
CUA_AKCJE = {"click", "double_click", "right_click", "middle_click", "drag", "scroll", "type", "key", "set_value",
             "focus_app", "bring_to_front"}
# działania wejścia, które Hermes wysyła z delivery_mode; na pulpicie X11 klawiatura, przewijanie i przeciąganie
# działają tylko na wierzchu, a wejście Komputera przepuszcza je tylko w oknie już aktywnym (docs/KOMPUTER.md §6)
CUA_NA_WIERZCHU = {"click", "double_click", "right_click", "middle_click", "drag", "scroll", "type", "key"}
CUA_KLUCZ = re.compile(r"^cua:([a-z_]+):(background|foreground)$")


def check_komputer(a: fl.Agent, cfg: dict, r: Report) -> None:
    """Ekran sterują tylko agenci z `komputer: true` we fleet.yaml, bez lokalnego terminala i bez trybów, które
    wyłączają zgody (`approvals.mode: off` i /yolo przełączają sterownik w tryb bez ograniczeń)."""
    toolsets = cfg.get("platform_toolsets") or {}
    plats = sorted(p for p, ts in toolsets.items() if "computer_use" in (ts or []))
    if plats and not a.komputer:
        r.err(f"{a.name}: toolset computer_use na {', '.join(plats)} bez `komputer: true` we fleet.yaml")
    appr = cfg.get("approvals") or {}
    if appr.get("mode") is False or str(appr.get("mode", "")).lower() == "off":     # YAML 1.1: `off` = False
        r.err(f"{a.name}: approvals.mode: off wyłącza wszystkie zgody (także computer_use); zostaw smart albo manual")
    lista = cfg.get("command_allowlist") or []
    if "allowlist" in appr:
        r.err(f"{a.name}: approvals.allowlist nie istnieje w Hermesie; stałe zgody to command_allowlist na górze configu")
    for wpis in lista:
        wpis = str(wpis)
        if "*" in wpis or "?" in wpis:
            r.err(f"{a.name}: command_allowlist {wpis!r}: Hermes porównuje klucze dokładnie, gwiazdki nic nie znaczą")
        if wpis.startswith("cua:"):
            m = CUA_KLUCZ.match(wpis)
            if not a.komputer:
                r.err(f"{a.name}: command_allowlist {wpis!r} bez `komputer: true` we fleet.yaml")
            elif not m or m.group(1) not in CUA_AKCJE:
                r.err(f"{a.name}: command_allowlist {wpis!r}: zły klucz, wzór cua:<akcja>:<background|foreground>")
            elif m.group(1) == "bring_to_front":
                r.err(f"{a.name}: command_allowlist {wpis!r}: okno na wierzch zatwierdza człowiek przy każdym "
                      "działaniu, nie stała zgoda (docs/KOMPUTER.md §8)")
            elif m.group(2) == "foreground" and m.group(1) not in CUA_NA_WIERZCHU:
                r.err(f"{a.name}: command_allowlist {wpis!r}: na wierzchu tylko działania wejścia "
                      f"({', '.join(sorted(CUA_NA_WIERZCHU))})")
        if wpis.startswith("plugin_rule:komputer"):
            r.err(f"{a.name}: command_allowlist {wpis!r}: zgody na Twój komputer daje tylko człowiek, nie config")
    if (cfg.get("bot_desktop") or {}).get("auto_start"):
        r.err(f"{a.name}: bot_desktop.auto_start: ekran agenta to Komputer Jarva (docs/KOMPUTER.md), nie pulpit Hermesa")
    if a.komputer:
        terminal = cfg.get("terminal") or {}
        for plat, ts in toolsets.items():
            ts = ts or []
            if "code_execution" in ts:
                r.err(f"{a.name}: agent z computer_use nie może mieć code_execution (na {plat}): kod działałby obok kluczy floty")
            if "terminal" in ts and str(terminal.get("backend", "local")) == "local":
                r.err(f"{a.name}: agent z computer_use nie ma lokalnego terminala (na {plat}); terminal tylko w Komputerze Jarva")
        if "terminal" in {t for ts in toolsets.values() for t in (ts or [])} and terminal.get("sync_back_max_bytes") != 0:
            r.err(f"{a.name}: terminal w Komputerze Jarva wymaga terminal.sync_back_max_bytes: 0 "
                  "(zdalny katalog nie wraca do profilu)")

CALIBRATION_FAMILIES = ("gpt", "claude", "deepseek", "kimi", "generic")
CALIBRATION_MAX_RULES = 3   # reguł na sekcję: każda nowa wypiera inną (shared/calibration/README.md)


def check_calibration(r: Report) -> None:
    """shared/calibration/<rodzina>.md: sekcje Wszyscy / Orkiestrator / Wykonawca, najwyżej 3 reguły w każdej."""
    import re as _re

    for fam in CALIBRATION_FAMILIES:
        path = fl.CALIBRATION_DIR / f"{fam}.md"
        if not path.exists():
            r.err(f"calibration: brak {w_repo(path)}")
            continue
        text = _re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=_re.S)
        parts = {p.partition("\n")[0].strip(): p.partition("\n")[2] for p in _re.split(r"^### ", text, flags=_re.M)[1:]}
        for sec in ("Wszyscy", "Orkiestrator", "Wykonawca"):
            if sec not in parts:
                r.err(f"calibration/{fam}.md: brak sekcji ### {sec}")
                continue
            rules = [ln for ln in parts[sec].splitlines() if ln.lstrip().startswith("- ")]
            if not rules:
                r.err(f"calibration/{fam}.md: sekcja {sec} bez reguł")
            elif len(rules) > CALIBRATION_MAX_RULES:
                r.err(f"calibration/{fam}.md: sekcja {sec} ma {len(rules)} reguł (max {CALIBRATION_MAX_RULES})")


def check_lock(fleet: fl.Fleet, own: dict[str, set[str]], r: Report) -> None:
    lock = fl.load_lock()
    sources = lock.get("sources", {})
    for name, spec in sources.items():
        if spec.get("type") == "git" and not re.fullmatch(r"[0-9a-f]{40}", str(spec.get("rev", ""))):
            r.err(f"lock: źródło {name} musi być przypięte do pełnego SHA")
        if not spec.get("license"):
            r.err(f"lock: źródło {name} bez licencji")
    active = {a.name for a in fleet.active()}
    for agent, entries in (lock.get("agents") or {}).items():
        if agent not in active:
            r.err(f"lock: agent {agent} nie jest aktywny we fleet.yaml")
        dests, vnames = set(), set()
        for e in entries or []:
            if e.get("source") not in sources:
                r.err(f"lock/{agent}: nieznane źródło {e.get('source')!r}")
            dest = str(e.get("dest", ""))
            if not re.fullmatch(r"[a-z0-9-]+/[a-z0-9-]+", dest):
                r.err(f"lock/{agent}: dest {dest!r} musi mieć postać kategoria/nazwa")
            if dest in dests:
                r.err(f"lock/{agent}: zduplikowany dest {dest}")
            pomin = e.get("pomin")
            if pomin is not None and (not isinstance(pomin, list) or not all(isinstance(p, str) and p for p in pomin)
                                      or "SKILL.md" in pomin or any(p.upper().startswith("LICENSE") for p in pomin)):
                r.err(f"lock/{agent}: {dest}: `pomin` to lista wzorców plików (bez SKILL.md i licencji)")
            dests.add(dest)
            vname = dest.split("/")[-1]
            if vname in vnames or vname in own.get(agent, set()):
                r.err(f"lock/{agent}: kolizja nazwy skilla {vname!r}")
            vnames.add(vname)


def check_skan_wyjatki(r: Report) -> None:
    """vendor/skan-wyjatki.yaml: każdy wyjątek skanu wskazuje skill z locka, ma przypięty rev i powód."""
    path = fl.REPO_ROOT / "vendor" / "skan-wyjatki.yaml"
    if not path.exists():
        return
    lock = fl.load_lock()
    sources = lock.get("sources", {})
    entries = {(e.get("source"), e.get("path")) for es in (lock.get("agents") or {}).values() for e in es or []}
    for i, w in enumerate((fl.load_yaml(path) or {}).get("wyjatki") or [], 1):
        tag = f"skan-wyjatki #{i} ({w.get('zrodlo')}:{w.get('skill')})"
        for pole in ("zrodlo", "rev", "skill", "regula", "powod"):
            if not w.get(pole):
                r.err(f"{tag}: brak pola {pole}")
        spec = sources.get(w.get("zrodlo"))
        if spec is None:
            r.err(f"{tag}: nieznane źródło")
            continue
        if (w.get("zrodlo"), w.get("skill")) not in entries:
            r.err(f"{tag}: tego skilla nie ma w locku")
        rev = str(w.get("rev") or "")
        if rev == "*" and spec.get("type") != "repo-tree":
            r.err(f"{tag}: rev „*” tylko dla skilli z tego repo; cudze przypinamy do commitu")
        if spec.get("type") == "git" and rev != "*" and not str(spec.get("rev", "")).startswith(rev):
            r.warn(f"{tag}: rev {rev} ≠ lock {str(spec.get('rev'))[:7]}: wyjątek nie działa, przejrzyj ustalenie na nowo")


ZRODLA_STATUSY = {"uzywane", "do-wdrozenia", "czeka", "odlozone"}


def check_zrodla(r: Report) -> None:
    """vendor/zrodla.yaml: każde repo z docs/SOURCES.md i skills.lock.yaml jest w spisie, z przejrzanym commitem.
    Repo z GitHuba albo model z Hugging Face (to też repozytorium: `zrodla.py sprawdz` pyta je tak samo); model ze spisu
    musi mieć atrybucję w SOURCES.md, ale nie każdy model z SOURCES.md jest w spisie (pobierane w locie trzyma pin)."""
    path = fl.REPO_ROOT / "vendor" / "zrodla.yaml"
    if not path.exists():
        r.err("brak vendor/zrodla.yaml (spis źródeł)")
        return
    zrodla = (fl.load_yaml(path) or {}).get("zrodla") or {}
    repos: dict[str, str] = {}
    for name, spec in zrodla.items():
        spec = spec or {}
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(name)):
            r.err(f"zrodla: nazwa {name!r} tylko z małych liter, cyfr i myślników")
        if spec.get("paczka"):          # źródło bez repo git: archiwum, przejrzane = SHA-256 paczki
            if not re.fullmatch(r"https://[^\s]+\.(tar\.gz|tgz|tar\.xz|tar\.bz2|tar|zip)", str(spec["paczka"])):
                r.err(f"zrodla/{name}: paczka musi być adresem https archiwum .tar.gz / .tgz / .tar.xz / .tar.bz2 "
                      "/ .tar / .zip")
            if not re.fullmatch(r"[0-9a-f]{64}", str(spec.get("przejrzane", ""))):
                r.err(f"zrodla/{name}: przejrzane paczki musi być jej SHA-256 (64 znaki)")
            if spec.get("kopia") and not (fl.REPO_ROOT / str(spec["kopia"])).is_dir():
                r.err(f"zrodla/{name}: kopia {spec['kopia']} nie istnieje w repo")
            if spec.get("status") not in ZRODLA_STATUSY:
                r.err(f"zrodla/{name}: status {spec.get('status')!r} spoza {sorted(ZRODLA_STATUSY)}")
            continue
        m = re.fullmatch(r"https://(?:github\.com/|(huggingface\.co/))([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)",
                         str(spec.get("repo", "")))
        klucz = ((m.group(1) or "") + m.group(2)).lower() if m else ""      # owner/repo albo huggingface.co/owner/model
        if not m:
            r.err(f"zrodla/{name}: repo musi być adresem https://github.com/<właściciel>/<repo> "
                  "albo https://huggingface.co/<właściciel>/<model>")
        elif klucz in repos:
            r.err(f"zrodla/{name}: repo już w spisie jako {repos[klucz]}")
        else:
            repos[klucz] = name
        if spec.get("status") not in ZRODLA_STATUSY:
            r.err(f"zrodla/{name}: status {spec.get('status')!r} spoza {sorted(ZRODLA_STATUSY)}")
        if not re.fullmatch(r"[0-9a-f]{40}", str(spec.get("przejrzane", ""))):
            r.err(f"zrodla/{name}: przejrzane musi być pełnym SHA commitu")
        if "galaz" in spec and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", str(spec["galaz"] or "")):
            r.err(f"zrodla/{name}: galaz to nazwa gałęzi wydań (np. 8.1), bez refs/heads/")
    sources_md = (fl.REPO_ROOT / "docs" / "SOURCES.md").read_text(encoding="utf-8")
    w_sources = {m.lower().removesuffix(".git").rstrip(".")
                 for m in re.findall(r"github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", sources_md)}
    w_modele = {"huggingface.co/" + m.lower() for m in
                re.findall(r"huggingface\.co/(?!datasets/|spaces/)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", sources_md)}
    for repo in sorted(w_sources - set(repos)):
        r.err(f"zrodla: github.com/{repo} (docs/SOURCES.md) nie ma w vendor/zrodla.yaml")
    for name, spec in (fl.load_lock().get("sources") or {}).items():
        url = str(spec.get("repo", "")).lower().removesuffix(".git")
        if spec.get("type") == "git" and url.removeprefix("https://github.com/") not in repos:
            r.err(f"zrodla: źródło {name} z skills.lock.yaml ({url}) nie ma w vendor/zrodla.yaml")
    w_lock = {str(s.get("repo", "")).lower().removesuffix(".git").removeprefix("https://github.com/")
              for s in (fl.load_lock().get("sources") or {}).values()}
    for repo, name in repos.items():
        if zrodla[name].get("status") == "uzywane" and repo not in w_sources | w_lock | w_modele:
            r.err(f"zrodla/{name}: status uzywane, a repo nie ma w docs/SOURCES.md (licencja i atrybucja)")


def check_cron(a: fl.Agent, own_skills: set[str], vendored: set[str], r: Report) -> None:
    src = a.dir / "cron" / "jobs.yaml"
    if not src.exists():
        return
    spec = fl.load_yaml(src) or {}
    ids = set()
    for job in spec.get("jobs", []) or []:
        jid = job.get("id", "")
        if not jid.startswith(a.name + "-") and not jid.startswith(a.name.replace("jarvo-", "") + "-"):
            r.err(f"{a.name}/cron: id {jid!r} musi zaczynać się od nazwy agenta")
        if jid in ids:
            r.err(f"{a.name}/cron: zduplikowane id {jid}")
        ids.add(jid)
        if not job.get("schedule"):
            r.err(f"{a.name}/cron/{jid}: brak schedule")
        if job.get("script") and not (a.dir / "scripts" / job["script"]).exists():
            r.err(f"{a.name}/cron/{jid}: brak skryptu scripts/{job['script']}")
        for s in job.get("skills", []) or []:
            if s not in own_skills and s not in vendored:
                r.err(f"{a.name}/cron/{jid}: skill {s!r} nie istnieje w profilu")


def check_related(a: fl.Agent, known: set[str], r: Report) -> None:
    """metadata.hermes.related_skills własnych skilli wskazują skille, które są w profilu (własne + z locka).

    Profil z .no-bundled-skills nie ma skilli wbudowanych Hermesa, więc brak = błąd; w pozostałych ostrzeżenie
    (odwołanie może dotyczyć skilla wbudowanego)."""
    strict = (a.dir / ".no-bundled-skills").exists()
    for skill_md in fl.iter_skill_files(a.dir / "skills"):
        try:
            fm, _ = fl.read_skill(skill_md)
        except Exception:
            continue    # błąd frontmattera zgłasza check_profile
        related = ((fm.get("metadata") or {}).get("hermes") or {}).get("related_skills") or []
        for name in related:
            if str(name) not in known:
                msg = f"{a.name}/{skill_md.parent.name}: related_skills {name!r} nie istnieje w profilu"
                r.err(msg) if strict else r.warn(msg)


def check_evals(fleet: fl.Fleet, r: Report) -> None:
    import evalslib as ev
    kanarki: dict[str, str] = {}
    for a in fleet.active():
        path = fl.REPO_ROOT / "evals" / a.name / "scenarios.yaml"
        if not path.exists():
            r.err(f"{a.name}: brak evals/{a.name}/scenarios.yaml")
            continue
        data = fl.load_yaml(path) or {}
        scen = data.get("scenarios") or []
        tok = data.get("kanarek")
        if not isinstance(tok, str) or not ev.KANAREK_RE.match(tok):
            r.err(f"{a.name}/evals: brak kanarka albo zły format (kanarek: \"JARVO-KANAREK-<12 hex>\", docs/RSI.md)")
        elif tok in kanarki.values():
            r.err(f"{a.name}/evals: kanarek taki sam jak u {next(k for k, v in kanarki.items() if v == tok)}")
        else:
            kanarki[a.name] = tok
        if sum(1 for s in scen if ev.zbior(s) == "odlozony") < 2:
            r.err(f"{a.name}/evals: < 2 scenariuszy w zbiorze odłożonym (pole zbior: odlozony, docs/RSI.md)")
        if len(scen) < MIN_EVALS:
            r.err(f"{a.name}: {len(scen)} scenariuszy evals < {MIN_EVALS} (Definition of Ready)")
        ids = set()
        n_out = 0
        for s in scen:
            sid = s.get("id")
            if not sid or sid in ids:
                r.err(f"{a.name}/evals: brak albo duplikat id {sid!r}")
            ids.add(sid)
            if s.get("type") not in EVAL_TYPES:
                r.err(f"{a.name}/evals/{sid}: typ {s.get('type')!r}")
            if "zbior" in s and s["zbior"] not in ev.ZBIORY:
                r.err(f"{a.name}/evals/{sid}: zbior {s['zbior']!r} (dozwolone: {', '.join(ev.ZBIORY)})")
            if not str(s.get("input", "")).strip():
                r.err(f"{a.name}/evals/{sid}: brak input")
            if not (s.get("expect") or {}).get("should"):
                r.err(f"{a.name}/evals/{sid}: brak expect.should")
            n_out += s.get("type") == "out_of_scope"
        if a.name != fleet.orchestrator and n_out < 3:
            r.err(f"{a.name}: evals mają {n_out} scenariuszy out_of_scope (< 3)")


def check_scripts(r: Report) -> None:
    bash = fl.bash()                # na Windows Git Bash, nigdy System32\bash.exe (WSL)
    bez_basha = 0
    for path in sorted(fl.REPO_ROOT.rglob("*")):
        if any(p in SKIP_DIRS for p in path.parts) or not path.is_file():
            continue
        if path.suffix == ".py":
            # kompilacja w pamięci: repo w kontenerze jest tylko do odczytu (py_compile chce zapisać .pyc)
            try:
                compile(path.read_text(encoding="utf-8"), str(path), "exec", dont_inherit=True)
            except SyntaxError as exc:
                r.err(f"{w_repo(path)}: błąd składni Pythona: {exc.msg} (linia {exc.lineno})")
        elif path.suffix == ".sh":
            if bash is None:
                bez_basha += 1
                continue
            res = subprocess.run([bash, "-n", str(path)], capture_output=True, text=True, encoding="utf-8",
                                 errors="replace")
            if res.returncode:
                r.err(f"{w_repo(path)}: błąd składni bash: {res.stderr.strip()[:200]}")
        elif path.suffix in {".cjs", ".mjs", ".js"} and shutil.which("node"):
            res = subprocess.run([shutil.which("node"), "--check", str(path)], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace")
            if res.returncode:
                r.err(f"{w_repo(path)}: błąd składni JS: {res.stderr.strip()[:200]}")
    if bez_basha:
        r.warn(f"składnia {bez_basha} skryptów .sh niesprawdzona: brak basha (na Windows potrzebny Git Bash)")


def check_secrets(r: Report) -> None:
    for path in sorted(fl.REPO_ROOT.rglob("*")):
        if any(p in SKIP_DIRS for p in path.parts) or not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        if path.name == ".env" or (path.suffix == ".env" and not path.name.endswith(".example")):
            r.err(f"{w_repo(path)}: plik .env nie może być w repo")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(text):
                r.err(f"{w_repo(path)}: wygląda na {label}")


# pakiet aplikacji to sklejone hq/web/src/*.js w jednym IIFE: nazwy z najwyższego poziomu muszą być jednoznaczne
# (dwie funkcje o tej samej nazwie nie wywracają składni, druga po cichu zastępuje pierwszą)
NAZWA_GLOBALNA = re.compile(r"^(?:async\s+)?(?:function\*?|class|const|let|var)\s+([A-Za-z_$][\w$]*)", re.M)
DESTRUKTURYZACJA = re.compile(r"^(?:const|let|var)\s*[{\[]([^=]*?)[}\]]\s*=", re.M)


def nazwy_globalne_js(tekst: str) -> list[str]:
    """Nazwy deklarowane w kolumnie 0 pliku źródłowego pakietu (także z destrukturyzacji `const { a, b: c } = …`)."""
    nazwy = NAZWA_GLOBALNA.findall(tekst)
    for wnetrze in DESTRUKTURYZACJA.findall(tekst):
        for cz in wnetrze.split(","):
            nazwa = cz.strip().removeprefix("...").split(":")[-1].split("=")[0].strip()
            if re.fullmatch(r"[A-Za-z_$][\w$]*", nazwa):
                nazwy.append(nazwa)
    return nazwy


def slownik_i18n(tekst: str) -> dict[str, dict[str, set[str] | None]]:
    """SLOWNIK z hq/web/src/04-i18n.js: {"pl"|"en": {klucz: formy liczby mnogiej albo None}}."""
    napis = r'"(?:[^"\\]|\\.)*"'
    wpis = re.compile(rf'"([a-z0-9_.-]+)":\s*(\{{(?:[^{{}}"]|{napis})*\}}|{napis})')
    pl = tekst.split("\n  pl: {", 1)[1].split("\n  en: {", 1)[0]
    en = tekst.split("\n  en: {", 1)[1].split("\n};", 1)[0]
    return {j: {k: (set(re.findall(r"(\w+):\s*\"", v)) if v.startswith("{") else None) for k, v in wpis.findall(blok)}
            for j, blok in (("pl", pl), ("en", en))}


FORMY_MNOGIE = {"pl": {"one", "few", "many", "other"}, "en": {"one", "other"}}


def check_hq_pakiet(r: Report) -> None:
    """Pakiet aplikacji (docs/HQ.md „Aplikacja”): jednoznaczne nazwy globalne i te same klucze tekstów PL/EN."""
    src = fl.REPO_ROOT / "hq" / "web" / "src"
    gdzie: dict[str, str] = {}
    for f in sorted(src.glob("*.js")):
        for nazwa in nazwy_globalne_js(f.read_text(encoding="utf-8")):
            if nazwa in gdzie:
                r.err(f"hq/web/src/{f.name}: nazwa {nazwa!r} jest już w {gdzie[nazwa]} (pakiet to jeden zakres)")
            else:
                gdzie[nazwa] = f.name
    i18n = src / "04-i18n.js"
    if not i18n.exists():
        return
    try:
        sl = slownik_i18n(i18n.read_text(encoding="utf-8"))
    except IndexError:
        r.err("hq/web/src/04-i18n.js: brak bloków pl / en w SLOWNIK")
        return
    for brak, jest, jezyk in ((set(sl["pl"]) - set(sl["en"]), "pl", "en"), (set(sl["en"]) - set(sl["pl"]), "en", "pl")):
        for k in sorted(brak):
            r.err(f"hq/web/src/04-i18n.js: klucz {k!r} jest w {jest}, brak w {jezyk}")
    for jezyk, wpisy in sl.items():
        for k, formy in wpisy.items():
            inny = sl["en" if jezyk == "pl" else "pl"].get(k, formy)
            if (formy is None) != (inny is None):
                r.err(f"hq/web/src/04-i18n.js: {k!r} ma liczbę mnogą tylko w jednym języku")
            elif formy is not None and not FORMY_MNOGIE[jezyk] <= formy:
                r.err(f"hq/web/src/04-i18n.js: {jezyk} {k!r} bez form {sorted(FORMY_MNOGIE[jezyk] - formy)}")
    # szuflada (61-szuflada.js): sekcje minimum z §15.1, każda z nazwą w słowniku; Klucze i Modele osadzone
    szuflada = src / "61-szuflada.js"
    if szuflada.exists():
        kod = szuflada.read_text(encoding="utf-8")
        blok = kod.split("const SEKCJE_SZUFLADY = [", 1)[-1].split("];", 1)[0]
        sekcje = re.findall(r'id:\s*"([a-z-]+)"', blok)
        for brak in [x for x in SZUFLADA_MINIMUM if x not in sekcje]:
            r.err(f"hq/web/src/61-szuflada.js: brak sekcji {brak!r} w SEKCJE_SZUFLADY (spec §15.1: nic bez wejścia)")
        for sid in sekcje:
            if f"szuflada.{sid}" not in sl["pl"]:
                r.err(f"hq/web/src/04-i18n.js: brak klucza 'szuflada.{sid}' (nazwa sekcji szuflady)")
        osadzone = kod.split("const OSADZONE = {", 1)[-1].split("}", 1)[0]
        for pod in ("klucze", "modele"):
            if f"{pod}:" not in osadzone:
                r.err(f"hq/web/src/61-szuflada.js: OSADZONE bez {pod!r} (Połączenia › Klucze i Modele)")
    for rel, zdanie in TRYB_BEZPOSREDNI.items():
        plik = fl.REPO_ROOT / rel
        tekst = " ".join(plik.read_text(encoding="utf-8").split()) if plik.exists() else ""
        if zdanie not in tekst:
            r.err(f"{rel}: brak zasady trybu „bezpośrednio” ({zdanie!r}; docs/HQ.md §2f)")


def check_hq(r: Report) -> None:
    """Jarvo HQ (plugin dashboardu): pliki, manifest, zgodność pokoi z grafiką, licencja htm."""
    import json
    hq = fl.REPO_ROOT / "hq"
    if not hq.exists():
        return
    for rel in ("plugin/manifest.json", "plugin/plugin_api.py", "plugin/hq_core.py", "plugin/ochrona.py", "web/style.css",
                "plugin/rozmowy.py", "plugin/czytnik.py", "plugin/wzmianki.py", "plugin/kontekst.py", "plugin/agenci.py",
                "plugin/brama.py", "plugin/strumien.py", "plugin/przebiegi.py", "plugin/scalanie.py", "plugin/budzenia.py",
                "plugin/prace.py", "plugin/obserwator.py", "plugin/silnik.py", "plugin/trasy_rozmow.py",
                "plugin/aplikacja.py", "plugin/podpowiedzi.py", "plugin/glos.py", "plugin/trasy_aplikacji.py",
                "web/src/12-wzmianki.js", "web/src/38-start.js", "web/src/61-szuflada.js",
                "web/vendor/htm.umd.js", "web/vendor/LICENSE-htm", "web/demo/index.html", "web/demo/mock.js"):
        if not (hq / rel).exists():
            r.err(f"hq: brak {rel}")
    # każdy moduł wtyczki trafia do builda (hqbuild.PLUGIN_FILES), inaczej _load w plugin_api.py padnie w kontenerze
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_hqbuild_walidacja", fl.REPO_ROOT / "scripts" / "hqbuild.py")
        hqb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hqb)
        for p in sorted((hq / "plugin").glob("*.py")):
            if p.name not in hqb.PLUGIN_FILES:
                r.err(f"hq/plugin/{p.name}: brak w scripts/hqbuild.py PLUGIN_FILES (nie trafi do wtyczki)")
    except Exception as exc:  # noqa: BLE001
        r.err(f"scripts/hqbuild.py: nie wczytuje się ({type(exc).__name__})")
    try:
        manifest = json.loads((hq / "plugin" / "manifest.json").read_text(encoding="utf-8"))
        for key in ("name", "label", "entry", "tab"):
            if not manifest.get(key):
                r.err(f"hq/manifest.json: brak pola {key}")
        # zakładka /jarvo (powłoka w branding/powloka.js przekierowuje tam "/"); styl ładuje loader, nie manifest
        if (manifest.get("tab") or {}).get("path") != "/jarvo" or manifest.get("label") != "Jarvo":
            r.err("hq/manifest.json: zakładka ma mieć path /jarvo i label Jarvo (docs/HQ.md „Powłoka”)")
        if "css" in manifest:
            r.err("hq/manifest.json: bez klucza css (styl wczytuje loader dopiero na /jarvo)")
    except (OSError, ValueError) as exc:
        r.err(f"hq/manifest.json: {exc}")
    # łatka powłoki dashboardu: każdy wpis z dokładną liczbą trafień (patch_dashboard.py wywraca build przy innej)
    try:
        powloka = json.loads((fl.REPO_ROOT / "branding" / "powloka.json").read_text(encoding="utf-8"))
        for grupa, klucze in (("js", ("nazwa", "wzor", "zamiana", "ile", "gotowe")), ("css", ("nazwa", "selektor", "dowod", "ile"))):
            for wpis in powloka.get(grupa) or []:
                brak = [k for k in klucze if k not in wpis]
                if brak or not isinstance(wpis.get("ile"), int) or wpis["ile"] < 1:
                    r.err(f"branding/powloka.json: {grupa} {wpis.get('nazwa', '?')}: brak {brak or 'ile ≥ 1'}")
        if not (fl.REPO_ROOT / "branding" / "powloka.js").exists():
            r.err("branding: brak powloka.js (skrypt powłoki w index.html)")
    except (OSError, ValueError) as exc:
        r.err(f"branding/powloka.json: {exc}")
    # znaczniki bloku kontekstu, które nazywa zasada w każdym SOUL (SOUL_KONTEKST), składa kontekst.py
    kontekst_py = (hq / "plugin" / "kontekst.py").read_text(encoding="utf-8") if (hq / "plugin" / "kontekst.py").exists() else ""
    for znacznik in SOUL_KONTEKST:
        if znacznik.replace("<kod>]", "{kod_bloku}") not in kontekst_py:
            r.err(f"hq/plugin/kontekst.py: nie składa znacznika {znacznik!r} z zasady SOUL (popraw oba miejsca)")
    src = sorted((hq / "web" / "src").glob("*.js"))
    if not src:
        r.err("hq/web/src: brak plików źródłowych")
    art = (hq / "web" / "src" / "20-art.js")
    if art.exists():
        block = art.read_text(encoding="utf-8").split("const ROOMS = {", 1)[-1].split("};", 1)[0]
        js_rooms = set(re.findall(r"^\s+(\w+):\s*\{", block, re.M))
        if js_rooms != fl.HQ_ROOMS:
            r.err(f"hq: pokoje w 20-art.js {sorted(js_rooms)} ≠ fleetlib.HQ_ROOMS {sorted(fl.HQ_ROOMS)}")
    check_hq_pakiet(r)


# stary adres zakładki (sprzed /jarvo): zostaje tylko w powłoce (branding/powloka.js przekierowuje go), w testach
# przekierowania i w CHANGELOG-ach. „/base” jako część nazwy pliku (templates/base.html) to nie adres.
STARY_ADRES = re.compile(r"/base(?![\w.-])")
BEZ_BASE_POMIN = {"CHANGELOG.md"}
BEZ_BASE_KATALOGI = ("site", "hq", "knowledge", "profiles", "shared", "wiedza", "komputer", "infra", "scripts")


def check_bez_base(r: Report) -> None:
    """Adres dashboardu to /jarvo: instalatory, CLI, skrypty, strona, pluginy, profile i dokumenty nie podają starego."""
    root = fl.REPO_ROOT
    pliki = [root / "install.sh", root / "install.ps1", root / "bin" / "jarvo", root / "README.md"]
    pliki += sorted((root / "docs").glob("*.md"))
    for katalog in BEZ_BASE_KATALOGI:
        pliki += sorted(p for p in (root / katalog).rglob("*")
                        if p.is_file() and p.suffix in (".md", ".js", ".cjs", ".html", ".json", ".py", ".sh", ".css", ".yaml", ".yml", ".txt")
                        and p.name not in BEZ_BASE_POMIN and p != Path(__file__).resolve()
                        and not {"node_modules", "vendor", "__pycache__"} & set(p.parts))
    for p in pliki:
        try:
            tekst = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for m in STARY_ADRES.finditer(tekst):
            nr = tekst.count("\n", 0, m.start()) + 1
            r.err(f"{w_repo(p)}:{nr}: stary adres zakładki zamiast /jarvo (docs/HQ.md „Powłoka”)")
    # wersja instalatora hosta: docs/INSTALER.md opisuje bieżącą (co zmienia dla komputera)
    skrypt, opis = root / "install.sh", root / "docs" / "INSTALER.md"
    if not (skrypt.is_file() and opis.is_file()):
        return
    m = re.search(r"^HOST_VERSION=(\d+)$", skrypt.read_text(encoding="utf-8"), re.M)
    if not m or f"`HOST_VERSION` {m.group(1)}" not in opis.read_text(encoding="utf-8"):
        r.err(f"docs/INSTALER.md: brak opisu `HOST_VERSION` {m.group(1) if m else '?'} z install.sh")


def md_slug(heading: str) -> str:
    """Kotwica nagłówka tak, jak liczy ją GitHub: małe litery, bez interpunkcji, spacje → '-'."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def md_without_code(text: str) -> str:
    return re.sub(r"^```.*?^```", "", text, flags=re.S | re.M)


def md_tables(text: str):
    """Tabele Markdown jako listy wierszy (komórki bez `|` i spacji na brzegach)."""
    rows: list[list[str]] = []
    for line in text.splitlines() + [""]:
        if line.startswith("|"):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
        elif rows:
            yield rows
            rows = []


def check_docs(fleet: fl.Fleet, r: Report) -> None:
    """Dokumentacja zgodna z kodem: linki i kotwice istnieją, listy floty są pełne, liczby w tabelach się zgadzają."""
    root = fl.REPO_ROOT
    docs = [p for p in sorted(root.rglob("*.md")) if SKIP_DIRS.isdisjoint(p.relative_to(root).parts)]
    anchors: dict[Path, set[str]] = {}
    for doc in docs:
        text = md_without_code(doc.read_text(encoding="utf-8"))
        for url in MD_LINK.findall(text):
            if re.match(r"[a-z][a-z0-9+.-]*:", url):
                continue
            path, _, anchor = url.partition("#")
            target = (doc.parent / path).resolve() if path else doc
            rel = w_repo(doc)
            if not target.exists():
                r.err(f"{rel}: link do nieistniejącego {url}")
            elif anchor and target.suffix == ".md":
                if target not in anchors:
                    body = md_without_code(target.read_text(encoding="utf-8"))
                    anchors[target] = {md_slug(h) for h in re.findall(r"^#{1,6}\s+(.+)$", body, re.M)}
                if anchor not in anchors[target]:
                    r.err(f"{rel}: kotwica #{anchor} nie istnieje w {path or doc.name}")
    for rel in DOCS_WITH_FLEET:
        path = root / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for a in fleet.active():
            if f"`{a.name}`" not in text:
                r.err(f"{rel}: brak agenta `{a.name}` (dokument opisuje całą flotę)")
    counts = {}
    for a in fleet.active():
        scen = fl.load_yaml(root / "evals" / a.name / "scenarios.yaml") if (root / "evals" / a.name).exists() else {}
        counts[a.name] = {"skille": len(list((a.dir / "skills").rglob("SKILL.md"))),
                          "evals": len((scen or {}).get("scenarios") or [])}
    uchwyty = {a.name: a.handle for a in fleet.active()}
    for doc in docs:
        for table in md_tables(md_without_code(doc.read_text(encoding="utf-8"))):
            # kolumna „Uchwyt”: `@handle` z fleet.yaml (docs/FLEET.md „Uchwyty”)
            kol_uchwytu = next((i for i, h in enumerate(table[0]) if h.lower() == "uchwyt"), None)
            for row in table[2:] if kol_uchwytu is not None else []:
                agent = re.search(r"`(jarvo[a-z0-9-]*)`", row[0])
                if agent and agent.group(1) in uchwyty and kol_uchwytu < len(row) \
                        and not re.search(rf"@{re.escape(uchwyty[agent.group(1)])}(?![a-z0-9_-])", row[kol_uchwytu]):
                    r.err(f"{w_repo(doc)}: {agent.group(1)} ma uchwyt @{uchwyty[agent.group(1)]}, "
                          f"a tabela podaje {row[kol_uchwytu]!r}")
            cols = {i: DOC_COUNT_COLUMNS[h.lower()] for i, h in enumerate(table[0]) if h.lower() in DOC_COUNT_COLUMNS}
            for row in table[2:] if cols else []:
                agent = re.search(r"`(jarvo[a-z0-9-]*)`", row[0])
                if not agent or agent.group(1) not in counts:
                    continue
                for i, kind in cols.items():
                    num = re.search(r"\d+", row[i]) if i < len(row) else None
                    real = counts[agent.group(1)][kind]
                    if num and int(num.group()) != real:
                        r.err(f"{w_repo(doc)}: {agent.group(1)} ma {real} ({kind}), "
                              f"a tabela podaje {num.group()}")


# polecenia, które działają tylko z daną usługą: skill, który ich używa, musi to zadeklarować (`metadata.jarvo.wymaga`)
SERVICE_COMMANDS = {"skarbiec": r"ads\.py (?:szkic|koperta|pauza|budzet|stop)\b"}
PATTERNS_FILE = "skills/fleet/dispatch-playbook/references/patterns.md"


def check_routing(fleet: fl.Fleet, r: Report) -> None:
    """Nowy agent nie może zostać „niewidzialny”: każdy specjalista ma `oddaj_gdy` (generowana tabela Ręki), generalista
    kieruje przez tę tabelę, a Jarvo ma każdego specjalistę we wzorcach misji."""
    aktywni = fleet.active()
    for a in aktywni:
        if a.kind == "specialist" and (not a.oddaj_gdy or a.oddaj_gdy.startswith("TODO")):
            r.err(f"{a.name}: brak `oddaj_gdy` w fleet.yaml (kiedy generalista ma oddać mu zadanie; tabela jest generowana)")
    for a in aktywni:
        if a.kind != "generalist":
            continue
        if not any(fl.ODDAJ_MARKER in p.read_text(encoding="utf-8") for p in (a.dir / "skills").rglob("*.md")):
            r.err(f"{a.name}: żaden skill nie ma znacznika {fl.ODDAJ_MARKER} (tabela „komu oddać” musi być generowana "
                  f"z fleet.yaml, nie pisana ręcznie)")
    orch = next((a for a in aktywni if a.name == fleet.orchestrator), None)
    wzorce = orch.dir / PATTERNS_FILE if orch else None
    if wzorce and wzorce.is_file():
        tekst = wzorce.read_text(encoding="utf-8")
        for a in aktywni:
            if a.kind == "specialist" and f"`{a.name}`" not in tekst:
                r.err(f"{a.name}: nie występuje w żadnym wzorcu misji Jarva ({PATTERNS_FILE})")


def check_services(fleet: fl.Fleet, r: Report) -> None:
    """`metadata.jarvo.wymaga` tylko ze znanych usług; polecenia zależne od usługi tylko w skillach, które ją deklarują."""
    znane = fl.compose_services() | set(((fleet.raw.get("infra") or {}).get("uslugi_planowane") or {}).keys())
    for a in fleet.active():
        for name, path in fl.skill_names(a.dir / "skills").items():
            fm, body = fl.read_skill(path)
            wymaga = fl.skill_requires(fm)
            for u in wymaga:
                if u not in znane:
                    r.err(f"{a.name}/{name}: wymaga nieznanej usługi {u!r} (ani w docker-compose, ani w infra.uslugi_planowane)")
            for usluga, wzor in SERVICE_COMMANDS.items():
                if re.search(wzor, body) and usluga not in wymaga:
                    r.err(f"{a.name}/{name}: używa poleceń usługi {usluga!r}, ale nie deklaruje `wymaga: [{usluga}]`")


def run() -> Report:
    r = Report()
    fleet = fl.load_fleet()
    protocol = (fl.REPO_ROOT / fleet.raw["shared"]["protocol"]).read_text(encoding="utf-8")
    check_fleet(fleet, r)
    check_routing(fleet, r)
    check_services(fleet, r)
    own: dict[str, set[str]] = {}
    lock = fl.load_lock()
    for a in fleet.active():
        own[a.name] = check_profile(fleet, a, protocol, r)
    check_lock(fleet, own, r)
    check_skan_wyjatki(r)
    check_zrodla(r)
    for a in fleet.active():
        vendored = {Path(e["dest"]).name for e in (lock.get("agents", {}).get(a.name) or [])}
        extra = {"roster"} if a.name == fleet.orchestrator else set()
        check_cron(a, own[a.name] | extra, vendored, r)
        check_related(a, own[a.name] | extra | vendored, r)
    check_evals(fleet, r)
    check_calibration(r)
    check_hq(r)
    check_bez_base(r)
    check_docs(fleet, r)
    check_scripts(r)
    check_secrets(r)
    return r


def main() -> int:
    r = run()
    for w in r.warnings:
        print(f"  ⚠ {w}")
    for e in r.errors:
        print(f"  ✗ {e}")
    print(f"Walidacja: {len(r.errors)} błędów, {len(r.warnings)} ostrzeżeń")
    return 1 if r.errors else 0


if __name__ == "__main__":
    sys.exit(main())
