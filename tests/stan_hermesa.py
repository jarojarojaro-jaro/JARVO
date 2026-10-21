"""Atrapa state.db profilu Hermesa dla testów czytnika i importu rozmów (schemat z tests/data/hermes_state_schema.sql,
zrzucony z obrazu jarvo-hermes). `zbuduj(sciezka)` tworzy bazę z trzema sesjami:

- `s-indeks`: sesja z pełnym indeksem wyświetlania (`display_identity` jak w Hermesie, `display_order` z wyzwalacza):
  pokolenie kompresji (ogon chroniony skopiowany do nowego pokolenia), streszczenie samodzielne (ukryte), streszczenie
  scalone z poprzednią treścią i ze znacznikiem końca, wiersz `model_only` (pominięty) i drugi z metadanymi
  zakodowanymi dwa razy (SQL go nie rozpoznaje, więc zostaje, jak w Hermesie), nieudana tura bez typu, `steer`,
  `async_delegation_complete`, wiadomość z `[screenshot]`, wiersz cofnięty (active = 0, compacted = 0);
- `s-stara`: ta sama historia bez `display_identity` (stara sesja sprzed indeksu: deduplikacja po tożsamości);
- `s-pusta`: sesja bez wiadomości.
Uruchomione jako skrypt zapisuje bazę pod podaną ścieżką (porównanie z projekcją Hermesa w kontenerze).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

SCHEMAT = Path(__file__).resolve().parent / "data" / "hermes_state_schema.sql"
NIEUDANA = "Your request was not processed. Send it again if you still want me to carry it out."
STRESZCZENIE = "[CONTEXT SUMMARY]: Właściciel prosił o stronę piekarni; strona gotowa."
GRANICA = "[END OF PRIOR CONTEXT — COMPACTION SUMMARY BELOW]"
NAGLOWEK = "[PRIOR CONTEXT — for reference only; not a new message]"
KONIEC = "--- END OF CONTEXT SUMMARY — respond to the message below, not the summary above ---"
WYWOLANIE = [{"id": "call_1", "type": "function", "function": {"name": "terminal", "arguments": "{\"command\": \"ls\"}"}}]


def _tozsamosc(rola, tresc, ts, tool_call_id, tool_calls, tool_name) -> bytes:
    """Jak SessionDB._display_identity(_display_dedupe_key(row)) dla zwykłych wierszy."""
    return hashlib.sha256(repr((rola, tresc, ts, tool_call_id, tool_calls, tool_name)).encode("utf-8")).digest()


def _historia() -> list[dict]:
    """(pokolenie 1: skompaktowane) + (pokolenie 2: aktywne). Ogon 5–6 skopiowany jako 8–9."""
    tc = json.dumps(WYWOLANIE)
    g1 = dict(active=0, compacted=1)
    g2 = dict(active=1, compacted=0)
    return [
        dict(role="user", content="Zrób stronę dla piekarni", timestamp=100.0, **g1),
        dict(role="assistant", content="", tool_calls=tc, timestamp=101.0, **g1),
        dict(role="tool", content="index.html", tool_call_id="call_1", tool_name="terminal", timestamp=102.0, **g1),
        dict(role="assistant", content="Gotowe, strona jest.", timestamp=103.0, **g1),
        dict(role="user", content="Dodaj stopkę", timestamp=104.0, **g1),
        dict(role="assistant", content="Dodam stopkę.", timestamp=105.0, **g1),
        dict(role="user", content=STRESZCZENIE, _compressed_summary=1, timestamp=106.0, **g2),
        dict(role="user", content="Dodaj stopkę", timestamp=104.0, **g2),
        dict(role="assistant", content="Dodam stopkę.", timestamp=105.0, **g2),
        dict(role="user", content="Popraw to\n[screenshot]", timestamp=107.0, **g2),
        dict(role="assistant", content="(dla modelu)", display_metadata=json.dumps({"model_only": True}),
             timestamp=108.0, **g2),
        dict(role="assistant", content="(podwójnie)", display_metadata=json.dumps(json.dumps({"model_only": True})),
             timestamp=108.5, **g2),
        dict(role="assistant", content=NIEUDANA, timestamp=109.0, **g2),
        dict(role="user", content="dopisz NIP", display_kind="steer", timestamp=110.0, **g2),
        dict(role="user", content="Background task finished: raport.md", display_kind="async_delegation_complete",
             timestamp=111.0, **g2),
        dict(role="user", content=f"{NAGLOWEK}\nWcześniejsza wiadomość\n{GRANICA}\n{STRESZCZENIE}", timestamp=112.0, **g2),
        dict(role="user", content=f"{STRESZCZENIE}\n{KONIEC}\nA teraz kolory?", _compressed_summary=1,
             timestamp=113.0, **g2),
        dict(role="assistant", content="cofnięte", timestamp=114.0, active=0, compacted=0),
        dict(role="assistant", content="Kolory zmienione.", display_metadata=json.dumps({"reactions": ["👍"]}),
             timestamp=115.0, **g2),
    ]


def _wstaw(conn, sid: str, wiersze: list[dict], *, indeks: bool) -> None:
    for w in wiersze:
        w = {"tool_call_id": None, "tool_calls": None, "tool_name": None, **w}
        ident = (_tozsamosc(w["role"], w["content"], w["timestamp"], w["tool_call_id"], w["tool_calls"], w["tool_name"])
                 if indeks else None)
        pola = {**w, "session_id": sid, "display_identity": ident}
        conn.execute(f"INSERT INTO messages ({', '.join(pola)}) VALUES ({', '.join('?' * len(pola))})",
                     tuple(pola.values()))


def zbuduj(sciezka: Path | str, *, sesje_uzytkownika: dict[str, str] | None = None) -> Path:
    """Baza z sesjami s-indeks, s-stara i s-pusta (+ `sesje_uzytkownika` = {id: tekst} z jedną wiadomością
    właściciela i odpowiedzią, np. do importu hq-sessions.json). Tryb dziennika DELETE: odczyt `mode=ro` nie
    tworzy plików -wal ani -shm."""
    sciezka = Path(sciezka)
    conn = sqlite3.connect(sciezka)
    conn.executescript(SCHEMAT.read_text(encoding="utf-8"))
    conn.execute("INSERT INTO schema_version (version) VALUES (30)")
    for i, sid in enumerate(("s-indeks", "s-stara", "s-pusta")):
        conn.execute("INSERT INTO sessions (id, source, title, started_at, last_activity_at) VALUES (?, 'api_server', ?, ?, ?)",
                     (sid, f"Sesja {sid}", 90.0 + i, 120.0 + i))
    _wstaw(conn, "s-indeks", _historia(), indeks=True)
    _wstaw(conn, "s-stara", _historia(), indeks=False)
    for j, (sid, tekst) in enumerate((sesje_uzytkownika or {}).items()):
        conn.execute("INSERT INTO sessions (id, source, title, started_at, last_activity_at) VALUES (?, 'api_server', ?, ?, ?)",
                     (sid, f"Baza {sid}", 1000.0 + j, 2000.0 + j))
        _wstaw(conn, sid, [dict(role="user", content=tekst, timestamp=1000.5 + j, active=1, compacted=0),
                           dict(role="assistant", content="ok", timestamp=1001.0 + j, active=1, compacted=0)], indeks=True)
    conn.commit()
    conn.close()
    return sciezka


if __name__ == "__main__":
    print(zbuduj(sys.argv[1]))
