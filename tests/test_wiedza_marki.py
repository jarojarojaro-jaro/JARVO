"""Agent biznesowy (fleet.yaml `marka`, docs/WIEDZA.md „Agenci biznesowi”): w skarbcu widzi tylko `brands/<marka>/`,
`agenci/<siebie>/`, `fleet/`, `inspiracje/` i orzeczenia swoje, swojej marki i wszystkich. Szukanie (słowa i wektory),
czytanie, przypomnienia, szkice, orzeczenia, strażnik narzędzi plików i kompilacja; agent bez marki widzi wszystko."""
import importlib.util
import json
import re
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "wiedza"))
import wiedza as w  # noqa: E402
import kompilacja as k  # noqa: E402
from atrapa_wektorow import AtrapaWektorow, usluga_atrapy  # noqa: E402

# stub interfejsu Hermesa (jak w test_wiedza_plugin.py): agent/memory_provider.py bez importu Hermesa
if "agent.memory_provider" not in sys.modules:
    agent_pkg = types.ModuleType("agent")
    mp = types.ModuleType("agent.memory_provider")

    class MemoryProvider:                      # noqa: D401 - stub
        pass

    class _Thread:
        def __init__(self, target, name): self.target = target
        def start(self): pass

    mp.MemoryProvider = MemoryProvider
    mp.is_trivial_prompt = lambda text: not text or len(text.strip()) < 4 or text.strip().startswith("/")
    mp.spawn_context_thread = lambda target, *, name, daemon=True: _Thread(target, name)
    agent_pkg.memory_provider = mp
    sys.modules["agent"], sys.modules["agent.memory_provider"] = agent_pkg, mp

if "jarvo_wiedza_plugin" in sys.modules:
    pl = sys.modules["jarvo_wiedza_plugin"]
else:
    spec = importlib.util.spec_from_file_location("jarvo_wiedza_plugin", REPO / "wiedza" / "plugin" / "__init__.py")
    pl = importlib.util.module_from_spec(spec)
    sys.modules["jarvo_wiedza_plugin"] = pl
    spec.loader.exec_module(pl)


def _agent(name, short, **extra):
    return {"name": name, "short": short, "title": short, "emoji": "", "kind": "specialist", "description": f"Agent {short}.",
            "room": "office", "label": short, "telegram_topic": short.lower(), "autonomy_max": "A1", "skills": [], "scripts": [], **extra}


FLEET = {"orchestrator": "jarvo", "agents": [_agent("jarvo", "Jarvo"), _agent("jarvo-web", "Web"),
                                             _agent("jarvo-jarodev", "Jarodev", marka="jarodev", handle="jarodev")]}
ZAKRES = ("brands/jarodev/", "agenci/jarvo-jarodev/", "fleet/", "inspiracje/", "orzeczenia/jarodev", "orzeczenia/marki/jarodev",
          "orzeczenia/wszyscy")


def notatka(sk, rel, tytul, tresc, typ="fakt", **fm):
    front = {"typ": typ, "tagi": ["test"], "utworzono": "2026-11-01", "zmieniono": "2026-11-01", "status": "aktualna", "zrodlo": "karta t_1", **fm}
    sk.zapisz_plik(rel, w.sklej(front, f"# {tytul}\n\n**{tresc}**\n\n## Powiązane\n- [[brands/_hub-marki|Marki]]\n"))


