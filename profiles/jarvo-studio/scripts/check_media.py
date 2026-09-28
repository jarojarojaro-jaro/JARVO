#!/usr/bin/env python3
"""Kontrola plików mediów względem specyfikacji platform (ffprobe; bez dodatkowych bibliotek).

    python3 check_media.py <plik|katalog> [--spec ig-post] [--auto] [--max-mb 8] [--json]

--spec   sprawdza wszystkie pliki względem jednego klucza z tabeli SPECS
--auto   dobiera spec po wymiarach pliku (i ostrzega, gdy żaden nie pasuje)
Kod wyjścia 1, gdy jest błąd (zły wymiar, za długie wideo, plik nieczytelny).
Tabela jest zsynchronizowana z skills/studio/formaty-platform/references/specs.md.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# spec: (szer, wys, max_sek_wideo albo None)
SPECS = {
    "ig-post": (1080, 1350, None), "ig-square": (1080, 1080, None), "ig-story": (1080, 1920, 60),
    "ig-reel": (1080, 1920, 180), "tiktok": (1080, 1920, 600), "yt-short": (1080, 1920, 180),
    "yt-thumb": (1280, 720, None), "yt-video": (1920, 1080, None), "li-post": (1200, 627, None),
    "li-video": (1080, 1350, 600), "x-post": (1600, 900, None), "fb-post": (1080, 1350, None),
    "og": (1200, 630, None), "email-hero": (1200, 600, None),
}
MEDIA_EXT = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".mp4", ".mov", ".webm"}


def probe(path: Path) -> dict:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration,size",
           "-of", "json", str(path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip()[:200] or "ffprobe error")
    data = json.loads(res.stdout)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    dur = float(data.get("format", {}).get("duration") or 0)
    is_video = path.suffix.lower() in {".mp4", ".mov", ".webm"} or (dur > 0.5 and path.suffix.lower() == ".gif")
    return {"width": video.get("width"), "height": video.get("height"), "codec": video.get("codec_name"),
            "duration": round(dur, 2) if is_video else None, "audio": bool(audio), "is_video": is_video,
            "bytes": path.stat().st_size}


def match_spec(w: int, h: int) -> list[str]:
    return [k for k, (sw, sh, _) in SPECS.items() if (sw, sh) == (w, h)]


def check_file(path: Path, spec: str | None, auto: bool, max_mb: float) -> dict:
    out = {"file": str(path), "errors": [], "warnings": []}
    try:
        info = probe(path)
    except Exception as exc:
        out["errors"].append(f"nieczytelny plik: {exc}")
        return out
    out.update(info)
    specs = [spec] if spec else (match_spec(info["width"] or 0, info["height"] or 0) if auto else [])
    if auto and not specs:
        out["warnings"].append(f"wymiary {info['width']}×{info['height']} nie pasują do żadnej specyfikacji platform")
    for s in specs:
        sw, sh, max_s = SPECS[s]
        if (info["width"], info["height"]) != (sw, sh):
            out["errors"].append(f"{s}: wymiary {info['width']}×{info['height']}, oczekiwane {sw}×{sh}")
        if info["is_video"] and max_s and info["duration"] and info["duration"] > max_s:
            out["errors"].append(f"{s}: wideo {info['duration']} s > limit {max_s} s")
    out["specs"] = specs
    if info["bytes"] > max_mb * 1024 * 1024:
        out["warnings"].append(f"plik {info['bytes'] / 1048576:.1f} MB > {max_mb} MB")
    if info["is_video"]:
        if info["codec"] not in {"h264", "hevc", "vp9", "av1"}:
            out["warnings"].append(f"kodek wideo {info['codec']} (zalecany h264)")
        if not info["audio"]:
            out["warnings"].append("brak ścieżki audio (ok dla GIF-owych animacji; reels/TikTok zwykle z dźwiękiem)")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target")
    ap.add_argument("--spec", choices=sorted(SPECS))
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--max-mb", type=float, default=8.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    target = Path(args.target)
    files = sorted(p for p in (target.rglob("*") if target.is_dir() else [target]) if p.suffix.lower() in MEDIA_EXT)
    results = [check_file(f, args.spec, args.auto, args.max_mb) for f in files]
    errors = sum(len(r["errors"]) for r in results)
    if args.json:
        print(json.dumps({"files": results, "errors": errors}, ensure_ascii=False, indent=1))
    else:
        for r in results:
            status = "BŁĄD" if r["errors"] else ("uwaga" if r["warnings"] else "ok")
            dims = f"{r.get('width')}×{r.get('height')}" if r.get("width") else "?"
            dur = f" {r['duration']}s" if r.get("duration") else ""
            print(f"[{status}] {r['file']} {dims}{dur} {','.join(r.get('specs', []))}")
            for m in r["errors"] + r["warnings"]:
                print(f"    - {m}")
        print(f"PODSUMOWANIE: {len(results)} plików, {errors} błędów")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
