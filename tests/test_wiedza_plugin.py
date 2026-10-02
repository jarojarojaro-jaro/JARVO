"""Wtyczka jarvo-wiedza (wiedza/plugin): dostawca pamięci na stubie interfejsu Hermesa (agent.memory_provider),
przypomnienia, narzędzia, strażnik orzeczeń, lustro pamięci, wyciągi (model podstawiony), hak kanbana."""
import importlib.util
import json
import sqlite3
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "wiedza"))
import wiedza as w  # noqa: E402

# stub interfejsu Hermesa: to samo API co agent/memory_provider.py (bez importu Hermesa w testach)
if "agent.memory_provider" not in sys.modules:
    agent_pkg = types.ModuleType("agent")
    mp = types.ModuleType("agent.memory_provider")

    class MemoryProvider:                      # noqa: D401 - stub
        def system_prompt_block(self): return ""
        def prefetch(self, query, *, session_id=""): return ""
        def sync_turn(self, *a, **k): pass
        def on_session_end(self, messages): pass
        def on_pre_compress(self, messages): return ""
        def on_memory_write(self, *a, **k): pass
        def on_turn_start(self, *a, **k): pass
        def shutdown(self): pass

    def is_trivial_prompt(text):
        return not text or len(text.strip()) < 4 or text.strip().lower() in {"ok", "hej", "cześć", "dzięki"} or text.strip().startswith("/")

    class _Thread:
        def __init__(self, target, name): self.target = target
        def start(self): pass

    mp.MemoryProvider, mp.is_trivial_prompt = MemoryProvider, is_trivial_prompt
    mp.spawn_context_thread = lambda target, *, name, daemon=True: _Thread(target, name)
    agent_pkg.memory_provider = mp
    sys.modules["agent"], sys.modules["agent.memory_provider"] = agent_pkg, mp

spec = importlib.util.spec_from_file_location("jarvo_wiedza_plugin", REPO / "wiedza" / "plugin" / "__init__.py")
pl = importlib.util.module_from_spec(spec)
sys.modules["jarvo_wiedza_plugin"] = pl
spec.loader.exec_module(pl)

FLEET = {"orchestrator": "jarvo", "agents": [
    {"name": "jarvo-web", "short": "Web", "title": "Web Senior Dev", "emoji": "🌐", "kind": "specialist", "description": "Strony i SEO.",
     "room": "devlab", "label": "Pracownia", "telegram_topic": "web", "autonomy_max": "A1",
     "skills": [{"name": "nowa-strona", "description": "Nowa strona."}], "scripts": ["audit.sh"]}]}


@pytest.fixture
def srodowisko(tmp_path, monkeypatch):
    """Dane floty jak na VPS: <root>/jarvo/knowledge, <root>/jarvo/state, HERMES_HOME profilu = <root>/profiles/jarvo-web."""
    monkeypatch.setenv("WIEDZA_DZIS", "2026-09-30")
    monkeypatch.delenv("JARVO_KNOWLEDGE_DIR", raising=False)
    monkeypatch.delenv("JARVO_STATE_DIR", raising=False)
    root = tmp_path / "data"
    home = root / "profiles" / "jarvo-web"
    home.mkdir(parents=True)
    (root / "jarvo" / "knowledge" / "brands" / "acme").mkdir(parents=True)
    (root / "jarvo" / "knowledge" / "brands" / "acme" / "BRAND.md").write_text("# Acme\nKolory: czerwony.\n", encoding="utf-8")
    fleet = tmp_path / "fleet.json"
    fleet.write_text(json.dumps(FLEET, ensure_ascii=False), encoding="utf-8")
    assert w.main(["--skarbiec", str(root / "jarvo" / "knowledge"), "--stan", str(root / "jarvo" / "state"), "zasiej", "--fleet", str(fleet)]) == 0
    sk = w.Skarbiec(root / "jarvo" / "knowledge", root / "jarvo" / "state")
    sk.zapisz_plik("agenci/jarvo-web/lightpanda nie renderuje three.js", w.sklej(
        {"typ": "fakt", "tagi": ["web"], "utworzono": "2026-09-30", "zmieniono": "2026-09-30", "status": "aktualna", "zrodlo": "karta t_1", "agent": "jarvo-web"},
        "# Lightpanda nie renderuje three.js\n\n**Zrzuty stron z WebGL robimy Chromium, bo Lightpanda daje pusty kadr.**\n\n## Powiązane\n- [[agenci/jarvo-web/_hub-web|Web]]\n"))
    w.dodaj_orzeczenie(sk, "jarvo-web", "W stronach użytkownika nie używaj innerHTML", "rozmowa HQ")
    w.dodaj_orzeczenie(sk, "wszyscy", "Odpowiadaj po polsku", "człowiek")
    w.dodaj_orzeczenie(sk, "marki/acme", "Przyciski zaokrąglone", "rozmowa")
    p = pl.SkarbiecProvider()
    p.initialize("sesja-123", hermes_home=str(home), platform="api_server", agent_context="primary")
    return root, home, sk, p


