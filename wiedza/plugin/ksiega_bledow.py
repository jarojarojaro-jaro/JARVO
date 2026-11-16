"""Księga błędów pod wynikiem narzędzia (hak `transform_tool_result`, docs/WIEDZA.md §4b).

Właściciel 17.11: agent, który trafia na błąd, ma najpierw sprawdzić, czy to już było, i zrobić to poprawnie, a nie
powtarzać go (16.11 Jarvo godzinę klikał to samo okienko Turnstile i nic nie powiedział). Hak dopisuje pod wynikiem
narzędzia z sygnaturą notatki `bledy/` krótki blok „To już było: <tytuł> → jak poprawnie: …” (najwyżej MAX_TRAFIEN
notatek, najwyżej MAX_ZNAKOW_BLOKU znaków), a pod błędem bez notatki jedną linię: po rozwiązaniu zapisz go w księdze.
Bez modelu: sygnatury z plików `bledy/*.md` w pamięci procesu, czytane od nowa po zmianie katalogu (sprawdzenie
najwyżej co KONTROLA_S).

Kiedy hak patrzy w wynik:
- status `error` (Hermes: wynik z polem `error` albo porażka narzędzia): sygnatury wszystkich notatek, a bez trafienia
  linia o zapisie nowego błędu (raz na sesję i narzędzie);
- zwykły wynik: tylko sygnatury i tylko poza narzędziami, które oddają cudzy tekst (CZYTAJACE: pliki, terminal, kod,
  skille, pamięć), bo tam sygnatura to treść, a nie stan narzędzia;
- notatka z polem `narzedzia` (np. `[komputer, computer_use]`) patrzy tylko w wyniki tych narzędzi (`mcp__phone__*`:
  przedrostek), w każdym statusie;
- narzędzia skarbca (`wiedza_*`) nigdy: wynik `wiedza_czytaj` notatki błędu zawiera jej sygnatury.
Ta sama notatka w tej samej sesji: pełny blok raz, potem jedna linia. Licznik przypomnień (state/bledy-licznik.json,
pod blokadą międzyprocesową, zapis atomowy) rośnie raz na sesję i notatkę.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

MAX_TRAFIEN = 2
MAX_ZNAKOW_KROKU = 360            # krok „jak poprawnie” w bloku (całość: wiedza_czytaj)
MAX_ZNAKOW_BLOKU = 1000
MAX_SKAN = 60_000                 # tyle początku wyniku sprawdzamy…
KONIEC_SKAN = 8_000               # …i tyle końca (odmowa bywa na końcu długiego wyniku)
MAX_JSON = 400_000                # wynik JSON do tej długości rozpakowany przed sprawdzeniem („\u0105” → „ą”)
KONTROLA_S = 5.0                  # najwyżej tak często sprawdzamy, czy pliki księgi się zmieniły
MAX_SESJI = 256                   # sesji pamiętanych w procesie (pełny blok raz na sesję)
PLIK_ZAMKA = "bledy-licznik.lock"
CZYTAJACE = frozenset({"read_file", "search_files", "terminal", "execute_code", "process", "skill_view", "skills_list",
                       "skill_manage", "session_search", "memory", "todo", "write_file", "patch", "delegate_task",
                       "clarify"})
WLASNE = "wiedza_"
NAGLOWEK = "\n\n[księga błędów] "

_lock = threading.Lock()
_ksiegi: Dict[str, dict] = {}     # skarbiec → {"spr": czas sprawdzenia, "stempel": pliki, "wpisy": notatki}
_sesje: Dict[str, set] = {}       # sesja → {"n:<notatka>", "nowy:<narzędzie>"}


def _stempel(katalog: Path) -> tuple:
    try:
        with os.scandir(katalog) as it:
            return tuple(sorted((e.name, e.stat().st_mtime_ns, e.stat().st_size) for e in it if e.name.endswith(".md")))
    except OSError:
        return ()


def wpisy(lib, skarbiec: Path, stan: Path) -> List[dict]:
    """Notatki księgi (wiedza.wpisy_ksiegi) z pamięci procesu; pliki czytane od nowa tylko po zmianie katalogu."""
    klucz, teraz = str(skarbiec), time.monotonic()
    with _lock:
        k = _ksiegi.get(klucz)
    if k and teraz - k["spr"] < KONTROLA_S:
        return k["wpisy"]
    stempel = _stempel(skarbiec / lib.KSIEGA)
    if k and k["stempel"] == stempel:
        k["spr"] = teraz
        return k["wpisy"]
    lista = lib.wpisy_ksiegi(lib.Skarbiec(skarbiec, stan)) if stempel else []
    with _lock:
        _ksiegi[klucz] = {"spr": teraz, "stempel": stempel, "wpisy": lista}
    return lista


def _napisy(dane: Any, out: List[str], glebokosc: int = 0) -> None:
    if isinstance(dane, str):
        out.append(dane)
    elif glebokosc < 8 and isinstance(dane, dict):
        for v in dane.values():
            _napisy(v, out, glebokosc + 1)
    elif glebokosc < 8 and isinstance(dane, list):
        for v in dane:
            _napisy(v, out, glebokosc + 1)


def tekst_wyniku(result: str) -> str:
    """Tekst wyniku do sprawdzenia: wynik JSON rozpakowany (same napisy, bez ucieczek \\uXXXX i \\"), długi przycięty
    do początku i końca."""
    t = result
    if result[:1] in "{[" and len(result) <= MAX_JSON:
        try:
            napisy: List[str] = []
            _napisy(json.loads(result), napisy)
            t = "\n".join(napisy)
        except ValueError:
            pass
    return t if len(t) <= MAX_SKAN + KONIEC_SKAN else t[:MAX_SKAN] + "\n" + t[-KONIEC_SKAN:]


def _narzedzie_pasuje(wzory: List[str], narzedzie: str) -> bool:
    return any(narzedzie == w or (w.endswith("*") and narzedzie.startswith(w[:-1])) for w in wzory)


def kandydaci(lista: List[dict], narzedzie: str, blad: bool) -> List[dict]:
    """Notatki, które w ogóle patrzą w wynik tego narzędzia przy tym statusie (pole `narzedzia`, CZYTAJACE)."""
    return [w for w in lista
            if (_narzedzie_pasuje(w["narzedzia"], narzedzie) if w["narzedzia"] else blad or narzedzie not in CZYTAJACE)]


def dopasuj(lista: List[dict], tekst: str) -> List[dict]:
    """Notatki z `lista` (kandydaci), których sygnatura jest w `tekst` (po wiedza.norm_komunikatu), najwyżej MAX_TRAFIEN."""
    out = []
    for w in lista:
        if any(p.search(tekst) for p in w["wzorce"]):
            out.append(w)
            if len(out) == MAX_TRAFIEN:
                break
    return out


def _pierwszy_raz(sesja: str, klucz: str) -> bool:
    """Czy `klucz` (notatka albo „nowy błąd” narzędzia) pada w tej sesji pierwszy raz; zapamiętuje go."""
    with _lock:
        znane = _sesje.get(sesja)
        if znane is None:
            if len(_sesje) >= MAX_SESJI:
                _sesje.pop(next(iter(_sesje)))
            znane = _sesje[sesja] = set()
        if klucz in znane:
            return False
        znane.add(klucz)
        return True


def policz(lib, stan: Path, rel: str, zamek: Callable, zamien: Callable) -> int:
    """Przypomnienie notatki `rel` +1 w state/bledy-licznik.json (blokada międzyprocesowa: brama i pracownicy kart to
    osobne procesy; zapis atomowy). Zwraca liczbę przypomnień po zmianie; 0, gdy stanu nie da się zapisać."""
    plik = stan / lib.LICZNIK_BLEDOW
    with zamek(stan / PLIK_ZAMKA, 0.5):
        dane = lib.licznik_bledow(stan)
        wpis = dane.get(rel) if isinstance(dane.get(rel), dict) else {}
        try:
            n = int(wpis.get("przypomnien") or 0) + 1
        except (TypeError, ValueError):
            n = 1
        dane[rel] = {"przypomnien": n, "ostatnio": time.strftime("%Y-%m-%d %H:%M")}
        try:
            tmp = plik.with_name(f"{plik.name}.{os.getpid()}.tmp")
            tmp.write_text(json.dumps(dane, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
            zamien(tmp, plik)
        except OSError as e:
            logger.debug("jarvo-wiedza: licznik księgi błędów: %s", e)
            return 0
    return n


def _skroc(s: str, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def dopisek(lib, narzedzie: str, result: str, status: str, sesja: str, skarbiec: Path, stan: Path, *,
            zamek: Callable, zamien: Callable) -> str:
    """Tekst do dopisania pod wynikiem narzędzia (zaczyna się pustą linią) albo "" (wynik bez zmian)."""
    if not narzedzie or narzedzie.startswith(WLASNE) or not skarbiec.is_dir():
        return ""
    blad = status == "error"
    sesja = sesja or "bez-sesji"
    lista = kandydaci(wpisy(lib, skarbiec, stan), narzedzie, blad)
    if not lista and not blad:                         # zwykły wynik bez notatki do sprawdzenia: bez czytania wyniku
        return ""
    trafienia = dopasuj(lista, lib.norm_komunikatu(tekst_wyniku(result)))
    if not trafienia:
        if blad and _pierwszy_raz(sesja, f"nowy:{narzedzie}"):
            return (NAGLOWEK + "Tego błędu nie ma w księdze błędów (`bledy/`). Gdy go rozwiążesz, a może wrócić (nie "
                    "literówka ani zły argument), zapisz go: wiedza_zapisz z typ=blad, sygnatury = dosłowny fragment tego "
                    "komunikatu, treść w akapitach „Objaw: …”, „Przyczyna: …”, „Jak poprawnie: …”.")
        return ""
    linie = []
    for w in trafienia:
        if _pierwszy_raz(sesja, f"n:{w['sciezka']}"):
            n = w["wystapienia"] + policz(lib, stan, w["sciezka"], zamek, zamien)
            linie.append(f"To już było: {w['tytul']} (wystąpień: {n}) → jak poprawnie: {_skroc(w['jak'], MAX_ZNAKOW_KROKU)} "
                         f"Zrób to zamiast ponawiać; całość: wiedza_czytaj(\"{w['sciezka']}\").")
        else:
            linie.append(f"To już było: {w['tytul']}: krok „jak poprawnie” masz wyżej w tej rozmowie; zrób go, nie ponawiaj.")
    na_linie = MAX_ZNAKOW_BLOKU // len(linie)          # cały blok najwyżej ok. MAX_ZNAKOW_BLOKU znaków
    return NAGLOWEK + "\n".join(_skroc(l, na_linie) for l in linie)
