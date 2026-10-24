"""Magazyn rozmów aplikacji Jarvo: /opt/data/jarvo/state/rozmowy.db (SQLite, tryb 0600, właściciel hermes).

Wątki (rozmowy z paska bocznego), ich członkowie (agent + jego sesja Hermesa, tworzona leniwie), rodowód sesji
(rotacje po kompresji, import, przejęcie), wpisy wątku (wiadomości właściciela i notatki systemu: tekstu agentów tu
nie kopiujemy, czytamy go z state.db profilu), przebiegi (jedna tura agenta zlecona przez aplikację = jedno
`POST /v1/runs`), przekazania i karty kanbana wątku. Opis schematu i zasad: docs/HQ.md „Rozmowy”.

- Jedno połączenie piszące (wątek silnika), WAL, synchronous=NORMAL, foreign_keys, busy_timeout 5 s; każdy zapis
  w jednej transakcji (BEGIN IMMEDIATE). Odczyty z innych wątków otwierają krótkie połączenia tylko do odczytu.
- Migracje numerowane (`PRAGMA user_version`, każda w jednej transakcji, dziennik w tabeli `migracje`); przed
  przejściem na nową wersję kopia `rozmowy.db.bak-v<stara>` przez `sqlite3 .backup` (zostają dwie ostatnie).
- Import starych rozmów Bazy (`hq-sessions.json`, docs/HQ.md „Rozmowy”): `migruj_hq_sessions`, idempotentny
  per sesja przez tabelę `sesje`.
Czysty Python (sqlite3), bez Hermesa i FastAPI: testy na hoście (tests/test_rozmowy_db.py).
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import secrets
import sqlite3
import sys
import threading
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping

_H = Path(os.environ.get("HERMES_HOME", "/opt/data"))
HOME = _H.parent.parent if _H.parent.name == "profiles" else _H      # jak hq_core.HOME: korzeń danych Hermesa
JARVO_DIR = Path(os.environ.get("JARVO_DATA_DIR", str(HOME / "jarvo")))
SCIEZKA = JARVO_DIR / "state" / "rozmowy.db"
HQ_SESJE = JARVO_DIR / "state" / "hq-sessions.json"      # stare rozmowy Bazy: {agent: id sesji}
PROFILE = HOME / "profiles"

KOSZ_DNI = 30              # wątek w koszu tyle dni, potem usunięty na stałe (sesje i karty zostają jako nagrobki)
BLOKADY_DNI = 30           # blokada karty zostaje tyle dni po tym, jak karta skończyła się albo trafiła do archiwum
PAYLOAD_DNI = 90           # treść wysłana agentowi (payload) zerowana tyle dni po końcu przebiegu
PODGLAD_MAX = 140
TYTUL_MAX = 120
TYTUL_AUTO = 60
OSTATNI_MAX = 2
KOPIE_MIGRACJI = 2

STANY_AKTYWNE = ("kolejka", "wysylanie", "przyjety", "pracuje", "czeka_na_ture", "czeka_na_zgode", "zatrzymywanie",
                 "dopisany")
STANY_KONCOWE = ("gotowe", "blad", "zatrzymane", "przerwane", "zgubione", "anulowane", "wlaczony")
# stany, które zajmują miejsce w limicie przebiegów (lokalnym i bramy): od wysłania do zatrzymywania
STANY_W_LIMICIE = ("wysylanie", "przyjety", "pracuje", "czeka_na_ture", "czeka_na_zgode", "zatrzymywanie")

# ----------------------------------------------------------------------------------------------- schemat

MIGRACJA_1 = """
CREATE TABLE watki (
  id              TEXT PRIMARY KEY,
  tytul           TEXT NOT NULL DEFAULT '',
  tytul_zrodlo    TEXT NOT NULL DEFAULT 'auto' CHECK (tytul_zrodlo IN ('auto','wlasciciel','import')),
  tytul_szukaj    TEXT NOT NULL DEFAULT '',
  rodzaj          TEXT NOT NULL DEFAULT 'zwykly' CHECK (rodzaj IN ('zwykly','import','decyzje','kontynuacja','test')),
  przypiety       INTEGER NOT NULL DEFAULT 0,
  archiwum        INTEGER NOT NULL DEFAULT 0,
  usuniety_at     REAL,
  koordynator     TEXT NOT NULL DEFAULT 'jarvo',
  kanal           TEXT,
  utworzony_at    REAL NOT NULL,
  aktywnosc_at    REAL NOT NULL,
  przeczytane_at  REAL NOT NULL DEFAULT 0,
  nieprzeczytane  INTEGER NOT NULL DEFAULT 0,
  status          TEXT NOT NULL DEFAULT 'cisza' CHECK (status IN ('cisza','pracuje','czeka','blad')),
  podglad         TEXT NOT NULL DEFAULT '',
  ostatni_agenci  TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX watki_lista ON watki (usuniety_at, archiwum, przypiety DESC, aktywnosc_at DESC);

CREATE TABLE czlonkowie (
  watek_id    TEXT NOT NULL REFERENCES watki(id) ON DELETE CASCADE,
  agent       TEXT NOT NULL,
  rola        TEXT NOT NULL DEFAULT 'rozmowa' CHECK (rola IN ('rozmowa','nadzor')),
  sesja_id    TEXT,
  sesja_tip   TEXT,
  widzial_at  REAL NOT NULL DEFAULT 0,
  odczyt_id   INTEGER NOT NULL DEFAULT 0,
  tury        INTEGER NOT NULL DEFAULT 0,
  dodany_at   REAL NOT NULL,
  PRIMARY KEY (watek_id, agent, rola)
);

CREATE TABLE sesje (
  agent       TEXT NOT NULL,
  sesja_id    TEXT NOT NULL,
  watek_id    TEXT REFERENCES watki(id) ON DELETE SET NULL,
  rola        TEXT NOT NULL DEFAULT 'rozmowa',
  rodzic_id   TEXT,
  powod       TEXT NOT NULL DEFAULT 'start' CHECK (powod IN ('start','kompresja','import','przejecie','rotacja')),
  przypieta   INTEGER NOT NULL DEFAULT 0,
  dodana_at   REAL NOT NULL,
  PRIMARY KEY (agent, sesja_id)
);
CREATE INDEX sesje_watek ON sesje (watek_id);

CREATE TABLE wpisy (
  id            TEXT PRIMARY KEY,
  watek_id      TEXT NOT NULL REFERENCES watki(id) ON DELETE CASCADE,
  seq           INTEGER NOT NULL,
  rodzaj        TEXT NOT NULL CHECK (rodzaj IN ('wlasciciel','system')),
  tekst         TEXT NOT NULL DEFAULT '',
  tresc         TEXT NOT NULL DEFAULT '',
  szukaj        TEXT NOT NULL DEFAULT '',
  adresaci      TEXT NOT NULL DEFAULT '[]',
  tryb          TEXT NOT NULL DEFAULT 'jarvo' CHECK (tryb IN ('jarvo','bezposrednio')),
  zalaczniki    TEXT NOT NULL DEFAULT '[]',
  obrazy        TEXT NOT NULL DEFAULT '[]',
  dane          TEXT NOT NULL DEFAULT '{}',
  klucz         TEXT,
  utworzony_at  REAL NOT NULL,
  UNIQUE (watek_id, seq),
  UNIQUE (watek_id, klucz)
);
CREATE INDEX wpisy_czas ON wpisy (watek_id, utworzony_at);

CREATE TABLE przebiegi (
  id                     TEXT PRIMARY KEY,
  watek_id               TEXT NOT NULL REFERENCES watki(id) ON DELETE CASCADE,
  wpis_id                TEXT REFERENCES wpisy(id) ON DELETE SET NULL,
  agent                  TEXT NOT NULL,
  rola                   TEXT NOT NULL DEFAULT 'rozmowa',
  zrodlo                 TEXT NOT NULL DEFAULT 'wlasciciel'
                           CHECK (zrodlo IN ('wlasciciel','przekaz','nadzor','decyzja','system')),
  lancuch_id             TEXT NOT NULL,
  lancuch_zrodlo         TEXT NOT NULL DEFAULT 'wpis' CHECK (lancuch_zrodlo IN ('wpis','budzenie','obca')),
  hop                    INTEGER NOT NULL DEFAULT 0,
  przekaz_z              TEXT REFERENCES przebiegi(id),
  nadzorowany            INTEGER NOT NULL DEFAULT 0,
  nadzor_stan            TEXT CHECK (nadzor_stan IN ('czeka','sprawdza','ok','uwagi','przekazano','pytanie','w_rozmowie',
                           'pominiety','blad')),
  nadzor_przez           TEXT REFERENCES przebiegi(id),
  nadzor_zgoda           TEXT CHECK (nadzor_zgoda IN ('czeka','sprawdza','ok','uwaga','pominiety')),
  nadzor_zgoda_przez     TEXT REFERENCES przebiegi(id),
  nadzor_dla             TEXT,
  sesja_id               TEXT,
  run_id                 TEXT,
  stan                   TEXT NOT NULL CHECK (stan IN ('kolejka','wysylanie','przyjety','pracuje','czeka_na_ture',
                           'czeka_na_zgode','zatrzymywanie','dopisany','gotowe','blad','zatrzymane','przerwane','zgubione',
                           'anulowane','wlaczony')),
  powod                  TEXT NOT NULL DEFAULT '',
  odlaczony              INTEGER NOT NULL DEFAULT 0,
  stop_lokalny           INTEGER NOT NULL DEFAULT 0,
  dopisany_do            TEXT REFERENCES przebiegi(id),
  user_msg_id            INTEGER,
  cialo_sha              TEXT,
  kroki                  TEXT,
  proby                  INTEGER NOT NULL DEFAULT 0,
  nastepna_proba_at      REAL,
  utworzony_at           REAL NOT NULL,
  wyslany_at             REAL, przyjety_at REAL, zakonczony_at REAL,
  ostatnie_zdarzenie_at  REAL,
  ostatnie_zdarzenie     TEXT,
  zgoda                  TEXT,
  blad                   TEXT,
  uzycie                 TEXT,
  payload                TEXT,
  payload_sha            TEXT,
  autor                  TEXT,
  idem                   TEXT NOT NULL UNIQUE,
  ponowienie_z           TEXT REFERENCES przebiegi(id)
);
CREATE INDEX przebiegi_aktywne ON przebiegi (stan)
  WHERE stan IN ('kolejka','wysylanie','przyjety','pracuje','czeka_na_ture','czeka_na_zgode','zatrzymywanie','dopisany');
CREATE INDEX przebiegi_watek ON przebiegi (watek_id, utworzony_at);
CREATE INDEX przebiegi_sha ON przebiegi (payload_sha);
CREATE INDEX przebiegi_lancuch ON przebiegi (lancuch_id);
CREATE INDEX przebiegi_nadzor ON przebiegi (watek_id, nadzor_stan) WHERE nadzor_stan = 'czeka';

CREATE TABLE przekazy (
  klucz          TEXT PRIMARY KEY,
  watek_id       TEXT REFERENCES watki(id) ON DELETE CASCADE,
  akcja          TEXT NOT NULL CHECK (akcja IN ('przekaz','zapytaj')),
  od_agenta      TEXT NOT NULL,
  do_agenta      TEXT,
  tresc          TEXT NOT NULL,
  pliki          TEXT NOT NULL DEFAULT '[]',
  stan           TEXT NOT NULL CHECK (stan IN ('przyjety','odrzucony')),
  powod          TEXT NOT NULL DEFAULT '',
  rola           TEXT NOT NULL DEFAULT 'rozmowa',
  lancuch_id     TEXT,
  przebieg_id    TEXT REFERENCES przebiegi(id),
  z_przebiegu    TEXT REFERENCES przebiegi(id),
  spoznione      INTEGER NOT NULL DEFAULT 0,
  at             REAL NOT NULL
);

CREATE TABLE karty (
  task_id        TEXT PRIMARY KEY,
  watek_id       TEXT REFERENCES watki(id) ON DELETE SET NULL,
  agent_zrodlo   TEXT NOT NULL,
  rodzic_task_id TEXT,
  utworzona_at   REAL NOT NULL,
  ostatni_stan   TEXT,
  zmieniona_at   REAL
);
CREATE INDEX karty_watek ON karty (watek_id, utworzona_at);

CREATE TABLE blokady_kart (
  task_id   TEXT PRIMARY KEY,
  powod     TEXT NOT NULL,
  at        REAL NOT NULL
);

CREATE TABLE meta (klucz TEXT PRIMARY KEY, wartosc TEXT NOT NULL);

CREATE TABLE migracje (wersja INTEGER PRIMARY KEY, at REAL NOT NULL);
"""

MIGRACJE: tuple[str, ...] = (MIGRACJA_1,)     # migracja n = MIGRACJE[n - 1]; nowe tylko dopisujemy na końcu

# kolumny JSON i logiczne każdej tabeli (dekodowane przy odczycie, kodowane przy zapisie)
JSON_POLA = {
    "watki": {"ostatni_agenci": []},
    "wpisy": {"adresaci": [], "zalaczniki": [], "obrazy": [], "dane": {}},
    "przebiegi": {"payload": None, "autor": None, "zgoda": None, "blad": None, "uzycie": None, "kroki": None,
                  "nadzor_dla": None},
    "przekazy": {"pliki": []},
}
BOOL_POLA = {
    "watki": ("przypiety", "archiwum"),
    "przebiegi": ("nadzorowany", "odlaczony", "stop_lokalny"),
    "przekazy": ("spoznione",),
    "sesje": ("przypieta",),
}
POLA_PRZEBIEGU = frozenset({
    "watek_id", "wpis_id", "agent", "rola", "zrodlo", "lancuch_id", "lancuch_zrodlo", "hop", "przekaz_z",
    "nadzorowany", "nadzor_stan", "nadzor_przez", "nadzor_zgoda", "nadzor_zgoda_przez", "nadzor_dla", "sesja_id",
    "run_id", "stan", "powod", "odlaczony", "stop_lokalny", "dopisany_do", "user_msg_id", "cialo_sha", "kroki",
    "proby", "nastepna_proba_at", "wyslany_at", "przyjety_at", "zakonczony_at", "ostatnie_zdarzenie_at",
    "ostatnie_zdarzenie", "zgoda", "blad", "uzycie", "payload", "payload_sha", "autor", "ponowienie_z",
})
POLA_PRZEKAZU = frozenset({"klucz", "watek_id", "akcja", "od_agenta", "do_agenta", "tresc", "pliki", "stan", "powod",
                           "rola", "lancuch_id", "przebieg_id", "z_przebiegu", "spoznione", "at"})
POLA_WATKU_ZMIANA = frozenset({"tytul", "tytul_zrodlo", "przypiety", "archiwum", "status", "podglad", "kanal"})
PROFIL_RE = re.compile(r"^[a-z0-9-]+$")


# ----------------------------------------------------------------------------------------------- pomocnicze

def zloz(s: str) -> str:
    """Tekst do wyszukiwania: NFKD bez znaków łączących, ł→l, małe litery (jak wzmianki.zloz)."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.category(c).startswith("M"))
    return s.replace("ł", "l").replace("Ł", "L").lower()


def nowe_id(prefiks: str, teraz: float) -> str:
    """`w_<13 hex ms><8 hex losowo>` (tak samo e_, p_, k_): rośnie z czasem, nie da się zgadnąć."""
    return f"{prefiks}_{int(teraz * 1000):013x}{secrets.token_hex(4)}"


def tytul_z_tresci(tresc: str, *, obrazy: int = 0, at: float | None = None, maks: int = TYTUL_AUTO) -> str:
    """Tytuł z pierwszej wiadomości: białe znaki złożone, cięcie na granicy słowa do `maks` znaków z „…”.
    Sam obraz bez tekstu: „Obraz z <data>”."""
    tekst = " ".join(str(tresc or "").split())
    if not tekst:
        if obrazy:
            return "Obraz z " + time.strftime("%Y-%m-%d", time.localtime(at or time.time()))
        return ""
    if len(tekst) <= maks:
        return tekst
    ciecie = tekst[:maks - 1]
    if " " in ciecie and not tekst[maks - 1].isspace():
        ciecie = ciecie.rsplit(" ", 1)[0]
    return ciecie.rstrip(" ,.;:-") + "…"


def podglad_z(tekst: str, maks: int = PODGLAD_MAX) -> str:
    tekst = " ".join(str(tekst or "").split())
    return tekst if len(tekst) <= maks else tekst[:maks - 1].rstrip() + "…"


def _json(v: Any) -> str | None:
    return None if v is None else json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def _z_json(raw: Any, domyslna: Any) -> Any:
    if raw is None:
        return domyslna if domyslna is None else type(domyslna)()
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return domyslna if domyslna is None else type(domyslna)()


def _wiersz(tabela: str, row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for pole, domyslna in JSON_POLA.get(tabela, {}).items():
        if pole in d:
            d[pole] = _z_json(d[pole], domyslna)
    for pole in BOOL_POLA.get(tabela, ()):
        if pole in d and d[pole] is not None:
            d[pole] = bool(d[pole])
    return d


def _do_bazy(tabela: str, pola: Mapping[str, Any]) -> dict:
    out = {}
    for k, v in pola.items():
        if k in JSON_POLA.get(tabela, {}) and not (v is None or isinstance(v, str)):
            v = _json(v)
        elif isinstance(v, bool):
            v = int(v)
        out[k] = v
    return out


def _like(q: str) -> str:
    return "%" + zloz(q).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


# ----------------------------------------------------------------------------------------------- magazyn

def _przenosne():
    """przenosne.py wtyczki (załadowany przez plugin_api jako jarvo_hq_przenosne albo z pliku obok)."""
    mod = sys.modules.get("jarvo_hq_przenosne")
    if mod is None:
        spec = importlib.util.spec_from_file_location("jarvo_hq_przenosne", Path(__file__).with_name("przenosne.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["jarvo_hq_przenosne"] = mod
        spec.loader.exec_module(mod)
    return mod


def _tryb_0600(sciezka: Path) -> None:
    """Plik tylko dla właściciela: chmod 0600, na Windows ACL (przenosne.tryb_pliku)."""
    _przenosne().tryb_pliku(sciezka, 0o600)


def _plik_0600(sciezka: Path) -> None:
    """Pusty plik z trybem 0600, zanim sqlite go otworzy (bez okna z trybem z umask); istniejący zostaje."""
    try:
        os.close(os.open(sciezka, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    except FileExistsError:
        return
    except OSError:
        pass
    try:
        _tryb_0600(sciezka)
    except OSError:
        pass


class Rozmowy:
    """Repozytorium rozmowy.db. Tworzy je wątek silnika (jedno połączenie piszące, chronione blokadą); metody
    odczytu wołane z innego wątku otwierają własne krótkie połączenie (WAL: nie czekają na zapis)."""

    def __init__(self, sciezka: Path | str = SCIEZKA, zegar: Callable[[], float] = time.time):
        self.sciezka = Path(sciezka)
        self.zegar = zegar
        self._blokada = threading.RLock()
        self._watek = threading.get_ident()
        self.sciezka.parent.mkdir(parents=True, exist_ok=True)
        _plik_0600(self.sciezka)            # treści właściciela: plik od początku 0600 (sqlite nie zmienia trybu)
        self._conn = self._polacz()

    # ---- połączenia
    def _polacz(self, tylko_odczyt: bool = False) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.sciezka), timeout=5, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        if tylko_odczyt:
            conn.execute("PRAGMA query_only = 1")
        else:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def zamknij(self) -> None:
        with self._blokada:
            self._conn.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        """Jedna transakcja zapisu (BEGIN IMMEDIATE): całość albo nic."""
        with self._blokada:
            c = self._conn
            c.execute("BEGIN IMMEDIATE")
            try:
                yield c
            except BaseException:
                c.execute("ROLLBACK")
                raise
            c.execute("COMMIT")

    @contextmanager
    def _odczyt(self) -> Iterator[sqlite3.Connection]:
        if threading.get_ident() == self._watek:
            with self._blokada:
                yield self._conn
            return
        conn = self._polacz(tylko_odczyt=True)
        try:
            yield conn
        finally:
            conn.close()

    # ---- migracje
    def wersja(self) -> int:
        with self._odczyt() as c:
            return int(c.execute("PRAGMA user_version").fetchone()[0])

    def migruj(self) -> int:
        """Numerowane migracje, każda w jednej transakcji; przed zmianą istniejącej bazy kopia `.bak-v<stara>`."""
        with self._blokada:
            c = self._conn
            stara = int(c.execute("PRAGMA user_version").fetchone()[0])
            if stara > len(MIGRACJE):
                raise RuntimeError(f"rozmowy.db ma wersję {stara}, nowszą niż ten kod ({len(MIGRACJE)})")
            if stara == len(MIGRACJE):
                return stara
            if stara > 0:
                self._kopia(stara)
            for nr in range(stara + 1, len(MIGRACJE) + 1):
                teraz = self.zegar()
                skrypt = (f"BEGIN IMMEDIATE;\n{MIGRACJE[nr - 1]}\n"
                          f"INSERT INTO migracje (wersja, at) VALUES ({nr}, {teraz!r});\n"
                          f"INSERT OR IGNORE INTO meta (klucz, wartosc) VALUES ('utworzono', '{teraz!r}');\n"
                          f"PRAGMA user_version = {nr};\nCOMMIT;")
                try:
                    c.executescript(skrypt)
                except BaseException:
                    if c.in_transaction:
                        c.execute("ROLLBACK")
                    raise
            return len(MIGRACJE)

    def _kopia(self, wersja: int) -> Path:
        cel = self.sciezka.with_name(f"{self.sciezka.name}.bak-v{wersja}")
        cel.unlink(missing_ok=True)
        _plik_0600(cel)
        dst = sqlite3.connect(str(cel))
        try:
            self._conn.backup(dst)
        finally:
            dst.close()
        try:
            _tryb_0600(cel)
        except OSError:
            pass
        kopie = sorted(self.sciezka.parent.glob(self.sciezka.name + ".bak-v*"),
                       key=lambda p: int(p.name.rsplit("-v", 1)[-1]) if p.name.rsplit("-v", 1)[-1].isdigit() else -1)
        for stara in kopie[:-KOPIE_MIGRACJI]:
            stara.unlink(missing_ok=True)
        return cel

    # ------------------------------------------------------------------------------------------- wątki
    _WATEK_SQL = ("SELECT w.*, (SELECT json_group_array(agent) FROM (SELECT agent FROM czlonkowie c "
                  "WHERE c.watek_id = w.id AND c.rola = 'rozmowa' ORDER BY c.dodany_at, c.agent)) AS czlonkowie_json "
                  "FROM watki w")

    def _watek_z(self, row: sqlite3.Row | None) -> dict | None:
        d = _wiersz("watki", row)
        if d is None:
            return None
        d["czlonkowie"] = _z_json(d.pop("czlonkowie_json", None), [])
        d.pop("tytul_szukaj", None)
        return d

    def utworz_watek(self, *, tytul: str = "", rodzaj: str = "zwykly", koordynator: str = "jarvo",
                     kanal: str | None = None, tytul_zrodlo: str | None = None, at: float | None = None) -> dict:
        teraz = self.zegar() if at is None else at
        tytul = str(tytul or "")[:TYTUL_MAX]
        wid = nowe_id("w", teraz)
        zrodlo = tytul_zrodlo or ("import" if rodzaj == "import" else "auto")
        with self._tx() as c:
            c.execute("INSERT INTO watki (id, tytul, tytul_zrodlo, tytul_szukaj, rodzaj, koordynator, kanal, "
                      "utworzony_at, aktywnosc_at, przeczytane_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (wid, tytul, zrodlo, zloz(tytul), rodzaj, koordynator, kanal, teraz, teraz, teraz))
        return self.watek(wid)

    def watek(self, wid: str) -> dict | None:
        with self._odczyt() as c:
            return self._watek_z(c.execute(self._WATEK_SQL + " WHERE w.id = ?", (wid,)).fetchone())

    def lista(self, *, filtr: str = "rozmowy", q: str = "", limit: int = 50,
              przed: tuple | None = None) -> tuple[list[dict], tuple | None]:
        """Strona listy wątków (najnowsza aktywność najpierw; w „rozmowy” przypięte na górze). Filtry: rozmowy,
        przypiete, archiwum, kosz; wątki `test` (próba agenta) nigdy na liście. Kursor `przed`/`dalej` =
        (aktywnosc_at, id, przypiety); trasa podaje go klientowi jako nieprzezroczysty tekst (`kursor_tekst`)."""
        limit = max(1, min(int(limit or 50), 50))
        warunki, arg = [], []
        if filtr == "kosz":
            warunki.append("w.usuniety_at IS NOT NULL")
        else:
            warunki.append("w.usuniety_at IS NULL AND w.rodzaj != 'test'")
            if filtr == "archiwum":
                warunki.append("w.archiwum = 1")
            elif filtr == "przypiete":
                warunki.append("w.przypiety = 1 AND w.archiwum = 0")
            else:
                warunki.append("w.archiwum = 0")
        if q.strip():
            warunki.append("(w.tytul_szukaj LIKE ? ESCAPE '\\' OR EXISTS (SELECT 1 FROM wpisy e WHERE e.watek_id = w.id "
                           "AND e.rodzaj = 'wlasciciel' AND e.szukaj LIKE ? ESCAPE '\\'))")
            arg += [_like(q), _like(q)]
        z_przypietymi = filtr == "rozmowy"
        if przed:
            ts, id_, strefa = _kursor(przed)
            if z_przypietymi:
                warunki.append("(w.przypiety < ? OR (w.przypiety = ? AND (w.aktywnosc_at < ? OR "
                               "(w.aktywnosc_at = ? AND w.id < ?))))")
                arg += [strefa, strefa, ts, ts, id_]
            else:
                warunki.append("(w.aktywnosc_at < ? OR (w.aktywnosc_at = ? AND w.id < ?))")
                arg += [ts, ts, id_]
        porzadek = ("w.przypiety DESC, " if z_przypietymi else "") + "w.aktywnosc_at DESC, w.id DESC"
        sql = f"{self._WATEK_SQL} WHERE {' AND '.join(warunki)} ORDER BY {porzadek} LIMIT ?"
        with self._odczyt() as c:
            rows = c.execute(sql, (*arg, limit + 1)).fetchall()
        watki = [self._watek_z(r) for r in rows[:limit]]
        dalej = None
        if len(rows) > limit:
            ost = watki[-1]
            dalej = (ost["aktywnosc_at"], ost["id"], int(bool(z_przypietymi and ost["przypiety"])))
        return watki, dalej

    def zmien(self, wid: str, **pola) -> dict:
        nieznane = set(pola) - POLA_WATKU_ZMIANA
        if nieznane:
            raise ValueError(f"nieznane pola wątku: {sorted(nieznane)}")
        if "tytul" in pola:
            tytul = " ".join(str(pola["tytul"] or "").split())[:TYTUL_MAX]
            pola["tytul"] = tytul
            pola["tytul_szukaj"] = zloz(tytul)
            pola.setdefault("tytul_zrodlo", "wlasciciel")
        if "podglad" in pola:
            pola["podglad"] = podglad_z(pola["podglad"])
        if pola:
            dane = _do_bazy("watki", pola)
            with self._tx() as c:
                c.execute(f"UPDATE watki SET {', '.join(f'{k} = ?' for k in dane)} WHERE id = ?", (*dane.values(), wid))
        return self.watek(wid)

    def usun(self, wid: str, *, trwale: bool = False) -> list[dict]:
        """Do kosza (`usuniety_at`) albo na stałe. Sesje Hermesa nigdy nie są usuwane: rodowód w `sesje` i karty
        zostają z `watek_id = NULL` (nagrobek). Zwraca sesje wątku (silnik odpina przypięte po trwałym usunięciu)."""
        with self._tx() as c:
            sesje = [_wiersz("sesje", r) for r in c.execute("SELECT * FROM sesje WHERE watek_id = ?", (wid,))]
            if trwale:
                c.execute("DELETE FROM watki WHERE id = ?", (wid,))
            else:
                c.execute("UPDATE watki SET usuniety_at = ? WHERE id = ? AND usuniety_at IS NULL", (self.zegar(), wid))
        return sesje

    def przywroc(self, wid: str) -> dict | None:
        with self._tx() as c:
            c.execute("UPDATE watki SET usuniety_at = NULL WHERE id = ?", (wid,))
        return self.watek(wid)

    def przeczytane(self, wid: str, do_at: float) -> None:
        with self._tx() as c:
            c.execute("UPDATE watki SET przeczytane_at = max(przeczytane_at, ?), "
                      "nieprzeczytane = CASE WHEN ? >= aktywnosc_at THEN 0 ELSE nieprzeczytane END WHERE id = ?",
                      (do_at, do_at, wid))

    def aktywnosc(self, wid: str, *, at: float, podglad: str | None = None, nieprzeczytane_plus: int = 0,
                  status: str | None = None, agent: str | None = None) -> dict | None:
        """Nowa aktywność w wątku: sortowanie, podgląd, licznik nieprzeczytanych, status; wątek z archiwum wraca na
        listę (archiwum = „nic się tu nie dzieje”). `agent`: ostatnia praca (≤ 2 agentów, najnowszy pierwszy)."""
        with self._tx() as c:
            row = c.execute("SELECT ostatni_agenci FROM watki WHERE id = ?", (wid,)).fetchone()
            if row is None:
                return None
            ostatni = _z_json(row["ostatni_agenci"], [])
            if agent:
                ostatni = [agent] + [a for a in ostatni if a != agent]
            sql = ["aktywnosc_at = max(aktywnosc_at, ?)", "nieprzeczytane = nieprzeczytane + ?", "archiwum = 0",
                   "ostatni_agenci = ?"]
            arg: list[Any] = [at, nieprzeczytane_plus, _json(ostatni[:OSTATNI_MAX])]
            if podglad is not None:
                sql.append("podglad = ?")
                arg.append(podglad_z(podglad))
            if status is not None:
                sql.append("status = ?")
                arg.append(status)
            c.execute(f"UPDATE watki SET {', '.join(sql)} WHERE id = ?", (*arg, wid))
        return self.watek(wid)

    # ------------------------------------------------------------------------------------------- członkowie i sesje
    def czlonek(self, wid: str, agent: str, rola: str = "rozmowa") -> dict | None:
        with self._odczyt() as c:
            return _wiersz("czlonkowie", c.execute("SELECT * FROM czlonkowie WHERE watek_id = ? AND agent = ? AND rola = ?",
                                                   (wid, agent, rola)).fetchone())

    def czlonkowie(self, wid: str, *, rola: str | None = None) -> list[dict]:
        sql, arg = "SELECT * FROM czlonkowie WHERE watek_id = ?", [wid]
        if rola:
            sql += " AND rola = ?"
            arg.append(rola)
        with self._odczyt() as c:
            return [_wiersz("czlonkowie", r) for r in c.execute(sql + " ORDER BY dodany_at, agent", arg)]

    def zapewnij_czlonka(self, wid: str, agent: str, rola: str = "rozmowa") -> dict:
        """Członek wątku (tworzony przy pierwszym zwróceniu się do agenta); rola `nadzor` = osobna sesja nadzoru
        koordynatora. Sesja Hermesa powstaje później (dyspozytor, `ustaw_sesje`)."""
        with self._tx() as c:
            c.execute("INSERT OR IGNORE INTO czlonkowie (watek_id, agent, rola, dodany_at) VALUES (?, ?, ?, ?)",
                      (wid, agent, rola, self.zegar()))
        return self.czlonek(wid, agent, rola)

    def ustaw_sesje(self, wid: str, agent: str, sesja_id: str, *, rola: str = "rozmowa", powod: str = "start",
                    rodzic: str | None = None, przypieta: bool = False) -> dict:
        """Sesja Hermesa członka: pierwsza zostaje w `sesja_id`, każda nowa (kompresja, rotacja nadzoru) staje się
        `sesja_tip`; wpis w rodowodzie `sesje`. Sesja należy najwyżej do jednego wątku (ValueError przy próbie
        przypięcia cudzej)."""
        teraz = self.zegar()
        with self._tx() as c:
            obca = c.execute("SELECT watek_id FROM sesje WHERE agent = ? AND sesja_id = ?", (agent, sesja_id)).fetchone()
            if obca is not None and obca["watek_id"] != wid:
                raise ValueError(f"sesja {agent}/{sesja_id} należy już do innego wątku")
            c.execute("INSERT OR IGNORE INTO czlonkowie (watek_id, agent, rola, dodany_at) VALUES (?, ?, ?, ?)",
                      (wid, agent, rola, teraz))
            c.execute("INSERT OR IGNORE INTO sesje (agent, sesja_id, watek_id, rola, rodzic_id, powod, przypieta, dodana_at) "
                      "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (agent, sesja_id, wid, rola, rodzic, powod, int(przypieta), teraz))
            c.execute("UPDATE czlonkowie SET sesja_id = COALESCE(sesja_id, ?), sesja_tip = ?, "
                      "tury = CASE WHEN ? = 'rotacja' THEN 0 ELSE tury END "
                      "WHERE watek_id = ? AND agent = ? AND rola = ?", (sesja_id, sesja_id, powod, wid, agent, rola))
        return self.czlonek(wid, agent, rola)

    def zmien_czlonka(self, wid: str, agent: str, rola: str = "rozmowa", *, widzial_at: float | None = None,
                      odczyt_id: int | None = None, tury_plus: int = 0) -> dict | None:
        """Znacznik „widział do” (blok kontekstu), znak wodny obserwatora (`odczyt_id`) i licznik tur nadzoru."""
        with self._tx() as c:
            c.execute("UPDATE czlonkowie SET widzial_at = max(widzial_at, COALESCE(?, widzial_at)), "
                      "odczyt_id = max(odczyt_id, COALESCE(?, odczyt_id)), tury = tury + ? "
                      "WHERE watek_id = ? AND agent = ? AND rola = ?", (widzial_at, odczyt_id, tury_plus, wid, agent, rola))
        return self.czlonek(wid, agent, rola)

    def ustaw_przypieta(self, agent: str, sesja_id: str, przypieta: bool) -> None:
        with self._tx() as c:
            c.execute("UPDATE sesje SET przypieta = ? WHERE agent = ? AND sesja_id = ?", (int(przypieta), agent, sesja_id))

    def watek_sesji(self, agent: str, sesja_id: str) -> tuple[str, str] | None:
        """(watek_id, rola) dla sesji Hermesa agenta; None dla obcej sesji albo nagrobka po usuniętym wątku."""
        with self._odczyt() as c:
            r = c.execute("SELECT watek_id, rola FROM sesje WHERE agent = ? AND sesja_id = ?", (agent, sesja_id)).fetchone()
        return (r["watek_id"], r["rola"]) if r and r["watek_id"] else None

    def sesje_watku(self, wid: str, *, agent: str | None = None, rola: str | None = None) -> list[dict]:
        """Rodowód sesji wątku w kolejności dodania (oś czasu czyta każdą sesję rodowodu)."""
        sql, arg = "SELECT * FROM sesje WHERE watek_id = ?", [wid]
        for pole, v in (("agent", agent), ("rola", rola)):
            if v:
                sql += f" AND {pole} = ?"
                arg.append(v)
        with self._odczyt() as c:
            return [_wiersz("sesje", r) for r in c.execute(sql + " ORDER BY dodana_at, sesja_id", arg)]

    def sesje_czlonkow(self, agent: str | None = None, *, nieprzypiete: bool = False) -> list[dict]:
        """Wszystkie sesje znane aplikacji (z nagrobkami): obserwator, wykluczenie z listy wszystkiego, ponowne
        przypinanie (`nieprzypiete=True`: tylko sesje żywych wątków jeszcze nieprzypięte w Hermesie)."""
        sql, arg = "SELECT * FROM sesje WHERE 1 = 1", []
        if agent:
            sql += " AND agent = ?"
            arg.append(agent)
        if nieprzypiete:
            sql += " AND przypieta = 0 AND watek_id IS NOT NULL"
        with self._odczyt() as c:
            return [_wiersz("sesje", r) for r in c.execute(sql + " ORDER BY dodana_at", arg)]

    # ------------------------------------------------------------------------------------------- wpisy
    def dodaj_wpis(self, wid: str, *, rodzaj: str, tekst: str = "", tresc: str = "", adresaci: Iterable[str] = (),
                   tryb: str = "jarvo", zalaczniki: Iterable[Mapping] = (), obrazy: Iterable[Mapping] = (),
                   dane: Mapping | None = None, klucz: str | None = None, at: float | None = None) -> dict:
        """Wpis wątku z kolejnym `seq`. Idempotentny po (wątek, klucz): ten sam klucz zwraca istniejący wpis
        z polem `powtorzony: True` (podwójne kliknięcie, ponowione żądanie). Obrazy tylko jako ścieżki inboxa."""
        obrazy = [dict(o) for o in obrazy]
        if any(str(o.get("path", "")).startswith("data:") or "dane" in o for o in obrazy):
            raise ValueError("obrazy w rozmowy.db tylko jako ścieżki inboxa, nigdy data URL")
        teraz = self.zegar() if at is None else at
        eid = nowe_id("e", teraz)
        try:
            with self._tx() as c:
                if klucz is not None:
                    jest = c.execute("SELECT * FROM wpisy WHERE watek_id = ? AND klucz = ?", (wid, klucz)).fetchone()
                    if jest is not None:
                        return {**_wiersz("wpisy", jest), "powtorzony": True}
                seq = c.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM wpisy WHERE watek_id = ?", (wid,)).fetchone()[0]
                c.execute("INSERT INTO wpisy (id, watek_id, seq, rodzaj, tekst, tresc, szukaj, adresaci, tryb, zalaczniki, "
                          "obrazy, dane, klucz, utworzony_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (eid, wid, seq, rodzaj, tekst, tresc, zloz(tekst) if rodzaj == "wlasciciel" else "",
                           _json(list(adresaci)), tryb, _json([dict(z) for z in zalaczniki]), _json(obrazy),
                           _json(dict(dane or {})), klucz, teraz))
        except sqlite3.IntegrityError:
            jest = self.wpis_po_kluczu(wid, klucz) if klucz is not None else None
            if jest is None:
                raise
            return {**jest, "powtorzony": True}
        return {**self.wpis(eid), "powtorzony": False}

    def wpis(self, eid: str) -> dict | None:
        with self._odczyt() as c:
            return _wiersz("wpisy", c.execute("SELECT * FROM wpisy WHERE id = ?", (eid,)).fetchone())

    def wpis_po_kluczu(self, wid: str, klucz: str) -> dict | None:
        with self._odczyt() as c:
            return _wiersz("wpisy", c.execute("SELECT * FROM wpisy WHERE watek_id = ? AND klucz = ?", (wid, klucz)).fetchone())

    def watek_po_kluczu(self, klucz: str) -> dict | None:
        """Wątek, którego pierwszy wpis (seq 1, właściciel) ma ten klucz: `POST /rozmowy` z wiadomością powtórzone po
        zerwanym połączeniu dostaje ten sam wątek. Bez osobnego indeksu: pętla po wątkach (CROSS JOIN ustala kolejność),
        a w każdym indeks UNIQUE (watek_id, klucz)."""
        with self._odczyt() as c:
            r = c.execute("SELECT w.id FROM watki w CROSS JOIN wpisy e ON e.watek_id = w.id AND e.klucz = ? "
                          "WHERE e.seq = 1 AND e.rodzaj = 'wlasciciel' ORDER BY w.utworzony_at LIMIT 1", (klucz,)).fetchone()
        return self.watek(r[0]) if r else None

    def wpisy(self, wid: str, *, przed_at: float | None = None, po_at: float | None = None, limit: int = 200) -> list[dict]:
        """Wpisy wątku po `seq` rosnąco; `przed_at` = najnowsze `limit` przed tą chwilą, `po_at` = po niej."""
        sql, arg = "SELECT * FROM wpisy WHERE watek_id = ?", [wid]
        if przed_at is not None:
            sql += " AND utworzony_at < ?"
            arg.append(przed_at)
        if po_at is not None:
            sql += " AND utworzony_at > ?"
            arg.append(po_at)
        sql += " ORDER BY seq DESC LIMIT ?" if po_at is None else " ORDER BY seq ASC LIMIT ?"
        with self._odczyt() as c:
            rows = [_wiersz("wpisy", r) for r in c.execute(sql, (*arg, max(1, int(limit))))]
        return rows if po_at is not None else rows[::-1]

    # ------------------------------------------------------------------------------------------- przebiegi
    def dodaj_przebieg(self, **pola) -> dict:
        """Nowy przebieg (domyślnie `kolejka(start)`); `idem` = `jarvo-<id>` (Idempotency-Key bramy),
        `lancuch_id` domyślnie = wpis, który go zaczął."""
        nieznane = set(pola) - POLA_PRZEBIEGU - {"id", "utworzony_at"}
        if nieznane:
            raise ValueError(f"nieznane pola przebiegu: {sorted(nieznane)}")
        teraz = pola.pop("utworzony_at", None) or self.zegar()
        pid = pola.pop("id", None) or nowe_id("p", teraz)
        pola.setdefault("stan", "kolejka")
        pola.setdefault("powod", "start" if pola["stan"] == "kolejka" else "")
        if not pola.get("lancuch_id"):
            if not pola.get("wpis_id"):
                raise ValueError("przebieg bez łańcucha: podaj lancuch_id albo wpis_id")
            pola["lancuch_id"] = pola["wpis_id"]
        dane = _do_bazy("przebiegi", {**pola, "id": pid, "idem": f"jarvo-{pid}", "utworzony_at": teraz})
        with self._tx() as c:
            c.execute(f"INSERT INTO przebiegi ({', '.join(dane)}) VALUES ({', '.join('?' * len(dane))})", tuple(dane.values()))
        return self.przebieg(pid)

    def usun_przebieg(self, pid: str) -> None:
        """Wiersz przebiegu, który nigdy nie ruszył (steer odrzucony przez bramę): bez śladu."""
        with self._tx() as c:
            c.execute("DELETE FROM przebiegi WHERE id = ?", (pid,))

    def usun_nagrobki(self, agent: str) -> int:
        """Nagrobki sesji (`watek_id IS NULL`) jednego profilu: sprzątanie po usuniętym profilu (agenci testowi E2E)."""
        with self._tx() as c:
            return c.execute("DELETE FROM sesje WHERE agent = ? AND watek_id IS NULL", (agent,)).rowcount

    def przebieg(self, pid: str) -> dict | None:
        with self._odczyt() as c:
            return _wiersz("przebiegi", c.execute("SELECT * FROM przebiegi WHERE id = ?", (pid,)).fetchone())

    def zmien_przebieg(self, pid: str, **pola) -> dict:
        nieznane = set(pola) - POLA_PRZEBIEGU
        if nieznane:
            raise ValueError(f"nieznane pola przebiegu: {sorted(nieznane)}")
        if pola:
            dane = _do_bazy("przebiegi", pola)
            with self._tx() as c:
                c.execute(f"UPDATE przebiegi SET {', '.join(f'{k} = ?' for k in dane)} WHERE id = ?", (*dane.values(), pid))
        return self.przebieg(pid)

    def _przebiegi(self, gdzie: str, arg: Iterable[Any] = ()) -> list[dict]:
        with self._odczyt() as c:
            return [_wiersz("przebiegi", r) for r in
                    c.execute(f"SELECT * FROM przebiegi WHERE {gdzie} ORDER BY utworzony_at, id", tuple(arg))]

    def przebiegi_aktywne(self) -> list[dict]:
        """Nieskończone przebiegi wszystkich wątków (FIFO po czasie zlecenia): dyspozytor, odzyskiwanie po restarcie."""
        return self._przebiegi(f"stan IN ({', '.join('?' * len(STANY_AKTYWNE))})", STANY_AKTYWNE)

    def przebiegi_watku(self, wid: str, *, aktywne: bool = False) -> list[dict]:
        if aktywne:
            return self._przebiegi(f"watek_id = ? AND stan IN ({', '.join('?' * len(STANY_AKTYWNE))})", (wid, *STANY_AKTYWNE))
        return self._przebiegi("watek_id = ?", (wid,))

    def przebiegi_do_ponowienia(self, wid: str, *, limit: int = 5) -> list[dict]:
        """Nieudane, przerwane, zgubione i zatrzymane przebiegi rozmowy wątku, po których ten agent nie pracował już
        w tym wątku (ta sama zasada co „Czeka na Ciebie”): migawka wątku niesie je, żeby karta z „Ponów” przetrwała
        przeładowanie strony. Najnowsze, najwyżej `limit`."""
        return self._przebiegi(
            "id IN (SELECT p.id FROM przebiegi p WHERE p.watek_id = ? AND p.rola = 'rozmowa' AND COALESCE(p.zrodlo, '') != 'nadzor' "
            "AND p.stan IN ('blad', 'przerwane', 'zgubione', 'zatrzymane') AND NOT EXISTS (SELECT 1 FROM przebiegi n "
            "WHERE n.watek_id = p.watek_id AND n.agent = p.agent AND n.rola = 'rozmowa' AND n.utworzony_at > p.utworzony_at) "
            "ORDER BY p.utworzony_at DESC LIMIT ?)", (wid, max(1, min(int(limit), 20))))

    def przebiegi_lancucha(self, lancuch_id: str) -> list[dict]:
        return self._przebiegi("lancuch_id = ?", (lancuch_id,))

    def nasze_wiersze(self, wid: str) -> dict[str, dict]:
        """Przebiegi wątku, które wysłały turę: po czym scalanie rozpozna nasze wiersze użytkownika w state.db
        (`user_msg_id`, a przed nim `payload_sha` od `wyslany_at − 2 s`) i wiersze tury w toku."""
        with self._odczyt() as c:
            rows = c.execute("SELECT id, agent, rola, sesja_id, user_msg_id, payload_sha, wyslany_at, stan, zrodlo "
                             "FROM przebiegi WHERE watek_id = ? AND (wyslany_at IS NOT NULL OR user_msg_id IS NOT NULL)",
                             (wid,)).fetchall()
        return {r["id"]: {**dict(r), "aktywny": r["stan"] in STANY_AKTYWNE} for r in rows}

    def do_nadzoru(self, wid: str) -> list[dict]:
        return self._przebiegi("watek_id = ? AND nadzor_stan = 'czeka'", (wid,))

    # ------------------------------------------------------------------------------------------- przekazania, karty, meta
    def dodaj_przekaz(self, **pola) -> dict:
        """Prośba narzędzia `rozmowa` (przyjęta albo odrzucona); idempotentna po kluczu `<profil>:<sesja>:<id wywołania>`."""
        nieznane = set(pola) - POLA_PRZEKAZU
        if nieznane or not pola.get("klucz"):
            raise ValueError(f"przekaz: brak klucza albo nieznane pola {sorted(nieznane)}")
        pola.setdefault("at", self.zegar())
        dane = _do_bazy("przekazy", pola)
        with self._tx() as c:
            c.execute(f"INSERT OR IGNORE INTO przekazy ({', '.join(dane)}) VALUES ({', '.join('?' * len(dane))})",
                      tuple(dane.values()))
        return self.przekaz(pola["klucz"])

    def przekaz(self, klucz: str) -> dict | None:
        with self._odczyt() as c:
            return _wiersz("przekazy", c.execute("SELECT * FROM przekazy WHERE klucz = ?", (klucz,)).fetchone())

    def przypnij_karte(self, task_id: str, wid: str | None, agent_zrodlo: str, rodzic: str | None = None) -> bool:
        """Karta kanbana wątku (powiązanie po sesji pochodzenia); True, gdy nowa."""
        with self._tx() as c:
            cur = c.execute("INSERT OR IGNORE INTO karty (task_id, watek_id, agent_zrodlo, rodzic_task_id, utworzona_at) "
                            "VALUES (?, ?, ?, ?, ?)", (task_id, wid, agent_zrodlo, rodzic, self.zegar()))
            return cur.rowcount == 1

    def karty_watku(self, wid: str) -> list[dict]:
        with self._odczyt() as c:
            return [dict(r) for r in c.execute("SELECT * FROM karty WHERE watek_id = ? ORDER BY utworzona_at, task_id", (wid,))]

    def zmien_karte(self, task_id: str, *, stan: str) -> None:
        with self._tx() as c:
            c.execute("UPDATE karty SET ostatni_stan = ?, zmieniona_at = ? WHERE task_id = ?", (stan, self.zegar(), task_id))

    def zablokuj_karte(self, task_id: str, powod: str) -> bool:
        """Karta zatrzymana przez aplikację (usunięty wątek, nieaktywny agent): True tylko za pierwszym razem."""
        with self._tx() as c:
            return c.execute("INSERT OR IGNORE INTO blokady_kart (task_id, powod, at) VALUES (?, ?, ?)",
                             (task_id, powod, self.zegar())).rowcount == 1

    def meta(self, klucz: str, domyslna: str | None = None) -> str | None:
        with self._odczyt() as c:
            r = c.execute("SELECT wartosc FROM meta WHERE klucz = ?", (klucz,)).fetchone()
        return r["wartosc"] if r else domyslna

    def ustaw_meta(self, klucz: str, wartosc: str) -> None:
        with self._tx() as c:
            c.execute("INSERT INTO meta (klucz, wartosc) VALUES (?, ?) ON CONFLICT(klucz) DO UPDATE SET wartosc = excluded.wartosc",
                      (klucz, str(wartosc)))

    def usun_meta(self, klucz: str) -> bool:
        with self._tx() as c:
            return c.execute("DELETE FROM meta WHERE klucz = ?", (klucz,)).rowcount == 1

    def czeka_na_wlasciciela(self, *, limit: int = 4, od: float | None = None) -> list[dict]:
        """„Czeka na Ciebie” na ekranie startu (docs/HQ.md „Ekran startu”): zgody w toku i nieudane przebiegi z ostatniej
        doby, po których ten agent nie pracował już w tym wątku (Ponów zakłada nowy przebieg), tylko z wątków na
        liście (bez archiwum, kosza i prób agenta). Zgody najpierw, potem najnowsze. Bez treści rozmowy."""
        od = self.zegar() - 86400 if od is None else od
        with self._odczyt() as c:
            rows = c.execute(
                "SELECT p.id, p.agent, p.stan, p.watek_id, w.tytul, "
                "COALESCE(p.zakonczony_at, p.ostatnie_zdarzenie_at, p.utworzony_at) AS at FROM przebiegi p "
                "JOIN watki w ON w.id = p.watek_id "
                "WHERE w.usuniety_at IS NULL AND w.archiwum = 0 AND w.rodzaj != 'test' AND p.rola = 'rozmowa' AND ("
                "p.stan = 'czeka_na_zgode' OR (p.stan = 'blad' AND COALESCE(p.zakonczony_at, p.utworzony_at) >= ? "
                "AND NOT EXISTS (SELECT 1 FROM przebiegi n WHERE n.watek_id = p.watek_id AND n.agent = p.agent "
                "AND n.rola = 'rozmowa' AND n.utworzony_at > p.utworzony_at))) "
                "ORDER BY p.stan = 'czeka_na_zgode' DESC, at DESC LIMIT ?", (od, max(1, min(int(limit), 20)))).fetchall()
        return [{"rodzaj": "zgoda" if r["stan"] == "czeka_na_zgode" else "blad", "przebieg": r["id"], "agent": r["agent"],
                 "watek": r["watek_id"], "tytul": r["tytul"], "at": r["at"]} for r in rows]

    # ------------------------------------------------------------------------------------------- sprzątanie, zdrowie
    def sprzataj(self) -> dict:
        """Codziennie: wątki w koszu dłużej niż 30 dni usunięte na stałe (sesje i karty zostają jako nagrobki,
        silnik odpina przypięte sesje z wyniku i woła `ustaw_przypieta(..., False)`), blokady kart 30 dni po końcu
        albo archiwum karty, `payload` wyzerowany 90 dni po końcu przebiegu."""
        teraz = self.zegar()
        with self._tx() as c:
            stare = [r["id"] for r in c.execute("SELECT id FROM watki WHERE usuniety_at IS NOT NULL AND usuniety_at < ?",
                                                (teraz - KOSZ_DNI * 86400,))]
            do_odpiecia = [dict(agent=r["agent"], sesja_id=r["sesja_id"]) for r in c.execute(
                f"SELECT agent, sesja_id FROM sesje WHERE przypieta = 1 AND watek_id IN ({', '.join('?' * len(stare))})", stare)]
            for wid in stare:
                c.execute("DELETE FROM watki WHERE id = ?", (wid,))
            c.execute("DELETE FROM blokady_kart WHERE task_id IN (SELECT task_id FROM karty WHERE ostatni_stan IN "
                      "('done', 'archived') AND zmieniona_at < ?)", (teraz - BLOKADY_DNI * 86400,))
            zerowane = c.execute(
                f"UPDATE przebiegi SET payload = NULL WHERE payload IS NOT NULL AND zakonczony_at IS NOT NULL "
                f"AND zakonczony_at < ? AND stan IN ({', '.join('?' * len(STANY_KONCOWE))})",
                (teraz - PAYLOAD_DNI * 86400, *STANY_KONCOWE)).rowcount
        return {"usuniete": stare, "do_odpiecia": do_odpiecia, "payload_wyzerowane": zerowane}

    def zdrowie(self) -> dict:
        """Liczby do /health (bez treści): stan bazy, wątki, przebiegi aktywne i w kolejce, sesje do przypięcia."""
        try:
            with self._odczyt() as c:
                ok = c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
                watki = c.execute("SELECT count(*) FROM watki WHERE usuniety_at IS NULL").fetchone()[0]
                aktywne = c.execute(f"SELECT count(*) FROM przebiegi WHERE stan IN ({', '.join('?' * len(STANY_W_LIMICIE))})",
                                    STANY_W_LIMICIE).fetchone()[0]
                kolejka = c.execute("SELECT count(*) FROM przebiegi WHERE stan = 'kolejka'").fetchone()[0]
                nieprzypiete = c.execute("SELECT count(*) FROM sesje WHERE przypieta = 0 AND watek_id IS NOT NULL").fetchone()[0]
                wersja = c.execute("PRAGMA user_version").fetchone()[0]
        except sqlite3.Error:
            return {"db_ok": False}
        return {"db_ok": ok, "wersja": wersja, "watki": watki, "przebiegi_aktywne": aktywne, "kolejka": kolejka,
                "sesje_nieprzypiete": nieprzypiete}

    # ------------------------------------------------------------------------------------------- import
    def importuj_sesje(self, agent: str, sesja_id: str, *, tytul: str, aktywnosc_at: float) -> dict | None:
        """Jedna stara rozmowa Bazy jako wątek `import` (jedna transakcja: wątek, członek, rodowód). None, gdy ta
        sesja już należy do jakiegoś wątku (import idempotentny per sesja)."""
        teraz = self.zegar()
        wid = nowe_id("w", teraz)
        with self._tx() as c:
            if c.execute("SELECT 1 FROM sesje WHERE agent = ? AND sesja_id = ?", (agent, sesja_id)).fetchone():
                return None
            c.execute("INSERT INTO watki (id, tytul, tytul_zrodlo, tytul_szukaj, rodzaj, utworzony_at, aktywnosc_at, "
                      "przeczytane_at) VALUES (?, ?, 'import', ?, 'import', ?, ?, ?)",
                      (wid, tytul, zloz(tytul), teraz, aktywnosc_at, aktywnosc_at))
            c.execute("INSERT INTO czlonkowie (watek_id, agent, rola, sesja_id, sesja_tip, widzial_at, dodany_at) "
                      "VALUES (?, ?, 'rozmowa', ?, ?, ?, ?)", (wid, agent, sesja_id, sesja_id, aktywnosc_at, teraz))
            c.execute("INSERT INTO sesje (agent, sesja_id, watek_id, rola, powod, dodana_at) VALUES (?, ?, ?, 'rozmowa', 'import', ?)",
                      (agent, sesja_id, wid, teraz))
        return self.watek(wid)


def _kursor(przed: tuple | list | str) -> tuple[float, str, int]:
    """Kursor listy → (aktywnosc_at, id, strefa przypiętych 1/0); przyjmuje krotkę albo tekst z `kursor_tekst`.
    Zły kursor = ValueError (trasa odpowiada 400)."""
    if isinstance(przed, str):
        strefa_t = przed.startswith("p:")
        czesci = (przed[2:] if strefa_t else przed).split(":")
        if len(czesci) != 2:
            raise ValueError("zły kursor listy")
        przed = (czesci[0], czesci[1], int(strefa_t))
    if len(przed) not in (2, 3):
        raise ValueError("zły kursor listy")
    ts, id_ = float(przed[0]), str(przed[1])
    strefa = int(przed[2]) if len(przed) == 3 else 0
    if not id_ or strefa not in (0, 1):
        raise ValueError("zły kursor listy")
    return ts, id_, strefa


def kursor_tekst(kursor: tuple | None) -> str | None:
    """Kursor listy dla klienta (`?przed=`): `<ts>:<id>`, w strefie przypiętych `p:<ts>:<id>` (id to `w_<hex>`)."""
    if kursor is None:
        return None
    ts, id_, strefa = _kursor(kursor)
    return ("p:" if strefa else "") + f"{ts!r}:{id_}"


# ----------------------------------------------------------------------------------------------- import Bazy

def agenci_z_fleet_json(sciezka: Path | str) -> dict[str, str]:
    """{profil: nazwa wyświetlana} z fleet.json pluginu (`short`, inaczej `title`, inaczej nazwa profilu)."""
    try:
        dane = json.loads(Path(sciezka).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {a["name"]: a.get("short") or a.get("title") or a["name"]
            for a in dane.get("agents", []) if isinstance(a, dict) and a.get("name")}


def _sesja_w_profilu(state_db: Path, sesja_id: str) -> dict | None:
    """Sesja z state.db profilu (tylko odczyt, `mode=ro` przez `as_uri()`): czas ostatniej aktywności i liczba
    wiadomości właściciela; None, gdy sesji nie ma."""
    if not state_db.is_file():
        return None
    conn = sqlite3.connect(state_db.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
    try:
        r = conn.execute("SELECT COALESCE(last_activity_at, started_at) FROM sessions WHERE id = ?", (sesja_id,)).fetchone()
        if r is None:
            return None
        uzytkownika = conn.execute("SELECT count(*) FROM messages WHERE session_id = ? AND role = 'user'",
                                   (sesja_id,)).fetchone()[0]
        return {"aktywnosc_at": float(r[0] or 0), "uzytkownika": int(uzytkownika)}
    finally:
        conn.close()


_ZALOGOWANI: set[str] = set()


def migruj_hq_sessions(db: Rozmowy, plik: Path | str = HQ_SESJE, profile_root: Path | str = PROFILE, *,
                       agenci: Mapping[str, str] | None = None, fleet_json: Path | str | None = None,
                       log: Callable[[str], None] | None = None) -> dict:
    """Stare rozmowy Bazy (`hq-sessions.json` = {agent: id sesji}) jako wątki `import`. Uruchamiane przy każdym
    starcie silnika (stara Baza dalej pisze ten plik), idempotentne per sesja. Pomijane: puste i „None” (stary kod
    tak zapisywał), agenci spoza floty (`agenci` = {profil: nazwa wyświetlana}, domyślnie z `fleet_json`; zapis
    w dzienniku raz na proces), sesje bez wiersza w state.db profilu albo bez żadnej wiadomości właściciela. Sesji
    w Hermesie nie przemianowujemy. Plik zostaje bez zmian."""
    log = log or (lambda _m: None)
    if agenci is None:
        agenci = agenci_z_fleet_json(fleet_json or Path(__file__).with_name("fleet.json"))
    wynik: dict[str, Any] = {"zaimportowane": [], "pominiete": {}}
    try:
        dane = json.loads(Path(plik).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return wynik
    if not isinstance(dane, dict):
        return wynik
    root = Path(profile_root).resolve()
    for agent, sid in sorted(dane.items()):
        sid = str(sid or "").strip()
        if not sid or sid == "None":
            wynik["pominiete"][agent] = "brak_sesji"
            continue
        if not PROFIL_RE.fullmatch(str(agent)) or agent not in agenci:
            wynik["pominiete"][agent] = "nieznany_agent"
            if agent not in _ZALOGOWANI:
                _ZALOGOWANI.add(agent)
                log(f"jarvo-hq: import hq-sessions.json pomija agenta spoza floty {agent!r}")
            continue
        if db.watek_sesji(agent, sid) is not None or any(s["sesja_id"] == sid for s in db.sesje_czlonkow(agent)):
            wynik["pominiete"][agent] = "juz_zaimportowana"
            continue
        state_db = (root / agent / "state.db").resolve()
        if root not in state_db.parents:
            wynik["pominiete"][agent] = "zla_sciezka"
            continue
        try:
            sesja = _sesja_w_profilu(state_db, sid)
        except sqlite3.Error:
            sesja = None
        if sesja is None or sesja["uzytkownika"] == 0:
            wynik["pominiete"][agent] = "pusta_sesja"
            continue
        watek = db.importuj_sesje(agent, sid, tytul=f"Rozmowa z {agenci[agent]} (Baza)", aktywnosc_at=sesja["aktywnosc_at"])
        if watek is None:
            wynik["pominiete"][agent] = "juz_zaimportowana"
        else:
            wynik["zaimportowane"].append(watek["id"])
    return wynik
