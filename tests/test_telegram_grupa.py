"""Grupa „Jarvo HQ” z tematami (14.11): `jarvo telegram tematy` (grupa z wiadomości właściciela, zakładanie
brakujących wątków createForumTopic, ponowne użycie znanych, TELEGRAM_* do jarvo.env, wątek Kernela do sesje.json,
wdrożenie tras), rady po polsku przy błędach Telegrama i `jarvo telegram wyslij --watek` (atrapa Bot API)."""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from jarvo import instalator, sciezki, srodowisko  # noqa: E402
from jarvo import wiedza_cli as wc  # noqa: E402

TOKEN = "7000001:AAH" + "x" * 32
GRUPA = "-1001234567890"
FLOTA = {"orchestrator": "jarvo", "agents": [
    {"name": "jarvo", "short": "Jarvo", "telegram_topic": "general"},
    {"name": "jarvo-sherlock", "short": "Sherlock", "telegram_topic": "sherlock"},
    {"name": "jarvo-jarodev", "short": "Jarodev", "telegram_topic": "jarodev"},
    {"name": "jarvo-bez-watku", "short": "Cichy", "telegram_topic": ""}]}


class BotAPI:
    """Atrapa api_telegrama: zapisuje wołania, zakłada tematy od numeru 101, `bledy` = metoda → BladTelegrama."""

    def __init__(self):
        self.wolania: list[tuple[str, dict]] = []
        self.bledy: dict[str, wc.BladTelegrama] = {}
        self.usuniete: set[int] = set()
        self.forum, self.status = True, "administrator"
        self.nastepny = 101

    def __call__(self, token, metoda, dane=None, **_kw):
        assert token == TOKEN
        dane = dict(dane or {})
        self.wolania.append((metoda, dane))
        if metoda in self.bledy:
            raise self.bledy[metoda]
        if metoda == "getChat":
            return {"id": int(dane["chat_id"]), "title": "Jarvo HQ", "type": "supergroup", "is_forum": self.forum}
        if metoda == "getMe":
            return {"id": 7000001, "is_bot": True, "username": "jarvo_proba_bot"}
        if metoda == "getChatMember":
            return {"status": self.status}
        if metoda == "sendChatAction":
            if dane.get("message_thread_id") in self.usuniete:
                raise wc.BladTelegrama(400, "Bad Request: message thread not found")
            return True
        if metoda == "createForumTopic":
            self.nastepny += 1
            return {"message_thread_id": self.nastepny - 1, "name": dane["name"]}
        if metoda == "sendMessage":
            return {"message_id": 1}
        raise AssertionError(metoda)

    def metody(self, nazwa):
        return [d for m, d in self.wolania if m == nazwa]


class Flota:
    def __init__(self):
        self.wywolania = 0

    def zainstaluj_flote(self, u, env, log=print):
        self.wywolania += 1
        return {"restart_bramy": True}

    def uslugi_do_restartu(self, wynik):
        return ["brama"] if wynik.get("restart_bramy") else []


@pytest.fixture
def inst(tmp_path, monkeypatch):
    root = tmp_path / "Jarvo"
    root.mkdir()
    u = sciezki.uklad({"JARVO_ROOT": str(root)})
    for k in u.katalogi():
        k.mkdir(parents=True, exist_ok=True)
    (u.program / "current.json").write_text(json.dumps({"app": str(REPO)}), encoding="utf-8")
    (u.build / "wiedza").mkdir(parents=True, exist_ok=True)
    (u.build / "wiedza" / "fleet.json").write_text(json.dumps(FLOTA), encoding="utf-8")
    wc.zapisz_env(u.dane / ".env", {"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_ALLOWED_USERS": "123456789"})
    wc.zapisz_env(wc.konfig(u) / "jarvo.env", {"TELEGRAM_OWNER_ID": "123456789"})
    skrzynka = tmp_path / "kernel" / "skrzynka"
    (wc.konfig(u) / "sesje.json").write_text(json.dumps({
        "gpu": {"nazwa": "Kernel", "skrzynka": str(skrzynka)},
        "dev": {"nazwa": "Jarodev", "profil": "jarvo-jarodev"}}), encoding="utf-8")
    api = BotAPI()
    monkeypatch.setattr(wc, "api_telegrama", api)
    flota = Flota()
    monkeypatch.setattr(instalator, "stan_serwisu", lambda _u, _ot: (None, ""))
    monkeypatch.setattr(srodowisko, "hermes_python", lambda _c: Path(sys.executable))
    ot = instalator.Otoczenie(env={"PATH": os.environ.get("PATH", ""), "JARVO_ROOT": str(root)},
                              modul=lambda n: flota if n == "flota" else instalator.modul(n))
    return u, ot, api, flota


