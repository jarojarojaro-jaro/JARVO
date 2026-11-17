"""jarvo/sesje_omp.py z atrapą `omp`: tura JSONL, błąd, SIGTERM, trzymana dzierżawa = brak tury, partia,
powiadomienie o zajętej sesji, terminal z blokadą, polecenie `jarvo sesja`."""
from __future__ import annotations

import json
import os
import threading
import time

import pytest

import atrapa_omp

pytestmark = pytest.mark.skipif(os.name == "nt", reason="sesje omp z blokadą: Linux i macOS")
fcntl = pytest.importorskip("fcntl")

from jarvo import cli, sesje_omp as so  # noqa: E402

om = so.rdzen


@pytest.fixture
def at(tmp_path, monkeypatch):
    k = tmp_path / "atrapa"
    monkeypatch.setenv("ATRAPA_OMP", str(k))
    monkeypatch.setenv("JARVO_OMP", str(atrapa_omp.zrob(k)))
    om._dzierzawy.clear()
    return k


@pytest.fixture
def w(tmp_path, at):
    surowy = {"nazwa": "Kernel", "skrzynka": str(tmp_path / "k" / "skrzynka"), "czat": "-1001", "watek": "7",
              "panel": {"zaplecze": "omp", "sesje": str(tmp_path / "k" / "sesje"), "sesja": "01a13b13-14db",
                        "cwd": str(tmp_path), "omp_arg": ["--no-context-files"], "potwierdzenia": True}}
    wpis = om.wpis_z("gpu", surowy, tmp_path)
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


def tury(at):
    return [a for a in wywolania(at) if "-p" in a]


def telegramowa(w, nazwa, tekst="z telefonu"):
    om.zapisz_atomowo(w.nowe / nazwa, {"dopisek": "gpu", "tekst": tekst, "czas": "2026-11-17 12:00:00",
                                       "chat_id": "-1001", "watek": "7", "media": []})


def test_tura_z_panelu(w, at):
    om.wyslij(w, "sprawdź GPU", "k1", media=[str(w.nowe / "a.png")])
    tg = Telegram()
    assert so.skrzynka(w, tg) == 0
    (argv,) = tury(at)
    i = argv.index("--session-dir")
    assert argv[i + 1] == str(w.sesje) and argv[argv.index("--resume") + 1] == w.sesja
    assert argv[argv.index("--mode") + 1] == "json" and "--no-context-files" in argv and argv[-1] == f"@{w.nowe}/a.png"
    tresc = argv[argv.index("--mode") + 2]
    assert "[Panel · gpu · " in tresc and "sprawdź GPU" in tresc and "[[czeka-na-tak]]" in tresc
    d = json.loads((w.zrobione / "panel-k1.json").read_text())
    assert d["odpowiedz"] == "Gotowe, zrobione." and om.przebieg(w, "k1")["stan"] == "gotowe"
    plik = w.tura / f"{d['tura']}.jsonl"
    zdarzenia, _ = om.ogon(w, d["tura"])
    assert [z["typ"] for z in zdarzenia] == ["narzedzie", "delta", "delta", "koniec"]
    assert zdarzenia[0] == {"typ": "narzedzie", "nazwa": "bash", "intencja": "Sprawdzam GPU"}
    assert zdarzenia[-1]["ok"] is True and "SEKRET" not in plik.read_text()
    assert tg.wyslane == [("🖥 Kernel\n\nGotowe, zrobione.", "-1001", "7")]
    assert om.czytaj_stan(w)["tura"] is None and om.stan(w)["stan"] == "wolny"


def test_bez_lustra_i_z_telegrama(w, at):
    om.wyslij(w, "cicho", "k1", lustro=False)
    tg = Telegram()
    so.skrzynka(w, tg)
    assert tg.wyslane == []
    telegramowa(w, "1.json")
    so.skrzynka(w, tg)
    assert tg.wyslane == [("Kernel\n\nGotowe, zrobione.", "-1001", "7")]
    assert "[Telegram · gpu" in tury(at)[-1][tury(at)[-1].index("--mode") + 2]


