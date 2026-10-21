"""Strumień SSE aplikacji (hq/plugin/strumien.py): powtórka od kursora, routing po wątkach, reset (epoka, za stare,
przepełnienie) z `id`, ramka `kursor` po powtórce, jedno połączenie na klienta, limit strumieni, pamięć subskrypcji
(ten sam URL = zbiór z ostatniego POST, nowy URL wygrywa), bufor ograniczony bajtami, zamknięcie przy wyłączaniu
procesu."""
import asyncio
import json

from conftest import load_script

st = load_script("hq/plugin/strumien.py", "jarvo_test_strumien")


def _ramki(dane: bytes) -> list[tuple[str | None, str, dict]]:
    out = []
    for blok in dane.decode().split("\n\n"):
        pola = dict(x.split(": ", 1) for x in blok.splitlines() if ": " in x and not x.startswith(":"))
        if "event" in pola:
            out.append((pola.get("id"), pola["event"], json.loads(pola["data"])))
    return out


async def _czytaj(pol) -> bytes:
    out = b""
    async for kawalek in pol.strumien():
        out += kawalek
    return out


def test_powtorka_routing_i_reset():
    async def main():
        hub = st.Hub(zycie=0.3, ping=0.1, hello=lambda: {"wersja": "abc", "silnik": "ok"})
        od = hub.kursor()
        hub.nadaj("przebieg.delta", {"tekst": "A"}, watek_id="w_1")
        hub.nadaj("przebieg.delta", {"tekst": "B"}, watek_id="w_2")
        hub.nadaj("watek.zmiana", {"watek": {"id": "w_2"}})
        r = _ramki(await _czytaj(hub.polacz("k_aaaaaa", ["w_1"], od)))
        assert r[0][1] == "hello" and r[0][2]["wersja"] == "abc" and r[0][2]["epoka"] == hub.epoka
        assert [(t, d.get("tekst")) for _i, t, d in r[1:]] == [("przebieg.delta", "A"), ("watek.zmiana", None),
                                                              ("kursor", None)]
        assert r[-1][0] == hub.kursor()                  # po powtórce: kursor chwili połączenia
        # od środka: tylko późniejsze
        r2 = _ramki(await _czytaj(hub.polacz("k_bbbbbb", ["w_1", "w_2"], r[1][0])))
        assert [t for _i, t, _d in r2[1:]] == ["przebieg.delta", "watek.zmiana", "kursor"]
        assert r2[1][2]["tekst"] == "B"
        for zly, powod in (("ffffff.1", "epoka"), (f"{hub.epoka}.999", "za_stare"), ("bez-kropki", "za_stare")):
            r3 = _ramki(await _czytaj(hub.polacz("k_aaaaaa", [], zly)))
            assert ("reset", {"powod": powod}) in [(t, d) for _i, t, d in r3]
        assert hub.liczba_polaczen() == 0
    asyncio.run(main())


def test_na_zywo_ping_i_przepelnienie(monkeypatch):
    async def main():
        hub = st.Hub(zycie=0.5, ping=0.1)
        pol = hub.polacz("k_bbbbbb", ["w_1"], None)
        zadanie = asyncio.ensure_future(_czytaj(pol))
        await asyncio.sleep(0.05)
        assert hub.subskrybowane_watki() == {"w_1"}
        hub.nadaj("przebieg.delta", {"tekst": "x"}, watek_id="w_1")
        hub.nadaj("przebieg.delta", {"tekst": "y"}, watek_id="w_9")          # inny wątek: nie przychodzi
        assert hub.subskrybuj("k_bbbbbb", watki=["w_9"])
        hub.nadaj("przebieg.delta", {"tekst": "z"}, watek_id="w_9")
        dane = await zadanie
        r = _ramki(dane)
        assert [d["tekst"] for _i, t, d in r if t == "przebieg.delta"] == ["x", "z"]
        assert b": ping" in dane and dane.startswith(b"retry: 1000")
        # przepełnienie kolejki połączenia = reset i zrzucenie zaległości
        monkeypatch.setattr(st, "KOLEJKA", 3)
        pol = hub.polacz("k_cccccc", ["w_1"], None)
        for i in range(5):
            pol._wstaw(st._ramka(f"{hub.epoka}.{i}", "przebieg.delta", {"tekst": str(i)}))
        r = _ramki(await _czytaj(pol))
        assert ("reset", {"powod": "przepelnienie"}) in [(t, d) for _i, t, d in r]
    asyncio.run(main())


