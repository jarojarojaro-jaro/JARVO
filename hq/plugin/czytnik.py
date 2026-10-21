"""Czytnik sesji Hermesa do osi czasu wątku: wiersze jednej sesji z state.db profilu, tylko do odczytu.

- **Główna droga: projekcja Hermesa.** `SessionDB(<state.db>, read_only=True).get_messages(sid,
  include_compacted=True)` i `hermes_cli.web_routers.sessions._project_for_display(rows, home=<profil>)`, czyli
  to samo, co robi `GET /api/sessions/{id}/messages` dashboardu Hermesa: kolejność po id / `display_order` (nigdy
  po czasie), jedna pozycja na pokolenie kompresji, bez wierszy `model_only`, streszczenia kompresji rzutowane,
  nieoznaczone nieudane tury jako `failed_turn`. `read_only=True`: Hermes nie dopisuje `display_order` (brak zapisu).
- **Zapasowo: surowy SQL tylko do odczytu** (`file:…?mode=ro` z `Path.as_uri()`), gdy Hermesa nie da się
  zaimportować albo jego odczyt się wyłożył. Te same reguły z kolumn: wiersze widoczne (`active = 1 OR
  compacted = 1`) bez `model_only`; przy pełnym indeksie wyświetlania grupy po `display_order` z wierszem
  (active, id) najwyższym; bez indeksu (stare sesje) tożsamość (rola, treść, czas, tool_call_id, tool_calls,
  tool_name) w kolejności pierwszego wystąpienia. Uproszczenia względem Hermesa (opisane w docs/HQ.md „Rozmowy”):
  streszczenia rozpoznawane po początku `[CONTEXT COMPACTION — ` / `[CONTEXT SUMMARY]:`, streszczenie w treści
  listowej zawsze ukryte, komentarze Codex (`codex_message_items`) pomijane, w starych sesjach bez indeksu nośnik
  przekazania użytkownika liczony po surowej treści.
- Obie drogi dają tę samą listę pozycji (`normalizuj`), a `python3 czytnik.py --porownaj <state.db> <sesja>`
  sprawdza to na prawdziwej sesji w kontenerze (i że state.db zostaje bajt w bajt ten sam).
Czysty Python (sqlite3); Hermes tylko w imporcie z osłoną. Testy: tests/test_czytnik.py.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable, Iterable

PREFIKS_JSON = "\x00json:"                    # hermes_state.SessionDB._CONTENT_JSON_PREFIX (treść listowa)
PRZEDROSTKI_STRESZCZENIA = ("[CONTEXT COMPACTION — ", "[CONTEXT SUMMARY]:")
GRANICA_SCALENIA = "[END OF PRIOR CONTEXT — COMPACTION SUMMARY BELOW]"
NAGLOWEK_SCALENIA = "[PRIOR CONTEXT — for reference only; not a new message]"
KONIEC_STRESZCZENIA = "--- END OF CONTEXT SUMMARY — respond to the message below, not the summary above ---"
NIEUDANA_TURA = (                             # agent/turn_failure_copy.py: dokładny tekst, wtedy `failed_turn`
    "Your request was not processed. Send it again if you still want me to carry it out.",
    "This turn did not complete. Some actions may already have run; verify their effects before resending.",
)
BRAK_SESJI = "brak_sesji"
PROFIL_RE = re.compile(r"^[a-z0-9-]+$")
# kolumny, które czyta aplikacja (spr. raz na profil; brak = schemat Hermesa się zmienił)
SCHEMAT_WYMAGANY = {
    "messages": ("id", "session_id", "role", "content", "tool_calls", "tool_call_id", "tool_name", "timestamp", "active",
                 "compacted", "_compressed_summary", "display_kind", "display_metadata", "display_order"),
    "sessions": ("id", "source", "title", "parent_session_id", "started_at", "last_activity_at", "end_reason"),
    "session_turn_leases": ("conversation_id", "holder", "acquired_at", "expires_at"),
}
_WIDOCZNE = " AND (active = 1 OR compacted = 1)"
_BEZ_MODEL_ONLY = (" AND COALESCE(json_extract(CASE WHEN json_valid(display_metadata) THEN display_metadata "
                   "ELSE json_object() END, '$.model_only'), 0) = 0")


class SchematZmieniony(RuntimeError):
    """state.db profilu nie ma kolumn, które czyta aplikacja (aktualizacja Hermesa): silnik przechodzi na odczyt
    przez bramę profilu, `/health` mówi `schemat_hermesa: "zmieniony"`."""


# ----------------------------------------------------------------------------------------------- wspólne

def uri_tylko_odczyt(state_db: Path | str) -> str:
    """`file:` URI z `mode=ro`; `as_uri()` koduje `?` i `#` w ścieżce (jak hermes_state_holders.read_only_db_uri)."""
    return Path(state_db).resolve().as_uri() + "?mode=ro"


def _polacz(state_db: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(uri_tylko_odczyt(state_db), uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = 1")
    return conn


def sprawdz_schemat(state_db: Path | str) -> list[str]:
    """Brakujące kolumny jako `tabela.kolumna` (pusta lista = schemat zgodny)."""
    conn = _polacz(state_db)
    try:
        brak = []
        for tabela, kolumny in SCHEMAT_WYMAGANY.items():
            sa = {r[1] for r in conn.execute(f"PRAGMA table_info({tabela})")}
            brak += [f"{tabela}.{k}" for k in kolumny if k not in sa]
        return brak
    finally:
        conn.close()


def tekst_tresci(content: Any) -> str:
    """Treść jako tekst: lista części → teksty i `[screenshot]` za każdy obraz, połączone `\\n` (tak Hermes
    utrwala treść z obrazami, session_persistence._durable_content)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for p in content:
            if isinstance(p, str):
                out.append(p)
            elif isinstance(p, dict):
                if p.get("type") in ("image_url", "input_image", "image"):
                    out.append("[screenshot]")
                elif isinstance(p.get("text"), str):
                    out.append(p["text"])
        return "\n".join(out)
    return str(content)


