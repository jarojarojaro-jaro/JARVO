"""ruchy.py: losowanie ruchów z biblioteki cinetic (MIT) i tokeny.js (krzywe, sprężyny, puls, OKLab w sekundach)."""

from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys

import pytest
import yaml

from conftest import REPO

sys.path.insert(0, str(REPO / "profiles/jarvo-wideo/scripts"))
import ruchy as rc  # noqa: E402

SKILL = REPO / "profiles/jarvo-wideo/skills/wideo/losowanie-ruchow"
TOKENY = REPO / "profiles/jarvo-wideo/scripts/tokeny.js"
T = rc.wczytaj()


def test_biblioteka_cala_z_licencja():
    assert len(T) == 273 and rc.sprawdz(T) == []
    assert {t["category"] for t in T} == set(rc.KAT_PL)
    lic = (SKILL / "assets/cinetic/LICENSE").read_text(encoding="utf-8")
    assert lic.startswith("MIT License") and "Leonxlnx" in lic
    zr = yaml.safe_load((REPO / "vendor/zrodla.yaml").read_text(encoding="utf-8"))["zrodla"]["cinetic"]
    assert zr["status"] == "uzywane" and (REPO / zr["kopia"] / "techniques.json").is_file()


def test_sprawdz_lapie_zepsute_wpisy():
    zly = dict(T[0], id=T[1]["id"], category="nie-ma", energy="szybka", role="gwiazda", formats=["tv"])
    bledy = rc.sprawdz([T[1], zly, dict(T[2], ban_safe=False, ban_safe_variant="")])
    tekst = "\n".join(bledy)
    for frag in ("powtórzone id", "nieznana kategoria", "nieznana energia", "nieznana rola", "formats", "ban_safe false"):
        assert frag in tekst, frag


def test_wagi_rola_dowod_energia():
    t = {"role": "workhorse", "evidence": 4, "energy": "medium"}
    assert rc.waga(t, "medium") == 6.0                               # 3 × (1 + 4/4)
    assert rc.waga(dict(t, evidence=40), "medium") == 9.0            # dowód najwyżej ×3
    assert rc.waga(dict(t, energy="any"), "medium") == pytest.approx(4.2)
    assert rc.waga(dict(t, energy="high"), "calm") == 0.0            # spokojny film nigdy nie bierze wysokiej energii
    assert rc.waga(dict(t, role="signature", energy="calm"), "medium") == 0.5


def test_rozmiar_planu_i_sloty():
    assert rc.ile_ruchow("launch", 30, "medium") == 12 and rc.ile_ruchow("launch", 30, "calm") == 9
    assert rc.ile_ruchow("sting", 2, "medium") == 4                  # minimum rodzaju
    assert rc.ile_ruchow("loop", 600, "medium") == len(rc.KOLEJNOSC["loop"])
    assert rc.sloty("sting", 6, "medium") == {"logo_and_end_card": 1, "opening_hook": 1, "typography_motion": 1,
                                              "micro_interaction": 1}


@pytest.mark.parametrize("rodzaj", list(rc.RODZAJE.values()))
@pytest.mark.parametrize("energia", ["calm", "medium", "high"])
def test_plan_zgodny_z_regulami(rodzaj, energia):
    for ziarno in range(8):
        plan = rc.losuj(T, rodzaj, energia, ziarno=ziarno)
        r = plan["ruchy"]
        assert len(r) == rc.ile_ruchow(rodzaj, rc.SEKUNDY[rodzaj], energia)
        assert len({t["id"] for t in r}) == len(r)
        assert all(rc.pasuje(t, rodzaj) for t in r)
        assert sum(t["role"] == "signature" for t in r) <= (2 if len(r) >= 10 else 1)
        if energia == "calm":
            assert not any(t["energy"] == "high" for t in r)


def test_ziarno_powtarza_plan_a_bez_i_unikaj_wykluczaja():
    a = rc.losuj(T, "launch", "medium", ziarno=41)
    b = rc.losuj(T, "launch", "medium", ziarno=41)
    assert [t["id"] for t in a["ruchy"]] == [t["id"] for t in b["ruchy"]]
    bez = {t["id"] for t in a["ruchy"]}
    c = rc.losuj(T, "launch", "medium", ziarno=41, bez=bez)
    assert not bez & {t["id"] for t in c["ruchy"]}