@pytest.fixture
def skarbiec(tmp_path, monkeypatch):
    """Dane floty jak natywnie: <root>/jarvo/knowledge i state, profile <root>/profiles/<agent>."""
    monkeypatch.setenv("WIEDZA_DZIS", "2026-11-14")
    for zmienna in ("JARVO_KNOWLEDGE_DIR", "JARVO_STATE_DIR", "HERMES_HOME"):
        monkeypatch.delenv(zmienna, raising=False)
    monkeypatch.setattr(pl, "CISZA_S", 0)
    root = tmp_path / "data"
    kn, stan = root / "jarvo" / "knowledge", root / "jarvo" / "state"
    for a in FLEET["agents"]:
        (root / "profiles" / a["name"]).mkdir(parents=True)
    fleet = tmp_path / "fleet.json"
    fleet.write_text(json.dumps(FLEET, ensure_ascii=False), encoding="utf-8")
    assert w.main(["--skarbiec", str(kn), "--stan", str(stan), "zasiej", "--fleet", str(fleet)]) == 0
    sk = w.Skarbiec(kn, stan)
    notatka(sk, "projekty/strona pani basi", "Strona pani Basi", "Strona internetowa dla pani Basi: wizytówka salonu fryzjerskiego.", typ="projekt")
    notatka(sk, "user/firma wlasciciela", "Firma właściciela", "Właściciel robi strona internetowa i automatyzacje dla firm.")
    notatka(sk, "brands/enigmalabz/kernel gpu", "Kernel GPU Enigma", "Silnik GPU Enigmalabz: strona internetowa produktu i kernel.")
    sk.plik("brands/enigmalabz/BRAND.md").write_text("# Brand kit: Enigmalabz\n\nStrona internetowa enigmalabz, kolory czarne.\n", encoding="utf-8")
    notatka(sk, "brands/jarodev/oferta jarodev", "Oferta Jarodev", "Jarodev: strona internetowa i automatyzacja dla małych firm.")
    sk.plik("brands/jarodev/BRAND.md").write_text("# Brand kit: Jarodev\n\nStrona internetowa jarodev.pl, kolory granatowe.\n", encoding="utf-8")
    notatka(sk, "agenci/jarvo-jarodev/lejek klientow", "Lejek klientów", "Lejek: grupy na Facebooku, kto szuka strona internetowa.",
            agent="jarvo-jarodev")
    notatka(sk, "agenci/jarvo-web/lighthouse", "Lighthouse w Chromium", "Web mierzy strona internetowa Lighthouse w Chromium.", agent="jarvo-web")
    notatka(sk, "fleet/strona w tydzien", "Strona w tydzień", "Lekcja floty: strona internetowa w tydzień, bez dziur w treści.", typ="lekcja")
    w.dodaj_orzeczenie(sk, "wszyscy", "Odpowiadaj po polsku", "człowiek")
    w.dodaj_orzeczenie(sk, "marki/jarodev", "Ceny podawaj brutto", "człowiek")
    w.dodaj_orzeczenie(sk, "marki/enigmalabz", "Kernel nazywaj silnikiem Enigmy", "człowiek")
    w.dodaj_orzeczenie(sk, "jarvo-jarodev", "Posty publikuj dopiero po tak właściciela", "człowiek")
    assert w.main(["--skarbiec", str(kn), "--stan", str(stan), "indeksuj"]) == 0
    return root, sk


def provider(root, agent):
    p = pl.SkarbiecProvider()
    p.initialize("sesja-marki", hermes_home=str(root / "profiles" / agent), platform="api_server", agent_context="primary")
    return p


def szukaj(p, **args):
    return json.loads(p.handle_tool_call("wiedza_szukaj", {"zapytanie": "strona internetowa", "limit": 12, **args}))


def test_zasiew_niesie_marke_i_hub_marki(skarbiec):
    root, sk = skarbiec
    meta = json.loads((sk.stan / "wiedza-agenci.json").read_text(encoding="utf-8"))
    assert meta["jarvo-jarodev"]["marka"] == "jarodev" and "marka" not in meta["jarvo"] and "marka" not in meta["jarvo-web"]
    assert meta["jarvo-jarodev"]["orzeczenia"] == "orzeczenia/jarodev"
    hub = sk.wczytaj("brands/jarodev/_hub-jarodev")
    assert hub.fm["typ"] == "hub" and "[[orzeczenia/marki/jarodev|" in hub.tresc
    assert "brands/jarodev/oferta jarodev" in hub.tresc                          # lista automatyczna marki (indeksuj)
    assert "marka: [[brands/jarodev/_hub-jarodev|jarodev]]" in sk.wczytaj("agenci/jarvo-jarodev/_hub-jarodev").tresc
    assert "marka:" not in sk.wczytaj("agenci/jarvo-web/_hub-web").tresc
    assert sk.istnieje("orzeczenia/marki/jarodev")
    assert w.zakres_marki("jarodev", "jarvo-jarodev", "orzeczenia/jarodev") == ZAKRES
    assert w.zakres_marki("") == () and w.zakres_marki("../x") == ()
    ix = w.Indeks(sk)
    try:
        bledy = [b for b in w.lint(sk, ix)["bledy"] if "jarodev" in b]
    finally:
        ix.zamknij()
    assert bledy == []


