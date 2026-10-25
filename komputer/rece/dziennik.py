"""Dziennik rąk `<stan>/rece/dziennik.jsonl`: kto, kiedy i co zdecydowano, bez treści.

Jeden obiekt JSON na wiersz: czas, zdarzenie (on, off, serve, serve_odmowa, mcp, narzedzie, stop, koniec) i tylko
pola z listy POLA. Nigdy wpisywany tekst (zostaje liczba znaków), zawartość ekranu, tytuły okien, adresy ani
sekrety: wartości to nazwy narzędzi, kody decyzji, nazwy aplikacji podane przez właściciela, klawisze skrótów
i liczby. Plik do 2 MB i jedna kopia (`dziennik.jsonl.1`), zapis pod blokadą (kilka procesów bramki naraz).
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

MAKS = 2 * 1024 * 1024
POLA = frozenset({"zgoda", "profil", "aplikacje", "aplikacja", "do", "na", "narzedzie", "decyzja", "kod", "znaki",
                  "klawisze", "pid", "sterownik", "powod", "zatrzymane", "platforma"})
KLAWISZ = re.compile(r"^[A-Za-z0-9_+\- ]{1,24}$")


def _czysty(wartosc, glebokosc: int = 0):
    if isinstance(wartosc, bool) or isinstance(wartosc, (int, float)) or wartosc is None:
        return wartosc
    if isinstance(wartosc, str):
        tekst = "".join(z for z in wartosc if z >= " " and z != "\x7f")
        return tekst[:120]
    if isinstance(wartosc, (list, tuple)) and glebokosc < 1:
        return [_czysty(w, glebokosc + 1) for w in list(wartosc)[:20]]
    return str(type(wartosc).__name__)


def klawisze(args: dict) -> list[str]:
    """Klawisze z press_key i hotkey (nazwy klawiszy, nie tekst); inne wartości zastępuje „?”."""
    surowe = args.get("keys") if isinstance(args.get("keys"), list) else [args.get("key")]
    return [str(k) if isinstance(k, str) and KLAWISZ.match(k) else "?" for k in surowe if k is not None][:8]


def zapisz(plik: Path, zdarzenie: str, **pola) -> None:
    from jarvo import przenosne
    wpis = {"czas": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "zdarzenie": str(zdarzenie)[:40]}
    wpis.update({k: _czysty(v) for k, v in pola.items() if k in POLA and v is not None})
    wiersz = json.dumps(wpis, ensure_ascii=False) + "\n"
    plik = Path(plik)
    if not plik.parent.parent.is_dir():
        return                                  # bez instalacji Jarva (brak <stan>) nie zakładamy katalogów
    try:
        plik.parent.mkdir(exist_ok=True)
        with przenosne.Zamek(plik.with_name(plik.name + ".lock")):
            try:
                if plik.stat().st_size + len(wiersz) > MAKS:
                    os.replace(plik, plik.with_name(plik.name + ".1"))
            except FileNotFoundError:
                pass
            with open(plik, "a", encoding="utf-8", newline="\n") as f:
                f.write(wiersz)
    except OSError:
        pass                                    # dziennik nie zatrzymuje rąk ani ich wyłączenia


def ostatnie(plik: Path, n: int = 10) -> list[dict]:
    try:
        wiersze = Path(plik).read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, n):]
    except OSError:
        return []
    wynik = []
    for w in wiersze:
        try:
            wynik.append(json.loads(w))
        except ValueError:
            continue
    return wynik
