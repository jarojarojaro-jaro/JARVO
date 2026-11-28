"""Wtyczka jarvo-wiedza (wiedza/plugin): dostawca pamięci na stubie interfejsu Hermesa (agent.memory_provider),
przypomnienia, narzędzia, strażnik orzeczeń, lustro pamięci, wyciągi (model podstawiony), hak kanbana."""
import importlib.util
import inspect
import json
import os
import re
import shutil
import sqlite3
import sys
import time
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
    assert "Mam wspólny skarbiec" in blok and "Gdy właściciel mnie poprawia" in blok and "Twój hub" not in blok   # „ja” = agent
    for linia in ("[web] W stronach użytkownika nie używaj innerHTML", "[wszyscy] Odpowiadaj po polsku", "[acme] Przyciski zaokrąglone"):
        assert blok.count(linia) == 1                  # agent bez marki: orzeczenia każdej marki (15.11), raz w prompcie
    assert p.prefetch("ok") == "" and p.prefetch("/new") == ""
    r = p.prefetch("czemu zrzut strony z three.js jest pusty?")
    assert "`agenci/jarvo-web/lightpanda nie renderuje three.js`" in r and "Zrzuty stron z WebGL" in r
    assert "Orzeczenia" not in r and "innerHTML" not in r and "Odpowiadaj po polsku" not in r   # nie co turę (20.11)
    r2 = p.prefetch("jakie kolory ma marka Acme?")
    assert "brands/acme/BRAND" in r2 and "Przyciski zaokrąglone" not in r2
    dziennik = (root / "jarvo" / "state" / "wiedza-przypomnienia.jsonl").read_text(encoding="utf-8").splitlines()
    assert b"\r" not in (root / "jarvo" / "state" / "wiedza-przypomnienia.jsonl").read_bytes()      # LF także na Windows
    wpis = json.loads(dziennik[-1])
    assert wpis["agent"] == "jarvo-web" and wpis["zapytanie"] == "jakie kolory ma marka Acme?" and "brands/acme/BRAND" in wpis["notatki"]
    assert wpis["orzeczen"] == 0 and wpis["sesja"] == "sesja-123" and wpis["znakow"] == len(r2)
    assert len(r2) <= pl.MAX_PRZYPOMNIENIA
    assert p.prefetch("o niczym konkretnym xyzzy") == ""                           # bez trafień: nic przed turą


def test_orzeczenie_dopisane_w_sesji_przed_tura_i_w_nowej_instancji(srodowisko):
    """Prompt jest zamrożony na sesję: orzeczenie dopisane po jego budowie idzie przed turą (tylko ono), także gdy
    brama tworzy agenta od nowa na turę i bierze prompt z bazy (odciski w state/), a po kompresji (nowa sesja,
    blok od nowa) stoi już w prompcie. Prompt nieznany (sesja sprzed tej wersji): orzeczenia jak dawniej."""
    root, home, sk, p = srodowisko
    p.system_prompt_block()
    w.dodaj_orzeczenie(sk, "jarvo-web", "Zawsze podawaj wynik Lighthouse mobile", "rozmowa")
    r = p.prefetch("czemu zrzut strony z three.js jest pusty?")
    assert r.startswith("## Nowe orzeczenia (wiążące od tej tury)\n- 2026-09-30 · [web] Zawsze podawaj wynik Lighthouse mobile.")
    assert "innerHTML" not in r and "lightpanda" in r
    swieza = pl.SkarbiecProvider()                                                   # brama: nowy agent, ten sam prompt
    swieza.initialize("sesja-123", hermes_home=str(home), platform="telegram", agent_context="primary")
    r = swieza.prefetch("czemu zrzut strony z three.js jest pusty?")
    assert "Lighthouse mobile" in r and "innerHTML" not in r
    p.system_prompt_block()                                                          # kompresja: blok od nowa…
    p.on_session_switch("sesja-po-kompresji", parent_session_id="sesja-123")         # …i nowa sesja
    p._cache = ("", 0.0, "")
    assert "Orzeczenia" not in p.prefetch("czemu zrzut strony z three.js jest pusty?", session_id="sesja-po-kompresji")
    stara = pl.SkarbiecProvider()
    stara.initialize("sesja-sprzed-zmiany", hermes_home=str(home), platform="telegram", agent_context="primary")
    r = stara.prefetch("czemu zrzut strony z three.js jest pusty?")
    assert r.startswith("## Orzeczenia (wiążące)") and "innerHTML" in r and "Lighthouse mobile" in r


def test_uchylone_orzeczenie_nie_trafia_do_promptu(srodowisko):
    """orzeczenia/marki/enigmalabz.md 14.11: orzeczenie i jego uchylenie szły razem w każdym przypomnieniu. Uchylone
    (data + cytowany początek treści) i samo uchylenie odpadają; obowiązuje nowsza linia. Uchylenie dopisane po
    budowie promptu idzie przed turą, bo prompt nadal ma starą linię."""
    root, home, sk, p = srodowisko
    w.dodaj_orzeczenie(sk, "marki/enigmalabz", "W wynikach Enigmy nie raportuj porównania ze stockową llama.cpp", "rozmowa")
    w.dodaj_orzeczenie(sk, "marki/enigmalabz", "Porównania wobec stock llama.cpp robimy ZAWSZE", "rozmowa")
    w.dodaj_orzeczenie(sk, "marki/enigmalabz", "Orzeczenie z 2026-09-30 „W wynikach Enigmy nie raportuj porównania ze stockową "
                       "llama.cpp” jest uchylone i nie obowiązuje nikogo", "rozmowa")
    blok = p.system_prompt_block()
    assert "Porównania wobec stock llama.cpp robimy ZAWSZE" in blok
    assert "nie raportuj porównania" not in blok and "uchylone" not in blok
    assert "nie raportuj" not in p.prefetch("ile t/s robi Enigma wobec stock llama")
    w.dodaj_orzeczenie(sk, "wszyscy", "Orzeczenie z 2026-09-30 „Odpowiadaj po polsku” jest uchylone", "rozmowa")
    p._cache = ("", 0.0, "")
    r = p.prefetch("ile t/s robi Enigma wobec stock llama")
    assert r.startswith("## Nowe orzeczenia") and "„Odpowiadaj po polsku” jest uchylone" in r
    assert "Odpowiadaj po polsku" not in p.system_prompt_block()
    linie, uchylenia = pl.orzeczenia_obowiazujace(sk, [("orzeczenia/wszyscy", 20)])
    assert linie == [] and len(uchylenia) == 1
    w.dodaj_orzeczenie(sk, "wszyscy", "Orzeczenie z 2026-09-30 „Takiej linii nie ma” jest uchylone", "rozmowa")   # chybione
    assert "Takiej linii nie ma" in p.system_prompt_block()                         # zostaje widoczne, nic nie znika po cichu


def test_ostatni_blok_critical_z_soul_na_koncu(srodowisko):
    """Najważniejsze zasady na obu krawędziach promptu: ostatni blok <critical> z SOUL.md profilu stoi na końcu
    bloku skarbca (dosłownie); SOUL bez bloku albo bez pliku: nic."""
    root, home, sk, p = srodowisko
    assert "<critical>" not in p.system_prompt_block()                              # bez SOUL.md
    (home / "SOUL.md").write_text("# Web\n\nTreść.\n", encoding="utf-8")
    assert "<critical>" not in p.system_prompt_block()
    (home / "SOUL.md").write_text("<critical>\nPierwszy\n</critical>\n\nŚrodek.\n\n<critical>\n- Zgoda JARO.\n- Po polsku.\n</critical>\n",
                                  encoding="utf-8")
    blok = p.system_prompt_block()
    assert blok.endswith("\n\n<critical>\n- Zgoda JARO.\n- Po polsku.\n</critical>") and "Pierwszy" not in blok


def test_arsenal_w_bloku_promptu_kazdego_agenta(srodowisko):
    """14.11: darmową maszynę InstaBox znał tylko Jarvo; Wideograf, Web i reszta nie wiedzieli, że mogą jej użyć.
    Arsenał (`fleet/arsenal.md`, sekcja „## Zasoby”) jest w stałym bloku promptu każdego agenta."""
    root, home, sk, p = srodowisko
    assert "Arsenał floty" not in p.system_prompt_block()                            # bez pliku: bez sekcji
    sk.plik("fleet/arsenal.md").parent.mkdir(parents=True, exist_ok=True)
    sk.plik("fleet/arsenal.md").write_text(
        "# Arsenał floty\n\n**Lista.**\n\n## Zasoby\n- **Zapas mocy** · 4 vCPU · `zapas-mocy uruchom -- 'x'`\n"
        "- **Serwer** · CPU 80%\n\n## Powiązane\n- hub: [[_hub-skarbiec]]\n", encoding="utf-8")
    blok = p.system_prompt_block()                                                   # profil jarvo-web, nie Jarvo
    assert "# Arsenał floty" in blok and "- Zapas mocy: 4 vCPU; `zapas-mocy uruchom -- 'x'`" in blok and "- Serwer: CPU 80%" in blok
    assert "_hub-skarbiec" not in blok.split("# Arsenał floty")[1]                   # tylko sekcja Zasoby
    assert pl._zapis_w_skarbcu({"path": str(sk.plik("fleet/arsenal.md"))}) is None   # Jarvo dopisuje wprost


