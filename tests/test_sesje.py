"""Skrzynki sesji zewnętrznych: „… gpu” od właściciela trafia do skrzynki sesji zamiast do Jarva."""

import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("jarvo_sesje_t", REPO / "sesje" / "plugin" / "__init__.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Brama:
    def __init__(self, dozwolony=True):
        self.wyslane = []
        self.dozwolony = dozwolony
        brama = self

        class Adapter:
            async def send(self, chat_id, tekst):
                brama.wyslane.append((chat_id, tekst))

        self.adapter = Adapter()

    def _is_user_authorized_for_source(self, _zrodlo):
        return self.dozwolony

    def _delivery_adapter_for(self, _zrodlo):
        return self.adapter


def ustaw(tmp_path, monkeypatch):
    dane = tmp_path / "dane"
    (dane / "jarvo" / "konfig").mkdir(parents=True)
    skrzynka = tmp_path / "kernel" / "skrzynka"
    (dane / "jarvo" / "konfig" / "sesje.json").write_text(
        json.dumps({"GPU": {"nazwa": "Kernel", "skrzynka": str(skrzynka)}}), encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(dane))
    return skrzynka


def zdarzenie(tekst, mid="41", media=()):
    return SimpleNamespace(text=tekst, internal=False, message_id=mid, media_urls=list(media), reply_to_text=None,
                           source=SimpleNamespace(chat_id="777", platform="telegram"))


def test_rozpoznaje_tylko_ostatnie_slowo():
    s = load()
    dopiski = {"gpu": {}}
    assert s.rozpoznaj("https://x.com/a/status/1 ciekawe gpu", dopiski) == ("gpu", "https://x.com/a/status/1 ciekawe")
    assert s.rozpoznaj("zobacz to, GPU.", dopiski) == ("gpu", "zobacz to")
    assert s.rozpoznaj("gpu", dopiski) == ("gpu", "")
    assert s.rozpoznaj("nowe gpu od nvidii, co myślisz", dopiski) is None      # słowo w środku: zwykła rozmowa
    assert s.rozpoznaj("kup gpus", dopiski) is None


def test_wiadomosc_z_dopiskiem_idzie_do_skrzynki_raz(tmp_path, monkeypatch):
    s = load()
    skrzynka = ustaw(tmp_path, monkeypatch)
    zdjecie = tmp_path / "zdj.jpg"
    zdjecie.write_bytes(b"\xff\xd8")
    brama = Brama()
    ev = zdarzenie("https://x.com/a/status/1 to dla nas? gpu", media=[zdjecie])
    wynik = asyncio.run(s.przechwyc(event=ev, gateway=brama))
    assert wynik["action"] == "skip"
    pliki = list((skrzynka / "nowe").glob("*.json"))
    assert len(pliki) == 1
    wpis = json.loads(pliki[0].read_text(encoding="utf-8"))
    assert wpis["tekst"] == "https://x.com/a/status/1 to dla nas?" and wpis["nazwa"] == "Kernel"
    assert Path(wpis["media"][0]).read_bytes() == b"\xff\xd8"           # kopia: plik Hermesa może zniknąć
    assert brama.wyslane == [("777", "📥 Kernel: przyjąłem, analizuję.")]
    # ten sam event drugi raz (druga rejestracja wtyczki, ponowienie): bez drugiego pliku i potwierdzenia
    assert asyncio.run(s.przechwyc(event=ev, gateway=brama))["action"] == "skip"
    assert len(list((skrzynka / "nowe").glob("*.json"))) == 1 and len(brama.wyslane) == 1


def test_obcy_nadawca_i_zwykla_wiadomosc_ida_do_jarva(tmp_path, monkeypatch):
    s = load()
    skrzynka = ustaw(tmp_path, monkeypatch)
    assert asyncio.run(s.przechwyc(event=zdarzenie("link gpu"), gateway=Brama(dozwolony=False))) is None
    assert asyncio.run(s.przechwyc(event=zdarzenie("co nowego w briefie?", mid="42"), gateway=Brama())) is None
    assert not (skrzynka / "nowe").exists()


def test_bez_konfiguracji_nic_nie_przechwytuje(tmp_path, monkeypatch):
    s = load()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "pusto"))
    assert asyncio.run(s.przechwyc(event=zdarzenie("link gpu"), gateway=Brama())) is None


