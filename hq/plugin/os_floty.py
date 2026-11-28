"""Oś zadań floty (docs/HQ.md „Oś floty”, JARO 28.11): każde zlecenie dowolnego agenta to jeden wpis od chwili zlecenia
do końca, żeby agent widział, co robią inni i które urządzenia są zajęte (28.11 test OLX i SMS Jarva stukały naraz
w telefon `first`), a JARO, co flota zrobiła dziś.

- **Baza** `<dane>/jarvo/state/os-floty.db` (WAL, tryb 0600): tabela `zadania` (kolumny w SCHEMAT) i `stan` (znaczniki
  ostatnio przeczytanego per źródło). Pisze tylko `Zbieracz` w wątku silnika panelu (`runda` co RUNDA_S); trasy,
  `jarvo flota os` i hak „Teraz we flocie” (wiedza/plugin/flota_teraz.py) czytają ją tylko do odczytu. `klucz` wpisu
  (`sesja:<id>`, `karta:<id>`) jak u strażnika telefonu: po nim zasoby i rozróżnienie sesji jednego profilu w haku.
- **Źródła** (agenci niczego nie dopisują): przebiegi panelu (`rozmowy.db`), karty (`kanban.db`), rutyny (`raporty.db`),
  sesje omp (`<skrzynka>/zrobione|bledy/*.json` spoza panelu i tura w toku ze `stan.json`), tury Telegrama Hermesa
  (dzierżawy tur w state.db przez czytnik panelu, tylko od wdrożenia) i zasoby z `<stan>/telefon-zadania.json`
  (strażnik telefonu w zgody/plugin). Brak źródła = pomija je.
- **Wpis raz zapisany zostaje** (historia nie znika z rozmową): zbieracz zmienia stan, koniec, wynik i dokłada zasoby;
  pusty tytuł, prompt i wynik źródła nie zeruje zapisanych (np. treść przebiegu zerowana po 90 dniach).
- Tytuł, prompt i wynik przez `utajnij` (ochrona.py); prompt i wynik pełny ≤ 20 000 znaków, tytuł ≤ 120, wynik ≤ 300.
- **Trasy** (`dolacz`, GET tylko z karty panelu jak raporty.py): `GET /flota/os?dzien=RRRR-MM-DD&agent=<a>` →
  {dzien, dni, zadania: [skrót]}, `GET /flota/os/{id}` → {zadanie}; strumień `flota.os` {zadania: [skrót…]} z wpisami
  zmienionymi w obiegu (najwyżej ZDARZENIE_MAKS najnowszych).
Czysty Python (sqlite3); testy: tests/test_os_floty.py.
"""

import asyncio
import datetime
import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable

RUNDA_S = 5.0
TYTUL_MAKS = 120
WYNIK_MAKS = 300
TEKST_MAKS = 20_000
ZAKLADKA_S = 120.0              # przebiegi i pliki skrzynki: tyle sekund przed znacznikiem czytamy jeszcze raz
WYNIK_WSTECZ_S = 2 * 86400      # odpowiedź Hermesa z state.db tylko dla przebiegów skończonych w tym czasie
ZAJETY_S = 600.0                # jak zgody/plugin _ZAJETY_S: krok na telefonie w tym czasie = telefon zajęty
ZDARZENIE_MAKS = 100
DNI_MAKS = 60
DZIEN_MAKS = 1000
ODCZYT_ZRODLA = ("same-origin", "none")
DZIEN_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
AGENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
ID_RE = re.compile(r"^[pkrto]:[A-Za-z0-9_.:@+-]{1,300}$")

STANY_OTWARTE = ("w_toku", "pytanie")
STANY_KONCOWE = ("gotowe", "przerwane", "blad")
# przebiegi panelu (rozmowy.py STANY_*) → stan wpisu; `wlaczony` = dopisek w trakcie tury: stan tury, do której doszedł
STAN_PRZEBIEGU = {"kolejka": "w_toku", "wysylanie": "w_toku", "przyjety": "w_toku", "pracuje": "w_toku",
                  "czeka_na_ture": "w_toku", "zatrzymywanie": "w_toku", "dopisany": "w_toku",
                  "czeka_na_zgode": "pytanie", "gotowe": "gotowe", "wlaczony": "gotowe",
                  "zatrzymane": "przerwane", "przerwane": "przerwane", "anulowane": "przerwane",
                  "blad": "blad", "zgubione": "blad"}
# karty kanbana Hermesa: zlecona i nieskończona = w toku; zablokowana czeka na człowieka (needs_input i inne powody)
STAN_KARTY = {"triage": "w_toku", "todo": "w_toku", "ready": "w_toku", "scheduled": "w_toku", "running": "w_toku",
              "review": "w_toku", "blocked": "pytanie", "done": "gotowe", "failed": "blad"}
BLEDY_KARTY = ("crashed", "timed_out", "spawn_failed", "gave_up", "failed")
ZLECIL_KARTY = {"": "JARO", "user": "JARO", "dashboard": "JARO", "cli": "JARO", "operator": "Operator"}
# sesje omp: `zrodlo` wiadomości skrzynki → (zlecił, kanał); brak zrodla = Telegram (jarvo/sesje_omp.py)
ZRODLO_OMP = {"telegram": ("JARO", "telegram"), "terminal": ("JARO", "terminal"), "operator": ("Operator", "terminal"),
              "reczne": ("Operator", "terminal")}

