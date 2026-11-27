"""Oczy floty: obraz z narzędzi do modelu głównego i narzędzia ekranu oraz telefonu bez tool_search.

Klucze (jarvo/flota.py KLUCZE_WSZYSTKICH) i middleware obrazu MCP (zgody/plugin/obraz.py) sprawdzam zawsze. Decyzję
Hermesa (obraz natywnie dla commandcode, zapas bez obrazu dostaje tekst, tool_search wyłączony) sprawdzam prawdziwym
kodem Hermesa offline (config w tmp, bez kluczy i sieci) przy JARVO_TEST_HERMES_SRC i JARVO_HERMES_PYTHON, jak
test_prompt_hermesa.py.
"""

from __future__ import annotations

import base64
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from jarvo import flota  # noqa: E402
import install_fleet  # noqa: E402

_spec = importlib.util.spec_from_file_location("jarvo_zgody_obraz", REPO / "zgody" / "plugin" / "obraz.py")
obraz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(obraz)

K = flota.KLUCZE_WSZYSTKICH
MODELE = K["providers.commandcode.models"]


# ------------------------------------------------------------------------------------------------ klucze profili

def test_klucze_oczu_we_wszystkich_profilach():
    assert K["tools.tool_search.enabled"] == "off"
    assert MODELE["deepseek/deepseek-v4.1-flash"] == {"supports_vision": True}
    assert MODELE["deepseek/deepseek-v4-pro"] == {"supports_vision": False}
    assert K["auxiliary.vision.timeout"] == 45 and K["auxiliary.vision.reasoning_effort"] == "low"
    # provider/model/base_url w auxiliary.vision przełączyłyby każdy zrzut na model pomocniczy (vision_routing.py)
    assert not {"auxiliary.vision.provider", "auxiliary.vision.model", "auxiliary.vision.base_url"} & set(K)
    # model.supports_vision dotyczy każdego modelu, także zapasu bez obrazu
    assert "model.supports_vision" not in K


def test_kazdy_model_commandcode_floty_ma_zmierzony_obraz():
    fleet = yaml.safe_load((REPO / "fleet.yaml").read_text(encoding="utf-8"))
    modele = set(fleet["models"]["presets"]["commandcode"].values())
    modele |= {z["model"] for z in fleet["models"]["fallback"].values() if z.get("provider") == "commandcode"}
    modele.add("deepseek/deepseek-v4.1-flash")                                # model główny instalacji (27.11)
    assert modele <= set(MODELE), modele - set(MODELE)


def test_wpis_modeli_z_kropka_i_ukosnikiem_trafia_do_configu(tmp_path):
    plik = tmp_path / "ustawienia.json"
    plik.write_text(json.dumps({"wszystkie": K, "profile": {}}), encoding="utf-8")
    a = install_fleet.parser().parse_args(["--dane", str(tmp_path / "dane"), "--build", str(tmp_path / "build"),
                                           "--natywnie", "--bez-sekretow", "--ustawienia-profili", str(plik)])
    f = install_fleet.Flota(a, wypisz=lambda _t: None)
    config = tmp_path / "dane" / "profiles" / "jarvo" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("model:\n  provider: commandcode\n  default: deepseek/deepseek-v4.1-flash\n"
                      "auxiliary:\n  jarvo_wiedza:\n    timeout: 600\n", encoding="utf-8")
    f.ustaw_klucze_profilu("jarvo", config)
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert cfg["providers"]["commandcode"]["models"]["deepseek/deepseek-v4.1-flash"]["supports_vision"] is True
    assert cfg["tools"]["tool_search"]["enabled"] == "off"
    assert cfg["auxiliary"] == {"jarvo_wiedza": {"timeout": 600}, "vision": {"timeout": 45, "reasoning_effort": "low"}}


# ------------------------------------------------------------------------------------------------ obraz z MCP

def _wynik_mcp(tekst: str) -> str:
    return json.dumps({"result": tekst}, ensure_ascii=False)