def test_blad_tury(w, at):
    (at / "tryb").write_text("blad")
    om.wyslij(w, "x", "k1")
    tg = Telegram()
    so.skrzynka(w, tg)
    p = om.przebieg(w, "k1")
    assert p["stan"] == "blad" and "model niedostępny" in p["blad"]
    assert tg.wyslane[0][0].startswith("⚠️ Kernel: tura nie wyszła")


def test_partia_po_szesc(w, at):
    for i in range(8):
        telegramowa(w, f"{i}.json", f"wiadomość {i}")
    so.skrzynka(w, Telegram())
    t = tury(at)
    assert len(t) == 2
    assert "wiadomość 6/6" in t[0][t[0].index("--mode") + 2] and "wiadomość 2/2" in t[1][t[1].index("--mode") + 2]
    assert len(list(w.zrobione.glob("*.json"))) == 8


def test_trzymana_dzierzawa_bez_tury(w, at):
    (at / "held.json").write_text(json.dumps([w.sesja]))
    om.wyslij(w, "x", "k1")
    tg = Telegram()
    so.skrzynka(w, tg)
    assert tury(at) == [] and (w.nowe / "panel-k1.json").exists() and tg.wyslane == []
    stary = time.time() - 300
    os.utime(w.nowe / "panel-k1.json", (stary, stary))
    so.skrzynka(w, tg)
    so.skrzynka(w, tg)
    assert len(tg.wyslane) == 1 and "1 wiadomość(i) czeka" in tg.wyslane[0][0]
    (at / "held.json").write_text("[]")
    so.skrzynka(w, tg)
    assert len(tury(at)) == 1 and om.czytaj_stan(w)["powiadomiono"] is None


def test_blokada_terminala_bez_tury(w, at):
    om.wyslij(w, "x", "k1")
    with w.blokada.open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        so.skrzynka(w, Telegram())
    assert tury(at) == [] and om.przebieg(w, "k1")["stan"] == "kolejka"


def test_sigterm_zatrzymuje_ture(w, at):
    (at / "tryb").write_text("spi")
    om.wyslij(w, "długie", "k1")
    watek = threading.Thread(target=so.skrzynka, args=(w, Telegram()))
    watek.start()
    for _ in range(100):
        if om.stan(w)["stan"] == "pracuje" and (at / "spi").exists():
            break
        time.sleep(0.1)
    assert om.przebieg(w, "k1")["stan"] == "pracuje"
    assert om.zatrzymaj(w) is True
    watek.join(20)
    p = om.przebieg(w, "k1")
    assert p["stan"] == "blad" and "zatrzymana" in p["blad"]
    zdarzenia, _ = om.ogon(w, p["tura"])
    assert zdarzenia[-1]["typ"] == "koniec" and zdarzenia[-1]["ok"] is False


def test_terminal(w, at):
    po = []
    om.wyslij(w, "x", "k1")
    assert so.terminal(w, ["--model", "opus"], po_wyjsciu=lambda *a: po.append(a)) == 0
    argv = wywolania(at)[-1]
    assert argv[:4] == ["--session-dir", str(w.sesje), "--resume", w.sesja] and argv[-2:] == ["--model", "opus"]
    assert len(po) == 1 and om.czytaj_stan(w)["terminal"] is None and not om.blokada_zajeta(w)
    (at / "held.json").write_text(json.dumps([w.sesja]))
    om._dzierzawy.clear()
    n = len(wywolania(at))
    assert so.terminal(w, [], po_wyjsciu=lambda *a: None) == 1
    assert all(a[:2] == ["session", "lease"] for a in wywolania(at)[n:])


def test_polecenie_w_parserze():
    a, reszta = cli._parser().parse_known_args(["sesja", "op", "terminal", "--model", "opus"])
    assert (a.klucz, a.akcja, reszta, a.funkcja) == ("op", "terminal", ["--model", "opus"], so.polecenie_sesja)
    assert "sesja" in cli.Z_RESZTA
