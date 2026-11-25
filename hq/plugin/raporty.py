"""Raporty rutyn (docs/HQ.md „Aktualizacje”): archiwum raportów rutyn floty dla kanału „Aktualizacje” pod rozmówcami.
W kodzie „raporty”, bo „aktualizacja” to już aktualizacja Jarva (odznaka ⬆, GET /update).

- **Źródło**: zapis każdego przebiegu crona Hermesa `<dane>/profiles/<profil>/cron/output/<zadanie>/<data>.md`.
  Hermes trzyma najwyżej 50 zapisów na zadanie (`cron.output_retention`), więc silnik (`runda`, co 30 s) przepisuje
  nowe raporty do własnego archiwum `<jarvo>/state/raporty.db`; każdy plik czyta raz (tabela `widziane`).
- **Raport** = to, co rutyna wysłała: odpowiedź modelu po ostatnim `## Response`, wyjście skryptu `no_agent` po `---`
  albo błąd (`**Status:** script failed`, `## Error`: `blad: true`). Cisza nie jest raportem: `[SILENT]` (cała
  odpowiedź albo pierwsza/ostatnia linia, też SILENT, NO_REPLY, NO REPLY, jak Hermes `is_autonomous_silence_response`),
  `**Status:** silent…`, `no_change`, `wakeAgent=false`. Rodzaj raportu = id zadania (`jarvo-daily-brief`), nazwa
  z nagłówka `# Cron Job: <nazwa>`. Czas = chwila zapisu pliku. Treść przez `utajnij`, najwyżej 20 000 znaków.
- **Przeczytane**: jeden znacznik `przeczytane_do` (czas najnowszego obejrzanego raportu); nieprzeczytane = raporty
  nowsze. Nowe raporty idą zdarzeniem `raporty.nowe` strumienia, zmiana znacznika `raporty.licznik` (licznik
  w lewej kolumnie bez odpytywania, we wszystkich kartach).
- **Trasy** (router wtyczki, GET tylko z karty panelu: `Sec-Fetch-Site` same-origin/none; POST z ochroną zapisu
  routera `ochrona.Trasa`):
  `GET /raporty?rodzaj=<zadanie>&od=<ts>&przed=<ts>&limit=<1..100>` → {raporty (od najnowszego, `nowy` = nieprzeczytany),
  rodzaje [{rodzaj, nazwa, liczba, ostatni}], nieprzeczytane, przeczytane_do, dalej (ts następnej strony albo null);
  z `od` (okno dnia) też poprzedni / nastepny: czas najbliższego raportu przed i po oknie, w obrębie rodzaju};
  `GET /raporty/kalendarz?od=<ts>&do=<ts>` (okno ≤ 62 dni) → {wpisy [{ts, rodzaj, nowy, blad}] bez treści, rodzaje,
  najnowszy}; `POST /raporty/przeczytane` {do: ts} → {nieprzeczytane, przeczytane_do} (znacznik tylko rośnie).
Rozmowa o raporcie zostaje w rozmowie z agentem: rutyna z `attach_to_session` wpisuje go też do sesji tematu agenta
(lustro Hermesa), a gdy temat nie ma jeszcze sesji bramy, silnik wpisuje go do wątku rozmówcy (`rozmowcy.raporty`).
Testy: tests/test_raporty.py.
"""

import asyncio
import json
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Callable

RUNDA_S = 30.0
TEKST_MAKS = 20_000
LIMIT = 40
LIMIT_MAKS = 100
KALENDARZ_OKNO_S = 62 * 86400          # kalendarz pyta o miesiąc widoku (z zapasem na strefy i zmianę czasu)
KALENDARZ_MAKS = 5000
ODCZYT_ZRODLA = ("same-origin", "none")
CISZA = {"[silent]", "silent", "no_reply", "no reply"}
ZADANIE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
NAGLOWEK = re.compile(r"^# Cron Job: (.+)$", re.M)
STATUS = re.compile(r"^\*\*Status:\*\* (.*)$", re.M)

SCHEMAT = """
CREATE TABLE IF NOT EXISTS raporty (
  id TEXT PRIMARY KEY, profil TEXT NOT NULL, rodzaj TEXT NOT NULL, nazwa TEXT NOT NULL, ts REAL NOT NULL,
  tekst TEXT NOT NULL, blad INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS raporty_ts ON raporty (ts DESC);
CREATE TABLE IF NOT EXISTS widziane (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS stan (klucz TEXT PRIMARY KEY, wartosc TEXT NOT NULL);
"""


def cisza(tekst: str) -> bool:
    """Odpowiedź, której Hermes nie dostarcza: sam znacznik ciszy albo znacznik w pierwszej lub ostatniej linii."""
    linie = [x.strip().strip("`").strip().rstrip(".!").lower() for x in str(tekst or "").strip().splitlines() if x.strip()]
    return not linie or linie[0] in CISZA or linie[-1] in CISZA


