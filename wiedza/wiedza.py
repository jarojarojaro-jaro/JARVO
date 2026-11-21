#!/usr/bin/env python3
"""Skarbiec wiedzy floty Jarvo (drugi mózg): narzędzie bez zależności poza biblioteką standardową.

Skarbiec to katalog zwykłych plików Markdown (projekt: docs/WIEDZA.md). Ten skrypt:
  zasiej      katalogi i huby (FOLDERY_SKARBCA), SCHEMA.md, huby agentów (z fleet.json; agent spoza floty do archiwum/),
              INDEX, LOG, orzeczenia, docs repo i pliki profili → zrodla/jarvo-repo, tożsamość Jarva i mapa → jarvo/
              (build/wiedza/tozsamosc), lustra pamięci profili, księga błędów z wiedza/bledy (tylko nowe notatki), git
              init, indeks i wektory
  archiwizuj  notatki albo katalogi do archiwum/ (linki do następcy albo do archiwum); przenies: inny folder, linki
              przepisane; streszczenie: blok „najważniejsze” huba; pamiec: lustro pamięci Hermesa po treści plików
  indeksuj    indeks FTS5 (state/wiedza.db), INDEX.md i listy w hubach z plików (0 tokenów, deterministycznie), wektory
              nowych i zmienionych notatek (gdy działa usługa wiedza/wektory.py)
  szukaj      wyszukiwanie po polsku (ogonki bez znaczenia, aliasy notatek): wektory (albo hybryda z BM25, --silnik),
              a bez usługi wektorów same słowa (BM25); wynik: ścieżka · streszczenie
  czytaj      cała notatka
  zapisz      szkic do skrzynka/ (agent nie pisze notatek sam: zasada 9 schematu); typ blad z --sygnatura
  orzeczenie  jedna datowana linia w orzeczenia/<kogo>.md (tylko od człowieka)
  lint        raport LINT.md (martwe linki, sieroty, brak źródła, sekrety, duplikaty, przeterminowane…)
  graf        węzły i linki jako JSON (zakładka „Wiedza”)
  cofnij      cofa ostatni punkt zapisu git
  status      liczby (także wektory i stan usługi)
  ocena       trafność przypomnień na zestawie pytań (hit@5, MRR, ms) dla silnika hybryda | wektory | slowa

Używane przez wtyczkę jarvo-wiedza (import), rutyny (CLI), `jarvo wiedza` (jarvo/wiedza_cli.py), testy
(tests/test_wiedza.py). Domyślne ścieżki: JARVO_KNOWLEDGE_DIR, a bez niej <dane>/jarvo/knowledge, gdzie <dane> to
HERMES_HOME (profil: dwa katalogi wyżej), bez HERMES_HOME domyślny korzeń Jarva (docs/NATYWNIE.md c1; w kontenerze
/opt/data), i JARVO_STATE_DIR (albo <skarbiec>/../state).
Przenośność (docs/NATYWNIE.md K01, K07): notatki zawsze z LF, git w UTF-8 bez zamiany końców linii, zamiana pliku
ponawiana, gdy na Windows trzyma go inny program, na Windows nazwy bez „:”, „\\” i nazw urządzeń (CON, NUL…), na macOS
ścieżki w NFC. Lint zgłasza nazwy, które nie przejdą na inny system (nazwy urządzeń Windows, kropka albo spacja na
końcu, zapis spoza NFC, ta sama nazwa inną wielkością liter, ścieżka dłuższa niż 240 znaków) i zapisuje podsumowanie
w state/wiedza-lint.json (czyta je `jarvo doctor`, który sam niczego nie zapisuje).
Jeden piszący (§6): `Blokada` = blokada systemu (msvcrt na Windows, fcntl na POSIX) na state/wiedza.zamek i znacznik
state/wiedza.lock z PID-em i czasem (ten sam format czyta i stawia scripts/install_fleet.py przy zasiewie).
Wektory (docs/WIEDZA.md §7, W4): model e5-small działa w osobnej usłudze (wiedza/wektory.py, venv narzędzi), a ten
plik zostaje przy bibliotece standardowej: KlientWektorow pyta ją po HTTP na 127.0.0.1 z tokenem ze state/wektory.json,
wektory notatek leżą w tabeli `wektory` w state/wiedza.db, iloczyn skalarny liczy czysty Python.
"""
from __future__ import annotations

import argparse
import array
import base64
import contextlib
import datetime as dt
import hashlib
import http.client
import json
import math
import operator
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

WINDOWS = os.name == "nt"
MACOS = sys.platform == "darwin"


def _domyslny_skarbiec() -> str:
    """JARVO_KNOWLEDGE_DIR; bez niej <dane>/jarvo/knowledge, gdzie <dane> to HERMES_HOME (profil: dwa katalogi wyżej),
    a bez HERMES_HOME domyślny korzeń Jarva: %LOCALAPPDATA%\\Jarvo\\dane, ~/.jarvo/dane, w kontenerze /opt/data,
    na Linuksie natywnie ${XDG_DATA_HOME:-~/.local/share}/jarvo/dane (jarvo/sciezki.py)."""
    if os.environ.get("JARVO_KNOWLEDGE_DIR"):
        return os.environ["JARVO_KNOWLEDGE_DIR"]
    if os.environ.get("HERMES_HOME"):
        dane = Path(os.environ["HERMES_HOME"])
        dane = dane.parent.parent if dane.parent.name == "profiles" else dane
    elif os.environ.get("JARVO_ROOT"):
        dane = Path(os.environ["JARVO_ROOT"]).expanduser() / "dane"
    elif WINDOWS:
        dane = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Jarvo" / "dane"
    elif MACOS:
        dane = Path.home() / ".jarvo" / "dane"
    elif Path("/opt/data").is_dir():
        return "/opt/data/jarvo/knowledge"
    else:
        dane = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "jarvo" / "dane"
    return str(dane / "jarvo" / "knowledge")


DOMYSLNY_SKARBIEC = _domyslny_skarbiec()

# Jedna definicja folderów skarbca (docs/WIEDZA.md §2): z niej huby i opisy (zasiew), foldery nowych notatek kompilatora,
# zakres wyszukiwania, przypomnień i wektorów, sekcje INDEX-u, drzewo zakładki Wiedza i lint; Mózg (hq/web/src/63-mozg.js,
# `MOZG_KATEGORIE`) ma test zgodności z tą listą. Kolejność = kolejność w hubie skarbca, INDEX-ie i drzewie.
# `tytul`: tytuł huba (i sekcji INDEX-u), `hub`: nazwa pliku huba albo "" (folder bez huba), `pisze`: kto kładzie tu notatki
# (zasiew: generowane z repo, floty i pamięci; kompilator: ze szkiców; czlowiek: orzeczenia; skrypt: brand kit, briefy,
# inspiracje; surowe: źródła i szkice; archiwizacja: `wiedza.py archiwizuj` i zasiew), `kompilator`: folder nowych notatek
# kompilatora (poza tym `agenci/<agent>/` i `brands/<marka>/`), `recall`: notatki wracają w wyszukiwaniu i przypomnieniach.
FOLDERY_SKARBCA: dict[str, dict] = {
    "": {"tytul": "Skarbiec wiedzy", "hub": "_hub-skarbiec", "pisze": "zasiew", "kompilator": False, "recall": True,
         "opis": "Strona główna skarbca: huby folderów, liczby, ostatnie zmiany."},
    "jarvo": {"tytul": "Jarvo", "hub": "_hub-jarvo", "pisze": "zasiew", "kompilator": False, "recall": True,
              "opis": ("Tożsamość Jarva: kim jest (SOUL), zasady pracy, zasady krytyczne i jego pamięć. Notatki generowane "
                       "z repo i z pamięci Hermesa (zasiew i każda zmiana pamięci); poprawki właściciela w `orzeczenia/`.")},
    "orzeczenia": {"tytul": "Orzeczenia", "hub": "_hub-orzeczenia", "pisze": "czlowiek", "kompilator": False, "recall": True,
                   "opis": "Korekty od człowieka, jedna datowana linia każda. Agent dostaje swoje orzeczenia przed każdą turą."},
    "user": {"tytul": "Ty", "hub": "_hub-ty", "pisze": "kompilator", "kompilator": True, "recall": True,
             "opis": ("Kim jesteś, czym się zajmujesz, Twoja firma, decyzje i preferencje (`user/USER.md` z wywiadu Jarva, "
                      "`user/pamięć jarva o tobie` z pamięci Hermesa, fakty z rozmów).")},
    "projekty": {"tytul": "Projekty", "hub": "_hub-projekty", "pisze": "kompilator", "kompilator": True, "recall": True,
                 "opis": "Jedna notatka na misję albo projekt: stan, decyzje, wyniki (linki do plików), marka, agenci."},
    "brands": {"tytul": "Marki", "hub": "_hub-marki", "pisze": "skrypt", "kompilator": False, "recall": True,
               "opis": "Brand kity (`brands/<marka>/`): kolory, fonty, ton. Orzeczenia marki: `orzeczenia/marki/<marka>.md`."},
    "inspiracje": {"tytul": "Inspiracje", "hub": "_hub-inspiracje", "pisze": "skrypt", "kompilator": False, "recall": True,
                   "opis": ("Strony referencyjne branż słabo pokrytych w katalogu Inspo (`inspiracje/strony/<branża>/<domena>`): "
                            "układ, paleta, fonty, zrzuty; pisze Web skillem `inspiracje-stron`. Inspiracja, nie wzór do kopiowania.")},
    "agenci": {"tytul": "Agenci", "hub": "_hub-agenci", "pisze": "kompilator", "kompilator": False, "recall": True,
               "opis": ("Jeden katalog na aktywnego agenta: hub (rola, skille, skrypty z `fleet.yaml`) i notatki o jego pracy "
                        "(narzędzia, skille, ograniczenia). Agenci wycofani z floty leżą w `archiwum/agenci/`.")},
    "fleet": {"tytul": "Flota", "hub": "", "pisze": "zasiew", "kompilator": False, "recall": True,
              "opis": "Arsenał floty, księga lekcji i węzły skilli (`fleet/skille/`, generowane z repo)."},
    "podmioty": {"tytul": "Podmioty", "hub": "_hub-podmioty", "pisze": "kompilator", "kompilator": True, "recall": True,
                 "opis": "Firmy, ludzie w rolach publicznych, narzędzia, usługi, konta: jedna notatka na podmiot, aktualizowana."},
    "pojecia": {"tytul": "Pojęcia", "hub": "_hub-pojecia", "pisze": "kompilator", "kompilator": True, "recall": True,
                "opis": "Metody, wzorce, definicje, lekcje ogólne: jedna notatka na pojęcie."},
    "bledy": {"tytul": "Księga błędów", "hub": "_hub-bledy", "pisze": "kompilator", "kompilator": True, "recall": True,
              "opis": ("Księga błędów: jedna notatka na rodzaj błędu narzędzia albo pracy, z sygnaturami (dosłowne fragmenty "
                       "komunikatu), objawem, przyczyną, krokiem „jak poprawnie” i licznikiem wystąpień. Gdy wynik narzędzia ma "
                       "sygnaturę, wtyczka dopisuje pod nim „To już było” z tym krokiem.")},
    "rozmowy": {"tytul": "Rozmowy", "hub": "_hub-rozmowy", "pisze": "kompilator", "kompilator": True, "recall": True,
                "opis": "Skompilowane ustalenia z rozmów i kart: decyzje, fakty, pliki. Surowe wyciągi leżą w `zrodla/rozmowy/`."},
    "briefy": {"tytul": "Briefy", "hub": "_hub-briefy", "pisze": "skrypt", "kompilator": False, "recall": True,
               "opis": ("Poranne briefy (`B-RRRR-MM-DD`) i przeglądy tygodnia (`T-RRRR-Wtt`) z treścią i tabelą decyzji: "
                        "odpowiedź właściciela, kiedy, co z nią zrobiono. Pisze skrypt `briefy.py`, odpowiedzi dopisuje Jarvo.")},
    "zrodla": {"tytul": "Źródła", "hub": "", "pisze": "surowe", "kompilator": False, "recall": False,
               "opis": "Surowe wyciągi rozmów, raporty kart, pliki i kopia repo (`zrodla/jarvo-repo/`): materiał, nie wiedza."},
    "skrzynka": {"tytul": "Skrzynka", "hub": "", "pisze": "surowe", "kompilator": False, "recall": False,
                 "opis": "Szkice czekające na kompilację (`skrzynka/zrobione/`: już skompilowane)."},
    "archiwum": {"tytul": "Archiwum", "hub": "_hub-archiwum", "pisze": "archiwizacja", "kompilator": False, "recall": False,
                 "opis": ("Notatki wycofane i zastąpione, w układzie dawnej ścieżki (`archiwum/agenci/<agent>/…`). Poza "
                          "przypomnieniami i kompilacją; link do notatki zastąpionej prowadzi do następcy (`zastapiona_przez`).")},
}
TOZSAMOSC = "jarvo"                  # folder tożsamości Jarva (notatki generowane, kompilator ich nie pisze)
ARCHIWUM = "archiwum"
PROFIL_TOZSAMOSCI = "jarvo"          # profil, którego tożsamość i pamięć ma skarbiec (orkiestrator floty)
LUSTRO_REPO = "zrodla/jarvo-repo"                     # kopia repo przy wdrożeniu: poza wyszukiwaniem, ale w grafie
FOLDERY = (*(f for f in FOLDERY_SKARBCA if f), "zrodla/rozmowy", "zrodla/karty", "zrodla/pliki", LUSTRO_REPO, "skrzynka/zrobione",
           "inspiracje/strony", "orzeczenia/marki")
# folder → (nazwa pliku huba, tytuł): foldery z hubem
HUBY = {f: (d["hub"], d["tytul"]) for f, d in FOLDERY_SKARBCA.items() if d["hub"]}
OPISY_FOLDEROW = {f: d["opis"] for f, d in FOLDERY_SKARBCA.items() if f}
FOLDERY_NOTATEK = tuple(f for f, d in FOLDERY_SKARBCA.items() if d["kompilator"])   # + agenci/<agent>, brands/<marka>
SUROWE = ("zrodla/", "skrzynka/")                      # materiał, nie wiedza: poza grafem (bez lustra repo) i INDEX-em
POZA_WYSZUKIWANIEM = tuple(f"{f}/" for f, d in FOLDERY_SKARBCA.items() if f and not d["recall"])   # + archiwum/
LUSTRO_KATALOGI = ("profiles", "shared", "vendor")     # podkatalogi z `--repo` (płaskie *.md obok to docs/)
PLIKI_SPECJALNE = {"INDEX.md", "LOG.md", "LINT.md", "SCHEMA.md"}
# własne formaty (brand kit, karta strony referencyjnej z DESIGN.md dembrandta, USER.md, źródła, szkice, archiwum briefów)
BEZ_FRONTMATTERU = ("brands/", "inspiracje/", "user/", "zrodla/", "skrzynka/", "briefy/")
TYPY = {"hub", "agent", "projekt", "podmiot", "pojecie", "fakt", "decyzja", "lekcja", "zrodlo", "rozmowa", "orzeczenia", "skill",
        "blad", "tozsamosc"}
STATUSY = {"aktualna", "do-sprawdzenia", "sprzeczna", "przestarzala", "generowane", "wycofana"}
WYMAGANE = ("typ", "utworzono", "zmieniono", "status")
BEZ_ZRODLA = {"hub", "agent", "orzeczenia", "skill"}         # generowane z repo i floty (linki robi zasiew)
SKILLE = "fleet/skille"                                       # skill floty = węzeł grafu (zasiew z fleet.json)
# notatki o samej flocie (nie o klientach): ich odwołania do skryptów lint porównuje z repo (state/wiedza-kod.json)
O_FLOCIE = ("agenci/", "pojecia/", "fleet/", "orzeczenia/")
SKRYPT_RE = re.compile(r"`(?:[^`\s]*/)?([\w-]+\.(?:py|sh|js|cjs|mjs))\b[^`]*`")
MAX_SLOW = {"hub": 400, "agent": 600, "projekt": 400}
DOMYSLNY_MAX_SLOW = 250
# tożsamość Jarva w skarbcu (docs/WIEDZA.md §2a): notatki `jarvo/*` z plików tożsamości buildu (build/wiedza/tozsamosc:
# SOUL, ZASADY, KRYTYCZNE i MAPA z podstawionymi tokenami) i z pamięci Hermesa (memories/MEMORY.md, USER.md profilu)
# (ścieżka notatki, plik w tozsamosc/, plik źródła w repo dla `plik:`, tytuł, streszczenie)
NOTATKI_TOZSAMOSCI = (
    (f"{TOZSAMOSC}/kim jest jarvo", "SOUL.md", "profiles/jarvo/SOUL.md", "Kim jest Jarvo",
     "Postać Jarva z `profiles/jarvo/SOUL.md`: kim jest, charakter i głos. Jarvo ma ten tekst w prompcie każdej rozmowy"),
    (f"{TOZSAMOSC}/zasady pracy", "ZASADY.md", "profiles/jarvo/ZASADY.md", "Zasady pracy",
     "Jak Jarvo pracuje (`profiles/jarvo/ZASADY.md`): zasady, mapa skilli, formaty raportów. W prompcie każdej rozmowy, po postaci"),
    (f"{TOZSAMOSC}/zasady krytyczne", "KRYTYCZNE.md", "profiles/jarvo/ZASADY.md", "Zasady krytyczne",
     "Najważniejsze zasady na samym końcu promptu Jarva (ostatni blok `<critical>` z `profiles/jarvo/ZASADY.md`), "
     "powtórka zasad z początku, żeby model ich nie zgubił"),
)
PLIKI_PAMIECI = {"memory": "MEMORY.md", "user": "USER.md"}       # memories/ profilu (tools/memory_tool.py Hermesa)
NOTATKI_PAMIECI = {"memory": (f"{TOZSAMOSC}/pamięć jarva", "Pamięć Jarva", "Notatki Jarva z narzędzia memory"),
                   "user": ("user/pamięć jarva o tobie", "Pamięć Jarva o Tobie", "Co Jarvo pamięta o Tobie z narzędzia memory")}
MAPA_NOTATKA = f"{TOZSAMOSC}/jak działa jarvo"   # „Jarvo od A do Z”: MAPA.md repo + nakładki + bloki GEN (wiedza/mapa.py)
# kolejność tożsamości w hubie Jarva, INDEX-ie i Mózgu: mapa, postać, zasady, zasady krytyczne, pamięć
KOLEJNOSC_TOZSAMOSCI = [MAPA_NOTATKA, *(t[0] for t in NOTATKI_TOZSAMOSCI), *(n[0] for n in NOTATKI_PAMIECI.values())]
SEPARATOR_PAMIECI = "\n§\n"           # tools/memory_tool_store.py Hermesa: ENTRY_DELIMITER (cały, z końcami linii)
LIMITY_PAMIECI = {"memory": 2200, "user": 1375}   # domyślne Hermesa (memory.memory_char_limit, memory.user_char_limit)
STAN_PAMIECI = "wiedza-pamiec.json"   # state/: wersja (sha256) i wpisy pamięci każdego profilu z ostatniego lustra
ZAMEK_PAMIECI = "wiedza-pamiec.zamek"
MAX_STRESZCZENIA_HUBA = 1500          # znaków bloku STRESZCZENIE huba (`wiedza.py streszczenie`)
STRESZCZENIE_RE = re.compile(r"<!-- Jarvo:STRESZCZENIE -->\n?(.*?)\n?<!-- /Jarvo:STRESZCZENIE -->", re.S)
GEN_RE = re.compile(r"<!-- Jarvo:GEN (\w+) -->.*?<!-- /Jarvo:GEN \1 -->", re.S)
LISTA_RE = re.compile(r"<!-- Jarvo:GEN lista -->.*?<!-- /Jarvo:GEN lista -->", re.S)   # same linki: poza indeksem
# limit długości (lint) liczy tylko treść pisaną: bloki GEN (lista notatek, rejestr floty) robi zasiew, nie autor
LINK_RE = re.compile(r"\[\[([^\]\|#]+)(#[^\]\|]*)?(?:\|([^\]]*))?\]\]")
ZAKAZANE_W_NAZWIE = set('*"\\/<>:|?#^[]')            # Obsidian i Windows nie przyjmą takiej nazwy
DATA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STOPSLOWA = {"i", "a", "w", "z", "na", "do", "to", "że", "ze", "się", "sie", "nie", "jak", "co", "czy", "dla", "od", "po",
             "przez", "jest", "są", "sa", "the", "and", "or", "of", "for", "mi", "mnie", "ten", "ta", "te", "ale", "oraz", "o",
             "kto", "we", "gdzie", "kiedy", "czym", "który", "która", "które", "ktory", "ktora", "ktore", "jaki", "jaka", "jakie",
             "ma", "mam", "masz", "być", "byc", "był", "była", "było", "będzie", "bedzie", "ich", "jego", "jej", "nam", "nas", "moja", "mój", "moje"}