ARSENAL_DLUGI = """## Zasoby
- **Zapas mocy: InstaBox × 3 — `flota-01`, `flota-02`, `flota-03`** (od 14.11 jedna, od 19.11 trzy, 0 zł) · każda Linux w chmurze, 4 vCPU, 8 GB, Debian 13, python, docker; razem 12 vCPU / 24 GB · kiedy: CPU serwera zajęte (limit 80%), kilka renderów, buildów albo testów naraz, testy kerneli na CPU, długi build · jak: `zapas-mocy uruchom --wyslij PLIK --odbierz WYNIK -- 'polecenie'` (pomoc: `zapas-mocy pomoc`), maszynę wybiera `ZAPAS_MOCY_MASZYNA=flota-02` · limity: 1 maszyna na konto, pauza po 30 min bezczynności, 600 s na polecenie (dłużej `--tlo`), ffmpeg doinstaluj raz; bez sekretów i danych klientów · """ + "dalsze uwagi o maszynach " * 30 + """
- **Modern Web Guidance 1.0 (Chrome/Edge/Firefox/MDN)** · skille dla agentów kodujących: 250 nowoczesnych API (CSS, HTML, JS) + 203 przypadki użycia; `legacy-scan` na landingu: 3 s · kiedy: nowa strona albo przebudowa komponentu, żeby agent nie pisał starych wzorców (view transitions, popover, container queries, `scheduler.yield`) · jak: skill `modern-web-guidance` u Weba · """ + "dalsze uwagi o skanerze " * 30 + """
- **AssemblyAI — 3 konta floty, po $50 darmowych kredytów (19.11.2026)** · transkrypcja, TTS, streaming; plany Free, bez karty · kiedy: transkrypcje i napisy (jarvo-translator), testy API mowy · konta: first `ktos.pierwszy@gmail.com` ($50), second `ktos.drugi@gmail.com` ($50) · jak: klucz w panelu · """ + "dalsze uwagi o kontach " * 30 + """
- **Serwer** · Dell OptiPlex, i5 7. gen 4 rdzenie, 32 GB, bez GPU · CPU najwyżej 80%, ciężkie rzeczy `nice -n 15`, wideo koduj na karcie Intela (`h264_vaapi`, `/dev/dri/renderD128`).
- **Komputer Jarva** · przeglądarka Jarva w oknie na pulpicie serwera; właściciel widzi i przejmuje przez VNC · konta, logowanie, panele www: robi Jarvo.
- **Telefony** · 3 × realme (`first`, `second`, `third`) przez PhoneUse, zalogowane konta Google · konta przez „Zaloguj przez Google”, aplikacje mobilne, zrzuty z telefonu: robi Jarvo · adb: `first` = `100.99.219.95:5555` · YouTube: `first` kanał (nie ruszać)
- **GPU** · jaroserverai, RX 7900 XTX 24 GB, zwykle wyłączony · tylko sesja Kernel (testy kerneli i inferencji), produkcyjny czat :8080 nietykalny.

## Powiązane
- hub: [[_hub-skarbiec]]
"""


def test_arsenal_indeks_bez_ciecia_w_pol_wpisu(srodowisko):
    """20.11: Arsenał szedł w całości ucięty na 2400 znakach w pół słowa („…testy API mowy, tes”), więc Serwer,
    Komputer Jarva, Telefony i GPU wypadały z promptu. Teraz indeks: jedna linia na każdy zasób (nazwa: co; kiedy),
    całość ≤ MAX_ARSENAL, cięcie tylko na granicy słowa, bez adresów e-mail kont; pełny wpis przez wiedza_czytaj."""
    root, home, sk, p = srodowisko
    sk.plik("fleet/arsenal.md").parent.mkdir(parents=True, exist_ok=True)
    sk.plik("fleet/arsenal.md").write_text("# Arsenał floty\n\n" + ARSENAL_DLUGI, encoding="utf-8")
    sekcja = "# Arsenał floty" + p.system_prompt_block().split("\n\n# Arsenał floty")[1]
    assert len(sekcja) <= pl.MAX_ARSENAL and "wiedza_czytaj `fleet/arsenal`" in sekcja
    linie = [l for l in sekcja.splitlines() if l.startswith("- ")]
    nazwy = ["Zapas mocy: InstaBox × 3", "Modern Web Guidance 1.0", "AssemblyAI — 3 konta floty", "Serwer:", "Komputer Jarva:",
             "Telefony:", "GPU:"]
    assert len(linie) == 7 and all(l.startswith("- " + n) for l, n in zip(linie, nazwy))
    assert "@" not in sekcja and "dalsze uwagi" not in sekcja and "100.99.219.95" not in sekcja
    assert "- Serwer: Dell OptiPlex, i5 7. gen 4 rdzenie, 32 GB, bez GPU; CPU najwyżej 80%" in sekcja
    assert "- GPU: jaroserverai, RX 7900 XTX 24 GB, zwykle wyłączony; tylko sesja Kernel" in sekcja
    tresc = sk.plik("fleet/arsenal.md").read_text(encoding="utf-8")
    for l in linie:
        assert l.count("`") % 2 == 0
        for slowo in l[2:].rstrip("…").replace(":", " ").replace(";", " ").split():
            assert re.search(rf"(?<!\w){re.escape(slowo)}(?!\w)", tresc), slowo           # całe słowa z pliku, nic w pół


def test_przypomnienie_wektorami_z_uslugi_i_slowami_bez_niej(srodowisko):
    """Usługa wektorów działa (state/wektory.json z tokenem): przypomnienie i wiedza_szukaj trafiają po znaczeniu,
    dziennik ma silnik „wektory”; bez usługi te same tury idą słowami (silnik „slowa”), bez błędu."""
    from atrapa_wektorow import usluga_atrapy
    root, home, sk, p = srodowisko
    stan = root / "jarvo" / "state"
    p.prefetch("czemu kadr z animacji w przeglądarce wychodzi czarny?")
    assert _dziennik(root)["silnik"] == "slowa"
    with usluga_atrapy(stan):
        assert w.main(["--skarbiec", str(sk.root), "--stan", str(stan), "indeksuj"]) == 0
        r = p.prefetch("zrzut z animacją webgl daje pusty kadr")
        assert "`agenci/jarvo-web/lightpanda nie renderuje three.js`" in r
        wpis = _dziennik(root)
        assert wpis["silnik"] == "wektory" and wpis["ms"] >= 0
        wyn = json.loads(p.handle_tool_call("wiedza_szukaj", {"zapytanie": "pusty kadr przy webgl"}))["wyniki"]
        assert wyn and wyn[0]["sciezka"] == "agenci/jarvo-web/lightpanda nie renderuje three.js"
    r = p.prefetch("zrzut strony z three.js jest pusty")
    assert "lightpanda nie renderuje" in r and _dziennik(root)["silnik"] == "slowa"


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
    zle = json.loads(p.handle_tool_call("wiedza_zapisz", {"typ": "fakt", "tytul": "x", "tresc": "y", "source": "rozmowa", "tags": ["a"]}))
    assert "source, tags" in zle["error"] and "zrodlo" in zle["error"]                      # 11.11: 5 ślepych prób
    assert len(list((sk.root / "skrzynka").glob("*.md"))) == 1                              # nic nie zapisano
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
    # lustro idzie po treści plików pamięci (wiedza.synchronizuj_pamiec), hak tylko je wyzwala
    (home / "memories").mkdir()
    (home / "memories" / "USER.md").write_text("Użytkownik prowadzi agencję marketingową (źródło: rozmowa, 2026-09-30)", encoding="utf-8")
    p.on_memory_write("add", "user", "Użytkownik prowadzi agencję marketingową (źródło: rozmowa, 2026-09-30)")
    (home / "memories" / "MEMORY.md").write_text("hasło: tajne123", encoding="utf-8")
    p.on_memory_write("add", "memory", "hasło: tajne123")
    p.on_memory_write("remove", "memory", "cokolwiek")
    lustro = (sk.root / "skrzynka/pamiec-jarvo-web-user.md").read_text(encoding="utf-8")
    assert lustro.count("- 2026-09-30 · add user: Użytkownik prowadzi agencję") == 1
    assert not (sk.root / "skrzynka/pamiec-jarvo-web.md").exists()          # jedyny wpis MEMORY.md to sekret: bez szkicu
    assert b"\r" not in (sk.root / "skrzynka/pamiec-jarvo-web-user.md").read_bytes()
    assert not (sk.root / "user/pamięć jarva o tobie.md").exists()          # lustro-notatka tylko dla Jarva
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


