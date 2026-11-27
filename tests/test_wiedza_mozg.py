"""Mózg Jarva (docs/WIEDZA.md §2a, §2b, §6a): jedna definicja folderów, tożsamość i mapa w skarbcu, lustro pamięci Hermesa
po treści pliku, zapis pamięci z Mózgu (GET/PUT /pamiec, format i blokada Hermesa), archiwum i przeniesienie z
przepisaniem linków, streszczenia hubów, sekcje w indeksie, routing kompilatora (atrapa modelu) i cały obieg wiedzy
end to end: pamięć → lustro → szkic → kompilacja → indeks → przypomnienie w nowej sesji → graf Mózgu, oraz edycja
w Mózgu → plik Hermesa → lustro → przypomnienie."""
import glob
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "wiedza"))
import kompilacja as k  # noqa: E402
import mapa  # noqa: E402
import wiedza as w  # noqa: E402
from test_wiedza_plugin import pl  # noqa: E402  (stub interfejsu Hermesa i moduł wtyczki)

spec = importlib.util.spec_from_file_location("jarvo_wiedza_panel_mozg", REPO / "wiedza" / "plugin" / "dashboard" / "panel.py")
pm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pm)

FLEET = {"orchestrator": "jarvo", "agents": [
    {"name": "jarvo", "short": "Jarvo", "title": "Main Judge", "emoji": "🛰️", "kind": "orchestrator", "description": "Szef floty.",
     "room": "bridge", "label": "Mostek", "telegram_topic": "general", "autonomy_max": "A1", "skills": [], "scripts": []},
    {"name": "jarvo-web", "short": "Web", "title": "Web Senior Dev", "emoji": "🌐", "kind": "specialist", "description": "Strony i SEO.",
     "room": "devlab", "label": "Pracownia", "telegram_topic": "web", "autonomy_max": "A1", "handle": "web",
     "skills": [{"name": "nowa-strona", "description": "Nowa strona."}], "scripts": []}]}
SOUL = "# Jarvo\n\n## Charakter\nJestem prawą ręką JARO.\n"
ZASADY = ("<critical>\nZasady na start.\n</critical>\n\n# Zasady\n\n## Jak pracuję\nNajpierw dowód.\n\n<critical>\nDowód albo "
          "„(przypuszczam)”.\n</critical>\n")
MAPA = ("## Kim jestem\nJestem Jarvo, szef floty.\n\n<!-- Jarvo:RDZEN -->\n- Profil `jarvo` Hermesa, orkiestrator.\n"
        "<!-- /Jarvo:RDZEN -->\n\n## Gdzie co jest\nDane leżą w katalogu danych.\n\n<!-- Jarvo:GEN sciezki -->\n"
        "<!-- /Jarvo:GEN sciezki -->\n\n- Kopia skarbca idzie co godzinę na prywatny GitHub (`kopia-jarva`).\n\n"
        "## Kiedy\nRutyny chodzą same.\n\n<!-- Jarvo:GEN harmonogram -->\n<!-- /Jarvo:GEN harmonogram -->\n\n"
        "## Słownik\nNazwy właściciela.\n\n- „One” na końcu wiadomości: temat poboczny, teczka w `missions/poboczne/`.\n")
MAPA_NAKL = "## Kim jestem\nPracuję dla JARO z Enigmalabz.\n\n<!-- Jarvo:RDZEN -->\n- Strony JARO na SEOHost.\n<!-- /Jarvo:RDZEN -->\n"


def _hermes_python() -> str | None:
    """Python z venvu Hermesa (instalacja natywna albo HERMES_SRC): test zgodności z prawdziwym narzędziem memory."""
    for src in [os.environ.get("HERMES_SRC") or "", "/opt/hermes",
                *sorted(glob.glob(os.path.expanduser("~/.local/share/jarvo/program/hermes/*")))]:
        py = Path(src) / ".venv" / "bin" / "python"
        if src and (Path(src) / "tools" / "memory_tool_store.py").is_file() and py.is_file():
            return str(py)
    return None


@pytest.fixture
def dane(tmp_path, monkeypatch):
    """Układ danych natywnych: <dane>/jarvo/{knowledge,state}, <dane>/profiles/jarvo/memories, build/wiedza/tozsamosc."""
    monkeypatch.setenv("WIEDZA_DZIS", "2026-11-20")
    monkeypatch.delenv("JARVO_KNOWLEDGE_DIR", raising=False)
    monkeypatch.delenv("JARVO_STATE_DIR", raising=False)
    d = tmp_path / "dane"
    profil = d / "profiles" / "jarvo"
    (profil / "memories").mkdir(parents=True)
    (profil / "config.yaml").write_text("model:\n  default: x\nmemory:\n  memory_char_limit: 300\n  user_char_limit: 200\n"
                                        "  provider: jarvo-wiedza\n", encoding="utf-8")
    (profil / "memories" / "MEMORY.md").write_text("Patrol co 30 minut\n§\nBrief o 07:50", encoding="utf-8")
    (profil / "memories" / "USER.md").write_text("JARO pisze krótko", encoding="utf-8")
    (profil / "cron").mkdir()
    (profil / "cron" / "jobs.json").write_text(json.dumps({"jobs": [
        {"id": "jarvo-daily-brief", "name": "Poranny brief", "enabled": True, "schedule": {"kind": "cron", "expr": "50 7 * * *"},
         "deliver": "telegram:-1:1"},
        {"id": "jarvo-dzien", "name": "Dzień Jarodev", "enabled": False, "schedule": {"kind": "cron", "expr": "40 8 * * 1-6"}}]}),
        encoding="utf-8")
    toz = tmp_path / "build" / "wiedza" / "tozsamosc"
    toz.mkdir(parents=True)
    for nazwa, tekst in (("SOUL.md", SOUL), ("ZASADY.md", ZASADY.rsplit("<critical>", 1)[0]),
                         ("KRYTYCZNE.md", "<critical>\nDowód albo „(przypuszczam)”.\n</critical>\n"), ("MAPA.md", MAPA),
                         ("MAPA-nakladka.md", MAPA_NAKL)):
        (toz / nazwa).write_text(tekst, encoding="utf-8")
    (toz / "zrodla.json").write_text(json.dumps({"SOUL.md": {"plik": "profiles/jarvo/SOUL.md", "zmieniono": "2026-11-20"},
                                                 "MAPA.md": {"plik": "profiles/jarvo/MAPA.md", "zmieniono": "2026-11-19"}}),
                                     encoding="utf-8")
    fleet = tmp_path / "build" / "wiedza" / "fleet.json"
    fleet.write_text(json.dumps(FLEET, ensure_ascii=False), encoding="utf-8")
    root, stan = d / "jarvo" / "knowledge", d / "jarvo" / "state"
    root.mkdir(parents=True)
    assert w.main(["--skarbiec", str(root), "--stan", str(stan), "zasiej", "--fleet", str(fleet), "--tozsamosc", str(toz)]) == 0
    return {"dane": d, "profil": profil, "sk": w.Skarbiec(root, stan), "toz": toz, "fleet": fleet, "tmp": tmp_path}


def _cli(dane, *args) -> int:
    sk = dane["sk"]
    return w.main(["--skarbiec", str(sk.root), "--stan", str(sk.stan), *args])


# --------------------------------------------------------------- jedna definicja folderów