def _a(**kw):
    return argparse.Namespace(**{"grupa": None, "bez_wdrozenia": False, "czat": None, "watek": None, **kw})


def _grupy(u, grupy):
    p = wc.stan_skarbca(u) / wc.PLIK_GRUP
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"grupy": grupy}), encoding="utf-8")


def test_tematy_zaklada_brakujace_i_zapisuje_trasy(inst, capsys):
    u, ot, api, flota = inst
    (wc.profil(u) / "distribution.yaml").parent.mkdir(parents=True, exist_ok=True)
    (wc.profil(u) / "distribution.yaml").write_text("name: jarvo\n", encoding="utf-8")
    # właściciel napisał „start” w grupie i w wątku „Sherlock”, który sam założył (wtyczka jarvo-sesje)
    _grupy(u, {"-4001": {"nazwa": "stara grupa", "forum": False, "watki": {}},
               GRUPA: {"nazwa": "Jarvo HQ", "forum": True, "watki": {"1": {"nazwa": "General"},
                                                                    "55": {"nazwa": "🔎 Sherlock"}}}})
    assert wc.polecenie_telegram_tematy(u, _a(), [], ot) == 0
    zalozone = api.metody("createForumTopic")
    assert [d["name"] for d in zalozone] == ["Jarodev", "Kernel"] and all(d["chat_id"] == GRUPA for d in zalozone)
    env = wc.czytaj_env(wc.konfig(u) / "jarvo.env")
    assert env["TELEGRAM_HQ_CHAT_ID"] == GRUPA and env["TELEGRAM_TOPIC_SHERLOCK"] == "55"
    assert env["TELEGRAM_TOPIC_JARODEV"] == "101" and env["TELEGRAM_TOPIC_KERNEL"] == "102"
    assert env["TELEGRAM_OWNER_ID"] == "123456789"                             # reszta pliku zostaje
    sesje = json.loads((wc.konfig(u) / "sesje.json").read_text(encoding="utf-8"))
    assert sesje["gpu"]["czat"] == GRUPA and sesje["gpu"]["watek"] == "102"
    assert sesje["dev"] == {"nazwa": "Jarodev", "profil": "jarvo-jarodev"}
    assert flota.wywolania == 1
    out = capsys.readouterr().out
    assert "Sherlock: wątek 55 (był)" in out and "Jarodev: wątek 101 (nowy)" in out and "Kernel: wątek 102 (nowy)" in out
    assert "Flota wdrożona" in out and TOKEN not in out
    # drugi raz: wszystko znane (jarvo.env, sesje.json), nic nowego, bez wdrożenia
    api.wolania.clear()
    assert wc.polecenie_telegram_tematy(u, _a(), [], ot) == 0
    assert not api.metody("createForumTopic") and flota.wywolania == 1
    assert {d["message_thread_id"] for d in api.metody("sendChatAction")} == {55, 101, 102}
    assert "Wątki bez zmian" in capsys.readouterr().out


def test_tematy_zaklada_od_nowa_usuniety_watek(inst, capsys):
    u, ot, api, flota = inst
    wc.zapisz_env(wc.konfig(u) / "jarvo.env", {"TELEGRAM_HQ_CHAT_ID": GRUPA, "TELEGRAM_TOPIC_SHERLOCK": "55",
                                               "TELEGRAM_TOPIC_JARODEV": "56", "TELEGRAM_TOPIC_KERNEL": "57"})
    api.usuniete = {56}
    assert wc.polecenie_telegram_tematy(u, _a(bez_wdrozenia=True), [], ot) == 0
    assert [d["name"] for d in api.metody("createForumTopic")] == ["Jarodev"]
    env = wc.czytaj_env(wc.konfig(u) / "jarvo.env")
    assert env["TELEGRAM_TOPIC_JARODEV"] == "101" and env["TELEGRAM_TOPIC_KERNEL"] == "57"
    assert flota.wywolania == 0 and "wejdą przy następnym wdrożeniu" in capsys.readouterr().out


def test_tematy_bez_grupy_i_kilka_grup(inst, capsys):
    u, ot, api, _f = inst
    assert wc.polecenie_telegram_tematy(u, _a(), [], ot) == 2
    assert "napisz w niej „start”" in capsys.readouterr().err
    _grupy(u, {"-4001": {"nazwa": "A"}, "-4002": {"nazwa": "B"}})
    assert wc.polecenie_telegram_tematy(u, _a(), [], ot) == 2
    err = capsys.readouterr().err
    assert "-4001 „A”" in err and "--grupa" in err and not api.wolania
    assert wc.polecenie_telegram_tematy(u, _a(grupa="12345"), [], ot) == 2