def test_sesja_z_ekranem_albo_telefonem_bez_wyciagu(srodowisko, monkeypatch):
    """Rozmowa z narzędziem ekranu albo telefonu (computer_use, komputer, mcp__phone__*; docs/KOMPUTER.md §7): wyniki
    narzędzi to treść ekranu, więc z tej sesji żadnego wyciągu. Inne sesje tego samego agenta idą do wyciągu."""
    root, home, sk, p = srodowisko
    wywolania = []
    monkeypatch.setattr(pl.SkarbiecProvider, "_model", staticmethod(lambda s, u, max_tokens=1200: wywolania.append(u) or "## Fakty\n- x"))
    zwykla = [m for i in range(6) for m in ({"role": "user", "content": f"wypełnij formularz {i} w sklepie Acme"},
                                            {"role": "assistant", "content": "Zrobione, formularz wypełniony."})]
    ekran = [m for i in range(6) for m in (
        {"role": "user", "content": f"wypełnij formularz {i} w sklepie Acme"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "komputer", "arguments": "{}"}}]},
        {"role": "tool", "content": "Jan Kowalski, ul. Polna 1, tel. 600 100 200"})]
    op = pl.SkarbiecProvider()
    op.initialize("sesja-ekranu", hermes_home=str(home), platform="cli", agent_context="primary")
    assert op.on_pre_compress(ekran) == ""
    op.on_session_end(zwykla)                                  # ta sama sesja: oznaczona, mimo zapisu bez narzędzi
    assert wywolania == [] and not list((sk.root / "zrodla/rozmowy").glob("*.md"))
    assert op.prefetch("lightpanda three.js") != ""            # skarbiec czyta dalej, tylko nic nie wyciąga
    # telefon: sesję oznacza strażnik (pre_tool_call), zanim tura trafi do bufora
    assert pl.straznik("mcp__phone__screen", {"phone": "first"}, session_id="sesja-telefonu") is None
    tel = pl.SkarbiecProvider()
    tel.initialize("sesja-telefonu", hermes_home=str(home), platform="telegram", agent_context="primary")
    tel.on_session_end(zwykla)
    assert wywolania == []
    # rozmowa bez ekranu i telefonu: wyciąg jak zawsze
    czysta = pl.SkarbiecProvider()
    czysta.initialize("sesja-bez-ekranu", hermes_home=str(home), platform="telegram", agent_context="primary")
    czysta.on_session_end(zwykla)
    assert len(wywolania) == 1


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


def test_karta_z_bazy_w_katalogu_ze_znakami(tmp_path):
    """Baza kanbana czytana przez adres file: z Path.as_uri(): spacja, „#”, „%” i polskie znaki (np. C:\\Users\\Michał Żółć)
    nie psują adresu, a tryb tylko do odczytu zostaje."""
    db = tmp_path / "Michał Żółć #1 100%" / "kanban.db"
    db.parent.mkdir()
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE tasks(id TEXT PRIMARY KEY, title TEXT, workspace_path TEXT)")
    conn.execute("INSERT INTO tasks VALUES ('t_1', 'Łąka', 'C:/x')")
    conn.commit()
    conn.close()
    assert pl._karta_z_bazy(db, "t_1") == {"title": "Łąka", "workspace_path": "C:/x"}
    assert pl._karta_z_bazy(db, "t_2") == {} and pl._karta_z_bazy(tmp_path / "nie-ma.db", "t_1") == {}


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


def test_straznik_notatki_skarbca_tylko_przez_kompilacje(srodowisko, monkeypatch):
    """11.11 Jarvo poprawił notatkę `patch`-em (bez LOG, gita i indeksu). write_file i patch w notatkę, hub, LOG albo
    skrzynkę: blokada z drogą przez wiedza_zapisz; własne formaty skilli i pliki poza skarbcem idą dalej."""
    root, home, sk, p = srodowisko
    monkeypatch.setenv("HERMES_HOME", str(home))
    kn = root / "jarvo" / "knowledge"
    notatka = str(kn / "agenci/jarvo-web/lightpanda nie renderuje three.js.md")
    w = pl.straznik(tool_name="patch", args={"path": notatka, "old_string": "a", "new_string": "b"})
    assert w and w["action"] == "block" and "wiedza_zapisz" in w["message"]
    assert pl.straznik(tool_name="write_file", args={"path": str(kn / "INDEX.md"), "content": "x"})["action"] == "block"
    v4a = f"*** Begin Patch\n*** Update File: {notatka}\n@@\n-a\n+b\n*** End Patch"
    assert pl.straznik(tool_name="patch", args={"mode": "patch", "patch": v4a})["action"] == "block"
    for wolny in ("brands/acme/BRAND.md", "fleet/lekcje.md", "user/USER.md", "inspiracje/strony/x/y.md", "wideo/muzyka/a.md"):
        assert pl.straznik(tool_name="write_file", args={"path": str(kn / wolny), "content": "x"}) is None, wolny
    assert pl.straznik(tool_name="write_file", args={"path": str(root / "jarvo" / "workspaces" / "raport.md"), "content": "x"}) is None


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


def test_straznik_dopisuje_recenzenta_do_oddania(tmp_path, monkeypatch):
    """Pierwsza sesja 26.10: Web i Sherlock oddawali karty bez reviewer=, więc Hermes zostawiał je u nich i tor review
    uruchamiał ich znowu (Web 6 razy). Strażnik dopisuje recenzenta floty z flota.json; podany zostaje bez zmian."""
    monkeypatch.setattr(pl, "recenzent_floty", lambda: "jarvo")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "jarvo-web"))
    oddanie = {"summary": "Audyt gotowy", "metadata": {"artifacts": ["out/audyt.md"]}}
    assert pl.straznik(tool_name="kanban_request_review", args=oddanie) == {"action": "modify", "args": {"reviewer": "jarvo"}}
    assert pl.straznik(tool_name="kanban_request_review", args={**oddanie, "reviewer": " "})["args"] == {"reviewer": "jarvo"}
    assert pl.straznik(tool_name="kanban_request_review", args={**oddanie, "reviewer": "jarvo-sherlock"}) is None
    assert pl.straznik(tool_name="kanban_complete", args=oddanie) is None
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "jarvo"))      # sam recenzent: bez dopisku
    assert pl.straznik(tool_name="kanban_request_review", args=oddanie) is None
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "dom"))                       # host (poza profilem floty)
    assert pl.straznik(tool_name="kanban_request_review", args=oddanie) is None
    monkeypatch.setattr(pl, "recenzent_floty", lambda: None)                       # bez flota.json: jak dawniej
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "jarvo-web"))
    assert pl.straznik(tool_name="kanban_request_review", args=oddanie) is None


def test_straznik_wykonawca_nie_zamyka_swojej_karty(tmp_path, monkeypatch):
    """Pierwsza sesja 26.10: Łowca zamknął kartę sam (kanban_complete), więc nikt nie sprawdził listy leadów."""
    monkeypatch.setattr(pl, "recenzent_floty", lambda: "jarvo")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "jarvo-lowca"))
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_06f3c3fc")
    for args in ({"summary": "10 firm"}, {"task_id": "t_06f3c3fc", "summary": "10 firm"}):
        w = pl.straznik(tool_name="kanban_complete", args=args)
        assert w["action"] == "block" and "kanban_request_review" in w["message"]
    assert pl.straznik(tool_name="kanban_complete", args={"task_id": "t_inna0000"}) is None     # cudza karta (podkarta)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "jarvo"))                    # sędzia zamyka
    assert pl.straznik(tool_name="kanban_complete", args={"summary": "Zatwierdzam"}) is None
    monkeypatch.delenv("HERMES_KANBAN_TASK")                                                  # Jarvo w czacie
    assert pl.straznik(tool_name="kanban_complete", args={"task_id": "t_06f3c3fc"}) is None
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "jarvo-lowca"))             # poza kartą
    assert pl.straznik(tool_name="kanban_complete", args={"task_id": "t_06f3c3fc"}) is None


