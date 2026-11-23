"""jarvo/sesje_omp.py z atrapą `omp --mode rpc` (tests/atrapa_omp.py): tura, błąd, stop, trzymana dzierżawa = brak
tury, partia, powiadomienie o zajętej sesji, terminal z blokadą, dopisek w trakcie tury (steer), niedostarczony
steer wraca, /compact, licznik, bezczynny proces się zamyka, terminal prosi o sesję, padnięty proces, restart
skrzynki w trakcie tury, polecenie `jarvo sesja`."""
from __future__ import annotations

import datetime
import io
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import atrapa_omp

pytestmark = pytest.mark.skipif(os.name == "nt", reason="sesje omp z blokadą: Linux i macOS")
fcntl = pytest.importorskip("fcntl")

from jarvo import cli, sesje_omp as so  # noqa: E402

om = so.rdzen
REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def at(tmp_path, monkeypatch):
    k = tmp_path / "atrapa"
    monkeypatch.setenv("ATRAPA_OMP", str(k))
    monkeypatch.setenv("JARVO_OMP", str(atrapa_omp.zrob(k)))
    monkeypatch.setattr(so, "BEZCZYNNA_S", 0.0)        # jak dawna tura `-p`: proces kończy się, gdy nic nie czeka
    om._dzierzawy.clear()
    return k


def surowy_wpis(tmp_path, **panel):
    return {"nazwa": "Kernel", "skrzynka": str(tmp_path / "k" / "skrzynka"), "czat": "-1001", "watek": "7",
            "panel": {"zaplecze": "omp", "sesje": str(tmp_path / "k" / "sesje"), "sesja": "01a13b13-14db",
                      "cwd": str(tmp_path), "omp_arg": ["--no-context-files"], "potwierdzenia": True, **panel}}


@pytest.fixture
def w(tmp_path, at):
    wpis = om.wpis_z("gpu", surowy_wpis(tmp_path), tmp_path)
    (tmp_path / "k" / "sesje").mkdir(parents=True)
    wpis.katalogi()
    return wpis


class Telegram:
    def __init__(self):
        self.wyslane = []

    def __call__(self, tekst, czat, watek):
        self.wyslane.append((tekst, czat, watek))
        return True


def wywolania(at):
    p = at / "argv.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def procesy(at):
    return [a for a in wywolania(at) if "rpc" in a]


