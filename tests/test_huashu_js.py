"""huashu_pl.js: polska nakładka na silnik huashu-art-motion (kroje z polskimi znakami, liczby, napisy silnika,
tekst kanwy dla pomiaru, łatka postaci autora). Czyste funkcje liczone w node, bez przeglądarki."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from conftest import REPO

MODUL = REPO / "profiles/jarvo-wideo/scripts/huashu_pl.js"

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="brak node")


def node(kod: str) -> dict:
    skrypt = f"""const vm = require('vm'), fs = require('fs');
const ctx = {{}}; ctx.window = ctx; vm.createContext(ctx);
vm.runInContext(fs.readFileSync({json.dumps(str(MODUL))}, 'utf8'), ctx);
const H = ctx.HUASHU_PL;
{kod}"""
    wynik = subprocess.run(["node", "-e", skrypt], capture_output=True, text=True)
    assert wynik.returncode == 0, wynik.stderr
    return json.loads(wynik.stdout)


def test_liczby_po_polsku():
    w = node("console.log(JSON.stringify([H.fmt(1234.5, 1), H.fmt(12345678), H.fmt(-3.25, 1), H.fmt(-0.004, 2),"
             " H.fmt(2024, 0, false), H.fmt(99999.99, 2), H.fmt(130.5, 1)]));")
    assert w == ["1234,5", "12 345 678", "−3,3", "0,00", "2024", "99 999,99", "130,5"]


def test_napisy_silnika_po_polsku():
    w = node("console.log(JSON.stringify([H.pl('来源：示意数据'), H.pl('示意数据'), H.pl('收入　纵轴未从 0 开始'),"
             " H.pl('AI助手'), H.pl('？'), H.pl('Zażółć gęślą jaźń'), H.pl(42)]));")
    assert w[:2] == ["Źródło: dane przykładowe", "dane przykładowe"]
    assert w[2].endswith(" oś Y nie zaczyna się od 0") and w[3:6] == ["Asystent AI", "?", "Zażółć gęślą jaźń"]
    assert w[6] == 42


def test_kroje_bez_polskich_znakow_podmienione():
    w = node("""console.log(JSON.stringify(H.fonty([
  {family: 'PuHui-Bold', url: 'lib/fonts/NotoSansSC-700.woff'}, {family: 'Anton-400', url: 'lib/fonts/Anton-400.woff'},
  {family: 'NotoSerifSC', url: 'lib/fonts/NotoSerifSC-sub.woff', desc: {weight: '200 900'}},
  {family: 'LXGWWenKai-500', url: 'lib/fonts/LXGWWenKai-500.woff'}, {family: 'X', url: '/inny/x.woff'}], '/_lib/huashu/')));""")
    assert w[0] == {"family": "PuHui-Bold", "url": "/_lib/huashu/lib/fonts/Inter-var.woff", "desc": {"weight": "700"}, "pl": True}
    assert w[1] == {"family": "Anton-400", "url": "/_lib/huashu/lib/fonts/Anton-400.woff"}       # ma ą–ż: tylko adres
    assert [x["url"].rsplit("/", 1)[1] for x in w[2:4]] == ["EBGaramond-400.woff", "EBGaramond-600.woff"]
    assert w[4]["url"].endswith("Caveat-600.woff") and w[5]["url"] == "/inny/x.woff"
    # każdy krój zastępczy jest w paczce silnika i każda rodzina bez polskich znaków ma zastępstwo
    pod = node("console.log(JSON.stringify(H.PODMIANY));")
    assert set(pod) == {"PuHui-Medium", "PuHui-Bold", "PuHui-Heavy", "PuHui-Black", "NotoSansSC", "NotoSerifSC",
                        "LXGWWenKai-500", "GochiHand-400", "LilitaOne-400", "Rye-400", "UnifrakturMaguntia-400",
                        "NotoSerifJP-600"}


def test_tekst_kanwy_sklejony_w_linie():
    w = node("""const z = (tekst, x0, x1, y = 50, o = {}) => ({tekst, x0, x1, y0: y, y1: y + 30, by: y + 30, font: '40px "Inter"',
  rodzina: 'Inter', waga: 400, kolor: '#ffffff', krycie: 1, rozmiar: 40, ...o});
console.log(JSON.stringify(H.scal([z('1', 100, 120), z('2', 122, 142), z('zł', 160, 190),
  z('Tytuł', 100, 300, 200), z('Tytuł', 100, 300, 200), z('Inny', 100, 300, 400, {kolor: '#000000', krycie: 0.5}),
  z('daleko', 900, 1000)])));""")
    assert [x["tekst"] for x in w] == ["12 zł", "Tytuł", "Inny", "daleko"]   # cyfry po znaku, kontur nie dubluje
    assert w[0] == {"tekst": "12 zł", "x": 100, "y": 50, "w": 90, "h": 30, "kolor": "#ffffff", "rozmiar": 40,
                    "krycie": 1, "font": "Inter", "waga": 400, "klucz": '40px "Inter"|#ffffff'}


def test_id_napisu_stale_miedzy_probkami():
    """Licznik (8,9 → 130,5), tekst pisany po literze i napis w ruchu zostają jednym napisem dla czasu czytania."""
    w = node("""const P = [], z = (tekst, klucz = 'f|#fff') => ({tekst, klucz});