KOLUMNY = ("id", "rodzaj", "agent", "zlecil", "kanal", "tytul", "prompt", "stan", "start_at", "koniec_at", "wynik",
           "wynik_pelny", "wywolania", "zasoby", "rodzic", "watek_id", "klucz")
SKROT = tuple(k for k in KOLUMNY if k not in ("prompt", "wynik_pelny")) + ("zmieniono_at",)

SCHEMAT = """
CREATE TABLE IF NOT EXISTS zadania (
  id TEXT PRIMARY KEY,
  rodzaj TEXT NOT NULL,
  agent TEXT NOT NULL,
  zlecil TEXT NOT NULL,
  kanal TEXT NOT NULL,
  tytul TEXT NOT NULL,
  prompt TEXT NOT NULL DEFAULT '',
  stan TEXT NOT NULL,
  start_at REAL,
  koniec_at REAL,
  wynik TEXT NOT NULL DEFAULT '',
  wynik_pelny TEXT NOT NULL DEFAULT '',
  wywolania INTEGER,
  zasoby TEXT NOT NULL DEFAULT '[]',
  rodzic TEXT,
  watek_id TEXT,
  klucz TEXT,
  zmieniono_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS zadania_start ON zadania(start_at);
CREATE INDEX IF NOT EXISTS zadania_stan ON zadania(stan);
CREATE TABLE IF NOT EXISTS stan (klucz TEXT PRIMARY KEY, wartosc TEXT NOT NULL);
"""
# 28.11 (Main): test OLX i SMS Jarva to były dwie sesje tego samego profilu `jarvo`; hak rozróżnia zadania po kluczu
# strażnika telefonu (zgody/plugin `_klucz_zadania`): `sesja:<session_id>` (przebieg, tura Telegrama) albo
# `karta:<task_id>`; omp i rutyny bez klucza. Baza sprzed tej zmiany dostaje kolumnę przy otwarciu.
INDEKS_KLUCZA = "CREATE INDEX IF NOT EXISTS zadania_klucz ON zadania(klucz)"


# ----------------------------------------------------------------------------------------------- pomocnicze

