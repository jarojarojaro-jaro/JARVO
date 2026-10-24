"""Mózg floty z aplikacji (hq/plugin/mozg.py): rozpoznanie klucza, sprawdzenie u dostawcy, zapis do .env, przełączenie
profili floty na zestaw dostawcy, trwały wybór dla buildu (fleetlib.Fleet.apply_app_choice) i katalog modeli
w fleet.json wtyczki (hqbuild.fleet_json). Trasy: tests/test_aplikacja.py."""
from __future__ import annotations

import json
import sys

import pytest

from conftest import REPO, load_script

MZ = load_script("hq/plugin/mozg.py", "jarvo_test_mozg")
sys.path.insert(0, str(REPO / "scripts"))
import fleetlib as fl  # noqa: E402

FLOTA = {
    "agents": [{"name": "jarvo", "model_tier": "frontier", "delegation_tier": "fast"},
               {"name": "jarvo-web", "model_tier": "strong", "delegation_tier": "fast"},
               {"name": "../zle", "model_tier": "strong"}],
    "modele": {"domyslny": "openai-codex",
               "zestawy": {"openai-codex": {"frontier": "g6", "strong": "g6", "fast": "g6"},
                           "openrouter": {"frontier": "o-f", "strong": "o-s", "fast": "o-q"}},
               "zapasowe": {"openai-codex": {"provider": "commandcode", "model": "ds"}}},
}
CFG = """# config profilu (komentarz zostaje)
model:
  provider: "openai-codex"
  default: "g6"
  base_url: https://chatgpt.com/backend-api/codex
delegation:
  model: "g6"
  provider: "openai-codex"
  max_concurrent_children: 3
auxiliary:
  jarvo_wiedza:
    model: g6
fallback_providers:
  - provider: "commandcode"
    model: "ds"
"""


def test_rozpoznaj_po_przedrostku():
    assert MZ.rozpoznaj("sk-or-v1-" + "a" * 40) == "openrouter"
    assert MZ.rozpoznaj("sk-ant-api03-" + "b" * 40) == "anthropic"
    assert MZ.rozpoznaj("sk-proj-" + "c" * 40) == "openai-api"
    assert MZ.rozpoznaj("  sk-" + "d" * 40 + "\n") == "openai-api"
    for zly in ("", "sk-or-", "sk-" + "a" * 10, "pk-" + "a" * 40, "sk-" + "a" * 30 + " b", "sk-" + "ą" * 30):
        assert MZ.rozpoznaj(zly) is None


def test_sprawdz_kody_i_naglowki():
    widziane = []

    def get(kod):
        def f(url, nagl):
            widziane.append((url, nagl))
            if isinstance(kod, Exception):
                raise kod
            return kod
        return f
    assert MZ.sprawdz("anthropic", "sk-ant-x", get=get(200)) == "ok"
    assert widziane[-1][1]["x-api-key"] == "sk-ant-x" and "Authorization" not in widziane[-1][1]
    assert MZ.sprawdz("openai-api", "sk-x", get=get(429)) == "ok"
    assert widziane[-1][1]["Authorization"] == "Bearer sk-x"
    assert MZ.sprawdz("openrouter", "k", get=get(401)) == "zly"
    assert MZ.sprawdz("openrouter", "k", get=get(403)) == "zly"
    assert MZ.sprawdz("openrouter", "k", get=get(502)) == "siec"
    assert MZ.sprawdz("openrouter", "k", get=get(OSError("x"))) == "siec"


