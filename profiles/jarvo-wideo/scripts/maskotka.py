#!/usr/bin/env python3
"""Mówiąca maskotka Jarvo: robot z polskim lektorem, oczy i wskaźnik głosu w rytm mowy, mruganie, kołysanie.

    python3 maskotka.py "Cześć, jestem Jarvo. Pokażę ci, co zbudujemy dziś." -o out/wideo/jarvo/mowi.mp4
    python3 maskotka.py --plik tekst.txt -o film.mp4 [--format 9x16|1x1|16x9] [--glos pl-PL-MarekNeural]
                        [--tlo "#0E121A"] [--akcent "#B8FF3D"] [--bez-napisow] [--fps 30]

Wynik: MP4 z lektorem (Edge TTS, czasy słów), napisami karaoke (napisy.py, poza strefami UI) i plikiem
<film>.slowa.json. Animacja jest czystą funkcją czasu: głośność lektora (obwiednia 100/s) steruje wskaźnikiem głosu
i poświatą oczu, mrugnięcia mają stałe chwile (powtarzalny render). Robot to prawdziwa grafika marki (pixel art,
skalowanie bez rozmycia). Do reklam i reelsów „Jarvo mówi”, intro/outro, odpowiedzi w social media.
Kod wyjścia: 0 ok, 2 złe wejście.
"""
from __future__ import annotations

import argparse
import array
import json
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wideo_lib as wl  # noqa: E402

HERE = Path(__file__).resolve().parent / "maskotka"
FORMATY = {"9x16": (1080, 1920), "1x1": (1080, 1080), "16x9": (1920, 1080)}
MRUGNIECIA_CO = 3.3          # s; stałe chwile mrugnięć (bez losowości)


