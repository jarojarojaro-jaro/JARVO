"""hq/plugin/czytnik_omp.py: aktywna gałąź, obwiednie skrzynki, kompresja kroków, brak wyników i argumentów narzędzi
na osi, szczegóły kroku na żądanie (z offsetów, przyrostowo), nieznany format, odczyt przyrostowy."""
from __future__ import annotations

import json

import pytest

from conftest import load_script

cz = load_script("hq/plugin/czytnik_omp.py", "jarvo_test_czytnik_omp")


def msg(i, rodzic, rola, tresc, **reszta):
    return {"type": "message", "id": i, "parentId": rodzic, "timestamp": f"t{i}",
            "message": {"role": rola, "content": tresc, **reszta}}


def zapisz(plik, wpisy):
    with plik.open("a", encoding="utf-8") as f:
        for w in wpisy:
            f.write(json.dumps(w, ensure_ascii=False) + "\n")


@pytest.fixture(autouse=True)
def _czysto():
    cz.zapomnij()


def sesja(tmp_path):
    p = tmp_path / "2026_01a13b13.jsonl"
    zapisz(p, [
        {"type": "title", "v": 1, "title": "x"},
        {"type": "session", "version": 3, "id": "01a13b13", "timestamp": "t", "cwd": "/tmp", "parentSession": "01a0"},
        msg("u1", None, "user", [{"type": "text", "text":
            "Wiadomości od właściciela (panel, telegram). Zrób je.\n\n[Panel · gpu · 2026-11-17 · wiadomość 1/2]\n"
            "sprawdź GPU\n\n---\n\n[Telegram · gpu · 2026-11-17 · wiadomość 2/2]\nlink"}]),
        msg("a1", "u1", "assistant", [{"type": "thinking", "thinking": "myślę SEKRET"},
                                      {"type": "toolCall", "id": "c1", "name": "bash", "intent": "Sprawdzam GPU",
                                       "arguments": {"command": "cat SEKRET"}}]),
        msg("r1", "a1", "toolResult", [{"type": "text", "text": "SEKRET wynik"}], toolCallId="c1"),
        msg("a2", "r1", "assistant", [{"type": "toolCall", "id": "c2", "name": "read", "intent": "Czytam log",
                                       "arguments": {"path": "/SEKRET"}}]),
        msg("r2", "a2", "toolResult", [{"type": "text", "text": "SEKRET"}]),
        msg("x1", "r2", "assistant", [{"type": "text", "text": "porzucona gałąź"}]),
        {"type": "compaction", "id": "c9", "parentId": "r2", "timestamp": "t", "shortSummary": "streszczenie",
         "summary": "długie SEKRET", "tokensBefore": 611035, "tokensAfter": 43506},
        msg("a3", "c9", "assistant", [{"type": "text", "text": "Plan: restart bramy. [[czeka-na-tak]]"}]),
        msg("u2", "a3", "user", [{"type": "text", "text": "tak z terminala"}]),
    ])
    return p


def test_os_aktywnej_galezi_bez_wynikow_narzedzi(tmp_path):
    o = cz.os_sesji(sesja(tmp_path))
    assert o["blad"] is None and o["pelny"] is True and o["sesja"] == "01a13b13"
    assert [w["typ"] for w in o["wpisy"]] == ["uzytkownik", "kroki", "streszczenie", "asystent", "uzytkownik"]
    u, kroki, s, a, t = o["wpisy"]
    assert (s["przed"], s["po"]) == (611035, 43506)               # panel pisze „611k → 44k”
    assert u["zrodlo"] == "panel" and u["tekst"] == "sprawdź GPU\n\nlink"
    assert kroki["kroki"] == [{"nazwa": "bash", "intencja": "Sprawdzam GPU", "id": "c1", "wpis": "a1"},
                              {"nazwa": "read", "intencja": "Czytam log", "id": "c2", "wpis": "a2"}]
    assert a["czeka_na_tak"] is True and a["tekst"] == "Plan: restart bramy."
    assert t["zrodlo"] == "terminal"
    calosc = json.dumps(o, ensure_ascii=False)
    assert "SEKRET" not in calosc and "porzucona" not in calosc


