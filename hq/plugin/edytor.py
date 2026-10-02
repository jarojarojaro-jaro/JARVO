"""Jarvo HQ: edytor filmów (logika bez serwera, testowalna).

Projekt montażu to mały JSON (zapisywany obok filmu jako `<nazwa>.edycja.json`):

    {"version": 1, "canvas": {"w": 1080, "h": 1920, "fps": 30},
     "clips": [{"src": "/opt/data/jarvo/.../film.mp4", "in": 0.0, "out": 4.2, "speed": 1.0,
                "volume": 1.0, "muted": false, "fit": "contain"}],     # pasy; "blur" = rozmyte tło; "cover" + fx, fy, zoom
     "texts": [{"start": 0.5, "end": 3.0, ...}],          # wygląd rysuje przeglądarka (PNG na klatkę)
     "audio": [{"src": ".../muzyka.mp3", "start": 0.0, "in": 0.0, "out": 30.0, "volume": 0.4}]}

Klipy leżą jeden za drugim (ścieżka główna jak w CapCut), napisy i muzyka mają własny czas.
Eksport: jeden przebieg ffmpeg (klipy → concat → nakładki PNG → miks audio), plik obok oryginału.
Napisy rasteryzuje przeglądarka tą samą funkcją, którą rysuje podgląd, więc eksport wygląda jak podgląd.
"""

from __future__ import annotations

import json
import math
import os
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
MAX_WORDS = 40           # słów w jednym napisie karaoke (linia napisu ma ich 2–8)
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
                      "fit": c.get("fit") if c.get("fit") in ("cover", "blur") else "contain",
                      # kadr przy „Wypełnij”: punkt skupienia (0–1, 0,5 = środek) i przybliżenie (punch-in)
                      "fx": _num(c.get("fx"), 0, 1, 0.5), "fy": _num(c.get("fy"), 0, 1, 0.5),
                      "zoom": _num(c.get("zoom"), 1, 3, 1)})
    if not clips:
        raise ProjectError("Oś czasu jest pusta: dodaj co najmniej jeden klip.")
    total = sum((c["out"] - c["in"]) / c["speed"] for c in clips)
    if total > MAX_DURATION:
        raise ProjectError("Film dłuższy niż 3 godziny.")

    texts = []   # "i" = numer napisu w projekcie: po nim dobieramy jego obraz PNG
    for i, t in enumerate((project.get("texts") or [])[:MAX_TEXTS]):
        s = _num((t or {}).get("start"), 0, total, 0)
        e = _num(t.get("end"), 0, total, s)
        if e - s >= MIN_CLIP:
            x = {"start": s, "end": e, "i": i}
            kara = karaoke_windows(t, s, e)
            if kara:
                x["kara"] = kara
            texts.append(x)

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


def layout_clips(clips: list[dict]) -> list[tuple[dict, float, float]]:
    """(klip, początek, koniec) na osi: klipy jeden po drugim, długość (out − in) / tempo."""
    out, t = [], 0.0
    for c in clips:
        d = (float(c.get("out", 0)) - float(c.get("in", 0))) / float(c.get("speed") or 1)
        out.append((c, t, t + d))
        t += d
    return out


