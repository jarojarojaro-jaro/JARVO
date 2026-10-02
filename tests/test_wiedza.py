"""Skarbiec wiedzy (wiedza/wiedza.py): zasiew z fleet.json, indeks FTS5 po polsku, linki, lint, szkice, orzeczenia,
punkty zapisu git, bezpieczeństwo ścieżek, graf."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "wiedza"))
import wiedza as w  # noqa: E402

FLEET = {"orchestrator": "jarvo", "agents": [
    {"name": "jarvo", "short": "Jarvo", "title": "Main Judge", "emoji": "🛰️", "kind": "orchestrator", "description": "Main Judge floty.",
     "room": "bridge", "label": "Mostek", "telegram_topic": "general", "autonomy_max": "A1",
     "skills": [{"name": "intake", "description": "Intake: rozumie zlecenie."}], "scripts": ["patrol.py"]},
    {"name": "jarvo-web", "short": "Web", "title": "Web Senior Dev", "emoji": "🌐", "kind": "specialist", "description": "Strony i SEO.",
     "room": "devlab", "label": "Pracownia webowa", "telegram_topic": "web", "autonomy_max": "A1",
     "skills": [{"name": "nowa-strona", "description": "Nowa strona: od briefu do wdrożenia."}], "external_skills": ["gsap", "seo-audit"],
     "scripts": ["audit.sh", "seo_check.py"]},
    {"name": "jarvo-lowca", "short": "Łowca", "title": "Łowca leadów", "emoji": "🎯", "kind": "specialist", "description": "Leady B2B.",
     "room": "radar", "label": "Radar", "telegram_topic": "lowca", "autonomy_max": "A1", "skills": [], "scripts": ["krs.py"]},
]}
GIT = shutil.which("git") is not None


def notatka(sk, rel, tytul, tresc, typ="fakt", zrodlo="karta t_1", linki=(), **fm):
    front = {"typ": typ, "tagi": ["test"], "utworzono": "2026-09-30", "zmieniono": "2026-09-30", "status": "aktualna", "zrodlo": zrodlo, **fm}
    pow = "\n".join(f"- [[{l}]]" for l in linki)
    sk.zapisz_plik(rel, w.sklej(front, f"# {tytul}\n\n**{tresc}**\n\n## Powiązane\n{pow}\n"))


@pytest.fixture
def skarbiec(tmp_path, monkeypatch):
    monkeypatch.setenv("WIEDZA_DZIS", "2026-09-30")
    root = tmp_path / "knowledge"
    (root / "brands" / "acme").mkdir(parents=True)
    (root / "brands" / "acme" / "BRAND.md").write_text("# Acme\nKolory: czerwony.\n", encoding="utf-8")
    (root / "user").mkdir()
    (root / "user" / "USER.md").write_text("# Użytkownik\nMiki prowadzi agencję.\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "PLAN.md").write_text("# Plan\nTreść.\n", encoding="utf-8")
    fleet = tmp_path / "fleet.json"
    fleet.write_text(json.dumps(FLEET, ensure_ascii=False), encoding="utf-8")
    assert w.main(["--skarbiec", str(root), "--stan", str(tmp_path / "state"), "zasiej", "--fleet", str(fleet), "--docs", str(docs)]) == 0
    return w.Skarbiec(root, tmp_path / "state")


def test_zasiew_huby_orzeczenia_docs_git(skarbiec, tmp_path):
    sk = skarbiec
    huby = {p.name for p in sk.root.rglob("_hub-*.md")}
    assert huby == {"_hub-skarbiec.md", "_hub-agenci.md", "_hub-projekty.md", "_hub-marki.md", "_hub-ty.md", "_hub-podmioty.md",
                    "_hub-pojecia.md", "_hub-orzeczenia.md", "_hub-rozmowy.md", "_hub-jarvo.md", "_hub-web.md", "_hub-łowca.md"}
    assert len(huby) == len({h for h in huby})                       # nazwy unikalne w całym skarbcu (etykiety w grafie)
    hub = (sk.root / "agenci/jarvo-web/_hub-web.md").read_text(encoding="utf-8")
    assert "[[fleet/skille/nowa-strona|nowa-strona]]: Nowa strona: od briefu do wdrożenia." in hub
    assert "skille zewnętrzne (2): `gsap`, `seo-audit`" in hub
    assert "[[orzeczenia/web|Orzeczenia: Web]]" in hub and "<!-- Jarvo:GEN lista -->" in hub
    assert (sk.root / "orzeczenia/łowca.md").exists() and (sk.root / "orzeczenia/wszyscy.md").exists()
    assert (sk.root / "zrodla/jarvo-repo/PLAN.md").exists() and (sk.root / "SCHEMA.md").exists() and (sk.root / "LINT.md").exists()
    meta = json.loads((tmp_path / "state" / "wiedza-agenci.json").read_text(encoding="utf-8"))
    assert meta["jarvo-lowca"] == {"hub": "agenci/jarvo-lowca/_hub-łowca", "orzeczenia": "orzeczenia/łowca", "short": "Łowca",
                                   "title": "Łowca leadów", "opis": "Leady B2B."}
    index = (sk.root / "INDEX.md").read_text(encoding="utf-8")
    assert "[[agenci/jarvo-web/_hub-web|🌐 Web Senior Dev (jarvo-web)]]" in index and "[[user/USER|Użytkownik]]" in index
    assert "## [2026-09-30] zasiew |" in (sk.root / "LOG.md").read_text(encoding="utf-8")
    assert (sk.root / ".git").exists() == GIT


def test_ponowny_zasiew_zachowuje_reczna_czesc_i_odswieza_blok(skarbiec, tmp_path):
    sk = skarbiec
    p = sk.root / "agenci/jarvo-web/_hub-web.md"
    p.write_text(p.read_text(encoding="utf-8").replace("## Powiązane", "Ręczna uwaga o Webie.\n\n## Powiązane"), encoding="utf-8")
    fleet = json.loads((tmp_path / "fleet.json").read_text(encoding="utf-8"))
    fleet["agents"][1]["skills"].append({"name": "seo", "description": "SEO techniczne."})
    (tmp_path / "fleet.json").write_text(json.dumps(fleet, ensure_ascii=False), encoding="utf-8")
    assert w.main(["--skarbiec", str(sk.root), "--stan", str(tmp_path / "state"), "zasiej", "--fleet", str(tmp_path / "fleet.json")]) == 0
    hub = p.read_text(encoding="utf-8")
    assert "Ręczna uwaga o Webie." in hub and "[[fleet/skille/seo|seo]]: SEO techniczne." in hub and hub.count("<!-- Jarvo:GEN fleet -->") == 1
    (tmp_path / "docs" / "PLAN.md").unlink()                                  # dokument usunięty z repo znika z lustra
    (tmp_path / "docs" / "NOWY.md").write_text("# Nowy\n", encoding="utf-8")
    assert w.main(["--skarbiec", str(sk.root), "--stan", str(tmp_path / "state"), "zasiej", "--docs", str(tmp_path / "docs")]) == 0
    lustro = {x.name for x in (sk.root / "zrodla" / "jarvo-repo").glob("*.md")}
    assert "NOWY.md" in lustro and "PLAN.md" not in lustro


def test_opis_agenta_w_hubie_idzie_za_fleet_yaml(skarbiec, tmp_path):
    """Opis agenta (pogrubiony akapit huba) odświeża się z fleet.yaml przy zasiewie, chyba że człowiek go zmienił."""
    sk = skarbiec
    zasiew = ["--skarbiec", str(sk.root), "--stan", str(tmp_path / "state"), "zasiej", "--fleet", str(tmp_path / "fleet.json")]
    fleet = json.loads((tmp_path / "fleet.json").read_text(encoding="utf-8"))
    fleet["agents"][1]["description"] = "Strony i SEO techniczne, bez researchu rynku."
    (tmp_path / "fleet.json").write_text(json.dumps(fleet, ensure_ascii=False), encoding="utf-8")
    assert w.main(zasiew) == 0
    web = sk.root / "agenci/jarvo-web/_hub-web.md"
    assert "**Strony i SEO techniczne, bez researchu rynku.**" in web.read_text(encoding="utf-8")
    web.write_text(web.read_text(encoding="utf-8").replace("**Strony i SEO techniczne, bez researchu rynku.**",
                                                            "**Mój opis Weba.**"), encoding="utf-8")
    fleet["agents"][1]["description"] = "Jeszcze inny opis."
    (tmp_path / "fleet.json").write_text(json.dumps(fleet, ensure_ascii=False), encoding="utf-8")
    assert w.main(zasiew) == 0
    hub = web.read_text(encoding="utf-8")
    assert "**Mój opis Weba.**" in hub and "Jeszcze inny opis" not in hub                  # ręczna zmiana zostaje


def test_skarbiec_idzie_za_kodem_zmiany_i_nieaktualne_skrypty(skarbiec, tmp_path):
    """Hub agenta pokazuje ostatnie zmiany z CHANGELOG-u; lint wskazuje notatki floty z odwołaniem do skryptu,
    którego nie ma już w repo (notatki o klientach nie są sprawdzane)."""
    sk = skarbiec
    fleet = json.loads((tmp_path / "fleet.json").read_text(encoding="utf-8"))
    fleet["agents"][1]["changes_section"] = "Niewydane"
    fleet["agents"][1]["changes"] = ["Bramka jakości liczona skryptem."]
    fleet["repo_scripts"] = ["odcisk.py"]
    (tmp_path / "fleet.json").write_text(json.dumps(fleet, ensure_ascii=False), encoding="utf-8")
    assert w.main(["--skarbiec", str(sk.root), "--stan", str(tmp_path / "state"), "zasiej", "--fleet", str(tmp_path / "fleet.json")]) == 0
    hub = (sk.root / "agenci/jarvo-web/_hub-web.md").read_text(encoding="utf-8")
    assert "- ostatnie zmiany (CHANGELOG profilu, Niewydane):\n  - Bramka jakości liczona skryptem." in hub
    notatka(sk, "agenci/jarvo-web/audyt skryptem", "Audyt skryptem", "Audyt robi `audit.sh`, a zgody `scripts/odcisk.py --sprawdz`.",
            linki=["agenci/jarvo-web/_hub-web", "pojecia/_hub-pojecia"])
    notatka(sk, "agenci/jarvo-web/stary audyt", "Stary audyt", "Audyt robi `$HERMES_HOME/scripts/stary_audyt.py`.",
            linki=["agenci/jarvo-web/_hub-web", "pojecia/_hub-pojecia"])
    notatka(sk, "projekty/sklep klienta", "Sklep klienta", "Klient ma `manage.py` w Django.", typ="projekt",
            linki=["projekty/_hub-projekty", "pojecia/_hub-pojecia"])
    ix = w.Indeks(sk)
    raport = w.lint(sk, ix)
    ix.zamknij()
    nieaktualne = [o for o in raport["ostrzezenia"] if "nieaktualna wobec repo" in o]
    assert nieaktualne == ["nieaktualna wobec repo: skryptu `stary_audyt.py` nie ma we flocie: [[agenci/jarvo-web/stary audyt]]"]


def test_szukaj_po_polsku_bez_ogonkow_i_krok_po_linkach(skarbiec):
    sk = skarbiec
    notatka(sk, "agenci/jarvo-web/lighthouse tylko w chromium", "Lighthouse tylko w Chromium",
            "Wydajność strony mierzymy Chromium, bo Lightpanda nie renderuje WebGL.", linki=["agenci/jarvo-web/_hub-web", "pojecia/_hub-pojecia"])
    notatka(sk, "pojecia/audyt strony", "Audyt strony", "Audyt strony to Lighthouse, axe i linkinator.", typ="pojecie",
            linki=["pojecia/_hub-pojecia", "agenci/jarvo-web/lighthouse tylko w chromium"])
    notatka(sk, "brands/acme/ton marki", "Ton marki Acme", "Acme mówi krótko i po ludzku.", zrodlo="rozmowa 2026-09-30 jarvo-studio")
    w.dodaj_orzeczenie(sk, "marki/acme", "Przyciski zawsze zaokrąglone", "rozmowa HQ")
    ix = w.Indeks(sk)
    ix.odswiez()
    wyn = ix.szukaj("wydajnosc strony")
    assert wyn and wyn[0]["sciezka"] == "agenci/jarvo-web/lighthouse tylko w chromium"
    assert [r["sciezka"] for r in ix.szukaj("audyt", folder="pojecia")] == ["pojecia/audyt strony"]
    marka = ix.szukaj("Acme")
    assert "brands/acme/ton marki" in [r["sciezka"] for r in marka] and "orzeczenia/marki/acme" in [r["sciezka"] for r in marka]
    assert ix.szukaj("") == [] and ix.szukaj("i a w") == []
    assert not [r for r in ix.szukaj("Plan treść") if r["sciezka"].startswith("zrodla/")]        # źródła poza domyślnym wyszukiwaniem
    assert [r for r in ix.szukaj("Plan treść", zrodla=True) if r["sciezka"] == "zrodla/jarvo-repo/PLAN"]
    assert sk.rozwiaz("audyt strony") == "pojecia/audyt strony" and sk.rozwiaz("nie ma takiej") is None   # jak w Obsidianie: sama nazwa
    ix.zamknij()


def test_linki_w_pamieci_jak_z_dysku_i_bez_przeliczania_bez_zmian(skarbiec):
    """Rozwiązywanie z `mapa()` daje to samo co sprawdzanie dysku; odświeżenie bez zmian nie przelicza linków."""
    sk = skarbiec
    notatka(sk, "pojecia/audyt strony", "Audyt strony", "Audyt to Lighthouse.", typ="pojecie", linki=["pojecia/_hub-pojecia"])
    sk.zapisz_plik("SCHEMA", "# Schemat\n")
    zbior, znane = sk.mapa()
    for cel in ("audyt strony", "pojecia/audyt strony", "/pojecia/audyt strony", "nie ma takiej", "pojecia/nie ma",
                "SCHEMA", "pojecia/audyt strony.md", "pojecia/../pojecia/audyt strony", "brands/_szablon/x", ".git/HEAD"):
        assert sk.rozwiaz(cel, znane, zbior) == sk.rozwiaz(cel), cel
    ix = w.Indeks(sk)
    ix.odswiez()
    ix.db.execute("UPDATE linki SET etykieta = 'znacznik'")                    # bez zmian w skarbcu: tabela linków zostaje
    ix.odswiez()
    assert {r[0] for r in ix.db.execute("SELECT etykieta FROM linki")} == {"znacznik"}
    notatka(sk, "pojecia/nowe", "Nowe", "Nowa notatka.", typ="pojecie", linki=["audyt strony"])
    assert ix.odswiez()["nowe"] == 1
    linki = {(r["z"], r["do_"], r["rozwiazany"]) for r in ix.linki()}
    assert ("pojecia/nowe", "pojecia/audyt strony", 1) in linki and "znacznik" not in {r["etykieta"] for r in ix.linki()}
    notatka(sk, "pojecia/do schematu", "Do schematu", "Link do schematu.", typ="pojecie", linki=["SCHEMA"])
    ix.odswiez()
    assert ("pojecia/do schematu", "SCHEMA", 1) in {(r["z"], r["do_"], r["rozwiazany"]) for r in ix.linki()}
    (sk.root / "SCHEMA.md").unlink()                                           # zniknął tylko plik specjalny: linki od nowa
    assert ix.odswiez()["zmienione"] == 0
    assert ("pojecia/do schematu", "SCHEMA", 0) in {(r["z"], r["do_"], r["rozwiazany"]) for r in ix.linki()}
    for pelny in (False, True):                                                # FTS bez zdublowanych wierszy
        notatka(sk, "pojecia/nowe", "Nowe", f"Zmiana {pelny}.", typ="pojecie")
        ix.odswiez(pelny=pelny)
        assert ix.db.execute("SELECT count(*) FROM fts").fetchone()[0] == len(sk.pliki())
    ix.zamknij()


def test_lint_czysty_i_bledy(skarbiec):
    sk = skarbiec
    ix = w.Indeks(sk)
    r = w.lint(sk, ix)
    assert r["bledy"] == [] and r["ostrzezenia"] == []
    notatka(sk, "pojecia/dobra notatka", "Dobra notatka", "Ma źródło, hub, sąsiada i link do innego folderu.", typ="pojecie",
            linki=["pojecia/_hub-pojecia", "pojecia/druga notatka", "agenci/jarvo-web/_hub-web"])
    notatka(sk, "pojecia/druga notatka", "Druga notatka", "Też dobra.", typ="pojecie", linki=["pojecia/_hub-pojecia", "pojecia/dobra notatka", "user/_hub-ty"])
    r = w.lint(sk, ix)
    assert r["bledy"] == [] and r["ostrzezenia"] == []
    notatka(sk, "pojecia/martwy link", "Martwy link", "Linkuje do niczego.", typ="pojecie", linki=["pojecia/nie ma"])
    notatka(sk, "podmioty/bez zrodla", "Bez źródła", "Nikt nie wie skąd.", typ="podmiot", zrodlo="")
    notatka(sk, "podmioty/z sekretem", "Z sekretem", "klucz sk_live_" + "Q7w" * 8, typ="podmiot")
    notatka(sk, "podmioty/zla data", "Zła data", "Data po amerykańsku.", typ="podmiot", utworzono="09/30/2026")
    notatka(sk, "podmioty/przeterminowana", "Przeterminowana", "Cena z zeszłego roku.", typ="podmiot", wazne_do="2026-01-01")
    notatka(sk, "podmioty/dobra notatka", "Dobra notatka", "Ten sam tytuł co w pojęciach.", typ="podmiot")
    notatka(sk, "podmioty/za dluga", "Za długa", "słowo " * 300, typ="podmiot")
    notatka(sk, "podmioty/zly typ", "Zły typ", "Typ spoza schematu.", typ="ciekawostka")
    r = w.lint(sk, ix)
    b = "\n".join(r["bledy"])
    assert "martwy link `[[pojecia/nie ma]]` w [[pojecia/martwy link]]" in b
    assert "brak źródła (`zrodlo:`): [[podmioty/bez zrodla]]" in b
    assert "sekret w treści (klucz Stripe): [[podmioty/z sekretem]]" in b and "sk_live_Q7w" not in b
    assert "data `utworzono: 09/30/2026` nie jest RRRR-MM-DD" in b
    assert "typ spoza schematu `ciekawostka`" in b
    o = "\n".join(r["ostrzezenia"])
    assert "przeterminowana (`wazne_do: 2026-01-01`): [[podmioty/przeterminowana]]" in o
    assert "duplikat tytułu: [[podmioty/dobra notatka]], [[pojecia/dobra notatka]]" in o
    assert re.search(r"za długa \(30\d słów, limit 250\): \[\[podmioty/za dluga\]\]", o)
    assert "sierota (linkuje tylko lista huba): [[podmioty/bez zrodla]]" in o and "bez linku do huba folderu: [[podmioty/bez zrodla]]" in o
    assert (sk.root / "LINT.md").read_text(encoding="utf-8").startswith("# Lint skarbca (2026-09-30)")
    ix.zamknij()


def test_szkic_i_odmowy(skarbiec, capsys):
    sk = skarbiec
    rel = w.zapisz_szkic(sk, "fakt", "Lightpanda nie renderuje three.js", "Zrzuty przez Chromium.", "karta t_8f2", "jarvo-web", ["web"], skad="sesja s1")
    assert rel.startswith("skrzynka/2026-09-30-jarvo-web-lightpanda-nie-renderuje-three-js-")
    fm, tresc = w.podziel((sk.root / f"{rel}.md").read_text(encoding="utf-8"))
    assert fm["szkic"] is True and fm["typ"] == "fakt" and fm["zrodlo"] == "karta t_8f2" and fm["tagi"] == ["web"] and tresc.startswith("# Lightpanda")
    with pytest.raises(ValueError, match="sekret"):
        w.zapisz_szkic(sk, "fakt", "Klucz", "AKIA" + "A1B2C3D4E5F6G7H8", "karta", "jarvo-web")
    with pytest.raises(ValueError, match="typ spoza schematu"):
        w.zapisz_szkic(sk, "hub", "X", "Y", "karta", "jarvo-web")
    with pytest.raises(ValueError, match="źródło"):
        w.zapisz_szkic(sk, "fakt", "X", "Y", "", "jarvo-web")
    assert w.main(["--skarbiec", str(sk.root), "--stan", str(sk.stan), "zapisz", "--typ", "fakt", "--tytul", "T", "--tresc", "hasło: tajne123", "--zrodlo", "x"]) == 3
    assert "sekret" in capsys.readouterr().err


def test_orzeczenie_mapuje_profil_i_zapisuje_punkt(skarbiec):
    sk = skarbiec
    linia = w.dodaj_orzeczenie(sk, "jarvo-web", "W stronach użytkownika nie używaj innerHTML", "rozmowa HQ, karta t_3a1")
    assert linia == "- 2026-09-30 · [web] W stronach użytkownika nie używaj innerHTML. (źródło: rozmowa HQ, karta t_3a1)"
    assert linia in (sk.root / "orzeczenia/web.md").read_text(encoding="utf-8")
    w.dodaj_orzeczenie(sk, "wszyscy", "Odpowiadaj po polsku.", "człowiek")
    assert "[wszyscy] Odpowiadaj po polsku." in (sk.root / "orzeczenia/wszyscy.md").read_text(encoding="utf-8")
    w.dodaj_orzeczenie(sk, "marki/Acme", "Przyciski zaokrąglone", "rozmowa")
    assert (sk.root / "orzeczenia/marki/acme.md").exists()
    with pytest.raises(ValueError):
        w.dodaj_orzeczenie(sk, "web", "x" * 401, "")
    with pytest.raises(ValueError, match="sekret"):
        w.dodaj_orzeczenie(sk, "web", "token: " + "a1b2c3d4" * 3, "")
    assert "## [2026-09-30] orzeczenie | orzeczenia/web" in (sk.root / "LOG.md").read_text(encoding="utf-8")
    if GIT:
        log = subprocess.run(["git", "-C", str(sk.root), "log", "--format=%s"], capture_output=True, text=True).stdout
        assert log.splitlines()[0] == "orzeczenie: acme" and "zasiew skarbca" in log
        assert sk.cofnij().startswith("cofnięto punkt zapisu: orzeczenie: acme")
        assert not (sk.root / "orzeczenia/marki/acme.md").exists()


def test_czytaj_tylko_w_skarbcu(skarbiec, capsys):
    sk = skarbiec
    with pytest.raises(ValueError):
        sk.plik("../../etc/passwd")
    assert w.main(["--skarbiec", str(sk.root), "--stan", str(sk.stan), "czytaj", "../fleet.json"]) == 2
    assert w.main(["--skarbiec", str(sk.root), "--stan", str(sk.stan), "czytaj", "orzeczenia/web", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["tytul"] == "Orzeczenia: Web" and out["fm"]["typ"] == "orzeczenia"


def test_graf_i_status(skarbiec, capsys):
    sk = skarbiec
    notatka(sk, "pojecia/bramka jakości", "Bramka jakości", "Blokuje przy KRYTYCZNE.", typ="pojecie", linki=["pojecia/_hub-pojecia", "agenci/jarvo-web/_hub-web"])
    assert w.main(["--skarbiec", str(sk.root), "--stan", str(sk.stan), "indeksuj"]) == 0
    assert w.main(["--skarbiec", str(sk.root), "--stan", str(sk.stan), "graf"]) == 0
    graf = json.loads(capsys.readouterr().out.splitlines()[-1])
    wezly = {n["id"]: n for n in graf["wezly"]}
    assert wezly["pojecia/_hub-pojecia"]["hub"] and wezly["pojecia/bramka jakości"]["folder"] == "pojecia"
    assert not any(n["id"].startswith("zrodla/") for n in graf["wezly"])
    reczne = [l for l in graf["linki"] if l["z"] == "pojecia/bramka jakości"]
    assert {l["do"] for l in reczne} == {"pojecia/_hub-pojecia", "agenci/jarvo-web/_hub-web"} and not any(l["auto"] for l in reczne)
    assert any(l["z"] == "pojecia/_hub-pojecia" and l["do"] == "pojecia/bramka jakości" and l["auto"] for l in graf["linki"])   # lista huba
    r = w.status(sk, w.Indeks(sk))
    assert r["wg_folderu"]["pojecia"] == 2 and r["git"] == GIT and r["ostatni_wpis"] == "2026-09-30 zasiew"


def test_nazwy_i_frontmatter():
    assert w.nazwa_pliku("Bramka jakości: blokuje przy KRYTYCZNE/WYSOKIE!") == "bramka jakości blokuje przy krytyczne wysokie"
    assert w.nazwa_pliku("  M&W showcase, audyt 2026-09-30 ") == "m w showcase, audyt 2026-09-30"
    assert len(w.nazwa_pliku("x" * 100)) == 70 and w.slug_ascii("Łowca leadów: KRS") == "lowca-leadow-krs"
    fm = {"typ": "fakt", "tagi": ["a", "b"], "zrodlo": "karta t_1: audyt", "szkic": True, "pusty": ""}
    fm2, tresc = w.podziel(w.sklej(fm, "# T\n\ntreść\n"))
    assert fm2 == fm and tresc == "# T\n\ntreść\n"
    assert w.podziel("bez frontmatteru") == ({}, "bez frontmatteru")
    assert w.zawiera_sekret("hasło: qwerty12") == "hasło w tekście" and w.zawiera_sekret("zwykły tekst o hasłach") is None
    assert w.Indeks.zapytanie("Jak jest z wydajnością strony?") == '"jak"*' if False else '"wydajnością"* OR "strony"*' in w.Indeks.zapytanie("Jak jest z wydajnością strony?")


def test_skille_floty_to_wezly_grafu(skarbiec, tmp_path):
    """Każdy skill floty (własny i wspólny) to notatka-węzeł w `fleet/skille/`: linki do hubów agentów, powiązanych skilli
    i skryptów; poza domyślnym szukaniem i przypomnieniami (folder="fleet" je zwraca); zmienia się tylko ze skillem."""
    sk = skarbiec
    fleet = json.loads((tmp_path / "fleet.json").read_text(encoding="utf-8"))
    fleet["agents"][0]["skills"] = [
        {"name": "intake", "description": "Intake: rozumie zlecenie.", "path": "profiles/jarvo/skills/fleet/intake/SKILL.md",
         "version": "1.1.0", "reviewed": "2026-10-02", "related": ["dispatch-playbook", "wywiad"], "mentions": ["schemat", "liczby"],
         "scripts": ["patrol.py"], "sections": ["Kroki", "Format"]},
        {"name": "schemat", "description": "Schemat w rozmowie.", "path": "profiles/jarvo/skills/fleet/schemat/SKILL.md"}]
    graf_kodu = {"name": "graf-kodu", "description": "Mapa kodu.", "path": "shared/skills/graf-kodu/SKILL.md"}
    fleet["agents"][1]["shared_skills"] = [graf_kodu]
    fleet["agents"][2]["shared_skills"] = [graf_kodu]
    (tmp_path / "fleet.json").write_text(json.dumps(fleet, ensure_ascii=False), encoding="utf-8")
    r = w.zasiej(sk, fleet, None, None)
    assert r["skille"] == 3                       # intake (nowe dane), schemat i graf-kodu; nowa-strona bez zmian
    intake = sk.wczytaj("fleet/skille/intake")
    assert intake.typ == "skill" and intake.fm["status"] == "generowane" and intake.fm["agent"] == "jarvo"
    assert intake.fm["zrodlo"] == "profiles/jarvo/skills/fleet/intake/SKILL.md" and intake.streszczenie.startswith("Intake")
    assert "[[agenci/jarvo/_hub-jarvo|Jarvo]]" in intake.tresc and "[[fleet/skille/schemat|schemat]]" in intake.tresc
    assert "`dispatch-playbook`" in intake.tresc and "liczby" not in intake.tresc   # wzmianka bez skilla: pomijana
    assert "skrypty: `patrol.py`" in intake.tresc and "wersja 1.1.0 · przejrzany 2026-10-02" in intake.tresc
    wspolny = sk.wczytaj("fleet/skille/graf-kodu")
    assert "agent" not in wspolny.fm and "[[agenci/jarvo-web/_hub-web|Web]], [[agenci/jarvo-lowca/_hub-łowca|Łowca]]" in wspolny.tresc
    assert "skille wspólne floty (1): [[fleet/skille/graf-kodu|graf-kodu]]" in (sk.root / "agenci/jarvo-web/_hub-web.md").read_text(encoding="utf-8")
    ix = w.Indeks(sk)
    try:
        ix.odswiez()
        g = ix.graf()
        assert {"fleet/skille/intake", "fleet/skille/graf-kodu"} <= {n["id"] for n in g["wezly"]}
        krawedzie = {(l["z"], l["do"]) for l in g["linki"]}
        assert ("agenci/jarvo/_hub-jarvo", "fleet/skille/intake") in krawedzie
        assert ("fleet/skille/intake", "fleet/skille/schemat") in krawedzie
        assert not [x for x in ix.szukaj("intake zlecenie") if x["typ"] == "skill"]           # przypomnienia bez skilli
        assert [x["sciezka"] for x in ix.szukaj("intake zlecenie", folder="fleet")] == ["fleet/skille/intake"]
        assert "- skille floty: 4 notatek w `fleet/skille/`" in (w.zbuduj_index(sk, ix) and (sk.root / "INDEX.md").read_text(encoding="utf-8"))
        raport = w.lint(sk, ix)
        assert not [x for x in raport["bledy"] + raport["ostrzezenia"] if "fleet/skille" in x]
    finally:
        ix.zamknij()
    assert w.zasiej(sk, fleet, None, None)["skille"] == 0                 # bez zmian w skillach: pliki nietknięte
    fleet["agents"][0]["skills"] = fleet["agents"][0]["skills"][:1]
    assert w.zasiej(sk, fleet, None, None)["skille"] == 2                 # intake bez linku do schematu + schemat usunięty
    assert not sk.istnieje("fleet/skille/schemat") and "fleet/skille/schemat" not in sk.wczytaj("fleet/skille/intake").tresc