def test_ustaw_zmienna_zamienia_dopisuje_i_chmod(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# nagłówek\nA=1\nOPENROUTER_API_KEY=stary\nexport OPENROUTER_API_KEY=drugi\nB=2\n", encoding="utf-8")
    MZ.ustaw_zmienna(env, "OPENROUTER_API_KEY", "nowy")
    assert env.read_text(encoding="utf-8") == "# nagłówek\nA=1\nOPENROUTER_API_KEY=nowy\nB=2\n"
    assert env.stat().st_mode & 0o777 == 0o600
    MZ.ustaw_zmienna(tmp_path / "brak" / ".env", "X", "y")
    assert (tmp_path / "brak" / ".env").read_text(encoding="utf-8") == "X=y\n"


def _profile(tmp_path):
    for a in ("jarvo", "jarvo-web"):
        d = tmp_path / "profiles" / a
        d.mkdir(parents=True)
        (d / "config.yaml").write_text(CFG, encoding="utf-8")
    (tmp_path / "config.yaml").write_text("model:\n  # domyślny\n  provider: openai-codex\n  default: g6\n",
                                          encoding="utf-8")


def test_przelacz_flote(tmp_path):
    pytest.importorskip("ruamel.yaml")
    import yaml
    _profile(tmp_path)
    assert MZ.przelacz(tmp_path, FLOTA, "openrouter") == ["jarvo", "jarvo-web", "default"]
    j = yaml.safe_load((tmp_path / "profiles" / "jarvo" / "config.yaml").read_text(encoding="utf-8"))
    assert j["model"] == {"provider": "openrouter", "default": "o-f"}
    assert j["delegation"] == {"model": "o-q", "provider": "openrouter", "max_concurrent_children": 3}
    assert j["auxiliary"]["jarvo_wiedza"]["model"] == "o-f" and "fallback_providers" not in j
    assert "# config profilu" in (tmp_path / "profiles" / "jarvo" / "config.yaml").read_text(encoding="utf-8")
    w = yaml.safe_load((tmp_path / "profiles" / "jarvo-web" / "config.yaml").read_text(encoding="utf-8"))
    assert w["model"]["default"] == "o-s"
    h = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert "provider: openrouter" in h and "default: o-q" in h and "# domyślny" in h
    # z powrotem na ChatGPT: model zapasowy zestawu wraca
    MZ.przelacz(tmp_path, FLOTA, "openai-codex")
    j = yaml.safe_load((tmp_path / "profiles" / "jarvo" / "config.yaml").read_text(encoding="utf-8"))
    assert j["fallback_providers"] == [{"provider": "commandcode", "model": "ds"}] and j["model"]["default"] == "g6"
    with pytest.raises(MZ.BladMozgu):
        MZ.przelacz(tmp_path, FLOTA, "anthropic")


def test_podlacz_klucz_calosc_i_wybor_z_buildu(tmp_path):
    pytest.importorskip("ruamel.yaml")
    _profile(tmp_path)
    build = tmp_path / "BUILD.json"
    build.write_text(json.dumps({"modele": {"env": "", "dostawca": "openai-codex"}}), encoding="utf-8")
    rozdane = []
    klucz = "sk-or-v1-" + "e" * 48
    w = MZ.podlacz_klucz(klucz, home=tmp_path, flota=FLOTA, stan=tmp_path / "state" / "wybor.json", build_json=build,
                         get=lambda _u, _n: 200, rozdaj=rozdane.append)
    assert w == {"dostawca": "openrouter", "nazwa": "OpenRouter", "profile": ["jarvo", "jarvo-web", "default"]}
    assert rozdane == [tmp_path]
    wybor = json.loads((tmp_path / "state" / "wybor.json").read_text(encoding="utf-8"))
    assert wybor["dostawca"] == "openrouter" and wybor["nad"] == ""
    assert f"OPENROUTER_API_KEY={klucz}" in (tmp_path / ".env").read_text(encoding="utf-8")
    # błąd zapisu nie niesie klucza
    with pytest.raises(MZ.BladMozgu) as e:
        MZ.podlacz_klucz(klucz, home=tmp_path, flota=FLOTA, stan=tmp_path / "state" / "wybor.json", build_json=None,
                         get=lambda _u, _n: 200, rozdaj=lambda _h: (_ for _ in ()).throw(OSError(klucz)))
    assert e.value.kod == "zapis" and klucz not in str(e.value) and e.value.__cause__ is None


def test_apply_app_choice_dopoki_jarvo_env_sie_nie_zmieni():
    f = fl.load_fleet()
    env = {"JARVO_MODEL_PROVIDER": ""}
    assert f.apply_app_choice(env, {"dostawca": "openrouter", "nad": ""}) is True
    f.apply_model_overrides(env)
    assert f.provider == "openrouter" and f.model_for("frontier") == "anthropic/claude-opus-5.5"
    f = fl.load_fleet()
    env = {"JARVO_MODEL_PROVIDER": "commandcode"}            # jarvo.env zmieniony po wyborze w aplikacji: wygrywa
    assert f.apply_app_choice(env, {"dostawca": "openrouter", "nad": ""}) is False
    assert env["JARVO_MODEL_PROVIDER"] == "commandcode"
    assert f.apply_app_choice({}, {"dostawca": "openrouter", "nad": None}) is True     # stary build bez `modele`
    assert f.apply_app_choice({}, {"dostawca": "nie-ma"}) is False
    assert f.apply_app_choice({}, None) is False
    f = fl.load_fleet()
    env = {}
    assert f.apply_app_choice(env, {"dostawca": "anthropic", "nad": ""}) is True
    f.apply_model_overrides(env)
    assert f.provider == "anthropic" and f.fallback is None


def test_fleet_json_ma_katalog_modeli():
    hq = load_script("scripts/hqbuild.py", "jarvo_test_mozg_hqbuild")
    d = hq.fleet_json()
    z = d["modele"]["zestawy"]
    assert d["modele"]["domyslny"] == "openai-codex"
    assert {"openai-codex", "openrouter", "anthropic", "openai-api"} <= set(z)
    assert all({"frontier", "strong", "fast"} <= set(v) for v in z.values())
    assert all("delegation_tier" in a for a in d["agents"])
    for nazwa in ("openrouter", "anthropic", "openai-api"):
        assert nazwa in MZ.DOSTAWCY and nazwa in z      # każdy klucz z aplikacji ma zestaw we flocie