def test_dlugi_tekst_dzielony_po_liniach():
    from jarvo.wiedza_cli import kawalki_wiadomosci
    tekst = "\n".join(f"wiersz {i:03d} " + "x" * 90 for i in range(100))
    czesci = kawalki_wiadomosci(tekst, limit=1000)
    assert all(len(c) <= 1000 for c in czesci) and "\n".join(czesci) == tekst
    assert kawalki_wiadomosci("a" * 2500, limit=1000) == ["a" * 1000, "a" * 1000, "a" * 500]


class AdapterHermesa:
    """Jak gateway/platforms/base.py: obsługa wiadomości do zajętej rozmowy ustawiana przez set_busy_session_handler."""
    def __init__(self):
        self.do_jarva = []

        async def hermes(event, session_key):           # obsługa Hermesa: wiadomość trafia do trwającej tury Jarva
            self.do_jarva.append(event.text)
            return True
        self._busy_session_handler = hermes

    def set_busy_session_handler(self, handler):
        self._busy_session_handler = handler


def test_dopisek_do_zajetej_rozmowy_idzie_do_skrzynki(tmp_path, monkeypatch):
    """14.11: Jarvo był w trakcie tury, a trzy linki „… gpu” poszły do niego, bo zajęta rozmowa omija pre_gateway_dispatch."""
    s = load()
    skrzynka = ustaw(tmp_path, monkeypatch)
    brama = Brama()
    adapter = AdapterHermesa()
    brama.adapters = {"telegram": adapter}
    assert asyncio.run(s.hak_bramy(event=zdarzenie("cześć", mid="1"), gateway=brama)) is None
    asyncio.run(s.hak_bramy(event=zdarzenie("drugie", mid="2"), gateway=brama))   # bez drugiego owinięcia
    obsluga = adapter._busy_session_handler
    assert asyncio.run(obsluga(zdarzenie("https://x.com/a/status/1 gpu", mid="3"), "sesja")) is True
    assert asyncio.run(obsluga(zdarzenie("a to do Jarva", mid="4"), "sesja")) is True
    assert adapter.do_jarva == ["a to do Jarva"]
    assert len(list((skrzynka / "nowe").glob("*.json"))) == 1 and len(brama.wyslane) == 1


# -- grupa „Jarvo HQ”: wykrycie grupy, wątek Kernela, dopisek profilu (karta kanbana)

class BramaGrupy(Brama):
    """Jak Brama, ale adapter przyjmuje metadata (wątek grupy), jak plugins/platforms/telegram/adapter.py send."""
    def __init__(self, dozwolony=True):
        super().__init__(dozwolony)
        brama = self

        class Adapter:
            async def send(self, chat_id, tekst, metadata=None):
                brama.wyslane.append((chat_id, tekst, (metadata or {}).get("thread_id")))

        self.adapter = Adapter()


GRUPA = "-1001234567890"


def w_grupie(tekst, watek="7", temat=None, mid="51", nazwa_grupy="Jarvo HQ"):
    """Event z supergrupy z tematami jak adapter Telegrama Hermesa: chat_type "group", thread_id, raw_message (PTB)."""
    odpowiedz = SimpleNamespace(forum_topic_created=SimpleNamespace(name=temat)) if temat else None
    surowa = SimpleNamespace(chat=SimpleNamespace(id=int(GRUPA), title=nazwa_grupy, is_forum=True),
                             reply_to_message=odpowiedz, forum_topic_created=None, forum_topic_edited=None)
    return SimpleNamespace(text=tekst, internal=False, message_id=mid, media_urls=[], reply_to_text=None,
                           raw_message=surowa,
                           source=SimpleNamespace(chat_id=GRUPA, chat_type="group", thread_id=watek, chat_name=nazwa_grupy,
                                                  chat_topic=None, platform="telegram"))


def konfig_sesji(tmp_path, monkeypatch, wpisy):
    dane = tmp_path / "dane"
    (dane / "jarvo" / "konfig").mkdir(parents=True, exist_ok=True)
    (dane / "jarvo" / "konfig" / "sesje.json").write_text(json.dumps(wpisy), encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(dane / "profiles" / "jarvo"))       # zakres profilu trasy
    return dane


