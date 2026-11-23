#!/usr/bin/env python3
"""Build Jarvo HQ (pluginu dashboardu Hermesa) i jego wersji demo.

    python3 scripts/hqbuild.py --out build/plugins/jarvo-hq     # plugin (wołane też przez scripts/build.py)
    python3 scripts/hqbuild.py --demo build/hq-demo            # samodzielne demo z symulacją floty

Plugin: <out>/dashboard/{manifest.json, plugin_api.py, hq_core.py, przenosne.py, sciezki.py, ochrona.py, edytor.py,
animacja.py, rozmowy.py, czytnik.py, wzmianki.py, kontekst.py, agenci.py, brama.py, strumien.py, przebiegi.py, scalanie.py,
budzenia.py, prace.py, obserwator.py, silnik.py, trasy_rozmow.py, komendy.py, aplikacja.py, podpowiedzi.py, glos.py, mozg.py,
trasy_aplikacji.py, pomiar.py, liczby.py, _sciezki.py, konwertuj.py, izometria/, fleet.json, logowanie.html, dzwieki/,
dist/index.js, dist/zasoby/, dist/fonts/}. Pakiet, loader i pliki demo mają końce linii „\\n” także na Windows (te same
bajty na każdym systemie).
Pakiet aplikacji to sklejone hq/web/src/*.js (w kolejności nazw) w jednym IIFE, z htm (Apache-2.0) na początku; trafia do
dist/zasoby/app-<sha256[:12]>.js (z bliźniakiem .gz), style do app-<h>.css, kroje aplikacji do zasoby/kroje/.
dist/index.js to mały loader (≤ 4 KB, dashboard serwuje go na każdej stronie): rejestruje zakładkę /jarvo i dopiero
na niej wczytuje pakiet przez trasę /api/plugins/jarvo-hq/zasoby/ (cache na rok, gzip), z osłoną błędów.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleetlib as fl  # noqa: E402

HQ = fl.REPO_ROOT / "hq"
PLUGIN_FILES = ("manifest.json", "plugin_api.py", "hq_core.py", "ochrona.py", "edytor.py", "animacja.py",
                # przenośne pomocniki (podprocesy w wątkach, blokada, ACL) i ścieżki danych (alias /opt/data)
                "przenosne.py", "sciezki.py",
                # silnik rozmów aplikacji (docs/HQ.md „Rozmowy”): magazyn rozmowy.db, czytnik sesji Hermesa, wzmianki,
                # blok kontekstu, lista agentów, klient bramy, strumień SSE, rejestr przebiegów, oś czasu, budzenia,
                # praca floty, karty pracy w wątku, obserwator, wątek silnika i trasy; start aplikacji (gotowość,
                # podpowiedzi N0, GET /app)
                "rozmowy.py", "czytnik.py", "wzmianki.py", "kontekst.py", "agenci.py", "brama.py", "strumien.py",
                "przebiegi.py", "scalanie.py", "budzenia.py", "prace.py", "karty.py", "obserwator.py", "silnik.py",
                "trasy_rozmow.py",
                # komendy po „/” w kompozytorze (docs/HQ.md „Komendy”): /model, /new, /stop, /usage, /status, /help
                "komendy.py",
                "aplikacja.py", "podpowiedzi.py", "glos.py", "mozg.py", "trasy_aplikacji.py",
                # panel w sieci Tailscale: drugi nasłuch z logowaniem kluczem jednorazowym (docs/HQ.md „Panel w sieci”)
                "siec.py",
                # sesje omp jako rozmówcy (centrum 1d): skrzynka, stan, ogon tury; oś z pliku sesji bez wyników narzędzi
                "omp_sesje.py", "czytnik_omp.py",
                # rozmówcy panelu (centrum 1b): sesja tematu Telegrama, lustro panel → temat, stałe wątki i stan
                "tematy.py", "lustro.py", "rozmowcy.py",
                # źródła Mózgu (docs/HQ.md „Mózg”): skarbiec Jarva i grafy z konfig/mozg.json
                "mozg_zrodla.py",
                # kanał Aktualizacje (docs/HQ.md „Aktualizacje”): archiwum raportów rutyn z cron/output profili
                "raporty.py")
# wspólny graf wiedzy (canvas, układ sił): zakładka Wiedza (Mózg aplikacji HQ ma od 22.11 własną mapę-neuron)
GRAF_WSPOLNY = fl.REPO_ROOT / "shared" / "web" / "graf.js"


def bundle_js(src_dir: Path | None = None, naglowek: str = "Jarvo HQ: plugin dashboardu Hermesa. Plik generowany przez scripts/hqbuild.py z hq/web/src/.",
              wspolne: tuple[Path, ...] | None = None) -> str:
    """Jedno IIFE z htm, plikami `wspolne` (np. shared/web/graf.js) i src/*.js (w kolejności nazw); ten sam pakowacz
    służy zakładce „Wiedza” (wiedza/web/src, z grafem wspólnym). Bez `src_dir` = aplikacja HQ."""
    wspolne = wspolne or ()
    src_dir = src_dir or HQ / "web" / "src"
    htm = (HQ / "web" / "vendor" / "htm.umd.js").read_text(encoding="utf-8").strip()
    parts = [
        f"/* {naglowek} */",
        "/* htm 3.1.1 (c) Jason Miller, Apache-2.0: https://github.com/developit/htm */",
        "(function () {",
        "var htm = (function () { var module = { exports: {} }; var exports = module.exports;",
        htm,
        "return module.exports; })();",
        '"use strict";',
    ]
    for src in [*wspolne, *sorted(src_dir.glob("*.js"))]:
        parts.append(f"\n// ---- {src.name}\n" + src.read_text(encoding="utf-8"))
    parts.append("})();")
    return "\n".join(parts) + "\n"


