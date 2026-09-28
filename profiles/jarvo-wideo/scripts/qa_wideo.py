#!/usr/bin/env python3
"""Kontrola techniczna filmu przed oddaniem: jedno przejście FFmpeg, wynik w JSON i arkusz klatek do oceny okiem.

    python3 qa_wideo.py film.mp4 [--platforma tiktok] [--format 9:16] [--lektor] [--arkusz out/wideo/qa.jpg] [--json]

Sprawdza: kontener i kodeki (H.264 + AAC, yuv420p, faststart), rozdzielczość i proporcje, fps, długość wobec
platformy, głośność (LUFS zintegrowane i true peak), czarne klatki, zamrożony obraz, cisze w dźwięku.
--arkusz: klatki z początku (hook), środka i końca z zaznaczonymi strefami interfejsu platformy (9:16):
na nich widać, czy napisy, tekst i logo nie wchodzą pod przyciski i opis.
Kod wyjścia 1 = jest błąd blokujący. Tabela platform zgodna z skills/wideo/formaty-wideo/references/specs.md.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wideo_lib as wl  # noqa: E402

# platforma: (format, maks. sekund, zalecany zakres sekund)
PLATFORMS = {
    "tiktok": ("9:16", 600, (15, 60)), "ig-reel": ("9:16", 180, (15, 60)), "yt-short": ("9:16", 180, (15, 60)),
    "fb-reel": ("9:16", 90, (15, 60)), "ig-story": ("9:16", 60, (5, 15)), "li-video": ("4:5", 600, (30, 90)),
    "ig-feed": ("4:5", 60, (15, 45)), "x-video": ("16:9", 140, (15, 45)), "yt-video": ("16:9", 43200, (60, 900)),
    "kwadrat": ("1:1", 600, (15, 60)),
}
LUFS_OK = (-16.0, -12.0)
TRUE_PEAK_MAX = -1.0


def moov_first(path: Path) -> bool:
    """Czy atom moov jest przed mdat (faststart: odtwarzanie startuje przed pobraniem całości)."""
    with open(path, "rb") as f:
        pos = 0
        size_total = path.stat().st_size
        while pos < size_total:
            f.seek(pos)
            head = f.read(16)
            if len(head) < 8:
                return False
            size = int.from_bytes(head[:4], "big")
            kind = head[4:8]
            if size == 1:
                size = int.from_bytes(head[8:16], "big")
            if kind == b"moov":
                return True
            if kind == b"mdat":
                return False
            if size < 8:
                return False
            pos += size
    return False


def analyze(path: Path, has_audio: bool) -> dict:
    """Jedno dekodowanie: blackdetect + freezedetect (obraz), ebur128 + silencedetect (dźwięk)."""
    vf = "[0:v]blackdetect=d=0.4:pix_th=0.10,freezedetect=n=0.003:d=2[v]"
    args = ["ffmpeg", "-nostdin", "-hide_banner", "-i", str(path)]
    if has_audio:
        args += ["-filter_complex", f"{vf};[0:a]ebur128=peak=true,silencedetect=noise=-45dB:d=1.5[a]", "-map", "[v]", "-map", "[a]"]
    else:
        args += ["-filter_complex", vf, "-map", "[v]"]
    res = subprocess.run(args + ["-f", "null", "-"], capture_output=True, text=True)
    log = res.stderr
    out: dict = {"czarne": [], "zamrozone": [], "cisze": []}
    for m in re.finditer(r"black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)", log):
        out["czarne"].append([float(m.group(1)), float(m.group(2))])
    fz = re.findall(r"freeze_start: ([\d.]+)|freeze_end: ([\d.]+)", log)
    starts = [float(a) for a, _ in fz if a]
    ends = [float(b) for _, b in fz if b]
    out["zamrozone"] = [[s, ends[i] if i < len(ends) else None] for i, s in enumerate(starts)]
    ss = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    se = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    out["cisze"] = [[s, se[i] if i < len(se) else None] for i, s in enumerate(ss)]
    summary = log.split("Summary:")[-1] if "Summary:" in log else ""
    m = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    out["lufs"] = float(m.group(1)) if m else None
    m = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    out["true_peak"] = float(m.group(1)) if m and m.group(1) != "-inf" else None
    return out


def zones(w: int, h: int) -> list[tuple[int, int, int, int]]:
    """Strefy zasłaniane przez interfejs 9:16 (TikTok/Reels/Shorts): góra, dół z opisem, prawy pasek przycisków."""
    if h <= w:
        return []
    return [(0, 0, w, int(h * 0.10)), (0, int(h * 0.80), w, h - int(h * 0.80)), (int(w * 0.86), int(h * 0.45), w - int(w * 0.86), int(h * 0.35))]


def sheet(path: Path, dur: float, w: int, h: int, out: Path, marks: bool) -> Path:
    times = sorted({0.0, 0.5, 1.5, dur * 0.25, dur * 0.5, dur * 0.75, max(0.0, dur - 0.5)})
    times = [t for t in times if t < dur]
    cw = 270 if h > w else 480
    ch = wl.even(cw * h / w)
    draw = ""
    if marks:
        sx, sy = cw / w, ch / h
        draw = "".join(f",drawbox=x={int(x * sx)}:y={int(y * sy)}:w={int(bw * sx)}:h={int(bh * sy)}:color=red@0.28:t=fill"
                       for x, y, bw, bh in zones(w, h))
    with tempfile.TemporaryDirectory(prefix="jarvo-qa-") as tmp:
        for i, t in enumerate(times):
            label = f"{t:.1f}s"
            base = f"scale={cw}:{ch}{draw}"
            cell = Path(tmp) / f"c{i:02d}.png"
            try:
                wl.run(["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", "-vf",
                        base + f",drawtext=text='{label}':x=6:y=6:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=4",
                        str(cell)])
            except wl.FFError:
                wl.run(["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", "-vf", base, str(cell)])
        cols = min(4, len(times))
        rows = (len(times) + cols - 1) // cols
        out.parent.mkdir(parents=True, exist_ok=True)
        wl.run(["ffmpeg", "-y", "-framerate", "1", "-i", str(Path(tmp) / "c%02d.png"), "-vf",
                f"tile={cols}x{rows}:padding=4:color=0x0B0D12", "-frames:v", "1", "-q:v", "3", str(out)])
    return out


def check(path: Path, platform: str | None, fmt: str | None, voiced: bool, arkusz: Path | None) -> dict:
    errors, warns = [], []
    info = wl.probe(path)
    v, a = info["video"], info["audio"]
    dur = info["duration"]
    if not v:
        return {"plik": str(path), "ok": False, "bledy": ["brak ścieżki wideo"], "ostrzezenia": []}
    if platform:
        pf, max_s, (lo, hi) = PLATFORMS[platform]
        fmt = fmt or pf
        if dur > max_s:
            errors.append(f"{platform}: {dur:.1f} s > limit {max_s} s")
        elif not lo <= dur <= hi:
            warns.append(f"{platform}: {dur:.1f} s poza zalecanym zakresem {lo}–{hi} s")
    if fmt:
        tw, th = wl.parse_format(fmt)
        if (v["width"], v["height"]) != (tw, th):
            if v["width"] * th == v["height"] * tw:
                warns.append(f"rozdzielczość {v['width']}×{v['height']} (proporcje dobre, docelowo {tw}×{th})")
            else:
                errors.append(f"rozdzielczość {v['width']}×{v['height']}, format {fmt} wymaga {tw}×{th}")
    if v["codec"] != "h264":
        errors.append(f"kodek wideo {v['codec']} (platformy: H.264)")
    if v["pix_fmt"] != "yuv420p":
        errors.append(f"pix_fmt {v['pix_fmt']} (wymagane yuv420p, inaczej część telefonów nie odtworzy)")
    if not 23.9 <= (v["fps"] or 0) <= 60.1:
        warns.append(f"fps {v['fps']} (zalecane 24–60, standard 30)")
    if not a:
        (errors if voiced else warns).append("brak ścieżki audio (platformy wyciszają albo odrzucają)")
    elif a["codec"] != "aac":
        warns.append(f"kodek audio {a['codec']} (zalecany AAC)")
    if path.suffix.lower() in (".mp4", ".mov", ".m4v") and not moov_first(path):
        warns.append("brak faststart (moov na końcu): dodaj -movflags +faststart")
    an = analyze(path, bool(a))
    if a and an["lufs"] is not None:
        if not LUFS_OK[0] <= an["lufs"] <= LUFS_OK[1]:
            (errors if an["lufs"] < -20 or an["lufs"] > -10 else warns).append(
                f"głośność {an['lufs']} LUFS (cel −14, zakres {LUFS_OK[0]}…{LUFS_OK[1]}): montaz.py glosnosc")
        if an["true_peak"] is not None and an["true_peak"] > TRUE_PEAK_MAX:
            warns.append(f"true peak {an['true_peak']} dBFS > {TRUE_PEAK_MAX} (przester na telefonie)")
    for s, e in an["czarne"]:
        if s < 0.3:
            errors.append(f"czarny początek {s:.1f}–{e:.1f} s: pierwsza klatka to miniatura i hook")
        elif e - s >= 0.8 and e < dur - 0.3:
            warns.append(f"czarne klatki {s:.1f}–{e:.1f} s")
    for s, e in an["zamrozone"]:
        warns.append(f"zamrożony obraz od {s:.1f} s{f' do {e:.1f} s' if e else ''} (statyczna scena > 2 s nuży)")
    if voiced:
        for s, e in an["cisze"]:
            if (e or dur) - s >= 2.0:
                warns.append(f"cisza {s:.1f}–{(e or dur):.1f} s w filmie z lektorem")
    res = {"plik": str(path), "ok": not errors, "bledy": errors, "ostrzezenia": warns,
           "metryki": {"sek": round(dur, 2), "rozdzielczosc": f"{v['width']}x{v['height']}", "fps": v["fps"],
                       "wideo": v["codec"], "audio": a and a["codec"], "mb": round(info["size"] / 1048576, 2),
                       "lufs": an["lufs"], "true_peak": an["true_peak"]}}
    if arkusz:
        res["arkusz"] = str(sheet(path, dur, v["width"], v["height"], arkusz, marks=True))
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plik", nargs="+")
    ap.add_argument("--platforma", choices=sorted(PLATFORMS))
    ap.add_argument("--format", help="9:16 | 16:9 | 1:1 | 4:5 (domyślnie z platformy)")
    ap.add_argument("--lektor", action="store_true", help="film z lektorem: brak audio i długie cisze to błąd/ostrzeżenie")
    ap.add_argument("--arkusz", help="JPG z klatkami i strefami UI (przy wielu plikach: katalog)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    wl.need("ffmpeg")
    results = []
    for f in args.plik:
        ark = None
        if args.arkusz:
            ark = Path(args.arkusz)
            if len(args.plik) > 1:
                ark = ark / f"qa-{Path(f).stem}.jpg"
        results.append(check(Path(f), args.platforma, args.format, args.lektor, ark))
    if args.json:
        print(json.dumps(results if len(results) > 1 else results[0], ensure_ascii=False, indent=1))
    else:
        for r in results:
            print(f"{'✓' if r['ok'] else '✗'} {r['plik']}  {json.dumps(r.get('metryki', {}), ensure_ascii=False)}")
            for e in r["bledy"]:
                print(f"   ✗ {e}")
            for w in r["ostrzezenia"]:
                print(f"   ! {w}")
            if r.get("arkusz"):
                print(f"   arkusz: {r['arkusz']}")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
