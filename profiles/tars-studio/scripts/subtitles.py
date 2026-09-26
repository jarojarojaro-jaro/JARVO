#!/usr/bin/env python3
"""Napisy do wideo: transkrypcja (faster-whisper) → SRT → opcjonalne wypalenie (FFmpeg).

    python3 subtitles.py <wideo.mp4> [--lang pl] [--model small] [--burn] [--style "FontSize=18,Outline=2"]

Wynik: <wideo>.srt (do korekty!) i przy --burn: <wideo>.napisy.mp4.
faster-whisper jest w środowisku /opt/tars/venv (infra/Dockerfile). Model pobiera się przy pierwszym
użyciu do ~/.cache/huggingface (small ≈ 0,5 GB). Działa na CPU.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def fmt(t: float) -> str:
    h, rem = divmod(int(t), 3600)
    m, s = divmod(rem, 60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe(video: Path, lang: str, model_name: str, max_chars: int) -> Path:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        venv_py = "/opt/tars/venv/bin/python"
        if os.path.exists(venv_py) and sys.executable != venv_py:
            os.execv(venv_py, [venv_py, *sys.argv])
        raise SystemExit("Brak faster-whisper (zainstaluj w /opt/tars/venv).")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(video), language=lang, vad_filter=True, word_timestamps=True)
    lines, idx = [], 1
    for seg in segments:
        words = list(seg.words or [])
        if not words:
            lines.append((idx, seg.start, seg.end, seg.text.strip()))
            idx += 1
            continue
        chunk, start = [], words[0].start
        for w in words:
            chunk.append(w.word.strip())
            if len(" ".join(chunk)) >= max_chars or w is words[-1]:
                lines.append((idx, start, w.end, " ".join(chunk)))
                idx += 1
                chunk, start = [], w.end
    srt = video.with_suffix(".srt")
    srt.write_text("".join(f"{i}\n{fmt(a)} --> {fmt(b)}\n{t}\n\n" for i, a, b, t in lines), encoding="utf-8")
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
    ap.add_argument("--lang", default="pl")
    ap.add_argument("--model", default="small")
    ap.add_argument("--max-chars", type=int, default=32, help="maks. znaków w linii napisu (telefon: 28–36)")
    ap.add_argument("--burn", action="store_true")
    ap.add_argument("--srt", help="użyj istniejącego (poprawionego) SRT zamiast transkrypcji")
    ap.add_argument("--style", default="FontName=Inter,FontSize=16,Bold=1,Outline=2,Shadow=0,MarginV=60,Alignment=2")
    args = ap.parse_args(argv)
    video = Path(args.video)
    srt = Path(args.srt) if args.srt else transcribe(video, args.lang, args.model, args.max_chars)
    print(f"SRT: {srt}")
    if args.burn:
        print(f"Wideo z napisami: {burn(video, srt, args.style)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
