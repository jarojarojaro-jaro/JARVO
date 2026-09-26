#!/usr/bin/env python3
"""Napisy do wideo: transkrypcja (Parakeet przez tars-stt) → SRT → opcjonalne wypalenie (FFmpeg).

    python3 subtitles.py <wideo.mp4> [--max-chars 32] [--burn] [--style "FontSize=18,Outline=2"]

Wynik: <wideo>.srt (do korekty!) i przy --burn: <wideo>.napisy.mp4.
Transkrypcję robi /opt/tars/bin/tars-stt (Parakeet TDT 0.6B v3 int8, CPU, sam rozpoznaje język).
Model (~0,65 GB) pobiera się przy pierwszym użyciu do /opt/data/tars/models; w trakcie ok. 1,2 GB RAM.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

STT = os.environ.get("TARS_STT_BIN", "/opt/tars/bin/tars-stt")


def transcribe(video: Path, max_chars: int) -> Path:
    stt = STT if os.path.exists(STT) else shutil.which("tars-stt")
    if not stt:
        raise SystemExit("Brak tars-stt (obraz TARS: /opt/tars/bin/tars-stt).")
    srt = video.with_suffix(".srt")
    subprocess.run([stt, str(video), "--srt", str(srt), "--max-chars", str(max_chars)], check=True)
    return srt


def burn(video: Path, srt: Path, style: str) -> Path:
    out = video.with_name(video.stem + ".napisy.mp4")
    vf = f"subtitles={srt.as_posix()}:force_style='{style}'"
    subprocess.run(["ffmpeg", "-y", "-i", str(video), "-vf", vf, "-c:v", "libx264", "-crf", "20",
                    "-preset", "medium", "-c:a", "copy", str(out)], check=True)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--lang", default="", help="ignorowane: Parakeet sam rozpoznaje język")
    ap.add_argument("--max-chars", type=int, default=32, help="maks. znaków w linii napisu (telefon: 28–36)")
    ap.add_argument("--burn", action="store_true")
    ap.add_argument("--srt", help="użyj istniejącego (poprawionego) SRT zamiast transkrypcji")
    ap.add_argument("--style", default="FontName=Inter,FontSize=16,Bold=1,Outline=2,Shadow=0,MarginV=60,Alignment=2")
    args = ap.parse_args(argv)
    video = Path(args.video)
    srt = Path(args.srt) if args.srt else transcribe(video, args.max_chars)
    print(f"SRT: {srt}")
    if args.burn:
        print(f"Wideo z napisami: {burn(video, srt, args.style)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
