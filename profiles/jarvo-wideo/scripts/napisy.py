#!/usr/bin/env python3
"""Napisy PL do gotowego nagrania: transkrypcja (Parakeet) albo poprawiony SRT → ASS (karaoke/zwykłe) → wypalenie.

    python3 napisy.py nagranie.mp4                       # transkrypcja → nagranie.srt (do korekty!)
    python3 napisy.py nagranie.mp4 --srt poprawione.srt --wypal [--styl karaoke] [--akcent "#FFD400"]
    python3 napisy.py nagranie.mp4 --slowa lektor.slowa.json --wypal

Kolejność pracy: 1) transkrypcja → SRT, 2) korekta SRT (nazwy własne, liczby, interpunkcja), 3) --srt … --wypal.
Karaoke z SRT rozkłada czas linii na słowa proporcjonalnie (bez ponownej transkrypcji); z --slowa (czasy słów
z lektora albo z montaz.py transkrypcja) podświetlenie trafia co do słowa. Styl zgodny z film.py (strefy UI 9:16).
Wynik: <nagranie>.srt, <nagranie>.ass i przy --wypal: <nagranie>.napisy.mp4.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wideo_lib as wl  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plik")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--srt", help="użyj (poprawionego) SRT zamiast transkrypcji")
    src.add_argument("--slowa", help="JSON słów z czasem [{start,end,text}] (film.py lektor / montaz.py transkrypcja)")
    ap.add_argument("--wypal", action="store_true", help="wypal napisy w obraz (MP4)")
    ap.add_argument("--styl", choices=["karaoke", "zwykle"], default="karaoke")
    ap.add_argument("--kolor", default="#FFFFFF")
    ap.add_argument("--akcent", default="#FFD400")
    ap.add_argument("--font", default="Inter")
    ap.add_argument("--font-plik", help="plik fontu marki (TTF/OTF)")
    ap.add_argument("--pozycja", choices=["dol", "srodek", "gora"], default="dol")
    ap.add_argument("--male", action="store_true", help="bez WIELKICH LITER")
    ap.add_argument("--rozmiar", type=float, default=1.0)
    args = ap.parse_args(argv)
    wl.need("ffmpeg")
    video = Path(args.plik)
    if not video.exists():
        raise SystemExit(f"Brak pliku: {video}")
    if args.slowa:
        words = [wl.Word(float(w["start"]), float(w["end"]), str(w.get("text") or w.get("word"))) for w in
                 json.loads(Path(args.slowa).read_text(encoding="utf-8"))]
    elif args.srt:
        words = wl.words_from_lines(wl.parse_srt(Path(args.srt).read_text(encoding="utf-8")))
    else:
        words = wl.transcribe_words(video)
    if not words:
        raise SystemExit("Brak słów (cisza albo pusty SRT).")
    srt_out = video.with_suffix(".srt")
    if not args.srt or Path(args.srt).resolve() != srt_out.resolve():
        srt_out.write_text(wl.build_srt(words), encoding="utf-8")
    info = wl.probe(video)["video"] or {}
    w, h = info.get("width") or 1080, info.get("height") or 1920
    style = wl.SubStyle(styl=args.styl, font=args.font, kolor=args.kolor, akcent=args.akcent, pozycja=args.pozycja,
                        wielkie=not args.male, rozmiar=args.rozmiar)
    ass = video.with_suffix(".ass")
    ass.write_text(wl.build_ass(w, h, words, style), encoding="utf-8")
    result = {"srt": str(srt_out), "ass": str(ass), "slowa": len(words)}
    if args.wypal:
        out = video.with_name(video.stem + ".napisy.mp4")
        with tempfile.TemporaryDirectory(prefix="jarvo-napisy-") as tmp:
            shutil.copy2(ass, Path(tmp) / "n.ass")
            extra = ""
            if args.font_plik:
                (Path(tmp) / "fonts").mkdir()
                shutil.copy2(args.font_plik, Path(tmp) / "fonts")
                extra = ":fontsdir=fonts"
            audio = ["-c:a", "copy"] if wl.probe(video)["audio"] else []
            wl.run(["ffmpeg", "-y", "-i", str(video.resolve()), "-vf", f"ass=n.ass{extra},{wl.TV_RANGE}", "-c:v", "libx264", "-preset", "medium",
                    "-crf", "19", "-pix_fmt", "yuv420p", *wl.ENC_LIMITS, *audio, "-movflags", "+faststart", str(out.resolve())],
                   cwd=Path(tmp))
        result["wideo"] = str(out)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
