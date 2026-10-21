"""Czytnik sesji Hermesa (hq/plugin/czytnik.py): droga zapasowa na atrapie state.db (tests/stan_hermesa.py, schemat
zrzucony z obrazu) daje to, co projekcja Hermesa; state.db zostaje bajt w bajt ten sam. Porównanie z projekcją
Hermesa: tutaj, gdy Hermes jest do zaimportowania, a w kontenerze `python3 czytnik.py --porownaj` (docs/HQ.md)."""
import json
import sqlite3

import pytest

import stan_hermesa
from conftest import load_script

cz = load_script("hq/plugin/czytnik.py", "jarvo_test_czytnik")


@pytest.fixture
def baza(tmp_path):
    return stan_hermesa.zbuduj(tmp_path / "state.db")


def _skrot(wiersze):
    return [(w["id"], w["rola"], w["tresc"], w["rodzaj"], w["podsumowanie"]) for w in wiersze]


OCZEKIWANE_INDEKS = [
    (1, "user", "Zrób stronę dla piekarni", None, False),
    (2, "assistant", "", None, False),
    (3, "tool", "index.html", None, False),
    (4, "assistant", "Gotowe, strona jest.", None, False),
    (8, "user", "Dodaj stopkę", None, False),           # kopia ogona w nowym pokoleniu zastępuje wiersz 5
    (9, "assistant", "Dodam stopkę.", None, False),
    (7, "user", "", "hidden", True),                      # samo przekazanie po kompresji
    (10, "user", "Popraw to\n[screenshot]", None, False),
    (12, "assistant", "(podwójnie)", None, False),        # metadane zakodowane dwa razy: SQL Hermesa ich nie widzi
    (13, "assistant", stan_hermesa.NIEUDANA, "failed_turn", False),
    (14, "user", "dopisz NIP", "steer", False),
    (15, "user", "Background task finished: raport.md", "async_delegation_complete", False),
    (16, "user", "Wcześniejsza wiadomość", None, True),   # streszczenie scalone: zostaje prawdziwa treść
    (17, "user", "A teraz kolory?", None, True),          # znacznik końca: żywe pytanie po streszczeniu
    (19, "assistant", "Kolory zmienione.", None, False),
]


def test_sesja_z_indeksem_wyswietlania(baza):
    wiersze = cz.czytaj_zapasowo(baza, "s-indeks")
    assert _skrot(wiersze) == OCZEKIWANE_INDEKS
    pierwszy = wiersze[1]
    assert pierwszy["tool_calls"] == stan_hermesa.WYWOLANIE and pierwszy["skompaktowany"] and not pierwszy["aktywny"]
    assert wiersze[2]["tool_call_id"] == "call_1" and wiersze[2]["tool_name"] == "terminal"
    assert wiersze[-1]["meta"] == {"reactions": ["👍"]}
    assert all(set(w) == {"id", "sesja_id", "rola", "tresc", "tool_calls", "tool_call_id", "tool_name", "ts", "rodzaj",
                          "meta", "podsumowanie", "aktywny", "skompaktowany", "klucz"} for w in wiersze)
    assert len({w["klucz"] for w in wiersze}) == len(wiersze)


def test_stara_sesja_bez_indeksu_deduplikuje_po_tozsamosci(baza):
    wiersze = cz.czytaj_zapasowo(baza, "s-stara")
    # te same pozycje (id przesunięte o 19), ale „(podwójnie)” znika: Python Hermesa dekoduje metadane dwa razy
    oczekiwane = [(i + 19, *reszta) for i, *reszta in OCZEKIWANE_INDEKS if i != 12]
    assert _skrot(wiersze) == oczekiwane


def test_pusta_i_brakujaca_sesja(baza):
    assert cz.czytaj_zapasowo(baza, "s-pusta") == []
    assert cz.czytaj_zapasowo(baza, "s-nie-ma") is None


def test_odczyt_nie_zmienia_state_db(baza):
    przed = (baza.read_bytes(), baza.stat().st_mtime_ns, sorted(p.name for p in baza.parent.iterdir()))
    for sid in ("s-indeks", "s-stara", "s-pusta", "s-nie-ma"):
        cz.czytaj_zapasowo(baza, sid)
    cz.sprawdz_schemat(baza)
    assert (baza.read_bytes(), baza.stat().st_mtime_ns, sorted(p.name for p in baza.parent.iterdir())) == przed


def test_porownaj_bez_hermesa_mowi_ze_nierowne_ale_baza_bez_zmian(baza):
    if cz.hermes_dostepny():
        pytest.skip("Hermes jest do zaimportowania: test niżej porównuje naprawdę")
    wynik = cz.porownaj(baza, "s-indeks")
    assert wynik["state_db_bez_zmian"] and wynik["zapasowo"] == len(OCZEKIWANE_INDEKS)
    assert not wynik["rowne"] and wynik["blad_hermesa"]


@pytest.mark.skipif(not cz.hermes_dostepny(), reason="Hermes nie do zaimportowania (porównanie w kontenerze)")
@pytest.mark.parametrize("sid", ["s-indeks", "s-stara", "s-pusta", "s-nie-ma"])
def test_projekcja_hermesa_rowna_zapasowej(baza, sid):
    wynik = cz.porownaj(baza, sid)
    assert wynik["rowne"] and wynik["state_db_bez_zmian"], wynik


