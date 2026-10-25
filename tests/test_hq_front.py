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
APLIKACJA = ("02-sklep.js", "03-trasa.js", "04-i18n.js", "05-skroty.js", "06-tokeny.js", "07-sciezki.js", "11-strumien.js", "12-wzmianki.js",
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


# ---------------------------------------------------------------- panel bez logowania (docs/NATYWNIE.md W11, I11)

def _wycinek(plik: str, od: str, do: str) -> str:
    t = _tekst(plik)
    i = t.index(od)
    return t[i:t.index(do, i)]


ZRODLO_FETCH = r"""
const vm = require("vm"), fs = require("fs");
const kod = fs.readFileSync(process.argv[2], "utf8");
const czekaj = (ms) => new Promise((ok) => setTimeout(ok, ms));
function strumien(kawalki) {
  const enc = new TextEncoder();
  return new ReadableStream({ async pull(c) { if (!kawalki.length) { c.close(); return; } await czekaj(1);
    c.enqueue(enc.encode(kawalki.shift())); } });
}
async function przypadek(odp, { zamknij = false } = {}) {
  const zapytania = [], zdarzenia = [], bledy = [];
  const ctx = { TextDecoder, AbortController, console,
    authHeaders: (h) => Object.assign({ "X-Jarvo-Request": "1", "X-Hermes-Session-Token": "tok" }, h || {}),
    fetch: async (url, init) => { zapytania.push({ url, init: { ...init, signal: !!init.signal } });
      if (odp === "siec") throw new TypeError("Failed to fetch");
      return { ok: odp.status === 200, status: odp.status, body: strumien([...(odp.kawalki || [])]) }; } };
  vm.runInNewContext(kod + "\nthis.ZrodloFetch = ZrodloFetch;", ctx);
  const z = new ctx.ZrodloFetch("/api/plugins/jarvo-hq/strumien?klient=k&watki=");
  for (const typ of ["hello", "watek.wpis", "message"]) z.addEventListener(typ, (e) => zdarzenia.push([e.type, e.data, e.lastEventId]));
  z.onerror = () => bledy.push(z.readyState);
  if (zamknij) { await czekaj(5); z.close(); }
  await czekaj(80);
  return { zapytania, zdarzenia, bledy, stan: z.readyState, status: z.status };
}
(async () => {
  const wynik = {
    sse: await przypadek({ status: 200, kawalki: ["event: hello\ndata: {\"a\":1}\n", "\n: komentarz\nid: e1.5\r\nevent: watek.wpis\r\ndata: {\"x\"",
      ":2}\r\n\r\n", "data: linia1\ndata:linia2\n\nretry: 10\n\n"] }),
    nieupowazniony: await przypadek({ status: 401 }),
    siec: await przypadek("siec"),
    zamkniety: await przypadek({ status: 200, kawalki: ["data: a\n\n", "data: b\n\n", "data: c\n\n"] }, { zamknij: true }),
  };
  console.log(JSON.stringify(wynik));
})();
"""


@pytest.mark.skipif(not NODE, reason="brak node")
def test_strumien_przez_fetch_z_tokenem(tmp_path):
    """W11: bez logowania EventSource nie wyśle nagłówka z tokenem sesji, więc lider czyta SSE przez fetch: nagłówki
    panelu (token, X-Jarvo-Request), Accept text/event-stream, parser ramek („event:”, „data:” w kilku wierszach,
    „id:” zostaje dla następnych, komentarze i „retry:” pominięte, CRLF), status ≠ 200, sieć i koniec odpowiedzi =
    readyState 2 i jedno onerror; close() nie zgłasza błędu."""
    h = tmp_path / "zrodlo.cjs"
    h.write_text(ZRODLO_FETCH, encoding="utf-8")
    klasa = tmp_path / "klasa.js"
    klasa.write_text(_wycinek("11-strumien.js", "class ZrodloFetch", "const Strumien = "), encoding="utf-8")
    r = subprocess.run([NODE, str(h), str(klasa)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    w = __import__("json").loads(r.stdout)
    sse = w["sse"]
    assert sse["zdarzenia"] == [["hello", '{"a":1}', ""], ["watek.wpis", '{"x":2}', "e1.5"],
                                ["message", "linia1\nlinia2", "e1.5"]]
    assert sse["bledy"] == [2] and sse["stan"] == 2 and sse["status"] == 200
    init = sse["zapytania"][0]["init"]
    assert init["headers"]["X-Hermes-Session-Token"] == "tok" and init["headers"]["Accept"] == "text/event-stream"
    assert init["credentials"] == "include" and init["cache"] == "no-store" and init["signal"]
    assert w["nieupowazniony"]["bledy"] == [2] and w["nieupowazniony"]["status"] == 401
    assert not w["nieupowazniony"]["zdarzenia"]
    assert w["siec"]["bledy"] == [2] and w["siec"]["stan"] == 2
    assert w["zamkniety"]["bledy"] == [] and w["zamkniety"]["stan"] == 2


LOGOWANIE = r"""
const vm = require("vm"), fs = require("fs");
const kod = fs.readFileSync(process.argv[2], "utf8");
function przypadek(auth, schowek) {
  const ruchy = [], zapamietane = [];
  const pamiec = new Map(Object.entries(schowek || {}));
  const ctx = { Date, Number, String, window: { __HERMES_AUTH_REQUIRED__: auth },
    sessionStorage: { getItem: (k) => (pamiec.has(k) ? pamiec.get(k) : null), setItem: (k, v) => pamiec.set(k, v) },
    location: { replace: (u) => ruchy.push(["replace", u]), assign: (u) => ruchy.push(["assign", u]) },
    Trasa: { zapamietaj: () => zapamietane.push(1) }, basePath: () => "/hermes" };
  vm.runInNewContext(kod + "\nnaLogowanie(); naLogowanie();", ctx);
  return { ruchy, zapamietane: zapamietane.length, pamiec: [...pamiec.keys()] };
}
console.log(JSON.stringify({
  bez: przypadek(false),
  bez_zaraz_po: przypadek(false, { "jarvo.odswiezenie_401": String(Date.now() - 5000) }),
  bez_dawno: przypadek(false, { "jarvo.odswiezenie_401": String(Date.now() - 60000) }),
  z_logowaniem: przypadek(true),
}));
"""


@pytest.mark.skipif(not NODE, reason="brak node")
def test_401_bez_logowania_przeladowuje_strone_raz(tmp_path):
    """W11, I11: bez logowania 401 to nowy token po restarcie panelu, więc strona /jarvo wczytuje się od nowa (hash
    w sessionStorage), najwyżej raz na 20 s; z logowaniem (tryb LAN, kontener) jak dotąd strona logowania."""
    h = tmp_path / "logowanie.cjs"
    h.write_text(LOGOWANIE, encoding="utf-8")
    kod = tmp_path / "kod.js"
    kod.write_text(_wycinek("10-api.js", "const bezLogowania", "if (typeof window !== \"undefined\")"), encoding="utf-8")
    r = subprocess.run([NODE, str(h), str(kod)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    w = __import__("json").loads(r.stdout)
    assert w["bez"]["ruchy"] == [["replace", "/hermes/jarvo"]] and w["bez"]["zapamietane"] == 1
    assert w["bez_zaraz_po"]["ruchy"] == [] and w["bez_zaraz_po"]["zapamietane"] == 0     # bez pętli przeładowań
    assert w["bez_dawno"]["ruchy"] == [["replace", "/hermes/jarvo"]]
    assert w["z_logowaniem"]["ruchy"] == [["assign", "/hermes/login?next=%2Fhermes%2Fjarvo"]]


@pytest.mark.skipif(not NODE, reason="brak node")
def test_ryzyko_zgody_w_przegladarce_jak_na_serwerze(tmp_path):
    """W17: Os.ryzyko (15-os.js) zna te same polecenia Windows i macOS co przebiegi.ryzyko na serwerze."""
    import json as _json
    kod = tmp_path / "ryzyko.js"
    kod.write_text(_wycinek("15-os.js", "const RYZYKA", "// przyciski zgody"), encoding="utf-8")
    przypadki = {"Remove-Item -Recurse C:\\x": "usun", "del /s /q C:\\x": "usun", "rd /s /q build": "usun",
                 "reg delete HKCU\\Software\\X /f": "admin", "icacls C:\\x /grant Everyone:F": "admin",
                 "takeown /f C:\\x": "admin", "Set-ExecutionPolicy Bypass": "admin", "diskutil eraseDisk": "admin",
                 "Stop-Process -Name chrome": "restart", "launchctl unload x.plist": "restart",
                 "Invoke-WebRequest https://x": "siec", "delegate_task do Web": "inne", "rm -rf /tmp/x": "usun"}
    harness = tmp_path / "h.cjs"
    harness.write_text(
        'const vm = require("vm"), fs = require("fs");'
        'const ctx = {}; vm.runInNewContext(fs.readFileSync(process.argv[2], "utf8") + "\\nthis.ryzyko = ryzyko;", ctx);'
        'const p = JSON.parse(process.argv[3]); const out = {};'
        'for (const o of Object.keys(p)) out[o] = ctx.ryzyko({ opis: o });'
        'out.zapis = ctx.ryzyko({ klucz_wzorca: "plugin_rule:jarvo-zgody:write_file:a:b" });'
        'console.log(JSON.stringify(out));', encoding="utf-8")
    r = subprocess.run([NODE, str(harness), str(kod), _json.dumps(przypadki)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert _json.loads(r.stdout) == {**przypadki, "zapis": "zapis"}
    sl = validate.slownik_i18n(_tekst("04-i18n.js"))
    assert "zgoda.r_zapis" in sl["pl"] and "zgoda.r_zapis" in sl["en"]


def test_pliki_bez_logowania_bez_adresu_file():
    """W11: w trybie z tokenem SVG idzie jako data:, a nowa karta i PDF przez link podglądu :9120; adres /file zostaje
    tylko dla ciasteczka (z logowaniem). Ramka PDF z :9120 bez atrybutu sandbox (inne pochodzenie z CSP sandbox)."""
    api, pliki = _tekst("10-api.js"), _tekst("34-pliki.js")
    assert "const zTokenem = () => !!window.__HERMES_SESSION_TOKEN__;" in api
    for f in ("useSvgUrl", "useAdresPliku", "otworzPlik"):
        assert f"function {f}(" in api and f in pliki, f
    assert 'readAsDataURL(new Blob([b], { type: "image/svg+xml" }))' in api
    assert "window.open(urlPliku" not in pliki and "src=${urlPliku" not in pliki and "href=${urlPliku" not in pliki
    assert 'sandbox=${zTokenem() ? undefined : ""}' in pliki
    strumien = _tekst("11-strumien.js")
    assert "zTokenem() ? new ZrodloFetch(url) : new EventSource(url)" in strumien
    assert "headers: authHeaders() })).status" in strumien
    assert 'bezLogowania()\n        ? html`<${Wiersz} ikona="logout" tytul=${T("szuflada.bez_logowania")}' in _tekst("61-szuflada.js")
