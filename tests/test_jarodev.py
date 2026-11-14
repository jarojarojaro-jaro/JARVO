"""Agent biznesowy Jarodev (profiles/jarvo-jarodev, docs/LEADY.md „Agent biznesowy Jarodev”): lejek.py (duplikaty,
statusy ze zgodą, art. 398 PKE, RODO, retencja, limity dnia), poranek.py (rutyna bez modelu), wygrane.py (3 łatwe
wygrane z wyników seo_check i Lighthouse z pliku, bez sieci) i wpis agenta biznesowego we fleet.yaml."""
from __future__ import annotations

import json

import pytest
from conftest import REPO, load_script

SKRYPTY = "profiles/jarvo-jarodev/scripts"
lejek = load_script(f"{SKRYPTY}/lejek.py", "lejek")              # nazwa jak przy imporcie z poranek.py
poranek = load_script(f"{SKRYPTY}/poranek.py", "jarvo_test_jarodev_poranek")
wygrane = load_script(f"{SKRYPTY}/wygrane.py", "jarvo_test_jarodev_wygrane")

POST = "https://www.facebook.com/groups/strony.zlecenia/posts/123456789/?__cft__[0]=AZX&__tn__=%2CO%2CP-R&mibextid=abc"


@pytest.fixture
def kat(tmp_path, monkeypatch):
    monkeypatch.setenv("JARODEV_DZIS", "2026-11-14")
    return tmp_path / "jarvo-jarodev" / "lejek"


def run(kat, *argv: str) -> int:
    return lejek.main(["--katalog", str(kat), *argv])


def dodaj_osobe(kat, link=POST, nazwa="Anna K.", data="2026-11-13") -> int:
    return run(kat, "dodaj", "--zrodlo", "fb-grupa", "--rodzaj", "osoba", "--nazwa", nazwa, "--link", link,
               "--potrzeba", "strona dla kwiaciarni z zamówieniami", "--data", data)


def wpisy(kat) -> list[dict]:
    return json.loads((kat / "lejek.json").read_text(encoding="utf-8"))["wpisy"]


def test_init_zaklada_lejek_i_wzor_zrodel_bez_nadpisywania(kat, capsys):
    assert run(kat, "init") == 0
    zrodla = kat.parent / "zrodla.yaml"
    tekst = zrodla.read_text(encoding="utf-8")
    assert "grupy_fb: []" in tekst and "portale: []" in tekst and "właściciel" in tekst
    assert (kat / "lejek.json").exists() and (kat / "lejek.csv").read_text(encoding="utf-8").startswith("id,status,")
    zrodla.write_text("grupy_fb:\n  - {nazwa: Strony, link: https://www.facebook.com/groups/x}\n", encoding="utf-8")
    assert run(kat, "init") == 0
    assert "nie nadpisuję" in capsys.readouterr().out.splitlines()[-1]
    assert zrodla.read_text(encoding="utf-8").startswith("grupy_fb:\n  - ")       # wpis właściciela został


def test_dodaj_odsiewa_duplikaty_po_linku_bez_sledzenia(kat, capsys):
    assert dodaj_osobe(kat) == 0
    # ten sam post z innymi parametrami śledzącymi, z m. i bez końcowego „/”: duplikat
    assert dodaj_osobe(kat, link="https://m.facebook.com/groups/strony.zlecenia/posts/123456789?fbclid=x") == 0
    assert "duplikat" in capsys.readouterr().out
    assert dodaj_osobe(kat, nazwa="Piotr Z.") == 0           # inna osoba, ten sam link (np. link grupy): nowy wpis
    w = wpisy(kat)
    assert [x["id"] for x in w] == ["L-0001", "L-0002"] and w[0]["status"] == "nowy" and w[0]["data"] == "2026-11-13"
    # firma bez linku: nazwa + miasto (wielkość liter i polskie znaki bez znaczenia)
    for nazwa in ("Salon Łucja", "salon lucja"):
        assert run(kat, "dodaj", "--zrodlo", "mapy", "--rodzaj", "firma", "--nazwa", nazwa, "--miasto", "Gliwice",
                   "--potrzeba", "brak strony") == 0
    assert len(wpisy(kat)) == 3