def _ro(plik: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(Path(plik).resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
    conn.row_factory = sqlite3.Row
    return conn


def _json(raw: Any, domyslna: Any) -> Any:
    if not isinstance(raw, str) or not raw:
        return domyslna
    try:
        return json.loads(raw)
    except ValueError:
        return domyslna


def tytul_z(tekst: str) -> str:
    """Pierwsza niepusta linia, białe znaki zwinięte, ≤ TYTUL_MAKS (z „…”, gdy ucięta)."""
    for linia in str(tekst or "").splitlines():
        linia = " ".join(linia.split())
        if linia:
            return linia if len(linia) <= TYTUL_MAKS else linia[:TYTUL_MAKS - 1].rstrip() + "…"
    return ""


def skrot_wyniku(tekst: str) -> str:
    t = " ".join(str(tekst or "").split())
    return t if len(t) <= WYNIK_MAKS else t[:WYNIK_MAKS - 1].rstrip() + "…"


def _czas_omp(tekst: Any) -> float | None:
    """`czas` wiadomości skrzynki ('%Y-%m-%d %H:%M:%S' albo ISO z 'T'), czas lokalny serwera."""
    try:
        return datetime.datetime.fromisoformat(str(tekst or "")).timestamp()
    except ValueError:
        return None


def _czas_tury(tura: Any) -> float | None:
    """Start tury z jej id (`20261128-190344-3cdc50`, czas lokalny)."""
    try:
        return datetime.datetime.strptime(str(tura or "")[:15], "%Y%m%d-%H%M%S").timestamp()
    except ValueError:
        return None


def _dzis(teraz: float | None = None) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(time.time() if teraz is None else teraz))


def granice_dnia(dzien: str) -> tuple[float, float]:
    """[początek, koniec) dnia w strefie serwera (mktime liczy zmianę czasu)."""
    r, m, d = (int(x) for x in dzien.split("-"))
    return (time.mktime((r, m, d, 0, 0, 0, 0, 0, -1)), time.mktime((r, m, d + 1, 0, 0, 0, 0, 0, -1)))


def _wiersz(r: sqlite3.Row | dict, pola: Iterable[str]) -> dict:
    d = {k: r[k] for k in pola}
    if "zasoby" in d:
        d["zasoby"] = _json(d["zasoby"], [])
    return d


# ----------------------------------------------------------------------------------------------- odczyt

def lista(plik: Path | str, dzien: str | None = None, agent: str | None = None, *,
          teraz: float | None = None) -> dict:
    """{dzien, dni (z wpisami, malejąco, ≤ DNI_MAKS), zadania: [skrót]}: w toku i pytania na górze (od najstarszego
    startu; dziś wszystkie, inny dzień tylko jego), potem reszta dnia malejąco po starcie."""
    dzis = _dzis(teraz)
    dzien_ = dzien or dzis
    if not DZIEN_RE.match(dzien_):
        raise ValueError("zły dzień")
    if not Path(plik).is_file():
        return {"dzien": dzien_, "dni": [], "zadania": []}
    od, do = granice_dnia(dzien_)
    start = "COALESCE(start_at, koniec_at, zmieniono_at)"
    warunek, arg = ("AND agent = ?", [agent]) if agent else ("", [])
    otwarte = "stan IN ('w_toku', 'pytanie')"
    conn = _ro(plik)
    try:
        dni = [r[0] for r in conn.execute(
            f"SELECT DISTINCT date({start}, 'unixepoch', 'localtime') AS d FROM zadania WHERE 1=1 {warunek} "
            "ORDER BY d DESC LIMIT ?", [*arg, DNI_MAKS]) if r[0]]
        gora = [_wiersz(r, SKROT) for r in conn.execute(
            f"SELECT * FROM zadania WHERE {otwarte} {warunek}"
            + ("" if dzien_ == dzis else f" AND {start} >= ? AND {start} < ?")
            + f" ORDER BY {start}, id", [*arg] + ([] if dzien_ == dzis else [od, do]))]
        reszta = [_wiersz(r, SKROT) for r in conn.execute(
            f"SELECT * FROM zadania WHERE NOT {otwarte} {warunek} AND {start} >= ? AND {start} < ? "
            f"ORDER BY {start} DESC, id DESC LIMIT ?", [*arg, od, do, DZIEN_MAKS])]
    finally:
        conn.close()
    return {"dzien": dzien_, "dni": dni, "zadania": gora + reszta}


def wpis(plik: Path | str, id_: str) -> dict | None:
    """Pełny wpis (z promptem i pełnym wynikiem) albo None."""
    if not Path(plik).is_file():
        return None
    conn = _ro(plik)
    try:
        r = conn.execute("SELECT * FROM zadania WHERE id = ?", (id_,)).fetchone()
    finally:
        conn.close()
    return _wiersz(r, (*KOLUMNY, "zmieniono_at")) if r else None


# ----------------------------------------------------------------------------------------------- zbieracz

class Zbieracz:
    """Zbiera wpisy osi ze źródeł (wołać z jednego wątku naraz: `runda` z pętli silnika). `czytnik`: czytnik.Czytnik
    panelu (tury Telegrama, odpowiedź Hermesa), `omp`: moduł omp_sesje, `agenci()`: profile Hermesa floty."""

    def __init__(self, plik: Path | str, *, dane: Path | str, rozmowy_db: Path | str, kanban_db: Path | str,
                 raporty_db: Path | str, telefony: Path | str, omp=None, czytnik=None,
                 agenci: Callable[[], Iterable[str]] | None = None, dom: Path | str | None = None,
                 utajnij: Callable[[str], str] | None = None, zegar: Callable[[], float] = time.time,
                 log: Callable[[str], None] | None = None):
        self.plik = Path(plik)
        self.dane = Path(dane)
        self.rozmowy_db, self.kanban_db, self.raporty_db = Path(rozmowy_db), Path(kanban_db), Path(raporty_db)
        self.telefony = Path(telefony)
        self.omp, self.czytnik, self.agenci = omp, czytnik, agenci
        self.dom = Path(dom) if dom else None
        self.utajnij = utajnij or (lambda t: t)
        self.zegar = zegar
        self.log = log or (lambda _m: None)
        self._db: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        self._runda_at = 0.0
        self._zmienione: dict[str, dict] = {}

    # ---- baza
    def _baza(self) -> sqlite3.Connection:
        if self._db is None:
            self.plik.parent.mkdir(parents=True, exist_ok=True)
            if not self.plik.exists():                     # prompty i wyniki: tylko właściciel
                os.close(os.open(self.plik, os.O_WRONLY | os.O_CREAT, 0o600))
            db = sqlite3.connect(self.plik, timeout=5, check_same_thread=False)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=NORMAL")
            db.executescript(SCHEMAT)
            if "klucz" not in {r[1] for r in db.execute("PRAGMA table_info(zadania)")}:
                db.execute("ALTER TABLE zadania ADD COLUMN klucz TEXT")
            db.execute(INDEKS_KLUCZA)
            db.commit()
            self._db = db
        return self._db

    def zamknij(self) -> None:
        with self._lock:
            if self._db is not None:
                self._db.close()
                self._db = None

    def _znak(self, klucz: str, domyslny: str = "") -> str:
        r = self._baza().execute("SELECT wartosc FROM stan WHERE klucz = ?", (klucz,)).fetchone()
        return r[0] if r else domyslny

    def _ustaw_znak(self, klucz: str, wartosc: Any) -> None:
        self._baza().execute("INSERT INTO stan (klucz, wartosc) VALUES (?, ?) ON CONFLICT(klucz) DO UPDATE SET "
                             "wartosc = excluded.wartosc", (klucz, str(wartosc)))

    def _usun_znak(self, klucz: str) -> None:
        self._baza().execute("DELETE FROM stan WHERE klucz = ?", (klucz,))

    def _stary(self, id_: str) -> dict | None:
        r = self._baza().execute("SELECT * FROM zadania WHERE id = ?", (id_,)).fetchone()
        return dict(r) if r else None

    def _otwarte(self, prefiks: str) -> list[dict]:
        return [dict(r) for r in self._baza().execute(
            "SELECT * FROM zadania WHERE id LIKE ? AND stan IN ('w_toku', 'pytanie')", (prefiks + "%",))]

    def _zapisz(self, nowy: dict, stary: dict | None = None, *, stary_znany: bool = False) -> bool:
        """Wpis do bazy, gdy coś się zmieniło; pustych pól tekstu i braków źródła nie przepisuje na stare."""
        if not stary_znany:
            stary = self._stary(nowy["id"])
        w = {k: nowy.get(k) for k in KOLUMNY}
        for k in ("tytul", "prompt", "wynik", "wynik_pelny"):
            w[k] = str(w[k] or "")
        w["zasoby"] = list(w["zasoby"] or [])
        if stary is not None:
            for k in ("tytul", "prompt", "wynik", "wynik_pelny"):
                if not w[k] and stary[k]:
                    w[k] = stary[k]
            for k in ("start_at", "wywolania", "rodzic", "watek_id", "klucz"):
                if w[k] is None:
                    w[k] = stary[k]
            w["zasoby"] = list(dict.fromkeys([*_json(stary["zasoby"], []), *w["zasoby"]]))
        w["zasoby"] = json.dumps(w["zasoby"], ensure_ascii=False)
        if stary is not None and all(stary[k] == w[k] for k in KOLUMNY):
            return False
        w["zmieniono_at"] = self.zegar()
        self._baza().execute(f"INSERT OR REPLACE INTO zadania ({', '.join(w)}) VALUES ({', '.join('?' * len(w))})",
                             list(w.values()))
        self._zmienione[w["id"]] = w
        return True

    def _tekst(self, t: Any, maks: int = TEKST_MAKS) -> str:
        return self.utajnij(str(t or ""))[:maks]

    def _wpis(self, *, id_: str, rodzaj: str, agent: str, zlecil: str, kanal: str, prompt: str = "", tytul: str = "",
              stan: str, start_at=None, koniec_at=None, wynik: str = "", wywolania=None, zasoby=(), rodzic=None,
              watek_id=None, klucz=None) -> dict:
        prompt = self._tekst(prompt)
        wynik_pelny = self._tekst(wynik)
        return {"id": id_, "rodzaj": rodzaj, "agent": agent or "?", "zlecil": zlecil, "kanal": kanal,
                "tytul": tytul_z(self.utajnij(tytul)) if tytul else tytul_z(prompt), "prompt": prompt, "stan": stan,
                "start_at": start_at, "koniec_at": koniec_at, "wynik": skrot_wyniku(wynik_pelny),
                "wynik_pelny": wynik_pelny, "wywolania": wywolania, "zasoby": list(zasoby), "rodzic": rodzic,
                "watek_id": watek_id, "klucz": klucz}

    # ---- obieg
    def runda(self) -> list[dict] | None:
        """Wątek silnika (co ~2 s, zbiera co RUNDA_S): skróty wpisów zmienionych w obiegu albo None."""
        teraz = self.zegar()
        if teraz - self._runda_at < RUNDA_S:
            return None
        self._runda_at = teraz
        zmiany = self.zbierz(teraz)
        return zmiany or None

    def zbierz(self, teraz: float | None = None) -> list[dict]:
        """Jeden obieg po wszystkich źródłach; błąd jednego źródła nie zatrzymuje reszty. Zwraca skróty zmienionych
        wpisów (najnowsze ZDARZENIE_MAKS po starcie)."""
        teraz = self.zegar() if teraz is None else teraz
        with self._lock:
            self._zmienione = {}
            db = self._baza()
            for nazwa, zrodlo in (("przebiegi", self._przebiegi), ("karty", self._karty), ("rutyny", self._rutyny),
                                  ("omp", self._omp), ("telegram", self._telegram), ("zasoby", self._zasoby)):
                try:
                    zrodlo(teraz)
                    db.commit()
                except Exception as exc:     # brak źródła, zmieniony schemat: reszta osi idzie dalej
                    db.rollback()
                    self.log(f"jarvo-hq: oś floty {nazwa}: {type(exc).__name__}")
            zmienione = sorted(self._zmienione.values(), key=lambda w: -(w["start_at"] or w["koniec_at"] or 0))
        return [_wiersz(w, SKROT) for w in zmienione[:ZDARZENIE_MAKS]]

    # ---- przebiegi panelu
    def _przebiegi(self, teraz: float) -> None:
        if not self.rozmowy_db.is_file():
            return
        znak = float(self._znak("przebiegi", "0") or 0)
        otwarte = [w["id"][2:] for w in self._otwarte("p:")]
        conn = _ro(self.rozmowy_db)
        try:
            # klucz sesji: sesja przebiegu, a przed jej nadaniem (kolejka, dopisek) sesja członka wątku
            sql = ("SELECT p.*, w.tekst AS wpis_tekst, c.sesja_id AS sesja_czlonka FROM przebiegi p "
                   "LEFT JOIN wpisy w ON w.id = p.wpis_id LEFT JOIN czlonkowie c ON c.watek_id = p.watek_id "
                   "AND c.agent = p.agent AND c.rola = p.rola WHERE ")
            wiersze = {r["id"]: r for r in conn.execute(sql + "p.utworzony_at > ? ORDER BY p.utworzony_at",
                                                        (znak - ZAKLADKA_S,))}
            for i in range(0, len(otwarte), 500):
                kawalek = otwarte[i:i + 500]
                wiersze.update({r["id"]: r for r in conn.execute(
                    sql + f"p.id IN ({','.join('?' * len(kawalek))})", kawalek)})
            cele = {r["dopisany_do"] for r in wiersze.values() if r["dopisany_do"]} - set(wiersze)
            stany_celow = {r[0]: r[1] for r in conn.execute(
                f"SELECT id, stan FROM przebiegi WHERE id IN ({','.join('?' * len(cele))})", list(cele))} if cele else {}
            stany_celow.update({k: r["stan"] for k, r in wiersze.items()})
            przekazy = sorted({r["przekaz_z"] for r in wiersze.values() if r["przekaz_z"]})
            agenci_przekazu = {r[0]: r[1] for r in conn.execute(
                f"SELECT id, agent FROM przebiegi WHERE id IN ({','.join('?' * len(przekazy))})", przekazy)} \
                if przekazy else {}
        finally:
            conn.close()
        wpisy_omp = self._wpisy_omp()
        nowy_znak = znak
        for r in wiersze.values():
            nowy_znak = max(nowy_znak, float(r["utworzony_at"] or 0))
            id_ = f"p:{r['id']}"
            stary = self._stary(id_)
            if stary is not None and stary["stan"] in STANY_KONCOWE:
                continue                                  # skończony wpis zostaje, jak był
            stan_p = r["stan"]
            if stan_p == "wlaczony" and r["dopisany_do"]:
                stan_p = stany_celow.get(r["dopisany_do"], "gotowe")
            stan = STAN_PRZEBIEGU.get(stan_p, "w_toku")
            agent = str(r["agent"] or "")
            omp = r["zaplecze"] == "omp" or agent.startswith("s:")
            agent = agent[2:] if agent.startswith("s:") else agent
            payload = _json(r["payload"], {}) or {}
            prompt = r["wpis_tekst"] or (payload.get("prosba") if isinstance(payload, dict) else "") or ""
            koniec = (r["zakonczony_at"] or r["ostatnie_zdarzenie_at"] or r["utworzony_at"]) \
                if stan in STANY_KONCOWE else None
            wynik = ""
            if stan in STANY_KONCOWE:
                wynik = self._wynik_przebiegu(r, agent, omp, wpisy_omp, teraz)
            kroki = _json(r["kroki"], None)
            zlecil = {"wlasciciel": "JARO", "decyzja": "JARO", "nadzor": "JARO"}.get(r["zrodlo"], agent)
            if r["zrodlo"] == "przekaz" and r["przekaz_z"]:
                z = str(agenci_przekazu.get(r["przekaz_z"]) or agent)
                zlecil = z[2:] if z.startswith("s:") else z
            self._zapisz(self._wpis(
                id_=id_, rodzaj="panel", agent=agent, zlecil=zlecil, kanal="panel", prompt=prompt, stan=stan,
                start_at=r["utworzony_at"], koniec_at=koniec, wynik=wynik,
                wywolania=sum(1 for k in kroki if isinstance(k, dict) and k.get("narzedzie"))
                if isinstance(kroki, list) else None,
                rodzic=f"p:{r['dopisany_do'] or r['przekaz_z']}" if (r["dopisany_do"] or r["przekaz_z"]) else None,
                watek_id=r["watek_id"], klucz=None if omp or not (r["sesja_id"] or r["sesja_czlonka"])
                else f"sesja:{r['sesja_id'] or r['sesja_czlonka']}"), stary, stary_znany=True)
        self._ustaw_znak("przebiegi", repr(nowy_znak))

    def _wynik_przebiegu(self, r, agent: str, omp: bool, wpisy_omp: dict, teraz: float) -> str:
        blad = _json(r["blad"], None)
        if isinstance(blad, dict) and (blad.get("komunikat") or blad.get("szczegoly")):
            return " ".join(str(blad.get(k) or "") for k in ("komunikat", "szczegoly")).strip()
        if omp:
            w = wpisy_omp.get(agent)
            for gdzie in ("zrobione", "bledy"):
                d = _czytaj_json(w.skrzynka / gdzie / f"panel-{r['id']}.json") if w is not None else None
                if d:
                    return str(d.get("odpowiedz") or d.get("blad") or "")
            return ""
        koniec = r["zakonczony_at"] or r["ostatnie_zdarzenie_at"] or 0
        if self.czytnik is None or not r["sesja_id"] or not r["user_msg_id"] or teraz - float(koniec) > WYNIK_WSTECZ_S:
            return ""
        return self.czytnik.odpowiedz_tury(agent, [r["sesja_id"]], int(r["user_msg_id"]))

    # ---- karty kanbana
    def _karty(self, teraz: float) -> None:
        if not self.kanban_db.is_file():
            return
        znak = int(self._znak("karty_zdarzenie", "0") or 0)
        conn = _ro(self.kanban_db)
        try:
            maks = conn.execute("SELECT COALESCE(MAX(id), 0) FROM task_events").fetchone()[0]
            if znak <= 0 or maks < znak:                 # pierwszy obieg albo nowa tablica: wszystkie karty
                ids = [r[0] for r in conn.execute("SELECT id FROM tasks")]
            else:
                ids = [r[0] for r in conn.execute("SELECT DISTINCT task_id FROM task_events WHERE id > ?", (znak,))]
                ids = list(dict.fromkeys([*ids, *(w["id"][2:] for w in self._otwarte("k:"))]))
            karty = []
            for i in range(0, len(ids), 500):
                kawalek = ids[i:i + 500]
                q = ",".join("?" * len(kawalek))
                rodzice = {r[0]: r[1] for r in conn.execute(
                    f"SELECT child_id, parent_id FROM task_links WHERE child_id IN ({q})", kawalek)}
                biegi: dict[str, dict] = {}
                for r in conn.execute(f"SELECT task_id, outcome, summary, error, ended_at FROM task_runs "
                                      f"WHERE task_id IN ({q}) ORDER BY id", kawalek):
                    b = biegi.setdefault(r["task_id"], {"outcome": None, "summary": "", "error": "", "ended_at": None})
                    b.update(outcome=r["outcome"] or b["outcome"], ended_at=r["ended_at"] or b["ended_at"])
                    if r["summary"]:
                        b["summary"] = r["summary"]
                    if r["error"]:
                        b["error"] = r["error"]
                ostatnie = {r[0]: r[1] for r in conn.execute(
                    f"SELECT task_id, MAX(created_at) FROM task_events WHERE task_id IN ({q}) GROUP BY task_id", kawalek)}
                for r in conn.execute(f"SELECT * FROM tasks WHERE id IN ({q})", kawalek):
                    karty.append((dict(r), rodzice.get(r["id"]), biegi.get(r["id"]) or {}, ostatnie.get(r["id"])))
        finally:
            conn.close()
        powiazania = self._karty_z_rozmow([k[0] for k in karty])
        for t, rodzic, bieg, ostatnie in karty:
            stan = STAN_KARTY.get(t["status"])
            if stan is None:
                if t["status"] == "archived":
                    stan = "gotowe" if t["completed_at"] else ("blad" if bieg.get("outcome") in BLEDY_KARTY else "przerwane")
                else:
                    stan = "w_toku"
            koniec = None
            if stan in STANY_KONCOWE:
                koniec = t["completed_at"] or bieg.get("ended_at") or ostatnie
            wynik = bieg.get("summary") or t.get("result") or ""
            if stan == "blad" and not wynik:
                wynik = bieg.get("error") or t.get("last_failure_error") or ""
            tworca = str(t.get("created_by") or "").strip()
            zlecil = ZLECIL_KARTY.get(tworca.lower(), tworca)
            watek, z_przebiegu = powiazania.get(t["id"], (None, None))
            self._zapisz(self._wpis(
                id_=f"k:{t['id']}", rodzaj="karta", agent=str(t.get("assignee") or ""), zlecil=zlecil, kanal="lista",
                tytul=str(t.get("title") or ""), prompt="\n\n".join(x for x in (t.get("title"), t.get("body")) if x),
                stan=stan, start_at=t["created_at"], koniec_at=koniec, wynik=wynik,
                rodzic=f"k:{rodzic}" if rodzic else (f"p:{z_przebiegu}" if z_przebiegu else None), watek_id=watek,
                klucz=f"karta:{t['id']}"))
        self._ustaw_znak("karty_zdarzenie", maks)

    def _karty_z_rozmow(self, karty: list[dict]) -> dict[str, tuple[str | None, str | None]]:
        """task_id → (wątek panelu z `karty` rozmowy.db, przebieg, w którego sesji karta powstała)."""
        if not karty or not self.rozmowy_db.is_file():
            return {}
        out: dict[str, tuple[str | None, str | None]] = {}
        conn = _ro(self.rozmowy_db)
        try:
            for t in karty:
                r = conn.execute("SELECT watek_id FROM karty WHERE task_id = ?", (t["id"],)).fetchone()
                p = conn.execute("SELECT id, watek_id FROM przebiegi WHERE sesja_id = ? AND utworzony_at <= ? "
                                 "ORDER BY utworzony_at DESC LIMIT 1",
                                 (t["session_id"], float(t["created_at"] or 0) + 1)).fetchone() if t.get("session_id") else None
                out[t["id"]] = ((r[0] if r else None) or (p["watek_id"] if p else None), p["id"] if p else None)
        finally:
            conn.close()
        return out

    # ---- rutyny
    def _rutyny(self, teraz: float) -> None:
        if not self.raporty_db.is_file():
            return
        znak = int(self._znak("rutyny_rowid", "0") or 0)
        conn = _ro(self.raporty_db)
        try:
            wiersze = conn.execute("SELECT rowid, * FROM raporty WHERE rowid > ? ORDER BY rowid", (znak,)).fetchall()
        finally:
            conn.close()
        for r in wiersze:
            znak = max(znak, int(r["rowid"]))
            self._zapisz(self._wpis(
                id_=f"r:{r['id']}", rodzaj="rutyna", agent=r["profil"], zlecil="rutyna", kanal="cron",
                tytul=r["nazwa"] or r["rodzaj"], stan="blad" if r["blad"] else "gotowe", start_at=r["ts"],
                koniec_at=r["ts"], wynik=r["tekst"]))
        self._ustaw_znak("rutyny_rowid", znak)

    # ---- sesje omp
    def _wpisy_omp(self) -> dict:
        if self.omp is None:
            return {}
        try:
            return {k: w for k, w in self.omp.wpisy(self.dane, self.dom).items() if not w.blad and w.skrzynka}
        except Exception:
            return {}

    def _omp(self, teraz: float) -> None:
        for klucz, w in self._wpisy_omp().items():
            znak = float(self._znak(f"omp:{klucz}", "0") or 0)
            nowy_znak, widziane = znak, set()
            for gdzie in ("zrobione", "bledy"):
                katalog = w.skrzynka / gdzie
                if not katalog.is_dir():
                    continue
                for p in sorted(katalog.glob("*.json")):
                    try:
                        mtime = p.stat().st_mtime
                    except OSError:
                        continue
                    if mtime <= znak - ZAKLADKA_S or p.name.startswith("panel-"):
                        continue
                    d = _czytaj_json(p)
                    if not d or d.get("zrodlo") == "panel":
                        continue
                    nowy_znak = max(nowy_znak, mtime)
                    widziane.add(p.stem)
                    start = _czas_omp(d.get("czas")) or mtime
                    sek = d.get("sekundy")
                    koniec = ((_czas_tury(d.get("tura")) or start) + float(sek)) if isinstance(sek, (int, float)) else mtime
                    self._zapisz(self._wpis_omp(w, p.stem, d, "gotowe" if gdzie == "zrobione" else "blad", start,
                                                koniec, d.get("odpowiedz") if gdzie == "zrobione" else d.get("blad")))
            self._ustaw_znak(f"omp:{klucz}", repr(nowy_znak))
            self._omp_w_toku(w, teraz, widziane)

    def _wpis_omp(self, w, stem: str, d: dict, stan: str, start, koniec, wynik) -> dict:
        zrodlo = str(d.get("zrodlo") or "telegram")
        zlecil, kanal = ZRODLO_OMP.get(zrodlo, ("rutyna", "cron"))
        if zrodlo == "telegram" and str(d.get("nazwa") or w.nazwa) != w.nazwa:
            zlecil, kanal = "rutyna", "cron"                 # skrypt piszący do skrzynki (czuwanie, wyścigi)
        return self._wpis(id_=f"o:{w.klucz}:{stem}", rodzaj="omp", agent=w.klucz, zlecil=zlecil, kanal=kanal,
                          prompt=str(d.get("tekst") or ""), stan=stan, start_at=start, koniec_at=koniec,
                          wynik=str(wynik or ""))

    def _omp_w_toku(self, w, teraz: float, widziane: set[str]) -> None:
        """Tura skrzynki w toku (`stan.json`, żywy proces): wiadomości spoza panelu z `nowe/` sprzed jej startu."""
        stan = self.omp.czytaj_stan(w)
        tura = stan.get("tura") if isinstance(stan.get("tura"), dict) else None
        w_turze = set()
        if tura and self.omp.zyje(tura.get("pid")):
            start_tury = float(tura.get("start") or teraz)
            for p in sorted(w.nowe.glob("*.json")) if w.nowe.is_dir() else []:
                d = _czytaj_json(p)
                if not d or d.get("zrodlo") == "panel" or p.name.startswith("panel-"):
                    continue
                start = _czas_omp(d.get("czas"))
                if start is None or start > start_tury + 2:
                    continue                                 # czeka na następną turę
                w_turze.add(p.stem)
                self._zapisz(self._wpis_omp(w, p.stem, d, "w_toku", start, None, ""))
        for stary in self._otwarte(f"o:{w.klucz}:"):
            stem = stary["id"].split(":", 2)[2]
            if stem in w_turze or stem in widziane:
                continue
            if (w.zrobione / f"{stem}.json").exists() or (w.bledy / f"{stem}.json").exists() \
                    or (w.nowe / f"{stem}.json").exists():
                continue                                     # zrobione dojdzie w obiegu po znaczniku, nowe czeka
            self._zapisz({**stary, "zasoby": _json(stary["zasoby"], []), "stan": "przerwane", "koniec_at": teraz},
                         stary, stary_znany=True)

    # ---- tury Telegrama (Hermes)
    def _telegram(self, teraz: float) -> None:
        if self.czytnik is None or self.agenci is None:
            return
        trwa = set()
        for agent in list(self.agenci()):
            for d in self.czytnik.dzierzawy_profilu(agent, teraz) or []:
                if d.get("platforma") != "telegram":
                    continue
                id_ = f"t:{agent}:{d['sesja_id']}:{int(d.get('od') or 0)}"
                trwa.add(id_)
                if self._stary(id_) is not None:
                    continue
                tresc, _rodzaj = self.czytnik.ostatni_uzytkownika(agent, [d["sesja_id"]])
                self._ustaw_znak(f"tg:{id_}", self.czytnik.stan_sesji(agent, [d["sesja_id"]]).get("max_id", 0))
                self._zapisz(self._wpis(id_=id_, rodzaj="telegram", agent=agent, zlecil="JARO", kanal="telegram",
                                        prompt=tresc, stan="w_toku", start_at=d.get("od") or teraz,
                                        klucz=f"sesja:{d['sesja_id']}"))
        for stary in self._otwarte("t:"):
            if stary["id"] in trwa:
                continue
            _, agent, sesja, _od = stary["id"].split(":", 3)
            po_id = int(self._znak(f"tg:{stary['id']}", "0") or 0)
            wynik = self._tekst(self.czytnik.odpowiedz_tury(agent, [sesja], po_id))
            self._zapisz({**stary, "zasoby": _json(stary["zasoby"], []), "stan": "gotowe", "koniec_at": teraz,
                          "wynik": skrot_wyniku(wynik), "wynik_pelny": wynik}, stary, stary_znany=True)
            self._usun_znak(f"tg:{stary['id']}")

    # ---- zasoby
    def _zasoby(self, teraz: float) -> None:
        """Telefon (i pulpit) prowadzący teraz zadanie → zasób wpisów w toku z tym samym kluczem zadania."""
        dane = _czytaj_json(self.telefony)
        if not dane:
            return
        for nazwa, z in dane.items():
            if not isinstance(z, dict) or not z.get("klucz") or teraz - float(z.get("t") or 0) >= ZAJETY_S:
                continue
            zasob = "pulpit" if nazwa == "pulpit" else f"telefon:{nazwa}"
            for r in self._baza().execute("SELECT * FROM zadania WHERE klucz = ? AND stan IN ('w_toku', 'pytanie')",
                                          (str(z["klucz"]),)).fetchall():
                stary = dict(r)
                if zasob in _json(stary["zasoby"], []):
                    continue
                self._zapisz({**stary, "zasoby": [*_json(stary["zasoby"], []), zasob]}, stary, stary_znany=True)


def _czytaj_json(p: Path) -> dict | None:
    try:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


# ----------------------------------------------------------------------------------------------- trasy

def dolacz(router, *, plik: Path | str, log: Callable[[str], None] | None = None) -> None:
    """Trasy osi floty na routerze wtyczki (tylko odczyt, GET tylko z karty panelu jak raporty.py)."""
    # import tutaj (bez adnotacji Request w chwili importu modułu): FastAPI tylko w procesie panelu
    from fastapi import Request
    from fastapi.responses import JSONResponse

    log = log or (lambda _m: None)

    def blad(status: int, kod: str, pl: str, en: str):
        return JSONResponse({"blad": {"kod": kod, "komunikat": pl, "komunikat_en": en}}, status_code=status)

    def obca(request) -> bool:
        skad = (request.headers.get("sec-fetch-site") or "").strip().lower()
        if skad and skad not in ODCZYT_ZRODLA:
            log(f"jarvo-hq: odczyt odrzucony GET {request.url.path} (sec-fetch-site={skad[:20]})")
            return True
        return False

    @router.get("/flota/os")
    async def os_floty(request: Request, dzien: str | None = None, agent: str | None = None):
        if obca(request):
            return blad(403, "csrf", "Odmowa odczytu: żądanie nie przyszło z panelu Jarvo.",
                        "Read refused: the request did not come from the Jarvo dashboard.")
        if (dzien and not DZIEN_RE.match(dzien)) or (agent and not AGENT_RE.match(agent)):
            return blad(422, "zle_dane", "Niepoprawny dzień (RRRR-MM-DD) albo agent.", "Invalid day (YYYY-MM-DD) or agent.")
        try:
            return await asyncio.to_thread(lista, plik, dzien or None, agent or None)
        except ValueError:
            return blad(422, "zle_dane", "Niepoprawny dzień (RRRR-MM-DD).", "Invalid day (YYYY-MM-DD).")
        except sqlite3.Error as e:
            log(f"jarvo-hq: oś floty: {type(e).__name__}")
            return blad(503, "os_floty", "Oś floty jest niedostępna.", "The fleet timeline is unavailable.")

    @router.get("/flota/os/{id:path}")
    async def zadanie(request: Request, id: str):  # noqa: A002 - nazwa parametru ścieżki
        if obca(request):
            return blad(403, "csrf", "Odmowa odczytu: żądanie nie przyszło z panelu Jarvo.",
                        "Read refused: the request did not come from the Jarvo dashboard.")
        if not ID_RE.match(id):
            return blad(404, "brak", "Nie ma takiego zadania.", "No such task.")
        try:
            w = await asyncio.to_thread(wpis, plik, id)
        except sqlite3.Error as e:
            log(f"jarvo-hq: oś floty: {type(e).__name__}")
            return blad(503, "os_floty", "Oś floty jest niedostępna.", "The fleet timeline is unavailable.")
        if w is None:
            return blad(404, "brak", "Nie ma takiego zadania.", "No such task.")
        return {"zadanie": w}

