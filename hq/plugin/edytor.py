"""Jarvo HQ: edytor filmów (logika bez serwera, testowalna).

Projekt montażu to mały JSON (zapisywany obok filmu jako `<nazwa>.edycja.json`):

    {"version": 1, "canvas": {"w": 1080, "h": 1920, "fps": 30},
     "clips": [{"src": "/opt/data/jarvo/.../film.mp4", "in": 0.0, "out": 4.2, "speed": 1.0,
                "volume": 1.0, "muted": false, "fit": "contain"}],
     "texts": [{"start": 0.5, "end": 3.0, ...}],          # wygląd rysuje przeglądarka (PNG na klatkę)
     "audio": [{"src": ".../muzyka.mp3", "start": 0.0, "in": 0.0, "out": 30.0, "volume": 0.4}]}

Klipy leżą jeden za drugim (ścieżka główna jak w CapCut), napisy i muzyka mają własny czas.
Eksport: jeden przebieg ffmpeg (klipy → concat → nakładki PNG → miks audio), plik obok oryginału.
Napisy rasteryzuje przeglądarka tą samą funkcją, którą rysuje podgląd, więc eksport wygląda jak podgląd.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

VIDEO_EXT = {".mp4", ".webm", ".mov", ".mkv", ".m4v"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".opus"}
MEDIA_EXT = VIDEO_EXT | IMAGE_EXT | AUDIO_EXT

MAX_CLIPS = 200
MAX_TEXTS = 60
MAX_AUDIO = 12
MAX_DURATION = 3 * 3600.0
MIN_CLIP = 0.04          # jedna klatka przy 25 fps
FPS_ALLOWED = (24, 25, 30, 50, 60)


class ProjectError(ValueError):
    """Projekt, którego nie da się bezpiecznie złożyć (komunikat trafia do użytkownika)."""


def media_kind(p: Path | str) -> str | None:
    ext = Path(p).suffix.lower()
    if ext in VIDEO_EXT:
        return "video"
    if ext in IMAGE_EXT:
        return "image"
    if ext in AUDIO_EXT:
        return "audio"
    return None


def project_path(video: Path) -> Path:
    return video.with_name(f"{video.stem}.edycja.json")


def _num(v: Any, lo: float, hi: float, default: float) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(x):
        return default
    return min(hi, max(lo, x))


def _even(n: float) -> int:
    n = int(round(n))
    return max(2, n - (n % 2))       # libx264 + yuv420p wymaga parzystych wymiarów


def normalize(project: dict, resolve) -> dict:
    """Sprawdza i porządkuje projekt. `resolve(src) -> Path | None` pilnuje katalogów floty."""
    if not isinstance(project, dict):
        raise ProjectError("Projekt musi być obiektem JSON.")
    cv = project.get("canvas") or {}
    fps = int(_num(cv.get("fps"), 1, 60, 30))
    canvas = {"w": _even(_num(cv.get("w"), 16, 3840, 1920)), "h": _even(_num(cv.get("h"), 16, 3840, 1080)),
              "fps": min(FPS_ALLOWED, key=lambda f: abs(f - fps))}

    clips = []
    for c in (project.get("clips") or [])[:MAX_CLIPS + 1]:
        if len(clips) >= MAX_CLIPS:
            raise ProjectError(f"Najwyżej {MAX_CLIPS} klipów.")
        path = resolve(str((c or {}).get("src") or ""))
        kind = media_kind(path) if path else None
        if kind not in ("video", "image"):
            raise ProjectError(f"Klip spoza katalogów floty albo nie wideo/obraz: {(c or {}).get('src')}")
        a = _num(c.get("in"), 0, MAX_DURATION, 0)
        b = _num(c.get("out"), 0, MAX_DURATION, a + 3)
        if b - a < MIN_CLIP:
            raise ProjectError(f"Klip krótszy niż klatka: {path.name}")
        clips.append({"src": path, "kind": kind, "in": a, "out": b,
                      "speed": 1.0 if kind == "image" else _num(c.get("speed"), 0.25, 4, 1),
                      "volume": _num(c.get("volume"), 0, 2, 1), "muted": bool(c.get("muted")),
                      "fit": "cover" if c.get("fit") == "cover" else "contain"})
    if not clips:
        raise ProjectError("Oś czasu jest pusta: dodaj co najmniej jeden klip.")
    total = sum((c["out"] - c["in"]) / c["speed"] for c in clips)
    if total > MAX_DURATION:
        raise ProjectError("Film dłuższy niż 3 godziny.")

    texts = []
    for t in (project.get("texts") or [])[:MAX_TEXTS]:
        s = _num((t or {}).get("start"), 0, total, 0)
        e = _num(t.get("end"), 0, total, s)
        if e - s >= MIN_CLIP:
            texts.append({"start": s, "end": e})

    audio = []
    for m in (project.get("audio") or [])[:MAX_AUDIO]:
        path = resolve(str((m or {}).get("src") or ""))
        if not path or media_kind(path) not in ("audio", "video"):
            raise ProjectError(f"Ścieżka dźwięku spoza katalogów floty: {(m or {}).get('src')}")
        a = _num(m.get("in"), 0, MAX_DURATION, 0)
        b = _num(m.get("out"), 0, MAX_DURATION, a)
        start = _num(m.get("start"), 0, total, 0)
        b = min(b, a + (total - start))          # muzyka nie wychodzi poza film
        if b - a >= MIN_CLIP:
            audio.append({"src": path, "in": a, "out": b, "start": start, "volume": _num(m.get("volume"), 0, 2, 1)})
    return {"canvas": canvas, "clips": clips, "texts": texts, "audio": audio, "duration": total}


def _atempo(speed: float) -> str:
    # atempo przyjmuje 0.5–2.0 w jednym filtrze, więc szersze tempo składamy z kilku
    parts, s = [], speed
    while s > 2.0:
        parts.append("atempo=2.0"); s /= 2.0
    while s < 0.5:
        parts.append("atempo=0.5"); s /= 0.5
    if abs(s - 1.0) > 1e-6:
        parts.append(f"atempo={s:.6f}")
    return ",".join(parts)


def _f(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".") or "0"


def build_command(p: dict, has_audio: dict, text_pngs: list[Path], out: Path,
                  ffmpeg: str = "ffmpeg") -> list[str]:
    """Argumenty ffmpeg dla znormalizowanego projektu. `has_audio[src] -> bool` z ffprobe."""
    W, H, F = p["canvas"]["w"], p["canvas"]["h"], p["canvas"]["fps"]
    args = [ffmpeg, "-nostdin", "-hide_banner", "-y", "-loglevel", "error", "-progress", "pipe:1", "-nostats"]
    graph: list[str] = []
    n = 0
    seg_labels = []
    for i, c in enumerate(p["clips"]):
        dur_src = c["out"] - c["in"]
        dur = dur_src / c["speed"]
        if c["kind"] == "image":
            args += ["-loop", "1", "-framerate", str(F), "-t", _f(dur_src), "-i", str(c["src"])]
        else:
            args += ["-ss", _f(c["in"]), "-t", _f(dur_src), "-i", str(c["src"])]
        vi = n; n += 1
        fit = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}" if c["fit"] == "cover"
               else f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black")
        graph.append(f"[{vi}:v]setpts=(PTS-STARTPTS)/{_f(c['speed'])},fps={F},{fit},setsar=1,format=yuv420p,"
                     f"tpad=stop_mode=clone:stop_duration=1,trim=duration={_f(dur)},setpts=PTS-STARTPTS[v{i}]")
        if c["kind"] == "video" and not c["muted"] and has_audio.get(str(c["src"])) and c["volume"] > 0:
            chain = ",".join(x for x in ("asetpts=PTS-STARTPTS", _atempo(c["speed"]),
                                         f"volume={_f(c['volume'])}" if c["volume"] != 1 else "") if x)
            graph.append(f"[{vi}:a]{chain},aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                         f"apad,atrim=duration={_f(dur)},asetpts=PTS-STARTPTS[a{i}]")
        else:
            graph.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={_f(dur)},aformat=sample_fmts=fltp[a{i}]")
        seg_labels.append(f"[v{i}][a{i}]")
    graph.append(f"{''.join(seg_labels)}concat=n={len(p['clips'])}:v=1:a=1[vc][ac]")

    vlast = "vc"
    for k, (t, png) in enumerate(zip(p["texts"], text_pngs)):
        args += ["-i", str(png)]
        ti = n; n += 1
        graph.append(f"[{vlast}][{ti}:v]overlay=0:0:format=auto:enable='between(t,{_f(t['start'])},{_f(t['end'])})'[vt{k}]")
        vlast = f"vt{k}"

    alast = "ac"
    if p["audio"]:
        mix = ["[ac]"]
        for k, m in enumerate(p["audio"]):
            args += ["-ss", _f(m["in"]), "-t", _f(m["out"] - m["in"]), "-i", str(m["src"])]
            mi = n; n += 1
            ms = int(round(m["start"] * 1000))
            graph.append(f"[{mi}:a]asetpts=PTS-STARTPTS,volume={_f(m['volume'])},aresample=48000,"
                         f"aformat=sample_fmts=fltp:channel_layouts=stereo,adelay={ms}|{ms}[m{k}]")
            mix.append(f"[m{k}]")
        graph.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:normalize=0,"
                     f"alimiter=limit=0.97[amx]")
        alast = "amx"

    args += ["-filter_complex", ";".join(graph), "-map", f"[{vlast}]", "-map", f"[{alast}]",
             "-t", _f(p["duration"]), "-r", str(F),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    return args


def probe(path: Path, ffprobe: str = "ffprobe") -> dict:
    """Czas, wymiary i obecność dźwięku (ffprobe). Obraz: wymiary, bez czasu."""
    try:
        r = subprocess.run([ffprobe, "-v", "error", "-show_entries",
                            "format=duration:stream=codec_type,width,height,r_frame_rate:stream_tags=rotate",
                            "-of", "json", str(path)], capture_output=True, text=True, timeout=20)
        data = json.loads(r.stdout or "{}")
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return {"ok": False}
    streams = data.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    w, h = v.get("width"), v.get("height")
    if str((v.get("tags") or {}).get("rotate", "0")) in ("90", "-90", "270"):
        w, h = h, w
    fps = None
    if v.get("r_frame_rate") and "/" in v["r_frame_rate"]:
        a, b = v["r_frame_rate"].split("/")
        fps = round(float(a) / float(b), 3) if float(b) else None
    dur = (data.get("format") or {}).get("duration")
    return {"ok": True, "duration": float(dur) if dur not in (None, "N/A") else None, "w": w, "h": h, "fps": fps,
            "audio": any(s.get("codec_type") == "audio" for s in streams),
            "video": bool(v) and media_kind(path) != "audio"}


def export_name(video: Path) -> Path:
    """Wolna nazwa obok oryginału: film-edycja.mp4, film-edycja-2.mp4… (nigdy nie nadpisujemy)."""
    stem = re.sub(r"-edycja(-\d+)?$", "", video.stem)
    for k in range(1, 1000):
        cand = video.with_name(f"{stem}-edycja{'' if k == 1 else f'-{k}'}.mp4")
        if not cand.exists():
            return cand
    raise ProjectError("Za dużo wersji tego filmu w katalogu.")


def parse_progress(chunk: str) -> float | None:
    """Sekundy wyjścia z bloku `-progress` ffmpeg (out_time_us albo out_time_ms, oba w µs)."""
    val = None
    for line in chunk.splitlines():
        k, _, v = line.partition("=")
        if k in ("out_time_us", "out_time_ms") and v.strip().lstrip("-").isdigit():
            val = max(0.0, int(v) / 1e6)
    return val


def tools() -> dict:
    return {"ffmpeg": shutil.which("ffmpeg"), "ffprobe": shutil.which("ffprobe")}