def test_blok_promptu_i_przypomnienie(srodowisko):
    root, home, sk, p = srodowisko
    blok = p.system_prompt_block()
    assert "agenci/jarvo-web/_hub-web" in blok and "orzeczenia/web" in blok and "wiedza_orzeczenie" in blok
    assert p.prefetch("ok") == "" and p.prefetch("/new") == ""
    r = p.prefetch("czemu zrzut strony z three.js jest pusty?")
    assert "`agenci/jarvo-web/lightpanda nie renderuje three.js`" in r and "Zrzuty stron z WebGL" in r
    assert "## Orzeczenia (wiążące)" in r and "[web] W stronach użytkownika nie używaj innerHTML" in r and "[wszyscy] Odpowiadaj po polsku" in r
    assert "Przyciski zaokrąglone" not in r                                       # orzeczenia marki tylko przy trafieniu w markę
    r2 = p.prefetch("jakie kolory ma marka Acme?")
    assert "brands/acme/BRAND" in r2 and "[acme] Przyciski zaokrąglone" in r2
    dziennik = (root / "jarvo" / "state" / "wiedza-przypomnienia.jsonl").read_text(encoding="utf-8").splitlines()
    wpis = json.loads(dziennik[-1])
    assert wpis["agent"] == "jarvo-web" and wpis["zapytanie"] == "jakie kolory ma marka Acme?" and "brands/acme/BRAND" in wpis["notatki"]
    assert wpis["orzeczen"] >= 3 and wpis["sesja"] == "sesja-123" and wpis["znakow"] == len(r2)
    assert len(r2) <= pl.MAX_PRZYPOMNIENIA
    assert p.prefetch("o niczym konkretnym xyzzy") .startswith("## Orzeczenia")   # bez trafień zostają orzeczenia


def test_narzedzia(srodowisko):
    root, home, sk, p = srodowisko
    nazwy = [t["name"] for t in p.get_tool_schemas()]
    assert nazwy == ["wiedza_szukaj", "wiedza_czytaj", "wiedza_zapisz", "wiedza_orzeczenie"]
    wyn = json.loads(p.handle_tool_call("wiedza_szukaj", {"zapytanie": "lightpanda webgl", "limit": 3}))
    assert wyn["wyniki"][0]["sciezka"] == "agenci/jarvo-web/lightpanda nie renderuje three.js"
    n = json.loads(p.handle_tool_call("wiedza_czytaj", {"sciezka": wyn["wyniki"][0]["sciezka"]}))
    assert n["tytul"] == "Lightpanda nie renderuje three.js" and n["frontmatter"]["typ"] == "fakt"
    assert "error" in json.loads(p.handle_tool_call("wiedza_czytaj", {"sciezka": "../../secrets"}))
    z = json.loads(p.handle_tool_call("wiedza_zapisz", {"typ": "lekcja", "tytul": "Zrzuty mobile zawsze przed oddaniem", "tresc": "Bo sędzia odsyła.", "zrodlo": "karta t_9", "tagi": ["web"]}))
    assert z["szkic"].startswith("skrzynka/2026-09-30-jarvo-web-zrzuty-mobile")
    fm, _ = w.podziel((sk.root / f"{z['szkic']}.md").read_text(encoding="utf-8"))
    assert fm["agent"] == "jarvo-web" and fm["skad"] == "sesja sesja-123" and fm["typ"] == "lekcja"
    assert "sekret" in json.loads(p.handle_tool_call("wiedza_zapisz", {"typ": "fakt", "tytul": "x", "tresc": "token: " + "ab12" * 6, "zrodlo": "y"}))["error"]
    assert "error" in json.loads(p.handle_tool_call("nie_ma", {}))