def test_jeden_strumien_na_klienta_i_zamkniecie():
    async def main():
        hub = st.Hub(zycie=5, ping=5)
        stare = asyncio.ensure_future(_czytaj(hub.polacz("k_dddddd", [], None)))
        await asyncio.sleep(0.05)
        nowe = asyncio.ensure_future(_czytaj(hub.polacz("k_dddddd", [], None)))
        await asyncio.wait_for(stare, 1)                 # starsze połączenie tego klienta zamknięte od razu
        assert hub.liczba_polaczen() == 1
        hub.zamknij_wszystkie()                          # hak handle_exit: koniec bez czekania 25 s
        await asyncio.wait_for(nowe, 1)
        r = _ramki(await asyncio.wait_for(_czytaj(hub.polacz("k_eeeeee", [], None)), 1))
        assert [t for _i, t, _d in r] == ["hello"]       # po zamknięciu: tylko hello
    asyncio.run(main())


def test_reset_niesie_id_a_hello_tylko_bez_kursora():
    async def main():
        hub = st.Hub(zycie=0.2, ping=1)
        r = _ramki(await _czytaj(hub.polacz("k_eeeeee", [], None)))
        assert r[0][1] == "hello" and r[0][0] == hub.kursor()          # bez kursora: hello ustawia Last-Event-ID
        r = _ramki(await _czytaj(hub.polacz("k_eeeeee", [], "ffffff.7")))
        hello, reset = r[0], next(x for x in r if x[1] == "reset")
        assert hello[0] is None and reset[0] == hub.kursor()            # reset z bieżącym kursorem: koniec pętli
        r = _ramki(await _czytaj(hub.polacz("k_eeeeee", [], reset[0])))
        assert [t for _i, t, _d in r] == ["hello", "kursor"]
    asyncio.run(main())


def test_kursor_cichego_watku_idzie_naprzod():
    """Klient patrzy na cichy wątek, inne wątki mówią: każde wznowienie przesuwa jego kursor (ramka `kursor`), więc
    nie wypada z pierścienia i nie dostaje `reset` bez powodu."""
    async def main():
        hub = st.Hub(pojemnosc=50, zycie=0.05, ping=1)
        kursor = _ramki(await _czytaj(hub.polacz("k_dddddd", ["w_a"], None)))[0][0]
        for _cykl in range(3):
            for i in range(30):
                hub.nadaj("przebieg.delta", {"tekst": str(i)}, watek_id="w_b")
            r = _ramki(await _czytaj(hub.polacz("k_dddddd", ["w_a"], kursor)))
            assert [t for _i, t, _d in r] == ["hello", "kursor"], r
            kursor = r[-1][0]
            assert kursor == hub.kursor()
    asyncio.run(main())


def test_przepelnienie_reset_z_seq_ramki_ktora_sie_nie_zmiescila(monkeypatch):
    async def main():
        monkeypatch.setattr(st, "KOLEJKA", 3)
        hub = st.Hub(zycie=0.2, ping=1)
        pol = hub.polacz("k_ffffff", ["w_1"], None)
        for i in range(6):                              # sześć ramek, zanim pętla serwera cokolwiek wstawi
            hub.nadaj("przebieg.delta", {"tekst": str(i)}, watek_id="w_1")
        await asyncio.sleep(0.01)                       # pętla wstawia ramki: hello, 1, 2, przepełnienie przy 3
        r = [(i, t) for i, t, _d in _ramki(await _czytaj(pol))]
        e = hub.epoka
        assert r == [(f"{e}.3", "reset"), (f"{e}.4", "przebieg.delta"), (f"{e}.5", "przebieg.delta"),
                     (f"{e}.6", "przebieg.delta")]
        # spóźniona ramka sprzed resetu (drugi wątek nadawał równolegle) nie przychodzi po nim
        pol = hub.polacz("k_ffffff", ["w_1"], None)
        pol._wstaw(b"x", 10)                              # w kolejce: hello, x, y
        pol._wstaw(b"y", 11)
        pol._wstaw(b"z", 12)                              # przepełnienie: reset od 12
        pol._wstaw(b"o", 13)
        pol._wstaw(b"spozniona", 11)
        assert list(pol.kolejka) == [b"o"] and pol._reset_kursor == f"{e}.12"
    asyncio.run(main())


