"""TARS HQ: trasy backendu pluginu dashboardu Hermesa (montowane pod /api/plugins/tars-hq/).

Działa w procesie dashboardu (za jego uwierzytelnianiem). Czyta stan z hq_core (tylko odczyt),
a rozmowy z agentami przekazuje do API gatewaya (`/p/<profil>/api/sessions/...`) z kluczem profilu
czytanym po stronie serwera, więc przeglądarka nigdy nie widzi kluczy.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

_HERE = Path(__file__).resolve().parent


def _load_core():
    # plik obok, pod unikalną nazwą (dashboard ładuje pluginy po ścieżce, bez pakietu)
    spec = importlib.util.spec_from_file_location("tars_hq_core", _HERE / "hq_core.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tars_hq_core"] = mod
    spec.loader.exec_module(mod)
    return mod


core = _load_core()
router = APIRouter()


def _start_key_sharing() -> None:
    """Wspólne klucze floty na żywo: klucz dostawcy dodany w dashboardzie (profil „default”) trafia
    do wszystkich agentów bez restartu. Szczegóły i zasady: share_keys.py obok."""
    path = _HERE / "share_keys.py"
    if not path.exists() or os.environ.get("TARS_SHARE_KEYS", "1") == "0":
        return
    import threading

    spec = importlib.util.spec_from_file_location("tars_share_keys", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    threading.Thread(target=mod.watch, args=(core.HOME,), name="tars-share-keys", daemon=True).start()


try:
    _start_key_sharing()
except Exception as _exc:  # plugin działa dalej, klucze zsynchronizuje najbliższe wdrożenie
    print(f"tars-hq: wspólne klucze nieaktywne: {_exc}", file=sys.stderr)

HOME = core.HOME
FLEET_FILE = _HERE / "fleet.json"
SESSIONS_FILE = core.TARS_DIR / "state" / "hq-sessions.json"
API_BASE = os.environ.get("TARS_HQ_API_BASE") or f"http://127.0.0.1:{os.environ.get('API_SERVER_PORT', '8642')}"
ROOTS = core.Roots()
_cache: dict[str, tuple[float, object]] = {}


def _cached(key: str, ttl: float, fn):
    hit = _cache.get(key)
    now = time.monotonic()
    if hit and now - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (now, val)
    return val


def _fleet() -> list[dict]:
    return _cached("fleet", 30, lambda: core.load_fleet(FLEET_FILE))


def _agent(name: str) -> dict:
    a = next((a for a in _fleet() if a["name"] == name), None)
    if not a:
        raise HTTPException(404, f"Nie ma agenta {name!r} we flocie")
    return a


def _state_db(profile: str) -> Path:
    return HOME / "profiles" / profile / "state.db"


def _board(now: float) -> dict:
    # karty misji z INDEX.md czytamy zawsze, także zakończone dawno (postęp misji)
    mission_ids = [c for m in core.parse_missions(_index_md()) for c in m["cards"]]
    return _cached("board", 1.5, lambda: core.read_board(HOME / "kanban.db", now, extra_ids=mission_ids))


def _index_md() -> str:
    try:
        return core.MISSIONS_INDEX.read_text(encoding="utf-8")
    except OSError:
        return ""


def _current_tool(task: dict) -> dict | None:
    """Ostatnie wywołanie narzędzia pracownika karty (z jego sesji w state.db profilu)."""
    worker = task.get("worker") or task.get("assignee")
    if not worker:
        return None
    sid, since = core.worker_session(task)
    _, msgs = core.read_session_messages(_state_db(worker), sid, since, limit=12)
    items = [i for i in core.activity_from_messages(msgs) if i["kind"] == "tool"]
    return items[-1] if items else None


# --------------------------------------------------------------------------- stan

@router.get("/state")
async def state():
    now = time.time()
    board = await asyncio.to_thread(_board, now)
    running = [t for t in board["tasks"] if t.get("status") == "running"
               or (t.get("status") == "review" and t.get("worker") and t["worker"] != t.get("assignee"))]
    activity = {}
    for t in running[:12]:
        activity[t["id"]] = await asyncio.to_thread(
            _cached, f"tool:{t['id']}", 2.0, lambda t=t: _current_tool(t))
    return core.build_state(_fleet(), board, _index_md(), now, activity)


@router.get("/fleet")
async def fleet():
    return {"agents": _fleet()}


@router.get("/agent/{name}")
async def agent(name: str):
    a = _agent(name)
    now = time.time()
    board = await asyncio.to_thread(_board, now)
    tasks, events = board["tasks"], board["events"]
    orchestrator = next((x["name"] for x in _fleet() if x.get("kind") == "orchestrator"), "tars")
    cards = core.agent_cards(name, tasks, orchestrator)
    status = core.derive_status(name, cards, now)

    activity, session_id = [], None
    live = cards["running"][:1]
    if live:
        t = live[0]
        sid, since = core.worker_session(t)
        session_id, msgs = await asyncio.to_thread(core.read_session_messages, _state_db(name), sid, since, 160)
        activity = core.activity_from_messages(msgs)

    dirs = []
    for t in cards["running"] + cards["review"] + cards["blocked"] + cards["done"][:8]:
        if t.get("workspace_path"):
            dirs.append(Path(t["workspace_path"]))
    dirs.append(core.TARS_DIR / "workspaces" / name)
    outputs = await asyncio.to_thread(core.list_outputs, dirs, ROOTS)

    def brief(lst, n=20):
        return [core.card_brief(t) for t in lst[:n]]

    return {
        "agent": {**a, **status},
        "cards": {k: brief(v) for k, v in cards.items()},
        "activity": activity, "session_id": session_id,
        "outputs": outputs,
        "stats": core.agent_stats(name, tasks, events, now),
        "ts": now,
    }


@router.get("/task/{task_id}")
async def task(task_id: str):
    t = await asyncio.to_thread(core.read_task_detail, HOME / "kanban.db", task_id)
    if not t:
        raise HTTPException(404, "Nie ma takiej karty")
    return t


@router.get("/file")
async def file(path: str, download: bool = False):
    p = core.safe_path(path, ROOTS)
    if p is None:
        raise HTTPException(404, "Plik poza katalogami floty albo nie istnieje")
    kind = core.KIND_BY_EXT.get(p.suffix.lower(), "other")
    headers = {
        "X-Content-Type-Options": "nosniff",
        # treści od agentów (HTML, SVG, PDF) oglądamy w izolacji od sesji dashboardu
        "Content-Security-Policy": "sandbox; default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; media-src 'self'",
        "Cache-Control": "private, max-age=30",
    }
    media = None
    if kind in ("text", "html"):
        media = "text/plain; charset=utf-8"          # HTML jako tekst: podgląd kodu, bez wykonywania
    return FileResponse(p, media_type=media, headers=headers,
                        filename=p.name if download else None,
                        content_disposition_type="attachment" if download else "inline")


# --------------------------------------------------------------------------- czat

def _read_env(path: Path) -> dict[str, str]:
    out = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, _, v = line.partition("=")
                out[k.strip().removeprefix("export ").strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def _api_target(name: str) -> tuple[str, str]:
    """(bazowy URL profilu, klucz). Profil domyślny bez prefiksu, nazwany pod /p/<profil>."""
    if name in ("default", ""):
        key = _read_env(HOME / ".env").get("API_SERVER_KEY", "")
        return API_BASE, key
    key = _read_env(HOME / "profiles" / name / ".env").get("API_SERVER_KEY", "")
    return f"{API_BASE}/p/{name}", key


def _sessions() -> dict:
    try:
        return json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_sessions(data: dict) -> None:
    SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SESSIONS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    tmp.replace(SESSIONS_FILE)


async def _ensure_session(client: httpx.AsyncClient, name: str, base: str, key: str) -> str:
    sid = _sessions().get(name)
    headers = {"Authorization": f"Bearer {key}"}
    if sid and sid != "None":
        r = await client.get(f"{base}/api/sessions/{sid}", headers=headers)
        if r.status_code == 200:
            return sid
        if r.status_code != 404:
            # chwilowy błąd gatewaya (restart): nie zakładamy nowej sesji, żeby nie zgubić rozmowy
            raise HTTPException(502, _api_error(r, name))
    # tytuły sesji w Hermesie są unikalne: agent + czas
    title = f"TARS HQ · {name} · {time.strftime('%Y-%m-%d %H:%M:%S')}"
    r = await client.post(f"{base}/api/sessions", headers=headers, json={"title": title})
    if r.status_code >= 300:
        raise HTTPException(502, _api_error(r, name))
    sid = session_id_from(r.json())
    if not sid:
        raise HTTPException(502, "Gateway nie zwrócił identyfikatora sesji")
    data = _sessions()
    data[name] = sid
    _save_sessions(data)
    return sid


def session_id_from(body: dict) -> str | None:
    """Id sesji z odpowiedzi POST /api/sessions ({"object": "hermes.session", "session": {"id": …}})."""
    sess = body.get("session") if isinstance(body.get("session"), dict) else body
    sid = sess.get("id") or sess.get("session_id")
    return str(sid) if sid else None


def _api_error(r: httpx.Response, name: str) -> str:
    if r.status_code == 401:
        return f"Gateway odrzucił klucz profilu {name} (API_SERVER_KEY w jego .env). Uruchom deploy ponownie."
    try:
        detail = r.json().get("error", {})
        detail = detail.get("message") if isinstance(detail, dict) else detail
    except ValueError:
        detail = r.text[:200]
    return f"Gateway ({r.status_code}): {detail}"


@router.get("/chat/{name}/history")
async def chat_history(name: str, limit: int = 60):
    _agent(name)
    sid = _sessions().get(name)
    if not sid:
        return {"session_id": None, "messages": []}
    base, key = _api_target(name)
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(f"{base}/api/sessions/{sid}/messages",
                                 params={"limit": min(limit, 200), "order": "latest"},
                                 headers={"Authorization": f"Bearer {key}"})
        except httpx.HTTPError as exc:
            return JSONResponse({"session_id": sid, "messages": [], "error": f"Gateway niedostępny: {exc}"}, 503)
    if r.status_code == 404:
        return {"session_id": None, "messages": []}
    if r.status_code >= 300:
        return JSONResponse({"session_id": sid, "messages": [], "error": _api_error(r, name)}, 502)
    return {"session_id": sid, "messages": chat_messages(r.json().get("data", []))}


def chat_messages(raw: list[dict]) -> list[dict]:
    """Historia do dymków czatu: wypowiedzi użytkownika i agenta + skrót użytych narzędzi."""
    out: list[dict] = []
    for m in raw:
        role, content = m.get("role"), m.get("content")
        if m.get("display_kind") == "hidden":
            continue
        if role == "user" and isinstance(content, str):
            out.append({"role": "user", "text": content, "ts": m.get("timestamp")})
        elif role == "assistant":
            calls = m.get("tool_calls")
            if isinstance(calls, str):
                try:
                    calls = json.loads(calls)
                except ValueError:
                    calls = []
            tools = [core.tool_label((c.get("function") or {}).get("name"), (c.get("function") or {}).get("arguments"))
                     for c in calls or []]
            text = content if isinstance(content, str) else ""
            if out and out[-1]["role"] == "assistant" and not out[-1]["text"]:
                out[-1]["tools"] += tools
                out[-1]["text"] = text
            elif text or tools:
                out.append({"role": "assistant", "text": text, "tools": tools, "ts": m.get("timestamp")})
    return out


@router.post("/chat/{name}/send")
async def chat_send(name: str, request: Request):
    _agent(name)
    body = await request.json()
    message = str(body.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "Pusta wiadomość")
    base, key = _api_target(name)
    if not key:
        raise HTTPException(503, f"Profil {name} nie ma API_SERVER_KEY. Uruchom deploy (install-fleet go generuje).")

    client = httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=None, write=30, pool=10))
    try:
        sid = await _ensure_session(client, name, base, key)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(503, f"Gateway niedostępny: {exc}") from exc
    except HTTPException:
        await client.aclose()
        raise

    async def stream():
        try:
            async with client.stream(
                    "POST", f"{base}/api/sessions/{sid}/chat/stream",
                    headers={"Authorization": f"Bearer {key}", "Accept": "text/event-stream"},
                    json={"message": message}) as r:
                if r.status_code >= 300:
                    await r.aread()
                    err = {"message": _api_error(r, name)}
                    yield f"event: error\ndata: {json.dumps(err, ensure_ascii=False)}\n\n".encode()
                    return
                async for chunk in r.aiter_raw():
                    yield chunk
        except httpx.HTTPError as exc:
            yield f"event: error\ndata: {json.dumps({'message': f'Gateway: {exc}'})}\n\n".encode()
        finally:
            await client.aclose()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                                      "X-TARS-HQ-Session": sid})


@router.post("/chat/{name}/reset")
async def chat_reset(name: str):
    _agent(name)
    data = _sessions()
    data.pop(name, None)
    _save_sessions(data)
    return {"ok": True}


# ------------------------------------------------------------------------ diagnoza

@router.get("/health")
async def health():
    report = {"fleet": len(_fleet()), "kanban": (HOME / "kanban.db").exists(), "api_base": API_BASE, "agents": {}}
    async with httpx.AsyncClient(timeout=5) as client:
        for a in _fleet():
            base, key = _api_target(a["name"])
            entry = {"key": bool(key)}
            if key:
                try:
                    r = await client.get(f"{base}/v1/capabilities", headers={"Authorization": f"Bearer {key}"})
                    entry["api"] = r.status_code
                except httpx.HTTPError as exc:
                    entry["api"] = f"błąd: {exc.__class__.__name__}"
            report["agents"][a["name"]] = entry
    return report


# ----------------------------------------------------------------------------- aktualizacje
# Stan pisze pomocnik aktualizacji na hoście (scripts/updater.py). Dashboard może tylko poprosić
# o sprawdzenie albo aktualizację tej samej gałęzi (plik update-request); poleceń nie wykonuje.
UPDATE_FILE = core.TARS_DIR / "state" / "update.json"
UPDATE_REQUEST = core.TARS_DIR / "state" / "update-request"
UPDATER_STALE = 5 * 60  # pomocnik sprawdza co minutę; dłuższa cisza = nie działa


def _update_state() -> dict:
    try:
        state = json.loads(UPDATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"online": False, "state": "unknown", "behind": 0}
    last = max(state.get("checked_at") or 0, state.get("started_at") or 0, state.get("finished_at") or 0)
    state["online"] = state.get("state") == "updating" or time.time() - last < UPDATER_STALE
    state["pending"] = UPDATE_REQUEST.exists()
    return state


@router.get("/update")
async def update_status():
    return _update_state()


@router.post("/update")
async def update_request(request: Request):
    body = await request.json()
    action = body.get("action")
    if action not in ("check", "update"):
        raise HTTPException(400, "action: check albo update")
    state = _update_state()
    if not state.get("online"):
        raise HTTPException(503, "Pomocnik aktualizacji nie działa. Lokalnie: bash scripts/local-up.sh, "
                                 "na serwerze: sudo systemctl start tars-updater.")
    if state.get("state") == "updating":
        raise HTTPException(409, "Aktualizacja już trwa.")
    UPDATE_REQUEST.parent.mkdir(parents=True, exist_ok=True)
    UPDATE_REQUEST.write_text(action, encoding="utf-8")
    return JSONResponse({"ok": True, "action": action}, status_code=202)