def remap_times(p0: dict, p1: dict) -> dict:
    """Oś magnetyczna, ta sama reguła co remapTimes w hq/web/src/45-edytor.js: po zmianie klipów (usunięcie, wstawienie,
    przycięcie, tempo, przestawienie) napisy i uwagi idą za materiałem, z którego pochodzą (czas źródła klipu), a muzyka
    i lektor przesuwają się o wycięty albo wstawiony czas. Przy samym przestawieniu napis jedzie w całości z klipem."""
    l0, l1 = layout_clips(p0.get("clips") or []), layout_clips(p1.get("clips") or [])
    tot0, tot1 = (l0[-1][2] if l0 else 0.0), (l1[-1][2] if l1 else 0.0)
    ids0 = {c.get("id") for c in p0.get("clips") or []}

    def klucz(c: dict) -> str:
        return f"{c.get('id')}|{float(c.get('in', 0))}|{float(c.get('out', 0))}|{float(c.get('speed') or 1)}"
    reorder = (len(p0.get("clips") or []) == len(p1.get("clips") or [])
               and sorted(map(klucz, p0.get("clips") or [])) == sorted(map(klucz, p1.get("clips") or [])))

    def mapuj(t: float) -> float:
        if t >= tot0 - 1e-9:
            return t + tot1 - tot0
        i = next((k for k, s in enumerate(l0) if t < s[2]), 0)
        c0, a0, _ = l0[i]
        u = float(c0.get("in", 0)) + (t - a0) * float(c0.get("speed") or 1)

        def trafia(s) -> bool:
            c = s[0]
            return c.get("src") == c0.get("src") and float(c.get("in", 0)) - 1e-6 <= u <= float(c.get("out", 0)) + 1e-6
        same = next((s for s in l1 if s[0].get("id") == c0.get("id")), None)
        s1 = same if same and trafia(same) else next((s for s in l1 if s[0].get("id") not in ids0 and trafia(s)), None)
        if s1:
            return s1[1] + (u - float(s1[0].get("in", 0))) / float(s1[0].get("speed") or 1)
        if same:                                             # wycięty fragment klipu: na jego krawędź
            return same[1] if u < float(same[0].get("in", 0)) else same[2]
        for s in l0[i + 1:]:                                 # klip usunięty: tam, gdzie był
            nast = next((x for x in l1 if x[0].get("id") == s[0].get("id")), None)
            if nast:
                return nast[1]
        return tot1

    texts = []
    for x in p1.get("texts") or []:
        a, b = float(x.get("start", 0)), float(x.get("end", 0))
        if reorder:
            d = mapuj((a + b) / 2) - (a + b) / 2
            a, b = a + d, b + d
        else:
            a, b = mapuj(a), mapuj(b)
        if b - a >= 0.05:
            texts.append({**x, "start": round(a, 3), "end": round(b, 3)})
    audio = p1.get("audio") or []
    if not reorder:
        audio = [{**m, "start": round(mapuj(float(m.get("start", 0))), 3)} for m in audio]
    notes = [{**n, "t": round(mapuj(float(n.get("t", 0))), 3)} for n in p1.get("notes") or []]
    return {**p1, "texts": texts, "audio": audio, "notes": notes}


def karaoke_words(t: dict) -> list[str] | None:
    """Słowa napisu karaoke albo None (ta sama reguła co karaokeWords w 44-napisy.js): jest kolor `hl`, lista `words`
    i tyle samo słów w tekście (poprawiona literówka zostaje karaoke, inna liczba słów już nie)."""
    words, toks = t.get("words"), str(t.get("text") or "").split()
    if not t.get("hl") or not isinstance(words, list) or not words or len(words) != len(toks) or len(words) > MAX_WORDS:
        return None
    return toks


def karaoke_windows(t: dict, s: float, e: float) -> list[tuple[float, float, int]] | None:
    """Okna czasu osi, w których aktywne jest słowo j (czasy słów liczone od początku napisu).
    Przed pierwszym słowem aktywne jest pierwsze, ostatnie trwa do końca napisu: okna pokrywają cały napis."""
    if karaoke_words(t) is None:
        return None
    starts, top = [], 0.0
    for w in t["words"]:
        rel = _num(w[0] if isinstance(w, (list, tuple)) and w else 0, 0, MAX_DURATION, 0)
        top = max(top, rel)                                    # czasy rosną (jak w karaokeIndex)
        starts.append(min(e, s + top))
    out = []
    for j in range(len(starts)):
        a = s if j == 0 else starts[j]
        b = e if j == len(starts) - 1 else starts[j + 1]
        if b - a >= 0.001:
            out.append((a, b, j))
    return out or None


def blank_png(path: Path, w: int, h: int) -> Path:
    """Przezroczysty PNG w×h (tło warstwy karaoke między napisami), bez zależności."""
    import struct
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = (b"\x00" + b"\x00" * (4 * w)) * h
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    return path


def karaoke_concat(p: dict, pngs: dict[int, list[Path]], blank: Path, dest: Path) -> Path | None:
    """Wszystkie napisy karaoke jako JEDNA warstwa: lista demuxera concat (PNG aktywnego słowa + czas, przerwy
    = przezroczysty PNG). ffmpeg dekoduje naraz jeden obraz, więc pamięć nie rośnie z liczbą słów."""
    events = sorted((a, b, pngs[x["i"]][j]) for x in p["texts"] if x.get("kara") for a, b, j in x["kara"])
    if not events:
        return None
    lines, t = ["ffconcat version 1.0"], 0.0

    def add(path: Path, dur: float) -> None:
        if dur >= 0.001:
            lines.extend([f"file '{path}'", f"duration {dur:.3f}"])
    for a, b, png in events:
        if b <= t:
            continue                       # nakładające się napisy karaoke: wygrywa wcześniejszy
        a = max(a, t)
        add(blank, a - t)
        add(png, b - a)
        t = b
    add(blank, max(0.0, p["duration"] - t))
    lines.append(f"file '{blank}'")        # demuxer concat potrzebuje ostatniego pliku jeszcze raz
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


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