@pytest.mark.parametrize("blad, rada", [
    (wc.BladTelegrama(400, "Bad Request: not enough rights to create a topic"), "administratorem z prawem"),
    (wc.BladTelegrama(400, "Bad Request: the chat is not a forum"), "Tematy (Topics)"),
])
def test_tematy_bledy_telegrama_z_rada(inst, capsys, blad, rada):
    u, ot, api, flota = inst
    api.bledy["createForumTopic"] = blad
    assert wc.polecenie_telegram_tematy(u, _a(grupa=GRUPA), [], ot) == 1
    err = capsys.readouterr().err
    assert rada in err and "„Sherlock”" in err and flota.wywolania == 0
    # grupa i wątki znane do błędu już zapisane: następny przebieg ich nie zakłada drugi raz
    assert wc.czytaj_env(wc.konfig(u) / "jarvo.env")["TELEGRAM_HQ_CHAT_ID"] == GRUPA


def test_tematy_grupa_bez_tematow_i_bot_nie_w_grupie(inst, capsys):
    u, ot, api, _f = inst
    api.forum = False
    assert wc.polecenie_telegram_tematy(u, _a(grupa=GRUPA), [], ot) == 1
    assert "Tematy (Topics)" in capsys.readouterr().err and not api.metody("createForumTopic")
    api.forum = True
    api.bledy["getChat"] = wc.BladTelegrama(400, "Bad Request: chat not found")
    assert wc.polecenie_telegram_tematy(u, _a(grupa=GRUPA), [], ot) == 1
    assert "Bota nie ma w tej grupie" in capsys.readouterr().err
    assert "TELEGRAM_HQ_CHAT_ID" not in wc.czytaj_env(wc.konfig(u) / "jarvo.env")


def test_tematy_ostrzega_gdy_bot_nie_jest_adminem(inst, capsys):
    u, ot, api, _f = inst
    api.status = "member"
    assert wc.polecenie_telegram_tematy(u, _a(grupa=GRUPA, bez_wdrozenia=True), [], ot) == 0
    assert "nie jest administratorem" in capsys.readouterr().out


def test_wyslij_do_watku_grupy(inst, monkeypatch):
    u, ot, api, _f = inst
    monkeypatch.setattr(sys, "stdin", io.StringIO("⚡ Kernel\n\nodpowiedź"))
    assert wc.polecenie_telegram_wyslij(u, _a(czat=GRUPA, watek="102"), [], ot) == 0
    assert api.metody("sendMessage") == [{"chat_id": GRUPA, "disable_web_page_preview": True,
                                          "message_thread_id": 102, "text": "⚡ Kernel\n\nodpowiedź"}]
    # bez --czat: grupa Jarvo HQ z jarvo.env; General (1) bez message_thread_id; bez niczego: DM właściciela
    wc.zapisz_env(wc.konfig(u) / "jarvo.env", {"TELEGRAM_HQ_CHAT_ID": GRUPA})
    for argumenty in ({"watek": "7"}, {"watek": "1"}, {}):
        monkeypatch.setattr(sys, "stdin", io.StringIO("tekst"))
        assert wc.polecenie_telegram_wyslij(u, _a(**argumenty), [], ot) == 0
    wyslane = api.metody("sendMessage")[1:]
    assert [(d["chat_id"], d.get("message_thread_id")) for d in wyslane] == [(GRUPA, 7), (GRUPA, None),
                                                                            ("123456789", None)]
    monkeypatch.setattr(sys, "stdin", io.StringIO("tekst"))
    assert wc.polecenie_telegram_wyslij(u, _a(watek="abc"), [], ot) == 2


def test_parser_zna_tematy_i_watek():
    p = argparse.ArgumentParser()
    wc.dodaj_polecenia(p.add_subparsers(dest="polecenie"))
    a = p.parse_args(["telegram", "tematy", "--grupa", GRUPA, "--bez-wdrozenia"])
    assert a.funkcja is wc.polecenie_telegram_tematy and a.grupa == GRUPA and a.bez_wdrozenia
    a = p.parse_args(["telegram", "wyslij", "--czat", GRUPA, "--watek", "12"])
    assert a.funkcja is wc.polecenie_telegram_wyslij and (a.czat, a.watek) == (GRUPA, "12")
