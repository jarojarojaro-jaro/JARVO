"""Podpowiedzi na ekranie startu, etap N0 warstwy nauki (docs/HQ.md „Ekran startu”, spec-nauka §0, §5, §6.4).

- **Budżet ekranu**: pod polem wiadomości najwyżej 4 rzeczy. Najpierw „Czeka na Ciebie” (zgody w toku i nieudana
  praca z `rozmowy.db`, `Rozmowy.czeka_na_wlasciciela`), potem „Na początek”: najwyżej 3 startery.
- **Startery**: stała lista, jeden na specjalistę z floty (agent musi być w `fleet.json`), PL i EN. Klik tylko
  wpisuje tekst do pola wiadomości (adresat: Jarvo, bez wysyłki); awatar pokazuje specjalistę, który zwykle to robi.
  „Poznajmy się” nie jest starterem: żyje w karcie gotowości, dopóki USER.md nie ma imienia.
- **Każdy starter to eksperyment** (`nawyki.db`, tabele `podpowiedzi`, `reakcje`, `typy`, `zakazy`, `meta`; reszta
  schematu spec-nauka §8.2 przyjdzie w etapie 4c). Reakcje klienta: `pokazana` (raz na dzień, klucz od klienta),
  `kliknieta`, `odrzucona` (×), `nigdy` („Nie pokazuj tego”: na zawsze, zakaz w `zakazy`). Idempotentne po `klucz`.
  Starter ma stały identyfikator (`id_startera`), więc `GET /podpowiedzi` tylko czyta (połączenie `mode=ro`); wiersz
  `podpowiedzi` powstaje przy pierwszej reakcji.
- **Ranking Beta** (spec-nauka §5.2): waga wyniku `2^(−Δt/30 dni)`; typ `start` z priorytetem (1, 3), starter ściągany
  do średniej typu siłą k = 4; wynik = średnia startera. Zimny start pokazuje zawsze 3 startery (spec-nauka §6.4:
  „exactly 3”), więc próg 0,25 nie ukrywa starterów, tylko ustala kolejność; remis = stała kolejność listy.
  Starter odrzucony 2 razy bez kliknięcia śpi 14 dni, 3 razy = wyłączony; `nigdy` = nigdy więcej.
Bez tokenów i bez modelu. Testy: tests/test_aplikacja.py.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterable, Iterator

BUDZET = 4
STARTERY_MAKS = 3
CZEKA_MAKS = 4
POLOWICZNY_S = 30 * 86400.0
PRIORY = {"start": (1.0, 3.0)}
SILA_K = 4.0
PROG = 0.25
USPIENIE_S = 14 * 86400.0
GENERATOR = "n0-1"
WAGI = {"kliknieta": (0.2, 0.0), "wyslana": (0.5, 0.0), "ukonczona": (0.3, 0.0), "nieudana": (0.0, 0.3),
        "odrzucona": (0.0, 1.0), "nigdy": (0.0, 2.0), "zignorowana": (0.0, 0.15), "pozniej": (0.0, 0.0),
        "pokazana": (0.0, 0.0)}
REAKCJE_KLIENTA = ("pokazana", "kliknieta", "odrzucona", "nigdy")

# klucz, agent, (tytuł, powód, tekst do pola) PL i EN; kolejność = kolejność przy remisie (mock V2: web, łowca, ręka)
STARTERY = (
    ("strona", "jarvo-web",
     ("Zrób stronę dla mojej firmy", "pierwsza wersja w kilkanaście minut", "Zrób stronę dla mojej firmy: "),
     ("Build a website for my business", "a first version in minutes", "Build a website for my business: ")),
    ("klienci", "jarvo-lowca",
     ("Znajdź nowych klientów w okolicy", "firmy z KRS i CEIDG", "Znajdź nowych klientów w okolicy: "),
     ("Find new customers nearby", "companies from public registers", "Find new customers nearby: ")),
    ("plik", "jarvo-reka",
     ("Zamień plik na PDF albo Word", "wystarczy go przeciągnąć tutaj", "Zamień ten plik na PDF albo Word: "),
     ("Convert a file to PDF or Word", "just drag it here", "Convert this file to PDF or Word: ")),
    ("temat", "jarvo-sherlock",
     ("Sprawdź temat i źródła", "z linkami do źródeł", "Sprawdź temat i podaj źródła: "),
     ("Research a topic with sources", "with links to sources", "Research this topic and cite sources: ")),
    ("posty", "jarvo-studio",
     ("Zrób posty na social media", "grafiki i opisy do Twojej akceptacji", "Zrób posty na Instagram o: "),
     ("Make social media posts", "graphics and captions for your approval", "Make Instagram posts about: ")),
    ("film", "jarvo-wideo",
     ("Zrób krótki film na Reels", "scenariusz, montaż i napisy", "Zrób krótki film na Reels o: "),
     ("Make a short Reels video", "script, edit and captions", "Make a short Reels video about: ")),
    ("reklama", "jarvo-ads",
     ("Przygotuj kampanię reklamową", "puszczasz ją sam, po akceptacji", "Przygotuj kampanię reklamową dla: "),
     ("Prepare an ad campaign", "you launch it yourself after review", "Prepare an ad campaign for: ")),
    ("aplikacja", "jarvo-mobile",
     ("Czy potrzebuję aplikacji?", "uczciwie: natywna czy PWA", "Czy moja firma potrzebuje aplikacji mobilnej? Firma: "),
     ("Do I need an app?", "honestly: native or PWA", "Does my business need a mobile app? Business: ")),
)

SCHEMAT = """
CREATE TABLE IF NOT EXISTS meta (klucz TEXT PRIMARY KEY, wartosc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS podpowiedzi (
  id TEXT PRIMARY KEY, nawyk_id INTEGER, typ TEXT NOT NULL, regula TEXT NOT NULL,
  miejsce TEXT NOT NULL CHECK (miejsce IN ('start','nastepny','automatyzacja')),
  kontekst TEXT, tytul TEXT NOT NULL, powod TEXT NOT NULL, agent TEXT, adresat_jednorazowy INTEGER NOT NULL DEFAULT 0,
  prompt TEXT NOT NULL, slot INTEGER, eksploracja INTEGER NOT NULL DEFAULT 0, propensja REAL,
  wynik REAL, generator_wersja TEXT NOT NULL, hermes_sugestia_id TEXT,
  utworzona_at REAL NOT NULL, wygasa_at REAL, stan TEXT NOT NULL DEFAULT 'aktywna'
);
CREATE UNIQUE INDEX IF NOT EXISTS podpowiedzi_regula ON podpowiedzi (miejsce, regula) WHERE miejsce = 'start';
CREATE TABLE IF NOT EXISTS reakcje (
  id INTEGER PRIMARY KEY, podpowiedz_id TEXT NOT NULL REFERENCES podpowiedzi(id),
  rodzaj TEXT NOT NULL CHECK (rodzaj IN ('pokazana','kliknieta','wyslana','ukonczona','nieudana',
                                         'odrzucona','nigdy','pozniej','zignorowana')),
  ts REAL NOT NULL, klucz TEXT UNIQUE, dane TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS reakcje_podpowiedz ON reakcje (podpowiedz_id, ts);
CREATE TABLE IF NOT EXISTS typy (typ TEXT PRIMARY KEY, alfa REAL NOT NULL, beta REAL NOT NULL, ekspozycje REAL NOT NULL,
                                 stan TEXT NOT NULL DEFAULT 'aktywny', zmieniony_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS zakazy (klucz TEXT PRIMARY KEY, typ TEXT NOT NULL, centroid TEXT NOT NULL,
                                   utworzony_at REAL NOT NULL);
"""


class Nieznana(Exception):
    """Reakcja na podpowiedź, której nie ma (trasa: 409 `nieznana`)."""


def waga(dt: float) -> float:
    return 2.0 ** (-max(0.0, dt) / POLOWICZNY_S)


def srednia(alfa: float, beta: float) -> float:
    return alfa / (alfa + beta) if alfa + beta > 0 else 0.0


def id_startera(klucz: str) -> str:
    """Stały identyfikator startera (kształt `pd_<21 hex>` jak spec-nauka §8.2): GET nie musi niczego zapisywać."""
    return "pd_" + hashlib.sha256(f"start:{klucz}".encode()).hexdigest()[:21]


STARTER_PO_ID = {id_startera(s[0]): s for s in STARTERY}


class Nawyki:
    """Baza `nawyki.db` etapu N0. Odczyt (`start`) bez zapisu: wiersz podpowiedzi startera powstaje przy pierwszej
    reakcji (`reakcja`, trasa POST). Każda metoda otwiera krótkie połączenie (WAL); wołać przez asyncio.to_thread."""

    def __init__(self, sciezka: Path | str, *, zegar: Callable[[], float] = time.time):
        self.sciezka = Path(sciezka)
        self.zegar = zegar
        self._lock = threading.Lock()
        self._gotowa = False

    def _schemat(self) -> None:
        with self._lock:
            if self._gotowa:
                return
            self.sciezka.parent.mkdir(parents=True, exist_ok=True)
            c = sqlite3.connect(self.sciezka, timeout=5)
            try:
                c.execute("PRAGMA journal_mode = WAL")
                c.executescript(SCHEMAT)
                if int(c.execute("PRAGMA user_version").fetchone()[0]) < 1:
                    c.execute("PRAGMA user_version = 1")
                c.execute("INSERT OR IGNORE INTO meta (klucz, wartosc) VALUES ('utworzono', ?)", (repr(self.zegar()),))
                c.commit()
            finally:
                c.close()
            self._gotowa = True

    @contextmanager
    def _polacz(self) -> Iterator[sqlite3.Connection]:
        self._schemat()
        c = sqlite3.connect(self.sciezka, timeout=5)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    @contextmanager
    def _odczyt(self) -> Iterator[sqlite3.Connection | None]:
        """Połączenie tylko do odczytu; None, gdy bazy jeszcze nie ma (nikt nie reagował = sam priorytet)."""
        if not self.sciezka.is_file():
            yield None
            return
        c = sqlite3.connect(self.sciezka.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
        c.row_factory = sqlite3.Row
        try:
            yield c
        finally:
            c.close()

    # ------------------------------------------------------------------------------------------- startery
    def _wyniki(self, c: sqlite3.Connection | None, ids: Iterable[str]) -> tuple[dict[str, dict], tuple]:
        """id → {wynik, odrzucenia, klikniecia, ostatnie_odrzucenie, zakazany} i (alfa, beta, ekspozycje) typu."""
        teraz = self.zegar()
        ids = list(ids)
        suma = {i: [0.0, 0.0] for i in ids}
        info = {i: {"odrzucenia": 0, "klikniecia": 0, "ostatnie_odrzucenie": 0.0, "zakazany": False} for i in ids}
        typ_s = typ_f = eksp = 0.0
        if c is not None:
            for r in c.execute("SELECT r.podpowiedz_id, r.rodzaj, r.ts FROM reakcje r "
                               "JOIN podpowiedzi p ON p.id = r.podpowiedz_id WHERE p.typ = 'start'"):
                s, f = WAGI.get(r["rodzaj"], (0.0, 0.0))
                w = waga(teraz - r["ts"])
                typ_s += w * s
                typ_f += w * f
                if r["rodzaj"] == "pokazana":
                    eksp += w
                if r["podpowiedz_id"] not in suma:
                    continue
                suma[r["podpowiedz_id"]][0] += w * s
                suma[r["podpowiedz_id"]][1] += w * f
                x = info[r["podpowiedz_id"]]
                if r["rodzaj"] == "odrzucona":
                    x["odrzucenia"] += 1
                    x["ostatnie_odrzucenie"] = max(x["ostatnie_odrzucenie"], r["ts"])
                elif r["rodzaj"] in ("kliknieta", "wyslana", "ukonczona"):
                    x["klikniecia"] += 1
            for r in c.execute("SELECT id, stan FROM podpowiedzi WHERE typ = 'start'"):
                if r["id"] in info and r["stan"] != "aktywna":
                    info[r["id"]]["zakazany"] = True
            for r in c.execute("SELECT klucz FROM zakazy WHERE typ = 'start'"):
                k = str(r["klucz"]).split(":", 1)[-1]
                if id_startera(k) in info:
                    info[id_startera(k)]["zakazany"] = True
        a0, b0 = PRIORY["start"]
        alfa_t, beta_t = a0 + typ_s, b0 + typ_f
        m_t = srednia(alfa_t, beta_t)
        out = {}
        for i, (s, f) in suma.items():
            out[i] = {"wynik": srednia(SILA_K * m_t + s, SILA_K * (1 - m_t) + f), **info[i]}
        return out, (alfa_t, beta_t, eksp)

    def start(self, agenci: Iterable[str], *, czeka: int = 0) -> dict:
        """Startery do pokazania (tylko odczyt): {tryb, podpowiedzi:[Podpowiedz], wersja}. `agenci`: nazwy floty."""
        floty = set(agenci)
        lista_st = [s for s in STARTERY if s[1] in floty]
        miejsca = max(0, min(STARTERY_MAKS, BUDZET - max(0, czeka)))
        teraz = self.zegar()
        with self._odczyt() as c:
            wyniki, _typ = self._wyniki(c, [id_startera(s[0]) for s in lista_st])
        kandydaci = []
        for i, st in enumerate(lista_st):
            wy = wyniki[id_startera(st[0])]
            if wy["zakazany"]:
                continue
            if not wy["klikniecia"] and wy["odrzucenia"] >= 3:
                continue                                         # wyłączony (spec-nauka §5.4)
            if not wy["klikniecia"] and wy["odrzucenia"] >= 2 and teraz - wy["ostatnie_odrzucenie"] < USPIENIE_S:
                continue                                         # śpi 14 dni
            kandydaci.append((-round(wy["wynik"], 9), i, st, wy))
        kandydaci.sort(key=lambda x: (x[0], x[1]))
        lista = []
        for slot, (_, _, (k, agent, pl, en), wy) in enumerate(kandydaci[:miejsca]):
            lista.append({"id": id_startera(k), "typ": "start", "miejsce": "start", "klucz": k, "agent": agent,
                          "adresat_jednorazowy": False, "eksploracja": False, "slot": slot,
                          "tytul": pl[0], "powod": pl[1], "prompt": pl[2],
                          "tytul_en": en[0], "powod_en": en[1], "prompt_en": en[2],
                          "wynik": round(wy["wynik"], 4), "nad_progiem": wy["wynik"] >= PROG - 1e-9})
        wersja = hashlib.sha1(json.dumps([x["id"] for x in lista]).encode()).hexdigest()[:12]
        return {"tryb": "start", "podpowiedzi": lista, "wersja": wersja}

    # ------------------------------------------------------------------------------------------- reakcje
    def reakcja(self, pid: str, rodzaj: str, klucz: str | None = None, dane: dict | None = None) -> bool:
        """Zapis reakcji; True = nowa, False = już była (ten sam `klucz`). Nieznana podpowiedź = Nieznana.
        Pierwsza reakcja na starter zakłada jego wiersz w `podpowiedzi`; po każdej nowej `typy` dostaje świeże α, β."""
        if rodzaj not in WAGI:
            raise ValueError(rodzaj)
        teraz = self.zegar()
        with self._polacz() as c:
            w = c.execute("SELECT id, typ, regula FROM podpowiedzi WHERE id = ?", (pid,)).fetchone()
            if w is None:
                st = STARTER_PO_ID.get(pid)
                if st is None:
                    raise Nieznana(pid)
                k, agent, pl, _en = st
                c.execute("INSERT OR IGNORE INTO podpowiedzi (id, typ, regula, miejsce, tytul, powod, agent, prompt, "
                          "generator_wersja, utworzona_at) VALUES (?, 'start', ?, 'start', ?, ?, ?, ?, ?, ?)",
                          (pid, f"start:{k}", pl[0], pl[1], agent, pl[2], GENERATOR, teraz))
                w = c.execute("SELECT id, typ, regula FROM podpowiedzi WHERE id = ?", (pid,)).fetchone()
            nowa = c.execute("INSERT OR IGNORE INTO reakcje (podpowiedz_id, rodzaj, ts, klucz, dane) VALUES (?, ?, ?, ?, ?)",
                             (pid, rodzaj, teraz, klucz, json.dumps(dane or {}, ensure_ascii=False))).rowcount == 1
            if nowa and rodzaj == "nigdy":
                c.execute("INSERT OR IGNORE INTO zakazy (klucz, typ, centroid, utworzony_at) VALUES (?, ?, '', ?)",
                          (w["regula"], w["typ"], teraz))
                c.execute("UPDATE podpowiedzi SET stan = 'zakazana' WHERE id = ?", (pid,))
            if nowa:
                _, (alfa, beta, eksp) = self._wyniki(c, [])
                c.execute("INSERT INTO typy (typ, alfa, beta, ekspozycje, zmieniony_at) VALUES ('start', ?, ?, ?, ?) "
                          "ON CONFLICT(typ) DO UPDATE SET alfa = excluded.alfa, beta = excluded.beta, "
                          "ekspozycje = excluded.ekspozycje, zmieniony_at = excluded.zmieniony_at",
                          (alfa, beta, eksp, teraz))
        return nowa

    def zdrowie(self) -> dict:
        try:
            with self._odczyt() as c:
                if c is None:
                    return {"reakcje": 0, "zakazy": 0}
                return {"reakcje": int(c.execute("SELECT count(*) FROM reakcje").fetchone()[0]),
                        "zakazy": int(c.execute("SELECT count(*) FROM zakazy").fetchone()[0])}
        except sqlite3.Error as exc:
            return {"blad": type(exc).__name__}


def czeka_wiersze(rows: Iterable[dict], teraz: float, decyzje: Iterable[dict] = ()) -> list[dict]:
    """Wiersze „Czeka na Ciebie” (najwyżej CZEKA_MAKS): zgoda → „Zobacz”, błąd → „Napraw”, z linkiem do wątku.
    Pytania zespołu (zablokowane karty kanbana, `decisions` z hq_core.build_state) to jeden wiersz `decyzja` za
    zgodami: jedno pytanie z tytułem karty albo „N pytań”; otwiera decyzje w Starej Bazie (do etapu 4)."""
    rows = list(rows)
    out = [_wiersz_czeka(r) for r in rows if r["rodzaj"] == "zgoda"]
    pytania = [d for d in decyzje or () if isinstance(d, dict) and d.get("task_id")]
    if pytania:
        d = pytania[0]
        out.append({"rodzaj": "decyzja", "agent": str(d.get("assignee") or ""), "watek": None,
                    "przebieg": f"d:{d['task_id']}", "tytul": str(d.get("title") or "") if len(pytania) == 1 else "",
                    "at": d.get("since"), "liczba": len(pytania), "akcja": "zobacz"})
    out += [_wiersz_czeka(r) for r in rows if r["rodzaj"] != "zgoda"]
    return out[:CZEKA_MAKS]


def _wiersz_czeka(r: dict) -> dict:
    return {"rodzaj": r["rodzaj"], "agent": r["agent"], "watek": r["watek"], "przebieg": r["przebieg"],
            "tytul": r.get("tytul") or "", "at": r.get("at"), "akcja": "zobacz" if r["rodzaj"] == "zgoda" else "napraw"}

