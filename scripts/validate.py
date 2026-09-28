#!/usr/bin/env python3
"""Walidacja repo floty Jarvo. Uruchamiana lokalnie (`make validate`), w testach i przy każdym deployu.

Sprawdza: fleet.yaml ↔ profile, kompletność profilu (anatomia z docs/PROFILE-SPEC.md), budżet SOUL,
frontmatter i opisy skilli (≤ 60 znaków, bo tyle widzi model w indeksie), plik blokady skilli,
definicje crona, evals, składnię skryptów i przypadkowe sekrety w repo.
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
EVAL_TYPES = {"in_scope", "out_of_scope", "safety", "routing", "protocol"}
MIN_EVALS = 10
SECRET_PATTERNS = [
    (re.compile(r"sk-or-v1-[0-9a-f]{20,}"), "klucz OpenRouter"),
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "klucz Anthropic"),
    (re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"), "token bota Telegram"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "klucz AWS"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "klucz prywatny"),
]
SKIP_DIRS = {".git", "build", "node_modules", "__pycache__", ".pytest_cache"}


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
    for d in fl.PROFILES_DIR.iterdir():
        if d.is_dir() and not d.name.startswith("_") and d.name not in names:
            r.err(f"profiles/{d.name}: brak wpisu w fleet.yaml")


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
    if a.name == fleet.orchestrator and fl.ROSTER_MARKER not in soul:
        r.err(f"{a.name}: SOUL.md orkiestratora bez {fl.ROSTER_MARKER}")
    # budżet z najdłuższą kalibracją, jaką agent może dostać (zmiana dostawcy albo modelu w panelu)
    orch = a.name == fleet.orchestrator
    calib = max((fl.calibration_section(f"{fam}-x", orch) for fam in CALIBRATION_FAMILIES), key=len)
    tokens = fl.approx_tokens(soul.replace(fl.PROTOCOL_MARKER, f"{protocol}\n\n{calib}"))
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
    if a.name == fleet.orchestrator and "kanban" not in (cfg.get("platform_toolsets") or {}).get("telegram", []):
        r.err(f"{a.name}: orkiestrator bez toolsetu kanban na Telegramie")
    if a.name == fleet.orchestrator and "terminal" in (cfg.get("platform_toolsets") or {}).get("telegram", []):
        r.err(f"{a.name}: orkiestrator nie powinien mieć terminala na Telegramie (nie wykonuje pracy)")
    appr = cfg.get("approvals") or {}
    for key in ("cron_mode", "single_query_mode", "unattended_mode"):
        if appr.get(key) != "deny":
            r.err(f"{a.name}: approvals.{key} musi być 'deny' (pracownicy bez człowieka nie zatwierdzają A2)")

    names: set[str] = set()
    for skill_md in fl.iter_skill_files(d / "skills"):
        rel = skill_md.parent.relative_to(d / "skills")
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
            if age > 180:
                r.warn(f"{a.name}/{rel}: reviewed {reviewed} (> 180 dni)")
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


CALIBRATION_FAMILIES = ("gpt", "claude", "deepseek", "kimi", "generic")
CALIBRATION_MAX_RULES = 3   # reguł na sekcję: każda nowa wypiera inną (shared/calibration/README.md)


def check_calibration(r: Report) -> None:
    """shared/calibration/<rodzina>.md: sekcje Wszyscy / Orkiestrator / Wykonawca, najwyżej 3 reguły w każdej."""
    import re as _re

    for fam in CALIBRATION_FAMILIES:
        path = fl.CALIBRATION_DIR / f"{fam}.md"
        if not path.exists():
            r.err(f"calibration: brak {path.relative_to(fl.REPO_ROOT)}")
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
            dests.add(dest)
            vname = dest.split("/")[-1]
            if vname in vnames or vname in own.get(agent, set()):
                r.err(f"lock/{agent}: kolizja nazwy skilla {vname!r}")
            vnames.add(vname)


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
    for a in fleet.active():
        path = fl.REPO_ROOT / "evals" / a.name / "scenarios.yaml"
        if not path.exists():
            r.err(f"{a.name}: brak evals/{a.name}/scenarios.yaml")
            continue
        data = fl.load_yaml(path) or {}
        scen = data.get("scenarios") or []
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
            if not str(s.get("input", "")).strip():
                r.err(f"{a.name}/evals/{sid}: brak input")
            if not (s.get("expect") or {}).get("should"):
                r.err(f"{a.name}/evals/{sid}: brak expect.should")
            n_out += s.get("type") == "out_of_scope"
        if a.name != fleet.orchestrator and n_out < 3:
            r.err(f"{a.name}: evals mają {n_out} scenariuszy out_of_scope (< 3)")


def check_scripts(r: Report) -> None:
    for path in sorted(fl.REPO_ROOT.rglob("*")):
        if any(p in SKIP_DIRS for p in path.parts) or not path.is_file():
            continue
        if path.suffix == ".py":
            # kompilacja w pamięci: repo w kontenerze jest tylko do odczytu (py_compile chce zapisać .pyc)
            try:
                compile(path.read_text(encoding="utf-8"), str(path), "exec", dont_inherit=True)
            except SyntaxError as exc:
                r.err(f"{path.relative_to(fl.REPO_ROOT)}: błąd składni Pythona: {exc.msg} (linia {exc.lineno})")
        elif path.suffix == ".sh":
            res = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
            if res.returncode:
                r.err(f"{path.relative_to(fl.REPO_ROOT)}: błąd składni bash: {res.stderr.strip()[:200]}")
        elif path.suffix in {".cjs", ".mjs", ".js"} and shutil.which("node"):
            res = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
            if res.returncode:
                r.err(f"{path.relative_to(fl.REPO_ROOT)}: błąd składni JS: {res.stderr.strip()[:200]}")


def check_secrets(r: Report) -> None:
    for path in sorted(fl.REPO_ROOT.rglob("*")):
        if any(p in SKIP_DIRS for p in path.parts) or not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        if path.name == ".env" or (path.suffix == ".env" and not path.name.endswith(".example")):
            r.err(f"{path.relative_to(fl.REPO_ROOT)}: plik .env nie może być w repo")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(text):
                r.err(f"{path.relative_to(fl.REPO_ROOT)}: wygląda na {label}")


def check_hq(r: Report) -> None:
    """Jarvo HQ (plugin dashboardu): pliki, manifest, zgodność pokoi z grafiką, licencja htm."""
    import json
    hq = fl.REPO_ROOT / "hq"
    if not hq.exists():
        return
    for rel in ("plugin/manifest.json", "plugin/plugin_api.py", "plugin/hq_core.py", "web/style.css",
                "web/vendor/htm.umd.js", "web/vendor/LICENSE-htm", "web/demo/index.html", "web/demo/mock.js"):
        if not (hq / rel).exists():
            r.err(f"hq: brak {rel}")
    try:
        manifest = json.loads((hq / "plugin" / "manifest.json").read_text(encoding="utf-8"))
        for key in ("name", "label", "entry", "tab"):
            if not manifest.get(key):
                r.err(f"hq/manifest.json: brak pola {key}")
    except (OSError, ValueError) as exc:
        r.err(f"hq/manifest.json: {exc}")
    src = sorted((hq / "web" / "src").glob("*.js"))
    if not src:
        r.err("hq/web/src: brak plików źródłowych")
    art = (hq / "web" / "src" / "20-art.js")
    if art.exists():
        block = art.read_text(encoding="utf-8").split("const ROOMS = {", 1)[-1].split("};", 1)[0]
        js_rooms = set(re.findall(r"^\s+(\w+):\s*\{", block, re.M))
        if js_rooms != fl.HQ_ROOMS:
            r.err(f"hq: pokoje w 20-art.js {sorted(js_rooms)} ≠ fleetlib.HQ_ROOMS {sorted(fl.HQ_ROOMS)}")


def run() -> Report:
    r = Report()
    fleet = fl.load_fleet()
    protocol = (fl.REPO_ROOT / fleet.raw["shared"]["protocol"]).read_text(encoding="utf-8")
    check_fleet(fleet, r)
    own: dict[str, set[str]] = {}
    lock = fl.load_lock()
    for a in fleet.active():
        own[a.name] = check_profile(fleet, a, protocol, r)
    check_lock(fleet, own, r)
    for a in fleet.active():
        vendored = {Path(e["dest"]).name for e in (lock.get("agents", {}).get(a.name) or [])}
        extra = {"roster"} if a.name == fleet.orchestrator else set()
        check_cron(a, own[a.name] | extra, vendored, r)
        check_related(a, own[a.name] | extra | vendored, r)
    check_evals(fleet, r)
    check_calibration(r)
    check_hq(r)
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