def czy_streszczenie(content: Any) -> bool:
    """Treść jest przekazaniem po kompresji (samodzielnym albo scalonym z poprzednią treścią)."""
    tekst = tekst_tresci(content).lstrip()
    if GRANICA_SCALENIA in tekst:
        tekst = tekst.split(GRANICA_SCALENIA, 1)[1].lstrip()
    return tekst.startswith(PRZEDROSTKI_STRESZCZENIA)


def _bez_przekazania(content: Any) -> str | None:
    """Prawdziwa treść zachowana w nośniku streszczenia (część przed granicą scalenia albo po znaczniku końca);
    None = samo przekazanie (ukryte). Treść listowa: zawsze None (uproszczenie)."""
    if not isinstance(content, str):
        return None
    if GRANICA_SCALENIA in content:
        przed = content.split(GRANICA_SCALENIA, 1)[0].strip()
        if przed.startswith(NAGLOWEK_SCALENIA):
            przed = przed[len(NAGLOWEK_SCALENIA):].lstrip()
    elif KONIEC_STRESZCZENIA in content:
        przed = content.split(KONIEC_STRESZCZENIA, 1)[1].lstrip()
    else:
        przed = ""
    return przed or None


def _json(raw: Any, domyslna: Any) -> Any:
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return domyslna


def _meta(raw: Any) -> dict | None:
    """display_metadata jako słownik (stare wiersze bywają zakodowane dwa razy)."""
    m = raw
    for _ in range(2):
        if isinstance(m, str):
            m = _json(m, None)
    return m if isinstance(m, dict) else None


