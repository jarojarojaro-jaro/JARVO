#!/usr/bin/env python3
"""Archiwum briefów w skarbcu (folder `briefy/`, decyzja właściciela 12.11): każdy poranny brief i przegląd tygodnia
dostaje numer i notatkę z treścią i tabelą decyzji, do której Jarvo dopisuje odpowiedzi właściciela.

Numer = data: poranny brief `B-RRRR-MM-DD` (jeden na dzień roboczy), przegląd tygodnia `T-RRRR-Wtt` (tydzień ISO);
decyzja = `B-2026-11-12/3`. Notatkę pisze ten skrypt bez modelu z wyjścia rutyny Hermesa
(`<profil jarvo>/cron/output/<zadanie>/<data>.md`, sekcja `## Response`), wołany przez nadzorcę co minutę
i przez `fleet_report.py` przed każdym briefem (droga bez nadzorcy). Decyzja powtórzona w nowym briefie z dopiskiem
„(z B-…/n)” zamyka starą pozycję („→ nowy numer”), więc lista otwartych nie rośnie od powtórek.

    briefy.py synchronizuj      # zapisz brakujące notatki; JSON z nowymi numerami
    briefy.py otwarte           # decyzje bez odpowiedzi (14 dni)
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
    """Decyzje z briefów z ostatnich 14 dni bez odpowiedzi i bez przeniesienia („→ …”)."""
    skarbiec = Path(skarbiec or _sciezki.skarbiec())
    granica = f"{(dzis or dt.date.today()) - dt.timedelta(days=DNI_OTWARTYCH):%Y-%m-%d}"
    wynik = []
    for plik in sorted((skarbiec / FOLDER).glob("B-*.md")):
        if plik.stem[2:] < granica:
            continue
        for l in plik.read_text(encoding="utf-8", errors="replace").splitlines():
            m = WIERSZ.match(l)
            if m and not m[3].strip() and not m[5].strip().startswith("→"):
                wynik.append({"numer": m[1], "decyzja": m[2].strip(), "dni": (
                    (dzis or dt.date.today()) - dt.date.fromisoformat(plik.stem[2:])).days})
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
    polecenie = (argv if argv is not None else sys.argv[1:] or ["synchronizuj"])[0]
    if polecenie == "synchronizuj":
        print(json.dumps({"nowe": synchronizuj()}, ensure_ascii=False))
    elif polecenie == "otwarte":
        print(json.dumps(otwarte(), ensure_ascii=False, indent=1))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
