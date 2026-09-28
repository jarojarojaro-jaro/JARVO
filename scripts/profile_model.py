#!/usr/bin/env python3
"""Model agenta wybrany w dashboardzie przetrwa aktualizację floty.

    python profile_model.py snapshot <katalog profilu>   # przed `hermes profile update --force-config`
    python profile_model.py restore  <katalog profilu>   # po nim

`hermes profile update --force-config` nadpisuje config.yaml profilu tym z buildu floty. Blok `model`
wracamy do wersji sprzed aktualizacji, jeśli ktoś go zmienił (strona Models / `/model` przy wybranym
agencie), czyli gdy różni się od tego, co flota ustawiła poprzednio (.jarvo-fleet-model.json). Model
nietknięty przez człowieka idzie za flotą (np. po zmianie JARVO_MODEL_PROVIDER).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from ruamel.yaml import YAML

    _y = YAML()
    _y.preserve_quotes = True

    def load(p: Path):
        return _y.load(p.read_text(encoding="utf-8")) if p.exists() else None

    def dump(data, p: Path):
        with p.open("w", encoding="utf-8") as f:
            _y.dump(data, f)
except ImportError:  # pragma: no cover
    import yaml  # type: ignore

    def load(p: Path):
        return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None

    def dump(data, p: Path):
        p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

SNAP, MARK = ".jarvo-model-before.json", ".jarvo-fleet-model.json"


def model_of(cfg) -> dict | None:
    m = (cfg or {}).get("model")
    return {k: m[k] for k in ("provider", "default") if k in m} if isinstance(m, dict) else None


def recalibrate(prof: Path, model_id: str | None) -> None:
    """SOUL profilu dostaje kalibrację pod model wybrany w panelu (shared/calibration/, jak w buildzie)."""
    soul_path = prof / "SOUL.md"
    if not model_id or not soul_path.exists():
        return
    try:  # kalibracja to dodatek: jej błąd nie może zatrzymać instalacji profilu
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import fleetlib  # noqa: E402  (tylko tutaj: snapshot nie potrzebuje)

        new = fleetlib.recalibrate_soul(soul_path.read_text(encoding="utf-8"), model_id)
        if new is not None:
            soul_path.write_text(new, encoding="utf-8")
            print(f"  kalibracja SOUL pod {model_id}: {fleetlib.model_family(model_id)}")
    except Exception as exc:  # noqa: BLE001
        print(f"  ! kalibracja SOUL pominięta: {exc}")


def main(argv: list[str]) -> int:
    action, prof = argv[0], Path(argv[1])
    cfg_path = prof / "config.yaml"
    if action == "snapshot":
        before = model_of(load(cfg_path))
        (prof / SNAP).write_text(json.dumps(before), encoding="utf-8")
        return 0
    cfg = load(cfg_path)
    fleet_model = model_of(cfg)
    try:
        before = json.loads((prof / SNAP).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        before = None
    try:
        last_fleet = json.loads((prof / MARK).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        last_fleet = None
    chosen = before and last_fleet is not None and before != last_fleet
    if chosen and cfg is not None and before != fleet_model:
        for k, v in before.items():
            cfg["model"][k] = v
        dump(cfg, cfg_path)
        print(f"  model wybrany w panelu zostaje: {before.get('provider')} / {before.get('default')}")
        recalibrate(prof, before.get("default"))
    if fleet_model is not None:
        (prof / MARK).write_text(json.dumps(fleet_model), encoding="utf-8")
    (prof / SNAP).unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
