#!/usr/bin/env python3
"""Kontrola techniczna filmu przed oddaniem: jedno przejście FFmpeg, wynik w JSON i arkusz klatek do oceny okiem.

    python3 qa_wideo.py film.mp4 [--platforma tiktok] [--format 9:16] [--lektor] [--z-kodu] [--petla] [--ciecia 3.2,7.5-7.8]
                             [--arkusz out/wideo/qa.jpg] [--json]

Sprawdza: kontener i kodeki (H.264 + AAC, yuv420p, faststart, bez HDR), rozdzielczość i proporcje, fps, długość wobec
platformy, głośność (LUFS zintegrowane, true peak i rozpiętość LRA), czarne klatki, zamrożony obraz, cisze w dźwięku.
Kontrola klatek (wzorce za cinetic forensics, MIT; numpy z /opt/jarvo/venv, skrypt sam na niego przechodzi):
  duch        jedna klatka ze zwartą plamą, której nie ma w sąsiednich (zgubiony stan, zła klatka, słowo na 1 klatkę)  błąd
  zamrożenie  klatka powtórzona w środku ruchu (zmiana ≈ 0 albo ≤ 10% zmian obok)          błąd z --z-kodu, inaczej ostrzeżenie
  skok        zmiana w 1–2 klatkach ponad 2,5 × medianę ±4 klatek (kadr albo jeden z 9 regionów), której nie tłumaczy
              ruch rozłożony na ≥ 3 klatki ani cięcie (połowa kadru albo --ciecia)                              ostrzeżenie
  drgania     powolny ruch schodkami całych pikseli (korelacja fazowa łatek 256 px w pełnej rozdzielczości)     ostrzeżenie
  pasy        gładkie przejście kolorów narysowane płaskimi stopniami (kafle 64 px, próbki co sekundę)          ostrzeżenie
  szew pętli  (--petla) ostatnia → pierwsza klatka zmienia więcej niż max(0,4, 1,5 × krok na końcach)           błąd
--ciecia 3.2,7.5-7.8: zamierzone cięcia i błyski (sekundy); skok i duch w nich nie są zgłaszane.
Bez numpy zostaje stara kontrola „mrugnięć” (cała klatka inna niż obie sąsiednie) i ostrzeżenie.
--arkusz: klatki z początku (hook), środka i końca z zaznaczonymi strefami interfejsu platformy (9:16, bez --platforma TikTok):
na nich widać, czy napisy, tekst i logo nie wchodzą pod przyciski i opis.
Film z kodu (`--z-kodu`, i zawsze, gdy obok leży projekt z `projekt.py z-kodu`): projekt edytora `<film>.edycja.json`
istnieje, jego pliki są na miejscu, a film to jego render (ta sama długość, film nie starszy niż projekt), więc
właściciel otworzy w edytorze HQ dokładnie to, co dostał.
Kod wyjścia 1 = jest błąd blokujący. Tabela platform zgodna z skills/wideo/formaty-wideo/references/specs.md.
"""

from __future__ import annotations

