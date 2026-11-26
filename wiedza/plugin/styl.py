"""Styl odpowiedzi floty: bez myślników (— – i „--”) i bez słowa „karta” w tekście do właściciela.

Właściciel 20.11: „wypierdol pisanie double myślników, to tak wkurwia i jest takie AI slop… w briefie jest tego od
groma” (brief z 20.11: 46 myślników). Model i tak je pisze, więc poza promptem tekst każdej odpowiedzi przechodzi
przez `bez_myslnikow` (hak `transform_llm_output` wtyczki jarvo-wiedza), zanim trafi do Telegrama, panelu i historii.

Zasady zamiany (kod w ``` i w `…` oraz adresy URL zostają bez zmian):
- jeden myślnik ze spacjami w zdaniu („X — Y”) → dwukropek („X: Y”), a gdy przed nim już jest dwukropek, przecinek;
- dwa i więcej w jednym wierszu („A — wtrącenie — B”) → przecinki;
- myślnik na początku wiersza (punkt listy) → „- ”; sam myślnik w komórce tabeli („| — |”) → „-”;
- myślnik bez spacji między słowami („tak—nie”) → przecinek ze spacją; zakres liczb („2–3”, „13:46–15:01”) zostaje.
"""
from __future__ import annotations

import re

_KOD = re.compile(r"(`[^`\n]*`|https?://\S+)")
_SPACJA = re.compile(r"[ \t\u00a0]+(?:—|–|--)[ \t\u00a0]+")
_POCZATEK = re.compile(r"^([ \t]*)(?:—|–|--)[ \t]+")
_KOMORKA = re.compile(r"(?<=\|)([ \t]*)(?:—|–|--)([ \t]*)(?=\|)")
_KONIEC = re.compile(r"[ \t\u00a0]+(?:—|–)[ \t\u00a0]*$")
_MIEDZY_SLOWAMI = re.compile(r"(?<=[^\W\d_])(?:—|–)(?=[^\W\d_])")
_ZNAKI = ("—", "–", "--")


def _wiersz(w: str) -> str:
    """Jeden wiersz poza blokiem kodu; fragmenty `kodu` i adresy URL bez zmian."""
    if not any(z in w for z in _ZNAKI):
        return w
    czesci = _KOD.split(w)
    tekst = [c for i, c in enumerate(czesci) if i % 2 == 0]
    ile = sum(len(_SPACJA.findall(c)) for c in tekst)
    wynik = []
    for i, c in enumerate(czesci):
        if i % 2:
            wynik.append(c)
            continue
        if i == 0:
            c = _POCZATEK.sub(r"\1- ", c)
        c = _KOMORKA.sub(r"\1-\2", c)
        if ile >= 2:
            c = _SPACJA.sub(", ", c)
        else:
            c = _SPACJA.sub(lambda m: ", " if ":" in c[:m.start()].rsplit(".", 1)[-1] else ": ", c)
        c = _KONIEC.sub("", c)
        c = _MIEDZY_SLOWAMI.sub(", ", c)
        wynik.append(c)
    return "".join(wynik)


def bez_myslnikow(tekst: str) -> str:
    """Tekst odpowiedzi bez myślników poza blokami kodu (```) i fragmentami `kodu`."""
    if not tekst or not any(z in tekst for z in _ZNAKI):
        return tekst
    wyjscie, w_kodzie = [], False
    for w in tekst.split("\n"):
        if w.lstrip().startswith("```"):
            w_kodzie = not w_kodzie
            wyjscie.append(w)
            continue
        wyjscie.append(w if w_kodzie else _wiersz(w))
    return "\n".join(wyjscie)


# „karta” (zadanie z listy zadań) → „zadanie”: właściciel 26.11 („karta to jest kredytowa”); SOUL tego zakazuje, a model
# i tak pisze „Karta wróciła do oceny”. Odmiana rzeczownika, czasownik w czasie przeszłym zaraz po nim (wróciła →
# wróciło) i przymiotnik zaraz przed nim (nowa → nowe). Karta graficzna, kredytowa, SIM, pamięci, przeglądarki zostają.
_KARTA = {"karta": "zadanie", "karty": "zadania", "kartę": "zadanie", "kartą": "zadaniem", "karcie": "zadaniu",
          "kart": "zadań", "kartom": "zadaniom", "kartami": "zadaniami", "kartach": "zadaniach"}
_INNA_KARTA = r"(?!\s+(?:graficzn|kredytow|płatnicz|debetow|SIM|sim|pamięci|sieciow|dźwiękow|podarunkow|przeglądark|telefon|NFC|wideo))"
_SLOWO_KARTA = re.compile(r"(?<![\w`/.-])(?:(\w+a)\s+)?(" + "|".join(sorted(_KARTA, key=len, reverse=True)) + r")\b"
                          + _INNA_KARTA + r"(\s+\w+ła\b)?", re.I)
_PRZYMIOTNIK = {"ta": "to", "ona": "ono", "moja": "moje", "twoja": "twoje", "nasza": "nasze", "jego": "jego"}


def _jak(wzor: str, slowo: str) -> str:
    return slowo[:1].upper() + slowo[1:] if wzor[:1].isupper() else slowo


def _karta(m: re.Match) -> str:
    przym, rzecz, czas = m.group(1), m.group(2), m.group(3)
    nowe = _jak(rzecz, _KARTA[rzecz.lower()])
    if przym:
        p = przym.lower()
        if rzecz.lower() == "karta" and (p in _PRZYMIOTNIK or p.endswith(("owa", "na", "ta", "ja", "ia"))):
            przym = _jak(przym, _PRZYMIOTNIK.get(p, p[:-1] + "e"))
        nowe = f"{przym} {nowe}"
    if czas and rzecz.lower() == "karta":
        czas = czas[:-1] + "o"
    return nowe + (czas or "")


def bez_karty(tekst: str) -> str:
    """Tekst odpowiedzi z „zadaniem” zamiast „karty” poza blokami kodu (```), `kodem` i adresami URL."""
    if not tekst or not re.search(r"(?i)\bkar(t|ci)", tekst):
        return tekst
    wyjscie, w_kodzie = [], False
    for w in tekst.split("\n"):
        if w.lstrip().startswith("```"):
            w_kodzie = not w_kodzie
            wyjscie.append(w)
            continue
        if w_kodzie:
            wyjscie.append(w)
            continue
        czesci = _KOD.split(w)
        wyjscie.append("".join(c if i % 2 else _SLOWO_KARTA.sub(_karta, c) for i, c in enumerate(czesci)))
    return "\n".join(wyjscie)