# ------------------------------------------------------------------ podział pakietu (docs/HQ.md §2f „Pakiety”)
# Plugin dostaje rdzeń (app-rdzen-<h>.js: powłoka, rozmówcy, wątek, kompozytor, Markdown, strumień, API, i18n PL)
# i pakiety na żądanie, które 00-base.js wczytuje przez Zasoby.wczytaj(nazwa). Pliki pakietów to wzorce nazw w
# hq/web/src; `wspolne` to pliki spoza src dołączane na początek (dziś żaden pakiet ich nie ma). `zalezy`: pakiety
# wczytywane razem (Stara Baza otwiera edytor, edytor używa okien Bazy). Demo i testy biorą pełny pakiet (bundle_js).
PAKIETY = {
    # 19-piksele.js (silnik pikseli: pokoje, figurki): tylko wieża Starej Bazy; aplikacja ma znaki TARS (22-figurka.js)
    "baza": {"pliki": ("19-piksele.js", "20-art.js", "30-building.js", "40-panel.js", "50-chat.js", "56-flota.js", "60-hud.js",
                       "89-baza.js"), "zalezy": ("edytor",)},
    "edytor": {"pliki": ("43-*.js", "44-*.js", "45-*.js", "46-*.js", "47-*.js", "48-*.js", "49-*.js", "55-*.js"),
               "zalezy": ("baza",)},
    # pierwsze spotkanie z lektorem (nowa instalacja) i Ustawienia: poza pierwszym wyświetleniem rozmowy
    "poznajmy": {"pliki": ("36-glos.js", "37-poznajmy.js"), "zalezy": ()},
    "ustawienia": {"pliki": ("62-ustawienia.js",), "zalezy": ()},
    "mozg": {"pliki": ("63-mozg-neuron.js", "63-mozg.js"), "zalezy": ()},
    # Aktualizacje (#/aktualizacje): archiwum raportów rutyn, poza pierwszym wyświetleniem rozmowy
    "raporty": {"pliki": ("64-raporty.js",), "zalezy": ()},
    # stopka kompozytora (model, myślenie, tryb szybki, pierścień kontekstu z dymkiem): przy pierwszej otwartej
    # rozmowie, do tej pory rząd bloczka ma tylko „Do:”, spinacz i wysyłanie (ta sama wysokość)
    "stopka": {"pliki": ("33-stopka.js",), "zalezy": ()},
}
# budżet gzip (bajty) z projektu etapu 1 §7: przekroczenie zatrzymuje build. Mózg 20 KB (20.11, było 14 KB, przedtem
# 6 KB): części, grupy, szukanie w treści, [[linki]] i skupiska w grafie, a od 20.11 tożsamość Jarva, edytor pamięci
# (GET/PUT /pamiec), „Wstecz”, „Najważniejsze” ze streszczeń hubów i spis sekcji, wszystko PL i EN (ok. 18 KB); 21 KB
# od 22.11: wejście jako sieć SVG (MozgSiec) zamiast osobnego pakietu „kosmos” (−4,2 KB gzip w sumie); od 22.11
# wieczorem cały Mózg to jedna mapa-neuron w WebGL (63-mozg-neuron.js) i strona notatki zamiast listy i grafu canvas
# (shared/web/graf.js, 6,5 KB gzip, został tylko w zakładce Wiedza): 25 KB (ok. 24 KB: renderer WebGL z układem,
# włóknami, impulsami i kamerą ok. 6 KB, strona notatki z „Edytuj”); pakiet idzie tylko po wejściu w Mózg. Rdzeń
# 100 KB (20.11, było 95 KB): rozwijane kroki i komendy po „/” w kompozytorze
# (oba muszą działać od pierwszej rozmowy)
BUDZET_GZIP = {"app-rdzen.js": 100 * 1024, "app-rdzen.css": 18 * 1024, "mozg.js": 25 * 1024}
ZNACZNIK_PAKIETOW = '"@@PAKIETY@@"'
ZNACZNIK_CSS = re.compile(r"^/\* @@pakiet (\w+) \*/$", re.M)
DEKLARACJA = re.compile(r"^(?:async\s+)?(?:function\*?\s+([A-Za-z_$][\w$]*)|class\s+([A-Za-z_$][\w$]*)"
                        r"|(?:const|let|var)\s+(\{[^}]*\}|[A-Za-z_$][\w$]*[^\n]*))",
                        re.M)
# słowa, po których „/” zaczyna wyrażenie regularne, a nie dzielenie
PRZED_REGEXEM = {"return", "typeof", "case", "do", "else", "in", "of", "new", "delete", "void", "throw", "yield", "await"}


def pakiet_pliku(nazwa: str) -> str:
    """Pakiet pliku z hq/web/src: nazwa z PAKIETY albo „rdzen”."""
    import fnmatch
    for pakiet, opis in PAKIETY.items():
        if any(fnmatch.fnmatchcase(nazwa, w) for w in opis["pliki"]):
            return pakiet
    return "rdzen"