def test_middleware_przepuszcza_bez_obrazu_i_poza_mcp(monkeypatch):
    monkeypatch.setattr(obraz, "obraz_natywny", lambda: True)
    for nazwa, wynik in (("terminal", _wynik_mcp("MEDIA:/tmp/x.jpg")), ("mcp__phone__screen", _wynik_mcp("1 [Button]")),
                         ("mcp__phone__shot", {"_multimodal": True, "content": []})):
        assert obraz.obraz_mcp(tool_name=nazwa, args={}, next_call=lambda _a, w=wynik: w) is wynik
    brak = _wynik_mcp("MEDIA:/nie/ma/takiego.jpg\nopis")
    assert obraz.obraz_mcp(tool_name="mcp__phone__shot", args={}, next_call=lambda _a: brak) is brak


def test_middleware_bez_obrazu_w_modelu_zostawia_tekst(tmp_path, monkeypatch):
    monkeypatch.setattr(obraz, "obraz_natywny", lambda: False)
    wynik = _wynik_mcp(f"MEDIA:{tmp_path / 'a.jpg'}")
    assert obraz.obraz_mcp(tool_name="mcp__phone__shot", args={"phone": "third"}, next_call=lambda _a: wynik) is wynik


def test_bramka_bez_hermesa_to_tekst():
    assert obraz.obraz_natywny() in (True, False)
    if importlib.util.find_spec("tools") is None:
        assert obraz.obraz_natywny() is False


def test_rejestracja_middleware():
    zapisane = []

    class Ctx:
        def register_middleware(self, rodzaj, cb):
            zapisane.append((rodzaj, cb))

    obraz.zarejestruj(Ctx())
    assert zapisane == [("tool_execution", obraz.obraz_mcp)]
    manifest = yaml.safe_load((REPO / "zgody" / "plugin" / "plugin.yaml").read_text(encoding="utf-8"))
    assert manifest["provides_middleware"] == ["tool_execution"]


def test_shot_jako_obraz_z_tekstem_ekranu(tmp_path, monkeypatch):
    Image = pytest.importorskip("PIL.Image")
    monkeypatch.setattr(obraz, "obraz_natywny", lambda: True)
    maly, duzy = tmp_path / "shot.jpg", tmp_path / "ekran.png"
    Image.new("RGB", (360, 800), "white").save(maly, "JPEG", quality=60)
    Image.new("RGB", (2560, 1440), "white").save(duzy, "PNG")
    tekst = f"MEDIA:{maly}\njpeg 360x800 of the 720x1600 screen\n1 [Button] \"Pomiń\" @360,1500"
    wynik = obraz.obraz_mcp(tool_name="mcp__phone__shot", args={}, next_call=lambda _a: _wynik_mcp(tekst))
    assert wynik["_multimodal"] is True and wynik["content"][0] == {"type": "text", "text": tekst}
    url = wynik["content"][1]["image_url"]["url"]
    assert base64.b64decode(url.split(",", 1)[1]) == maly.read_bytes()                # mały JPEG bez przekodowania
    assert "Pomiń" in wynik["text_summary"] and "MEDIA:" in wynik["text_summary"]
    duza = obraz.koperta(_wynik_mcp(f"MEDIA:{duzy}"))
    with Image.open(io.BytesIO(base64.b64decode(duza["content"][1]["image_url"]["url"].split(",", 1)[1]))) as img:
        assert img.format == "JPEG" and max(img.size) == obraz.DLUZSZY_BOK


# ------------------------------------------------------------------------------------------------ prawdziwy Hermes

HERMES_SRC = os.environ.get("JARVO_TEST_HERMES_SRC")
HERMES_PY = os.environ.get("JARVO_HERMES_PYTHON")

