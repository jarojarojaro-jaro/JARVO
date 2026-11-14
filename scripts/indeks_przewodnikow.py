#!/usr/bin/env python3
"""INDEX.tsv nakładki `modern-web-guidance` (jarvo-web): lokalna wyszukiwarka przewodników Modern Web Guidance.

    python3 scripts/indeks_przewodnikow.py <klon modern-web-guidance na commicie z locka>

Wejście: klon repo dystrybucji (https://github.com/GoogleChrome/modern-web-guidance) na commicie `rev` źródła
`modern-web-guidance` z vendor/skills.lock.yaml (skrypt sprawdza HEAD). Wyjście: INDEX.tsv w skillu własnym, nad
którym leży wpis locka (`dest` = web/modern-web-guidance/upstream), wiersz na przewodnik, posortowane po id:

    id <TAB> tytuł (H1) <TAB> opis <TAB> upstream/guides/<kategoria>/<id>.md

Opis = opis z listy przewodników w README dystrybucji (ten sam co w wyszukiwarce CLI upstreamu); przewodnik spoza
listy dostaje pierwsze zdanie swojego tekstu (≤ 220 znaków). Wynik zależy tylko od plików klonu (deterministyczny).

Po zmianie `rev` w locku: przejrzyj diff upstreamu, sklonuj nowy commit, uruchom ten skrypt i dołącz zmieniony
INDEX.tsv do tego samego commita. Build (scripts/build.py) zatrzymuje się, gdy indeks nie pasuje do przewodników.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import fleetlib as fl

ZRODLO = "modern-web-guidance"
AGENT = "jarvo-web"
LIMIT_OPISU = 220
WPIS_README = re.compile(r"^- \*\*\[([^\]]+)\]\([^)]*\)\*\*: (.+)$", re.M)


def _pole(tekst: str) -> str:
    return " ".join(tekst.split())          # bez tabulatorów i nowych linii w polu TSV


LISTA = re.compile(r"^(?:[-*+]|\d+\.)\s")


def pierwsze_zdanie(tekst: str) -> str:
    """Pierwsze zdanie pierwszego akapitu prozy (bez nagłówków i bloków kodu); gdy przewodnik zaczyna się listą
    (spis treści, same reguły DO/DON'T), tytuły jego sekcji ## rozdzielone średnikami."""
    w_kodzie = False
    akapit: list[str] = []
    for linia in tekst.splitlines():
        if linia.lstrip().startswith("```"):
            w_kodzie = not w_kodzie
            continue
        if w_kodzie or linia.startswith("#"):
            continue
        if linia.strip():
            akapit.append(linia.strip())
        elif akapit:
            break
    if akapit and LISTA.match(akapit[0]):
        sekcje = [re.sub(r"^\d+\.\s*", "", l[3:].strip()) for l in tekst.splitlines() if l.startswith("## ")]
        zdanie = "; ".join(s for s in sekcje if s.lower() not in {"table of contents", "overview"})
        return zdanie if len(zdanie) <= LIMIT_OPISU else zdanie[:LIMIT_OPISU - 1].rstrip(" ;") + "…"
    zdanie = _pole(" ".join(akapit))
    if m := re.match(r"(.+?[.!?])(\s|$)", zdanie):
        zdanie = m.group(1)
    return zdanie if len(zdanie) <= LIMIT_OPISU else zdanie[:LIMIT_OPISU - 1].rstrip() + "…"


def wiersze(klon: Path, sciezka: str, prefiks: str) -> list[tuple[str, str, str, str]]:
    opisy = {m.group(1): _pole(m.group(2)) for m in WPIS_README.finditer((klon / "README.md").read_text(encoding="utf-8"))}
    skill = klon / sciezka
    out = []
    for md in sorted((skill / "guides").rglob("*.md")):
        tekst = md.read_text(encoding="utf-8")
        tytul = next((_pole(l[2:]) for l in tekst.splitlines() if l.startswith("# ")), md.stem)
        out.append((md.stem, tytul, opisy.get(md.stem) or pierwsze_zdanie(tekst),
                    f"{prefiks}/{md.relative_to(skill).as_posix()}"))
    ids = [w[0] for w in out]
    if len(set(ids)) != len(ids):
        raise SystemExit("zduplikowane id przewodników: indeks po id byłby niejednoznaczny")
    return sorted(out)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 1
    klon = Path(argv[0])
    lock = fl.load_lock()
    rev = lock["sources"][ZRODLO]["rev"]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=klon, check=True, capture_output=True, text=True).stdout.strip()
    if head != rev:
        raise SystemExit(f"klon jest na {head}, lock wymaga {rev} (git -C {klon} checkout {rev})")
    wpis = next(e for e in lock["agents"][AGENT] if e["source"] == ZRODLO)
    nakladka, podkatalog = wpis["dest"].rsplit("/", 1)
    cel = fl.PROFILES_DIR / AGENT / "skills" / nakladka / "INDEX.tsv"
    tabela = wiersze(klon, wpis["path"], podkatalog)
    with cel.open("w", encoding="utf-8", newline="\n") as f:
        f.writelines("\t".join(w) + "\n" for w in tabela)
    print(f"{cel.relative_to(fl.REPO_ROOT).as_posix()}: {len(tabela)} przewodników (rev {rev[:7]})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
