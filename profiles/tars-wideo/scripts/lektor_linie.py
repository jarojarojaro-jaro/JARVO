#!/usr/bin/env python3
"""Polski lektor dla lemo-opuscar (i innych silników z listą linii): zamiennik core/tts/tts.py + asr_check.py.

    python3 lektor_linie.py <projekt>/lines.json <projekt>/voices [--glos pl-PL-ZofiaNeural] [--tempo +5%] [--sprawdz]

lines.json jak w lemo-opuscar: [{"id": "l01", "text": "…", "voice": "…", "speed": 0.95}, …]
(voice z Kokoro, np. af_kore, jest ignorowany: głos PL z --glos albo pola "glos" w linii; speed → tempo).
Wynik jak w lemo: voices/<id>.wav (24 kHz mono, bez ciszy na brzegach), voices/dur.json i voices/words.json
({id: [[słowo, start, koniec], …]}): czasy słów prosto z Edge TTS, bez whispera.
--sprawdz: kontrola wymowy Parakeetem (tars-stt), linie rozpoznane inaczej = DIFF (zmień zapis i powtórz).
Kokoro mówi po angielsku i chińsku; do polskiego filmu zawsze ten skrypt.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wideo_lib as wl  # noqa: E402


def norm(s: str) -> list[str]:
    return re.sub(r"[^\w ]", "", s.lower().replace("-", " ")).split()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lines")
    ap.add_argument("out")
    ap.add_argument("--glos", default=wl.DEFAULT_VOICE)
    ap.add_argument("--tempo", default=None, help="np. +5%% (domyślnie z pola speed linii)")
    ap.add_argument("--sprawdz", action="store_true", help="kontrola wymowy Parakeetem")
    args = ap.parse_args(argv)
    lines = json.loads(Path(args.lines).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    items = []
    for ln in lines:
        rate = args.tempo or f"{round((float(ln.get('speed', 1.0)) - 1) * 100):+d}%"
        items.append({"text": ln["text"], "voice": ln.get("glos", args.glos), "rate": rate})
    speeches = wl.speak_many(items)
    dur, words, bad = {}, {}, 0
    for ln, sp in zip(lines, speeches):
        wav = out / f"{ln['id']}.wav"
        # przycięcie ciszy na brzegach jak w tts.py lemo (atak 30 ms, ogon 80 ms)
        wl.run(["ffmpeg", "-y", "-i", str(sp.audio), "-af",
                "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.03,"
                "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.08,areverse",
                "-ar", "24000", "-ac", "1", str(wav)])
        dur[ln["id"]] = round(wl.duration(wav), 3)
        lead = sp.words[0].start - 0.03 if sp.words else 0.0
        words[ln["id"]] = [[w.text, round(max(0.0, w.start - lead), 3), round(max(0.0, w.end - lead), 3)] for w in sp.words]
        status = ""
        if args.sprawdz:
            got = " ".join(w.text for w in wl.transcribe_words(wav))
            ok = norm(got) == norm(ln.get("asr", ln["text"]))
            bad += not ok
            status = f"{'OK  ' if ok else 'DIFF'} → {got}"
        print(ln["id"], dur[ln["id"]], ln["text"], status)
    (out / "dur.json").write_text(json.dumps(dur, indent=1), encoding="utf-8")
    (out / "words.json").write_text(json.dumps(words, ensure_ascii=False, indent=0), encoding="utf-8")
    if args.sprawdz:
        print("rozbieżności:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