def test_straznik_oddanie_z_dziurami_wraca_do_wykonawcy(tmp_path, monkeypatch):
    """Strona-wizytówka 26.10: 25× „[TU WPISZ…]” w index.html i sędzia zaakceptował. Oddanie z treścią zastępczą
    w pliku wyniku wraca do wykonawcy; RAPORT.md (opis pracy), JSON narzędzi i out/strony (cudze teksty) się nie liczą."""
    monkeypatch.setattr(pl, "recenzent_floty", lambda: "jarvo")
    ws = tmp_path / "karta"
    (ws / "out" / "strony").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "jarvo-web"))
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_dfde9ecf")
    monkeypatch.setenv("HERMES_KANBAN_WORKSPACE", str(ws))
    oddanie = {"summary": "Strona gotowa"}
    (ws / "out" / "index.html").write_text("<h1>Salon Ania</h1><p>Tel. 600 100 200</p>", encoding="utf-8")
    (ws / "out" / "RAPORT.md").write_text("Sprawdziłem: 0 wystąpień [TU WPISZ.", encoding="utf-8")
    (ws / "out" / "lighthouse.json").write_text('{"tekst": "lorem ipsum"}', encoding="utf-8")
    (ws / "out" / "strony" / "1.txt").write_text("Lorem ipsum z cudzej strony", encoding="utf-8")
    assert pl.straznik(tool_name="kanban_request_review", args=oddanie) == {"action": "modify", "args": {"reviewer": "jarvo"}}
    (ws / "out" / "index.html").write_text("<h1>[TU WPISZ: imię]</h1>", encoding="utf-8")
    w = pl.straznik(tool_name="kanban_request_review", args={**oddanie, "reviewer": "jarvo"})
    assert w["action"] == "block" and "index.html: [TU WPISZ" in w["message"] and "needs_input" in w["message"]
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "jarvo"))       # sędzia nie jest sprawdzany
    assert pl.straznik(tool_name="kanban_request_review", args=oddanie) is None


def test_straznik_sherlock_oddaje_tylko_z_rejestrem_zrodel(tmp_path, monkeypatch):
    """Pierwsza sesja 26.10: Sherlock oddał konkurencję bez sources.py i zrodla.json (zasada 9 SOUL tylko na papierze)."""
    monkeypatch.setattr(pl, "recenzent_floty", lambda: "jarvo")
    ws = tmp_path / "karta"
    (ws / "out").mkdir(parents=True)
    (ws / "out" / "konkurencja.md").write_text("3 konkurentów [1][2]", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "jarvo-sherlock"))
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_2d67cf6c")
    monkeypatch.setenv("HERMES_KANBAN_WORKSPACE", str(ws))
    w = pl.straznik(tool_name="kanban_request_review", args={"summary": "Konkurencja"})
    assert w["action"] == "block" and "zrodla.json" in w["message"]
    (ws / "out" / "zrodla.json").write_text('{"zrodla": []}', encoding="utf-8")
    assert pl.straznik(tool_name="kanban_request_review", args={"summary": "Konkurencja"})["action"] == "modify"
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "jarvo-web"))   # inni agenci bez rejestru
    (ws / "out" / "zrodla.json").unlink()
    assert pl.straznik(tool_name="kanban_request_review", args={"summary": "Audyt"})["action"] == "modify"


def _baza_kart(db: Path, karty: dict, ocena: dict = None) -> None:
    """kanban.db jak Hermesa: karty {id: skills} i zdarzenia `claimed` przebiegów {(id, run): source_status}."""
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE tasks(id TEXT PRIMARY KEY, title TEXT, body TEXT, skills TEXT, status TEXT)")
    conn.execute("CREATE TABLE task_events(id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, run_id INTEGER, kind TEXT, "
                 "payload TEXT, created_at INTEGER)")
    for tid, skille in karty.items():
        conn.execute("INSERT INTO tasks VALUES (?, 'Audyt', '', ?, 'running')", (tid, json.dumps(skille) if skille is not None else None))
    for (tid, run), zrodlo in (ocena or {}).items():
        conn.execute("INSERT INTO task_events(task_id, run_id, kind, payload, created_at) VALUES (?, ?, 'claimed', ?, 0)",
                     (tid, run, json.dumps({"source_status": zrodlo})))
    conn.commit()
    conn.close()


def test_straznik_budzet_wzroku_szybkiego_audytu(tmp_path, monkeypatch):
    """9.11: szybkie audyty Webu z 3–7 wywołaniami wzroku (36–120 s każde), sędzia 1–5 na kartę, choć skill mówi
    o jednym. Karta ze skillem szybki-audyt: wykonawca 2 (montaż i jedno przybliżenie), recenzent 1; inne bez limitu."""
    db = tmp_path / "kanban.db"
    _baza_kart(db, {"t_szybki": ["szybki-audyt"], "t_pelny": ["audyt-strony"], "t_bez": None},
               {("t_szybki", 1): "ready", ("t_szybki", 2): "review"})
    monkeypatch.setattr(pl, "recenzent_floty", lambda: "jarvo")
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "jarvo-web"))
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_szybki")
    monkeypatch.setenv("HERMES_KANBAN_RUN_ID", "1")
    assert pl.straznik(tool_name="vision_analyze", args={"image_url": "out/zrzuty.jpg"}) is None
    assert pl.straznik(tool_name="vision_analyze", args={"image_url": "out/zrzuty/1440.png"}) is None
    for narzedzie in ("vision_analyze", "browser_vision"):                       # wspólny budżet obu narzędzi
        w = pl.straznik(tool_name=narzedzie, args={"image_url": "out/zrzuty/390.png"})
        assert w["action"] == "block" and "2/2" in w["message"] and "Uwagi wizualne" in w["message"]
        assert "Do głębszej analizy" in w["message"] and "oddaj kartę" in w["message"]
    assert pl.straznik(tool_name="web_search", args={}) is None                  # inne narzędzia bez zmian
    # ocena tej karty (Hermes: claimed z source_status=review): recenzent 1 wywołanie
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "jarvo"))
    monkeypatch.setenv("HERMES_KANBAN_RUN_ID", "2")
    assert pl.straznik(tool_name="vision_analyze", args={"image_url": "out/zrzuty.jpg"}) is None
    w = pl.straznik(tool_name="vision_analyze", args={"image_url": "out/zrzuty/390.png"})
    assert w["action"] == "block" and "1/1" in w["message"] and "werdykt" in w["message"]
    # ocena bez zdarzenia w bazie: rolę daje profil recenzenta floty
    monkeypatch.setenv("HERMES_KANBAN_RUN_ID", "3")
    assert pl.straznik(tool_name="vision_analyze", args={}) is None
    assert pl.straznik(tool_name="browser_vision", args={})["action"] == "block"
    # karta bez szybkiego skilla i rozmowa poza kartą: nigdy blokady
    for karta in ("t_pelny", "t_bez", "t_brak"):
        monkeypatch.setenv("HERMES_KANBAN_TASK", karta)
        for profil in ("jarvo-web", "jarvo"):
            monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / profil))
            for _ in range(5):
                assert pl.straznik(tool_name="vision_analyze", args={}) is None, (karta, profil)
    monkeypatch.delenv("HERMES_KANBAN_TASK")
    for _ in range(5):
        assert pl.straznik(tool_name="vision_analyze", args={}) is None


def test_straznik_budzet_researchu_w_rozmowie(tmp_path, monkeypatch):
    """12.11: „szybki research” w rozmowie poszedł 7 min i ok. 45 wyszukiwań i stron. Jarvo poza kartą: 12 na turę;
    nowa wiadomość właściciela (nowy turn_id) to nowy budżet; karta i inni agenci bez limitu."""
    monkeypatch.setattr(pl, "recenzent_floty", lambda: "jarvo")
    monkeypatch.delenv("HERMES_KANBAN_TASK", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "jarvo"))
    for i in range(pl.BUDZET_RESEARCHU_W_ROZMOWIE):
        narzedzie = "web_search" if i % 2 else "web_extract"
        assert pl.straznik(tool_name=narzedzie, args={}, session_id="s1", turn_id="s1:t1") is None
    w = pl.straznik(tool_name="web_search", args={}, session_id="s1", turn_id="s1:t1")
    assert w["action"] == "block" and "zbadaj głęboko" in w["message"] and "12/12" in w["message"]
    assert pl.straznik(tool_name="web_search", args={}, session_id="s1", turn_id="s1:t2") is None
    assert pl.straznik(tool_name="pobierz_link", args={}, session_id="s1", turn_id="s1:t1") is None
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_1")                                 # karta: bez limitu rozmowy
    for _ in range(pl.BUDZET_RESEARCHU_W_ROZMOWIE + 1):
        assert pl.straznik(tool_name="web_search", args={}, session_id="s2", turn_id="s2:t1") is None
    monkeypatch.delenv("HERMES_KANBAN_TASK")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "jarvo-sherlock"))   # specjalista w rozmowie
    for _ in range(pl.BUDZET_RESEARCHU_W_ROZMOWIE + 1):
        assert pl.straznik(tool_name="web_extract", args={}, session_id="s3", turn_id="s3:t1") is None


def test_recenzent_floty_z_pliku_wtyczki(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO / "scripts"))
    import build
    out = build.build_wiedza_plugin(tmp_path / "jarvo-wiedza", "jarvo")
    assert json.loads((out / "flota.json").read_text(encoding="utf-8")) == {"recenzent": "jarvo"}
    monkeypatch.setattr(pl, "__file__", str(out / "__init__.py"))
    assert pl.recenzent_floty() == "jarvo"
    (out / "flota.json").write_text("{zepsuty", encoding="utf-8")
    assert pl.recenzent_floty() is None