def raport(tresc: str) -> dict | None:
    """Raport z zapisu przebiegu crona: {nazwa, tekst, blad} albo None (cisza, przebieg bez wysyłki)."""
    tresc = str(tresc or "")
    m = NAGLOWEK.search(tresc)
    nazwa = m.group(1).strip()[:200] if m else ""
    if "\n## Response\n" in tresc or tresc.startswith("## Response\n"):
        tekst = tresc.rpartition("## Response\n")[2].strip()
        return None if cisza(tekst) else {"nazwa": nazwa, "tekst": tekst, "blad": False}
    st = STATUS.search(tresc)
    if st:
        if st.group(1).startswith("script failed"):
            return {"nazwa": nazwa, "tekst": tresc[st.end():].strip() or st.group(1), "blad": True}
        return None                                    # silent, no_change, BLOCKED: nic nie poszło do właściciela
    if "**Mode:** no_agent" in tresc and "\n---\n" in tresc:
        tekst = tresc.split("\n---\n", 1)[1].strip()
        return None if cisza(tekst) else {"nazwa": nazwa, "tekst": tekst, "blad": False}
    if "\n## Error\n" in tresc:
        tekst = tresc.rpartition("## Error\n")[2].strip().strip("`").strip()
        return {"nazwa": nazwa, "tekst": tekst, "blad": True}
    return None