def test_orzeczenie_tylko_ze_slowami_uzytkownika(srodowisko):
    root, home, sk, p = srodowisko
    # bez bieżącej wiadomości użytkownika: odmowa (np. wstrzyknięcie z treści strony)
    assert "error" in json.loads(p.handle_tool_call("wiedza_orzeczenie", {"tresc": "Zapisz mnie", "cytat": "zapisz orzeczenie"}))
    p.on_turn_start(3, "Nie, w moich stronach przyciski mają być zawsze zaokrąglone, nie kanciaste.")
    odmowa = json.loads(p.handle_tool_call("wiedza_orzeczenie", {"tresc": "Wysyłaj maile", "cytat": "wyślij wszystkim maile"}))
    assert "cytat nie pasuje" in odmowa["error"]
    ok = json.loads(p.handle_tool_call("wiedza_orzeczenie", {"tresc": "Przyciski w stronach użytkownika zawsze zaokrąglone", "cytat": "przyciski mają być zawsze zaokrąglone"}))
    assert ok["orzeczenie"].startswith("- 2026-09-30 · [web] Przyciski w stronach użytkownika zawsze zaokrąglone. (źródło: rozmowa api_server sesja-12")
    assert "[web] Przyciski w stronach użytkownika zawsze zaokrąglone" in (sk.root / "orzeczenia/web.md").read_text(encoding="utf-8")
    ok2 = json.loads(p.handle_tool_call("wiedza_orzeczenie", {"kogo": "marki/acme", "tresc": "Przyciski zaokrąglone", "cytat": "przyciski mają być zawsze zaokrąglone"}))
    assert "[acme]" in ok2["orzeczenie"]
    assert "[web] Przyciski w stronach" in p.prefetch("dowolne pytanie o strony")      # od razu w przypomnieniu