def test_wznowienie_ze_starym_url_nie_przywraca_zamknietego_watku():
    async def main():
        hub = st.Hub(zycie=0.05, ping=1)
        pol = hub.polacz("k_gggggg", ["w_a"], None)
        kursor = hub.kursor()
        assert hub.subskrybuj("k_gggggg", watki=["w_b"])                 # właściciel zamknął w_a, otworzył w_b
        hub.rozlacz("k_gggggg", pol)
        assert hub.subskrybowane_watki() == {"w_b"}
        pol = hub.polacz("k_gggggg", ["w_a"], kursor)                     # przeglądarka: pierwotny URL
        assert hub.subskrybowane_watki() == {"w_b"} and pol.watki == {"w_b"}
        hub.nadaj("przebieg.delta", {"tekst": "a"}, watek_id="w_a")
        hub.nadaj("przebieg.delta", {"tekst": "b"}, watek_id="w_b")
        await asyncio.sleep(0.01)
        r = [d.get("tekst") for _i, t, d in _ramki(b"".join(x for x in pol.kolejka if isinstance(x, bytes)))
             if t == "przebieg.delta"]
        assert r == ["b"]
        hub.rozlacz("k_gggggg", pol)
        pol = hub.polacz("k_gggggg", ["w_c"], None)                       # klient otworzył strumień sam: nowy URL
        assert pol.watki == {"w_c"} and hub.subskrybowane_watki() == {"w_c"}
        # POST przed pierwszym połączeniem klienta (wyścig na starcie strony): nie ginie, suma z URL-em
        assert hub.subskrybuj("k_hhhhhh", watki=["w_d"]) is False
        pol = hub.polacz("k_hhhhhh", ["w_e"], None)
        assert pol.watki == {"w_d", "w_e"}
    asyncio.run(main())


def test_limit_strumieni_i_pamiec_subskrypcji(monkeypatch):
    async def main():
        monkeypatch.setattr(st, "POLACZENIA_MAKS", 3)
        hub = st.Hub(zycie=5, ping=5)
        pol = [hub.polacz(f"k_{i:06d}", [], None) for i in range(5)]
        await asyncio.sleep(0.01)                       # zamknięcie idzie przez pętlę połączenia
        assert hub.liczba_polaczen() == 3 and all(p._zamkniete for p in pol[:2])  # najstarsze zamknięte
        for p in pol[2:]:
            hub.rozlacz(p.klient, p)
        # subskrypcja bez żywego połączenia zostaje zapamiętana (ponowne połączenie z pierwotnym URL)
        assert hub.subskrybuj("k_zzzzzz", watki=["w_q"]) is False   # bez strumienia: False, ale zapamiętana
        assert "w_q" in hub.subskrybowane_watki()
        for i in range(250):
            hub.subskrybuj(f"k_s{i:05d}", watki=[f"w_{i}"])
        assert len(hub._subskrypcje) <= 200
    asyncio.run(main())


def test_bufor_ograniczony_bajtami(monkeypatch):
    monkeypatch.setattr(st, "BAJTY_MAKS", 10_000)
    hub = st.Hub(zycie=5, ping=5)
    for i in range(100):
        hub.nadaj("przebieg.delta", {"tekst": "x" * 500, "i": i}, watek_id="w_1")
    assert hub._bajty <= 10_000 + 1000 and len(hub._bufor) < 100
    assert hub._bajty == sum(len(r) for *_x, r in hub._bufor)