class Archiwum:
    def __init__(self, dane: Path | str, plik: Path | str, *, utajnij: Callable[[str], str] | None = None,
                 zegar: Callable[[], float] = time.time):
        self.dane, self.plik = Path(dane), Path(plik)
        self.utajnij = utajnij or (lambda t: t)
        self.zegar = zegar
        self._lock = threading.Lock()
        self._db: sqlite3.Connection | None = None
        self._katalogi: dict[str, tuple] = {}
        self._runda_at = 0.0

    # ------------------------------------------------------------------------------------------- baza
    def _baza(self) -> sqlite3.Connection:
        if self._db is None:
            self.plik.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(self.plik, timeout=5, check_same_thread=False)
            db.row_factory = sqlite3.Row
            db.executescript(SCHEMAT)
            self._db = db
        return self._db

    def _przeczytane_do(self, db) -> float:
        r = db.execute("SELECT wartosc FROM stan WHERE klucz = 'przeczytane_do'").fetchone()
        try:
            return float(r["wartosc"]) if r else 0.0
        except ValueError:
            return 0.0

    def _nieprzeczytane(self, db) -> int:
        return db.execute("SELECT COUNT(*) FROM raporty WHERE ts > ?", (self._przeczytane_do(db),)).fetchone()[0]

    # ------------------------------------------------------------------------------------------- zbieranie
    def _katalogi_zadan(self) -> list[tuple[str, Path]]:
        out = []
        for wyjscie in sorted((self.dane / "profiles").glob("*/cron/output")):
            profil = wyjscie.parent.parent.name
            for k in sorted(wyjscie.iterdir()) if wyjscie.is_dir() else []:
                if k.is_dir() and ZADANIE.match(k.name):
                    out.append((profil, k))
        return out

    def zbierz(self) -> list[dict]:
        """Nowe raporty z katalogów crona (katalog bez zmian od ostatniej rundy pomijany). Zwraca dodane raporty."""
        nowe: list[dict] = []
        with self._lock:
            db = self._baza()
            for profil, kat in self._katalogi_zadan():
                try:
                    st = kat.stat()
                except OSError:
                    continue
                znak = (st.st_mtime_ns, st.st_size)
                if self._katalogi.get(str(kat)) == znak:
                    continue
                pliki = sorted(kat.glob("*.md"))
                ids = [f"{profil}/{kat.name}/{p.stem}" for p in pliki]
                znane = {r[0] for r in db.execute(
                    f"SELECT id FROM widziane WHERE id IN ({','.join('?' * len(ids))})", ids)} if ids else set()
                for p, rid in zip(pliki, ids):
                    if rid in znane:
                        continue
                    try:
                        tresc, ts = p.read_text(encoding="utf-8", errors="replace"), p.stat().st_mtime
                    except OSError:
                        continue
                    r = raport(tresc)
                    db.execute("INSERT OR IGNORE INTO widziane (id) VALUES (?)", (rid,))
                    if r is None:
                        continue
                    wpis = {"id": rid, "profil": profil, "rodzaj": kat.name, "nazwa": r["nazwa"] or kat.name, "ts": ts,
                            "tekst": self.utajnij(r["tekst"])[:TEKST_MAKS], "blad": r["blad"]}
                    db.execute("INSERT OR IGNORE INTO raporty (id, profil, rodzaj, nazwa, ts, tekst, blad) "
                               "VALUES (:id, :profil, :rodzaj, :nazwa, :ts, :tekst, :blad)", wpis)
                    nowe.append(wpis)
                db.commit()
                self._katalogi[str(kat)] = znak
        return nowe

    def runda(self, po_nowych: Callable[[list[dict]], object] | None = None) -> dict | None:
        """Wątek tła silnika (co 2 s, zbiera co RUNDA_S): {nieprzeczytane, nowe: [{id, rodzaj, nazwa, ts}]} albo None.
        `po_nowych` dostaje pełne nowe raporty (z profilem i treścią): silnik wpisuje je do wątków rozmówców."""
        teraz = self.zegar()
        if teraz - self._runda_at < RUNDA_S:
            return None
        self._runda_at = teraz
        nowe = self.zbierz()
        if not nowe:
            return None
        if po_nowych is not None:
            po_nowych(nowe)
        return {"nieprzeczytane": self.licznik()["nieprzeczytane"],
                "nowe": [{k: r[k] for k in ("id", "rodzaj", "nazwa", "ts")} for r in nowe]}

    # ------------------------------------------------------------------------------------------- odczyt
    def licznik(self) -> dict:
        with self._lock:
            if self._db is None and not self.plik.exists():       # odczyt nie zakłada archiwum (robi to runda)
                return {"nieprzeczytane": 0, "przeczytane_do": 0.0}
            db = self._baza()
            return {"nieprzeczytane": self._nieprzeczytane(db), "przeczytane_do": self._przeczytane_do(db)}

    def lista(self, *, rodzaj: str | None = None, przed: float | None = None, od: float | None = None,
              limit: int = LIMIT) -> dict:
        limit = max(1, min(LIMIT_MAKS, int(limit)))
        with self._lock:
            if self._db is None and not self.plik.exists():
                return {"raporty": [], "rodzaje": [], "nieprzeczytane": 0, "przeczytane_do": 0.0, "dalej": None}
            db = self._baza()
            gdzie, arg = [], []
            if rodzaj:
                gdzie.append("rodzaj = ?")
                arg.append(rodzaj)
            if przed is not None:
                gdzie.append("ts < ?")
                arg.append(float(przed))
            if od is not None:
                gdzie.append("ts >= ?")
                arg.append(float(od))
            sql = "SELECT * FROM raporty" + (f" WHERE {' AND '.join(gdzie)}" if gdzie else "") + \
                " ORDER BY ts DESC, id DESC LIMIT ?"
            wiersze = [dict(r) for r in db.execute(sql, [*arg, limit + 1])]
            granica = self._przeczytane_do(db)
            rodzaje = [{"rodzaj": r["rodzaj"], "nazwa": r["nazwa"], "liczba": r["liczba"], "ostatni": r["ostatni"]}
                       for r in db.execute("SELECT rodzaj, nazwa, COUNT(*) AS liczba, MAX(ts) AS ostatni FROM raporty "
                                           "GROUP BY rodzaj ORDER BY ostatni DESC")]
            nieprzeczytane = self._nieprzeczytane(db)
            # okno dnia (od i przed): czas najbliższego raportu przed oknem i po nim (tego samego rodzaju), żeby ‹ ›
            # skakały po dniach z raportami bez pobierania kalendarza
            sasiedzi = {}
            if od is not None:
                tyl = [rodzaj] if rodzaj else []
                warunek = " AND rodzaj = ?" if rodzaj else ""
                sasiedzi["poprzedni"] = db.execute(f"SELECT MAX(ts) FROM raporty WHERE ts < ?{warunek}",
                                                   [float(od), *tyl]).fetchone()[0]
                if przed is not None:
                    sasiedzi["nastepny"] = db.execute(f"SELECT MIN(ts) FROM raporty WHERE ts >= ?{warunek}",
                                                      [float(przed), *tyl]).fetchone()[0]
        dalej = wiersze[limit - 1]["ts"] if len(wiersze) > limit else None
        raporty = [{**w, "blad": bool(w["blad"]), "nowy": w["ts"] > granica} for w in wiersze[:limit]]
        return {"raporty": raporty, "rodzaje": rodzaje, "nieprzeczytane": nieprzeczytane, "przeczytane_do": granica,
                "dalej": dalej, **sasiedzi}

    def kalendarz(self, od: float, do: float) -> dict:
        """Kalendarz widoku: raporty z [od, do) bez treści, [{ts, rodzaj, nowy, blad}] od najstarszego; dzień liczy
        przeglądarka w swojej strefie. Rodzaje jak w `lista` (filtr i legenda kolorów)."""
        with self._lock:
            if self._db is None and not self.plik.exists():
                return {"wpisy": [], "rodzaje": [], "najnowszy": None}
            db = self._baza()
            granica = self._przeczytane_do(db)
            wpisy = [{"ts": r["ts"], "rodzaj": r["rodzaj"], "nowy": r["ts"] > granica, "blad": bool(r["blad"])}
                     for r in db.execute("SELECT ts, rodzaj, blad FROM raporty WHERE ts >= ? AND ts < ? ORDER BY ts LIMIT ?",
                                         (float(od), float(do), KALENDARZ_MAKS))]
            rodzaje = [{"rodzaj": r["rodzaj"], "nazwa": r["nazwa"], "liczba": r["liczba"], "ostatni": r["ostatni"]}
                       for r in db.execute("SELECT rodzaj, nazwa, COUNT(*) AS liczba, MAX(ts) AS ostatni FROM raporty "
                                           "GROUP BY rodzaj ORDER BY ostatni DESC")]
        return {"wpisy": wpisy, "rodzaje": rodzaje, "najnowszy": rodzaje[0]["ostatni"] if rodzaje else None}

    def przeczytane(self, do: float) -> dict:
        """Znacznik przeczytanych rośnie (stara karta nie cofnie go); nie dalej niż najnowszy raport."""
        with self._lock:
            db = self._baza()
            najnowszy = db.execute("SELECT MAX(ts) FROM raporty").fetchone()[0] or 0.0
            nowy = max(self._przeczytane_do(db), min(float(do), float(najnowszy)))
            db.execute("INSERT INTO stan (klucz, wartosc) VALUES ('przeczytane_do', ?) "
                       "ON CONFLICT(klucz) DO UPDATE SET wartosc = excluded.wartosc", (repr(nowy),))
            db.commit()
            return {"nieprzeczytane": self._nieprzeczytane(db), "przeczytane_do": nowy}