def normalizuj(m: dict, sesja_id: str) -> dict:
    """Wiadomość po projekcji (Hermesa albo zapasowej) → pozycja czytnika o stałych polach."""
    tool_calls = m.get("tool_calls")
    if isinstance(tool_calls, str):
        tool_calls = _json(tool_calls, [])
    podsumowanie = bool(m.get("_compressed_summary")) or czy_streszczenie(m.get("content"))
    if podsumowanie:
        tresc = tekst_tresci(m.get("display_content")) if "display_content" in m else ""
    else:
        tresc = tekst_tresci(m.get("content"))
    ts = float(m.get("timestamp") or 0)
    rola = m.get("role") or ""
    return {
        "id": int(m.get("id") or 0),
        "sesja_id": sesja_id,
        "rola": rola,
        "tresc": tresc,
        "tool_calls": tool_calls if isinstance(tool_calls, list) else [],
        "tool_call_id": m.get("tool_call_id"),
        "tool_name": m.get("tool_name"),
        "ts": ts,
        "rodzaj": m.get("display_kind") or None,
        "meta": _meta(m.get("display_metadata")),
        "podsumowanie": podsumowanie,
        "aktywny": bool(m.get("active", 1)),
        "skompaktowany": bool(m.get("compacted", 0)),
        "klucz": hashlib.sha256(f"{rola}|{ts!r}|{tresc}".encode("utf-8", "surrogatepass")).hexdigest()[:16],
    }


def _sesja_istnieje(state_db: Path | str, sesja_id: str) -> bool:
    conn = _polacz(state_db)
    try:
        return conn.execute("SELECT 1 FROM sessions WHERE id = ?", (sesja_id,)).fetchone() is not None
    finally:
        conn.close()


# ----------------------------------------------------------------------------------------------- droga zapasowa

def _klucz_tozsamosci(r: sqlite3.Row) -> tuple:
    return (r["role"], r["content"], r["timestamp"], r["tool_call_id"], r["tool_calls"], r["tool_name"])


def _wiersze_widoku(conn: sqlite3.Connection, sesja_id: str) -> list[sqlite3.Row]:
    kolumny = {r[1] for r in conn.execute("PRAGMA table_info(messages)")}
    indeks = {"display_order", "display_identity"} <= kolumny and conn.execute(
        "SELECT 1 FROM messages WHERE session_id = ?" + _WIDOCZNE +
        " AND (display_order IS NULL OR display_identity IS NULL) LIMIT 1", (sesja_id,)).fetchone() is None
    if indeks:     # jak SessionDB._display_rows_from_conn: grupa display_order, w niej (active, id) najwyższe
        return conn.execute(
            f"""WITH page AS (SELECT display_order FROM messages WHERE session_id = ?{_WIDOCZNE}{_BEZ_MODEL_ONLY}
                              GROUP BY display_order)
                SELECT chosen.* FROM page JOIN messages AS chosen ON chosen.id = (
                    SELECT candidate.id FROM messages AS candidate
                    WHERE candidate.session_id = ? AND candidate.display_order = page.display_order
                      AND (candidate.active = 1 OR candidate.compacted = 1){_BEZ_MODEL_ONLY}
                    ORDER BY candidate.active DESC, candidate.id DESC LIMIT 1)
                ORDER BY page.display_order ASC""", (sesja_id, sesja_id)).fetchall()
    # stara sesja bez indeksu (jak SessionDB._legacy_display_page): tożsamość, kolejność pierwszego wystąpienia
    wybrane: dict[tuple, sqlite3.Row] = {}
    for r in conn.execute("SELECT * FROM messages WHERE session_id = ?" + _WIDOCZNE + " ORDER BY id ASC", (sesja_id,)):
        if (_meta(r["display_metadata"]) or {}).get("model_only"):
            continue
        k = _klucz_tozsamosci(r)
        jest = wybrane.get(k)
        if jest is None or (r["active"], r["id"]) > (jest["active"], jest["id"]):
            wybrane[k] = r
    return list(wybrane.values())


def _jak_hermes(r: sqlite3.Row) -> dict:
    """Wiersz jak SessionDB._row_to_message_dict (treść i tool_calls zdekodowane, flaga streszczenia)."""
    m = {k: r[k] for k in r.keys() if k not in ("display_identity", "display_order")}
    if m.pop("_compressed_summary", 0):
        m["_compressed_summary"] = True
    tresc = m.get("content")
    if isinstance(tresc, str) and tresc.startswith(PREFIKS_JSON):
        m["content"] = _json(tresc[len(PREFIKS_JSON):], tresc)
    if m.get("tool_calls"):
        m["tool_calls"] = _json(m["tool_calls"], [])
    if m.get("display_metadata") is not None:
        m["display_metadata"] = _meta(m["display_metadata"])
    return m