def test_szukaj_tylko_w_zakresie_marki(skarbiec):
    root, sk = skarbiec
    p = provider(root, "jarvo-jarodev")
    wyn = szukaj(p)
    sciezki = [r["sciezka"] for r in wyn["wyniki"]]
    assert "brands/jarodev/oferta jarodev" in sciezki and "agenci/jarvo-jarodev/lejek klientow" in sciezki
    assert "fleet/strona w tydzien" in sciezki
    assert all(w.w_zakresie(s, ZAKRES) for s in sciezki), sciezki
    assert "enigma" not in json.dumps(wyn, ensure_ascii=False).lower() and "basi" not in json.dumps(wyn, ensure_ascii=False).lower()
    assert len([r for r in szukaj(p, limit=2)["wyniki"] if r["typ"] != "orzeczenia"]) == 2     # limit liczony w zakresie
    for zly in ("projekty", "user", "brands/enigmalabz", "agenci/jarvo-web", "rozmowy"):
        blad = szukaj(p, folder=zly)["error"]
        assert "poza Twoim zakresem" in blad and "`brands/jarodev`" in blad, zly
    assert {r["sciezka"] for r in szukaj(p, folder="brands")["wyniki"]} <= {"brands/jarodev/oferta jarodev", "brands/jarodev/BRAND",
                                                                                "orzeczenia/marki/jarodev"}
    assert [r["sciezka"] for r in szukaj(p, folder="brands/jarodev")["wyniki"]]


def test_szukaj_wektorami_tylko_w_zakresie(skarbiec):
    root, sk = skarbiec
    ix = w.Indeks(sk)
    try:
        ix.odswiez()
        ix.odswiez_wektory(AtrapaWektorow())
        wyn = ix.szukaj("strona internetowa enigmalabz kernel", limit=5, wektory=AtrapaWektorow(), zakres=ZAKRES)
        assert ix.silnik == "wektory" and wyn and all(w.w_zakresie(r["sciezka"], ZAKRES) for r in wyn)
        wszystkie = ix.szukaj("strona internetowa enigmalabz kernel", limit=5, wektory=AtrapaWektorow())
        assert any(r["sciezka"].startswith("brands/enigmalabz/") for r in wszystkie)     # bez zakresu: cały skarbiec
    finally:
        ix.zamknij()
    with usluga_atrapy(sk.stan):                                                 # wtyczka przez usługę wektorów
        assert w.main(["--skarbiec", str(sk.root), "--stan", str(sk.stan), "indeksuj"]) == 0
        sciezki = [r["sciezka"] for r in szukaj(provider(root, "jarvo-jarodev"), zapytanie="kernel gpu enigmalabz")["wyniki"]]
        assert all(w.w_zakresie(s, ZAKRES) for s in sciezki), sciezki


def test_czytaj_tylko_w_zakresie(skarbiec):
    root, sk = skarbiec
    p = provider(root, "jarvo-jarodev")

    def czytaj(s):
        return json.loads(p.handle_tool_call("wiedza_czytaj", {"sciezka": s}))
    for dozwolona in ("brands/jarodev/oferta jarodev", "brands/jarodev/BRAND", "agenci/jarvo-jarodev/lejek klientow",
                      "fleet/strona w tydzien", "orzeczenia/wszyscy", "orzeczenia/marki/jarodev", "orzeczenia/jarodev"):
        assert "tresc" in czytaj(dozwolona), dozwolona
    for zakazana in ("projekty/strona pani basi", "user/firma wlasciciela", "brands/enigmalabz/kernel gpu", "brands/enigmalabz/BRAND",
                     "brands/jarodev/../enigmalabz/kernel gpu", "orzeczenia/marki/enigmalabz", "agenci/jarvo-web/lighthouse",
                     "brands/_hub-marki", "_hub-skarbiec"):
        odp = czytaj(zakazana)
        assert "tresc" not in odp and "poza Twoim zakresem" in odp["error"] and "wiedza_szukaj" in odp["error"], zakazana


