"""Pełna macierz CI instalacji natywnej (.github/workflows/natywnie.yml) i logika tests/live/natywnie_e2e.py.

Statycznie, bez uruchamiania workflow: 5 nóg z docs/NATYWNIE.md (g) „Runnery CI”, wyzwalacze (ręcznie, tagi v*, push
na main tylko w plikach instalatora i manifestu), akcje przypięte pełnym SHA w wersjach z T17, sekret tylko
w otoczeniu dwóch kroków (nigdy w `run`, echo ani otoczeniu zadania), instalacja dokładnie poleceniem z README (albo
z nagłówka bootstrapu, dopóki README go nie podaje) z adresem i JARVO_REF = SHA commitu, JARVO_NO_AUTOSTART tylko na
Linuksie, artefakty zawsze, ale po skanie sekretów i z retencją 14 dni, Node z vendor/natywne.yaml.

Logika skryptu e2e na danych z testu (bez sieci, portów i zmian w systemie): ocena `jarvo doctor --json` z jawnymi
wyjątkami, log drugiego przebiegu (UTF-8 i UTF-16 z Tee-Object), migawka i różnica z wyjątkami, skan sekretów
(plik z trafieniem znika), maskowanie, atrapa modelu dla pracownika kanbana, aktywni agenci z fleet.yaml. Wzory
sekretów w tym pliku składamy w czasie testu: validate.py szuka ich w źródłach repo.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from conftest import REPO, WINDOWS, load_script

WORKFLOW = REPO / ".github" / "workflows" / "natywnie.yml"
E2E = REPO / "tests" / "live" / "natywnie_e2e.py"
NATYWNIE = REPO / "docs" / "NATYWNIE.md"
SHA = re.compile(r"^[0-9a-f]{40}$")
# T17 (docs/NATYWNIE.md): wersje po przeglądzie; SHA sprawdzone przez `gh api repos/<akcja>/git/ref/tags/<wersja>`
# 2026-10-25 (lekkie tagi, więc SHA tagu = SHA commitu; action.yml każdej: using node24)
AKCJE = {
    "actions/checkout": ("v7.0.1", "3d3c42e5aac5ba805825da76410c181273ba90b1"),
    "actions/setup-python": ("v7.1.0", "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0"),
    "actions/setup-node": ("v7.1.0", "949feb2413d6458794dcd2491c4babbbce0c15c1"),
    "actions/upload-artifact": ("v7.0.2", "cf430e030ddbb5b0abf93d22962f4752f3646cd9"),
}
SEKRET = "JARVO_TEST_OPENROUTER_KEY"


@pytest.fixture(scope="module")
def wf() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def zadanie(wf) -> dict:
    assert list(wf["jobs"]) == ["instalacja"]
    return wf["jobs"]["instalacja"]


@pytest.fixture(scope="module")
def kroki(zadanie) -> list[dict]:
    return zadanie["steps"]


@pytest.fixture(scope="module")
def e2e():
    return load_script("tests/live/natywnie_e2e.py", "natywnie_e2e_test")


def _krok(kroki: list[dict], poczatek: str) -> dict:
    pasujace = [k for k in kroki if str(k.get("name", "")).startswith(poczatek)]
    assert len(pasujace) == 1, f"krok {poczatek!r}: {len(pasujace)}"
    return pasujace[0]


def _instalacje(kroki: list[dict]) -> list[dict]:
    """Kroki, które uruchamiają polecenie instalacji (oba przebiegi, oba systemy)."""
    return [k for k in kroki if "jarvo/bootstrap/install." in str(k.get("run", ""))]


# ---------------------------------------------------------------- workflow: wyzwalacze, nogi, uprawnienia

def test_wyzwalacze_bez_pushy_na_kazdy_commit(wf):
    on = wf.get("on", wf.get(True))                  # PyYAML (YAML 1.1) czyta klucz `on` jako True
    assert set(on) == {"workflow_dispatch", "push"}, "bez pull_request i bez harmonogramu: macOS liczy się ×10"
    push = on["push"]
    assert push["tags"] == ["v*"]
    assert push["branches"] == ["main"]
    for wzor in ("jarvo/**", "vendor/natywne*", "infra/python/natywne/**"):
        assert wzor in push["paths"], wzor
    assert all(not p.startswith(("!", "**")) for p in push["paths"]), "push na main tylko w wybranych ścieżkach"


def test_piec_nog_z_planu(zadanie):
    """Nogi i obrazy runnerów jak w docs/NATYWNIE.md (g) „Runnery CI” (dokument i CI mówią to samo)."""
    wiersz = next(w for w in NATYWNIE.read_text(encoding="utf-8").splitlines() if w.startswith("**Runnery CI.**"))
    plan = dict(re.findall(r"\b([A-Z0-9]{3,4}) = ([a-z0-9][a-z0-9.-]+[a-z0-9])", wiersz))
    assert set(plan) == {"W64", "WARM", "MARM", "L64", "LARM"}
    nogi = {n["noga"]: n["os"] for n in zadanie["strategy"]["matrix"]["include"]}
    assert nogi == plan
    assert zadanie["strategy"]["fail-fast"] is False, "jedna noga z błędem nie przerywa pozostałych"
    assert "latest" not in json.dumps(nogi), "przypięte obrazy runnerów (T15)"
    assert zadanie["runs-on"] == "${{ matrix.os }}"
    assert 60 <= zadanie["timeout-minutes"] <= 360


def test_uprawnienia_i_wspolbieznosc(wf, kroki):
    assert wf["permissions"] == {"contents": "read"}
    assert "github.ref" in wf["concurrency"]["group"]
    # trwającego przebiegu nie przerywamy (także tagu): nogi Windows kończą się, najnowszy commit czeka w kolejce
    assert wf["concurrency"]["cancel-in-progress"] is False
    checkout = next(k for k in kroki if str(k.get("uses", "")).startswith("actions/checkout@"))
    assert checkout["with"]["persist-credentials"] is False, "token GitHuba nie zostaje w .git/config"
    assert not any("continue-on-error" in k for k in kroki), "błąd ma być widoczny jako czerwona noga"


def test_akcje_przypiete_pelnym_sha():
    """Każde `uses:` to pełny SHA z komentarzem wersji (T17); wersje jak w tabeli T17 dokumentu, SHA jak w AKCJE."""
    tekst = WORKFLOW.read_text(encoding="utf-8")
    uzycia = re.findall(r"^\s*(?:-\s+)?uses:\s*(\S+?)@(\S+)(?:\s+#\s*(\S+))?\s*$", tekst, re.M)
    assert uzycia, "brak akcji"
    t17 = next(w for w in NATYWNIE.read_text(encoding="utf-8").splitlines() if w.startswith("| **T17**"))
    wersje_planu = dict(re.findall(r"\b([a-z-]+) (v\d+\.\d+\.\d+)", t17))
    for akcja, ref, wersja in uzycia:
        assert SHA.match(ref), f"{akcja}@{ref}: potrzebny pełny SHA, nie tag"
        assert akcja in AKCJE, f"{akcja}: nowa akcja wymaga przeglądu (docs/SOURCES.md) i wpisu w AKCJE"
        assert (wersja, ref) == AKCJE[akcja], akcja
        assert wersje_planu.get(akcja.split("/", 1)[1]) == wersja, f"{akcja} {wersja} a T17 w docs/NATYWNIE.md"


def test_node_z_manifestu(kroki):
    tekst = (REPO / "vendor" / "natywne.yaml").read_text(encoding="utf-8")
    m = re.search(r"^  node:\n(?:    .*\n)*?    wersja:\s*\"?([0-9.]+)\"?", tekst, re.M)
    assert m, "vendor/natywne.yaml bez wersji node"
    node = next(k for k in kroki if str(k.get("uses", "")).startswith("actions/setup-node@"))
    assert str(node["with"]["node-version"]) == m.group(1)
    assert node["with"]["package-manager-cache"] is False


# ---------------------------------------------------------------- workflow: instalacja i sekrety

def _adresy_z_dokumentow() -> dict[str, str]:
    """Adres bootstrapu z README (gdy README podaje już polecenie natywne), inaczej z nagłówka bootstrapu."""
    bootstrap = REPO / "jarvo" / "bootstrap"
    zrodla = [REPO / "README.md", bootstrap / "install.ps1", bootstrap / "install.sh"]
    ps = sh = None
    for p in zrodla:
        t = p.read_text(encoding="utf-8")
        ps = ps or re.search(r"irm\s+(https://\S+/jarvo/bootstrap/install\.ps1)\s*\|\s*iex", t)
        sh = sh or re.search(r"curl\s+-fsSL\s+(https://\S+/jarvo/bootstrap/install\.sh)\s*\|\s*bash", t)
    assert ps and sh, "brak polecenia instalacji natywnej w README i w nagłówkach bootstrapów"
    return {"windows": ps.group(1), "posix": sh.group(1)}


def test_instalacja_poleceniem_z_readme_z_tego_commitu(kroki):
    adresy = _adresy_z_dokumentow()
    instalacje = _instalacje(kroki)
    assert len(instalacje) == 4, "dwa przebiegi na dwóch rodzinach systemów"
    for k in instalacje:
        assert k["env"]["JARVO_REF"] == "${{ github.sha }}", k["name"]
        run = k["run"]
        if k.get("shell") == "powershell":
            assert k["if"].replace("${{", "").replace("}}", "").strip().endswith("runner.os == 'Windows'")
            m = re.search(r'irm "(https://[^"]+/install\.ps1)" \| iex\b', run)
            assert m, run
            assert m.group(1).replace("$env:JARVO_REF", "main") == adresy["windows"]
            assert "Tee-Object -FilePath $log" in run
        else:
            assert "runner.os != 'Windows'" in k["if"]
            m = re.search(r'curl -fsSL "(https://[^"]+/install\.sh)" \| bash\b', run)
            assert m, run
            assert m.group(1).replace("$JARVO_REF", "main") == adresy["posix"]
            assert '| tee "$RUNNER_TEMP/natywnie-artefakty/instalacja-' in run
            # macOS jak bez Homebrew: `bash` z polecenia to /bin/bash 3.2 (L02), a nie bash 5 runnera
            assert run.index('[ "$RUNNER_OS" = macOS ]; then export PATH="/usr/bin:/bin:') < run.index("curl -fsSL")
        assert "--bez-path" not in run and "JARVO_ROOT" not in json.dumps(k), "domyślny korzeń i PATH jak u ludzi"


def test_autostart_wylaczony_tylko_na_linuksie(zadanie, kroki):
    for noga in zadanie["strategy"]["matrix"]["include"]:
        linux = noga["os"].startswith("ubuntu")
        assert noga["bez_autostartu"] == ("1" if linux else ""), noga["noga"]
    for k in _instalacje(kroki):
        if k.get("shell") != "powershell":
            assert k["env"]["JARVO_NO_AUTOSTART"] == "${{ matrix.bez_autostartu }}"
        else:
            assert "JARVO_NO_AUTOSTART" not in k.get("env", {})


def test_sekret_tylko_w_otoczeniu_dwoch_krokow(zadanie, kroki):
    """Sekret nigdy w `run` (wyrażenie wstawiłoby go w tekst skryptu), nie w echo, nie w otoczeniu zadania (tam tylko
    „tak/nie”), a w otoczeniu tylko kroku z prawdziwym modelem i skanu sekretów (skan szuka jego wartości)."""
    assert "secrets." not in json.dumps(zadanie.get("env", {})).replace(
        "secrets.JARVO_TEST_OPENROUTER_KEY != ''", ""), "w otoczeniu zadania tylko porównanie z pustym"
    assert zadanie["env"]["JARVO_E2E_KLUCZ"] == "${{ secrets.JARVO_TEST_OPENROUTER_KEY != '' && 'tak' || 'nie' }}"
    z_sekretem = []
    for k in kroki:
        run = str(k.get("run", ""))
        assert "secrets." not in run, k.get("name")
        assert not re.search(r"(echo|printf|Write-Host|Write-Output|print\()[^\n]*" + SEKRET, run), k.get("name")
        assert "set -x" not in run, "xtrace wypisałby wartości zmiennych"
        if "secrets." in json.dumps(k.get("env", {})) or "secrets." in json.dumps(k.get("with", {})):
            z_sekretem.append(k)
            assert k["env"] == {SEKRET: "${{ secrets.JARVO_TEST_OPENROUTER_KEY }}"}, k.get("name")
    assert [k.get("id") or k["name"] for k in z_sekretem] == ["Prawdziwy model (tylko z sekretem "
                                                                "JARVO_TEST_OPENROUTER_KEY)", "skan"]
    model = z_sekretem[0]
    assert "env.JARVO_E2E_KLUCZ == 'tak'" in model["if"]


def test_artefakty_zawsze_po_skanie(kroki):
    nazwy = [k.get("name") or k.get("uses") for k in kroki]
    skan = _krok(kroki, "Skan sekretów")
    wysylka = next(k for k in kroki if str(k.get("uses", "")).startswith("actions/upload-artifact@"))
    assert kroki.index(skan) < kroki.index(wysylka) == len(kroki) - 1, nazwy
    assert skan["id"] == "skan" and skan["if"] == "always()"
    assert "natywnie_e2e.py skan" in skan["run"]
    assert wysylka["if"] == "always() && steps.skan.outputs.gotowe == 'tak'", "bez skanu (np. awaria) bez wysyłki"
    w = wysylka["with"]
    assert w["retention-days"] == 14
    assert w["path"] == "${{ runner.temp }}/natywnie-artefakty"
    assert "${{ matrix.noga }}" in w["name"] and "run_attempt" in w["name"]
    assert w["include-hidden-files"] is False
    podsumowanie = _krok(kroki, "Podsumowanie")
    assert kroki.index(skan) < kroki.index(podsumowanie) < kroki.index(wysylka), "podsumowanie z oczyszczonego raportu"


def test_kroki_po_instalacji_nie_urywaja_sprzatania(kroki):
    """Po pierwszej instalacji każdy krok biegnie także po błędzie wcześniejszego (raport, odinstalowanie,
    migawka, skan i artefakty pokazują, co się stało); po anulowaniu tylko skan, podsumowanie i wysyłka."""
    pierwsza = kroki.index(_instalacje(kroki)[0])
    for k in kroki[pierwsza + 2:]:
        warunek = str(k.get("if", ""))
        assert "!cancelled()" in warunek or warunek.startswith("always()"), k.get("name")


def test_polecenia_e2e_istnieja(e2e, kroki):
    podpolecenia = set(next(a for a in e2e.parser()._actions if a.dest == "polecenie").choices)
    uzyte = re.findall(r"python -X utf8 -B tests/live/natywnie_e2e\.py (\S+)", WORKFLOW.read_text(encoding="utf-8"))
    assert set(uzyte) >= {"migawka", "sprawdz", "panel", "komputer", "drugi-przebieg", "zbierz-logi", "odinstaluj",
                          "roznica", "skan", "podsumowanie", "prawdziwy-model"}
    assert set(uzyte) <= podpolecenia
    przed = _krok(kroki, "Migawka komputera przed")
    assert kroki.index(przed) < kroki.index(_instalacje(kroki)[0]), "migawka przed pierwszą instalacją"


def test_wyjatki_doctora_z_macierzy_parsuja_sie(e2e, zadanie):
    for noga in zadanie["strategy"]["matrix"]["include"]:
        wyjatki = e2e.parsuj_dopusc([noga["dopusc"]])
        assert wyjatki and all(powod and stany <= {"uwaga", "blad"} for _n, stany, powod in wyjatki), noga["noga"]
        assert ("autostart" in {n for n, _s, _p in wyjatki}) == noga["os"].startswith("ubuntu"), noga["noga"]


def test_skrypt_e2e_pomoc():
    r = subprocess.run([sys.executable, "-X", "utf8", "-B", str(E2E), "--help"], capture_output=True, text=True,
                       encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr
    for podpolecenie in ("migawka", "sprawdz", "odinstaluj", "skan"):
        assert podpolecenie in r.stdout


# ---------------------------------------------------------------- logika skryptu e2e

def test_ocena_doctora(e2e):
    d = {"wyniki": [{"nazwa": "korzeń", "stan": "ok"}, {"nazwa": "wolne miejsce", "stan": "uwaga", "opis": "8 GB"},
                    {"nazwa": "port 9120 (podgląd HQ)", "stan": "uwaga", "opis": "zajęty"},
                    {"nazwa": "lightpanda", "stan": "brak_platformy", "opis": "Windows"}]}
    zielony, problemy, uzyte = e2e.ocen_doctora(d, e2e.parsuj_dopusc(["wolne miejsce=uwaga:mały dysk"]))
    assert not zielony and [p["nazwa"] for p in problemy] == ["port 9120 (podgląd HQ)"]
    assert uzyte == [{"nazwa": "wolne miejsce", "stan": "uwaga", "opis": "8 GB", "powod": "mały dysk"}]
    zielony, problemy, _ = e2e.ocen_doctora(d, e2e.parsuj_dopusc(["wolne miejsce=uwaga;port 91* (*)=uwaga,blad:x"]))
    assert zielony and not problemy, "wzór nazwy i kilka wyjątków w jednym wierszu macierzy"
    d["wyniki"].append({"nazwa": "Hermes", "stan": "blad"})
    assert e2e.ocen_doctora(d, e2e.parsuj_dopusc(["*=uwaga"]))[0] is False, "błąd bez wyjątku na błąd"
    assert e2e.ocen_doctora(None, [])[0] is False, "brak JSON = czerwony"
    with pytest.raises(Exception):
        e2e.parsuj_dopusc(["bez-stanu"])


@pytest.mark.parametrize("kodowanie", ["utf-8", "utf-16"])
def test_drugi_przebieg(e2e, tmp_path, kodowanie):
    art = tmp_path / "art"
    dobry = ("[jarvo] Jarvo natywnie: instalacja\n[jarvo] uv 0.12.13: już jest\n[jarvo] kod Jarva abc: juz jest\n"
             "Gotowe. Zmiany w tym przebiegu: brak.\n[jarvo] Gotowe. Polecenie jarvo działa\n")
    log = tmp_path / "instalacja-2.log"
    log.write_text(dobry, encoding=kodowanie)        # utf-16 = Tee-Object z Windows PowerShell 5.1 (BOM)
    assert e2e.main(["drugi-przebieg", str(log), "--artefakty", str(art)]) == 0
    log.write_text(dobry.replace("brak.", "katalogi, uv.") + "[jarvo] pobieram uv 0.12.13\n", encoding=kodowanie)
    assert e2e.main(["drugi-przebieg", str(log), "--artefakty", str(art)]) == 1
    punkt = next(p for p in json.loads((art / "raport.json").read_text(encoding="utf-8"))["punkty"]
                 if p["id"] == "drugi-przebieg")
    assert punkt["ok"] is False and "katalogi, uv" in punkt["opis"] and "pobieram uv" in punkt["opis"]


def test_czytaj_tekst_z_limitem_utf16(e2e, tmp_path):
    p = tmp_path / "log.txt"
    p.write_text("początek\n" + "x" * 5000 + "\nkoniec źdźbła\n", encoding="utf-16", newline="\n")
    assert e2e.czytaj_tekst(p).startswith("początek")
    assert e2e.czytaj_tekst(p, limit=101).endswith("koniec źdźbła\n"), "nieparzysty limit nie psuje UTF-16"
    assert e2e.czytaj_tekst(p, limit=100).endswith("koniec źdźbła\n")
    p.write_bytes(b"\xef\xbb\xbfza\xc5\xbc\xc3\xb3\xc5\x82\xc4\x87")
    assert e2e.czytaj_tekst(p) == "zażółć"


def _migawka(e2e, monkeypatch, dom: Path) -> dict:
    miejsca = [("dom", dom, 1, "nazwy"), ("local", dom / ".local", 3, "nazwy"), ("start", dom / "start", 1, "tresc"),
               (f"odcisk:{dom / 'cache'}", dom / "cache", 0, "odcisk")]
    monkeypatch.setattr(e2e, "miejsca", lambda env=None: miejsca)
    monkeypatch.setattr(e2e, "_rejestr_windows", lambda: {})
    monkeypatch.setattr(e2e, "_autostart_systemu", lambda: {})
    return e2e.migawka({"USERPROFILE": str(dom), "HOME": str(dom)}, u=e2e.sciezki.Uklad(
        root=dom / "jarvo", program=dom / "jarvo" / "program", dane=dom / "jarvo" / "dane", stan=dom / "jarvo" / "stan",
        logi=dom / "jarvo" / "logi", cache=dom / "jarvo" / "cache", build=dom / "jarvo" / "build"))


def test_migawka_i_roznica(e2e, tmp_path, monkeypatch):
    dom = tmp_path / "dom"
    (dom / "start").mkdir(parents=True)
    (dom / "start" / "skrot.lnk").write_text("a", encoding="utf-8")
    (dom / "cache").mkdir()
    (dom / ".profile").write_text("export A=1\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(dom))
    przed = _migawka(e2e, monkeypatch, dom)
    assert przed["wpisy"]["start:skrot.lnk"].startswith("f:1:")
    assert przed["wpisy"]["plik-startowy:.profile"]
    # ślady po „instalacji i odinstalowaniu”: korzeń został, plik w cache, zmieniony skrót, blok w .profile,
    # pusty ~/.local/bin (wyjątek: pusty katalog XDG), resztka w ~/.local/share
    (dom / "jarvo").mkdir()
    (dom / "cache" / "nowy.whl").write_bytes(b"x")
    (dom / "start" / "skrot.lnk").write_text("b", encoding="utf-8")
    (dom / ".profile").write_text("export A=1\n# >>> jarvo >>>\n", encoding="utf-8")
    (dom / ".local" / "bin").mkdir(parents=True)
    (dom / ".local" / "share" / "jarvo").mkdir(parents=True)
    (dom / ".local" / "share" / "jarvo" / "x").write_text("x", encoding="utf-8")
    po = _migawka(e2e, monkeypatch, dom)
    r = e2e.roznica(przed, po)
    klucze = {z["klucz"]: z for z in r["zmiany"]}
    nie = {z["klucz"] for z in r["zmiany"] if not z["wyjasnienie"]}
    assert {"dom:jarvo", f"jarvo-korzen:{dom / 'jarvo'}", f"odcisk:{dom / 'cache'}", "start:skrot.lnk",
            "plik-startowy:.profile", "local:share/jarvo", "local:share/jarvo/x"} <= nie
    assert klucze["local:bin"]["wyjasnienie"] and klucze["local:bin"]["po"] == "d0", "pusty ~/.local/bin to wyjątek"
    assert klucze["dom:.local"]["rodzaj"] == "dodany" and klucze["dom:.local"]["po"] == "d"
    assert "dom:.local" in nie, "~/.local z resztką w środku nie jest pusty"
    assert r["niewyjasnione"] == len(nie)
    wyjatki = [e2e.parsuj_wyjatek(w) for w in ("*jarvo*|test", "start:*=zmieniony|test", "odcisk:*|test",
                                               "plik-startowy:*|test", "dom:.local|test", "dom:cache=zmieniony|test",
                                               "local:share|test")]
    assert wyjatki[1] == ("start:*", "zmieniony", "test") and wyjatki[2] == ("odcisk:*", "dowolnie", "test")
    r2 = e2e.roznica(przed, po, wyjatki)
    assert r2["niewyjasnione"] == 0, [z for z in r2["zmiany"] if not z["wyjasnienie"]]
    assert e2e.roznica(przed, przed)["zmiany"] == []
    assert e2e.parsuj_wyjatek("zmienna:A=B|x") == ("zmienna:A=B", "dowolnie", "x"), "„=” w kluczu to nie „kiedy”"
    with pytest.raises(Exception):
        e2e.parsuj_wyjatek("bez-powodu")


def test_wyjatki_szumu_systemu(e2e):
    przed = {"wpisy": {"localappdata:Temp": "d", "dom:NTUSER.DAT": "f"}}
    po = {"wpisy": {"localappdata:Temp": "d0", "dom:ntuser.dat.LOG1": "f", "library:LaunchAgents": "d0",
                    "dom:.cache": "d", "localappdata:Jarvo": "d"}}
    r = {z["klucz"]: z["wyjasnienie"] for z in e2e.roznica(przed, po)["zmiany"]}
    assert r["localappdata:Temp"] and r["dom:ntuser.dat.LOG1"] and r["dom:NTUSER.DAT"]
    assert r["library:LaunchAgents"], "pusty katalog LaunchAgentów"
    assert r["dom:.cache"] is None, "~/.cache z treścią nie jest pustym katalogiem XDG"
    assert r["localappdata:Jarvo"] is None
    # Firefox z obrazu runnera (W64: katalogi Mozilli doszły w trakcie przebiegu), ale nie inne programy w AppData
    r = {z["klucz"]: z["wyjasnienie"] for z in e2e.roznica({"wpisy": {}}, {"wpisy": {
        "appdata:Mozilla": "d", "localappdata:Mozilla": "d0", "appdata:Jarvo": "d"}})["zmiany"]}
    assert r["appdata:Mozilla"] and r["localappdata:Mozilla"] and r["appdata:Jarvo"] is None


def test_skan_usuwa_plik_z_sekretem(e2e, tmp_path, monkeypatch):
    for n in e2e.ZMIENNE_SEKRETOW:
        monkeypatch.delenv(n, raising=False)
    art = tmp_path / "art"
    (art / "logi").mkdir(parents=True)
    znany = hashlib.sha256(b"seed").hexdigest()             # jak API_SERVER_KEY = secrets.token_hex(32)
    z_otoczenia = "Ab3" * 10
    monkeypatch.setenv("JARVO_TEST_OPENROUTER_KEY", z_otoczenia)
    monkeypatch.setenv("JARVO_E2E_SEKRETY", str(tmp_path / "sekrety.json"))
    (tmp_path / "sekrety.json").write_text(json.dumps({"sha256": [hashlib.sha256(znany.encode()).hexdigest()]}),
                                           encoding="utf-8")
    wyjscie = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(wyjscie))
    (art / "czysty.log").write_text("sha256 " + "ab" * 32 + " ok\nmax_tokens: 1234567890123456\n", encoding="utf-8")
    (art / "logi" / "openrouter.log").write_text("klucz: " + "sk-or-v1-" + "0123456789abcdef" * 4 + "\n",
                                                 encoding="utf-8")
    (art / "logi" / "github.log").write_text("x " + "gh" + "p_" + "A1b2C3d4" * 5 + "\n", encoding="utf-16")
    (art / "logi" / "znany.log").write_text(f"wartość: {znany}\n", encoding="utf-8")
    (art / "logi" / "otoczenie.log").write_text(f"x={z_otoczenia}\n", encoding="utf-8")
    (art / "zrzut.png").write_bytes(b"\x89PNG\x00\x00" + ("sk-or-v1-" + "ab" * 32).encode())
    assert e2e.main(["skan", str(art)]) == 1
    raport = json.loads((art / "skan.json").read_text(encoding="utf-8"))
    assert sorted(raport["usuniete"]) == ["logi/github.log", "logi/openrouter.log", "logi/otoczenie.log",
                                          "logi/znany.log"]
    assert (art / "czysty.log").is_file() and (art / "zrzut.png").is_file(), "czysty tekst i plik binarny zostają"
    opis = (art / "logi" / "znany.log.usuniety.txt").read_text(encoding="utf-8")
    assert "znany sekret" in opis and znany not in opis and znany not in json.dumps(raport)
    assert z_otoczenia not in json.dumps(raport)
    assert wyjscie.read_text(encoding="utf-8") == "gotowe=tak\n"
    assert e2e.main(["skan", str(art)]) == 0, "drugi skan oczyszczonego katalogu: czysto"


def test_zbierz_logi_maskuje_znane_sekrety(e2e, tmp_path, monkeypatch):
    for n in e2e.ZMIENNE_SEKRETOW:
        monkeypatch.delenv(n, raising=False)
    root = tmp_path / "Jarvo"
    monkeypatch.setenv("JARVO_ROOT", str(root))
    monkeypatch.delenv("JARVO_E2E_SEKRETY", raising=False)
    klucz = hashlib.sha256(b"api").hexdigest()
    (root / "dane" / "profiles" / "jarvo").mkdir(parents=True)
    (root / "dane" / ".env").write_text(f"API_SERVER_KEY={klucz}\nAPI_SERVER_PORT=8642\n", encoding="utf-8")
    (root / "dane" / "profiles" / "jarvo" / ".env").write_text("TELEGRAM_BOT_TOKEN=\n", encoding="utf-8")
    (root / "logi").mkdir()
    (root / "logi" / "brama.log").write_text(f"start\nklucz {klucz} w logu\n", encoding="utf-8")
    (root / "logi" / "panel.log").write_text("czysto\n", encoding="utf-8")
    (root / "stan").mkdir()
    (root / "stan" / "nadzorca.json").write_text("{}", encoding="utf-8")
    art = tmp_path / "art"
    assert e2e.main(["zbierz-logi", "--artefakty", str(art)]) == 1, "sekret w logu usługi to błąd"
    brama = (art / "logi" / "jarvo" / "brama.log").read_text(encoding="utf-8")
    assert klucz not in brama and "<ukryty:API_SERVER_KEY>" in brama
    assert (art / "logi" / "jarvo" / "panel.log").is_file() and (art / "logi" / "stan" / "nadzorca.json").is_file()
    skroty = json.loads((tmp_path / "art-sekrety.json").read_text(encoding="utf-8"))["sha256"]
    assert skroty == [hashlib.sha256(klucz.encode()).hexdigest()], "tylko skróty, obok katalogu artefaktów"
    assert not any(klucz in p.read_text(encoding="utf-8", errors="replace") for p in art.rglob("*") if p.is_file())
    punkty = json.loads((art / "raport.json").read_text(encoding="utf-8"))["punkty"]
    punkt = next(p for p in punkty if p["id"] == "logi")
    assert punkt["ok"] is False and "jarvo/brama.log ×1" in punkt["opis"]


def test_podsumowanie_do_github(e2e, tmp_path, monkeypatch):
    art = tmp_path / "art"
    rap = e2e.Raport(e2e.katalog_artefaktow(str(art)))
    rap.punkt("a", "punkt dobry", True, "wszystko | w porządku")
    rap.punkt("b", "punkt zły", False, "coś\nnie tak")
    rap.punkt("c", "punkt pominięty", None, "brak sekretu")
    (art / "roznica.json").write_text(json.dumps({"zmiany": [{"klucz": "dom:x", "rodzaj": "dodany",
                                                               "wyjasnienie": None}],
                                                  "niewyjasnione": 1, "wyjasnione": 0}), encoding="utf-8")
    cel = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(cel))
    assert e2e.main(["podsumowanie", "--artefakty", str(art)]) == 0
    tekst = cel.read_text(encoding="utf-8")
    assert "| ok | punkt dobry | wszystko \\| w porządku |" in tekst
    assert "| **BŁĄD** | punkt zły | coś nie tak |" in tekst and "| pominięte | punkt pominięty |" in tekst
    assert "`dom:x` **bez wyjaśnienia**" in tekst


def test_bez_sekretow_maskuje(e2e, monkeypatch):
    for n in e2e.ZMIENNE_SEKRETOW:
        monkeypatch.delenv(n, raising=False)
    klucz = "sk-or-v1-" + "fedcba9876543210" * 4
    tekst = f"Authorization: Bearer {'Q1w2E3r4' * 4}\nAPI_SERVER_KEY={'a1' * 32}\nok {klucz} max_tokens: 4096\n"
    wynik = e2e.bez_sekretow(tekst, ["tajne-haslo-123"]) + e2e.bez_sekretow("tajne-haslo-123", ["tajne-haslo-123"])
    assert klucz not in wynik and "Q1w2E3r4" not in wynik and "a1a1" not in wynik and "tajne" not in wynik
    assert "API_SERVER_KEY=<ukryty>" in wynik and "Bearer <ukryty>" in wynik and "max_tokens: 4096" in wynik


def test_atrapa_dla_pracownika_kanbana(e2e):
    dalej = []

    def zwykla(w, m):
        dalej.append(w)
        return {"tekst": "echo"}

    pracownik = [{"role": "system", "content": "x"}, {"role": "user", "content": "work kanban task t_ab12"}]
    wynik = e2e.odpowiedz_e2e(pracownik, "atrapa", zwykla)
    assert wynik["narzedzie"][0] == "kanban_complete" and "t_ab12" in wynik["narzedzie"][1]["summary"]
    po_narzedziu = [{"role": "user", "content": "work kanban task t_ab12"}, {"role": "tool", "content": "{}"}]
    assert e2e.odpowiedz_e2e(po_narzedziu, "atrapa", zwykla) == {"tekst": "echo"}, "po wyniku: zwykła atrapa"
    z_dopiskiem = [{"role": "user", "content": [{"type": "text", "text": "[czas: 12:00] work kanban task t_cd34."}]}]
    assert e2e.odpowiedz_e2e(z_dopiskiem, "atrapa", zwykla)["narzedzie"][1]["summary"].count("t_cd34") == 1
    zwykle = [{"role": "user", "content": "Cześć, tu test e2e e2e-1a2b3c4d"}]
    assert e2e.odpowiedz_e2e(zwykle, "atrapa", zwykla) == {"tekst": "echo"}, "rozmowa bez prośby pracownika"
    assert len(dalej) == 2


def test_aktywni_agenci_z_fleet_yaml(e2e):
    import fleetlib
    assert e2e.aktywni_agenci(REPO / "fleet.yaml") == [a.name for a in fleetlib.load_fleet().active()]
    assert e2e.aktywni_agenci(REPO / "brak.yaml") == []


@pytest.mark.posix_only
def test_polecenie_jarvo_posix(e2e, tmp_path, monkeypatch):
    dom = tmp_path / "dom"
    monkeypatch.setenv("HOME", str(dom))
    for zmienna in ("JARVO_ROOT", "XDG_DATA_HOME"):
        monkeypatch.delenv(zmienna, raising=False)
    u = e2e.sciezki.uklad({"HOME": str(dom)})
    assert e2e.polecenie_jarvo(u) is None
    cel = dom / ".local" / "bin" / "jarvo"
    cel.parent.mkdir(parents=True)
    cel.write_text("#!/bin/sh\n# obce polecenie\n", encoding="utf-8")
    assert e2e.polecenie_jarvo(u) is None, "cudze ~/.local/bin/jarvo to nie nasza instalacja"
    cel.write_text(f"#!/bin/sh\n# {e2e.instalator.ZNACZNIK}\nexec python start.py \"$@\"\n", encoding="utf-8")
    assert e2e.polecenie_jarvo(u) == cel
    inny = e2e.sciezki.uklad({"HOME": str(dom), "JARVO_ROOT": str(tmp_path / "inny")})
    assert e2e.polecenie_jarvo(inny) is None, "polecenie domyślnego korzenia nie służy instalacji spod JARVO_ROOT"
    (tmp_path / "inny" / "bin").mkdir(parents=True)
    (tmp_path / "inny" / "bin" / "jarvo").write_text("#!/bin/sh\n", encoding="utf-8")
    assert e2e.polecenie_jarvo(inny) == tmp_path / "inny" / "bin" / "jarvo"


@pytest.mark.windows_only
def test_polecenie_jarvo_windows(e2e, tmp_path):
    u = e2e.sciezki.uklad({"JARVO_ROOT": str(tmp_path / "Jarvo")})
    assert e2e.polecenie_jarvo(u) is None
    (tmp_path / "Jarvo" / "bin").mkdir(parents=True)
    (tmp_path / "Jarvo" / "bin" / "jarvo.cmd").write_text("@echo off\r\n", encoding="ascii")
    assert e2e.polecenie_jarvo(u) == tmp_path / "Jarvo" / "bin" / "jarvo.cmd"


def test_migawka_prawdziwego_systemu_tylko_czyta(e2e, tmp_path, monkeypatch):
    """Migawka na tym komputerze (tylko odczyt: rejestr, Harmonogram, launchctl, systemctl, katalogi domowe) bez
    liczenia wielkich cache (odcisk na atrapie): klucze bez wartości sekretów, PATH użytkownika na Windows wprost."""
    monkeypatch.setattr(e2e, "_odcisk", lambda katalog, limit=50_000: "o:test")
    m = e2e.migawka(u=e2e.sciezki.Uklad(root=tmp_path / "brak", program=tmp_path / "brak" / "p", dane=tmp_path / "d",
                                        stan=tmp_path / "s", logi=tmp_path / "l", cache=tmp_path / "c",
                                        build=tmp_path / "b"))
    assert m["wpisy"] and m["system"] in e2e.sciezki.PLATFORMY
    assert not any(k.startswith("jarvo-") for k in m["wpisy"])
    for klucz, wartosc in m["wpisy"].items():
        if klucz.startswith("zmienna:") and e2e.SEKRET_NAZWA.search(klucz.split(":", 1)[1]):
            assert wartosc.endswith(":<sekret>"), klucz
        if WINDOWS and klucz.startswith(("zmienna:", "run:", "runonce:")) and klucz.lower() != "zmienna:path":
            assert re.fullmatch(r"\d+:(?:[0-9a-f]{16}|<sekret>)", wartosc), f"{klucz}: wartość tylko jako skrót"