def projektuj(m: dict) -> dict:
    """Część `_project_for_display`, której używa oś czasu: `failed_turn` dla nieoznaczonej nieudanej tury,
    streszczenie kompresji z `display_content` (prawdziwa treść z nośnika) albo ukryte."""
    m = dict(m)
    tresc = m.get("content")
    if (not m.get("display_kind") and m.get("role") == "assistant" and isinstance(tresc, str)
            and tresc.strip() in NIEUDANA_TURA):
        m["display_kind"] = "failed_turn"
    if not (m.get("_compressed_summary") or czy_streszczenie(tresc)):
        return m
    widok = _bez_przekazania(tresc)
    if widok is None:
        if not m.get("display_kind"):
            m["display_kind"] = "hidden"
    else:
        m["display_content"] = widok
        m.pop("display_kind", None)
    return m


def czytaj_zapasowo(state_db: Path | str, sesja_id: str) -> list[dict] | None:
    """Pozycje sesji przez surowy SQL tylko do odczytu; None = sesji nie ma (usunięta przez Hermesa)."""
    conn = _polacz(state_db)
    try:
        if conn.execute("SELECT 1 FROM sessions WHERE id = ?", (sesja_id,)).fetchone() is None:
            return None
        conn.execute("BEGIN")          # jeden spójny odczyt (WAL: migawka)
        try:
            wiersze = _wiersze_widoku(conn, sesja_id)
        finally:
            conn.execute("ROLLBACK")
    finally:
        conn.close()
    return [normalizuj(projektuj(_jak_hermes(r)), sesja_id) for r in wiersze]


# ----------------------------------------------------------------------------------------------- droga Hermesa

def _hermes():
    """(SessionDB, _project_for_display) albo ImportError (poza obrazem Hermesa)."""
    from hermes_state import SessionDB                                       # noqa: PLC0415
    from hermes_cli.web_routers.sessions import _project_for_display        # noqa: PLC0415
    return SessionDB, _project_for_display


def hermes_dostepny() -> bool:
    try:
        _hermes()
    except Exception:  # ImportError albo błąd przy imporcie modułów Hermesa
        return False
    return True


def czytaj_hermes(state_db: Path | str, sesja_id: str, home: Path | str | None = None) -> list[dict] | None:
    """Pozycje sesji przez projekcję Hermesa (SessionDB tylko do odczytu); None = sesji nie ma."""
    SessionDB, projekcja = _hermes()
    if not _sesja_istnieje(state_db, sesja_id):
        return None
    db = SessionDB(Path(state_db), read_only=True)
    try:
        wiersze = db.get_messages(sesja_id, include_compacted=True)
    finally:
        db.close()
    return [normalizuj(m, sesja_id) for m in projekcja(wiersze, home=home)]


# ----------------------------------------------------------------------------------------------- czytnik profili

