"""Jarvo HQ: trasy backendu pluginu dashboardu Hermesa (montowane pod /api/plugins/jarvo-hq/).

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
import shutil
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

_HERE = Path(__file__).resolve().parent


def _load_core():
    # plik obok, pod unikalną nazwą (dashboard ładuje pluginy po ścieżce, bez pakietu)
    spec = importlib.util.spec_from_file_location("jarvo_hq_core", _HERE / "hq_core.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["jarvo_hq_core"] = mod
    spec.loader.exec_module(mod)
    return mod


core = _load_core()
router = APIRouter()


def _start_key_sharing() -> None:
    """Wspólne klucze floty na żywo: klucz dostawcy dodany w dashboardzie (profil „default”) trafia
    do wszystkich agentów bez restartu. Szczegóły i zasady: share_keys.py obok."""
    path = _HERE / "share_keys.py"
    if not path.exists() or os.environ.get("JARVO_SHARE_KEYS", "1") == "0":
        return
    import threading

    spec = importlib.util.spec_from_file_location("jarvo_share_keys", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    threading.Thread(target=mod.watch, args=(core.HOME,), name="jarvo-share-keys", daemon=True).start()


try:
    _start_key_sharing()
except Exception as _exc:  # plugin działa dalej, klucze zsynchronizuje najbliższe wdrożenie
    print(f"jarvo-hq: wspólne klucze nieaktywne: {_exc}", file=sys.stderr)

HOME = core.HOME
FLEET_FILE = _HERE / "fleet.json"
SESSIONS_FILE = core.JARVO_DIR / "state" / "hq-sessions.json"
API_BASE = os.environ.get("JARVO_HQ_API_BASE") or f"http://127.0.0.1:{os.environ.get('API_SERVER_PORT', '8642')}"
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
    st = core.build_state(_fleet(), board, _index_md(), now, activity)
    # wyniki misji: pliki z katalogu misji (najpierw out/), żeby efekt pracy był widać od razu w Centrali
    missions_dir = core.MISSIONS_INDEX.parent
    for m in st.get("missions", []):
        if m.get("done"):
            m["outputs"] = await asyncio.to_thread(
                _cached, f"mout:{m['id']}", 10.0,
                lambda m=m: core.list_outputs([missions_dir / m["id"]], core.Roots(), limit=8))
    return st


@router.get("/fleet")
async def fleet():
    return {"agents": _fleet()}


@router.get("/agent/{name}")
async def agent(name: str):
    a = _agent(name)
    now = time.time()
    board = await asyncio.to_thread(_board, now)
    tasks, events = board["tasks"], board["events"]
    orchestrator = next((x["name"] for x in _fleet() if x.get("kind") == "orchestrator"), "jarvo")
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
    dirs.append(core.JARVO_DIR / "workspaces" / name)
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
    t["brief"] = core.parse_brief(t.get("body"))
    t["expected"] = core.expected_outputs(t["brief"].get("wyjscia"))
    t["outputs"] = await asyncio.to_thread(core.task_outputs, t, ROOTS)
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


# ------------------------------------------------------------------ edytor filmów
# Montaż robi przeglądarka (podgląd, oś czasu), a tu tylko: opis plików, zapis projektu obok filmu
# i eksport jednym przebiegiem ffmpeg w tle (jedno zadanie naraz, postęp z `-progress`).
def _load_editor():
    spec = importlib.util.spec_from_file_location("jarvo_hq_edytor", _HERE / "edytor.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["jarvo_hq_edytor"] = mod
    spec.loader.exec_module(mod)
    return mod


ed = _load_editor()
_edit = sys.modules.setdefault("jarvo_hq_edit_state", type(sys)("jarvo_hq_edit_state"))
if not hasattr(_edit, "jobs"):
    _edit.jobs = {}


def _media_path(raw: str) -> Path | None:
    p = core.safe_path(raw, ROOTS)
    return p if p is not None and ed.media_kind(p) else None


def _media_entry(p: Path) -> dict:
    info = ed.probe(p)
    return {"path": str(p), "name": p.name, "kind": ed.media_kind(p), "size": p.stat().st_size,
            "mtime": p.stat().st_mtime, **{k: info.get(k) for k in ("duration", "w", "h", "fps", "audio", "vcodec")}}


@router.get("/edit/info")
async def edit_info(path: str):
    """Film do edycji: jego parametry, zapisany projekt (jeśli jest) i media z tego samego katalogu."""
    p = _media_path(path)
    if p is None or ed.media_kind(p) != "video":
        raise HTTPException(404, "Film poza katalogami floty albo nie istnieje")
    t = ed.tools()
    if not t["ffprobe"]:
        raise HTTPException(503, "Brak ffprobe w kontenerze: edytor potrzebuje ffmpeg")

    def gather():
        sib = sorted((x for x in p.parent.iterdir() if x.is_file() and ed.media_kind(x) and not x.name.startswith(".")),
                     key=lambda x: -x.stat().st_mtime)[:60]
        media = [_media_entry(x) for x in sib]
        proj = None
        pp = ed.project_path(p)
        mtime = pp.stat().st_mtime if pp.is_file() else 0.0
        if pp.is_file():
            try:
                proj = json.loads(pp.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                proj = None
        subs = sorted((str(x) for x in p.parent.glob("*.srt") if x.is_file()), key=lambda x: x.lower())[:30]
        return {"file": _media_entry(p), "media": media, "project": proj, "ffmpeg": bool(t["ffmpeg"]),
                "stt": bool(t["stt"]), "subs": subs, "project_mtime": mtime}

    return await asyncio.to_thread(gather)


@router.get("/edit/media")
async def edit_media(path: str):
    """Opis jednego pliku (np. muzyka wysłana z dysku przez czat)."""
    p = _media_path(path)
    if p is None:
        raise HTTPException(404, "Plik poza katalogami floty albo to nie wideo, obraz ani dźwięk")
    return await asyncio.to_thread(_media_entry, p)


@router.post("/edit/save")
async def edit_save(request: Request):
    body = await request.json()
    p = _media_path(str(body.get("path") or ""))
    if p is None or ed.media_kind(p) != "video":
        raise HTTPException(404, "Film poza katalogami floty")
    proj = body.get("project")
    raw = json.dumps(proj, ensure_ascii=False, indent=1)
    if not isinstance(proj, dict) or len(raw) > 2_000_000:
        raise HTTPException(400, "Projekt musi być obiektem JSON do 2 MB")
    target = ed.project_path(p)
    # projekt zmieniony w międzyczasie przez kogoś innego (Wideograf: projekt.py) nie jest nadpisywany po cichu
    base = body.get("base")
    if base is not None and not body.get("force") and target.is_file() and target.stat().st_mtime > float(base) + 1e-3:
        raise HTTPException(409, "Projekt zmienił się poza edytorem")
    tmp = target.with_name(f".{target.name}.part")
    tmp.write_text(raw, encoding="utf-8")
    tmp.replace(target)
    return {"ok": True, "path": str(target), "ts": time.time(), "mtime": target.stat().st_mtime}


@router.get("/edit/stamp")
async def edit_stamp(path: str):
    """Kiedy i kto ostatnio zmienił projekt (edytor pyta co kilka sekund: zmiany agenta wczytuje sam)."""
    p = _media_path(path)
    if p is None:
        raise HTTPException(404, "Film poza katalogami floty")
    pp = ed.project_path(p)
    if not pp.is_file():
        return {"mtime": 0.0}
    try:
        who = (json.loads(pp.read_text(encoding="utf-8")).get("zmienil") or {}).get("kto")
    except (OSError, ValueError):
        who = None
    return {"mtime": pp.stat().st_mtime, "kto": who}


@router.get("/edit/srt")
async def edit_srt(path: str):
    """Plik napisów z katalogu floty → lista {start, end, text} (czas źródła)."""
    p = core.safe_path(path, ROOTS)
    if p is None or p.suffix.lower() != ".srt" or p.stat().st_size > 5 * 2**20:
        raise HTTPException(404, "Napisy poza katalogami floty albo to nie plik .srt")
    return {"captions": ed.parse_srt(p.read_text(encoding="utf-8", errors="replace"))}


async def _proc(*args: str, timeout: float = 3600) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        _out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("Przekroczony czas")
    return proc.returncode, err.decode("utf-8", "replace")


async def _run_speech(job: dict, src: Path) -> None:
    """Pauzy (ffmpeg silencedetect, dokładne) + słowa (jarvo-stt, jeśli jest) → <źródło>.mowa.json obok pliku."""
    t = ed.tools()
    tmp = core.JARVO_DIR / "state" / "edytor" / f"mowa-{job['id']}.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        info = await asyncio.to_thread(ed.probe, src)
        code, log = await _proc(t["ffmpeg"], "-nostdin", "-hide_banner", "-i", str(src), "-vn",
                                "-af", f"silencedetect=noise={ed.SILENCE_DB}dB:d={ed.SILENCE_MIN}", "-f", "null", "-", timeout=900)
        if code != 0:
            raise RuntimeError((log.strip().splitlines() or ["ffmpeg: błąd"])[-1][:300])
        silences = ed.parse_silences(log, info.get("duration"))
        job["progress"] = 0.2
        words = []
        if t["stt"]:
            code, err = await _proc(t["stt"], str(src), "--json", str(tmp))
            if code != 0 or not tmp.is_file():
                raise RuntimeError((err.strip().splitlines() or [f"jarvo-stt: kod {code}"])[-1][:300])
            words = json.loads(tmp.read_text(encoding="utf-8")).get("words") or []
        data = ed.speech_data(words, silences, info.get("duration"))
        ed.speech_path(src).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        if data["lines"]:   # napisy także jako .srt: widzi je agent i inne narzędzia
            ed.auto_srt_path(src).write_text(ed.to_srt(data["lines"]), encoding="utf-8")
        job.update(state="done", progress=1.0, speech=data)
    except Exception as exc:
        job.update(state="error", error=str(exc)[:400])
    finally:
        job["ended"] = time.time()
        tmp.unlink(missing_ok=True)


def _read_speech(src: Path) -> dict | None:
    p = ed.speech_path(src)
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
    except (OSError, ValueError):
        return None


@router.get("/edit/speech")
async def edit_speech_get(src: str):
    """Zapisana wcześniej analiza mowy źródła (albo 404, gdy jeszcze jej nie było)."""
    p = _media_path(src)
    data = _read_speech(p) if p else None
    if data is None:
        raise HTTPException(404, "Brak analizy mowy dla tego pliku")
    return data


@router.post("/edit/speech")
async def edit_speech(request: Request):
    """Analiza mowy: pauzy z ffmpeg i słowa z Parakeeta (w tle, wynik przez /edit/job)."""
    import uuid

    body = await request.json()
    src = _media_path(str(body.get("src") or ""))
    if src is None or ed.media_kind(src) not in ("video", "audio"):
        raise HTTPException(404, "Źródło poza katalogami floty albo bez dźwięku")
    jid = uuid.uuid4().hex[:12]
    cached = None if body.get("force") else _read_speech(src)
    if cached is not None:
        job = {"id": jid, "kind": "speech", "state": "done", "progress": 1.0, "speech": cached, "ended": time.time()}
    else:
        if not ed.tools()["ffmpeg"]:
            raise HTTPException(503, "Brak ffmpeg w kontenerze")
        if any(j.get("state") == "running" and j.get("kind") == "speech" for j in _edit.jobs.values()):
            raise HTTPException(409, "Trwa już analiza mowy: poczekaj, aż się skończy")
        job = {"id": jid, "kind": "speech", "state": "running", "progress": 0.0, "started": time.time()}
        job["task"] = asyncio.create_task(_run_speech(job, src))
    _edit.jobs[jid] = job
    return _job_view(job)


# kopia podglądowa (WebM VP9) dla filmów, których kodeka przeglądarka nie odtwarza (np. Chromium bez H.264)
def _proxy_file(src: Path) -> Path:
    return core.JARVO_DIR / "state" / "edytor" / "proxy" / f"{ed.proxy_key(src)}.webm"


async def _run_proxy(job: dict, src: Path, out: Path) -> None:
    part = out.with_name(f".{out.stem}.part.webm")
    try:
        code, err = await _proc(*ed.proxy_command(src, part, ffmpeg=ed.tools()["ffmpeg"]), timeout=3600)
        if code != 0 or not part.is_file():
            raise RuntimeError((err.strip().splitlines() or [f"ffmpeg: kod {code}"])[-1][:300])
        part.replace(out)
        job.update(state="done", progress=1.0)
    except Exception as exc:
        job.update(state="error", error=str(exc)[:400])
    finally:
        job["ended"] = time.time()
        part.unlink(missing_ok=True)


@router.post("/edit/proxy")
async def edit_proxy(request: Request):
    import uuid

    body = await request.json()
    src = _media_path(str(body.get("src") or ""))
    if src is None or ed.media_kind(src) != "video":
        raise HTTPException(404, "Film poza katalogami floty")
    running = next((j for j in _edit.jobs.values()
                    if j.get("kind") == "proxy" and j.get("src") == str(src) and j.get("state") == "running"), None)
    if running:
        return _job_view(running)
    out = _proxy_file(src)
    jid = uuid.uuid4().hex[:12]
    if out.is_file():
        job = {"id": jid, "kind": "proxy", "src": str(src), "state": "done", "progress": 1.0, "ended": time.time()}
    else:
        if not ed.tools()["ffmpeg"]:
            raise HTTPException(503, "Brak ffmpeg w kontenerze")
        out.parent.mkdir(parents=True, exist_ok=True)
        for old in out.parent.glob("*.webm"):     # stare kopie (ponad 7 dni) sprzątamy przy okazji
            if time.time() - old.stat().st_mtime > 7 * 86400:
                old.unlink(missing_ok=True)
        job = {"id": jid, "kind": "proxy", "src": str(src), "state": "running", "progress": 0.0, "started": time.time()}
        job["task"] = asyncio.create_task(_run_proxy(job, src, out))
    _edit.jobs[jid] = job
    return _job_view(job)


@router.get("/edit/proxy-file")
async def edit_proxy_file(src: str):
    p = _media_path(src)
    out = _proxy_file(p) if p else None
    if out is None or not out.is_file():
        raise HTTPException(404, "Kopia podglądowa jeszcze nie gotowa")
    return FileResponse(out, media_type="video/webm", headers={"Cache-Control": "private, max-age=3600"})


def _data_png(url: str, dest: Path) -> None:
    import base64
    head, _, data = str(url).partition(",")
    if head != "data:image/png;base64" or not data:
        raise ed.ProjectError("Napis musi być obrazem PNG (data URL).")
    raw = base64.b64decode(data, validate=True)
    if len(raw) > 12 * 2**20 or not raw.startswith(b"\x89PNG"):
        raise ed.ProjectError("Obraz napisu jest uszkodzony albo za duży.")
    dest.write_bytes(raw)


async def _run_export(job: dict, cmd: list[str], total: float, tmpdir: Path, out: Path) -> None:
    part = out.with_name(f".{out.stem}.part.mp4")
    cmd = cmd[:-1] + [str(part)]
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        job["proc"] = proc
        err_task = asyncio.create_task(proc.stderr.read())
        buf = ""
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            buf += line.decode("utf-8", "replace")
            if buf.endswith("progress=continue\n") or buf.endswith("progress=end\n"):
                sec = ed.parse_progress(buf)
                if sec is not None and total > 0:
                    job["progress"] = min(0.999, sec / total)
                buf = ""
        code = await proc.wait()
        err = (await err_task).decode("utf-8", "replace").strip()
        if job.get("state") == "cancelled":
            return
        if code != 0 or not part.is_file():
            job.update(state="error", error=(err.splitlines() or [f"ffmpeg zakończył się kodem {code}"])[-1][:400])
            return
        part.replace(out)
        job.update(state="done", progress=1.0, out=str(out), size=out.stat().st_size)
    except Exception as exc:  # zadanie ma skończyć się stanem, nie wiszącym „w toku”
        job.update(state="error", error=str(exc)[:400])
    finally:
        job.pop("proc", None)
        job["ended"] = time.time()
        part.unlink(missing_ok=True)
        shutil.rmtree(tmpdir, ignore_errors=True)


@router.post("/edit/export")
async def edit_export(request: Request):
    import uuid

    body = await request.json()
    p = _media_path(str(body.get("path") or ""))
    if p is None or ed.media_kind(p) != "video":
        raise HTTPException(404, "Film poza katalogami floty")
    t = ed.tools()
    if not (t["ffmpeg"] and t["ffprobe"]):
        raise HTTPException(503, "Brak ffmpeg w kontenerze")
    if any(j.get("state") == "running" and j.get("kind", "export") == "export" for j in _edit.jobs.values()):
        raise HTTPException(409, "Trwa inny eksport: poczekaj, aż się skończy")
    try:
        proj = ed.normalize(body.get("project") or {}, _media_path)
        pngs = body.get("texts") or []
        if len(pngs) != len((body.get("project") or {}).get("texts") or []):
            raise ed.ProjectError("Liczba obrazów napisów nie zgadza się z projektem.")
    except ed.ProjectError as exc:
        raise HTTPException(400, str(exc))
    tmpdir = core.JARVO_DIR / "state" / "edytor" / uuid.uuid4().hex[:12]
    tmpdir.mkdir(parents=True, exist_ok=True)
    try:
        files = []   # tylko napisy, które przeszły walidację, w kolejności proj["texts"]
        for k, x in enumerate(proj["texts"]):
            dest = tmpdir / f"napis-{k}.png"
            _data_png(pngs[x["i"]], dest)
            files.append(dest)
        has_audio = {}
        for c in proj["clips"]:
            if c["kind"] == "video" and str(c["src"]) not in has_audio:
                has_audio[str(c["src"])] = (await asyncio.to_thread(ed.probe, c["src"])).get("audio", False)
        out = ed.export_name(p)
        cmd = ed.build_command(proj, has_audio, files, out, ffmpeg=t["ffmpeg"])
    except (ed.ProjectError, ValueError) as exc:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise HTTPException(400, str(exc))
    for jid in [k for k, j in _edit.jobs.items() if j.get("ended") and time.time() - j["ended"] > 3600]:
        _edit.jobs.pop(jid, None)
    jid = uuid.uuid4().hex[:12]
    job = {"id": jid, "state": "running", "progress": 0.0, "started": time.time(), "duration": proj["duration"], "target": str(out)}
    _edit.jobs[jid] = job
    job["task"] = asyncio.create_task(_run_export(job, cmd, proj["duration"], tmpdir, out))
    return _job_view(job)


def _job_view(job: dict) -> dict:
    return {k: v for k, v in job.items() if k not in ("proc", "task")}


@router.get("/edit/job/{jid}")
async def edit_job(jid: str):
    job = _edit.jobs.get(jid)
    if not job:
        raise HTTPException(404, "Nie ma takiego eksportu")
    return _job_view(job)


@router.post("/edit/job/{jid}/cancel")
async def edit_cancel(jid: str):
    job = _edit.jobs.get(jid)
    if not job:
        raise HTTPException(404, "Nie ma takiego eksportu")
    if job.get("state") == "running":
        job["state"] = "cancelled"
        proc = job.get("proc")
        if proc and proc.returncode is None:
            proc.kill()
    return _job_view(job)


# ------------------------------------------------------------------ „Odpal”: podgląd stron na :9120
# Strona zrobiona przez agenta otwiera się w nowej karcie z osobnego portu, pod adresem z losowym
# tokenem (wydaje go zalogowany dashboard albo agent przez scripts/jarvo_link.py; wspólny plik linków). Nagłówek CSP sandbox daje jej nieprzezroczyste
# pochodzenie: skrypty strony działają, ale nie widzą sesji dashboardu i nie wyślą do niego ciasteczek.
PREVIEW_PORT = int(os.environ.get("JARVO_PREVIEW_PORT", "9120"))
# adres, pod którym przeglądarka widzi serwer podglądu (compose: IP z JARVO_BIND_IP); agenci biorą go
# z env albo z pliku state/preview.json, który zapisujemy przy starcie
PREVIEW_URL = os.environ.get("JARVO_PREVIEW_URL") or f"http://localhost:{PREVIEW_PORT}"
PREVIEW_CSP = ("sandbox allow-scripts allow-forms allow-popups allow-modals allow-downloads "
               "allow-popups-to-escape-sandbox")
# stan wspólny dla ponownych importów pluginu (dashboard może przeładować pluginy w tym samym procesie)
_preview = sys.modules.setdefault("jarvo_hq_preview_state", type(sys)("jarvo_hq_preview_state"))
if not hasattr(_preview, "error"):
    _preview.error = None


def _preview_handler():
    import mimetypes
    from http.server import BaseHTTPRequestHandler
    from urllib.parse import unquote, urlsplit

    class Handler(BaseHTTPRequestHandler):
        server_version = "jarvo-preview"
        sys_version = ""

        def log_message(self, *a):  # bez logów każdego żądania
            pass

        def _fail(self, code: int, text: str):
            # send_error wkłada tekst do linii statusu (latin-1): polskie znaki by go wysadziły
            data = f"<!doctype html><meta charset=utf-8><title>{code}</title><p>{text}</p>".encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Security-Policy", "sandbox")
            self.end_headers()
            self.wfile.write(data)

        def _serve(self, body: bool):
            path = unquote(urlsplit(self.path).path)
            token, _, rel = path.lstrip("/").partition("/")
            root = core.link_root(core.LINKS_FILE, token, time.time())
            if root is None:
                return self._fail(404, "Link wygasł albo jest błędny. Kliknij „▶ Odpal” w Jarvo HQ jeszcze raz. "
                                       "/ This link expired or is wrong: click “▶ Run” in Jarvo HQ again.")
            if not rel and not path.endswith("/"):
                self.send_response(301)
                self.send_header("Location", f"/{token}/")
                return self.end_headers()
            p = core.site_file(root, rel, ROOTS)
            if p is None:
                return self._fail(404, "Nie ma takiego pliku.")
            ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json", "image/svg+xml"):
                ctype += "; charset=utf-8"
            data = p.read_bytes() if body else b""
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(p.stat().st_size))
            self.send_header("Content-Security-Policy", PREVIEW_CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")   # moduły JS i fonty z nieprzezroczystego pochodzenia
            self.end_headers()
            if body:
                self.wfile.write(data)

        def do_GET(self):
            self._serve(True)

        def do_HEAD(self):
            self._serve(False)

    return Handler


def _start_preview() -> None:
    if getattr(_preview, "server", None) or PREVIEW_PORT == 0:
        return
    import threading
    from http.server import ThreadingHTTPServer

    try:
        srv = ThreadingHTTPServer(("0.0.0.0", PREVIEW_PORT), _preview_handler())
    except OSError as exc:
        _preview.error = f"port {PREVIEW_PORT} zajęty ({exc.strerror})"
        return
    srv.daemon_threads = True
    _preview.server = srv
    threading.Thread(target=srv.serve_forever, name="jarvo-preview", daemon=True).start()
    try:
        info = core.JARVO_DIR / "state" / "preview.json"
        info.parent.mkdir(parents=True, exist_ok=True)
        info.write_text(json.dumps({"url": PREVIEW_URL, "port": PREVIEW_PORT}), encoding="utf-8")
    except OSError:
        pass


try:
    _start_preview()
except Exception as _exc:
    _preview.error = str(_exc)


@router.post("/site")
async def site(request: Request):
    """Adres podglądu strony dla pliku wynikowego (HTML): {port, path}; przeglądarka składa host."""
    body = await request.json()
    p = core.safe_path(str(body.get("path") or ""), ROOTS)
    if p is None:
        raise HTTPException(404, "Plik poza katalogami floty albo nie istnieje")
    if not getattr(_preview, "server", None):
        raise HTTPException(503, f"Podgląd stron nie działa: {_preview.error or 'serwer nie wystartował'}")
    root = core.site_root(p, ROOTS)
    token = await asyncio.to_thread(core.link_for, core.LINKS_FILE, root, time.time())
    rel = p.relative_to(root).as_posix()
    return {"port": PREVIEW_PORT, "path": f"/{token}/{rel}"}


# ------------------------------------------------------ „Pokaż w folderze”: Eksplorator Windows (WSL)
# Folder otwiera pomocnik na hoście (scripts/updater.py), bo tylko on ma explorer.exe. Dashboard
# zostawia prośbę z samą ścieżką pliku; pomocnik sprawdza ją jeszcze raz po swojej stronie.
REVEAL_REQUEST = core.JARVO_DIR / "state" / "reveal-request"


@router.post("/reveal")
async def reveal(request: Request):
    body = await request.json()
    p = core.safe_path(str(body.get("path") or ""), ROOTS)
    if p is None:
        raise HTTPException(404, "Plik poza katalogami floty albo nie istnieje")
    host = _update_state()
    if not host.get("online") or not (host.get("host") or {}).get("explorer"):
        raise HTTPException(503, "Otwieranie folderu działa w lokalnej instalacji (WSL) z uruchomionym "
                                 "scripts/local-up.sh. Ścieżkę możesz skopiować.")
    REVEAL_REQUEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = REVEAL_REQUEST.with_suffix(".tmp")
    tmp.write_text(json.dumps({"path": str(p), "at": time.time()}), encoding="utf-8")
    tmp.replace(REVEAL_REQUEST)
    return JSONResponse({"ok": True}, status_code=202)


@router.get("/host")
async def host_info():
    """Co umie host: otwieranie folderów (WSL), ścieżka danych po stronie Windows, port podglądu."""
    st = _update_state()
    h = st.get("host") or {}
    return {"explorer": bool(st.get("online") and h.get("explorer")), "data_win": h.get("data_win"),
            "data_host": h.get("data_host"), "preview": bool(getattr(_preview, "server", None)),
            "preview_port": PREVIEW_PORT}


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
    title = f"Jarvo HQ · {name} · {time.strftime('%Y-%m-%d %H:%M:%S')}"
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
            # 500 = maksimum gatewaya: jedna tura z narzędziami to kilkadziesiąt wpisów, a w dymkach
            # pokazujemy tylko wypowiedzi (ostatnie `limit`), więc bierzemy z zapasem
            r = await client.get(f"{base}/api/sessions/{sid}/messages",
                                 params={"limit": 500, "order": "latest"},
                                 headers={"Authorization": f"Bearer {key}"})
        except httpx.HTTPError as exc:
            return JSONResponse({"session_id": sid, "messages": [], "error": f"Gateway niedostępny: {exc}"}, 503)
    if r.status_code == 404:
        return {"session_id": None, "messages": []}
    if r.status_code >= 300:
        return JSONResponse({"session_id": sid, "messages": [], "error": _api_error(r, name)}, 502)
    return {"session_id": sid, "messages": chat_messages(r.json().get("data", []))[-max(1, min(limit, 200)):]}


def chat_messages(raw: list[dict]) -> list[dict]:
    """Historia do dymków czatu: wypowiedzi użytkownika i agenta + skrót użytych narzędzi."""
    out: list[dict] = []
    for m in raw:
        role, content = m.get("role"), m.get("content")
        if m.get("display_kind") == "hidden":
            continue
        if role == "user":
            text = core.user_text(content)
            if text:
                out.append({"role": "user", "text": text, "ts": m.get("timestamp")})
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


_chat_runs: set = set()


@router.post("/chat/{name}/send")
async def chat_send(name: str, request: Request):
    _agent(name)
    body = await request.json()
    attachments = []
    for raw in body.get("attachments") or []:
        p = core.safe_path(str(raw), ROOTS)
        if p is None:
            raise HTTPException(400, f"Załącznik poza katalogami floty albo nie istnieje: {raw}")
        attachments.append(str(p))
    message = core.compose_message(str(body.get("message") or ""), attachments)
    if not message:
        raise HTTPException(400, "Pusta wiadomość")
    # obrazy idą też jako części wiadomości: model z widzeniem je zobaczy, bez widzenia Hermes zamieni je
    # na opis (vision_analyze). Tylko data:image, najwyżej 4 i ~8 MB razem (limit gatewaya to 10 MB).
    images = [str(u) for u in (body.get("images") or [])[:4]
              if isinstance(u, str) and u.startswith(("data:image/png;", "data:image/jpeg;", "data:image/webp;", "data:image/gif;"))]
    if sum(len(u) for u in images) > 8_000_000:
        raise HTTPException(413, "Obrazy są za duże (razem ponad ~6 MB). Wyślij mniej naraz.")
    payload = [{"type": "text", "text": message}, *({"type": "image_url", "image_url": {"url": u}} for u in images)] \
        if images else message
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

    # Odbiór od gatewaya w tle, niezależnie od przeglądarki: zamknięta karta, odświeżenie albo zerwane Wi-Fi nie
    # przerywają pracy agenta (zerwany strumień = przerwany run). Wynik zostaje w sesji i w historii czatu HQ.
    queue: asyncio.Queue = asyncio.Queue()
    listening = {"on": True}

    async def pump():
        try:
            async with client.stream(
                    "POST", f"{base}/api/sessions/{sid}/chat/stream",
                    headers={"Authorization": f"Bearer {key}", "Accept": "text/event-stream"},
                    json={"message": payload}) as r:
                if r.status_code >= 300:
                    await r.aread()
                    err = {"message": _api_error(r, name)}
                    queue.put_nowait(f"event: error\ndata: {json.dumps(err, ensure_ascii=False)}\n\n".encode())
                    return
                async for chunk in r.aiter_raw():
                    if listening["on"]:
                        queue.put_nowait(chunk)
        except httpx.HTTPError as exc:
            if listening["on"]:
                queue.put_nowait(f"event: error\ndata: {json.dumps({'message': f'Gateway: {exc}'})}\n\n".encode())
        finally:
            queue.put_nowait(None)
            await client.aclose()

    task = asyncio.create_task(pump())
    _chat_runs.add(task)                       # silna referencja: zadanie żyje do końca runu
    task.add_done_callback(_chat_runs.discard)

    async def stream():
        try:
            while True:
                item = await queue.get()
                if item is None:
                    return
                yield item
        finally:
            listening["on"] = False            # przeglądarka odeszła: pump dalej opróżnia strumień do końca

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                                      "X-Jarvo-HQ-Session": sid})


@router.post("/upload")
async def upload(request: Request):
    """Plik z czatu HQ (wklejony, przeciągnięty, z 📎) → /opt/data/jarvo/inbox/<data>/<nazwa>."""
    from urllib.parse import unquote

    inbox = core.JARVO_DIR / "inbox"
    target = core.upload_target(inbox, unquote(request.headers.get("X-File-Name", "")), time.time())
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.part")
    size = 0
    try:
        with tmp.open("wb") as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > core.UPLOAD_MAX:
                    raise HTTPException(413, f"Plik większy niż {core.UPLOAD_MAX // 2**20} MB")
                f.write(chunk)
        if not size:
            raise HTTPException(400, "Pusty plik")
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)
    return core.file_entry(target, inbox)


@router.post("/chat/{name}/reset")
async def chat_reset(name: str):
    _agent(name)
    data = _sessions()
    data.pop(name, None)
    _save_sessions(data)
    return {"ok": True}


# ------------------------------------------------------------------------ diagnoza

@router.post("/task/{task_id}/retry")
async def task_retry(task_id: str):
    """Ponowienie karty porzuconej po błędach (hermes kanban unblock → dispatcher uruchomi ją znowu)."""
    if not task_id.replace("_", "").isalnum():
        raise HTTPException(400, "Zły identyfikator karty")
    hermes = os.environ.get("JARVO_HERMES_BIN") or "/opt/hermes/.venv/bin/hermes"
    proc = await asyncio.create_subprocess_exec(hermes, "kanban", "unblock", task_id,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    out, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
    if proc.returncode != 0:
        raise HTTPException(500, f"Nie udało się ponowić karty: {out.decode(errors='replace')[-300:]}")
    return {"ok": True}


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
UPDATE_FILE = core.JARVO_DIR / "state" / "update.json"
UPDATE_REQUEST = core.JARVO_DIR / "state" / "update-request"
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
                                 "na serwerze: sudo systemctl start jarvo-updater.")
    if state.get("state") == "updating":
        raise HTTPException(409, "Aktualizacja już trwa.")
    UPDATE_REQUEST.parent.mkdir(parents=True, exist_ok=True)
    UPDATE_REQUEST.write_text(action, encoding="utf-8")
    return JSONResponse({"ok": True, "action": action}, status_code=202)