def test_przypomnienie_i_prompt_agenta_marki(skarbiec):
    root, sk = skarbiec
    p = provider(root, "jarvo-jarodev")
    blok = p.system_prompt_block()
    assert blok.startswith("# Skarbiec wiedzy (jarvo-wiedza): zakres marki `jarodev`") and "`brands/jarodev/`" in blok
    assert "Masz wspólny skarbiec" not in blok
    r = p.prefetch("klient pyta o strona internetowa dla firmy enigmalabz kernel")
    assert "brands/jarodev/oferta jarodev" in r or "agenci/jarvo-jarodev/lejek klientow" in r
    for notatka_ in re.findall(r"^- `([^`]+)`", r, re.M):
        assert w.w_zakresie(notatka_, ZAKRES), notatka_
    assert "enigma" not in r.lower() and "basi" not in r.lower() and "projekty/" not in r
    assert "Ceny podawaj brutto" in r and "Posty publikuj dopiero po tak właściciela" in r and "Odpowiadaj po polsku" in r
    schematy = {t["name"]: t for t in p.get_tool_schemas()}
    assert schematy["wiedza_orzeczenie"]["parameters"]["properties"]["kogo"]["description"] == "ja (ten agent) albo marki/jarodev; domyślnie ja"
    assert "brands/jarodev" in schematy["wiedza_szukaj"]["parameters"]["properties"]["folder"]["description"]


def test_agent_bez_marki_widzi_wszystko(skarbiec):
    root, sk = skarbiec
    p = provider(root, "jarvo")
    sciezki = {r["sciezka"] for r in szukaj(p)["wyniki"]}
    assert {"projekty/strona pani basi", "brands/enigmalabz/kernel gpu", "brands/jarodev/oferta jarodev"} <= sciezki
    assert "tresc" in json.loads(p.handle_tool_call("wiedza_czytaj", {"sciezka": "projekty/strona pani basi"}))
    assert "error" not in szukaj(p, folder="projekty")
    assert p.system_prompt_block().startswith("# Skarbiec wiedzy floty (jarvo-wiedza)\nMasz wspólny skarbiec wiedzy floty:")
    r = p.prefetch("kernel gpu enigmalabz")
    assert "brands/enigmalabz/kernel gpu" in r and "Kernel nazywaj silnikiem Enigmy" in r
    schematy = {t["name"]: t for t in p.get_tool_schemas()}
    assert schematy["wiedza_orzeczenie"]["parameters"]["properties"]["kogo"]["description"] == "ja (ten agent), wszyscy albo marki/<marka>; domyślnie ja"
    z = json.loads(p.handle_tool_call("wiedza_zapisz", {"typ": "fakt", "tytul": "Fakt Jarva", "tresc": "Treść.", "zrodlo": "rozmowa"}))
    assert "marka" not in w.podziel((sk.root / f"{z['szkic']}.md").read_text(encoding="utf-8"))[0]


def test_szkic_i_lustro_pamieci_niosa_marke(skarbiec):
    root, sk = skarbiec
    p = provider(root, "jarvo-jarodev")
    z = json.loads(p.handle_tool_call("wiedza_zapisz", {"typ": "fakt", "tytul": "Piekarnia chce stronę", "tresc": "Piekarnia z Lublina pyta o stronę.",
                                                        "zrodlo": "grupa FB"}))
    fm, _ = w.podziel((sk.root / f"{z['szkic']}.md").read_text(encoding="utf-8"))
    assert fm["marka"] == "jarodev" and fm["agent"] == "jarvo-jarodev"
    p.on_memory_write("add", "memory", "Właściciel odpowiada klientom wieczorem (rozmowa 2026-11-14)")
    fm, _ = w.podziel((sk.root / "skrzynka/pamiec-jarvo-jarodev.md").read_text(encoding="utf-8"))
    assert fm["marka"] == "jarodev"


