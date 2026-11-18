"""Grupa „Jarvo HQ” z tematami (14.11): `jarvo telegram tematy` (grupa z wiadomości właściciela, zakładanie
brakujących wątków createForumTopic, ponowne użycie znanych, nazwy JARVO/JARODEV/KERNEL, TELEGRAM_* do jarvo.env,
wątek Kernela do sesje.json, kanał domowy bramy, wdrożenie tras), dom Jarva w temacie General (17.11), rady po polsku
przy błędach Telegrama i `jarvo telegram wyslij --watek` (atrapa Bot API)."""
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
    {"name": "jarvo-sklep", "short": "Sklep", "telegram_topic": "sklep"},
    {"name": "jarvo-bez-watku", "short": "Cichy", "telegram_topic": ""}]}


class BotAPI:
    """Atrapa api_telegrama: zapisuje wołania, zakłada tematy od numeru 101, `bledy` = metoda → BladTelegrama, `nazwy`
    = wątek → nazwa tematu (General „1”); zmiana na tę samą nazwę jak Telegram: TOPIC_NOT_MODIFIED."""

    def __init__(self):
        self.wolania: list[tuple[str, dict]] = []
        self.bledy: dict[str, wc.BladTelegrama] = {}
        self.usuniete: set[int] = set()
        self.forum, self.status = True, "administrator"
        self.nastepny = 101
        self.nazwy: dict[int, str] = {1: "General"}

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
            self.nazwy[self.nastepny - 1] = dane["name"]
            return {"message_thread_id": self.nastepny - 1, "name": dane["name"]}
        if metoda in ("editForumTopic", "editGeneralForumTopic"):
            watek = dane.get("message_thread_id", 1)
            if self.nazwy.get(watek) == dane["name"]:
                raise wc.BladTelegrama(400, "Bad Request: TOPIC_NOT_MODIFIED")
            self.nazwy[watek] = dane["name"]
            return True
        if metoda == "sendMessage":
            return {"message_id": 1}
        if metoda == "deleteForumTopic":
            return True
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
        "dev": {"nazwa": "Sklep", "profil": "jarvo-sklep"}}), encoding="utf-8")
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
    api.nazwy[55] = "🔎 Sherlock"
    wc.zapisz_env(wc.konfig(u) / "host.env", {"TELEGRAM_HOME_CHANNEL": "123456789"})   # źródło przy wdrożeniu
    wc.zapisz_env(u.dane / ".env", {"TELEGRAM_HOME_CHANNEL": "123456789", "TELEGRAM_HOME_CHANNEL_THREAD_ID": "9"})
    assert wc.polecenie_telegram_tematy(u, _a(), [], ot) == 0
    zalozone = api.metody("createForumTopic")
    assert [d["name"] for d in zalozone] == ["SKLEP", "KERNEL", "UPDATES"] and all(d["chat_id"] == GRUPA for d in zalozone)
    # nazwy jednolite: General → JARVO, istniejący wątek przemianowany
    assert api.metody("editGeneralForumTopic") == [{"chat_id": GRUPA, "name": "JARVO"}]
    assert api.metody("editForumTopic") == [{"chat_id": GRUPA, "message_thread_id": 55, "name": "SHERLOCK"}]
    assert api.nazwy == {1: "JARVO", 55: "SHERLOCK", 101: "SKLEP", 102: "KERNEL", 103: "UPDATES"}
    env = wc.czytaj_env(wc.konfig(u) / "jarvo.env")
    assert env["TELEGRAM_HQ_CHAT_ID"] == GRUPA and env["TELEGRAM_TOPIC_SHERLOCK"] == "55"
    assert env["TELEGRAM_TOPIC_SKLEP"] == "101" and env["TELEGRAM_TOPIC_KERNEL"] == "102"
    assert env["TELEGRAM_TOPIC_UPDATES"] == "103"                            # archiwum raportów rutyn (18.11)
    assert env["TELEGRAM_OWNER_ID"] == "123456789"                             # reszta pliku zostaje
    # dom Jarva: kanał domowy bramy = grupa (General, bez wątku), także w host.env, żeby wdrożenie nie cofnęło
    for plik in (u.dane / ".env", wc.konfig(u) / "host.env"):
        brama = wc.czytaj_env(plik)
        assert brama["TELEGRAM_HOME_CHANNEL"] == GRUPA and "TELEGRAM_HOME_CHANNEL_THREAD_ID" not in brama
    assert wc.czytaj_env(u.dane / ".env")["TELEGRAM_BOT_TOKEN"] == TOKEN
    sesje = json.loads((wc.konfig(u) / "sesje.json").read_text(encoding="utf-8"))
    assert sesje["gpu"]["czat"] == GRUPA and sesje["gpu"]["watek"] == "102"
    assert sesje["dev"] == {"nazwa": "Sklep", "profil": "jarvo-sklep"}
    assert flota.wywolania == 1
    out = capsys.readouterr().out
    assert "SHERLOCK: wątek 55 (był, nazwa „SHERLOCK”)" in out and "SKLEP: wątek 101 (nowy)" in out
    assert "KERNEL: wątek 102 (nowy)" in out and "JARVO: temat General (zmieniona)" in out
    assert "UPDATES: wątek 103 (nowy): kopia raportów rutyn (archiwum)" in out
    assert f"Dom Jarva: grupa Jarvo HQ {GRUPA}, temat General „JARVO”" in out
    assert "Flota wdrożona" in out and TOKEN not in out
    # drugi raz: wszystko znane (jarvo.env, sesje.json, nazwy, kanał domowy), nic nowego, bez wdrożenia
    api.wolania.clear()
    assert wc.polecenie_telegram_tematy(u, _a(), [], ot) == 0
    assert not api.metody("createForumTopic") and flota.wywolania == 1
    assert {d["message_thread_id"] for d in api.metody("sendChatAction")} == {55, 101, 102, 103}
    assert api.nazwy == {1: "JARVO", 55: "SHERLOCK", 101: "SKLEP", 102: "KERNEL", 103: "UPDATES"}
    out = capsys.readouterr().out
    assert "Wątki bez zmian" in out and "JARVO: temat General (bez zmian)" in out and "nazwa „" not in out


