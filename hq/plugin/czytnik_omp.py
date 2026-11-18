"""Oś rozmowy z pliku sesji omp (`*.jsonl`, wersja 3), tylko odczyt (docs/centrum §3.2, krok 1d).

    os_sesji(plik, ostatnie=200) -> {"wpisy": [...], "pelny": bool, "sesja": id, "blad": None | "nieznany format"}
    odpowiedzi(plik) -> int | None   odpowiedzi kończące turę spoza panelu (licznik nieprzeczytanych rozmówcy)

Aktywna gałąź: od ostatniego wpisu (liść) w górę po `parentId`. `pelny` = sesja odgałęziona z innej
(`parentSession` w nagłówku): jej początek leży w innym pliku. Wpis osi:

    {"id", "czas", "typ": "uzytkownik", "zrodlo": "telegram|panel|terminal|<inne>", "tekst"}
    {"id", "czas", "typ": "asystent", "tekst", "czeka_na_tak": bool}    znacznik [[czeka-na-tak]] wycięty
    {"id", "czas", "typ": "kroki", "kroki": [{"nazwa", "intencja"}, …]}  kolejne narzędzia w jednym wpisie
    {"id", "czas", "typ": "streszczenie", "tekst"}                     compaction (krótkie streszczenie)

**Nigdy nie ma wyników ani argumentów narzędzi**: wpisy `toolResult` są pomijane bez czytania, z wywołania
narzędzia zostaje nazwa i intencja (`intent`). Wiadomość użytkownika z obwiedniami skrzynki (`[Telegram · …]`,
`[Panel · …]`, jarvo/sesje_omp.prompt) to tekst bloków bez wstępu i nagłówków; bez obwiedni = terminal.
Plik czytany przyrostowo (pamięć: offset i skrócone wpisy), więc wielki plik sesji kosztuje raz.
Nieznany format = `blad`, nigdy wyjątek (rozmówca „niedostępny”, reszta panelu działa).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

WERSJE = (3,)
SCHEMAT_WYMAGANY = {"session": ("type", "version", "id"), "wpis": ("type", "id")}
ZNACZNIK_TAK = "[[czeka-na-tak]]"
_NAGLOWEK = re.compile(r"^\[(Telegram|Panel|[A-ZŁŚŻŹĆŃÓĘĄ][\w ]{0,20}) · ([^\]\n]*)wiadomość \d+/\d+\]\n", re.M)
_KLUCZ = re.compile(r"· #([A-Za-z0-9][A-Za-z0-9_-]{0,63}) · $")
_PAMIEC: dict[str, dict] = {}


def _tekst(tresc) -> str:
    if isinstance(tresc, str):
        return tresc
    return "".join(c.get("text", "") for c in tresc or [] if isinstance(c, dict) and c.get("type") == "text")


def bloki_obwiedni(tekst: str) -> list[dict]:
    """[{zrodlo, tekst, klucz}] wiadomości skrzynki (partia może mieszać panel i Telegram; `klucz` = klucz wiadomości
    panelu z nagłówka, czyli id przebiegu); bez nagłówków = terminal."""
    naglowki = list(_NAGLOWEK.finditer(tekst))
    if not naglowki:
        return [{"zrodlo": "terminal", "tekst": tekst.strip(), "klucz": None}]
    bloki = []
    for i, m in enumerate(naglowki):
        koniec = naglowki[i + 1].start() if i + 1 < len(naglowki) else len(tekst)
        blok = tekst[m.end():koniec].strip().removesuffix("---").strip()
        k = _KLUCZ.search(m.group(2))
        if blok:
            bloki.append({"zrodlo": m.group(1).lower(), "tekst": blok, "klucz": k.group(1) if k else None})
    return bloki


def bez_obwiedni(tekst: str) -> tuple[str, str]:
    """(źródło pierwszego bloku, tekst bloków) dla wiadomości skrzynki; bez nagłówków = (terminal, tekst)."""
    bloki = bloki_obwiedni(tekst)
    return (bloki[0]["zrodlo"] if bloki else "terminal"), "\n\n".join(b["tekst"] for b in bloki)


def _skrot(e: dict) -> dict | None:
    """Skrócony wpis osi z wpisu sesji (None = niewidoczny, ale zostaje w drzewie)."""
    typ, czas = e.get("type"), e.get("timestamp")
    if typ == "compaction":
        return {"typ": "streszczenie", "czas": czas, "tekst": str(e.get("shortSummary") or "")[:2000]}
    if typ != "message":
        return None
    m = e.get("message") or {}
    rola = m.get("role")
    if rola == "user":
        bloki = bloki_obwiedni(_tekst(m.get("content")))
        if not any(b["tekst"] for b in bloki):
            return None
        wynik = {"typ": "uzytkownik", "czas": czas, "zrodlo": bloki[0]["zrodlo"],
                 "tekst": "\n\n".join(b["tekst"] for b in bloki)}
        klucze = [b["klucz"] for b in bloki if b["klucz"]]
        if klucze:                                     # wiadomości panelu: odpowiedź należy do ich przebiegów
            wynik["klucze"] = klucze
        if len({b["zrodlo"] for b in bloki}) > 1:      # partia z kilku kanałów: panel pokazuje bloki spoza panelu
            wynik["bloki"] = [{"zrodlo": b["zrodlo"], "tekst": b["tekst"]} for b in bloki]
        return wynik
    if rola == "assistant":
        kroki = [{"nazwa": str(c.get("name") or ""), "intencja": str(c.get("intent") or "")[:200]}
                 for c in m.get("content") or [] if isinstance(c, dict) and c.get("type") == "toolCall"]
        tekst = _tekst(m.get("content")).strip()
        wynik = {"czas": czas, "kroki": kroki}
        if tekst:
            tak = ZNACZNIK_TAK in tekst
            wynik.update(typ="asystent", tekst=tekst.replace(ZNACZNIK_TAK, "").strip(), czeka_na_tak=tak)
        elif kroki:
            wynik["typ"] = "kroki"
        else:
            return None
        return wynik
    return None                                  # toolResult, developer, custom: nigdy na osi


def _czytaj(plik: Path) -> dict:
    st = plik.stat()
    klucz = str(plik)
    p = _PAMIEC.get(klucz)
    if not p or p["ino"] != st.st_ino or st.st_size < p["od"]:
        p = {"ino": st.st_ino, "od": 0, "naglowek": None, "wpisy": {}, "lisc": None, "blad": None, "odpowiedzi": 0}
        _PAMIEC[klucz] = p
    if st.st_size == p["od"] or p["blad"]:
        return p
    with plik.open("rb") as f:
        f.seek(p["od"])
        dane = f.read(st.st_size - p["od"])
    koniec = dane.rfind(b"\n") + 1
    for linia in dane[:koniec].splitlines():
        if not linia.strip():
            continue
        if b'"role":"toolResult"' in linia[:400]:           # wynik narzędzia: tylko id i rodzic, treści nie parsujemy
            ident = re.search(rb'"id":"([^"]+)"', linia[:400])
            rodzic = re.search(rb'"parentId":(null|"([^"]*)")', linia[:400])
            if ident:
                i = ident.group(1).decode()
                p["wpisy"][i] = ((rodzic.group(2) or b"").decode() or None if rodzic else None, None)
                p["lisc"] = i
            continue
        try:
            e = json.loads(linia)
        except ValueError:
            continue
        if not isinstance(e, dict):
            continue
        if e.get("type") == "session":
            if any(k not in e for k in SCHEMAT_WYMAGANY["session"]) or e.get("version") not in WERSJE:
                p["blad"] = "nieznany format"
                return p
            p["naglowek"] = {"id": e["id"], "parentSession": e.get("parentSession")}
            continue
        if "id" not in e or "type" not in e or "parentId" not in e:
            continue
        skrot = _skrot(e)
        p["wpisy"][e["id"]] = (e.get("parentId"), skrot)
        if skrot and skrot["typ"] == "asystent" and not skrot["kroki"] and not _z_panelu(p["wpisy"], e.get("parentId")):
            p["odpowiedzi"] += 1
        p["lisc"] = e["id"]
    p["od"] += koniec
    if p["naglowek"] is None and p["od"] > 0 and p["wpisy"]:
        p["blad"] = "nieznany format"
    return p


def _z_panelu(wpisy: dict, i: str | None) -> bool:
    """Tura zaczęła się wiadomością panelu (najbliższy wpis użytkownika w górę gałęzi niesie klucze przebiegów)."""
    widziane = set()
    while i and i not in widziane:
        widziane.add(i)
        rodzic, skrot = wpisy.get(i, (None, None))
        if skrot and skrot["typ"] == "uzytkownik":
            return bool(skrot.get("klucze"))
        i = rodzic
    return False


def odpowiedzi(plik: Path | str) -> int | None:
    """Licznik nieprzeczytanych rozmówcy omp: liczba odpowiedzi kończących turę w pliku (asystent z tekstem, bez
    wywołań narzędzi), z pominięciem tur z panelu (te liczy koniec przebiegu); None = pliku nie da się czytać.
    Kroki narzędzi, wyniki i tekst przy wywołaniu narzędzia licznika nie ruszają: jedna tura = jedna wiadomość."""
    try:
        p = _czytaj(Path(plik))
    except OSError:
        return None
    return None if p["blad"] else p["odpowiedzi"]


def os_sesji(plik: Path | str | None, ostatnie: int = 200) -> dict:
    wynik = {"wpisy": [], "pelny": False, "sesja": None, "blad": None}
    if not plik:
        return {**wynik, "blad": "brak pliku sesji"}
    try:
        p = _czytaj(Path(plik))
    except OSError:
        return {**wynik, "blad": "brak pliku sesji"}
    if p["blad"]:
        return {**wynik, "blad": p["blad"]}
    galaz, i, widziane = [], p["lisc"], set()
    while i and i not in widziane and len(galaz) < ostatnie * 4:
        widziane.add(i)
        rodzic, skrot = p["wpisy"].get(i, (None, None))
        if skrot:
            galaz.append({"id": i, **skrot})
        i = rodzic
    galaz.reverse()
    wpisy: list[dict] = []
    for w in galaz:                               # kompresja: narzędzia pod rząd → jeden wpis „kroki”
        kroki = list(w.pop("kroki", []))         # kopia: lista w pamięci czytnika zostaje nietknięta
        if w["typ"] == "asystent":
            wpisy.append(w)
            if kroki:
                wpisy.append({"id": w["id"] + ":k", "czas": w["czas"], "typ": "kroki", "kroki": kroki})
        elif w["typ"] == "kroki" and wpisy and wpisy[-1]["typ"] == "kroki":
            wpisy[-1]["kroki"].extend(kroki)
        elif w["typ"] == "kroki":
            wpisy.append({**w, "kroki": kroki})
        else:
            wpisy.append(w)
    n = p["naglowek"] or {}
    return {**wynik, "wpisy": wpisy[-ostatnie:], "pelny": bool(n.get("parentSession")), "sesja": n.get("id")}


def zapomnij(plik: Path | str | None = None) -> None:
    """Czyści pamięć czytnika (testy, zmiana pliku sesji wpisu)."""
    if plik is None:
        _PAMIEC.clear()
    else:
        _PAMIEC.pop(str(plik), None)
        _PAMIEC.pop(os.fspath(plik), None)