class Czytnik:
    """Czyta sesje członków wątku. `profile_root` = /opt/data/profiles, `agenci()` = nazwy profili, które wolno
    czytać (flota + agenci testowi/własni). `tryb`: "auto" (Hermes, gdy się da), "hermes" albo "zapasowy"."""

    def __init__(self, profile_root: Path | str, agenci: Callable[[], Iterable[str]], *, tryb: str = "auto",
                 log: Callable[[str], None] | None = None):
        self.root = Path(profile_root)
        self.agenci = agenci
        self.log = log or (lambda _m: None)
        if tryb not in ("auto", "hermes", "zapasowy"):
            raise ValueError(f"zły tryb czytnika: {tryb}")
        self._tryb = "zapasowy" if tryb == "zapasowy" else ("hermes" if hermes_dostepny() else "zapasowy")
        if tryb == "hermes" and self._tryb != "hermes":
            raise RuntimeError("projekcja Hermesa niedostępna")
        self._schemat: dict[str, list[str]] = {}

    @property
    def tryb(self) -> str:
        """`hermes` albo `zapasowy` (dla /health: `czytnik`)."""
        return self._tryb

    def state_db(self, profil: str) -> Path:
        """Ścieżka state.db profilu; nazwa sprawdzona wobec listy agentów, zanim powstanie ścieżka."""
        if not PROFIL_RE.fullmatch(str(profil or "")) or profil not in set(self.agenci()):
            raise ValueError(f"nieznany profil {profil!r}")
        sciezka = (self.root / profil / "state.db").resolve()
        if self.root.resolve() not in sciezka.parents:
            raise ValueError(f"profil {profil!r} poza katalogiem profili")
        return sciezka

    def schemat(self, profil: str) -> list[str]:
        """Brakujące kolumny state.db profilu (sprawdzane raz na profil)."""
        if profil not in self._schemat:
            sciezka = self.state_db(profil)
            self._schemat[profil] = sprawdz_schemat(sciezka) if sciezka.exists() else []
        return self._schemat[profil]

    def sesja(self, profil: str, sesja_id: str) -> list[dict] | None:
        """Pozycje jednej sesji agenta (None = `brak_sesji`). SchematZmieniony, gdy brak wymaganych kolumn."""
        sciezka = self.state_db(profil)
        if not sciezka.exists():
            return None
        brak = self.schemat(profil)
        if brak:
            raise SchematZmieniony(f"{profil}: brak kolumn {', '.join(brak)}")
        if self._tryb == "hermes":
            try:
                return czytaj_hermes(sciezka, sesja_id, home=sciezka.parent)
            except Exception as exc:  # odczyt Hermesa się wyłożył: od teraz droga zapasowa (zgłasza /health)
                self.log(f"jarvo-hq: czytnik Hermesa zawiódł ({type(exc).__name__}), przechodzę na zapasowy")
                self._tryb = "zapasowy"
        return czytaj_zapasowo(sciezka, sesja_id)

    def linia(self, profil: str, sesje: Iterable[str]) -> list[dict]:
        """Każda sesja rodowodu członka: `{sesja_id, stan: ok|brak_sesji, wiersze}` (oś czasu pokaże lukę)."""
        out = []
        for sid in sesje:
            wiersze = self.sesja(profil, sid)
            out.append({"sesja_id": sid, "stan": BRAK_SESJI if wiersze is None else "ok", "wiersze": wiersze or []})
        return out

    # ---- sondy silnika (rejestr przebiegów, obserwator): krótkie zapytania tylko do odczytu
    def _sonda(self, profil: str, fn: Callable, *arg, domyslna: Any = None):
        try:
            sciezka = self.state_db(profil)
        except ValueError:            # agent zniknął z listy (np. sprzątnięty agent testowy)
            return domyslna
        if not sciezka.exists():
            return domyslna
        try:
            return fn(sciezka, *arg)
        except sqlite3.Error as exc:
            self.log(f"jarvo-hq: sonda state.db {profil} ({type(exc).__name__})")
            return domyslna

    def dzierzawa(self, profil: str, sesje: Iterable[str], teraz: float) -> dict | None:
        """Ważna dzierżawa tury na rodowodzie członka (dowolny posiadacz) albo None."""
        d = self._sonda(profil, dzierzawy, list(sesje), teraz, domyslna=[])
        return d[0] if d else None

    def nasz_wiersz(self, profil: str, sesje: Iterable[str], sha: str, od_ts: float) -> int | None:
        return self._sonda(profil, nasz_wiersz, list(sesje), sha, od_ts)

    def odpowiedz_po(self, profil: str, sesje: Iterable[str], po_id: int) -> bool:
        return bool(self._sonda(profil, odpowiedz_po, list(sesje), po_id, domyslna=False))

    def stan_sesji(self, profil: str, sesje: Iterable[str]) -> dict:
        return self._sonda(profil, stan_sesji, list(sesje), domyslna={"max_id": 0, "skompaktowane": 0})

    def dzieci_kompresji(self, profil: str, sesje: Iterable[str]) -> list[tuple[str, str]]:
        return self._sonda(profil, dzieci_kompresji, list(sesje), domyslna=[])

    def steery_po(self, profil: str, sesje: Iterable[str], od_ts: float) -> list[str]:
        return self._sonda(profil, steery_po, list(sesje), od_ts, domyslna=[])

    @staticmethod
    def tekst_steera(tresc: str) -> str:
        """Tekst dopisku z wiersza `steer` (funkcja modułu `tekst_steera`)."""
        return tekst_steera(tresc)

    @staticmethod
    def dopisek_w_steerze(tresc: str, tekst: str) -> bool:
        """Wiersz `steer` niesie ten dopisek (funkcja modułu `dopisek_w_steerze`)."""
        return dopisek_w_steerze(tresc, tekst)

    def ostatni_uzytkownika(self, profil: str, sesje: Iterable[str]) -> tuple[str, str]:
        return self._sonda(profil, ostatni_uzytkownika, list(sesje), domyslna=("", "")) or ("", "")

    def dzierzawy_profilu(self, profil: str, teraz: float) -> list[dict]:
        return self._sonda(profil, dzierzawy_profilu, teraz, domyslna=[])


