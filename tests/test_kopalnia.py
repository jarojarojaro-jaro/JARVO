"""Kopalnia pomysłów: materiał do porannego briefu bez modelu (profiles/jarvo/scripts/kopalnia.py)."""

from __future__ import annotations

import datetime as dt
import os
import sqlite3

from conftest import load_script

kopalnia = load_script("profiles/jarvo/scripts/kopalnia.py")

TERAZ = dt.datetime(2026, 11, 18, 7, 50)          # środa
KLUCZ = "sk_live_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6"


def _baza(dane, wiadomosci):
    baza = dane / "profiles" / "jarvo" / "state.db"
    baza.parent.mkdir(parents=True)
    conn = sqlite3.connect(baza)
    conn.execute("CREATE TABLE sessions (id TEXT, source TEXT)")
    conn.execute("CREATE TABLE messages (session_id TEXT, role TEXT, content TEXT, timestamp REAL, tool_calls TEXT)")
    for i, (zrodlo, rola, tresc, godzin_temu) in enumerate(wiadomosci):
        conn.execute("INSERT INTO sessions VALUES (?, ?)", (f"s{i}", zrodlo))
        conn.execute("INSERT INTO messages VALUES (?, ?, ?, ?, NULL)",
                     (f"s{i}", rola, tresc, TERAZ.timestamp() - godzin_temu * 3600))
    conn.commit()
    conn.close()


def test_tylko_wiadomosci_wlasciciela_z_okna_i_bez_kluczy(tmp_path):
    _baza(tmp_path, [
        ("telegram", "user", "agent od kerneli ma wiedzieć sam https://x.com/a/status/2121352628915593422", 3),
        ("telegram", "user", f"klucz to {KLUCZ} a hasło: Tajne123!", 5),
        ("telegram", "assistant", "odpowiedź Jarva", 3),
        ("kanban", "user", "KONTEKST karty dla pracownika", 2),
        ("cli", "user", "test operatora z terminala", 2),
        ("oneshot", "user", "jarvo chat -q operatora", 2),
        ("cron", "user", "Przygotuj poranny brief", 1),
        ("telegram", "user", "stara wiadomość sprzed okna", 60),
    ])
    w = kopalnia.wiadomosci_wlasciciela(tmp_path, TERAZ.timestamp() - 48 * 3600)
    teksty = [x["tekst"] for x in w]
    assert len(teksty) == 2
    assert teksty[0] == "klucz to [ukryte] a hasło: [ukryte]"                  # najstarsza pierwsza
    assert "x.com/a/status/2121352628915593422" in teksty[1]       # link zostaje, choć ma długi numer
    assert all(x["skad"] == "telegram" for x in w)


def test_poniedzialek_obejmuje_weekend():
    assert kopalnia.okno_godzin(dt.datetime(2026, 11, 16, 7, 50)) == 72
    assert kopalnia.okno_godzin(TERAZ) == 48


def test_wczesniejsze_pomysly_z_odpowiedzia(tmp_path):
    (tmp_path / "briefy").mkdir()
    (tmp_path / "briefy" / "B-2026-11-16.md").write_text(
        "| Numer | Decyzja | Odpowiedź właściciela | Kiedy | Co zrobione |\n|---|---|---|---|---|\n"
        "| B-2026-11-16/1 | Publikacja posta? Rekomenduję tak. | ok | 2026-11-16 | karta t_1 |\n"
        "| B-2026-11-16/2 | 🛠 Zbudować arsenał dla floty: 14.11 prośba o InstaBox. Rekomenduję tak. | nie, za wcześnie "
        "| 2026-11-16 |  |\n", encoding="utf-8")
    (tmp_path / "briefy" / "B-2026-09-01.md").write_text(
        "| B-2026-09-01/1 | 🛠 Zbudować stary pomysł. | | | |\n", encoding="utf-8")
    p = kopalnia.pomysly_wczesniej(tmp_path, TERAZ.date())
    assert [x["numer"] for x in p] == ["B-2026-11-16/2"]
    assert p[0]["odpowiedz"] == "nie, za wcześnie"


def test_skille_floty_bez_skilli_hermesa(tmp_path):
    def skill(profil, sciezka, fm):
        p = tmp_path / "profiles" / profil / "skills" / sciezka / "SKILL.md"
        p.parent.mkdir(parents=True)
        p.write_text(f"---\n{fm}\n---\n# x\n", encoding="utf-8")
    skill("jarvo-wideo", "wideo/film", 'name: film\ndescription: "Film od zera."\nmetadata:\n  jarvo:\n    agent: jarvo-wideo')
    skill("jarvo-wideo", "creative/manim-video", 'name: manim-video\ndescription: "Hermes."\nmetadata:\n  hermes:\n    tags: []')
    assert kopalnia.skille_floty(tmp_path) == {"jarvo-wideo": ["film: Film od zera."]}


def test_notatki_zmienione_bez_briefow_i_plikow_technicznych(tmp_path):
    stare = TERAZ.timestamp() - 100 * 3600
    for rel, czas in [("flota/instabox.md", TERAZ.timestamp()), ("flota/stara.md", stare),
                      ("briefy/B-2026-11-18.md", TERAZ.timestamp()), ("LOG.md", TERAZ.timestamp()),
                      ("zrodla/jarvo-repo/SOUL.md", TERAZ.timestamp()), ("fleet/skille/film.md", TERAZ.timestamp()),
                      ("flota/_hub-flota.md", TERAZ.timestamp())]:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
        os.utime(p, (czas, czas))
    assert kopalnia.notatki_zmienione(tmp_path, TERAZ.timestamp() - 48 * 3600) == {"liczba": 1, "sciezki": ["flota/instabox"]}