def test_osoba_z_posta_tylko_minimum_danych(kat, capsys):
    """RODO: e-mail albo telefon osoby prywatnej nie trafia do lejka; osoba musi mieć link do posta."""
    for potrzeba in ("strona, pisz anna.k@example.com", "strona, tel. 601 234 567", "strona +48 601-234-567"):
        assert run(kat, "dodaj", "--zrodlo", "fb-grupa", "--rodzaj", "osoba", "--nazwa", "Anna", "--link", POST,
                   "--potrzeba", potrzeba) == 2
    assert "RODO" in capsys.readouterr().err
    assert run(kat, "dodaj", "--zrodlo", "fb-grupa", "--rodzaj", "osoba", "--nazwa", "Anna", "--potrzeba", "strona") == 2
    assert run(kat, "dodaj", "--zrodlo", "fb-grupa", "--rodzaj", "osoba", "--nazwa", "Anna", "--link", "javascript:x",
               "--potrzeba", "strona") == 2
    assert not (kat / "lejek.json").exists()
    # budżet w potrzebie to nie telefon
    assert run(kat, "dodaj", "--zrodlo", "fb-grupa", "--rodzaj", "osoba", "--nazwa", "Anna", "--link", POST,
               "--potrzeba", "sklep, budżet 3 000 - 5 000 zł") == 0


def test_statusy_wymagaja_zgody_i_kanalu(kat, capsys):
    assert dodaj_osobe(kat) == 0
    assert run(kat, "status", "L-0001", "wyslany", "--kanal", "fb-komentarz") == 2      # z nowy nie wolno
    assert run(kat, "status", "L-0001", "szkic", "--uwaga", "out/szkice/L-0001.md") == 0
    assert run(kat, "status", "L-0001", "zaakceptowany") == 3                           # bez zgody właściciela
    assert "„tak” właściciela" in capsys.readouterr().err
    assert run(kat, "status", "L-0001", "zaakceptowany", "--zgoda", "„tak” właściciela w czacie 14.11 10:20") == 0
    assert run(kat, "status", "L-0001", "wyslany") == 2                                 # kanał obowiązkowy
    assert run(kat, "status", "L-0001", "wyslany", "--kanal", "fb-komentarz") == 0
    w = wpisy(kat)[0]
    assert (w["status"], w["kanal"], w["kontakt"]) == ("wyslany", "fb-komentarz", "2026-11-14")
    assert [h["status"] for h in w["historia"]] == ["nowy", "szkic", "zaakceptowany", "wyslany"]
    assert w["historia"][2]["zgoda"].startswith("„tak”")
    assert run(kat, "status", "L-0009", "szkic") == 2


@pytest.mark.parametrize("kanal", ["email", "telefon", "sms", "formularz", "fb-wiadomosc", "fb-komentarz"])
def test_firma_z_map_bez_informacji_handlowej_na_urzadzenie(kat, capsys, kanal):
    """Art. 398 PKE: firma z Map albo audytu nie pytała, więc mail, telefon, SMS, formularz i Messenger to odmowa."""
    assert run(kat, "dodaj", "--zrodlo", "mapy", "--rodzaj", "firma", "--nazwa", "Salon", "--miasto", "Gliwice",
               "--link", "https://maps.google.com/?cid=1", "--potrzeba", "brak strony") == 0
    assert run(kat, "status", "L-0001", "szkic") == 0
    assert run(kat, "status", "L-0001", "zaakceptowany", "--zgoda", "„tak” właściciela") == 0
    assert run(kat, "status", "L-0001", "wyslany", "--kanal", kanal) == 3
    assert "art. 398" in capsys.readouterr().err and wpisy(kat)[0]["status"] == "zaakceptowany"
    assert run(kat, "status", "L-0001", "wyslany", "--kanal", "list") == 0


def test_lista_stats_i_csv(kat, capsys):
    assert dodaj_osobe(kat) == 0 and dodaj_osobe(kat, nazwa="Piotr Z.") == 0
    assert run(kat, "status", "L-0002", "szkic") == 0
    capsys.readouterr()
    assert run(kat, "lista", "--status", "szkic", "--json") == 0
    assert [w["id"] for w in json.loads(capsys.readouterr().out)] == ["L-0002"]
    assert run(kat, "stats", "--json") == 0
    st = json.loads(capsys.readouterr().out)
    assert st["wpisy"] == 2 and st["po_statusie"]["szkic"] == 1 and st["czeka_na_zgode"] == ["L-0002"]
    assert st["konwersja"] is None
    csv = (kat / "lejek.csv").read_text(encoding="utf-8").splitlines()
    assert len(csv) == 3 and "historia" not in csv[0] and "klucz" not in csv[0]


