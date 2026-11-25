"""Oś czasu wątku (hq/plugin/scalanie.py): ukrywanie naszych wierszy, rodzaje pozycji, grupa kroków, tura w toku
i kursor (strony, pokolenie kompresji), członek nieczytelny. Baza i czytnik to atrapy o kształcie Rozmowy/Czytnik;
całość z prawdziwą bazą i bramą sprawdza tests/test_silnik_rozmow.py."""
import hashlib
import json

import pytest

from conftest import load_script

sc = load_script("hq/plugin/scalanie.py", "jarvo_test_scalanie")
cz = load_script("hq/plugin/czytnik.py", "jarvo_test_scalanie_czytnik")
bz = load_script("hq/plugin/budzenia.py", "jarvo_test_scalanie_budzenia")
och = load_script("hq/plugin/ochrona.py", "jarvo_test_scalanie_ochrona")

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


def test_podglad_krokow_tylko_na_stronie_z_redakcja_poczatku_i_pamiecia():
    """20.11: oś Jarva liczyła ~1,3 s, bo redagowała wszystkie wyniki narzędzi całej historii; teraz tylko strona,
    tylko początek wyniku (sekret w pokazanym fragmencie dalej zamaskowany) i raz na ten sam początek."""
    wiersze = []
    for n in range(6):                    # 6 tur: krok + wynik + odpowiedź; strona (limit 3) bierze dwie ostatnie
        wiersze += [wiersz(10 * n + 1, "assistant", "", tool_calls=[{"id": f"c{n}", "function": {
                        "name": "terminal", "arguments": '{"command": "env"}'}}]),
                    wiersz(10 * n + 2, "tool", f"wynik {n} token=sk-proj-{'A' * 40} " + "x" * 50_000, tool_call_id=f"c{n}"),
                    wiersz(10 * n + 3, "assistant", f"tura {n}")]
    wejscia = []

    def utajnij(t):
        wejscia.append(len(t))
        return och.utajnij(t)

    czyt = Czytnik({"web": [{"sesja_id": "s1", "stan": "ok", "wiersze": wiersze}]})
    db = Baza([], [], {"web": ["s1"]})
    wynik = sc.os_watku(db, czyt, WID, limit=3, budzenia=bz, utajnij=utajnij)
    kroki = [k for p in wynik["pozycje"] for k in p.get("kroki") or []]
    assert [k["podglad"][:7] for k in kroki] == ["wynik 5"]
    assert "sk-proj-" + "A" * 40 not in kroki[0]["podglad"] and len(kroki[0]["podglad"]) <= sc.PODGLAD_KROKU
    assert wejscia == [sc.PRZED_PODGLADEM]                     # jeden wynik ze strony, sam początek
    assert all("_wynik" not in k for k in kroki)
    starsza = sc.os_watku(db, czyt, WID, przed=wynik["przed"], limit=3, budzenia=bz, utajnij=utajnij)
    assert [k["podglad"][:7] for p in starsza["pozycje"] for k in p.get("kroki") or []] == ["wynik 3", "wynik 4"]
    assert len(wejscia) == 3
    sc.os_watku(db, czyt, WID, limit=3, budzenia=bz, utajnij=utajnij)
    assert len(wejscia) == 3                                   # ten sam wynik drugi raz: z pamięci


def test_kopia_prosby_po_kompresji_w_trakcie_tury_jest_nasza():
    """25.11: Hermes skompresował rozmowę w trakcie tury i skopiował prośbę do nowej sesji z nowym id wiersza; oś
    pokazała prośbę drugi raz, a dalsza praca straciła `w_toku` i stała obok żywego dymka."""
    w1 = wpis(1, tekst="wejdź na stronę", ts=100.9)
    sha = hashlib.sha256("wejdź na stronę".encode()).hexdigest()
    p1 = przebieg("p_1", stan="pracuje", aktywny=True, payload_sha=sha, wyslany_at=101.0, user_msg_id=1, wpis_id=w1["id"])
    linia = [{"sesja_id": "s1", "stan": "ok", "wiersze": [wiersz(1, "user", "wejdź na stronę", ts=101.0),
                                                         wiersz(2, "assistant", "Wchodzę.")]},
             {"sesja_id": "s2", "stan": "ok", "wiersze": [wiersz(3, "user", "streszczenie", podsumowanie=True),
                                                         wiersz(4, "user", "wejdź na stronę", ts=101.0),
                                                         wiersz(5, "assistant", "Gra wystartowała.")]}]
    wynik = sc.os_watku(Baza([w1], [p1], {"web": ["s1", "s2"]}), Czytnik({"web": linia}), WID, budzenia=bz)
    poz = wynik["pozycje"]
    assert [p["rodzaj"] for p in poz].count("wlasciciel") == 1
    assert [(p["tekst"], p["przebieg_id"], p["w_toku"]) for p in poz if p["rodzaj"] == "agent"] == [
        ("Wchodzę.", "p_1", True), ("Gra wystartowała.", "p_1", True)]


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


