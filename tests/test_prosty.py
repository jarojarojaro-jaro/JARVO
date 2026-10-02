"""Prosty polski (profiles/jarvo/scripts/prosty.py): limity, słownik ze skilla, strona bierna, łańcuchy rzeczowników
i liczby tygodnia z bazy sesji Jarva (tylko wiadomości do właściciela)."""

from __future__ import annotations

import json
import sqlite3

from conftest import load_script

p = load_script("profiles/jarvo/scripts/prosty.py", "jarvo_prosty_test")

URZEDOWE = ("W związku z powyższym dokonano weryfikacji wdrożenia, które zostało zrealizowane w ramach misji M-12, "
            "w celu zapewnienia poprawności działania formularza kontaktowego na stronie.")


def typy(w):
    return {u["typ"] for u in w["uwagi"]}


def test_urzedowe_zdanie_i_prosta_wersja():
    w = p.sprawdz(URZEDOWE)
    assert {"strona bierna", "łańcuch rzeczowników", "„dokona…”", "„w celu…”", "„zrealizowa…”"} <= typy(w)
    assert p.sprawdz("Sprawdziłem wdrożenie z misji M-12. Formularz kontaktowy działa.")["ok"]


def test_limity_skroty_i_kod():
    dlugie = " ".join(["słowo"] * 26) + "."
    assert typy(p.sprawdz(dlugie)) == {"za długie zdanie"}
    akapit = " ".join(f"Zdanie numer {i}." for i in range(7))
    assert typy(p.sprawdz(akapit)) == {"za długi akapit"}
    # skróty nie kończą zdania; kod, tabele i listy nie liczą się jako akapit urzędowy
    w = p.sprawdz("Strona ma np. 3 sekcje, tj. ofertę. Skill `w celu-test` zostaje.\n\n| w celu | x |\n\n```\nw celu\n```")
    assert w["ok"] and w["zdania"] == 2
    lista = "\n".join(f"- punkt {i}. Krótki." for i in range(8))
    assert p.sprawdz(lista)["ok"]                                     # punkt listy to osobny akapit


def test_slownik_ze_skilla_bez_falszywych_alarmow():
    s = p.slownik()
    assert len(s) > 20 and any(z == "w celu" for _w, z, _p in s)
    # „celem” (rzeczownik) i „bądź” (tryb rozkazujący) nie są urzędowe
    assert p.sprawdz("Celem misji jest strona. Bądź spokojny, działa.")["ok"]


def test_tydzien_z_bazy_sesji(tmp_path):
    baza = tmp_path / "profiles" / "jarvo" / "state.db"
    baza.parent.mkdir(parents=True)
    c = sqlite3.connect(baza)
    c.execute("CREATE TABLE sessions (id TEXT, source TEXT)")
    c.execute("CREATE TABLE messages (session_id TEXT, role TEXT, content TEXT, tool_calls TEXT, timestamp REAL)")
    c.executemany("INSERT INTO sessions VALUES (?, ?)", [("t", "telegram"), ("k", "kanban"), ("c", "cron")])
    now = 1_000_000.0
    c.executemany("INSERT INTO messages VALUES (?, ?, ?, ?, ?)", [
        ("t", "assistant", "Web skończył stronę. Sprawdzam jakość.", None, now - 100),
        ("t", "assistant", URZEDOWE, None, now - 200),
        ("t", "assistant", "szukam", json.dumps([{"id": 1}]), now - 300),      # wywołanie narzędzia: pomijamy
        ("c", "assistant", "[SILENT]", None, now - 400),
        ("k", "assistant", URZEDOWE, None, now - 500),                          # sędzia na tablicy: nie do właściciela
        ("t", "assistant", URZEDOWE, None, now - 8 * 86400),                    # starsze niż tydzień
        ("t", "user", URZEDOWE, None, now - 50)])
    c.commit()
    c.close()
    w = p.tydzien(tmp_path, now)
    assert (w["wiadomosci"], w["w_normie"]) == (2, 1) and len(w["najczestsze"]) == 3
    assert p.tydzien(tmp_path / "brak", now) == {"wiadomosci": 0, "w_normie": 0, "najczestsze": []}


def test_cli(capsys):
    assert p.main(["--tekst", URZEDOWE]) == 1
    out = capsys.readouterr().out.strip().splitlines()
    assert out[0].startswith("✗ potknięcia") and json.loads(out[-1])["ok"] is False
    assert p.main(["--tekst", "Działa."]) == 0