def test_tematy_zaklada_od_nowa_usuniety_watek(inst, capsys):
    u, ot, api, flota = inst
    wc.zapisz_env(wc.konfig(u) / "jarvo.env", {"TELEGRAM_HQ_CHAT_ID": GRUPA, "TELEGRAM_TOPIC_SHERLOCK": "55",
                                               "TELEGRAM_TOPIC_SKLEP": "56", "TELEGRAM_TOPIC_KERNEL": "57",
                                               "TELEGRAM_TOPIC_UPDATES": "58"})
    api.usuniete = {56}
    assert wc.polecenie_telegram_tematy(u, _a(bez_wdrozenia=True), [], ot) == 0
    assert [d["name"] for d in api.metody("createForumTopic")] == ["SKLEP"]
    env = wc.czytaj_env(wc.konfig(u) / "jarvo.env")
    assert env["TELEGRAM_TOPIC_SKLEP"] == "101" and env["TELEGRAM_TOPIC_KERNEL"] == "57"
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
    assert rada in err and "„SHERLOCK”" in err and flota.wywolania == 0
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


def test_tematy_usuwa_trasy_i_watki_specjalistow(inst, capsys):
    """16.11: w grupie tylko Jarvo, agenci biznesowi i Kernel. Trasa wątku, którego flota już nie ma, wypada zawsze;
    sam wątek w Telegramie znika tylko na --usun-zbedne (może mieć rozmowę właściciela)."""
    u, ot, api, _f = inst
    wc.zapisz_env(wc.konfig(u) / "jarvo.env", {"TELEGRAM_HQ_CHAT_ID": GRUPA, "TELEGRAM_TOPIC_SHERLOCK": "55",
                                               "TELEGRAM_TOPIC_STUDIO": "56", "TELEGRAM_TOPIC_KERNEL": "57"})
    (u.build / "wiedza" / "fleet.json").write_text(json.dumps({"orchestrator": "jarvo", "agents": [
        {"name": "jarvo", "short": "Jarvo", "telegram_topic": "general"},
        {"name": "jarvo-sherlock", "short": "Sherlock", "telegram_topic": ""}]}), encoding="utf-8")
    assert wc.polecenie_telegram_tematy(u, _a(bez_wdrozenia=True), [], ot) == 0
    env = wc.czytaj_env(wc.konfig(u) / "jarvo.env")
    assert "TELEGRAM_TOPIC_SHERLOCK" not in env and "TELEGRAM_TOPIC_STUDIO" not in env and env["TELEGRAM_TOPIC_KERNEL"] == "57"
    assert not api.metody("deleteForumTopic") and "usunie go --usun-zbedne" in capsys.readouterr().out
    wc.zapisz_env(wc.konfig(u) / "jarvo.env", {"TELEGRAM_TOPIC_SHERLOCK": "55"})
    assert wc.polecenie_telegram_tematy(u, _a(bez_wdrozenia=True, usun_zbedne=True), [], ot) == 0
    assert api.metody("deleteForumTopic") == [{"chat_id": GRUPA, "message_thread_id": 55}]
    assert "TELEGRAM_TOPIC_SHERLOCK" not in wc.czytaj_env(wc.konfig(u) / "jarvo.env")


