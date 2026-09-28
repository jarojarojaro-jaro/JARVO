#!/usr/bin/env python3
"""Montaż nagrań: cięcie fragmentów, kadr pod format (9:16 z poziomego), usuwanie ciszy, głośność, transkrypcja.

    python3 montaz.py wytnij nagranie.mp4 -o klip.mp4 --zakresy "0:12.5-0:41,1:10-1:32.4"
    python3 montaz.py kadr nagranie.mp4 -o pion.mp4 --format 9:16 [--x 0.5] [--tryb przytnij|rozmyte]
    python3 montaz.py cisza nagranie.mp4 -o bez-ciszy.mp4 [--prog -35] [--min 0.5] [--zapas 0.12]
    python3 montaz.py glosnosc film.mp4 -o film-14lufs.mp4 [--lufs -14]
    python3 montaz.py transkrypcja nagranie.mp4 [-o out/wideo/transkrypcja] [--co 20]
    python3 montaz.py napraw film.mp4 -o film-ok.mp4       # yuv420p/zakres TV/faststart po silnikach zewnętrznych

Czas: sekundy (75.5) albo m:ss(.x) / h:mm:ss. Każde cięcie jest przekodowane (dokładne co do klatki).
kadr --x: środek kadru w poziomie (0 = lewa krawędź, 0.5 = środek, 1 = prawa); rozmyte = całe ujęcie
na rozmytym tle (dobre do slajdów i nagrań ekranu). glosnosc: dwa przejścia loudnorm (pomiar → korekta).
transkrypcja: Parakeet (jarvo-stt) → słowa z czasem (JSON) + tekst z czasami co --co sekund (do wyboru fragmentów).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wideo_lib as wl  # noqa: E402

ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", *wl.ENC_LIMITS, "-c:a", "aac",
       "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart"]


def parse_time(s: str) -> float:
    s = s.strip()
    if not s:
        raise ValueError("pusty czas")
    parts = s.split(":")
    val = 0.0
    for p in parts:
        val = val * 60 + float(p.replace(",", "."))
    return val


def parse_ranges(spec: str) -> list[tuple[float, float]]:
    out = []
    for part in spec.split(","):
        if not part.strip():
            continue
        a, _, b = part.partition("-")
        start, end = parse_time(a), parse_time(b)
        if end <= start:
            raise SystemExit(f"Zakres {part!r}: koniec przed początkiem")
        out.append((start, end))
    return out


def has_audio(path: Path) -> bool:
    return bool(wl.probe(path)["audio"])


def cut(src: Path, ranges: list[tuple[float, float]], out: Path) -> Path:
    audio = has_audio(src)
    fc, labels = [], []
    for i, (a, b) in enumerate(ranges):
        fc.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}]")
        labels.append(f"[v{i}]")
        if audio:
            fc.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,"
                      f"afade=t=out:st={max(0.0, b - a - 0.03):.3f}:d=0.03[a{i}]")
            labels.append(f"[a{i}]")
    n = len(ranges)
    fc.append("".join(labels) + f"concat=n={n}:v=1:a={1 if audio else 0}[vc]" + ("[a]" if audio else ""))
    fc.append(f"[vc]{wl.TV_RANGE}[v]")
    maps = ["-map", "[v]"] + (["-map", "[a]"] if audio else [])
    out.parent.mkdir(parents=True, exist_ok=True)
    wl.run(["ffmpeg", "-y", "-i", str(src), "-filter_complex", ";".join(fc), *maps, *ENC, str(out)])
    return out


def reframe(src: Path, out: Path, fmt: str, x: float, mode: str) -> Path:
    w, h = wl.parse_format(fmt)
    x = min(1.0, max(0.0, x))
    if mode == "rozmyte":
        fc = (f"[0:v]split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=24:2,"
              f"eq=brightness=-0.08[bg];[b]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
              f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,{wl.TV_RANGE}[v]")
    else:
        fc = (f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
              f"crop={w}:{h}:x=(iw-{w})*{x:.3f}:y=(ih-{h})/2,setsar=1,{wl.TV_RANGE}[v]")
    maps = ["-map", "[v]"] + (["-map", "0:a"] if has_audio(src) else [])
    out.parent.mkdir(parents=True, exist_ok=True)
    wl.run(["ffmpeg", "-y", "-i", str(src), "-filter_complex", fc, *maps, *ENC, str(out)])
    return out


def silences(src: Path, thresh_db: float, min_len: float) -> list[tuple[float, float]]:
    res = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(src), "-vn", "-af",
                          f"silencedetect=noise={thresh_db}dB:d={min_len}", "-f", "null", "-"], capture_output=True, text=True)
    ss = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", res.stderr)]
    se = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", res.stderr)]
    dur = wl.duration(src)
    return [(max(0.0, s), se[i] if i < len(se) else dur) for i, s in enumerate(ss)]


def remove_silence(src: Path, out: Path, thresh_db: float, min_len: float, pad: float) -> tuple[Path, dict]:
    if not has_audio(src):
        raise SystemExit("Nagranie bez dźwięku: nie ma czego wycinać.")
    dur = wl.duration(src)
    sil = silences(src, thresh_db, min_len)
    keep, t = [], 0.0
    for s, e in sil:
        a, b = t, s + pad
        if b - a > 0.15:
            keep.append((a, min(b, dur)))
        t = max(t, e - pad)
    if dur - t > 0.15:
        keep.append((t, dur))
    if not keep:
        raise SystemExit("Całe nagranie to cisza (sprawdź --prog).")
    cut(src, keep, out)
    kept = sum(b - a for a, b in keep)
    return out, {"przed_s": round(dur, 2), "po_s": round(kept, 2), "wyciete_s": round(dur - kept, 2), "fragmenty": len(keep)}


def loudness(src: Path, out: Path, target: float) -> tuple[Path, dict]:
    first = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(src), "-vn", "-af",
                            f"loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", first.stderr, re.S)
    if not m:
        raise SystemExit("Pomiar głośności nie powiódł się (brak dźwięku?).")
    meas = json.loads(m.group(0))
    af = (f"loudnorm=I={target}:TP=-1.5:LRA=11:measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:"
          f"measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}:"
          "linear=true,aresample=48000")
    out.parent.mkdir(parents=True, exist_ok=True)
    wl.run(["ffmpeg", "-y", "-i", str(src), "-af", af, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags",
            "+faststart", str(out)])
    return out, {"przed_lufs": float(meas["input_i"]), "cel_lufs": target}


def fix(src: Path, out: Path) -> Path:
    """Film z zewnętrznego silnika → standard platform: yuv420p w zakresie TV, H.264, AAC, faststart (dźwięk bez zmian)."""
    audio = ["-c:a", "aac", "-b:a", "192k"] if has_audio(src) else []
    out.parent.mkdir(parents=True, exist_ok=True)
    wl.run(["ffmpeg", "-y", "-i", str(src), "-vf", wl.TV_RANGE, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            *wl.ENC_LIMITS, *audio, "-movflags", "+faststart", str(out)])
    return out


def transcript(src: Path, outbase: Path, every: float) -> dict:
    words = wl.transcribe_words(src)
    outbase.parent.mkdir(parents=True, exist_ok=True)
    wl.write_json(outbase.with_suffix(".slowa.json"), [w.__dict__ for w in words])
    lines, cur, t0 = [], [], None
    for w in words:
        if t0 is None:
            t0 = w.start
        cur.append(w.text)
        if w.end - t0 >= every or re.search(r"[.!?]$", w.text) and w.end - t0 >= every / 2:
            lines.append(f"[{int(t0 // 60)}:{t0 % 60:05.2f}] {' '.join(cur)}")
            cur, t0 = [], None
    if cur and t0 is not None:
        lines.append(f"[{int(t0 // 60)}:{t0 % 60:05.2f}] {' '.join(cur)}")
    outbase.with_suffix(".txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"slowa": len(words), "slowa_json": str(outbase.with_suffix(".slowa.json")), "tekst": str(outbase.with_suffix(".txt"))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("wytnij")
    c.add_argument("plik")
    c.add_argument("-o", required=True)
    c.add_argument("--zakresy", required=True)
    k = sub.add_parser("kadr")
    k.add_argument("plik")
    k.add_argument("-o", required=True)
    k.add_argument("--format", default="9:16")
    k.add_argument("--x", type=float, default=0.5)
    k.add_argument("--tryb", choices=["przytnij", "rozmyte"], default="przytnij")
    s = sub.add_parser("cisza")
    s.add_argument("plik")
    s.add_argument("-o", required=True)
    s.add_argument("--prog", type=float, default=-35.0, help="próg ciszy w dB (np. -35; głośne tło: -30)")
    s.add_argument("--min", type=float, default=0.5, help="minimalna cisza do wycięcia (s)")
    s.add_argument("--zapas", type=float, default=0.12, help="zostaw tyle ciszy przy słowach (s)")
    g = sub.add_parser("glosnosc")
    g.add_argument("plik")
    g.add_argument("-o", required=True)
    g.add_argument("--lufs", type=float, default=-14.0)
    n = sub.add_parser("napraw", help="yuv420p (zakres TV), H.264, AAC, faststart: dla filmów z lemo/anidoodle/HyperFrames")
    n.add_argument("plik")
    n.add_argument("-o", required=True)
    t = sub.add_parser("transkrypcja")
    t.add_argument("plik")
    t.add_argument("-o", default=None, help="baza nazwy wyników (domyślnie obok nagrania)")
    t.add_argument("--co", type=float, default=20.0, help="linia tekstu co ~N sekund")
    args = ap.parse_args(argv)
    wl.need("ffmpeg")
    src = Path(args.plik)
    if not src.exists():
        raise SystemExit(f"Brak pliku: {src}")
    try:
        if args.cmd == "wytnij":
            out = cut(src, parse_ranges(args.zakresy), Path(args.o))
            print(json.dumps({"plik": str(out), "sek": round(wl.duration(out), 2)}, ensure_ascii=False))
        elif args.cmd == "kadr":
            out = reframe(src, Path(args.o), args.format, args.x, args.tryb)
            print(json.dumps({"plik": str(out), "format": args.format}, ensure_ascii=False))
        elif args.cmd == "cisza":
            out, stats = remove_silence(src, Path(args.o), args.prog, args.min, args.zapas)
            print(json.dumps({"plik": str(out), **stats}, ensure_ascii=False))
        elif args.cmd == "glosnosc":
            out, stats = loudness(src, Path(args.o), args.lufs)
            print(json.dumps({"plik": str(out), **stats}, ensure_ascii=False))
        elif args.cmd == "napraw":
            out = fix(src, Path(args.o))
            print(json.dumps({"plik": str(out)}, ensure_ascii=False))
        else:
            base = Path(args.o) if args.o else src.with_suffix("")
            print(json.dumps(transcript(src, base, args.co), ensure_ascii=False))
        return 0
    except wl.FFError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