def test_licznik_generacji_pod_blokada_miedzyprocesowa(tmp_path, monkeypatch):
    """Brama i pracownicy kanbana to osobne procesy: licznik czyta i pisze pod blokadą pliku (fcntl / msvcrt).
    Zajęta blokada: bez czekania od razu „nie”, z czekaniem po czasie praca idzie dalej bez niej, jak dawniej."""
    zamek = tmp_path / "state" / "generacje-ai.lock"
    with pl._zamek(zamek) as wzieta:
        assert wzieta is True
        with pl._zamek(zamek, czekaj_s=0) as druga:                              # drugi uchwyt = jak drugi proces
            assert druga is False
        t0 = time.monotonic()
        with pl._zamek(zamek, czekaj_s=0.3) as trzecia:
            assert trzecia is False and time.monotonic() - t0 >= 0.25
    with pl._zamek(zamek, czekaj_s=0) as po_zwolnieniu:
        assert po_zwolnieniu is True
    # bez HERMES_HOME i JARVO_STATE_DIR: katalog domowy Hermesa (hermes_constants), nie /opt/data
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.delenv("JARVO_STATE_DIR", raising=False)
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_dom")
    stale = types.ModuleType("hermes_constants")
    stale.get_hermes_home = lambda: tmp_path / "dom-hermesa"
    monkeypatch.setitem(sys.modules, "hermes_constants", stale)
    assert pl.straznik(tool_name="image_generate", args={}) is None
    stan = json.loads((tmp_path / "dom-hermesa" / "jarvo" / "state" / "generacje-ai.json").read_text(encoding="utf-8"))
    assert stan == {"t_dom": {"image_generate": 1}}


def test_schemat_tylko_dla_jarva(srodowisko, tmp_path, monkeypatch):
    """Narzędzia `schemat` (SVG → PNG) i `pobierz_link` (skrzynka linków) dostaje tylko Jarvo; wykonawcy mają same
    narzędzia skarbca."""
    root, _home, _sk, p = srodowisko
    assert "schemat" not in {s["name"] for s in p.get_tool_schemas()}
    assert "nieznane narzędzie" in p.handle_tool_call("schemat", {"svg": "<svg/>", "tytul": "x"})
    assert "nieznane narzędzie" in p.handle_tool_call("pobierz_link", {"linki": ["https://example.com"]})
    (root / "profiles" / "jarvo").mkdir(parents=True)
    j = pl.SkarbiecProvider()
    j.initialize("sesja-j", hermes_home=str(root / "profiles" / "jarvo"), platform="telegram", agent_context="primary")
    nazwy = [s["name"] for s in j.get_tool_schemas()]
    assert nazwy[-2:] == ["schemat", "pobierz_link"] and len(nazwy) == 6
    monkeypatch.setenv("JARVO_CHROMIUM", str(tmp_path / "nie-ma"))
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.delenv("JARVO_SCHEMATY_DIR", raising=False)
    assert "Nie udało się narysować" in json.loads(j.handle_tool_call("schemat", {"svg": "<svg/>", "tytul": "x"}))["error"]
    # katalog schematów z profilu wtyczki, nie z prawdziwego korzenia Jarva właściciela
    assert (root / "jarvo" / "workspaces" / "jarvo" / "schematy").is_dir()