def test_tematy_bierze_nowy_numer_grupy_po_wlaczeniu_tematow(inst, monkeypatch, capsys):
    """15.11: bot znał tylko stary numer zwykłej grupy (wiadomość „start” przed włączeniem tematów); getChat pod nim
    mówi „bez tematów”, a nowy numer supergrupy Telegram podaje dopiero w błędzie wysyłki (migrate_to_chat_id).
    `tematy` sam go bierze, bez drugiego „start” właściciela; grupa nieprzeniesiona = dawna rada o tematach."""
    u, ot, api, _f = inst
    stara = "-5318577883"
    _grupy(u, {stara: {"nazwa": "JARVO", "watki": {}}})
    przeniesiona = {"tak": True}

    def telegram(token, metoda, dane=None, **kw):
        if (dane or {}).get("chat_id") == stara:
            if metoda == "getChat":
                return {"id": int(stara), "title": "JARVO", "type": "group", "is_forum": False}
            if metoda == "sendChatAction" and przeniesiona["tak"]:
                raise wc.BladTelegrama(400, "Bad Request: group chat was upgraded to a supergroup chat", GRUPA)
        return api(token, metoda, dane, **kw)
    monkeypatch.setattr(wc, "api_telegrama", telegram)
    assert wc.polecenie_telegram_tematy(u, _a(bez_wdrozenia=True), [], ot) == 0
    assert f"dostała nowy numer {GRUPA}" in capsys.readouterr().out
    assert {d["chat_id"] for d in api.metody("createForumTopic")} == {GRUPA}
    assert wc.czytaj_env(wc.konfig(u) / "jarvo.env")["TELEGRAM_HQ_CHAT_ID"] == GRUPA
    przeniesiona["tak"] = False
    assert wc.polecenie_telegram_tematy(u, _a(grupa=stara), [], ot) == 1
    assert "Tematy (Topics)" in capsys.readouterr().err


