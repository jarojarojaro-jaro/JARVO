"""Twórca aplikacji, etap 3: werdykt bramki (punkty, blokady, niezmierzone), testy wrogie na Androidzie przez adb
(atrapa adb) i iOS w GitHub Actions (atrapa API). Bez sieci, bez urządzenia, bez macOS."""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "profiles" / "jarvo-mobile" / "scripts"))

import bramka  # noqa: E402
import ios_ci  # noqa: E402
import urzadzenie as ur  # noqa: E402


def zapisz(p: Path, dane) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dane), encoding="utf-8")


@pytest.fixture
def app(tmp_path):
    zapisz(tmp_path / "out/jakosc/sprawdz.json", {"kontrole": [{"id": "TYPY", "ok": True, "opis": ""},
                                                              {"id": "J-TODO", "ok": True, "ostrz": True, "opis": "1"}]})
    zapisz(tmp_path / "out/zrzuty/zrzuty.json", {"wyniki": [{"trasa": "/"}], "bledy_lacznie": 0, "axe_powazne": 0})
    zapisz(tmp_path / "out/jakosc/wrogie/wrogie.json", {"wyniki": [
        {"id": "konsola", "status": "ok"}, {"id": "duza-czcionka", "status": "not_run", "dlaczego": "tylko urządzenie"}]})
    return tmp_path


def ocena(zle: dict | None = None) -> dict:
    zle = zle or {}
    return {"osie": [{"os": n, "zaliczona": n not in zle, "dowod": f"web/iphone-jasny/start.png ({n})",
                      "roznica": zle.get(n, ""), "poprawka": "zmiana" if n in zle else ""} for n in bramka.OSIE]}


def test_pass_i_niezmierzone(app):
    w = bramka.werdykt(app, 1, ocena())
    assert w["werdykt"] == "PASS" and w["wynik"] == 100 and w["warstwy"] == ["web"]
    assert any("android" in n for n in w["niezmierzone"]) and any("duza-czcionka" in n for n in w["niezmierzone"])
    assert "Niezmierzone" in bramka.werdykt_md(w)


def test_punkty_osi(app):
    w = bramka.werdykt(app, 1, ocena({8: "animacja w pętli"}))
    assert w["wynik"] == 95 and w["werdykt"] == "PASS" and len(w["roznice"]) == 1
    w = bramka.werdykt(app, 1, ocena({1: "logowanie na start", 7: "biały prostokąt w ciemnym"}))
    assert w["wynik"] == 100 - 8 - 5 and w["werdykt"] == "REVISE" and len(w["roznice"]) == 2
    w = bramka.werdykt(app, 1, ocena({1: "a", 2: "b"}))
    assert w["wynik"] == 84 and w["werdykt"] == "REVISE"


def test_problemy_i_blokady(app):
    zapisz(app / "out/jakosc/wrogie/wrogie.json", {"wyniki": [{"id": "offline", "status": "blad", "dlaczego": "brak paska"}]})
    w = bramka.werdykt(app, 1, ocena())
    assert w["wynik"] == 85 and w["werdykt"] == "REVISE"
    zapisz(app / "out/jakosc/wrogie-android/wrogie.json", {"wyniki": [
        {"id": "smierc-procesu", "status": "blad", "dlaczego": "awaria aplikacji (log crash / ReactNativeJS)"}]})
    assert bramka.werdykt(app, 1, ocena())["werdykt"] == "BLOCK"


def test_sekret_brak_zrzutow_runda(app):
    zapisz(app / "out/jakosc/sprawdz.json", {"kontrole": [{"id": "J-SEKRET", "ok": False, "opis": "sk_live w kodzie"}]})
    assert bramka.werdykt(app, 1, ocena())["werdykt"] == "BLOCK"
    (app / "out/jakosc/sprawdz.json").unlink()
    (app / "out/zrzuty/zrzuty.json").unlink()
    w = bramka.werdykt(app, 4, ocena())
    assert w["werdykt"] == "BLOCK" and len(w["blokady"]) == 2


def test_os_bez_dowodu_i_bez_poprawki(app):
    o = ocena({3: "małe cele"})
    o["osie"][2]["poprawka"] = ""
    o["osie"][0]["dowod"] = ""
    w = bramka.werdykt(app, 1, o)
    assert any("bez dowodu" in p for p in w["problemy"]) and any("bez najmniejszej poprawki" in p for p in w["problemy"])


# ------------------------------------------------------------------ Android przez adb (atrapa)

class FakeAdb(ur.Adb):
    def __init__(self, crash: str = "", siec: bool = False, perms=("android.permission.CAMERA",)):
        super().__init__("test:5555", "adb")
        self.polecenia: list[str] = []
        self.crash, self.siec, self.perms = crash, siec, perms

    def polacz(self):
        pass

    def run(self, *args, timeout=60, binarnie=False):
        if binarnie:
            return b"\x89PNG fake"
        return self.sh(" ".join(args[1:]) if args and args[0] == "shell" else " ".join(args))

    def sh(self, p, timeout=60):
        self.polecenia.append(p)
        if p.startswith("getprop ro.build.version.release"):
            return "14\n"
        if p.startswith("getprop"):
            return "34\n"
        if p == "wm size":
            return "Physical size: 1080x2340\n"
        if p == "wm density":
            return "Physical density: 420\n"
        if p.startswith("pm list packages"):
            return "package:host.exp.exponent\n"
        if p.startswith("logcat -d"):
            return self.crash
        if p.startswith("cat /sdcard/jarvo-ui.xml"):
            return '<node text="Start"/><node text="Salon Ola"/>'
        if p.startswith("dumpsys package"):
            return "\n".join(f"      {x}: granted=true" for x in self.perms)
        if p.startswith("dumpsys activity"):
            return "  mResumedActivity: ActivityRecord{1 u0 pl.salonola.app/.MainActivity t9}"
        if p.startswith("ping"):
            if self.siec:
                return "1 packets transmitted, 1 received, 0% packet loss"
            raise RuntimeError("unreachable")
        return ""