def test_streszczenia_i_nieudana_tura_jak_w_hermesie():
    assert cz.czy_streszczenie("[CONTEXT SUMMARY]: x")
    assert cz.czy_streszczenie(f"poprzednie\n{cz.GRANICA_SCALENIA}\n[CONTEXT COMPACTION — REFERENCE ONLY] …")
    assert not cz.czy_streszczenie(f"poprzednie\n{cz.GRANICA_SCALENIA}\nzwykły tekst")
    assert not cz.czy_streszczenie("cytuję [CONTEXT SUMMARY]: w środku")
    m = cz.projektuj({"role": "assistant", "content": f"  {cz.NIEUDANA_TURA[1]}\n"})
    assert m["display_kind"] == "failed_turn"
    # odpowiedź, która tylko cytuje komunikat, zostaje odpowiedzią; oznaczony wiersz nie dostaje nowego typu
    assert "display_kind" not in cz.projektuj({"role": "assistant", "content": "Hermes: " + cz.NIEUDANA_TURA[0]})
    assert cz.projektuj({"role": "assistant", "content": cz.NIEUDANA_TURA[0], "display_kind": "x"})["display_kind"] == "x"
    # streszczenie z typem innym niż hidden i bez treści do pokazania zachowuje swój typ
    assert cz.projektuj({"role": "user", "content": "[CONTEXT SUMMARY]: a", "display_kind": "auto_continue"}
                        )["display_kind"] == "auto_continue"


def test_tekst_tresci_z_obrazami():
    assert cz.tekst_tresci([{"type": "text", "text": "Popraw"}, {"type": "image_url", "image_url": {"url": "x"}},
                            {"type": "input_image"}]) == "Popraw\n[screenshot]\n[screenshot]"
    assert cz.tekst_tresci(None) == "" and cz.tekst_tresci(5) == "5"


def test_tresc_listowa_zakodowana_przez_hermesa(tmp_path):
    baza = stan_hermesa.zbuduj(tmp_path / "state.db")
    conn = sqlite3.connect(baza)
    czesci = [{"type": "text", "text": "z obrazem"}, {"type": "image_url", "image_url": {"url": "data:,"}}]
    conn.execute("INSERT INTO messages (session_id, role, content, timestamp) VALUES ('s-pusta', 'user', ?, 5.0)",
                 (cz.PREFIKS_JSON + json.dumps(czesci),))
    conn.commit()
    conn.close()
    (w,) = cz.czytaj_zapasowo(baza, "s-pusta")
    assert w["tresc"] == "z obrazem\n[screenshot]"


def test_czytnik_profili_sprawdza_nazwe_i_schemat(tmp_path):
    root = tmp_path / "profiles"
    (root / "test-e2e-a").mkdir(parents=True)
    stan_hermesa.zbuduj(root / "test-e2e-a" / "state.db")
    logi = []
    c = cz.Czytnik(root, lambda: ["test-e2e-a", "jarvo-web"], tryb="zapasowy", log=logi.append)
    assert c.tryb == "zapasowy"
    assert _skrot(c.sesja("test-e2e-a", "s-indeks")) == OCZEKIWANE_INDEKS
    assert c.sesja("jarvo-web", "s-indeks") is None                     # profil bez state.db
    linia = c.linia("test-e2e-a", ["s-nie-ma", "s-pusta"])
    assert [(x["sesja_id"], x["stan"]) for x in linia] == [("s-nie-ma", cz.BRAK_SESJI), ("s-pusta", "ok")]
    for zly in ("jarvo-reka", "../etc", "Test", ""):
        with pytest.raises(ValueError):
            c.sesja(zly, "s-indeks")
    # schemat po aktualizacji Hermesa bez wymaganej kolumny
    (root / "jarvo-web").mkdir()
    conn = sqlite3.connect(root / "jarvo-web" / "state.db")
    conn.executescript("CREATE TABLE sessions (id TEXT); CREATE TABLE messages (id INTEGER, session_id TEXT);")
    conn.close()
    with pytest.raises(cz.SchematZmieniony):
        c.sesja("jarvo-web", "x")
    assert "messages.display_order" in c.schemat("jarvo-web")


def test_schemat_atrapy_ma_wymagane_kolumny(baza):
    assert cz.sprawdz_schemat(baza) == []


def test_tryb_auto_bez_hermesa_to_zapasowy(tmp_path):
    if cz.hermes_dostepny():
        pytest.skip("Hermes dostępny")
    assert cz.Czytnik(tmp_path, lambda: [], tryb="auto").tryb == "zapasowy"
    with pytest.raises(RuntimeError):
        cz.Czytnik(tmp_path, lambda: [], tryb="hermes")
    with pytest.raises(ValueError):
        cz.Czytnik(tmp_path, lambda: [], tryb="inny")


def test_cli(baza, capsys):
    assert cz.main(["--schemat", str(baza)]) == 0
    assert cz.main(["--zapasowo", str(baza), "s-pusta"]) == 0
    assert "[]" in capsys.readouterr().out