def test_przyrostowo_i_kompresja_bez_mutacji(tmp_path):
    p = sesja(tmp_path)
    cz.os_sesji(p)
    zapisz(p, [msg("a4", "u2", "assistant", [{"type": "toolCall", "id": "c", "name": "grep", "intent": "Szukam",
                                              "arguments": {}}]),
               msg("a5", "a4", "assistant", [{"type": "text", "text": "Znalazłem."}])])
    o1 = cz.os_sesji(p)
    o2 = cz.os_sesji(p)
    assert o1 == o2 and o1["wpisy"][-1]["tekst"] == "Znalazłem." and o1["wpisy"][-2]["kroki"][0]["nazwa"] == "grep"
    assert len(cz.os_sesji(p, ostatnie=2)["wpisy"]) == 2


def test_nieznany_format(tmp_path):
    p = tmp_path / "s.jsonl"
    zapisz(p, [{"type": "session", "version": 99, "id": "x"}])
    assert cz.os_sesji(p)["blad"] == "nieznany format"
    q = tmp_path / "q.jsonl"
    zapisz(q, [msg("u1", None, "user", "bez nagłówka")])
    assert cz.os_sesji(q)["blad"] == "nieznany format"
    assert cz.os_sesji(tmp_path / "brak.jsonl")["blad"] == "brak pliku sesji"
    assert cz.os_sesji(None)["blad"] == "brak pliku sesji"


def test_partia_panel_i_telegram_z_kluczami(tmp_path):
    """Partia skrzynki: blok panelu niesie klucz (= id przebiegu), blok z Telegrama zostaje osobno (scalanie pokaże
    go jako dymek 📱, a wiadomość panelu pokazuje jej wpis)."""
    p = tmp_path / "2026_s2.jsonl"
    zapisz(p, [
        {"type": "session", "version": 3, "id": "s2", "timestamp": "t", "cwd": "/tmp"},
        msg("u1", None, "user", [{"type": "text", "text":
            "Wstęp.\n\n[Panel · op · 2026-11-17 12:00:00 · #p_abc123 · wiadomość 1/2]\nz panelu\n\n---\n\n"
            "[Telegram · op · 2026-11-17 12:00:01 · wiadomość 2/2]\nz telefonu"}]),
        msg("a1", "u1", "assistant", [{"type": "text", "text": "ok"}]),
    ])
    u, a = cz.os_sesji(p)["wpisy"]
    assert u["klucze"] == ["p_abc123"] and u["tekst"] == "z panelu\n\nz telefonu"
    assert u["bloki"] == [{"zrodlo": "panel", "tekst": "z panelu"}, {"zrodlo": "telegram", "tekst": "z telefonu"}]
    sc = load_script("hq/plugin/scalanie.py", "jarvo_test_czytnik_omp_scalanie")
    poz = sc.pozycje_omp({"klucz": "s:op"}, cz.os_sesji(p))
    assert [(x["rodzaj"], x.get("zrodlo"), x["tekst"]) for x in poz] == [("wlasciciel", "telegram", "z telefonu"),
                                                                           ("agent", None, "ok")]
    assert poz[1]["przebieg_id"] == "p_abc123" and poz[1]["przebiegi"] == ["p_abc123"]


def test_tresc_linkow_nie_w_dymku_wlasciciela():
    """20.11: panel pokazywał w dymku właściciela całą treść pobraną spod linku (i błąd pobierania), choć wysłał
    tylko link z dopiskiem. Dopisek skrzynki to kontekst dla modelu; załączniki po nim zostają."""
    from pathlib import Path
    zrodlo = (Path(__file__).resolve().parents[1] / "jarvo" / "sesje_omp.py").read_text(encoding="utf-8")
    assert f"\\n\\n{cz.ZNACZNIK_LINKOW}\\n" in zrodlo           # ten sam napis co w prompt() skrzynki
    tekst = ("Wiadomości od właściciela (telegram). Zrób je według zasad sesji. Na końcu jedna odpowiedź.\n\n"
             "[Telegram · gpu · 03:55 · wiadomość 1/1]\nhttps://x.com/a/status/1 o co w tym chodzi sprawdz dokladnie"
             f"\n\n{cz.ZNACZNIK_LINKOW}\n{{\"error\": \"pobieranie linków: brak pliku\"}}\n(załącznik: /tmp/a.jpg)")
    (blok,) = cz.bloki_obwiedni(tekst)
    assert blok["tekst"] == "https://x.com/a/status/1 o co w tym chodzi sprawdz dokladnie\n(załącznik: /tmp/a.jpg)"


