#!/usr/bin/env python3
"""Księga lekcji floty bez modelu (0 tokenów): co jest gotowe do propozycji, co wypada i czy wdrożona zmiana
pomogła (docs/RSI.md §R1, skill `fleet-improvement`).

    python3 lekcje.py [--plik <knowledge>/fleet/lekcje.md] [--evals <jarvo>/evals/historia.jsonl] [--json]

Format wpisu (jedna linia, pola po „ · ”):
    - [jarvo-web] <reguła> · potwierdzenia: 3 · karty: t_1, t_2, t_3 · od: 2026-10-01 · ostatnio: 2026-10-12
      [· waga: bezpieczeństwo|pieniądze|A2] [· wdrożone: 2026-10-13 a1b2c3d] [· powroty: t_9]

- gotowa do propozycji: ≥ 3 potwierdzenia z różnych kart albo ≥ 1 przy wadze bezpieczeństwo, pieniądze, A2,
- przeterminowana: bez nowego potwierdzenia od 60 dni (`ostatnio`, a bez niego `od`); wdrożonych nie przycinamy,
- skutek wdrożonej (za ACE: licznik „pomogło / zaszkodziło”, u nas z pomiaru): wynik evals agenta z ostatniego
  pełnego przebiegu przed datą wdrożenia i z pierwszego po niej; zmiana ≥ +0,03 = pomogło, ≤ −0,03 = zaszkodziło,
  inaczej bez zmian; bez przebiegu po wdrożeniu = brak pomiaru. `powroty` (karty, na których błąd wrócił po
  wdrożeniu) mówią, że reguła nie działa, niezależnie od evals.
Ostatnia linia wyjścia to JSON.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

PROG = 0.03
DNI_WAZNOSCI = 60
WAGI = {"bezpieczeństwo", "bezpieczenstwo", "pieniądze", "pieniadze", "a2"}
WPIS = re.compile(r"^\s*-\s*\[(?P<agent>[a-z0-9-]+)\]\s*(?P<tresc>.+)$")
DATA = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _data(s: str | None) -> dt.date | None:
    m = DATA.search(s or "")
    try:
        return dt.date.fromisoformat(m.group(1)) if m else None
    except ValueError:
        return None


def wczytaj(tekst: str) -> tuple[list[dict], list[str]]:
    """(lekcje, linie z błędem formatu). Linie spoza listy (nagłówki, opisy) pomija."""
    lekcje, bledy = [], []
    for nr, linia in enumerate(tekst.splitlines(), 1):
        m = WPIS.match(linia)
        if not m:
            if linia.strip().startswith("- ["):
                bledy.append(f"{nr}: {linia.strip()[:120]}")
            continue
        czesci = [c.strip() for c in m.group("tresc").split(" · ")]
        pola = {}
        for c in czesci[1:]:
            k, sep, v = c.partition(":")
            if sep:
                pola[k.strip().lower()] = v.strip()
        karty = [k.strip() for k in pola.get("karty", "").split(",") if k.strip() and k.strip() != "…"]
        try:
            potw = int(pola.get("potwierdzenia", "0"))
        except ValueError:
            potw = 0
            bledy.append(f"{nr}: potwierdzenia nie są liczbą")
        wdr = pola.get("wdrożone") or pola.get("wdrozone")
        lekcje.append({
            "linia": nr, "agent": m.group("agent"), "regula": czesci[0],
            "potwierdzenia": potw, "karty": karty, "rozne_karty": len(set(karty)),
            "od": str(_data(pola.get("od")) or ""), "ostatnio": str(_data(pola.get("ostatnio")) or _data(pola.get("od")) or ""),
            "waga": pola.get("waga", "").lower(),
            "wdrozone": str(_data(wdr) or "") if wdr else "",
            "commit": (wdr or "").split()[-1] if wdr and len((wdr or "").split()) > 1 else "",
            "powroty": [k.strip() for k in pola.get("powroty", "").split(",") if k.strip()],
        })
    return lekcje, bledy


def _evals_agenta(historia: list[dict], agent: str) -> list[tuple[dt.date, float]]:
    out = []
    for w in historia:
        if w.get("agent") != agent or w.get("czesciowy"):
            continue
        d = _data(w.get("data"))
        score = ((w.get("podsumowanie") or {}).get("razem") or {}).get("score")
        if d and isinstance(score, (int, float)):
            out.append((d, float(score)))
    return sorted(out)


def skutek(lekcja: dict, historia: list[dict]) -> dict:
    """Pomiar wdrożonej lekcji: wynik evals przed i po dacie wdrożenia, zmiana, werdykt, powroty błędu."""
    d = _data(lekcja["wdrozone"])
    seria = _evals_agenta(historia, lekcja["agent"])
    przed = [s for (dd, s) in seria if d and dd < d]
    po = [s for (dd, s) in seria if d and dd >= d]
    out = {"przed": przed[-1] if przed else None, "po": po[0] if po else None, "powroty": lekcja["powroty"]}
    if out["przed"] is None or out["po"] is None:
        out["werdykt"] = "brak pomiaru"
    else:
        zmiana = round(out["po"] - out["przed"], 4)
        out["zmiana"] = zmiana
        out["werdykt"] = "pomogło" if zmiana >= PROG else "zaszkodziło" if zmiana <= -PROG else "bez zmian"
    if lekcja["powroty"]:
        out["uwaga"] = f"błąd wrócił po wdrożeniu ({len(lekcja['powroty'])}×): reguła nie działa, popraw ją albo cofnij"
    return out


def ocen(lekcje: list[dict], historia: list[dict], dzis: dt.date) -> dict:
    gotowe, przeterminowane, wdrozone, czeka = [], [], [], []
    for lk in lekcje:
        if lk["wdrozone"]:
            wdrozone.append({**lk, "skutek": skutek(lk, historia)})
            continue
        ost = _data(lk["ostatnio"])
        if ost and (dzis - ost).days > DNI_WAZNOSCI:
            przeterminowane.append(lk)
        elif min(lk["potwierdzenia"], lk["rozne_karty"] or lk["potwierdzenia"]) >= 3 or (
                lk["waga"] in WAGI and lk["potwierdzenia"] >= 1):
            gotowe.append(lk)
        else:
            czeka.append(lk)
    return {"gotowe": gotowe, "przeterminowane": przeterminowane, "wdrozone": wdrozone, "czeka": len(czeka),
            "razem": len(lekcje)}


def domyslne() -> tuple[Path, Path]:
    dane = Path(os.environ.get("JARVO_DATA_DIR") or "")
    if not str(dane) or str(dane) == ".":
        h = Path(os.environ.get("HERMES_HOME", "/opt/data"))
        dane = h.parent.parent if h.parent.name == "profiles" else h
    jarvo = dane / "jarvo"
    return jarvo / "knowledge" / "fleet" / "lekcje.md", jarvo / "evals" / "historia.jsonl"


def podsumuj(plik: Path, evals: Path, dzis: dt.date | None = None) -> dict:
    """Wynik dla przeglądu tygodnia (fleet_report.py): brak księgi = pusty wynik, nie błąd."""
    try:
        tekst = plik.read_text(encoding="utf-8")
    except OSError:
        return {"razem": 0, "gotowe": [], "przeterminowane": [], "wdrozone": [], "czeka": 0, "bledy_formatu": []}
    historia = []
    try:
        for line in evals.read_text(encoding="utf-8").splitlines():
            try:
                historia.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        pass
    lekcje, bledy = wczytaj(tekst)
    return {**ocen(lekcje, historia, dzis or dt.date.today()), "bledy_formatu": bledy}


def main(argv: list[str] | None = None) -> int:
    plik, evals = domyslne()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plik", type=Path, default=plik)
    ap.add_argument("--evals", type=Path, default=evals)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    wynik = podsumuj(args.plik, args.evals)
    if not args.json:
        print(f"Lekcje: {wynik['razem']} (gotowe {len(wynik['gotowe'])}, czeka {wynik['czeka']}, "
              f"do usunięcia {len(wynik['przeterminowane'])}, wdrożone {len(wynik['wdrozone'])})")
        for w in wynik["wdrozone"]:
            s = w["skutek"]
            print(f"- [{w['agent']}] {w['regula'][:70]}: {s['werdykt']}" + (f" ({s['uwaga']})" if s.get("uwaga") else ""))
    print(json.dumps(wynik, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