const kolejne = [[z('8,9')], [z('16,4'), z('P')], [z('130,5'), z('Przy')], [z('130,5'), z('Przychody'), z('Przychody')],
  [z('Koszty'), z('130,5'), z('130,5', 'g|#000')]];
console.log(JSON.stringify({ id: kolejne.map((f) => H.nadajId(f, P).map((x) => x.tekst + ':' + x.id)),
  rodziny: [H.rodzinaZ('bold 58px PuHui-Bold'), H.rodzinaZ('96px "Cinzel-700", serif'), H.rodzinaZ('600 34px RobotoCondensed')],
  wagi: [H.wagaZ('bold 58px X'), H.wagaZ('600 34px X'), H.wagaZ('26px X')], klucz: 'klucz' in H.nadajId([z('a')], [])[0] }));""")
    assert w["id"] == [["8,9:k1"], ["16,4:k1", "P:k2"], ["130,5:k1", "Przy:k2"], ["130,5:k1", "Przychody:k2", "Przychody:k3"],
                       ["Koszty:k4", "130,5:k1", "130,5:k5"]]
    assert w["rodziny"] == ["PuHui-Bold", "Cinzel-700", "RobotoCondensed"] and w["wagi"] == [700, 600, 400]
    assert w["klucz"] is False


def test_latka_postaci_autora():
    kod = ("c.fillStyle = '#FFFFFF'; c.beginPath(); c.ellipse(0, 300, 330, 200, 0, Math.PI, 0); c.fill();\n"
           "c.fillStyle = '#FFE2CC'; c.beginPath(); c.roundRect(-70, 120, 140, 110, 30); c.fill();\n"
           "c.fillStyle = '#1B1B1F'; c.beginPath(); c.ellipse(0, 40, 190, 175, 0, 0, 7); c.fill();\n"
           "c.fillStyle = '#FFFFFF'; c.beginPath(); c.moveTo(-180, -20); c.bezierCurveTo(-180, -290, 180, -290, 180, -20);"
           " c.closePath(); c.fill(); c.stroke();\n"
           "c.beginPath(); c.ellipse(0, -12, 280, 64, 0, 0, 7); c.fill(); c.stroke();\n")
    w = node(f"""const out = H.latka('y4_storytime', {json.dumps(kod)});
let blad = ''; try {{ H.latka('y4_storytime', 'inny kod'); }} catch (e) {{ blad = e.message; }}
console.log(JSON.stringify({{out, blad, inna: H.latka('y2_vox', 'bez zmian')}}));""")
    assert "bezierCurveTo(-180, -290" not in w["out"] and "ellipse(0, -12, 280" not in w["out"]   # bez kapelusza
    assert w["out"].count("window.HUASHU_PL.postac()") == 3                    # koszulka, skóra, włosy z marki
    assert "nie pasuje do kodu silnika" in w["blad"] and w["inna"] == "bez zmian"


def test_tokeny_wzoru_3b1b_po_polsku():
    """Słowo z ą–ż prostym krojem w całości, spójnik w/z/i przed słowem nie jest zmienną, skrót zostaje słowem;
    zmienne we wzorze dalej kursywą."""
    w = node("""const t = s => H.tokeny(s).filter(([x]) => x !== ' ');
console.log(JSON.stringify([t('Słowa w zdaniu i AI'), t('a² + b² = c²'), t('W domu, z kotem')]));""")
    assert w[0] == [["Słowa", False], ["w", False], ["zdaniu", False], ["i", False], ["AI", False]]
    assert [x for x, it in w[1] if it] == ["a", "b", "c"]
    assert w[2] == [["W", False], ["domu", False], [",", False], ["z", False], ["kotem", False]]
    kod = ("const toks = text => (String(text).match(/[A-Za-z]{2,}|./gu) || []).flatMap(s => s.length > 1 && "
           "!/[a-z]/.test(s) ? [...s] : [s])   // 全大写的一串（QK）是几个变量，拆开\n"
           "  .map(s => ({ s, zh: isZh(s), it: /^[a-zA-Z]$/.test(s), gap: 0 }));\n")
    out = node(f"console.log(JSON.stringify(H.latka('t1_3b1b', {json.dumps(kod)})));")
    assert out.strip() == "const toks = text => window.HUASHU_PL.tokeny(String(text)).map(([s, it]) => ({ s, zh: isZh(s), it, gap: 0 }));"
