"""Aplikacja Jarvo, etapy 3a i 3b (docs/HQ.md „Aplikacja”): testy node czystych modułów (tests/js/hq_front.test.cjs),
jednoznaczne nazwy w pakiecie, teksty PL/EN (te same klucze, użyte klucze istnieją, neutralne szablony z agentem),
kontrast tokenów obu motywów, klasy j-* mają style, brak innerHTML i składnia sklejonego pakietu."""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import load_script

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "hq" / "web" / "src"
CSS = (REPO / "hq" / "web" / "style.css").read_text(encoding="utf-8")
NODE = shutil.which("node")
validate = load_script("scripts/validate.py", "jarvo_test_validate_front")

# pliki aplikacji (wersja 2); stara Baza i edytor zostają w 00–89
APLIKACJA = ("02-sklep.js", "03-trasa.js", "04-i18n.js", "05-skroty.js", "06-tokeny.js", "11-strumien.js", "12-wzmianki.js",
             "13-markdown.js", "14-czas.js", "15-os.js", "16-akcje.js", "20-ui.js", "21-ikony.js", "30-pasek.js", "31-watek.js",
             "32-wiadomosc.js", "33-kompozytor.js", "34-pliki.js", "38-start.js", "61-szuflada.js", "90-app.js", "22-figurka.js",
             "23-robot.js", "36-glos.js", "37-poznajmy.js")


def _tekst(nazwa: str) -> str:
    return (SRC / nazwa).read_text(encoding="utf-8")


@pytest.mark.skipif(not NODE, reason="brak node")
def test_moduly_czyste_w_node():
    r = subprocess.run([NODE, str(REPO / "tests" / "js" / "hq_front.test.cjs")], capture_output=True, text=True,
                       timeout=60, env={**os.environ, "TZ": "Europe/Warsaw"})
    assert r.returncode == 0, r.stderr + r.stdout
    assert r.stdout.startswith("ok ")


def test_nazwy_globalne_jednoznaczne():
    przyklad = "const { useState, useRef: ref } = SDK.hooks;\nfunction A() {}\n  const wewnatrz = 1;\nconst [x, ...y] = z;\n"
    assert validate.nazwy_globalne_js(przyklad) == ["A", "useState", "ref", "x", "y"]
    gdzie = {}
    for f in sorted(SRC.glob("*.js")):
        for n in validate.nazwy_globalne_js(f.read_text(encoding="utf-8")):
            assert n not in gdzie, f"{n}: {f.name} i {gdzie[n]}"
            gdzie[n] = f.name
    for n in ("AppJarvo", "StaraBaza", "sklep", "Trasa", "T", "Skroty", "Motyw", "Strumien", "Czas", "Os", "akcje",
              "Ikona", "Pasek", "Szuflada", "BladApi"):
        assert n in gdzie, n


def test_bez_innerhtml():
    for f in APLIKACJA + ("10-api.js", "89-baza.js"):
        t = _tekst(f)
        assert "innerHTML" not in t and "dangerouslySetInnerHTML" not in t and "outerHTML" not in t, f


def test_teksty_pl_en():
    sl = validate.slownik_i18n(_tekst("04-i18n.js"))
    assert set(sl["pl"]) == set(sl["en"])
    for k, formy in sl["pl"].items():
        assert (formy is None) == (sl["en"][k] is None), k
        if formy is not None:
            assert {"one", "few", "many", "other"} <= formy and {"one", "other"} <= sl["en"][k], k
    klucze = set(sl["pl"])
    uzyte, rodziny = set(), set()
    for f in APLIKACJA + ("10-api.js",):
        t = _tekst(f)
        uzyte |= set(re.findall(r"\bT\(\s*\"([a-z0-9_.-]+)\"", t))
        uzyte |= set(re.findall(r"\bopis:\s*\"([a-z]+\.[a-z0-9_.-]+)\"", t))
        for a, b in re.findall(r"\bT\([^()]*\?\s*\"([a-z0-9_.-]+)\"\s*:\s*\"([a-z0-9_.-]+)\"", t):
            uzyte |= {a, b}
        rodziny |= set(re.findall(r"\bT\(`([a-z_]+\.)\$\{", t))
    assert uzyte and not uzyte - klucze, sorted(uzyte - klucze)
    for r in rodziny:
        assert any(k.startswith(r) for k in klucze), r
    # rodziny z wartości w kodzie: każdy stan przebiegu, stan wiersza, połączenie, grupa listy, motyw
    for st in ("kolejka", "wysylanie", "przyjety", "pracuje", "czeka_na_ture", "czeka_na_zgode", "zatrzymywanie",
               "dopisany", "gotowe", "blad", "zatrzymane", "przerwane", "zgubione", "anulowane", "wlaczony"):
        assert f"przebieg.{st}" in klucze, st
    for k in ("stan.czeka", "stan.pracuje", "stan.blad", "polaczenie.ok", "polaczenie.laczy", "polaczenie.przerwany",
              "grupa.przypiete", "grupa.dzis", "grupa.wczoraj", "grupa.tydzien", "grupa.wczesniej",
              "motyw.system", "motyw.jasny", "motyw.ciemny"):
        assert k in klucze, k
    sekcje = re.findall(r"\{ id: \"([a-z-]+)\", ikona:", _tekst("61-szuflada.js"))
    assert sekcje and all(f"szuflada.{s}" in klucze for s in sekcje), sekcje


