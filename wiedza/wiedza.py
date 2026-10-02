#!/usr/bin/env python3
"""Skarbiec wiedzy floty Jarvo (drugi mózg): narzędzie bez zależności poza biblioteką standardową.

Skarbiec to katalog zwykłych plików Markdown (projekt: docs/WIEDZA.md). Ten skrypt:
  zasiej      katalogi, SCHEMA.md, huby (z fleet.json), INDEX, LOG, orzeczenia, docs repo → zrodla/jarvo-repo, git init
  indeksuj    indeks FTS5 (state/wiedza.db), INDEX.md i listy w hubach z plików (0 tokenów, deterministycznie)
  szukaj      wyszukiwanie po polsku (ogonki bez znaczenia), wynik: ścieżka · streszczenie
  czytaj      cała notatka
  zapisz      szkic do skrzynka/ (agent nie pisze notatek sam: zasada 9 schematu)
  orzeczenie  jedna datowana linia w orzeczenia/<kogo>.md (tylko od człowieka)
  lint        raport LINT.md (martwe linki, sieroty, brak źródła, sekrety, duplikaty, przeterminowane…)
  graf        węzły i linki jako JSON (zakładka „Wiedza”)
  cofnij      cofa ostatni punkt zapisu git
  status      liczby

Używane przez wtyczkę jarvo-wiedza (import), rutyny (CLI), testy (tests/test_wiedza.py).
Domyślne ścieżki: JARVO_KNOWLEDGE_DIR (albo /opt/data/jarvo/knowledge) i JARVO_STATE_DIR (albo <skarbiec>/../state).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

DOMYSLNY_SKARBIEC = os.environ.get("JARVO_KNOWLEDGE_DIR", "/opt/data/jarvo/knowledge")

FOLDERY = ("zrodla/rozmowy", "zrodla/karty", "zrodla/pliki", "zrodla/jarvo-repo", "skrzynka/zrobione", "agenci",
           "projekty", "brands", "user", "podmioty", "pojecia", "orzeczenia/marki", "rozmowy", "fleet")
# folder → (nazwa pliku huba, tytuł)
HUBY = {"": ("_hub-skarbiec", "Skarbiec wiedzy"), "agenci": ("_hub-agenci", "Agenci"), "projekty": ("_hub-projekty", "Projekty"),
        "brands": ("_hub-marki", "Marki"), "user": ("_hub-ty", "Ty"), "podmioty": ("_hub-podmioty", "Podmioty"),
        "pojecia": ("_hub-pojecia", "Pojęcia"), "orzeczenia": ("_hub-orzeczenia", "Orzeczenia"), "rozmowy": ("_hub-rozmowy", "Rozmowy")}
OPISY_FOLDEROW = {
    "agenci": "Jeden katalog na agenta: hub (rola, skille, skrypty z `fleet.yaml`) i notatki o tym, czego się nauczył.",
    "projekty": "Jedna notatka na misję albo projekt: stan, decyzje, wyniki (linki do plików), marka, agenci.",
    "brands": "Brand kity (`brands/<marka>/`): kolory, fonty, ton. Orzeczenia marki: `orzeczenia/marki/<marka>.md`.",
    "user": "Kim jesteś, czym się zajmujesz, oferta, klienci, głos marki (`user/USER.md` z wywiadu Jarva).",
    "podmioty": "Firmy, ludzie w rolach publicznych, narzędzia, konkurenci, dostawcy: jedna notatka na rzecz.",
    "pojecia": "Metody, wzorce, definicje, lekcje ogólne: jedna notatka na pojęcie.",
    "orzeczenia": "Korekty od człowieka, jedna datowana linia każda. Agent dostaje swoje orzeczenia przed każdą turą.",
    "rozmowy": "Skompilowane ustalenia z rozmów i kart: decyzje, fakty, pliki. Surowe wyciągi leżą w `zrodla/rozmowy/`.",
}
POZA_WYSZUKIWANIEM = ("zrodla/", "skrzynka/")          # domyślnie nie wracają w wynikach (surowe i szkice)
PLIKI_SPECJALNE = {"INDEX.md", "LOG.md", "LINT.md", "SCHEMA.md"}
BEZ_FRONTMATTERU = ("brands/", "user/", "zrodla/", "skrzynka/")   # własne formaty (brand kit, USER.md, źródła, szkice)
TYPY = {"hub", "agent", "projekt", "podmiot", "pojecie", "fakt", "decyzja", "lekcja", "zrodlo", "rozmowa", "orzeczenia", "skill"}
STATUSY = {"aktualna", "do-sprawdzenia", "sprzeczna", "przestarzala", "generowane"}
WYMAGANE = ("typ", "utworzono", "zmieniono", "status")
BEZ_ZRODLA = {"hub", "agent", "orzeczenia", "skill"}         # generowane z repo i floty (linki robi zasiew)
SKILLE = "fleet/skille"                                       # skill floty = węzeł grafu (zasiew z fleet.json)
# notatki o samej flocie (nie o klientach): ich odwołania do skryptów lint porównuje z repo (state/wiedza-kod.json)
O_FLOCIE = ("agenci/", "pojecia/", "fleet/", "orzeczenia/")
SKRYPT_RE = re.compile(r"`(?:[^`\s]*/)?([\w-]+\.(?:py|sh|cjs|mjs))\b[^`]*`")
MAX_SLOW = {"hub": 400, "agent": 600, "projekt": 400}
DOMYSLNY_MAX_SLOW = 250
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


def dzis() -> str:
    return os.environ.get("WIEDZA_DZIS") or dt.date.today().isoformat()


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


def _wartosc(v: str):
    if v.startswith("[") and v.endswith("]"):
        return [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1]
    if v in ("true", "false"):
        return v == "true"
    return v


def sklej(fm: dict, tresc: str) -> str:
    linie = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            linie.append(f"{k}: [{', '.join(str(x) for x in v)}]")
        elif isinstance(v, bool):
            linie.append(f"{k}: {'true' if v else 'false'}")
        else:
            s = str(v)
            if s == "" or any(c in s for c in ":#{}\"'") or s != s.strip():
                s = '"' + s.replace('"', '\\"') + '"'
            linie.append(f"{k}: {s}")
    linie.append("---")
    return "\n".join(linie) + "\n" + tresc.lstrip("\n")


def bez_ogonkow(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).replace("ł", "l").replace("Ł", "L")


def nazwa_pliku(tytul: str) -> str:
    """Tytuł, jak się go mówi → nazwa pliku: małe litery, polskie znaki i spacje zostają, bez znaków zakazanych."""
    s = tytul.strip().lower()
    s = "".join(c if (c.isalnum() or c in " ,-.()") else " " for c in s)
    s = re.sub(r"\s+", " ", s).strip(" .-")
    return s[:70].rstrip(" .-") or "notatka"


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


# ------------------------------------------------------------------------------------------------ notatka

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
        """Bezpieczna ścieżka w skarbcu (bez `..`, bez symlinków na zewnątrz); `.md` dopisywane, gdy brak."""
        rel = rel.strip().lstrip("/")
        if not rel.endswith(".md"):
            rel += ".md"
        p = (self.root / rel).resolve()
        if p != self.root and self.root not in p.parents:
            raise ValueError(f"ścieżka poza skarbcem: {rel}")
        return p

    def rel(self, p: Path) -> str:
        return p.relative_to(self.root).as_posix()[:-3]

    def pliki(self) -> list[str]:
        """Wszystkie notatki (bez katalogów z kropką i plików specjalnych), ścieżki bez `.md`."""
        out = []
        for p in self.root.rglob("*.md"):
            r = p.relative_to(self.root)
            if any(part.startswith(".") or part == "_szablon" for part in r.parts):   # katalogi z kropką i szablony (brands/_szablon)
                continue
            if len(r.parts) == 1 and r.name in PLIKI_SPECJALNE:
                continue
            out.append(r.as_posix()[:-3])
        return sorted(out)

    def istnieje(self, rel: str) -> bool:
        try:
            return self.plik(rel).is_file()
        except ValueError:
            return False

    # ---- czytanie
    def wczytaj(self, rel: str) -> Notatka:
        p = self.plik(rel)
        text = p.read_text(encoding="utf-8", errors="replace")
        fm, tresc = podziel(text)
        m = re.search(r"^# (.+)$", tresc, re.M)
        tytul = bez_markdown(m.group(1)) if m else self.rel(p).rsplit("/", 1)[-1]
        streszczenie = ""
        if m:
            for linia in tresc[m.end():].splitlines():
                s = linia.strip()
                if not s and streszczenie:
                    break
                if s and not s.startswith(("#", "<!--", "|", "-", "```")):
                    streszczenie = (streszczenie + " " + bez_markdown(s)).strip()
        if not streszczenie:
            for linia in tresc.splitlines():
                s = linia.strip()
                if s and not s.startswith(("#", "<!--", "|", "-", "```", "---")):
                    streszczenie = bez_markdown(s)
                    break
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
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, p)
        return p

    def dopisz_log(self, rodzaj: str, tresc: str) -> None:
        p = self.root / "LOG.md"
        if not p.exists():
            p.write_text("# Dziennik skarbca\n\nTylko dopisywanie. Format: `## [data] rodzaj | co się stało`.\n", encoding="utf-8")
        with p.open("a", encoding="utf-8") as f:
            f.write(f"\n## [{dzis()}] {rodzaj} | {tresc.strip()}\n")

    # ---- git (punkty zapisu)
    def git(self, *args: str) -> subprocess.CompletedProcess | None:
        try:
            return subprocess.run(["git", *GIT_TOZSAMOSC, "-C", str(self.root), *args], capture_output=True, text=True)
        except FileNotFoundError:
            return None

    def git_init(self) -> bool:
        if (self.root / ".git").exists():
            return True
        r = self.git("init", "-q")
        if r is None or r.returncode != 0:
            return False
        (self.root / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
        return True

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
    """SQLite poza skarbcem (state/wiedza.db): FTS5 z `remove_diacritics 2` (ogonki bez znaczenia), linki, metadane."""

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
        """)

    def zamknij(self) -> None:
        self.db.close()

    def odswiez(self, pelny: bool = False) -> dict:
        """Indeks przyrostowy po mtime i rozmiarze. Linki przeliczane w całości, ale tylko gdy coś się zmieniło
        (notatka, lista plików specjalnych) albo przy `pelny`; bez zmian odświeżenie to sam przegląd katalogów."""
        pliki = self.sk.pliki()
        zbior = set(pliki)
        specjalne = ",".join(sorted(n for n in PLIKI_SPECJALNE if (self.sk.root / n).is_file()))
        stare = {r["sciezka"]: (r["mtime"], r["rozmiar"]) for r in self.db.execute("SELECT sciezka, mtime, rozmiar FROM pliki")}
        nowe = zmienione = 0
        notatki: dict[str, Notatka] = {}
        with self.db:
            if pelny:                                    # DELETE po kolumnie UNINDEXED skanuje całe FTS: przy przebudowie raz
                self.db.execute("DELETE FROM fts")
            for rel in pliki:
                p = self.sk.plik(rel)
                st = p.stat()
                if not pelny and rel in stare and stare[rel] == (st.st_mtime, st.st_size):
                    continue
                n = self.sk.wczytaj(rel)
                notatki[rel] = n
                nowe += rel not in stare
                zmienione += rel in stare
                if rel in stare and not pelny:           # nowa notatka nie ma wiersza w FTS (pliki i fts w jednej transakcji)
                    self.db.execute("DELETE FROM fts WHERE sciezka = ?", (rel,))
                self.db.execute("INSERT INTO fts(sciezka, tytul, streszczenie, tresc, tagi) VALUES (?,?,?,?,?)",
                                (rel, n.tytul, n.streszczenie, LISTA_RE.sub("", n.tresc), " ".join(n.fm.get("tagi") or []) if isinstance(n.fm.get("tagi"), list) else str(n.fm.get("tagi") or "")))
                self.db.execute("INSERT OR REPLACE INTO pliki VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (rel, n.mtime, n.rozmiar, n.tytul, n.streszczenie, n.typ, str(n.fm.get("status") or ""),
                                 str(n.fm.get("agent") or ""), n.folder, str(n.fm.get("zmieniono") or ""),
                                 str(n.fm.get("wazne_do") or ""), int(n.hub), n.slowa))
            usuniete = [s for s in stare if s not in zbior]
            for s in usuniete:
                self.db.execute("DELETE FROM fts WHERE sciezka = ?", (s,))
                self.db.execute("DELETE FROM pliki WHERE sciezka = ?", (s,))
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
        return {"pliki": len(pliki), "nowe": nowe, "zmienione": zmienione, "usuniete": len(usuniete)}

    @staticmethod
    def zapytanie(q: str) -> str:
        slowa = [w for w in re.findall(r"\w+", q.lower()) if len(w) >= 2 and w not in STOPSLOWA][:12]
        return " OR ".join(f'"{w}"*' for w in slowa)

    def szukaj(self, q: str, limit: int = 5, folder: str | None = None, agent: str | None = None, zrodla: bool = False) -> list[dict]:
        zap = self.zapytanie(q)
        if not zap:
            return []
        wiersze = self.db.execute(
            "SELECT f.sciezka, p.tytul, p.streszczenie, p.typ, p.status, p.folder, p.agent, p.zmieniono, "
            "bm25(fts, 0, 3.0, 2.0, 1.0, 1.5) AS w FROM fts f JOIN pliki p ON p.sciezka = f.sciezka WHERE fts MATCH ? ORDER BY w LIMIT ?",
            (zap, limit * 6)).fetchall()
        out, widziane = [], set()
        for r in wiersze:
            s = r["sciezka"]
            if not zrodla and s.startswith(POZA_WYSZUKIWANIEM):
                continue
            if r["typ"] == "skill" and not folder:            # węzły grafu o flocie: tylko z folder="fleet"
                continue
            if folder and not s.startswith(folder.rstrip("/") + "/"):
                continue
            if agent and r["agent"] and r["agent"] != agent:
                continue
            if s in widziane:
                continue
            widziane.add(s)
            out.append({"sciezka": s, "tytul": r["tytul"], "streszczenie": r["streszczenie"], "typ": r["typ"],
                        "status": r["status"], "zmieniono": r["zmieniono"], "wynik": round(-r["w"], 3)})
            if len(out) >= limit:
                break
        # krok po linkach: trafienie w marce pociąga orzeczenia tej marki
        for r in list(out):
            if r["sciezka"].startswith("brands/") and "/" in r["sciezka"][7:]:
                marka = r["sciezka"].split("/")[1]
                orz = f"orzeczenia/marki/{marka}"
                if self.sk.istnieje(orz) and orz not in widziane:
                    widziane.add(orz)
                    out.append({"sciezka": orz, "tytul": f"Orzeczenia marki {marka}", "streszczenie": "korekty użytkownika dotyczące tej marki",
                                "typ": "orzeczenia", "status": "aktualna", "zmieniono": "", "wynik": 0.0})
        return out

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
        wezly = [{"id": r["sciezka"], "tytul": r["tytul"], "folder": r["folder"], "typ": r["typ"], "status": r["status"],
                  "hub": bool(r["hub"]), "agent": r["agent"], "zmieniono": r["zmieniono"], "we": we.get(r["sciezka"], 0),
                  "wy": wy.get(r["sciezka"], 0)} for r in self.notatki() if not r["sciezka"].startswith(POZA_WYSZUKIWANIEM)]
        return {"wezly": wezly, "linki": [l for l in linki if not l["z"].startswith(POZA_WYSZUKIWANIEM)]}


