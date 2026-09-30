"""Kompilacja skarbca (wiedza/kompilacja.py) z podstawionym modelem: nowa notatka, aktualizacja, sprzeczność, odrzucenie,
błędny JSON (ponowienie, licznik prób), linki tylko do istniejących ścieżek (hub, sąsiad, inny folder), limity, blokada,
LOG, punkt zapisu git, na sucho."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "wiedza"))
import wiedza as w  # noqa: E402
import kompilacja as k  # noqa: E402

GIT = shutil.which("git") is not None
FLEET = {"orchestrator": "jarvo", "agents": [
    {"name": "jarvo-web", "short": "Web", "title": "Web Senior Dev", "emoji": "🌐", "kind": "specialist", "description": "Strony i SEO.",
     "room": "devlab", "label": "Pracownia", "telegram_topic": "web", "autonomy_max": "A1", "skills": [], "scripts": []}]}


def notatka(sk, rel, tytul, tresc, typ="fakt", zrodlo="karta t_1", linki=(), **fm):
    front = {"typ": typ, "tagi": ["test"], "utworzono": "2026-09-01", "zmieniono": "2026-09-01", "status": "aktualna", "zrodlo": zrodlo, **fm}
    pow = "\n".join(f"- [[{l}]]" for l in linki)
    sk.zapisz_plik(rel, w.sklej(front, f"# {tytul}\n\n**{tresc}**\n\n## Powiązane\n{pow}\n"))


@pytest.fixture
def sk(tmp_path, monkeypatch):
    monkeypatch.setenv("WIEDZA_DZIS", "2026-09-30")
    root = tmp_path / "knowledge"
    fleet = tmp_path / "fleet.json"
    fleet.write_text(json.dumps(FLEET, ensure_ascii=False), encoding="utf-8")
    assert w.main(["--skarbiec", str(root), "--stan", str(tmp_path / "state"), "zasiej", "--fleet", str(fleet)]) == 0
    sk = w.Skarbiec(root, tmp_path / "state")
    notatka(sk, "pojecia/audyt strony", "Audyt strony", "Audyt strony to Lighthouse, axe i linkinator.", typ="pojecie",
            linki=["pojecia/_hub-pojecia", "agenci/jarvo-web/_hub-web"])
    notatka(sk, "agenci/jarvo-web/lightpanda nie renderuje three.js", "Lightpanda nie renderuje three.js",
            "Zrzuty stron z WebGL robimy Chromium.", linki=["agenci/jarvo-web/_hub-web", "pojecia/audyt strony"], agent="jarvo-web")
    w.main(["--skarbiec", str(root), "--stan", str(tmp_path / "state"), "indeksuj"])
    return sk


def szkic(sk, typ, tytul, tresc, zrodlo="karta t_9", agent="jarvo-web"):
    return w.zapisz_szkic(sk, typ, tytul, tresc, zrodlo, agent, ["web"], skad="test")


def model_z(odpowiedzi):
    """Model zwracający kolejne odpowiedzi (str albo dict) i zapisujący prompty."""
    prompty = []
    kolejka = list(odpowiedzi)

    def f(system, user):
        prompty.append(user)
        o = kolejka.pop(0) if kolejka else {"wyniki": []}
        return o if isinstance(o, str) else json.dumps(o, ensure_ascii=False)
    f.prompty = prompty
    return f


def test_nowa_aktualizacja_sprzecznosc_odrzucenie(sk):
    szkic(sk, "lekcja", "Zrzuty mobile zawsze przed oddaniem", "Sędzia odsyła strony bez zrzutów mobile.")
    szkic(sk, "fakt", "Lightpanda a WebGL", "Lightpanda od wersji 0.5 renderuje WebGL, więc Chromium nie jest potrzebne.", zrodlo="karta t_10")
    szkic(sk, "fakt", "Audyt strony: linkinator", "Linkinator sprawdza także obrazy.", zrodlo="karta t_11")
    szkic(sk, "fakt", "Szum", "Dzisiaj jest ładna pogoda.", zrodlo="rozmowa x")
    model = model_z([
        {"wyniki": [{"decyzja": "nowa", "sciezka": "agenci/jarvo-web/zrzuty mobile: zawsze przed oddaniem", "typ": "lekcja", "tytul": "Zrzuty mobile zawsze przed oddaniem",
                     "streszczenie": "Strona bez zrzutów mobile wraca od sędziego", "tresc": "Przed oddaniem robimy zrzuty 375 i 768 px. " * 4,
                     "tagi": ["web", "qa"], "linki": ["pojecia/audyt strony", "nie/istnieje", "agenci/jarvo-web/_hub-web"], "wazne_do": None, "powod": "nowa lekcja"}]},
        {"wyniki": [{"decyzja": "sprzecznosc", "sciezka": "agenci/jarvo-web/lightpanda nie renderuje three.js", "typ": "fakt", "tytul": "Lightpanda a WebGL",
                     "streszczenie": "Lightpanda 0.5 renderuje WebGL", "tresc": "Nowe źródło twierdzi, że Chromium nie jest już potrzebne.", "tagi": [], "linki": [], "wazne_do": "2026-12-31", "powod": "przeczy notatce"}]},
        {"wyniki": [{"decyzja": "aktualizacja", "sciezka": "pojecia/audyt strony", "typ": "pojecie", "tytul": "Audyt strony",
                     "streszczenie": "Audyt strony to Lighthouse, axe i linkinator, także obrazy", "tresc": "Linkinator sprawdza linki i obrazy. Lighthouse mierzy wydajność.",
                     "tagi": ["seo"], "linki": ["agenci/jarvo-web/lightpanda nie renderuje three.js"], "wazne_do": None, "powod": "uzupełnienie"}]},
        {"wyniki": [{"decyzja": "odrzuc", "powod": "szum bez wartości"}]},
    ])
    r = k.Kompilacja(sk, model).uruchom()
    assert (r["nowe"], r["aktualizacje"], r["sprzeczne"], r["odrzucone"], r["bledy"]) == (1, 1, 1, 1, 0)
    assert "KANDYDACI" in model.prompty[0] and "[agenci/jarvo-web/lightpanda nie renderuje three.js]" in model.prompty[1]
    # nowa: ścieżka z nazwą pliku bez znaków zakazanych, hub + sąsiad + inny folder, bez martwych linków
    nowa = sk.root / "agenci/jarvo-web/zrzuty mobile zawsze przed oddaniem.md"
    fm, tresc = w.podziel(nowa.read_text(encoding="utf-8"))
    assert fm["typ"] == "lekcja" and fm["zrodlo"] == "karta t_9" and fm["agent"] == "jarvo-web" and fm["utworzono"] == "2026-09-30"
    assert tresc.startswith("# Zrzuty mobile zawsze przed oddaniem\n\n**Strona bez zrzutów mobile wraca od sędziego.**")
    assert "- hub: [[agenci/jarvo-web/_hub-web]]" in tresc and "[[pojecia/audyt strony]]" in tresc and "nie/istnieje" not in tresc
    assert "[[agenci/jarvo-web/lightpanda nie renderuje three.js]]" in tresc            # sąsiad dobrany automatycznie
    # sprzeczność: obie wersje, status sprzeczna, źródła połączone
    fm2, tresc2 = w.podziel((sk.root / "agenci/jarvo-web/lightpanda nie renderuje three.js.md").read_text(encoding="utf-8"))
    assert fm2["status"] == "sprzeczna" and fm2["zrodlo"] == "karta t_1; karta t_10" and fm2["zmieniono"] == "2026-09-30" and fm2["utworzono"] == "2026-09-01"
    assert "Zrzuty stron z WebGL robimy Chromium." in tresc2 and "## Sprzeczność (2026-09-30)" in tresc2 and "(źródło: karta t_10)" in tresc2
    assert tresc2.index("## Sprzeczność") < tresc2.index("## Powiązane")
    # aktualizacja: stare linki ręczne zostają, nowe dochodzą, tagi scalone
    fm3, tresc3 = w.podziel((sk.root / "pojecia/audyt strony.md").read_text(encoding="utf-8"))
    assert fm3["tagi"] == ["test", "seo"] and fm3["zrodlo"] == "karta t_1; karta t_11" and "Linkinator sprawdza linki i obrazy." in tresc3
    assert "[[agenci/jarvo-web/_hub-web]]" in tresc3 and "- hub: [[pojecia/_hub-pojecia]]" in tresc3
    # szkice przeniesione, INDEX i listy hubów odświeżone, LOG, git
    assert not list((sk.root / "skrzynka").glob("*.md")) and len(list((sk.root / "skrzynka/zrobione").glob("*.md"))) == 4
    assert "zrzuty mobile zawsze przed oddaniem" in (sk.root / "INDEX.md").read_text(encoding="utf-8")
    assert "[[agenci/jarvo-web/zrzuty mobile zawsze przed oddaniem|" in (sk.root / "agenci/jarvo-web/_hub-web.md").read_text(encoding="utf-8")
    log = (sk.root / "LOG.md").read_text(encoding="utf-8")
    assert "## [2026-09-30] kompilacja | szkice: 4 · nowe: 1 · aktualizacje: 1 · sprzeczne: 1 · odrzucone: 1 · błędy: 0" in log
    assert "odrzucony (szum bez wartości)" in log and "sprzeczność w [[agenci/jarvo-web/lightpanda nie renderuje three.js]]" in log
    assert r["git"] == GIT and not (sk.stan / "wiedza.lock").exists()
    assert json.loads((sk.stan / "wiedza-kompilacja.json").read_text(encoding="utf-8"))["raport"]["nowe"] == 1
    ix = w.Indeks(sk)
    lint = w.lint(sk, ix)
    assert lint["bledy"] == []
    ix.zamknij()


def test_rozmowa_daje_kilka_notatek_i_zly_folder_jest_poprawiany(sk):
    szkic(sk, "rozmowa", "Landing Acme w Astro", "## Decyzje\n- landing w Astro\n## Fakty\n- Acme sprzedaje kotły", zrodlo="zrodla/rozmowy/x")
    model = model_z([{"wyniki": [
        {"decyzja": "nowa", "sciezka": "rozmowy/landing acme w astro", "typ": "rozmowa", "tytul": "Landing Acme w Astro", "streszczenie": "Ustalono stack landingu Acme", "tresc": "Landing w Astro. " * 6, "tagi": [], "linki": [], "wazne_do": None, "powod": "rozmowa"},
        {"decyzja": "nowa", "sciezka": "zly/folder/acme sprzedaje kotły", "typ": "podmiot", "tytul": "Acme sprzedaje kotły", "streszczenie": "Acme to producent kotłów", "tresc": "Kotły gazowe i pompy ciepła. " * 5, "tagi": [], "linki": [], "wazne_do": None, "powod": "fakt o firmie"},
        {"decyzja": "nowa", "sciezka": "", "typ": "decyzja", "tytul": "Astro dla landingów", "streszczenie": "Landingi robimy w Astro", "tresc": "Bo statyczne i szybkie. " * 5, "tagi": [], "linki": ["agenci/jarvo-web/_hub-web"], "wazne_do": None, "powod": "decyzja"},
        {"decyzja": "aktualizacja", "sciezka": "pojecia/_hub-pojecia", "typ": "pojecie", "tytul": "Hub", "streszczenie": "x", "tresc": "próba nadpisania huba", "tagi": [], "linki": [], "wazne_do": None, "powod": "zła"},
    ]}])
    r = k.Kompilacja(sk, model).uruchom()
    assert r["nowe"] == 4 and r["bledy"] == 0
    assert (sk.root / "rozmowy/landing acme w astro.md").exists()
    assert (sk.root / "podmioty/acme sprzedaje kotły.md").exists()                 # zły folder → z typu
    assert (sk.root / "projekty/astro dla landingów.md").exists()                    # decyzja → projekty/
    assert (sk.root / "pojecia/hub.md").exists() and "próba nadpisania huba" not in (sk.root / "pojecia/_hub-pojecia.md").read_text(encoding="utf-8")
    fm, tresc = w.podziel((sk.root / "rozmowy/landing acme w astro.md").read_text(encoding="utf-8"))
    assert "- hub: [[rozmowy/_hub-rozmowy]]" in tresc and fm["agent"] == "jarvo-web"


def test_zly_json_ponowienie_licznik_prob_i_odrzucenie_sekretu(sk):
    p = sk.root / f"{szkic(sk, 'fakt', 'Coś', 'Treść czegoś.')}.md"
    model = model_z(["to nie jest json", "nadal nie"])
    r = k.Kompilacja(sk, model).uruchom()
    assert r["bledy"] == 1 and len(model.prompty) == 2 and "wyłącznie poprawnym JSON" in model.prompty[1]
    assert p.exists() and int(w.podziel(p.read_text(encoding="utf-8"))[0]["proby"]) == 1
    for _ in range(2):
        k.Kompilacja(sk, model_z(["x", "y"])).uruchom()
    assert not p.exists() and (sk.root / "skrzynka/zrobione" / p.name).exists()
    assert "odrzucony po 3 nieudanych próbach modelu" in (sk.root / "LOG.md").read_text(encoding="utf-8")
    szkic(sk, "fakt", "Klucz", "Zwykła treść.")
    r = k.Kompilacja(sk, model_z([{"wyniki": [{"decyzja": "nowa", "sciezka": "pojecia/klucz", "typ": "fakt", "tytul": "Klucz", "streszczenie": "sk_live_" + "Q7w" * 8, "tresc": "x", "tagi": [], "linki": [], "wazne_do": None, "powod": "p"}]}])).uruchom()
    assert r["odrzucone"] == 1 and not (sk.root / "pojecia/klucz.md").exists()
    r = k.Kompilacja(sk, model_z([RuntimeError])).uruchom()                          # brak szkiców: model nie jest wołany
    assert r["szkice"] == 0


def test_limity_blokada_i_na_sucho(sk):
    for i in range(3):
        szkic(sk, "fakt", f"Fakt {i}", f"Treść faktu numer {i}.")
    r = k.Kompilacja(sk, None).uruchom()                                             # na sucho: bez zapisu, lista kandydatów
    assert r["na_sucho"] and r["nowe"] == 0 and len(r["wpisy"]) == 3 and "kandydaci:" in r["wpisy"][0]
    assert len(list((sk.root / "skrzynka").glob("*.md"))) == 3
    (sk.stan / "wiedza.lock").write_text("1 0\n", encoding="utf-8")
    r = k.Kompilacja(sk, model_z([])).uruchom()
    assert r["zablokowana"] and len(list((sk.root / "skrzynka").glob("*.md"))) == 3
    (sk.stan / "wiedza.lock").unlink()
    odp = {"wyniki": [{"decyzja": "nowa", "sciezka": "pojecia/x", "typ": "fakt", "tytul": "X", "streszczenie": "x", "tresc": "y", "tagi": [], "linki": [], "wazne_do": None, "powod": "p"}]}
    r = k.Kompilacja(sk, model_z([odp, odp, odp]), limit_szkicow=2).uruchom()
    assert r["pominiete"] == 1 and len(list((sk.root / "skrzynka").glob("*.md"))) == 1
    r = k.Kompilacja(sk, model_z([odp]), limit_notatek=0).uruchom()
    assert r["pominiete"] == 1 and r["nowe"] == 0


def test_cli_na_sucho(sk, capsys):
    szkic(sk, "fakt", "Fakt", "Treść.")
    assert k.main(["--skarbiec", str(sk.root), "--stan", str(sk.stan), "--na-sucho"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("na sucho: szkice: 1") and "kandydaci:" in out
    assert k._json_z_odpowiedzi('```json\n{"decyzja": "odrzuc", "powod": "x"}\n```') == {"wyniki": [{"decyzja": "odrzuc", "powod": "x"}]}
    assert k._json_z_odpowiedzi("Oto wynik: {\"wyniki\": []} dziękuję") == {"wyniki": []} and k._json_z_odpowiedzi("nic") is None


def test_sprzatanie_zrobione_po_30_dniach(sk):
    import os, time
    kat = sk.root / "skrzynka" / "zrobione"
    kat.mkdir(parents=True, exist_ok=True)
    stary, nowy = kat / "stary.md", kat / "nowy.md"
    stary.write_text("x", encoding="utf-8")
    nowy.write_text("y", encoding="utf-8")
    dawno = time.time() - 40 * 86400
    os.utime(stary, (dawno, dawno))
    szkic(sk, "fakt", "Coś", "Treść.")
    odp = {"wyniki": [{"decyzja": "odrzuc", "powod": "test"}]}
    r = k.Kompilacja(sk, model_z([odp])).uruchom()
    assert r["sprzatniete"] == 1 and not stary.exists() and nowy.exists()