def test_pliki_z_odpowiedzi_przy_korzeniu_natywnym(monkeypatch):
    """Instalacja natywna: karty plików z odpowiedzi agenta także dla ścieżek pod faktycznym korzeniem (litera dysku,
    „\\” albo „/”, spacja w nazwie użytkownika, `kod` w backtickach) i dla starych /opt/data; reszta tekstu nie."""
    korzen = "C:\\Users\\Michał Żółć\\AppData\\Local\\Jarvo\\dane"
    monkeypatch.setenv("HERMES_HOME", korzen)
    nat = load_script("hq/plugin/scalanie.py", "jarvo_test_scalanie_natywny")
    widziane = []
    plik = lambda s: widziane.append(s) or {"path": s}                       # noqa: E731
    tekst = (f"Gotowe: `{korzen}\\jarvo\\workspaces\\web\\out\\index.html` i C:/Users/Michał Żółć/AppData/Local/Jarvo/"
             "dane/jarvo/inbox/a.png. Stary: /opt/data/jarvo/x.txt, obcy: C:/Windows/win.ini")
    assert [p["path"] for p in nat._pliki(tekst, plik)] == [
        f"{korzen}\\jarvo\\workspaces\\web\\out\\index.html",
        "C:/Users/Michał Żółć/AppData/Local/Jarvo/dane/jarvo/inbox/a.png", "/opt/data/jarvo/x.txt"]
    assert sc._pliki(tekst, plik) == [{"path": "/opt/data/jarvo/x.txt"}]        # kontener: tylko /opt/data


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


def test_cicha_odpowiedz_na_budzenie_bez_pozycji():
    """Pierwsza sesja 26.10: Jarvo odpowiadał „[SILENT]” na budzenia z tablicy, a oś pokazywała to jako wiadomość.
    Sama cisza = brak pozycji; linia ciszy w dłuższej odpowiedzi znika, reszta tekstu zostaje."""
    linia = [{"sesja_id": "s1", "stan": "ok", "wiersze": [
        wiersz(1, "user", BUDZENIE),
        wiersz(2, "assistant", "[SILENT]"),
        wiersz(3, "user", BUDZENIE),
        wiersz(4, "assistant", " `[silent]`.\n"),
        wiersz(5, "user", BUDZENIE),
        wiersz(6, "assistant", "Web skończył audyt.\n[SILENT]"),
        wiersz(7, "assistant", "", tool_calls=[{"id": "c1", "function": {"name": "kanban_show", "arguments": "{}"}}]),
        wiersz(8, "assistant", "[SILENT]", tool_calls=[{"id": "c2", "function": {"name": "kanban_list", "arguments": "{}"}}]),
        wiersz(9, "assistant", "Cytuję znacznik [SILENT] w zdaniu."),
    ]}]
    wynik = sc.os_watku(Baza([], [], {"web": ["s1"]}), Czytnik({"web": linia}), WID, budzenia=bz)
    agent = [p["tekst"] for p in wynik["pozycje"] if p["rodzaj"] == "agent"]
    assert agent == ["Web skończył audyt.", "Cytuję znacznik [SILENT] w zdaniu."]
    assert [p["rodzaj"] for p in wynik["pozycje"]] == ["budzenie", "budzenie", "budzenie", "agent", "kroki", "agent"]
    assert sc.bez_ciszy("[SILENT]") == "" and sc.bez_ciszy("Zwykła odpowiedź") == "Zwykła odpowiedź"


