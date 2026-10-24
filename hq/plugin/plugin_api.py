"""Jarvo HQ: trasy backendu pluginu dashboardu Hermesa (montowane pod /api/plugins/jarvo-hq/).

Działa w procesie dashboardu (za jego uwierzytelnianiem). Czyta stan z hq_core (tylko odczyt),
a rozmowy z agentami przekazuje do API gatewaya (`/p/<profil>/api/sessions/...`) z kluczem profilu
czytanym po stronie serwera, więc przeglądarka nigdy nie widzi kluczy.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import math
import os
import re
import sys
import shutil
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

_HERE = Path(__file__).resolve().parent


def _load(name: str, file: str):
    # plik obok, pod unikalną nazwą (dashboard ładuje pluginy po ścieżce, bez pakietu)
    spec = importlib.util.spec_from_file_location(name, _HERE / file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


core = _load("jarvo_hq_core", "hq_core.py")
# ochrona zapisu (CSRF): każda trasa POST tego routera dostaje ochrona.wymagaj_zapisu (ochrona.Trasa);
# ten sam plik jedzie do wtyczki jarvo-wiedza (scripts/build.py)
ochrona = _load("jarvo_hq_ochrona", "ochrona.py")
router = APIRouter(route_class=ochrona.Trasa)


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
    # karty misji z INDEX.md czytamy zawsze, także zakończone dawno (postęp misji); TTL krótszy niż odpytywanie
    # Centrali (3 s), ale wspólny z panelem agenta (2,5 s), więc oba widoki naraz czytają tablicę raz
    def read():
        mission_ids = [c for m in core.parse_missions(_index_md()) for c in m["cards"]]
        return core.read_board(HOME / "kanban.db", now, extra_ids=mission_ids)
    return _cached("board", 2.5, read)


def _index_md() -> str:
    def read():
        try:
            return core.MISSIONS_INDEX.read_text(encoding="utf-8")
        except OSError:
            return ""
    return _cached("index", 2.0, read)


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
    tasks = board["tasks"]
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
    # panel odpytuje co 2,5 s, a przejście katalogów roboczych to ~0,1 s: wyniki agenta odświeżane co 10 s (jak misji)
    outputs = await asyncio.to_thread(_cached, f"aout:{name}", 10.0, lambda: core.list_outputs(dirs, ROOTS))

    def brief(lst, n=20):
        return [core.card_brief(t) for t in lst[:n]]

    return {
        "agent": {**a, **status},
        "cards": {k: brief(v) for k, v in cards.items()},
        "activity": activity, "session_id": session_id,
        "outputs": outputs,
        "stats": core.agent_stats(name, board, now),
        "evals": await asyncio.to_thread(_cached, f"evals:{name}", 30.0, lambda: core.eval_trend(name)),
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
ed = _load("jarvo_hq_edytor", "edytor.py")
anim = _load("jarvo_hq_animacja", "animacja.py")
_edit = sys.modules.setdefault("jarvo_hq_edit_state", type(sys)("jarvo_hq_edit_state"))
if not hasattr(_edit, "jobs"):
    _edit.jobs = {}


def _media_path(raw: str) -> Path | None:
    p = core.safe_path(raw, ROOTS)
    return p if p is not None and ed.media_kind(p) else None


_probe_cache: dict[tuple, dict] = {}


def _probe(p: Path) -> dict:
    """ffprobe raz na wersję pliku (ścieżka, mtime, rozmiar): edytor przy otwarciu i przeładowaniu bada do 60 mediów."""
    st = p.stat()
    key = (str(p), st.st_mtime_ns, st.st_size)
    if key not in _probe_cache:
        if len(_probe_cache) > 512:
            _probe_cache.clear()
        _probe_cache[key] = ed.probe(p)
    return _probe_cache[key]


_tlo_cache: dict[tuple, float | None] = {}


async def _tlo(src: Path, a: float = 0.0, d: float = ed.SZUM_MAX) -> float | None:
    """Tło nagrania (dB) pod czysty głos: pomiar raz na wersję pliku i zakres (edytor.szum_cmd)."""
    st = src.stat()
    key = (str(src), st.st_mtime_ns, st.st_size, round(a), round(d))
    if key not in _tlo_cache:
        if len(_tlo_cache) > 256:
            _tlo_cache.clear()
        code, log = await _proc(*ed.szum_cmd(src, ed.tools()["ffmpeg"] or "ffmpeg", a, d), timeout=300)
        _tlo_cache[key] = ed.szum_z_logu(log) if code == 0 else None
    return _tlo_cache[key]


def _media_entry(p: Path) -> dict:
    info = _probe(p)
    return {"path": str(p), "name": p.name, "kind": ed.media_kind(p), "size": p.stat().st_size,
            "mtime": p.stat().st_mtime, **{k: info.get(k) for k in ("duration", "w", "h", "fps", "audio", "vcodec", "hdr")}}


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


@router.get("/edit/maska")
async def edit_maska(path: str):
    """Sylwetki osoby do typografii „za osobą” (Wideograf: maska.py): indeks klatek i katalog. Edytor sam porównuje
    klucz osi (maskaKlucz) z bieżącym projektem, więc po zmianie klipów nie użyje nieaktualnych sylwetek."""
    p = _media_path(path)
    if p is None or ed.media_kind(p) != "video":
        raise HTTPException(404, "Film poza katalogami floty")

    def read():
        try:
            idx = json.loads((ed.maska_dir(p) / "indeks.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(idx, dict):
            return {}
        return {"dir": str(ed.maska_dir(p)), "klucz": str(idx.get("klucz") or ""), "fps": idx.get("fps"),
                "klatki": [k for k in idx.get("klatki") or [] if isinstance(k, int)][:100000]}

    return await asyncio.to_thread(read)


@router.get("/edit/media")
async def edit_media(path: str):
    """Opis jednego pliku (np. muzyka wysłana z dysku przez czat)."""
    p = _media_path(path)
    if p is None:
        raise HTTPException(404, "Plik poza katalogami floty albo to nie wideo, obraz ani dźwięk")
    return await asyncio.to_thread(_media_entry, p)


# ------------------------------------------------------------------ edytor: menu Audio
# Biblioteka CC0 obok wtyczki (hqbuild kopiuje hq/web/dzwieki), w repo hq/web/dzwieki. Każde dodanie zapisuje plik
# obok filmu (dzwieki/, lektor/), więc eksport i Wideograf (projekt.py) widzą zwykłe pliki z katalogów floty.
DZWIEKI = next((d for d in (_HERE / "dzwieki", _HERE.parent / "web" / "dzwieki") if (d / "katalog.json").is_file()), None)
NAGRANIE_MAX = 60 * 2**20


def _film(raw: str) -> Path:
    p = _media_path(raw)
    if p is None or ed.media_kind(p) != "video":
        raise HTTPException(404, "Film poza katalogami floty")
    return p


def _wideo_skrypt(name: str) -> Path | None:
    """Skrypt Wideografa (lektor: film.py): z zainstalowanego profilu, a w repo z profiles/jarvo-wideo."""
    for d in (core.HOME / "profiles" / "jarvo-wideo" / "scripts", _HERE.parents[1] / "profiles" / "jarvo-wideo" / "scripts"):
        if (d / name).is_file():
            return d / name
    return None


@router.get("/edit/dzwieki")
async def edit_dzwieki():
    """Katalog biblioteki dźwięków: kategorie, efekty i podkłady (CC0)."""
    return await asyncio.to_thread(ed.dzwieki_katalog, DZWIEKI)


@router.get("/edit/dzwiek-plik")
async def edit_dzwiek_plik(id: str):
    """Plik z biblioteki do odsłuchu przed dodaniem."""
    hit = ed.dzwiek_plik(DZWIEKI, id)
    if not hit:
        raise HTTPException(404, "Nie ma takiego dźwięku w bibliotece")
    return FileResponse(hit[1], media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=86400"})


@router.post("/edit/dzwiek")
async def edit_dzwiek(request: Request):
    """Dźwięk z biblioteki → kopia w <katalog filmu>/dzwieki/ → opis pliku do dodania na oś."""
    body = await request.json()
    film = _film(str(body.get("path") or ""))
    try:
        dest = await asyncio.to_thread(ed.dzwiek_do_filmu, DZWIEKI, str(body.get("id") or ""), film)
    except ed.ProjectError as exc:
        raise HTTPException(404, str(exc))
    return await asyncio.to_thread(_media_entry, dest)


@router.get("/edit/muzyka")
async def edit_muzyka():
    """Muzyka ze skarbca (knowledge/wideo/muzyka i knowledge/brands/<marka>/muzyka): ta sama, którą bierze film.py."""
    def zbierz():
        kn = core.JARVO_DIR / "knowledge"
        dirs = [("", kn / "wideo" / "muzyka")] + [(b.name, b / "muzyka") for b in sorted((kn / "brands").glob("*")) if b.is_dir()]
        out = []
        for marka, d in dirs:
            if not d.is_dir():
                continue
            for f in sorted(d.rglob("*"))[:200]:
                if f.is_file() and ed.media_kind(f) == "audio" and core.safe_path(str(f), ROOTS):
                    out.append({**_media_entry(f), "marka": marka})
                if len(out) >= 60:
                    return out
        return out
    return {"muzyka": await asyncio.to_thread(zbierz)}


@router.post("/edit/wyodrebnij")
async def edit_wyodrebnij(request: Request):
    """Dźwięk innego filmu (albo klipu z osi) jako osobny plik audio w <katalog filmu>/dzwieki/."""
    body = await request.json()
    film = _film(str(body.get("path") or ""))
    src = _media_path(str(body.get("src") or ""))
    if src is None or ed.media_kind(src) != "video":
        raise HTTPException(404, "Źródło poza katalogami floty albo to nie film")
    info = await asyncio.to_thread(_probe, src)
    if not info.get("audio"):
        raise HTTPException(400, "Ten film nie ma dźwięku")
    t = ed.tools()
    if not t["ffmpeg"]:
        raise HTTPException(503, "Brak ffmpeg w kontenerze")
    dest = ed.wyodrebnij_cel(film, src)
    if not dest.is_file() or dest.stat().st_mtime < src.stat().st_mtime:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(f".{dest.stem}.part{dest.suffix}")
        try:
            code, err = await _proc(*ed.wyodrebnij_cmd(src, tmp, info.get("acodec"), t["ffmpeg"]), timeout=900)
            if code != 0:
                raise HTTPException(500, (err.strip().splitlines() or ["ffmpeg: błąd"])[-1][:300])
            tmp.replace(dest)
        finally:
            tmp.unlink(missing_ok=True)
    return await asyncio.to_thread(_media_entry, dest)


@router.post("/edit/kolor-auto")
async def edit_kolor_auto(request: Request):
    """„Auto” koloru klipu (za video-use auto_grade): signalstats na ~12 klatkach klipu → delikatne suwaki
    jasności, kontrastu i nasycenia (edytor.kolor_z_pomiaru, to samo co projekt.py kolor --auto)."""
    body = await request.json()
    src = _media_path(str(body.get("src") or ""))
    if src is None or ed.media_kind(src) not in ("video", "image"):
        raise HTTPException(404, "Klip poza katalogami floty albo to nie obraz")
    t = ed.tools()
    if not t["ffmpeg"]:
        raise HTTPException(503, "Brak ffmpeg w kontenerze")
    a = ed._num(body.get("in"), 0, ed.MAX_DURATION, 0)
    b = ed._num(body.get("out"), a, ed.MAX_DURATION, a + 3)
    code, log = await _proc(*ed.kolor_pomiar_cmd(src, a, b, t["ffmpeg"], sdr=_probe(src).get("sdr", "")), timeout=180)
    wynik = ed.kolor_z_pomiaru(log) if code == 0 else None
    if not wynik:
        raise HTTPException(500, "Nie udało się zmierzyć klatek klipu")
    return wynik


def _glos_body(body: dict) -> tuple[Path, float, float]:
    src = _media_path(str(body.get("src") or ""))
    if src is None or ed.media_kind(src) not in ("video", "audio"):
        raise HTTPException(404, "Plik poza katalogami floty albo bez dźwięku")
    if not ed.tools()["ffmpeg"]:
        raise HTTPException(503, "Brak ffmpeg w kontenerze")
    a = ed._num(body.get("in"), 0, ed.MAX_DURATION, 0)
    return src, a, ed._num(body.get("out"), a, ed.MAX_DURATION, a + 3)


@router.post("/edit/glos-tlo")
async def edit_glos_tlo(request: Request):
    """Tło nagrania klipu (dB) i poziom czystego głosu dobrany do niego („Auto”, edytor.glos_auto)."""
    src, a, b = _glos_body(await request.json())
    tlo = await _tlo(src, max(0.0, a - 30), b - max(0.0, a - 30) + 30)
    return {"tlo": tlo, "poziom": ed.glos_auto(tlo)}


@router.post("/edit/glos-probka")
async def edit_glos_probka(request: Request):
    """Odsłuch czystego głosu przed eksportem: 8 s klipu od wskazanej chwili źródła po łańcuchu poziomu (MP3)."""
    import uuid

    body = await request.json()
    src, a, b = _glos_body(body)
    poziom = ed.glos_norm(body.get("voice"))
    if not poziom:
        raise HTTPException(400, "Nieznany poziom czystego głosu")
    od = min(max(a, ed._num(body.get("od"), 0, ed.MAX_DURATION, a)), max(a, b - 1))
    tlo = await _tlo(src, max(0.0, a - 30), b - max(0.0, a - 30) + 30)
    tmp = core.JARVO_DIR / "state" / "edytor" / f"glos-{uuid.uuid4().hex[:12]}.mp3"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        code, log = await _proc(*ed.glos_probka_cmd(src, od, min(8.0, b - od), poziom, tlo, tmp, ed.tools()["ffmpeg"]), timeout=120)
        if code != 0 or not tmp.is_file():
            raise HTTPException(500, "Nie udało się przygotować odsłuchu: " + log.strip()[-200:])
        data = tmp.read_bytes()
    finally:
        tmp.unlink(missing_ok=True)
    return Response(content=data, media_type="audio/mpeg", headers={"Cache-Control": "no-store",
                                                                    "X-Jarvo-Tlo": "" if tlo is None else str(tlo)})


@router.post("/edit/lektor")
async def edit_lektor(request: Request):
    """Tekst na mowę: ten sam lektor co u Wideografa (film.py lektor: lokalny Matcha/Paradee albo Edge TTS, cache)
    → <katalog filmu>/lektor/."""
    body = await request.json()
    film = _film(str(body.get("path") or ""))
    tekst = " ".join(str(body.get("text") or "").split())
    if not tekst:
        raise HTTPException(400, "Wpisz tekst lektora")
    if len(tekst) > ed.LEKTOR_MAX:
        raise HTTPException(400, f"Tekst dłuższy niż {ed.LEKTOR_MAX} znaków")
    glos = str(body.get("glos") or ed.GLOSY[0])
    if glos not in ed.GLOSY:
        raise HTTPException(400, "Nieznany głos")
    tempo = ed.tempo_tts(body.get("tempo"))
    skrypt = _wideo_skrypt("film.py")
    if skrypt is None:
        raise HTTPException(503, "Brak skryptu lektora (profil Wideografa nie jest zainstalowany)")
    dest = ed.lektor_cel(film, tekst, glos, tempo)
    if not dest.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            # lokalny lektor czeka jeszcze na Parakeeta (czasy słów; przy pierwszym użyciu pobiera model)
            code, err = await _proc(sys.executable, str(skrypt), "lektor", tekst, "-o", str(dest), "--glos", glos,
                                    "--tempo", tempo, timeout=900 if glos in ed.GLOSY_LOKALNE else 300)
        except RuntimeError as exc:
            raise HTTPException(504, f"Lektor: {exc}")
        if code != 0 or not dest.is_file():
            raise HTTPException(502, (err.strip().splitlines() or ["Lektor nie odpowiedział"])[-1][:300])
    return await asyncio.to_thread(_media_entry, dest)


@router.post("/edit/nagranie")
async def edit_nagranie(request: Request):
    """Nagranie z mikrofonu (MediaRecorder: webm/opus albo mp4) → AAC w <katalog filmu>/lektor/nagranie-<czas>.m4a."""
    from urllib.parse import unquote

    film = _film(unquote(request.headers.get("X-Film-Path", "")))
    t = ed.tools()
    if not t["ffmpeg"]:
        raise HTTPException(503, "Brak ffmpeg w kontenerze")
    dest = ed.nagranie_cel(film, time.time())
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = dest.with_name(f".{dest.stem}.surowe")
    size = 0
    try:
        with raw.open("wb") as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > NAGRANIE_MAX:
                    raise HTTPException(413, f"Nagranie większe niż {NAGRANIE_MAX // 2**20} MB")
                f.write(chunk)
        if not size:
            raise HTTPException(400, "Puste nagranie")
        code, err = await _proc(*ed.nagranie_cmd(raw, dest, t["ffmpeg"]), timeout=300)
        if code != 0 or not dest.is_file():
            dest.unlink(missing_ok=True)
            raise HTTPException(400, "Nie udało się odczytać nagrania: " + (err.strip().splitlines() or [""])[-1][:200])
    finally:
        raw.unlink(missing_ok=True)
    return await asyncio.to_thread(_media_entry, dest)


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


_stamp_cache: dict[str, tuple[float, str | None]] = {}


@router.get("/edit/stamp")
async def edit_stamp(path: str):
    """Kiedy i kto ostatnio zmienił projekt (edytor pyta co kilka sekund: zmiany agenta wczytuje sam)."""
    p = _media_path(path)
    if p is None:
        raise HTTPException(404, "Film poza katalogami floty")
    pp = ed.project_path(p)
    if not pp.is_file():
        return {"mtime": 0.0}
    mtime = pp.stat().st_mtime
    hit = _stamp_cache.get(str(pp))
    if hit and hit[0] == mtime:                  # projekt (do 2 MB) parsowany tylko po zmianie, nie co 3 s
        return {"mtime": mtime, "kto": hit[1]}
    try:
        who = (json.loads(pp.read_text(encoding="utf-8")).get("zmienil") or {}).get("kto")
    except (OSError, ValueError):
        who = None
    if len(_stamp_cache) > 256:
        _stamp_cache.clear()
    _stamp_cache[str(pp)] = (mtime, who)
    return {"mtime": mtime, "kto": who}


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
# i dla filmów HDR z telefonu: podgląd po przeliczeniu kolorów, jak eksport (przeglądarka pokazałaby oryginał HDR)
def _proxy_file(src: Path) -> Path:
    return core.JARVO_DIR / "state" / "edytor" / "proxy" / f"{ed.proxy_key(src, _probe(src).get('sdr', ''))}.webm"


async def _run_proxy(job: dict, src: Path, out: Path) -> None:
    part = out.with_name(f".{out.stem}.part.webm")
    try:
        code, err = await _proc(*ed.proxy_command(src, part, ffmpeg=ed.tools()["ffmpeg"], sdr=_probe(src).get("sdr", "")),
                                timeout=3600)
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


def _data_klatka(url: str, base: Path) -> Path:
    """Klatka typografii z przeglądarki: WebP (edytor, lżejszy) albo PNG; rozszerzenie z zawartości, nie z nagłówka."""
    import base64
    head, _, data = str(url).partition(",")
    if head not in ("data:image/png;base64", "data:image/webp;base64") or not data:
        raise ed.ProjectError("Klatka typografii musi być obrazem PNG albo WebP (data URL).")
    raw = base64.b64decode(data, validate=True)
    ext = ".png" if raw.startswith(b"\x89PNG") else ".webp" if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP" else None
    if ext is None or len(raw) > 12 * 2**20:
        raise ed.ProjectError("Klatka typografii jest uszkodzona albo za duża.")
    dest = base.with_suffix(ext)
    dest.write_bytes(raw)
    return dest


def _typo_warstwy(raw, proj: dict, tmpdir: Path) -> dict:
    """Klatki typografii z przeglądarki ({"tyl"|"przod": [[od, do, WebP/PNG albo null], …], "pusty": przezroczysta
    klatka}, numery klatek) → listy concat. Odcinki muszą iść po kolei i nie wychodzić poza film. Wszystkie klatki
    i pusta w jednym formacie: demuxer concat dekoduje całą listę kodekiem pierwszego pliku (PNG wśród WebP = błąd
    dekodera i warstwa znika z filmu)."""
    if not isinstance(raw, dict):
        return {}
    fps = proj["canvas"]["fps"]
    limit = int(math.ceil(proj["duration"] * fps)) + 2
    listy = {}
    for warstwa in ("tyl", "przod"):
        segs = raw.get(warstwa)
        if not segs:
            continue
        if not isinstance(segs, list) or len(segs) > 20000:
            raise ed.ProjectError("Typografia: za dużo odcinków albo zły format.")
        lista, prev = [], 0
        for k, seg in enumerate(segs):
            if not isinstance(seg, list) or len(seg) != 3:
                raise ed.ProjectError("Typografia: zły odcinek.")
            a, b = int(seg[0]), int(seg[1])
            if a != prev or b <= a or b > limit:
                raise ed.ProjectError("Typografia: odcinki nie idą po kolei.")
            prev = b
            dest = _data_klatka(seg[2], tmpdir / f"typo-{warstwa}-{k:05d}") if seg[2] else None
            lista.append(((b - a) / fps, dest))
        listy[warstwa] = lista
    if not listy:
        return {}
    cv = proj["canvas"]
    blank = (_data_klatka(raw["pusty"], tmpdir / "typo-pusty") if raw.get("pusty")
             else ed.blank_png(tmpdir / "typo-pusty.png", cv["w"], cv["h"]))
    if {d.suffix for lista in listy.values() for _t, d in lista if d} - {blank.suffix}:
        raise ed.ProjectError("Typografia: klatki w różnych formatach (PNG i WebP). Odśwież edytor i eksportuj jeszcze raz.")
    out = {}
    for warstwa, lista in listy.items():
        d = ed.typo_concat(lista, blank, tmpdir / f"typo-{warstwa}.ffconcat")
        if d:
            out[warstwa] = d
    return out


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
        kpngs = body.get("karaoke") or {}
        raw_texts = (body.get("project") or {}).get("texts") or []
        for x in proj["texts"]:
            if x.get("kara") and len(kpngs.get(str(x["i"])) or []) != len(raw_texts[x["i"]].get("words") or []):
                raise ed.ProjectError("Napisy karaoke: liczba obrazów słów nie zgadza się z projektem.")
    except ed.ProjectError as exc:
        raise HTTPException(400, str(exc))
    tmpdir = core.JARVO_DIR / "state" / "edytor" / uuid.uuid4().hex[:12]
    tmpdir.mkdir(parents=True, exist_ok=True)
    try:
        files = []   # tylko napisy, które przeszły walidację, w kolejności proj["texts"]
        kara: dict[int, list] = {}
        for k, x in enumerate(proj["texts"]):
            dest = tmpdir / f"napis-{k}.png"
            _data_png(pngs[x["i"]], dest)
            files.append(dest)
            if x.get("kara"):     # karaoke: obraz na każde słowo (aktywne w kolorze), sklejone w jedną warstwę
                kara[x["i"]] = []
                for j, data in enumerate(kpngs[str(x["i"])]):
                    kd = tmpdir / f"napis-{k}-slowo-{j}.png"
                    _data_png(data, kd)
                    kara[x["i"]].append(kd)
        layer = None
        if kara:
            cv = proj["canvas"]
            layer = ed.karaoke_concat(proj, kara, ed.blank_png(tmpdir / "pusty.png", cv["w"], cv["h"]), tmpdir / "karaoke.ffconcat")
        typo = _typo_warstwy(body.get("typo"), proj, tmpdir)
        has_audio, sdr = {}, {}
        for c in proj["clips"]:
            if c["kind"] == "video" and str(c["src"]) not in has_audio:
                info = await asyncio.to_thread(ed.probe, c["src"])
                has_audio[str(c["src"])], sdr[str(c["src"])] = info.get("audio", False), info.get("sdr", "")
        szum = {s: await _tlo(Path(s), a, d) for s, (a, d) in ed.szum_zakresy(proj).items()}   # czysty głos
        out = ed.export_name(p)
        maska = ed.maska_concat(p, body.get("project") or {}, proj, tmpdir) if typo.get("tyl") else None
        cmd = ed.build_command(proj, has_audio, files, out, ffmpeg=t["ffmpeg"], karaoke=layer, typo=typo, maska=maska,
                               sdr=sdr, szum=szum)
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

        def _static(self, data: bytes, ctype: str, body: bool, csp: str | None = None):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            if csp:
                self.send_header("Content-Security-Policy", csp)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if body:
                self.wfile.write(data)

        def _serve(self, body: bool):
            parts = urlsplit(self.path)
            path = unquote(parts.path)
            # mostek podglądu animacji (HQ ↔ strona przez postMessage) i wspólne biblioteki animacji (three, gsap)
            if path == "/_jarvo/most.js":
                return self._static(anim.MOST_JS.encode(), "text/javascript; charset=utf-8", body)
            if path == "/_jarvo/flota.html":                # Centrala → Jak działa usługa (figura floty)
                try:
                    return self._static(flota_strona(), "text/html; charset=utf-8", body, csp=PREVIEW_CSP)
                except Exception as exc:  # brak iso.py albo zły fleet.json: opis zamiast zerwanego połączenia
                    return self._fail(503, f"Figura floty niedostępna: {exc}")
            if path.startswith("/_lib/"):
                lib = core.lib_file(path[len("/_lib/"):])
                if lib is None:
                    return self._fail(404, "Nie ma takiej biblioteki.")
                ctype = mimetypes.guess_type(lib.name)[0] or "application/octet-stream"
                if lib.suffix in (".js", ".mjs"):
                    ctype = "text/javascript; charset=utf-8"
                return self._static(lib.read_bytes(), ctype, body)
            token, _, rel = path.lstrip("/").partition("/")
            root = core.link_root(core.LINKS_FILE, token, time.time())
            if root is None or root == core.SCREEN_ROOT:
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
            data = p.read_bytes()
            if "jarvo-podglad=1" in parts.query and p.suffix.lower() in (".html", ".htm"):
                data = anim.wstrzyknij_most(data)          # tylko podgląd animacji w HQ, nie „▶ Odpal”
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
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
        info.write_text(json.dumps({"url": PREVIEW_URL, "port": PREVIEW_PORT,
                                    "android_url": os.environ.get("JARVO_ANDROID_SCREEN_URL")}), encoding="utf-8")
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


# ------------------------------------------- animacja HTML: podgląd na żywo i parametry (animacja.py)
@router.get("/anim/check")
async def anim_check(path: str):
    """Czy plik HTML to animacja z kontraktem (przycisk „◐ Animacja” przy plikach z linków w czacie)."""
    p = core.safe_path(path, ROOTS)
    return {"anim": bool(p) and await asyncio.to_thread(anim.to_animacja, p)}


@router.post("/anim/info")
async def anim_info(request: Request):
    """Link podglądu (mostek przez postMessage, bez pętli podglądu strony), parametry ze schematu i stan pomiaru.
    POST, bo wydaje token podglądu (zapis w state/preview-links.json): trasy GET niczego nie zapisują (ochrona.py)."""
    body = await request.json()
    p = core.safe_path(str(body.get("path") or ""), ROOTS)
    if p is None or not anim.to_animacja(p):
        raise HTTPException(404, "To nie animacja z kontraktem __seek (kontrakt-html.md) albo plik poza katalogami floty")
    if not getattr(_preview, "server", None):
        raise HTTPException(503, f"Podgląd stron nie działa: {_preview.error or 'serwer nie wystartował'}")
    root = p.parent
    token = await asyncio.to_thread(core.link_for, core.LINKS_FILE, root, time.time())
    return {"plik": str(p), "podglad": {"port": PREVIEW_PORT, "path": f"/{token}/{p.name}?render=1&jarvo-podglad=1"},
            "parametry": await asyncio.to_thread(anim.wczytaj, p), "pomiar": await asyncio.to_thread(anim.pomiar, p)}


@router.post("/anim/params")
async def anim_params(request: Request):
    """Nowe wartości parametrów → parametry.json obok strony (tylko pola ze schematu, typy sprawdzone)."""
    body = await request.json()
    p = core.safe_path(str(body.get("path") or ""), ROOTS)
    if p is None or not (p.parent / anim.PARAMETRY).is_file():
        raise HTTPException(404, "Brak parametry.json obok animacji")
    try:
        pola = await asyncio.to_thread(anim.zapisz, p, body.get("wartosci"))
    except anim.ParamError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "pola": pola, "pomiar": await asyncio.to_thread(anim.pomiar, p)}


# ------------------------------------------- ekran telefonu testowego (Redroid + ws-scrcpy) na :9122
# ws-scrcpy nie ma logowania, więc siedzi tylko w sieci floty; tu jest jedyne wejście do niego. Link z tokenem
# (wspólny plik linków, ważny 12 h) wydaje zalogowany dashboard albo agent (scripts/jarvo_link.py --android).
# Wejście na /<token>/ zamienia token na ciasteczko HttpOnly i przekierowuje na /, bo ws-scrcpy ładuje pliki
# i otwiera WebSockety od korzenia. Każde żądanie bez ważnego ciasteczka dostaje 403. Zwykłe żądania idą
# z `Connection: close`, więc każde kolejne przechodzi kontrolę od nowa; WebSocket po kontroli to czysty strumień.
# Ciasteczka przeglądarki (także dashboardu z :9119, bo ciasteczka nie znają portów) nie idą dalej do ws-scrcpy.
SCREEN_PORT = int(os.environ.get("JARVO_ANDROID_SCREEN_PORT", "9122"))
SCREEN_UPSTREAM = os.environ.get("JARVO_ANDROID_SCREEN_UPSTREAM", "jarvo-android-ekran:8000")
SCREEN_ROOT = core.SCREEN_ROOT
SCREEN_COOKIE = f"jarvo_ekran_{SCREEN_PORT}"
_screen = sys.modules.setdefault("jarvo_hq_screen_state", type(sys)("jarvo_hq_screen_state"))
if not hasattr(_screen, "error"):
    _screen.error = None


def _screen_upstream() -> tuple[str, int]:
    host, _, port = SCREEN_UPSTREAM.rpartition(":")
    return host or SCREEN_UPSTREAM, int(port or 8000)


def _screen_page(code: int, title: str, text: str, extra: list[str] | None = None) -> bytes:
    reason = {302: "Found", 400: "Bad Request", 403: "Forbidden", 503: "Service Unavailable"}.get(code, "Error")
    body = (f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'><title>{title}</title>"
            "<body style='font:16px/1.5 system-ui;max-width:34rem;margin:3rem auto;padding:0 1rem'>"
            f"<h1 style='font-size:1.3rem'>{title}</h1><p>{text}</p>").encode()
    head = [f"HTTP/1.1 {code} {reason}", "Content-Type: text/html; charset=utf-8", f"Content-Length: {len(body)}",
            "Cache-Control: no-store", "Referrer-Policy: no-referrer", "Connection: close", *(extra or [])]
    return ("\r\n".join(head) + "\r\n\r\n").encode("latin-1") + body


def screen_request(head: bytes, now: float) -> tuple[str, bytes]:
    """Decyzja dla nagłówka żądania (bez ciała): ("odpowiedz", bajty odpowiedzi) albo ("przekaz", nagłówek dla
    ws-scrcpy). Czysta funkcja, testowana bez gniazd."""
    from urllib.parse import unquote, urlsplit

    try:
        lines = head.decode("latin-1").split("\r\n")
        method, target, version = lines[0].split(" ", 2)
    except ValueError:
        return "odpowiedz", _screen_page(400, "Złe żądanie", "Nie rozumiem tego żądania.")
    headers = [(k.strip(), v.strip()) for k, _, v in (ln.partition(":") for ln in lines[1:] if ln)]
    path = unquote(urlsplit(target).path)
    first = path.lstrip("/").partition("/")[0]
    if first and core.link_root(core.LINKS_FILE, first, now) == SCREEN_ROOT:
        left = int(float(core.links_load(core.LINKS_FILE)[first]["exp"]) - now)
        return "odpowiedz", _screen_page(302, "Ekran telefonu", "Przekierowuję…", [
            "Location: /", f"Set-Cookie: {SCREEN_COOKIE}={first}; Path=/; Max-Age={left}; HttpOnly; SameSite=Lax"])
    cookies = {}
    for k, v in headers:
        if k.lower() == "cookie":
            for part in v.split(";"):
                n, _, val = part.strip().partition("=")
                cookies[n] = val
    tok = cookies.get(SCREEN_COOKIE, "")
    if not tok or core.link_root(core.LINKS_FILE, tok, now) != SCREEN_ROOT:
        return "odpowiedz", _screen_page(403, "Ekran telefonu testowego",
                                         "Ten adres otwiera się z linku: Jarvo HQ → pokój Aplikacje → „📱 Ekran telefonu” "
                                         "albo link od Twórcy aplikacji. Link jest ważny 12 godzin.")
    upgrade = any(k.lower() == "upgrade" and v.lower() == "websocket" for k, v in headers)
    host, port = _screen_upstream()
    out = [f"{method} {target} {version}"]
    for k, v in headers:
        kl = k.lower()
        if kl in ("cookie", "host") or (kl in ("connection", "keep-alive") and not upgrade):
            continue
        out.append(f"{k}: {v}")
    out.insert(1, f"Host: {host}:{port}")
    if not upgrade:
        out.append("Connection: close")
    return "przekaz", ("\r\n".join(out) + "\r\n\r\n").encode("latin-1")


def _screen_handler():
    import selectors
    import socket
    import socketserver

    def pipe(a, b) -> None:
        sel = selectors.DefaultSelector()
        sel.register(a, selectors.EVENT_READ, b)
        sel.register(b, selectors.EVENT_READ, a)
        try:
            while True:
                events = sel.select(timeout=3600)      # godzina ciszy = porzucona karta
                if not events:
                    return
                for key, _ in events:
                    data = key.fileobj.recv(65536)
                    if not data:
                        return
                    key.data.sendall(data)
        except OSError:
            return
        finally:
            sel.close()

    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            c = self.request
            c.settimeout(30)
            buf = b""
            try:
                while b"\r\n\r\n" not in buf:
                    chunk = c.recv(16384)
                    if not chunk:
                        return
                    buf += chunk
                    if len(buf) > 65536:
                        return c.sendall(_screen_page(400, "Złe żądanie", "Za długi nagłówek."))
                head, _, rest = buf.partition(b"\r\n\r\n")
                kind, data = screen_request(head, time.time())
                if kind == "odpowiedz":
                    return c.sendall(data)
                try:
                    up = socket.create_connection(_screen_upstream(), timeout=5)
                except OSError:
                    return c.sendall(_screen_page(503, "Telefon testowy jest wyłączony",
                                                  "Włącz go na serwerze poleceniem <code>jarvo android on</code> "
                                                  "(wymaga modułu binder w jądrze Linuksa, zob. docs/MOBILE.md §5)."))
                with up:
                    up.sendall(data + rest)
                    c.settimeout(None)
                    up.settimeout(None)
                    pipe(c, up)
            except OSError:
                return

    return Handler


def _start_screen() -> None:
    if getattr(_screen, "server", None) or SCREEN_PORT == 0:
        return
    import socketserver
    import threading

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    try:
        srv = Server(("0.0.0.0", SCREEN_PORT), _screen_handler())
    except OSError as exc:
        _screen.error = f"port {SCREEN_PORT} zajęty ({exc.strerror})"
        return
    _screen.server = srv
    threading.Thread(target=srv.serve_forever, name="jarvo-android-screen", daemon=True).start()


try:
    _start_screen()
except Exception as _exc:
    _screen.error = str(_exc)


def _screen_online() -> bool:
    import socket

    try:
        socket.create_connection(_screen_upstream(), timeout=1.5).close()
        return True
    except OSError:
        return False


@router.post("/android")
async def android_screen():
    """Link do ekranu telefonu testowego: {port, path}; przeglądarka składa host jak przy „Odpal”."""
    if not getattr(_screen, "server", None):
        raise HTTPException(503, f"Proxy ekranu telefonu nie działa: {_screen.error or 'serwer nie wystartował'}")
    if not await asyncio.to_thread(_screen_online):
        raise HTTPException(503, "Telefon testowy jest wyłączony. Włącz go na serwerze: jarvo android on.")
    token = await asyncio.to_thread(core.link_for, core.LINKS_FILE, SCREEN_ROOT, time.time(), core.SCREEN_TTL)
    return {"port": SCREEN_PORT, "path": f"/{token}/"}


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
    """Co umie host: otwieranie folderów (WSL), ścieżka danych po stronie Windows, port podglądu,
    telefon testowy (włączony profil android i działające proxy ekranu)."""
    st = _update_state()
    h = st.get("host") or {}
    android = bool(getattr(_screen, "server", None)) and await asyncio.to_thread(_screen_online)
    return {"explorer": bool(st.get("online") and h.get("explorer")), "data_win": h.get("data_win"),
            "data_host": h.get("data_host"), "preview": bool(getattr(_preview, "server", None)),
            "preview_port": PREVIEW_PORT, "android": android}


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


async def _przyjmij(request: Request, limit: int) -> dict:
    """Plik z przeglądarki strumieniem → /opt/data/jarvo/inbox/<data>/<nazwa> (nazwa z X-File-Name, oczyszczona).
    Strumień idzie do pliku tymczasowego o losowej nazwie; docelowa nazwa jest rezerwowana atomowo (`O_EXCL`, jak
    obrazy rozmów w trasy_rozmow.py) dopiero po odebraniu całości, więc dwie równoczesne wysyłki o tej samej nazwie
    (albo wysyłka i obraz z wiadomości) nie nadpiszą sobie plików."""
    import secrets
    from urllib.parse import unquote

    inbox = core.JARVO_DIR / "inbox"
    nazwa = unquote(request.headers.get("X-File-Name", ""))
    teraz = time.time()                         # jedna data katalogu (wysyłka przez północ: katalog już istnieje)
    target = core.upload_target(inbox, nazwa, teraz)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f".{secrets.token_hex(8)}.part"
    size = 0
    try:
        with tmp.open("wb") as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"Plik większy niż {limit // 2**20} MB")
                f.write(chunk)
        if not size:
            raise HTTPException(400, "Pusty plik")
        for _proba in range(100):
            try:
                os.close(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644))
            except FileExistsError:
                target = core.upload_target(inbox, nazwa, teraz)
                continue
            break
        else:
            raise HTTPException(409, "Nie da się zapisać pliku — spróbuj jeszcze raz")
        tmp.replace(target)                     # nadpisuje tylko własną, pustą rezerwację
    finally:
        tmp.unlink(missing_ok=True)
    return core.file_entry(target, inbox)


@router.post("/upload")
async def upload(request: Request):
    """Plik z czatu HQ (wklejony, przeciągnięty, z 📎) → inbox; limit jak dla załącznika rozmowy."""
    return await _przyjmij(request, core.UPLOAD_MAX)


# ------------------------------------------------------------------ konwerter plików (Centrala)
# Ten sam konwertuj.py co wspólny skill floty `konwersja-plikow` (hqbuild kopiuje go obok; w repo czytany
# z shared/skills). Plik z HQ → inbox (do 2 GB), wynik w inbox/<data>/konwerter/, pobranie przez /file?download.
# Zamiana w wątku, jedna naraz (film potrafi zająć cały procesor); następne czekają w kolejce.
import dataclasses  # noqa: E402
import threading  # noqa: E402

_KONW_PLIK = next((p for p in (_HERE / "konwertuj.py",
                               _HERE.parents[1] / "shared" / "skills" / "konwersja-plikow" / "scripts" / "konwertuj.py")
                   if p.is_file()), None)
konw = _load("jarvo_hq_konwertuj", str(_KONW_PLIK)) if _KONW_PLIK else None   # ścieżka absolutna: _HERE / abs = abs
_konw = sys.modules.setdefault("jarvo_hq_konw_state", type(sys)("jarvo_hq_konw_state"))
if not hasattr(_konw, "jobs"):
    _konw.jobs = {}
    _konw.lock = threading.Lock()


def _konwerter():
    if konw is None:
        raise HTTPException(503, "Konwerter niedostępny: brak konwertuj.py w pluginie (przebuduj HQ).")
    return konw


def _konw_zrodlo(raw: str) -> Path:
    p = core.safe_path(str(raw or ""), ROOTS)
    if p is None:
        raise HTTPException(404, f"Nie ma pliku w katalogach floty: {Path(str(raw or '')).name}")
    return p


@router.post("/konwerter/upload")
async def konwerter_upload(request: Request):
    return await _przyjmij(request, core.KONWERTER_MAX)


def _konw_meta(k, p: Path, fmt: str) -> dict | None:
    """Co plik mówi o właścicielu (miejsce GPS, telefon, data, autor, firma…) i co z nazwiskami jest w treści
    dokumentu: {wrazliwe, uwagi}; None = tego pliku tu nie wyczyścimy."""
    if fmt not in k.FOTO_META | k.WIDEO | k.AUDIO | k.DOKUMENTY_META:
        return None
    if fmt not in k.PAKIETY and not shutil.which("exiftool") or fmt == "pdf" and not shutil.which("qpdf"):
        return None
    try:
        m = k.metadane(p)
    except k.Blad:
        return None
    return {"wrazliwe": m["wrazliwe"], "uwagi": m.get("uwagi", [])}


@router.get("/konwerter/cele")
async def konwerter_cele(path: str):
    """Na co da się zamienić plik: cele pogrupowane (obraz, wideo, audio, pdf…) według silników w obrazie,
    oraz metadane o człowieku w zdjęciu, filmie, dźwięku, PDF i dokumencie (ostrzeżenie i przycisk „Usuń metadane”)."""
    k = _konwerter()
    p = _konw_zrodlo(path)
    try:
        fmt = k.format_pliku(p)
        cele = await asyncio.to_thread(k.cele, fmt)
    except k.Blad as exc:
        raise HTTPException(400, core.konwerter_blad(str(exc)))
    meta = await asyncio.to_thread(_konw_meta, k, p, fmt)
    return {"path": str(p), "name": p.name, "size": p.stat().st_size, "format": fmt, "nazwa": k.FORMATY[fmt][1],
            "grupa": k.FORMATY[fmt][0], "cele": cele, "metadane": meta and meta["wrazliwe"],
            "uwagi": meta["uwagi"] if meta else [], "czysc": meta is not None}


def _konwertuj_wszystko(job: dict, k, srcs: list[Path], na: str, opt, polacz: bool, out_dir: Path,
                        czysc: bool = False) -> dict:
    with _konw.lock:
        job["state"], job["started"] = "running", time.time()
        inbox = core.JARVO_DIR / "inbox"
        wyniki, bledy = [], []
        if polacz:
            wyniki.append(k.polacz(srcs, k.wolna_sciezka(out_dir / f"{srcs[0].stem}-razem.pdf"), opt))
        else:
            for s in srcs:
                try:
                    wyniki.append(k.usun_metadane(s, katalog=out_dir) if czysc else
                                  k.konwertuj(s, na, katalog=out_dir, opt=dataclasses.replace(opt, zasoby=None)))
                except k.Blad as exc:
                    if len(srcs) == 1:
                        raise
                    bledy.append({"name": s.name, "error": core.konwerter_blad(str(exc))})
        pliki = [Path(p) for w in wyniki for p in w["pliki"]]
        if not pliki:
            raise k.Blad(bledy[0]["error"] if bledy else "Nic nie powstało.")
        paczka = None
        if len(pliki) > 1:
            nazwa = f"{srcs[0].stem}-{'bez-metadanych' if czysc else 'pdf' if polacz else na}.zip"
            paczka = core.file_entry(core.spakuj(pliki, out_dir / nazwa), inbox)
        return {"files": [core.file_entry(p, inbox) for p in pliki], "zip": paczka, "errors": bledy,
                "route": wyniki[0]["trasa"], "before": sum(w["rozmiar_przed"] for w in wyniki),
                "after": sum(w["rozmiar_po"] for w in wyniki),
                "note": None if czysc else next((w["uwaga"] for w in wyniki if w.get("uwaga")), None),
                "removed": [{"name": Path(w["wejscie"]).name, "metadane": w["usuniete"], "count": w["wpisow_usunietych"],
                             "uwagi": w.get("uwagi", [])}
                            for w in wyniki] if czysc else None}


async def _run_konwersja(job: dict, *args) -> None:
    try:
        job.update(await asyncio.to_thread(_konwertuj_wszystko, job, *args))
        job["state"] = "done"
    except Exception as exc:   # Blad konwertera = opis po polsku; inny błąd też pokazujemy zamiast wisieć
        job["state"], job["error"] = "error", core.konwerter_blad(str(exc)) or exc.__class__.__name__
    finally:
        job["ended"] = time.time()


@router.post("/konwerter")
async def konwerter_start(request: Request):
    """{paths: [...], na: "pdf", jakosc?, rozmiar?, strony?, dpi?, polacz?} albo {paths, usun_metadane: true}
    → zadanie w tle (stan: /konwerter/job/<id>)."""
    k = _konwerter()
    body = await request.json()
    paths = body.get("paths")
    if not isinstance(paths, list) or not 1 <= len(paths) <= core.KONWERTER_PLIKOW:
        raise HTTPException(400, f"Podaj od 1 do {core.KONWERTER_PLIKOW} plików")
    srcs = [_konw_zrodlo(x) for x in paths]
    czysc = bool(body.get("usun_metadane"))
    polacz = bool(body.get("polacz")) and not czysc
    na = "pdf" if polacz else "" if czysc else k.norm(str(body.get("na") or ""))
    try:
        opt = k.Opcje(**core.konwerter_opcje(body))
        if not czysc and na not in k.FORMATY:
            raise k.Blad(f"Nie znam formatu „{na}”")
        if polacz and len(srcs) < 2:
            raise k.Blad("Do łączenia potrzeba co najmniej dwóch plików.")
        k.parse_rozmiar(opt.rozmiar)
        k.strony_lista(opt.strony, None)
    except (ValueError, k.Blad) as exc:
        raise HTTPException(400, core.konwerter_blad(str(exc)))
    for jid in [x for x, j in _konw.jobs.items() if j.get("ended") and time.time() - j["ended"] > 3600]:
        _konw.jobs.pop(jid, None)
    import uuid

    jid = uuid.uuid4().hex[:12]
    job = {"id": jid, "state": "queued", "created": time.time(), "na": na, "mode": "metadane" if czysc else "zamiana",
           "names": [p.name for p in srcs]}
    _konw.jobs[jid] = job
    out_dir = core.konwerter_katalog(core.JARVO_DIR / "inbox", time.time())
    job["task"] = asyncio.create_task(_run_konwersja(job, k, srcs, na, opt, polacz, out_dir, czysc))
    return _job_view(job)


@router.get("/konwerter/job/{jid}")
async def konwerter_job(jid: str):
    job = _konw.jobs.get(jid)
    if not job:
        raise HTTPException(404, "Nie ma takiej zamiany")
    return _job_view(job)


# ------------------------------------------------------------------ figura floty (Centrala → Jak działa usługa)
# Ten sam iso.py co wspólny skill `izometria` (hqbuild kopiuje skill obok; w repo czytany z shared/skills):
# klikalna wieża floty z fleet.json, demo = droga zlecenia. Strona budowana w pamięci (na nowo po zmianie floty)
# i podawana przez serwer podglądu (osobny port, sandbox), bo ma własne skrypty.
_ISO_PLIK = next((p for p in (_HERE / "izometria" / "scripts" / "iso.py",
                              _HERE.parents[1] / "shared" / "skills" / "izometria" / "scripts" / "iso.py")
                  if p.is_file()), None)
iso = _load("jarvo_hq_iso", str(_ISO_PLIK)) if _ISO_PLIK else None
FLOTA_PATH = "/_jarvo/flota.html"
JARVO_AKCENT = "#D4213D"           # akcent HQ (--thq-accent): figura świeci kolorem Jarva
_flota = sys.modules.setdefault("jarvo_hq_flota_state", type(sys)("jarvo_hq_flota_state"))


def flota_strona(fleet_file: Path | None = None) -> bytes:
    """Strona figury floty (HTML) z fleet.json pluginu; pamiętana, póki plik floty się nie zmieni."""
    if iso is None:
        raise RuntimeError("brak iso.py w pluginie (przebuduj HQ)")
    plik = fleet_file or FLEET_FILE
    klucz = (str(plik), plik.stat().st_mtime_ns)
    if getattr(_flota, "klucz", None) != klucz:
        dane = iso.dane_floty(iso.wczytaj_flote(plik))
        strona, _ = iso.zbuduj([("flota.js", iso.figura_floty(dane))], tytul="Flota Jarvo",
                               paleta=[iso.akcent_marki(f"Jarvo={JARVO_AKCENT}")], motyw="auto")
        _flota.klucz, _flota.strona = klucz, strona.encode("utf-8")
    return _flota.strona


@router.get("/flota")
async def flota():
    """Gdzie przeglądarka znajdzie figurę floty: {port, path} serwera podglądu (host składa przeglądarka)."""
    if iso is None:
        raise HTTPException(503, "Figura floty niedostępna: brak iso.py w pluginie (przebuduj HQ).")
    if not getattr(_preview, "server", None):
        raise HTTPException(503, f"Podgląd stron nie działa: {_preview.error or 'serwer nie wystartował'}")
    return {"port": PREVIEW_PORT, "path": FLOTA_PATH}


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
    report.update(await _zdrowie_rozmow())
    return report


# ----------------------------------------------------------------------------- aktualizacje
# Stan pisze pomocnik aktualizacji na hoście (scripts/updater.py). Dashboard może tylko poprosić
# o sprawdzenie albo aktualizację tej samej gałęzi (plik update-request); poleceń nie wykonuje.
UPDATE_FILE = core.JARVO_DIR / "state" / "update.json"
UPDATE_REQUEST = core.JARVO_DIR / "state" / "update-request"
UPDATER_STALE = 5 * 60  # pomocnik sprawdza co minutę; dłuższa cisza = nie działa
PRACA_FILE = core.JARVO_DIR / "state" / "praca.json"
PRACA_STALE = 2 * 60     # silnik odświeża praca.json co minutę


def _praca() -> dict:
    """Praca floty z praca.json silnika (spec §15.3): {aktywne, opis}; stary albo brak pliku = 0."""
    try:
        d = json.loads(PRACA_FILE.read_text(encoding="utf-8"))
        if time.time() - float(d.get("at") or 0) < PRACA_STALE:
            return {"aktywne": int(d.get("aktywne") or 0), "opis": [str(x)[:120] for x in (d.get("opis") or [])][:12]}
    except (OSError, ValueError, TypeError):
        pass
    return {"aktywne": 0, "opis": []}


def _po_pracy() -> float | None:
    """Czas prośby „Zaktualizuj, gdy skończą” (meta silnika `aktualizacja_po_pracy`); None = nie czeka."""
    s = _silnik()
    if s is None or s.db is None:
        return None
    try:
        v = s.db.meta("aktualizacja_po_pracy")
        return float(v) if v else None
    except Exception:
        return None


def _update_state() -> dict:
    try:
        state = json.loads(UPDATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {"online": False, "state": "unknown", "behind": 0}
    else:
        last = max(state.get(k) or 0 for k in ("checked_at", "started_at", "finished_at", "beat"))
        state["online"] = time.time() - last < UPDATER_STALE
        state["pending"] = UPDATE_REQUEST.exists()
        state["silent_for"] = int(time.time() - last) if last else None
        # pomocnik zniknął w trakcie (zamknięty WSL, restart, zawieszony deploy): nie udajemy, że trwa
        if not state["online"] and (state.get("state") == "updating" or state["pending"]):
            state["state"] = "stalled"
    state["praca"] = _praca()
    state["po_pracy"] = _po_pracy()
    return state


@router.get("/update")
async def update_status():
    return await asyncio.to_thread(_update_state)


def _blad_update(status: int, kod: str, pl: str, en: str) -> JSONResponse:
    # `detail` zostaje dla starego widżetu (95-update.js czyta detail), `blad` dla aplikacji
    return JSONResponse({"detail": pl, "blad": {"kod": kod, "komunikat": pl, "komunikat_en": en}}, status_code=status)


@router.post("/update")
async def update_request(request: Request):
    """`{action: check|update|cancel, gdy?: teraz|wolne}` (spec §15.3). `gdy: wolne` zapisuje w rozmowy.db prośbę
    „Zaktualizuj, gdy skończą”: plik update-request pisze silnik po 30 s bez pracy. `cancel` ją kasuje."""
    try:
        body = await request.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        return _blad_update(422, "zle_dane", "Treść musi być obiektem JSON.", "The body must be a JSON object.")
    action, gdy = body.get("action"), body.get("gdy") or "teraz"
    if action not in ("check", "update", "cancel") or gdy not in ("teraz", "wolne"):
        return _blad_update(400, "zle_dane", "action: check, update albo cancel; gdy: teraz albo wolne.",
                            "action: check, update or cancel; gdy: teraz or wolne.")
    if action == "cancel":
        s = _silnik()
        if s is not None and s.dziala():
            await s.wykonaj_fn(s.db.usun_meta, "aktualizacja_po_pracy")
        HUB.nadaj("aktualizacja", await asyncio.to_thread(_update_state))
        return JSONResponse({"ok": True, "action": action}, status_code=200)
    state = await asyncio.to_thread(_update_state)
    if not state.get("online"):
        return _blad_update(503, "pomocnik", "Pomocnik aktualizacji nie działa. Lokalnie: bash scripts/local-up.sh, "
                                             "na serwerze: sudo systemctl start jarvo-updater.",
                            "The update helper is not running.")
    if state.get("state") == "updating":
        return _blad_update(409, "trwa", "Aktualizacja już trwa.", "An update is already running.")
    if action == "update" and gdy == "wolne":
        s = _silnik()
        if s is None or not s.dziala():
            return _blad_update(503, "silnik", "Silnik rozmów nie działa — nie mogę poczekać na koniec pracy.",
                                "The conversation engine is not running — cannot wait for work to finish.")
        await s.wykonaj_fn(s.db.ustaw_meta, "aktualizacja_po_pracy", repr(time.time()))
        HUB.nadaj("aktualizacja", await asyncio.to_thread(_update_state))
        return JSONResponse({"ok": True, "action": action, "gdy": gdy}, status_code=202)
    UPDATE_REQUEST.parent.mkdir(parents=True, exist_ok=True)
    UPDATE_REQUEST.write_text(action, encoding="utf-8")
    if action == "update":
        s = _silnik()
        if s is not None and s.dziala():
            await s.wykonaj_fn(s.db.usun_meta, "aktualizacja_po_pracy")
    return JSONResponse({"ok": True, "action": action}, status_code=202)


# ------------------------------------------------------- powłoka /jarvo: zasoby aplikacji, próba ochrony zapisu
# Loader dist/index.js (scripts/hqbuild.py) wczytuje pakiet aplikacji dopiero na /jarvo, stąd: nazwy z hashem treści,
# bliźniak .gz i cache na rok (pliki pluginu dashboard serwuje z no-store). Tylko nazwy z białej listy.
ZASOBY = _HERE / "dist" / "zasoby"
ZASOB_WZOR = re.compile(r"^(?:(?:app|narzedzia)-[0-9a-f]{12}\.(?:js|css)|kroje/[A-Za-z0-9_.-]+\.(?:woff2|ttf))$")
ZASOB_TYPY = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
              ".woff2": "font/woff2", ".ttf": "font/ttf"}
ZASOB_NAGLOWKI = {"Cache-Control": "private, max-age=31536000, immutable", "Vary": "Accept-Encoding",
                  "X-Content-Type-Options": "nosniff"}


def _zasob(nazwa: str, gzip_ok: bool) -> tuple[Path, dict] | None:
    """Plik zasobu do wysłania i nagłówki (gzip, gdy przeglądarka go przyjmuje i jest bliźniak .gz); None = 404."""
    if not ZASOB_WZOR.match(nazwa or ""):
        return None
    p = ZASOBY / nazwa
    if not core._within(p.resolve(), ZASOBY.resolve()):
        return None
    naglowki = dict(ZASOB_NAGLOWKI)
    gz = p.with_name(p.name + ".gz")
    if gzip_ok and gz.is_file():
        naglowki["Content-Encoding"] = "gzip"
        return gz, naglowki
    return (p, naglowki) if p.is_file() else None


@router.get("/zasoby/{nazwa:path}")
async def zasoby(nazwa: str, request: Request):
    hit = _zasob(nazwa, "gzip" in request.headers.get("accept-encoding", "").lower())
    if hit is None:
        raise HTTPException(404, "Nie ma takiego zasobu")
    return FileResponse(hit[0], media_type=ZASOB_TYPY[Path(nazwa).suffix], headers=hit[1])


# ----------------------------------------------------------------------------- rozmowy: silnik i trasy
# Silnik rozmów aplikacji (docs/HQ.md „Rozmowy”): wątek tła startowany przy imporcie wtyczki (aplikacja dashboardu
# ma lifespan, więc on_startup routera się nie wykona), jeden na proces; trasy w trasy_rozmow.py na tym routerze
# (ochrona CSRF z ochrona.Trasa). JARVO_HQ_SILNIK=0 wyłącza silnik (testy), trasy odpowiadają wtedy 503 `silnik`.
from types import SimpleNamespace  # noqa: E402

roz = SimpleNamespace(hq_core=core, ochrona=ochrona)
for _nazwa in ("agenci", "rozmowy", "czytnik", "kontekst", "wzmianki", "budzenia", "scalanie", "brama", "strumien",
               "przebiegi", "prace", "obserwator", "aplikacja", "podpowiedzi", "glos", "mozg", "silnik"):
    setattr(roz, _nazwa, _load(f"jarvo_hq_{_nazwa}", f"{_nazwa}.py"))
trasy_rozmow = _load("jarvo_hq_trasy_rozmow", "trasy_rozmow.py")
trasy_aplikacji = _load("jarvo_hq_trasy_aplikacji", "trasy_aplikacji.py")
_dziennik_hq = roz.silnik.ustaw_dziennik(HOME / "logs" / "jarvo-hq.log"
                                         if os.environ.get("JARVO_HQ_SILNIK", "1") != "0" else None)
AGENCI = roz.agenci.Agenci(FLEET_FILE, core.JARVO_DIR / "state" / "agenci.json")


def _log_hq(linia: str) -> None:
    _dziennik_hq.info(linia)


def _wersja_paczki() -> str:
    """Wersja do `hello` strumienia: skrót paczki aplikacji (zmienia się po każdej aktualizacji)."""
    for p in sorted(ZASOBY.glob("app-*.js")):
        return p.stem.split("-", 1)[1]
    try:
        return json.loads((_HERE / "manifest.json").read_text(encoding="utf-8")).get("version", "")
    except (OSError, ValueError):
        return ""


WERSJA = _wersja_paczki()
_WERSJA_E2E: list[str] = []          # tylko test E2E nowej wersji (POST /e2e/wersja): wersja w hello zamiast WERSJA


def _silnik():
    return roz.silnik.instancja()


def _hello() -> dict:
    """Stan silnika w `hello` strumienia, tak samo jak w /health (`_zdrowie_rozmow`): brak instancji przy
    włączonym silniku = start się nie udał (`awaria`), przy JARVO_HQ_SILNIK=0 = `wylaczony`."""
    s = _silnik()
    if s is None:
        stan = "wylaczony" if os.environ.get("JARVO_HQ_SILNIK", "1") == "0" else "awaria"
    else:
        stan = "ok" if s.dziala() else ("awaria" if s.stan == "awaria" else "start")
    return {"wersja": _WERSJA_E2E[-1] if _WERSJA_E2E else WERSJA, "silnik": stan}


def _start_silnika():
    stary = roz.silnik.instancja()
    if stary is not None:                     # drugi import wtyczki w tym samym procesie: ten sam silnik i hub
        return stary.hub
    hub = roz.strumien.Hub(log=_log_hq, hello=_hello)
    if os.environ.get("JARVO_HQ_SILNIK", "1") == "0":
        return hub
    try:
        s = roz.silnik.Silnik(moduly=roz, home=HOME, jarvo_dir=core.JARVO_DIR, api_base=API_BASE, agenci=AGENCI,
                              hub=hub, log=_log_hq, stan_aktualizacji=_update_state)
        roz.silnik.zarejestruj(s).start(czekaj=2.0)
        roz.silnik.zahacz_uvicorn(hub.zamknij_wszystkie)
    except Exception as exc:  # wtyczka działa dalej (stare trasy), /health i hello mówią „awaria”
        _log_hq(f"jarvo-hq: silnik rozmów nie wystartował ({type(exc).__name__})")
    return hub


HUB = _start_silnika()
trasy_rozmow.dolacz(router, m=roz, silnik=_silnik, hub=HUB, agenci=AGENCI, inbox=core.JARVO_DIR / "inbox", log=_log_hq)
# start aplikacji (GET /app, podpowiedzi N0): gotowość bez sekretów (aplikacja.py), nawyki.db (podpowiedzi.py)
GOTOWOSC = roz.aplikacja.Gotowosc(home=HOME, profil=HOME / "profiles" / "jarvo",
                                  user_md=core.JARVO_DIR / "knowledge" / "user" / "USER.md", api_base=API_BASE)
NAWYKI = roz.podpowiedzi.Nawyki(core.JARVO_DIR / "state" / "nawyki.db")
GLOS = roz.glos.Glos(core.JARVO_DIR / "state" / "glos")   # głos Jarva w aplikacji (lokalny jarvo-tts, pamięć WAV)
def _decyzje() -> list[dict]:
    """Pytania zespołu (zablokowane karty kanbana, jak Centrala Starej Bazy) dla „Czeka na Ciebie” w aplikacji."""
    now = time.time()
    return _cached("decyzje", 5.0, lambda: core.build_state(_fleet(), _board(now), _index_md(), now, {}).get("decisions") or [])




def _rozdaj_klucze(home: Path) -> None:
    """Klucz wklejony w aplikacji od razu u wszystkich agentów (share_keys.sync; wątek wtyczki zrobiłby to za ~3 s)."""
    spec = importlib.util.spec_from_file_location("jarvo_share_keys_sync", _HERE / "share_keys.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.sync(home)


# mózg z aplikacji (mozg.py): klucz API albo ChatGPT w pierwszym spotkaniu przełącza flotę; fleet.json czytany na
# nowo przy każdym wywołaniu (po aktualizacji floty ma nowe zestawy), wybór dla buildu w state/dostawca-modeli.json
MOZG = {"home": HOME, "flota": lambda: json.loads(FLEET_FILE.read_text(encoding="utf-8")),
        "stan": core.JARVO_DIR / "state" / "dostawca-modeli.json", "build_json": Path("/opt/jarvo/build/BUILD.json"),
        "rozdaj": _rozdaj_klucze, "status": roz.aplikacja.status_hermesa}
trasy_aplikacji.dolacz(router, m=roz, trasy=trasy_rozmow, silnik=_silnik, agenci=AGENCI, gotowosc=GOTOWOSC,
                       nawyki=NAWYKI, stan_aktualizacji=_update_state, hello=_hello, decyzje=_decyzje, glos=GLOS,
                       mozg=MOZG, log=_log_hq)


async def _zdrowie_rozmow() -> dict:
    """Część /health silnika rozmów (docs/HQ.md „Rozmowy”): bez treści, same liczby i stany."""
    s = _silnik()
    if s is None:
        return {"silnik": "wylaczony" if os.environ.get("JARVO_HQ_SILNIK", "1") == "0" else "awaria",
                "pid": os.getpid(), "strumien": {"polaczenia": HUB.liczba_polaczen()},
                "csrf_odmowy": ochrona.ODMOWY["razem"]}
    out = s.zdrowie()
    if s.db is not None:
        db = await asyncio.to_thread(s.db.zdrowie)
        out["rozmowy"] = {k: db.get(k) for k in ("db_ok", "wersja", "watki", "przebiegi_aktywne", "kolejka")}
        out["rozmowy"]["limit"] = s.limit
        out["sesje_nieprzypiete"] = db.get("sesje_nieprzypiete", 0)

    def _schemat() -> str:
        try:
            braki = [b for a in AGENCI.nazwy() if (HOME / "profiles" / a / "state.db").exists()
                     for b in s.czytnik.schemat(a)]
        except Exception:
            return "nieznany"
        return "zmieniony" if braki else "ok"

    out["schemat_hermesa"] = await asyncio.to_thread(_schemat)
    out["csrf_odmowy"] = ochrona.ODMOWY["razem"]
    return out


if os.environ.get("JARVO_E2E") == "1":
    @router.post("/csrf-proba")
    async def csrf_proba():
        """Trasa zapisu bez skutków ubocznych dla testu ochrony zapisu (scripts/jarvo-e2e.sh); tylko z JARVO_E2E=1."""
        return {"ok": True}

    @router.post("/e2e/limit")
    async def e2e_limit(request: Request):
        """Limit przebiegów silnika na czas testu E2E (to samo co JARVO_HQ_MAX_PRZEBIEGOW, bez restartu dashboardu;
        restart wraca do wartości z env); tylko z JARVO_E2E=1. Treść `{"limit": 1..50}`, odpowiedź z poprzednim."""
        try:
            limit = int((await request.json()).get("limit"))
        except (ValueError, TypeError, AttributeError):
            return JSONResponse({"blad": {"kod": "zle_dane", "komunikat": "Podaj limit 1–50.",
                                          "komunikat_en": "Give a limit 1–50."}}, status_code=422)
        s = _silnik()
        if s is None or not s.dziala() or not 1 <= limit <= 50:
            return JSONResponse({"blad": {"kod": "zle_dane" if s is not None and s.dziala() else "silnik",
                                          "komunikat": "Limit 1–50 przy działającym silniku.",
                                          "komunikat_en": "Limit 1–50 with the engine running."}},
                                status_code=422 if s is not None and s.dziala() else 503)

        def _ustaw() -> int:
            stary = s.rejestr.limit
            s.rejestr.limit = s.limit = limit
            s.rejestr.zmiana_stanu()          # dyspozytor od razu sprawdza kolejkę z nowym limitem
            _log_hq(f"jarvo-hq: limit przebiegów {stary}→{limit} (test E2E)")
            return stary

        return {"limit": limit, "poprzedni": await s.wykonaj_fn(_ustaw)}

    @router.post("/e2e/gotowosc")
    async def e2e_gotowosc(request: Request):
        """Test ekranu startu (scripts/jarvo-e2e.sh etap3): `{"brama": "startuje"|null}` wymusza stan bramy w gotowości
        (młoda brama bez restartu), każde wywołanie czyści pamięć gotowości (model, brama); tylko z JARVO_E2E=1."""
        try:
            brama = (await request.json()).get("brama")
        except (ValueError, AttributeError):
            brama = None
        GOTOWOSC.brama_wymuszona = brama if brama in ("startuje", "niedostepna") else None
        GOTOWOSC.odswiez()
        return {"brama": GOTOWOSC.brama_wymuszona}

    @router.post("/e2e/wersja")
    async def e2e_wersja(request: Request):
        """Test „Nowa wersja Jarva” (etap3): `{"wersja": "<napis>"|null}` podmienia wersję w hello i rozłącza każdy
        strumień (jak restart dashboardu po aktualizacji, bez restartu); null wraca do wersji paczki; tylko z JARVO_E2E=1."""
        try:
            w = (await request.json()).get("wersja")
        except (ValueError, AttributeError):
            w = None
        _WERSJA_E2E.clear()
        if isinstance(w, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,40}", w):
            _WERSJA_E2E.append(w)
        return {"wersja": _hello()["wersja"], "rozlaczone": HUB.rozlacz_wszystkie()}
