"""Pliki .github/workflows/*.yml, które GitHub odrzuca w całości ("workflow file issue": przebieg czerwony bez
żadnego zadania, nawet gdy plik ma tylko workflow_dispatch). Najczęstsza przyczyna: kontekst wyrażenia użyty tam,
gdzie GitHub go nie udostępnia (migracja.yml miał ${{ runner.temp }} w env zadania)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
PLIKI = sorted((REPO / ".github" / "workflows").glob("*.yml"))

# dostępność kontekstów wg docs.github.com/actions/reference/workflows-and-actions/contexts#context-availability
KONTEKSTY = {
    "env": {"github", "secrets", "inputs", "vars"},
    "jobs.env": {"github", "needs", "strategy", "matrix", "vars", "secrets", "inputs"},
    "jobs.runs-on": {"github", "needs", "strategy", "matrix", "vars", "inputs"},
    "jobs.if": {"github", "needs", "vars", "inputs"},
}
WYRAZENIE = re.compile(r"\$\{\{(.*?)\}\}", re.S)
NAZWA = re.compile(r"(?<![\w.'\"-])([A-Za-z_][\w-]*)\s*(?=[.\[])")


def _konteksty(wartosc) -> set[str]:
    """Nazwy kontekstów (github, runner, ...) użyte w wyrażeniach ${{ }} wartości (także zagnieżdżonej)."""
    if isinstance(wartosc, dict):
        return set().union(*map(_konteksty, wartosc.values())) if wartosc else set()
    if isinstance(wartosc, list):
        return set().union(*map(_konteksty, wartosc)) if wartosc else set()
    teksty = WYRAZENIE.findall(str(wartosc)) if wartosc is not None else []
    # bez literałów w apostrofach: 'runner.temp' w napisie nie jest kontekstem
    return {m for t in teksty for m in NAZWA.findall(re.sub(r"'[^']*'", "''", t))}


def _wf(plik: Path) -> dict:
    return yaml.safe_load(plik.read_text(encoding="utf-8"))


@pytest.mark.parametrize("plik", PLIKI, ids=lambda p: p.name)
def test_konteksty_tylko_tam_gdzie_github_je_daje(plik):
    wf = _wf(plik)
    bledy = [f"env: {k}" for k in _konteksty(wf.get("env")) - KONTEKSTY["env"]]
    for nazwa, zadanie in (wf.get("jobs") or {}).items():
        for pole in ("env", "runs-on", "if"):
            if pole == "if" and isinstance(zadanie.get("if"), str) and "${{" not in zadanie["if"]:
                uzyte = _konteksty("${{ " + zadanie["if"] + " }}")
            else:
                uzyte = _konteksty(zadanie.get(pole))
            bledy += [f"jobs.{nazwa}.{pole}: {k}" for k in uzyte - KONTEKSTY[f"jobs.{pole}"]]
    assert not bledy, f"{plik.name}: konteksty niedostępne w tym miejscu (GitHub odrzuci plik): {bledy}"


@pytest.mark.parametrize("plik", PLIKI, ids=lambda p: p.name)
def test_kazde_zadanie_ma_kroki_i_maszyne(plik):
    wf = _wf(plik)
    assert wf.get("name"), plik.name
    # PyYAML czyta klucz `on` jako True
    assert wf.get(True) or wf.get("on"), plik.name
    for nazwa, zadanie in (wf.get("jobs") or {}).items():
        assert zadanie.get("runs-on") or zadanie.get("uses"), f"{plik.name}: {nazwa} bez runs-on"
        for krok in zadanie.get("steps") or []:
            assert ("run" in krok) != ("uses" in krok), f"{plik.name}: {nazwa}: krok {krok.get('name')} run xor uses"


def test_wykrywa_runner_w_env_zadania():
    assert _konteksty({"A": "${{ runner.temp }}/x", "B": "${{ github.token }}"}) == {"runner", "github"}
    assert _konteksty("${{ format('{0}', 'runner.temp') }}") == set()
    assert _konteksty("${{ matrix.os == 'windows-2025' && 'a' || 'b' }}") == {"matrix"}