def test_raport_rutyny_w_sesji_tematu_to_wiadomosc_agenta():
    """18.11: rutyna z attach_to_session (Hermes `_cron_mirror_message`) wpisuje raport do sesji tematu JARVO jako
    wiadomość użytkownika „[Cron delivery: <nazwa>]”; w rozmowie z rozmówcą to nie dymek właściciela 📱, tylko
    wiadomość Jarva z nazwą rutyny, a odpowiedź właściciela z Telegrama zostaje jego dymkiem."""
    class BazaRozmowcy(Baza):
        def watek(self, wid):
            return {"id": wid, "rodzaj": "rozmowa", "rozmowca": "f:jarvo"}

    linia = [{"sesja_id": "s1", "stan": "ok", "wiersze": [
        wiersz(1, "user", "[Cron delivery: Poranny brief]\n☀️ Brief B-2026-11-18\n1. Telefon dla Jarodeva?"),
        wiersz(2, "user", "1 ok"),
        wiersz(3, "assistant", "Przydzielam telefon."),
    ]}]
    wynik = sc.os_watku(BazaRozmowcy([], [], {"jarvo": ["s1"]}), Czytnik({"jarvo": linia}), WID, budzenia=bz)
    poz = wynik["pozycje"]
    assert [p["rodzaj"] for p in poz] == ["rutyna", "wlasciciel", "agent"]
    assert poz[0]["agent"] == "jarvo" and poz[0]["rutyna"] == {"nazwa": "Poranny brief"}
    assert poz[0]["tekst"] == "☀️ Brief B-2026-11-18\n1. Telefon dla Jarodeva?"
    assert poz[1]["zrodlo"] == "telegram" and poz[1]["agent"] is None
    assert [k["rodzaj"] for k in sc.pozycje_kontekstu(BazaRozmowcy([], [], {"jarvo": ["s1"]}), Czytnik({"jarvo": linia}),
                                                      WID, budzenia=bz)] == ["agent"]


# ----------------------------------------------------------------------------------------------- szczegóły kroku

def test_krok_hermesa_z_adresem_mysla_i_wynikiem():
    """Krok osi niesie adres `ref`; szczegóły z linii członka: argumenty, myśl (reasoning + tekst wiersza), wynik
    terminala (output, kod wyjścia), czas między wywołaniem a wynikiem; sekret w wyniku ukryty."""
    klucz = "sk-proj-" + "a" * 30
    linia = [{"sesja_id": "s1", "stan": "ok", "wiersze": [
        wiersz(1, "user", "zrób"),
        wiersz(2, "assistant", "Sprawdzam.", mysl="Muszę sprawdzić klucz.", tool_calls=[{"id": "call_1", "function": {
            "name": "terminal", "arguments": '{"command": "env | grep KEY"}'}}]),
        wiersz(3, "tool", json.dumps({"output": f"OPENAI_API_KEY={klucz}\nok", "exit_code": 0}), ts=104.5,
               tool_call_id="call_1"),
        wiersz(4, "assistant", "Gotowe."),
    ]}]
    poz = sc.os_watku(Baza([], [], {"web": ["s1"]}), Czytnik({"web": linia}), WID)["pozycje"]
    (grupa,) = [p for p in poz if p["rodzaj"] == "kroki"]
    ref = grupa["kroki"][0]["ref"]
    assert ref == "h:web:rozmowa:call_1" and sc.czytaj_ref(ref) == ("h", ("web", "rozmowa", "call_1"))
    surowy = sc.krok_hermesa(linia, "call_1")
    assert surowy["argumenty"] == {"command": "env | grep KEY"} and surowy["mysl"] == "Muszę sprawdzić klucz.\n\nSprawdzam."
    assert (surowy["kod"], surowy["czas_ms"], surowy["blad"]) == (0, 2500, False)
    widok = sc.widok_kroku(surowy, utajnij=och.utajnij_krok, poufny=och.poufny_krok)
    assert widok["wynik"] == "OPENAI_API_KEY=[ukryte]\nok" and klucz not in json.dumps(widok)
    assert widok["argumenty"] == [{"klucz": "command", "wartosc": "env | grep KEY"}] and widok["gotowy"]
    assert sc.krok_hermesa(linia, "call_9") is None
    linia[0]["wiersze"].pop(2)                                  # wynik jeszcze nie przyszedł
    assert sc.widok_kroku(sc.krok_hermesa(linia, "call_1"), utajnij=str)["gotowy"] is False