def test_wiadomosc_w_grupie_zapisuje_grupe_i_watek_a_idzie_dalej(tmp_path, monkeypatch):
    s = load()
    dane = konfig_sesji(tmp_path, monkeypatch, {})
    brama = BramaGrupy()
    assert asyncio.run(s.przechwyc(event=w_grupie("co u was?", temat="Sherlock"), gateway=brama)) is None
    plik = dane / "jarvo" / "state" / "telegram-grupy.json"
    grupa = json.loads(plik.read_text(encoding="utf-8"))["grupy"][GRUPA]
    assert grupa["nazwa"] == "Jarvo HQ" and grupa["forum"] is True and grupa["watki"]["7"]["nazwa"] == "Sherlock"
    mtime = plik.stat().st_mtime_ns
    assert s.zapamietaj_grupe(w_grupie("drugie", temat="Sherlock", mid="52"), dane) is False      # bez zmian: bez zapisu
    assert plik.stat().st_mtime_ns == mtime
    assert s.zapamietaj_grupe(w_grupie("ogólne", watek="1", mid="53"), dane) is True
    assert json.loads(plik.read_text(encoding="utf-8"))["grupy"][GRUPA]["watki"]["1"]["nazwa"] == "General"
    # obcy w grupie: nic nie zapisuje, wiadomość idzie zwykłą drogą
    asyncio.run(s.przechwyc(event=w_grupie("spam", watek="9", temat="Obcy", mid="54"), gateway=BramaGrupy(dozwolony=False)))
    assert "9" not in json.loads(plik.read_text(encoding="utf-8"))["grupy"][GRUPA]["watki"]
    assert brama.wyslane == []


def test_start_w_watku_zapisuje_potwierdza_i_zleca_watki_operatorowi(tmp_path, monkeypatch):
    """„start” nie budzi Jarva i nie każe właścicielowi nic uruchamiać (14.11: „uruchom na serwerze: jarvo telegram
    tematy”): bot potwierdza, a zlecenie wątków idzie do Claude Code w DLA-CLAUDE.md, jedno na grupę."""
    s = load()
    dane = konfig_sesji(tmp_path, monkeypatch, {})
    brama = BramaGrupy()
    wynik = asyncio.run(s.przechwyc(event=w_grupie("Start", watek="12", temat="Kernel", mid="60"), gateway=brama))
    assert wynik["action"] == "skip"
    assert brama.wyslane[0][0] == GRUPA and brama.wyslane[0][2] == "12" and "„Kernel”" in brama.wyslane[0][1]
    assert "jarvo " not in brama.wyslane[0][1] and "uruchom" not in brama.wyslane[0][1]
    assert json.loads((dane / "jarvo" / "state" / "telegram-grupy.json").read_text(encoding="utf-8"))[
        "grupy"][GRUPA]["watki"]["12"]["nazwa"] == "Kernel"
    zlecenia = dane / "jarvo" / "missions" / "DLA-CLAUDE.md"
    asyncio.run(s.przechwyc(event=w_grupie("start", watek="1", mid="61"), gateway=brama))     # drugi „start”: bez drugiego
    otwarte = [l for l in zlecenia.read_text(encoding="utf-8").splitlines() if l.startswith("- [ ]")]
    assert len(otwarte) == 1 and f"jarvo telegram tematy --grupa {GRUPA}" in otwarte[0]
    assert s.zlec_tematy(GRUPA, {"gpu": {"nazwa": "Kernel", "czat": GRUPA, "watek": "12"}}, dane) is False  # wątki są


def test_wiadomosc_w_watku_kernela_idzie_do_skrzynki_bez_dopisku(tmp_path, monkeypatch):
    s = load()
    skrzynka = tmp_path / "kernel" / "skrzynka"
    konfig_sesji(tmp_path, monkeypatch, {"gpu": {"nazwa": "Kernel", "skrzynka": str(skrzynka), "czat": GRUPA, "watek": "12"}})
    brama = BramaGrupy()
    assert asyncio.run(s.przechwyc(event=w_grupie("https://x.com/a/status/9 zobacz", watek="12", mid="70"),
                                   gateway=brama))["action"] == "skip"
    wpis = json.loads(next((skrzynka / "nowe").glob("*.json")).read_text(encoding="utf-8"))
    assert wpis["tekst"] == "https://x.com/a/status/9 zobacz" and wpis["dopisek"] == "gpu"
    assert wpis["chat_id"] == GRUPA and wpis["watek"] == "12"
    assert brama.wyslane == [(GRUPA, "📥 Kernel: przyjąłem, analizuję.", "12")]
    # inny wątek tej grupy bez dopisku: zwykła droga (Jarvo / agent wątku)
    assert asyncio.run(s.przechwyc(event=w_grupie("a to dla Jarva", watek="1", mid="71"), gateway=brama)) is None
    # DM z dopiskiem „gpu” jak dotąd: skrzynka, bez wątku (Kernel odpowie w DM)
    assert asyncio.run(s.przechwyc(event=zdarzenie("link gpu", mid="72"), gateway=brama))["action"] == "skip"
    dm = [json.loads(p.read_text(encoding="utf-8")) for p in (skrzynka / "nowe").glob("*.json")]
    assert {w["watek"] for w in dm} == {"12", ""}