def cover_filter(W: int, H: int, c: dict) -> str:
    """„Wypełnij” z kadrem: obraz skalowany tak, by pokrył kadr powiększony o `zoom`, i wycięty z punktem skupienia
    (fx, fy). To ten sam kadr co w podglądzie (CSS object-position fx fy + scale(zoom) wokół tego punktu)."""
    z, fx, fy = c.get("zoom", 1), c.get("fx", 0.5), c.get("fy", 0.5)
    sw, sh = (_even(W * z), _even(H * z)) if z != 1 else (W, H)
    return (f"scale={sw}:{sh}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H}:(iw-{W})*{_f(fx)}:(ih-{H})*{_f(fy)}")


def blur_filter(W: int, H: int, i: int) -> str:
    """„Rozmyte tło”: całe ujęcie na środku, pod nim to samo ujęcie pokrywające kadr, rozmyte i lekko przyciemnione
    (jak `film.py --tryb rozmyte`; podgląd: blurBg w przeglądarce). Etykiety z numerem klipu: jeden graf na eksport.
    Promień rośnie z kadrem (24 px przy 1080), bo boxblur odrzuca promień większy niż ćwierć krótszego boku."""
    r = max(2, round(min(W, H) * 0.022))
    return (f"split[bg{i}][fg{i}];[bg{i}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"boxblur={r}:2,eq=brightness=-0.08[bb{i}];[fg{i}]scale={W}:{H}:force_original_aspect_ratio=decrease[ff{i}];"
            f"[bb{i}][ff{i}]overlay=(W-w)/2:(H-h)/2")


def build_command(p: dict, has_audio: dict, text_pngs: list[Path], out: Path,
                  ffmpeg: str = "ffmpeg", karaoke: Path | None = None) -> list[str]:
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
        fit = (cover_filter(W, H, c) if c["fit"] == "cover" else blur_filter(W, H, i) if c["fit"] == "blur"
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
        if t.get("kara") and karaoke:
            continue                        # ten napis jest w warstwie karaoke niżej
        args += ["-i", str(png)]
        ti = n; n += 1
        graph.append(f"[{vlast}][{ti}:v]overlay=0:0:format=auto:enable='between(t,{_f(t['start'])},{_f(t['end'])})'[vt{k}]")
        vlast = f"vt{k}"

    if karaoke:
        # -reinit_filter 0: obrazy mogą mieć różny format pikseli (RGB/RGBA); bez tego ffmpeg przebudowuje graf
        # w trakcie i nakładka gubi warstwę (sprawdzone testem na kolorach)
        args += ["-reinit_filter", "0", "-f", "concat", "-safe", "0", "-i", str(karaoke)]
        ki = n; n += 1
        graph.append(f"[{ki}:v]fps={F},format=rgba[kl]")
        graph.append(f"[{vlast}][kl]overlay=0:0:format=auto:eof_action=pass[vk]")
        vlast = "vk"

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
                            "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate:stream_tags=rotate",
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
            "video": bool(v) and media_kind(path) != "audio", "vcodec": v.get("codec_name")}


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


_SRT_TIME = re.compile(r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})")


def _srt_sec(m: re.Match) -> float:
    h, mi, se, ms = m.groups()
    return int(h) * 3600 + int(mi) * 60 + int(se) + int(ms.ljust(3, "0")) / 1000


def parse_srt(text: str, limit: int = 5000) -> list[dict]:
    """Napisy SRT → [{start, end, text}] (bloki bez czasu pomijamy, tagi <i> itp. usuwamy)."""
    out = []
    for block in re.split(r"\n\s*\n", text.replace("\r", "").replace("\ufeff", "").strip()):
        lines = [x for x in block.split("\n") if x.strip()]
        for i, line in enumerate(lines):
            if "-->" in line:
                a, _, b = line.partition("-->")
                ma, mb = _SRT_TIME.search(a), _SRT_TIME.search(b)
                body = re.sub(r"<[^>]+>", "", "\n".join(lines[i + 1:])).strip()
                if ma and mb and body and _srt_sec(mb) > _srt_sec(ma):
                    out.append({"start": _srt_sec(ma), "end": _srt_sec(mb), "text": body})
                break
        if len(out) >= limit:
            break
    return out