def test_wyslij_do_watku_grupy(inst, monkeypatch):
    u, ot, api, _f = inst
    monkeypatch.setattr(sys, "stdin", io.StringIO("⚡ Kernel\n\nodpowiedź"))
    assert wc.polecenie_telegram_wyslij(u, _a(czat=GRUPA, watek="102"), [], ot) == 0
    assert api.metody("sendMessage") == [{"chat_id": GRUPA, "disable_web_page_preview": True,
                                          "message_thread_id": 102, "text": "⚡ Kernel\n\nodpowiedź"}]
    # bez --czat i bez grupy: DM właściciela (dom Jarva bez grupy)
    monkeypatch.setattr(sys, "stdin", io.StringIO("tekst"))
    assert wc.polecenie_telegram_wyslij(u, _a(), [], ot) == 0
    # z grupą Jarvo HQ w jarvo.env: --watek do jej wątku, General (1) bez message_thread_id, bez niczego dom Jarva
    # (General, bez wątku), --czat <ID właściciela> nadal do DM
    wc.zapisz_env(wc.konfig(u) / "jarvo.env", {"TELEGRAM_HQ_CHAT_ID": GRUPA})
    for argumenty in ({"watek": "7"}, {"watek": "1"}, {}, {"czat": "123456789"}):
        monkeypatch.setattr(sys, "stdin", io.StringIO("tekst"))
        assert wc.polecenie_telegram_wyslij(u, _a(**argumenty), [], ot) == 0
    wyslane = api.metody("sendMessage")[1:]
    assert [(d["chat_id"], d.get("message_thread_id")) for d in wyslane] == [
        ("123456789", None), (GRUPA, 7), (GRUPA, None), (GRUPA, None), ("123456789", None)]
    monkeypatch.setattr(sys, "stdin", io.StringIO("tekst"))
    assert wc.polecenie_telegram_wyslij(u, _a(watek="abc"), [], ot) == 2


def test_proba_idzie_do_domu_jarva(inst, capsys):
    """17.11: próbna wiadomość (jak każda, którą Jarvo wysyła sam) do tematu General grupy, bez message_thread_id;
    bez grupy do DM właściciela."""
    u, ot, api, _f = inst
    assert wc.polecenie_telegram_test(u, argparse.Namespace(bez_rutyn=True), [], ot) == 0
    wc.zapisz_env(wc.konfig(u) / "jarvo.env", {"TELEGRAM_HQ_CHAT_ID": GRUPA})
    assert wc.polecenie_telegram_test(u, argparse.Namespace(bez_rutyn=True), [], ot) == 0
    assert [(d["chat_id"], "message_thread_id" in d) for d in api.metody("sendMessage")] == [
        ("123456789", False), (GRUPA, False)]
    assert f"do domu Jarva: grupa Jarvo HQ {GRUPA}, temat General „JARVO”" in capsys.readouterr().out
    assert json.loads((wc.stan_skarbca(u) / "telegram.json").read_text(encoding="utf-8"))["do"] == GRUPA


def test_tematy_bez_prawa_do_nazw_zapisuje_trasy_i_ostrzega(inst, capsys):
    """Brak prawa „Zarządzanie tematami” przy zmianie nazwy General nie blokuje tras ani domu Jarva: kod 1 i rada."""
    u, ot, api, _f = inst
    api.bledy["editGeneralForumTopic"] = wc.BladTelegrama(400, "Bad Request: not enough rights to manage topics")
    assert wc.polecenie_telegram_tematy(u, _a(grupa=GRUPA, bez_wdrozenia=True), [], ot) == 1
    err = capsys.readouterr().err
    assert "nazwy tematu „JARVO” nie zmieniłem" in err and "Zarządzanie tematami" in err
    assert wc.czytaj_env(wc.konfig(u) / "jarvo.env")["TELEGRAM_TOPIC_KERNEL"] == "103"
    assert wc.czytaj_env(u.dane / ".env")["TELEGRAM_HOME_CHANNEL"] == GRUPA