def test_retencja_usuwa_tylko_osoby_bez_kontaktu(kat, capsys):
    assert dodaj_osobe(kat, data="2026-08-01") == 0                                     # stara, bez kontaktu
    assert dodaj_osobe(kat, nazwa="Piotr", data="2026-08-01") == 0                      # stara, z kontaktem
    for status, extra in (("szkic", ()), ("zaakceptowany", ("--zgoda", "tak")), ("wyslany", ("--kanal", "fb-wiadomosc"))):
        assert run(kat, "status", "L-0002", status, *extra) == 0
    assert dodaj_osobe(kat, nazwa="Ewa", data="2026-11-01") == 0                        # świeża
    assert run(kat, "dodaj", "--zrodlo", "mapy", "--rodzaj", "firma", "--nazwa", "Firma", "--miasto", "Gliwice",
               "--potrzeba", "brak strony", "--data", "2026-01-01") == 0                # firma: bez retencji osób
    capsys.readouterr()
    assert run(kat, "retencja") == 0
    assert json.loads(capsys.readouterr().out)["do_usuniecia"] == ["L-0001"] and len(wpisy(kat)) == 4   # podgląd
    assert run(kat, "retencja", "--wykonaj") == 0
    assert [w["id"] for w in wpisy(kat)] == ["L-0002", "L-0003", "L-0004"]


def test_limity_dnia(kat, capsys, monkeypatch):
    for _ in range(3):
        assert run(kat, "licz", "fb-posty", "--limit", "3") == 0
    assert run(kat, "licz", "fb-posty", "--limit", "3", "--sprawdz") == 3                 # 4. ponad limit
    assert run(kat, "licz", "fb-posty", "--limit", "3") == 3
    assert "limit dnia fb-posty: 3/3" in capsys.readouterr().err
    assert run(kat, "licz", "fb-grupy") == 0                                            # domyślny limit 10
    assert run(kat, "licz", "nieznany") == 2
    monkeypatch.setenv("JARODEV_DZIS", "2026-11-15")                                    # nowy dzień: od zera
    capsys.readouterr()
    assert run(kat, "licz", "fb-posty", "--limit", "3") == 0
    assert json.loads(capsys.readouterr().out)["dzis"] == 1


def test_domyslny_katalog_z_hermes_home(tmp_path, monkeypatch):
    for z in ("JARODEV_LEJEK", "JARVO_DATA_DIR"):
        monkeypatch.delenv(z, raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "dane" / "profiles" / "jarvo-jarodev"))
    assert lejek.domyslny_katalog() == tmp_path / "dane" / "jarvo" / "workspaces" / "jarvo-jarodev" / "lejek"
    monkeypatch.setenv("JARVO_DATA_DIR", str(tmp_path / "jd"))
    assert lejek.domyslny_katalog() == tmp_path / "jd" / "workspaces" / "jarvo-jarodev" / "lejek"


