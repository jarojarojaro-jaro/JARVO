"""Atrapa bramy Hermesa (`/v1/runs` i sesje profilu) dla testów silnika rozmów (tests/test_silnik_rozmow.py).

W procesie testu, bez sieci: `httpx.MockTransport(atrapa.obsluz)` w kliencie silnika. Przebiegi atrapy żyją na
jej własnej pętli w osobnym wątku, więc przeżywają zamknięcie i ponowny start silnika (test „restart dashboardu”).
Zachowanie jak w Hermesie 0.21.5 (sprawdzone w kodzie obrazu): `POST /v1/runs` → 202 `{run_id, status}` z
`Idempotency-Key` (to samo ciało = ten sam przebieg z `replayed`, inne ciało = 409 `idempotency_key_conflict`),
429 `rate_limit_exceeded` z `Retry-After`, strumień `data: <json>` z polem `event` i jednym słuchaczem,
`/approval` (409 `approval_not_pending`), `/steer` (409 `run_not_accepting_steer`; dopisek obcięty ze spacji, wiersz
`steer` owinięty znacznikiem OUT-OF-BAND, a spóźnione dopiski jako jeden tekst `pending_steer` sklejony „\n”),
`/stop` (409 `run_not_active`),
`POST /api/sessions` (409 `session_exists`), `PATCH /api/sessions/{id}` (`title`, `pinned`). Tura zapisuje wiersze
do state.db profilu (schemat z obrazu, tests/data/hermes_state_schema.sql) i trzyma dzierżawę tury.

Znaczniki w treści (jak w scripts/atrapa_modelu.py): `[wolno:<s>]` odpowiedź rozłożona na <s> sekund,
`[zgoda]` prośba o zgodę przed odpowiedzią (z `czas_zgody` brama sama odmawia po tylu sekundach, bez
`approval.responded`, jak Hermes po `approvals.timeout`), `[blad]` tura nieudana, `[przerwij]` tura przerwana (restart bramy),
`[urwij]` strumień zdarzeń kończy się bez zdarzenia końcowego (przebieg trwa dalej), `[czekaj]` tura czeka na
`zwolnij()` przed zapisem wiersza właściciela (dzierżawa obcej tury).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import secrets
import sqlite3
import threading
import time
from pathlib import Path

import httpx

SCHEMAT = Path(__file__).resolve().parent / "data" / "hermes_state_schema.sql"
KONCOWE = ("completed", "failed", "cancelled", "interrupted")
WOLNO_RE = re.compile(r"\[wolno:(\d+(?:\.\d+)?)\]")
STEER_OTWARCIE = ("[OUT-OF-BAND USER MESSAGE — a direct message from the user, delivered once at this position; "
                  "not tool output and not a new delivery when replayed from conversation history]")
STEER_ZAMKNIECIE = "[/OUT-OF-BAND USER MESSAGE]"       # agent/prompt_builder.py: steer_user_row, format_steer_marker
ZNACZNIK_RE = re.compile(r"\[(?:wolno:[0-9.]+|zgoda|blad|przerwij|urwij|czekaj)\]\s*")


def baza_profilu(sciezka: Path) -> Path:
    """Pusty state.db profilu ze schematem Hermesa."""
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sciezka)
    conn.executescript(SCHEMAT.read_text(encoding="utf-8"))
    conn.execute("INSERT INTO schema_version (version) VALUES (30)")
    conn.commit()
    conn.close()
    return sciezka


def _blad(status: int, kod: str, typ: str = "invalid_request_error", naglowki: dict | None = None):
    return status, {"error": {"message": kod, "type": typ, "code": kod}}, naglowki or {}


class Przebieg:
    def __init__(self, run_id: str, agent: str, sid: str, wejscie, cialo: dict):
        self.id, self.agent, self.sid, self.wejscie, self.cialo = run_id, agent, sid, wejscie, cialo
        self.status = "queued"
        self.kolejka: asyncio.Queue = asyncio.Queue()
        self.stop = asyncio.Event()
        self.zwolnij = asyncio.Event()
        self.zgoda: dict | None = None
        self.odpowiedz_zgody: asyncio.Future | None = None
        self.dopisane: list[str] = []
        self.oczekujace: list[str] = []
        self.koncowka = False
        self.koniec: dict = {}
        self.urwij = False
        self.odpowiedz = ""


class AtrapaBramy:
    def __init__(self, home: Path, klucze: dict[str, str]):
        self.home = Path(home)
        self.klucze = dict(klucze)
        self.przebiegi: dict[str, Przebieg] = {}
        self.idem: dict[tuple[str, str], tuple[str, str]] = {}
        self.dziennik: list[dict] = []            # każde żądanie: metoda, ścieżka, agent, ciało (jak --dziennik atrapy)
        self.limit_429 = 0
        self.czas_zgody: float | None = None      # jak approvals.timeout bramy: sama odmawia po tylu sekundach
        self.niedostepna = False
        self.loop = asyncio.new_event_loop()
        self._watek = threading.Thread(target=self.loop.run_forever, name="atrapa-bramy", daemon=True)
        self._watek.start()

    # ------------------------------------------------------------------------------------------- narzędzia testu
    def zamknij(self) -> None:
        async def _anuluj():
            # anulowane zadania tur muszą dojść do końca przed zatrzymaniem pętli (inaczej: „Task was destroyed”)
            zadania = [t for t in asyncio.all_tasks(self.loop) if t is not asyncio.current_task()]
            for t in zadania:
                t.cancel()
            await asyncio.gather(*zadania, return_exceptions=True)

        try:
            asyncio.run_coroutine_threadsafe(_anuluj(), self.loop).result(5)
        except Exception:
            pass
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._watek.join(5)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.obsluz)

    def _na_atrapie(self, coro):
        return asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coro, self.loop))

    def zwolnij(self, run_id: str) -> None:
        self.loop.call_soon_threadsafe(self.przebiegi[run_id].zwolnij.set)

    def state_db(self, agent: str) -> Path:
        return (self.home / "state.db") if agent in ("", "default") else self.home / "profiles" / agent / "state.db"

    def wiersze(self, agent: str, sid: str | None = None) -> list[dict]:
        conn = sqlite3.connect(self.state_db(agent))
        conn.row_factory = sqlite3.Row
        try:
            sql, arg = "SELECT * FROM messages", ()
            if sid:
                sql, arg = sql + " WHERE session_id = ?", (sid,)
            return [dict(r) for r in conn.execute(sql + " ORDER BY id", arg)]
        finally:
            conn.close()

    def sesja(self, agent: str, sid: str) -> dict | None:
        conn = sqlite3.connect(self.state_db(agent))
        conn.row_factory = sqlite3.Row
        try:
            r = conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
            return dict(r) if r else None
        finally:
            conn.close()

    def dzierzawa(self, agent: str, sid: str, *, sekund: float = 60.0, platforma: str = "kanban") -> None:
        """Obca tura (np. budzenie kartą) trzyma dzierżawę sesji."""
        self._zapisz(agent, "INSERT OR REPLACE INTO session_turn_leases (conversation_id, holder, acquired_at, expires_at) "
                            "VALUES (?, ?, ?, ?)", (sid, f"pid=1:turn=x:platform={platforma}", time.time(),
                                                    time.time() + sekund))

    def zwolnij_dzierzawe(self, agent: str, sid: str) -> None:
        self._zapisz(agent, "DELETE FROM session_turn_leases WHERE conversation_id = ?", (sid,))

    def runs(self, agent: str | None = None) -> list[dict]:
        return [z for z in self.dziennik if z["sciezka"].endswith("/v1/runs") and z["metoda"] == "POST"
                and (agent is None or z["agent"] == agent)]

    # ------------------------------------------------------------------------------------------- state.db
    def _zapisz(self, agent: str, sql: str, arg: tuple) -> int:
        conn = sqlite3.connect(self.state_db(agent), timeout=5)
        try:
            cur = conn.execute(sql, arg)
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def _wiersz(self, agent: str, sid: str, rola: str, tresc: str, **pola) -> int:
        dane = {"session_id": sid, "role": rola, "content": tresc, "timestamp": time.time(), **pola}
        return self._zapisz(agent, f"INSERT INTO messages ({', '.join(dane)}) VALUES ({', '.join('?' * len(dane))})",
                            tuple(dane.values()))

    # ------------------------------------------------------------------------------------------- HTTP
    async def obsluz(self, request: httpx.Request) -> httpx.Response:
        """Wołane na pętli silnika; logika na pętli atrapy."""
        sciezka = request.url.path
        agent = ""
        m = re.match(r"^/p/([a-z0-9-]+)(/.*)$", sciezka)
        if m:
            agent, sciezka = m.group(1), m.group(2)
        if self.niedostepna:
            raise httpx.ConnectError("brama wyłączona", request=request)
        if request.headers.get("authorization") != f"Bearer {self.klucze.get(agent or 'default')}":
            return httpx.Response(401, json={"error": {"message": "unauthorized", "type": "auth", "code": "unauthorized"}})
        cialo = request.content
        try:
            dane = json.loads(cialo) if cialo else None
        except ValueError:
            dane = None
        self.dziennik.append({"metoda": request.method, "sciezka": sciezka, "agent": agent, "cialo": dane,
                              "naglowki": {k: v for k, v in request.headers.items() if k.lower() != "authorization"}})
        m = re.match(r"^/v1/runs/([^/]+)/events$", sciezka)
        if m and request.method == "GET":
            p = self.przebiegi.get(m.group(1))
            if p is None:
                return httpx.Response(404, json={"error": {"code": "run_not_found", "message": "", "type": "x"}})
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=self._strumien(p))
        status, odp, naglowki = await self._na_atrapie(
            self._zadanie(request.method, sciezka, agent, dane, cialo, dict(request.headers)))
        return httpx.Response(status, json=odp, headers=naglowki)

    async def _strumien(self, p: Przebieg):
        """Na pętli silnika: zdarzenia przebiegu jako `data: <json>` aż do zdarzenia końcowego."""
        while True:
            ev = await self._na_atrapie(p.kolejka.get())
            if ev is None:                         # [urwij]: koniec strumienia bez zdarzenia końcowego
                return
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode()
            if str(ev.get("event", "")).startswith("run.") and ev["event"] != "run.steered":
                return

    async def _zadanie(self, metoda: str, sciezka: str, agent: str, dane, surowe: bytes, naglowki: dict):
        if metoda == "POST" and sciezka == "/api/sessions":
            sid, tytul = dane["id"], dane.get("title") or ""
            if self.sesja(agent, sid):
                return _blad(409, "session_exists")
            self._zapisz(agent, "INSERT INTO sessions (id, source, title, started_at, last_activity_at) "
                                "VALUES (?, 'api_server', ?, ?, ?)", (sid, tytul, time.time(), time.time()))
            return 201, {"id": sid, "title": tytul}, {}
        m = re.match(r"^/api/sessions/([^/]+)$", sciezka)
        if m and metoda == "PATCH":
            sid = m.group(1)
            if not self.sesja(agent, sid):
                return _blad(404, "session_not_found")
            if "title" in dane:
                self._zapisz(agent, "UPDATE sessions SET title = ? WHERE id = ?", (dane["title"], sid))
            if "pinned" in dane:
                self._zapisz(agent, "UPDATE sessions SET pinned = ? WHERE id = ?", (int(bool(dane["pinned"])), sid))
            return 200, self.sesja(agent, sid), {}
        if metoda == "POST" and sciezka == "/v1/runs":
            return self._start(agent, dane, surowe, naglowki.get("idempotency-key", ""))
        m = re.match(r"^/v1/runs/([^/]+)(/[a-z]+)?$", sciezka)
        if not m:
            return _blad(404, "not_found")
        p = self.przebiegi.get(m.group(1))
        if p is None:
            return _blad(404, "run_not_found")
        akcja = m.group(2) or ""
        if akcja == "" and metoda == "GET":
            out = {"run_id": p.id, "status": p.status, **p.koniec}
            if p.status == "waiting_for_approval" and p.zgoda:
                out["approval"] = p.zgoda
            return 200, out, {}
        if akcja == "/approval":
            if not p.zgoda or p.odpowiedz_zgody is None or p.odpowiedz_zgody.done() \
                    or dane.get("request_id") != p.zgoda["request_id"]:
                return _blad(409, "approval_not_pending")
            p.odpowiedz_zgody.set_result(dane.get("choice"))
            return 200, {"ok": True}, {}
        if akcja == "/steer":
            if p.status != "running":
                return _blad(409, "run_not_accepting_steer")
            tekst = str(dane.get("input") or "").strip()          # jak AIAgent.steer: obcięte spacje z brzegów
            if p.koncowka:
                p.oczekujace.append(tekst)
            else:
                p.dopisane.append(tekst)
                self._wiersz(p.agent, p.sid, "user", f"{STEER_OTWARCIE}\n{tekst}\n{STEER_ZAMKNIECIE}",
                             display_kind="steer")
                p.kolejka.put_nowait({"event": "run.steered", "accepted": True, "timestamp": time.time()})
            return 202, {"accepted": True}, {}
        if akcja == "/stop":
            if p.status in KONCOWE:
                return _blad(409, "run_not_active")
            p.status = "stopping"
            p.stop.set()
            return 200, {"run_id": p.id, "status": "stopping"}, {}
        return _blad(404, "not_found")

    def _start(self, agent: str, dane: dict, surowe: bytes, klucz: str):
        if self.limit_429 > 0:
            self.limit_429 -= 1
            return _blad(429, "rate_limit_exceeded", "rate_limit_error", {"Retry-After": "1"})
        sha = hashlib.sha256(surowe).hexdigest()
        if klucz and (agent, klucz) in self.idem:
            byl_sha, run_id = self.idem[(agent, klucz)]
            if byl_sha != sha:
                return _blad(409, "idempotency_key_conflict")
            p = self.przebiegi[run_id]
            return 202, {"run_id": run_id, "status": "started" if p.status in ("queued", "running") else p.status,
                         "replayed": True}, {}
        run_id = "run_" + secrets.token_hex(8)
        p = Przebieg(run_id, agent, dane["session_id"], dane["input"], dane)
        self.przebiegi[run_id] = p
        if klucz:
            self.idem[(agent, klucz)] = (sha, run_id)
        self.loop.create_task(self._tura(p))
        return 202, {"run_id": run_id, "status": "started", "replayed": False}, {}

    # ------------------------------------------------------------------------------------------- tura
    @staticmethod
    def _tekst(wejscie) -> tuple[str, int]:
        if isinstance(wejscie, list):
            czesci = wejscie[0]["content"]
            tekst = "\n".join(c["text"] for c in czesci if c.get("type") == "text")
            return tekst, sum(1 for c in czesci if c.get("type") == "image_url")
        return str(wejscie), 0

    async def _spij(self, p: Przebieg, s: float) -> bool:
        """Czeka `s` sekund; True = przyszedł stop."""
        try:
            await asyncio.wait_for(p.stop.wait(), timeout=s)
            return True
        except asyncio.TimeoutError:
            return False

    def _koniec(self, p: Przebieg, status: str, **pola) -> None:
        p.status = status
        p.koniec = {"output": p.odpowiedz, "pending_steer": "\n".join(p.oczekujace) or None, **pola}
        self.zwolnij_dzierzawe(p.agent, p.sid)
        ev = {"event": f"run.{status}", "timestamp": time.time(), **p.koniec}
        p.kolejka.put_nowait(ev)

    async def _tura(self, p: Przebieg) -> None:
        tekst, obrazy = self._tekst(p.wejscie)
        if "[czekaj]" in tekst:
            czekaj = asyncio.ensure_future(p.zwolnij.wait())
            stop = asyncio.ensure_future(p.stop.wait())
            await asyncio.wait({czekaj, stop}, return_when=asyncio.FIRST_COMPLETED)
            czekaj.cancel()
            stop.cancel()
            if p.stop.is_set():
                self._koniec(p, "cancelled", interrupted=True)
                return
        p.status = "running"
        self.dzierzawa(p.agent, p.sid, platforma="api_server")
        projekcja = "\n".join([tekst, *(["[screenshot]"] * obrazy)]) if obrazy else tekst
        self._wiersz(p.agent, p.sid, "user", projekcja)
        ostatnia = [x for x in tekst.splitlines() if x.strip()][-1:] or [""]
        p.odpowiedz = f"Odpowiedź: {ZNACZNIK_RE.sub('', ostatnia[0])[:80]}"
        if "[urwij]" in tekst:
            p.kolejka.put_nowait({"event": "message.delta", "delta": "…", "timestamp": time.time()})
            p.kolejka.put_nowait(None)
            p.odpowiedz = "…" + p.odpowiedz
            await asyncio.sleep(0.5)
        if "[zgoda]" in tekst:
            rid = "req_" + secrets.token_hex(4)
            # pattern_key = opis wzorca Hermesa (tools/approval_detection.py DANGEROUS_PATTERNS)
            p.zgoda = {"request_id": rid, "command": "rm -rf /tmp/jarvo-e2e-zgoda", "pattern_key": "recursive delete",
                       "pattern_keys": ["recursive delete"], "description": "recursive delete",
                       "choices": ["once", "session", "deny"]}
            p.odpowiedz_zgody = self.loop.create_future()
            p.status = "waiting_for_approval"
            p.kolejka.put_nowait({"event": "approval.request", "timestamp": time.time(), **p.zgoda})
            stop = asyncio.ensure_future(p.stop.wait())
            await asyncio.wait({p.odpowiedz_zgody, stop}, timeout=self.czas_zgody, return_when=asyncio.FIRST_COMPLETED)
            stop.cancel()
            if p.stop.is_set():
                self._koniec(p, "cancelled", interrupted=True)
                return
            if not p.odpowiedz_zgody.done():
                # czas bramy minął: odmowa bez `approval.responded`, status zostaje waiting_for_approval do końca
                p.odpowiedz_zgody.cancel()
                p.odpowiedz = "zgoda:czas " + p.odpowiedz
            else:
                wybor = p.odpowiedz_zgody.result()
                p.status = "running"
                p.kolejka.put_nowait({"event": "approval.responded", "choice": wybor, "timestamp": time.time()})
                p.odpowiedz = f"zgoda:{wybor} " + p.odpowiedz
        if "[blad]" in tekst:
            self._wiersz(p.agent, p.sid, "assistant", "Your request was not processed.", display_kind="failed_turn")
            self._koniec(p, "failed", error="model error", turn_exit_reason="model_error")
            return
        if "[przerwij]" in tekst:
            self._koniec(p, "interrupted", interrupted=True, turn_exit_reason="interrupted")
            return
        m = WOLNO_RE.search(tekst)
        czas = float(m.group(1)) if m else 0.0
        kawalki = [p.odpowiedz[i:i + 6] for i in range(0, len(p.odpowiedz), 6)]
        p.kolejka.put_nowait({"event": "tool.started", "tool": "read_file", "preview": "notatki.md",
                              "timestamp": time.time()})
        p.kolejka.put_nowait({"event": "tool.completed", "tool": "read_file", "duration": 0.01, "error": False,
                              "preview": "ok", "timestamp": time.time()})
        for k in kawalki:
            if await self._spij(p, czas / max(1, len(kawalki))):
                self._wiersz(p.agent, p.sid, "assistant", p.odpowiedz[:3])
                self._koniec(p, "cancelled", interrupted=True)
                return
            p.kolejka.put_nowait({"event": "message.delta", "delta": k, "timestamp": time.time()})
        if p.dopisane:
            dop = " | dopisane: " + "; ".join(p.dopisane)
            p.odpowiedz += dop
            p.kolejka.put_nowait({"event": "message.delta", "delta": dop, "timestamp": time.time()})
        p.koncowka = True
        await asyncio.sleep(0.05)
        self._wiersz(p.agent, p.sid, "assistant", p.odpowiedz)
        self._koniec(p, "completed", usage={"input_tokens": 1, "output_tokens": 1})