# ------------------------------------------------------------------------------------------------ INDEX.md i listy hubów

def zbuduj_index(sk: Skarbiec, ix: Indeks) -> int:
    """INDEX.md z plików (deterministycznie): każda notatka jedną linią, sekcje po folderach."""
    grupy: dict[str, list] = {}
    for r in ix.notatki():
        grupy.setdefault(r["folder"], []).append(r)
    linie = ["# Indeks skarbca", "", f"Generowany przez `wiedza.py indeksuj` ({dzis()}). Jedna linia = jedna notatka: link · streszczenie · typ · zmieniono.", ""]
    n = 0
    for folder in sorted(grupy, key=lambda f: (f != "", f)):
        wiersze = grupy[folder]
        nazwa = HUBY.get(folder, (None, folder or "Skarbiec"))[1]
        if folder in ("zrodla", "skrzynka"):
            linie += [f"## {nazwa} ({len(wiersze)} plików, poza wyszukiwaniem)", ""]
            continue
        linie += [f"## {nazwa}", ""]
        skille = [r for r in wiersze if r["typ"] == "skill"]
        if skille:
            linie.append(f"- skille floty: {len(skille)} notatek w `{SKILLE}/` (węzły grafu; szukanie z `folder=fleet`)")
        for r in sorted((r for r in wiersze if r["typ"] != "skill"), key=lambda r: (not r["hub"], r["sciezka"])):
            s = (r["streszczenie"] or "").replace("\n", " ")
            s = s[:120].rstrip() + ("…" if len(s) > 120 else "")
            czesci = [f"[[{r['sciezka']}|{r['tytul']}]]"] + ([s] if s else []) + [r["typ"] or "?"] + ([r["zmieniono"]] if r["zmieniono"] else [])
            linie.append("- " + " · ".join(czesci))
            n += 1
        linie.append("")
    sk.zapisz_plik("INDEX", "\n".join(linie).rstrip("\n") + "\n")
    return n