def zapisz_zwarte(plik, wpisy):
    """Jak omp: JSON bez spacji (wyniki narzędzi idą szybką ścieżką, bez parsowania treści)."""
    with plik.open("a", encoding="utf-8") as f:
        for w in wpisy:
            f.write(json.dumps(w, ensure_ascii=False, separators=(",", ":")) + "\n")


def wpis(i, rodzic, rola, tresc, czas, **reszta):
    return {"type": "message", "id": i, "parentId": rodzic, "timestamp": czas,
            "message": {"role": rola, "content": tresc, **reszta}}


@pytest.mark.parametrize("zwarte", [False, True])
def test_szczegoly_kroku_na_zadanie_i_przyrostowo(tmp_path, monkeypatch, zwarte):
    """Rozwinięty krok: argumenty, myśl od poprzedniego wywołania, wynik dopiero, gdy dojdzie (przyrostowo, z offsetów);
    oś dalej bez argumentów i wyników, a linie wyników w zapisie omp nie są parsowane."""
    p = tmp_path / "2026_s3.jsonl"
    z = zapisz_zwarte if zwarte else zapisz
    z(p, [
        {"type": "session", "version": 3, "id": "s3", "timestamp": "2026-11-20T10:00:00Z", "cwd": "/tmp"},
        wpis("u1", None, "user", [{"type": "text", "text": "napraw"}], "2026-11-20T10:00:00Z"),
        wpis("a1", "u1", "assistant", [
            {"type": "thinking", "thinking": "Najpierw sprawdzę log."},
            {"type": "toolCall", "id": "c1", "name": "bash", "intent": "Czytam log",
             "arguments": {"command": "tail -n 5 log", "i": "Czytam log"}},
            {"type": "text", "text": "I jeszcze plik."},
            {"type": "toolCall", "id": "c2", "name": "edit", "intent": "Poprawiam", "arguments": {"path": "a.py"}}],
            "2026-11-20T10:00:01Z"),
    ])
    kroki = cz.os_sesji(p)["wpisy"][-1]["kroki"]
    assert [(k["id"], k["wpis"]) for k in kroki] == [("c1", "a1"), ("c2", "a1")]
    k1 = cz.szczegoly(p, "a1", "c1")
    assert (k1["argumenty"]["command"], k1["mysl"], k1["wynik"]) == ("tail -n 5 log", "Najpierw sprawdzę log.", None)
    k2 = cz.szczegoly(p, "a1", "c2")
    assert (k2["narzedzie"], k2["mysl"], k2["wynik"]) == ("edit", "I jeszcze plik.", None)

    parsowane = []
    skrot = cz._skrot
    monkeypatch.setattr(cz, "_skrot", lambda e: parsowane.append(e["id"]) or skrot(e))
    od = cz._PAMIEC[str(p)]["od"]
    z(p, [
        wpis("r1", "a1", "toolResult", [{"type": "text", "text": "linia 1\nlinia 2"}], "2026-11-20T10:00:03Z",
             toolCallId="c1", toolName="bash", details={"exitCode": 0, "wallTimeMs": 120}, isError=False),
        wpis("r2", "r1", "toolResult", [{"type": "text", "text": "Edit rejected"}], "2026-11-20T10:00:04Z",
             toolCallId="c2", toolName="edit", details={"diff": "-a\n+b"}, isError=True),
    ])
    k1 = cz.szczegoly(p, "a1", "c1")
    assert (k1["wynik"], k1["kod"], k1["czas_ms"], k1["blad"]) == ("linia 1\nlinia 2", 0, 120, False)
    k2 = cz.szczegoly(p, "a1", "c2")
    assert (k2["wynik"], k2["zmiana"], k2["blad"], k2["czas_ms"]) == ("Edit rejected", "-a\n+b", True, 3000)
    assert cz._PAMIEC[str(p)]["od"] > od                   # dopisane linie czytane od offsetu
    assert parsowane == ([] if zwarte else ["r1", "r2"])  # zapis omp: wyników nie parsujemy przy czytaniu osi
    assert cz.szczegoly(p, "a1", "c1") is k1               # gotowy krok z pamięci
    assert cz.szczegoly(p, "a1", "c9") is None and cz.szczegoly(p, "u1", "c1") is None
    assert cz.szczegoly(p, "brak", "c1") is None and cz.szczegoly(tmp_path / "brak.jsonl", "a1", "c1") is None
    assert "linia 1" not in json.dumps(cz.os_sesji(p))     # oś nadal bez wyników
