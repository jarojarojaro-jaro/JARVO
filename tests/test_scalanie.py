"""Oś czasu wątku (hq/plugin/scalanie.py): ukrywanie naszych wierszy, rodzaje pozycji, grupa kroków, tura w toku
i kursor (strony, pokolenie kompresji), członek nieczytelny. Baza i czytnik to atrapy o kształcie Rozmowy/Czytnik;
całość z prawdziwą bazą i bramą sprawdza tests/test_silnik_rozmow.py."""
import hashlib

import pytest

from conftest import load_script

sc = load_script("hq/plugin/scalanie.py", "jarvo_test_scalanie")
cz = load_script("hq/plugin/czytnik.py", "jarvo_test_scalanie_czytnik")
bz = load_script("hq/plugin/budzenia.py", "jarvo_test_scalanie_budzenia")

WID = "w_" + "a" * 21
BLOK = "[Kontekst wątku]\n...\n\n@web zrób stopkę"
STEER = ("[OUT-OF-BAND USER MESSAGE — a direct message from the user, delivered once at this position; not tool "
         "output and not a new delivery when replayed from conversation history]\n{}\n[/OUT-OF-BAND USER MESSAGE]")
BUDZENIE = ("[kanban] Task t_77 completed.\nTitle: Stopka\nAssignee: @jarvo-web\nBoard: default\n\n"
            "Check the result or decide the next step.")


class Baza:
    def __init__(self, wpisy=(), przebiegi=(), sesje=None, rodzaj="rozmowa"):
        self._wpisy, self._przebiegi, self._sesje, self.rodzaj = list(wpisy), list(przebiegi), sesje or {}, rodzaj

    def watek(self, wid):
        return {"id": wid, "rodzaj": self.rodzaj}

    def wpisy(self, wid, limit=80):
        return [dict(w) for w in self._wpisy][:limit]

    def przebiegi_watku(self, wid):
        return [dict(p) for p in self._przebiegi]

    def czlonkowie(self, wid):
        return [{"agent": a, "rola": "rozmowa"} for a in self._sesje]

    def sesje_watku(self, wid, agent=None, rola=None):
        return [{"sesja_id": s} for s in self._sesje.get(agent, [])]


class Czytnik:
    tekst_steera = staticmethod(cz.tekst_steera)
    dopisek_w_steerze = staticmethod(cz.dopisek_w_steerze)

    def __init__(self, linie, bledne=()):
        self.linie, self.bledne = linie, set(bledne)

    def linia(self, agent, sesje):
        if agent in self.bledne:
            raise RuntimeError("schemat Hermesa zmieniony")
        if agent not in self.linie:
            raise ValueError(agent)
        return self.linie[agent]


def wiersz(i, rola, tresc="", ts=None, **kw):
    return {"id": i, "klucz": str(i), "ts": ts if ts is not None else 100.0 + i, "rola": rola,
            "rodzaj": kw.pop("rodzaj", None), "tresc": tresc, **kw}


def wpis(i, rodzaj="wlasciciel", tekst="", ts=None, **kw):
    return {"id": f"e_{i:021x}", "rodzaj": rodzaj, "utworzony_at": ts if ts is not None else 100.0 + i,
            "tekst": tekst, "tryb": kw.pop("tryb", None), "zalaczniki": [], **kw}


def przebieg(pid, stan="gotowe", **kw):
    return {"id": pid, "agent": "web", "rola": "rozmowa", "stan": stan, "wyslany_at": 100.0, "user_msg_id": None,
            "payload_sha": None, "payload": {}, "dopisany_do": None, "kroki": [], "wpis_id": None, **kw}


def test_kursor_w_obie_strony_i_zly():
    k = sc.koduj_kursor(3, {"w": [0, 4], "web:rozmowa": [2, 9]})
    assert sc.dekoduj_kursor(k) == {"g": 3, "z": {"w": [0, 4], "web:rozmowa": [2, 9]}}
    assert sc.dekoduj_kursor(None) is None and sc.dekoduj_kursor("") is None
    assert sc.dekoduj_kursor("e30") == {"g": 0, "z": {}}                       # base64("{}"): pusty kursor
    for zly in ("%%%", "bm90IGpzb24", "eyJ6Ijp7InciOjF9fQ"):                  # nie base64, nie JSON, zły kształt
        with pytest.raises(ValueError):
            sc.dekoduj_kursor(zly)