def test_orzeczenie_agenta_marki_tylko_ja_albo_marka(skarbiec):
    root, sk = skarbiec
    p = provider(root, "jarvo-jarodev")
    p.on_turn_start(1, "Nie, ceny w ofertach zawsze podawaj z VAT, brutto, nigdy netto.")
    cytat = "ceny w ofertach zawsze podawaj z VAT"
    for kogo in ("wszyscy", "marki/enigmalabz", "jarvo-web", "web"):
        odp = json.loads(p.handle_tool_call("wiedza_orzeczenie", {"kogo": kogo, "tresc": "Ceny brutto", "cytat": cytat}))
        assert "tylko dla siebie" in odp["error"] and "marki/jarodev" in odp["error"], kogo
    assert "Ceny brutto" not in (sk.root / "orzeczenia/wszyscy.md").read_text(encoding="utf-8")
    ok = json.loads(p.handle_tool_call("wiedza_orzeczenie", {"kogo": "marki/jarodev", "tresc": "Ceny w ofertach brutto", "cytat": cytat}))
    assert "Ceny w ofertach brutto" in ok["orzeczenie"]
    for kogo in ("ja", "jarodev", "jarvo-jarodev"):
        ok = json.loads(p.handle_tool_call("wiedza_orzeczenie", {"kogo": kogo, "tresc": f"Ceny z VAT {kogo}", "cytat": cytat}))
        assert "orzeczenie" in ok, kogo
    assert "Ceny z VAT jarodev" in (sk.root / "orzeczenia/jarodev.md").read_text(encoding="utf-8")


def test_straznik_narzedzi_plikow_w_zakresie_marki(skarbiec, monkeypatch):
    root, sk = skarbiec
    kn = sk.root
    monkeypatch.setenv("HERMES_HOME", str(root / "profiles" / "jarvo-jarodev"))
    for narzedzie, sciezka in (("read_file", "projekty/strona pani basi.md"), ("read_file", "brands/enigmalabz/BRAND.md"),
                               ("read_file", "orzeczenia/marki/enigmalabz.md"), ("search_files", ""), ("search_files", "brands"),
                               ("search_files", "projekty"), ("write_file", "brands/enigmalabz/BRAND.md"),
                               ("read_file", "brands/jarodev/../enigmalabz/BRAND.md")):
        blok = pl.straznik(tool_name=narzedzie, args={"path": str(kn / sciezka) if sciezka else str(kn), "pattern": "x"})
        assert blok and blok["action"] == "block" and "poza Twoim zakresem" in blok["message"] and "wiedza_szukaj" in blok["message"], (narzedzie, sciezka)
    v4a = f"*** Begin Patch\n*** Update File: {kn / 'user/firma wlasciciela.md'}\n@@\n-a\n+b\n*** End Patch"
    assert pl.straznik(tool_name="patch", args={"mode": "patch", "patch": v4a})["action"] == "block"
    for narzedzie, sciezka in (("read_file", "brands/jarodev/BRAND.md"), ("read_file", "agenci/jarvo-jarodev/lejek klientow.md"),
                               ("search_files", "fleet"), ("search_files", "brands/jarodev"), ("read_file", "orzeczenia/wszyscy.md"),
                               ("write_file", "brands/jarodev/BRAND.md"), ("read_file", "inspiracje/strony/x/y.md")):
        assert pl.straznik(tool_name=narzedzie, args={"path": str(kn / sciezka), "pattern": "x"}) is None, (narzedzie, sciezka)
    zapis = pl.straznik(tool_name="write_file", args={"path": str(kn / "agenci/jarvo-jarodev/lejek klientow.md"), "content": "x"})
    assert zapis["action"] == "block" and "pisze tylko kompilacja" in zapis["message"]          # w zakresie, ale notatka
    assert pl.straznik(tool_name="read_file", args={"path": str(root / "workspaces" / "raport.md")}) is None
    monkeypatch.setenv("HERMES_HOME", str(root / "profiles" / "jarvo"))                           # bez marki: bez zmian
    assert pl.straznik(tool_name="read_file", args={"path": str(kn / "projekty/strona pani basi.md")}) is None
    assert pl.straznik(tool_name="search_files", args={"path": str(kn), "pattern": "x"}) is None


def _model(odpowiedzi):
    prompty, kolejka = [], list(odpowiedzi)

    def f(system, user):
        prompty.append(user)
        return json.dumps(kolejka.pop(0) if kolejka else {"wyniki": []}, ensure_ascii=False)
    f.prompty = prompty
    return f


