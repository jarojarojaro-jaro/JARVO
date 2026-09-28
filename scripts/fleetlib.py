"""Wspólne funkcje narzędzi floty Jarvo (build, validate, deploy, evals).

Tylko biblioteka standardowa + YAML. Działa z PyYAML albo z ruamel.yaml (który jest
w środowisku Hermesa), więc skrypty można uruchamiać zarówno lokalnie, jak i w kontenerze.
"""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
PROFILES_DIR = REPO_ROOT / "profiles"
SHARED_DIR = REPO_ROOT / "shared"
VENDOR_LOCK = REPO_ROOT / "vendor" / "skills.lock.yaml"
FLEET_FILE = REPO_ROOT / "fleet.yaml"

CALIBRATION_DIR = SHARED_DIR / "calibration"
# prefiks identyfikatora modelu (bez dostawcy) → plik kalibracji w shared/calibration/
MODEL_FAMILIES = (("gpt-", "gpt"), ("chatgpt", "gpt"), ("o3", "gpt"), ("o4", "gpt"), ("claude", "claude"),
                  ("deepseek", "deepseek"), ("kimi", "kimi"))
PROTOCOL_MARKER = "<!-- Jarvo:PROTOCOL -->"
ROSTER_MARKER = "<!-- Jarvo:ROSTER -->"
AGENT_KINDS = {"orchestrator", "specialist", "generalist"}
AUTONOMY_LEVELS = {"A0", "A1", "A2", "A3"}
HQ_ROOMS = {"bridge", "study", "devlab", "atelier", "filmstudio", "workshop", "office"}   # pokoje w Jarvo HQ (hq/web/src/20-art.js)
# Hermes ucina opis skilla w indeksie promptu do 60 znaków (agent/skill_utils.py).
SKILL_PROMPT_DESC_LIMIT = 60
# Budżet main promptu (SOUL.md) w przybliżonych tokenach (~3.5 znaku/token dla PL/EN).
SOUL_TOKEN_BUDGET = 3200


# --------------------------------------------------------------------------- YAML

def _yaml_backend():
    try:
        import yaml  # type: ignore

        return "pyyaml", yaml
    except ImportError:  # pragma: no cover - zależy od środowiska
        from ruamel.yaml import YAML  # type: ignore

        return "ruamel", YAML(typ="safe", pure=True)


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
    en: dict = field(default_factory=dict)   # angielskie title / hq_label / description (HQ po angielsku)

    @property
    def dir(self) -> Path:
        return PROFILES_DIR / self.name


@dataclass
class Fleet:
    raw: dict
    agents: list[Agent]

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
        JARVO_MODEL_FRONTIER / _STRONG / _FAST (np. z compose/jarvo.env)."""
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

    def agent(self, name: str) -> Agent:
        for a in self.agents:
            if a.name == name:
                return a
        raise KeyError(name)

    def active(self) -> list[Agent]:
        return [a for a in self.agents if a.status == "active"]

    def model_for(self, tier: str) -> str:
        return self.tiers[tier]


def load_fleet(path: Path | None = None) -> Fleet:
    raw = load_yaml(path or FLEET_FILE)
    agents = []
    for entry in raw.get("agents", []):
        agents.append(
            Agent(
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
                en={k: " ".join(str(v).split()) for k, v in (entry.get("en") or {}).items() if v},
            )
        )
    return Fleet(raw=raw, agents=agents)


def load_lock(path: Path | None = None) -> dict:
    return load_yaml(path or VENDOR_LOCK)


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


def skill_names(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for path in iter_skill_files(root):
        fm, _ = read_skill(path)
        name = str(fm.get("name") or path.parent.name)
        out[name] = path
    return out


def approx_tokens(text: str) -> int:
    return int(len(text) / 3.5) + 1


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