def test_narzedzia_jarva_przed_initialize_jak_w_hermesie(tmp_path, monkeypatch):
    """Hermes pyta o schematy w add_provider, przed initialize() (i z nich buduje trasę wywołań): Jarvo widzi
    `pobierz_link` i `schemat` od razu po HERMES_HOME profilu, wykonawca nie. 11.11 na żywo: „Unknown tool”."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "data" / "profiles" / "jarvo"))
    assert [s["name"] for s in pl.SkarbiecProvider().get_tool_schemas()][-2:] == ["schemat", "pobierz_link"]
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "data" / "profiles" / "jarvo-web"))
    assert "pobierz_link" not in {s["name"] for s in pl.SkarbiecProvider().get_tool_schemas()}


def test_awaria_schematu_nie_zabiera_skarbca(srodowisko, tmp_path, monkeypatch):
    """Zepsuty schemat.py (brak pliku, błąd w kodzie): Jarvo traci tylko `schemat`, narzędzia wiedza_* zostają."""
    root, _home, _sk, _p = srodowisko
    (root / "profiles" / "jarvo").mkdir(parents=True)
    j = pl.SkarbiecProvider()
    j.initialize("sesja-j", hermes_home=str(root / "profiles" / "jarvo"), platform="telegram", agent_context="primary")

    def zepsuty():
        raise SyntaxError("zepsuty schemat.py")
    monkeypatch.setattr(pl, "_schemat", zepsuty)
    nazwy = [s["name"] for s in j.get_tool_schemas()]
    assert nazwy == ["wiedza_szukaj", "wiedza_czytaj", "wiedza_zapisz", "wiedza_orzeczenie", "pobierz_link"]
    monkeypatch.setattr(pl, "_linki", zepsuty)
    assert "niedostępne" in json.loads(j.handle_tool_call("pobierz_link", {"linki": ["https://example.com"]}))["error"]
    assert [s["name"] for s in j.get_tool_schemas()][4:] == []
    assert "niedostępne" in json.loads(j.handle_tool_call("schemat", {"svg": "<svg/>", "tytul": "x"}))["error"]
    assert "wyniki" in json.loads(j.handle_tool_call("wiedza_szukaj", {"zapytanie": "marka"}))
    # nieudany import nie zostaje w sys.modules jako pusty moduł
    zly = tmp_path / "zly.py"
    zly.write_text("raise RuntimeError('x')\n", encoding="utf-8")
    monkeypatch.setattr(pl, "_HERE", tmp_path)
    with pytest.raises(RuntimeError):
        pl._modul("jarvo_zly_test", "zly.py")
    assert "jarvo_zly_test" not in sys.modules


def _chwila(tekst: str) -> float:
    """Czas lokalny (daty z dala od zmiany czasu: 25.10.2026 godzina 02:00–03:00 jest dwa razy)."""
    import datetime as dt
    return dt.datetime.strptime(tekst, "%Y-%m-%d %H:%M").timestamp()


def test_ostatnia_pora_nocnego_przebiegu():
    """Ostatnia pora 03:10 nie później niż teraz: przed 03:10 to wczorajsza, po niej dzisiejsza (czas lokalny)."""
    assert w.ostatnia_noc(_chwila("2026-10-20 02:59")) == _chwila("2026-10-19 03:10")
    assert w.ostatnia_noc(_chwila("2026-10-20 03:10")) == _chwila("2026-10-20 03:10")
    assert w.ostatnia_noc(_chwila("2026-10-20 23:00")) == _chwila("2026-10-20 03:10")


def test_nocny_przebieg_nadrabiany_po_uspieniu(srodowisko):
    """Laptop uśpiony o 03:10: nocny przebieg nie przepada do następnej nocy, tylko rusza raz po wybudzeniu; potem
    obowiązuje zwykły rytm (szkice odstane, test_harmonogram_kompilacji_po_szkicach). Bez szkiców nic nie rusza."""
    root, home, sk, p = srodowisko
    kn, st = root / "jarvo" / "knowledge", root / "jarvo" / "state"

    def ostatnia(t):
        (st / "wiedza-kompilacja.json").write_text(json.dumps({"ostatnia": t}), encoding="utf-8")
    ostatnia(_chwila("2026-10-20 02:50"))
    assert not w.pora_kompilacji(kn, st, _chwila("2026-10-20 07:30"))          # skrzynka pusta
    rel = w.zapisz_szkic(sk, "fakt", "Nocny fakt", "Treść.", "karta t_5", "jarvo-web")
    os.utime(sk.plik(rel), (_chwila("2026-10-20 03:02"),) * 2)
    assert w.pora_kompilacji(kn, st, _chwila("2026-10-20 03:05")) is False      # szkic świeży, przed porą nocną
    assert w.pora_kompilacji(kn, st, _chwila("2026-10-20 03:11"))               # pora nocna (dawniej tylko okno 10 min)
    assert w.pora_kompilacji(kn, st, _chwila("2026-10-20 07:30"))               # po wybudzeniu: nadrabia
    ostatnia(_chwila("2026-10-20 07:31"))
    os.utime(sk.plik(rel), (_chwila("2026-10-20 07:58"),) * 2)
    assert not w.pora_kompilacji(kn, st, _chwila("2026-10-20 08:00"))          # po nadrobieniu: zwykły rytm


def test_harmonogram_kompilacji_po_szkicach(srodowisko):
    """Kompilacja rusza, gdy najnowszy szkic ma ≥ 5 min (seria z rozmowy skończona) albo najstarszy ≥ 15 min (ciągły
    dopływ), a nie najwyżej raz na godzinę; po przebiegu przerwanym błędem modelu czeka 15 min; bez szkiców nigdy."""
    root, home, sk, p = srodowisko
    kn, st = root / "jarvo" / "knowledge", root / "jarvo" / "state"
    stan = st / "wiedza-kompilacja.json"
    t0 = _chwila("2026-10-20 10:00")
    stan.write_text(json.dumps({"ostatnia": t0}), encoding="utf-8")
    assert not w.pora_kompilacji(kn, st, t0 + 3600)                                # pusta skrzynka: 0 wywołań modelu
    a = sk.plik(w.zapisz_szkic(sk, "fakt", "Fakt A", "Treść.", "karta t_1", "jarvo-web"))
    os.utime(a, (t0 + 60,) * 2)
    assert not w.pora_kompilacji(kn, st, t0 + 60 + w.SZKIC_SPOKOJ_S - 1)           # szkic świeży: może dojść następny
    assert w.pora_kompilacji(kn, st, t0 + 60 + w.SZKIC_SPOKOJ_S)                    # 5 min spokoju
    b = sk.plik(w.zapisz_szkic(sk, "fakt", "Fakt B", "Treść.", "karta t_2", "jarvo-web"))
    for minuta in range(1, 15):                                                    # szkic co minutę: najnowszy zawsze świeży
        os.utime(b, (t0 + 60 + minuta * 60,) * 2)
        assert not w.pora_kompilacji(kn, st, t0 + 60 + minuta * 60 + 30)
    assert w.pora_kompilacji(kn, st, t0 + 60 + w.SZKIC_NAJSTARSZY_S)                # najstarszy 15 min: mimo dopływu
    stan.write_text(json.dumps({"ostatnia": t0 + 1200, "raport": {"przerwana": "TimeoutError"}}), encoding="utf-8")
    assert not w.pora_kompilacji(kn, st, t0 + 1200 + w.KOMPILACJA_PO_AWARII_S - 1)  # dostawca wyłączony: nie palimy prób
    assert w.pora_kompilacji(kn, st, t0 + 1200 + w.KOMPILACJA_PO_AWARII_S)


def test_tik_dyspozytora_kompiluje_bez_rozmowy_w_bramie(srodowisko, monkeypatch):
    """Brama po restarcie bez żadnej rozmowy (dostawca pamięci nie zainicjowany): tik dyspozytora sam puszcza jedną
    kompilację, gdy szkice odstały, z HERMES_HOME profilu jarvo; drugi tik w trakcie przebiegu nie puszcza drugiej."""
    import subprocess
    import threading
    root, home, sk, p = srodowisko
    (root / "profiles" / "jarvo").mkdir()
    monkeypatch.setenv("HERMES_HOME", str(root))                   # brama: HERMES_HOME hosta, nie profilu
    (root / "jarvo" / "state" / "wiedza-kompilacja.json").write_text(json.dumps({"ostatnia": time.time()}), encoding="utf-8")
    puszczone, trwa, koniec = [], threading.Event(), threading.Event()

    def run(argv, **kw):
        puszczone.append((argv, kw["env"].get("HERMES_HOME")))
        trwa.set()
        koniec.wait(10)
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({"szkice": 1, "nowe": 1}), stderr="")
    monkeypatch.setattr(subprocess, "run", run)
    pl.tik_kompilacji(board="default", outcome="idle")
    assert puszczone == []                                          # pusta skrzynka: nic
    stary = time.time() - w.SZKIC_SPOKOJ_S - 5
    os.utime(sk.plik(w.zapisz_szkic(sk, "fakt", "Arsenał", "Trzy telefony.", "rozmowa", "jarvo")), (stary, stary))
    pl.tik_kompilacji(board="default", outcome="idle")
    assert trwa.wait(5)
    pl.tik_kompilacji(board="default", outcome="idle")             # przebieg trwa: drugiego nie ma
    koniec.set()
    for _ in range(100):
        if not pl._kompilacja_trwa.locked():
            break
        time.sleep(0.02)
    assert len(puszczone) == 1
    argv, hermes_home = puszczone[0]
    assert hermes_home == str(root / "profiles" / "jarvo")
    assert argv[argv.index("--skarbiec") + 1] == str(root / "jarvo" / "knowledge") and "--json" in argv


def test_progi_wyciagu(srodowisko, monkeypatch):
    """Wyciąg po 10 min ciszy, także z krótkiej sesji: od 2 wiadomości użytkownika albo z jednej od 300 znaków;
    jedno krótkie pytanie nie kosztuje wywołania modelu."""
    root, home, sk, p = srodowisko
    assert pl.CISZA_S == 600 and pl.MIN_TUR == 2 and pl.MIN_ZNAKOW_TURY == 300
    assert not pl._dosc_tresci(["gdzie jest kod strony?"]) and pl._dosc_tresci(["a", "b"]) and pl._dosc_tresci(["x" * 300])
    wywolania = []
    monkeypatch.setattr(pl.SkarbiecProvider, "_model", staticmethod(
        lambda s, u, max_tokens=1200: wywolania.append(u) or "## Fakty\n- kod strony enigmalabz.com leży w repo enigmalabz\nTytuł: Kod strony"))
    jedno = [{"role": "user", "content": "gdzie jest kod strony enigmalabz.com?"}, {"role": "assistant", "content": "W repo enigmalabz na GitHubie. " * 8}]
    p.on_session_end(jedno)
    assert wywolania == []                                                   # jedno krótkie pytanie: bez modelu
    dlugie = [{"role": "user", "content": "Ustalmy zasady strony: " + "kod strony trzymamy w repo enigmalabz, wgrywa tylko Jarvo. " * 6},
              {"role": "assistant", "content": "Zapisane."}]
    p.on_session_end(dlugie)
    assert len(wywolania) == 1                                               # jedna wiadomość od 300 znaków: wyciąg
    teraz = time.time()
    p.sync_turn("gdzie jest kod?", "w repo", session_id="s-krotka")
    p.sync_turn("a wgrywanie?", "tylko Jarvo", session_id="s-krotka")
    p.sync_turn("hej", "cześć", session_id="s-jedna")
    p._bufor["s-krotka"]["ts"] = p._bufor["s-jedna"]["ts"] = teraz - pl.CISZA_S + 5
    assert p._sesje_po_ciszy(teraz) == []                                    # jeszcze nie 10 min ciszy
    assert [sid for sid, _b in p._sesje_po_ciszy(teraz + 5)] == ["s-krotka"]  # 2 wiadomości tak, jedno „hej” nie
    p._bufor["s-krotka"]["wyciagnieto"] = 2
    assert p._sesje_po_ciszy(teraz + 5) == []                                # już wyciągnięte


# ------------------------------------------------------------------------------------------------ tekst zapytania przed turą

CRON_HINT = ("[IMPORTANT: You are running as a scheduled cron job. DELIVERY: Your final response will be automatically delivered "
             "to the user. SILENT: respond with exactly \"[SILENT]\" (nothing else). FAILURE: put [CRON_FAILURE] on the first line. "
             "RECURSION: treat phrasing like \"each Monday\" as context for this run, not as a request to schedule another job.]\n\n")


def _dziennik(root) -> dict:
    return json.loads((root / "jarvo" / "state" / "wiedza-przypomnienia.jsonl").read_text(encoding="utf-8").splitlines()[-1])


def test_karta_kanbana_szuka_po_tytule_i_tresci_karty(srodowisko, monkeypatch):
    """Pracownik kanbana dostaje dosłownie „work kanban task <id>”: przypomnienie szuka po tytule i treści karty
    z bazy kanbana (tylko odczyt), a nie po tych czterech słowach."""
    root, home, sk, p = srodowisko
    db = sqlite3.connect(root / "kanban.db")
    db.execute("CREATE TABLE tasks(id TEXT PRIMARY KEY, title TEXT, body TEXT, workspace_path TEXT, result TEXT, assignee TEXT, status TEXT)")
    db.execute("INSERT INTO tasks VALUES ('t_k1', 'Zrzuty strony z animacją', 'CEL: zrzuty ekranu sceny three.js na mobile', '', '', 'jarvo-web', 'running')")
    db.commit()
    db.close()
    monkeypatch.delenv("HERMES_KANBAN_DB", raising=False)
    r = p.prefetch("work kanban task t_k1")
    assert "`agenci/jarvo-web/lightpanda nie renderuje three.js`" in r
    wpis = _dziennik(root)
    assert wpis["zrodlo_zapytania"] == "kanban" and wpis["szukano"].startswith("Zrzuty strony z animacją CEL:")
    assert isinstance(wpis["ms"], float) and wpis["ms"] >= 0
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_k1")                   # sam napis bez id: id ze środowiska pracownika
    p._cache = ("", 0.0, "")
    assert "lightpanda" in p.prefetch("work kanban task")
    assert p._tekst_zapytania("work kanban task t_nie_ma") == ("", "kanban-brak")
    r2 = p.prefetch("work kanban task t_nie_ma")                         # brak karty: tylko orzeczenia, bez losowych notatek
    assert r2.startswith("## Orzeczenia") and _dziennik(root)["zrodlo_zapytania"] == "kanban-brak"


def test_rutyna_bez_reguly_harmonogramu(srodowisko):
    """Prompt rutyny (cron) zaczyna się regułką harmonogramu Hermesa: szukamy po samym zadaniu, bez regułki, bloków
    danych i „## Run Context”."""
    root, home, sk, p = srodowisko
    notatnik = ("## Job notepad (persistent across runs)\nThis durable scratchpad survives.\n`hermes cron notepad x set <key> <value>`.\n\n"
                "- licznik: 3\n\n")
    dane = "## Script Output\nThe following data was collected by a pre-run script.\n\n```\nfaktura delivery report\n```\n\n"
    zadanie = "Sprawdź, czy zrzuty three.js działają"
    pelny = "[skill: raport]\n" + CRON_HINT + notatnik + dane + zadanie + "\n\n## Run Context\nuruchomienie ręczne"
    assert pl.prompt_rutyny(pelny) == zadanie
    assert pl.prompt_rutyny("zwykłe pytanie") == "zwykłe pytanie"
    assert p._tekst_zapytania(pelny) == (zadanie, "cron")
    r = p.prefetch(pelny)
    assert "lightpanda nie renderuje three.js" in r
    wpis = _dziennik(root)
    assert wpis["zrodlo_zapytania"] == "cron" and wpis["szukano"] == zadanie and wpis["zapytanie"].startswith("[skill: raport]")
    assert p._tekst_zapytania("czemu zrzut jest pusty?") == ("czemu zrzut jest pusty?", "wiadomosc")


