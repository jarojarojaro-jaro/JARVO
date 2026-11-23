#!/usr/bin/env python3
"""Archiwum briefów w skarbcu (folder `briefy/`, decyzja właściciela 12.11): każdy poranny brief i przegląd tygodnia
dostaje numer i notatkę z treścią i tabelą decyzji, do której Jarvo dopisuje odpowiedzi właściciela.

Numer = data: poranny brief `B-RRRR-MM-DD` (jeden na dzień roboczy), przegląd tygodnia `T-RRRR-Wtt` (tydzień ISO);
decyzja = `B-2026-11-12/3`. Notatkę pisze ten skrypt bez modelu z wyjścia rutyny Hermesa
(`<profil jarvo>/cron/output/<zadanie>/<data>.md`, sekcja `## Response`), wołany przez nadzorcę co minutę
i przez `fleet_report.py` przed każdym briefem (droga bez nadzorcy). Decyzja powtórzona w nowym briefie z dopiskiem
„(z B-…/n)” zamyka starą pozycję („→ nowy numer”), więc lista otwartych nie rośnie od powtórek.

Odpowiedź właściciela zapisuje kod, nie model (23.11 właściciel: „odpowiadam na coś, a on mnie pyta o to samo”; Jarvo
trzy dni nie wpisywał odpowiedzi z 20.11 do tabeli): hak wtyczki jarvo-wiedza woła `zapisz_odpowiedz` przy każdej
odpowiedzi na brief, a `filtruj_brief` wycina z nowego briefu pytania o sprawy już ustalone (ten sam numer w „(z …)”
albo ta sama decyzja innymi słowami, `podobne`).

    briefy.py synchronizuj                      # zapisz brakujące notatki; JSON z nowymi numerami
    briefy.py otwarte                           # decyzje bez odpowiedzi (14 dni), bez spraw już ustalonych
    briefy.py odpowiedz B-…/n "słowa"           # odpowiedź właściciela do wiersza (gdy kod jej nie przypisał)
    briefy.py zrobione B-…/n "co zrobione"      # kolumna „Co zrobione”
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _sciezki  # noqa: E402

FOLDER = "briefy"
RUTYNY = {"jarvo-daily-brief": ("B", "Poranny brief"), "jarvo-weekly-review": ("T", "Przegląd tygodnia")}
DNI_OTWARTYCH = 14
DNI_USTALONYCH = 30
# ta sama decyzja innymi słowami: wspólne rdzenie słów (5 znaków) / wszystkie; na briefach 10–23.11 każda para ≥ 0,4
# to ta sama sprawa, najwyższa para różnych spraw 0,33
PROG_PODOBNE = 0.4
NIE_SLOWA = {"rekom", "tego", "jest", "przed", "przez", "albo", "żeby", "czy", "nadal", "aktua", "wisi", "powie", "dzięk"}
NUMER_BRIEFU = re.compile(r"\b([BT]-\d{4}-(?:\d{2}-\d{2}|W\d{2}))(?:/(\d{1,2}))?\b")
# „1 ok, 2 nie”, „4 pomijac zdublowane…”, „5 - tak”: numer na początku wiadomości albo po nowej linii, przecinku,
# średniku, kropce ze spacją (nie „1.01.2027” ani „zapisać 3 klucze”)
SEGMENT = re.compile(r"(?:^|(?<=[\n,;])|(?<=\.\s))[ \t]*(\d{1,2})(?:[ \t]*[-–.):]+[ \t]*|[ \t]+)(?=\S)")
# cytat przed słowami właściciela: panel „> Odpowiadam na raport …”, Telegram „[Replying to…: "…"]” (cały brief)
CYTAT = re.compile(r"^\s*(?:(?:>[^\n]*\n)+|\[Replying to.*?\"\]\s*\n)\s*", re.S)
NAGLOWEK_DECYZJI = re.compile(r"(czeka na ciebie|potrzebuj\w* \d+ decyzj|do decyzji|decyzje)", re.I)
POZYCJA = re.compile(r"^\s*(\d{1,2})[.)]\s+(.+)$")
POWTORKA = re.compile(r"\(z ((?:B|T)-\d{4}-(?:\d{2}-\d{2}|W\d{2})/\d+)\)")
WIERSZ = re.compile(r"^\| ((?:B|T)-[\dW-]+/\d+) \| (.*) \| (.*) \| (.*) \| (.*) \|$")
NAZWA_WYJSCIA = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})\.md$")


def identyfikator(zadanie: str, czas: dt.datetime) -> str:
    litera = RUTYNY[zadanie][0]
    if litera == "T":
        rok, tydzien, _ = czas.isocalendar()
        return f"T-{rok}-W{tydzien:02d}"
    return f"B-{czas:%Y-%m-%d}"


def odpowiedz(tekst: str) -> str:
    """Treść wysłana właścicielowi: sekcja `## Response` pliku wyjścia rutyny; [SILENT] i brak = pusto."""
    m = re.search(r"^## Response\s*$", tekst, re.M)
    tresc = tekst[m.end():].strip() if m else ""
    return "" if not tresc or tresc.strip().upper().startswith("[SILENT]") else tresc


def decyzje(tresc: str) -> list[tuple[int, str]]:
    """Numerowane pozycje pod nagłówkiem decyzji („Czeka na Ciebie (5 decyzji):”, „Potrzebuję 2 decyzji:”)."""
    wynik: list[list] = []
    w_sekcji = False
    for linia in tresc.splitlines():
        czysta = linia.strip().strip("*").strip()
        if not w_sekcji:
            w_sekcji = bool(NAGLOWEK_DECYZJI.search(czysta)) and not POZYCJA.match(linia)
            continue
        m = POZYCJA.match(linia)
        if m:
            wynik.append([int(m[1]), m[2].strip()])
        elif not czysta:
            if wynik:
                break
        elif wynik and linia[:1].isspace():
            wynik[-1][1] += " " + czysta
        elif wynik:
            break
    return [(n, t) for n, t in wynik]


def _komorka(tekst: str) -> str:
    return " ".join(tekst.replace("|", "/").split())


def notatka(numer: str, zadanie: str, czas: dt.datetime, tresc: str, zrodlo: str, poprzedni: str | None) -> str:
    rodzaj = RUTYNY[zadanie][1]
    poz = decyzje(tresc)
    wiersze = [f"| {numer}/{n} | {_komorka(t)} |  |  |  |" for n, t in poz]
    streszczenie = (f"{rodzaj} z {czas:%Y-%m-%d %H:%M}: {len(poz)} decyzji czeka na odpowiedź właściciela."
                    if poz else f"{rodzaj} z {czas:%Y-%m-%d %H:%M}, bez decyzji do podjęcia.")
    czesci = ["---", f"typ: brief", f"tagi: [brief, {zadanie}]", f"utworzono: {czas:%Y-%m-%d}",
              f"zmieniono: {czas:%Y-%m-%d}", "status: aktualna", f"zrodlo: \"{zrodlo}\"", f"numer: {numer}", "---",
              f"# {rodzaj} {numer}", "", f"**{streszczenie}**", ""]
    if poz:
        czesci += ["## Decyzje", "Odpowiedź właściciela i to, co z nią zrobiono, dopisuje Jarvo (skill `decision-queue`).",
                   "", "| Numer | Decyzja | Odpowiedź właściciela | Kiedy | Co zrobione |", "|---|---|---|---|---|",
                   *wiersze, ""]
    czesci += ["## Treść", "", tresc.strip(), "", "## Powiązane", f"- hub: [[{FOLDER}/_hub-briefy|Briefy]]"]
    if poprzedni:
        czesci.append(f"- poprzedni: [[{FOLDER}/{poprzedni}]]")
    return "\n".join(czesci) + "\n"


def _zapisz(plik: Path, tekst: str) -> None:
    plik.parent.mkdir(parents=True, exist_ok=True)
    tmp = plik.with_suffix(".md.tmp")
    tmp.write_text(tekst, encoding="utf-8", newline="\n")
    os.replace(tmp, plik)


def _hub(skarbiec: Path) -> None:
    hub = skarbiec / FOLDER / "_hub-briefy.md"
    if hub.exists():
        return
    _zapisz(hub, "\n".join([
        "---", "typ: hub", "tagi: [hub, brief]", f"utworzono: {dt.date.today():%Y-%m-%d}",
        f"zmieniono: {dt.date.today():%Y-%m-%d}", "status: aktualna", "---", "# Briefy", "",
        "**Każdy poranny brief (`B-RRRR-MM-DD`) i przegląd tygodnia (`T-RRRR-Wtt`) z numerem, treścią i tabelą decyzji "
        "z odpowiedziami właściciela.**", "",
        "Notatki pisze skrypt `briefy.py` po wysłaniu rutyny; odpowiedzi i to, co z nich zrobiono, dopisuje Jarvo. Trwałe "
        "ustalenia z decyzji idą do skarbca jako notatki `decyzja` ze źródłem „brief B-…/n”.", "",
        "## Powiązane", "- hub: [[_hub-skarbiec|Skarbiec wiedzy]]", "- [[orzeczenia/_hub-orzeczenia|Orzeczenia]]", ""]))


def _zamknij_powtorki(skarbiec: Path, numer: str, tresc: str) -> None:
    """Pozycja nowego briefu z „(z B-…/n)” zamyka starą: „→ <nowy numer>/<m>” w kolumnie „Co zrobione”."""
    for n, t in decyzje(tresc):
        for stary in POWTORKA.findall(t):
            plik = skarbiec / FOLDER / f"{stary.split('/')[0]}.md"
            if not plik.exists():
                continue
            linie = plik.read_text(encoding="utf-8").splitlines()
            for i, l in enumerate(linie):
                m = WIERSZ.match(l)
                if m and m[1] == stary and not m[3].strip():
                    linie[i] = f"| {m[1]} | {m[2]} | {m[3]} | {m[4]} | → {numer}/{n} |"
            _zapisz(plik, "\n".join(linie) + "\n")


# ------------------------------------------------------------------------------------- sprawy już ustalone

def _slowa(tekst: str) -> set[str]:
    t = POWTORKA.sub("", tekst.lower())
    return {w[:5] for w in re.findall(r"[a-ząćęłńóśźż0-9]{4,}", t)} - NIE_SLOWA


def podobne(a: str, b: str) -> bool:
    """Ta sama decyzja innymi słowami (Jaccard rdzeni słów ≥ PROG_PODOBNE)."""
    sa, sb = _slowa(a), _slowa(b)
    return bool(sa and sb) and len(sa & sb) / len(sa | sb) >= PROG_PODOBNE


def _wiersze(skarbiec: Path, od: str) -> list[dict]:
    wynik = []
    for plik in sorted((skarbiec / FOLDER).glob("B-*.md")):
        if plik.stem[2:] < od:
            continue
        for l in plik.read_text(encoding="utf-8", errors="replace").splitlines():
            if m := WIERSZ.match(l):
                wynik.append({"numer": m[1], "decyzja": m[2].strip(), "odpowiedz": m[3].strip(), "kiedy": m[4].strip(),
                              "zrobione": m[5].strip(), "brief": plik.stem})
    return wynik


def _odpowiedz_wlasciciela(w: dict) -> bool:
    """Prawdziwa odpowiedź (jego słowa), nie myślnik ani przeniesienie."""
    return bool(w["odpowiedz"].strip(" —–-"))


def ustalone(skarbiec: Path | None = None, dzis: dt.date | None = None) -> list[dict]:
    """Decyzje z odpowiedzią właściciela z ostatnich 30 dni: numer, decyzja, jego słowa, kiedy."""
    skarbiec = Path(skarbiec or _sciezki.skarbiec())
    od = f"{(dzis or dt.date.today()) - dt.timedelta(days=DNI_USTALONYCH):%Y-%m-%d}"
    return [w for w in _wiersze(skarbiec, od) if _odpowiedz_wlasciciela(w)]


def _odwolania(tekst: str) -> set[str]:
    """Numery z dopisków „(z B-2026-11-18/4 i /5)”: {B-2026-11-18/4, B-2026-11-18/5}."""
    wynik = set()
    for dopisek in re.findall(r"\(z ([^)]*)\)", tekst):
        if m := NUMER_BRIEFU.search(dopisek):
            wynik |= {f"{m[1]}/{n}" for n in re.findall(r"/(\d{1,2})\b", dopisek[m.start(1):])}
    return wynik


def juz_ustalona(decyzja: str, lista: list[dict], numer: str = "") -> dict | None:
    """Ustalona sprawa, o którą pyta `decyzja` (wiersz `numer`): odwołanie „(z …)” w jedną albo drugą stronę
    do wiersza z odpowiedzią albo ta sama decyzja innymi słowami."""
    odwolania = _odwolania(decyzja)
    for u in lista:
        if u["numer"] in odwolania or (numer and numer in _odwolania(u["decyzja"])) or podobne(decyzja, u["decyzja"]):
            return u
    return None


def filtruj_brief(tresc: str, skarbiec: Path | None = None, dzis: dt.date | None = None) -> tuple[str, list[dict]]:
    """Brief bez pytań o sprawy już ustalone: pozycje wycięte, reszta przenumerowana, liczba w nagłówku poprawiona;
    zwraca (tekst, [{"pozycja", "ustalona"}]). Bez takich pozycji tekst bez zmian."""
    lista = ustalone(skarbiec, dzis)
    linie = tresc.splitlines()
    naglowek, pozycje, w_sekcji = None, [], False      # pozycje: [numer, pierwsza linia, ostatnia linia]
    for i, linia in enumerate(linie):
        czysta = linia.strip().strip("*").strip()
        if not w_sekcji:
            if NAGLOWEK_DECYZJI.search(czysta) and not POZYCJA.match(linia):
                naglowek, w_sekcji = i, True
            continue
        m = POZYCJA.match(linia)
        if m:
            pozycje.append([int(m[1]), i, i])
        elif pozycje and czysta and linia[:1].isspace():
            pozycje[-1][2] = i
        elif pozycje:
            break
    usuniete, zostaje = [], []
    for n, a, b in pozycje:
        tekst = " ".join(x.strip() for x in linie[a:b + 1])
        u = juz_ustalona(tekst, lista) if lista else None
        (usuniete.append({"pozycja": n, "ustalona": u}) if u else zostaje.append((a, b)))
    if not usuniete:
        return tresc, []
    wyciete = {i for n, a, b in pozycje for i in range(a, b + 1) if (a, b) not in zostaje}
    for nowy, (a, _b) in enumerate(zostaje, 1):
        linie[a] = POZYCJA.sub(lambda m: m[0].replace(m[1], str(nowy), 1), linie[a], count=1)
    if zostaje:
        ile = len(zostaje)
        slowo = "decyzja" if ile == 1 else "decyzje" if ile % 10 in (2, 3, 4) and ile % 100 not in (12, 13, 14) else "decyzji"
        linie[naglowek] = re.sub(r"\d+\s+decyzj\w*", f"{ile} {slowo}", linie[naglowek], count=1)
    else:   # nic do decyzji: bez nagłówka sekcji i bez „Odpowiedz np. …”
        wyciete.add(naglowek)
        wyciete |= {i for i, l in enumerate(linie) if i > naglowek and re.match(r"\s*\**\s*Odpowiedz np\.", l)}
    return "\n".join(l for i, l in enumerate(linie) if i not in wyciete) + ("\n" if tresc.endswith("\n") else ""), usuniete


# ------------------------------------------------------------------------------- odpowiedź właściciela

def _temat(decyzja: str) -> str:
    """Rdzeń tematu decyzji („Jarodev: …” → „jarod”); pusto, gdy decyzja nie zaczyna się od „Temat:”."""
    t = re.sub(r"^[^\wąćęłńóśźż]+", "", decyzja.lower())
    glowa = t.split(":", 1)[0] if ":" in t[:40] else ""
    slowa = re.findall(r"[a-ząćęłńóśźż0-9]{4,}", glowa)
    return slowa[0][:5] if len(slowa) == 1 else ""


def przypisz(tekst: str, wiersze: list[dict]) -> dict[str, str]:
    """Odpowiedź właściciela → {numer wiersza: jego słowa}. Numery pozycji („1 ok, 4 pomijać…”) albo, bez numeru,
    fragment z tematem decyzji („Jarodev jeszcze nie”) lub ≥ 2 wspólnymi słowami, gdy pasuje dokładnie do jednego wiersza."""
    po_nr = {int(w["numer"].rsplit("/", 1)[1]): w["numer"] for w in wiersze}
    wynik: dict[str, str] = {}
    trafienia = [m for m in SEGMENT.finditer(tekst) if int(m[1]) in po_nr]
    reszta = list(tekst)
    for k, m in enumerate(trafienia):
        # odpowiedź z numerem kończy się na następnym numerze albo na końcu linii; linie bez numeru idą niżej po temacie
        nastepny = trafienia[k + 1].start() if k + 1 < len(trafienia) else len(tekst)
        linia = tekst.find("\n", m.end())
        koniec = min(nastepny, linia if linia >= 0 else len(tekst))
        slowa = tekst[m.end():koniec].strip(" \t\n,;.")
        if slowa:
            wynik.setdefault(po_nr[int(m[1])], f"{m[1]} {slowa}")
        reszta[m.start():koniec] = [" "] * (koniec - m.start())
    reszta = "".join(reszta)
    for fragment in re.split(r"\n+|;|(?<=\S)\.\s+|\s+oraz\s+", reszta):
        f = fragment.strip()
        if len(f) < 3:
            continue
        sf = _slowa(f)
        pasuje = [w for w in wiersze if w["numer"] not in wynik
                  and ((_temat(w["decyzja"]) and _temat(w["decyzja"]) in sf) or len(sf & _slowa(w["decyzja"])) >= 2)]
        if len(pasuje) == 1:
            wynik[pasuje[0]["numer"]] = f
    return wynik


def _plik_briefu(skarbiec: Path, numer: str) -> Path:
    return skarbiec / FOLDER / f"{numer}.md"


def _ustaw_wiersz(linie: list[str], numer: str, odpowiedz: str | None = None, kiedy: str | None = None,
                  zrobione: str | None = None, nadpisz: bool = False) -> bool:
    for i, l in enumerate(linie):
        m = WIERSZ.match(l)
        if not m or m[1] != numer:
            continue
        if odpowiedz is not None and m[3].strip() and not nadpisz:
            return False
        o = _komorka(odpowiedz) if odpowiedz is not None else m[3].strip()
        z = _komorka(zrobione) if zrobione is not None else m[5].strip()
        linie[i] = f"| {m[1]} | {m[2]} | {o} | {kiedy or m[4].strip()} | {z} |"
        return True
    return False


def zapisz_odpowiedz(skarbiec: Path, numer: str, tekst: str, kiedy: dt.datetime | None = None) -> dict[str, str]:
    """Wiadomość właściciela w odpowiedzi na brief `numer`: surowy tekst do sekcji „Odpowiedzi właściciela” notatki
    (nic nie ginie) i jego słowa do pustych wierszy, które da się przypisać (`przypisz`). Zwraca {wiersz: słowa}."""
    plik = _plik_briefu(skarbiec, numer)
    if not plik.exists() or not tekst.strip():
        return {}
    kiedy = kiedy or dt.datetime.now()
    linie = plik.read_text(encoding="utf-8").splitlines()
    wiersze = [{"numer": m[1], "decyzja": m[2]} for l in linie if (m := WIERSZ.match(l)) and not m[3].strip()
               and not m[5].strip().startswith("→")]
    przypisane = przypisz(tekst, wiersze)
    for nr, slowa in przypisane.items():
        _ustaw_wiersz(linie, nr, f"„{slowa}” ({kiedy:%d.%m %H:%M})", f"{kiedy:%Y-%m-%d}")
    wpis = f"- {kiedy:%Y-%m-%d %H:%M}: „{_komorka(tekst)}”"
    if wpis not in linie:
        if "## Odpowiedzi właściciela" not in linie:
            gdzie = linie.index("## Treść") if "## Treść" in linie else len(linie)
            linie[gdzie:gdzie] = ["## Odpowiedzi właściciela", "Wiadomości właściciela na ten brief, zapisane przez kod.", ""]
        gdzie = linie.index("## Odpowiedzi właściciela") + 2
        while gdzie < len(linie) and linie[gdzie].startswith("- "):
            gdzie += 1
        linie.insert(gdzie, wpis)
    _zapisz(plik, "\n".join(linie) + "\n")
    return przypisane


def odpowiedz_z_wiadomosci(wiadomosc: str, poprzednia: str = "", skarbiec: Path | None = None,
                           kiedy: dt.datetime | None = None) -> tuple[str, dict[str, str], list[str]] | None:
    """Czy wiadomość odpowiada na brief i co z niej zapisano: (numer briefu, {wiersz: słowa}, wiersze bez odpowiedzi)
    albo None. Brief rozpoznany po cytacie (panel „> Odpowiadam na raport…”, Telegram „[Replying to…]”), po numerze
    „B-…/n” w treści albo po briefie w poprzedniej wiadomości Jarva, gdy wiadomość zaczyna się od numeru pozycji."""
    skarbiec = Path(skarbiec or _sciezki.skarbiec())
    tekst = str(wiadomosc or "")
    cytat = CYTAT.match(tekst)
    glowa, tresc = (tekst[:cytat.end()], tekst[cytat.end():]) if cytat else ("", tekst)
    numer = None
    if (m := NUMER_BRIEFU.search(glowa)) and re.search(r"brief|przegląd", glowa, re.I):
        numer = m[1]
    elif cytat and re.search(r"Poranny brief|Przegląd tygodnia", glowa):
        briefy = sorted(p.stem for p in (skarbiec / FOLDER).glob("B-*.md"))
        numer = briefy[-1] if briefy else None
    elif SEGMENT.match(tresc.lstrip()) and (m := NUMER_BRIEFU.search(str(poprzednia or "")[:400])):
        numer = m[1]
    if not numer:
        # „B-2026-11-12/3 ok” po czasie: wiadomość zaczyna się od numeru pozycji (nie prompt rutyny z listą numerów)
        if not re.match(r"\s*[BT]-[\dW-]+/\d", tresc):
            return None
        wskazane = [(m[1], m[2], m.end()) for m in NUMER_BRIEFU.finditer(tresc) if m[2]]
        numer = wskazane[0][0]
        tresc = "\n".join(f"{n} {tresc[koniec:].split('B-', 1)[0].strip(' ,;:')}" for b, n, koniec in wskazane if b == numer)
    if not _plik_briefu(skarbiec, numer).exists():
        return None
    przypisane = zapisz_odpowiedz(skarbiec, numer, tresc.strip(), kiedy)
    puste = [m[1] for l in _plik_briefu(skarbiec, numer).read_text(encoding="utf-8").splitlines()
             if (m := WIERSZ.match(l)) and not m[3].strip() and not m[5].strip().startswith("→")]
    return numer, przypisane, puste


def wyjscia_domyslne() -> Path:
    return _sciezki.dane() / "profiles" / "jarvo" / "cron" / "output"


def synchronizuj(skarbiec: Path | None = None, wyjscia: Path | None = None) -> list[str]:
    """Notatki dla wysłanych briefów i przeglądów, których jeszcze nie ma; zwraca nowe numery (najstarsze najpierw)."""
    skarbiec = Path(skarbiec or _sciezki.skarbiec())
    wyjscia = Path(wyjscia or wyjscia_domyslne())
    if not skarbiec.is_dir():
        return []
    nowe = []
    for zadanie in RUTYNY:
        for plik in sorted((wyjscia / zadanie).glob("*.md")):
            m = NAZWA_WYJSCIA.search(plik.name)
            if not m:
                continue
            czas = dt.datetime.strptime(f"{m[1]} {m[2]}:{m[3]}", "%Y-%m-%d %H:%M")
            numer = identyfikator(zadanie, czas)
            cel = skarbiec / FOLDER / f"{numer}.md"
            if cel.exists():
                continue
            try:
                tresc = odpowiedz(plik.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            if not tresc:
                continue
            _hub(skarbiec)
            istniejace = sorted(p.stem for p in (skarbiec / FOLDER).glob(f"{numer[0]}-*.md") if p.stem < numer)
            zrodlo = f"rutyna {zadanie} {czas:%Y-%m-%d %H:%M} (cron/output/{zadanie}/{plik.name})"
            _zapisz(cel, notatka(numer, zadanie, czas, tresc, zrodlo, istniejace[-1] if istniejace else None))
            _zamknij_powtorki(skarbiec, numer, tresc)
            nowe.append(numer)
    return nowe


def otwarte(skarbiec: Path | None = None, dzis: dt.date | None = None) -> list[dict]:
    """Decyzje z briefów z ostatnich 14 dni bez odpowiedzi i bez przeniesienia („→ …”), bez spraw już ustalonych
    w innym briefie (ten sam numer w „(z …)” albo ta sama decyzja innymi słowami)."""
    skarbiec = Path(skarbiec or _sciezki.skarbiec())
    dzis = dzis or dt.date.today()
    lista = ustalone(skarbiec, dzis)
    wynik = []
    for w in _wiersze(skarbiec, f"{dzis - dt.timedelta(days=DNI_OTWARTYCH):%Y-%m-%d}"):
        if w["odpowiedz"] or w["zrobione"].startswith("→") or juz_ustalona(w["decyzja"], lista, w["numer"]):
            continue
        wynik.append({"numer": w["numer"], "decyzja": w["decyzja"], "dni": (dzis - dt.date.fromisoformat(w["brief"][2:])).days})
    return wynik


def tydzien(dzis: dt.date | None = None, skarbiec: Path | None = None) -> list[dict]:
    """Briefy z ostatnich 7 dni do przeglądu tygodnia: numer, ile decyzji, ile z odpowiedzią, ile przeniesionych."""
    skarbiec = Path(skarbiec or _sciezki.skarbiec())
    od = f"{(dzis or dt.date.today()) - dt.timedelta(days=7):%Y-%m-%d}"
    wynik = []
    for plik in sorted((skarbiec / FOLDER).glob("B-*.md")):
        if plik.stem[2:] < od:
            continue
        wiersze = [m for l in plik.read_text(encoding="utf-8", errors="replace").splitlines() if (m := WIERSZ.match(l))]
        wynik.append({"numer": plik.stem, "decyzje": len(wiersze),
                      "z_odpowiedzia": sum(1 for m in wiersze if m[3].strip()),
                      "przeniesione": sum(1 for m in wiersze if m[5].strip().startswith("→"))})
    return wynik


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:] or ["synchronizuj"]
    polecenie = argv[0]
    if polecenie == "synchronizuj":
        print(json.dumps({"nowe": synchronizuj()}, ensure_ascii=False))
    elif polecenie == "otwarte":
        print(json.dumps(otwarte(), ensure_ascii=False, indent=1))
    elif polecenie in ("odpowiedz", "zrobione") and len(argv) >= 3 and (m := NUMER_BRIEFU.fullmatch(argv[1])) and m[2]:
        plik = _plik_briefu(Path(_sciezki.skarbiec()), m[1])
        if not plik.exists():
            print(f"brak notatki {m[1]}", file=sys.stderr)
            return 1
        linie = plik.read_text(encoding="utf-8").splitlines()
        teraz = dt.datetime.now()
        slowa = " ".join(argv[2:])
        ok = (_ustaw_wiersz(linie, argv[1], f"„{slowa}”", f"{teraz:%Y-%m-%d}", nadpisz=True) if polecenie == "odpowiedz"
              else _ustaw_wiersz(linie, argv[1], zrobione=slowa))
        if not ok:
            print(f"brak wiersza {argv[1]}", file=sys.stderr)
            return 1
        _zapisz(plik, "\n".join(linie) + "\n")
        print(f"{argv[1]}: zapisane")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