def odswiez_listy_hubow(sk: Skarbiec, ix: Indeks) -> int:
    """Blok `lista` w hubie folderu (i w hubie agenta): linki do wszystkich notatek folderu, 0 tokenów."""
    notatki = [r for r in ix.notatki() if not r["hub"]]
    ile = 0
    for folder, (hub, _t) in HUBY.items():
        if folder == "":
            continue
        rel = f"{folder}/{hub}"
        if not sk.istnieje(rel):
            continue
        if folder == "agenci":
            wiersze = [f"- [[{r['sciezka']}|{r['tytul']}]]" for r in ix.notatki() if r["hub"] and r["sciezka"].startswith("agenci/") and r["sciezka"].count("/") == 2]
        else:
            wiersze = [f"- [[{r['sciezka']}|{r['tytul']}]]" + (f" · {r['streszczenie'][:90]}" if r["streszczenie"] else "")
                       for r in notatki if r["sciezka"].startswith(folder + "/")]
        ile += _wpisz_liste(sk, rel, wiersze)
    for r in ix.notatki():
        if r["hub"] and r["sciezka"].startswith("agenci/") and r["sciezka"].count("/") == 2:
            katalog = r["sciezka"].rsplit("/", 1)[0] + "/"
            wiersze = [f"- [[{n['sciezka']}|{n['tytul']}]]" + (f" · {n['streszczenie'][:90]}" if n["streszczenie"] else "")
                       for n in notatki if n["sciezka"].startswith(katalog)]
            ile += _wpisz_liste(sk, r["sciezka"], wiersze)
    return ile