def test_jedna_definicja_folderow():
    """FOLDERY_SKARBCA: z niej huby, opisy, foldery kompilatora, zakres wyszukiwania i lista zasiewu (bez kopii list)."""
    assert list(w.HUBY) == [f for f, d in w.FOLDERY_SKARBCA.items() if d["hub"]]
    assert set(w.FOLDERY_NOTATEK) == {"user", "projekty", "podmioty", "pojecia", "bledy", "rozmowy"}
    assert w.POZA_WYSZUKIWANIEM == ("zrodla/", "skrzynka/", "archiwum/")
    assert {w.TOZSAMOSC, w.ARCHIWUM} <= set(w.FOLDERY_SKARBCA) and "wycofana" in w.STATUSY and "tozsamosc" in w.TYPY
    assert all(f in w.FOLDERY for f in w.FOLDERY_SKARBCA if f)
    assert not hasattr(k, "FOLDERY_NOTATEK")                                  # kompilator bierze listę z wiedza.py
    assert all(set(d) == {"tytul", "hub", "pisze", "kompilator", "recall", "opis"} for d in w.FOLDERY_SKARBCA.values())
    assert all("—" not in d["opis"] and "–" not in d["opis"] for d in w.FOLDERY_SKARBCA.values())


def test_streszczenie_sekcji_z_sama_tabela():
    """Sekcja z samą tabelą (REKORDY Kernela) ma w przypomnieniu liczby, nie pusty opis (22.11)."""
    tekst = ("| metryka | rekord | data |\n|---|---|---|\n| sweep, mediana | **115.5 t/s** | 2026-10-15 |\n"
             "| tg128 | 44.0 t/s | 2026-10-15 |\n| trzeci | 1 | 2 |\n\nPo tabeli.")
    assert w.streszczenie_tresci(tekst) == "Po tabeli."
    assert w.streszczenie_tresci(tekst.split("\n\n")[0]) == ("sweep, mediana, rekord: 115.5 t/s, data: 2026-10-15; "
                                                              "tg128, rekord: 44.0 t/s, data: 2026-10-15")
    assert w.streszczenie_tresci("") == ""


# --------------------------------------------------------------- tożsamość i mapa

def test_tozsamosc_i_lustra_pamieci_z_frontmatterem(dane):
    sk = dane["sk"]
    oczekiwane = {"jarvo/kim jest jarvo": ("repo", "profiles/jarvo/SOUL.md", "2026-11-20"),
                  "jarvo/zasady pracy": ("repo", "profiles/jarvo/ZASADY.md", None),
                  "jarvo/zasady krytyczne": ("repo", "profiles/jarvo/ZASADY.md", None),
                  "jarvo/jak działa jarvo": ("repo", "profiles/jarvo/MAPA.md", "2026-11-19"),
                  "jarvo/pamięć jarva": ("pamiec", "profiles/jarvo/memories/MEMORY.md", None),
                  "user/pamięć jarva o tobie": ("pamiec", "profiles/jarvo/memories/USER.md", None)}
    for rel, (edycja, plik, data) in oczekiwane.items():
        n = sk.wczytaj(rel)
        assert n.fm["typ"] == "tozsamosc" and n.fm["status"] == "aktualna" and n.fm["zrodlo"] == "wiedza.py zasiej", rel
        assert n.fm["edycja"] == edycja and n.fm["plik"] == plik and w.DATA_RE.match(n.fm["zmieniono"]), rel
        assert data is None or n.fm["zmieniono"] == data, rel
        assert not w.zly_naglowek(sk.plik(rel).read_text(encoding="utf-8")), rel
    assert sk.wczytaj("jarvo/pamięć jarva").fm["pamiec"] == "memory" and sk.wczytaj("user/pamięć jarva o tobie").fm["pamiec"] == "user"
    pam = sk.wczytaj("jarvo/pamięć jarva").tresc
    assert "- Patrol co 30 minut\n- Brief o 07:50" in pam and "2 wpisy, 34 z 300 znaków" in pam
    krytyczne = sk.wczytaj("jarvo/zasady krytyczne").tresc
    assert "> Dowód albo „(przypuszczam)”." in krytyczne and "\n<critical>" not in krytyczne
    assert "Dowód albo" not in sk.wczytaj("jarvo/zasady pracy").tresc            # zamykający blok tylko w krytycznych
    assert "### Jak pracuję" in sk.wczytaj("jarvo/zasady pracy").tresc          # nagłówki o poziom niżej niż tytuł
    hub = sk.plik("jarvo/_hub-jarvo").read_text(encoding="utf-8")
    kolejnosc = [hub.index(f"[[{s}|") for s in w.KOLEJNOSC_TOZSAMOSCI]
    assert kolejnosc == sorted(kolejnosc) and "[[orzeczenia/jarvo|Twoje poprawki dla Jarva (orzeczenia)]]" in hub
    assert "# 🛰️ Jarvo (jarvo)" in sk.plik("agenci/jarvo/_hub-jarvo").read_text(encoding="utf-8")   # nie „Main Judge”
    ix = w.Indeks(sk)
    raport = w.lint(sk, ix)
    ix.zamknij()
    assert not [x for x in raport["bledy"] + raport["ostrzezenia"] if "jarvo/" in x and "agenci/jarvo" not in x], raport


def test_mapa_jarva_notatka_rdzen_i_sekcje(dane):
    sk = dane["sk"]
    n = sk.wczytaj("jarvo/jak działa jarvo")
    assert n.tytul == "Jarvo od A do Z" and n.fm["sekcje"] is True
    t = n.tresc
    assert t.index("## Kim jestem") < t.index("## Gdzie co jest") < t.index("## Kiedy") < t.index("## Słownik")
    assert "Jestem Jarvo, szef floty." in t and "Pracuję dla JARO z Enigmalabz." in t and "<!-- Jarvo:RDZEN" not in t
    assert "- codziennie 07:50: Poranny brief (`jarvo`" in t and "od poniedziałku do soboty 08:40: Dzień Jarodev (`jarvo`, wstrzymana)" in t
    assert "_Stan z rutyn Hermesa" in t and "- skarbiec: `" in t
    # rdzeń: tylko RDZEN (repo, potem nakładka) i zwarte GEN, bez dat i wstrzymanych rutyn
    rd = mapa.rdzen(MAPA, MAPA_NAKL, [{"nazwa": "Poranny brief", "kiedy": "50 7 * * *", "agent": "jarvo", "wlaczona": True},
                                     {"nazwa": "Dzień", "kiedy": "40 8 * * 1-6", "agent": "jarvo-jarodev", "wlaczona": False}],
                    {"dane Jarva": "/d/jarvo", "skarbiec": "/d/jarvo/knowledge", "misje": "/d/jarvo/missions"})
    assert rd == ("### Kim jestem\n- Profil `jarvo` Hermesa, orkiestrator.\n- Strony JARO na SEOHost.\n\n"
                  "### Gdzie co jest\n- dane Jarva `/d/jarvo`: skarbiec `knowledge/`, misje `missions/`\n\n"
                  "### Kiedy\n- codziennie 07:50: Poranny brief")
    # sekcje w indeksie: przypomnienie trafia w sekcję, wiedza_czytaj czyta samą sekcję
    ix = w.Indeks(sk)
    ix.odswiez()
    wyniki = [r["sciezka"] for r in w.notatki_przypomnienia(ix, "gdzie jest kopia skarbca na githubie", pomin_tozsamosc=True)]
    assert "jarvo/jak działa jarvo#Gdzie co jest" in wyniki and "jarvo/jak działa jarvo" not in wyniki
    assert "jarvo/kim jest jarvo" not in [r["sciezka"] for r in w.notatki_przypomnienia(ix, "kim jest jarvo charakter", pomin_tozsamosc=True)]
    ix.zamknij()
    sekcja = sk.wczytaj("jarvo/jak działa jarvo#gdzie co jest")
    assert sekcja.sciezka == "jarvo/jak działa jarvo#Gdzie co jest" and sekcja.tresc.startswith("## Gdzie co jest")
    assert "## Kiedy" not in sekcja.tresc