def test_dopisek_dev_zaklada_karte_dla_profilu(tmp_path, monkeypatch):
    s = load()
    konfig_sesji(tmp_path, monkeypatch, {"dev": {"nazwa": "Jarodev", "profil": "jarvo-jarodev"}})
    karty = []

    def zaloz(profil, tytul, tresc, klucz):
        karty.append({"profil": profil, "tytul": tytul, "tresc": tresc, "klucz": klucz})
        return "t_abc123"

    monkeypatch.setattr(s, "zaloz_karte", zaloz)
    brama = Brama()
    tekst = "Dodaj eksport CSV do raportu kosztów w panelu, z filtrem dat i sumą na końcu dev"
    assert asyncio.run(s.przechwyc(event=zdarzenie(tekst, mid="80"), gateway=brama))["action"] == "skip"
    assert asyncio.run(s.przechwyc(event=zdarzenie(tekst, mid="80"), gateway=brama))["action"] == "skip"   # ponowienie
    assert len(karty) == 1
    k = karty[0]
    assert k["profil"] == "jarvo-jarodev" and k["klucz"] == "telegram:777:80"
    assert k["tytul"] == "Dodaj eksport CSV do raportu kosztów w panelu, z filtrem…"
    assert k["tresc"] == ("Dodaj eksport CSV do raportu kosztów w panelu, z filtrem dat i sumą na końcu\n\n"
                          "— od właściciela przez Telegram, dopisek dev")
    assert brama.wyslane == [("777", "📥 Jarodev: przyjąłem, karta t_abc123.")]


def test_karta_przez_api_kanbana_hermesa(monkeypatch):
    """zaloz_karte woła hermes_cli.kanban_db.create_task jak narzędzie kanban_create (atrapa modułów Hermesa)."""
    import sys
    import contextlib
    import types
    s = load()
    wolania = []
    kb = types.ModuleType("hermes_cli.kanban_db")
    kb.create_task = lambda conn, **kw: wolania.append((conn, kw)) or "t_42"
    kbc = types.ModuleType("hermes_cli.kanban_db_connect")
    kbc.connect_closing = contextlib.contextmanager(lambda board=None: (yield "polaczenie"))
    pakiet = types.ModuleType("hermes_cli")
    pakiet.kanban_db, pakiet.kanban_db_connect = kb, kbc
    for nazwa, mod in (("hermes_cli", pakiet), ("hermes_cli.kanban_db", kb), ("hermes_cli.kanban_db_connect", kbc)):
        monkeypatch.setitem(sys.modules, nazwa, mod)
    assert s.zaloz_karte("jarvo-jarodev", "Tytuł", "Treść", "telegram:1:2") == "t_42"
    assert wolania == [("polaczenie", {"title": "Tytuł", "body": "Treść", "assignee": "jarvo-jarodev",
                                       "created_by": "user", "idempotency_key": "telegram:1:2"})]


def test_nieudana_karta_idzie_do_jarva_i_mozna_ponowic(tmp_path, monkeypatch):
    s = load()
    konfig_sesji(tmp_path, monkeypatch, {"dev": {"nazwa": "Jarodev", "profil": "jarvo-jarodev"}})
    monkeypatch.setattr(s, "zaloz_karte", lambda *a: (_ for _ in ()).throw(RuntimeError("kanban zajęty")))
    assert asyncio.run(s.przechwyc(event=zdarzenie("napraw build dev", mid="90"), gateway=Brama())) is None
    monkeypatch.setattr(s, "zaloz_karte", lambda *a: "t_1")
    assert asyncio.run(s.przechwyc(event=zdarzenie("napraw build dev", mid="90"), gateway=Brama()))["action"] == "skip"