import argparse
import json
import os
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
LRA_MAX = 10.0          # rozpiętość głośności (LU): 4–10 dla filmów z głosem i muzyką (za skillem fframes)


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
    res = subprocess.run(args + ["-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
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
    m = re.search(r"LRA:\s+(-?[\d.]+) LU\b", summary)
    out["lra"] = float(m.group(1)) if m else None
    return out


def zones(w: int, h: int, platform: str | None = None) -> list[tuple[int, int, int, int]]:
    """Strefy zasłaniane przez interfejs 9:16 platformy (wideo_lib.strefy_ui, bez platformy TikTok) jako (x, y, szer., wys.)."""
    return [(int(x0), int(y0), int(x1 - x0), int(y1 - y0)) for _n, (x0, y0, x1, y1) in wl.strefy_ui(w, h, platform)]


def sheet(path: Path, dur: float, w: int, h: int, out: Path, marks: bool, platform: str | None = None) -> Path:
    times = sorted({0.0, 0.5, 1.5, dur * 0.25, dur * 0.5, dur * 0.75, max(0.0, dur - 0.5)})
    times = [t for t in times if t < dur]
    cw = 270 if h > w else 480
    ch = wl.even(cw * h / w)
    draw = ""
    if marks:
        sx, sy = cw / w, ch / h
        draw = "".join(f",drawbox=x={int(x * sx)}:y={int(y * sy)}:w={int(bw * sx)}:h={int(bh * sy)}:color=red@0.28:t=fill"
                       for x, y, bw, bh in zones(w, h, platform))
    with tempfile.TemporaryDirectory(prefix="jarvo-qa-") as tmp:
        for i, t in enumerate(times):
            label = f"{t:.1f}s"
            base = f"scale={cw}:{ch}{draw}"
            cell = Path(tmp) / f"c{i:02d}.png"
            try:
                wl.run(["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", "-vf",
                        base + f",drawtext=text='{label}'{wl.drawtext_kroj()}:x=6:y=6:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=4",
                        str(cell)])
            except wl.FFError:
                wl.run(["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", "-vf", base, str(cell)])
        cols = min(4, len(times))
        rows = (len(times) + cols - 1) // cols
        out.parent.mkdir(parents=True, exist_ok=True)
        wl.run(["ffmpeg", "-y", "-framerate", "1", "-i", str(Path(tmp) / "c%02d.png"), "-vf",
                f"tile={cols}x{rows}:padding=4:color=0x0B0D12", "-frames:v", "1", "-q:v", "3", str(out)])
    return out


POP_W, POP_H = 48, 27     # klatki do wykrywania mrugnięć: małe i w skali szarości (szybko, bez numpy)


def gray_frames(path: Path, max_frames: int = 36000) -> tuple[list[bytes], float]:
    """Małe klatki w skali szarości (ffmpeg dekoduje, Python liczy: bez numpy) i fps."""
    info = wl.probe(path)
    fps = (info["video"] or {}).get("fps") or 30
    size = POP_W * POP_H
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-frames:v", str(max_frames),
                          "-vf", f"scale={POP_W}:{POP_H}:flags=area,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=False).stdout
    return [raw[i:i + size] for i in range(0, len(raw) - size + 1, size)], fps


def _diff(a: bytes, b: bytes) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def single_frame_pops(frames: list[bytes], fps: float = 30, min_jump: float = 14.0, ratio: float = 3.0) -> list[float]:
    """Klatka i to „mrugnięcie”, gdy mocno różni się od obu sąsiadek, a sąsiadki są do siebie podobne
    (d(i-1, i+1) co najmniej `ratio` razy mniejsze). Cięcie sceny (jeden skok) i szybki ruch kamery (sąsiadki też
    się różnią) nie są liczone. Zwraca czasy klatek w sekundach."""
    out, prev = [], None
    for i in range(1, len(frames) - 1):
        d_in = prev if prev is not None else _diff(frames[i - 1], frames[i])
        d_out = _diff(frames[i], frames[i + 1])
        prev = d_out
        if min(d_in, d_out) >= min_jump and _diff(frames[i - 1], frames[i + 1]) * ratio <= min(d_in, d_out):
            out.append(round(i / fps, 3))
    return out


# ------------------------------------------------------------------ kontrola klatek (wzorce za cinetic forensics, MIT)
# d[f] = średnia |zmiana jasności| klatki f-1 → f (0–255) na klatkach 480 px dłuższego boku; regiony = siatka 3×3.
KL_BOK = 480
SKOK_MIN, SKOK_RAZY, SKOK_PLUS, SKOK_REGION, SKOK_TLO = 1.0, 2.5, 0.3, 1.5, 0.15
CIECIE_UDZIAL = 0.5        # skok, w którym zmienia się co najmniej połowa kadru, to cięcie, nie skok elementu
STOJ_MAX, STOJ_RAZY, STOJ_RUCH = 0.05, 0.1, 0.8   # powtórzona klatka: zmiana ≈ 0 albo ≤ 10% zmian obok (szum kodera)
DUCH_ROZNI, DUCH_ZGODNE = 80, 30
DUCH_UDZIAL = 2000 / (1920 * 1080)   # ~2000 px w Full HD: mniejsze plamki to szum kodera
DUCH_ZASIEG = 0.1                    # ruch w promieniu 10% dłuższego boku (~192 px w Full HD) = szybki element, nie duch
DRG_SPOCZYNEK, DRG_SKOK, DRG_UDZIAL, DRG_PRZEJSCIA, DRG_OKNA = 0.03, 0.08, 0.25, 4, 6
DRG_LATKA = 256
PASY_KAFEL, PASY_ZAKRES, PASY_UDZIAL, PASY_PROBKI = 64, (1, 12), 0.03, 40
SZEW_MIN, SZEW_RAZY = 0.4, 1.5
REGIONY = ("lewa góra", "góra", "prawa góra", "lewa", "środek", "prawa", "lewy dół", "dół", "prawy dół")


def numpy_jest() -> bool:
    try:
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


def _rozmiar(w: int, h: int, bok: int = KL_BOK) -> tuple[int, int]:
    """Rozmiar klatek analizy: dłuższy bok `bok`, proporcje filmu, wymiary parzyste."""
    if w >= h:
        return bok, max(2, wl.even(bok * h / w))
    return max(2, wl.even(bok * w / h)), bok


def _klatki(path: Path, w: int, h: int, vf: str = "", ss: float | None = None, t: float | None = None,
            max_frames: int = 36000):
    """Klatki w skali szarości (numpy uint8 h×w) prosto z ffmpeg, po jednej: film nie leży cały w pamięci."""
    import numpy as np
    cmd = ["ffmpeg", "-nostdin", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", f"{ss:.3f}"]
    cmd += ["-i", str(path)]
    if t is not None:
        cmd += ["-t", f"{t:.3f}"]
    cmd += ["-frames:v", str(max_frames), "-vf", f"{vf}scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "-"]
    size = w * h
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as p:
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, w)


def _regiony(diff) -> list[float]:
    h, w = diff.shape
    ys, xs = (0, h // 3, 2 * h // 3, h), (0, w // 3, 2 * w // 3, w)
    return [float(diff[ys[r]:ys[r + 1], xs[c]:xs[c + 1]].mean()) for r in range(3) for c in range(3)]


def duch(a, b, c) -> bool:
    """Klatka b to duch: na zwartej plamie (rdzeń po zerodowaniu: cienkie krawędzie ruchu odpadają) różni się
    od obu sąsiadek, które są tam zgodne, a obok plamy nie rusza się więcej niż w całym kadrze (ruch skupiony przy
    plamie = szybki element przelatujący przez kadr; ruch wszędzie = panorama, na której duch dalej jest duchem)."""
    import numpy as np
    ab, bc, ac = (np.abs(x.astype(np.int16) - y) for x, y in ((a, b), (b, c), (a, c)))
    plama = (ab > DUCH_ROZNI) & (bc > DUCH_ROZNI) & (ac < DUCH_ZGODNE)
    prog = max(4, DUCH_UDZIAL * a.size)
    rdzen = np.zeros_like(plama)
    rdzen[1:-1, 1:-1] = (plama[1:-1, 1:-1] & plama[:-2, 1:-1] & plama[2:, 1:-1] & plama[1:-1, :-2] & plama[1:-1, 2:])
    if plama.sum() <= prog or rdzen.sum() <= prog / 2:
        return False
    ys, xs = np.nonzero(rdzen)
    r = int(DUCH_ZASIEG * max(a.shape))
    y0, y1, x0, x1 = max(0, ys.min() - r), ys.max() + r + 1, max(0, xs.min() - r), xs.max() + r + 1
    ruch = ac > DUCH_ZGODNE
    obok = ruch[y0:y1, x0:x1]
    return int(obok.sum()) < prog or float(obok.mean()) <= 2 * float(ruch.mean())


def zmiany(klatki) -> dict:
    """Jedno przejście po klatkach: d (cały kadr), dr (9 regionów), udział zmienionych pikseli, duchy, pierwsza
    i ostatnia klatka (szew pętli)."""
    import numpy as np
    d, dr, p, duchy = [0.0], [[0.0] * 9], [0.0], []
    okno, pierwsza, n = [], None, 0
    for k in klatki:
        if pierwsza is None:
            pierwsza = k
        if okno:
            diff = np.abs(k.astype(np.int16) - okno[-1])
            d.append(float(diff.mean()))
            dr.append(_regiony(diff))
            p.append(float((diff > 24).mean()))
        okno = (okno + [k])[-3:]
        if len(okno) == 3 and duch(*okno):
            duchy.append(n - 1)
        n += 1
    duchy = [f for f in duchy if not any(0 < abs(f - g) <= 2 for g in duchy)]   # seria „duchów” to szybki ruch
    return {"d": d[:n], "dr": dr[:n], "p": p[:n], "duchy": duchy, "pierwsza": pierwsza,
            "ostatnia": okno[-1] if okno else None, "n": n}


def _mediana(xs: list[float]) -> float:
    s = sorted(xs)
    return (s[len(s) // 2] + s[(len(s) - 1) // 2]) / 2 if s else 0.0


def skoki(d: list[float], dr: list[list[float]], p: list[float], ciecia: list[int] = (), pomin: set[int] = frozenset()
          ) -> tuple[list[tuple[int, int | None]], list[int]]:
    """Nagła zmiana w 1–2 klatkach (cały kadr albo jeden z 9 regionów) wobec mediany ±4 klatek. Zmiana rozłożona
    na ≥ 3 klatki to zamierzony ruch (śmignięcie, zalanie), zmiana większości kadru albo zadeklarowana to cięcie.
    Zwraca (skoki [(klatka, region albo None)], cięcia [klatka])."""
    n, out, ciete = len(d), [], []
    for f in range(1, n):
        if f in pomin or f - 1 in pomin:
            continue
        sasiedzi = [j for j in range(max(1, f - 4), min(n, f + 5)) if j != f]
        seria, region = None, None
        if d[f] > max(SKOK_MIN, SKOK_RAZY * _mediana([d[j] for j in sasiedzi]) + SKOK_PLUS):
            seria = d
        else:
            for r in range(9):
                v = dr[f][r]
                if v > max(SKOK_REGION, SKOK_RAZY * _mediana([dr[j][r] for j in sasiedzi]) + SKOK_PLUS) and d[f] <= SKOK_TLO * v:
                    seria, region = [x[r] for x in dr], r
                    break
        if seria is None:
            continue
        if sum(1 for j in range(f - 2, f + 3) if 0 < j < n and seria[j] > 0.5 * seria[f]) >= 3:
            continue
        if any(abs(f - c) <= 1 for c in ciecia) or (region is None and p[f] >= CIECIE_UDZIAL):
            ciete.append(f)
        elif not out or out[-1][0] != f - 1:
            out.append((f, region))
    return out, ciete


def zamrozenia(d: list[float]) -> list[int]:
    """Powtórzona klatka w środku ruchu: przed i po niej obraz się zmienia, a ona jest kopią poprzedniej
    (po koderze kopia ma szum, więc liczy się też zmiana ≤ 10% zmian obok)."""
    return [f for f in range(2, len(d) - 1) if min(d[f - 1], d[f + 1]) > STOJ_RUCH
            and d[f] < max(STOJ_MAX, STOJ_RAZY * min(d[f - 1], d[f + 1]))]


def schody(dr: list[list[float]], fps: float) -> list[tuple[int, int, int]]:
    """Kandydaci na drgania: w oknie 1 s region na zmianę stoi (zmiana ≈ 0) i skacze pojedynczymi klatkami.
    Zwraca (pierwsza klatka, ostatnia, region); potwierdza `drgania` w pełnej rozdzielczości."""
    n, okno, out = len(dr), max(8, int(round(fps))), []
    for r in range(9):
        s = [x[r] for x in dr]
        f, koniec = 1, n <= okno
        while not koniec:
            if f + okno >= n:                   # ostatnie okno zawsze dosuwa do końca filmu
                f, koniec = max(1, n - okno), True
            w = s[f:f + okno]
            stoi = [v < DRG_SPOCZYNEK for v in w]
            skacze = [v > DRG_SKOK for v in w]
            przejscia = sum(1 for i in range(1, okno) if skacze[i] and stoi[i - 1])
            pojedyncze = sum(1 for i in range(okno) if skacze[i] and not (i and skacze[i - 1]) and not (i + 1 < okno and skacze[i + 1]))
            if (sum(stoi) >= DRG_UDZIAL * okno and sum(skacze) >= DRG_UDZIAL * okno and przejscia >= DRG_PRZEJSCIA
                    and pojedyncze >= 0.6 * sum(skacze)):
                if out and out[-1][2] == r and f <= out[-1][1] + 1:
                    out[-1] = (out[-1][0], f + okno - 1, r)
                else:
                    out.append((f, f + okno - 1, r))
                f += okno // 2
            else:
                f += max(1, okno // 4)
    return out


def przesuniecie(a, b) -> tuple[float, float]:
    """Przesunięcie (dy, dx) obrazu b względem a z korelacji fazowej, z dokładnością do ułamka piksela."""
    import numpy as np
    okno = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))
    fa, fb = np.fft.fft2(a * okno), np.fft.fft2(b * okno)
    r = fb * np.conj(fa)
    r = np.real(np.fft.ifft2(r / (np.abs(r) + 1e-9)))
    py, px = np.unravel_index(int(np.argmax(r)), r.shape)

    def dokladnie(i: int, n: int, wzdluz) -> float:
        lo, mid, hi = wzdluz((i - 1) % n), wzdluz(i), wzdluz((i + 1) % n)
        mian = lo - 2 * mid + hi
        sub = 0.5 * (lo - hi) / mian if mian else 0.0
        v = i + sub
        return v - n if v > n / 2 else v
    return (dokladnie(py, r.shape[0], lambda i: r[i, px]), dokladnie(px, r.shape[1], lambda i: r[py, i]))


def drgania(path: Path, w: int, h: int, fps: float, kandydaci: list[tuple[int, int, int]]
            ) -> list[tuple[int, int, list[str]]]:
    """Potwierdzenie drgań w pełnej rozdzielczości: łatka regionu sunie powoli (< 1 px na klatkę, w sumie ≥ 2 px),
    ale całymi pikselami: klatki stoi, stoi, skok o 1 px. Gładki ruch przesuwa ją o ułamki co klatkę.
    Pisanie, miganie i podmiana treści nie są ruchem, więc tu odpadają. Kandydaci zachodzący na siebie w czasie
    to jedna grupa (jedno dekodowanie). Zwraca (pierwsza klatka, ostatnia, regiony)."""
    import numpy as np
    grupy: list[list] = []
    for f0, f1, r in sorted(kandydaci):
        if grupy and f0 <= grupy[-1][1]:
            grupy[-1][1] = max(grupy[-1][1], f1)
            grupy[-1][2].append(r)
        else:
            grupy.append([f0, f1, [r]])
    lw, lh = min(DRG_LATKA, w // 3), min(DRG_LATKA, h // 3)
    out = []
    for f0, f1, regiony in grupy[:DRG_OKNA]:
        klatki = list(_klatki(path, w, h, ss=max(0.0, (f0 - 1) / fps), t=(f1 - f0 + 2) / fps))
        if len(klatki) < 6:
            continue
        potw = []
        for r in sorted(set(regiony)):
            cy, cx = (2 * (r // 3) + 1) * h // 6, (2 * (r % 3) + 1) * w // 6
            y0, x0 = max(0, cy - lh // 2), max(0, cx - lw // 2)
            latki = [k[y0:y0 + lh, x0:x0 + lw].astype(np.float32) for k in klatki]
            kroki = [przesuniecie(a, b) for a, b in zip(latki, latki[1:])]
            dlug = [(dy * dy + dx * dx) ** 0.5 for dy, dx in kroki]
            suma = (sum(dy for dy, _ in kroki) ** 2 + sum(dx for _, dx in kroki) ** 2) ** 0.5
            calkowite = sum(1 for v in dlug if abs(v - round(v)) < 0.15)
            stoi = sum(1 for v in dlug if v < 0.15)
            if (suma >= 2 and max(dlug) < 1.6 and sum(dlug) / len(dlug) < 1.0 and calkowite >= 0.85 * len(dlug)
                    and stoi >= DRG_UDZIAL * len(dlug) and len(dlug) - stoi >= 2):
                potw.append(REGIONY[r])
        if potw:
            out.append((f0, f1, potw))
    return out


def pasy_klatki(k) -> float:
    """Udział kadru w pasach: kafle 64 px z gładkim przejściem o 1–12 poziomów jasności narysowanym płaskimi
    stopniami co 1 poziom (bez szumu i bez faktury) i z kierunkiem (średnie wierszy albo kolumn rosną: to przejście,
    nie pojedyncze plamki szumu). Przejście z ziarnem albo z faktury ma gęste drobne różnice."""
    import numpy as np
    s = PASY_KAFEL
    h, w = (k.shape[0] // s) * s, (k.shape[1] // s) * s
    if not h or not w:
        return 0.0
    t = k[:h, :w].astype(np.int16).reshape(h // s, s, w // s, s).transpose(0, 2, 1, 3)
    zakres = t.max(axis=(2, 3)) - t.min(axis=(2, 3))
    dx, dy = np.abs(np.diff(t, axis=3)), np.abs(np.diff(t, axis=2))
    duze = (dx >= 2).mean(axis=(2, 3)) + (dy >= 2).mean(axis=(2, 3))
    niezerowe = ((dx > 0).mean(axis=(2, 3)) + (dy > 0).mean(axis=(2, 3))) / 2
    profil = np.maximum(np.ptp(t.mean(axis=3), axis=2), np.ptp(t.mean(axis=2), axis=2))
    pas = ((zakres >= PASY_ZAKRES[0]) & (zakres <= PASY_ZAKRES[1]) & (duze < 0.002) & (niezerowe > 0)
           & (niezerowe <= 0.08) & (profil >= 0.5))
    return float(pas.sum() * s * s / k.size)


def pasy(path: Path, w: int, h: int, dur: float) -> list[tuple[float, float]]:
    """Pasy na gładkich przejściach: próbki co sekundę (najwyżej 40) w pełnej rozdzielczości. Zwraca (sekunda, udział)."""
    co = max(1.0, dur / PASY_PROBKI)
    out = []
    for i, k in enumerate(_klatki(path, w, h, vf=f"fps=1/{co:g},", max_frames=PASY_PROBKI)):
        u = pasy_klatki(k)
        if u > PASY_UDZIAL:
            out.append((round(i * co, 1), round(u, 3)))
    return out


def szew(z: dict) -> tuple[float, float]:
    """Szew pętli: zmiana ostatnia → pierwsza klatka i próg max(0,4, 1,5 × mediana kroku na końcach filmu)."""
    import numpy as np
    zmiana = float(np.abs(z["ostatnia"].astype(np.int16) - z["pierwsza"]).mean())
    d = z["d"]
    return round(zmiana, 3), round(max(SZEW_MIN, SZEW_RAZY * _mediana(d[1:11] + d[-10:])), 3)


def _czasy(klatki: list[int], fps: float) -> str:
    return ", ".join(f"{f / fps:.2f}" for f in klatki[:8]) + (" …" if len(klatki) > 8 else "")


def kontrola_klatek(path: Path, w: int, h: int, fps: float, dur: float, z_kodu: bool = False, petla: bool = False,
                    ciecia: list[tuple[float, float]] = ()) -> tuple[list[str], list[str], dict]:
    """Skoki, zamrożenia, duchy, drgania, pasy i szew pętli (--petla). Zwraca (błędy, ostrzeżenia, metryki)."""
    errors, warns = [], []
    aw, ah = _rozmiar(w, h)
    z = zmiany(_klatki(path, aw, ah))
    if z["n"] < 3:
        return errors, warns, {}
    deklarowane = [f for a, b in ciecia for f in range(int(a * fps), int(b * fps) + 1)]
    z["duchy"] = [f for f in z["duchy"] if not any(abs(f - c) <= 1 for c in deklarowane)]   # zamierzony błysk
    drg = drgania(path, w, h, fps, schody(z["dr"], fps))
    pomin = {f + 1 for f in z["duchy"]} | set(z["duchy"]) | {f for f0, f1, _ in drg for f in range(f0, f1 + 1)}
    sk, ciete = skoki(z["d"], z["dr"], z["p"], deklarowane, pomin)
    stoj = zamrozenia(z["d"])
    ps = pasy(path, w, h, dur)
    if z["duchy"]:
        errors.append(f"duch: pojedyncza klatka z plamą, której nie ma w sąsiednich ({len(z['duchy'])}×, s: "
                      f"{_czasy(z['duchy'], fps)}): zgubiony stan, zła klatka renderu albo słowo napisów na 1 klatkę; obejrzyj "
                      "`html_wideo.py klatki --czasy` wokół tych chwil")
    if stoj:
        (errors if z_kodu else warns).append(
            f"zamrożona klatka w ruchu ({len(stoj)}×, s: {_czasy(stoj, fps)}): klatka powtórzona, ruch się zacina"
            + ("; w filmie z kodu każda klatka jest renderem, więc to błąd seek albo kolejności klatek" if z_kodu else
               "; regularnie co kilka klatek = zmiana fps (np. 25 → 30), wtedy film w fps materiału"))
    if sk:
        opis = [f"{f / fps:.2f}" + (f" ({REGIONY[r]})" if r is not None else "") for f, r in sk[:8]]
        warns.append(f"skok w 1–2 klatkach, którego nie tłumaczy ruch ({len(sk)}×, s: {', '.join(opis)}"
                     f"{' …' if len(sk) > 8 else ''}): element przeskakuje zamiast wejść; jeśli to zamierzone cięcie, "
                     "podaj `--ciecia`")
    for f0, f1, reg in drg:
        gdzie = "cały kadr" if len(reg) == 9 else ", ".join(reg)
        warns.append(f"drgania {(f0 - 1) / fps:.1f}–{f1 / fps:.1f} s ({gdzie}): powolny ruch idzie schodkami całych pikseli; przesuwaj "
                     "przez transform (ułamki piksela), nie top/left, albo przyspiesz ruch")
    if len(ps) >= (2 if dur >= 4 else 1):
        warns.append(f"pasy na gładkim przejściu (s: {', '.join(f'{t:.0f}' for t, _ in ps[:6])}; do "
                     f"{max(u for _, u in ps):.0%} kadru): dodaj ziarno 1–2% albo zmień przejście kolorów")
    metryki = {"skoki": len(sk), "ciecia": len(ciete), "zamrozenia": len(stoj), "duchy": len(z["duchy"]),
               "drgania": len(drg), "pasy": len(ps)}
    if petla:
        zmiana, prog = szew(z)
        metryki["szew"] = zmiana
        if zmiana > prog:
            errors.append(f"szew pętli: ostatnia → pierwsza klatka zmienia {zmiana} (próg {prog}, krok ruchu na końcach): "
                          "pętla przeskoczy; koniec ma wracać do stanu z początku")
        elif zmiana < STOJ_MAX and _mediana(z["d"][1:11] + z["d"][-10:]) > STOJ_RUCH:
            warns.append("szew pętli: ostatnia klatka = pierwsza, w pętli ta klatka zagra dwa razy (zacięcie); "
                         "zakończ klatkę przed powrotem do stanu początkowego")
    return errors, warns, metryki


def ciecia_z_argumentu(s: str | None) -> list[tuple[float, float]]:
    """„3.2,7.5-7.8” → [(3.2, 3.2), (7.5, 7.8)] (sekundy)."""
    out = []
    for kawalek in (s or "").split(","):
        if kawalek.strip():
            a, _, b = kawalek.partition("-")
            out.append((float(a), float(b or a)))
    return out


def wymagaj_numpy(skrypt: str) -> None:
    """Python bez numpy (np. Hermesa): uruchomiony wprost skrypt rusza od nowa Pythonem narzędzi z obrazu."""
    venv = Path("/opt/jarvo/venv/bin/python")
    if (not numpy_jest() and venv.exists() and Path(sys.argv[0]).resolve() == Path(skrypt).resolve()
            and not os.environ.get("JARVO_QA_REEXEC")):
        os.environ["JARVO_QA_REEXEC"] = "1"
        import narzedzia as nz                  # noqa: PLC0415  (execv na POSIX, podproces na Windows)
        nz.od_nowa(venv, skrypt)


def projekt_z_kodu(path: Path, dur: float, wymagany: bool) -> tuple[list[str], list[str]]:
    """Film z kodu oddajemy jako projekt edytora (`projekt.py z-kodu`): projekt jest, pliki są, film = jego render."""
    errors, warns = [], []
    pp = path.with_name(f"{path.stem}.edycja.json")          # jak edytor.project_path
    try:
        proj = json.loads(pp.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if wymagany:
            errors.append(f"film z kodu bez projektu edytora ({pp.name}): projekt.py z-kodu {path.name} --obraz <czysty obraz> "
                          "… --render, inaczej właściciel nie poprawi go w edytorze HQ")
        return errors, warns
    except (OSError, ValueError) as exc:
        return [f"projekt edytora {pp.name} nieczytelny: {exc}"], warns
    if "zKodu" not in proj:
        if wymagany:
            errors.append(f"{pp.name} nie jest projektem filmu z kodu (brak zKodu): projekt.py z-kodu {path.name} … --nadpisz")
        return errors, warns
    pliki = {str(x.get("src")) for k in ("clips", "audio") for x in proj.get(k) or [] if x.get("src")}
    brak = sorted(Path(f).name for f in pliki if not Path(f).is_file())
    if brak:
        errors.append(f"projekt edytora wskazuje pliki, których nie ma ({', '.join(brak[:4])}): edytor go nie otworzy")
    os_ = sum((float(c.get("out", 0)) - float(c.get("in", 0))) / float(c.get("speed") or 1) for c in proj.get("clips") or [])
    if abs(os_ - dur) > 0.1:
        errors.append(f"film ({dur:.2f} s) nie jest renderem projektu ({os_:.2f} s): projekt.py render {path.name} --out {path.name}")
    elif pp.stat().st_mtime > path.stat().st_mtime + 1:
        warns.append(f"projekt zmieniony po renderze filmu: projekt.py render {path.name} --out {path.name}")
    return errors, warns


def check(path: Path, platform: str | None, fmt: str | None, voiced: bool, arkusz: Path | None,
          z_kodu: bool = False, petla: bool = False, ciecia: list[tuple[float, float]] = ()) -> dict:
    errors, warns = [], []
    info = wl.probe(path)
    v, a = info["video"], info["audio"]
    dur = info["duration"]
    if not v:
        return {"plik": Path(path).as_posix(), "ok": False, "bledy": ["brak ścieżki wideo"], "ostrzezenia": []}
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
    if v.get("hdr"):
        errors.append(f"film w HDR ({v['hdr']}): platformy i telefony pokażą go inaczej niż w podglądzie; przelicz na "
                      "zwykły obraz (eksport edytora HQ, projekt.py render, montaz.py robią to same)")
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
        if an.get("lra") is not None and an["lra"] > LRA_MAX and dur >= 10:
            warns.append(f"rozpiętość głośności {an['lra']} LU > {LRA_MAX:g} (cel 4–10): ciche i głośne części do wyrównania "
                         "(głośność ścieżek, montaz.py glosnosc)")
    for s, e in an["czarne"]:
        if s < 0.3:
            errors.append(f"czarny początek {s:.1f}–{e:.1f} s: pierwsza klatka to miniatura i hook")
        elif e - s >= 0.8 and e < dur - 0.3:
            warns.append(f"czarne klatki {s:.1f}–{e:.1f} s")
    for s, e in an["zamrozone"]:
        warns.append(f"zamrożony obraz od {s:.1f} s{f' do {e:.1f} s' if e else ''} (statyczna scena > 2 s nuży)")
    klatki = {}
    if numpy_jest():
        e_, w_, klatki = kontrola_klatek(path, v["width"], v["height"], v["fps"] or 30, dur, z_kodu, petla, ciecia)
        errors += e_
        warns += w_
    else:
        frames, fps = gray_frames(path)
        pops = single_frame_pops(frames, fps=fps)
        if pops:
            shown = ", ".join(f"{t:.2f}" for t in pops[:8]) + (" …" if len(pops) > 8 else "")
            (errors if len(pops) > 3 else warns).append(
                f"pojedyncze klatki inne niż sąsiednie ({len(pops)}×, s: {shown}): obejrzyj `html_wideo.py klatki --czasy` wokół tych chwil")
        warns.append("kontrola klatek (skoki, zamrożenia, duchy, drgania, pasy, szew pętli) pominięta: ten Python nie "
                     "ma numpy; uruchom qa_wideo.py wprost (sam przejdzie na /opt/jarvo/venv)")
    if voiced:
        for s, e in an["cisze"]:
            if (e or dur) - s >= 2.0:
                warns.append(f"cisza {s:.1f}–{(e or dur):.1f} s w filmie z lektorem")
    e_, w_ = projekt_z_kodu(path, dur, z_kodu)
    errors += e_
    warns += w_
    res = {"plik": Path(path).as_posix(), "ok": not errors, "bledy": errors, "ostrzezenia": warns,
           "metryki": {"sek": round(dur, 2), "rozdzielczosc": f"{v['width']}x{v['height']}", "fps": v["fps"],
                       "wideo": v["codec"], "audio": a and a["codec"], "mb": round(info["size"] / 1048576, 2),
                       "lufs": an["lufs"], "true_peak": an["true_peak"], "lra": an.get("lra")}}
    if klatki:
        res["metryki"]["klatki"] = klatki
    if arkusz:
        res["arkusz"] = str(sheet(path, dur, v["width"], v["height"], arkusz, marks=True, platform=platform))
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plik", nargs="+")
    ap.add_argument("--platforma", choices=sorted(PLATFORMS))
    ap.add_argument("--format", help="9:16 | 16:9 | 1:1 | 4:5 (domyślnie z platformy)")
    ap.add_argument("--lektor", action="store_true", help="film z lektorem: brak audio i długie cisze to błąd/ostrzeżenie")
    ap.add_argument("--z-kodu", action="store_true", help="film z kodu: bez projektu edytora (projekt.py z-kodu) to błąd")
    ap.add_argument("--petla", action="store_true", help="film to pętla: ostatnia klatka ma przechodzić w pierwszą bez skoku")
    ap.add_argument("--ciecia", help="zamierzone cięcia i błyski w sekundach: 3.2,7.5-7.8 (skok w nich to nie błąd)")
    ap.add_argument("--arkusz", help="JPG z klatkami i strefami UI (przy wielu plikach: katalog)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    wl.need("ffmpeg")
    wymagaj_numpy(__file__)
    results = []
    for f in args.plik:
        ark = None
        if args.arkusz:
            ark = Path(args.arkusz)
            if len(args.plik) > 1:
                ark = ark / f"qa-{Path(f).stem}.jpg"
        results.append(check(Path(f), args.platforma, args.format, args.lektor, ark, args.z_kodu, args.petla,
                             ciecia_z_argumentu(args.ciecia)))
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
