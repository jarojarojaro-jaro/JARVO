"""Rutyna „Nowe wersje” (profiles/jarvo/scripts/nowe_wersje.py): co zgłasza, jak raz i dokąd, bez sieci."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
from pathlib import Path

import yaml

SKRYPT = Path(__file__).resolve().parents[1] / "profiles/jarvo/scripts/nowe_wersje.py"
spec = importlib.util.spec_from_file_location("nowe_wersje", SKRYPT)
nw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nw)


def _repo(tmp: Path) -> Path:
    (tmp / "vendor").mkdir(parents=True)
    (tmp / "infra/node").mkdir(parents=True)
    (tmp / "vendor/natywne.yaml").write_text(yaml.safe_dump({
        "hermes": {"repo": "https://github.com/NousResearch/hermes-agent", "tag": "v2026.9.24"},
        "narzedzia": {
            "agent-browser": {"wersja": "0.43.0", "pliki": {"linux-x64": {"url": "https://github.com/vercel-labs/agent-browser/releases/download/v0.43.0/agent-browser-linux-x64"}}},
            "cua-driver": {"wersja": "0.38.0", "pliki": {"linux-x64": {"url": "https://github.com/trycua/cua/releases/download/cua-driver-rs-v0.38.0/x"}}},
            "ffmpeg": {"wersja": "9.0.2", "pliki": {"linux-x64": {"url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-09-30-13-08/f"}}},
            "chrome-komputer": {"wersja": "156.0.8078.47", "pliki": {"linux-x64": {"url": "https://storage.googleapis.com/chrome-for-testing-public/156.0.8078.47/linux64/c.zip"}}},
        }}), encoding="utf-8")
    (tmp / "infra/node/package.json").write_text(json.dumps({"dependencies": {"sharp": "0.35.4"}}), encoding="utf-8")
    return tmp


def _siec(wydania: dict):
    def pobierz(url: str):
        if "api.github.com/repos/" in url:
            return [{"tag_name": t, "html_url": f"https://x/{t}", "prerelease": False} for t in wydania[url.split("/repos/")[1].split("/releases")[0]]]
        if "chrome-for-testing" in url:
            return {"channels": {"Stable": {"version": wydania["chrome"]}}}
        if "registry.npmjs.org" in url:
            return {"version": wydania["sharp"]}
        raise AssertionError(url)
    return pobierz


def test_jedno_zlecenie_z_nowymi_wersjami_i_bez_powtorek(tmp_path):
    repo = _repo(tmp_path / "r")
    stan, zlecenia = tmp_path / "stan.json", tmp_path / "DLA-CLAUDE.md"
    zlecenia.write_text("# Zlecenia dla Claude Code\n\n- [x] 2026-11-14 · stare · po co · plik\n", encoding="utf-8")
    siec = _siec({
        "NousResearch/hermes-agent": ["v2026.9.24"],
        "vercel-labs/agent-browser": ["v0.44.0", "v0.43.0"],
        # inny produkt z tego samego repo nie liczy się jako nowa wersja cua-driver
        "trycua/cua": ["cua-agent-v9.0.0", "cua-driver-rs-v0.38.0"],
        # dzienne buildy BtbN z tego samego miesiąca co pin to nie nowa wersja
        "BtbN/FFmpeg-Builds": ["autobuild-2026-09-30-20-00"],
        "chrome": "157.0.8103.78", "sharp": "0.35.4"})
    nowe = nw.sprawdz(repo, stan, zlecenia, pobierz=siec, dzis=dt.date(2026, 11, 15))
    assert [n.split(" (")[0] for n in nowe] == ["agent-browser 0.43.0 → v0.44.0", "chrome-komputer 156.0.8078.47 → 157.0.8103.78"]
    otwarte = [l for l in zlecenia.read_text(encoding="utf-8").splitlines() if l.startswith("- [ ] ")]
    assert len(otwarte) == 1 and otwarte[0].startswith("- [ ] 2026-11-15 · nowe wersje (2): agent-browser 0.43.0 → v0.44.0")
    # drugi przebieg z tą samą siecią: nic nowego, zlecenie się nie dubluje
    assert nw.sprawdz(repo, stan, zlecenia, pobierz=siec, dzis=dt.date(2026, 11, 16)) == []
    assert len([l for l in zlecenia.read_text(encoding="utf-8").splitlines() if l.startswith("- [ ] ")]) == 1


def test_blad_jednego_zrodla_nie_zatrzymuje_reszty(tmp_path):
    repo = _repo(tmp_path / "r")
    stan, zlecenia = tmp_path / "stan.json", tmp_path / "DLA-CLAUDE.md"
    ok = _siec({"NousResearch/hermes-agent": ["v2026.9.24"], "vercel-labs/agent-browser": ["v0.43.0"], "trycua/cua": [],
                "BtbN/FFmpeg-Builds": [], "chrome": "156.0.8078.47", "sharp": "0.36.0"})

    def pobierz(url):
        if "agent-browser" in url:
            raise OSError("403 rate limit")
        return ok(url)
    nowe = nw.sprawdz(repo, stan, zlecenia, pobierz=pobierz, dzis=dt.date(2026, 11, 15))
    assert [n.split(" (")[0] for n in nowe] == ["npm sharp 0.35.4 → 0.36.0"]
    assert "agent-browser" in json.loads(stan.read_text(encoding="utf-8"))["bledy"]


def test_rutyna_bez_modelu_w_cronie():
    jobs = {j["id"]: j for j in yaml.safe_load((SKRYPT.parents[1] / "cron/jobs.yaml").read_text(encoding="utf-8"))["jobs"]}
    assert jobs["jarvo-new-versions"]["no_agent"] is True and jobs["jarvo-new-versions"]["script"] == "nowe_wersje.py"
