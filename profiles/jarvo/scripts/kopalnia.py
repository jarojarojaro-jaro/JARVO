#!/usr/bin/env python3
"""Kopalnia pomysłów (decyzja właściciela 2026-11-14, wzór: skill idea-miner Garry'ego Tana): dane bez modelu (0 tokenów)
do porannego briefu, z których Jarvo wybiera jedną rzecz wartą zbudowania (skill `kopalnia-pomyslow`).

Źródła z ostatnich 48 h (w poniedziałek 72 h, żeby weekend nie przepadł):
- wiadomości właściciela do Jarva (state.db profilu jarvo; bez tablicy, terminala i rutyn), skrócone, z zamaskowanymi
  długimi ciągami podobnymi do kluczy;
- notatki skarbca nowe albo zmienione (ścieżki; bez surowych źródeł, szkiców, lustra repo, stron skilli i briefów);
- własne skille floty (z `metadata.jarvo` we frontmatterze), żeby nie proponować drugi raz tego, co już jest;
- wcześniejsze pomysły z briefów (pozycje „🛠” z 30 dni) z odpowiedzią właściciela i tym, co zrobiono.

    python3 kopalnia.py            # JSON jak w danych briefu
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _sciezki  # noqa: E402
import briefy  # noqa: E402

GODZIN = 48
GODZIN_PO_WEEKENDZIE = 72
POMIJANE_ZRODLA = {"kanban", "cli", "tui", "cron", "oneshot"}  # karty, terminal i `jarvo chat -q` operatora, rutyny
MAX_WIADOMOSCI = 60
MAX_ZNAKOW_WIADOMOSCI = 400
MAX_ZNAKOW_RAZEM = 12000
MAX_NOTATEK = 40
MAX_OPISU_SKILLA = 70
DNI_POMYSLOW = 30
ZNAK_POMYSLU = "🛠"
# surowe źródła i szkice, lustro repo, strony skilli z zasiewu, archiwum briefów: nie praca właściciela
POMIJANE_W_SKARBCU = ("zrodla/", "skrzynka/", "briefy/", "fleet/skille/", "state/", ".git/", ".obsidian/")
TECHNICZNE = {"INDEX.md", "LOG.md", "LINT.md", "SCHEMA.md"}
# ciąg liter i cyfr ≥ 32 znaków poza ścieżką adresu (klucz, token): maskowany, zanim trafi do modelu i archiwum
KLUCZ = re.compile(r"(?<![/\w=.-])(?=[A-Za-z0-9_\-]*\d)(?=[A-Za-z0-9_\-]*[A-Za-z])[A-Za-z0-9_\-]{32,}")
HASLO = re.compile(r"(?i)\b(hasł?o|haslo|password|passwd|token|api[_ -]?key)\b(\s*[:=]\s*)\S+")


def okno_godzin(teraz: dt.datetime) -> int:
    return GODZIN_PO_WEEKENDZIE if teraz.weekday() == 0 else GODZIN


def _maskuj(tekst: str) -> str:
    return HASLO.sub(r"\1\2[ukryte]", KLUCZ.sub("[ukryte]", tekst))


def wiadomosci_wlasciciela(dane: Path, od: float) -> list[dict]:
    """Wiadomości właściciela (rola user) od `od`, najnowsze ostatnie; razem najwyżej MAX_ZNAKOW_RAZEM znaków."""
    baza = dane / "profiles" / "jarvo" / "state.db"
    if not baza.is_file():
        return []
    conn = sqlite3.connect(baza.absolute().as_uri() + "?mode=ro", uri=True, timeout=5)
    try:
        rows = conn.execute(
            "SELECT s.source, m.timestamp, m.content FROM messages m JOIN sessions s ON s.id = m.session_id "
            "WHERE m.role = 'user' AND m.timestamp >= ? AND m.content IS NOT NULL AND m.content != '' "
            "ORDER BY m.timestamp", (od,)).fetchall()
    finally:
        conn.close()
    wynik: list[dict] = []
    for zrodlo, ts, tresc in rows:
        if (zrodlo or "") in POMIJANE_ZRODLA or not isinstance(tresc, str) or not tresc.strip():
            continue
        tekst = _maskuj(" ".join(tresc.split()))
        if len(tekst) > MAX_ZNAKOW_WIADOMOSCI:
            tekst = tekst[:MAX_ZNAKOW_WIADOMOSCI - 1] + "…"
        wynik.append({"kiedy": dt.datetime.fromtimestamp(ts).strftime("%m-%d %H:%M"), "skad": zrodlo, "tekst": tekst})
    wynik = wynik[-MAX_WIADOMOSCI:]
    while wynik and sum(len(w["tekst"]) for w in wynik) > MAX_ZNAKOW_RAZEM:
        wynik.pop(0)                              # najstarsze odpadają pierwsze
    return wynik


def notatki_zmienione(skarbiec: Path, od: float) -> dict:
    """Ścieżki notatek skarbca nowych albo zmienionych od `od` (najnowsze najpierw) i ich liczba."""
    if not skarbiec.is_dir():
        return {"liczba": 0, "sciezki": []}
    zmienione = []
    for p in skarbiec.rglob("*.md"):
        rel = p.relative_to(skarbiec).as_posix()
        if rel.startswith(POMIJANE_W_SKARBCU) or p.name in TECHNICZNE or p.name.startswith("_hub"):
            continue
        try:
            czas = p.stat().st_mtime
        except OSError:
            continue
        if czas >= od:
            zmienione.append((czas, rel[:-3]))
    zmienione.sort(reverse=True)
    return {"liczba": len(zmienione), "sciezki": [s for _, s in zmienione[:MAX_NOTATEK]]}


def _frontmatter(tekst: str) -> str:
    m = re.match(r"---\s*\n(.*?)\n---", tekst, re.S)
    return m.group(1) if m else ""


def skille_floty(dane: Path) -> dict[str, list[str]]:
    """Własne skille floty na agenta: „nazwa: opis” (z `metadata.jarvo` we frontmatterze; skille Hermesa pomijane)."""
    wynik: dict[str, list[str]] = {}
    for profil in sorted((dane / "profiles").glob("*/")):
        pozycje = []
        for plik in sorted((profil / "skills").rglob("SKILL.md")):
            try:
                fm = _frontmatter(plik.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            if not re.search(r"^  jarvo:", fm, re.M):
                continue
            nazwa = re.search(r"^name:\s*(.+)$", fm, re.M)
            opis = re.search(r"^description:\s*(.+)$", fm, re.M)
            if nazwa:
                o = (opis.group(1).strip().strip("\"'") if opis else "")[:MAX_OPISU_SKILLA]
                pozycje.append(f"{nazwa.group(1).strip()}: {o}" if o else nazwa.group(1).strip())
        if pozycje:
            wynik[profil.name] = pozycje
    return wynik


def pomysly_wczesniej(skarbiec: Path, dzis: dt.date) -> list[dict]:
    """Pozycje „🛠” z briefów z 30 dni: numer, treść, odpowiedź właściciela, co zrobione (najstarsze najpierw)."""
    granica = f"{dzis - dt.timedelta(days=DNI_POMYSLOW):%Y-%m-%d}"
    wynik = []
    for plik in sorted((skarbiec / briefy.FOLDER).glob("B-*.md")):
        if plik.stem[2:] < granica:
            continue
        for linia in plik.read_text(encoding="utf-8", errors="replace").splitlines():
            m = briefy.WIERSZ.match(linia)
            if m and ZNAK_POMYSLU in m[2]:
                wynik.append({"numer": m[1], "pomysl": m[2].strip(), "odpowiedz": m[3].strip(),
                              "co_zrobione": m[5].strip()})
    return wynik


def zbierz(dane: Path | None = None, skarbiec: Path | None = None, teraz: dt.datetime | None = None) -> dict:
    dane = Path(dane or _sciezki.dane())
    skarbiec = Path(skarbiec or _sciezki.skarbiec())
    teraz = teraz or dt.datetime.now()
    godzin = okno_godzin(teraz)
    od = teraz.timestamp() - godzin * 3600
    return {
        "okno_godzin": godzin,
        "wiadomosci_wlasciciela": wiadomosci_wlasciciela(dane, od),
        "notatki_zmienione": notatki_zmienione(skarbiec, od),
        "skille_floty": skille_floty(dane),
        "pomysly_wczesniej": pomysly_wczesniej(skarbiec, teraz.date()),
    }


def main(argv: list[str] | None = None) -> int:
    print(json.dumps(zbierz(), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