def test_android_wrogie_ok_i_przywraca_ustawienia(tmp_path, monkeypatch):
    monkeypatch.setattr(ur, "CZEKAJ_S", 0)
    monkeypatch.setattr(ur.time, "sleep", lambda s: None)
    adb = FakeAdb()
    r = ur.wrogie(adb, "pl.salonola.app", tmp_path)
    st = {w["id"]: w["status"] for w in r["wyniki"]}
    assert st["start"] == "ok" and st["duza-czcionka"] == "ok" and st["uprawnienia"] == "ok"
    assert st["offline"] == "blad"            # atrapa nie pokazuje „Brak internetu” → test działa
    for przywroc in ("settings put system font_scale 1.0", "wm size reset", "wm density reset", "cmd uimode night no",
                     "cmd connectivity airplane-mode disable"):
        assert przywroc in adb.polecenia
    assert "pm revoke pl.salonola.app android.permission.CAMERA" in adb.polecenia
    assert (tmp_path / "wrogie.json").exists() and (tmp_path / "start-ekran.png").read_bytes().startswith(b"\x89PNG")


def test_android_awaria_i_siec_ktorej_nie_da_sie_odciac(tmp_path, monkeypatch):
    monkeypatch.setattr(ur, "CZEKAJ_S", 0)
    monkeypatch.setattr(ur.time, "sleep", lambda s: None)
    adb = FakeAdb(crash="E/AndroidRuntime( 123): FATAL EXCEPTION: main\n", siec=True)
    r = ur.wrogie(adb, "pl.salonola.app", tmp_path, ["start", "offline"])
    st = {w["id"]: w for w in r["wyniki"]}
    assert st["start"]["status"] == "blad" and "awaria" in st["start"]["dlaczego"]
    assert st["offline"]["status"] == "not_run"


def test_android_expo_go_pomija_testy_buildu(tmp_path, monkeypatch):
    monkeypatch.setattr(ur, "CZEKAJ_S", 0)
    monkeypatch.setattr(ur.time, "sleep", lambda s: None)
    adb = FakeAdb()
    r = ur.wrogie(adb, "exp://u.expo.dev/p/group/g", tmp_path, ["uprawnienia", "swieza-instalacja", "start"])
    st = {w["id"]: w["status"] for w in r["wyniki"]}
    assert st == {"uprawnienia": "not_run", "swieza-instalacja": "not_run", "start": "ok"}
    assert any("am start -a android.intent.action.VIEW -d 'exp://u.expo.dev/p/group/g' host.exp.exponent" == p for p in adb.polecenia)
    assert not any(p.startswith("pm clear") for p in adb.polecenia)


def test_android_bez_urzadzenia(monkeypatch):
    adb = ur.Adb("nie-ma:5555", "/nie/ma/adb")
    with pytest.raises(ur.BrakUrzadzenia):
        adb.polacz()


# ------------------------------------------------------------------ iOS w GitHub Actions (atrapa API)

def test_ios_bez_tokenu(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(ios_ci.BrakTokenu):
        ios_ci.token()


def test_ios_przebieg_i_artefakt(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setattr(ios_ci.time, "sleep", lambda s: None)
    bufor = io.BytesIO()
    with zipfile.ZipFile(bufor, "w") as z:
        z.writestr("jasny-start.png", b"\x89PNG" + b"x" * 20000)
        z.writestr("ciemny-start.png", b"\x89PNG" + b"x" * 100)          # prawie pusty → błąd
        z.writestr("bledy.txt", "")
    wywolania = []

    def api(metoda, sciezka, dane=None, surowe=False):
        wywolania.append((metoda, sciezka, dane))
        if sciezka.endswith("/dispatches"):
            return {"workflow_run_id": 77}
        if sciezka.endswith("/artifacts"):
            return {"artifacts": [{"name": "jarvo-ios", "id": 5}]}
        if sciezka.endswith("/zip"):
            return bufor.getvalue()
        return {"id": 77, "status": "completed", "conclusion": "success", "html_url": "https://github.com/o/r/actions/runs/77"}
    monkeypatch.setattr(ios_ci, "api", api)
    run_id = ios_ci.uruchom("o/r", "expo-go", ["/", "/wiecej"])
    assert run_id == 77 and wywolania[0][2] == {"ref": "jarvo/ci", "inputs": {"tryb": "expo-go", "trasy": "/ /wiecej"},
                                                "return_run_details": True}
    r = ios_ci.wynik(tmp_path, "o/r", 77, ios_ci.czekaj("o/r", 77, 1))
    st = {w["id"]: w["status"] for w in r["wyniki"]}
    assert st == {"jasny": "ok", "ciemny": "blad", "duza-czcionka": "not_run"}
    assert (tmp_path / "out/jakosc/ios/wynik.json").exists()


def test_ios_stare_api_bez_id(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setattr(ios_ci.time, "sleep", lambda s: None)
    monkeypatch.setattr(ios_ci, "api", lambda m, s, d=None, surowe=False: {} if s.endswith("/dispatches")
                        else {"workflow_runs": [{"id": 91}]})
    assert ios_ci.uruchom("o/r", "build", ["/"]) == 91


def test_ios_przygotuj(tmp_path):
    p = ios_ci.przygotuj(tmp_path)
    assert p == tmp_path / ".github/workflows/jarvo-ios.yml" and "macos-26" in p.read_text(encoding="utf-8")