def _wpisz_liste(sk: Skarbiec, rel: str, wiersze: list[str]) -> int:
    p = sk.plik(rel)
    stary = p.read_text(encoding="utf-8")
    tresc = "## Notatki (lista automatyczna)\n" + ("\n".join(wiersze) if wiersze else "_jeszcze pusto_")
    nowy = zastap_blok(stary, "lista", tresc)
    if nowy != stary:
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


def notatka_skilla(s: dict, agenci: list[tuple[str, str, str]], znane: set[str]) -> str:
    """Notatka-węzeł skilla floty: opis, kto go ma, powiązane skille i skrypty (linki robi zasiew, nie autor)."""
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
    opis = s.get("description") or "(skill bez opisu)"
    return (f"# {s['name']}\n\n**{opis}**\n\n"
            + zastap_blok("", "skill", "## Z repo (SKILL.md i fleet.yaml)\n" + "\n".join(wiersze)).strip() + "\n")


def zasiej_skille(sk: Skarbiec, skille: dict[str, tuple[dict, list]]) -> int:
    """`fleet/skille/<nazwa>.md` dla każdego skilla floty (własnego i wspólnego): węzeł grafu połączony z hubami agentów,
    powiązanymi skillami i skryptami. Plik zmienia się tylko, gdy zmienił się skill; skill usunięty z floty znika."""
    katalog = sk.root / SKILLE
    katalog.mkdir(parents=True, exist_ok=True)
    zmienione = 0
    for nazwa, (s, agenci) in sorted(skille.items()):
        rel = f"{SKILLE}/{nazwa}"
        tresc = notatka_skilla(s, agenci, set(skille))
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


