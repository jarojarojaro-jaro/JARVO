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