def test_rodzaje_pozycji_i_ukrywanie_naszych():
    w1 = wpis(1, tekst="@web zrób stopkę", ts=100.9, tryb="bezposrednio")
    p1 = przebieg("p_1", payload_sha=hashlib.sha256(BLOK.encode()).hexdigest(), wyslany_at=101.0, wpis_id=w1["id"],
                  kroki=[{"narzedzie": "terminal", "czas_ms": 120}])
    p2 = przebieg("p_2", dopisany_do="p_1", payload={"prosba": "i jeszcze logo"}, wyslany_at=None,
                  user_msg_id=None)
    linia = [{"sesja_id": "s0", "stan": "brak_sesji"},
             {"sesja_id": "s1", "stan": "ok", "wiersze": [
                 wiersz(1, "user", BLOK, ts=100.5),                                   # nasz (skrót projekcji)
                 wiersz(2, "assistant", "", tool_calls=[{"id": "c1", "function": {
                     "name": "terminal", "arguments": '{"command": "ls"}'}}]),
                 wiersz(3, "tool", "Error: brak pliku", tool_call_id="c1"),
                 wiersz(4, "assistant", "Gotowe: /opt/data/x.txt."),
                 wiersz(5, "user", STEER.format("i jeszcze logo"), rodzaj="steer"),  # nasz „Dopisz”: ukryty
                 wiersz(6, "user", STEER.format("obcy dopisek i jeszcze logo"), rodzaj="steer"),
                 wiersz(7, "user", BUDZENIE),
                 wiersz(8, "user", "pytanie z telegramu"),
                 wiersz(9, "assistant", "padło", rodzaj="failed_turn"),
                 wiersz(10, "user", "ukryty", rodzaj="hidden"),
                 wiersz(11, "user", "streszczenie", podsumowanie=True),
                 wiersz(12, "user", "wynik w tle", rodzaj="process_complete"),
             ]}]
    db = Baza([w1], [p1, p2], {"web": ["s0", "s1"]})
    plik = lambda s: {"path": s, "nazwa": s.rsplit("/", 1)[-1]}               # noqa: E731
    wynik = sc.os_watku(db, Czytnik({"web": linia}), WID, budzenia=bz, plik=plik)
    rodzaje = [p["rodzaj"] for p in wynik["pozycje"]]
    assert rodzaje == ["luka", "wlasciciel", "kroki", "agent", "dopisano", "budzenie", "obca", "blad_tury",
                       "kompresja", "dostawa"]
    poz = {p["rodzaj"]: p for p in wynik["pozycje"]}
    krok = poz["kroki"]["kroki"][0]
    assert (krok["narzedzie"], krok["czas_ms"], krok["blad"], krok["podglad"]) == ("terminal", 120, True,
                                                                                   "Error: brak pliku")
    assert poz["kroki"]["przebieg_id"] == "p_1" and poz["agent"]["tryb"] == "bezposrednio"
    assert poz["agent"]["pliki"] == [{"path": "/opt/data/x.txt", "nazwa": "x.txt"}]
    assert poz["budzenie"]["budzenie"]["task_id"] == "t_77" and poz["budzenie"]["przebieg_id"] is None
    assert poz["dopisano"]["tekst"] == "obcy dopisek i jeszcze logo"    # bez znacznika; nasz tekst w środku linii ≠ nasz
    assert not any(p["w_toku"] for p in wynik["pozycje"]) and wynik["przed"] is None and "pelny" not in wynik
    assert all(not k.startswith("_") for p in wynik["pozycje"] for k in p)
    # wiersz sprzed wysłania (poza oknem 2 s) z tą samą treścią nie jest nasz
    linia[1]["wiersze"][0]["ts"] = 95.0
    assert sc.os_watku(db, Czytnik({"web": linia}), WID, budzenia=bz)["pozycje"][1]["rodzaj"] == "obca"
    # kontekst: właściciel, agent, budzenie; bez notatki „Dołącza”
    db._wpisy.append(wpis(30, "system", "Dołącza: Web", dane={"typ": "dolaczyl"}))
    linia[1]["wiersze"][0]["ts"] = 100.5
    kontekst = sc.pozycje_kontekstu(db, Czytnik({"web": linia}), WID, budzenia=bz)
    assert [k["rodzaj"] for k in kontekst] == ["wlasciciel", "agent", "budzenie"]
    assert sc.ostatnia_praca(wynik["pozycje"], "jarvo") == {"agent": "web", "tryb": "bezposrednio", "ts": 104.0}