def test_kompilacja_kladzie_szkic_marki_w_brands(skarbiec, monkeypatch):
    root, sk = skarbiec
    monkeypatch.setattr(k, "ROWNOLEGLE", 1)
    w.zapisz_szkic(sk, "projekt", "Strona dla piekarni", "Piekarnia z Lublina chce strona internetowa z menu.", "grupa FB",
                   "jarvo-jarodev", ["lead"], skad="test", marka="jarodev")
    model = _model([
        {"wyniki": [{"decyzja": "nowa", "sciezka": "projekty/strona dla piekarni", "typ": "projekt", "tytul": "Strona dla piekarni",
                     "streszczenie": "Piekarnia z Lublina chce stronę z menu", "tresc": "Piekarnia z Lublina pyta o stronę z menu.",
                     "linki": ["projekty/strona pani basi", "brands/enigmalabz/kernel gpu", "brands/jarodev/oferta jarodev"]},
                    {"decyzja": "aktualizacja", "sciezka": "projekty/strona pani basi", "typ": "projekt", "tytul": "Piekarnia: termin",
                     "streszczenie": "Termin piekarni to grudzień", "tresc": "Piekarnia chce stronę do grudnia."},
                    {"decyzja": "aktualizacja", "sciezka": "brands/jarodev/BRAND", "typ": "fakt", "tytul": "Kolory piekarni",
                     "streszczenie": "Piekarnia lubi brąz", "tresc": "Piekarnia chce brązowe kolory."}]}])
    przed_basia = (sk.root / "projekty/strona pani basi.md").read_text(encoding="utf-8")
    przed_kit = (sk.root / "brands/jarodev/BRAND.md").read_text(encoding="utf-8")
    r = k.Kompilacja(sk, model).uruchom()
    prompt = model.prompty[0]
    assert "Marka agenta: jarodev. Notatki tylko w folderach: brands/jarodev/, agenci/jarvo-jarodev/" in prompt
    assert "enigma" not in prompt.lower() and "projekty/" not in prompt and "user/" not in prompt and "pani basi" not in prompt.lower()
    assert "- brands/jarodev/_hub-jarodev" in prompt and "Ceny podawaj brutto" in prompt and "Kernel nazywaj" not in prompt
    assert r["nowe"] == 3 and all(n.startswith("brands/jarodev/") for n in r["notatki"]), r["notatki"]
    nowa = sk.wczytaj("brands/jarodev/strona dla piekarni")
    cele = [c for c, _e, _a in nowa.linki]
    assert cele[0] == "brands/jarodev/_hub-jarodev" and "brands/jarodev/oferta jarodev" in cele
    assert all(w.w_zakresie(c, ZAKRES) for c in cele), cele
    assert (sk.root / "projekty/strona pani basi.md").read_text(encoding="utf-8") == przed_basia          # cudza notatka nietknięta
    assert (sk.root / "brands/jarodev/BRAND.md").read_text(encoding="utf-8") == przed_kit                 # brand kit nietknięty
    assert "brands/jarodev/strona dla piekarni" in sk.wczytaj("brands/jarodev/_hub-jarodev").tresc       # lista huba marki
    ix = w.Indeks(sk)
    try:
        assert [b for b in w.lint(sk, ix)["bledy"] if "jarodev" in b] == []
    finally:
        ix.zamknij()


def test_kompilacja_marka_z_agenta_gdy_szkic_jej_nie_ma(skarbiec, monkeypatch):
    """Szkic z karty albo `wiedza.py zapisz` bez pola `marka`: kompilacja bierze markę agenta z wiedza-agenci.json."""
    root, sk = skarbiec
    monkeypatch.setattr(k, "ROWNOLEGLE", 1)
    w.zapisz_szkic(sk, "lekcja", "Grupy FB rano", "Posty w grupach rano mają więcej odpowiedzi.", "karta t_5", "jarvo-jarodev", [], skad="test")
    model = _model([{"wyniki": [{"decyzja": "nowa", "sciezka": "pojecia/grupy fb rano", "typ": "lekcja", "tytul": "Grupy FB rano",
                                 "streszczenie": "Posty rano mają więcej odpowiedzi", "tresc": "Posty w grupach rano mają więcej odpowiedzi.",
                                 "linki": []}]}])
    r = k.Kompilacja(sk, model).uruchom()
    assert r["notatki"] == ["brands/jarodev/grupy fb rano"]
    assert not (sk.root / "pojecia/grupy fb rano.md").exists()