# ----------------------------------------------------------------------------------------------- sondy state.db

PLATFORMA_RE = re.compile(r":platform=([^:]+)$")      # turn= też ma dwukropki: kotwica na końcu


def platforma(holder: str) -> str:
    """Platforma tury z posiadacza dzierżawy (`pid=…:turn=…:platform=<p>`)."""
    m = PLATFORMA_RE.search(str(holder or ""))
    return m.group(1) if m else ""


def _w(sesje: list[str]) -> str:
    return ", ".join("?" * len(sesje))


def dzierzawy(state_db: Path | str, sesje: list[str], teraz: float) -> list[dict]:
    """Ważne (`expires_at > teraz`) dzierżawy tury na sesjach rodowodu (klucz = korzeń kompresji, więc pytamy
    o każdy id rodowodu)."""
    if not sesje:
        return []
    conn = _polacz(state_db)
    try:
        rows = conn.execute(f"SELECT conversation_id, holder, acquired_at, expires_at FROM session_turn_leases "
                            f"WHERE conversation_id IN ({_w(sesje)}) AND expires_at > ?", (*sesje, teraz)).fetchall()
    finally:
        conn.close()
    return [{"sesja_id": r["conversation_id"], "platforma": platforma(r["holder"]), "od": float(r["acquired_at"]),
             "do": float(r["expires_at"])} for r in rows]


def dzierzawy_profilu(state_db: Path | str, teraz: float) -> list[dict]:
    """Wszystkie ważne dzierżawy tur profilu (praca floty do `praca.json`)."""
    conn = _polacz(state_db)
    try:
        rows = conn.execute("SELECT conversation_id, holder, expires_at FROM session_turn_leases WHERE expires_at > ?",
                            (teraz,)).fetchall()
    finally:
        conn.close()
    return [{"sesja_id": r["conversation_id"], "platforma": platforma(r["holder"]), "do": float(r["expires_at"])}
            for r in rows]


def _tresc_wiersza(raw: Any) -> str:
    if isinstance(raw, str) and raw.startswith(PREFIKS_JSON):
        raw = _json(raw[len(PREFIKS_JSON):], raw)
    return tekst_tresci(raw)


def nasz_wiersz(state_db: Path | str, sesje: list[str], sha: str, od_ts: float) -> int | None:
    """Id wiersza użytkownika naszej tury: treść (trwała projekcja) o skrócie `sha`, czas ≥ `od_ts` (wyslany_at − 2 s).
    Hermes zapisuje go raz, na starcie tury, gdy już trzyma dzierżawę."""
    if not sesje or not sha:
        return None
    conn = _polacz(state_db)
    try:
        for r in conn.execute(f"SELECT id, content FROM messages WHERE session_id IN ({_w(sesje)}) AND role = 'user' "
                              f"AND timestamp >= ? ORDER BY id", (*sesje, od_ts)):
            if hashlib.sha256(_tresc_wiersza(r["content"]).encode("utf-8", "surrogatepass")).hexdigest() == sha:
                return int(r["id"])
    finally:
        conn.close()
    return None


