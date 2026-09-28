#!/usr/bin/env python3
"""Klatki do oceny okiem (vision_analyze) i cięcia ujęć: arkusz klatek z wielu klipów, lista zmian scen.

    python3 kadry.py arkusz klip1.mp4 [klip2.mp4 …] [--klatek 4] [-o out/wideo/kandydaci.jpg]
    python3 kadry.py sceny nagranie.mp4 [--prog 0.35] [--json]
    python3 kadry.py wzor film-wzor.mp4 [--fps 2] [-o out/wideo/wzor]   # film-wzór → klatki, cięcia, rytm

arkusz: każdy klip = jeden rząd klatek (równo rozłożonych), podpisany numerem klipu i czasem, żeby
w jednym obrazie porównać kandydatów na ujęcie (ostrość, kadr, znak wodny, tekst, pasuje do sceny?).
sceny: momenty cięć montażowych w gotowym nagraniu (do klipów z długiego materiału i wyboru fragmentów).
wzor: film, który ma być wzorem („zrób coś takiego dla naszego produktu”): arkusze klatek co 1/fps s z czasem
w rogu (do vision), cięcia i rytm muzyki (rytm.py) w wzor.json. Z tego rozpisujesz mapę bitów: przejścia,
ruch kamery, kolory, fonty, co na którym takcie; przenosisz strukturę, nigdy treści, logo ani assetów.
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


def contact_rows(videos: list[Path], per: int, out: Path, cell_w: int = 240) -> Path:
    with tempfile.TemporaryDirectory(prefix="jarvo-kadry-") as tmp:
        tdir = Path(tmp)
        n = 0
        for vi, video in enumerate(videos, 1):
            info = wl.probe(video)
            v = info["video"] or {}
            ratio = (v.get("height") or 9) / (v.get("width") or 16)
            cell_h = wl.even(min(cell_w * ratio, cell_w * 1.8))
            dur = info["duration"] or 1.0
            times = [0.2] if wl.is_image(video) else [dur * (k + 0.5) / per for k in range(per)]
            for k in range(per):
                t = times[min(k, len(times) - 1)]
                label = f"{vi}.{k + 1} {t:.1f}s"
                base = (f"scale={cell_w}:{cell_h}:force_original_aspect_ratio=decrease,"
                        f"pad={cell_w}:{wl.even(cell_w * 1.8)}:(ow-iw)/2:(oh-ih)/2:color=0x15171C")
                cell = tdir / f"c{n:03d}.png"
                seek = [] if wl.is_image(video) else ["-ss", f"{t:.2f}"]
                try:
                    wl.run(["ffmpeg", "-y", *seek, "-i", str(video), "-frames:v", "1", "-vf",
                            base + f",drawtext=text='{label}':x=6:y=6:fontsize=16:fontcolor=white:box=1:boxcolor=0xD62D20:boxborderw=4",
                            str(cell)])
                except wl.FFError:
                    wl.run(["ffmpeg", "-y", *seek, "-i", str(video), "-frames:v", "1", "-vf", base, str(cell)])
                n += 1
        out.parent.mkdir(parents=True, exist_ok=True)
        wl.run(["ffmpeg", "-y", "-framerate", "1", "-i", str(tdir / "c%03d.png"), "-vf",
                f"tile={per}x{len(videos)}:padding=4:color=0x0B0D12", "-frames:v", "1", "-q:v", "3", str(out)])
    return out


def scene_changes(video: Path, threshold: float) -> list[float]:
    res = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(video), "-an", "-vf",
                          f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"], capture_output=True, text=True)
    return [round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", res.stderr)]


def reference(video: Path, fps: float, out_dir: Path, per_sheet: int = 40, cols: int = 8) -> dict:
    """Film-wzór → arkusze klatek (czas w rogu), cięcia i rytm."""
    info = wl.probe(video)
    dur = info["duration"] or 0.0
    v = info["video"] or {}
    ratio = (v.get("height") or 9) / (v.get("width") or 16)
    cw = 240
    ch = wl.even(cw * ratio)
    n = max(1, int(dur * fps))
    out_dir.mkdir(parents=True, exist_ok=True)
    sheets = []
    for k, first in enumerate(range(0, n, per_sheet)):
        cnt = min(per_sheet, n - first)
        rows = (cnt + cols - 1) // cols
        dest = out_dir / f"wzor-{k + 1}.jpg"
        base = f"fps={fps},scale={cw}:{ch}"
        label = f",drawtext=text='%{{pts\\:hms\\:{first / fps:.3f}}}':x=4:y=4:fontsize=14:fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=3"
        tile = f",tile={cols}x{rows}:padding=4:color=0x0B0D12"
        common = ["ffmpeg", "-y", "-ss", f"{first / fps:.3f}", "-t", f"{cnt / fps:.3f}", "-i", str(video), "-frames:v", "1", "-q:v", "3"]
        try:
            wl.run(common[:-4] + ["-vf", base + label + tile] + common[-4:] + [str(dest)])
        except wl.FFError:   # bez fontu do drawtext: arkusz bez czasu (czas = kolejność × 1/fps od początku arkusza)
            wl.run(common[:-4] + ["-vf", base + tile] + common[-4:] + [str(dest)])
        sheets.append({"plik": str(dest), "od": round(first / fps, 2), "do": round((first + cnt) / fps, 2)})
    res = {"film": str(video), "sek": round(dur, 2), "co_s": round(1 / fps, 3), "arkusze": sheets,
           "ciecia": scene_changes(video, 0.35)}
    if info.get("audio"):
        try:
            import rytm
            r = rytm.analyze(video)
            res["rytm"] = {k: r[k] for k in ("bpm", "pierwszy_bit", "takty", "drop")}
        except SystemExit:
            pass
    (out_dir / "wzor.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("arkusz")
    a.add_argument("pliki", nargs="+")
    a.add_argument("--klatek", type=int, default=4)
    a.add_argument("-o", default="out/wideo/kandydaci.jpg")
    s = sub.add_parser("sceny")
    s.add_argument("plik")
    s.add_argument("--prog", type=float, default=0.35, help="czułość cięć 0–1 (niżej = więcej cięć)")
    s.add_argument("--json", action="store_true")
    w = sub.add_parser("wzor")
    w.add_argument("plik")
    w.add_argument("--fps", type=float, default=2.0, help="klatek na sekundę wzoru (2 = co 0,5 s)")
    w.add_argument("-o", default="out/wideo/wzor", help="katalog na arkusze i wzor.json")
    args = ap.parse_args(argv)
    wl.need("ffmpeg")
    try:
        if args.cmd == "arkusz":
            vids = [Path(p) for p in args.pliki]
            missing = [str(p) for p in vids if not p.exists()]
            if missing:
                raise SystemExit(f"Brak plików: {', '.join(missing)}")
            out = contact_rows(vids, max(1, min(args.klatek, 8)), Path(args.o))
            print(f"Arkusz: {out}  (rząd N = klip N: " + ", ".join(f"{i}={p.name}" for i, p in enumerate(vids, 1)) + ")")
            return 0
        if args.cmd == "wzor":
            r = reference(Path(args.plik), max(0.25, min(args.fps, 10)), Path(args.o))
            print(f"Wzór {r['sek']} s: {len(r['arkusze'])} arkuszy (klatka co {r['co_s']} s), {len(r['ciecia'])} cięć")
            for sh in r["arkusze"]:
                print(f"  {sh['plik']}  ({sh['od']}–{sh['do']} s)")
            if r.get("rytm"):
                print(f"  rytm: {r['rytm']['bpm']} BPM, drop {r['rytm']['drop']} s")
            print(f"  → {Path(args.o) / 'wzor.json'}: rozpisz mapę bitów (przejścia, kamera, kolory, fonty) i przenieś na produkt")
            return 0
        cuts = scene_changes(Path(args.plik), args.prog)
        dur = wl.duration(Path(args.plik))
        bounds = [0.0] + cuts + [round(dur, 2)]
        shots = [{"nr": i + 1, "od": bounds[i], "do": bounds[i + 1], "sek": round(bounds[i + 1] - bounds[i], 2)}
                 for i in range(len(bounds) - 1) if bounds[i + 1] - bounds[i] > 0.05]
        if args.json:
            print(json.dumps({"ciecia": cuts, "ujecia": shots}, ensure_ascii=False, indent=1))
        else:
            for sh in shots:
                print(f"{sh['nr']:>3}. {sh['od']:>7.2f}–{sh['do']:<7.2f} ({sh['sek']} s)")
        return 0
    except wl.FFError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