def nazwy_globalne(kod: str) -> list[str]:
    """Nazwy zadeklarowane na najwyższym poziomie pliku (deklaracje od pierwszej kolumny, jak w hq/web/src)."""
    out: list[str] = []
    for m in DEKLARACJA.finditer(kod):
        if m.group(1) or m.group(2):
            out.append(m.group(1) or m.group(2))
            continue
        g = m.group(3)
        if g.startswith("{"):        # const { a, b: c } = …
            out += [n.split(":")[-1].strip() for n in g.strip("{} ").split(",") if n.strip()]
        else:                        # const a = 1, b = 2 (przecinki poza nawiasami i łańcuchami)
            out.append(re.match(r"[A-Za-z_$][\w$]*", g).group(0))
            linia, glebokosc = re.sub(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|`[^`]*`", '""', g), 0
            for i, c in enumerate(linia):
                glebokosc += (c in "([{") - (c in ")]}")
                if c == "," and glebokosc == 0:
                    m2 = re.match(r",\s*([A-Za-z_$][\w$]*)\s*=", linia[i:])
                    if m2:
                        out.append(m2.group(1))
    return list(dict.fromkeys(out))


def uzyte(kod: str, nazwy) -> list[str]:
    """Które z nazw występują w kodzie jako identyfikatory (nie jako pole po kropce)."""
    slowa = set(re.findall(r"(?<![\w$.])[A-Za-z_$][\w$]*", kod))
    return [n for n in nazwy if n in slowa]


def zwiez_js(kod: str) -> str:
    """Bez komentarzy, wcięć i pustych linii; łańcuchy, wyrażenia regularne i szablony bez zmian, poza szablonami
    html`…`, w których htm i tak usuwa białe znaki z nową linią (wcięcia po nowej linii znikają). Nowe linie zostają
    (automatyczne średniki), więc wynik zachowuje się jak źródło; test_hq_zasoby.py sprawdza go w node."""
    out: list[str] = []
    stos: list[str] = []          # "{" klamra kodu, "$" wyrażenie w szablonie, "`"/"h" szablon (h = html`…`)
    i, n = 0, len(kod)
    ostatni = ""                  # ostatni znaczący fragment kodu (rozpoznanie regexu)

    def nowa_linia():
        while out and out[-1] in (" ", "\t"):
            out.pop()
        if out and out[-1] != "\n":
            out.append("\n")

    while i < n:
        c = kod[i]
        if stos and stos[-1] in "`h":                      # tekst szablonu
            if c == "\\":
                out.append(kod[i:i + 2]); i += 2; continue
            if c == "`":
                stos.pop(); out.append(c); i += 1; ostatni = "`"; continue
            if c == "$" and kod.startswith("${", i):
                stos.append("$"); out.append("${"); i += 2; ostatni = "{"; continue
            if c == "\n" and stos[-1] == "h":
                out.append(c); i += 1
                while i < n and kod[i] in " \t":
                    i += 1
                continue
            out.append(c); i += 1; continue
        if c in "'\"":
            j = i + 1
            while j < n and kod[j] != c:
                j += 2 if kod[j] == "\\" else 1
            out.append(kod[i:j + 1]); i = j + 1; ostatni = c; continue
        if c == "`":
            stos.append("h" if ostatni == "html" else "`"); out.append(c); i += 1; continue
        if c == "/" and kod.startswith("//", i):
            j = kod.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and kod.startswith("/*", i):
            j = kod.find("*/", i + 2)
            tresc = kod[i:j + 2]
            i = j + 2
            if "\n" in tresc:
                nowa_linia()
            elif out and out[-1] not in " \n":
                out.append(" ")
            continue
        if c == "/":
            regex = not ostatni or ostatni in PRZED_REGEXEM or ostatni in tuple("(,=:[!&|?{};+-*%<>~^\n")
            if regex:
                j, klasa = i + 1, False
                while j < n:
                    if kod[j] == "\\":
                        j += 2; continue
                    if kod[j] == "[":
                        klasa = True
                    elif kod[j] == "]":
                        klasa = False
                    elif kod[j] == "/" and not klasa:
                        break
                    j += 1
                j += 1
                while j < n and (kod[j].isalnum()):
                    j += 1
                out.append(kod[i:j]); i = j; ostatni = "/r"; continue
        if c == "\n":
            nowa_linia(); i += 1
            while i < n and kod[i] in " \t":
                i += 1
            continue
        if c in " \t":
            if out and out[-1] not in " \n":
                out.append(" ")
            i += 1; continue
        if c == "{":
            stos.append("{")
        elif c == "}" and stos:
            if stos.pop() == "$":
                out.append(c); i += 1; ostatni = "}"; continue
        m = re.compile(r"[A-Za-z_$][\w$]*|\d[\w.]*").match(kod, i)
        if m:
            out.append(m.group(0)); i = m.end(); ostatni = m.group(0); continue
        out.append(c); i += 1; ostatni = c
    return "".join(out).strip() + "\n"


def _htm() -> list[str]:
    htm = (HQ / "web" / "vendor" / "htm.umd.js").read_text(encoding="utf-8").strip()
    return ["/* htm 3.1.1 (c) Jason Miller, Apache-2.0: https://github.com/developit/htm */",
            "var htm = (function () { var module = { exports: {} }; var exports = module.exports;", htm,
            "return module.exports; })();"]


