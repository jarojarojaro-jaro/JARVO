#!/usr/bin/env python3
"""Buduje gotowe dystrybucje profili Hermesa z tego repo.

    python scripts/build.py --hermes-src /opt/hermes [--env-file /srv/tars/compose/tars.env]

Wynik: build/
  profiles/<agent>/   dystrybucja gotowa do `hermes profile install` / `update`
  host/config.yaml    config profilu hosta (default): gateway, trasy Telegrama, kanban
  BUILD.json          manifest (commit repo, źródła skilli, agenci)

Kroki dla każdego aktywnego agenta z fleet.yaml:
  1. kopia profiles/<agent>/ (bez plików roboczych),
  2. SOUL.md: wstawienie wspólnego protokołu (i skrótu floty dla TARS-a),
  3. profile.yaml z opisem z fleet.yaml (routing kanbana, roster),
  4. config.yaml: podstawienie tokenów @@...@@ (modele, katalogi, strefa czasowa),
  5. skille zewnętrzne z vendor/skills.lock.yaml (+ licencje, + DESCRIPTION.md kategorii),
  6. dla TARS-a: skill `roster` i rubryki sędziego generowane z fleet.yaml i quality/rubric.md,
  7. cron/jobs.yaml → cron/jobs.json (przez API crona Hermesa, stałe ID zadań).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleetlib as fl  # noqa: E402

COPY_IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", ".DS_Store", "node_modules", ".env", "*.env", "jobs.yaml"
)

CATEGORY_DESCRIPTIONS = {
    # kategorie własne
    "fleet": "Dowodzenie flotą TARS: przyjmowanie zleceń, misje, karty, ocena, decyzje, patrol, raporty.",
    "sherlock": "Metoda śledcza: wieloźródłowy research, weryfikacja faktów, raporty z cytatami.",
    "web": "Workflowy Web Senior Deva: brand z URL, audyty, nowe strony, landingi, favicony, obrazy, wdrożenia.",
    "studio": "Workflowy Studio: pakiety kampanii, grafiki social, filmy z kodu, generacja AI, formaty, copy PL, publikacja.",
    "reka": "Workflowy prawej ręki: składanie pakietów misji, dokumenty i konwersje, szybkie prototypy, granice.",
    # kategorie skilli zewnętrznych
    "research": "Narzędzia researchu z Hermesa (MIT): wyszukiwarki, cytowanie, arXiv, YouTube, Reddit, RSS, OSINT firm.",
    "market": "Research rynku (marketingskills, MIT): profile konkurencji, research klientów.",
    "web-quality": "Jakość stron (web-quality-skills, MIT): audyt, Core Web Vitals, wydajność, dostępność, dobre praktyki.",
    "seo": "SEO techniczne i on-page (claude-seo, MIT): audyt, schema, obrazy, sitemap, hreflang, GEO, local, programmatic.",
    "marketing": "Marketing (marketingskills, MIT): copy, social, content, launch, reklamy, psychologia, e-maile, CRO.",
    "design": "Design (Anthropic skills Apache-2.0 + Hermes MIT): frontend, systemy designu, grafika, motywy, testy UI.",
    "deploy": "Publikacja stron (Hermes, MIT): wersjonowane wdrożenia i tymczasowe podglądy. Produkcja tylko za zgodą.",
    "video": "Wideo z HTML (HyperFrames, Apache-2.0): kompozycje, animacje, launch video, explainery, napisy, slideshow.",
    "creative": "Kreacja (Hermes, MIT): Manim, infografiki, humanizer, kalendarz social, ideacja, memy, diagramy.",
    "meta": "Meta-skille: tworzenie i ulepszanie skilli (Anthropic skill-creator, Apache-2.0).",
}


# ----------------------------------------------------------------------------- env

def read_env_file(path: Path | None) -> dict[str, str]:
    env: dict[str, str] = {}
    if path and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    # zmienne środowiska procesu mają pierwszeństwo
    for key, value in os.environ.items():
        if key.startswith(("TARS_", "TELEGRAM_")):
            env[key] = value
    return env


# -------------------------------------------------------------------------- tokens

def render_tokens(text: str, tokens: dict[str, str]) -> str:
    for key, value in tokens.items():
        text = text.replace(f"@@{key}@@", value)
    return text


def base_tokens(fleet: fl.Fleet, agent: fl.Agent, runtime_build_dir: str, env: dict[str, str]) -> dict[str, str]:
    shared = fleet.raw.get("shared", {})
    owner = env.get("TELEGRAM_OWNER_ID", "").strip()
    return {
        "PROVIDER": fleet.provider,
        "MODEL": fleet.model_for(agent.model_tier),
        "DELEGATION_MODEL": fleet.model_for(agent.delegation_tier),
        "MODEL_FRONTIER": fleet.model_for("frontier"),
        "MODEL_STRONG": fleet.model_for("strong"),
        "MODEL_FAST": fleet.model_for("fast"),
        "TIMEZONE": shared.get("timezone", "Europe/Warsaw"),
        "MISSIONS_DIR": shared.get("missions_dir", "/opt/data/tars/missions"),
        "WORKSPACES_DIR": shared.get("workspaces_dir", "/opt/data/tars/workspaces"),
        "KNOWLEDGE_DIR": "/opt/data/tars/knowledge",
        "BUILD_DIR": runtime_build_dir,
        "AGENT": agent.name,
        "REVIEWER": fleet.reviewer,
        "ORCHESTRATOR": fleet.orchestrator,
        # cel dostarczania rutyn: DM właściciela (trasa DM → tars), albo lokalnie gdy brak
        "OWNER_DELIVER": f"telegram:{owner}" if owner else "local",
    }


# ------------------------------------------------------------------------ vendoring

class SourceResolver:
    """Zwraca katalog z drzewem źródła skilli (hermes-tree albo repo git na commicie)."""

    def __init__(self, lock: dict, hermes_src: Path | None, cache: Path, local_src: dict[str, Path]):
        self.sources = lock.get("sources", {})
        self.hermes_src = hermes_src
        self.cache = cache
        self.local_src = local_src
        self._resolved: dict[str, Path] = {}

    def resolve(self, name: str) -> Path:
        if name in self._resolved:
            return self._resolved[name]
        spec = self.sources[name]
        if spec["type"] == "hermes-tree":
            if not self.hermes_src:
                raise SystemExit("Źródło 'hermes' wymaga --hermes-src (np. /opt/hermes w kontenerze).")
            path = self.hermes_src
        elif name in self.local_src:
            path = self.local_src[name]
            head = _git(["rev-parse", "HEAD"], cwd=path).strip()
            if head != spec["rev"]:
                raise SystemExit(f"Lokalne źródło {name} jest na {head}, lock wymaga {spec['rev']}.")
        else:
            path = self.cache / f"{name}@{spec['rev'][:12]}"
            if not (path / ".git").exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                _git(["init", "-q", str(path)])
                _git(["remote", "add", "origin", spec["repo"]], cwd=path)
                _git(["fetch", "-q", "--depth", "1", "origin", spec["rev"]], cwd=path)
                _git(["checkout", "-q", "FETCH_HEAD"], cwd=path)
        self._resolved[name] = path
        return path


def _git(args: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def vendor_skills(agent: str, out_skills: Path, lock: dict, resolver: SourceResolver, report: list) -> None:
    for entry in lock.get("agents", {}).get(agent, []) or []:
        source = entry["source"]
        spec = lock["sources"][source]
        src_root = resolver.resolve(source)
        src = src_root / entry["path"]
        if not (src / "SKILL.md").exists():
            raise SystemExit(f"[{agent}] brak SKILL.md w {source}:{entry['path']}")
        dest = out_skills / entry["dest"]
        if dest.exists():
            raise SystemExit(f"[{agent}] kolizja: {entry['dest']} już istnieje (skill własny o tej nazwie?)")
        shutil.copytree(src, dest, ignore=COPY_IGNORE)
        # licencja
        if spec.get("license_file") == "per-skill":
            lic = next((p for p in dest.iterdir() if p.name.lower().startswith("license")), None)
            if lic is None or "Apache License" not in lic.read_text(encoding="utf-8", errors="ignore"):
                raise SystemExit(f"[{agent}] {entry['path']}: brak licencji Apache-2.0, nie kopiujemy")
        elif spec.get("license_file"):
            shutil.copy2(src_root / spec["license_file"], dest / "LICENSE-UPSTREAM")
        elif spec["type"] == "hermes-tree":
            hermes_license = src_root / "LICENSE"
            if hermes_license.exists():
                shutil.copy2(hermes_license, dest / "LICENSE-UPSTREAM")
        # Apache-2.0 §4d: plik NOTICE źródła (jeśli jest) jedzie razem ze skillem
        for notice in (src_root / "NOTICE", src_root / "NOTICE.md", src_root / "NOTICE.txt"):
            if notice.is_file():
                shutil.copy2(notice, dest / "NOTICE-UPSTREAM")
                break
        rev = spec.get("rev") or _hermes_rev(src_root)
        fl.write_json(dest / ".vendored.json", {
            "source": source, "repo": spec.get("repo", "hermes-agent (image tree)"),
            "rev": rev, "path": entry["path"], "license": spec["license"],
        })
        report.append({"agent": agent, "dest": entry["dest"], "source": source, "rev": rev})


def _hermes_rev(root: Path) -> str:
    stamp = root / "install-stamp.json"
    if stamp.exists():
        try:
            return json.loads(stamp.read_text())["commit"]
        except Exception:
            pass
    try:
        return _git(["rev-parse", "HEAD"], cwd=root).strip()
    except Exception:
        return "unknown"


def write_category_descriptions(skills_root: Path) -> None:
    for cat_dir in sorted(p for p in skills_root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        desc_file = cat_dir / "DESCRIPTION.md"
        if desc_file.exists():
            continue
        desc = CATEGORY_DESCRIPTIONS.get(cat_dir.name)
        if desc:
            desc_file.write_text(f"---\ndescription: {json.dumps(desc, ensure_ascii=False)}\n---\n", encoding="utf-8")


# ---------------------------------------------------------------- generated (TARS)

def render_roster_skill(fleet: fl.Fleet) -> str:
    lines = [
        "---",
        "name: roster",
        'description: "Kto jest we flocie: agenci, zakresy, skille do kart."',
        "version: 1.0.0",
        "author: TARS (generowane z fleet.yaml)",
        "license: MIT",
        "metadata:",
        "  tars:",
        f"    agent: {fleet.orchestrator}",
        "    generated: true",
        "---",
        "",
        "# Roster floty (generowane, nie edytuj ręcznie)",
        "",
        "Źródło: `fleet.yaml`. Karty przypisuj **wyłącznie** do agentów z tej listy. Dispatcher",
        "nie wykona karty przypisanej do nieistniejącego profilu.",
        "",
        "| Agent | Rola | Zakres | Model | Maks. autonomia |",
        "|---|---|---|---|---|",
    ]
    for a in fleet.active():
        lines.append(f"| `{a.name}` | {a.emoji} {a.title} | {a.description} | {a.model_tier} | {a.autonomy_max} |")
    lines += [
        "",
        f"Recenzent kart: `{fleet.reviewer}` (snajperzy wołają `kanban_request_review(reviewer=\"{fleet.reviewer}\")`).",
        "",
        "## Skille, które warto przypinać do kart (`kanban_create(skills=[...])`)",
        "",
        "Nazwy muszą istnieć w profilu wykonawcy. Poniższe listy są generowane z repo.",
        "",
    ]
    lock = fl.load_lock()
    for a in fleet.active():
        if a.name == fleet.orchestrator:
            continue
        own = sorted(fl.skill_names(a.dir / "skills").keys())
        vendored = sorted(Path(e["dest"]).name for e in lock.get("agents", {}).get(a.name, []) or [])
        lines.append(f"### `{a.name}`")
        lines.append(f"- workflowy własne: {', '.join(f'`{n}`' for n in own) or '—'}")
        if vendored:
            lines.append(f"- skille zewnętrzne: {', '.join(f'`{n}`' for n in vendored)}")
        if a.pin_skills:
            lines.append(f"- przypinaj domyślnie: {', '.join(f'`{n}`' for n in a.pin_skills)}")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_roster_summary(fleet: fl.Fleet) -> str:
    rows = ["| Agent | Rola |", "|---|---|"]
    for a in fleet.active():
        if a.name == fleet.orchestrator:
            continue
        rows.append(f"| `{a.name}` | {a.emoji} {a.title} |")
    return "\n".join(rows)


def copy_rubrics(fleet: fl.Fleet, review_skill_refs: Path) -> None:
    review_skill_refs.mkdir(parents=True, exist_ok=True)
    for a in fleet.active():
        rubric = a.dir / "quality" / "rubric.md"
        if rubric.exists():
            shutil.copy2(rubric, review_skill_refs / f"rubric-{a.name}.md")


# ---------------------------------------------------------------------------- cron

def build_cron(agent_dir: Path, out_dir: Path, tokens: dict[str, str], hermes_src: Path | None) -> int:
    src = agent_dir / "cron" / "jobs.yaml"
    if not src.exists():
        return 0
    spec = fl.loads_yaml(render_tokens(src.read_text(encoding="utf-8"), tokens)) or {}
    jobs = spec.get("jobs", []) or []
    if not jobs:
        return 0
    if hermes_src is None:
        raise SystemExit("Budowa crona wymaga --hermes-src (API crona Hermesa waliduje harmonogramy).")
    code = _CRON_SNIPPET
    payload = json.dumps(jobs, ensure_ascii=False)
    with tempfile.TemporaryDirectory(prefix="tars_cron_") as tmp:
        env = dict(os.environ, HERMES_HOME=tmp, TARS_CRON_JOBS=payload, TARS_CRON_OUT=str(out_dir / "cron" / "jobs.json"))
        env["PYTHONPATH"] = os.pathsep.join([str(hermes_src), env.get("PYTHONPATH", "")])
        python = os.environ.get("TARS_HERMES_PYTHON") or sys.executable
        res = subprocess.run([python, "-c", code], env=env, capture_output=True, text=True)
        if res.returncode != 0:
            raise SystemExit(f"Budowa crona dla {agent_dir.name} nie powiodła się:\n{res.stdout}\n{res.stderr}")
    return len(jobs)


_CRON_SNIPPET = r"""
import json, os, shutil
from pathlib import Path
from cron import jobs as cj