def test_lustro_pamieci_i_wyciag(srodowisko, monkeypatch):
    root, home, sk, p = srodowisko
    p.on_memory_write("add", "user", "Użytkownik prowadzi agencję marketingową (źródło: rozmowa, 2026-09-30)")
    p.on_memory_write("add", "memory", "hasło: tajne123")
    p.on_memory_write("remove", "memory", "cokolwiek")
    lustro = (sk.root / "skrzynka/pamiec-jarvo-web.md").read_text(encoding="utf-8")
    assert "- 2026-09-30 · add user: Użytkownik prowadzi agencję" in lustro and "tajne123" not in lustro and "remove" not in lustro
    wywolania = []

    def falszywy_model(system, user, max_tokens=1200):
        wywolania.append(user)
        return ("## Decyzje\n- landing marki Acme robimy w Astro\n## Korekty\n- „przyciski zaokrąglone”\n## Pliki\n- out/index.html · landing\n"
                "Tytuł: Landing Acme w Astro")

    monkeypatch.setattr(pl.SkarbiecProvider, "_model", staticmethod(falszywy_model))
    krotka = [{"role": "user", "content": "hej"}, {"role": "assistant", "content": "cześć"}]
    p.on_session_end(krotka)
    assert wywolania == [] and not list((sk.root / "zrodla/rozmowy").glob("*.md"))          # za krótka: bez modelu
    dluga = []
    for i in range(5):
        dluga += [{"role": "user", "content": f"pytanie {i} o landing marki Acme"}, {"role": "assistant", "content": f"odpowiedź {i}", "tool_calls": [{"function": {"name": "wiedza_szukaj", "arguments": "{}"}}]},
                  {"role": "tool", "content": "wynik narzędzia"}]
    tekst = p.on_pre_compress(dluga)
    assert tekst.startswith("Ustalenia z tej części rozmowy zapisano w skarbcu wiedzy: zrodla/rozmowy/2026-09-30-jarvo-web-sesja-12-landing-acme-w-astro")
    assert len(wywolania) == 1 and "UŻYTKOWNIK: pytanie 0" in wywolania[0] and "AGENT (narzędzie wiedza_szukaj)" in wywolania[0] and "NARZĘDZIE: wynik" in wywolania[0]
    zrodlo = (sk.root / "zrodla/rozmowy/2026-09-30-jarvo-web-sesja-12-landing-acme-w-astro.md").read_text(encoding="utf-8")
    fm, tresc = w.podziel(zrodlo)
    assert fm["typ"] == "zrodlo" and fm["zrodlo"].startswith("sesja sesja-123 (api_server, kompresja, tury 1–5)") and "Tytuł:" not in tresc
    szkice = list((sk.root / "skrzynka").glob("2026-09-30-jarvo-web-landing-acme-w-astro-*.md"))
    assert len(szkice) == 1 and w.podziel(szkice[0].read_text(encoding="utf-8"))[0]["typ"] == "rozmowa"
    # koniec sesji: tylko nowe tury (5 już wyciągnięte), dwie nowe to za mało → bez drugiego wywołania
    p.on_session_end(dluga + [{"role": "user", "content": "jeszcze jedno"}, {"role": "assistant", "content": "ok"}])
    assert len(wywolania) == 1
    # cztery nowe tury → drugi wyciąg od tury 6
    p.sync_turn("a", "b", session_id="sesja-123")
    p.on_session_end(dluga + [{"role": "user", "content": f"nowe {i}: dłuższe pytanie o wdrożenie landingu na Vercel i domenę"} for i in range(4)])
    assert len(wywolania) == 2 and "UŻYTKOWNIK: nowe 0" in wywolania[1] and "pytanie 0" not in wywolania[1]
    # sekret w wyciągu → nic nie zapisujemy
    monkeypatch.setattr(pl.SkarbiecProvider, "_model", staticmethod(lambda s, u, max_tokens=1200: "## Fakty\n- klucz sk_live_" + "Q7w" * 8 + "\nTytuł: Klucz"))
    p2 = pl.SkarbiecProvider()
    p2.initialize("sesja-999", hermes_home=str(home), platform="cli", agent_context="primary")
    assert p2.on_pre_compress(dluga) == "" and not list((sk.root / "zrodla/rozmowy").glob("*klucz*"))
    # subagent i cron: tylko odczyt
    p3 = pl.SkarbiecProvider()
    p3.initialize("sub", hermes_home=str(home), platform="subagent", agent_context="subagent")
    assert "error" in json.loads(p3.handle_tool_call("wiedza_zapisz", {"typ": "fakt", "tytul": "x", "tresc": "y", "zrodlo": "z"}))
    assert p3.prefetch("lightpanda three.js") != ""
    p4 = pl.SkarbiecProvider()                                                      # rutyna (cron): szkice tak, wyciągi nie
    p4.initialize("cron", hermes_home=str(home), platform="cron", agent_context="cron")
    assert "szkic" in json.loads(p4.handle_tool_call("wiedza_zapisz", {"typ": "rozmowa", "tytul": "Tydzień floty 2026-09-27", "tresc": "Co się zmieniło.", "zrodlo": "LOG.md"}))
    assert "error" in json.loads(p4.handle_tool_call("wiedza_orzeczenie", {"tresc": "x", "cytat": "y"}))
    assert p4.on_pre_compress(dluga) == ""