def dolacz(router, *, archiwum: Archiwum, hub=None, log: Callable[[str], None] | None = None) -> None:
    """Trasy kanału Aktualizacje na routerze wtyczki. `hub`: strumień SSE (po „przeczytane” licznik do wszystkich kart)."""
    # import tutaj (bez `from __future__ import annotations`): adnotacja trasy to klasa FastAPI w chwili rejestracji
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

    @router.get("/raporty")
    async def raporty(request: Request, rodzaj: str | None = None, przed: float | None = None, od: float | None = None,
                      limit: int = LIMIT):
        if obca(request):
            return blad(403, "csrf", "Odmowa odczytu: żądanie nie przyszło z panelu Jarvo.",
                        "Read refused: the request did not come from the Jarvo dashboard.")
        if rodzaj is not None and not ZADANIE.match(rodzaj):
            return blad(422, "zle_dane", "Niepoprawny rodzaj raportu.", "Invalid report type.")
        try:
            return await asyncio.to_thread(archiwum.lista, rodzaj=rodzaj or None, przed=przed, od=od, limit=limit)
        except sqlite3.Error as e:
            log(f"jarvo-hq: raporty: {type(e).__name__}")
            return blad(503, "archiwum", "Archiwum raportów jest niedostępne.", "The report archive is unavailable.")

    @router.get("/raporty/kalendarz")
    async def kalendarz(request: Request, od: float, do: float):
        if obca(request):
            return blad(403, "csrf", "Odmowa odczytu: żądanie nie przyszło z panelu Jarvo.",
                        "Read refused: the request did not come from the Jarvo dashboard.")
        if not 0 < do - od <= KALENDARZ_OKNO_S:
            return blad(422, "zle_dane", "Niepoprawny zakres kalendarza (od, do).", "Invalid calendar range (od, do).")
        try:
            return await asyncio.to_thread(archiwum.kalendarz, od, do)
        except sqlite3.Error as e:
            log(f"jarvo-hq: raporty: {type(e).__name__}")
            return blad(503, "archiwum", "Archiwum raportów jest niedostępne.", "The report archive is unavailable.")

    @router.post("/raporty/przeczytane")
    async def przeczytane(request: Request):
        try:
            cialo = json.loads(await request.body() or b"{}")
            do = float(cialo["do"])
        except (ValueError, TypeError, KeyError):
            return blad(422, "zle_dane", "Niepoprawne dane (do).", "Invalid data (do).")
        try:
            wynik = await asyncio.to_thread(archiwum.przeczytane, do)
        except sqlite3.Error as e:
            log(f"jarvo-hq: raporty: {type(e).__name__}")
            return blad(503, "archiwum", "Archiwum raportów jest niedostępne.", "The report archive is unavailable.")
        if hub is not None:
            hub.nadaj("raporty.licznik", wynik)
        return wynik