specs = json.loads(os.environ["TARS_CRON_JOBS"])
home = Path(os.environ["HERMES_HOME"])
with cj.use_cron_store(home):
    for s in specs:
        job = cj.create_job(
            prompt=s.get("prompt"), schedule=s["schedule"], name=s.get("name"),
            deliver=s.get("deliver"), skills=s.get("skills"), script=s.get("script"),
            enabled_toolsets=s.get("enabled_toolsets"), no_agent=bool(s.get("no_agent", False)),
            reasoning_effort=s.get("reasoning_effort"), paused=bool(s.get("paused", False)),
            paused_reason=s.get("paused_reason"), model=s.get("model"), provider=s.get("provider"),
        )
        stable = s["id"]
        records = cj.load_jobs()
        for rec in records:
            if rec.get("id") == job["id"]:
                rec["id"] = stable
        cj.save_jobs(records, replace=True)
store = home / "cron" / "jobs.json"
out = Path(os.environ["TARS_CRON_OUT"])
out.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(store, out)
"""


# ---------------------------------------------------------------------------- host

def build_host(fleet: fl.Fleet, out: Path, env: dict[str, str]) -> list[str]:
    """Config profilu hosta: gateway + multipleks + trasy Telegrama + dispatcher."""
    notes: list[str] = []
    template = fl.REPO_ROOT / "profiles" / "_host" / "config.yaml"
    config = fl.load_yaml(template)
    routes = []
    owner = env.get("TELEGRAM_OWNER_ID", "").strip()
    hq = env.get("TELEGRAM_HQ_CHAT_ID", "").strip()
    if owner:
        routes.append({"name": "owner-dm", "platform": "telegram", "chat_id": owner, "profile": fleet.orchestrator})
    else:
        notes.append("Brak TELEGRAM_OWNER_ID: DM z botem nie zostanie skierowany do TARS-a.")
    if hq:
        for a in fleet.active():
            topic = a.telegram_topic
            if not topic:
                continue
            if topic == "general":
                routes.append({"name": f"hq-{a.name}", "platform": "telegram", "chat_id": hq, "profile": a.name})
                continue
            thread = env.get(f"TELEGRAM_TOPIC_{topic.upper()}", "").strip()
            if thread:
                routes.append({"name": f"hq-{a.name}", "platform": "telegram", "chat_id": hq,
                               "thread_id": thread, "profile": a.name})
            else:
                notes.append(f"Brak TELEGRAM_TOPIC_{topic.upper()}: wątek {a.name} w TARS HQ nie ma trasy.")
    else:
        notes.append("Brak TELEGRAM_HQ_CHAT_ID: grupa „TARS HQ” nie ma tras (działa tylko DM).")
    config.setdefault("gateway", {})["profile_routes"] = routes
    config["timezone"] = fleet.raw.get("shared", {}).get("timezone", "Europe/Warsaw")
    # host (gateway, zadania pomocnicze kanbana) używa dostawcy floty i jej najszybszego modelu
    config["model"] = {"provider": fleet.provider, "default": fleet.model_for("fast")}
    out.mkdir(parents=True, exist_ok=True)
    header = "# Wygenerowane przez scripts/build.py z profiles/_host/config.yaml + fleet.yaml. Nie edytuj na serwerze.\n"
    (out / "config.yaml").write_text(header + fl.dump_yaml(config), encoding="utf-8")
    shutil.copy2(fl.REPO_ROOT / "profiles" / "_host" / "SOUL.md", out / "SOUL.md")
    return notes


# ---------------------------------------------------------------------------- main

def build_agent(fleet, agent, out_root, lock, resolver, protocol, runtime_build_dir, env, hermes_src, report):
    src = agent.dir
    dest = out_root / agent.name
    shutil.copytree(src, dest, ignore=COPY_IGNORE)
    tokens = base_tokens(fleet, agent, runtime_build_dir, env)

    # SOUL.md
    soul_path = dest / "SOUL.md"
    soul = soul_path.read_text(encoding="utf-8")
    if fl.PROTOCOL_MARKER not in soul:
        raise SystemExit(f"[{agent.name}] SOUL.md nie ma znacznika {fl.PROTOCOL_MARKER}")
    soul = soul.replace(fl.PROTOCOL_MARKER, protocol.strip())
    if agent.name == fleet.orchestrator:
        soul = soul.replace(fl.ROSTER_MARKER, render_roster_summary(fleet))
    soul_path.write_text(render_tokens(soul, tokens), encoding="utf-8")

    # profile.yaml
    (dest / "profile.yaml").write_text(fl.dump_yaml({
        "description": agent.description,
        "description_auto": False,
        "display_name": f"{agent.emoji} {agent.title}".strip(),
    }), encoding="utf-8")

    # config.yaml i skrypty: tokeny
    for rel in ["config.yaml", "distribution.yaml"]:
        p = dest / rel
        if p.exists():
            p.write_text(render_tokens(p.read_text(encoding="utf-8"), tokens), encoding="utf-8")
    # model zapasowy zestawu: agent nie milknie, gdy główny model odmówi (np. poza planem)
    if fleet.fallback and (dest / "config.yaml").exists():
        fb = fleet.fallback
        with (dest / "config.yaml").open("a", encoding="utf-8") as f:
            f.write(f'\nfallback_providers:\n  - provider: "{fb["provider"]}"\n    model: "{fb["model"]}"\n')

    # skille własne → tokeny w SKILL.md i references
    for md in (dest / "skills").rglob("*.md"):
        md.write_text(render_tokens(md.read_text(encoding="utf-8"), tokens), encoding="utf-8")

    # TARS: roster + rubryki
    if agent.name == fleet.orchestrator:
        roster = dest / "skills" / "fleet" / "roster" / "SKILL.md"
        roster.parent.mkdir(parents=True, exist_ok=True)
        roster.write_text(render_roster_skill(fleet), encoding="utf-8")
        copy_rubrics(fleet, dest / "skills" / "fleet" / "sdlc-review" / "references")

    # skille zewnętrzne
    vendor_skills(agent.name, dest / "skills", lock, resolver, report)
    if (dest / "skills").exists():
        write_category_descriptions(dest / "skills")

    # cron
    n_jobs = build_cron(src, dest, tokens, hermes_src)

    # sprzątanie plików źródłowych, których nie chcemy w dystrybucji
    for leftover in ["cron/jobs.yaml"]:
        p = dest / leftover
        if p.exists():
            p.unlink()
    return n_jobs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(fl.REPO_ROOT / "build"))
    ap.add_argument("--hermes-src", default=os.environ.get("TARS_HERMES_SRC"),
                    help="drzewo Hermesa (skille 'hermes' + API crona), w kontenerze: /opt/hermes")
    ap.add_argument("--cache", default=None, help="cache klonów źródeł skilli (domyślnie <out>/.cache)")
    ap.add_argument("--local-src", action="append", default=[],
                    help="nazwa=ścieżka: użyj lokalnego klonu źródła (musi być na commicie z locka)")
    ap.add_argument("--env-file", default=None, help="plik z TELEGRAM_OWNER_ID, TELEGRAM_HQ_CHAT_ID, TELEGRAM_TOPIC_*")
    ap.add_argument("--runtime-build-dir", default="/opt/tars/build",
                    help="ścieżka, pod którą build będzie widoczny w kontenerze (external_dirs prawej ręki)")
    ap.add_argument("--agent", action="append", default=[], help="buduj tylko wskazanych agentów")
    args = ap.parse_args(argv)

    fleet = fl.load_fleet()
    lock = fl.load_lock()
    out = Path(args.out).resolve()
    cache = Path(args.cache).resolve() if args.cache else out / ".cache"
    hermes_src = Path(args.hermes_src).resolve() if args.hermes_src else None
    local_src = {}
    for item in args.local_src:
        name, _, path = item.partition("=")
        local_src[name] = Path(path).resolve()
    env = read_env_file(Path(args.env_file) if args.env_file else None)
    fleet.apply_model_overrides(env)
    print(f"Modele: {fleet.provider} · " + ", ".join(f"{t}={m}" for t, m in fleet.tiers.items()))
    protocol = (fl.REPO_ROOT / fleet.raw["shared"]["protocol"]).read_text(encoding="utf-8")

    profiles_out = out / "profiles"
    if profiles_out.exists():
        shutil.rmtree(profiles_out)
    profiles_out.mkdir(parents=True)
    resolver = SourceResolver(lock, hermes_src, cache, local_src)

    report: list[dict] = []
    summary = []
    for agent in fleet.active():
        if args.agent and agent.name not in args.agent:
            continue
        n_jobs = build_agent(fleet, agent, profiles_out, lock, resolver, protocol,
                             args.runtime_build_dir, env, hermes_src, report)
        n_skills = len(list(fl.iter_skill_files(profiles_out / agent.name / "skills")))
        summary.append({"agent": agent.name, "skills": n_skills, "cron_jobs": n_jobs})
        print(f"✓ {agent.name}: {n_skills} skilli, {n_jobs} rutyn cron")

    import hqbuild  # TARS HQ: plugin dashboardu (pokoje agentów, czat, decyzje)
    hq_dir = hqbuild.build_plugin(out / "plugins" / "tars-hq", fleet)
    print(f"✓ TARS HQ: {hq_dir.relative_to(out)}")

    notes = build_host(fleet, out / "host", env)
    for note in notes:
        print(f"! {note}")

    try:
        repo_rev = _git(["rev-parse", "HEAD"], cwd=fl.REPO_ROOT).strip()
    except Exception:
        repo_rev = "unknown"
    fl.write_json(out / "BUILD.json", {
        "built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "repo_rev": repo_rev,
        "agents": summary,
        "plugins": ["tars-hq"],
        "vendored": report,
        "notes": notes,
    })
    print(f"Build gotowy: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