@pytest.mark.parametrize("kiedy,polsku", [("every 30m", "co 30 min"), ("50 7 * * *", "codziennie 07:50"),
                                          ("50 18 * * 0", "niedziela 18:50"), ("10 9 * * 1-5", "od poniedziałku do piątku 09:10"),
                                          ("20 9 1 * *", "1. dnia miesiąca 09:20"), ("0 */2 * * *", "`0 */2 * * *`")])
def test_harmonogram_po_polsku(kiedy, polsku):
    assert mapa.czas_po_polsku(kiedy) == polsku


# --------------------------------------------------------------- pamięć: lustro po treści pliku

def test_lustro_pamieci_po_tresci_pliku_bez_narzedzia(dane):
    """Regresja 20.11: wpisy USER.md z 19 i 20.11 nie dotarły do skarbca, bo plik zmienił się poza narzędziem memory
    (przepisanie przy prompcie v2). Teraz decyduje treść pliku: zasiew, start sesji, tura wtyczki i zapis z Mózgu."""
    sk, profil = dane["sk"], dane["profil"]
    szkic = sk.root / "skrzynka" / "pamiec-jarvo-user.md"
    assert szkic.read_text(encoding="utf-8").count("add user: JARO pisze krótko") == 1          # pierwszy zasiew: wszystko
    (profil / "memories" / "USER.md").write_text("JARO pisze krótko\n§\nTokeny Antigravity traktuje jak walutę (19.11)\n§\n"
                                                  "Chce widzieć pracę agentów na żywo w panelu (20.11)", encoding="utf-8")
    p = pl.SkarbiecProvider()
    p.initialize("sesja-nowa", hermes_home=str(profil), platform="api_server", agent_context="primary")   # bez narzędzia memory
    tekst = szkic.read_text(encoding="utf-8")
    assert "add user: Tokeny Antigravity traktuje jak walutę (19.11)" in tekst and "na żywo w panelu (20.11)" in tekst
    assert tekst.count("JARO pisze krótko") == 1                                                 # znane wpisy nie wracają
    assert "Tokeny Antigravity" in sk.wczytaj("user/pamięć jarva o tobie").tresc
    assert w.synchronizuj_pamiec(sk, profil, "jarvo") == {"zmienione": [], "wpisow": 0, "notatki": []}   # ta sama wersja
    p.sync_turn("hej", "cześć", session_id="sesja-nowa")                                         # tura bez zmiany pliku
    assert szkic.read_text(encoding="utf-8") == tekst
    (profil / "memories" / "MEMORY.md").write_text("Patrol co 30 minut", encoding="utf-8")       # usunięcie wpisu
    p.sync_turn("hej", "cześć", session_id="sesja-nowa")
    assert "Brief o 07:50" not in sk.wczytaj("jarvo/pamięć jarva").tresc


def test_szkic_z_user_md_trafia_do_user(dane):
    """Lustro USER.md (pamiec-jarvo-user): fakt idzie do user/, choćby model zaproponował agenci/jarvo/."""
    sk = dane["sk"]
    (sk.root / "skrzynka" / "pamiec-jarvo.md").unlink()                    # zostaje sam szkic z USER.md
    model = lambda system, user: json.dumps({"wyniki": [{"decyzja": "nowa", "sciezka": "agenci/jarvo/jaro pisze krótko",
                                                          "typ": "fakt", "tytul": "JARO pisze krótko", "streszczenie": "JARO pisze krótko.",
                                                          "tresc": "JARO pisze krótko i wielkimi literami; liczy się sens.",
                                                          "powod": "nowy fakt"}]})
    r = k.Kompilacja(sk, model).uruchom()
    assert r["notatki"] == ["user/jaro pisze krótko"], r


# --------------------------------------------------------------- zapis pamięci z Mózgu (GET/PUT /pamiec)

def test_pamiec_get_put_409_limit_i_bledy(dane):
    sk, d, profil = dane["sk"], dane["dane"], dane["profil"]
    panel = pm.Panel(sk.root, sk.stan, repo=dane["tmp"] / "repo", dane=d)
    lib = panel.lib
    g = panel.pamiec()
    assert g["memory"]["wpisy"] == ["Patrol co 30 minut", "Brief o 07:50"] and g["memory"]["limit"] == 300
    assert g["user"]["limit"] == 200 and g["user"]["uzyte"] == len("JARO pisze krótko") and g["user"]["wersja"]
    r = panel.zapisz_pamiec("memory", ["Patrol co 30 minut", " Brief o 08:00 ", "Nowy wpis\nw dwóch liniach"], g["memory"]["wersja"])
    assert (profil / "memories" / "MEMORY.md").read_bytes() == "Patrol co 30 minut\n§\nBrief o 08:00\n§\nNowy wpis\nw dwóch liniach".encode()
    assert r["wpisy"][1] == "Brief o 08:00" and r["wersja"] != g["memory"]["wersja"]
    assert "- Nowy wpis\n  w dwóch liniach" in sk.wczytaj("jarvo/pamięć jarva").tresc               # lustro od razu
    assert "add memory: Brief o 08:00" in (sk.root / "skrzynka" / "pamiec-jarvo.md").read_text(encoding="utf-8")
    with pytest.raises(lib.BladPamieci) as e:                                                   # stara wersja: 409
        panel.zapisz_pamiec("memory", ["x"], g["memory"]["wersja"])
    assert e.value.status == 409 and e.value.kod == "zmieniona" and e.value.dane["aktualna"]["wersja"] == r["wersja"]
    for wpisy, kod in ((["a" * 201], "limit"), (["ok", "  "], "pusty_wpis"), (["ok", "ok"], "zly_wpis"),
                       (["x\n§\ny"], "zly_wpis"), (["hasło: tajne1234"], "zly_wpis"), ("tekst", "zly_wpis"), ([3], "zly_wpis")):
        with pytest.raises(lib.BladPamieci) as e:
            panel.zapisz_pamiec("user", wpisy, g["user"]["wersja"])
        assert e.value.kod == kod and e.value.status == 400, wpisy
    assert (profil / "memories" / "USER.md").read_text(encoding="utf-8") == "JARO pisze krótko"          # nic nie zapisane
    assert e.value.jako_json()["blad"]["kod"] == "zly_wpis"
    with pytest.raises(FileNotFoundError):
        panel.zapisz_pamiec("sekrety", [], "")
    assert "pamiec | zmiana z Mózgu: MEMORY.md Jarva, wpisów 2 → 3" in (sk.root / "LOG.md").read_text(encoding="utf-8")