def komendy(at, typ=None):
    p = at / "rpc.jsonl"
    wszystkie = [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
    return [c for c in wszystkie if typ is None or c["type"] == typ]


def tury(at):
    return komendy(at, "prompt")


def telegramowa(w, nazwa, tekst="z telefonu"):
    om.zapisz_atomowo(w.nowe / nazwa, {"dopisek": "gpu", "tekst": tekst, "czas": "2026-11-17 12:00:00",
                                       "chat_id": "-1001", "watek": "7", "media": []})


def czekaj(warunek, czas=15.0, opis=""):
    koniec = time.time() + czas
    while time.time() < koniec:
        if warunek():
            return
        time.sleep(0.05)
    raise AssertionError(f"nie doczekałem się: {opis}")


def w_tle(w, tg=None):
    t = threading.Thread(target=so.skrzynka, args=(w, tg or Telegram()), daemon=True)
    t.start()
    return t


def test_tura_z_panelu(w, at):
    (w.nowe / "a.png").write_bytes(b"\x89PNG obraz")
    om.wyslij(w, "sprawdź GPU", "k1", media=[str(w.nowe / "a.png")])
    tg = Telegram()
    assert so.skrzynka(w, tg) == 0
    (argv,) = procesy(at)
    assert argv[argv.index("--session-dir") + 1] == str(w.sesje) and argv[argv.index("--resume") + 1] == w.sesja
    assert argv[argv.index("--mode") + 1] == "rpc" and "--no-ui" in argv and "--no-context-files" in argv
    (p,) = tury(at)
    assert "[Panel · gpu · " in p["message"] and "sprawdź GPU" in p["message"] and "[[czeka-na-tak]]" in p["message"]
    assert f"(załącznik: {w.nowe}/a.png)" in p["message"] and p["images"] == 1
    d = json.loads((w.zrobione / "panel-k1.json").read_text())
    assert d["odpowiedz"] == "Gotowe, zrobione." and om.przebieg(w, "k1")["stan"] == "gotowe"
    plik = w.tura / f"{d['tura']}.jsonl"
    zdarzenia, _ = om.ogon(w, d["tura"])
    assert [z["typ"] for z in zdarzenia] == ["narzedzie", "delta", "delta", "koniec"]
    assert zdarzenia[0] == {"typ": "narzedzie", "nazwa": "bash", "intencja": "Sprawdzam GPU"}
    assert zdarzenia[-1]["ok"] is True and "SEKRET" not in plik.read_text()
    assert tg.wyslane == [("🖥 sprawdź GPU", "-1001", "7"), ("Kernel\n\nGotowe, zrobione.", "-1001", "7")]
    s = om.czytaj_stan(w)
    assert s["tura"] is None and s["rpc"] is None and om.stan(w)["stan"] == "wolny"


def test_bez_lustra_i_z_telegrama(w, at):
    om.wyslij(w, "cicho", "k1", lustro=False)
    tg = Telegram()
    so.skrzynka(w, tg)
    assert tg.wyslane == []
    telegramowa(w, "1.json")
    so.skrzynka(w, tg)
    assert tg.wyslane == [("Kernel\n\nGotowe, zrobione.", "-1001", "7")]
    assert "[Telegram · gpu" in tury(at)[-1]["message"]


def test_blad_tury(w, at):
    (at / "tryb").write_text("blad")
    om.wyslij(w, "x", "k1")
    tg = Telegram()
    so.skrzynka(w, tg)
    p = om.przebieg(w, "k1")
    assert p["stan"] == "blad" and "model niedostępny" in p["blad"]
    assert tg.wyslane[0][0].startswith("⚠️ Kernel: tura nie wyszła")


def test_partia_po_szesc_w_jednym_procesie(w, at):
    for i in range(8):
        telegramowa(w, f"{i}.json", f"wiadomość {i}")
    so.skrzynka(w, Telegram())
    t = tury(at)
    assert len(t) == 2 and len(procesy(at)) == 1
    assert "wiadomość 6/6" in t[0]["message"] and "wiadomość 2/2" in t[1]["message"]
    assert len(list(w.zrobione.glob("*.json"))) == 8


def test_trzymana_dzierzawa_bez_tury(w, at):
    (at / "held.json").write_text(json.dumps([w.sesja]))
    om.wyslij(w, "x", "k1")
    tg = Telegram()
    so.skrzynka(w, tg)
    assert procesy(at) == [] and (w.nowe / "panel-k1.json").exists() and tg.wyslane == []
    stary = time.time() - 300
    os.utime(w.nowe / "panel-k1.json", (stary, stary))
    so.skrzynka(w, tg)
    so.skrzynka(w, tg)
    assert len(tg.wyslane) == 1 and "1 wiadomość(i) czeka" in tg.wyslane[0][0]
    (at / "held.json").write_text("[]")
    so.skrzynka(w, tg)
    assert len(tury(at)) == 1 and om.czytaj_stan(w)["powiadomiono"] is None


def test_terminal_trzyma_blokade(w, at):
    om.wyslij(w, "x", "k1")
    om.komenda(w, "compact", "", "c1")
    with w.blokada.open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        assert so.skrzynka(w, Telegram()) == 0
        assert om.stan(w)["stan"] == "terminal"
    assert procesy(at) == [] and om.przebieg(w, "k1")["stan"] == "kolejka"
    assert om.wynik_komendy(w, "c1")["stan"] == "kolejka"


def test_proba_panelu_nie_zatrzymuje_skrzynki(w, at):
    """InstaBox 20.11: stan() panelu (próbny flock) trafił w chwilę startu skrzynki, ta uznała sesję za zajętą
    i skończyła się bez tury. Krótko trzymana blokada (tu 0,2 s, jak powolna próba) nie może tego zrobić."""
    om.wyslij(w, "x", "k1")
    with w.blokada.open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        watek = w_tle(w)
        time.sleep(0.2)
        fcntl.flock(f, fcntl.LOCK_UN)
    watek.join(15)
    assert om.przebieg(w, "k1")["stan"] == "gotowe" and len(tury(at)) == 1


def test_stop_z_panelu(w, at):
    (at / "tryb").write_text("spi")
    om.wyslij(w, "długie", "k1")
    watek = w_tle(w)
    czekaj(lambda: om.stan(w)["stan"] == "pracuje" and (at / "spi").exists(), opis="tura śpi")
    assert om.przebieg(w, "k1")["stan"] == "pracuje"
    assert om.zatrzymaj(w) is True
    watek.join(20)
    assert not watek.is_alive()
    p = om.przebieg(w, "k1")
    assert p["stan"] == "blad" and "zatrzymana" in p["blad"]
    assert komendy(at, "abort_and_restore_queue")                  # abort przez RPC, proces nie był zabijany
    zdarzenia, _ = om.ogon(w, p["tura"])
    assert zdarzenia[-1]["typ"] == "koniec" and zdarzenia[-1]["ok"] is False


def test_dopisek_w_trakcie_tury(w, at):
    (at / "tryb").write_text("czekaj")
    om.wyslij(w, "zrób raport", "k1")
    tg = Telegram()
    watek = w_tle(w, tg)
    czekaj(lambda: (at / "czeka").exists() and om.stan(w)["stan"] == "pracuje", opis="tura czeka na steer")
    om.wyslij(w, "zwykła, po turze", "k3")                          # bez steer: czeka na własną turę
    r = om.dopisz(w, "i dodaj wykres", "k2")
    assert r["nowy"] and r["tryb"] == "steer"
    czekaj(lambda: om.przebieg(w, "k2")["stan"] == "wlaczony", opis="dopisek w turze")
    tura = om.przebieg(w, "k1")["tura"]
    assert om.przebieg(w, "k2")["tura"] == tura
    watek.join(20)
    (steer,) = komendy(at, "steer")
    assert steer["message"].startswith(so.WSTEP_DOPISKU) and "#k2 · wiadomość 1/1]\ni dodaj wykres" in steer["message"]
    assert om.przebieg(w, "k1")["stan"] == "gotowe"
    p2 = om.przebieg(w, "k2")
    assert p2 == {**p2, "stan": "wlaczony", "tura": tura} and p2["odpowiedz"] == "Gotowe, zrobione. Dopiski: 1."
    assert len(tury(at)) == 2 and "zwykła, po turze" in tury(at)[1]["message"]
    assert om.przebieg(w, "k3")["stan"] == "gotowe" and om.przebieg(w, "k3")["tura"] != tura
    assert tg.wyslane[0] == ("🖥 zrób raport\n\ni dodaj wykres", "-1001", "7")
    assert om.dopisz(w, "po wszystkim", "k4")["tryb"] == "kolejka"


def test_niedostarczony_dopisek_wraca_jako_tura(w, at):
    (at / "tryb").write_text("nie_dostarczaj")
    om.wyslij(w, "pierwsza", "k1")
    watek = w_tle(w)
    czekaj(lambda: (at / "czeka").exists(), opis="tura czeka")
    om.dopisz(w, "spóźniony", "k2")
    watek.join(20)
    (usun,) = komendy(at, "remove_queued_message")
    assert usun["queue"] == "steering" and "spóźniony" in usun["message"]
    p1, p2 = om.przebieg(w, "k1"), om.przebieg(w, "k2")
    assert p1["stan"] == p2["stan"] == "gotowe" and p1["tura"] != p2["tura"]
    assert "spóźniony" in tury(at)[1]["message"]


def test_compact_i_licznik(w, at):
    assert om.komendy_omp(w) == [{"nazwa": "compact", "opis": om.KOMENDY["compact"][0], "aliasy": ["compress"]}]
    assert om.licznik(w) == om.LICZNIK_PUSTY
    om.wyslij(w, "x", "k1")
    so.skrzynka(w, Telegram())
    lic = om.licznik(w)
    assert (lic["model"], lic["kontekst"], lic["okno"], lic["procent"]) == ("atrapa/model-x", 5000, 200000, 2.5)
    assert (lic["wejscie"], lic["wyjscie"], lic["cache_odczyt"], lic["cache_zapis"]) == (100, 10, 900, 50)
    r = om.komenda(w, "/compress", "skup się na GPU", "c1")
    assert r["nowy"] and om.komenda(w, "compact", "", "c1")["nowy"] is False
    assert (w.nowe / om.BUDZIK).exists() and om.czekajace(w) == []    # budzik nie jest wiadomością
    assert om.wynik_komendy(w, "c1")["stan"] == "kolejka"
    so.skrzynka(w, Telegram())
    (c,) = komendy(at, "compact")
    assert c["customInstructions"] == "skup się na GPU"
    wk = om.wynik_komendy(w, "c1")
    assert wk["stan"] == "gotowe" and wk["wynik"] == "Kontekst skompresowany: było 5 000 tokenów, jest 1 200 (0,6% okna)."
    assert om.licznik(w)["kontekst"] == 1200
    (at / "compact_blad").write_text("")
    om.komenda(w, "compact", "", "c2")
    so.skrzynka(w, Telegram())
    wk = om.wynik_komendy(w, "c2")
    assert wk["stan"] == "blad" and "Nothing to compact" in wk["blad"]
    with pytest.raises(ValueError):
        om.komenda(w, "reboot", "", "c3")
    assert om.wynik_komendy(w, "nie-ma")["stan"] == "brak"


def test_licznik_z_pliku_sesji(w, at):
    om.wyslij(w, "x", "k1")
    so.skrzynka(w, Telegram())
    (w.skrzynka / om.PLIK_LICZNIKA).unlink()
    lic = om.licznik(w)
    assert (lic["model"], lic["kontekst"], lic["okno"], lic["procent"]) == ("atrapa/model-x", 1050, 0, 0.0)
    om.zapisz_atomowo(w.skrzynka / om.PLIK_LICZNIKA, {**om.LICZNIK_PUSTY, "model": "atrapa/model-x", "okno": 200000})
    stary = time.time() - 600
    os.utime(w.skrzynka / om.PLIK_LICZNIKA, (stary, stary))           # terminal pracował po skrzynce
    lic = om.licznik(w)
    assert (lic["kontekst"], lic["okno"], lic["procent"], round(lic["koszt"], 2)) == (1050, 200000, 0.5, 0.01)
    (w.skrzynka / om.PLIK_LICZNIKA).write_text("zepsuty")
    assert om.licznik(w)["kontekst"] == 1050


def test_licznik_po_compact_i_zmianach_z_terminala(w, at):
    """23.11 właściciel: „zrobiłem compact, a w interfejsie się nie zupdatowało”. Kompresja, poziom myślenia i tryb
    szybki zmienione w terminalu (wpisy `compaction`, `thinking_level_change`, `service_tier_change` w pliku sesji)
    licznik pokazuje od razu, bez nowej odpowiedzi modelu; nowszy wybór panelu (model.json) wygrywa z tym z pliku."""
    om.wyslij(w, "x", "k1")
    so.skrzynka(w, Telegram())
    (w.skrzynka / om.PLIK_LICZNIKA).unlink()
    teraz = datetime.datetime.now(datetime.timezone.utc)
    iso = lambda s: (teraz + datetime.timedelta(seconds=s)).isoformat().replace("+00:00", "Z")  # noqa: E731
    wpisy = [{"type": "compaction", "id": "c1", "parentId": None, "timestamp": iso(-60), "summary": "…",
              "shortSummary": "Remote compaction", "tokensBefore": 611035, "tokensAfter": 43506},
             {"type": "thinking_level_change", "id": "t1", "parentId": "c1", "timestamp": iso(-50), "thinkingLevel": "xhigh"},
             {"type": "service_tier_change", "id": "s1", "parentId": "t1", "timestamp": iso(-40), "serviceTier": "priority"}]
    with om.plik_sesji(w).open("a", encoding="utf-8") as f:
        f.write("".join(json.dumps(e, separators=(",", ":")) + "\n" for e in wpisy))
    lic = om.licznik(w)
    assert (lic["kontekst"], lic["myslenie"], lic["fast"]) == (43506, "xhigh", True)
    assert lic["kompresja"]["przed"] == 611035 and lic["kompresja"]["po"] == 43506
    om.ustaw_opcje_skrzynki(w, myslenie="low", fast=False)              # wybór panelu po zmianach w terminalu
    assert (om.licznik(w)["myslenie"], om.licznik(w)["fast"]) == ("low", False)
    stary = teraz.timestamp() - 3600
    os.utime(w.skrzynka / om.PLIK_MODELU, (stary, stary))               # wybór sprzed zmian w terminalu
    assert (om.licznik(w)["myslenie"], om.licznik(w)["fast"]) == ("xhigh", True)


def test_odpowiedz_tury_to_wszystkie_teksty_po_ostatnim_narzedziu():
    """23.11: Kernel napisał podsumowanie 13 linków, w tej chwili doszedł dopisek, dopisał zdanie o nim i właściciel
    dostał tylko to zdanie. Odpowiedź tury = wszystkie teksty po ostatnim wywołaniu narzędzia; komentarz przy
    wywołaniu narzędzia („Meanwhile…”) nie jest odpowiedzią."""
    t = so.Tura.__new__(so.Tura)
    t.koncowe, t.odpowiedz, t.dopiski, t.f, t.wynik, t.cisza, t.koniec, t.prompt_id, t.usuwane = \
        [], "", {}, None, None, False, False, None, {}
    asystent = lambda tekst, narzedzie=False: {"type": "message_end", "message": {"role": "assistant", "content":  # noqa: E731
        [{"type": "text", "text": tekst}] + ([{"type": "toolCall", "id": "c", "name": "bash"}] if narzedzie else [])}}
    for e in (asystent("Meanwhile wiersz w rejestrze.", True),
              {"type": "message_end", "message": {"role": "toolResult", "content": [{"type": "text", "text": "ok"}]}},
              asystent("Podsumowanie: 1. Strata… 13. Multi-Branch."),
              {"type": "message_end", "message": {"role": "user", "content": [{"type": "text", "text": "dopisek"}]}},
              asystent("Punkt 14 zapisany, commit 92be3f2.")):
        t.zdarzenie(e)
    assert t.odpowiedz == "Podsumowanie: 1. Strata… 13. Multi-Branch.\n\nPunkt 14 zapisany, commit 92be3f2."


def test_opcje_panelu_w_procesie_rpc_i_liczniku(w, at):
    """`/effort` i `/fast` z panelu (model.json: `myslenie`, `fast`, obok modelu) skrzynka stosuje w procesie RPC
    (`set_thinking_level`, `set_fast_mode`) przed turą, bez restartu procesu; licznik pokazuje je, a podsumowanie
    pliku sesji czyta dopisane linie przyrostowo."""
    om.ustaw_model_skrzynki(w, "atrapa/model-x")
    assert om.ustaw_opcje_skrzynki(w, myslenie="high", fast=True) == {"myslenie": "high", "fast": True}
    assert json.loads((w.skrzynka / om.PLIK_MODELU).read_text()) == {"model": "atrapa/model-x", "myslenie": "high",
                                                                     "fast": True}
    with pytest.raises(ValueError):
        om.ustaw_opcje_skrzynki(w, myslenie="bardzo")
    om.wyslij(w, "x", "k1")
    so.skrzynka(w, Telegram())
    poz = [(c["type"], c.get("level", c.get("enabled"))) for c in komendy(at)
           if c["type"] in ("set_thinking_level", "set_fast_mode")]
    assert poz == [("set_thinking_level", "high"), ("set_fast_mode", True)] and len(procesy(at)) == 1
    lic = om.licznik(w)
    assert (lic["myslenie"], lic["fast"]) == ("high", True)
    om.ustaw_opcje_skrzynki(w, myslenie="", fast=None)
    om.ustaw_model_skrzynki(w, None)
    assert not (w.skrzynka / om.PLIK_MODELU).exists()
    p1 = om.podsumowanie_sesji(w)
    om.wyslij(w, "y", "k2")
    so.skrzynka(w, Telegram())
    p2 = om.podsumowanie_sesji(w)
    assert p2["odpowiedzi"] == p1["odpowiedzi"] + 1 and p2["model"] == "model-x"


def test_dopisek_do_tury_starej_skrzynki_idzie_do_kolejki(w, at):
    """Tura starej skrzynki (`omp -p`, bez procesu RPC w stan.json) nie przyjmuje steera: `dopisz` mówi `kolejka`."""
    om.zapisz_stan(w, tura={"id": "20261120-120000-abcdef", "pid": os.getpid(), "start": time.time(), "klucze": []},
                   rpc=None)
    assert om.dopisz(w, "i jeszcze to", "k9")["tryb"] == "kolejka"


def test_bezczynny_proces_zamyka_sie(w, at, monkeypatch):
    monkeypatch.setattr(so, "BEZCZYNNA_S", 1.5)
    om.wyslij(w, "a", "k1")
    watek = w_tle(w)
    czekaj(lambda: om.przebieg(w, "k1")["stan"] == "gotowe", opis="pierwsza tura")
    s = om.stan(w)
    assert s["stan"] == "wolny" and s["proces_od"] and watek.is_alive()   # sesja w procesie RPC, nie „terminal”
    om.wyslij(w, "b", "k2")
    czekaj(lambda: om.przebieg(w, "k2")["stan"] == "gotowe", opis="druga tura w tym samym procesie")
    watek.join(10)
    assert not watek.is_alive() and len(procesy(at)) == 1 and len(tury(at)) == 2
    assert om.czytaj_stan(w)["rpc"] is None and not om.blokada_zajeta(w) and om.stan(w)["proces_od"] is None


def test_zamykaj_bezczynna_min_z_wpisu(tmp_path, at):
    wpis = om.wpis_z("gpu", surowy_wpis(tmp_path, zamykaj_bezczynna_min=30), tmp_path)
    assert so.Sesja(wpis).bezczynna_s == 1800


def test_przed_tura_i_nowy_system(tmp_path, at, monkeypatch):
    """Kernel: `kernel.py system` przed każdą turą składa system.md; zmieniony system = nowy proces omp (omp czyta
    `--append-system-prompt` przy starcie), niezmieniony = ten sam proces."""
    monkeypatch.setattr(so, "BEZCZYNNA_S", 60.0)
    zrodlo, system, licz = tmp_path / "zasady.md", tmp_path / "system.md", tmp_path / "hak.txt"
    zrodlo.write_text("v1")
    hak = ("import pathlib, sys; z, s, n = map(pathlib.Path, sys.argv[1:]); n.write_text((n.read_text() if n.exists()"
           " else '') + '.'); t = z.read_text(); (s.read_text() if s.exists() else None) != t and s.write_text(t)")
    wpis = om.wpis_z("gpu", surowy_wpis(tmp_path, omp_arg=["--append-system-prompt", str(system)],
                                        przed_tura=[sys.executable, "-c", hak, str(zrodlo), str(system), str(licz)]),
                     tmp_path)
    (tmp_path / "k" / "sesje").mkdir(parents=True)
    wpis.katalogi()
    om.wyslij(wpis, "k1", "k1")
    watek = w_tle(wpis)
    czekaj(lambda: om.przebieg(wpis, "k1")["stan"] == "gotowe", opis="k1")
    om.wyslij(wpis, "k2", "k2")
    czekaj(lambda: om.przebieg(wpis, "k2")["stan"] == "gotowe", opis="k2")
    assert system.read_text() == "v1" and licz.read_text() == ".." and len(procesy(at)) == 1
    time.sleep(0.05)
    zrodlo.write_text("v2 z nowym arsenałem")
    om.wyslij(wpis, "k3", "k3")
    czekaj(lambda: om.przebieg(wpis, "k3")["stan"] == "gotowe", opis="k3")
    assert system.read_text() == "v2 z nowym arsenałem" and licz.read_text() == "..." and len(procesy(at)) == 2
    (wpis.skrzynka / om.PLIK_ZWOLNIJ).write_text(str(os.getpid()))
    watek.join(10)
    assert not watek.is_alive()


def test_terminal_prosi_skrzynke_o_sesje(w, at, monkeypatch):
    monkeypatch.setattr(so, "BEZCZYNNA_S", 60.0)
    om.wyslij(w, "a", "k1")
    watek = w_tle(w)
    czekaj(lambda: om.przebieg(w, "k1")["stan"] == "gotowe", opis="tura")
    start = time.time()
    assert so.terminal(w, [], po_wyjsciu=lambda *a: None) == 0
    assert time.time() - start < 20 and not watek.is_alive()
    assert not (w.skrzynka / om.PLIK_ZWOLNIJ).exists() and wywolania(at)[-1][:2] == ["--session-dir", str(w.sesje)]


def test_proces_padl(w, at):
    (at / "tryb").write_text("padnij")
    om.wyslij(w, "x", "k1")
    so.skrzynka(w, Telegram())
    p = om.przebieg(w, "k1")
    assert p["stan"] == "blad" and "omp padł" in p["blad"] and "kod 3" in p["blad"]
    (at / "tryb").write_text("ok")
    om.wyslij(w, "y", "k2")
    so.skrzynka(w, Telegram())
    assert om.przebieg(w, "k2")["stan"] == "gotowe" and len(procesy(at)) == 2


def test_restart_skrzynki_w_trakcie_tury(w, at, tmp_path):
    (at / "tryb").write_text("spi")
    om.wyslij(w, "długie", "k1")
    kod = ("import json, signal, sys; from pathlib import Path; sys.path.insert(0, sys.argv[3]);"
           "from jarvo import sesje_omp as so;"
           "w = so.rdzen.wpis_z('gpu', json.loads(sys.argv[1]), Path(sys.argv[2]));"
           "signal.signal(signal.SIGTERM, so.koniec_uslugi); so.skrzynka(w, lambda *a: True)")
    usluga = subprocess.Popen([sys.executable, "-c", kod, json.dumps(surowy_wpis(tmp_path)), str(tmp_path), str(REPO)],
                              cwd=REPO)
    try:
        czekaj(lambda: (at / "spi").exists() and om.stan(w)["stan"] == "pracuje", opis="tura usługi")
        omp = om.czytaj_stan(w)["rpc"]["pid"]
        tura = om.czytaj_stan(w)["tura"]["id"]
        usluga.send_signal(signal.SIGTERM)
        assert usluga.wait(20) == 128 + signal.SIGTERM
    finally:
        usluga.kill()
    assert not om.zyje(omp) and (w.nowe / "panel-k1.json").exists()   # wiadomość czeka, omp zamknięty
    zdarzenia, _ = om.ogon(w, tura)
    assert zdarzenia[-1]["typ"] == "koniec" and zdarzenia[-1]["ok"] is False
    (at / "tryb").write_text("ok")
    so.skrzynka(w, Telegram())
    assert om.przebieg(w, "k1")["stan"] == "gotowe"


def test_sierota_po_padnietej_skrzynce(w, at):
    sierota = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", "omp", "--session-dir", str(w.sesje)])
    threading.Thread(target=sierota.wait, daemon=True).start()     # jak init: zombie znika od razu
    try:
        (w.tura / "20261117-120000-abcdef.jsonl").write_text('{"typ": "delta", "tekst": "A"}\n')
        om.zapisz_stan(w, rpc={"pid": sierota.pid, "skrzynka": 999999, "od": 1},
                       tura={"id": "20261117-120000-abcdef", "pid": sierota.pid, "start": 1, "klucze": ["k1"]})
        om.wyslij(w, "x", "k1")
        so.skrzynka(w, Telegram())
        assert sierota.wait(10) != 0
    finally:
        sierota.kill()
    zdarzenia, _ = om.ogon(w, "20261117-120000-abcdef")
    assert zdarzenia[-1] == {"typ": "koniec", "ok": False, "kod": 1, "odpowiedz": ""}
    assert om.przebieg(w, "k1")["stan"] == "gotowe"


def test_terminal(w, at):
    po = []
    om.wyslij(w, "x", "k1")
    assert so.terminal(w, ["--model", "opus"], po_wyjsciu=lambda *a: po.append(a)) == 0
    argv = wywolania(at)[-1]
    assert argv[:4] == ["--session-dir", str(w.sesje), "--resume", w.sesja] and argv[-2:] == ["--model", "opus"]
    assert "-e" not in argv                        # bez panel.wiedza: bez wtyczki mózgu
    assert len(po) == 1 and om.czytaj_stan(w)["terminal"] is None and not om.blokada_zajeta(w)
    (at / "held.json").write_text(json.dumps([w.sesja]))
    om._dzierzawy.clear()
    n = len(wywolania(at))
    assert so.terminal(w, [], po_wyjsciu=lambda *a: None) == 1
    assert all(a[:2] == ["session", "lease"] for a in wywolania(at)[n:])


def test_terminal_z_mozgiem_sesji(tmp_path, at, monkeypatch):
    """Wpis z `panel.wiedza`: terminal ładuje wtyczkę omp mózgu (`-e jarvo/omp/mozg_sesji.ts` przed argumentami
    właściciela) i daje jej polecenie `jarvo sesja <klucz> wiedza` tym samym Pythonem i kodem (JARVO_SESJA_WIEDZA)."""
    wpis = om.wpis_z("gpu", surowy_wpis(tmp_path, wiedza={"katalog": str(tmp_path / "wiki")}), tmp_path)
    (tmp_path / "k" / "sesje").mkdir(parents=True)
    wpis.katalogi()
    srodowiska, prawdziwy = [], subprocess.Popen

    def popen(*a, **k):
        srodowiska.append(k.get("env") or {})
        return prawdziwy(*a, **k)
    monkeypatch.setattr(so.subprocess, "Popen", popen)
    assert so.terminal(wpis, ["--model", "opus"], po_wyjsciu=lambda *a: None, korzen=tmp_path / "root") == 0
    assert wywolania(at)[-1][-4:] == ["-e", str(so.ROZSZERZENIE), "--model", "opus"] and so.ROZSZERZENIE.is_file()
    (env,) = [e for e in srodowiska if "JARVO_SESJA_WIEDZA" in e]
    assert env["JARVO_SESJA_KLUCZ"] == "gpu" and json.loads(env["JARVO_SESJA_WIEDZA"]) == [
        sys.executable, "-I", "-X", "utf8", str(REPO / "jarvo" / "start.py"), "--korzen", str(tmp_path / "root"),
        "sesja", "gpu", "wiedza"]


def test_wiedza_z_terminalu(tmp_path, at, monkeypatch, capsys):
    """`wiedza przed-tura` i `po-turze` (wtyczka omp terminalu) robią to co tura skrzynki, z kanałem `terminal`:
    blok z notatką i linkiem, wiersz rejestru z kanałem (domyślne `linki_z` mają terminal), wpis dziennika z kanałem;
    `--dopisek` bez zapisu do rejestru; po turze wyciąg odpowiedzi w werdykcie; zły JSON = kod 2."""
    from jarvo import mozg_sesji
    monkeypatch.setattr(mozg_sesji, "stan_wektorow_instalacji", lambda: tmp_path / "brak-uslugi")
    wiki = tmp_path / "wiki"
    (wiki / "llm").mkdir(parents=True)
    (wiki / "llm" / "inkling-2-mini.md").write_text("---\ntyp: llm\n---\n# Inkling 2 Mini\n\n**Inkling na XTX: 33,9 t/s, "
                                                    "limit to kernele MoE.**\n", encoding="utf-8")
    (wiki / "ZRODLA.md").write_text("# Rejestr\n\n## Powiązane\n- [[index]]\n", encoding="utf-8")
    wpis = om.wpis_z("gpu", surowy_wpis(tmp_path, wiedza={"katalog": str(wiki), "zrodla": "ZRODLA.md"}), tmp_path)
    wpis.katalogi()

    def wiedza(*arg, wejscie=""):
        monkeypatch.setattr(sys, "stdin", io.StringIO(wejscie))
        kod = so.polecenie_wiedzy(wpis, list(arg))
        return kod, capsys.readouterr().out

    kod, out = wiedza("przed-tura", wejscie="https://x.com/unslothai/status/2123873656069877899 inkling MoE na xtx?")
    assert kod == 0 and out.startswith("<memory-context>") and "`llm/inkling-2-mini` · Inkling 2 Mini" in out
    assert "nowy, wiersz w `ZRODLA.md`" in out
    assert "https://x.com/unslothai/status/2123873656069877899 (terminal " in (wiki / "ZRODLA.md").read_text()
    dziennik = wpis.skrzynka / "wiedza" / "przypomnienia.jsonl"
    ostatni = json.loads(dziennik.read_text().splitlines()[-1])
    assert ostatni["kanal"] == "terminal" and "llm/inkling-2-mini" in ostatni["notatki"]
    kod, out = wiedza("przed-tura", "--dopisek", wejscie="a ten? https://example.com/dopisek")
    assert kod == 0 and "example.com/dopisek: nowy" in out
    assert "example.com/dopisek" not in (wiki / "ZRODLA.md").read_text()
    kod, out = wiedza("po-turze", wejscie=json.dumps({
        "wiadomosci": ["https://x.com/unslothai/status/2123873656069877899 inkling MoE na xtx?",
                       "a ten? https://example.com/dopisek"], "odpowiedz": "Gotowe, zrobione."}))
    assert kod == 0 and len(json.loads(out)["linki"]["czeka"]) == 2
    z = (wiki / "ZRODLA.md").read_text()
    assert "https://example.com/dopisek (terminal " in z and z.count("bez analizy w wiki; odpowiedź ") == 2
    assert wiedza("po-turze", wejscie="nie json")[0] == 2


def test_polecenie_w_parserze():
    a, reszta = cli._parser().parse_known_args(["sesja", "op", "terminal", "--model", "opus"])
    assert (a.klucz, a.akcja, reszta, a.funkcja) == ("op", "terminal", ["--model", "opus"], so.polecenie_sesja)
    assert "sesja" in cli.Z_RESZTA


def test_mozg_sesji_w_turze(tmp_path, at, monkeypatch):
    """Wpis z `panel.wiedza` i `panel.tozsamosc`: blok <memory-context> przed pierwszym nagłówkiem wiadomości (panel go
    nie pokazuje), link z Telegrama w rejestrze przed turą, po turze wyciąg odpowiedzi w werdykcie, system.md złożony
    przed procesem omp; dopisek w trakcie tury nie pisze do rejestru."""
    from jarvo import mozg_sesji
    monkeypatch.setattr(mozg_sesji, "stan_wektorow_instalacji", lambda: tmp_path / "brak-uslugi")
    wiki = tmp_path / "wiki"
    (wiki / "llm").mkdir(parents=True)
    (wiki / "llm" / "inkling-2-mini.md").write_text("---\ntyp: llm\n---\n# Inkling 2 Mini\n\n**Inkling na XTX: 33,9 t/s, "
                                                    "limit to kernele MoE.**\n", encoding="utf-8")
    (wiki / "ZRODLA.md").write_text("# Rejestr\n\n## Powiązane\n- [[index]]\n", encoding="utf-8")
    toz = tmp_path / "toz"
    toz.mkdir()
    (toz / "SOUL.md").write_text("# Kernel\n")
    (toz / "ZASADY.md").write_text("# Zasady\n<!-- Jarvo:MAPA -->\n")
    (toz / "MAPA.md").write_text("## Kim jestem\n<!-- Jarvo:RDZEN -->\n- sesja omp\n<!-- /Jarvo:RDZEN -->\n")
    system = tmp_path / "system.md"
    wpis = om.wpis_z("gpu", surowy_wpis(tmp_path, omp_arg=["--append-system-prompt", str(system)],
                                        wiedza={"katalog": str(wiki), "zrodla": "ZRODLA.md"},
                                        tozsamosc={"soul": str(toz / "SOUL.md"), "zasady": str(toz / "ZASADY.md"),
                                                   "mapa": str(toz / "MAPA.md"), "plik": str(system)}), tmp_path)
    (tmp_path / "k" / "sesje").mkdir(parents=True)
    wpis.katalogi()
    telegramowa(wpis, "1.json", "https://x.com/unslothai/status/2123873656069877899 inkling MoE na xtx?")
    so.skrzynka(wpis, Telegram())
    (p,) = tury(at)
    m = p["message"]
    assert m.index("<memory-context>") < m.index("[Telegram · gpu") and "`llm/inkling-2-mini` · Inkling 2 Mini" in m
    assert "nowy, wiersz w `ZRODLA.md`" in m
    assert czytnik_omp_bloki(m) == ["https://x.com/unslothai/status/2123873656069877899 inkling MoE na xtx?"]
    assert system.read_text().startswith("# Kernel\n\n# Zasady\n### Kim jestem\n- sesja omp")
    z = (wiki / "ZRODLA.md").read_text()
    assert "## Linki od właściciela (wpisywane automatycznie)" in z and "bez analizy w wiki; odpowiedź " in z
    assert "Gotowe, zrobione." in z
    assert (wpis.skrzynka / "wiedza" / "przypomnienia.jsonl").exists()
    tekst, _ = so.dopisek(wpis, {"tekst": "https://example.com/nowy", "czas": "2026-11-22 12:00:00"})
    assert "example.com/nowy: nowy" in tekst and "example.com/nowy" not in (wiki / "ZRODLA.md").read_text()


def czytnik_omp_bloki(tekst):
    import importlib.util
    spec = importlib.util.spec_from_file_location("czytnik_omp_t", REPO / "hq" / "plugin" / "czytnik_omp.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return [b["tekst"] for b in mod.bloki_obwiedni(tekst)]