def zasiej(sk: Skarbiec, fleet: dict | None, docs: Path | None, schema: Path | None) -> dict:
    sk.root.mkdir(parents=True, exist_ok=True)
    for f in FOLDERY:
        (sk.root / f).mkdir(parents=True, exist_ok=True)
    raport = {"huby": 0, "agenci": 0, "skille": 0, "docs": 0, "git": False}
    if schema and schema.exists():
        shutil.copy2(schema, sk.root / "SCHEMA.md")
    # huby folderów (część ręczna zostaje: piszemy tylko, gdy pliku nie ma; bloki GEN odświeżane zawsze)
    for folder, (hub, tytul) in HUBY.items():
        rel = f"{folder}/{hub}" if folder else hub
        if not sk.istnieje(rel):
            opis = OPISY_FOLDEROW.get(folder, "Strona główna skarbca: huby folderów, liczby, ostatnie zmiany.")
            body = f"# {tytul}\n\n**{opis}**\n\n## Powiązane\n" + (f"- hub: [[_hub-skarbiec|Skarbiec wiedzy]]\n" if folder else "")
            sk.zapisz_plik(rel, sklej(_hub_frontmatter("hub"), body))
            raport["huby"] += 1
    # hub główny: linki do hubów folderów (blok GEN)
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
            if not sk.istnieje(rel):
                body = (f"# {a.get('emoji', '')} {a.get('title', a['name'])} ({a['name']})\n\n**{a.get('description', '').strip()}**\n\n"
                        f"## Powiązane\n- hub: [[agenci/_hub-agenci|Agenci]]\n- [[{orz}|Orzeczenia: {a.get('short') or krotki}]]\n"
                        f"- [[fleet/lekcje|Księga lekcji floty]]\n").replace("#  ", "# ")
                sk.zapisz_plik(rel, sklej(_hub_frontmatter("agent", "fleet.yaml", agent=a["name"]), body))
                raport["agenci"] += 1
            skille = "\n".join(f"- [[{SKILLE}/{s['name']}|{s['name']}]]: {s.get('description', '').strip()}"
                               for s in a.get("skills", [])) or "_brak_"
            skrypty = ", ".join(f"`{s}`" for s in a.get("scripts", [])) or "_brak_"
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
            gen = (f"## Z rejestru floty (fleet.yaml)\n- rola: {a.get('kind', '')} · autonomia: {a.get('autonomy_max', '')} · "
                   f"pokój HQ: {a.get('label', a.get('room', ''))} (`{a.get('room', '')}`) · temat Telegrama: `{a.get('telegram_topic', '')}`\n"
                   f"- skille ({len(a.get('skills', []))}):\n{skille}{zewn_linia}\n- skrypty: {skrypty}{zmiany_linia}")
            pl = sk.plik(rel)
            tekst = pl.read_text(encoding="utf-8")
            m = re.search(r"^(# .+\n\n)\*\*(.+)\*\*$", tekst, re.M)
            stary = (poprzednie.get(a["name"]) or {}).get("opis")
            if m and opis and m.group(2) != opis and (stary is None or m.group(2) == stary):
                tekst = tekst[:m.start(2) - 2] + f"**{opis}**" + tekst[m.end(2) + 2:]
            sk.zapisz_plik(rel, zastap_blok(tekst, "fleet", gen))
            if not sk.istnieje(orz):
                sk.zapisz_plik(orz, sklej(_hub_frontmatter("orzeczenia", "człowiek", agent=a["name"]),
                                          f"# Orzeczenia: {a.get('short') or krotki}\n\n**Korekty od użytkownika dla `{a['name']}`, jedna datowana linia każda; agent czyta je przed każdą turą.**\n\n"
                                          f"## Powiązane\n- hub: [[orzeczenia/_hub-orzeczenia|Orzeczenia]]\n- [[{rel}|{a.get('short') or krotki}]]\n\n## Linie\n"))
        (sk.stan).mkdir(parents=True, exist_ok=True)
        (sk.stan / "wiedza-agenci.json").write_text(json.dumps(agenci_meta, ensure_ascii=False, indent=1), encoding="utf-8")
        # skrypty, które naprawdę są w repo: lint wskazuje notatki floty odwołujące się do nieistniejących
        znane_skrypty = sorted({s for a in fleet.get("agents", []) for s in a.get("scripts", [])} | set(fleet.get("repo_scripts") or []))
        (sk.stan / "wiedza-kod.json").write_text(json.dumps({"skrypty": znane_skrypty}, ensure_ascii=False, indent=1), encoding="utf-8")
        raport["skille"] = zasiej_skille(sk, skille_floty)
    if not sk.istnieje("orzeczenia/wszyscy"):
        sk.zapisz_plik("orzeczenia/wszyscy", sklej(_hub_frontmatter("orzeczenia", "człowiek"),
                                                   "# Orzeczenia: wszyscy\n\n**Korekty od użytkownika dla całej floty, jedna datowana linia każda.**\n\n"
                                                   "## Powiązane\n- hub: [[orzeczenia/_hub-orzeczenia|Orzeczenia]]\n\n## Linie\n"))
    if not sk.istnieje("fleet/lekcje"):
        sk.zapisz_plik("fleet/lekcje", sklej(_hub_frontmatter("lekcja", "przegląd tygodnia (skill fleet-improvement)"),
                                             "# Księga lekcji floty\n\n**Obserwacje z recenzji sędziego: jedna linia = jedna sprawdzalna reguła z licznikiem potwierdzeń.**\n\n"
                                             "## Powiązane\n- hub: [[agenci/_hub-agenci|Agenci]]\n"))
    if docs and docs.is_dir():
        lustro = sk.root / "zrodla" / "jarvo-repo"
        nazwy = set()
        for d in sorted(docs.glob("*.md")):
            shutil.copy2(d, lustro / d.name)
            nazwy.add(d.name)
            raport["docs"] += 1
        for stara in lustro.glob("*.md"):            # dokument usunięty z repo nie zostaje w skarbcu jako „źródło”
            if stara.name not in nazwy:
                stara.unlink()
    if not (sk.root / "INDEX.md").exists():
        (sk.root / "INDEX.md").write_text("# Indeks skarbca\n\n_Pusty do pierwszego `wiedza.py indeksuj`._\n", encoding="utf-8")
    if not (sk.root / "LINT.md").exists():
        (sk.root / "LINT.md").write_text("# Lint skarbca\n\n_Jeszcze nie uruchomiono `wiedza.py lint`._\n", encoding="utf-8")
    sk.dopisz_log("zasiew", f"huby: {raport['huby']} folderów, {raport['agenci']} agentów; skille: {raport['skille']} zmienionych; "
                            f"docs repo: {raport['docs']} plików")
    raport["git"] = sk.git_init() and sk.punkt_zapisu("zasiew skarbca")
    return raport