def podziel_i18n(kod: str) -> tuple[str, str]:
    """04-i18n.js → (rdzeń ze słownikiem angielskim pustym, treść słownika angielskiego). Angielski idzie osobnym
    pakietem „en”, wczytywanym tylko przy angielskim dashboardzie (polski to język domyślny)."""
    poczatek = kod.index("\n  en: {\n") + len("\n  en: ")
    koniec = kod.index("\n  },\n};\n", poczatek) + len("\n  }")
    return kod[:poczatek] + "{}" + kod[koniec:], kod[poczatek:koniec]


def pakiety_js(src_dir: Path | None = None) -> dict[str, str]:
    """Pakiety pluginu: {"rdzen": kod, "baza": kod, …, "en": kod}. Rdzeń to IIFE jak w bundle_js z placeholderem
    ZNACZNIK_PAKIETOW (build_plugin wstawia nazwy plików) i na końcu eksportem do window.__JARVO_W__ tych nazw, których
    używają pakiety. Pakiet to IIFE, które bierze nazwy rdzenia z __JARVO_W__, deklaruje nazwy innych pakietów
    (uzupełniane, gdy te dojdą: Zasoby.wczytaj ładuje zależności równolegle) i rejestruje swoje przez W.__pakiet."""
    src_dir = src_dir or HQ / "web" / "src"
    zrodla: dict[str, list[tuple[str, str]]] = {"rdzen": []}
    for p in PAKIETY:
        zrodla[p] = [(w, (fl.REPO_ROOT / w).read_text(encoding="utf-8")) for w in PAKIETY[p].get("wspolne", ())
                     if (fl.REPO_ROOT / w).exists()]
    en = ""
    for src in sorted(src_dir.glob("*.js")):
        kod = src.read_text(encoding="utf-8")
        if src.name == "04-i18n.js":
            kod, en = podziel_i18n(kod)
        zrodla[pakiet_pliku(src.name)].append((src.name, kod))
    kody = {p: "\n".join(f"// ---- {nazwa}\n{k}" for nazwa, k in pliki) for p, pliki in zrodla.items()}
    kody["en"] = f"Object.assign(SLOWNIK.en, {en});\n"
    globalne = {p: nazwy_globalne(k) for p, k in kody.items()}
    rdzen_nazwy = globalne["rdzen"]
    eksport: set[str] = set()
    out: dict[str, str] = {}
    for p in [*PAKIETY, "en"]:
        if p != "en" and not zrodla[p]:
            continue
        wlasne = set(globalne[p])
        z_rdzenia = [x for x in uzyte(kody[p], rdzen_nazwy) if x not in wlasne]
        obce = sorted({x for q in PAKIETY if q != p for x in uzyte(kody[p], globalne[q]) if x not in wlasne})
        eksport.update(z_rdzenia)
        czesci = [f"/* Jarvo HQ: pakiet „{p}” (na żądanie). Plik generowany przez scripts/hqbuild.py. */",
                  "(function () {", '"use strict";', "var __W = window.__JARVO_W__;"]
        if z_rdzenia:
            czesci.append("var { " + ", ".join(z_rdzenia) + " } = __W;")
        if obce:
            czesci.append("var " + ", ".join(obce) + ";")
        czesci.append(kody[p])
        uzup = "; ".join(f"{x} = __W.{x}" for x in obce)
        czesci.append(f'__W.__pakiet("{p}", {{ {", ".join(globalne[p])} }}, function () {{ {uzup} }});')
        czesci.append("})();")
        out[p] = zwiez_js("\n".join(czesci))
    rdzen = ["/* Jarvo HQ: rdzeń aplikacji. Plik generowany przez scripts/hqbuild.py z hq/web/src/. */",
             "(function () {", *_htm(), '"use strict";', kody["rdzen"],
             "Object.assign(window.__JARVO_W__, { " + ", ".join(x for x in rdzen_nazwy if x in eksport) + " });", "})();"]
    out["rdzen"] = zwiez_js("\n".join(rdzen))
    return out


def pakiety_css(css: str) -> dict[str, str]:
    """hq/web/style.css podzielony znacznikami „/* @@pakiet <nazwa> */” (bez znacznika: rdzeń); @import każdego
    pakietu idzie na jego początek (CSS wymaga go przed regułami)."""
    czesci: dict[str, list[str]] = {}
    pakiet, poz = "rdzen", 0
    for m in ZNACZNIK_CSS.finditer(css):
        czesci.setdefault(pakiet, []).append(css[poz:m.start()])
        pakiet, poz = m.group(1), m.end()
    czesci.setdefault(pakiet, []).append(css[poz:])
    out = {}
    for p, kawalki in czesci.items():
        tekst = "".join(kawalki)
        importy = re.findall(r"^@import [^;]+;$", tekst, re.M)
        tekst = re.sub(r"^@import [^;]+;\n?", "", tekst, flags=re.M)
        out[p] = zwiez_css("\n".join(importy) + "\n" + tekst)
    return out