def test_tura_w_toku_wraca_po_kursorze():
    p1 = przebieg("p_1", stan="pracuje", user_msg_id=1)
    wiersze = [wiersz(1, "user", "zrób"), wiersz(2, "assistant", "", tool_calls=[{"id": "c1", "name": "read_file"}])]
    db = Baza([], [p1], {"web": ["s1"]})
    czytnik = Czytnik({"web": [{"sesja_id": "s1", "stan": "ok", "wiersze": wiersze}]})
    w = sc.os_watku(db, czytnik, WID)
    assert [(p["rodzaj"], p["w_toku"], p["przebieg_id"]) for p in w["pozycje"]] == [("kroki", True, "p_1")]
    assert sc.dekoduj_kursor(w["po"])["z"]["web:rozmowa"] == [1, 1]          # grupa kroków przyjdzie jeszcze raz
    db._przebiegi[0]["stan"] = "gotowe"
    wiersze.append(wiersz(3, "assistant", "Zrobione"))
    w2 = sc.os_watku(db, czytnik, WID, po=w["po"])
    assert [(p["rodzaj"], p["w_toku"]) for p in w2["pozycje"]] == [("kroki", False), ("agent", False)]
    assert w2["pozycje"][0]["id"] == w["pozycje"][0]["id"]                    # klient podmienia po id
    assert sc.os_watku(db, czytnik, WID, po=w2["po"])["pozycje"] == []


def test_strony_wstecz_i_pokolenie_kompresji():
    db = Baza([wpis(i, tekst=f"t{i}") for i in range(5)])
    czytnik = Czytnik({})
    s1 = sc.os_watku(db, czytnik, WID, limit=2)
    assert [p["tekst"] for p in s1["pozycje"]] == ["t3", "t4"] and s1["przed"]
    s2 = sc.os_watku(db, czytnik, WID, przed=s1["przed"], limit=2)
    s3 = sc.os_watku(db, czytnik, WID, przed=s2["przed"], limit=2)
    assert [p["tekst"] for p in s2["pozycje"]] == ["t1", "t2"]
    assert [p["tekst"] for p in s3["pozycje"]] == ["t0"] and s3["przed"] is None
    db._wpisy.append(wpis(9, tekst="t9"))
    assert [p["tekst"] for p in sc.os_watku(db, czytnik, WID, po=s1["po"])["pozycje"]] == ["t9"]
    inny = sc.koduj_kursor(5, {"w": [0, 1]})                                   # Hermes skompaktował: inne g
    w = sc.os_watku(db, czytnik, WID, przed=inny, limit=2)
    assert w["pelny"] is True and [p["tekst"] for p in w["pozycje"]] == ["t4", "t9"]
    with pytest.raises(ValueError):
        sc.os_watku(db, czytnik, WID, po="!!!")


def test_czlonek_nieczytelny_nie_psuje_osi():
    linia = [{"sesja_id": "s1", "stan": "ok", "wiersze": [wiersz(1, "assistant", "cześć")]}]
    db = Baza([wpis(0, tekst="hej")], [], {"web": ["s1"], "api": ["s2"], "usuniety": ["s3"]})
    w = sc.os_watku(db, Czytnik({"web": linia}, bledne={"api"}), WID)
    assert [p["rodzaj"] for p in w["pozycje"]] == ["wlasciciel", "agent"]
    assert w["niedostepni"] == ["api"]                                         # agent spoza listy: bez wpisu