def test_szablony_z_agentem_bez_odmiany():
    """Nazwy agenta nie odmieniamy: {agent} nie stoi po przyimku ani przed czasownikiem w czasie przeszłym."""
    pl = re.findall(r'"([a-z0-9_.-]+)":\s*"((?:[^"\\]|\\.)*)"', _tekst("04-i18n.js").split("\n  en: {", 1)[0])
    for k, v in pl:
        if "{agent}" not in v:
            continue
        assert not re.search(r"(?i)\b(do|dla|od|u|z|ze|przez|o|na|w|we|ku|przy)\s+\{agent\}", v), k
        assert not re.search(r"\{agent\}\s+\w+(ł|ła|ło|li|ły)\b", v), k
        # zdanie nie zaczyna się od nazwy agenta z małą literą dalej („{agent} pracuje”): nazwa bywa pusta albo
        # długa, a tekst wygląda wtedy jak urwany; zaczynamy od rzeczy („Pracuje: {agent}”, „Praca · {agent}”)
        assert not re.match(r"\{agent\} [a-ząćęłńóśźż]", v), k


def _bloki_motywow():
    def blok(selektor):
        i = CSS.index(selektor)
        j = CSS.index("{", i)
        return dict(re.findall(r"--j-([\w-]+):\s*([^;]+);", CSS[j:CSS.index("}", j)]))
    return {"ciemny": blok('.jarvo-app, .jarvo-app[data-motyw="ciemny"] {'), "jasny": blok('.jarvo-app[data-motyw="jasny"] {')}


def _rgba(v):
    v = v.strip()
    if v.startswith("#"):
        h = v[1:]
        h = "".join(c * 2 for c in h) if len(h) == 3 else h
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (1.0,)
    cz = [x.strip() for x in re.match(r"rgba?\(([^)]*)\)", v).group(1).split(",")]
    return (float(cz[0]), float(cz[1]), float(cz[2]), float(cz[3]) if len(cz) > 3 else 1.0)


def _nad(fg, bg):
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3)) + (1.0,)


def _kontrast(a, b):
    def lum(c):
        f = [(x / 255) / 12.92 if x / 255 <= 0.03928 else ((x / 255 + 0.055) / 1.055) ** 2.4 for x in c[:3]]
        return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def test_tokeny_oba_motywy_te_same_nazwy():
    b = _bloki_motywow()
    assert set(b["ciemny"]) == set(b["jasny"]) and len(b["jasny"]) >= 30


# (kolor, tło, tło pod półprzezroczystym tłem, próg): tekst ≥ 4.5, kropki stanu, krawędzie i fokus ≥ 3
PARY = [(fg, bg, "tlo-pasek" if bg in ("tlo-hover", "tlo-aktywne") else "tlo", 4.5)
        for fg in ("tekst", "tekst-2", "tekst-3")
        for bg in ("tlo", "tlo-pasek", "tlo-karta", "tlo-2", "tlo-pop", "tlo-hover", "tlo-aktywne")] + [
    ("tekst", "tlo-aktywne", "tlo-pop", 4.5), ("tekst-2", "tlo-aktywne", "tlo-pop", 4.5),
    ("papier-tekst", "papier", "tlo", 4.5), ("akcent-na", "akcent", "tlo", 4.5), ("akcent-na", "akcent-hover", "tlo", 4.5),
    ("mocny-na", "mocny", "tlo", 4.5), ("blad", "tlo", "tlo", 4.5), ("blad", "tlo-karta", "tlo", 4.5),
    ("blad", "tlo-pop", "tlo", 4.5), ("blad", "blad-tlo", "tlo", 4.5), ("uwaga", "tlo", "tlo", 4.5),
    ("uwaga", "uwaga-tlo", "tlo", 4.5), ("tekst", "uwaga-tlo", "tlo", 4.5),
    ("ok", "tlo-pasek", "tlo", 3), ("uwaga", "tlo-pasek", "tlo", 3), ("krawedz", "tlo-karta", "tlo", 3),
    ("krawedz", "tlo-pasek", "tlo", 3)] + [("fokus", bg, "tlo", 3) for bg in ("tlo", "tlo-pasek", "tlo-karta", "tlo-pop")]


