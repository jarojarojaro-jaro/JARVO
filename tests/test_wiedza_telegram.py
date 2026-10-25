"""Telegram natywnie (docs/NATYWNIE.md H11, I36, K08) na atrapie Bot API, bez prawdziwego bota: `jarvo telegram
ustaw` (token i lista dozwolonych do <dane>/.env bez wypisywania, trasa właściciela do <dane>/jarvo/konfig/jarvo.env,
ID z pierwszej wiadomości do bota, wdrożenie floty i restart bramy), `jarvo telegram test` (próbna wiadomość, po
udanej rutyny Jarva się włączają, ręczne wyłączenie zostaje), `status` bez wartości i ślad 409 w logach bramy.

Atrapa działa też sama, do prób na żywo (jarvo telegram … z JARVO_TELEGRAM_API=http://127.0.0.1:<port>):
    python tests/test_wiedza_telegram.py --port 19194 [--dziennik plik.jsonl] [--konflikt]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

TOKEN = "7000001:AAH" + "x" * 32
BOT = {"id": 7000001, "is_bot": True, "first_name": "Jarvo próba", "username": "jarvo_proba_bot"}


# ---------------------------------------------------------------- atrapa Bot API

class Obsluga(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_a) -> None:
        pass

    def _odpowiedz(self, kod: int, dane: dict) -> None:
        tresc = json.dumps(dane, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(tresc)))
        self.end_headers()
        self.wfile.write(tresc)

    def _parametry(self) -> dict:
        dl = int(self.headers.get("Content-Length") or 0)
        surowe = self.rfile.read(dl) if dl else b""
        typ = (self.headers.get("Content-Type") or "").lower()
        if "json" in typ and surowe:
            return json.loads(surowe.decode("utf-8"))
        if surowe:
            return {k: v[-1] for k, v in urllib.parse.parse_qs(surowe.decode("utf-8")).items()}
        return {k: v[-1] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).items()}

    def do_GET(self) -> None:
        self.do_POST()

    def do_POST(self) -> None:
        s: Atrapa = self.server                          # type: ignore[assignment]
        czesci = urllib.parse.urlsplit(self.path).path.strip("/").split("/")
        if len(czesci) != 2 or not czesci[0].startswith("bot"):
            return self._odpowiedz(404, {"ok": False, "error_code": 404, "description": "Not Found"})
        token, metoda = czesci[0][3:], czesci[1]
        p = self._parametry()
        s.zapisz({"metoda": metoda, "parametry": p})
        if token not in s.tokeny:
            return self._odpowiedz(401, {"ok": False, "error_code": 401, "description": "Unauthorized"})
        if metoda == "getMe":
            return self._odpowiedz(200, {"ok": True, "result": BOT})
        if metoda == "getUpdates":
            if s.konflikt:
                return self._odpowiedz(409, {"ok": False, "error_code": 409, "description": "Conflict: terminated by "
                                             "other getUpdates request; make sure that only one bot instance is running"})
            offset = int(p.get("offset") or 0)
            koniec = time.monotonic() + min(float(p.get("timeout") or 0), s.maks_czekania)
            while True:
                with s.zamek:
                    gotowe = [a for a in s.aktualizacje if a["update_id"] >= offset]
                    if offset:
                        s.aktualizacje = [a for a in s.aktualizacje if a["update_id"] >= offset]
                if gotowe or time.monotonic() >= koniec:
                    return self._odpowiedz(200, {"ok": True, "result": gotowe})
                time.sleep(0.05)
        if metoda == "sendMessage":
            czat = str(p.get("chat_id"))
            if s.znane_czaty is not None and czat not in s.znane_czaty:
                return self._odpowiedz(400, {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"})
            with s.zamek:
                s.wyslane.append({"chat_id": czat, "text": p.get("text")})
                n = len(s.wyslane)
            return self._odpowiedz(200, {"ok": True, "result": {"message_id": n, "date": int(time.time()),
                                                                "chat": {"id": int(czat), "type": "private"},
                                                                "text": p.get("text")}})
        return self._odpowiedz(200, {"ok": True, "result": True})     # setMyCommands, deleteWebhook, …


class Atrapa(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, port: int = 0, dziennik: str | None = None):
        super().__init__(("127.0.0.1", port), Obsluga)
        self.tokeny = {TOKEN}
        self.konflikt = False
        self.znane_czaty: set[str] | None = None
        self.aktualizacje: list[dict] = []
        self.wyslane: list[dict] = []
        self.wywolania: list[dict] = []
        self.maks_czekania = 1.0
        self.zamek = threading.Lock()
        self.dziennik = dziennik

    @property
    def adres(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"

    def zapisz(self, wpis: dict) -> None:
        with self.zamek:
            self.wywolania.append(wpis)
        if self.dziennik:
            with open(self.dziennik, "a", encoding="utf-8") as f:
                f.write(json.dumps({**wpis, "czas": time.time()}, ensure_ascii=False) + "\n")

    def wiadomosc_od(self, ident: int, imie: str = "Michał") -> None:
        with self.zamek:
            self.aktualizacje.append({"update_id": 100 + len(self.aktualizacje), "message": {
                "message_id": 1, "date": int(time.time()), "text": "/start", "chat": {"id": ident, "type": "private"},
                "from": {"id": ident, "is_bot": False, "first_name": imie, "username": "michal"}}})


def main_atrapy() -> None:
    ap = argparse.ArgumentParser(description="Atrapa Bot API Telegrama (tylko testy i próby)")
    ap.add_argument("--port", type=int, default=19194)
    ap.add_argument("--dziennik", default=None)
    ap.add_argument("--konflikt", action="store_true", help="getUpdates zwraca 409 (dwie bramy na jednym tokenie)")
    ap.add_argument("--czekaj", type=float, default=25.0, help="najdłuższe czekanie getUpdates (long polling)")
    a = ap.parse_args()
    s = Atrapa(a.port, a.dziennik)
    s.konflikt, s.maks_czekania = a.konflikt, a.czekaj
    print(f"atrapa Bot API: {s.adres} (token próby: {TOKEN})", flush=True)
    s.serve_forever()


if __name__ == "__main__":
    main_atrapy()
    sys.exit(0)


# ---------------------------------------------------------------- testy

import pytest  # noqa: E402

from jarvo import instalator, sciezki, srodowisko  # noqa: E402
from jarvo import wiedza_cli as wc  # noqa: E402

RUTYNY = ["jarvo-patrol", "jarvo-daily-brief", "jarvo-weekly-review", "jarvo-knowledge-freshness"]


@pytest.fixture
def api(monkeypatch):
    s = Atrapa()
    watek = threading.Thread(target=s.serve_forever, daemon=True)
    watek.start()
    monkeypatch.setenv("JARVO_TELEGRAM_API", s.adres)
    yield s
    s.shutdown()
    s.server_close()


class Nadzorca:
    def __init__(self, dziala: bool):
        self.dziala, self.restarty = dziala, []

    def polacz(self, _u):
        if not self.dziala:
            raise RuntimeError("Nadzorca Jarva nie działa")
        return self

    def status(self):
        return {"nadzorca": {"pid": 1}, "uslugi": {"brama": {"stan": "dziala", "pid": 2}}}

    def restart(self, nazwa):
        self.restarty.append(nazwa)


class Flota:
    """Atrapa jarvo/flota.py: wdrożenie zapisuje trasę właściciela w rutynach (jak build z OWNER_DELIVER)."""

    def __init__(self, u):
        self.u, self.wywolania, self.potwierdzone = u, 0, []

    def zainstaluj_flote(self, u, env, log=print):
        self.wywolania += 1
        wlasciciel = wc.czytaj_env(wc.konfig(u) / "jarvo.env")["TELEGRAM_OWNER_ID"]
        _jobs(u, deliver=f"telegram:{wlasciciel}")
        return {"restart_bramy": True, "restart_panelu": True, "odcisk_panelu": "0123456789abcdef"}

    def uslugi_do_restartu(self, wynik):
        return [n for n, pole in (("brama", "restart_bramy"), ("panel", "restart_panelu")) if wynik.get(pole)]

    def potwierdz_restart_panelu(self, u, odcisk):
        self.potwierdzone.append(odcisk)


def _jobs(u, *, wlaczone=False, deliver="local"):
    jobs = [{"id": i, "name": i, "enabled": wlaczone, "state": "scheduled" if wlaczone else "paused",
             "paused_at": None if wlaczone else "2026-10-25T02:00:00", "deliver": deliver, "schedule_display": "every 30m"}
            for i in RUTYNY]
    p = wc.profil(u) / "cron" / "jobs.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"jobs": jobs}), encoding="utf-8")


@pytest.fixture
def inst(tmp_path, monkeypatch):
    root = tmp_path / "Michał Żółć" / "Jarvo"
    root.mkdir(parents=True)
    try:
        u = sciezki.uklad({"JARVO_ROOT": str(root)})
    except sciezki.BladUkladu:
        root = tmp_path / "Jarvo test"
        root.mkdir()
        u = sciezki.uklad({"JARVO_ROOT": str(root)})
    for k in u.katalogi():
        k.mkdir(parents=True, exist_ok=True)
    (u.program / "current.json").write_text(json.dumps({"app": str(REPO), "hermes": str(tmp_path / "hermes")}),
                                            encoding="utf-8")
    (tmp_path / "hermes").mkdir()
    monkeypatch.setattr(srodowisko, "hermes_python", lambda _c: Path(sys.executable))
    wc.profil(u).mkdir(parents=True)
    nadzorca, flota = Nadzorca(dziala=False), Flota(u)
    moduly = {"nadzorca": nadzorca, "flota": flota}
    ot = instalator.Otoczenie(env={"PATH": os.environ.get("PATH", ""), "JARVO_ROOT": str(root)},
                              modul=lambda n: moduly.get(n) or instalator.modul(n))
    return u, ot, nadzorca, flota


def _a(**kw):
    domyslne = {"wlasciciel": None, "grupa": None, "token_ze_stdin": False, "bez_wdrozenia": False,
                "bez_sprawdzenia": False, "bez_rutyn": False, "json": False, "sprawdz": False}
    return argparse.Namespace(**{**domyslne, **kw})


def _hermes(wolane):
    def f(argv, env, cwd):
        wolane.append([str(x) for x in argv])
        return subprocess.CompletedProcess(argv, 0, "ok", "")
    return f


# -- Bot API

def test_api_telegrama_ok_bledy_i_brak_sieci(api):
    assert wc.api_telegrama(TOKEN, "getMe")["username"] == "jarvo_proba_bot"
    zly = "7000001:" + "z" * 35
    with pytest.raises(wc.BladTelegrama) as e:
        wc.api_telegrama(zly, "getMe")
    assert e.value.kod == 401 and "z" * 35 not in str(e.value) and "BotFather" in wc.rada_telegrama(e.value)
    api.konflikt = True
    with pytest.raises(wc.BladTelegrama) as e:
        wc.api_telegrama(TOKEN, "getUpdates", {"timeout": 0})
    assert e.value.kod == 409 and "inny program" in wc.rada_telegrama(e.value)
    with pytest.raises(wc.BladTelegrama) as e:
        wc.api_telegrama(TOKEN, "getMe", baza="http://127.0.0.1:9", czas=2)          # nikt nie słucha
    assert e.value.kod == 0 and TOKEN not in str(e.value)


def test_zapisz_env_scala_bez_wartosci(tmp_path):
    """.env z BOM i CRLF (Notatnik): inne linie i komentarze zostają, duplikat klucza znika, zapis z LF; wynik to same
    nazwy kluczy (wartości nie wracają do wywołującego, więc nie trafią na ekran)."""
    p = tmp_path / ".env"
    p.write_bytes("﻿# bot\r\nTELEGRAM_BOT_TOKEN=stary\r\nINNY=1\r\nTELEGRAM_BOT_TOKEN=duplikat\r\n".encode("utf-8"))
    assert wc.zapisz_env(p, {"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_ALLOWED_USERS": "123"}) == \
        ["TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USERS"]
    tekst = p.read_bytes().decode("utf-8")
    assert b"\r" not in p.read_bytes() and tekst.count("TELEGRAM_BOT_TOKEN=") == 1 and "# bot" in tekst and "INNY=1" in tekst
    assert wc.czytaj_env(p) == {"TELEGRAM_BOT_TOKEN": TOKEN, "INNY": "1", "TELEGRAM_ALLOWED_USERS": "123"}
    assert wc.zapisz_env(p, {"TELEGRAM_BOT_TOKEN": TOKEN}) == []                        # bez zmian: bez zapisu


# -- ustaw

def test_ustaw_bez_terminala_token_z_wejscia(inst, api, monkeypatch, capsys):
    """Token z wejścia (nie z argumentów: historia powłoki), ID właściciela z opcji, bez wdrożenia. Token nie pojawia się
    w wyjściu; drugie ustawienie bez zmian nic nie robi."""
    u, ot, nadzorca, flota = inst
    monkeypatch.setattr(sys, "stdin", io.StringIO(TOKEN + "\n"))
    assert wc.polecenie_telegram_ustaw(u, _a(token_ze_stdin=True, wlasciciel="123456789", bez_wdrozenia=True), [], ot,
                                       interaktywnie=False) == 0
    wyj = capsys.readouterr()
    assert TOKEN not in wyj.out + wyj.err and "@jarvo_proba_bot" in wyj.out and "jarvo telegram test" in wyj.out
    env = wc.czytaj_env(u.dane / ".env")
    assert env["TELEGRAM_BOT_TOKEN"] == TOKEN and env["TELEGRAM_ALLOWED_USERS"] == "123456789"
    assert env["TELEGRAM_HOME_CHANNEL"] == "123456789"
    assert wc.czytaj_env(wc.konfig(u) / "jarvo.env") == {"TELEGRAM_OWNER_ID": "123456789"}
    assert flota.wywolania == 0 and nadzorca.restarty == []
    if os.name != "nt":
        assert (u.dane / ".env").stat().st_mode & 0o777 == 0o600
    # drugi raz bez terminala: zapisany token zostaje, nic się nie zmienia
    assert wc.polecenie_telegram_ustaw(u, _a(wlasciciel="123456789", bez_wdrozenia=True), [], ot, interaktywnie=False) == 0
    assert "Nic się nie zmieniło" in capsys.readouterr().out


def test_ustaw_odrzuca_zly_token_i_nic_nie_zapisuje(inst, api, monkeypatch, capsys):
    u, ot, _n, _f = inst
    monkeypatch.setattr(sys, "stdin", io.StringIO("to-nie-token\n"))
    assert wc.polecenie_telegram_ustaw(u, _a(token_ze_stdin=True, wlasciciel="1234"), [], ot, interaktywnie=False) == 2
    monkeypatch.setattr(sys, "stdin", io.StringIO("7000001:" + "q" * 35 + "\n"))       # nieznany Telegramowi
    assert wc.polecenie_telegram_ustaw(u, _a(token_ze_stdin=True, wlasciciel="1234"), [], ot, interaktywnie=False) == 1
    wyj = capsys.readouterr()
    assert "Nic nie zmieniłem" in wyj.err and "q" * 35 not in wyj.out + wyj.err
    assert not (u.dane / ".env").exists() and not (wc.konfig(u) / "jarvo.env").exists()
    assert wc.polecenie_telegram_ustaw(u, _a(wlasciciel="1234"), [], ot, interaktywnie=False) == 2   # bez wejścia i zapisu


def test_ustaw_id_z_pierwszej_wiadomosci_do_bota(inst, api, capsys):
    """Interaktywnie bez --wlasciciel: właściciel pisze do bota, getUpdates daje jego ID, po potwierdzeniu wiadomość jest
    potwierdzona (offset), żeby brama jej potem nie przetworzyła."""
    u, ot, _n, _f = inst
    api.wiadomosc_od(555000111)
    pytania = []
    assert wc.polecenie_telegram_ustaw(u, _a(bez_wdrozenia=True), [], ot, interaktywnie=True,
                                       pytaj=lambda t: pytania.append(t) or "",
                                       pytaj_ukryte=lambda t: TOKEN) == 0
    assert "ID 555000111" in pytania[0] and "Michał" in pytania[0]
    assert wc.czytaj_env(wc.konfig(u) / "jarvo.env")["TELEGRAM_OWNER_ID"] == "555000111"
    potwierdzenia = [w["parametry"].get("offset") for w in api.wywolania if w["metoda"] == "getUpdates"]
    assert 101 in [int(x) for x in potwierdzenia if x is not None]
    assert TOKEN not in capsys.readouterr().out


def test_ustaw_konflikt_409_przy_wykrywaniu(inst, api, capsys):
    """Bota czyta już inny program (stara flota): wykrywanie mówi o 409, a ID można podać ręcznie."""
    u, ot, _n, _f = inst
    api.konflikt = True
    assert wc.polecenie_telegram_ustaw(u, _a(bez_wdrozenia=True), [], ot, interaktywnie=True,
                                       pytaj=lambda t: "987654321", pytaj_ukryte=lambda t: TOKEN) == 0
    out = capsys.readouterr().out
    assert "inny program" in out and wc.czytaj_env(wc.konfig(u) / "jarvo.env")["TELEGRAM_OWNER_ID"] == "987654321"


def test_ustaw_wdraza_flote_i_restartuje_uslugi(inst, api, monkeypatch, capsys):
    """Z flotą: wdrożenie (trasa w configu bramy, rutyny do właściciela), restart usług przez działającego nadzorcę
    i potwierdzenie odcisku panelu; źródłowe host.env (merge_env przy wdrożeniu) dostaje te same wartości."""
    u, ot, nadzorca, flota = inst
    nadzorca.dziala = True
    (wc.profil(u) / "distribution.yaml").write_text("name: jarvo\n", encoding="utf-8")
    _jobs(u)
    wc.konfig(u).mkdir(parents=True, exist_ok=True)
    (wc.konfig(u) / "host.env").write_text("TELEGRAM_BOT_TOKEN=\nOPENROUTER_API_KEY=\n", encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", io.StringIO(TOKEN + "\n"))
    assert wc.polecenie_telegram_ustaw(u, _a(token_ze_stdin=True, wlasciciel="123456789", grupa="-1001234567890"), [],
                                       ot, interaktywnie=False) == 0
    assert flota.wywolania == 1 and nadzorca.restarty == ["brama", "panel"] and flota.potwierdzone == ["0123456789abcdef"]
    assert wc.czytaj_env(wc.konfig(u) / "host.env")["TELEGRAM_BOT_TOKEN"] == TOKEN
    assert wc.czytaj_env(wc.konfig(u) / "jarvo.env")["TELEGRAM_HQ_CHAT_ID"] == "-1001234567890"
    assert all(r["deliver"] == "telegram:123456789" for r in wc.stan_rutyn(u)["lista"])
    assert "Flota wdrożona; restart: brama, panel" in capsys.readouterr().out
    monkeypatch.setattr(sys, "stdin", io.StringIO(TOKEN + "\n"))                     # nic nowego: bez wdrożenia
    assert wc.polecenie_telegram_ustaw(u, _a(token_ze_stdin=True, wlasciciel="123456789"), [], ot, interaktywnie=False) == 0
    assert flota.wywolania == 1


# -- test i rutyny (I36)

def _ustawiony(u, wlasciciel="123456789"):
    wc.zapisz_env(u.dane / ".env", {"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_ALLOWED_USERS": wlasciciel})
    wc.zapisz_env(wc.konfig(u) / "jarvo.env", {"TELEGRAM_OWNER_ID": wlasciciel})


def test_proba_wysyla_i_wlacza_rutyny(inst, api, capsys):
    u, ot, _n, _f = inst
    _ustawiony(u)
    _jobs(u, deliver="telegram:123456789")
    wolane = []
    assert wc.polecenie_telegram_test(u, _a(), [], ot, uruchom=_hermes(wolane)) == 0
    assert api.wyslane and api.wyslane[0]["chat_id"] == "123456789" and "próbna wiadomość" in api.wyslane[0]["text"]
    assert sorted(a[a.index("cron") + 2] for a in wolane) == sorted(RUTYNY)
    assert {a[a.index("cron") + 1] for a in wolane} == {"resume"}
    zapis = json.loads((wc.stan_skarbca(u) / "rutyny.json").read_text(encoding="utf-8"))
    assert zapis["wlaczone"] is True and zapis["reczne"] is False and zapis["powod"] == "próbna wiadomość Telegram"
    stan = json.loads((wc.stan_skarbca(u) / "telegram.json").read_text(encoding="utf-8"))
    assert stan["bot"] == "@jarvo_proba_bot" and stan["do"] == "123456789" and TOKEN not in json.dumps(stan)
    out = capsys.readouterr().out
    assert "Rutyny włączone." in out and TOKEN not in out


def test_proba_szanuje_reczne_wylaczenie_i_bez_rutyn(inst, api, capsys):
    u, ot, _n, _f = inst
    _ustawiony(u)
    _jobs(u)
    wolane = []
    assert wc.polecenie_telegram_test(u, _a(bez_rutyn=True), [], ot, uruchom=_hermes(wolane)) == 0 and not wolane
    przenosne_zapis = {"wlaczone": False, "reczne": True, "powod": "jarvo rutyny off"}
    (wc.stan_skarbca(u)).mkdir(parents=True, exist_ok=True)
    (wc.stan_skarbca(u) / "rutyny.json").write_text(json.dumps(przenosne_zapis), encoding="utf-8")
    assert wc.polecenie_telegram_test(u, _a(), [], ot, uruchom=_hermes(wolane)) == 0 and not wolane
    assert "wyłączyłeś je sam" in capsys.readouterr().out


def test_proba_bez_rozmowy_z_botem(inst, api, capsys):
    """Bot nie zacznie rozmowy sam (400 chat not found): rada „napisz /start”, rutyny zostają wstrzymane."""
    u, ot, _n, _f = inst
    _ustawiony(u)
    _jobs(u)
    api.znane_czaty = set()
    wolane = []
    assert wc.polecenie_telegram_test(u, _a(), [], ot, uruchom=_hermes(wolane)) == 1
    assert "/start" in capsys.readouterr().err and not wolane


# -- status i 409

def test_konflikt_409_w_logu_bramy(inst):
    """Ślad 409 z adaptera Telegrama Hermesa w logu bramy z ostatniej doby: blad w doctorze z radą; stary ślad
    (sprzed 3 dni) już nie."""
    u, ot, _n, _f = inst
    teraz = time.time()
    swiezy = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(teraz - 600))
    stary = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(teraz - 3 * 86400))
    u.logi.mkdir(parents=True, exist_ok=True)
    (u.logi / "brama.log").write_text(
        f"{stary} WARNING [Telegram] Telegram polling conflict (1/5) — previous session still held open\n"
        f"{swiezy} WARNING gateway.platforms.telegram: [Telegram] Telegram polling conflict (2/5) — previous session "
        f"still held open on Telegram's servers. Error: Conflict: terminated by other getUpdates request {TOKEN}\n",
        encoding="utf-8")
    k = wc.konflikt_409(u, teraz)
    assert k and k["kiedy"] == swiezy and TOKEN not in k["linia"] and k["plik"].endswith("brama.log")
    wyniki = wc.sprawdz_telegram(u, ot, teraz)
    blad = next(x for x in wyniki if x["nazwa"] == "Telegram: jedna brama na token")
    assert blad["stan"] == "blad" and "docker stop jarvo-hermes" in blad["rada"]
    (u.logi / "brama.log").write_text(f"{stary} WARNING Telegram polling conflict (1/5)\n"     # ślad wyjątku bez czasu
                                      "telegram.error.Conflict: Conflict: terminated by other getUpdates request\n",
                                      encoding="utf-8")
    assert wc.konflikt_409(u, teraz) is None                                     # dostaje czas linii przed nim (stary)
    pozniej = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(teraz - 60))
    (u.logi / "brama.log").write_text(f"{swiezy} WARNING [Telegram] Telegram polling conflict (5/5)\n"
                                      f"{pozniej} WARNING [Telegram] Connected to Telegram (polling mode)\n",
                                      encoding="utf-8")
    assert wc.konflikt_409(u, teraz) is None                                     # brama połączyła się od nowa: po sprawie


def test_status_bez_wartosci(inst, api, capsys):
    u, ot, _n, _f = inst
    assert wc.sprawdz_telegram(u, ot)[0]["opis"] == "bot nie jest ustawiony"
    _ustawiony(u)
    _jobs(u)
    assert wc.polecenie_telegram_status(u, _a(json=True, sprawdz=True), [], ot) == 0
    out = capsys.readouterr().out
    d = json.loads(out)
    assert d["token"] is True and d["wlasciciel"] == "123456789" and d["bot"] == "@jarvo_proba_bot" and TOKEN not in out
    assert wc.sprawdz_telegram(u, ot)[0]["stan"] == "ok"
    wc.zapisz_env(wc.konfig(u) / "jarvo.env", {"TELEGRAM_OWNER_ID": ""})
    assert "brak trasy DM" in wc.sprawdz_telegram(u, ot)[0]["opis"]