def test_hak_kanbana(srodowisko, monkeypatch):
    root, home, sk, p = srodowisko
    monkeypatch.setenv("HERMES_HOME", str(home))
    ws = root / "jarvo" / "workspaces" / "jarvo-web" / "t_abc"
    (ws / "out").mkdir(parents=True)
    (ws / "out" / "RAPORT.md").write_text("# Raport\nLighthouse 97.\n", encoding="utf-8")
    db = sqlite3.connect(root / "kanban.db")
    db.execute("CREATE TABLE tasks(id TEXT PRIMARY KEY, title TEXT, body TEXT, workspace_path TEXT, result TEXT, assignee TEXT, status TEXT)")
    db.execute("INSERT INTO tasks VALUES ('t_abc', 'Landing Acme', 'CEL: landing', ?, 'Gotowe: out/index.html', 'jarvo-web', 'done')", (str(ws),))
    db.commit()
    db.close()
    pl.karta_zamknieta(task_id="t_abc", profile_name="jarvo-web", board="default", assignee="jarvo-web", run_id=7, summary="Landing oddany, Lighthouse 97.")
    kopia = sk.root / "zrodla/karty/2026-09-30-t_abc-raport.md"
    assert kopia.read_text(encoding="utf-8").startswith("# Raport")
    szkic = list((sk.root / "skrzynka").glob("2026-09-30-jarvo-web-karta-landing-acme-*.md"))
    assert len(szkic) == 1
    fm, tresc = w.podziel(szkic[0].read_text(encoding="utf-8"))
    assert fm["typ"] == "projekt" and fm["zrodlo"] == "karta t_abc" and "[[zrodla/karty/2026-09-30-t_abc-raport]]" in tresc and "Lighthouse 97" in tresc
    pl.karta_zamknieta(task_id="nie_ma", assignee="jarvo-web", summary="x")          # brak karty w bazie: szkic bez raportów, bez wyjątku
    assert len(list((sk.root / "skrzynka").glob("*karta-karta-nie-ma*"))) == 1


def test_straznik_pamieci_bez_danych_logowania():
    """Red team: Wideograf zapisał login z czatu w pamięci. Hak pre_tool_call odrzuca to u każdego agenta."""
    for tekst in ("Login do YouTube Studio: jan@firma.pl", "hasło Wiosna2026!", "klucz sk_live_JarvoRedTeam_fake_0000",
                  "PIN do karty 1234", "karta firmowa 4111 1111 1111 1111, ważna 12/28"):
        w = pl.straznik(tool_name="memory", args={"action": "add", "target": "user", "content": tekst})
        assert w and w["action"] == "block" and "danych logowania" in w["message"], tekst
    wsad = {"operations": [{"action": "add", "content": "Raporty w punktach"}, {"action": "add", "new_text": "hasło: Lato2026!"}]}
    assert pl.straznik(tool_name="memory", args=wsad)["action"] == "block"
    for tekst in ("Właściciel woli raporty w punktach (źródło: rozmowa, 2026-10-02)", "hasło do Wi-Fi jest w sejfie",
                  "kontakt do faktur: jan@firma.pl", "NIP 5252344078, konto PL61 1090 1014 0000 0712 1981 2874",
                  "karta lojalnościowa klientów od 2026 roku"):
        assert pl.straznik(tool_name="memory", args={"action": "add", "content": tekst}) is None, tekst
    assert pl.straznik(tool_name="web_search", args={"query": "hasło Wiosna2026!"}) is None    # inne narzędzia bez zmian


def test_straznik_limit_generacji_na_karte(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVO_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("JARVO_LIMIT_WIDEO_AI", "2")
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_film")
    assert pl.straznik(tool_name="video_generate", args={}) is None
    assert pl.straznik(tool_name="video_generate", args={}) is None
    w = pl.straznik(tool_name="video_generate", args={})
    assert w["action"] == "approve" and "2/2" in w["message"] and "A2" in w["message"]
    assert pl.straznik(tool_name="image_generate", args={}) is None                           # osobny limit obrazów (12)
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_inna")
    assert pl.straznik(tool_name="video_generate", args={}) is None                           # licznik na kartę
    stan = json.loads((tmp_path / "state" / "generacje-ai.json").read_text(encoding="utf-8"))
    assert stan == {"t_film": {"video_generate": 2, "image_generate": 1}, "t_inna": {"video_generate": 1}}