@pytest.mark.parametrize("motyw", ["ciemny", "jasny"])
def test_kontrast_tokenow(motyw):
    t = _bloki_motywow()[motyw]

    def kolor(nazwa, pod="tlo"):
        c = _rgba(t[nazwa])
        return _nad(c, kolor(pod)) if c[3] < 1 else c

    zle = []
    for fg, bg, pod, prog in PARY:
        k = _kontrast(kolor(fg), kolor(bg, pod))
        if k < prog:
            zle.append(f"{fg} na {bg}: {k:.2f} < {prog}")
    assert not zle, zle


def test_klasy_aplikacji_maja_style():
    zdefiniowane = set(re.findall(r"\.(j-[a-z0-9-]+)", CSS))
    uzyte = set()
    for f in APLIKACJA + ("89-baza.js",):
        for napis in re.findall(r"\"([^\"\n]*)\"|`([^`]*)`", _tekst(f)):
            for s in napis:
                uzyte |= {k for k in re.findall(r"(?<![\w-])(j-[a-z0-9]+(?:-[a-z0-9]+)*)(?![\w$-])", s)}
    # bez własnego stylu: wariant domyślny przycisku, znak w awatarze, sekcja grupy listy (styl ma nagłówek)
    bez_stylu = {"j-btn-zwykly", "j-awatar-z", "j-grupa"}
    braki = sorted(uzyte - zdefiniowane - bez_stylu)
    assert not braki, braki
    assert {"j-uklad", "j-pasek", "j-glowna", "j-szuflada", "j-arkusz", "j-sr"} <= uzyte


def test_przewijane_pola_bez_kontekstu_nakladania():
    """Menu i podpowiedzi to `position: fixed` w środku rozmowy i listy: mask, filter, transform, contain albo
    will-change na ich przodku przycina je albo chowa pod kompozytorem (menu karty pliku nad kompozytorem znikało)."""
    import re
    for klasa in (".j-watek-s", ".j-watek", ".j-os", ".j-lista", ".j-pasek-l"):
        for m in re.finditer(r"(?m)^([^{}@/]*)\{([^}]*)\}", CSS):
            sel = [s.strip() for s in m.group(1).split(",")]
            if klasa in sel:
                zle = re.findall(r"(?:^|;)\s*(mask(?:-image)?|-webkit-mask-image|filter|transform|contain|will-change)\s*:", m.group(2))
                assert not zle, f"{klasa}: {zle}"


def test_awatar_zawsze_pozycjonowany():
    """Figurka w awatarze to `position: absolute; inset: 0`: awatar ze `static` (np. w regule telefonu) oddaje ją
    najbliższemu przodkowi z pozycją i figurka wypełnia cały dymek wiadomości."""
    import re
    for m in re.finditer(r"([^{}]*)\{([^}]*)\}", CSS):
        if any(s.strip().endswith(".j-awatar") for s in m.group(1).split(",")):
            assert not re.search(r"position\s*:\s*static", m.group(2)), m.group(1).strip()


def test_css_aplikacji_w_przestrzeni_jarvo_app():
    sekcja = re.sub(r"/\*.*?\*/", "", CSS.split("Aplikacja Jarvo (wersja 2", 1)[1].split("*/", 1)[1], flags=re.S)
    assert "prefers-reduced-motion" in sekcja and "@container app (max-width: 1023px)" in sekcja
    assert "@container app (max-width: 639px)" in sekcja
    for sel in re.findall(r"(?m)^([^\s@}/][^{]*)\{", sekcja):
        for s in re.split(r",(?![^()]*\))", sel):      # przecinki poza nawiasami (:is(a, b))
            s = s.strip()
            assert s.startswith((".j-", ".jarvo-app", "html[data-jarvo-app]", "from", "to", "@")) or s == "", s
    # motyw dashboardu (Fosfor) nie sięga do aplikacji: linie skanowania, poświata, kanciaste przyciski, fosforowe ramki
    for wzor in ("html[data-jarvo-app] body::after", ".jarvo-app { text-shadow: none; }",
                 ".jarvo-app :is(button, input, select, textarea) { border-radius: var(--j-r, 0) !important; }",
                 ".jarvo-app :focus-visible { outline: 2px solid var(--j-fokus) !important;"):
        assert wzor in sekcja, wzor


@pytest.mark.skipif(not NODE, reason="brak node")
def test_pakiet_sklejony_ma_poprawna_skladnie(tmp_path):
    hqbuild = load_script("scripts/hqbuild.py", "jarvo_test_hqbuild_front")
    plik = tmp_path / "app.js"
    plik.write_text(hqbuild.bundle_js(), encoding="utf-8")
    r = subprocess.run([NODE, "--check", str(plik)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "window.__JARVO_APP__ = { App: AppJarvo, StaraBaza, wersja: 2 };" in plik.read_text(encoding="utf-8")