def zwiez_css(css: str) -> str:
    """Bez komentarzy i zbędnych białych znaków (łańcuchy w CSS stylów HQ nie mają „/*” ani podwójnych spacji)."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r" ?([{};]) ?", r"\1", css)
    return css.replace(";}", "}").strip() + "\n"


def gzip_rozmiar(dane: bytes) -> int:
    return len(gzip.compress(dane, compresslevel=9, mtime=0))


def personality(soul: str) -> list[list]:
    """Pierwsza linia sekcji „## Osobowość” z SOUL.md („Szczerość 95%, humor 30%, …”, opcjonalnie po
    „Parametry:”) → [[nazwa, wartość], …]."""
    m = re.search(r"^## Osobowość\s*\n(?:Parametry:\s*)?([^\n]+)", soul, re.M)
    if not m:
        return []
    first = m.group(1).split(".")[0]
    return [[name.strip().capitalize(), int(val)] for name, val in re.findall(r"([^\W\d_]+)\s+(\d{1,3})%", first)]


# nazwy parametrów osobowości z SOUL.md po angielsku (HQ w wersji angielskiej)
TRAITS_EN = {"Szczerość": "Honesty", "Humor": "Humor", "Zwięzłość": "Brevity", "Ciekawość": "Curiosity",
             "Ostrożność": "Caution", "Kreatywność": "Creativity", "Dokładność": "Precision", "Empatia": "Empathy"}


def fleet_json(fleet: fl.Fleet | None = None) -> dict:
    fleet = fleet or fl.load_fleet()
    lock = fl.load_lock()
    agents = []
    for a in fleet.active():
        soul = (a.dir / "SOUL.md").read_text(encoding="utf-8") if (a.dir / "SOUL.md").exists() else ""
        agents.append({
            "name": a.name, "title": a.title, "emoji": a.emoji, "kind": a.kind,
            "room": a.hq_room, "label": a.hq_label or a.title, "short": a.hq_short, "rola": a.rola,
            "handle": a.handle, "aliasy": a.aliasy,   # uchwyt @… i złożone aliasy wzmianki (hq/plugin/wzmianki.py)
            "description": a.description, "model_tier": a.model_tier, "model": fleet.model_for(a.model_tier),
            "delegation_tier": a.delegation_tier,
            "autonomy_max": a.autonomy_max, "telegram_topic": a.telegram_topic,
            "skills": sorted(fl.skill_names(a.dir / "skills").keys()),
            "vendored": len(fl.skille_z_locka(lock, a.name)),
            "personality": personality(soul),
            "en": {"title": a.en.get("title") or a.title, "label": a.en.get("hq_label") or a.hq_label or a.title,
                   "description": a.en.get("description") or a.description, "rola": a.en.get("rola") or a.rola,
                   "personality": [[TRAITS_EN.get(k, k), v] for k, v in personality(soul)]},
        })
    # katalog modeli dla mózgu z aplikacji (hq/plugin/mozg.py): zestawy poziomów każdego dostawcy i modele zapasowe
    m = fleet.raw["models"]
    zestawy = {m["provider"]: dict(m["tiers"]), **{k: dict(v) for k, v in (m.get("presets") or {}).items()}}
    zapasowe = {k: dict(v) for k, v in (m.get("fallback") or {}).items() if isinstance(v, dict)}
    return {"orchestrator": fleet.orchestrator, "reviewer": fleet.reviewer, "agents": agents,
            "modele": {"domyslny": m["provider"], "zestawy": zestawy, "zapasowe": zapasowe}}


# Loader zakładki /jarvo (dist/index.js). Dashboard wczytuje go na każdej stronie (no-store), więc jest mały
# i bez skutków ubocznych: rejestruje komponent synchronicznie (inaczej Hermes zgłasza brak register()), a pakiet
# aplikacji i style pobiera dopiero, gdy /jarvo naprawdę się renderuje. Błąd wczytania albo renderu i pakiet, którego
# po 7 s nadal nie ma, dają ekran błędu z „Odśwież” i „Otwórz klasyczny panel”, nigdy pustą stronę (Hermes nie owija
# stron pluginów w osłonę błędów); wiszący arkusz stylów czeka najwyżej 3 s, a po błędzie następne wejście na /jarvo
# próbuje od nowa. Pakiet idzie trasą /api/plugins/jarvo-hq/zasoby/ (gzip, cache na rok); dashboard bez logowania
# (tylko 127.0.0.1, __HERMES_AUTH_REQUIRED__ false) wpuszcza /api/ wyłącznie z nagłówkiem tokenu, którego <script>
# nie wyśle, więc tam loader bierze tę samą kopię ze statycznego /dashboard-plugins/jarvo-hq/dist/zasoby/.
# Atrybuty <html>: data-jarvo-wstepnie (zasłona startowa, ustawia skrypt powłoki z branding/powloka.js),
# data-jarvo-gotowe (zasłona znika), data-jarvo-app (ukryta powłoka Hermesa; tylko aplikacja w wersji ≥ 2),
# data-jarvo-embed (strona w ramce szuflady: sam loader, bez aplikacji). Osłona błędów to klasa przez prototyp (bez
# składni class), stara Baza (wersja < 2) nie chowa powłoki, tylko zdejmuje zasłonę (jej przejście trwa 0,15 s).
# Komentarze są tu, nie w loaderze: każdy bajt loadera idzie z każdą stroną dashboardu.
LOADER = """/* Jarvo: loader zakładki /jarvo. Plik generowany przez scripts/hqbuild.py. */
(function () {
  var SDK = window.__HERMES_PLUGIN_SDK__, R = SDK.React, h = R.createElement, d = document.documentElement;
  var B = (window.__HERMES_BASE_PATH__ || "").replace(/\\/+$/, "");
  var Z = B + (window.__HERMES_AUTH_REQUIRED__ === false ? "/dashboard-plugins/jarvo-hq/dist/zasoby/" : "/api/plugins/jarvo-hq/zasoby/");
  var JS = Z + "@@JS@@", CSS = Z + "@@CSS@@", obietnica = null;
  var pl = true;
  try { pl = /^pl/i.test(localStorage.getItem("hermes-locale") || "pl"); } catch (e) {}
  function T(a, b) { return pl ? a : b; }
  function laduj() {
    if (obietnica) return obietnica;
    var l = document.createElement("link"), s = document.createElement("script");
    obietnica = Promise.all([new Promise(function (ok) {
      l.rel = "stylesheet"; l.href = CSS;
      l.onload = l.onerror = function () { ok(); };
      setTimeout(ok, 3000);
      document.head.appendChild(l);
    }), new Promise(function (ok, nie) {
      s.src = JS; s.async = true;
      s.onload = function () { window.__JARVO_APP__ ? ok() : nie(new Error("brak __JARVO_APP__")); };
      s.onerror = function () { nie(new Error("nie wczytano " + JS)); };
      document.body.appendChild(s);
    })]).catch(function (e) { obietnica = null; l.remove(); s.remove(); throw e; });
    return obietnica;
  }
  function gotowe() {
    d.setAttribute("data-jarvo-gotowe", "");
    setTimeout(function () { if (d.hasAttribute("data-jarvo-gotowe")) d.removeAttribute("data-jarvo-wstepnie"); }, 200);
  }
  function sprzatnij() { ["data-jarvo-app", "data-jarvo-wstepnie", "data-jarvo-gotowe"].forEach(function (a) { d.removeAttribute(a); }); }
  function Blad() {
    R.useEffect(gotowe, []);
    return h("div", {className: "jarvo-blad-ladowania", role: "alert", style: {padding: "2rem 1.5rem", maxWidth: "40rem", lineHeight: 1.5}},
      h("p", {style: {fontSize: "1.1rem", margin: "0 0 .75rem"}}, T("Coś poszło nie tak przy otwieraniu Jarva.", "Something went wrong while opening Jarvo.")),
      h("p", {style: {margin: 0}},
        h("a", {href: location.href, onClick: function (e) { e.preventDefault(); location.reload(); }}, T("Odśwież", "Reload")), " · ",
        h("a", {href: B + "/sessions"}, T("Otwórz klasyczny panel", "Open the classic dashboard"))));
  }
  function Oslona(p) { R.Component.call(this, p); this.state = {blad: false}; }
  Oslona.prototype = Object.create(R.Component.prototype);
  Oslona.prototype.constructor = Oslona;
  Oslona.getDerivedStateFromError = function () { return {blad: true}; };
  Oslona.prototype.componentDidCatch = function (e) { d.removeAttribute("data-jarvo-app"); console.error("Jarvo:", e); };
  Oslona.prototype.render = function () { return this.state.blad ? h(Blad) : this.props.children; };
  function Jarvo(props) {
    var osadzony = d.hasAttribute("data-jarvo-embed");
    var st = R.useState(window.__JARVO_APP__ ? 1 : 0), stan = st[0], ustaw = st[1];
    R.useEffect(function () {
      var t = setTimeout(function () { ustaw(function (x) { return x || 2; }); }, 7000);
      if (!stan && !osadzony) laduj().then(function () { ustaw(1); }, function (e) { console.error("Jarvo:", e); ustaw(2); });
      return function () { clearTimeout(t); sprzatnij(); };
    }, []);
    R.useEffect(function () {
      if (stan === 1 && !(window.__JARVO_APP__.wersja >= 2)) gotowe();
    }, [stan]);
    if (osadzony) return h("p", {style: {padding: "1.5rem"}}, T("Jarvo jest otwarty w głównym oknie.", "Jarvo is open in the main window."));
    if (stan === 1) return h(Oslona, null, h(window.__JARVO_APP__.App, props));
    if (stan === 2) return h(Blad);
    return h("div", {className: "jarvo-splash", role: "status", "aria-label": "Jarvo"});
  }
  window.__HERMES_PLUGINS__.register("jarvo-hq", Jarvo);
})();
"""
LOADER_MAX = 4096
# kroje aplikacji (motyw TARS: Geist treść, Geist Mono dane, Archivo szeroki nagłówki; OFL, hq/web/fonts/tars/ z
# licencjami, pliki Fontsource bez zmian) i Inter edytora: serwowane z /zasoby/kroje/
KROJE_APLIKACJI = ("geist-latin-wght-normal.woff2", "geist-latin-ext-wght-normal.woff2",
                   "geist-mono-latin-wght-normal.woff2", "geist-mono-latin-ext-wght-normal.woff2",
                   "archivo-latin-wdth-normal.woff2", "archivo-latin-ext-wdth-normal.woff2")
# style leżą pod /api/plugins/jarvo-hq/zasoby/, a pełna biblioteka krojów edytora (kroje.css i ~150 plików) zostaje
# w dist/fonts/ pluginu: względny adres z czterema „..” trafia tam także za proxy z prefiksem ścieżki
DO_DIST = "../../../../dashboard-plugins/jarvo-hq/dist/"


def zasob(katalog: Path, prefiks: str, dane: bytes, rozszerzenie: str) -> str:
    """Zapis zasobu pod nazwą z hashem treści i bliźniaka .gz (poziom 9, mtime 0: build jest powtarzalny)."""
    nazwa = f"{prefiks}-{hashlib.sha256(dane).hexdigest()[:12]}.{rozszerzenie}"
    (katalog / nazwa).write_bytes(dane)
    (katalog / (nazwa + ".gz")).write_bytes(gzip.compress(dane, compresslevel=9, mtime=0))
    return nazwa


def style_aplikacji(css: str) -> str:
    """hq/web/style.css z adresami poprawionymi pod /zasoby/: Inter edytora z kroje/, biblioteka krojów z dist/fonts/."""
    css = re.sub(r"url\((['\"]?)fonts/(Inter-latin(?:-ext)?\.woff2)\1\)", r"url(\1kroje/\2\1)", css)
    return re.sub(r"url\((['\"]?)fonts/", lambda m: f"url({m.group(1)}{DO_DIST}fonts/", css)


def loader_js(js: str, css: str) -> str:
    out = LOADER.replace("@@JS@@", js).replace("@@CSS@@", css)
    if len(out.encode("utf-8")) > LOADER_MAX:
        raise SystemExit(f"loader dist/index.js ma {len(out.encode())} B, limit {LOADER_MAX} B (każda strona dashboardu go pobiera)")
    return out


def zapisz_pakiety(zasoby: Path) -> tuple[str, str]:
    """Pakiety JS/CSS w zasobach (nazwy ze skrótu treści) i mapa pakietów na żądanie wstawiona do rdzenia; budżet
    gzip (BUDZET_GZIP) zatrzymuje build. Zwraca (JS rdzenia, CSS rdzenia) dla loadera."""
    js = pakiety_js()
    css = pakiety_css(style_aplikacji((HQ / "web" / "style.css").read_text(encoding="utf-8")))
    prefiks = lambda p: "mozg" if p == "mozg" else f"app-{p}"
    mapa: dict[str, dict] = {}
    for p in [x for x in js if x != "rdzen"] + [x for x in css if x not in js and x != "rdzen"]:
        wpis = mapa.setdefault(p, {"zalezy": list(PAKIETY.get(p, {}).get("zalezy", ()))})
        if p in js:
            wpis["js"] = zasob(zasoby, prefiks(p), js[p].encode("utf-8"), "js")
        if p in css:
            wpis["css"] = zasob(zasoby, prefiks(p), css[p].encode("utf-8"), "css")
    if ZNACZNIK_PAKIETOW not in js["rdzen"]:
        raise SystemExit(f"hq/web/src/00-base.js: brak znacznika {ZNACZNIK_PAKIETOW} (mapa pakietów na żądanie)")
    rdzen = js["rdzen"].replace(ZNACZNIK_PAKIETOW, json.dumps(mapa, ensure_ascii=False, separators=(",", ":")), 1)
    pliki = {"app-rdzen.js": rdzen.encode("utf-8"), "app-rdzen.css": css["rdzen"].encode("utf-8")}
    if "mozg" in js:
        pliki["mozg.js"] = js["mozg"].encode("utf-8")
    for nazwa, dane in pliki.items():
        if gzip_rozmiar(dane) > BUDZET_GZIP[nazwa]:
            raise SystemExit(f"{nazwa}: {gzip_rozmiar(dane)} B gzip, budżet {BUDZET_GZIP[nazwa]} B (docs/HQ.md §2f)")
    return (zasob(zasoby, "app-rdzen", pliki["app-rdzen.js"], "js"), zasob(zasoby, "app-rdzen", pliki["app-rdzen.css"], "css"))


# strona logowania panelu w sieci (hq/plugin/siec.py, docs/HQ.md „Panel w sieci”): wygląd jarvo.pl z site/ (logo,
# DM Sans i JetBrains Mono z tymi samymi @font-face co site/style.css), wszystko w jednym pliku HTML: bramka podaje
# go bez sesji, a poza /login, /auth/… i plikami Hermesa nic innego nie jest dostępne bez logowania
LOGOWANIE_SIECI = "logowanie.html"


def strona_logowania_sieci() -> bytes:
    """branding/panel-siec/logowanie.html z logo (site/assets/logo.svg) i krojami jarvo.pl jako data: URL."""
    site = fl.REPO_ROOT / "site"
    fonty = []
    for blok in re.findall(r"@font-face\s*\{[^}]*\}", (site / "style.css").read_text(encoding="utf-8")):
        plik = re.search(r"url\((['\"]?)(assets/fonts/[\w.-]+\.woff2)\1\)", blok)
        if not plik:
            raise SystemExit(f"site/style.css: @font-face bez pliku woff2 z assets/fonts/: {blok[:80]}")
        dane = base64.b64encode((site / plik.group(2)).read_bytes()).decode("ascii")
        fonty.append(" ".join(blok.replace(plik.group(0), f"url(data:font/woff2;base64,{dane})").split()))
    if len(fonty) < 2:
        raise SystemExit("site/style.css: brak @font-face krojów jarvo.pl (DM Sans, JetBrains Mono)")
    logo = (site / "assets" / "logo.svg").read_text(encoding="utf-8").strip()
    szablon = (fl.REPO_ROOT / "branding" / "panel-siec" / "logowanie.html").read_text(encoding="utf-8")
    if szablon.count("@@FONTY@@") != 1 or szablon.count("@@LOGO@@") != 1:
        raise SystemExit("branding/panel-siec/logowanie.html: potrzebne dokładnie jedno @@FONTY@@ i jedno @@LOGO@@")
    return szablon.replace("@@FONTY@@", "\n".join(fonty)).replace("@@LOGO@@", logo).encode("utf-8")


def build_plugin(out: Path, fleet: fl.Fleet | None = None) -> Path:
    dash = out / "dashboard"
    if out.exists():
        shutil.rmtree(out)
    zasoby = dash / "dist" / "zasoby"
    (zasoby / "kroje").mkdir(parents=True)
    for name in PLUGIN_FILES:
        shutil.copy2(HQ / "plugin" / name, dash / name)
    js, css = zapisz_pakiety(zasoby)
    (dash / "dist" / "index.js").write_text(loader_js(js, css), encoding="utf-8", newline="\n")
    for k in KROJE_APLIKACJI:
        shutil.copy2(HQ / "web" / "fonts" / "tars" / k, zasoby / "kroje" / k)
    for k in ("Inter-latin.woff2", "Inter-latin-ext.woff2"):
        shutil.copy2(HQ / "web" / "fonts" / k, zasoby / "kroje" / k)
    shutil.copy2(HQ / "web" / "vendor" / "LICENSE-htm", dash / "dist" / "LICENSE-htm")
    # czcionki motywu Fosfor (VT323, IBM Plex Mono; OFL): serwowane lokalnie, bez Google Fonts;
    # te same pliki trafiają na stronę logowania (branding/patch_dashboard.py)
    shutil.copytree(fl.REPO_ROOT / "branding" / "fonts", dash / "dist" / "fonts")
    # krój edytora filmów (Inter, OFL): zapas, gdy system nie ma SF Pro / Segoe UI / Roboto
    shutil.copytree(HQ / "web" / "fonts", dash / "dist" / "fonts", dirs_exist_ok=True)
    # biblioteka dźwięków CC0 edytora (scripts/dzwieki.py): menu Audio, odsłuch i kopia obok filmu przy dodaniu
    shutil.copytree(HQ / "web" / "dzwieki", dash / "dzwieki")
    # wspólne klucze floty: plugin pilnuje ich na bieżąco (skrypt jest też uruchamiany przy wdrożeniu)
    shutil.copy2(fl.REPO_ROOT / "scripts" / "share_keys.py", dash / "share_keys.py")
    # pomiar animacji Wideografa: HQ pokazuje raport i sprawdza jego aktualność tym samym kodem
    shutil.copy2(fl.REPO_ROOT / "profiles" / "jarvo-wideo" / "scripts" / "pomiar.py", dash / "pomiar.py")
    # liczby floty: HQ liczy jakość agentów tą samą funkcją co przegląd tygodnia Jarva
    shutil.copy2(fl.REPO_ROOT / "profiles" / "jarvo" / "scripts" / "liczby.py", dash / "liczby.py")
    # liczby.py importuje _sciezki (katalogi danych w kontenerze i natywnie, E7): bez niego HQ nie policzy liczb
    shutil.copy2(fl.REPO_ROOT / "profiles" / "jarvo" / "scripts" / "_sciezki.py", dash / "_sciezki.py")
    # konwerter plików w Centrali: ten sam skrypt co wspólny skill floty `konwersja-plikow`
    shutil.copy2(fl.REPO_ROOT / "shared" / "skills" / "konwersja-plikow" / "scripts" / "konwertuj.py", dash / "konwertuj.py")
    # figura floty w Centrali („Jak działa usługa”): ten sam iso.py co wspólny skill `izometria`, z szablonem,
    # licencją iso-glow (MIT) i krojem OFL; plugin buduje stronę z fleet.json
    shutil.copytree(fl.REPO_ROOT / "shared" / "skills" / "izometria", dash / "izometria",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "przyklady", "examples"))
    fl.kopiuj_kroje_izometrii(dash / "izometria" / "scripts")
    fl.write_json(dash / "fleet.json", fleet_json(fleet))
    (dash / LOGOWANIE_SIECI).write_bytes(strona_logowania_sieci())
    for ikona in ("ikona-180.png", "ikona-512.png"):        # aplikacja na ekranie telefonu (siec.py IKONY)
        shutil.copy2(fl.REPO_ROOT / "branding" / "panel-siec" / ikona, dash / ikona)
    return dash


def build_demo(out: Path) -> Path:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "app.js").write_text(bundle_js(), encoding="utf-8", newline="\n")
    shutil.copy2(HQ / "web" / "style.css", out / "style.css")
    shutil.copytree(HQ / "web" / "fonts", out / "fonts")
    shutil.copy2(HQ / "web" / "demo" / "mock.js", out / "mock.js")
    shutil.copy2(HQ / "web" / "demo" / "index.html", out / "index.html")
    (out / "fleet.js").write_text("window.JARVO_HQ_FLEET = " + json.dumps(fleet_json(), ensure_ascii=False, indent=1) + ";\n",
                                  encoding="utf-8", newline="\n")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="katalog pluginu (np. build/plugins/jarvo-hq)")
    ap.add_argument("--demo", help="katalog demo (np. build/hq-demo)")
    args = ap.parse_args(argv)
    if not args.out and not args.demo:
        ap.error("podaj --out albo --demo")
    if args.out:
        print(f"✓ plugin Jarvo HQ: {build_plugin(Path(args.out))}")
    if args.demo:
        print(f"✓ demo Jarvo HQ: {build_demo(Path(args.demo)) / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