def test_status_pokazuje_uklad_grupy(inst, capsys):
    """`jarvo telegram status`: dom Jarva, tematy (kogo wybierasz tematem), DM jako wejście zapasowe, ostrzeżenie,
    gdy kanał domowy bramy wskazuje gdzie indziej."""
    u, ot, api, _f = inst
    assert wc.polecenie_telegram_tematy(u, _a(grupa=GRUPA, bez_wdrozenia=True), [], ot) == 0
    capsys.readouterr()
    assert wc.polecenie_telegram_status(u, argparse.Namespace(json=False, sprawdz=False), [], ot) == 0
    out = capsys.readouterr().out
    assert f"Dom Jarva: grupa Jarvo HQ {GRUPA}, temat General „JARVO”" in out
    assert "JARVO (General): Jarvo (dom" in out and "SHERLOCK (wątek 101): agent jarvo-sherlock" in out
    assert "KERNEL (wątek 103): sesja Kernel (skrzynka)" in out
    assert "UPDATES (wątek 104): archiwum raportów rutyn" in out
    assert "DM 123456789: wejście zapasowe do Jarva" in out and "UWAGA: kanał domowy" not in out
    wc.zapisz_env(u.dane / ".env", {"TELEGRAM_HOME_CHANNEL": "123456789"})
    assert wc.polecenie_telegram_status(u, argparse.Namespace(json=True, sprawdz=False), [], ot) == 0
    stan = json.loads(capsys.readouterr().out)
    assert stan["dom_jarva"] == GRUPA and stan["dom"] == "123456789"
    assert [t["tytul"] for t in stan["tematy"]] == ["JARVO", "SHERLOCK", "SKLEP", "KERNEL", "UPDATES"]
    assert wc.polecenie_telegram_status(u, argparse.Namespace(json=False, sprawdz=False), [], ot) == 0
    assert "UWAGA: kanał domowy bramy" in capsys.readouterr().out
    assert any(w["nazwa"] == "Telegram: dom Jarva" and w["stan"] == "uwaga" for w in wc.sprawdz_telegram(u))


def test_cel_rutyn_jak_build_i_stare_rutyny_wdraza(inst):
    """`deliver` rutyn, którego oczekuje `jarvo telegram tematy/ustaw`, to ROUTINE_DELIVER buildu (18.11: General jako
    wątek 1, kopia w UPDATES); rutyny ze starym celem (sama grupa: Hermes zakładał temat „Hermes — <rutyna>”) albo
    bez UPDATES wymagają wdrożenia."""
    import build
    import fleetlib as fl
    u, _ot, _api, _f = inst
    wc.zapisz_env(wc.konfig(u) / "jarvo.env", {"TELEGRAM_HQ_CHAT_ID": GRUPA, "TELEGRAM_TOPIC_UPDATES": "58"})
    flota = fl.load_fleet()
    env = wc.czytaj_env(wc.konfig(u) / "jarvo.env")
    oczekiwany = build.base_tokens(flota, flota.agent(flota.orchestrator), "/b", env)["ROUTINE_DELIVER"]
    assert wc.cel_rutyn(u, GRUPA) == oczekiwany == f"telegram:{GRUPA}:1,telegram:{GRUPA}:58"
    assert wc.cel_rutyn(u, "123456789") == "telegram:123456789"
    jobs = wc.profil(u) / "cron" / "jobs.json"
    jobs.parent.mkdir(parents=True, exist_ok=True)
    for deliver, dobry in ((f"telegram:{GRUPA}", False), (f"telegram:{GRUPA}:1", False), (oczekiwany, True)):
        jobs.write_text(json.dumps({"jobs": [{"id": "jarvo-patrol", "name": "Patrol floty", "deliver": deliver}]}),
                        encoding="utf-8")
        assert wc.rutyny_do_domu(u, GRUPA) is dobry, deliver


def test_parser_zna_tematy_i_watek():
    p = argparse.ArgumentParser()
    wc.dodaj_polecenia(p.add_subparsers(dest="polecenie"))
    a = p.parse_args(["telegram", "tematy", "--grupa", GRUPA, "--bez-wdrozenia"])
    assert a.funkcja is wc.polecenie_telegram_tematy and a.grupa == GRUPA and a.bez_wdrozenia
    a = p.parse_args(["telegram", "wyslij", "--czat", GRUPA, "--watek", "12"])
    assert a.funkcja is wc.polecenie_telegram_wyslij and (a.czat, a.watek) == (GRUPA, "12")
