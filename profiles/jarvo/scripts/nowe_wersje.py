#!/usr/bin/env python3
"""Rutyna „Nowe wersje” bez modelu: nowsze wydania programów przypiętych w instalacji Jarva trafiają jako zlecenie do
Claude Code (`missions/DLA-CLAUDE.md`), zanim ktoś o nie zapyta.

    python3 nowe_wersje.py [--repo <kod Jarva>] [--pokaz]

Decyzja właściciela 14.11 („jak wychodzi nowe, to mieć na uwadze i updatować”; agent-browser stał na 0.38.1, gdy
wyszło 0.43.0 z poprawkami bezpieczeństwa). Źródła prawdy o wersjach to pliki kodu bieżącej instalacji
(JARVO_REPO): `vendor/natywne.yaml` (narzędzia z wydań GitHuba, Chrome for Testing, Node.js, Hermes) i
`infra/node/package.json` (paczki npm floty). Aktualizacja i tak przechodzi przegląd z docs/SOURCES.md, więc rutyna
niczego nie instaluje: gdy są nowe wydania, dopisuje jeden wiersz `- [ ] data · co · po co · plik` ze wszystkimi
naraz (adresy wydań w stanie), a Claude Code bierze go na starcie sesji (`stan-jarva`, wiersz „Zlecenia dla Claude”). To samo wydanie zgłasza raz (stan w
`<stan>/nowe-wersje.json`); `stan-jarva` ostrzega, gdy rutyna długo nie sprawdzała.

Cron uruchamia ją bez agenta (no_agent): wyjście idzie do właściciela, a puste wyjście to cisza, więc bez `--pokaz`
nic nie wypisuje. Błąd sieci przy jednym źródle nie zatrzymuje pozostałych; trafia do stanu, nie do właściciela.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Callable

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _sciezki  # noqa: E402  (katalogi z HERMES_HOME, nie z /opt)

GITHUB = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/releases/download/([^/]+)/")
CFT = re.compile(r"^https://storage\.googleapis\.com/chrome-for-testing-public/([\d.]+)/")
NODE = re.compile(r"^https://nodejs\.org/dist/v([\d.]+)/")
CFT_STABLE = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json"
NODE_INDEX = "https://nodejs.org/dist/index.json"
NPM = "https://registry.npmjs.org/{}/latest"
PO_CO = ("decyzja właściciela 16.11: nowe wersje bierzemy od razu, bez testów porównawczych (sprawdził je producent); "
         "zostają automatyczne testy repo i sumy pobrań")

Pobierz = Callable[[str], object]


def pobierz_json(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "jarvo-nowe-wersje", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 (stałe adresy https)
        return json.load(r)


def wersja(tekst: str) -> tuple[int, ...]:
    """Liczby z tagu w kolejności: „v0.43.0” → (0, 43, 0), „cua-driver-rs-v0.38.0” → (0, 38, 0), „20261021” → (20261021,).
    Dzienne buildy BtbN („autobuild-RRRR-MM-DD-…”) liczą się po miesiącu: przypinamy build z końca miesiąca, a nowy dzień
    to nie nowa wersja."""
    liczby = tuple(int(x) for x in re.findall(r"\d+", tekst))
    return liczby[:2] if tekst.startswith("autobuild-") else liczby


def przedrostek(tag: str) -> str:
    """Część tagu przed pierwszą cyfrą: wydania innego produktu z tego samego repo („cua-agent-v…”) mają inny."""
    return re.split(r"\d", tag, maxsplit=1)[0]


def przypiete(repo: Path) -> list[dict]:
    """Co jest przypięte w kodzie instalacji: nazwa, wersja, rodzaj źródła i dane do sprawdzenia."""
    dane = yaml.safe_load((repo / "vendor/natywne.yaml").read_text(encoding="utf-8"))
    wynik: list[dict] = []
    h = dane.get("hermes") or {}
    m = re.match(r"https://github\.com/([^/]+)/([^/]+?)/?$", str(h.get("repo", "")))
    if m and h.get("tag"):
        wynik.append({"nazwa": "hermes", "pin": str(h["tag"]), "rodzaj": "github", "owner": m[1], "repo": m[2], "tag": str(h["tag"]),
                      "plik": "vendor/natywne.yaml (hermes)"})
    for nazwa, w in (dane.get("narzedzia") or {}).items():
        urls = [p["url"] for p in (w.get("pliki") or {}).values() if isinstance(p, dict) and p.get("url")]
        if not urls:
            continue
        u = urls[0]
        if m := GITHUB.match(u):
            wynik.append({"nazwa": nazwa, "pin": str(w.get("wersja", m[3])), "rodzaj": "github", "owner": m[1], "repo": m[2],
                          "tag": m[3], "plik": "vendor/natywne.yaml"})
        elif m := CFT.match(u):
            wynik.append({"nazwa": nazwa, "pin": m[1], "rodzaj": "chrome", "plik": "vendor/natywne.yaml"})
        elif m := NODE.match(u):
            wynik.append({"nazwa": nazwa, "pin": m[1], "rodzaj": "node", "plik": "vendor/natywne.yaml"})
    pakiet = repo / "infra/node/package.json"
    if pakiet.is_file():
        for nazwa, pin in (json.loads(pakiet.read_text(encoding="utf-8")).get("dependencies") or {}).items():
            wynik.append({"nazwa": f"npm {nazwa}", "pin": str(pin), "rodzaj": "npm", "pakiet": nazwa, "plik": "infra/node/package.json"})
    return wynik


def najnowsza(p: dict, pobierz: Pobierz, cache: dict) -> tuple[str, str] | None:
    """(wersja, adres wydania) nowsza niż przypięta albo None. Wyjątek sieci idzie wyżej."""
    if p["rodzaj"] == "github":
        klucz = f"{p['owner']}/{p['repo']}"
        if klucz not in cache:
            cache[klucz] = pobierz(f"https://api.github.com/repos/{klucz}/releases?per_page=40")
        pref = przedrostek(p["tag"])
        beta = bool(re.search(r"(?i)alpha|beta|rc", p["tag"]))
        tagi = [r for r in cache[klucz] if isinstance(r, dict) and not r.get("draft") and (beta or not r.get("prerelease"))
                and przedrostek(r.get("tag_name", "")) == pref and wersja(r.get("tag_name", ""))]
        if pref == "autobuild-" and tagi:
            # FFmpeg-Builds trzyma 14 ostatnich buildów dziennych, a 2 lata tylko ostatni build miesiąca: build z miesiąca,
            # który trwa, zniknie (pin by się zepsuł). Liczy się ostatni build miesiąca, po którym jest już następny.
            biezacy = max(wersja(r["tag_name"]) for r in tagi)
            tagi = [r for r in tagi if wersja(r["tag_name"]) < biezacy]
        if not tagi:
            return None
        top = max(tagi, key=lambda r: (wersja(r["tag_name"]), tuple(int(x) for x in re.findall(r"\d+", r["tag_name"]))))
        if wersja(top["tag_name"]) > wersja(p["tag"]):
            return top["tag_name"], top.get("html_url") or f"https://github.com/{klucz}/releases/tag/{top['tag_name']}"
        return None
    if p["rodzaj"] == "chrome":
        if "cft" not in cache:
            cache["cft"] = pobierz(CFT_STABLE)
        stabilna = cache["cft"]["channels"]["Stable"]["version"]
        return (stabilna, "https://googlechromelabs.github.io/chrome-for-testing/") if wersja(stabilna) > wersja(p["pin"]) else None
    if p["rodzaj"] == "node":
        if "node" not in cache:
            cache["node"] = pobierz(NODE_INDEX)
        glowna = wersja(p["pin"])[0]
        ta_linia = [r["version"].lstrip("v") for r in cache["node"] if wersja(r["version"])[:1] == (glowna,)]
        top = max(ta_linia, key=wersja, default=p["pin"])
        return (top, f"https://nodejs.org/en/blog/release/v{top}") if wersja(top) > wersja(p["pin"]) else None
    if p["rodzaj"] == "npm":
        nowa = str(pobierz(NPM.format(p["pakiet"].replace("/", "%2f")))["version"])
        return (nowa, f"https://www.npmjs.com/package/{p['pakiet']}/v/{nowa}") if wersja(nowa) > wersja(p["pin"]) else None
    return None


def sprawdz(repo: Path, stan_plik: Path, zlecenia: Path, pobierz: Pobierz = pobierz_json, dzis: dt.date | None = None) -> list[str]:
    """Dopisuje zlecenia dla nowych wydań i zwraca ich wiersze (do `--pokaz`)."""
    dzis = dzis or dt.date.today()
    try:
        stan = json.loads(stan_plik.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stan = {}
    zgloszone: dict = stan.get("zgloszone", {})
    bledy: dict = {}
    nowe: list[str] = []
    cache: dict = {}
    for p in przypiete(repo):
        try:
            n = najnowsza(p, pobierz, cache)
        except Exception as e:  # noqa: BLE001 (jedno źródło nie zatrzymuje reszty)
            bledy[p["nazwa"]] = f"{type(e).__name__}: {str(e)[:120]}"
            continue
        if n is None:
            zgloszone.pop(p["nazwa"], None)       # pin dogonił wydanie: następne nowe zgłosimy od nowa
            continue
        if zgloszone.get(p["nazwa"]) == n[0]:
            continue
        zgloszone[p["nazwa"]] = n[0]
        nowe.append(f"{p['nazwa']} {p['pin']} → {n[0]} ({n[1]}; {p['plik']})")
    if nowe:
        # jedno zlecenie na przebieg: pierwszy przebieg 14.11 znalazł 19 wydań naraz, a każde i tak przechodzi ten sam
        # przegląd; w zleceniu nazwy i wersje, adresy wydań w stanie
        krotko = ", ".join(re.sub(r" \(.*\)$", "", n) for n in nowe)
        wiersz = f"- [ ] {dzis.isoformat()} · nowe wersje ({len(nowe)}): {krotko} · {PO_CO} · {stan_plik}"
        tekst = zlecenia.read_text(encoding="utf-8") if zlecenia.is_file() else "# Zlecenia dla Claude Code\n"
        zlecenia.parent.mkdir(parents=True, exist_ok=True)
        zlecenia.write_text(tekst.rstrip("\n") + "\n" + wiersz + "\n", encoding="utf-8")
    stan_plik.parent.mkdir(parents=True, exist_ok=True)
    stan_plik.write_text(json.dumps({"sprawdzone": dt.datetime.now().isoformat(timespec="seconds"), "zgloszone": zgloszone,
                                     "ostatnio_nowe": nowe, "bledy": bledy}, ensure_ascii=False, indent=1), encoding="utf-8")
    return nowe


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=os.environ.get("JARVO_REPO", ""), help="kod bieżącej instalacji (JARVO_REPO)")
    ap.add_argument("--pokaz", action="store_true", help="wypisz dopisane zlecenia (ręcznie; cron zostaje cichy)")
    a = ap.parse_args(argv)
    repo = Path(a.repo) if a.repo else Path(__file__).resolve().parents[3]
    if not (repo / "vendor/natywne.yaml").is_file():
        return 0                                     # obraz bez manifestu: nic do porównania, cisza
    nowe = sprawdz(repo, _sciezki.stan() / "nowe-wersje.json", _sciezki.misje() / "DLA-CLAUDE.md")
    if a.pokaz:
        print("\n".join(nowe) or "nic nowego")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