def _srt_ts(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def to_srt(lines: list[dict]) -> str:
    return "".join(f"{i}\n{_srt_ts(x['start'])} --> {_srt_ts(x['end'])}\n{x['text']}\n\n" for i, x in enumerate(lines, 1))


def auto_srt_path(src: Path) -> Path:
    """Napisy z mowy zapisujemy obok źródła: następnym razem wczytują się od razu (i widzi je agent)."""
    return src.with_name(f"{src.stem}.auto.srt")


def stt_bin() -> str | None:
    env = os.environ.get("JARVO_STT_BIN")
    if env:
        return env if Path(env).exists() else None
    return shutil.which("jarvo-stt") or ("/opt/jarvo/bin/jarvo-stt" if Path("/opt/jarvo/bin/jarvo-stt").exists() else None)


def tools() -> dict:
    return {"ffmpeg": shutil.which("ffmpeg"), "ffprobe": shutil.which("ffprobe"), "stt": stt_bin()}


# ----------------------------------------------------------------------------- mowa: pauzy, wtrącenia, napisy
SILENCE_DB = -35       # próg ciszy (dB); pauza krótsza niż SILENCE_MIN nie jest zaznaczana
SILENCE_MIN = 0.35
_FILLER = re.compile(r"^(y+|e+|ee+m*|m+|h?m+|ym+|em+|uh+m*|um+|eh+m*|ah+|yhm+|mhm+)$")


def is_filler(word: str) -> bool:
    """Wtrącenia typu „yyy”, „eee”, „mmm”, „hmm” (bez interpunkcji i wielkości liter)."""
    w = re.sub(r"[^\w]", "", word.lower())
    return bool(w) and bool(_FILLER.match(w))


def parse_silences(log: str, duration: float | None = None) -> list[list[float]]:
    """Wynik filtra silencedetect → [[start, end], …]; cisza do końca pliku kończy się na `duration`."""
    out, start = [], None
    for line in log.splitlines():
        m = re.search(r"silence_start: (-?[\d.]+)", line)
        if m:
            start = max(0.0, float(m.group(1)))
            continue
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and start is not None:
            out.append([round(start, 3), round(float(m.group(1)), 3)])
            start = None
    if start is not None and duration:
        out.append([round(start, 3), round(duration, 3)])
    return [x for x in out if x[1] - x[0] > 0.05]


def lines_from_words(words: list, max_chars: int = 32, max_gap: float = 0.6, max_dur: float = 3.5) -> list[dict]:
    """Słowa [[start, end, tekst]] → linie napisów zgrane ze słowami (nowa linia po pauzie,
    końcu zdania, za długim tekście albo czasie). Wtrąceń nie pokazujemy w napisach."""
    lines, cur = [], []
    def flush():
        if cur:   # words: czasy słów od początku linii (napisy karaoke, jak groupLines w edytorze)
            lines.append({"start": cur[0][0], "end": cur[-1][1], "text": " ".join(w[2] for w in cur),
                          "words": [[round(w[0] - cur[0][0], 3), round(w[1] - cur[0][0], 3), w[2]] for w in cur]})
            cur.clear()
    for w in words:
        a, b, t = float(w[0]), float(w[1]), str(w[2])
        if is_filler(t):
            continue
        if cur and (a - cur[-1][1] > max_gap or len(" ".join(x[2] for x in cur)) + 1 + len(t) > max_chars
                    or b - cur[0][0] > max_dur):
            flush()
        cur.append((a, b, t))
        if t.endswith((".", "!", "?", "…")):
            flush()
    flush()
    return lines


def speech_path(src: Path) -> Path:
    return src.with_name(f"{src.stem}.mowa.json")


def speech_data(words: list, silences: list, duration: float | None) -> dict:
    return {"v": 1, "duration": duration, "words": words, "silences": silences,
            "fillers": [i for i, w in enumerate(words) if is_filler(str(w[2]))],
            "lines": lines_from_words(words)}


def proxy_key(src: Path) -> str:
    import hashlib
    st = src.stat()
    return hashlib.sha1(f"{src}|{st.st_size}|{int(st.st_mtime)}".encode()).hexdigest()[:20]


def proxy_command(src: Path, out: Path, ffmpeg: str = "ffmpeg") -> list[str]:
    """Kopia do podglądu, którą odtworzy każda przeglądarka: WebM VP9 do 540 p, klatka kluczowa co 0,5 s
    (szybkie przewijanie), szybkie kodowanie. Eksport i tak bierze oryginał."""
    return [ffmpeg, "-nostdin", "-hide_banner", "-y", "-loglevel", "error", "-i", str(src),
            "-vf", "scale=-2:'min(540,ih)':flags=bilinear,format=yuv420p", "-c:v", "libvpx-vp9", "-deadline", "realtime",
            "-cpu-used", "8", "-row-mt", "1", "-b:v", "1200k", "-g", "15", "-c:a", "libopus", "-b:a", "96k", "-ac", "2",
            "-f", "webm", str(out)]