def test_huby_agentow_tylko_gdy_pytanie_nazywa_agenta(srodowisko):
    """Hub agenta (`agenci/<agent>/_hub-*`) nie zajmuje miejsca w „może się przydać”, chyba że pytanie nazywa agenta."""
    root, home, sk, p = srodowisko
    ix = w.Indeks(sk)
    try:
        ix.odswiez()
        assert any(t["sciezka"] == "agenci/jarvo-web/_hub-web" for t in ix.szukaj("strony SEO nowa strona", limit=10))
        assert all(not t["sciezka"].startswith("agenci/jarvo-web/_hub-") for t in w.notatki_przypomnienia(ix, "strony SEO nowa strona"))
        assert any(t["sciezka"] == "agenci/jarvo-web/_hub-web" for t in w.notatki_przypomnienia(ix, "co umie Web: strony SEO nowa strona"))
    finally:
        ix.zamknij()
    assert w.hub_agenta_nazwany("agenci/jarvo-wideo/_hub-wideograf", {"co", "robi", "wideograf"})
    assert w.hub_agenta_nazwany("agenci/jarvo-lowca/_hub-łowca", {"jarvo", "lowca"})
    assert not w.hub_agenta_nazwany("agenci/jarvo-web/_hub-web", {"strona", "seo"})
    assert "_hub-web" not in p.prefetch("strony SEO nowa strona")


def test_ksiega_bledow_hak_i_szkic_bledu(srodowisko, monkeypatch):
    """Księga błędów (17.11, właściciel: „ma sprawdzać sekcję błędów i uczyć się”): hak `transform_tool_result`
    zarejestrowany, dopisuje lekcję pod odmową z sygnaturą notatki `bledy/`, sukces zostawia bez zmian, a szkic błędu
    idzie przez wiedza_zapisz z sygnaturami."""
    root, home, sk, p = srodowisko
    monkeypatch.setenv("HERMES_HOME", str(home))
    haki = {}

    class Ctx:
        def register_memory_provider(self, provider): pass
        def register_hook(self, nazwa, f): haki[nazwa] = f
        def register_auxiliary_task(self, *a, **k): pass

    pl.register(Ctx())
    assert haki["transform_tool_result"] is pl.przypomnienie_bledu
    assert w.zasiej_bledy(sk, REPO / "wiedza" / "bledy") >= 12
    odmowa = json.dumps({"error": "Google: This browser or app may not be secure."})
    nowy = pl.przypomnienie_bledu(tool_name="komputer", result=odmowa, status="error", session_id="sesja-k")
    assert nowy.startswith(odmowa) and "To już było: Google nie loguje w przeglądarce Komputera" in nowy
    assert "telefonie floty" in nowy
    assert pl.przypomnienie_bledu(tool_name="komputer", result='{"ok": true}', status="ok", session_id="sesja-k") is None
    assert pl.przypomnienie_bledu(tool_name="komputer", result={"error": "x"}, status="error") is None   # nie tekst: bez zmian
    assert "księga błędów" in p.system_prompt_block() and "typ=blad" in p.system_prompt_block()
    schemat = next(t for t in p.get_tool_schemas() if t["name"] == "wiedza_zapisz")
    assert "blad" in schemat["parameters"]["properties"]["typ"]["enum"] and "sygnatury" in schemat["parameters"]["properties"]
    z = json.loads(p.handle_tool_call("wiedza_zapisz", {
        "typ": "blad", "tytul": "Npm EINTEGRITY", "zrodlo": "karta t_7", "sygnatury": ["EINTEGRITY"],
        "tresc": "Objaw: npm EINTEGRITY.\n\nPrzyczyna: uszkodzony cache.\n\nJak poprawnie: `npm cache verify` i jedno ponowienie."}))
    assert z["szkic"].startswith("skrzynka/")
    assert w.podziel(sk.plik(z["szkic"]).read_text(encoding="utf-8"))[0]["sygnatury"] == ["EINTEGRITY"]
    zle = json.loads(p.handle_tool_call("wiedza_zapisz", {"typ": "blad", "tytul": "x", "tresc": "Objaw: y.", "zrodlo": "z"}))
    assert "sygnatury" in zle["error"]


def _jak_hermes(katalog: Path, nazwa: str):
    """Wtyczka załadowana tak jak dostawcę pamięci ładuje Hermes (plugins/plugin_loader.py, load_plugin_module):
    każdy sąsiedni `*.py` jako podmoduł `<pakiet>.<plik>`, potem `__init__`, potem podmoduły przypisane pakietowi pod
    nazwą pliku (to przypisanie nadpisuje funkcję `__init__` o tej samej nazwie)."""
    spec = importlib.util.spec_from_file_location(nazwa, katalog / "__init__.py", submodule_search_locations=[str(katalog)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nazwa] = mod
    podmoduly = []
    for plik in sorted(katalog.glob("*.py")):
        if plik.name == "__init__.py":
            continue
        s = importlib.util.spec_from_file_location(f"{nazwa}.{plik.stem}", plik)
        sub = importlib.util.module_from_spec(s)
        sys.modules[s.name] = sub
        s.loader.exec_module(sub)
        podmoduly.append((plik.stem, sub))
    spec.loader.exec_module(mod)
    for stem, sub in podmoduly:
        setattr(mod, stem, sub)
    return mod


def test_haki_po_ladowaniu_jak_hermes_i_odmowa_komputera_u_pracownika_karty(tmp_path, monkeypatch):
    """18.11, karta t_8a8a79ab po wdrożeniu księgi błędów: odmowa Komputera „ekran ma teraz inna sesja Jarva” i Google
    na Komputerze bez żadnego „[księga błędów]”, bez state/bledy-licznik.json. Hermes ładuje katalog wtyczki jako
    pakiet i przypisuje mu sąsiednie pliki pod ich nazwami, więc funkcje `cisza_tablicy` i `ksiega_bledow` z `__init__`
    zamieniały się w moduły `cisza_tablicy.py` i `ksiega_bledow.py`: `register()` oddawał moduły, a oba haki rzucały
    „'module' object is not callable”. Test ładuje wtyczkę jak Hermes (z wiedza.py obok, jak po buildzie), rejestruje
    haki i puszcza przez hak wynik odmowy Komputera w procesie pracownika karty."""
    wtyczka = tmp_path / "plugins" / "jarvo-wiedza"
    shutil.copytree(REPO / "wiedza" / "plugin", wtyczka, ignore=shutil.ignore_patterns("__pycache__", "dashboard"))
    for plik in ("wiedza.py", "kompilacja.py"):
        shutil.copy2(REPO / "wiedza" / plik, wtyczka / plik)
    for m in [m for m in sys.modules if m.startswith("jarvo_") and m != "jarvo_wiedza_plugin"]:
        monkeypatch.delitem(sys.modules, m)                  # moduły pomocnicze z kopii wtyczki, nie z repo
    mod = _jak_hermes(wtyczka, "_hermes_user_memory.jarvo_wiedza_test")
    haki = {}

    class Ctx:
        def register_memory_provider(self, provider): pass
        def register_hook(self, nazwa, f): haki[nazwa] = f
        def register_auxiliary_task(self, *a, **k): pass

    mod.register(Ctx())
    assert haki and all(inspect.isfunction(f) for f in haki.values()), {k: type(f) for k, f in haki.items()}
    # pracownik karty Jarva: HERMES_HOME profilu, numer karty w otoczeniu, skarbiec z zasiewem księgi
    monkeypatch.setenv("WIEDZA_DZIS", "2026-11-18")
    monkeypatch.delenv("JARVO_KNOWLEDGE_DIR", raising=False)
    monkeypatch.delenv("JARVO_STATE_DIR", raising=False)
    root = tmp_path / "dane"
    (root / "profiles" / "jarvo").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(root / "profiles" / "jarvo"))
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_8a8a79ab")
    sk = w.Skarbiec(root / "jarvo" / "knowledge", root / "jarvo" / "state")
    w.zasiej(sk, None, None, None, None, REPO / "wiedza" / "bledy")
    # odmowa wejścia Komputera (infra/komputer/zasady.wynik_odmowy, kod `zajete`) tak, jak oddaje ją computer_use
    # Hermesa: spłaszczona do message, z kodem decyzji „zablokowane”, bez nazwy zasady
    zajete = json.dumps({"ok": False, "action": "list_windows", "code": "zablokowane", "message":
                         "Komputer Jarva: ekran ma teraz inna sesja Jarva (karta t_8a8a79ab, ostatnie wywołanie 9 s temu); "
                         "zwolni się najpóźniej za 111 s albo wcześniej, gdy tamta sesja skończy."}, ensure_ascii=False)
    hak = haki["transform_tool_result"]
    nowy = hak(tool_name="computer_use", args={}, result=zajete, status="ok", task_id="t_8a8a79ab", session_id="sesja-karty",
               tool_call_id="c1", turn_id="", api_request_id="", duration_ms=3)
    assert nowy and nowy.startswith(zajete) and "To już było: Ekran Komputera zajęty przez inną kartę" in nowy
    # Google na ekranie Komputera (odczyt strony narzędziem `komputer`, zwykły wynik)
    google = json.dumps({"okno": 1, "tekst": "Logowanie – Konta Google\nTa przeglądarka lub aplikacja może nie być bezpieczna"})
    nowy = hak(tool_name="komputer", args={}, result=google, status="ok", task_id="t_8a8a79ab", session_id="sesja-karty")
    assert nowy and "Google nie loguje w przeglądarce Komputera" in nowy
    licznik = w.licznik_bledow(sk.stan)
    assert licznik["bledy/ekran komputera zajęty przez inną kartę"]["przypomnien"] == 1
    assert licznik["bledy/google nie loguje w przeglądarce komputera, konta google na telefonie"]["przypomnien"] == 1