def test_kategoria_i_wyczerpanie():
    p = rc.losuj(T, "launch", "medium", kategoria="transition", ile=3, ziarno=1)
    assert len(p["ruchy"]) == 3 and {t["category"] for t in p["ruchy"]} == {"transition"}
    wszystkie = {t["id"] for t in T if t["category"] == "opening_hook"}
    with pytest.raises(rc.Blad, match="nic nie zostało") as e:
        rc.losuj(T, "launch", "medium", kategoria="opening_hook", bez=wszystkie)
    assert e.value.kod == 1


def test_losowanie_rozklada_sie_po_bibliotece():
    widziane = set()
    for z in range(200):
        widziane |= {t["id"] for t in rc.losuj(T, "launch", "medium", ziarno=z)["ruchy"]}
    assert len(widziane) > 120                                        # nie te same kilka ruchów


def test_cli_karta_lista_json_i_bledy(tmp_path, capsys):
    out = tmp_path / "ruchy.json"
    assert rc.main(["losuj", "--rodzaj", "pion", "--energia", "spokojna", "--ziarno", "7", "--json", str(out)]) == 0
    md = capsys.readouterr().out
    assert md.startswith("<!-- ruchy.py losuj --ziarno 7 --rodzaj pion --energia spokojna --sekundy 15 -->")
    assert "**Przepis:**" in md and "f(n) = n/60" in md
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan["ziarno"] == 7 and plan["rodzaj"] == "pion" and plan["ruchy"][0]["kategoria"] in rc.KATEGORIE
    assert rc.main(["losuj", "--rodzaj", "pion", "--energia", "spokojna", "--ziarno", "7", "--unikaj", str(out),
                    "--format", "json"]) == 0
    drugi = json.loads(capsys.readouterr().out)
    assert not {r["id"] for r in plan["ruchy"]} & {r["id"] for r in drugi["ruchy"]}
    assert rc.main(["karta", "tr-shape-match-cut"]) == 0 and "### Shape match cut" in capsys.readouterr().out
    assert rc.main(["lista", "--kategoria", "kamera", "--rodzaj", "petla"]) == 0
    assert all(" kamera " in ln for ln in capsys.readouterr().out.splitlines()[:-2] if ln)
    assert rc.main(["losuj", "--rodzaj", "kino"]) == 2 and "nieznany rodzaj 'kino'" in capsys.readouterr().err
    assert rc.main(["karta", "nie-ma"]) == 1


def test_wariant_bez_zakazu_pokazany_obok_pelnego_przepisu():
    t = next(t for t in T if t.get("ban_safe") is False)
    k = rc.karta(t)
    assert t["recipe"] in k and t["ban_safe_variant"] in k and "**Wariant bez " in k


def test_skill_przypiety_w_rodzajach_i_module_serwowanym():
    import narzedzia as nz
    assert "tokeny.js" in nz.JARVO_JS_PLIKI
    s = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    meta = yaml.safe_load(s.split("---")[1])
    assert meta["name"] == "losowanie-ruchow" and len(meta["description"]) <= 60
    assert "ruchy.py losuj" in (REPO / "profiles/jarvo-wideo/skills/wideo/rodzaje-filmu/SKILL.md").read_text(encoding="utf-8")
    przepisy = (SKILL / "references/przepisy.md").read_text(encoding="utf-8")
    eksport = set(__import__("re").findall(r"export (?:const|function) (\w+)", TOKENY.read_text(encoding="utf-8")))
    for nazwa in ("E", "SPR", "f", "prog", "tw", "lmix", "spr", "hitPulse", "mixColor", "inertia", "blurIn", "stagger"):
        assert nazwa in eksport and f"`{nazwa}" in przepisy, nazwa


# ------------------------------------------------------------------ tokeny.js w node

def node(kod: str):
    skrypt = f"import * as K from {json.dumps(str(TOKENY))};\n{kod}"
    w = subprocess.run(["node", "--input-type=module", "-e", skrypt], capture_output=True, text=True)
    assert w.returncode == 0, w.stderr
    return json.loads(w.stdout)


