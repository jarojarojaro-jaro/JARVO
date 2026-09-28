#!/usr/bin/env python3
"""Rytm muzyki: tempo (BPM), siatka bitów, takty i „drop”: pod nie układasz cięcia i ruch.

    python3 rytm.py muzyka.mp3 [--json out/wideo/src/rytm.json] [--od 0 --do 60]
    python3 rytm.py film-wzor.mp4                 # też z dźwięku filmu (np. wzór do rozpisania na bity)

Wynik: BPM, pierwszy bit (faza), czasy bitów, początki taktów (co 4 bity), drop (najmocniejsze wejście po
spokojniejszym fragmencie) i propozycja cięć: co takt, a na dropie najmocniejsza scena. Liczy na obwiedni
energii dźwięku (ffmpeg dekoduje 8 kHz mono, Python liczy; bez numpy i bez sieci). Muzyka elektroniczna
i pop ze stałym tempem: pewnie; swobodne tempo (akustyka, mowa): traktuj jako wskazówkę i sprawdź uchem.
"""

from __future__ import annotations

import argparse
import array
import json
import math
import subprocess
import sys
from pathlib import Path

SR = 8000          # próbkowanie do analizy
HOP = 80           # 10 ms: obwiednia 100 wartości na sekundę
ENV_SR = SR / HOP