# ------------------------------------------------------------------------------------------------ szkice i orzeczenia

def zapisz_szkic(sk: Skarbiec, typ: str, tytul: str, tresc: str, zrodlo: str, agent: str = "", tagi: list | None = None,
                 linki: list | None = None, skad: str = "") -> str:
    if typ not in TYPY - {"hub", "orzeczenia"}:
        raise ValueError(f"typ spoza schematu: {typ} (dozwolone: {', '.join(sorted(TYPY - {'hub', 'orzeczenia'}))})")
    if not tytul.strip() or not tresc.strip():
        raise ValueError("szkic musi mieć tytuł i treść")
    if not zrodlo.strip():
        raise ValueError("szkic musi mieć źródło (karta, rozmowa, plik, adres)")
    sekret = zawiera_sekret(tytul + "\n" + tresc)
    if sekret:
        raise ValueError(f"szkic zawiera sekret ({sekret}); sekrety nigdy nie trafiają do skarbca")
    skrot = hashlib.sha1(f"{tytul}{tresc}{dzis()}".encode()).hexdigest()[:6]
    rel = f"skrzynka/{dzis()}-{slug_ascii(agent or 'agent', 16)}-{slug_ascii(tytul)}-{skrot}"
    fm = {"szkic": True, "typ": typ, "tytul": tytul.strip(), "agent": agent or "", "zrodlo": zrodlo.strip(), "utworzono": dzis(),
          "skad": skad or "", "tagi": tagi or [], "linki": linki or []}
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
        if folder and folder not in ("orzeczenia",):
            ile = sum(1 for rel in notatki if rel.startswith(folder + "/") and not notatki[rel]["hub"])
            if ile < 3:
                info.append(f"cienki folder `{folder}/` ({ile} notatek)")
    szkice = [p for p in (sk.root / "skrzynka").glob("*.md")]
    stare = [p.name for p in szkice if (dt.datetime.now().timestamp() - p.stat().st_mtime) > 7 * 86400]
    if szkice:
        info.append(f"szkice w skrzynce: {len(szkice)}" + (f" (starsze niż 7 dni: {len(stare)})" if stare else ""))
    raport = {"bledy": bledy, "ostrzezenia": ostrz, "informacje": info, "notatek": len([r for r in notatki if not r.startswith(POZA_WYSZUKIWANIEM)]),
              "data": dzis()}
    linie = [f"# Lint skarbca ({dzis()})", "", f"Notatek: {raport['notatek']} · błędy: {len(bledy)} · ostrzeżenia: {len(ostrz)} · informacje: {len(info)}", ""]
    for naglowek, lista in (("Błędy", bledy), ("Ostrzeżenia", ostrz), ("Informacje", info)):
        linie += [f"## {naglowek}", ""] + ([f"- {x}" for x in lista] or ["- brak"]) + [""]
    (sk.root / "LINT.md").write_text("\n".join(linie), encoding="utf-8")
    return raport


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
    return {"skarbiec": str(sk.root), "indeks": str(sk.stan / "wiedza.db"), "wg_folderu": wg_folderu, "szkice": szkice,
            "linki": ix.db.execute("SELECT COUNT(*) FROM linki WHERE rozwiazany = 1").fetchone()[0],
            "git": (sk.root / ".git").exists(), "ostatni_wpis": ostatni}