def test_poranek_przygotowuje_lejek_i_robi_retencje(kat, capsys):
    assert dodaj_osobe(kat, data="2026-07-01") == 0
    assert dodaj_osobe(kat, nazwa="Ewa", data="2026-11-10") == 0
    assert run(kat, "status", "L-0002", "szkic") == 0
    capsys.readouterr()
    assert poranek.main(["--katalog", str(kat)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert "Czeka na zgodę właściciela (szkic): L-0002" in out[1]
    assert "usunięto 1" in out[2] and "puste: grupy_fb, portale, mapy" in out[3]
    dane = json.loads(out[-1])
    assert dane["retencja_usuniete"] == ["L-0001"] and dane["zrodla"] == {"grupy_fb": 0, "portale": 0, "mapy": 0}
    (kat.parent / "zrodla.yaml").write_text("grupy_fb:\n  - {nazwa: A, link: https://x}\n  - {nazwa: B, link: https://y}\n"
                                            "portale: []\nmapy: [{miasto: Gliwice, branze: [fryzjer]}]\n", encoding="utf-8")
    assert poranek.stan_zrodel(kat.parent / "zrodla.yaml") == {"grupy_fb": 2, "portale": 0, "mapy": 1}


SEO = {"head": {"errors": ["brak meta description"], "warnings": ["title ma 9 znaków (zalecane 15–60): 'Strona'"],
                "info": []},
       "content": {"errors": ["3 obrazy bez alt"], "warnings": [], "info": []},
       "crawl": {"errors": ["brak sitemap.xml"], "warnings": [], "info": []},
       "og": {"errors": ["brak og:image"], "warnings": [], "info": []}}
LH = {"categories": {"performance": {"score": 0.31}},
      "audits": {"largest-contentful-paint": {"numericValue": 6800.0}, "total-byte-weight": {"numericValue": 5.5e6}}}


def test_wygrane_ukladaja_trzy_rozne_obszary_od_szybkosci(tmp_path, capsys):
    (tmp_path / "seo.json").write_text(json.dumps(SEO), encoding="utf-8")
    (tmp_path / "lh.json").write_text(json.dumps(LH), encoding="utf-8")
    out = tmp_path / "audyt"
    assert wygrane.main(["https://salon.pl", "--seo-json", str(tmp_path / "seo.json"), "--lighthouse-json",
                         str(tmp_path / "lh.json"), "--out", str(out), "--json"]) == 0
    wynik = json.loads((out / "wygrane.json").read_text(encoding="utf-8"))
    trzy = wynik["trzy"]
    assert [w["obszar"] for w in trzy] == ["Szybkość na telefonie", "Waga strony", "SEO: nagłówek strony"]
    assert "6.8 s" in trzy[0]["co"] and trzy[2]["co"] == "brak meta description"
    assert len({w["obszar"] for w in trzy}) == 3 and all(w["dowod"] for w in trzy)
    md = (out / "WYGRANE.md").read_text(encoding="utf-8")
    assert "## Trzy łatwe wygrane" in md and "## Pozostałe znaleziska" in md and "brak sitemap.xml" in md


def test_wygrane_bez_lighthouse_i_bez_znalezisk(tmp_path):
    assert [w["obszar"] for w in wygrane.uloz(SEO, None)[:3]] == \
        ["SEO: nagłówek strony", "SEO: treść i nagłówki", "Indeksowanie w Google"]
    assert wygrane.uloz({}, {"categories": {"performance": {"score": 0.95}}, "audits": {}}) == []
    assert "strona jest w dobrym stanie" in wygrane.raport_md("https://x.pl", [], [])
    # wolna, ale bez LCP: wynik wydajności
    assert wygrane.wygrane_szybkosci({"categories": {"performance": {"score": 0.2}}, "audits": {}})[0]["co"] == \
        "wynik wydajności 20/100 na telefonie"


def test_wygrane_strona_nie_odpowiada_kod_3(tmp_path):
    (tmp_path / "seo.json").write_text(json.dumps({"error": "HTTP 503"}), encoding="utf-8")
    assert wygrane.main(["--seo-json", str(tmp_path / "seo.json"), "--out", str(tmp_path / "o")]) == 3
    assert json.loads((tmp_path / "o" / "wygrane.json").read_text(encoding="utf-8"))["blad"] == "HTTP 503"
    with pytest.raises(SystemExit):
        wygrane.main(["https://x.pl"])                                                   # bez --web-skrypty


def test_wygrane_wola_seo_check_weba(tmp_path, monkeypatch):
    """Ścieżka sieciowa bez sieci: seo_check.py z katalogu Weba podmieniony atrapą, która drukuje wynik."""
    web = tmp_path / "web"
    web.mkdir()
    (web / "seo_check.py").write_text(f"import json\nprint(json.dumps({SEO!r}))\n", encoding="utf-8")
    out = tmp_path / "o"
    assert wygrane.main(["https://salon.pl/", "--web-skrypty", str(web), "--out", str(out)]) == 0
    wynik = json.loads((out / "wygrane.json").read_text(encoding="utf-8"))
    assert wynik["zmierzono"] == {"seo": True, "lighthouse": False} and "bez Lighthouse" in wynik["uwagi"][0]
    assert json.loads((out / "seo.json").read_text(encoding="utf-8")) == SEO


def test_jarodev_to_agent_biznesowy_z_marka():
    import fleetlib as fl
    a = fl.load_fleet().agent("jarvo-jarodev")
    assert (a.marka, a.kind, a.handle, a.telegram_topic, a.komputer) == ("jarodev", "specialist", "jarodev", "jarodev", True)
    assert all(not x.marka for x in fl.load_fleet().agents if x.name != "jarvo-jarodev")
    cron = fl.load_yaml(REPO / "profiles/jarvo-jarodev/cron/jobs.yaml")["jobs"]
    assert [j["id"] for j in cron] == ["jarodev-dzien"] and cron[0]["paused"] is True
    assert "kanban" in cron[0]["enabled_toolsets"] and "computer_use" not in cron[0]["enabled_toolsets"]


def test_walidator_pilnuje_marki(monkeypatch):
    import fleetlib as fl
    import validate
    fleet = fl.load_fleet()
    for wpis in fleet.raw["agents"]:
        if wpis["name"] == "jarvo-reka":
            wpis["marka"] = "jarodev"                                      # generalista i druga ta sama marka
        if wpis["name"] == "jarvo-web":
            wpis["marka"] = "Jaro Dev"                                     # zły slug
    fleet2 = fl.Fleet(raw=fleet.raw, agents=[
        fl.Agent(**{**a.__dict__, "marka": str(next(e for e in fleet.raw["agents"] if e["name"] == a.name).get("marka") or "")})
        for a in fleet.agents])
    r = validate.Report()
    validate.check_marki(fleet2, r)
    bledy = "\n".join(r.errors)
    assert "jarvo-web: marka 'Jaro Dev' musi pasować do [a-z0-9-]+" in bledy
    assert "jarvo-reka: marka tylko u specjalisty" in bledy
    assert "jarvo-reka: marka 'jarodev' należy już do jarvo-jarodev" in bledy