def odpowiedz_po(state_db: Path | str, sesje: list[str], po_id: int) -> bool:
    """Czy po wierszu `po_id` jest odpowiedź asystenta z tekstem (przebieg „tylko z osi czasu”)."""
    if not sesje:
        return False
    conn = _polacz(state_db)
    try:
        return conn.execute(f"SELECT 1 FROM messages WHERE session_id IN ({_w(sesje)}) AND id > ? AND role = 'assistant' "
                            f"AND COALESCE(content, '') != '' LIMIT 1", (*sesje, po_id)).fetchone() is not None
    finally:
        conn.close()


def stan_sesji(state_db: Path | str, sesje: list[str]) -> dict:
    """Znak wodny obserwatora: najwyższe id wiadomości i liczba wierszy skompaktowanych (pokolenie kompresji)."""
    if not sesje:
        return {"max_id": 0, "skompaktowane": 0}
    conn = _polacz(state_db)
    try:
        r = conn.execute(f"SELECT COALESCE(MAX(id), 0), COALESCE(SUM(compacted = 1), 0) FROM messages "
                         f"WHERE session_id IN ({_w(sesje)})", sesje).fetchone()
    finally:
        conn.close()
    return {"max_id": int(r[0] or 0), "skompaktowane": int(r[1] or 0)}


def dzieci_kompresji(state_db: Path | str, sesje: list[str]) -> list[tuple[str, str]]:
    """(dziecko, rodzic): sesje potomne rodowodu, których rodzic skończył się kompresją z rotacją."""
    if not sesje:
        return []
    conn = _polacz(state_db)
    try:
        return [(r[0], r[1]) for r in conn.execute(
            f"SELECT s.id, s.parent_session_id FROM sessions s JOIN sessions p ON p.id = s.parent_session_id "
            f"WHERE s.parent_session_id IN ({_w(sesje)}) AND p.end_reason = 'compression' ORDER BY s.started_at, s.id",
            sesje)]
    finally:
        conn.close()


def ostatni_uzytkownika(state_db: Path | str, sesje: list[str]) -> tuple[str, str]:
    """(treść, display_kind) najnowszego wiersza użytkownika rodowodu (rodzaj obcej tury: `[kanban]` = budzenie,
    `steer` = dopisek w trakcie tury)."""
    if not sesje:
        return "", ""
    conn = _polacz(state_db)
    try:
        r = conn.execute(f"SELECT content, display_kind FROM messages WHERE session_id IN ({_w(sesje)}) "
                         f"AND role = 'user' ORDER BY id DESC LIMIT 1", sesje).fetchone()
    finally:
        conn.close()
    return (_tresc_wiersza(r["content"]), str(r["display_kind"] or "")) if r else ("", "")


STEER_OTWARCIE = "[OUT-OF-BAND USER MESSAGE"          # agent/prompt_builder.py STEER_MARKER_OPEN (początek)
STEER_ZAMKNIECIE = "[/OUT-OF-BAND USER MESSAGE]"


def steery_po(state_db: Path | str, sesje: list[str], od_ts: float) -> list[str]:
    """Treści wierszy `steer` rodowodu od `od_ts` (dopiski, które Hermes dostarczył do tury; silnik sprawdza nimi
    dopisek, którego `pending_steer` nie rozstrzygnął)."""
    if not sesje:
        return []
    conn = _polacz(state_db)
    try:
        rows = conn.execute(f"SELECT content, display_kind FROM messages WHERE session_id IN ({_w(sesje)}) "
                            f"AND role = 'user' AND timestamp >= ? ORDER BY id", (*sesje, od_ts)).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        tresc = _tresc_wiersza(r["content"])
        if str(r["display_kind"] or "") == "steer" or tresc.strip().startswith(STEER_OTWARCIE):
            out.append(tresc)
    return out