def test_odpowiedz_na_brief_hakiem_i_brief_bez_ustalonych(tmp_path, monkeypatch):
    """23.11 właściciel: „odpowiadam na coś, a on mnie pyta o to samo”. Odpowiedź na brief zapisuje hak `pre_llm_call`
    (kod, nie model), a `transform_llm_output` wycina z nowego briefu pytanie o sprawę ustaloną; agent floty bez zmian."""
    root = tmp_path / "dane"
    skrypty = root / "profiles" / "jarvo" / "scripts"
    skrypty.mkdir(parents=True)
    for plik in ("briefy.py", "_sciezki.py"):
        shutil.copy2(REPO / "profiles" / "jarvo" / "scripts" / plik, skrypty / plik)
    monkeypatch.delenv("JARVO_KNOWLEDGE_DIR", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(root / "profiles" / "jarvo"))
    haki = []

    class Ctx:
        def register_memory_provider(self, provider): pass
        def register_hook(self, nazwa, f): haki.append((nazwa, f))
        def register_auxiliary_task(self, *a, **k): pass

    pl.register(Ctx())
    przed = [f for n, f in haki if n == "pre_llm_call"]
    assert pl.odpowiedz_na_brief in przed and pl.blokada_przed_tura in przed
    briefy = root / "jarvo" / "knowledge" / "briefy"
    briefy.mkdir(parents=True)
    (briefy / "B-2026-11-20.md").write_text(
        "# Poranny brief B-2026-11-20\n\n## Decyzje\n\n| Numer | Decyzja | Odpowiedź właściciela | Kiedy | Co zrobione |\n|---|---|---|---|---|\n"
        "| B-2026-11-20/1 | AssemblyAI: zapisać 3 klucze do `konfig/assemblyai-konta/`? Rekomenduję tak. |  |  |  |\n\n## Treść\n\nx\n",
        encoding="utf-8")
    wynik = pl.odpowiedz_na_brief(user_message="> Odpowiadam na raport „Poranny brief” (07:51): ☀️ Brief B-2026-11-20\n\n1 tak, zapisać",
                                  conversation_history=[], session_id="s", turn_id="t")
    assert "B-2026-11-20/1: 1 tak, zapisać" in wynik["context"] and "zrobione" in wynik["context"]
    assert "| „1 tak, zapisać”" in (briefy / "B-2026-11-20.md").read_text(encoding="utf-8")
    assert pl.odpowiedz_na_brief(user_message="co słychać?", conversation_history=[]) is None
    brief = ("☀️ Brief B-2026-11-23 · Dzień dobry.\nCzeka na Ciebie (2 decyzji):\n"
             "1. AssemblyAI: zapisać 3 klucze w `konfig/assemblyai-konta/`? Rekomenduję tak.\n"
             "2. Szukać zamiennika wyszukiwarki przed 1.01.2027? Rekomenduję tak.\nOdpowiedz np. „1 ok”.")
    nowy = pl.blokada_bez_ciszy(response_text=brief, session_id="cron", turn_id="t2")
    assert "AssemblyAI" not in nowy and "(1 decyzja):\n1. Szukać zamiennika" in nowy
    monkeypatch.setenv("HERMES_HOME", str(root / "profiles" / "jarvo-web"))               # inny agent: bez briefów
    assert pl.odpowiedz_na_brief(user_message="> Odpowiadam na raport „Poranny brief” (07:51): Brief B-2026-11-20\n\n1 nie",
                                 conversation_history=[]) is None


def test_teraz_we_flocie_hakiem(tmp_path, monkeypatch):
    """28.11 test OLX i SMS Jarva stukały naraz w telefon `first`: hak `pre_llm_call` daje agentowi blok „Teraz we
    flocie” z osi floty (zadania w toku innych agentów, zajęte urządzenia); własne zadania i pusta oś = nic."""
    root = tmp_path / "dane"
    state = root / "jarvo" / "state"
    state.mkdir(parents=True)
    for zmienna in ("JARVO_KNOWLEDGE_DIR", "JARVO_STATE_DIR", "HERMES_KANBAN_TASK"):
        monkeypatch.delenv(zmienna, raising=False)
    monkeypatch.setenv("HERMES_HOME", str(root / "profiles" / "jarvo"))
    haki = []

    class Ctx:
        def register_memory_provider(self, provider): pass
        def register_hook(self, nazwa, f): haki.append((nazwa, f))
        def register_auxiliary_task(self, *a, **k): pass

    pl.register(Ctx())
    assert ("pre_llm_call", pl.teraz_we_flocie) in haki
    assert pl.teraz_we_flocie(session_id="s1") is None                   # brak osi: nic
    teraz = time.time()
    c = sqlite3.connect(state / "os-floty.db")
    c.execute("CREATE TABLE zadania (id TEXT PRIMARY KEY, agent TEXT, tytul TEXT, stan TEXT, start_at REAL, zasoby TEXT, "
              "klucz TEXT, zmieniono_at REAL)")
    c.executemany("INSERT INTO zadania VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
        ("k:t1", "jarvo-web", "Strona OLX", "w_toku", teraz - 60, "[]", "karta:t1", teraz),
        ("p:p1", "jarvo", "Własna rozmowa", "w_toku", teraz - 30, "[]", "sesja:s1", teraz),
        ("p:p2", "jarvo", "Test OLX", "w_toku", teraz - 20, "[]", "sesja:s2", teraz)])
    c.commit()
    c.close()
    telefony = tmp_path / "stan" / "telefon-zadania.json"
    telefony.parent.mkdir()
    telefony.write_text(json.dumps({"first": {"klucz": "sesja:obca", "t": teraz - 5},
                                    "second": {"klucz": "sesja:s1", "t": teraz - 5}}), encoding="utf-8")
    tekst = pl.teraz_we_flocie(session_id="s1")["context"]
    assert tekst.startswith("Teraz we flocie (inne zadania;") and "jarvo-web · Strona OLX · od " in tekst
    assert "jarvo (twoja inna rozmowa) · Test OLX · od " in tekst      # ten sam profil, inna sesja
    assert "telefon:first · zajęty przez inne zadanie (sesja:obca)" in tekst
    assert "Własna rozmowa" not in tekst and "telefon:second" not in tekst