def test_pamiec_put_przez_api_i_blokada(dane, monkeypatch):
    """PUT przez trasę FastAPI: kody HTTP z kontraktu, a zapis czeka na blokadę `.lock` Hermesa (503 po czasie)."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    import fastapi
    sk, d = dane["sk"], dane["dane"]
    monkeypatch.setenv("JARVO_KNOWLEDGE_DIR", str(sk.root))
    monkeypatch.setenv("JARVO_STATE_DIR", str(sk.stan))
    monkeypatch.setenv("HERMES_HOME", str(d))
    for nazwa in ("jarvo_wiedza_panel", "jarvo_wiedza_ochrona", "jarvo_wiedza_lib"):
        sys.modules.pop(nazwa, None)
    s = importlib.util.spec_from_file_location("jarvo_test_mozg_api", REPO / "wiedza" / "plugin" / "dashboard" / "plugin_api.py")
    api = importlib.util.module_from_spec(s)
    s.loader.exec_module(api)
    app = fastapi.FastAPI()
    app.include_router(api.router, prefix="/p")
    c = TestClient(app)
    h = {"X-Jarvo-Request": "1"}
    g = c.get("/p/pamiec").json()
    assert c.put("/p/pamiec/user", json={"wpisy": ["JARO"], "wersja": "zla"}, headers=h).status_code == 409
    r = c.put("/p/pamiec/user", json={"wpisy": ["a" * 500], "wersja": g["user"]["wersja"]}, headers=h)
    assert r.status_code == 400 and r.json()["blad"] == {"kod": "limit", "opis": "500 znaków z 200: skróć albo usuń wpisy",
                                                         "limit": 200, "uzyte": 500}
    assert c.put("/p/pamiec/user", content="zle", headers={**h, "Content-Type": "application/json"}).status_code == 400
    monkeypatch.setattr(api.PANEL.lib, "zamek_pamieci", _zajety(api.PANEL.lib))
    r = c.put("/p/pamiec/user", json={"wpisy": ["JARO"], "wersja": g["user"]["wersja"]}, headers=h)
    assert r.status_code == 503 and r.json()["blad"]["kod"] == "zajeta"
    monkeypatch.undo()


def _zajety(lib):
    def zamek(plik, czekaj_s=10.0):
        raise lib.BladPamieci("zajeta", "zajęta", 503)
    return zamek


def test_zapis_pamieci_zgodny_z_hermesem_co_do_bajtu(tmp_path):
    """Plik zapisany przez PUT czyta prawdziwe narzędzie memory Hermesa tak samo (te same wpisy, bez dryfu), a plik
    zapisany przez Hermesa ma te same bajty co nasz zapis tych samych wpisów. Blokada: ten sam plik `.lock`."""
    py = _hermes_python()
    if not py:
        pytest.skip("brak instalacji Hermesa (HERMES_SRC, /opt/hermes albo ~/.local/share/jarvo/program/hermes)")
    profil = tmp_path / "profiles" / "jarvo"
    (profil / "memories").mkdir(parents=True)
    wpisy = ["JARO pisze krótko, ZDANIA WIELKIMI", "Wpis z § w środku i\ndrugą linią", "Ostatni: ąęśćżźół"]
    stan = w.zapisz_pamiec(profil, "user", wpisy, w.czytaj_pamiec(w.plik_pamieci(profil, "user"))["wersja"])
    assert (profil / "memories" / "USER.md.lock").exists() and oct((profil / "memories" / "USER.md.lock").stat().st_mode)[-3:] == "600"
    hermes = str(Path(py).parents[2])
    skrypt = ("import json, sys\nfrom tools import memory_tool as mt\nfrom tools.memory_tool_store import MemoryStore\n"
              "s = MemoryStore(3000, 2000)\ns.load_from_disk()\n"
              "dryf = s._detect_external_drift('user', mt.get_memory_dir().joinpath('USER.md').read_text(encoding='utf-8'))\n"
              "r = s.add('memory', 'Wpis od Hermesa')\n"
              "print(json.dumps({'user': s.user_entries, 'dryf': dryf, 'ok': r.get('success')}))\n")
    wynik = subprocess.run([py, "-c", skrypt], cwd=hermes, env={**os.environ, "HERMES_HOME": str(profil), "PYTHONPATH": hermes},
                           capture_output=True, text=True, timeout=120)
    assert wynik.returncode == 0, wynik.stderr[-2000:]
    d = json.loads(wynik.stdout.strip().splitlines()[-1])
    assert d == {"user": wpisy, "dryf": None, "ok": True}
    assert stan["wpisy"] == wpisy
    od_hermesa = (profil / "memories" / "MEMORY.md").read_bytes()
    assert w.wpisy_z_pamieci(od_hermesa.decode("utf-8")) == ["Wpis od Hermesa"]
    w.zapisz_pamiec(profil, "memory", ["Wpis od Hermesa"], w.czytaj_pamiec(w.plik_pamieci(profil, "memory"))["wersja"])
    assert (profil / "memories" / "MEMORY.md").read_bytes() == od_hermesa


# --------------------------------------------------------------- tożsamość i pamięć każdego agenta (22.11)

def test_tozsamosc_i_pamiec_kazdego_agenta(dane, monkeypatch):
    """22.11 właściciel: każdy agent ma obieg mózgu Jarva. Zasiew robi z build/wiedza/tozsamosc/agenci/<agent>/ notatki
    w jego katalogu (kim jest, zasady, mapa z sekcjami), lustro pamięci jego profilu (z `profil:` dla Mózgu), agent nie
    dostaje w przypomnieniu swojej tożsamości (ma ją w prompcie), kompilacja jej nie nadpisuje, a Mózg edytuje jego
    pamięć przez GET/PUT /pamiec?profil= tylko dla agenta floty z katalogiem profilu."""
    sk, d, toz = dane["sk"], dane["dane"], dane["toz"]
    web = toz / "agenci" / "jarvo-web"
    web.mkdir(parents=True)
    (web / "SOUL.md").write_text("# Web\n\nJestem Web, Web Senior Dev floty Jarva.\n\n## Charakter\n- Mówię liczbami.\n", encoding="utf-8")
    (web / "ZASADY.md").write_text("## Zasady pracy\n1. Najpierw pomiar.\n", encoding="utf-8")
    (web / "MAPA.md").write_text("## Kim jestem\nJestem Web.\n\n<!-- Jarvo:RDZEN -->\n- Profil `jarvo-web`.\n<!-- /Jarvo:RDZEN -->\n\n"
                                 "## Gdzie co jest\nPracuję w katalogu roboczym.\n", encoding="utf-8")
    (web / "zrodla.json").write_text(json.dumps({"MAPA.md": {"plik": "profiles/jarvo-web/MAPA.md", "zmieniono": "2026-11-22"}}),
                                     encoding="utf-8")
    profil = d / "profiles" / "jarvo-web"
    (profil / "memories").mkdir(parents=True)
    (profil / "memories" / "MEMORY.md").write_text("Hosting enigmy: SEOHost (22.11)", encoding="utf-8")
    (profil / "memories" / "USER.md").write_text("", encoding="utf-8")
    assert _cli(dane, "zasiej", "--fleet", str(dane["fleet"]), "--tozsamosc", str(toz), "--profile", str(d / "profiles")) == 0
    for rel, edycja in (("kim jest web", "repo"), ("zasady pracy web", "repo"), ("jak działa web", "repo"),
                        ("pamięć web", "pamiec"), ("pamięć web o tobie", "pamiec")):
        n = sk.wczytaj(f"agenci/jarvo-web/{rel}")
        assert n.fm["typ"] == "tozsamosc" and n.fm["edycja"] == edycja and "[[agenci/jarvo-web/_hub-web|Web]]" in n.tresc, rel
    mapa_web = sk.wczytaj("agenci/jarvo-web/jak działa web")
    assert mapa_web.tytul == "Web od A do Z" and mapa_web.fm["sekcje"] is True and mapa_web.fm["plik"] == "profiles/jarvo-web/MAPA.md"
    assert "- skarbiec: `" in mapa_web.tresc and "<!-- Jarvo:RDZEN" not in mapa_web.tresc
    pam = sk.wczytaj("agenci/jarvo-web/pamięć web")
    assert pam.fm["profil"] == "jarvo-web" and pam.fm["pamiec"] == "memory" and "- Hosting enigmy: SEOHost (22.11)" in pam.tresc
    assert "Web czyta je na starcie" in pam.tresc and "profil" not in sk.wczytaj("jarvo/pamięć jarva").fm
    assert "add memory: Hosting enigmy" in (sk.root / "skrzynka" / "pamiec-jarvo-web.md").read_text(encoding="utf-8")
    # przypomnienie: swojej tożsamości agent nie dostaje drugi raz (mapy tak), cudzą tak
    assert w.tozsamosc_w_prompcie("agenci/jarvo-web/kim jest web", "jarvo-web")
    assert w.tozsamosc_w_prompcie("agenci/jarvo-web/pamięć web o tobie", "jarvo-web")
    assert not w.tozsamosc_w_prompcie("agenci/jarvo-web/jak działa web#Gdzie co jest", "jarvo-web")
    assert not w.tozsamosc_w_prompcie("agenci/jarvo-web/kim jest web", "jarvo")
    assert w.tozsamosc_w_prompcie("jarvo/kim jest jarvo", "jarvo") and not w.tozsamosc_w_prompcie("jarvo/jak działa jarvo", "jarvo")
    # cudza tożsamość tylko, gdy pytanie nazywa agenta (22.11: Sherlock na „dla kogo pracujesz?” dostawał 5 cudzych
    # sekcji „Dla kogo pracuję”, hit@5 0,2); zwykłe notatki z katalogu innego agenta wracają jak zawsze
    dla_kogo = w._slowa_ascii("dla kogo pracujesz")
    assert w.tozsamosc_obca("agenci/jarvo-web/jak działa web#Dla kogo pracuję i po co", "jarvo-sherlock", dla_kogo)
    assert w.tozsamosc_obca("jarvo/jak działa jarvo#Dla kogo pracuję i po co", "jarvo-sherlock", dla_kogo)
    assert not w.tozsamosc_obca("agenci/jarvo-sherlock/jak działa sherlock#Dla kogo pracuję i po co", "jarvo-sherlock", dla_kogo)
    assert not w.tozsamosc_obca("agenci/jarvo-web/jak działa web#Dla kogo pracuję i po co", "jarvo",
                                w._slowa_ascii("dla kogo pracuje web"))
    assert not w.tozsamosc_obca("agenci/jarvo-wideo/pamięć wideograf", "jarvo", w._slowa_ascii("co pamięta wideograf"))
    assert not w.tozsamosc_obca("agenci/jarvo-web/hosting enigmy na seohost", "jarvo-sherlock", dla_kogo)
    ix = w.Indeks(sk)
    ix.odswiez()
    assert "agenci/jarvo-web/kim jest web" not in [r["sciezka"] for r in w.notatki_przypomnienia(
        ix, "kim jest web charakter liczbami", limit=10, pomin_tozsamosc="jarvo-web")]
    wezel = next(x for x in ix.graf()["wezly"] if x["id"] == "agenci/jarvo-web/pamięć web")
    assert wezel["profil"] == "jarvo-web" and wezel["edycja"] == "pamiec"
    ix.zamknij()
    assert k.Kompilacja(sk, lambda s, u: "{}").wlasny_format("agenci/jarvo-web/kim jest web")   # kompilacja nie nadpisze
    # Mózg: pamięć agenta floty przez panel (te same kody co u Jarva), obca nazwa = 400, brak profilu = 404
    panel = pm.Panel(sk.root, sk.stan, repo=dane["tmp"] / "repo", dane=d)
    g = panel.pamiec("jarvo-web")
    assert g["memory"]["wpisy"] == ["Hosting enigmy: SEOHost (22.11)"] and g["memory"]["notatka"] == "agenci/jarvo-web/pamięć web"
    assert g["user"]["wpisy"] == [] and g["memory"]["limit"] == w.LIMITY_PAMIECI["memory"]
    r = panel.zapisz_pamiec("user", ["JARO chce Astro na stronach (22.11)"], g["user"]["wersja"], "jarvo-web")
    assert (profil / "memories" / "USER.md").read_text(encoding="utf-8") == "JARO chce Astro na stronach (22.11)"
    assert r["notatka"] == "agenci/jarvo-web/pamięć web o tobie"
    assert "- JARO chce Astro" in sk.wczytaj("agenci/jarvo-web/pamięć web o tobie").tresc               # lustro od razu
    assert "zmiana z Mózgu: USER.md jarvo-web" in (sk.root / "LOG.md").read_text(encoding="utf-8")
    assert panel.pamiec("")["memory"]["wpisy"] == ["Patrol co 30 minut", "Brief o 07:50"]                 # bez profilu: Jarvo
    for zly in ("jarvo-obcy", "../jarvo", "jarvo-web/../jarvo"):
        with pytest.raises(ValueError):
            panel.pamiec(zly)
    meta = json.loads((sk.stan / "wiedza-agenci.json").read_text(encoding="utf-8"))
    (sk.stan / "wiedza-agenci.json").write_text(json.dumps({**meta, "jarvo-ads": {"hub": "agenci/jarvo-ads/_hub-ads"}}),
                                                encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        panel.pamiec("jarvo-ads")                                                    # we flocie, ale bez profilu
    # trasa FastAPI: ?profil= przy GET i PUT, nagłówek zapisu jak dotąd
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    import fastapi
    monkeypatch.setenv("JARVO_KNOWLEDGE_DIR", str(sk.root))
    monkeypatch.setenv("JARVO_STATE_DIR", str(sk.stan))
    monkeypatch.setenv("HERMES_HOME", str(d))
    for nazwa in ("jarvo_wiedza_panel", "jarvo_wiedza_ochrona", "jarvo_wiedza_lib"):
        monkeypatch.delitem(sys.modules, nazwa, raising=False)
    s = importlib.util.spec_from_file_location("jarvo_test_mozg_api_agent", REPO / "wiedza" / "plugin" / "dashboard" / "plugin_api.py")
    api = importlib.util.module_from_spec(s)
    s.loader.exec_module(api)
    app = fastapi.FastAPI()
    app.include_router(api.router, prefix="/p")
    c = TestClient(app)
    g = c.get("/p/pamiec?profil=jarvo-web").json()
    assert g["user"]["wpisy"] == ["JARO chce Astro na stronach (22.11)"]
    assert c.get("/p/pamiec?profil=jarvo-obcy").status_code == 400
    assert c.put("/p/pamiec/memory?profil=jarvo-web", json={"wpisy": ["x"], "wersja": g["memory"]["wersja"]}).status_code == 403
    r = c.put("/p/pamiec/memory?profil=jarvo-web", json={"wpisy": ["Hosting: SEOHost"], "wersja": g["memory"]["wersja"]},
              headers={"X-Jarvo-Request": "1"})
    assert r.status_code == 200 and (profil / "memories" / "MEMORY.md").read_text(encoding="utf-8") == "Hosting: SEOHost"


# --------------------------------------------------------------- archiwum, przeniesienie, streszczenie

def _notatka(sk, rel, tytul, tresc, linki=(), typ="fakt", **fm):
    front = {"typ": typ, "tagi": ["t"], "utworzono": "2026-11-01", "zmieniono": "2026-11-01", "status": "aktualna", "zrodlo": "test", **fm}
    sk.zapisz_plik(rel, w.sklej(front, f"# {tytul}\n\n**{tresc}**\n\n## Powiązane\n" + "".join(f"- [[{l}]]\n" for l in linki)))


def test_archiwizuj_i_przenies_przepisuja_linki_wszedzie(dane):
    sk = dane["sk"]
    _notatka(sk, "agenci/jarvo/instabox ma 200 gib", "InstaBox ma 200 GiB", "Maszyna ma 200 GiB dysku.", ["agenci/jarvo/_hub-jarvo"])
    _notatka(sk, "podmioty/instabox", "InstaBox", "Darmowa maszyna w chmurze.", ["podmioty/_hub-podmioty"], typ="podmiot")
    _notatka(sk, "projekty/zapas mocy", "Zapas mocy", "Liczymy na [[agenci/jarvo/instabox ma 200 gib|dysk]] i "
             "[[instabox ma 200 gib#Dysk]].", ["projekty/_hub-projekty", "agenci/jarvo/instabox ma 200 gib"])
    _notatka(sk, "user/styl jaro", "Styl JARO", "JARO pisze krótko.", ["user/_hub-ty"])
    hub = sk.plik("agenci/jarvo/_hub-jarvo").read_text(encoding="utf-8")
    sk.zapisz_plik("agenci/jarvo/_hub-jarvo", hub + "\nRęcznie: [[agenci/jarvo/instabox ma 200 gib]], [[user/styl jaro]]\n")
    assert _cli(dane, "archiwizuj", "agenci/jarvo/instabox ma 200 gib", "--powod", "scalona w podmiot",
                "--zastapiona-przez", "podmioty/instabox") == 0
    arch = sk.wczytaj("archiwum/agenci/jarvo/instabox ma 200 gib")
    assert arch.fm["status"] == "wycofana" and arch.fm["zastapiona_przez"] == "podmioty/instabox" and arch.fm["wycofano"] == "2026-11-20"
    projekt = sk.plik("projekty/zapas mocy").read_text(encoding="utf-8")
    assert "[[podmioty/instabox|dysk]]" in projekt and "[[podmioty/instabox#Dysk]]" in projekt and "- [[podmioty/instabox]]" in projekt
    assert "Ręcznie: [[podmioty/instabox]]" in sk.plik("agenci/jarvo/_hub-jarvo").read_text(encoding="utf-8")
    assert sk.wczytaj("agenci/jarvo/instabox ma 200 gib").sciezka == "podmioty/instabox"           # stara ścieżka → następca
    assert sk.przekierowanie("agenci/jarvo/instabox ma 200 gib") == "podmioty/instabox"
    assert _cli(dane, "przenies", "user/styl jaro", "pojecia") == 0
    assert sk.istnieje("pojecia/styl jaro") and not sk.istnieje("user/styl jaro")
    assert "Ręcznie: [[podmioty/instabox]], [[pojecia/styl jaro]]" in sk.plik("agenci/jarvo/_hub-jarvo").read_text(encoding="utf-8")
    assert "[[pojecia/styl jaro|" in sk.plik("pojecia/_hub-pojecia").read_text(encoding="utf-8")       # listy hubów odświeżone
    assert "[[pojecia/styl jaro|" in (sk.root / "INDEX.md").read_text(encoding="utf-8")
    log = (sk.root / "LOG.md").read_text(encoding="utf-8")
    assert "archiwum | archiwum: agenci/jarvo/instabox ma 200 gib (scalona w podmiot)" in log and "przeniesienie | przeniesienie" in log
    ix = w.Indeks(sk)
    raport = w.lint(sk, ix)
    assert not [b for b in raport["bledy"] if "martwy" in b], raport["bledy"]
    assert not any(r["sciezka"].startswith("archiwum/") for r in ix.szukaj("instabox 200 gib dysk", limit=10))
    ix.zamknij()
    for zle in (["user/_hub-ty", "pojecia"], ["jarvo/kim jest jarvo", "pojecia"], ["pojecia/styl jaro", "archiwum"],
                ["pojecia/styl jaro", "nie-ma-takiego"]):
        assert _cli(dane, "przenies", *zle) == 3, zle
    assert _cli(dane, "archiwizuj", "pojecia/styl jaro", "--powod", "x", "--zastapiona-przez", "pojecia/nie ma") == 3


def test_streszczenie_huba_przezywa_zasiew_i_indeksuj(dane):
    sk = dane["sk"]
    tekst = "**Najważniejsze o Tobie:** piszesz krótko; decyzje z 11.11 w [[user/_hub-ty|Ty]].\n\n- serwer tylko dla agentów"
    assert _cli(dane, "streszczenie", "user", "--tekst", tekst) == 0
    assert _cli(dane, "zasiej", "--fleet", str(dane["fleet"]), "--tozsamosc", str(dane["toz"])) == 0
    assert _cli(dane, "indeksuj") == 0
    n = sk.wczytaj("user/_hub-ty")
    assert w.podsumowanie_huba(n.tresc) == tekst and n.fm["streszczono"] == "2026-11-20"
    assert n.streszczenie.startswith("Najważniejsze o Tobie: piszesz krótko")
    assert n.tresc.index("<!-- Jarvo:STRESZCZENIE -->") < n.tresc.index("## Powiązane")
    ix = w.Indeks(sk)
    ix.odswiez()
    wezel = next(x for x in ix.graf()["wezly"] if x["id"] == "user/_hub-ty")
    assert wezel["podsumowanie"] == tekst and wezel["streszczono"] == "2026-11-20"
    pam = next(x for x in ix.graf()["wezly"] if x["id"] == "user/pamięć jarva o tobie")
    assert (pam["edycja"], pam["pamiec"], pam["plik"]) == ("pamiec", "user", "profiles/jarvo/memories/USER.md")
    assert "user/_hub-ty" in [r["sciezka"] for r in w.notatki_przypomnienia(ix, "najważniejsze o tobie piszesz krótko")]
    ix.zamknij()
    assert _cli(dane, "streszczenie", "user", "--tekst", "x" * 1501) == 3
    assert _cli(dane, "streszczenie", "nie-ma", "--tekst", "x") == 3


# --------------------------------------------------------------- routing kompilatora (atrapa modelu)

@pytest.fixture
def ks(dane, monkeypatch):
    monkeypatch.setattr(k, "ROWNOLEGLE", 1)
    sk = dane["sk"]
    for p in (sk.root / "skrzynka").glob("*.md"):                    # szkice pamięci z zasiewu nie mieszają się do tabeli
        p.unlink()
    _notatka(sk, "podmioty/instabox darmowa maszyna", "InstaBox: darmowa maszyna", "InstaBox to darmowa maszyna Linux w chmurze.",
             ["podmioty/_hub-podmioty"], typ="podmiot", aliasy=["InstaBox", "instabox.sh"])
    (sk.root / "agenci" / "jarvo-web").mkdir(parents=True, exist_ok=True)
    w.main(["--skarbiec", str(sk.root), "--stan", str(sk.stan), "indeksuj"])
    return sk


@pytest.mark.parametrize("szkic_agent,wynik,oczekiwane", [
    ("jarvo", {"decyzja": "nowa", "sciezka": "agenci/jarvo/właściciel pisze wielkimi literami", "typ": "fakt",
               "o_wlascicielu": True, "tytul": "Właściciel pisze wielkimi literami", "tresc": "JARO pisze wielkimi literami."},
     "user/właściciel pisze wielkimi literami"),
    ("jarvo", {"decyzja": "nowa", "sciezka": "agenci/jarvo/najpierw pomiar potem zmiana", "typ": "lekcja",
               "tytul": "Najpierw pomiar, potem zmiana", "tresc": "Zmianę wydajności robimy po pomiarze bazowym."},
     "pojecia/najpierw pomiar, potem zmiana"),
    ("jarvo-web", {"decyzja": "nowa", "sciezka": "agenci/jarvo-web/deploy przez ssh z kluczem", "typ": "lekcja", "o_agencie": True,
                   "tytul": "Deploy przez SSH z kluczem", "tresc": "Web wgrywa strony skryptem przez SSH z kluczem."},
     "agenci/jarvo-web/deploy przez ssh z kluczem"),
    ("jarvo", {"decyzja": "nowa", "sciezka": "agenci/jarvo/konto w monid", "typ": "fakt", "aliasy": ["Monid"],
               "tytul": "Konto w Monid", "tresc": "Monid daje 1 USD kredytu na start."},
     "podmioty/konto w monid"),
])
def test_routing_kompilatora(ks, szkic_agent, wynik, oczekiwane):
    """Tabela „o czym jest notatka → folder”: agenci/ tylko z o_agencie; fakt o właścicielu → user/; lekcja ogólna →
    pojecia/; fakt z aliasami bez notatki podmiotu → podmioty/."""
    w.zapisz_szkic(ks, "fakt", wynik["tytul"], wynik["tresc"], "rozmowa 20.11", szkic_agent, skad="test")
    r = k.Kompilacja(ks, lambda s, u: json.dumps({"wyniki": [{**wynik, "streszczenie": wynik["tresc"], "powod": "test"}]})).uruchom()
    assert r["notatki"] == [oczekiwane] and ks.istnieje(oczekiwane), r


def test_fakt_o_podmiocie_aktualizuje_jego_notatke(ks):
    """Nowy fakt o InstaBoxie (model daje „nowa” w agenci/jarvo/) dopisuje się do istniejącej notatki podmiotu: jedna
    notatka na podmiot zamiast siedemnastej w agenci/jarvo/. Kandydat podmiotu jest w prompcie (szukanie w podmioty/)."""
    w.zapisz_szkic(ks, "fakt", "InstaBox ma 200 GiB dysku", "Maszyna InstaBox ma 200 GiB dysku i 8 GB RAM.", "karta t_1", "jarvo",
                   skad="test")
    prompty = []

    def model(system, user):
        prompty.append(user)
        return json.dumps({"wyniki": [{"decyzja": "nowa", "sciezka": "agenci/jarvo/instabox ma 200 gib dysku", "typ": "fakt",
                                       "tytul": "InstaBox ma 200 GiB dysku", "streszczenie": "InstaBox ma 200 GiB dysku.",
                                       "tresc": "Maszyna InstaBox ma 200 GiB dysku i 8 GB RAM.", "powod": "nowy fakt"}]})
    r = k.Kompilacja(ks, model).uruchom()
    assert r["aktualizacje"] == 1 and r["nowe"] == 0 and r["notatki"] == ["podmioty/instabox darmowa maszyna"], r
    assert "[podmioty/instabox darmowa maszyna]" in prompty[0] and "O CZYM JEST NOTATKA → FOLDER" in k.SYSTEM
    n = ks.wczytaj("podmioty/instabox darmowa maszyna")
    assert "2026-11-20: Maszyna InstaBox ma 200 GiB dysku i 8 GB RAM." in n.tresc and n.fm["typ"] == "podmiot"
    assert not list((ks.root / "agenci" / "jarvo").glob("instabox*"))


def test_kompilator_nie_pisze_tozsamosci_ani_archiwum(ks):
    w.zapisz_szkic(ks, "fakt", "Pamięć Jarva", "Nowy fakt o pamięci.", "karta t_2", "jarvo", skad="test")
    r = k.Kompilacja(ks, lambda s, u: json.dumps({"wyniki": [{"decyzja": "aktualizacja", "sciezka": "jarvo/pamięć jarva", "typ": "fakt",
                                                               "tytul": "Pamięć Jarva", "streszczenie": "x", "tresc": "Nowy fakt.",
                                                               "powod": "x"}]})).uruchom()
    assert "jarvo/pamięć jarva" not in r["notatki"] and r["nowe"] == 1
    assert ks.wczytaj("jarvo/pamięć jarva").fm["typ"] == "tozsamosc"


# --------------------------------------------------------------- obieg end to end

def test_obieg_pamiec_kompilacja_przypomnienie_mozg(dane):
    """Jeden obieg: rozmowa zapisuje pamięć (plik Hermesa) → lustro i szkic → kompilacja (atrapa modelu) → notatka
    w user/ → indeks → przypomnienie w NOWEJ sesji → węzeł w grafie Mózgu. Potem edycja w Mózgu (PUT) → ten sam plik
    → lustro → Hermes przy następnej sesji czyta zmianę (tu: wczytanie pliku jak w Hermesie) i przypomnienie ją zna."""
    sk, profil, d = dane["sk"], dane["profil"], dane["dane"]
    for p in (sk.root / "skrzynka").glob("*.md"):
        p.unlink()
    (profil / "memories" / "USER.md").write_text("JARO pisze krótko\n§\nJARO chce widzieć agentów na żywo w panelu", encoding="utf-8")
    sesja = pl.SkarbiecProvider()
    sesja.initialize("s1", hermes_home=str(profil), platform="api_server", agent_context="primary")
    sesja.on_memory_write("add", "user", "JARO chce widzieć agentów na żywo w panelu")
    szkic = (sk.root / "skrzynka" / "pamiec-jarvo-user.md").read_text(encoding="utf-8")
    assert "add user: JARO chce widzieć agentów na żywo w panelu" in szkic

    def model(system, user):
        return json.dumps({"wyniki": [{"decyzja": "nowa", "sciezka": "agenci/jarvo/panel na żywo", "typ": "fakt",
                                       "o_wlascicielu": True, "tytul": "JARO chce widzieć agentów na żywo w panelu",
                                       "streszczenie": "JARO chce w panelu widzieć pracę agentów na żywo.",
                                       "tresc": "JARO chce w panelu Jarvo widzieć pracę agentów na żywo (20.11).", "powod": "nowy fakt"}]})
    r = k.Kompilacja(sk, model).uruchom()
    assert r["notatki"] == ["user/jaro chce widzieć agentów na żywo w panelu"], r
    nowa = pl.SkarbiecProvider()                                          # nowa sesja Jarva
    nowa.initialize("s2", hermes_home=str(profil), platform="api_server", agent_context="primary")
    blok = nowa.prefetch("czy w panelu widać pracę agentów na żywo?", session_id="s2")
    assert "`user/jaro chce widzieć agentów na żywo w panelu`" in blok
    assert "pamięć jarva o tobie" not in blok                             # pamięć jest w prompcie Jarva: bez dublowania
    panel = pm.Panel(sk.root, sk.stan, repo=dane["tmp"] / "repo", dane=d)
    assert "user/jaro chce widzieć agentów na żywo w panelu" in {x["id"] for x in panel.graph()["wezly"]}
    g = panel.pamiec()["user"]
    panel.zapisz_pamiec("user", [*g["wpisy"], "JARO woli raport w 3 punktach"], g["wersja"])
    assert w.wpisy_z_pamieci((profil / "memories" / "USER.md").read_text(encoding="utf-8-sig"))[-1] == "JARO woli raport w 3 punktach"
    assert "JARO woli raport w 3 punktach" in panel.note("user/pamięć jarva o tobie")["tresc"]
    assert "add user: JARO woli raport w 3 punktach" in (sk.root / "skrzynka" / "pamiec-jarvo-user.md").read_text(encoding="utf-8")
    inny = pl.SkarbiecProvider()                                          # inny agent nie ma pamięci Jarva w prompcie
    (d / "profiles" / "jarvo-web").mkdir(parents=True)
    inny.initialize("s3", hermes_home=str(d / "profiles" / "jarvo-web"), platform="api_server", agent_context="primary")
    assert "`user/pamięć jarva o tobie`" in inny.prefetch("czy JARO woli raport w 3 punktach?", session_id="s3")


# --------------------------------------------------------------- regresje 21.11 (porządki Jarva: 64 przeniesienia, 23 archiwizacje)

def test_przenies_i_archiwizuj_poprawiaja_linie_hub(dane, capsys):
    """21.11: po `przenies` w notatce zostawała linia `- hub: [[agenci/jarvo/_hub-jarvo]]` (lint 153 → 161 ostrzeżeń „bez
    linku do huba folderu”, Jarvo poprawiał pythonem). Teraz przeniesiona notatka wskazuje hub nowego folderu, a notatka
    w archiwum hub archiwum (etykieta idzie za hubem); inne linki bez zmian."""
    sk = dane["sk"]
    _notatka(sk, "agenci/jarvo/lekcja ogólna", "Lekcja ogólna", "Najpierw pomiar.", ["agenci/jarvo/_hub-jarvo", "user/_hub-ty"])
    tekst = sk.plik("agenci/jarvo/lekcja ogólna").read_text(encoding="utf-8").replace(
        "- [[agenci/jarvo/_hub-jarvo]]", "- hub: [[agenci/jarvo/_hub-jarvo|Jarvo]]")
    sk.zapisz_plik("agenci/jarvo/lekcja ogólna", tekst)
    _notatka(sk, "podmioty/stara firma", "Stara firma", "Firma zamknięta.", [])
    sk.zapisz_plik("podmioty/stara firma", sk.plik("podmioty/stara firma").read_text(encoding="utf-8").replace(
        "## Powiązane\n", "## Powiązane\n- hub: [[podmioty/_hub-podmioty]]\n"))
    assert _cli(dane, "przenies", "agenci/jarvo/lekcja ogólna", "pojecia") == 0
    t = sk.plik("pojecia/lekcja ogólna").read_text(encoding="utf-8")
    assert "- hub: [[pojecia/_hub-pojecia|Pojęcia]]" in t and "_hub-jarvo" not in t and "- [[user/_hub-ty]]" in t
    assert "huby: 1" in capsys.readouterr().out
    assert _cli(dane, "archiwizuj", "podmioty/stara firma", "--powod", "zamknięta") == 0
    assert "- hub: [[archiwum/_hub-archiwum]]" in sk.plik("archiwum/podmioty/stara firma").read_text(encoding="utf-8")
    ix = w.Indeks(sk)
    raport = w.lint(sk, ix)
    ix.zamknij()
    assert not [o for o in raport["ostrzezenia"] if "bez linku do huba folderu" in o and "lekcja ogólna" in o], raport


def test_archiwizuj_sprawdza_wszystkie_sciezki_przed_zmiana(dane, capsys):
    """21.11: jedna literówka na liście `archiwizuj` przerywała całość bez wskazania, która. Teraz wszystkie ścieżki są
    sprawdzane przed zmianą, komunikat wymienia każdą złą, a skarbiec, LOG i git zostają bez zmian."""
    sk = dane["sk"]
    _notatka(sk, "pojecia/dobra", "Dobra", "Istnieje.", ["pojecia/_hub-pojecia"])
    _notatka(sk, "pojecia/druga dobra", "Druga dobra", "Istnieje.", ["pojecia/_hub-pojecia"])
    log = (sk.root / "LOG.md").read_text(encoding="utf-8")
    kod = _cli(dane, "archiwizuj", "pojecia/dobra", "pojecia/literowka", "pojecia/druga dobra", "user/_hub-ty",
               "pojecia/inna literowka", "--powod", "porządki")
    err = capsys.readouterr().err
    assert kod == 3 and "nic nie zarchiwizowane, popraw 3 z 5" in err
    assert "`pojecia/literowka`: nie ma takiej notatki" in err and "`pojecia/inna literowka`" in err and "`user/_hub-ty`" in err
    assert sk.istnieje("pojecia/dobra") and sk.istnieje("pojecia/druga dobra") and not (sk.root / "archiwum" / "pojecia").exists()
    assert (sk.root / "LOG.md").read_text(encoding="utf-8") == log
    with pytest.raises(ValueError, match="nic nie przeniesione: nie ma notatki `pojecia/brak`; `pojecia/druga dobra` już istnieje"):
        w.przenies_notatki(sk, {"pojecia/brak": "user/brak", "pojecia/dobra": "pojecia/druga dobra"})
    assert sk.istnieje("pojecia/dobra")


def test_napraw_huby_po_starych_przenosinach(dane, capsys):
    """Jednorazowa naprawa skarbca po przenosinach sprzed poprawki (`wiedza.py napraw-huby`, `jarvo wiedza napraw-huby`):
    linia hub każdej notatki wskazuje hub jej folderu; notatka bez linii hub i bez linku do huba folderu dostaje ją;
    notatki poprawne, huby i tożsamość bez zmian; drugi przebieg nic nie zmienia."""
    sk = dane["sk"]
    _notatka(sk, "pojecia/po przenosinach", "Po przenosinach", "Była w agenci/jarvo.", [])
    sk.zapisz_plik("pojecia/po przenosinach", sk.plik("pojecia/po przenosinach").read_text(encoding="utf-8").replace(
        "## Powiązane\n", "## Powiązane\n- hub: [[agenci/jarvo/_hub-jarvo]]\n- [[user/_hub-ty]]\n"))
    _notatka(sk, "podmioty/bez huba", "Bez huba", "Nie ma linii hub.", ["pojecia/po przenosinach"])
    _notatka(sk, "user/poprawna", "Poprawna", "Ma hub swojego folderu.", ["user/_hub-ty"])
    # kompilator pisze „hub:” przy każdym hubie: dalsze linie hub do innych folderów to linki między folderami
    sk.zapisz_plik("user/poprawna", sk.plik("user/poprawna").read_text(encoding="utf-8").replace(
        "- [[user/_hub-ty]]", "- hub: [[user/_hub-ty]]\n- hub: [[agenci/jarvo/_hub-jarvo]]"))
    _notatka(sk, "pojecia/jedyny link", "Jedyny link", "Jedyną drogą do innego folderu był dawny hub.", [])
    sk.zapisz_plik("pojecia/jedyny link", sk.plik("pojecia/jedyny link").read_text(encoding="utf-8").replace(
        "## Powiązane\n", "## Powiązane\n- hub: [[agenci/jarvo/_hub-jarvo|Jarvo]]\n- [[pojecia/po przenosinach]]\n"))
    poprawna = sk.plik("user/poprawna").read_text(encoding="utf-8")
    tozsamosc = sk.plik("jarvo/kim jest jarvo").read_text(encoding="utf-8")
    ix = w.Indeks(sk)
    przed = [o for o in w.lint(sk, ix)["ostrzezenia"] if "bez linku do huba folderu" in o]
    ix.zamknij()
    assert any("po przenosinach" in o for o in przed) and any("bez huba" in o for o in przed)
    assert _cli(dane, "napraw-huby") == 0
    out = capsys.readouterr().out
    assert "- pojecia/po przenosinach" in out and "- podmioty/bez huba" in out and "user/poprawna" not in out
    t = sk.plik("pojecia/po przenosinach").read_text(encoding="utf-8")
    assert "- hub: [[pojecia/_hub-pojecia]]\n- [[user/_hub-ty]]" in t
    assert "## Powiązane\n- hub: [[podmioty/_hub-podmioty]]\n- [[pojecia/po przenosinach]]" in sk.plik("podmioty/bez huba").read_text(encoding="utf-8")
    assert sk.plik("user/poprawna").read_text(encoding="utf-8") == poprawna
    assert ("- hub: [[pojecia/_hub-pojecia|Pojęcia]]\n- [[agenci/jarvo/_hub-jarvo]]\n- [[pojecia/po przenosinach]]"
            in sk.plik("pojecia/jedyny link").read_text(encoding="utf-8"))          # jedyny link do innego folderu zostaje
    assert sk.plik("jarvo/kim jest jarvo").read_text(encoding="utf-8") == tozsamosc
    assert "naprawa | naprawa linii hub w notatkach\n- podmioty/bez huba\n- pojecia/jedyny link\n- pojecia/po przenosinach" in (sk.root / "LOG.md").read_text(encoding="utf-8")
    ix = w.Indeks(sk)
    po = w.lint(sk, ix)["ostrzezenia"]
    ix.zamknij()
    assert not [o for o in po if "bez linku do huba folderu" in o]
    assert not [o for o in po if "bez linku do innego folderu" in o and ("jedyny link" in o or "poprawna" in o)]
    log = (sk.root / "LOG.md").read_text(encoding="utf-8")
    assert _cli(dane, "napraw-huby") == 0 and "poprawione: 0" in capsys.readouterr().out
    assert (sk.root / "LOG.md").read_text(encoding="utf-8") == log                   # drugi przebieg: nic, bez wpisu w LOG
