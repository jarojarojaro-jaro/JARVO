"""Skill izometria (shared/skills/izometria): budowa strony z szablonu iso-glow, kontrola figur, kolor marki,
polecenia PNG i filmu, kopia kroju przy buildzie, spis źródeł z paczką bez gita.

Przeglądarka (iso_render.cjs) i film (html_wideo.py) są sprawdzane w kontenerze; tu czyste funkcje i budowa.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import tarfile
from pathlib import Path

import pytest

import build
import fleetlib as fl
import zrodla
from conftest import load_script

ISO = load_script("shared/skills/izometria/scripts/iso.py")
SKILL = fl.REPO_ROOT / "shared" / "skills" / "izometria"
PRZYKLADY = [SKILL / "assets" / "przyklady" / "ekspres.js",
             SKILL / "assets" / "iso-glow" / "assets" / "examples" / "desk-computer.js",
             SKILL / "assets" / "iso-glow" / "assets" / "examples" / "office-tower.js"]


def figury(*sciezki: Path) -> list[tuple[str, str]]:
    return [(str(p), p.read_text(encoding="utf-8")) for p in sciezki]


def test_szablon_ma_kazde_miejsce_nakladki_raz():
    """Nowa wersja iso-glow, która zmieni te miejsca, ma wywrócić test, a nie po cichu zostawić angielski szablon."""
    s = ISO.SZABLON.read_text(encoding="utf-8")
    for stare, _ in ISO.ZAMIANY_STALE:
        assert s.count(stare) == 1, stare[:60]
    for stare in (ISO.GOOGLE_FONTS, ISO.STOPKA, "<title>Iso Figures</title>", "Iso figures</span>",
                  "/* paste figure scripts here (see examples/) */"):
        assert s.count(stare) == 1, stare[:60]


def test_kopia_upstreamu_bez_zmian_i_bez_drugiego_skilla():
    kopia = SKILL / "assets" / "iso-glow"
    assert not list(SKILL.rglob("SKILL.md"))[1:], "w skillu może być tylko jeden SKILL.md (Hermes widziałby drugi skill)"
    assert "April Zhu" in (kopia / "LICENSE").read_text() and "Tolga Cohce" in (kopia / "LICENSE").read_text()
    assert (kopia / "ISO-GLOW.md").read_text().startswith("---\nname: iso-glow")


def test_zbuduj_strona_po_polsku_bez_sieci():
    strona, raport = ISO.zbuduj(figury(*PRZYKLADY), tytul="Figury <Jarva>")
    assert raport["bledy"] == [] and [f["id"] for f in raport["figury"]] == ["ekspres", "computer", "tower"]
    assert '<html lang="pl">' in strona and "<title>Figury &lt;Jarva&gt;</title>" in strona
    assert "fonts.googleapis" not in strona and 'font-family:"JetBrains Mono"' in strona
    assert "data:font/woff2;base64," in strona
    assert "Rys. 1" in strona and "← Wstecz" in strona and "Kolor poświaty" in strona
    assert "Made with ISO-GLOW" in strona                       # nasze materiały: stopka zostaje
    assert strona.index("window.__isoCzas") < strona.index("FIGS.push(")
    # każda figura we własnym <script> (błąd jednej nie zabija reszty), czas przez __isoCzas
    assert len(re.findall(r"<script>\n/\* [\w-]+\.js \*/\n", strona)) == 3
    assert "const t = setTimeout(fn, ms)" not in strona and "__isoCzas.after(fn, ms)" in strona
    assert re.search(r"/\*ISO_JARVO\*/\{\"kadr\": false, \"podpis\": false, \"motyw\": \"auto\"\}/\*ISO_JARVO\*/", strona)
    assert not re.search(r"https?://(?!www\.w3\.org|iso-glow\.vercel\.app)", strona)


def test_zbuduj_dla_klienta_kadr_bez_stopki_kolor_marki():
    paleta = [ISO.akcent_marki("Marka=#1E3A8A")]
    strona, _ = ISO.zbuduj(figury(PRZYKLADY[0]), "Kasa", paleta, motyw="jasny", kadr=True, demo=True, stopka=False,
                           kroj="systemowy")
    assert "Made with ISO-GLOW" not in strona and "iso-glow.vercel.app" not in strona
    assert '"kadr": true' in strona and '"motyw": "jasny"' in strona
    assert "autoDemo: true" in strona and json.dumps(paleta) in strona
    assert "@font-face" not in strona and "https://" not in strona


def test_akcent_marki_widoczny_na_obu_panelach():
    nazwa, ciemny, ciemny_hi, jasny, jasny_hi = ISO.akcent_marki("#1E3A8A")        # granat ginie na ciemnym panelu
    assert nazwa == "Marka"
    assert ISO.kontrast(ISO._hex(ciemny), ISO._hex(ISO.PANEL["ciemny"])) >= 3
    assert ISO.kontrast(ISO._hex(jasny), ISO._hex(ISO.PANEL["jasny"])) >= 3
    assert jasny == "#1e3a8a"                                                       # na jasnym zostaje kolor marki
    assert ISO.akcent_marki("Pomarańcz=#ff7a1a,#ffb070", 2)[:3] == ["Pomarańcz", "#ff7a1a", "#ffb070"]
    assert ISO.akcent_marki("#E4572E", 2)[0] == "Marka 2"
    for zly in ("czerwony", "#12", "A=#ff0000,#00ff00,#0000ff", "<b>=#ff0000"):
        with pytest.raises(ISO.Blad):
            ISO.akcent_marki(zly)


def test_kontrola_figur():
    for p in PRZYKLADY:                     # przykłady (nasz i upstreamu) są czyste
        k = ISO.kontrola(p.read_text(encoding="utf-8"), p.name)
        assert k["bledy"] == [] and k["uwagi"] == [], (p.name, k)
    zla = """FIGS.push({ id: 'x', name: 'X', aria: 'a',
      mount(stage, api) {
        // komentarz z #ff0000 i https://example.com nie jest błędem
        stage.innerHTML = `<rect fill="#ff7a1a"/><image href="https://cdn.example.com/a.png"/>`;
        fetch('/dane.json'); setTimeout(() => {}, 10); const r = Math.random();
        return { demo() {} };
      } });"""
    k = ISO.kontrola(zla, "zla.js")
    assert sorted({b["kod"] for b in k["bledy"]}) == ["adres", "kolor", "siec"]
    assert all(b["linia"] in (4, 5) for b in k["bledy"])
    assert {u["kod"] for u in k["uwagi"]} == {"czas", "losowosc"}
    assert ISO.kontrola("const a = 1;")["bledy"][0]["kod"] == "brak-figury"
    assert {u["kod"] for u in ISO.kontrola("FIGS.push({ id: 'y', name: 'Y', mount() {} });")["uwagi"]} == {"aria", "demo"}
    # id ani klasa z literami a–f to nie kolor; skrypt w napisie zamyka stronę
    assert ISO.kontrola("FIGS.push({id:'cafe', aria:'', demo(){}, mount(s){ s.querySelector('#cafe-glass'); }})")["bledy"] == []
    assert ISO.kontrola("FIGS.push({ id: 'z', x: '</script>' })")["bledy"][0]["kod"] == "skrypt"


def test_zbuduj_odrzuca_bledy_i_podwojne_id():
    with pytest.raises(ISO.Blad, match="kolor"):
        ISO.zbuduj([("a.js", "FIGS.push({ id: 'a', mount(s) { s.style.fill = 'rgb(1,2,3)'; } });")])
    with pytest.raises(ISO.Blad, match="dwa razy"):
        ISO.zbuduj(figury(PRZYKLADY[0], PRZYKLADY[0]))
    with pytest.raises(ISO.Blad, match="paleta"):
        ISO.zbuduj(figury(PRZYKLADY[0]), paleta="neon")


def test_figury_ze_zbudowanej_strony(tmp_path):
    strona, _ = ISO.zbuduj(figury(*PRZYKLADY))
    p = tmp_path / "galeria.html"
    p.write_text(strona, encoding="utf-8")
    assert ISO.lista_figur(p) == [{"id": "ekspres", "nazwa": "Ekspres do kawy"},
                                  {"id": "computer", "nazwa": "Desk computer"},
                                  {"id": "tower", "nazwa": "Office tower"}]
    assert ISO.kontrola(ISO.figury_ze_strony(strona))["bledy"] == []
    with pytest.raises(ISO.Blad):
        ISO.figury_ze_strony("<html></html>")


def test_png_i_film_polecenia(tmp_path):
    assert ISO.nazwy_png(tmp_path / "a.png", ["x"]) == [tmp_path / "a.png"]
    assert ISO.nazwy_png(tmp_path / "a.png", ["x", "y"]) == [tmp_path / "a-x.png", tmp_path / "a-y.png"]
    assert ISO._rozmiar("1080x1350") == (1080, 1350)
    with pytest.raises(ISO.Blad):
        ISO._rozmiar("duzy")
    url = ISO._url(tmp_path / "s.html", render=True, figura="ekspres", tlo="0", podpis=False, akcent=None)
    assert url.endswith("/s.html?render=1&figura=ekspres&tlo=0")
    cmd = ISO.polecenie_wideo(tmp_path / "s.html", tmp_path / "f.mp4", "ekspres", 6, 30, (1080, 1920), "ciemny",
                              True, None, Path("/x/html_wideo.py"))
    assert cmd[1:5] == ["/x/html_wideo.py", "wideo", str(tmp_path / "s.html"), "--preset"] and "jarvo" in cmd
    assert cmd[cmd.index("--query") + 1] == "demo=1&motyw=ciemny&figura=ekspres&podpis=1"
    assert cmd[cmd.index("--rozmiar") + 1] == "1080x1920" and cmd[cmd.index("--dlugosc") + 1] == "6"


def test_cli_zbuduj_i_figury(tmp_path, capsys):
    out = tmp_path / "x" / "kasa.html"
    assert ISO.main(["zbuduj", str(PRZYKLADY[0]), "-o", str(out), "--kadr", "--bez-stopki", "--akcent", "#E4572E"]) == 0
    wynik = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert wynik["paleta"] == ["Marka"] and wynik["stopka"] is False and out.exists()
    assert ISO.main(["figury", str(out)]) == 0
    assert json.loads(capsys.readouterr().out) == [{"id": "ekspres", "nazwa": "Ekspres do kawy"}]
    assert ISO.main(["sprawdz", str(out)]) == 0
    zla = tmp_path / "zla.js"
    zla.write_text("FIGS.push({ id: 'z', mount(s) { s.innerHTML = '<rect fill=\"#abcdef\"/>'; } });")
    assert ISO.main(["zbuduj", str(zla), "-o", str(tmp_path / "z.html")]) == 1
    assert ISO.main(["sprawdz", str(zla)]) == 1
    assert "kolor wpisany" in capsys.readouterr().out


def test_build_kopiuje_kroj_do_skilla(tmp_path):
    lock = {"sources": {"jarvo": {"type": "repo-tree", "license": "MIT", "notice": "Jarvo."}},
            "agents": {"jarvo-studio": [{"source": "jarvo", "path": "shared/skills/izometria", "dest": "design/izometria"}]}}
    resolver = build.SourceResolver(lock, None, tmp_path / "cache", {})
    build.vendor_skills("jarvo-studio", tmp_path / "skills", lock, resolver, [])
    skill = tmp_path / "skills" / "design" / "izometria"
    for name in build.ISO_KROJ:
        assert (skill / "scripts" / "kroje" / name).read_bytes() == (fl.REPO_ROOT / "hq/web/fonts/kroje" / name).read_bytes()
    assert (skill / "assets" / "iso-glow" / "LICENSE").exists() and (skill / "LICENSE-UPSTREAM").exists()
    # w kontenerze nie ma repo: krój z kopii obok skryptu
    iso = load_script(str(skill / "scripts" / "iso.py"), "jarvo_test_iso_zbudowany")
    assert iso.REPO is None and iso.KROJE == [skill / "scripts" / "kroje"]
    assert 'font-family:"JetBrains Mono"' in iso._kroj_css()


def _tar(pliki: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel, dane in pliki.items():
            info = tarfile.TarInfo(f"iso-glow/{rel}")
            info.size = len(dane)
            tar.addfile(info, io.BytesIO(dane))
    return buf.getvalue()


def test_zrodla_paczka_bez_gita(tmp_path):
    kopia = tmp_path / "kopia"
    (kopia / "assets").mkdir(parents=True)
    (kopia / "ISO-GLOW.md").write_bytes(b"skill")
    (kopia / "LICENSE").write_bytes(b"MIT")
    (kopia / "assets" / "gallery.html").write_bytes(b"<html>")
    stara = _tar({"SKILL.md": b"skill", "LICENSE": b"MIT", "assets/gallery.html": b"<html>"})
    spec = {"paczka": "https://x/iso-glow.tar.gz", "kopia": str(kopia), "nazwy": {"SKILL.md": "ISO-GLOW.md"},
            "status": "uzywane", "przejrzane": hashlib.sha256(stara).hexdigest()}
    w = zrodla.sprawdz_paczke("iso-glow", spec, pobieranie=lambda url: stara)
    assert w["zmiany"] is False and "blad" not in w
    nowa = _tar({"SKILL.md": b"skill v2", "LICENSE": b"MIT", "assets/gallery.html": b"<html>",
                 "assets/examples/lamp.js": b"FIGS.push()"})
    w = zrodla.sprawdz_paczke("iso-glow", spec, pobieranie=lambda url: nowa)
    assert w["zmiany"] and w["glowa"] == hashlib.sha256(nowa).hexdigest()
    assert w["dodane"] == ["assets/examples/lamp.js"] and w["zmienione"] == ["SKILL.md"] and w["usuniete"] == []
    assert w["zmienione_skille"] == ["SKILL.md"] and w["licencja"] == []
    raport = zrodla.raport([w])
    assert "## iso-glow (uzywane): nowa wersja paczki" in raport and "`assets/examples/lamp.js`" in raport
    w = zrodla.sprawdz_paczke("iso-glow", spec, pobieranie=lambda url: (_ for _ in ()).throw(OSError("brak sieci")))
    assert w["blad"].startswith("niedostępne")


def test_spis_zrodel_ma_iso_glow_z_suma():
    spis = zrodla.wczytaj()
    assert spis["iso-glow"]["kopia"] == "shared/skills/izometria/assets/iso-glow"
    assert re.fullmatch(r"[0-9a-f]{64}", spis["iso-glow"]["przejrzane"])
    assert spis["ai-iso-skill"]["repo"] == "https://github.com/MrBongoC/ai-iso-skill"