# ------------------------------------------------------------------------------------------------ CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Skarbiec wiedzy floty Jarvo (docs/WIEDZA.md)")
    ap.add_argument("--skarbiec", default=DOMYSLNY_SKARBIEC, help="katalog skarbca (JARVO_KNOWLEDGE_DIR)")
    ap.add_argument("--stan", default=None, help="katalog na indeks (JARVO_STATE_DIR, domyślnie <skarbiec>/../state)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    z = sub.add_parser("zasiej", help="katalogi, huby, INDEX, LOG, orzeczenia, docs repo, git init")
    z.add_argument("--fleet", help="fleet.json z buildu (agenci, skille, skrypty)")
    z.add_argument("--docs", help="katalog docs/ repo → zrodla/jarvo-repo/")
    z.add_argument("--schema", default=str(Path(__file__).with_name("SCHEMA.md")), help="SCHEMA.md do skopiowania")
    i = sub.add_parser("indeksuj", help="indeks FTS5 + INDEX.md + listy hubów")
    i.add_argument("--pelny", action="store_true")
    s = sub.add_parser("szukaj", help="wyszukiwanie")
    s.add_argument("zapytanie")
    s.add_argument("--limit", type=int, default=5)
    s.add_argument("--folder")
    s.add_argument("--agent")
    s.add_argument("--zrodla", action="store_true", help="także zrodla/ i skrzynka/")
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
    a = ap.parse_args(argv)

    sk = Skarbiec(a.skarbiec, a.stan)
    if a.cmd == "zasiej":
        fleet = json.loads(Path(a.fleet).read_text(encoding="utf-8")) if a.fleet else None
        r = zasiej(sk, fleet, Path(a.docs) if a.docs else None, Path(a.schema) if a.schema else None)
        ix = Indeks(sk)
        ix.odswiez(pelny=True)
        n = zbuduj_index(sk, ix)
        odswiez_listy_hubow(sk, ix)
        ix.odswiez()
        sk.punkt_zapisu("zasiew skarbca: indeks")
        print(f"✓ zasiew: {r['huby']} hubów folderów, {r['agenci']} hubów agentów, {r['skille']} skilli zmienionych, {r['docs']} docs, "
              f"indeks {n} notatek, git: {'tak' if r['git'] else 'nie'}")
        return 0
    if not sk.root.is_dir():
        print(f"✗ brak skarbca {sk.root} (najpierw `zasiej`)", file=sys.stderr)
        return 2
    ix = Indeks(sk)
    try:
        if a.cmd == "indeksuj":
            r = ix.odswiez(pelny=a.pelny)
            n = zbuduj_index(sk, ix)
            h = odswiez_listy_hubow(sk, ix)
            ix.odswiez()
            print(f"✓ indeks: {r['pliki']} plików ({r['nowe']} nowych, {r['zmienione']} zmienionych, {r['usuniete']} usuniętych), INDEX.md: {n} notatek, huby odświeżone: {h}")
        elif a.cmd == "szukaj":
            ix.odswiez()
            wyn = ix.szukaj(a.zapytanie, limit=a.limit, folder=a.folder, agent=a.agent, zrodla=a.zrodla)
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
                                   [x.strip() for x in a.linki.split(",") if x.strip()], a.skad)
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
    finally:
        ix.zamknij()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