def obwiednia(audio: Path, sr: int = 8000, hop: int = 80) -> list[float]:
    """RMS w oknach 10 ms, znormalizowane do 0..1 (95. percentyl = 1)."""
    raw = subprocess.run([wl.need("ffmpeg"), "-v", "error", "-i", str(audio), "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                         capture_output=True).stdout
    s = array.array("h", raw)
    env = [math.sqrt(sum(x * x for x in s[i:i + hop]) / hop) for i in range(0, len(s) - hop, hop)]
    top = sorted(env)[int(len(env) * 0.95)] if env else 1
    return [min(1.0, v / (top or 1)) for v in env]


def wygladz(env: list[float], t: float, okno: float = 0.05) -> float:
    i0, i1 = int((t - okno) * 100), int((t + okno) * 100)
    wart = [env[i] for i in range(max(0, i0), min(len(env), i1 + 1))]
    return sum(wart) / len(wart) if wart else 0.0


def mrug(t: float) -> float:
    """Skala pionowa oczu: 1 = otwarte, ~0.1 w środku mrugnięcia (0,14 s)."""
    faza = (t + 0.7) % MRUGNIECIA_CO
    return 1.0 - 0.9 * math.sin(math.pi * faza / 0.14) if faza < 0.14 else 1.0


def klatka(Image, ImageDraw, ImageFilter, baza, oczy, W, H, t, glos, tlo, akcent):
    img = Image.new("RGB", (W, H), tlo)
    skala = max(1, int(min(W * 0.62 / baza.width, H * 0.58 / baza.height)))
    rw, rh = baza.width * skala, baza.height * skala
    bob = math.sin(2 * math.pi * t / 2.4) * 0.012 * rh - glos * 0.01 * rh
    # pion: robot w górnych 2/3, stopy nad strefą napisów (napisy.py kładzie je ~70–78% wysokości)
    x, y = (W - rw) // 2, int(H * 0.64 - rh + bob) if H > W else int((H * 0.9 - rh) / 2 + bob)
    # cień kontaktowy (mniejszy, gdy robot „podskakuje” przy mocnej sylabie)
    cien = Image.new("L", (W, H), 0)
    ImageDraw.Draw(cien).ellipse([W / 2 - rw * 0.34, y + rh - rh * 0.02, W / 2 + rw * 0.34, y + rh + rh * 0.04], fill=110)
    img.paste((0, 0, 0), mask=cien.filter(ImageFilter.GaussianBlur(18)))
    ciało = baza.resize((rw, rh), Image.NEAREST)
    img.paste(ciało, (x, y), ciało)
    # oczy: mruganie + poświata sterowana głosem
    s = mrug(t)
    o = oczy.resize((rw, max(1, int(rh * s))), Image.NEAREST) if s < 1 else oczy.resize((rw, rh), Image.NEAREST)
    oy = y + int((rh - o.height) * 0.3) if s < 1 else y
    if glos > 0.05:
        blask = o.split()[3].filter(ImageFilter.GaussianBlur(10 * skala / 3))
        warstwa = Image.new("RGB", o.size, akcent)
        img.paste(warstwa, (x, oy), blask.point(lambda v: int(v * min(1.0, glos * 1.4))))
    img.paste(o, (x, oy), o)
    # wskaźnik głosu pod oczami: 5 słupków w kolorze akcentu
    ex0, ey0, ex1, ey1 = oczy.getbbox()
    cx, cy = x + (ex0 + ex1) / 2 * skala, y + (ey1 + 6) * skala
    d = ImageDraw.Draw(img)
    for k in range(5):
        wys = (1.5 + 9 * glos * (0.55 + 0.45 * math.sin(t * 23 + k * 1.7))) * skala
        bx = cx + (k - 2) * 5 * skala
        d.rectangle([bx - 1.5 * skala, cy - wys / 2, bx + 1.5 * skala, cy + wys / 2], fill=akcent)
    return img


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tekst", nargs="?")
    ap.add_argument("--plik")
    ap.add_argument("-o", "--wyjscie", required=True)
    ap.add_argument("--format", choices=list(FORMATY), default="9x16")
    ap.add_argument("--glos", default=wl.DEFAULT_VOICE)
    ap.add_argument("--tempo", default="+0%")
    ap.add_argument("--tlo", default="#0E121A")
    ap.add_argument("--akcent", default="#B8FF3D")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--ogon", type=float, default=0.8, help="sekundy ciszy na końcu (robot mruga, oddycha)")
    ap.add_argument("--bez-napisow", action="store_true")
    a = ap.parse_args(argv)
    tekst = Path(a.plik).read_text(encoding="utf-8").strip() if a.plik else (a.tekst or "").strip()
    if not tekst:
        print("✗ podaj tekst albo --plik", file=sys.stderr)
        return 2
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        print("✗ brak Pillow: python3 $HERMES_HOME/scripts/narzedzia.py instaluj html", file=sys.stderr)
        return 2
    W, H = FORMATY[a.format]
    mowa = wl.speak_many([{"text": tekst, "voice": a.glos, "rate": a.tempo}])[0]
    env = obwiednia(mowa.audio)
    dur = mowa.duration + a.ogon
    out = Path(a.wyjscie)
    out.parent.mkdir(parents=True, exist_ok=True)
    slowa = out.with_suffix(".slowa.json")
    wl.write_json(slowa, [w.__dict__ for w in mowa.words])
    baza = Image.open(HERE / "robot-front.png").convert("RGBA")
    oczy = Image.open(HERE / "robot-eyes.png").convert("RGBA")
    surowy = out.with_suffix(".bez-napisow.mp4") if not a.bez_napisow else out
    ff = subprocess.Popen([wl.need("ffmpeg"), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(a.fps), "-i", "-", "-i", str(mowa.audio), "-af", f"apad=pad_dur={a.ogon},loudnorm=I=-14:TP=-1.5",
                           "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                           "-t", f"{dur:.3f}", "-movflags", "+faststart", str(surowy)], stdin=subprocess.PIPE)
    for i in range(int(dur * a.fps)):
        t = i / a.fps
        ff.stdin.write(klatka(Image, ImageDraw, ImageFilter, baza, oczy, W, H, t, wygladz(env, t), a.tlo, a.akcent).tobytes())
    ff.stdin.close()
    if ff.wait():
        print("✗ ffmpeg nie złożył filmu", file=sys.stderr)
        return 2
    if not a.bez_napisow:
        r = subprocess.run([sys.executable, str(Path(__file__).with_name("napisy.py")), str(surowy), "--slowa", str(slowa),
                            "--wypal", "--akcent", a.akcent], capture_output=True, text=True)
        gotowy = surowy.with_name(surowy.stem + ".napisy.mp4")
        if r.returncode or not gotowy.exists():
            print(f"✗ napisy: {(r.stderr or r.stdout)[-300:]}", file=sys.stderr)
            return 2
        gotowy.replace(out)
    print(json.dumps({"film": str(out), "sek": round(dur, 2), "slowa": str(slowa), "format": a.format,
                      "glos": a.glos}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