@pytest.mark.parametrize("ref", ["", "x:a:b", "o::c1", "o:a/b:c1", "h:Web:rozmowa:c1", "h:web:rozmowa", "o:" + "a" * 65 + ":c",
                                 "o:a1:c 1", "h:web:rozmowa:c1\n"])
def test_zly_adres_kroku(ref):
    with pytest.raises(ValueError):
        sc.czytaj_ref(ref)


def test_widok_kroku_przyciecie_redakcja_i_plik_z_poswiadczeniami():
    dlugi = "\n".join(f"linia {i}" for i in range(500))
    s = {"narzedzie": "bash", "argumenty": {"command": "seq 500", "i": "Liczę"}, "wynik": dlugi, "mysl": ""}
    w = sc.widok_kroku(s, utajnij=str)
    assert w["argumenty"] == [{"klucz": "command", "wartosc": "seq 500"}]          # intencja jest w nagłówku kroku
    assert w["wynik"].count("\n") == 59 and w["przyciete"] and w["linie"] == 500 and not w["wiecej"]
    w = sc.widok_kroku(s, utajnij=str, wiecej=True)
    assert w["wynik"] == dlugi and not w["przyciete"] and w["wiecej"]
    w = sc.widok_kroku({**s, "wynik": "x" * 200_000}, utajnij=str, wiecej=True)
    assert len(w["wynik"]) == 65536 and w["przyciete"]                              # twardy sufit „Pokaż więcej”
    # redakcja przed przycięciem: sekret na granicy 4 KB nie zostaje w połowie
    w = sc.widok_kroku({"argumenty": {}, "wynik": "x" * 4090 + "ghp_" + "A" * 36}, utajnij=och.utajnij_krok)
    assert "ghp_" not in w["wynik"] and w["przyciete"]
    # plik z poświadczeniami: bez wyniku i diffu, treść zapisu ukryta, ścieżka zostaje
    w = sc.widok_kroku({"argumenty": {"path": "/home/x/.env", "content": "A=1\nB=2"}, "wynik": "A=1", "zmiana": "+A=1"},
                       utajnij=och.utajnij_krok, poufny=och.poufny_krok)
    assert w["poufny"] and w["wynik"] is None and w["zmiana"] is None and w["gotowy"]
    assert w["argumenty"] == [{"klucz": "path", "wartosc": "/home/x/.env"},
                              {"klucz": "content", "wartosc": sc.UKRYTE_POSWIADCZENIA}]


@pytest.mark.parametrize("tekst,sekret", [
    ("curl -H 'Authorization: Bearer abcdef1234567890' x", "abcdef1234567890"),
    ("export GH_TOKEN=abc123def456", "abc123def456"),
    ('{"api_key": "zxcv1234qwer"}', "zxcv1234qwer"),
    ("psql postgres://jaro:tajne1haslo@db:5432/x", "tajne1haslo"),
    ("password: hunter2x", "hunter2x"),
    ("klucz sk-ant-" + "b" * 30, "b" * 30),
])
def test_utajnij_krok(tekst, sekret):
    wynik = och.utajnij_krok(tekst)
    assert sekret not in wynik and "[ukryte]" in wynik
    assert och.utajnij_krok("max_tokens: 4096, model: x") == "max_tokens: 4096, model: x"


@pytest.mark.parametrize("tekst,poufny", [
    ("cat ~/.env", True), ("/opt/x/prod.env", True), ("cat .env.local", True), ("~/.config/gh/hosts.yml", True),
    ("~/.ssh/id_ed25519", True), ("/root/auth.json", True), ("sqlite3 state.db .tables", True),
    ("~/.phoneuse/body_token", True), ("~/.secrets/x", True), ("~/deploy3/a", True),
    ("~/.ssh/config", False), ("~/.ssh/id_ed25519.pub", False), (".venv/bin/python", False),
    ("docs/environment.md", False), ("README.md", False), ("", False),
])
def test_poufny_krok(tekst, poufny):
    assert och.poufny_krok(tekst) is poufny