@pytest.mark.skipif(not shutil.which("node"), reason="brak node")
def test_tokeny_liczby_jak_w_bibliotece():
    w = node("""
const sp = (cfg) => { let mx = 0, at = 0; for (let i = 0; i <= 240; i++) { const v = K.sprezyna(i / 60, cfg); if (v > mx) mx = v; if (Math.abs(1 - v) < 0.03 && !at) at = i; } return { mx, at }; };
console.log(JSON.stringify({
  out: [K.E.out(0.25), K.E.out(0.5)], smooth: K.E.smooth(0.5), expo: K.E.expo(0.12),
  prog: K.prog(0.15, 0, 0.3, K.E.linear), tw: K.tw(1, 0, 2, 10, 20, K.E.linear), lmix: K.lmix(1, 4, 0.5),
  snap: sp(K.SPR.snap), calm: sp(K.SPR.calm), spr0: K.spr(0.5, 1, K.SPR.firm),
  puls: [K.hitPulse(0), K.hitPulse(K.f(2)), K.hitPulse(K.f(2) + K.f(5)), K.hitPulse(K.f(33))],
  sq: K.squash(K.f(1)), mix: K.mixColor('#08965A', '#F5F6F7', 0.5), mixKoniec: K.mixColor('#000', 'rgb(255, 255, 255)', 1),
  in0: K.inertia(0, 0, 600), in1: K.inertia(0.1, 0, 600), rand: [K.rand(1), K.rand('a'), K.rand(1)],
  blur: [K.blurIn(0, 10), K.blurIn(0.6, 10), K.blurOut(0.3, 10)], st: K.stagger(2, 3, K.f(24)),
}));
""")
    assert w["out"][0] == pytest.approx(0.83, abs=0.01) and w["out"][1] == pytest.approx(0.97, abs=0.01)
    assert w["smooth"] == pytest.approx(0.5, abs=1e-3) and w["expo"] == pytest.approx(0.5, abs=0.02)
    assert w["prog"] == pytest.approx(0.5) and w["tw"] == pytest.approx(15) and w["lmix"] == pytest.approx(2)
    assert w["snap"]["mx"] == pytest.approx(1.06, abs=0.01)                 # 6% przestrzelenia (tabela biblioteki)
    assert w["calm"]["mx"] <= 1.0 and 36 <= w["calm"]["at"] <= 44         # tekst: 0% przestrzelenia, ~97% w ok. 41 kl.
    assert w["spr0"] == 0
    assert w["puls"][0] == 0 and w["puls"][1] == pytest.approx(1) and w["puls"][2] == pytest.approx(0.3679, abs=1e-3)
    assert w["puls"][3] == 0 and w["sq"]["along"] < 1 < w["sq"]["across"]
    assert w["mix"] == "rgb(147, 198, 167)" and w["mixKoniec"] == "rgb(255, 255, 255)"   # OKLab, nie szare sRGB
    assert w["in0"]["v"] == 600 and 0 < w["in1"]["x"] < w["in1"]["total"]
    assert w["rand"][0] == w["rand"][2] and 0 <= w["rand"][1] < 1
    assert w["blur"] == [10, 0, 0] and w["st"] == pytest.approx(0.4)


def test_losowanie_nie_zalezy_od_globalnego_random():
    random.seed(1)
    a = [t["id"] for t in rc.losuj(T, "feature", "medium", ziarno=5)["ruchy"]]
    random.seed(2)
    assert a == [t["id"] for t in rc.losuj(T, "feature", "medium", ziarno=5)["ruchy"]]


def test_katalog_tanich_chwytow_bez_zakazow_koloru_i_kroju():
    """Katalog dla krytyka (za cinetic taste-and-slop): ID jednoznaczne w 12 grupach, podpięty w kontroli,
    a zakazy kolorów i krojów biblioteki tylko w akapicie „Czego tu nie ma”."""
    import re
    kw = REPO / "profiles/jarvo-wideo/skills/wideo/kontrola-wideo"
    tekst = (kw / "references/tanie-chwyty.md").read_text(encoding="utf-8")
    ids = re.findall(r"^- \*\*([A-L]\d+) ", tekst, flags=re.M)
    assert len(ids) == len(set(ids)) >= 90 and {i[0] for i in ids} == set("ABCDEFGHIJKL")
    for grupa in "ABCDEFGHIJKL":                                          # numeracja w grupie bez dziur
        nr = [int(i[1:]) for i in ids if i[0] == grupa]
        assert nr == list(range(1, len(nr) + 1)), grupa
    poza = tekst.split("**Czego tu nie ma (świadomie):**")
    assert len(poza) == 2
    reszta = poza[0] + poza[1].split("\n\n", 1)[1]
    for zakaz in ("szeryf", "kursyw", "pomarańcz", "fiolet", "neon", "beż", "szkło"):
        assert zakaz not in reszta.lower(), zakaz
    skill = (kw / "SKILL.md").read_text(encoding="utf-8")
    assert "references/tanie-chwyty.md" in skill and "tanie-chwyty.md" in (kw / "references/zakazane.md").read_text(encoding="utf-8")