def envelope(path: Path, start: float = 0.0, end: float | None = None) -> list[float]:
    """Energia (RMS) w oknach 10 ms."""
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", str(start), "-i", str(path)]
    if end is not None:
        cmd += ["-t", str(max(0.1, end - start))]
    cmd += ["-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=False).stdout
    if len(raw) < SR:
        raise SystemExit(f"za mało dźwięku w {path} (brak ścieżki audio?)")
    pcm = array.array("h")
    pcm.frombytes(raw[: len(raw) - len(raw) % 2])
    return [math.sqrt(sum(x * x for x in pcm[i:i + HOP]) / HOP) for i in range(0, len(pcm) - HOP + 1, HOP)]


def onsets(env: list[float]) -> list[float]:
    """Siła uderzeń: przyrost energii (log) względem średniej z ostatnich 100 ms, tylko dodatni."""
    lg = [math.log1p(x) for x in env]
    out = [0.0] * len(lg)
    for i in range(1, len(lg)):
        ref = sum(lg[max(0, i - 10):i]) / min(i, 10)
        out[i] = max(0.0, lg[i] - ref)
    return out


def tempo(on: list[float], lo: int = 70, hi: int = 180) -> float:
    """BPM z autokorelacji obwiedni uderzeń (lag w oknach 10 ms), z lekką preferencją 90–140 BPM."""
    n = len(on)
    mean = sum(on) / n
    x = [v - mean for v in on]
    best, best_bpm = -1e18, 120.0
    for bpm in range(lo, hi + 1):
        lag = ENV_SR * 60 / bpm
        l0 = int(lag)
        frac = lag - l0
        s = 0.0
        for i in range(n - l0 - 1):
            s += x[i] * (x[i + l0] * (1 - frac) + x[i + l0 + 1] * frac)
        s /= max(1, n - l0)
        s *= 1.0 + 0.15 * math.exp(-((bpm - 118) / 30) ** 2)
        if s > best:
            best, best_bpm = s, bpm
    # dokładniej: przeszukanie co 0.1 wokół zwycięzcy
    fine = [best_bpm + d / 10 for d in range(-9, 10)]
    def score(bpm):
        lag = ENV_SR * 60 / bpm
        l0, frac = int(lag), lag - int(lag)
        return sum(x[i] * (x[i + l0] * (1 - frac) + x[i + l0 + 1] * frac) for i in range(n - l0 - 1))
    return round(max(fine, key=score), 1)


def phase(on: list[float], bpm: float) -> float:
    """Pierwszy bit: przesunięcie, przy którym uderzenia najlepiej trafiają w siatkę."""
    period = ENV_SR * 60 / bpm
    best, best_off = -1.0, 0.0
    steps = max(1, int(period))
    for k in range(steps):
        s, pos = 0.0, float(k)
        while pos < len(on):
            i = int(round(pos))
            s += max(on[max(0, i - 1):i + 2] or [0])
            pos += period
        if s > best:
            best, best_off = s, k
    return best_off / ENV_SR


def refine(on: list[float], first: float, period: float, dur: float) -> tuple[float, float]:
    """Dopasowanie siatki do prawdziwych uderzeń: szczyt w ±40 ms od każdego bitu, potem prosta (najmniejsze
    kwadraty) czas = pierwszy + k·okres. Bez tego 0,3 BPM błędu to pół sekundy rozjazdu po 3 minutach."""
    pts = []
    k = 0
    while first + k * period < dur:
        c = int(round((first + k * period) * ENV_SR))
        win = range(max(0, c - 4), min(len(on), c + 5))
        if win:
            i = max(win, key=lambda j: on[j])
            if on[i] > 0:
                pts.append((k, i / ENV_SR, on[i]))
        k += 1
    if len(pts) < 8:
        return first, period
    top = sorted(p[2] for p in pts)[len(pts) // 2]          # tylko wyraźne uderzenia (górna połowa)
    pts = [(kk, t) for kk, t, v in pts if v >= top]
    n = len(pts)
    mk, mt = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    var = sum((p[0] - mk) ** 2 for p in pts)
    if var == 0:
        return first, period
    per = sum((p[0] - mk) * (p[1] - mt) for p in pts) / var
    if abs(per - period) > period * 0.03:                   # dopasowanie uciekło: zostaje autokorelacja
        return first, period
    return max(0.0, mt - per * mk), per


def downbeat(on: list[float], beats: list[float]) -> int:
    """Który z pierwszych 4 bitów zaczyna takt: ten, po którym co 4. bit uderza najmocniej."""
    def at(t):
        i = int(round(t * ENV_SR))
        return max(on[max(0, i - 2):i + 3] or [0])
    return max(range(min(4, len(beats))), key=lambda k: sum(at(t) for t in beats[k::4]))


def drop(env: list[float], bars: list[float]) -> float | None:
    """Drop: początek taktu z największym skokiem średniej energii (2 takty po vs 2 takty przed)."""
    if len(bars) < 5:
        return None
    def mean(a, b):
        i, j = int(a * ENV_SR), int(b * ENV_SR)
        seg = env[i:j]
        return sum(seg) / len(seg) if seg else 0.0
    best, best_t = 0.0, None
    for k in range(2, len(bars) - 2):
        before, after = mean(bars[k - 2], bars[k]), mean(bars[k], bars[k + 2])
        if before > 0 and after / before > best:
            best, best_t = after / before, bars[k]
    return best_t if best >= 1.25 else None


def analyze(path: Path, start: float = 0.0, end: float | None = None) -> dict:
    env = envelope(path, start, end)
    on = onsets(env)
    dur = len(env) / ENV_SR
    bpm = tempo(on)
    first = phase(on, bpm)
    period = 60 / bpm
    first, period = refine(on, first, period, dur)
    bpm = round(60 / period, 1)
    beats = [round(start + first + k * period, 3) for k in range(int((dur - first) / period) + 1)]
    rel = [b - start for b in beats]
    db = downbeat(on, rel)
    bars = beats[db::4]
    d = drop(env, [b - start for b in bars])
    return {"plik": str(path), "bpm": bpm, "bit_s": round(period, 4), "pierwszy_bit": beats[0] if beats else None,
            "bity": beats, "takty": bars, "drop": round(start + d, 3) if d is not None else None,
            "ciecia": {"co_takt": bars, "co_2_bity": beats[db::2]}, "dlugosc": round(dur, 2)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plik")
    ap.add_argument("--od", type=float, default=0.0)
    ap.add_argument("--do", type=float)
    ap.add_argument("--json", help="zapisz wynik do pliku JSON")
    a = ap.parse_args(argv)
    r = analyze(Path(a.plik), a.od, a.do)
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    bars = ", ".join(f"{t:.2f}" for t in r["takty"][:12]) + (" …" if len(r["takty"]) > 12 else "")
    print(f"{Path(a.plik).name}: {r['bpm']} BPM (bit co {r['bit_s']:.3f} s), pierwszy bit {r['pierwszy_bit']:.2f} s")
    print(f"Takty (tu cięcia): {bars}")
    print(f"Drop: {r['drop']:.2f} s (tu najmocniejsza scena)" if r["drop"] is not None else "Drop: nie wykryto wyraźnego")
    return 0


if __name__ == "__main__":
    sys.exit(main())