def tekst_steera(tresc: str) -> str:
    """Tekst dopisku z wiersza `steer` (Hermes owija go znacznikiem: otwarcie w pierwszej linii, zamknięcie w ostatniej);
    bez znacznika: cała treść."""
    t = str(tresc or "").strip()
    if t.startswith(STEER_OTWARCIE) and t.endswith(STEER_ZAMKNIECIE):
        _glowa, _, reszta = t.partition("\n")
        return reszta[:-len(STEER_ZAMKNIECIE)].strip("\n")
    return t


def dopisek_w_steerze(tresc: str, tekst: str) -> bool:
    """Wiersz `steer` niesie dopisek `tekst` całymi liniami, po kolei (Hermes skleja kilka dopisków jednej tury
    znakiem nowej linii i obcina spacje z brzegów). Nie podciąg: krótki dopisek „ok” nie ukryje obcego „ok, usuń”."""
    szukane = str(tekst or "").strip().split("\n")
    if szukane == [""]:
        return False
    linie = tekst_steera(tresc).split("\n")
    return any(linie[i:i + len(szukane)] == szukane for i in range(len(linie) - len(szukane) + 1))


# ----------------------------------------------------------------------------------------------- CLI

def _odcisk(sciezka: Path) -> tuple[str, int]:
    return hashlib.sha256(sciezka.read_bytes()).hexdigest(), sciezka.stat().st_mtime_ns


def porownaj(state_db: Path | str, sesja_id: str, home: Path | str | None = None) -> dict:
    """Projekcja Hermesa kontra droga zapasowa na jednej sesji i dowód, że state.db się nie zmienił."""
    sciezka = Path(state_db)
    przed = _odcisk(sciezka)
    zapasowo = czytaj_zapasowo(sciezka, sesja_id)
    try:
        hermes = czytaj_hermes(sciezka, sesja_id, home=home or sciezka.parent)
        blad = None
    except Exception as exc:
        hermes, blad = None, f"{type(exc).__name__}: {exc}"
    po = _odcisk(sciezka)
    roznice = []
    if hermes is not None and zapasowo is not None:
        for i, (a, b) in enumerate(zip(hermes, zapasowo)):
            if a != b:
                roznice.append({"poz": i, "pola": sorted(k for k in a if a[k] != b.get(k))})
        if len(hermes) != len(zapasowo):
            roznice.append({"dlugosc": [len(hermes), len(zapasowo)]})
    return {"sesja": sesja_id, "hermes": None if hermes is None else len(hermes),
            "zapasowo": None if zapasowo is None else len(zapasowo), "blad_hermesa": blad,
            "rowne": blad is None and hermes == zapasowo, "roznice": roznice[:10],
            "state_db_bez_zmian": przed == po}


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Czytnik sesji Hermesa (tylko do odczytu).")
    ap.add_argument("--porownaj", nargs=2, metavar=("STATE_DB", "SESJA"),
                    help="porównaj projekcję Hermesa z drogą zapasową na jednej sesji")
    ap.add_argument("--zapasowo", nargs=2, metavar=("STATE_DB", "SESJA"), help="wypisz pozycje drogą zapasową")
    ap.add_argument("--schemat", metavar="STATE_DB", help="sprawdź wymagane kolumny")
    a = ap.parse_args(argv)
    if a.porownaj:
        wynik = porownaj(*a.porownaj)
        print(json.dumps(wynik, ensure_ascii=False))
        return 0 if wynik["rowne"] and wynik["state_db_bez_zmian"] else 1
    if a.zapasowo:
        print(json.dumps(czytaj_zapasowo(*a.zapasowo), ensure_ascii=False, indent=1))
        return 0
    if a.schemat:
        brak = sprawdz_schemat(a.schemat)
        print(json.dumps({"brak": brak}))
        return 1 if brak else 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