DECYZJA = r"""
import importlib.util, json, os, sys
from pathlib import Path
from hermes_cli.config import load_config
from tools.computer_use.vision_routing import should_route_capture_to_aux_vision
from tools.vision_tools import _accepts_tool_result_images
from agent.image_routing import decide_image_input_mode, _lookup_supports_vision
from agent.vision_message_prep import VisionMessagePrepMixin
from tools.tool_search import load_config as ts_config, should_activate
cfg = load_config()
p = "commandcode"
wynik = {m: {"capture_aux": should_route_capture_to_aux_vision(p, m, cfg),
             "tool_result": _accepts_tool_result_images(p, m, cfg),
             "tryb": decide_image_input_mode(p, m, cfg), "obraz": _lookup_supports_vision(p, m, cfg)}
         for m in sys.argv[2:]}
from PIL import Image
plik = Path(os.environ["HERMES_HOME"]) / "shot.jpg"
Image.new("RGB", (360, 800), "white").save(plik, "JPEG")
obraz_spec = importlib.util.spec_from_file_location("jarvo_zgody_obraz", Path(sys.argv[1]) / "obraz.py")
obraz = importlib.util.module_from_spec(obraz_spec); obraz_spec.loader.exec_module(obraz)
wynik["bramka"] = obraz.obraz_natywny()
koperta = obraz.obraz_mcp(tool_name="mcp__phone__shot", args={},
                          next_call=lambda _a: json.dumps({"result": f"MEDIA:{plik}\n1 [Button] \"OK\" @1,1"}))
class Agent(VisionMessagePrepMixin):
    def __init__(self, model): self.provider, self.model = p, model
wynik["tresc"] = {m: type(Agent(m)._tool_result_content_for_active_model("mcp__phone__shot", koperta)).__name__
                  for m in sys.argv[2:]}
c = ts_config()
wynik["tool_search"] = {"enabled": c.enabled, "aktywny": should_activate(c, 7000, 1_000_000)}
print("WYNIK " + json.dumps(wynik))
"""


@pytest.mark.skipif(not (HERMES_SRC and HERMES_PY),
                    reason="ustaw JARVO_TEST_HERMES_SRC i JARVO_HERMES_PYTHON, aby sprawdzić decyzję kodem Hermesa")
def test_decyzja_hermesa_obraz_natywnie_a_zapas_tekstem(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    cfg = {"model": {"provider": "commandcode", "default": "deepseek/deepseek-v4.1-flash"}}
    for klucz, wartosc in K.items():
        *sciezka, ostatni = klucz.split(".")
        wezel = cfg
        for czesc in sciezka:
            wezel = wezel.setdefault(czesc, {})
        wezel[ostatni] = wartosc
    (home / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.endswith(("_API_KEY", "_TOKEN"))}
    env.update(HERMES_HOME=str(home), HOME=str(tmp_path), PYTHONUTF8="1")
    modele = ["deepseek/deepseek-v4.1-flash", "deepseek/deepseek-v4-flash", "deepseek/deepseek-v4-pro"]
    wyjscie = subprocess.run([HERMES_PY, "-P", "-c", DECYZJA, str(REPO / "zgody" / "plugin"), *modele],
                             cwd=HERMES_SRC, env=env, capture_output=True, text=True, timeout=300, check=True).stdout
    w = json.loads(next(l for l in wyjscie.splitlines() if l.startswith("WYNIK "))[len("WYNIK "):])
    for m in modele[:2]:
        assert w[m] == {"capture_aux": False, "tool_result": True, "tryb": "native", "obraz": True}, m
        assert w["tresc"][m] == "list", m                                       # obraz w wyniku narzędzia
    assert w["deepseek/deepseek-v4-pro"]["capture_aux"] is True and w["deepseek/deepseek-v4-pro"]["obraz"] is False
    assert w["tresc"]["deepseek/deepseek-v4-pro"] == "str"                    # zapas bez obrazu: tekst, tura idzie dalej
    assert w["bramka"] is True
    assert w["tool_search"] == {"enabled": "off", "aktywny": False}