MAX_SLOW_ZAPYTANIA = 12          # słów w zapytaniu FTS5; dłuższe pytanie zostawia najrzadsze (Indeks.slowa_informacyjne)
MAX_SLOW_OCENIANYCH = 60         # tyle pierwszych słów długiego pytania liczymy w indeksie
# wektory (docs/WIEDZA.md §7, decyzja W4): jeden ciepły model e5-small na instalację w usłudze wiedza/wektory.py
WEKTORY_STAN = "wektory.json"     # state/: port, token, model i PID usługi (pisze ją usługa przy starcie, czytają klienci)
WEKTORY_CZAS_S = 0.3              # przypomnienie przed turą: tyle czeka na wektor pytania, potem same słowa (BM25)
WEKTORY_CZAS_NARZEDZIA_S = 2.0    # wiedza_szukaj i kandydaci kompilacji (poza turą rozmowy)
WEKTORY_CZAS_ZAPISU_S = 120.0     # osadzanie notatek (indeksuj, kompilacja, zasiew): jedna paczka
WEKTORY_PACZKA = 8                # notatek na jedno wywołanie usługi (zapytanie z tury nie czeka za długą paczką)
MAX_ZNAKOW_WEKTORA = 1200         # treści notatki w tekście wektora, po tytule i streszczeniu
DLUGIE_ZAPYTANIE = 25             # słów: dłuższe pytanie idzie zdaniami, wynik notatki = najlepsze zdanie
MAX_ZDAN = 8                      # zdań długiego pytania (pierwsze; każde to osobny wektor)
MIN_SLOW_ZDANIA = 3               # krótszy kawałek długiego pytania (nagłówek, „Tak.”) nie dostaje wektora
WEKTOROW_W_RANKINGU = 30
RRF_K = 60                        # miejsce na liście → punkty 1 / (k + pozycja) (Reciprocal Rank Fusion)
SILNIKI = ("wektory", "hybryda", "slowa")
# wybór pomiarem `wiedza.py ocena` na zestawie syntetycznym tests/data/wiedza-ocena.json (2026-11-08, 33 pytania):
# wektory hit@5 32/33, MRR 0,83; hybryda RRF 28/33, 0,77; słowa 25/33, 0,66 (docs/WIEDZA.md §7)
SILNIK = "wektory"
MAX_ALIASOW = 8                   # aliasów jednej notatki (frontmatter `aliasy:`)
MAX_DOPISKOW_ALIASOW = 5          # tytułów dopisanych do jednego zapytania
WERSJA_INDEKSU = "3"              # 2: aliasy i wektory, 3: sekcje i streszczenia hubów; inna wersja = jedno pełne odświeżenie
HUB_AGENTA_RE = re.compile(r"^agenci/[^/]+/_hub-[^/]+$")
SEKRETY = [
    ("klucz Stripe", re.compile(r"\bsk_(live|test)_[A-Za-z0-9]{8,}")),
    ("klucz OpenAI/Anthropic", re.compile(r"\bsk-(ant-)?[A-Za-z0-9_-]{20,}")),
    ("klucz AWS", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("token GitHub", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("token Slack", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("klucz Google", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}")),
    ("klucz prywatny", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("hasło w tekście", re.compile(r"(?i)\b(has[łl]o|password|passwd)\s*[:=]\s*\S{4,}")),
    ("klucz API w tekście", re.compile(r"(?i)\b(api[_ -]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_\-]{16,}")),
]
GIT_TOZSAMOSC = ["-c", "user.name=Jarvo", "-c", "user.email=jarvo@localhost", "-c", "commit.gpgsign=false"]
# pliki w historii bajt w bajt jak na dysku (bez CRLF z core.autocrlf=true Git for Windows), długie ścieżki na Windows;
# automatyczne porządki gita po commicie od razu, nie w tle: nowy git (macOS) pakował obiekty w odłączonym procesie,
# który zostawał po poleceniu (zmieniał skarbiec po `jarvo doctor`, na Windows trzymałby pliki przy deinstalacji)
GIT_PRZENOSNIE = ["-c", "core.autocrlf=false", "-c", "core.longpaths=true", "-c", "gc.autoDetach=false",
                  "-c", "maintenance.autoDetach=false"]
# .gitignore skarbca: *.tmp (zapis atomowy) i śmieci menedżera plików tego systemu (Finder, Eksplorator)
GITIGNORE_SYSTEMU = (".DS_Store",) if MACOS else ("Thumbs.db", "desktop.ini") if WINDOWS else ()
BEZ_OKNA = getattr(subprocess, "CREATE_NO_WINDOW", 0)            # Windows: git bez migającego okna konsoli
ZAJETY_PLIK = (5, 32, 33)          # WinError: odmowa dostępu, plik otwarty przez inny proces, zablokowany fragment
PROBY_ZAMIANY = 10
# nazwy urządzeń Windows: „con.md” otwiera konsolę, „nul.md” połyka zapis (także z rozszerzeniem i spacją przed kropką)
ZAREZERWOWANE = frozenset({"con", "prn", "aux", "nul", "conin$", "conout$", *(f"com{i}" for i in range(1, 10)),
                           *(f"lpt{i}" for i in range(1, 10))})
MAX_SCIEZKI = 240                  # pełna ścieżka pliku: Windows bez LongPathsEnabled nie otworzy dłuższej niż 260 (K07)
# jeden piszący skarbca (docs/WIEDZA.md §6): znacznik z PID-em i czasem (czyta go też scripts/install_fleet.py, zasiew
# przy wdrożeniu) i osobny plik blokady systemu: na Windows bajt zablokowany przez msvcrt nie da się nawet przeczytać,
# więc znacznika samego nie blokujemy
ZNACZNIK_BLOKADY = "wiedza.lock"
PLIK_ZAMKA = "wiedza.zamek"
BLOKADA_STARA_S = 2 * 3600         # starszy znacznik to resztka po awarii (jak w install_fleet.py)
LINT_JSON = "wiedza-lint.json"     # state/: podsumowanie ostatniego lintu dla `jarvo doctor` i statusu
# agent biznesowy (pole `marka` we fleet.yaml, docs/WIEDZA.md „Agenci biznesowi”): w skarbcu widzi tylko swoją markę,
# siebie, wiedzę o flocie, inspiracje i księgę błędów; reszta (projekty, rozmowy, user, inne marki, inni agenci) nie dla niego
WSPOLNE_DLA_MAREK = ("fleet/", "inspiracje/", "bledy/")
MARKA_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
# księga błędów (docs/WIEDZA.md §4b): notatka `bledy/<tytuł>` typu `blad` z sygnaturami; wtyczka dopisuje jej krok „jak
# poprawnie” pod wynikiem narzędzia z sygnaturą (hak transform_tool_result), licznik przypomnień w state/
KSIEGA = "bledy"
LICZNIK_BLEDOW = "bledy-licznik.json"     # state/: notatka → {"przypomnien", "ostatnio"} (pisze wtyczka pod blokadą)
ZASIANE_BLEDY = "bledy-zasiane.json"      # state/: notatki z zasiewu repo (`wiedza/bledy/`): usunięta nie wraca
MAX_SYGNATUR = 12
MAX_ZNAKOW_SYGNATURY = 200
JAK_POPRAWNIE_RE = re.compile(r"^\W*jak poprawnie\W*?:\**[ \t]*(.+?)\s*(?=\n\s*\n|\n\W*(?:objaw|przyczyna)\W*?:|\n#|\Z)",
                              re.I | re.M | re.S)


def dzis() -> str:
    return os.environ.get("WIEDZA_DZIS") or dt.date.today().isoformat()


def zamien_plik(zrodlo: str | Path, cel: str | Path) -> None:
    """os.replace, ponawiane przez ok. 2 s, gdy na Windows plik trzyma inny program (Obsidian, antywirus, indeksowanie:
    WinError 5, 32, 33). Na POSIX takiego błędu nie ma, więc to zwykłe os.replace."""
    for proba in range(PROBY_ZAMIANY):
        try:
            os.replace(zrodlo, cel)
            return
        except PermissionError as e:
            if getattr(e, "winerror", None) not in ZAJETY_PLIK or proba == PROBY_ZAMIANY - 1:
                raise
            time.sleep(0.05 * (proba + 1))


def pid_zyje(pid: int) -> bool:
    """Czy proces o tym PID-zie działa (znacznik blokady bez żywego właściciela to resztka po awarii), jak w
    scripts/install_fleet.py: POSIX kill(pid, 0), Windows OpenProcess + GetExitCodeProcess (STILL_ACTIVE)."""
    if pid <= 0:
        return False
    if not WINDOWS:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    uchwyt = k32.OpenProcess(0x1000, False, pid)              # PROCESS_QUERY_LIMITED_INFORMATION
    if not uchwyt:
        return ctypes.get_last_error() == 5                   # odmowa dostępu: proces jest, tylko cudzy
    try:
        kod = wintypes.DWORD()
        return bool(k32.GetExitCodeProcess(uchwyt, ctypes.byref(kod))) and kod.value == 259    # STILL_ACTIVE
    finally:
        k32.CloseHandle(uchwyt)


def znacznik_blokady(stan: str | Path) -> dict | None:
    """Znacznik state/wiedza.lock: {"pid", "wiek_s", "zywy", "aktualny"} albo None (brak). `aktualny` = blokuje: proces
    żyje, a znacznik jest młodszy niż BLOKADA_STARA_S; inaczej to resztka po awarii."""
    p = Path(stan) / ZNACZNIK_BLOKADY
    try:
        tresc = p.read_text(encoding="utf-8", errors="replace").split()
        wiek = max(0.0, time.time() - p.stat().st_mtime)
    except OSError:
        return None
    pid = int(tresc[0]) if tresc and tresc[0].isdigit() else 0
    zywy = pid_zyje(pid)
    return {"pid": pid, "wiek_s": round(wiek, 1), "zywy": zywy, "aktualny": zywy and wiek < BLOKADA_STARA_S}


# harmonogram kompilacji (docs/WIEDZA.md §6): ta sama reguła dla nadzorcy (natywnie, od startu komputera) i haka tiku
# dyspozytora w bramie (gdy wtyczka jest tam załadowana, np. VPS)
SZKIC_SPOKOJ_S = 5 * 60               # kompilacja, gdy najnowszy szkic ma tyle (seria szkiców z jednej rozmowy idzie razem)…
SZKIC_NAJSTARSZY_S = 15 * 60          # …albo najstarszy tyle (ciągły dopływ szkiców nie odkłada kompilacji w nieskończoność)
KOMPILACJA_PO_AWARII_S = 15 * 60      # po przebiegu przerwanym błędem wywołania modelu (Hermes wyłącza dostawcę na 10 min)
KOMPILACJA_NOC = (3, 10)              # godzina, minuta: nocny przebieg (czas lokalny komputera, w kontenerze jego strefa);
                                      # komputer uśpiony o tej porze nadrabia przebieg raz, po wybudzeniu
STAN_KOMPILACJI = "wiedza-kompilacja.json"    # state/: czas i raport ostatniej kompilacji (pisze kompilacja.py)


def ostatnia_noc(teraz: float, pora: tuple = KOMPILACJA_NOC) -> float:
    """Ostatnia pora nocnego przebiegu nie później niż `teraz` (dziś o 03:10 albo wczoraj), w czasie lokalnym."""
    chwila = dt.datetime.fromtimestamp(teraz)
    noc = chwila.replace(hour=pora[0], minute=pora[1], second=0, microsecond=0)
    if noc > chwila:
        noc -= dt.timedelta(days=1)
    return noc.timestamp()


def stan_kompilacji(stan: str | Path) -> tuple[float, bool]:
    """(czas ostatniej kompilacji, czy przerwał ją błąd wywołania modelu) z state/wiedza-kompilacja.json."""
    try:
        d = json.loads((Path(stan) / STAN_KOMPILACJI).read_text(encoding="utf-8"))
        return float(d.get("ostatnia") or 0), bool((d.get("raport") or {}).get("przerwana"))
    except (OSError, ValueError, TypeError, AttributeError):
        return 0.0, False


def pora_kompilacji(skarbiec: str | Path, stan: str | Path, teraz: float) -> bool:
    """Szkice w skrzynce i: najnowszy ma ≥ SZKIC_SPOKOJ_S (seria z jednej rozmowy już się skończyła) albo najstarszy
    ≥ SZKIC_NAJSTARSZY_S, albo nocny przebieg, którego jeszcze nie było (ostatnia kompilacja przed ostatnią porą
    KOMPILACJA_NOC; komputer uśpiony o 03:10 nadrabia go raz po wybudzeniu, docs/NATYWNIE.md K03). Po przebiegu
    przerwanym błędem wywołania modelu czeka KOMPILACJA_PO_AWARII_S. Bez szkiców nigdy (0 wywołań modelu)."""
    skrzynka = Path(skarbiec) / "skrzynka"
    czasy = [p.stat().st_mtime for p in skrzynka.glob("*.md") if p.is_file()] if skrzynka.is_dir() else []
    if not czasy:
        return False
    ostatnia, przerwana = stan_kompilacji(stan)
    if ostatnia < ostatnia_noc(teraz):
        return True
    if przerwana and teraz - ostatnia < KOMPILACJA_PO_AWARII_S:
        return False
    return teraz - max(czasy) >= SZKIC_SPOKOJ_S or teraz - min(czasy) >= SZKIC_NAJSTARSZY_S


def _sprobuj_zamek(f) -> bool | None:
    """Jedna próba blokady systemu bez czekania: True wzięta, False zajęta, None system plików bez blokad."""
    try:
        if WINDOWS:
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (BlockingIOError, PermissionError):     # POSIX: EWOULDBLOCK, Windows: EACCES
        return False
    except OSError:
        return None


class Blokada:
    """Jeden piszący skarbca (kompilacja: wątek bramy, przycisk w panelu, `jarvo wiedza kompiluj`). Blokada systemu
    (msvcrt.locking, fcntl.flock) na state/wiedza.zamek wyklucza drugi przebieg także w tym samym procesie (każde
    `wez()` ma własny uchwyt) i znika sama, gdy proces padnie. Znacznik state/wiedza.lock („PID czas”) widzi zasiew
    z scripts/install_fleet.py, który blokady systemu nie zna: czeka na żywy znacznik i stawia własny. Dlatego po
    wzięciu blokady żywy, świeży znacznik innego właściciela (wdrożenie w toku) też oznacza „zajęte”."""

    def __init__(self, stan: str | Path, czekaj_s: float = 0.0):
        self.stan = Path(stan)
        self.czekaj_s = czekaj_s
        self._f = None
        self._moj = ""
        self.powod = ""

    def wez(self) -> bool:
        try:
            self.stan.mkdir(parents=True, exist_ok=True)
            f = open(self.stan / PLIK_ZAMKA, "a+b")
        except OSError as e:
            self.powod = f"brak zapisu w {self.stan} ({e.strerror or e})"
            return False
        koniec = time.monotonic() + self.czekaj_s
        wynik = _sprobuj_zamek(f)
        if wynik is False and WINDOWS:
            # Windows zwalnia blokadę zakresu pliku zmarłego procesu z opóźnieniem („zależnie od dostępnych zasobów
            # systemu”, dokumentacja LockFileEx): przy znaczniku martwego właściciela chwilę czekamy, zamiast mówić
            # „inna kompilacja trwa” o procesie, którego już nie ma
            z = znacznik_blokady(self.stan)
            if z and z.get("zywy") is False:
                koniec = max(koniec, time.monotonic() + 5.0)
        while wynik is False and time.monotonic() < koniec:
            time.sleep(0.05)
            wynik = _sprobuj_zamek(f)
        if wynik is False:
            f.close()
            self.powod = "inna kompilacja trwa"
            return False
        self._f = f
        z = znacznik_blokady(self.stan)
        if z and z["aktualny"]:
            self._zwolnij_zamek()
            self.powod = f"skarbiec zajęty (proces {z['pid']}, np. zasiew przy wdrożeniu)"
            return False
        self._moj = f"{os.getpid()} {int(time.time())}\n"
        p = self.stan / ZNACZNIK_BLOKADY
        tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
        try:
            tmp.write_text(self._moj, encoding="utf-8", newline="\n")
            zamien_plik(tmp, p)
        except OSError as e:
            with contextlib.suppress(OSError):
                tmp.unlink()
            self._zwolnij_zamek()
            self.powod = f"nie zapiszę znacznika {p} ({e.strerror or e})"
            return False
        return True

    def zwolnij(self) -> None:
        p = self.stan / ZNACZNIK_BLOKADY
        if self._moj:
            with contextlib.suppress(OSError):
                if p.read_text(encoding="utf-8") == self._moj:     # cudzego znacznika (wdrożenie po awarii) nie ruszamy
                    p.unlink()
            self._moj = ""
        self._zwolnij_zamek()

    def _zwolnij_zamek(self) -> None:
        f, self._f = self._f, None
        if f is None:
            return
        try:
            if WINDOWS:
                import msvcrt
                with contextlib.suppress(OSError):
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            f.close()                                    # POSIX: zamknięcie zwalnia flock

    def __enter__(self) -> bool:
        return self.wez()

    def __exit__(self, *_exc) -> None:
        self.zwolnij()


def utf8_wyjscie() -> None:
    """Na Windows stdout i stderr w UTF-8 (✓, ✗, ogonki), także gdy wyjście idzie do pliku albo potoku, a nie do konsoli."""
    if not WINDOWS:
        return
    for strumien in (sys.stdout, sys.stderr):
        try:
            strumien.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


# ------------------------------------------------------------------------------------------------ frontmatter i tekst

def podziel(text: str) -> tuple[dict, str]:
    """Frontmatter (proste `klucz: wartość`, listy `[a, b]`, cudzysłowy) i treść. Bez YAML-a, bo schemat go nie potrzebuje."""
    if not text.startswith("---\n"):
        return {}, text
    koniec = text.find("\n---", 4)
    if koniec < 0:
        return {}, text
    naglowek, tresc = text[4:koniec], text[koniec + 4:]
    tresc = tresc[1:] if tresc.startswith("\n") else tresc
    fm: dict = {}
    for linia in naglowek.splitlines():
        if not linia.strip() or linia.lstrip().startswith("#") or linia[:1] in " \t":
            continue
        klucz, sep, wart = linia.partition(":")
        if sep:
            fm[klucz.strip()] = _wartosc(wart.strip())
    return fm, tresc


_ELEMENT_LISTY_RE = re.compile(r'\s*("(?:[^"\\]|\\.)*"|\'[^\']*\'|[^,]*)\s*(?:,|$)')


def _elementy_listy(wnetrze: str) -> list[str]:
    """Elementy listy `[a, "b, c", 'd']` (bez nawiasów): przecinek w cudzysłowie nie dzieli elementu (sygnatury błędów)."""
    return [e for e in (m.group(1).strip() for m in _ELEMENT_LISTY_RE.finditer(wnetrze)) if e]


def _wartosc(v: str):
    if v.startswith("[") and v.endswith("]"):
        return [_wartosc(x) if x[0] in "'\"" else x for x in _elementy_listy(v[1:-1])]
    if len(v) >= 2 and v[0] == v[-1] == '"':
        return re.sub(r'\\(["\\])', r"\1", v[1:-1])   # odwrotność `_w_cudzyslow`
    if len(v) >= 2 and v[0] == v[-1] == "'":
        return v[1:-1]
    if v in ("true", "false"):
        return v == "true"
    return v


def goly_yaml(s: str, w_liscie: bool = False) -> bool:
    """Czy `s` przejdzie w YAML-u bez cudzysłowu (wartość albo element listy `[a, b]`): bez znaku specjalnego na
    początku, bez „: ” i „ #” w środku, w liście bez przecinków i nawiasów."""
    if not s or s != s.strip() or s[0] in "{}[]&*!%@`,|>#'\"" or s in ("-", "?") or s.startswith(("- ", "? ")):
        return False
    if ": " in s or s.endswith(":") or " #" in s:
        return False
    return not (w_liscie and any(c in s for c in ",[]{}"))


def zly_naglowek(text: str) -> str:
    """Linia frontmatteru, której YAML (Obsidian, Quartz) nie przeczyta, albo "". `podziel` jest pobłażliwy (bierze
    wszystko po pierwszym „:”), więc `zrodlo: log (orzeczen: 3)` przechodzi u nas, a Quartz przerywa całą budowę
    („bad indentation of a mapping entry”, Mózg 15.11); tak samo `aliasy: [@nazwa]`. Bez PyYAML (`goly_yaml`)."""
    if not text.startswith("---\n"):
        return ""
    koniec = text.find("\n---", 4)
    for linia in text[4:koniec if koniec >= 0 else 4].splitlines():
        if not linia.strip() or linia.lstrip().startswith("#") or linia[:1] in " \t":
            continue
        _k, sep, wart = linia.partition(":")
        v = wart.strip()
        if not sep or not v or v[0] in "'\"" or v in ("|", ">", "|-", ">-"):
            continue
        if v.startswith("[") and v.endswith("]"):
            elementy = _elementy_listy(v[1:-1])
            if any(x[0] not in "'\"" and not goly_yaml(x, w_liscie=True) for x in elementy):
                return linia
        elif not goly_yaml(v):
            return linia
    return ""


def _w_cudzyslow(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def sklej(fm: dict, tresc: str) -> str:
    linie = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            linie.append(f"{k}: [{', '.join(x if goly_yaml(x := str(e), w_liscie=True) else _w_cudzyslow(x) for e in v)}]")
        elif isinstance(v, bool):
            linie.append(f"{k}: {'true' if v else 'false'}")
        else:
            s = str(v)
            if s == "" or any(c in s for c in ":#{}\"'") or s != s.strip() or not goly_yaml(s):
                s = _w_cudzyslow(s)
            linie.append(f"{k}: {s}")
    linie.append("---")
    return "\n".join(linie) + "\n" + tresc.lstrip("\n")


def bez_ogonkow(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).replace("ł", "l").replace("Ł", "L")


def _nfc(rel: str) -> str:
    """Ścieżka z dysku w NFC na macOS: nazwa zapisana w NFD (stare HFS+, niektóre programy) ma pasować do linków w notatkach.
    APFS szuka plików bez względu na normalizację; na Linuksie i Windows NFC i NFD to różne nazwy, więc bez zmian."""
    return unicodedata.normalize("NFC", rel) if MACOS else rel


def nazwa_pliku(tytul: str) -> str:
    """Tytuł, jak się go mówi → nazwa pliku: małe litery, polskie znaki (w NFC) i spacje zostają, bez znaków
    zakazanych, kropki i spacji na końcu i bez nazw urządzeń Windows („con” → „con (notatka)”), więc plik przejdzie
    na każdy system (K07)."""
    s = unicodedata.normalize("NFC", tytul).strip().lower()
    s = "".join(c if (c.isalnum() or c in " ,-.()") else " " for c in s)
    s = re.sub(r"\s+", " ", s).strip(" .-")
    s = s[:70].rstrip(" .-") or "notatka"
    return f"{s} (notatka)" if urzadzenie_windows(s) else s


def urzadzenie_windows(nazwa: str) -> bool:
    """Nazwa urządzenia Windows (CON, NUL, COM1…), także z rozszerzeniem i spacją przed kropką („nul .md”)."""
    return nazwa.split(".", 1)[0].strip().lower() in ZAREZERWOWANE


def nieprzenosna(czesc: str) -> str | None:
    """Powód, dla którego ta część ścieżki (katalog albo plik z rozszerzeniem) nie przejdzie na każdy system, albo None."""
    if urzadzenie_windows(czesc):
        return "nazwa urządzenia Windows"
    if czesc != czesc.rstrip(". "):
        return "kropka albo spacja na końcu (Windows ją obetnie)"
    if unicodedata.normalize("NFC", czesc) != czesc:
        return "znaki zapisane spoza NFC (inny zapis polskich liter: link i nazwa się rozjadą)"
    return None


def slug_ascii(tytul: str, n: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", bez_ogonkow(tytul).lower()).strip("-")
    return s[:n].rstrip("-") or "szkic"


def zawiera_sekret(text: str) -> str | None:
    for nazwa, wzor in SEKRETY:
        if wzor.search(text):
            return nazwa
    return None


def bez_markdown(s: str) -> str:
    s = LINK_RE.sub(lambda m: (m.group(3) or m.group(1)).strip(), s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    return re.sub(r"[*_`]+", "", s).strip()


def zastap_blok(text: str, nazwa: str, tresc: str) -> str:
    """Wymienia blok `<!-- Jarvo:GEN nazwa -->…<!-- /Jarvo:GEN nazwa -->`; brak bloku = doklejony na końcu."""
    blok = f"<!-- Jarvo:GEN {nazwa} -->\n{tresc.strip()}\n<!-- /Jarvo:GEN {nazwa} -->"
    wzor = re.compile(rf"<!-- Jarvo:GEN {nazwa} -->.*?<!-- /Jarvo:GEN {nazwa} -->", re.S)
    if wzor.search(text):
        return wzor.sub(lambda _m: blok, text)
    return text.rstrip("\n") + "\n\n" + blok + "\n"


def podsumowanie_huba(tresc: str) -> str:
    """Tekst bloku STRESZCZENIE huba (`wiedza.py streszczenie`: „wszystko zebrane w jednej”) albo pusto."""
    m = STRESZCZENIE_RE.search(tresc or "")
    return m.group(1).strip() if m else ""


def wstaw_streszczenie(tresc: str, streszczenie: str) -> str:
    """Treść huba (bez frontmatteru) z blokiem STRESZCZENIE: istniejący wymieniony, nowy zaraz pod tytułem i pogrubionym
    opisem (przed częścią ręczną, listą i „Powiązanymi”). Zasiew i indeksuj ruszają tylko bloki GEN, więc blok zostaje."""
    blok = f"<!-- Jarvo:STRESZCZENIE -->\n{streszczenie.strip()}\n<!-- /Jarvo:STRESZCZENIE -->"
    if STRESZCZENIE_RE.search(tresc):
        return STRESZCZENIE_RE.sub(lambda _m: blok, tresc, count=1)
    m = re.search(r"\A\s*# [^\n]*\n(?:\s*\n\*\*[^\n]*\*\*[ \t]*\n)?", tresc)
    if not m:
        return blok + "\n\n" + tresc.lstrip("\n")
    return tresc[:m.end()].rstrip("\n") + "\n\n" + blok + "\n\n" + tresc[m.end():].lstrip("\n")


_METADANA_RE = re.compile(r"^(updated|zaktualizowano|zmieniono|utworzono|status|data)\s*:", re.I)


def streszczenie_tresci(tresc: str, od: int = 0) -> str:
    """Streszczenie notatki (indeks, przypomnienie, Mózg): tekst bloku STRESZCZENIE huba (pierwszy akapit), inaczej
    pierwszy akapit po tytule (od pozycji `od`), bez komentarzy i linii metadanych („updated: …” w user/USER.md), a w
    notatce z samych list pierwsze punkty; na końcu pierwsza linia tekstu w całej treści."""
    podsumowanie = podsumowanie_huba(tresc)
    if podsumowanie:
        akapit = re.split(r"\n\s*\n", podsumowanie, maxsplit=1)[0]
        return " ".join(bez_markdown(l.strip().lstrip("-*• ").strip()) for l in akapit.splitlines() if l.strip())
    out, punkty = "", []
    if od:
        for linia in re.sub(r"<!--.*?-->", "", tresc[od:], flags=re.S).splitlines():
            s = linia.strip()
            if (not s and out) or (s.startswith("#") and punkty and not out):    # akapit skończony albo sekcja z samych list
                break
            if s.startswith("- ") and not out and len(punkty) < 3:
                punkty.append(bez_markdown(s[2:]))
            if s and not s.startswith(("#", "<!--", "|", "-", "```")) and not _METADANA_RE.match(s):
                out = (out + " " + bez_markdown(s)).strip()
        if not out and punkty:
            return "; ".join(p for p in punkty if p)
    if not out:
        for linia in tresc.splitlines():
            s = linia.strip()
            if s and not s.startswith(("#", "<!--", "|", "-", "```", "---")) and not _METADANA_RE.match(s):
                return bez_markdown(s)
    return out


MIN_SLOW_SEKCJI_NOTATKI = 300       # notatka dłuższa, z co najmniej MIN_SEKCJI sekcjami `## `: sekcje w indeksie osobno
MIN_SEKCJI = 3
BEZ_SEKCJI = ("Powiązane", "Notatki (lista automatyczna)")


def sekcje_notatki(n: "Notatka") -> list[tuple[str, str]]:
    """[(nazwa sekcji, treść z nagłówkiem)] notatki dzielonej w indeksie (Indeks._dodaj_sekcje): `sekcje: true` we
    frontmatterze (mapa Jarva) albo długa notatka (≥ MIN_SLOW_SEKCJI_NOTATKI słów) z ≥ MIN_SEKCJI sekcjami `## `
    (np. user/USER.md z wywiadu); bez hubów, archiwum, źródeł i szkiców, bez „Powiązanych” i list generowanych."""
    if n.hub or n.sciezka.startswith(POZA_WYSZUKIWANIEM):
        return []
    tresc = GEN_RE.sub(lambda m: m.group(0) if "GEN lista" not in m.group(0) else "", n.tresc)
    sekcje = [(m.group(1).strip(), m.group(0).strip()) for m in re.finditer(r"^## (.+?)[ \t]*\n.*?(?=^## |\Z)", tresc, re.M | re.S)]
    sekcje = [(nazwa, t) for nazwa, t in sekcje if nazwa not in BEZ_SEKCJI and len(t.split("\n", 1)[-1].strip()) > 0]
    if n.fm.get("sekcje") is True or (len(sekcje) >= MIN_SEKCJI and n.slowa >= MIN_SLOW_SEKCJI_NOTATKI):
        return sekcje
    return []


def wytnij_sekcje(n: "Notatka", sekcja: str) -> "Notatka | None":
    """Sama sekcja `## <sekcja>` notatki (wielkość liter i ogonki bez znaczenia) jako Notatka `ścieżka#Sekcja` albo None."""
    klucz = bez_ogonkow(sekcja).strip().lower()
    for m in re.finditer(r"^## (.+?)[ \t]*\n.*?(?=^## |\Z)", n.tresc, re.M | re.S):
        if bez_ogonkow(m.group(1)).strip().lower() == klucz:
            nazwa, tekst = m.group(1).strip(), m.group(0).strip()
            return Notatka(sciezka=f"{n.sciezka}#{nazwa}", tytul=f"{n.tytul}: {nazwa}", streszczenie=streszczenie_tresci(tekst)[:240],
                           fm=n.fm, tresc=tekst + "\n", linki=[l for l in n.linki if f"[[{l[0]}" in tekst],
                           slowa=len(re.findall(r"\w+", tekst)), mtime=n.mtime, rozmiar=n.rozmiar)
    return None


# ------------------------------------------------------------------------------------------------ notatka

def zakres_marki(marka: str, agent: str = "", orzeczenia: str = "") -> tuple[str, ...]:
    """Ścieżki skarbca widoczne dla agenta biznesowego (fleet.yaml `marka`): katalogi z „/” na końcu, pliki orzeczeń bez
    `.md`. Brak marki (albo marka spoza [a-z0-9-]) = pusta krotka: agent widzi cały skarbiec."""
    if not marka or not MARKA_RE.fullmatch(marka):
        return ()
    z = [f"brands/{marka}/", *([f"agenci/{agent}/"] if agent else []), *WSPOLNE_DLA_MAREK,
         *([orzeczenia] if orzeczenia else []), f"orzeczenia/marki/{marka}", "orzeczenia/wszyscy"]
    return tuple(dict.fromkeys(z))


def marki_z_orzeczeniami(sk: "Skarbiec") -> list[str]:
    """Marki, które mają plik `orzeczenia/marki/<marka>.md` (posortowane): agent bez marki widzi cały skarbiec, więc
    w przypomnieniu dostaje orzeczenia każdej marki."""
    katalog = sk.root / "orzeczenia" / "marki"
    try:
        return sorted(p.stem for p in katalog.glob("*.md") if p.is_file() and not p.name.startswith(("_", ".")))
    except OSError:
        return []


def w_zakresie(rel: str, zakres) -> bool:
    """Ścieżka (notatka bez `.md`, plik albo katalog) w zakresie agenta; pusty zakres = wszystko."""
    if not zakres:
        return True
    rel = rel.strip().strip("/").removesuffix(".md")
    return any(rel == z.rstrip("/") or (z.endswith("/") and rel.startswith(z)) for z in zakres)


def folder_w_zakresie(folder: str, zakres) -> bool:
    """Folder `wiedza_szukaj` w zakresie: w dozwolonym katalogu albo nad nim (`brands`, `orzeczenia`: wyniki i tak
    tylko z zakresu); pusty zakres = każdy folder."""
    f = folder.strip().strip("/")
    return not zakres or any(z.startswith(f + "/") or w_zakresie(f, (z,)) for z in zakres)


def _warunek_zakresu(zakres) -> tuple[str, list[str]]:
    """Warunek SQL na kolumnę `p.sciezka` (LIMIT liczy wtedy tylko notatki z zakresu)."""
    czesci, arg = [], []
    for z in zakres:
        if z.endswith("/"):
            czesci.append("p.sciezka LIKE ? ESCAPE '\\'")
            arg.append(z.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
        else:
            czesci.append("p.sciezka = ?")
            arg.append(z)
    return "(" + " OR ".join(czesci) + ")", arg


@dataclass
class Notatka:
    sciezka: str                      # względem skarbca, bez `.md`, POSIX
    tytul: str
    streszczenie: str
    fm: dict
    tresc: str                        # bez frontmatteru
    linki: list = field(default_factory=list)   # (cel, etykieta, auto)
    slowa: int = 0
    mtime: float = 0.0
    rozmiar: int = 0

    @property
    def folder(self) -> str:
        return self.sciezka.split("/", 1)[0] if "/" in self.sciezka else ""

    @property
    def hub(self) -> bool:
        return self.sciezka.rsplit("/", 1)[-1].startswith("_hub-")

    @property
    def typ(self) -> str:
        return str(self.fm.get("typ") or ("hub" if self.hub else ""))


def _zwykly_cel(cel: str) -> bool:
    """Cel linku, który na pewno jest albo nie jest w `Skarbiec.pliki()` (bez sprawdzania dysku)."""
    czesci = cel.split("/")
    return (not cel.endswith(".md") and "\\" not in cel and cel + ".md" not in PLIKI_SPECJALNE
            and all(c and c not in (".", "..") and not c.startswith(".") and c != "_szablon" for c in czesci))


class Skarbiec:
    def __init__(self, root: str | Path, stan: str | Path | None = None):
        self.root = Path(root).resolve()
        self.stan = Path(stan).resolve() if stan else Path(os.environ.get("JARVO_STATE_DIR") or (self.root.parent / "state")).resolve()

    # ---- ścieżki
    def plik(self, rel: str) -> Path:
        """Bezpieczna ścieżka w skarbcu (bez `..`, bez symlinków na zewnątrz); `.md` dopisywane, gdy brak.
        Na Windows bez „:” (litera dysku, strumień NTFS zamiast pliku) i „\\” (drugi separator ścieżki)."""
        rel = rel.strip().lstrip("/")
        if WINDOWS and (":" in rel or "\\" in rel):
            raise ValueError(f"nazwa z „:” albo „\\” (Windows jej nie przyjmie): {rel}")
        if not rel.endswith(".md"):
            rel += ".md"
        if WINDOWS and any(urzadzenie_windows(c) for c in rel.split("/")):    # „nul.md” połknąłby zapis bez śladu
            raise ValueError(f"nazwa urządzenia Windows (CON, NUL, COM1…): {rel}")
        p = (self.root / rel).resolve()
        if p != self.root and self.root not in p.parents:
            raise ValueError(f"ścieżka poza skarbcem: {rel}")
        return p

    def rel(self, p: Path) -> str:
        return _nfc(p.relative_to(self.root).as_posix()[:-3])

    def pliki_ze_stanem(self) -> dict[str, tuple[float, int]]:
        """Notatki (ścieżka bez `.md`) → (mtime, rozmiar) jednym przejściem os.walk: bez katalogów z kropką i szablonów
        (brands/_szablon), bez plików specjalnych w korzeniu. Odświeżenie indeksu przed każdą turą: rglob ze stat-em
        osobno to ok. 55 ms na 1 200 plików, os.walk ok. 7 ms (pomiar 20.11)."""
        out: dict[str, tuple[float, int]] = {}
        korzen = str(self.root)
        for katalog, podkatalogi, nazwy in os.walk(korzen):
            podkatalogi[:] = [d for d in podkatalogi if not d.startswith(".") and d != "_szablon"]
            rel_kat = os.path.relpath(katalog, korzen).replace(os.sep, "/")
            for nazwa in nazwy:
                if not nazwa.endswith(".md") or nazwa.startswith(".") or (rel_kat == "." and nazwa in PLIKI_SPECJALNE):
                    continue
                rel = nazwa[:-3] if rel_kat == "." else f"{rel_kat}/{nazwa[:-3]}"
                if WINDOWS and any(urzadzenie_windows(c) for c in f"{rel}.md".split("/")):   # „nul.md” ze skarbca z Linuksa:
                    continue                                                                  # Win32 go nie otworzy (K07)
                try:
                    st = os.stat(os.path.join(katalog, nazwa))
                except OSError:
                    continue
                out[_nfc(rel)] = (st.st_mtime, st.st_size)
        return dict(sorted(out.items()))

    def pliki(self) -> list[str]:
        """Wszystkie notatki (bez katalogów z kropką i plików specjalnych), ścieżki bez `.md`, posortowane."""
        return list(self.pliki_ze_stanem())

    def istnieje(self, rel: str) -> bool:
        try:
            return self.plik(rel).is_file()
        except ValueError:
            return False

    def przekierowanie(self, rel: str) -> str | None:
        """Notatka przeniesiona do archiwum (`archiwum/<dawna ścieżka>`): jej następca (`zastapiona_przez`, gdy istnieje
        i sam nie jest w archiwum) albo wpis w archiwum; None, gdy pod dawną ścieżką nic nie leżało. Stara ścieżka
        z pamięci agenta, starej sesji albo notatki sprzed przeniesienia prowadzi tak do aktualnej wiedzy."""
        rel = rel.strip().strip("/").removesuffix(".md")
        if not rel or rel.startswith(ARCHIWUM + "/"):
            return None
        stara = f"{ARCHIWUM}/{rel}"
        if not self.istnieje(stara):
            return None
        try:
            fm, _ = podziel(self.plik(stara).read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            return stara
        nastepca = str(fm.get("zastapiona_przez") or "").strip().strip("/").removesuffix(".md")
        return nastepca if nastepca and not nastepca.startswith(ARCHIWUM + "/") and self.istnieje(nastepca) else stara

    # ---- czytanie
    def wczytaj(self, rel: str) -> Notatka:
        """Notatka (z frontmatterem, tytułem, streszczeniem, linkami). `ścieżka#Sekcja` (wpis sekcji z indeksu) = sama ta
        sekcja; ścieżka przeniesiona do archiwum = następca albo wpis w archiwum (przekierowanie)."""
        if "#" in rel:
            baza, _, sekcja = rel.partition("#")
            n = self.wczytaj(baza)
            return (wytnij_sekcje(n, sekcja) if sekcja.strip() else None) or n
        p = self.plik(rel)
        if not p.exists():
            # model pisze ścieżkę bez polskich znaków („przegladarce”); 12.11 dwa nieudane wiedza_czytaj z rzędu
            klucz = bez_ogonkow(p.name).lower()
            p = next((q for q in sorted(p.parent.glob("*.md")) if bez_ogonkow(q.name).lower() == klucz), p) \
                if p.parent.is_dir() else p
        if not p.exists() and (nowa := self.przekierowanie(rel)):     # przeniesiona do archiwum: następca albo archiwum
            p = self.plik(nowa)
        text = p.read_text(encoding="utf-8", errors="replace")
        fm, tresc = podziel(text)
        m = re.search(r"^# (.+)$", tresc, re.M)
        tytul = bez_markdown(m.group(1)) if m else self.rel(p).rsplit("/", 1)[-1]
        streszczenie = streszczenie_tresci(tresc, m.end() if m else 0)
        n = Notatka(sciezka=self.rel(p), tytul=tytul, streszczenie=streszczenie[:240], fm=fm, tresc=tresc,
                    slowa=len(re.findall(r"\w+", GEN_RE.sub("", tresc))), mtime=p.stat().st_mtime, rozmiar=p.stat().st_size)
        n.linki = self._linki(tresc)
        return n

    def _linki(self, tresc: str) -> list[tuple[str, str, bool]]:
        auto_zakresy = [(m.start(), m.end()) for m in GEN_RE.finditer(tresc)]
        out = []
        for m in LINK_RE.finditer(tresc):
            cel = m.group(1).strip()
            if cel.endswith(".md"):
                cel = cel[:-3]
            auto = any(a <= m.start() < b for a, b in auto_zakresy)
            out.append((cel, (m.group(3) or cel).strip(), auto))
        return out

    def mapa(self) -> tuple[set[str], dict[str, str]]:
        """Jedno przejście po dysku na wiele linków: zbiór ścieżek notatek i nazwa pliku → pierwsza ścieżka."""
        pliki = self.pliki()
        znane: dict[str, str] = {}
        for rel in pliki:
            znane.setdefault(rel.rsplit("/", 1)[-1], rel)
        return set(pliki), znane

    def rozwiaz(self, cel: str, znane: dict[str, str] | None = None, zbior: set[str] | None = None) -> str | None:
        """Cel linku → ścieżka notatki: pełna ścieżka albo (jak w Obsidianie) sama nazwa pliku, gdy jednoznaczna.

        Z `zbior` (z `mapa()`) zwykła ścieżka rozstrzyga się w pamięci; dysk tylko dla nietypowych celów
        (pliki specjalne, `.md` na końcu, katalogi z kropką, `..`)."""
        cel = cel.strip().lstrip("/")
        if zbior is not None and cel in zbior:
            return cel
        if (zbior is None or not _zwykly_cel(cel)) and self.istnieje(cel):
            return cel
        if "/" not in cel:
            return (znane if znane is not None else self.mapa()[1]).get(cel)
        return None

    # ---- pisanie
    def zapisz_plik(self, rel: str, text: str) -> Path:
        p = self.plik(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(text, encoding="utf-8", newline="\n")      # LF także na Windows (Obsidian, git, sumy)
        zamien_plik(tmp, p)
        return p

    def dopisz_log(self, rodzaj: str, tresc: str) -> None:
        p = self.root / "LOG.md"
        if not p.exists():
            p.write_text("# Dziennik skarbca\n\nTylko dopisywanie. Format: `## [data] rodzaj | co się stało`.\n",
                         encoding="utf-8", newline="\n")
        with p.open("a", encoding="utf-8", newline="\n") as f:
            f.write(f"\n## [{dzis()}] {rodzaj} | {tresc.strip()}\n")

    # ---- git (punkty zapisu)
    def git(self, *args: str) -> subprocess.CompletedProcess | None:
        """git w skarbcu; wyjście zawsze w UTF-8 (opisy z polskimi znakami, także na Windows z kodowaniem cp1250)."""
        try:
            return subprocess.run([shutil.which("git") or "git", *GIT_TOZSAMOSC, *GIT_PRZENOSNIE, "-C", str(self.root), *args],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=BEZ_OKNA)
        except FileNotFoundError:
            return None

    def git_init(self) -> bool:
        if (self.root / ".git").exists():
            self._gitignore_systemu()
            return True
        r = self.git("init", "-q")
        if r is None or r.returncode != 0:
            return False
        (self.root / ".gitignore").write_text("\n".join(("*.tmp", *GITIGNORE_SYSTEMU)) + "\n", encoding="utf-8", newline="\n")
        return True

    def _gitignore_systemu(self) -> None:
        """Skarbiec z innego systemu (np. przeniesiony z kontenera na Windows): brakujące śmieci tego systemu do .gitignore.
        Na Linuksie lista jest pusta, więc plik zostaje taki, jak go zostawił `git init`."""
        p = self.root / ".gitignore"
        try:
            stary = p.read_text(encoding="utf-8") if p.exists() else ""
            brak = [w for w in GITIGNORE_SYSTEMU if w not in stary.splitlines()]
            if brak:
                p.write_text(stary + ("" if not stary or stary.endswith("\n") else "\n") + "\n".join(brak) + "\n",
                             encoding="utf-8", newline="\n")
        except OSError:
            pass

    def punkt_zapisu(self, komunikat: str) -> bool:
        if not (self.root / ".git").exists():
            return False
        r = self.git("add", "-A")
        if r is None or r.returncode != 0:
            return False
        r = self.git("diff", "--cached", "--quiet")
        if r is not None and r.returncode == 0:
            return True   # nic nowego
        r = self.git("commit", "-q", "-m", komunikat)
        return r is not None and r.returncode == 0

    def cofnij(self) -> str:
        if not (self.root / ".git").exists():
            return "skarbiec nie ma punktów zapisu (brak git)"
        r = self.git("log", "-1", "--format=%s")
        ostatni = (r.stdout.strip() if r and r.returncode == 0 else "") or "?"
        r = self.git("revert", "--no-edit", "HEAD")
        if r is None or r.returncode != 0:
            return "nie udało się cofnąć: " + ((r.stderr or r.stdout).strip() if r else "brak git")
        return f"cofnięto punkt zapisu: {ostatni}"


# ------------------------------------------------------------------------------------------------ indeks FTS5

class Indeks:
    """SQLite poza skarbcem (state/wiedza.db): FTS5 z `remove_diacritics 2` (ogonki bez znaczenia), linki, metadane,
    aliasy notatek (frontmatter `aliasy:`) i wektory notatek (`wektory`: ścieżka, hash tekstu, id modelu, float32)."""

    def __init__(self, sk: Skarbiec):
        self.sk = sk
        sk.stan.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(sk.stan / "wiedza.db"), timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS pliki(sciezka TEXT PRIMARY KEY, mtime REAL, rozmiar INTEGER, tytul TEXT, streszczenie TEXT,
                typ TEXT, status TEXT, agent TEXT, folder TEXT, zmieniono TEXT, wazne_do TEXT, hub INTEGER, slowa INTEGER);
            CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(sciezka UNINDEXED, tytul, streszczenie, tresc, tagi,
                tokenize='unicode61 remove_diacritics 2');
            CREATE TABLE IF NOT EXISTS linki(z TEXT, do_ TEXT, etykieta TEXT, auto INTEGER, rozwiazany INTEGER);
            CREATE INDEX IF NOT EXISTS linki_do ON linki(do_);
            CREATE TABLE IF NOT EXISTS meta(klucz TEXT PRIMARY KEY, wartosc TEXT);
            CREATE TABLE IF NOT EXISTS aliasy(sciezka TEXT, alias TEXT, tytul TEXT);
            CREATE INDEX IF NOT EXISTS aliasy_sciezka ON aliasy(sciezka);
            CREATE TABLE IF NOT EXISTS wektory(sciezka TEXT PRIMARY KEY, hash TEXT, model TEXT, wektor BLOB, mtime REAL,
                rozmiar INTEGER);
            CREATE TABLE IF NOT EXISTS sekcje(sciezka TEXT PRIMARY KEY, rodzic TEXT, mtime REAL, rozmiar INTEGER, tytul TEXT,
                streszczenie TEXT, typ TEXT, status TEXT, agent TEXT, folder TEXT, zmieniono TEXT);
            CREATE INDEX IF NOT EXISTS sekcje_rodzic ON sekcje(rodzic);
            CREATE VIEW IF NOT EXISTS wpisy AS
                SELECT sciezka, mtime, rozmiar, tytul, streszczenie, typ, status, agent, folder, zmieniono FROM pliki
                UNION ALL SELECT sciezka, mtime, rozmiar, tytul, streszczenie, typ, status, agent, folder, zmieniono FROM sekcje;
        """)
        wersja = self.db.execute("SELECT wartosc FROM meta WHERE klucz = 'wersja'").fetchone()
        self._przebuduj = wersja is None or wersja[0] != WERSJA_INDEKSU      # indeks sprzed aliasów: raz od nowa
        self.silnik = "slowa"                   # silnik ostatniego szukaj(): hybryda | wektory | slowa (dziennik przypomnień)

    def zamknij(self) -> None:
        self.db.close()

    def odswiez(self, pelny: bool = False) -> dict:
        """Indeks przyrostowy po mtime i rozmiarze. Linki przeliczane w całości, ale tylko gdy coś się zmieniło
        (notatka, lista plików specjalnych) albo przy `pelny`; bez zmian odświeżenie to sam przegląd katalogów.
        Wektorów nie liczy (to robi odswiez_wektory przy indeksuj, kompilacji i zasiewie, poza turą rozmowy)."""
        pelny = pelny or self._przebuduj
        stan_plikow = self.sk.pliki_ze_stanem()
        pliki = list(stan_plikow)
        zbior = set(pliki)
        specjalne = ",".join(sorted(n for n in PLIKI_SPECJALNE if (self.sk.root / n).is_file()))
        stare = {r["sciezka"]: (r["mtime"], r["rozmiar"]) for r in self.db.execute("SELECT sciezka, mtime, rozmiar FROM pliki")}
        nowe = zmienione = 0
        notatki: dict[str, Notatka] = {}
        with self.db:
            if pelny:                                    # DELETE po kolumnie UNINDEXED skanuje całe FTS: przy przebudowie raz
                self.db.execute("DELETE FROM fts")
                self.db.execute("DELETE FROM aliasy")
            for rel in pliki:
                if not pelny and rel in stare and stare[rel] == stan_plikow[rel]:
                    continue
                n = self.sk.wczytaj(rel)
                notatki[rel] = n
                nowe += rel not in stare
                zmienione += rel in stare
                if rel in stare and not pelny:           # nowa notatka nie ma wiersza w FTS (pliki i fts w jednej transakcji)
                    self.db.execute("DELETE FROM fts WHERE sciezka = ?", (rel,))
                    self._usun_sekcje(rel)
                elif pelny:
                    self.db.execute("DELETE FROM sekcje WHERE rodzic = ?", (rel,))
                self._dodaj_sekcje(n)
                self.db.execute("INSERT INTO fts(sciezka, tytul, streszczenie, tresc, tagi) VALUES (?,?,?,?,?)",
                                (rel, n.tytul, n.streszczenie, LISTA_RE.sub("", n.tresc), " ".join(n.fm.get("tagi") or []) if isinstance(n.fm.get("tagi"), list) else str(n.fm.get("tagi") or "")))
                self.db.execute("INSERT OR REPLACE INTO pliki VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (rel, n.mtime, n.rozmiar, n.tytul, n.streszczenie, n.typ, str(n.fm.get("status") or ""),
                                 str(n.fm.get("agent") or ""), n.folder, str(n.fm.get("zmieniono") or ""),
                                 str(n.fm.get("wazne_do") or ""), int(n.hub), n.slowa))
                if not pelny:
                    self.db.execute("DELETE FROM aliasy WHERE sciezka = ?", (rel,))
                for alias in aliasy_notatki(n):
                    self.db.execute("INSERT INTO aliasy VALUES (?,?,?)", (rel, alias, n.tytul))
            usuniete = [s for s in stare if s not in zbior]
            for s in usuniete:
                self._usun_sekcje(s)
                self.db.execute("DELETE FROM fts WHERE sciezka = ?", (s,))
                self.db.execute("DELETE FROM pliki WHERE sciezka = ?", (s,))
                self.db.execute("DELETE FROM aliasy WHERE sciezka = ?", (s,))
                self.db.execute("DELETE FROM wektory WHERE sciezka = ?", (s,))
            # linki: całość od nowa (potrzebne do lintu, grafu i rozszerzania wyników), gdy cokolwiek się zmieniło
            stan_linkow = self.db.execute("SELECT wartosc FROM meta WHERE klucz = 'linki'").fetchone()
            if pelny or nowe or zmienione or usuniete or stan_linkow is None or stan_linkow[0] != specjalne:
                znane: dict[str, str] = {}
                for rel in pliki:
                    znane.setdefault(rel.rsplit("/", 1)[-1], rel)
                self.db.execute("DELETE FROM linki")
                for rel in pliki:
                    n = notatki.get(rel) or self.sk.wczytaj(rel)
                    for cel, etykieta, auto in n.linki:
                        cel_r = self.sk.rozwiaz(cel, znane, zbior)
                        self.db.execute("INSERT INTO linki VALUES (?,?,?,?,?)", (rel, cel_r or cel, etykieta, int(auto), int(cel_r is not None)))
                self.db.execute("INSERT OR REPLACE INTO meta VALUES ('linki', ?)", (specjalne,))
            if self._przebuduj:
                self.db.execute("INSERT OR REPLACE INTO meta VALUES ('wersja', ?)", (WERSJA_INDEKSU,))
        self._przebuduj = False
        return {"pliki": len(pliki), "nowe": nowe, "zmienione": zmienione, "usuniete": len(usuniete)}

    def _dodaj_sekcje(self, n: Notatka) -> None:
        """Sekcje `## ` długiej notatki jako osobne wpisy indeksu (`ścieżka#Sekcja`: FTS, wektory, wyniki szukania):
        przypomnienie trafia w sekcję z odpowiedzią, a wektor całej notatki widzi tylko jej początek (MAX_ZNAKOW_WEKTORA)."""
        for nazwa, tekst in sekcje_notatki(n):
            s = f"{n.sciezka}#{nazwa}"
            stresz = streszczenie_tresci(tekst)[:240]
            self.db.execute("INSERT OR REPLACE INTO sekcje VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (s, n.sciezka, n.mtime, n.rozmiar, f"{n.tytul}: {nazwa}", stresz, n.typ, str(n.fm.get("status") or ""),
                             str(n.fm.get("agent") or ""), n.folder, str(n.fm.get("zmieniono") or "")))
            self.db.execute("INSERT INTO fts(sciezka, tytul, streszczenie, tresc, tagi) VALUES (?,?,?,?,?)",
                            (s, f"{n.tytul}: {nazwa}", stresz, tekst, ""))

    def _usun_sekcje(self, rodzic: str) -> None:
        for (s,) in self.db.execute("SELECT sciezka FROM sekcje WHERE rodzic = ?", (rodzic,)).fetchall():
            self.db.execute("DELETE FROM fts WHERE sciezka = ?", (s,))
            self.db.execute("DELETE FROM wektory WHERE sciezka = ?", (s,))
        self.db.execute("DELETE FROM sekcje WHERE rodzic = ?", (rodzic,))

    @staticmethod
    def slowa(q: str) -> list[str]:
        """Słowa zapytania bez stopsłów i powtórzeń, w kolejności z pytania."""
        return list(dict.fromkeys(w for w in re.findall(r"\w+", q.lower()) if len(w) >= 2 and w not in STOPSLOWA))

    @staticmethod
    def zapytanie(q: str | list[str]) -> str:
        slowa = q if isinstance(q, list) else Indeks.slowa(q)[:MAX_SLOW_ZAPYTANIA]
        return " OR ".join(f'"{w}"*' for w in slowa)

    def slowa_informacyjne(self, q: str, n: int = MAX_SLOW_ZAPYTANIA) -> list[str]:
        """Do `n` słów zapytania. Dłuższe pytanie (zlecenie karty, prompt rutyny) zostawia słowa najrzadsze w skarbcu
        (liczba notatek z tym prefiksem w FTS5), w kolejności z pytania, zamiast pierwszych `n`; słowa bez żadnej
        notatki odpadają, bo nic nie znajdą."""
        slowa = self.slowa(q)
        if len(slowa) <= n:
            return slowa
        df = {w: self.db.execute("SELECT count(*) FROM fts WHERE fts MATCH ?", (f'"{w}"*',)).fetchone()[0]
              for w in slowa[:MAX_SLOW_OCENIANYCH]}
        trafne = [w for w in df if df[w]]
        if not trafne:
            return slowa[:n]
        wybrane = set(sorted(trafne, key=lambda w: df[w])[:n])       # sort stabilny: przy remisie wcześniejsze słowo
        return [w for w in slowa if w in wybrane]

    def rozszerz(self, q: str, zakres=()) -> str:
        """Zapytanie z tytułami notatek, których alias (frontmatter `aliasy:`) pada w pytaniu: „co lubi szefowa” →
        „co lubi szefowa Ola Wrona”. Ogonki i wielkość liter bez znaczenia, słowa aliasu pasują też w odmianie
        (_ma_fraze). Tytuł, który już jest w pytaniu, nie wraca. Z `zakres` (agent biznesowy) tylko aliasy notatek
        z zakresu."""
        slowa = _slowa_lista(q)
        if not slowa:
            return q
        w_pytaniu = " ".join(slowa)
        dopiski: list[str] = []
        for alias, tytul, sciezka in self.db.execute("SELECT alias, tytul, sciezka FROM aliasy ORDER BY sciezka, alias"):
            if (tytul in dopiski or " ".join(_slowa_lista(tytul)) in w_pytaniu or not _ma_fraze(slowa, alias.split())
                    or not w_zakresie(sciezka, zakres)):
                continue
            dopiski.append(tytul)
            if len(dopiski) >= MAX_DOPISKOW_ALIASOW:
                break
        return q + (" " + " ".join(dopiski) if dopiski else "")

    def szukaj_wektorami(self, osadzacz, q: str, n: int = WEKTOROW_W_RANKINGU, zakres=()) -> list[tuple[str, float]] | None:
        """[(ścieżka, kosinus)] najlepszych `n` notatek albo None (brak modelu, wektorów, usługi albo czasu: wołający
        zostaje przy słowach). Pytanie dłuższe niż DLUGIE_ZAPYTANIE słów idzie zdaniami (każde z aliasami), wynik notatki
        to najlepsze zdanie. Iloczyn skalarny w czystym Pythonie: wektory są znormalizowane, brama nie ma numpy.
        Z `zakres` (agent biznesowy) ranking tylko notatek z zakresu, więc `n` najlepszych jest z zakresu."""
        model = getattr(osadzacz, "model", "") if osadzacz is not None else ""
        if not model:
            return None
        wiersze = self.db.execute("SELECT sciezka, wektor FROM wektory WHERE model = ?", (model,)).fetchall()
        if not wiersze:
            return None
        pytania = osadzacz.osadz([f"query: {self.rozszerz(z, zakres)}" for z in zdania_zapytania(q)])
        if not pytania:
            return None
        wymiar = len(pytania[0])
        wyniki = []
        for s, blob in (wiersze if not zakres else [x for x in wiersze if w_zakresie(x[0], zakres)]):
            v = wektor_z_bajtow(blob)
            if len(v) == wymiar:
                wyniki.append((-max(_iloczyn(p, v) for p in pytania), s))
        wyniki.sort()
        return [(s, -w) for w, s in wyniki[:n]]

    def szukaj(self, q: str, limit: int = 5, folder: str | None = None, agent: str | None = None, zrodla: bool = False,
               wektory=None, silnik: str | None = None, zakres=()) -> list[dict]:
        """Notatki do pytania. `wektory` (KlientWektorow albo atrapa: `model`, `osadz(teksty)`) i `silnik` (SILNIKI,
        domyślnie SILNIK): wektory = lista wektorów (kosinus), a notatki jeszcze bez wektora (nowe od ostatniego
        osadzania, zrodla/ przy `zrodla`) wchodzą z miejscem z listy BM25; hybryda = fuzja RRF listy BM25 i listy
        wektorów; slowa = BM25. Bez wektorów (brak usługi, modelu, czasu) zawsze BM25; użyty silnik zostaje
        w `self.silnik`. Zapytanie rozszerzają aliasy notatek (rozszerz). `zakres` (zakres_marki, agent biznesowy): tylko
        notatki z zakresu, już w zapytaniu (BM25 z warunkiem SQL, wektory przefiltrowane), więc wyników jest do `limit`.
        Archiwum (notatki wycofane i zastąpione) tylko z `folder="archiwum"`: link i stara ścieżka prowadzą do następcy."""
        silnik = silnik if silnik in SILNIKI else SILNIK
        wek = self.szukaj_wektorami(wektory, q, zakres=zakres) if wektory is not None and silnik != "slowa" else None
        self.silnik = silnik if wek is not None else "slowa"
        kolumny = "p.sciezka, p.tytul, p.streszczenie, p.typ, p.status, p.folder, p.agent, p.zmieniono"
        podzielone = {r[0] for r in self.db.execute("SELECT DISTINCT rodzic FROM sekcje")}

        def dopuszczona(r) -> bool:
            s = r["sciezka"]
            if s in podzielone:                           # notatka podzielona na sekcje: wracają jej sekcje, nie całość
                return False
            if s.startswith(ARCHIWUM + "/"):
                return bool(folder) and folder.strip("/").split("/", 1)[0] == ARCHIWUM and s.startswith(folder.rstrip("/") + "/")
            if not zrodla and s.startswith(POZA_WYSZUKIWANIEM):
                return False
            if r["typ"] == "skill" and not folder:            # węzły grafu o flocie: tylko z folder="fleet"
                return False
            if folder and not s.startswith(folder.rstrip("/") + "/"):
                return False
            if zakres and not w_zakresie(s, zakres):
                return False
            return not (agent and r["agent"] and r["agent"] != agent)

        bm = []
        zap = self.zapytanie(self.slowa_informacyjne(self.rozszerz(q, zakres)))
        if zap:
            warunek, arg = _warunek_zakresu(zakres) if zakres else ("", [])
            bm = [r for r in self.db.execute(
                f"SELECT {kolumny}, bm25(fts, 0, 3.0, 2.0, 1.0, 1.5) AS w FROM fts f JOIN wpisy p ON p.sciezka = f.sciezka "
                f"WHERE fts MATCH ?{' AND ' + warunek if warunek else ''} ORDER BY w LIMIT ?", (zap, *arg, limit * 6)).fetchall()
                  if dopuszczona(r)]
        if wek is None:
            ranking = [(r, round(-r["w"], 3)) for r in bm]
        else:
            meta = {r["sciezka"]: r for r in bm}
            brak = [s for s, _w in wek if s not in meta]
            for i in range(0, len(brak), 500):
                czesc = brak[i:i + 500]
                for r in self.db.execute(f"SELECT {kolumny} FROM wpisy p WHERE p.sciezka IN ({','.join('?' * len(czesc))})", czesc):
                    meta[r["sciezka"]] = r
            lista_wek = [s for s, _w in wek if s in meta and dopuszczona(meta[s])]
            wynik: dict[str, float] = {}
            if self.silnik == "wektory":
                z_wektorem = {r[0] for r in self.db.execute("SELECT sciezka FROM wektory WHERE model = ?", (wektory.model,))}
                for lista in (lista_wek, [r["sciezka"] for r in bm if r["sciezka"] not in z_wektorem]):
                    for poz, s in enumerate(lista):
                        wynik.setdefault(s, 1.0 / (RRF_K + poz))
            else:
                for lista in ([r["sciezka"] for r in bm], lista_wek):
                    for poz, s in enumerate(lista):
                        wynik[s] = wynik.get(s, 0.0) + 1.0 / (RRF_K + poz)
            ranking = [(meta[s], round(wynik[s], 5)) for s in sorted(wynik, key=lambda s: (-wynik[s], s))]
        out, widziane = [], set()
        for r, punkty in ranking:
            s = r["sciezka"]
            baza = s.split("#", 1)[0]                    # notatka albo jej sekcja: jedno miejsce, wyżej oceniony wpis
            if s in widziane or baza in widziane:
                continue
            widziane.update((s, baza))
            out.append({"sciezka": s, "tytul": r["tytul"], "streszczenie": r["streszczenie"], "typ": r["typ"],
                        "status": r["status"], "zmieniono": r["zmieniono"], "wynik": punkty})
            if len(out) >= limit:
                break
        # krok po linkach: trafienie w marce pociąga orzeczenia tej marki
        for r in list(out):
            if r["sciezka"].startswith("brands/") and "/" in r["sciezka"][7:]:
                marka = r["sciezka"].split("/")[1]
                orz = f"orzeczenia/marki/{marka}"
                if self.sk.istnieje(orz) and orz not in widziane and w_zakresie(orz, zakres):
                    widziane.add(orz)
                    out.append({"sciezka": orz, "tytul": f"Orzeczenia marki {marka}", "streszczenie": "korekty użytkownika dotyczące tej marki",
                                "typ": "orzeczenia", "status": "aktualna", "zmieniono": "", "wynik": 0.0})
        return out

    def odswiez_wektory(self, osadzacz, czas_s: float | None = None, przerwa_s: float = 0.0) -> dict:
        """Wektory notatek przyrostowo (po odswiez(): pliki i FTS aktualne). Tekst wektora jak w pomiarze: „passage: ”,
        tytuł, streszczenie, początek treści (tekst_wektora). Nowa albo zmieniona notatka (mtime, rozmiar) z innym hashem
        tekstu dostaje nowy wektor; ten sam hash = sam nowy mtime. Inny model niż w bazie = pełne przeliczenie (wektory
        starego modelu znikają). Zrodla/ i skrzynka/ bez wektorów (poza wyszukiwaniem). Paczki po WEKTORY_PACZKA, każda
        we własnej transakcji, z `przerwa_s` między nimi (nadrabianie w usłudze nie zajmuje procesora bez przerwy);
        usługa niedostępna w trakcie = przerwane, reszta przy następnym razie. Zwraca liczby."""
        model = getattr(osadzacz, "model", "") if osadzacz is not None else ""
        wynik = {"model": model, "nowe": 0, "usuniete": 0, "wektorow": 0, "notatek": 0, "przerwane": not model}
        if not model:
            return wynik
        with self.db:
            wynik["usuniete"] = self.db.execute("DELETE FROM wektory WHERE model != ? OR sciezka NOT IN (SELECT sciezka FROM wpisy)",
                                                (model,)).rowcount
        stare = {r[0]: (r[1], r[2], r[3]) for r in self.db.execute("SELECT sciezka, mtime, rozmiar, hash FROM wektory")}
        szukane = [(r[0], r[1], r[2]) for r in self.db.execute("SELECT sciezka, mtime, rozmiar FROM wpisy")
                   if not r[0].startswith(POZA_WYSZUKIWANIEM)]
        wynik["notatek"] = len(szukane)
        zmienione = {s: (m, n) for s, m, n in szukane if stare.get(s, (None, None, None))[:2] != (m, n)}
        kolejka = []
        if zmienione:
            teksty = {s: tekst_wektora(t, st, tr) for s, t, st, tr in
                      self.db.execute("SELECT sciezka, tytul, streszczenie, tresc FROM fts") if s in zmienione}
            with self.db:
                for s, (m, n) in zmienione.items():
                    if s not in teksty:
                        continue
                    h = hashlib.sha256(teksty[s].encode("utf-8")).hexdigest()[:16]
                    if s in stare and stare[s][2] == h:          # dotknięty plik bez zmiany tekstu: bez osadzania
                        self.db.execute("UPDATE wektory SET mtime = ?, rozmiar = ? WHERE sciezka = ?", (m, n, s))
                    else:
                        kolejka.append((s, h, m, n, teksty[s]))
        for i in range(0, len(kolejka), WEKTORY_PACZKA):
            if i and przerwa_s > 0:
                time.sleep(przerwa_s)
            paczka = kolejka[i:i + WEKTORY_PACZKA]
            wektory = osadzacz.osadz([x[4] for x in paczka], czas_s=czas_s)
            if not wektory or len(wektory) != len(paczka):
                wynik["przerwane"] = True
                break
            with self.db:
                for (s, h, m, n, _t), v in zip(paczka, wektory):
                    self.db.execute("INSERT OR REPLACE INTO wektory VALUES (?,?,?,?,?,?)", (s, h, model, wektor_do_bajtow(v), m, n))
            wynik["nowe"] += len(paczka)
        wynik["wektorow"] = self.db.execute("SELECT count(*) FROM wektory WHERE model = ?", (model,)).fetchone()[0]
        return wynik

    def notatki(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM pliki ORDER BY sciezka").fetchall()

    def linki(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM linki").fetchall()

    def graf(self) -> dict:
        we: dict[str, int] = {}
        wy: dict[str, int] = {}
        linki = []
        for l in self.linki():
            if not l["rozwiazany"]:
                continue
            we[l["do_"]] = we.get(l["do_"], 0) + 1
            wy[l["z"]] = wy.get(l["z"], 0) + 1
            linki.append({"z": l["z"], "do": l["do_"], "auto": bool(l["auto"])})
        def w_grafie(s: str) -> bool:                  # kopia repo (docs, zasady agentów, materiały skilli) też jest w grafie
            return not s.startswith(SUROWE) or s.startswith(LUSTRO_REPO + "/")
        wezly = []
        for r in self.notatki():
            if not w_grafie(r["sciezka"]):
                continue
            w = {"id": r["sciezka"], "tytul": r["tytul"], "folder": r["folder"], "typ": r["typ"], "status": r["status"],
                 "hub": bool(r["hub"]), "agent": r["agent"], "zmieniono": r["zmieniono"], "we": we.get(r["sciezka"], 0),
                 "wy": wy.get(r["sciezka"], 0)}
            if r["hub"] or r["typ"] == "tozsamosc" or r["sciezka"].startswith(ARCHIWUM + "/"):
                w.update(self._pola_mozgu(r["sciezka"], bool(r["hub"])))
            wezly.append(w)
        return {"wezly": wezly, "linki": [l for l in linki if w_grafie(l["z"])]}

    def _pola_mozgu(self, rel: str, hub: bool) -> dict:
        """Pola węzła dla Mózgu z pliku (huby, tożsamość, archiwum: kilkadziesiąt plików): `edycja`, `pamiec`, `plik`
        (tożsamość), `podsumowanie` i `streszczono` (hub ze streszczeniem), `zastapiona_przez` i `wycofano` (archiwum)."""
        try:
            fm, tresc = podziel(self.sk.plik(rel).read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            return {}
        out = {k: str(fm[k]) for k in ("edycja", "pamiec", "plik", "zastapiona_przez", "wycofano", "streszczono") if fm.get(k)}
        if hub and (p := podsumowanie_huba(tresc)):
            out["podsumowanie"] = p[:MAX_STRESZCZENIA_HUBA]
        return out


# ------------------------------------------------------------------------------------------------ wektory i aliasy

def _slowa_lista(s: str) -> list[str]:
    return re.findall(r"\w+", bez_ogonkow(s).lower())


def _ma_fraze(slowa: list[str], fraza: list[str]) -> bool:
    """Fraza aliasu w słowach pytania (oba bez ogonków, małymi literami), słowo po słowie. Słowo aliasu od 4 liter
    pasuje też do odmiany: słowo pytania zaczyna się od niego bez dwóch ostatnich liter, ale od co najmniej 4
    („szefowa” → „szefowej”, „właścicielka” → „właścicielce”); krótsze tylko dokładnie („Ola”)."""
    def pasuje(slowo: str, f: str) -> bool:
        return slowo == f or (len(f) >= 4 and slowo.startswith(f[:max(4, len(f) - 2)]))
    n = len(fraza)
    return n > 0 and any(all(pasuje(slowa[i + j], f) for j, f in enumerate(fraza)) for i in range(len(slowa) - n + 1))


def aliasy_notatki(n: Notatka) -> list[str]:
    """Aliasy z frontmattera `aliasy: [właściciel, szef]` (lista albo tekst z przecinkami) jako frazy bez ogonków,
    małymi literami, najwyżej MAX_ALIASOW."""
    surowe = n.fm.get("aliasy") or []
    lista = surowe if isinstance(surowe, list) else str(surowe).split(",")
    out = [" ".join(_slowa_lista(str(a)[:60])) for a in lista]
    return list(dict.fromkeys(a for a in out if a))[:MAX_ALIASOW]


def zdania_zapytania(q: str) -> list[str]:
    """Pytanie do osadzenia: krótkie (do DLUGIE_ZAPYTANIE słów) w całości, dłuższe (treść karty, prompt rutyny)
    zdaniami od MIN_SLOW_ZDANIA słów, najwyżej MAX_ZDAN pierwszych; bez takich zdań całe pytanie."""
    if len(q.split()) <= DLUGIE_ZAPYTANIE:
        return [q]
    czesci = [" ".join(c.split()) for c in re.split(r"(?<=[.!?])\s+|\n+| — ", q)]
    return [c for c in czesci if len(c.split()) >= MIN_SLOW_ZDANIA][:MAX_ZDAN] or [q]


def tekst_wektora(tytul: str, streszczenie: str, tresc: str) -> str:
    """Tekst notatki dla modelu e5 (prefiks „passage: ”): tytuł, streszczenie i początek treści z indeksu FTS."""
    return f"passage: {tytul}. {streszczenie or ''} {(tresc or '')[:MAX_ZNAKOW_WEKTORA]}"


def wektor_do_bajtow(v) -> bytes:
    """float32 little-endian (ten sam układ na każdym systemie i w odpowiedzi usługi)."""
    a = array.array("f", v)
    if sys.byteorder == "big":
        a.byteswap()
    return a.tobytes()


def wektor_z_bajtow(b: bytes) -> array.array:
    a = array.array("f")
    a.frombytes(b[:len(b) - len(b) % 4])
    if sys.byteorder == "big":
        a.byteswap()
    return a


_iloczyn = getattr(math, "sumprod", None) or (lambda a, b: sum(map(operator.mul, a, b)))   # sumprod od Pythona 3.12


class KlientWektorow:
    """Klient usługi wektorów (wiedza/wektory.py: jeden ciepły model e5-small na instalację w venvie narzędzi, docs/
    WIEDZA.md §7). Port, token, id modelu i PID z state/wektory.json (pisze je usługa przy starcie); HTTP tylko na
    127.0.0.1, z tokenem w nagłówku, bez proxy systemu (http.client). Sama biblioteka standardowa: brama Hermesa i
    `jarvo chat` nie mają numpy ani onnxruntime. Brak pliku, martwy PID, odmowa, zły token, inny model albo przekroczony
    `czas_s` = None, a powód w `blad`: wołający zostaje przy słowach (BM25), tura idzie dalej bez błędu."""

    MAX_ODPOWIEDZI = 32 << 20

    def __init__(self, stan: str | Path, czas_s: float = WEKTORY_CZAS_S):
        self.czas_s = czas_s
        self.blad = ""
        try:
            d = json.loads((Path(stan) / WEKTORY_STAN).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        d = d if isinstance(d, dict) else {}
        port, pid = d.get("port"), d.get("pid")
        self.port = port if isinstance(port, int) and 0 < port < 65536 else 0
        self.token = str(d.get("token") or "")
        self.model = str(d.get("model") or "")
        if self.port and isinstance(pid, int) and not pid_zyje(pid):     # resztka po awarii usługi: bez czekania na port
            self.port, self.blad = 0, f"usługa wektorów nie działa (PID {pid})"
        if not self.dostepny:
            self.model = ""
            self.blad = self.blad or "usługa wektorów nie działa (brak state/wektory.json)"

    @property
    def dostepny(self) -> bool:
        return bool(self.port and self.token and self.model)

    def _zapytaj(self, metoda: str, sciezka: str, cialo: dict | None = None, czas_s: float | None = None) -> dict | None:
        if not self.dostepny:
            return None
        polaczenie = http.client.HTTPConnection("127.0.0.1", self.port, timeout=self.czas_s if czas_s is None else czas_s)
        try:
            dane = json.dumps(cialo, ensure_ascii=False).encode("utf-8") if cialo is not None else None
            polaczenie.request(metoda, sciezka, body=dane, headers={"Authorization": f"Bearer {self.token}",
                                                                    "Content-Type": "application/json"})
            odp = polaczenie.getresponse()
            tresc = odp.read(self.MAX_ODPOWIEDZI)
            if odp.status != 200:
                self.blad = f"usługa wektorów: HTTP {odp.status}"
                return None
            wynik = json.loads(tresc.decode("utf-8"))
            return wynik if isinstance(wynik, dict) else None
        except (OSError, http.client.HTTPException, ValueError) as e:
            self.blad = f"usługa wektorów: {type(e).__name__}"           # TimeoutError, ConnectionRefusedError…
            if isinstance(e, (TimeoutError, ConnectionRefusedError)):
                self.port = 0          # usługa wisi albo jej nie ma: ten klient już jej nie pyta (jeden czas na przebieg)
            return None
        finally:
            polaczenie.close()

    def zdrowie(self, czas_s: float | None = None) -> dict | None:
        """{"model", "wymiar", "pid", "od"} działającej usługi albo None."""
        w = self._zapytaj("GET", "/zdrowie", czas_s=czas_s)
        return w if w and w.get("model") == self.model else None

    def osadz(self, teksty: list[str], czas_s: float | None = None) -> list[array.array] | None:
        """Znormalizowane wektory tekstów (z prefiksami e5: „query: ”, „passage: ”) albo None."""
        if not teksty:
            return []
        w = self._zapytaj("POST", "/osadz", {"teksty": list(teksty)}, czas_s)
        if not w or w.get("model") != self.model:
            self.blad = self.blad or "usługa wektorów: inny model niż w state/wektory.json"
            return None
        try:
            wymiar = int(w["wymiar"])
            plaskie = wektor_z_bajtow(base64.b64decode(w["wektory"]))
        except (KeyError, TypeError, ValueError):
            self.blad = "usługa wektorów: zła odpowiedź"
            return None
        if wymiar <= 0 or len(plaskie) != wymiar * len(teksty):
            self.blad = "usługa wektorów: zła odpowiedź"
            return None
        return [plaskie[i * wymiar:(i + 1) * wymiar] for i in range(len(teksty))]


def _slowa_ascii(s: str) -> set[str]:
    return set(re.findall(r"\w+", bez_ogonkow(s).lower()))


def hub_agenta_nazwany(sciezka: str, slowa_pytania: set[str]) -> bool:
    """Pytanie nazywa agenta tego huba (`agenci/jarvo-web/_hub-web`: „web”, „jarvo-web”; ogonki bez znaczenia)."""
    katalog, _, plik = sciezka.rpartition("/_hub-")
    agent = katalog.split("/", 1)[-1]
    nazwy = [_slowa_ascii(plik), _slowa_ascii(agent.removeprefix("jarvo-"))]
    return any(n and n <= slowa_pytania for n in nazwy)


def notatki_przypomnienia(ix: Indeks, q: str, limit: int = 5, wektory=None, silnik: str | None = None, zakres=(),
                          pomin_tozsamosc: bool = False) -> list[dict]:
    """Notatki „może się przydać” przed turą (wtyczka jarvo-wiedza) i w `ocena`: wyszukiwanie (Indeks.szukaj: wektory,
    gdy usługa odpowie w czasie, inaczej słowa) bez orzeczeń (idą osobno), hubów bez streszczenia i hubów agentów
    `agenci/<agent>/_hub-*`, chyba że pytanie nazywa tego agenta (hub ma ogólne słowa o całej dziedzinie, więc bez
    tego zajmuje miejsca przy każdym pytaniu o pracę). Hub ze streszczeniem (`streszczono`, blok STRESZCZENIE) to
    notatka zbiorcza części i wraca jak każda inna. `pomin_tozsamosc`: agent, który ma tożsamość i pamięć ze skarbca
    już w prompcie (Jarvo: SOUL, ZASADY, KRYTYCZNE, MEMORY, USER), nie dostaje ich drugi raz (notatki `typ: tozsamosc`).
    Archiwum nie wraca (Indeks.szukaj). Użyty silnik: `ix.silnik`. `zakres`: agent biznesowy (zakres_marki)."""
    slowa = _slowa_ascii(q)
    out = []
    for t in ix.szukaj(q, limit=limit + 8, wektory=wektory, silnik=silnik, zakres=zakres):
        if t["typ"] == "orzeczenia" or (pomin_tozsamosc and t["typ"] == "tozsamosc" and t["sciezka"].split("#")[0] != MAPA_NOTATKA):
            continue
        if HUB_AGENTA_RE.match(t["sciezka"]):
            if not hub_agenta_nazwany(t["sciezka"], slowa):
                continue
        elif t["typ"] == "hub" and not _ze_streszczeniem(ix.sk, t["sciezka"]):
            continue
        out.append(t)
        if len(out) >= limit:
            break
    return out


def _ze_streszczeniem(sk: "Skarbiec", rel: str) -> bool:
    try:
        return bool(podsumowanie_huba(sk.plik(rel).read_text(encoding="utf-8", errors="replace")))
    except (OSError, ValueError):
        return False


def trafia(sciezka: str, wzor: list[str]) -> bool:
    """Wynik pasuje do wzorca: ta sama ścieżka; sekcja `notatka#Sekcja` pasuje też do wzorca całej notatki (wzorzec
    z sekcją wymaga tej sekcji)."""
    return sciezka in wzor or ("#" in sciezka and sciezka.split("#", 1)[0] in wzor)


def ocena(ix: Indeks, zestaw: list, limit: int = 5, wektory=None, silnik: str | None = None, pomin_tozsamosc: bool = False) -> dict:
    """Pomiar przypomnień na zestawie `[{"pytanie": ..., "wzor": [ścieżki]}]` (zestaw właściciela leży poza repo):
    to samo wyszukiwanie co wtyczka przed turą (odświeżenie indeksu + notatki_przypomnienia, te same wektory i czas
    na nie). hit@k = jakakolwiek ścieżka wzorcowa w pierwszych k, MRR = średnia 1/pozycja pierwszej wzorcowej (0 bez
    trafienia), czas na pytanie w ms, silnik każdego pytania (hybryda, wektory albo slowa, gdy wektorów zabrakło)."""
    if not isinstance(zestaw, list) or not all(isinstance(p, dict) and str(p.get("pytanie") or "").strip() and isinstance(p.get("wzor"), list)
                                               for p in zestaw):
        raise ValueError('zestaw to lista [{"pytanie": "...", "wzor": ["ścieżka notatki", ...]}]')
    ix.odswiez()
    pytania, czasy = [], []
    for p in zestaw:
        wzor = [str(s).strip().strip("/").removesuffix(".md") for s in p["wzor"]]
        wzor += [n for s in wzor if not ix.sk.istnieje(s) and (n := ix.sk.przekierowanie(s)) and n not in wzor]   # po archiwizacji
        start = time.perf_counter()
        ix.odswiez()
        sciezki = [t["sciezka"] for t in notatki_przypomnienia(ix, str(p["pytanie"]), limit=limit, wektory=wektory, silnik=silnik,
                                                               pomin_tozsamosc=pomin_tozsamosc)]
        ms = round((time.perf_counter() - start) * 1000, 1)
        pozycja = next((i + 1 for i, s in enumerate(sciezki) if trafia(s, wzor)), 0)
        czasy.append(ms)
        pytania.append({"pytanie": p["pytanie"], "wzor": wzor, "wyniki": sciezki, "pozycja": pozycja, "ms": ms,
                        "silnik": ix.silnik})
    n = len(pytania)
    trafione = sum(1 for p in pytania if p["pozycja"])
    posortowane = sorted(czasy)
    mediana = (posortowane[(n - 1) // 2] + posortowane[n // 2]) / 2 if n else 0.0
    silniki: dict[str, int] = {}
    for p in pytania:
        silniki[p["silnik"]] = silniki.get(p["silnik"], 0) + 1
    return {"pytan": n, "k": limit, "trafione": trafione, "hit_at_k": round(trafione / n, 3) if n else 0.0,
            "mrr": round(sum(1 / p["pozycja"] for p in pytania if p["pozycja"]) / n, 3) if n else 0.0,
            "ms_mediana": round(mediana, 1), "ms_p95": posortowane[min(n - 1, round(0.95 * (n - 1)))] if n else 0.0,
            "ms_max": max(czasy, default=0.0), "silniki": silniki, "pytania": pytania}


# ------------------------------------------------------------------------------------------------ księga błędów

_ZNAKI_KOMUNIKATU = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "“": '"', "”": '"', "„": '"', "«": '"', "»": '"'})


def norm_komunikatu(s: str) -> str:
    """Tekst do porównania z sygnaturą: typograficzne apostrofy i cudzysłowy jak proste, białe znaki pojedynczo, małe
    litery. Ogonki zostają: „zajęte” na stronie to nie kod odmowy `zajete`."""
    return " ".join(str(s or "").translate(_ZNAKI_KOMUNIKATU).split()).casefold()


def wzorzec_sygnatury(s: str) -> re.Pattern | None:
    """Sygnatura notatki księgi błędów: `/…/` = wyrażenie regularne, inne = dosłowny fragment komunikatu; oba
    sprawdzane na tekście po `norm_komunikatu` (małe litery, pojedyncze spacje). None = pusta albo błędne wyrażenie."""
    s = str(s or "").strip()
    if len(s) > 2 and s[0] == s[-1] == "/":
        try:
            return re.compile(s[1:-1], re.I)
        except re.error:
            return None
    s = norm_komunikatu(s)
    return re.compile(re.escape(s)) if s else None


def _lista_fm(v) -> list[str]:
    lista = v if isinstance(v, list) else [v] if isinstance(v, str) else []
    return [str(x).strip() for x in lista if str(x).strip()]


def sygnatury(fm: dict) -> list[str]:
    """Pole `sygnatury:` notatki albo szkicu (lista albo jeden tekst), najwyżej MAX_SYGNATUR po MAX_ZNAKOW_SYGNATURY."""
    return [s[:MAX_ZNAKOW_SYGNATURY] for s in _lista_fm(fm.get("sygnatury"))][:MAX_SYGNATUR]


def wystapienia(fm: dict) -> int:
    try:
        return max(0, int(str(fm.get("wystapienia") or 0)))
    except ValueError:
        return 0


def jak_poprawnie(tresc: str) -> str:
    """Akapit „Jak poprawnie: …” notatki błędu w jednej linii, bez pogrubień i z etykietami zamiast linków (kod w `…`
    zostaje, bo to nazwy narzędzi i poleceń); pusto, gdy go nie ma."""
    m = JAK_POPRAWNIE_RE.search(tresc or "")
    if not m:
        return ""
    t = LINK_RE.sub(lambda l: (l.group(3) or l.group(1)).strip(), m.group(1))
    return " ".join(t.replace("**", "").split())


def licznik_bledow(stan: str | Path) -> dict:
    """state/bledy-licznik.json: notatka → {"przypomnien": n, "ostatnio": "RRRR-MM-DD GG:MM"}; {} bez pliku."""
    try:
        d = json.loads((Path(stan) / LICZNIK_BLEDOW).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def wpisy_ksiegi(sk: Skarbiec) -> list[dict]:
    """Notatki księgi błędów do dopasowania wyników narzędzi (bez huba, bez `przestarzala`, z choć jedną poprawną
    sygnaturą): ścieżka, tytuł, krok „jak poprawnie” (bez niego streszczenie), wystąpienia, wzorce, narzędzia.
    Same pliki, bez indeksu: wtyczka czyta to w milisekundach."""
    out = []
    for p in sorted((sk.root / KSIEGA).glob("*.md")):
        if p.stem.startswith("_hub-"):
            continue
        rel = sk.rel(p)
        try:
            n = sk.wczytaj(rel)
        except (OSError, ValueError):
            continue
        if str(n.fm.get("status") or "") == "przestarzala":
            continue
        wzorce = [w for w in (wzorzec_sygnatury(s) for s in sygnatury(n.fm)) if w]
        if wzorce:
            out.append({"sciezka": rel, "tytul": n.tytul, "jak": jak_poprawnie(n.tresc) or n.streszczenie,
                        "wystapienia": wystapienia(n.fm), "wzorce": wzorce, "narzedzia": _lista_fm(n.fm.get("narzedzia"))})
    return out


def lint_bledu(n: Notatka) -> tuple[list[str], list[str]]:
    """(błędy, ostrzeżenia) notatki księgi błędów: błędne wyrażenie w sygnaturze i nieliczbowe `wystapienia` to błąd
    (wtyczka by ich nie użyła), brak sygnatur, kroku „Jak poprawnie” albo typu `blad` to ostrzeżenie."""
    bledy, ostrz = [], []
    syg = sygnatury(n.fm)
    bledy += [f"błędne wyrażenie w sygnaturze `{s[:60]}`" for s in syg if wzorzec_sygnatury(s) is None]
    v = n.fm.get("wystapienia")
    if v not in (None, "") and not str(v).isdigit():
        bledy.append(f"`wystapienia: {v}` nie jest liczbą")
    if not syg:
        ostrz.append("błąd bez sygnatur (wtyczka nie przypomni go pod wynikiem narzędzia)")
    if not jak_poprawnie(n.tresc):
        ostrz.append("błąd bez akapitu „Jak poprawnie:”")
    if n.typ != "blad":
        ostrz.append(f"w księdze błędów typ `{n.typ}` zamiast `blad`")
    return bledy, ostrz


def _nietknieta_ze_starego_zasiewu(obecna: str, nowa: str) -> bool:
    """Notatka zasiana przed zapisem skrótów (state z samą listą): nietknięta, gdy kompilacja jej nie zmieniała
    (`zmieniono` równe `utworzono`) i ma to samo źródło i wystąpienia co wersja z repo (kompilacja dopisuje źródło
    i liczy wystąpienia)."""
    fm, _ = podziel(obecna)
    fm_nowa, _ = podziel(nowa)
    return (bool(fm.get("utworzono")) and fm.get("zmieniono") == fm.get("utworzono")
            and fm.get("zrodlo") == fm_nowa.get("zrodlo") and fm.get("wystapienia") == fm_nowa.get("wystapienia"))


def zasiej_bledy(sk: Skarbiec, katalog: Path | None) -> int:
    """Notatki księgi błędów z repo (`wiedza/bledy/*.md`) do `bledy/`. state/bledy-zasiane.json pamięta skrót
    zasianej treści każdej notatki: nową notatkę z repo kładzie; notatkę, którą skarbiec już miał przed zasiewem,
    zostawia na zawsze (skrót pusty); zasianą, a nietkniętą od zasiewu (ten sam skrót) wymienia na nowszą wersję
    z repo (np. nowe sygnatury); zmienioną przez kompilację albo człowieka zostawia; usunięta nie wraca.
    Zwraca liczbę nowych i wymienionych notatek."""
    if not katalog or not katalog.is_dir():
        return 0
    plik = sk.stan / ZASIANE_BLEDY
    try:
        dane = json.loads(plik.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dane = {}
    zasiane: dict = dict.fromkeys(dane) if isinstance(dane, list) else dane if isinstance(dane, dict) else {}
    skrot = lambda t: hashlib.sha256(t.encode("utf-8")).hexdigest()
    zmienione = 0
    for p in sorted(katalog.glob("*.md")):
        rel = f"{KSIEGA}/{unicodedata.normalize('NFC', p.stem)}"
        nowa = p.read_text(encoding="utf-8")
        if rel not in zasiane:
            if sk.istnieje(rel):
                zasiane[rel] = ""                      # notatka skarbca o tej nazwie: nie nasza, nie ruszamy
                continue
        else:
            zapisany = zasiane[rel]
            if zapisany == "" or zapisany == skrot(nowa) or not sk.istnieje(rel):
                continue
            obecna = sk.plik(rel).read_text(encoding="utf-8")
            if obecna == nowa:                         # stary zasiew tej samej wersji: tylko skrót do stanu
                zasiane[rel] = skrot(nowa)
                continue
            if not (skrot(obecna) == zapisany if zapisany else _nietknieta_ze_starego_zasiewu(obecna, nowa)):
                continue                               # zmieniona po zasiewie (kompilacja, człowiek): zostaje
        sk.zapisz_plik(rel, nowa)
        zasiane[rel] = skrot(nowa)
        zmienione += 1
    sk.stan.mkdir(parents=True, exist_ok=True)
    tresc = json.dumps(dict(sorted(zasiane.items())), ensure_ascii=False, indent=1) + "\n"
    if not plik.is_file() or plik.read_text(encoding="utf-8") != tresc:
        plik.write_text(tresc, encoding="utf-8", newline="\n")
    return zmienione


# ------------------------------------------------------------------------------------------------ INDEX.md i listy hubów

def _klucz_notatki(r) -> tuple:
    """Kolejność notatek w INDEX-ie i listach hubów: huby, tożsamość w stałej kolejności (KOLEJNOSC_TOZSAMOSCI), reszta po ścieżce."""
    s = r["sciezka"]
    return (not r["hub"], KOLEJNOSC_TOZSAMOSCI.index(s) if s in KOLEJNOSC_TOZSAMOSCI else len(KOLEJNOSC_TOZSAMOSCI), s)


def zbuduj_index(sk: Skarbiec, ix: Indeks) -> int:
    """INDEX.md z plików (deterministycznie): każda notatka jedną linią, sekcje po folderach w kolejności FOLDERY_SKARBCA;
    źródła, skrzynka i archiwum tylko liczbą."""
    grupy: dict[str, list] = {}
    for r in ix.notatki():
        grupy.setdefault(r["folder"], []).append(r)
    linie = ["# Indeks skarbca", "", f"Generowany przez `wiedza.py indeksuj` ({dzis()}). Jedna linia = jedna notatka: link · streszczenie · typ · zmieniono.", ""]
    n = 0
    kolejnosc = list(FOLDERY_SKARBCA)
    for folder in sorted(grupy, key=lambda f: (kolejnosc.index(f) if f in kolejnosc else len(kolejnosc), f)):
        wiersze = grupy[folder]
        nazwa = FOLDERY_SKARBCA[folder]["tytul"] if folder in FOLDERY_SKARBCA else folder
        if f"{folder}/" in POZA_WYSZUKIWANIEM:
            linie += [f"## {nazwa} ({len(wiersze)} plików, poza wyszukiwaniem)", ""]
            continue
        linie += [f"## {nazwa}", ""]
        skille = [r for r in wiersze if r["typ"] == "skill"]
        if skille:
            linie.append(f"- skille floty: {len(skille)} notatek w `{SKILLE}/` (węzły grafu; szukanie z `folder=fleet`)")
        for r in sorted((r for r in wiersze if r["typ"] != "skill"), key=_klucz_notatki):
            s = (r["streszczenie"] or "").replace("\n", " ")
            s = s[:120].rstrip() + ("…" if len(s) > 120 else "")
            czesci = [f"[[{r['sciezka']}|{r['tytul']}]]"] + ([s] if s else []) + [r["typ"] or "?"] + ([r["zmieniono"]] if r["zmieniono"] else [])
            linie.append("- " + " · ".join(czesci))
            n += 1
        linie.append("")
    sk.zapisz_plik("INDEX", "\n".join(linie).rstrip("\n") + "\n")
    return n


def _wiersz_bledu(sk: Skarbiec, r: dict, licznik: dict) -> str:
    """Wiersz huba księgi błędów: link, wystąpienia z notatki (zgłoszenia i zasiew) i przypomnienia wtyczki ze state/."""
    try:
        n = wystapienia(sk.wczytaj(r["sciezka"]).fm)
    except (OSError, ValueError):
        n = 0
    lic = licznik.get(r["sciezka"]) if isinstance(licznik.get(r["sciezka"]), dict) else {}
    przyp = f" · przypomniano: {lic.get('przypomnien', 0)} (ostatnio {lic.get('ostatnio', '?')})" if lic.get("przypomnien") else ""
    return f"- [[{r['sciezka']}|{r['tytul']}]] · wystąpień: {n}{przyp}"


def odswiez_listy_hubow(sk: Skarbiec, ix: Indeks) -> int:
    """Blok `lista` w hubie folderu (i w hubie agenta albo marki agenta biznesowego, `brands/<marka>/_hub-<marka>`):
    linki do wszystkich notatek folderu, 0 tokenów. Hub księgi błędów ma przy notatce liczniki zamiast streszczenia,
    hub archiwum wymienia też huby zarchiwizowanych agentów, hub Jarva tożsamość w stałej kolejności."""
    wszystkie = sorted(ix.notatki(), key=_klucz_notatki)
    notatki = [r for r in wszystkie if not r["hub"]]
    ile = 0
    for folder, (hub, _t) in HUBY.items():
        if folder == "":
            continue
        rel = f"{folder}/{hub}"
        if not sk.istnieje(rel):
            continue
        if folder == "agenci":
            wiersze = [f"- [[{r['sciezka']}|{r['tytul']}]]" for r in ix.notatki() if r["hub"] and r["sciezka"].startswith("agenci/") and r["sciezka"].count("/") == 2]
        elif folder == KSIEGA:
            licznik = licznik_bledow(sk.stan)
            wiersze = [_wiersz_bledu(sk, r, licznik) for r in notatki if r["sciezka"].startswith(folder + "/")]
        else:
            zrodlo = [r for r in wszystkie if r["sciezka"] != rel] if folder == ARCHIWUM else notatki
            wiersze = [f"- [[{r['sciezka']}|{r['tytul']}]]" + (f" · {r['streszczenie'][:90]}" if r["streszczenie"] else "")
                       for r in zrodlo if r["sciezka"].startswith(folder + "/")]
        ile += _wpisz_liste(sk, rel, wiersze)
    for r in ix.notatki():
        if r["hub"] and r["sciezka"].startswith(("agenci/", "brands/")) and r["sciezka"].count("/") == 2:
            katalog = r["sciezka"].rsplit("/", 1)[0] + "/"
            wiersze = [f"- [[{n['sciezka']}|{n['tytul']}]]" + (f" · {n['streszczenie'][:90]}" if n["streszczenie"] else "")
                       for n in notatki if n["sciezka"].startswith(katalog)]
            ile += _wpisz_liste(sk, r["sciezka"], wiersze)
    return ile


def _wpisz_liste(sk: Skarbiec, rel: str, wiersze: list[str]) -> int:
    """Blok `lista` huba; zmieniona lista = `zmieniono: dziś` huba (20.11: hub „Ty” pokazywał 7.11, choć jego notatki się
    zmieniały)."""
    p = sk.plik(rel)
    stary = p.read_text(encoding="utf-8")
    tresc = "## Notatki (lista automatyczna)\n" + ("\n".join(wiersze) if wiersze else "_jeszcze pusto_")
    nowy = zastap_blok(stary, "lista", tresc)
    if nowy != stary:
        fm, body = podziel(nowy)
        if fm.get("zmieniono") and str(fm["zmieniono"]) != dzis():
            fm["zmieniono"] = dzis()
            nowy = sklej(fm, body)
        sk.zapisz_plik(rel, nowy)
        return 1
    return 0


# ------------------------------------------------------------------------------------------------ zasiew

def _hub_frontmatter(typ: str, zrodlo: str = "wiedza.py zasiej", **extra) -> dict:
    fm = {"typ": typ, "tagi": ["hub"], "utworzono": dzis(), "zmieniono": dzis(), "status": "aktualna", "zrodlo": zrodlo}
    fm.update(extra)
    return fm


def hub_agenta(a: dict) -> tuple[str, str]:
    """(ścieżka huba agenta, nazwa pliku orzeczeń) z wpisu fleet.json."""
    krotki = nazwa_pliku(a.get("short") or a["name"].replace("jarvo-", "") or a["name"]).replace(" ", "-")
    return f"agenci/{a['name']}/_hub-{krotki}", krotki


def lustro(rel_repo: str) -> str:
    """Ścieżka pliku repo w skarbcu (kopia z `zasiej --repo`), bez `.md`: cel linku."""
    return f"{LUSTRO_REPO}/{rel_repo[:-3] if rel_repo.endswith('.md') else rel_repo}"


def notatka_skilla(s: dict, agenci: list[tuple[str, str, str]], znane: set[str], w_lustrze: set[str] | None = None) -> str:
    """Notatka-węzeł skilla floty: opis, kto go ma, powiązane skille i skrypty (linki robi zasiew, nie autor);
    materiały skilla (references) linkują do ich kopii w `zrodla/jarvo-repo/`, gdy zasiew ją położył."""
    powiazane = [n for n in dict.fromkeys([*s.get("related", []), *s.get("mentions", [])]) if n in znane and n != s["name"]]
    obce = [n for n in s.get("related", []) if n not in znane]
    wiersze = ["- agent: " + ", ".join(f"[[{hub}|{nazwa}]]" for hub, nazwa, _a in agenci)]
    wersja = " · ".join(x for x in (f"wersja {s['version']}" if s.get("version") else "",
                                    f"przejrzany {s['reviewed']}" if s.get("reviewed") else "") if x)
    plik = f"plik w repo: `{s['path']}`" if s.get("path") else ""
    if wersja or plik:
        wiersze.append("- " + " · ".join(x for x in (wersja, plik) if x))
    if s.get("scripts"):
        wiersze.append("- skrypty: " + ", ".join(f"`{x}`" for x in s["scripts"]))
    if powiazane or obce:
        wiersze.append("- powiązane skille: " + ", ".join([f"[[{SKILLE}/{n}|{n}]]" for n in powiazane] + [f"`{n}`" for n in obce]))
    if s.get("sections"):
        wiersze.append("- sekcje: " + " · ".join(s["sections"]))
    katalog = s.get("path", "").rsplit("/", 1)[0]
    materialy = [r for r in s.get("references") or [] if lustro(f"{katalog}/references/{r}") in (w_lustrze or set())]
    if materialy:
        wiersze.append("- materiały (references): " + ", ".join(f"[[{lustro(f'{katalog}/references/{r}')}|{r}]]" for r in materialy))
    opis = s.get("description") or "(skill bez opisu)"
    return (f"# {s['name']}\n\n**{opis}**\n\n"
            + zastap_blok("", "skill", "## Z repo (SKILL.md i fleet.yaml)\n" + "\n".join(wiersze)).strip() + "\n")


def zasiej_skille(sk: Skarbiec, skille: dict[str, tuple[dict, list]], w_lustrze: set[str] | None = None) -> int:
    """`fleet/skille/<nazwa>.md` dla każdego skilla floty (własnego i wspólnego): węzeł grafu połączony z hubami agentów,
    powiązanymi skillami i skryptami. Plik zmienia się tylko, gdy zmienił się skill; skill usunięty z floty znika."""
    katalog = sk.root / SKILLE
    katalog.mkdir(parents=True, exist_ok=True)
    zmienione = 0
    for nazwa, (s, agenci) in sorted(skille.items()):
        rel = f"{SKILLE}/{nazwa}"
        tresc = notatka_skilla(s, agenci, set(skille), w_lustrze)
        stare_fm, stara = podziel(sk.plik(rel).read_text(encoding="utf-8")) if sk.istnieje(rel) else ({}, None)
        if stara is not None and stara.strip() == tresc.strip():
            continue
        fm = _hub_frontmatter("skill", s.get("path") or "fleet.yaml", status="generowane", tagi=["skill"],
                              utworzono=str(stare_fm.get("utworzono") or dzis()))
        if len(agenci) == 1:
            fm["agent"] = agenci[0][2]
        sk.zapisz_plik(rel, sklej(fm, tresc))
        zmienione += 1
    for stary in katalog.glob("*.md"):                 # skill usunięty z floty nie zostaje w grafie
        if stary.stem not in skille:
            stary.unlink()
            zmienione += 1
    return zmienione


def zasiej_lustro(sk: Skarbiec, repo: Path) -> tuple[int, set[str]]:
    """Pliki profili z buildu (`wiedza/repo`: SOUL, README, CHANGELOG, rubryka, materiały skilli, spis źródeł) do
    `zrodla/jarvo-repo/` w układzie repo. Plik zmieniony w repo jest nadpisywany, usunięty znika."""
    cel = sk.root / LUSTRO_REPO
    nowe: set[str] = set()
    zmienione = 0
    for src in sorted(repo.rglob("*.md")):
        rel = src.relative_to(repo).as_posix()
        if rel.split("/", 1)[0] not in LUSTRO_KATALOGI:
            continue
        nowe.add(rel)
        dst = cel / rel
        dane = src.read_bytes()
        if not dst.exists() or dst.read_bytes() != dane:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(dane)
            zmienione += 1
    for katalog in LUSTRO_KATALOGI:
        for stary in sorted((cel / katalog).rglob("*.md")) if (cel / katalog).is_dir() else []:
            if stary.relative_to(cel).as_posix() not in nowe:
                stary.unlink()
                zmienione += 1
        for d in sorted((cel / katalog).rglob("*"), reverse=True) if (cel / katalog).is_dir() else []:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
    return zmienione, {lustro(r) for r in nowe}


def hub_marki(marka: str) -> str:
    """Hub marki agenta biznesowego: `brands/<marka>/_hub-<marka>` (lista notatek marki, cel linku notatek z kompilacji)."""
    return f"brands/{marka}/_hub-{marka}"


def zasiej_marke(sk: Skarbiec, marka: str, a: dict, hub_agenta_rel: str) -> None:
    """Agent biznesowy (fleet.yaml `marka`): hub marki i plik orzeczeń marki, gdy ich nie ma. Brand kit (`BRAND.md`
    z `brand-z-url`) może jeszcze nie istnieć; kompilacja i tak kładzie tu notatki ze szkiców tego agenta."""
    hub, orz = hub_marki(marka), f"orzeczenia/marki/{marka}"
    if not sk.istnieje(hub):
        sk.zapisz_plik(hub, sklej(_hub_frontmatter("hub", "fleet.yaml", agent=a["name"]),
                                  f"# Marka {marka}\n\n**Wiedza marki `{marka}`: brand kit i notatki z pracy agenta `{a['name']}`; "
                                  f"kompilacja kładzie tu notatki z jego szkiców.**\n\n## Powiązane\n- hub: [[brands/_hub-marki|Marki]]\n"
                                  f"- [[{hub_agenta_rel}|{a.get('short') or a['name']}]]\n- [[{orz}|Orzeczenia marki {marka}]]\n"))
    if not sk.istnieje(orz):
        sk.zapisz_plik(orz, sklej(_hub_frontmatter("orzeczenia", "człowiek"),
                                  f"# Orzeczenia: {marka}\n\n**Korekty od użytkownika dla marki `{marka}`, jedna datowana linia każda.**\n\n"
                                  f"## Powiązane\n- hub: [[orzeczenia/_hub-orzeczenia|Orzeczenia]]\n- [[{hub}|Marka {marka}]]\n\n## Linie\n"))


# ------------------------------------------------------------------------------------------------ pamięć Hermesa

class BladPamieci(ValueError):
    """Zapis pamięci odrzucony: `kod` (zmieniona, limit, pusty_wpis, zly_wpis, zajeta), status HTTP i dane dla panelu."""

    def __init__(self, kod: str, opis: str, status: int = 400, **dane):
        super().__init__(opis)
        self.kod, self.status, self.dane = kod, status, dane

    def jako_json(self) -> dict:
        return {"blad": {"kod": self.kod, "opis": str(self), **self.dane}}


def plik_pamieci(profil: str | Path, cel: str) -> Path:
    """memories/MEMORY.md (`memory`) albo memories/USER.md (`user`) profilu Hermesa (tools/memory_tool.get_memory_dir)."""
    if cel not in PLIKI_PAMIECI:
        raise ValueError(f"nieznana pamięć `{cel}` (memory albo user)")
    return Path(profil) / "memories" / PLIKI_PAMIECI[cel]


def wpisy_z_pamieci(surowy: str) -> list[str]:
    """Wpisy pliku pamięci jak MemoryStore._parse_entries Hermesa: podział po całym separatorze, obcięte, bez pustych."""
    return [e for e in (x.strip() for x in surowy.split(SEPARATOR_PAMIECI)) if e]


def czytaj_pamiec(plik: Path) -> dict:
    """{"wpisy", "wersja", "zmieniono", "uzyte"}: wpisy jak po wczytaniu w Hermesie (UTF-8 z BOM-em albo bez, bez
    powtórzeń), wersja = sha256 bajtów pliku (brak pliku = skrót pustego), zmieniono = czas pliku ISO (albo ""), uzyte =
    znaki wpisów ze separatorami (tak liczy limit Hermes). Plik, którego nie da się przeczytać jako UTF-8: ValueError
    (Hermes też odmawia wtedy zapisu, żeby nie skasować pamięci)."""
    try:
        dane, mtime = plik.read_bytes(), plik.stat().st_mtime
    except FileNotFoundError:
        dane, mtime = b"", 0.0
    except OSError as e:
        raise ValueError(f"nie czytam {plik.name}: {e.strerror or e}") from e
    try:
        surowy = dane.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise ValueError(f"{plik.name} nie jest poprawnym UTF-8 (Hermes też go nie zapisze)") from e
    wpisy = list(dict.fromkeys(wpisy_z_pamieci(surowy)))
    return {"wpisy": wpisy, "wersja": hashlib.sha256(dane).hexdigest(), "uzyte": len(SEPARATOR_PAMIECI.join(wpisy)),
            "zmieniono": dt.datetime.fromtimestamp(mtime).astimezone().isoformat(timespec="seconds") if mtime else ""}


def limity_pamieci(profil: str | Path) -> dict[str, int]:
    """`memory.memory_char_limit` i `memory.user_char_limit` z config.yaml profilu (sekcja `memory:` czytana bez PyYAML,
    jak w Hermesie: tools/memory_tool.load_on_disk_store), bez nich domyślne Hermesa (LIMITY_PAMIECI)."""
    out = dict(LIMITY_PAMIECI)
    try:
        tekst = (Path(profil) / "config.yaml").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    m = re.search(r"^memory:[ \t]*(?:#.*)?\n((?:[ \t]+.*(?:\n|$)|[ \t]*\n)*)", tekst, re.M)
    for cel, klucz in (("memory", "memory_char_limit"), ("user", "user_char_limit")):
        k = re.search(rf"^[ \t]+{klucz}:[ \t]*['\"]?(\d+)", m.group(1), re.M) if m else None
        if k and int(k.group(1)) > 0:
            out[cel] = int(k.group(1))
    return out


def _zwolnij_zamek_pliku(f) -> None:
    if WINDOWS:
        import msvcrt
        with contextlib.suppress(OSError):
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    # POSIX: zamknięcie pliku zwalnia flock


def _czekaj_na_zamek(f, czekaj_s: float) -> bool:
    """Blokada systemu na otwartym pliku z czekaniem do `czekaj_s`; system plików bez blokad = jak wzięta."""
    koniec = time.monotonic() + czekaj_s
    wynik = _sprobuj_zamek(f)
    while wynik is False and time.monotonic() < koniec:
        time.sleep(0.05)
        wynik = _sprobuj_zamek(f)
    return wynik is not False


@contextlib.contextmanager
def zamek_pliku(p: Path, czekaj_s: float = 5.0):
    """Krótka blokada systemu na pliku-zamku (stan lustra pamięci: hak w bramie, panel i zasiew piszą ten sam stan);
    daje True (wzięta) albo False (zajęta po `czekaj_s`)."""
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a+b") as f:
        wzieta = _czekaj_na_zamek(f, czekaj_s)
        try:
            yield wzieta
        finally:
            if wzieta:
                _zwolnij_zamek_pliku(f)


@contextlib.contextmanager
def zamek_pamieci(plik: Path, czekaj_s: float = 10.0):
    """Ta sama blokada co narzędzie memory Hermesa (MemoryStore._file_lock): osobny plik `<plik>.lock` (O_NOFOLLOW,
    0600), flock LOCK_EX na POSIX, msvcrt na pierwszym bajcie na Windows; Hermes czeka bez końca, tu najwyżej
    `czekaj_s`, potem BladPamieci `zajeta` (503)."""
    plik.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(plik.with_name(plik.name + ".lock"), os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        f = os.fdopen(fd, "r+", encoding="utf-8")
    except Exception:
        os.close(fd)
        raise
    with f:
        if not _czekaj_na_zamek(f, czekaj_s):
            raise BladPamieci("zajeta", f"{plik.name} zapisuje teraz Jarvo; spróbuj za chwilę", 503)
        try:
            yield
        finally:
            _zwolnij_zamek_pliku(f)


def _zapisz_jak_hermes(plik: Path, tresc: str) -> None:
    """Zapis atomowy jak utils.atomic_write_text Hermesa (MemoryStore._write_file): plik tymczasowy `.mem_*.tmp` obok
    (mkstemp, 0600), tekst w UTF-8 z domyślnymi końcami linii, fsync, zamiana na miejscu celu dowiązania. Nowy plik
    zostaje 0600 (Hermes daje mu maskę procesu; istniejący i tak ma 0600 z mkstemp)."""
    cel = Path(os.path.realpath(plik))
    fd, tmp = tempfile.mkstemp(dir=str(cel.parent), prefix=".mem_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(tresc)
            f.flush()
            os.fsync(f.fileno())
        zamien_plik(tmp, cel)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def sprawdz_wpisy(wpisy, limit: int, skaner=None) -> list[str]:
    """Wpisy z panelu gotowe do zapisu (obcięte jak w Hermesie) albo BladPamieci: `pusty_wpis`, `zly_wpis` (nie tekst,
    powtórzony, z sekretem, rozbijający separator „§” albo odrzucony przez skaner zagrożeń Hermesa `skaner(tekst)` →
    komunikat), `limit` (znaki wpisów ze separatorami ponad limit profilu)."""
    if not isinstance(wpisy, list):
        raise BladPamieci("zly_wpis", "`wpisy` to lista tekstów")
    czyste: list[str] = []
    for i, w in enumerate(wpisy):
        if not isinstance(w, str):
            raise BladPamieci("zly_wpis", f"wpis {i + 1} nie jest tekstem", indeks=i)
        w = w.replace("\r\n", "\n").strip()
        if not w:
            raise BladPamieci("pusty_wpis", f"wpis {i + 1} jest pusty (usuń go albo wpisz treść)", indeks=i)
        if wpisy_z_pamieci(f"a{SEPARATOR_PAMIECI}{w}{SEPARATOR_PAMIECI}b") != ["a", w, "b"]:
            raise BladPamieci("zly_wpis", f"wpis {i + 1} ma znak „§” w osobnej linii (to separator wpisów)", indeks=i)
        if w in czyste:
            raise BladPamieci("zly_wpis", f"wpis {i + 1} powtarza wpis {czyste.index(w) + 1}", indeks=i)
        if (sekret := zawiera_sekret(w)):
            raise BladPamieci("zly_wpis", f"wpis {i + 1} zawiera sekret ({sekret}); sekrety tylko w sejfie", indeks=i)
        if skaner is not None and (powod := skaner(w)):
            raise BladPamieci("zly_wpis", f"wpis {i + 1}: {powod}", indeks=i)
        czyste.append(w)
    uzyte = len(SEPARATOR_PAMIECI.join(czyste))
    if uzyte > limit:
        raise BladPamieci("limit", f"{uzyte} znaków z {limit}: skróć albo usuń wpisy", limit=limit, uzyte=uzyte)
    return czyste


def stan_pamieci(profil: str | Path, cel: str) -> dict:
    """Jedna pamięć dla panelu (GET /pamiec): wpisy, limit, uzyte, wersja, zmieniono, plik (względem danych), notatka."""
    p = czytaj_pamiec(plik_pamieci(profil, cel))
    return {**p, "limit": limity_pamieci(profil)[cel], "plik": f"profiles/{Path(profil).name}/memories/{PLIKI_PAMIECI[cel]}",
            "notatka": NOTATKI_PAMIECI[cel][0]}


def zapisz_pamiec(profil: str | Path, cel: str, wpisy, wersja: str, skaner=None) -> dict:
    """Zapis całej listy wpisów pamięci (Mózg, PUT /pamiec) tym samym formatem i blokadą co narzędzie memory Hermesa:
    wpisy połączone ENTRY_DELIMITER („\\n§\\n”), bez znaku na końcu, UTF-8, atomowo pod `<plik>.lock`. `wersja` (sha256
    z odczytu) inna niż teraz na dysku = BladPamieci `zmieniona` (409) z aktualnym stanem; nic nie jest zapisane.
    Ta sama treść = bez zapisu. Zwraca stan_pamieci po zapisie."""
    plik = plik_pamieci(profil, cel)
    czyste = sprawdz_wpisy(wpisy, limity_pamieci(profil)[cel], skaner)
    with zamek_pamieci(plik):
        teraz = czytaj_pamiec(plik)
        if str(wersja or "") != teraz["wersja"]:
            raise BladPamieci("zmieniona", "pamięć zmieniła się w międzyczasie (Jarvo albo inne okno); wczytaj ponownie",
                              409, aktualna=stan_pamieci(profil, cel))
        tresc = SEPARATOR_PAMIECI.join(czyste)
        if plik.read_bytes() != tresc.encode("utf-8") if plik.exists() else True:
            _zapisz_jak_hermes(plik, tresc)
    return stan_pamieci(profil, cel)


def _liczba(n: int, jeden: str, kilka: str, wiele: str) -> str:
    return f"{n} " + (jeden if n == 1 else kilka if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else wiele)


def _zapisz_tozsamosc(sk: "Skarbiec", rel: str, body: str, zmieniono: str, plik: str, edycja: str, pamiec: str = "",
                      sekcje: bool = False) -> bool:
    """Notatka tożsamości (`typ: tozsamosc`, generowana): frontmatter z kontraktu Mózgu (plik źródła, edycja: repo albo
    pamiec), zapis tylko przy zmianie treści. True = zapisana."""
    zmieniono = zmieniono if DATA_RE.match(zmieniono or "") else dzis()
    stary = sk.plik(rel).read_text(encoding="utf-8", errors="replace") if sk.istnieje(rel) else ""
    stare_fm = podziel(stary)[0] if stary else {}
    utworzono = str(stare_fm.get("utworzono") or "")
    fm = {"typ": "tozsamosc", "tagi": ["tozsamosc"], "utworzono": utworzono if DATA_RE.match(utworzono) else min(zmieniono, dzis()),
          "zmieniono": zmieniono, "status": "aktualna", "zrodlo": "wiedza.py zasiej", "plik": plik, "edycja": edycja}
    if pamiec:
        fm["pamiec"] = pamiec
    if sekcje:
        fm["sekcje"] = True
    tekst = sklej(fm, body)
    if tekst == stary:
        return False
    zapewnij_hub(sk, TOZSAMOSC)
    sk.zapisz_plik(rel, tekst)
    return True


def zapewnij_hub(sk: "Skarbiec", folder: str) -> bool:
    """Hub folderu z FOLDERY_SKARBCA, gdy go nie ma (część ręczna pisana raz; bloki GEN odświeża zasiew). True = nowy."""
    if folder not in HUBY:
        return False
    hub, tytul = HUBY[folder]
    rel = f"{folder}/{hub}" if folder else hub
    if sk.istnieje(rel):
        return False
    body = (f"# {tytul}\n\n**{OPISY_FOLDEROW.get(folder) or FOLDERY_SKARBCA[''].get('opis')}**\n\n## Powiązane\n"
            + ("- hub: [[_hub-skarbiec|Skarbiec wiedzy]]\n" if folder else ""))
    sk.zapisz_plik(rel, sklej(_hub_frontmatter("hub"), body))
    return True


def zapisz_notatke_pamieci(sk: "Skarbiec", profil: str | Path, cel: str, p: dict | None = None) -> bool:
    """Lustro pliku pamięci Jarva w skarbcu: `jarvo/pamięć jarva` (MEMORY.md) albo `user/pamięć jarva o tobie` (USER.md),
    wpisy jako lista (wpis z sekretem jako dopisek), `zmieniono` = data pliku. True = zapisana."""
    rel, tytul, opis = NOTATKI_PAMIECI[cel]
    p = p or czytaj_pamiec(plik_pamieci(profil, cel))
    limit = limity_pamieci(profil)[cel]
    plik = f"profiles/{Path(profil).name}/memories/{PLIKI_PAMIECI[cel]}"
    wpisy = ["(wpis z sekretem: pominięty w skarbcu)" if zawiera_sekret(w) else w for w in p["wpisy"]]
    lista = "\n".join("- " + w.replace("\n", "\n  ") for w in wpisy) or "_Pusto._"
    body = (f"# {tytul}\n\n**{opis} (`{plik}`): {_liczba(len(wpisy), 'wpis', 'wpisy', 'wpisów')}, {p['uzyte']} z {limit} znaków. "
            "Jarvo czyta je na starcie każdej rozmowy; zmiana w Mózgu (Zmień) działa od następnej rozmowy.**\n\n"
            f"## Wpisy\n{lista}\n\n## Powiązane\n- hub: [[{TOZSAMOSC}/{HUBY[TOZSAMOSC][0]}|Jarvo]]\n"
            + (f"- [[user/{HUBY['user'][0]}|Ty]]\n" if cel == "user" else ""))
    return _zapisz_tozsamosc(sk, rel, body, p["zmieniono"][:10], plik, "pamiec", cel)


def _dopisz_szkic_pamieci(sk: "Skarbiec", agent: str, cel: str, wpisy: list[str], marka: str = "") -> str:
    """Nowe wpisy pamięci agenta do szkicu w skrzynce: `pamiec-<agent>` (MEMORY.md) albo `pamiec-<agent>-user` (USER.md,
    o właścicielu: kompilacja kładzie fakty w user/). Linia „- data · add cel: wpis” (kompilacja szuka kandydatów osobno
    dla każdej linii)."""
    rel = f"skrzynka/pamiec-{agent}" + ("-user" if cel == "user" else "")
    if not sk.istnieje(rel):
        tytul = f"Pamięć agenta {agent}" + (" o właścicielu" if cel == "user" else "") + ": wpisy"
        fm = {"szkic": True, "typ": "fakt", "tytul": tytul, "agent": agent,
              "zrodlo": f"pamięć (memory) agenta {agent}, {PLIKI_PAMIECI[cel]}", "utworzono": dzis(), "skad": "lustro memory",
              "tagi": ["pamiec"], "linki": [], "pamiec": cel}
        if marka:
            fm["marka"] = marka
        sk.zapisz_plik(rel, sklej(fm, f"# {tytul}\n\nWpisy `memory` ({PLIKI_PAMIECI[cel]}) w kolejności zapisu; kompilacja "
                                      "robi z nich notatki.\n"))
    with sk.plik(rel).open("a", encoding="utf-8", newline="\n") as f:
        for w in wpisy:
            f.write(f"- {dzis()} · add {cel}: {' '.join(w.split())[:500]}\n")
    return rel


def synchronizuj_pamiec(sk: "Skarbiec", profil: str | Path, agent: str, marka: str = "") -> dict:
    """Lustro pamięci Hermesa po TREŚCI pliku, nie po wywołaniu narzędzia (20.11: wpisy USER.md z 19 i 20.11 nie dotarły
    do skarbca, bo plik zmienił się poza narzędziem memory). state/wiedza-pamiec.json pamięta wersję (sha256) i wpisy
    każdego pliku każdego profilu; nowa wersja = wpisy, których wcześniej nie było (pierwszy raz: wszystkie), idą do
    szkicu w skrzynce (_dopisz_szkic_pamieci), a dla Jarva (PROFIL_TOZSAMOSCI) odświeżona notatka-lustro. Woła to hak
    zapisu pamięci, start sesji i tura wtyczki, zasiew i zapis z Mózgu; ta sama wersja = nic (dwa odczyty i skrót).
    Zwraca {"zmienione": [cele], "wpisow": n, "notatki": [ścieżki]} (+ "zajete", gdy stan trzyma inny proces)."""
    wynik: dict = {"zmienione": [], "wpisow": 0, "notatki": []}
    profil = Path(profil)
    if not (profil / "memories").is_dir() or not agent:
        return wynik
    with zamek_pliku(sk.stan / ZAMEK_PAMIECI) as wzieta:
        if not wzieta:
            wynik["zajete"] = True
            return wynik
        plik_stanu = sk.stan / STAN_PAMIECI
        try:
            stan = json.loads(plik_stanu.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            stan = {}
        stan = stan if isinstance(stan, dict) else {}
        if not isinstance(stan.get(agent), dict):
            stan[agent] = {}
        moj = stan[agent]
        for cel in PLIKI_PAMIECI:
            try:
                p = czytaj_pamiec(plik_pamieci(profil, cel))
            except ValueError:
                continue
            stary = moj.get(cel) if isinstance(moj.get(cel), dict) else {}
            if stary.get("wersja") != p["wersja"]:
                znane = set(stary.get("wpisy") or [])
                nowe = [w for w in p["wpisy"] if w not in znane and not zawiera_sekret(w)]
                if nowe:
                    _dopisz_szkic_pamieci(sk, agent, cel, nowe, marka)
                    wynik["wpisow"] += len(nowe)
                wynik["zmienione"].append(cel)
                moj[cel] = {"wersja": p["wersja"], "wpisy": p["wpisy"]}
            if agent == PROFIL_TOZSAMOSCI and zapisz_notatke_pamieci(sk, profil, cel, p):
                wynik["notatki"].append(NOTATKI_PAMIECI[cel][0])
        if wynik["zmienione"]:
            tmp = plik_stanu.with_name(f"{plik_stanu.name}.{os.getpid()}.tmp")
            tmp.write_text(json.dumps(stan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
            zamien_plik(tmp, plik_stanu)
    return wynik


# ------------------------------------------------------------------------------------------------ tożsamość Jarva

_NAGLOWEK_RE = re.compile(r"^(#{1,5}) ", re.M)


def dla_czytelnika(tekst: str) -> str:
    """Plik promptu jako treść notatki: nagłówki o poziom niżej (tytuł notatki jest jedynym `# `, poza blokami kodu),
    bloki `<critical>…</critical>` jako cytat (znacznik promptu, w Mózgu i Obsidianie byłby surowym HTML-em)."""
    out, w_kodzie, w_krytycznym = [], False, False
    for linia in tekst.strip("\n").splitlines():
        s = linia.strip()
        if s.startswith("```"):
            w_kodzie = not w_kodzie
        if not w_kodzie and s in ("<critical>", "</critical>"):
            w_krytycznym = s == "<critical>"
            continue
        if not w_kodzie and _NAGLOWEK_RE.match(linia):
            linia = "#" + linia
        out.append(("> " + linia if linia else ">") if w_krytycznym else linia)
    return "\n".join(out)


def _data_pliku(p: Path) -> str:
    try:
        return dt.date.fromtimestamp(p.stat().st_mtime).isoformat()
    except OSError:
        return dzis()


def zasiej_tozsamosc(sk: "Skarbiec", katalog: Path | None) -> list[str]:
    """Notatki `jarvo/*` z plików tożsamości buildu (scripts/build.py → build/wiedza/tozsamosc/: tokeny podstawione,
    bez znaczników protokołu i rostera): SOUL → `kim jest jarvo`, ZASADY bez zamykającego bloku → `zasady pracy`,
    KRYTYCZNE (ten blok) → `zasady krytyczne`. `zmieniono` = data zmiany pliku w repo (tozsamosc/zrodla.json: data
    ostatniego commitu pliku), bez niej data pliku. Brak katalogu albo pliku = notatka zostaje, jaka była. Zwraca
    zapisane ścieżki."""
    if not katalog or not Path(katalog).is_dir():
        return []
    katalog = Path(katalog)
    try:
        daty = json.loads((katalog / "zrodla.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        daty = {}
    daty = daty if isinstance(daty, dict) else {}
    out = []
    for rel, nazwa, plik_repo, tytul, opis in NOTATKI_TOZSAMOSCI:
        src = katalog / nazwa
        if not src.is_file():
            continue
        info = daty.get(nazwa) if isinstance(daty.get(nazwa), dict) else {}
        zmieniono = str(info.get("zmieniono") or "")
        body = (f"# {tytul}\n\n**{opis}. Zmiana przez repo: w Mózgu „Poproś o zmianę”.**\n\n"
                f"{dla_czytelnika(src.read_text(encoding='utf-8', errors='replace'))}\n\n"
                f"## Powiązane\n- hub: [[{TOZSAMOSC}/{HUBY[TOZSAMOSC][0]}|Jarvo]]\n")
        if _zapisz_tozsamosc(sk, rel, body, zmieniono if DATA_RE.match(zmieniono) else _data_pliku(src),
                             str(info.get("plik") or plik_repo), "repo"):
            out.append(rel)
    return out


def _modul_mapy():
    """wiedza/mapa.py obok tego pliku (zasiew działa z repo); bez niego (kopia w katalogu wtyczki) None."""
    mod = sys.modules.get("jarvo_wiedza_mapa")
    if mod is not None:
        return mod
    plik = Path(__file__).with_name("mapa.py")
    if not plik.is_file():
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("jarvo_wiedza_mapa", plik)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["jarvo_wiedza_mapa"] = mod
    spec.loader.exec_module(mod)
    return mod


def sciezki_jarva(sk: "Skarbiec", profil: Path | None) -> dict[str, str]:
    """Ścieżki dla bloku GEN `sciezki` mapy (istniejące katalogi tej instalacji): dane Jarva, skarbiec, misje, robocze,
    od właściciela, stan, profil Jarva i jego pamięć, skrypty, rutyny."""
    dane = sk.root.parent
    kandydaci = {"dane Jarva": dane, "skarbiec": sk.root, "misje": dane / "missions", "robocze": dane / "workspaces",
                 "od właściciela": dane / "inbox", "stan (indeks, rozmowy panelu, raporty)": sk.stan}
    if profil:
        kandydaci.update({"mój profil": profil, "pamięć (MEMORY.md, USER.md)": profil / "memories",
                          "skrypty": profil / "scripts", "rutyny (jobs.json, raporty)": profil / "cron"})
    return {k: p.as_posix() for k, p in kandydaci.items() if p.is_dir()}


def tematy_telegrama(sk: "Skarbiec") -> dict[str, str]:
    """Numery tematów grupy Jarvo HQ (TELEGRAM_TOPIC_<KLUCZ>) jak w `jarvo telegram status`: trasy z `<dane>/jarvo/konfig/
    jarvo.env` (z tego pliku tylko te klucze, żadnych innych wartości), nadpisane zmiennymi procesu (brama)."""
    out: dict[str, str] = {}
    try:
        for linia in (sk.root.parent / "konfig" / "jarvo.env").read_text(encoding="utf-8", errors="replace").splitlines():
            klucz, sep, wartosc = linia.strip().removeprefix("export ").partition("=")
            if sep and klucz.strip().startswith("TELEGRAM_TOPIC_"):
                out[klucz.strip()] = wartosc.strip().strip("'\"")
    except OSError:
        pass
    out.update({k: v for k, v in os.environ.items() if k.startswith("TELEGRAM_TOPIC_")})
    return out


def zasiej_mape(sk: "Skarbiec", katalog: Path | None, fleet: dict | None, profile: Path | None,
                agenci_meta: dict | None = None) -> bool:
    """Notatka `jarvo/jak działa jarvo` („Jarvo od A do Z”, docs/WIEDZA.md §2b): MAPA.md repo i nakładki z buildu
    (tozsamosc/MAPA.md, MAPA-nakladka.md, tokeny podstawione) i bloki GEN z danych tej instalacji (wiedza/mapa.py):
    agenci i skille (fleet.json), arsenał (`fleet/arsenal`), ścieżki, harmonogram (zadania cron wszystkich profili,
    także wstrzymane, wątki Telegrama, timery systemd usera). `sekcje: true`: każda sekcja to osobny wpis indeksu
    (przypomnienie trafia w sekcję, nie w całą mapę). True = zapisana."""
    mapa = _modul_mapy()
    if mapa is None or not katalog or not (Path(katalog) / "MAPA.md").is_file():
        return False
    katalog = Path(katalog)
    repo = (katalog / "MAPA.md").read_text(encoding="utf-8", errors="replace")
    nakl = (katalog / "MAPA-nakladka.md").read_text(encoding="utf-8", errors="replace") if (katalog / "MAPA-nakladka.md").is_file() else ""
    agenci = [{**a, "hub": (agenci_meta or {}).get(a["name"], {}).get("hub", "")} for a in (fleet or {}).get("agents", [])]
    profil = Path(profile) / PROFIL_TOZSAMOSCI if profile else None
    cron = mapa.zadania_cron_profili(Path(profile)) if profile and Path(profile).is_dir() else []
    arsenal = sk.plik("fleet/arsenal").read_text(encoding="utf-8", errors="replace") if sk.istnieje("fleet/arsenal") else ""
    d = dzis()
    gen = {"agenci": mapa.render_agenci(agenci), "skille": mapa.render_skille(agenci), "arsenal": mapa.render_arsenal(arsenal),
           "sciezki": mapa.render_sciezki(sciezki_jarva(sk, profil if profil and profil.is_dir() else None)),
           "harmonogram": mapa.render_harmonogram(cron, mapa.timery_systemd(),
                                                  mapa.watki_telegrama(sk.stan / "telegram-grupy.json", tematy_telegrama(sk)))}
    zrodla = {"agenci": f"fleet.yaml, {d}", "skille": f"fleet.yaml i skille profili, {d}", "arsenal": f"`fleet/arsenal`, {d}",
              "sciezki": f"tej instalacji, {d}", "harmonogram": f"rutyn Hermesa (cron/jobs.json) i timerów systemd, {d}"}
    try:
        daty = json.loads((katalog / "zrodla.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        daty = {}
    zmiany = [str((daty.get(n) or {}).get("zmieniono") or "") for n in ("MAPA.md", "MAPA-nakladka.md") if isinstance(daty, dict)]
    zmieniono = max([z for z in zmiany if DATA_RE.match(z)] or [_data_pliku(katalog / "MAPA.md")])
    body = mapa.notatka(repo, nakl, gen, zrodla) + f"\n## Powiązane\n- hub: [[{TOZSAMOSC}/{HUBY[TOZSAMOSC][0]}|Jarvo]]\n"
    return _zapisz_tozsamosc(sk, MAPA_NOTATKA, body, zmieniono, "profiles/jarvo/MAPA.md", "repo", sekcje=True)


def odswiez_hub_jarva(sk: "Skarbiec", orzeczenia_jarva: str = "") -> None:
    """Blok GEN `tozsamosc` w hubie `jarvo/_hub-jarvo`: tożsamość w stałej kolejności (istniejące notatki), pamięć
    o Tobie (user/) i orzeczenia (poprawki właściciela dla Jarva i dla wszystkich)."""
    zapewnij_hub(sk, TOZSAMOSC)
    rel = f"{TOZSAMOSC}/{HUBY[TOZSAMOSC][0]}"
    linie = []
    for s in KOLEJNOSC_TOZSAMOSCI:
        if sk.istnieje(s):
            n = sk.wczytaj(s)
            linie.append(f"- [[{s}|{n.tytul}]]" + (f" · {n.streszczenie[:110]}" if n.streszczenie else ""))
    for s, etykieta in ((orzeczenia_jarva, "Twoje poprawki dla Jarva (orzeczenia)"),
                        ("orzeczenia/wszyscy", "Poprawki dla całej floty (orzeczenia)")):
        if s and sk.istnieje(s):
            linie.append(f"- [[{s}|{etykieta}]]")
    tekst = sk.plik(rel).read_text(encoding="utf-8")
    nowy = zastap_blok(tekst, "tozsamosc", "## Tożsamość i pamięć\n" + ("\n".join(linie) or "_jeszcze pusto_"))
    if nowy != tekst:
        sk.zapisz_plik(rel, nowy)


# ------------------------------------------------------------------------------------------------ porządki: archiwum, przeniesienie, streszczenie

def _norm(rel: str) -> str:
    return unicodedata.normalize("NFC", str(rel or "").strip().strip("/").removesuffix(".md"))


def przepisz_linki(text: str, cele: dict[str, str], rozwiaz, znane_po: dict[str, str]) -> tuple[str, int]:
    """Linki `[[cel#kotwica|etykieta]]`, których cel (`rozwiaz(cel)` przed przeniesieniem) jest w `cele`, wskazują nową
    ścieżkę; kotwica i etykieta zostają. Sama nazwa pliku, która po przeniesieniu dalej jednoznacznie trafia w nowe miejsce,
    zostaje bez zmian. Zwraca (tekst, liczba przepisanych linków)."""
    ile = 0

    def zamien(m: re.Match) -> str:
        nonlocal ile
        cel = m.group(1).strip()
        cel = cel[:-3] if cel.endswith(".md") else cel
        stara = rozwiaz(cel)
        if stara not in cele:
            return m.group(0)
        nowa = cele[stara]
        if "/" not in cel and znane_po.get(cel) == nowa:
            return m.group(0)
        ile += 1
        return f"[[{nowa}{m.group(2) or ''}{'|' + m.group(3) if m.group(3) is not None else ''}]]"

    return LINK_RE.sub(zamien, text), ile


HUB_LINIA_RE = re.compile(r"^(- hub: )\[\[([^\]\|#]+)(#[^\]\|]*)?(?:\|([^\]]*))?\]\][ \t]*$", re.M)


def hub_notatki(sk: "Skarbiec", rel: str) -> str | None:
    """Właściwy hub notatki: hub w jej katalogu (folder skarbca, agent, marka, agent w archiwum), a bez niego hub jej
    folderu najwyższego poziomu (`inspiracje/strony/…` → `inspiracje/_hub-inspiracje`, `archiwum/podmioty/…` →
    `archiwum/_hub-archiwum`); None, gdy folder nie ma huba."""
    if "/" not in rel:
        return None
    katalog, gora = rel.rsplit("/", 1)[0], rel.split("/", 1)[0]
    d = sk.root / katalog
    huby = sorted(p.stem for p in d.glob("_hub-*.md")) if d.is_dir() else []
    if huby:
        return f"{katalog}/{huby[0]}"
    return f"{gora}/{HUBY[gora][0]}" if gora in HUBY and sk.istnieje(f"{gora}/{HUBY[gora][0]}") else None


def popraw_hub(sk: "Skarbiec", rel: str, tekst: str, znane: dict | None = None, zbior: set | None = None,
               stary_hub: str = "") -> str:
    """Notatka `rel` bez linku do huba swojego folderu (21.11: po `przenies` zostawała linia `- hub:
    [[agenci/jarvo/_hub-jarvo]]`, lint „bez linku do huba folderu”): linia hub dawnego folderu (`stary_hub`, bez niego
    pierwsza linia `- hub:`, bo kompilator stawia hub własnego folderu pierwszy) wskazuje hub jej folderu (hub_notatki;
    etykieta idzie za hubem). Gdy była to jedyna droga do innego folderu, dawny cel zostaje zwykłym linkiem w następnej
    linii. Notatka bez linii hub, z sekcją „## Powiązane”, dostaje ją na początku sekcji. Notatka, która ma już link do
    huba swojego folderu, zostaje bez zmian (dalsze linie `- hub:` do innych folderów to linki między folderami)."""
    gora = rel.split("/", 1)[0]
    if rel.rsplit("/", 1)[-1].startswith("_hub-") or rel.startswith((*SUROWE, TOZSAMOSC + "/")) or rel in KOLEJNOSC_TOZSAMOSCI:
        return tekst
    hub = hub_notatki(sk, rel)
    if not hub:
        return tekst
    _fm, body = podziel(tekst)
    naglowek = tekst[:len(tekst) - len(body)]
    if zbior is None:
        zbior, znane = sk.mapa()
    rozw = lambda c: sk.rozwiaz(c.strip().removesuffix(".md"), znane, zbior) or c.strip()       # noqa: E731
    reczne = [rozw(m.group(1)) for m in LINK_RE.finditer(GEN_RE.sub("", body))]
    if any(c.startswith(gora + "/") and c.rsplit("/", 1)[-1].startswith("_hub-") for c in reczne):
        return tekst
    linie = list(HUB_LINIA_RE.finditer(body))
    m = next((x for x in linie if rozw(x.group(2)) == stary_hub), None) if stary_hub else None
    m = m or (linie[0] if linie else None)
    if m is None:
        pow_ = re.search(r"^## Powiązane[ \t]*\n", body, re.M)
        return naglowek + body[:pow_.end()] + f"- hub: [[{hub}]]\n" + body[pow_.end():] if pow_ else tekst
    dawny = rozw(m.group(2))
    etykieta = f"|{sk.wczytaj(hub).tytul}" if m.group(4) is not None else ""
    linia = f"{m.group(1)}[[{hub}{m.group(3) or ''}{etykieta}]]"
    inne = [c for i, c in enumerate(reczne) if c.split("/", 1)[0] != gora and c != dawny]
    if not inne and dawny.split("/", 1)[0] != gora:
        linia += f"\n- [[{dawny}]]"                       # jedyny link do innego folderu zostaje
    return naglowek + body[:m.start()] + linia + body[m.end():]


def napraw_huby(sk: "Skarbiec") -> dict:
    """Jednorazowa naprawa po przenosinach sprzed 21.11: popraw_hub we wszystkich notatkach (bez źródeł, szkiców, kopii
    repo, hubów i tożsamości). Zwraca {"sprawdzone", "poprawione", "notatki": [ścieżki]}."""
    zbior, znane = sk.mapa()
    out: dict = {"sprawdzone": 0, "poprawione": 0, "notatki": []}
    for rel in sorted(zbior):
        if rel.startswith(SUROWE) or rel.rsplit("/", 1)[-1].startswith("_hub-"):
            continue
        p = sk.plik(rel)
        tekst = p.read_text(encoding="utf-8", errors="replace")
        out["sprawdzone"] += 1
        nowy = popraw_hub(sk, rel, tekst, znane, zbior)
        if nowy != tekst:
            sk.zapisz_plik(rel, nowy)
            out["poprawione"] += 1
            out["notatki"].append(rel)
    return out


def przenies_notatki(sk: "Skarbiec", mapa: dict[str, str], fm_dodaj: dict[str, dict] | None = None,
                     przekieruj: dict[str, str] | None = None, pliki: dict[str, str] | None = None) -> dict:
    """Przenosi notatki (`mapa`: stara ścieżka → nowa, bez `.md`) i przepisuje linki do nich we wszystkich notatkach
    skarbca (bez kopii repo `zrodla/jarvo-repo/`, którą nadpisuje wdrożenie, i bez LOG.md, który jest historią):
    link do starej ścieżki wskazuje potem `przekieruj[stara]` (następca) albo nową ścieżkę. Pole `zastapiona_przez`
    w archiwum też idzie za przeniesieniem. `fm_dodaj[stara]` dopisuje klucze frontmatteru przeniesionej notatki,
    `pliki` (względne ścieżki z rozszerzeniem) to załączniki przenoszone bez zmian. Puste katalogi po starych ścieżkach
    znikają. Zwraca {"przeniesione", "notatek_z_linkami", "linkow", "_mapa" (stara → nowa)}."""
    zbior, znane = sk.mapa()
    bledy = []                                              # wszystkie przed jakąkolwiek zmianą: nic nie przeniesione
    for stara, nowa in mapa.items():
        if stara not in zbior:
            bledy.append(f"nie ma notatki `{stara}`")
        elif sk.istnieje(nowa) or list(mapa.values()).count(nowa) > 1:
            bledy.append(f"`{nowa}` już istnieje")
        else:
            try:
                sk.plik(nowa)                               # ścieżka poza skarbcem
            except ValueError as e:
                bledy.append(str(e))
    if bledy:
        raise ValueError("nic nie przeniesione: " + "; ".join(bledy))
    cele = {s: (przekieruj or {}).get(s) or n for s, n in mapa.items()}
    stare_huby = {n: hub_notatki(sk, s) or "" for s, n in mapa.items()}      # hub dawnego folderu (przed przeniesieniem)
    for stara, nowa in mapa.items():
        tekst = sk.plik(stara).read_text(encoding="utf-8", errors="replace")
        if fm_dodaj and fm_dodaj.get(stara):
            fm, body = podziel(tekst)
            fm.update(fm_dodaj[stara])
            tekst = sklej(fm, body)
        sk.zapisz_plik(nowa, tekst)
    for stara, nowa in (pliki or {}).items():
        cel = sk.root / nowa
        cel.parent.mkdir(parents=True, exist_ok=True)
        zamien_plik(sk.root / stara, cel)
    katalogi = set()
    for stara in [*mapa, *(s.removesuffix(".md") for s in pliki or {})]:
        p = sk.root / f"{stara}.md"
        if p.is_file():
            p.unlink()
        katalogi.add(p.parent)
    for d in sorted(katalogi, key=lambda d: len(d.parts), reverse=True):
        while d != sk.root and d.is_dir() and not any(d.iterdir()):
            d.rmdir()
            d = d.parent
    po = (zbior - set(mapa)) | set(mapa.values())
    znane_po: dict[str, str] = {}
    for rel in sorted(po):
        znane_po.setdefault(rel.rsplit("/", 1)[-1], rel)
    rozwiaz = lambda c: sk.rozwiaz(c, znane, zbior) if c not in mapa else c            # noqa: E731
    wynik = {"przeniesione": len(mapa) + len(pliki or {}), "notatek_z_linkami": 0, "linkow": 0, "huby": 0, "_mapa": dict(mapa)}
    przeniesione = set(mapa.values())
    for rel in sorted(po):
        if rel.startswith(LUSTRO_REPO + "/"):
            continue
        p = sk.plik(rel)
        tekst = p.read_text(encoding="utf-8", errors="replace")
        nowy, ile = przepisz_linki(tekst, cele, rozwiaz, znane_po)
        if rel in przeniesione:                              # przeniesiona notatka: linia hub z jej nowego folderu
            poprawiona = popraw_hub(sk, rel, nowy, znane_po, po, cele.get(stare_huby.get(rel, ""), stare_huby.get(rel, "")))
            if poprawiona != nowy:
                nowy, ile = poprawiona, ile + 1
                wynik["huby"] += 1
        fm, body = podziel(nowy)
        zast = _norm(str(fm.get("zastapiona_przez") or ""))
        if zast in cele:
            fm["zastapiona_przez"] = cele[zast]
            nowy, ile = sklej(fm, body), ile + 1
        if nowy != tekst:
            sk.zapisz_plik(rel, nowy)
            wynik["notatek_z_linkami"] += 1
            wynik["linkow"] += ile
    return wynik


def _chronione(rel: str) -> str:
    """Powód, dla którego tej ścieżki nie archiwizujemy ani nie przenosimy, albo pusto."""
    gora = rel.split("/", 1)[0]
    if rel in FOLDERY_SKARBCA or (gora in HUBY and rel == f"{gora}/{HUBY[gora][0]}") or rel == HUBY[""][0]:
        return "folderu skarbca ani jego huba nie ruszam (zmień FOLDERY_SKARBCA w wiedza.py)"
    if rel.startswith(("zrodla/", "skrzynka/")) or gora in ("zrodla", "skrzynka"):
        return "źródła i szkice nie są wiedzą (archiwizuję notatki)"
    if gora == TOZSAMOSC:
        return "tożsamość Jarva generuje zasiew (zmiana przez repo albo pamięć)"
    if gora == ARCHIWUM:
        return "już w archiwum"
    return ""


def archiwizuj(sk: "Skarbiec", sciezki: list[str], powod: str, zastapiona_przez: str = "") -> dict:
    """Notatki (albo całe katalogi, np. `agenci/jarvo-operator`) do `archiwum/<dawna ścieżka>` z frontmatterem
    `status: wycofana`, `wycofano`, `powod` i opcjonalnie `zastapiona_przez`. Linki do nich wszędzie wskazują następcę
    (gdy podany), inaczej nową ścieżkę w archiwum. Bez blokady i punktu zapisu (robi je CLI albo zasiew)."""
    powod = " ".join(str(powod or "").split())
    if not powod:
        raise ValueError("podaj powód (--powod)")
    nastepca = _norm(zastapiona_przez)
    notatki: list[str] = []
    zalaczniki: dict[str, str] = {}
    wszystkie = sk.pliki()
    bledy: list[str] = []                     # 21.11: jedna literówka na liście przerywała całość bez wskazania, która
    for s in (_norm(x) for x in sciezki):
        if (blad := _chronione(s)):
            bledy.append(f"`{s}`: {blad}")
            continue
        katalog = sk.root / s
        if katalog.is_dir():
            notatki += [r for r in wszystkie if r.startswith(s + "/")]
            for p in sorted(katalog.rglob("*")):
                if p.is_file() and p.suffix != ".md":
                    r = p.relative_to(sk.root).as_posix()
                    zalaczniki[r] = f"{ARCHIWUM}/{r}"
        elif sk.istnieje(s):
            notatki.append(s)
        else:
            bledy.append(f"`{s}`: nie ma takiej notatki ani katalogu")
    notatki = list(dict.fromkeys(notatki))
    if nastepca and (nastepca in notatki or nastepca.startswith(ARCHIWUM + "/") or not sk.istnieje(nastepca)):
        bledy.append(f"następca `{nastepca}` musi być istniejącą notatką spoza archiwum i spoza archiwizowanych")
    if bledy:
        raise ValueError(f"nic nie zarchiwizowane, popraw {len(bledy)} z {len(sciezki) + bool(nastepca)}: " + "; ".join(bledy))
    if not notatki:
        raise ValueError("nic do archiwizacji (katalog bez notatek)")
    fm = {"status": "wycofana", "wycofano": dzis(), "powod": powod, **({"zastapiona_przez": nastepca} if nastepca else {})}
    return przenies_notatki(sk, {s: f"{ARCHIWUM}/{s}" for s in notatki}, {s: fm for s in notatki},
                            {s: nastepca for s in notatki} if nastepca else None, zalaczniki)


def przenies(sk: "Skarbiec", sciezka: str, folder: str) -> dict:
    """Notatka do innego folderu skarbca pod tym samym tytułem (nazwą pliku), linki przepisane wszędzie. Folder: klucz
    FOLDERY_SKARBCA z notatkami albo istniejący podkatalog (`agenci/jarvo-web`, `brands/acme`); bez archiwum (do tego
    `archiwizuj`), tożsamości, źródeł i skrzynki. Bez blokady i punktu zapisu (robi je CLI)."""
    s, folder = _norm(sciezka), _norm(folder)
    if (blad := _chronione(s)):
        raise ValueError(f"`{s}`: {blad}")
    if not sk.istnieje(s):
        raise ValueError(f"nie ma notatki `{s}`")
    if s.rsplit("/", 1)[-1].startswith("_hub-"):
        raise ValueError("hubów nie przenoszę (hub agenta przenosi zasiew razem z jego katalogiem)")
    gora = folder.split("/", 1)[0]
    if gora not in FOLDERY_SKARBCA or not gora or gora in (ARCHIWUM, TOZSAMOSC, "zrodla", "skrzynka") \
            or ("/" in folder and not (sk.root / folder).is_dir()):
        raise ValueError(f"`{folder}` nie jest folderem notatek (dozwolone: "
                         + ", ".join(f for f in FOLDERY_SKARBCA if f and f not in (ARCHIWUM, TOZSAMOSC, "zrodla", "skrzynka"))
                         + " albo istniejący podkatalog, np. agenci/jarvo-web)")
    nowa = f"{folder}/{s.rsplit('/', 1)[-1]}"
    if nowa == s:
        raise ValueError(f"`{s}` już jest w `{folder}/`")
    return przenies_notatki(sk, {s: nowa})


def hub_do_streszczenia(sk: "Skarbiec", hub: str) -> str:
    """Ścieżka huba z argumentu: ścieżka huba, nazwa pliku `_hub-…`, folder z FOLDERY_SKARBCA albo katalog z jednym hubem
    (`agenci/jarvo-web`)."""
    s = _norm(hub)
    if s in HUBY:
        return f"{s}/{HUBY[s][0]}" if s else HUBY[""][0]
    if sk.istnieje(s) and s.rsplit("/", 1)[-1].startswith("_hub-"):
        return s
    if s and (sk.root / s).is_dir():
        huby = sorted(sk.rel(p) for p in (sk.root / s).glob("_hub-*.md"))
        if len(huby) == 1:
            return huby[0]
    if "/" not in s and s.startswith("_hub-") and (r := sk.mapa()[1].get(s)):
        return r
    raise ValueError(f"nie znam huba `{hub}` (podaj ścieżkę huba albo folder: {', '.join(f for f in HUBY if f)})")


def streszczenie(sk: "Skarbiec", hub: str, tekst: str) -> str:
    """Blok STRESZCZENIE w hubie (najważniejsze z części jednym tekstem, Markdown do MAX_STRESZCZENIA_HUBA znaków)
    i `streszczono: dziś` we frontmatterze. Zasiew i indeksuj go nie nadpisują. Zwraca ścieżkę huba."""
    rel = hub_do_streszczenia(sk, hub)
    tekst = "\n".join(l.rstrip() for l in str(tekst or "").replace("\r\n", "\n").strip().splitlines())
    if not tekst:
        raise ValueError("streszczenie jest puste")
    if len(tekst) > MAX_STRESZCZENIA_HUBA:
        raise ValueError(f"streszczenie ma {len(tekst)} znaków, limit {MAX_STRESZCZENIA_HUBA}: skróć do najważniejszego")
    if "<!--" in tekst:
        raise ValueError("streszczenie bez komentarzy HTML (znaczniki bloków skarbca)")
    if (sekret := zawiera_sekret(tekst)):
        raise ValueError(f"streszczenie zawiera sekret ({sekret})")
    fm, body = podziel(sk.plik(rel).read_text(encoding="utf-8"))
    fm["streszczono"] = dzis()
    sk.zapisz_plik(rel, sklej(fm, wstaw_streszczenie(body, tekst)))
    return rel


def porzadki(sk: Skarbiec, rodzaj: str, opis: str, operacja, czekaj_s: float = 60.0) -> dict:
    """Operacja porządkowa skarbca (archiwizuj, przenies, streszczenie; CLI i `jarvo wiedza …`): blokada skarbca (jeden
    piszący z kompilacją i zasiewem), punkt zapisu przed (cofnij = dokładnie ta operacja) i po, wpis w LOG, indeks,
    INDEX i listy hubów od nowa. Wektory przeniesionych notatek idą za nimi (ta sama treść, bez ponownego osadzania)."""
    blok = Blokada(sk.stan, czekaj_s)
    if not blok.wez():
        raise RuntimeError(f"skarbiec zajęty: {blok.powod}")
    try:
        sk.punkt_zapisu(f"przed: {opis}")
        wynik = operacja()
        mapa = wynik.pop("_mapa", {}) if isinstance(wynik, dict) else {}
        ix = Indeks(sk)
        try:
            with ix.db:
                for stara, nowa in mapa.items():
                    if not nowa.startswith(POZA_WYSZUKIWANIEM):
                        ix.db.execute("UPDATE OR REPLACE wektory SET sciezka = ? WHERE sciezka = ?", (nowa, stara))
            ix.odswiez()
            zbuduj_index(sk, ix)
            odswiez_listy_hubow(sk, ix)
            ix.odswiez()
            if mapa:
                ix.odswiez_wektory(KlientWektorow(sk.stan, WEKTORY_CZAS_ZAPISU_S))
        finally:
            ix.zamknij()
        if wynik.get("poprawione") == 0:                       # naprawa bez zmian: bez wpisu w LOG i punktu zapisu
            return wynik
        szczegoly = [f"{s} → {n}" for s, n in mapa.items()] or [str(n) for n in wynik.get("notatki") or []]
        sk.dopisz_log(rodzaj, opis + "".join(f"\n- {x}" for x in szczegoly))
        wynik["git"] = sk.punkt_zapisu(opis)
        return wynik
    finally:
        blok.zwolnij()


def tytul_huba_agenta(a: dict) -> str:
    """Tytuł huba agenta z fleet.yaml: emoji, krótka nazwa z HQ (`hq_short`, jak mówi właściciel: „Jarvo”, a nie tytuł
    roli „Main Judge”) i profil."""
    return " ".join(x for x in (a.get("emoji", ""), a.get("short") or a.get("title") or a["name"], f"({a['name']})") if x)


def zasiej(sk: Skarbiec, fleet: dict | None, docs: Path | None, schema: Path | None, repo: Path | None = None,
           bledy: Path | None = None, tozsamosc: Path | None = None, profile: Path | None = None) -> dict:
    """Zasiew (wdrożenie, `jarvo wiedza zasiej`): foldery i huby z FOLDERY_SKARBCA, huby agentów z fleet.json (agent
    spoza floty: cały katalog i jego orzeczenia do archiwum), skille, kopia repo, księga błędów, tożsamość Jarva
    (`tozsamosc`: build/wiedza/tozsamosc) i lustra pamięci profili floty (`profile`: <dane>/profiles), LOG i punkt
    zapisu git. Część ręczna hubów i bloki STRESZCZENIE zostają; bloki GEN odświeżane zawsze."""
    sk.root.mkdir(parents=True, exist_ok=True)
    for f in FOLDERY:
        (sk.root / f).mkdir(parents=True, exist_ok=True)
    raport = {"huby": 0, "agenci": 0, "skille": 0, "docs": 0, "repo": 0, "bledy": 0, "archiwum": [], "tozsamosc": 0,
              "pamiec": 0, "git": False}
    w_lustrze: set[str] = set()
    if repo and repo.is_dir():
        raport["repo"], w_lustrze = zasiej_lustro(sk, repo)
    if schema and schema.exists():
        shutil.copy2(schema, sk.root / "SCHEMA.md")
    # huby folderów (część ręczna zostaje: piszemy tylko, gdy pliku nie ma; bloki GEN odświeżane zawsze)
    for folder in HUBY:
        raport["huby"] += zapewnij_hub(sk, folder)
    linie = [f"- [[{f}/{h}|{t}]] · {OPISY_FOLDEROW.get(f, '')}" for f, (h, t) in HUBY.items() if f]
    linie += ["- [[INDEX|Indeks]] · każda notatka jedną linią", "- [[LOG|Dziennik]] · co się działo ze skarbcem", "- [[LINT|Lint]] · ostatni raport zdrowia",
              "- [[SCHEMA|Schemat]] · zasady skarbca"]
    p = sk.plik(HUBY[""][0])
    sk.zapisz_plik(HUBY[""][0], zastap_blok(p.read_text(encoding="utf-8"), "huby", "## Foldery\n" + "\n".join(linie)))
    # agenci z fleet.json
    agenci_meta: dict[str, dict] = {}
    try:   # opisy z poprzedniego zasiewu: pogrubiony opis huba idzie za fleet.yaml, dopóki człowiek go nie zmienił
        poprzednie = json.loads((sk.stan / "wiedza-agenci.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        poprzednie = {}
    skille_floty: dict[str, tuple[dict, list]] = {}
    if fleet:
        for a in fleet.get("agents", []):
            rel, krotki = hub_agenta(a)
            orz = f"orzeczenia/{krotki}"
            opis = " ".join(a.get("description", "").split())
            agenci_meta[a["name"]] = {"hub": rel, "orzeczenia": orz, "short": a.get("short") or krotki, "title": a.get("title", ""),
                                      "opis": opis}
            marka = str(a.get("marka") or "").strip()
            marka = marka if MARKA_RE.fullmatch(marka) else ""
            if marka:                          # agent biznesowy: zakres skarbca (zakres_marki) czytają wtyczka i kompilacja
                agenci_meta[a["name"]]["marka"] = marka
            if not sk.istnieje(rel):
                body = (f"# {tytul_huba_agenta(a)}\n\n**{a.get('description', '').strip()}**\n\n"
                        f"## Powiązane\n- hub: [[agenci/_hub-agenci|Agenci]]\n- [[{orz}|Orzeczenia: {a.get('short') or krotki}]]\n"
                        f"- [[fleet/lekcje|Księga lekcji floty]]\n")
                sk.zapisz_plik(rel, sklej(_hub_frontmatter("agent", "fleet.yaml", agent=a["name"]), body))
                raport["agenci"] += 1
            skille = "\n".join(f"- [[{SKILLE}/{s['name']}|{s['name']}]]: {s.get('description', '').strip()}"
                               for s in a.get("skills", [])) or "_brak_"
            skrypty = ", ".join(f"`{s}`" for s in a.get("scripts", [])) or "_brak_"
            def serwer(m: dict) -> str:
                czesci = ([f"trust: {m['trust']}"] if m.get("trust") else []) + ([", ".join(m["tools"])] if m.get("tools") else [])
                return f"`{m['name']}`" + (f" ({' · '.join(czesci)})" if czesci else "")
            mcp = "; ".join(serwer(m) for m in a.get("mcp") or [])
            mcp_linia = f"\n- serwery MCP: {mcp}" if mcp else ""
            env = a.get("env") or []
            if env:
                mcp_linia += "\n- zmienne środowiska (same nazwy, wartości w .env): " + ", ".join(f"`{e}`" for e in env)
            if a.get("tools"):
                mcp_linia += f"\n- narzędzia (toolbox.yaml, {len(a['tools'])}): " + ", ".join(f"`{x}`" for x in a["tools"])
            if a.get("evals"):
                mcp_linia += f"\n- evals ({len(a['evals'])}): " + ", ".join(f"`{e['id']}`" for e in a["evals"])
            pliki_repo = [(f"profiles/{a['name']}/{r}", etykieta) for r, etykieta in
                          (("SOUL.md", "postać (SOUL)"), ("ZASADY.md", "zasady pracy"), ("README.md", "README"),
                           ("quality/rubric.md", "rubryka"),
                           ("CHANGELOG.md", "wszystkie zmiany"))]
            z_repo = [f"[[{lustro(r)}|{etykieta}]]" for r, etykieta in pliki_repo if lustro(r) in w_lustrze]
            if z_repo:
                mcp_linia += "\n- z repo: " + " · ".join(z_repo)
            zewn = a.get("external_skills") or []
            zewn_linia = (f"\n- skille zewnętrzne ({len(zewn)}): " + ", ".join(f"`{s}`" for s in zewn)) if zewn else ""
            wsp = a.get("shared_skills") or []
            if wsp:
                zewn_linia = (f"\n- skille wspólne floty ({len(wsp)}): " + ", ".join(f"[[{SKILLE}/{s['name']}|{s['name']}]]" for s in wsp)
                              + zewn_linia)
            for s in [*a.get("skills", []), *wsp]:
                skille_floty.setdefault(s["name"], (s, []))[1].append((rel, a.get("short") or krotki, a["name"]))
            zmiany = "".join(f"\n  - {z}" for z in a.get("changes") or [])
            zmiany_linia = (f"\n- ostatnie zmiany (CHANGELOG profilu, {a.get('changes_section') or 'najnowsze'}):{zmiany}"
                            if zmiany else "")
            uchwyt = f"uchwyt: @{a['handle']} · " if a.get("handle") else ""   # @… w rozmowie aplikacji Jarvo
            uchwyt += f"marka: [[{hub_marki(marka)}|{marka}]] · " if marka else ""
            gen = (f"## Z rejestru floty (fleet.yaml)\n- rola: {a.get('kind', '')} · autonomia: {a.get('autonomy_max', '')} · "
                   f"{uchwyt}pokój HQ: {a.get('label', a.get('room', ''))} (`{a.get('room', '')}`) · temat Telegrama: `{a.get('telegram_topic', '')}`\n"
                   f"- skille ({len(a.get('skills', []))}):\n{skille}{zewn_linia}\n- skrypty: {skrypty}{mcp_linia}{zmiany_linia}")
            pl = sk.plik(rel)
            tekst = pl.read_text(encoding="utf-8")
            m = re.search(r"^(# .+\n\n)\*\*(.+)\*\*$", tekst, re.M)
            stary = (poprzednie.get(a["name"]) or {}).get("opis")
            if m and opis and m.group(2) != opis and (stary is None or m.group(2) == stary):
                tekst = tekst[:m.start(2) - 2] + f"**{opis}**" + tekst[m.end(2) + 2:]
            # tytuł z fleet.yaml (dawne huby: „🛰️ Main Judge (jarvo)”); tytuł zmieniony ręcznie (bez „(profil)”) zostaje
            tekst = re.sub(rf"^# .*\({re.escape(a['name'])}\)[ \t]*$", lambda _m: f"# {tytul_huba_agenta(a)}", tekst, count=1,
                           flags=re.M)
            sk.zapisz_plik(rel, zastap_blok(tekst, "fleet", gen))
            if not sk.istnieje(orz):
                sk.zapisz_plik(orz, sklej(_hub_frontmatter("orzeczenia", "człowiek", agent=a["name"]),
                                          f"# Orzeczenia: {a.get('short') or krotki}\n\n**Korekty od użytkownika dla `{a['name']}`, jedna datowana linia każda; agent czyta je przed każdą turą.**\n\n"
                                          f"## Powiązane\n- hub: [[orzeczenia/_hub-orzeczenia|Orzeczenia]]\n- [[{rel}|{a.get('short') or krotki}]]\n\n## Linie\n"))
            if marka:
                zasiej_marke(sk, marka, a, rel)
        # agent usunięty z floty (14.11 jarvo-operator): cały katalog `agenci/<agent>/` i plik jego orzeczeń do archiwum
        # (Zespół to tylko aktywni), linki z notatek i hubów wskazują archiwum; blok z rejestru mówi, kiedy i czemu
        w_flocie = {a["name"] for a in fleet.get("agents", [])}
        for hub in sorted((sk.root / "agenci").glob("*/_hub-*.md")):
            rel_h = sk.rel(hub)
            agent = str(sk.wczytaj(rel_h).fm.get("agent") or "")
            if not agent or agent in w_flocie or rel_h.split("/")[1] != agent:
                continue
            tekst = hub.read_text(encoding="utf-8")
            sk.zapisz_plik(rel_h, zastap_blok(tekst, "fleet", f"## Z rejestru floty (fleet.yaml)\n- `{agent}` nie ma już we "
                                                               f"flocie (zasiew {dzis()}): hub i notatki to historia w archiwum"))
            orz = "orzeczenia/" + hub.stem.removeprefix("_hub-")
            sciezki = [f"agenci/{agent}", *([orz] if sk.istnieje(orz) and orz != "orzeczenia/wszyscy" else [])]
            archiwizuj(sk, sciezki, "agent wycofany z floty")
            raport["archiwum"] += sciezki
        (sk.stan).mkdir(parents=True, exist_ok=True)
        (sk.stan / "wiedza-agenci.json").write_text(json.dumps(agenci_meta, ensure_ascii=False, indent=1), encoding="utf-8",
                                                    newline="\n")
        # skrypty, które naprawdę są w repo: lint wskazuje notatki floty odwołujące się do nieistniejących
        znane_skrypty = sorted({s for a in fleet.get("agents", []) for s in a.get("scripts", [])} | set(fleet.get("repo_scripts") or []))
        (sk.stan / "wiedza-kod.json").write_text(json.dumps({"skrypty": znane_skrypty}, ensure_ascii=False, indent=1), encoding="utf-8",
                                                 newline="\n")
        raport["skille"] = zasiej_skille(sk, skille_floty, w_lustrze)
    if not sk.istnieje("orzeczenia/wszyscy"):
        sk.zapisz_plik("orzeczenia/wszyscy", sklej(_hub_frontmatter("orzeczenia", "człowiek"),
                                                   "# Orzeczenia: wszyscy\n\n**Korekty od użytkownika dla całej floty, jedna datowana linia każda.**\n\n"
                                                   "## Powiązane\n- hub: [[orzeczenia/_hub-orzeczenia|Orzeczenia]]\n\n## Linie\n"))
    if not sk.istnieje("fleet/lekcje"):
        sk.zapisz_plik("fleet/lekcje", sklej(_hub_frontmatter("lekcja", "przegląd tygodnia (skill fleet-improvement)"),
                                             "# Księga lekcji floty\n\n**Obserwacje z recenzji sędziego: jedna linia = jedna sprawdzalna reguła z licznikiem potwierdzeń.**\n\n"
                                             "## Powiązane\n- hub: [[agenci/_hub-agenci|Agenci]]\n"))
    raport["bledy"] = zasiej_bledy(sk, bledy)            # księga błędów z repo: nowe notatki, istniejących nie rusza
    if docs and docs.is_dir():
        katalog_docs = sk.root / LUSTRO_REPO
        nazwy = set()
        for d in sorted(docs.glob("*.md")):
            shutil.copy2(d, katalog_docs / d.name)
            nazwy.add(d.name)
            raport["docs"] += 1
        for stara in katalog_docs.glob("*.md"):            # dokument usunięty z repo nie zostaje w skarbcu jako „źródło”
            if stara.name not in nazwy:
                stara.unlink()
    # hub główny: dokumenty repo i spis źródeł (kopie w zrodla/jarvo-repo/), żeby były w grafie przy skarbcu
    docs_w = sorted(p.stem for p in (sk.root / LUSTRO_REPO).glob("*.md"))
    linie_repo = [f"- [[{LUSTRO_REPO}/{n}|{n}]]" for n in docs_w]
    if f"{LUSTRO_REPO}/vendor/zrodla" in w_lustrze:
        linie_repo.append(f"- [[{LUSTRO_REPO}/vendor/zrodla|Źródła zewnętrzne]] · repo, z których bierzemy, i ich status")
    if linie_repo:
        p = sk.plik(HUBY[""][0])
        sk.zapisz_plik(HUBY[""][0], zastap_blok(p.read_text(encoding="utf-8"), "repo",
                                                "## Z repo (kopia przy wdrożeniu)\n" + "\n".join(linie_repo)))
    # tożsamość Jarva (jarvo/*) z plików buildu i lustra pamięci profili floty (po treści pliku: synchronizuj_pamiec)
    raport["tozsamosc"] = len(zasiej_tozsamosc(sk, tozsamosc)) + zasiej_mape(sk, tozsamosc, fleet, profile, agenci_meta)
    if profile and Path(profile).is_dir():
        agenci = [a["name"] for a in (fleet or {}).get("agents", [])] or [PROFIL_TOZSAMOSCI]
        for agent in agenci:
            s = synchronizuj_pamiec(sk, Path(profile) / agent, agent, (agenci_meta.get(agent) or {}).get("marka", ""))
            raport["pamiec"] += s["wpisow"]
            raport["tozsamosc"] += len(s["notatki"])
    odswiez_hub_jarva(sk, (agenci_meta.get(PROFIL_TOZSAMOSCI) or {}).get("orzeczenia", ""))
    if not (sk.root / "INDEX.md").exists():
        (sk.root / "INDEX.md").write_text("# Indeks skarbca\n\n_Pusty do pierwszego `wiedza.py indeksuj`._\n", encoding="utf-8",
                                          newline="\n")
    if not (sk.root / "LINT.md").exists():
        (sk.root / "LINT.md").write_text("# Lint skarbca\n\n_Jeszcze nie uruchomiono `wiedza.py lint`._\n", encoding="utf-8",
                                         newline="\n")
    sk.dopisz_log("zasiew", f"huby: {raport['huby']} folderów, {raport['agenci']} agentów; skille: {raport['skille']} zmienionych; "
                            f"docs repo: {raport['docs']} plików; pliki profili: {raport['repo']} zmienionych; "
                            f"księga błędów: {raport['bledy']} nowych albo wymienionych; tożsamość: {raport['tozsamosc']} notatek "
                            f"zmienionych; pamięć: {raport['pamiec']} nowych wpisów do kompilacji"
                            + (f"; do archiwum (agent wycofany z floty): {', '.join(raport['archiwum'])}" if raport["archiwum"] else ""))
    raport["git"] = sk.git_init() and sk.punkt_zapisu("zasiew skarbca")
    return raport


# ------------------------------------------------------------------------------------------------ szkice i orzeczenia

def zapisz_szkic(sk: Skarbiec, typ: str, tytul: str, tresc: str, zrodlo: str, agent: str = "", tagi: list | None = None,
                 linki: list | None = None, skad: str = "", marka: str = "", sygnatury_bledu: list | None = None) -> str:
    """Szkic w skrzynka/. `marka`: szkic agenta biznesowego (kompilacja kładzie notatki tylko w `brands/<marka>/` albo
    `agenci/<agent>/`). Typ `blad` (księga błędów) wymaga sygnatur (dosłowne fragmenty komunikatu albo `/wyrażenie/`)
    i akapitu „Jak poprawnie:” w treści."""
    if typ not in TYPY - {"hub", "orzeczenia"}:
        raise ValueError(f"typ spoza schematu: {typ} (dozwolone: {', '.join(sorted(TYPY - {'hub', 'orzeczenia'}))})")
    if not tytul.strip() or not tresc.strip():
        raise ValueError("szkic musi mieć tytuł i treść")
    if not zrodlo.strip():
        raise ValueError("szkic musi mieć źródło (karta, rozmowa, plik, adres)")
    syg = sygnatury({"sygnatury": list(sygnatury_bledu or [])})
    sekret = zawiera_sekret("\n".join([tytul, tresc, *syg]))
    if sekret:
        raise ValueError(f"szkic zawiera sekret ({sekret}); sekrety nigdy nie trafiają do skarbca")
    if typ == "blad":
        if not syg:
            raise ValueError("szkic błędu (typ blad) musi mieć `sygnatury`: dosłowne fragmenty komunikatu z wyniku narzędzia "
                             "(np. „We couldn't verify you're human”) albo wyrażenie `/…/`")
        zle = [s for s in syg if wzorzec_sygnatury(s) is None]
        if zle:
            raise ValueError(f"błędne wyrażenie w sygnaturach: {zle[0]} (popraw albo podaj dosłowny fragment)")
        if not jak_poprawnie(tresc):
            raise ValueError("szkic błędu (typ blad) ma treść w trzech akapitach: „Objaw: …”, „Przyczyna: …”, "
                             "„Jak poprawnie: …” (konkretny następny krok)")
    elif syg:
        raise ValueError("`sygnatury` ma tylko szkic błędu (typ blad)")
    skrot = hashlib.sha1(f"{tytul}{tresc}{dzis()}".encode()).hexdigest()[:6]
    rel = f"skrzynka/{dzis()}-{slug_ascii(agent or 'agent', 16)}-{slug_ascii(tytul)}-{skrot}"
    fm = {"szkic": True, "typ": typ, "tytul": tytul.strip(), "agent": agent or "", "zrodlo": zrodlo.strip(), "utworzono": dzis(),
          "skad": skad or "", "tagi": tagi or [], "linki": linki or []}
    if syg:
        fm["sygnatury"] = syg
    if marka:
        fm["marka"] = marka
    sk.zapisz_plik(rel, sklej(fm, f"# {tytul.strip()}\n\n{tresc.strip()}\n"))
    return rel


def dodaj_orzeczenie(sk: Skarbiec, kogo: str, tresc: str, zrodlo: str) -> str:
    tresc = " ".join(tresc.split())
    if not tresc or len(tresc) > 400:
        raise ValueError("orzeczenie to jedno zdanie do 400 znaków")
    sekret = zawiera_sekret(tresc)
    if sekret:
        raise ValueError(f"orzeczenie zawiera sekret ({sekret})")
    kogo = kogo.strip().lower()
    if kogo.startswith("marki/"):
        rel, etykieta = "orzeczenia/marki/" + nazwa_pliku(kogo[6:]).replace(" ", "-"), kogo[6:]
    else:
        meta = {}
        try:
            meta = json.loads((sk.stan / "wiedza-agenci.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        if kogo in meta:                       # pełna nazwa profilu (jarvo-web) → plik po krótkiej nazwie
            rel, etykieta = meta[kogo]["orzeczenia"], meta[kogo]["short"].lower()
        else:
            rel, etykieta = "orzeczenia/" + nazwa_pliku(kogo).replace(" ", "-"), kogo
    if not sk.istnieje(rel):
        sk.zapisz_plik(rel, sklej(_hub_frontmatter("orzeczenia", "człowiek"),
                                  f"# Orzeczenia: {etykieta}\n\n**Korekty od użytkownika, jedna datowana linia każda.**\n\n"
                                  f"## Powiązane\n- hub: [[orzeczenia/_hub-orzeczenia|Orzeczenia]]\n\n## Linie\n"))
    linia = f"- {dzis()} · [{etykieta}] {tresc.rstrip('.')}. (źródło: {' '.join(zrodlo.split()) or 'człowiek'})"
    p = sk.plik(rel)
    text = p.read_text(encoding="utf-8")
    fm, body = podziel(text)
    fm["zmieniono"] = dzis()
    sk.zapisz_plik(rel, sklej(fm, body.rstrip("\n") + "\n" + linia + "\n"))
    sk.dopisz_log("orzeczenie", f"{rel}: {tresc[:80]}")
    sk.punkt_zapisu(f"orzeczenie: {etykieta}")
    return linia


# ------------------------------------------------------------------------------------------------ lint

def lint(sk: Skarbiec, ix: Indeks) -> dict:
    """Zdrowie skarbca bez modelu. Błędy = do naprawy przez kompilację/człowieka; ostrzeżenia = warto; informacje = wiedzieć."""
    ix.odswiez()
    bledy, ostrz, info = [], [], []
    zbior, znane = sk.mapa()
    try:
        skrypty_repo = set(json.loads((sk.stan / "wiedza-kod.json").read_text(encoding="utf-8"))["skrypty"])
    except (OSError, ValueError, KeyError):
        skrypty_repo = None                        # skarbiec bez zasiewu z buildu: nie ma z czym porównać
    notatki = {r["sciezka"]: r for r in ix.notatki()}
    linki = ix.linki()
    we_reczne: dict[str, int] = {}
    for l in linki:
        if l["rozwiazany"] and not l["auto"]:
            we_reczne[l["do_"]] = we_reczne.get(l["do_"], 0) + 1
    for l in linki:
        if not l["rozwiazany"] and not l["z"].startswith(("zrodla/",)):
            bledy.append(f"martwy link `[[{l['do_']}]]` w [[{l['z']}]]")
    tytuly: dict[str, list[str]] = {}
    for rel, r in notatki.items():
        if rel.startswith(("zrodla/", "skrzynka/")):
            continue
        nazwa = rel.rsplit("/", 1)[-1]
        zle = sorted(set(nazwa) & ZAKAZANE_W_NAZWIE)
        if zle:
            bledy.append(f"nazwa pliku z zakazanymi znakami {''.join(zle)}: [[{rel}]]")
        n = sk.wczytaj(rel)
        sekret = zawiera_sekret(n.tresc)
        if sekret:
            bledy.append(f"sekret w treści ({sekret}): [[{rel}]]")
        zly = zly_naglowek(sk.plik(rel).read_text(encoding="utf-8", errors="replace")) if sk.plik(rel).exists() else ""
        if zly:
            bledy.append(f"frontmatter nie jest poprawnym YAML (wartość w cudzysłów): `{zly[:80]}` w [[{rel}]]")
        if rel.startswith(ARCHIWUM + "/") or n.typ == "tozsamosc":
            continue          # archiwum (historia) i tożsamość generowana z repo i pamięci: tylko nazwa, sekrety, YAML i martwe linki
        if skrypty_repo is not None and rel.startswith(O_FLOCIE) and not r["hub"]:
            for nazwa_s in sorted({m.group(1) for m in SKRYPT_RE.finditer(n.tresc)} - skrypty_repo):
                ostrz.append(f"nieaktualna wobec repo: skryptu `{nazwa_s}` nie ma we flocie: [[{rel}]]")
        wlasny_format = rel.startswith(BEZ_FRONTMATTERU) and not r["hub"]
        if not wlasny_format:
            brak = [k for k in WYMAGANE if not n.fm.get(k)]
            if brak:
                bledy.append(f"brak kluczy {', '.join(brak)}: [[{rel}]]")
            if n.typ and n.typ not in TYPY:
                bledy.append(f"typ spoza schematu `{n.typ}`: [[{rel}]]")
            st = str(n.fm.get("status") or "")
            if st and st not in STATUSY:
                bledy.append(f"status spoza schematu `{st}`: [[{rel}]]")
            for k in ("utworzono", "zmieniono", "wazne_do"):
                v = n.fm.get(k)
                if v and not DATA_RE.match(str(v)):
                    bledy.append(f"data `{k}: {v}` nie jest RRRR-MM-DD: [[{rel}]]")
            if n.typ not in BEZ_ZRODLA and not n.fm.get("zrodlo"):
                bledy.append(f"brak źródła (`zrodlo:`): [[{rel}]]")
            if st == "sprzeczna":
                info.append(f"sprzeczność do rozstrzygnięcia: [[{rel}]]")
            if st == "do-sprawdzenia":
                info.append(f"do sprawdzenia: [[{rel}]]")
            wd = str(n.fm.get("wazne_do") or "")
            if wd and DATA_RE.match(wd) and wd < dzis():
                ostrz.append(f"przeterminowana (`wazne_do: {wd}`): [[{rel}]]")
            limit = MAX_SLOW.get(n.typ, DOMYSLNY_MAX_SLOW)
            if n.slowa > limit:
                ostrz.append(f"za długa ({n.slowa} słów, limit {limit}): [[{rel}]]")
            if not r["hub"] and not n.streszczenie:
                ostrz.append(f"bez streszczenia (pierwszy akapit po tytule): [[{rel}]]")
            if not r["hub"] and rel.startswith(KSIEGA + "/"):
                bledy_k, ostrz_k = lint_bledu(n)
                bledy += [f"{b}: [[{rel}]]" for b in bledy_k]
                ostrz += [f"{o}: [[{rel}]]" for o in ostrz_k]
        if not r["hub"] and not wlasny_format and n.typ not in BEZ_ZRODLA and rel != "fleet/lekcje":
            reczne = [(c, a) for c, _e, a in n.linki if not a]
            cele = [sk.rozwiaz(c, znane, zbior) for c, _a in reczne]
            hub_folderu = f"{n.folder}/{HUBY.get(n.folder, ('', ''))[0]}" if n.folder in HUBY else ""
            if hub_folderu and hub_folderu not in cele and not any(c and c.startswith(n.folder + "/") and c.rsplit("/", 1)[-1].startswith("_hub-") for c in cele):
                ostrz.append(f"bez linku do huba folderu: [[{rel}]]")
            if not any(c and c.split("/", 1)[0] != n.folder for c in cele):
                ostrz.append(f"bez linku do innego folderu: [[{rel}]]")
            if we_reczne.get(rel, 0) == 0:
                ostrz.append(f"sierota (linkuje tylko lista huba): [[{rel}]]")
        if not r["hub"]:
            klucz = " ".join(sorted(set(re.findall(r"\w+", bez_ogonkow(n.tytul).lower())) - STOPSLOWA))
            if klucz:
                tytuly.setdefault(klucz, []).append(rel)
    for klucz, rels in tytuly.items():
        if len(rels) > 1:
            ostrz.append("duplikat tytułu: " + ", ".join(f"[[{r}]]" for r in rels))
    # duplikaty przybliżone: ≥ 80% wspólnych słów tytułu (≥ 3 słowa)
    slowa_t = {k: set(k.split()) for k in tytuly if len(k.split()) >= 3}
    odwrotny: dict[str, list[str]] = {}
    for k, ws in slowa_t.items():
        for w in ws:
            odwrotny.setdefault(w, []).append(k)
    pary = set()
    for k, ws in slowa_t.items():
        kand: dict[str, int] = {}
        for w in ws:
            for k2 in odwrotny[w]:
                if k2 != k:
                    kand[k2] = kand.get(k2, 0) + 1
        for k2, wspolne in kand.items():
            if wspolne >= 2 and wspolne / len(ws | slowa_t[k2]) >= 0.8:
                pary.add(tuple(sorted((k, k2))))
    for k, k2 in sorted(pary):
        ostrz.append(f"podobne tytuły: [[{tytuly[k][0]}]] i [[{tytuly[k2][0]}]]")
    for folder, (hub, tytul) in HUBY.items():
        if folder and folder not in ("orzeczenia", TOZSAMOSC, ARCHIWUM):
            ile = sum(1 for rel in notatki if rel.startswith(folder + "/") and not notatki[rel]["hub"])
            if ile < 3:
                info.append(f"cienki folder `{folder}/` ({ile} notatek)")
    szkice = [p for p in (sk.root / "skrzynka").glob("*.md")]
    stare = [p.name for p in szkice if (dt.datetime.now().timestamp() - p.stat().st_mtime) > 7 * 86400]
    if szkice:
        info.append(f"szkice w skrzynce: {len(szkice)}" + (f" (starsze niż 7 dni: {len(stare)})" if stare else ""))
    ostrz += nazwy_nieprzenosne(sk)
    raport = {"bledy": bledy, "ostrzezenia": ostrz, "informacje": info, "notatek": len([r for r in notatki if not r.startswith(POZA_WYSZUKIWANIEM)]),
              "data": dzis()}
    linie = [f"# Lint skarbca ({dzis()})", "", f"Notatek: {raport['notatek']} · błędy: {len(bledy)} · ostrzeżenia: {len(ostrz)} · informacje: {len(info)}", ""]
    for naglowek, lista in (("Błędy", bledy), ("Ostrzeżenia", ostrz), ("Informacje", info)):
        linie += [f"## {naglowek}", ""] + ([f"- {x}" for x in lista] or ["- brak"]) + [""]
    sk.zapisz_plik("LINT", "\n".join(linie))        # zapis atomowy: Obsidian może mieć LINT.md otwarty
    # podsumowanie dla `jarvo doctor` (doctor sam niczego nie zapisuje); ta sama treść = bez zapisu, więc drugi przebieg
    # wdrożenia niczego nie zmienia (data dnia zamiast znacznika czasu)
    tresc = json.dumps({"data": dzis(), "notatek": raport["notatek"], "bledy": len(bledy), "ostrzezenia": len(ostrz),
                        "informacje": len(info), "pierwsze_bledy": bledy[:5]}, ensure_ascii=False, indent=1) + "\n"
    with contextlib.suppress(OSError):
        cel = sk.stan / LINT_JSON
        if not cel.is_file() or cel.read_text(encoding="utf-8") != tresc:
            sk.stan.mkdir(parents=True, exist_ok=True)
            tmp = sk.stan / f"{LINT_JSON}.{os.getpid()}.tmp"
            tmp.write_text(tresc, encoding="utf-8", newline="\n")
            zamien_plik(tmp, cel)
    return raport


def nazwy_nieprzenosne(sk: Skarbiec) -> list[str]:
    """Ostrzeżenia K07 dla nazw, które nie przejdą na inny system (skarbiec przenosimy z kontenera na Windows i macOS,
    a Obsidian otwiera go na każdym): nazwy urządzeń Windows, kropka albo spacja na końcu, zapis spoza NFC, nazwy
    różniące się tylko wielkością liter w jednym katalogu i pełna ścieżka dłuższa niż MAX_SCIEZKI. Nazwy z dysku, nie
    z indeksu (na macOS indeks ma już NFC), bez katalogów z kropką (.git, .obsidian)."""
    out: list[str] = []
    for katalog, podkatalogi, pliki in os.walk(sk.root):
        podkatalogi[:] = sorted(d for d in podkatalogi if not d.startswith("."))
        baza = Path(katalog)
        rel_kat = baza.relative_to(sk.root).as_posix()
        wg_liter: dict[str, list[str]] = {}
        for nazwa in sorted([*podkatalogi, *(p for p in pliki if p.endswith(".md"))]):
            rel = nazwa if rel_kat == "." else f"{rel_kat}/{nazwa}"
            wg_liter.setdefault(unicodedata.normalize("NFC", nazwa).casefold(), []).append(rel)
            powod = nieprzenosna(nazwa)              # pełna nazwa z dysku (katalog albo plik z .md)
            if powod:
                out.append(f"nazwa nieprzenośna ({powod}): `{rel}`")
            elif nazwa.endswith(".md") and len(str(baza / nazwa)) > MAX_SCIEZKI:
                out.append(f"ścieżka dłuższa niż {MAX_SCIEZKI} znaków ({len(str(baza / nazwa))}; Windows bez długich ścieżek "
                           f"jej nie otworzy): `{rel}`")
        for rels in wg_liter.values():
            if len(rels) > 1:
                out.append("nazwy różnią się tylko wielkością liter (Windows i macOS widzą jeden plik): "
                           + ", ".join(f"`{r}`" for r in rels))
    return out


# ------------------------------------------------------------------------------------------------ status

def status(sk: Skarbiec, ix: Indeks) -> dict:
    ix.odswiez()
    wg_folderu: dict[str, int] = {}
    for r in ix.notatki():
        wg_folderu[r["folder"] or "/"] = wg_folderu.get(r["folder"] or "/", 0) + 1
    szkice = len(list((sk.root / "skrzynka").glob("*.md"))) if (sk.root / "skrzynka").is_dir() else 0
    log = sk.root / "LOG.md"
    ostatni = ""
    if log.exists():
        wpisy = re.findall(r"^## \[(\d{4}-\d{2}-\d{2})\] (\w+)", log.read_text(encoding="utf-8"), re.M)
        ostatni = " ".join(wpisy[-1]) if wpisy else ""
    def z_json(nazwa: str) -> dict:
        try:
            d = json.loads((sk.stan / nazwa).read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}
    komp = z_json("wiedza-kompilacja.json")
    return {"skarbiec": sk.root.as_posix(), "indeks": (sk.stan / "wiedza.db").as_posix(), "wg_folderu": wg_folderu, "szkice": szkice,
            "linki": ix.db.execute("SELECT COUNT(*) FROM linki WHERE rozwiazany = 1").fetchone()[0],
            "git": (sk.root / ".git").exists(), "ostatni_wpis": ostatni,
            "kompilacja": {"ostatnia": komp.get("ostatnia") or 0, "data": komp.get("data") or "",
                           "raport": komp.get("raport") or {}},
            "lint": z_json(LINT_JSON), "blokada": znacznik_blokady(sk.stan), "wektory": stan_wektorow(sk, ix)}


def stan_wektorow(sk: Skarbiec, ix: Indeks) -> dict:
    """Wektory w indeksie wg modelu i usługa (state/wektory.json, bez zapytania do niej): dla statusu i doctora."""
    klient = KlientWektorow(sk.stan)
    modele = {r[0]: r[1] for r in ix.db.execute("SELECT model, count(*) FROM wektory GROUP BY model")}
    notatek = sum(1 for r in ix.db.execute("SELECT sciezka FROM pliki") if not r[0].startswith(POZA_WYSZUKIWANIEM))
    return {"usluga": klient.dostepny, "model": klient.model, "powod": "" if klient.dostepny else klient.blad,
            "modele": modele, "wektorow": modele.get(klient.model, 0) if klient.model else sum(modele.values()),
            "notatek": notatek}


def opis_wektorow(w: dict) -> str:
    """Linia dla `indeksuj` i `zasiej` z wyniku Indeks.odswiez_wektory."""
    if not w["model"]:
        return "wektory: usługa wektorów nie działa, bez zmian (przypomnienia słowami; brakujące wektory nadrobi usługa po starcie)"
    return (f"✓ wektory: {w['wektorow']}/{w['notatek']} notatek ({w['nowe']} osadzonych, {w['usuniete']} usuniętych)"
            + (" · przerwane: usługa przestała odpowiadać, reszta następnym razem" if w["przerwane"] else ""))


# ------------------------------------------------------------------------------------------------ CLI

def main(argv: list[str] | None = None) -> int:
    utf8_wyjscie()
    ap = argparse.ArgumentParser(description="Skarbiec wiedzy floty Jarvo (docs/WIEDZA.md)")
    ap.add_argument("--skarbiec", default=DOMYSLNY_SKARBIEC, help="katalog skarbca (JARVO_KNOWLEDGE_DIR)")
    ap.add_argument("--stan", default=None, help="katalog na indeks (JARVO_STATE_DIR, domyślnie <skarbiec>/../state)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    z = sub.add_parser("zasiej", help="katalogi, huby, INDEX, LOG, orzeczenia, docs repo, git init")
    z.add_argument("--fleet", help="fleet.json z buildu (agenci, skille, skrypty)")
    z.add_argument("--docs", help="katalog docs/ repo → zrodla/jarvo-repo/")
    z.add_argument("--repo", help="wiedza/repo z buildu (pliki profili, materiały skilli, spis źródeł) → zrodla/jarvo-repo/")
    z.add_argument("--schema", default=str(Path(__file__).with_name("SCHEMA.md")), help="SCHEMA.md do skopiowania")
    z.add_argument("--bledy", help="wiedza/bledy z repo: notatki księgi błędów do bledy/ (tylko nowe, istniejących nie "
                                   "rusza, usunięta nie wraca)")
    z.add_argument("--tozsamosc", help="tożsamość Jarva z buildu (build/wiedza/tozsamosc: SOUL, ZASADY, KRYTYCZNE, MAPA) → "
                                       "jarvo/; domyślnie katalog `tozsamosc` obok --repo")
    z.add_argument("--profile", help="katalog profili Hermesa (<dane>/profiles): lustra pamięci; domyślnie <skarbiec>/../../profiles")
    ar = sub.add_parser("archiwizuj", help="notatki albo katalogi do archiwum/ (linki do następcy albo do archiwum)")
    ar.add_argument("sciezki", nargs="+")
    ar.add_argument("--powod", required=True)
    ar.add_argument("--zastapiona-przez", default="", help="notatka-następca: linki i stara ścieżka prowadzą do niej")
    pr = sub.add_parser("przenies", help="notatka do innego folderu (ten sam tytuł), linki przepisane")
    pr.add_argument("sciezka")
    pr.add_argument("folder")
    sz = sub.add_parser("streszczenie", help=f"blok STRESZCZENIE huba (do {MAX_STRESZCZENIA_HUBA} znaków)")
    sz.add_argument("hub", help="ścieżka huba albo folder (user, agenci/jarvo-web)")
    zr = sz.add_mutually_exclusive_group(required=True)
    zr.add_argument("--plik")
    zr.add_argument("--tekst")
    sub.add_parser("napraw-huby", help="linia `- hub:` każdej notatki wskazuje hub jej folderu (naprawa po przenosinach)")
    pm = sub.add_parser("pamiec", help="lustro pamięci Hermesa (po treści plików): notatki Jarva i szkice nowych wpisów")
    pm.add_argument("--profil", default=None, help="katalog profilu (domyślnie <skarbiec>/../../profiles/jarvo)")
    pm.add_argument("--agent", default=PROFIL_TOZSAMOSCI)
    i = sub.add_parser("indeksuj", help="indeks FTS5 + INDEX.md + listy hubów")
    i.add_argument("--pelny", action="store_true")
    s = sub.add_parser("szukaj", help="wyszukiwanie")
    s.add_argument("zapytanie")
    s.add_argument("--limit", type=int, default=5)
    s.add_argument("--folder")
    s.add_argument("--agent")
    s.add_argument("--zrodla", action="store_true", help="także zrodla/ i skrzynka/")
    s.add_argument("--silnik", choices=SILNIKI, default=SILNIK, help="wektory (domyślnie), hybryda (RRF z BM25) albo slowa")
    s.add_argument("--json", action="store_true")
    c = sub.add_parser("czytaj", help="cała notatka")
    c.add_argument("sciezka")
    c.add_argument("--json", action="store_true")
    w = sub.add_parser("zapisz", help="szkic do skrzynki")
    w.add_argument("--typ", required=True)
    w.add_argument("--tytul", required=True)
    w.add_argument("--tresc", help="treść (albo na stdin)")
    w.add_argument("--zrodlo", required=True)
    w.add_argument("--agent", default="")
    w.add_argument("--tagi", default="")
    w.add_argument("--linki", default="")
    w.add_argument("--skad", default="")
    w.add_argument("--sygnatura", action="append", default=[],
                   help="typ blad: dosłowny fragment komunikatu albo /wyrażenie/ (można kilka razy)")
    o = sub.add_parser("orzeczenie", help="jedna datowana linia korekty od człowieka")
    o.add_argument("--kogo", required=True, help="wszyscy | <agent> | marki/<marka>")
    o.add_argument("--tresc", required=True)
    o.add_argument("--zrodlo", default="człowiek")
    l = sub.add_parser("lint", help="raport LINT.md")
    l.add_argument("--json", action="store_true")
    l.add_argument("--strict", action="store_true", help="kod 1 przy błędach")
    g = sub.add_parser("graf", help="węzły i linki jako JSON")
    sub.add_parser("cofnij", help="cofa ostatni punkt zapisu git")
    st = sub.add_parser("status")
    st.add_argument("--json", action="store_true")
    oc = sub.add_parser("ocena", help="trafność przypomnień na zestawie pytań: hit@5, MRR, czas (to samo szukanie co wtyczka)")
    oc.add_argument("plik", help='JSON: [{"pytanie": "...", "wzor": ["ścieżka notatki", ...]}]')
    oc.add_argument("--limit", type=int, default=5, help="ile notatek przypomnienia (k w hit@k)")
    oc.add_argument("--silnik", choices=SILNIKI, default=SILNIK,
                    help="wektory (domyślnie), hybryda (RRF słów i wektorów), slowa (BM25); bez usługi wektorów zawsze slowa")
    oc.add_argument("--pomin-tozsamosc", action="store_true",
                    help="jak przypomnienie Jarva: bez notatek tożsamości (ma je w prompcie)")
    oc.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    sk = Skarbiec(a.skarbiec, a.stan)
    if a.cmd == "zasiej":
        fleet = json.loads(Path(a.fleet).read_text(encoding="utf-8")) if a.fleet else None
        toz = Path(a.tozsamosc) if a.tozsamosc else (Path(a.repo).parent / "tozsamosc" if a.repo else None)
        profile = Path(a.profile) if a.profile else sk.root.parent.parent / "profiles"
        r = zasiej(sk, fleet, Path(a.docs) if a.docs else None, Path(a.schema) if a.schema else None,
                   Path(a.repo) if a.repo else None, Path(a.bledy) if a.bledy else None, toz, profile)
        ix = Indeks(sk)
        ix.odswiez(pelny=True)
        n = zbuduj_index(sk, ix)
        odswiez_listy_hubow(sk, ix)
        ix.odswiez()
        sk.punkt_zapisu("zasiew skarbca: indeks")
        print(f"✓ zasiew: {r['huby']} hubów folderów, {r['agenci']} hubów agentów, {r['skille']} skilli zmienionych, {r['docs']} docs, "
              f"księga błędów {r['bledy']} nowych albo wymienionych, tożsamość {r['tozsamosc']} notatek, pamięć {r['pamiec']} "
              f"nowych wpisów, do archiwum: {', '.join(r['archiwum']) or 'nic'}, indeks {n} notatek, git: {'tak' if r['git'] else 'nie'}")
        print(opis_wektorow(ix.odswiez_wektory(KlientWektorow(sk.stan, WEKTORY_CZAS_ZAPISU_S))))
        ix.zamknij()
        return 0
    if not sk.root.is_dir():
        print(f"✗ brak skarbca {sk.root} (najpierw `zasiej`)", file=sys.stderr)
        return 2
    if a.cmd in ("archiwizuj", "przenies", "streszczenie", "napraw-huby"):
        try:
            if a.cmd == "napraw-huby":
                r = porzadki(sk, "naprawa", "naprawa linii hub w notatkach", lambda: napraw_huby(sk))
                print("\n".join(f"  - {n}" for n in r.pop("notatki")))
            elif a.cmd == "archiwizuj":
                opis = f"archiwum: {', '.join(a.sciezki)} ({' '.join(a.powod.split())[:120]})"
                r = porzadki(sk, "archiwum", opis, lambda: archiwizuj(sk, a.sciezki, a.powod, a.zastapiona_przez))
            elif a.cmd == "przenies":
                opis = f"przeniesienie: {a.sciezka} → {a.folder}/"
                r = porzadki(sk, "przeniesienie", opis, lambda: przenies(sk, a.sciezka, a.folder))
            else:
                tekst = Path(a.plik).read_text(encoding="utf-8") if a.plik else a.tekst
                r = porzadki(sk, "streszczenie", f"streszczenie huba {a.hub}",
                             lambda: {"hub": streszczenie(sk, a.hub, tekst)})
        except (ValueError, OSError, RuntimeError) as e:
            print(f"✗ {e}", file=sys.stderr)
            return 3
        print("✓ " + " · ".join(f"{k}: {v}" for k, v in r.items()))
        return 0
    if a.cmd == "pamiec":
        profil = Path(a.profil) if a.profil else sk.root.parent.parent / "profiles" / a.agent
        r = synchronizuj_pamiec(sk, profil, a.agent)
        print(f"✓ pamięć {a.agent}: zmienione {', '.join(r['zmienione']) or 'nic'}, {r['wpisow']} nowych wpisów do kompilacji, "
              f"notatki: {', '.join(r['notatki']) or 'bez zmian'}" + (" (stan zajęty, spróbuj za chwilę)" if r.get("zajete") else ""))
        return 0
    ix = Indeks(sk)
    try:
        if a.cmd == "indeksuj":
            r = ix.odswiez(pelny=a.pelny)
            n = zbuduj_index(sk, ix)
            h = odswiez_listy_hubow(sk, ix)
            ix.odswiez()
            print(f"✓ indeks: {r['pliki']} plików ({r['nowe']} nowych, {r['zmienione']} zmienionych, {r['usuniete']} usuniętych), INDEX.md: {n} notatek, huby odświeżone: {h}")
            print(opis_wektorow(ix.odswiez_wektory(KlientWektorow(sk.stan, WEKTORY_CZAS_ZAPISU_S))))
        elif a.cmd == "szukaj":
            ix.odswiez()
            wyn = ix.szukaj(a.zapytanie, limit=a.limit, folder=a.folder, agent=a.agent, zrodla=a.zrodla,
                            wektory=KlientWektorow(sk.stan, WEKTORY_CZAS_NARZEDZIA_S), silnik=a.silnik)
            if a.json:
                print(json.dumps(wyn, ensure_ascii=False, indent=1))
            elif not wyn:
                print("(nic nie znaleziono)")
            for r in ([] if a.json else wyn):
                print(f"- {r['sciezka']} · {r['tytul']}" + (f" · {r['streszczenie'][:110]}" if r["streszczenie"] else ""))
        elif a.cmd == "czytaj":
            try:
                n = sk.wczytaj(a.sciezka)
            except (ValueError, FileNotFoundError) as e:
                print(f"✗ {e}", file=sys.stderr)
                return 2
            if a.json:
                print(json.dumps({"sciezka": n.sciezka, "tytul": n.tytul, "fm": n.fm, "tresc": n.tresc}, ensure_ascii=False, indent=1))
            else:
                print(sk.plik(a.sciezka).read_text(encoding="utf-8"))
        elif a.cmd == "zapisz":
            tresc = a.tresc if a.tresc is not None else sys.stdin.read()
            try:
                rel = zapisz_szkic(sk, a.typ, a.tytul, tresc, a.zrodlo, a.agent, [t.strip() for t in a.tagi.split(",") if t.strip()],
                                   [x.strip() for x in a.linki.split(",") if x.strip()], a.skad, sygnatury_bledu=a.sygnatura)
            except ValueError as e:
                print(f"✗ {e}", file=sys.stderr)
                return 3
            print(f"✓ szkic: {rel}")
        elif a.cmd == "orzeczenie":
            try:
                linia = dodaj_orzeczenie(sk, a.kogo, a.tresc, a.zrodlo)
            except ValueError as e:
                print(f"✗ {e}", file=sys.stderr)
                return 3
            print(f"✓ orzeczenie: {linia}")
        elif a.cmd == "lint":
            r = lint(sk, ix)
            if a.json:
                print(json.dumps(r, ensure_ascii=False, indent=1))
            else:
                print(f"lint: {r['notatek']} notatek · błędy: {len(r['bledy'])} · ostrzeżenia: {len(r['ostrzezenia'])} · informacje: {len(r['informacje'])} → LINT.md")
                for b in r["bledy"][:20]:
                    print(f"  ✗ {b}")
            if a.strict and r["bledy"]:
                return 1
        elif a.cmd == "graf":
            ix.odswiez()
            print(json.dumps(ix.graf(), ensure_ascii=False))
        elif a.cmd == "cofnij":
            print(sk.cofnij())
        elif a.cmd == "status":
            r = status(sk, ix)
            if a.json:
                print(json.dumps(r, ensure_ascii=False, indent=1))
            else:
                print(f"skarbiec: {r['skarbiec']} · notatek: {sum(r['wg_folderu'].values())} · linków: {r['linki']} · szkiców: {r['szkice']} · git: {'tak' if r['git'] else 'nie'} · ostatni wpis: {r['ostatni_wpis'] or '-'}")
                for f, n in sorted(r["wg_folderu"].items()):
                    print(f"  {f:12} {n}")
                wek = r["wektory"]
                print(f"wektory: {wek['wektorow']}/{wek['notatek']} notatek · usługa: "
                      + (f"działa ({wek['model']})" if wek["usluga"] else f"nie działa ({wek['powod']}; przypomnienia słowami)"))
        elif a.cmd == "ocena":
            try:
                wektory = None if a.silnik == "slowa" else KlientWektorow(sk.stan)
                r = ocena(ix, json.loads(Path(a.plik).read_text(encoding="utf-8")), limit=a.limit, wektory=wektory,
                          silnik=a.silnik, pomin_tozsamosc=a.pomin_tozsamosc)
            except (OSError, ValueError) as e:
                print(f"✗ {e}", file=sys.stderr)
                return 2
            if a.json:
                print(json.dumps(r, ensure_ascii=False, indent=1))
            else:
                print(f"ocena: {r['pytan']} pytań · hit@{r['k']}: {r['trafione']}/{r['pytan']} ({r['hit_at_k']:.3f}) · MRR {r['mrr']:.3f} · "
                      f"ms: mediana {r['ms_mediana']}, max {r['ms_max']} · silnik: "
                      + ", ".join(f"{s} {n}" for s, n in sorted(r["silniki"].items())))
                for p in r["pytania"]:
                    if not p["pozycja"]:
                        print(f"  ✗ {p['pytanie'][:80]} → {', '.join(p['wyniki']) or '(nic)'}")
    finally:
        ix.zamknij()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
