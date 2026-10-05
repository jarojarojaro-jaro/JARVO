#!/usr/bin/env python3
"""Rytm muzyki: tempo (BPM), siatka bitów, takty, „drop” i uderzenia perkusji: pod nie układasz cięcia i ruch.

    python3 rytm.py muzyka.mp3 [--json out/wideo/src/rytm.json] [--od 0 --do 60]
    python3 rytm.py film-wzor.mp4                 # też z dźwięku filmu (np. wzór do rozpisania na bity)
    python3 rytm.py klik.wav whoosh.wav --szczyt  # gdzie efekt ma szczyt: kładziesz go tak, by szczyt trafił w zdarzenie
    python3 rytm.py sprawdz film.mp4 [--plan cues.json | --projekt film.edycja.json | --ciecia 1.2,3.4] [--json raport.json]

Wynik: BPM, pierwszy bit (faza), czasy bitów, początki taktów (co 4 bity), drop (najmocniejsze wejście po
spokojniejszym fragmencie) i propozycja cięć: co takt, a na dropie najmocniejsza scena. Perkusja w trzech pasmach
(za video-shotcraft, Apache-2.0): stopa 40–160 Hz (uderzenie, „zgniecenie” kadru), werbel 150–500 Hz razem
z trzaskiem 1–3 kHz (zamiana, cięcie: „teraz coś innego”) i talerze 6–14 kHz (gęstość drobnego ruchu: gęste talerze
= drobny ruch może być gęsty, rzadkie = spokój). `uderzenia` to pula kandydatów, nie wyzwalacz: stopa gra prawie
na każdym bicie, a uderzenie całego kadru dostają tylko `najmocniejsze` (2–3 na film, co najmniej 16 bitów od siebie,
najpierw stopy na bicie, nic w pierwszej sekundzie).
Siatka jest sprawdzana na prawdziwych uderzeniach: 0,5×, 1× i 2× tempa, wygrywa ta, w której bity trafiają
w uderzenia, a stopa w bity (`siatka`: trafienia, średni błąd, dryf, ocena).
sprawdz (po renderze): cięcia filmu (bez planu: wykryte w obrazie) kontra bity z dźwięku GOTOWEGO filmu, błąd
w klatkach: do 1,5 idealnie, do 3 dobrze, ponad 3 do poprawy (kod wyjścia 1). Wszystkie cięcia przesunięte o tyle
samo = przesunięcie dźwięku przy kodowaniu (AAC dokłada na początku ok. 1024–2048 próbek): poprawiasz jednym
przesunięciem całej ścieżki, nie każde cięcie osobno.
Liczy na obwiedni energii dźwięku (ffmpeg dekoduje i filtruje pasma, Python liczy; bez numpy i bez sieci).
Muzyka elektroniczna i pop ze stałym tempem: pewnie; swobodne tempo (akustyka, mowa): traktuj jako wskazówkę
i sprawdź uchem.
"""

from __future__ import annotations

import argparse
import array
import json
import bisect
import math
import re
import subprocess
import sys
from pathlib import Path

SR = 8000          # próbkowanie do analizy
HOP = 80           # 10 ms: obwiednia 100 wartości na sekundę
ENV_SR = SR / HOP
# pasma perkusji (filtry ffmpeg podwójne = 24 dB na oktawę; talerze potrzebują próbkowania ≥ 28 kHz)
PASMA = {
    "stopa": (["highpass=f=40,highpass=f=40,lowpass=f=160,lowpass=f=160"], SR),
    "werbel": (["highpass=f=150,highpass=f=150,lowpass=f=500,lowpass=f=500",          # ciało werbla
                "highpass=f=1000,highpass=f=1000,lowpass=f=3000,lowpass=f=3000"], SR),  # trzask: oba naraz
    "talerz": (["highpass=f=6000,highpass=f=6000,lowpass=f=14000,lowpass=f=14000"], 32000),
}
TOL = 0.035        # bit trafiony: uderzenie w ±35 ms (ok. jedna klatka przy 30 kl./s)
NAJ_ODSTEP = 16    # najmocniejsze uderzenia (uderzenie całego kadru) co najmniej 16 bitów od siebie, najwyżej 3


def envelope(path: Path, start: float = 0.0, end: float | None = None, af: str | None = None,
             sr: int = SR) -> list[float]:
    """Energia (RMS) w oknach 10 ms; `af` = filtr ffmpeg (pasmo), `sr` = próbkowanie do analizy."""
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", str(start), "-i", str(path)]
    if end is not None:
        cmd += ["-t", str(max(0.1, end - start))]
    cmd += ["-vn", "-ac", "1", "-ar", str(sr)] + (["-af", af] if af else []) + ["-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=False).stdout
    if len(raw) < sr:
        raise SystemExit(f"za mało dźwięku w {path} (brak ścieżki audio?)")
    pcm = array.array("h")
    pcm.frombytes(raw[: len(raw) - len(raw) % 2])
    hop = sr // 100
    return [math.sqrt(sum(x * x for x in pcm[i:i + hop]) / hop) for i in range(0, len(pcm) - hop + 1, hop)]


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


def peak(path: Path) -> dict:
    """Szczyt efektu (najgłośniejsze 10 ms) i jego początek (pierwsze przekroczenie 20% szczytu)."""
    env = envelope(path) if path.stat().st_size else []
    top = max(range(len(env)), key=lambda i: env[i])
    start = next(i for i, v in enumerate(env) if v >= 0.2 * env[top])
    return {"plik": str(path), "szczyt": round(top / ENV_SR, 3), "poczatek": round(start / ENV_SR, 3), "dlugosc": round(len(env) / ENV_SR, 3)}


def piki(on: list[float], odstep: float = 0.08) -> list[tuple[float, float]]:
    """Uderzenia z funkcji wejść: lokalne szczyty ≥ 30% wysokiego poziomu (95. centyl), co najmniej `odstep` s od
    siebie (mocniejszy wygrywa), czas dokładniej niż okno 10 ms (parabola przez szczyt i sąsiadów)."""
    dodatnie = sorted(v for v in on if v > 0)
    if not dodatnie:
        return []
    prog = 0.3 * dodatnie[int(0.95 * (len(dodatnie) - 1))]
    kand = sorted((i for i in range(1, len(on) - 1) if on[i] >= prog and on[i] >= on[i - 1] and on[i] > on[i + 1]),
                  key=lambda i: -on[i])
    d, zajete, wybrane = max(1, int(odstep * ENV_SR)), bytearray(len(on)), []
    for i in kand:
        if not zajete[i]:
            wybrane.append(i)
            zajete[max(0, i - d + 1):i + d] = b"\x01" * (min(len(on), i + d) - max(0, i - d + 1))
    out = []
    for i in sorted(wybrane):
        a, b, c = on[i - 1], on[i], on[i + 1]
        mian = a - 2 * b + c
        out.append(((i + (max(-0.5, min(0.5, 0.5 * (a - c) / mian)) if mian else 0.0)) / ENV_SR, b))
    return out


def uderzenia_pasm(path: Path, env: list[float], start: float = 0.0, end: float | None = None) -> list[dict]:
    """Uderzenia stopy, werbla i talerzy: [{t, s, k}] po czasie; s 0–1 = ostrość wejścia × głośność pasma.
    Pasmo dużo cichsze od całości (stopa i werbel −26 dB, talerze −40 dB) nie gra: to przeciek z innych pasm."""
    def gora(x):
        return sorted(x)[int(0.99 * (len(x) - 1))] if x else 0.0
    caly = gora(env) or 1.0
    wynik = []
    for k, (filtry, sr) in PASMA.items():
        envs = [envelope(path, start, end, f, sr) for f in filtry]
        if min(gora(e) for e in envs) < caly * (0.01 if k == "talerz" else 0.05):
            continue
        ons = [onsets(e) for e in envs]
        n = min(len(o) for o in ons)
        on = [math.prod(o[i] for o in ons) ** (1 / len(ons)) for i in range(n)]   # werbel: ciało i trzask naraz
        gory = [gora(e) or 1.0 for e in envs]
        pk = piki(on, 0.05 if k == "talerz" else 0.08)
        o_max = max((v for _, v in pk), default=0.0) or 1.0
        for t, v in pk:
            i = min(n - 1, int(round(t * ENV_SR)))
            # głośność w każdym podpaśmie osobno (werbel: ciało I trzask), względem jego zwykłego poziomu: wejście
            # liczone z przyrostu (log) widzi też ciche przecieki, np. stopę w paśmie werbla
            glos = min(max(e[max(0, i - 1):i + 4]) / g for e, g in zip(envs, gory))
            if glos >= 0.15:
                wynik.append({"t": round(start + t, 3), "s": round(min(1.0, math.sqrt(v / o_max * glos)), 2), "k": k})
    return sorted(wynik, key=lambda u: u["t"])


def najblizszy(czasy: list[float], t: float) -> float | None:
    """Najbliższy czas z posortowanej listy."""
    i = bisect.bisect_left(czasy, t)
    return min(czasy[max(0, i - 1):i + 1], key=lambda x: abs(x - t), default=None)


def ocena_siatki(first: float, period: float, dur: float, uderzenia: list[dict], start: float = 0.0) -> dict:
    """Jak dobrze siatka (pierwszy bit + k·okres) leży na prawdziwych uderzeniach stopy i werbla:
    trafienia = bity z uderzeniem w ±35 ms (w części, w której gra perkusja), na_bitach = mocne uderzenia stopy
    i werbla na bitach (na_polbitach: na bitach albo w połowie, stopa_na_bitach: sama stopa), średni błąd i dryf
    (rozjazd od początku do końca) w ms. Ocena: pewna / dobra / niepewna (wtedy sprawdź uchem)."""
    mocne = sorted(u["t"] - start for u in uderzenia if u["k"] in ("stopa", "werbel") and u["s"] >= 0.2)
    stopy = [u["t"] - start for u in uderzenia if u["k"] == "stopa" and u["s"] >= 0.3]
    if len(mocne) < 4:
        return {"trafienia": 0.0, "na_bitach": 0.0, "na_polbitach": 0.0, "stopa_na_bitach": 0.0, "sredni_blad_ms": None,
                "dryf_ms": None, "ocena": "niepewna"}
    bity = [first + k * period for k in range(int((dur - first) / period) + 1)]
    bity = [b for b in bity if mocne[0] - TOL <= b <= mocne[-1] + TOL] or bity
    bledy = [(b, u - b) for b in bity if (u := najblizszy(mocne, b)) is not None and abs(u - b) <= TOL]
    traf = len(bledy) / len(bity)
    na_bit = sum(1 for t in mocne if abs(najblizszy(bity, t) - t) <= TOL) / len(mocne)
    polbity = sorted(bity + [b + period / 2 for b in bity])
    na_pol = sum(1 for t in mocne if abs(najblizszy(polbity, t) - t) <= TOL) / len(mocne)
    stopa = (sum(1 for t in stopy if abs(najblizszy(bity, t) - t) <= TOL) / len(stopy)) if stopy else na_bit
    sredni = sum(abs(e) for _, e in bledy) / len(bledy) * 1000 if bledy else None
    dryf = None
    if len(bledy) >= 4:
        mb, me = sum(b for b, _ in bledy) / len(bledy), sum(e for _, e in bledy) / len(bledy)
        var = sum((b - mb) ** 2 for b, _ in bledy)
        nach = sum((b - mb) * (e - me) for b, e in bledy) / var if var else 0.0
        dryf = abs(nach) * (bledy[-1][0] - bledy[0][0]) * 1000
    sr_ms = 99.0 if sredni is None else sredni
    ocena = ("pewna" if traf >= 0.85 and na_pol >= 0.85 and sr_ms <= 10 and (dryf or 0.0) <= 10 else
             "dobra" if traf >= 0.6 and na_pol >= 0.7 and sr_ms <= 15 else "niepewna")
    return {"trafienia": round(traf, 3), "na_bitach": round(na_bit, 3), "na_polbitach": round(na_pol, 3),
            "stopa_na_bitach": round(stopa, 3),
            "sredni_blad_ms": round(sredni, 1) if sredni is not None else None,
            "dryf_ms": round(dryf, 1) if dryf is not None else None, "ocena": ocena}


def dopasuj_siatke(first: float, period: float, uderzenia: list[dict], dur: float,
                   start: float = 0.0) -> tuple[float, float]:
    """Siatka dopasowana do uderzeń stopy i werbla (bit = atak bębna): każde mocne uderzenie przypisane do
    najbliższego bitu (w 1/5 bitu; wcześniej sama faza z mediany odchyłek), prosta najmniejszych kwadratów czas = pierwszy + k·okres, w coraz dłuższym
    oknie (10, 20, 40… s), żeby mały błąd tempa nie zdążył się rozjechać. Wejście z całego pasma potrafi wypaść
    kilkadziesiąt ms przed atakiem stopy, a 0,7 BPM błędu to pół sekundy rozjazdu po minucie."""
    mocne = sorted(u["t"] - start for u in uderzenia if u["k"] in ("stopa", "werbel") and u["s"] >= 0.3)
    f, T = first, period
    d = sorted(x for t in mocne if t <= 20.0 and abs(x := t - f - round((t - f) / T) * T) < T / 3)
    if len(d) >= 4:
        f += d[len(d) // 2]                                       # najpierw sama faza (mediana odchyłek)
    for koniec in (10.0, 20.0, 40.0, 80.0, 160.0, 320.0, dur):
        pts = [(k, t) for t in mocne if t <= koniec and abs(t - f - (k := round((t - f) / T)) * T) < T / 5]
        n = len(pts)
        if n >= 6:
            mk, mt = sum(k for k, _ in pts) / n, sum(t for _, t in pts) / n
            var = sum((k - mk) ** 2 for k, _ in pts)
            nowy = sum((k - mk) * (t - mt) for k, t in pts) / var if var else T
            if abs(nowy - T) < 0.03 * T:
                f, T = mt - nowy * mk, nowy
        if koniec >= dur:
            break
    return f % T, T


def wybierz_siatke(first: float, period: float, dur: float, uderzenia: list[dict], start: float = 0.0):
    """Tempo podwójne albo połowiczne to częsta pomyłka (70 BPM zgłoszone jako 140). Najpierw siatka ósemek
    dopasowana do uderzeń (więcej punktów zaczepienia, także przy swingu), z niej kandydaci 2×, 1× (dwie fazy)
    i 0,5× (cztery fazy); ocena = bity z uderzeniem × uderzenia na bitach (stopa liczy się podwójnie).
    Zostaje 1×, chyba że inne tempo jest wyraźnie lepsze (o 0,2): za szybka siatka ma puste bity, za wolna gubi
    co drugie uderzenie (np. werbel na 2 i 4)."""
    f8, t8 = dopasuj_siatke(first, period / 2, uderzenia, dur, start)
    kand = [(1.0, f8 + j * t8, 2 * t8) for j in (0, 1)]
    if 60 / t8 <= 210:
        kand.append((2.0, f8, t8))
    if 60 / (4 * t8) >= 55:
        kand += [(0.5, f8 + j * t8, 4 * t8) for j in range(4)]
    oceny = [(m, f % p, p, ocena_siatki(f % p, p, dur, uderzenia, start)) for m, f, p in kand]
    wynik = lambda o: o[3]["trafienia"] * (o[3]["na_bitach"] + o[3]["stopa_na_bitach"]) / 2   # noqa: E731
    najlepsze = {m: max((o for o in oceny if o[0] == m), key=wynik) for m in {o[0] for o in oceny}}
    best = najlepsze[1.0]
    inne = [o for m, o in najlepsze.items() if m != 1.0 and wynik(o) >= wynik(best) + 0.2]
    if inne:
        best = max(inne, key=wynik)
    return best[1], best[2], {**best[3], "mnoznik": best[0],
                              "kandydaci": {f"{m:g}x": round(wynik(o), 3) for m, o in sorted(najlepsze.items())}}


def najmocniejsze(uderzenia: list[dict], bity: list[float], okres: float, ile: int = 3) -> list[dict]:
    """2–3 najmocniejsze stopy na film, co najmniej 16 bitów od siebie: tylko tu uderzenie całego kadru.
    Najpierw stopy na bicie (uderzenie kadru idzie z cięciem na siatce), spoza bitu tylko, gdy tamtych zabraknie;
    nic w pierwszej sekundzie od pierwszego bitu (uderzenie potrzebuje czegoś przed sobą)."""
    if not bity:
        return []
    kandydaci = []
    for u in uderzenia:
        if u["k"] == "stopa" and u["t"] >= bity[0] + 1.0 - TOL:
            b = najblizszy(bity, u["t"])
            kandydaci.append({"t": u["t"], "s": u["s"], "bit": bity.index(b), "na_bicie": abs(b - u["t"]) <= TOL})
    out: list[dict] = []
    for na_bicie in (True, False):
        for k in sorted((k for k in kandydaci if k["na_bicie"] == na_bicie), key=lambda k: -k["s"]):
            if len(out) < ile and all(abs(k["t"] - o["t"]) >= NAJ_ODSTEP * okres for o in out):
                out.append(k)
    return sorted(out, key=lambda o: o["t"])


def takty_info(env: list[float], bars: list[float], uderzenia: list[dict], start: float, dur: float) -> list[dict]:
    """Każdy takt: energia 0–1 (względem najgłośniejszego taktu) i liczba uderzeń talerzy (gęstość drobnego ruchu)."""
    granice = bars + [start + dur]
    srednie = []
    for a, b in zip(granice, granice[1:]):
        seg = env[int((a - start) * ENV_SR):int((b - start) * ENV_SR)]
        srednie.append(sum(seg) / len(seg) if seg else 0.0)
    top = max(srednie, default=0.0) or 1.0
    talerze = [u["t"] for u in uderzenia if u["k"] == "talerz"]
    return [{"t": a, "do": round(b, 3), "energia": round(e / top, 2), "talerze": sum(1 for t in talerze if a <= t < b)}
            for a, b, e in zip(granice, granice[1:], srednie)]


def opis_talerzy(info: list[dict]) -> list[str]:
    """Odcinki taktów według gęstości talerzy (gęsto ≥ 6 na takt, rzadko ≤ 2): gdzie drobny ruch, gdzie spokój."""
    klasa = lambda n: "gęsto" if n >= 6 else "rzadko" if n <= 2 else "średnio"   # noqa: E731
    out, i = [], 0
    while i < len(info):
        j = i
        while j + 1 < len(info) and klasa(info[j + 1]["talerze"]) == klasa(info[i]["talerze"]):
            j += 1
        nr = f"takt {i + 1}" if i == j else f"takty {i + 1}–{j + 1}"
        out.append(f"{nr} ({info[i]['t']:.1f}–{info[j]['do']:.1f} s): talerze {klasa(info[i]['talerze'])}")
        i = j + 1
    return out


def analyze(path: Path, start: float = 0.0, end: float | None = None) -> dict:
    env = envelope(path, start, end)
    on = onsets(env)
    dur = len(env) / ENV_SR
    bpm = tempo(on)
    first = phase(on, bpm)
    period = 60 / bpm
    first, period = refine(on, first, period, dur)
    uderzenia = uderzenia_pasm(path, env, start, end)
    first, period, siatka = wybierz_siatke(first, period, dur, uderzenia, start)
    bpm = round(60 / period, 1)
    beats = [round(start + first + k * period, 3) for k in range(int((dur - first) / period) + 1)]
    rel = [b - start for b in beats]
    db = downbeat(on, rel)
    bars = beats[db::4]
    d = drop(env, [b - start for b in bars])
    return {"plik": str(path), "bpm": bpm, "bit_s": round(period, 4), "pierwszy_bit": beats[0] if beats else None,
            "bity": beats, "takty": bars, "drop": round(start + d, 3) if d is not None else None,
            "ciecia": {"co_takt": bars, "co_2_bity": beats[db::2]}, "dlugosc": round(dur, 2), "siatka": siatka,
            "uderzenia": uderzenia, "najmocniejsze": najmocniejsze(uderzenia, beats, period),
            "takty_info": takty_info(env, bars, uderzenia, start, dur)}


# ---------------------------------------------------------------- po renderze: czy cięcia trafiają w bit

def ciecia_obrazu(film: Path, prog: float = 0.3) -> list[float]:
    """Cięcia w gotowym filmie (zmiana sceny w zmniejszonym obrazie): czas pierwszej klatki nowego ujęcia."""
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(film), "-an", "-vf",
                        f"scale=320:-2,select='gt(scene,{prog})',showinfo", "-f", "null", "-"], capture_output=True, text=True)
    return [round(float(t), 3) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def fps_filmu(film: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                        "-of", "csv=p=0", str(film)], capture_output=True, text=True)
    try:
        n, _, d = r.stdout.strip().partition("/")
        return float(n) / float(d or 1)
    except ValueError:
        return 30.0


def czasy_planu(dane) -> list[float]:
    """Czasy z pliku planu: lista liczb albo obiektów z t / czas / start / at (np. cues.json), albo słownik
    z listą (ciecia, cuts, cues, zdarzenia; z rytm.json: ciecia.co_takt)."""
    if isinstance(dane, dict):
        for k in ("ciecia", "cuts", "cues", "zdarzenia", "co_takt"):
            if k in dane:
                return czasy_planu(dane[k])
        lista = next((v for v in dane.values() if isinstance(v, list)), [])
        return czasy_planu(lista)
    out = []
    for x in dane or []:
        if isinstance(x, (int, float)):
            out.append(float(x))
        elif isinstance(x, dict) and x.get("na_bit", True) is not False:
            t = next((x[k] for k in ("t", "czas", "start", "at") if isinstance(x.get(k), (int, float))), None)
            if t is not None:
                out.append(float(t))
    return sorted(out)


def czasy_projektu(sciezka: Path) -> list[float]:
    """Cięcia osi projektu edytora (granice klipów), z filmu źródłowego albo wprost z <film>.edycja.json."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import projekt as pr  # noqa: PLC0415  (projekt.py ciągnie edytor HQ: tylko gdy potrzebny)
    proj = json.loads(sciezka.read_text(encoding="utf-8")) if sciezka.name.endswith(".edycja.json") else pr.load(sciezka)
    return [round(s, 3) for n, (_c, s, _e) in enumerate(pr.layout(proj["clips"])) if n]


def sprawdz(film: Path, czasy: list[float], fps: float, start: float = 0.0, end: float | None = None) -> dict:
    """Każde cięcie kontra bit z dźwięku gotowego filmu (i najbliższe mocne uderzenie): błąd w ms i klatkach."""
    r = analyze(film, start, end)
    bity, okres = r["bity"], r["bit_s"]
    polbity = sorted(bity + [b + okres / 2 for b in bity])
    mocne = sorted(u["t"] for u in r["uderzenia"] if u["k"] in ("stopa", "werbel") and u["s"] >= 0.3)
    wiersze = []
    for t in czasy:
        if t < start or (end is not None and t > end):
            continue
        b = najblizszy(bity, t)
        cel, gdzie = b, "bit"
        u = najblizszy(mocne, t)
        if u is not None and abs(u - t) < abs(t - b):
            cel, gdzie = u, "uderzenie"
        pb = najblizszy(polbity, t)
        if abs(t - cel) * fps > 1.5 and abs(t - pb) * fps <= 1.5:
            cel, gdzie = pb, "pół bitu"
        kl = abs(t - cel) * fps
        wiersze.append({"t": t, "cel": round(cel, 3), "do": gdzie, "blad_ms": round((t - cel) * 1000, 1),
                        "blad_kl": round(kl, 2), "bit_blad_ms": round((t - b) * 1000, 1),
                        "ocena": "idealnie" if kl <= 1.5 else "dobrze" if kl <= 3 else "popraw"})
    wspolne = None
    blisko = [w["bit_blad_ms"] / 1000 for w in wiersze if abs(w["bit_blad_ms"]) / 1000 < okres / 4]
    if len(blisko) >= 3:
        sr = sum(blisko) / len(blisko)
        odch = math.sqrt(sum((e - sr) ** 2 for e in blisko) / len(blisko))
        jeden_znak = all(e > 0 for e in blisko) or all(e < 0 for e in blisko)
        if jeden_znak and abs(sr) * fps >= 1 and odch * fps <= 0.5:
            wspolne = round(sr * 1000, 1)
    return {"film": str(film), "fps": round(fps, 3), "bpm": r["bpm"], "siatka": r["siatka"], "ciecia": wiersze,
            "popraw": sum(1 for w in wiersze if w["ocena"] == "popraw"), "wspolne_przesuniecie_ms": wspolne}


def main_sprawdz(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="rytm.py sprawdz", description="Po renderze: czy cięcia trafiają w bit.")
    ap.add_argument("film")
    zr = ap.add_mutually_exclusive_group()
    zr.add_argument("--plan", help="JSON z czasami (cues.json, plan cięć, rytm.json)")
    zr.add_argument("--projekt", help="film źródłowy projektu edytora albo <film>.edycja.json: granice klipów")
    zr.add_argument("--ciecia", help="czasy cięć w s, po przecinku")
    ap.add_argument("--fps", type=float, help="domyślnie z filmu")
    ap.add_argument("--od", type=float, default=0.0)
    ap.add_argument("--do", type=float)
    ap.add_argument("--json", help="zapisz raport do pliku JSON")
    a = ap.parse_args(argv)
    film = Path(a.film)
    if a.plan:
        czasy, skad = czasy_planu(json.loads(Path(a.plan).read_text(encoding="utf-8"))), "plan"
    elif a.projekt:
        czasy, skad = czasy_projektu(Path(a.projekt)), "projekt"
    elif a.ciecia:
        czasy, skad = sorted(float(x) for x in a.ciecia.split(",") if x.strip()), "lista"
    else:
        czasy, skad = ciecia_obrazu(film), "obraz"
    if not czasy:
        raise SystemExit("brak cięć do sprawdzenia (w obrazie nie wykryto zmian scen: podaj --plan, --projekt albo --ciecia)")
    r = sprawdz(film, czasy, a.fps or fps_filmu(film), a.od, a.do)
    r["zrodlo_ciec"] = skad
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    s = r["siatka"]
    print(f"{film.name}: {r['bpm']} BPM, siatka {s['ocena']} (bity z uderzeniem {s['trafienia']:.0%}, uderzenia na "
          f"bitach {s['na_bitach']:.0%}) · cięcia: {len(r['ciecia'])} ({skad}) · {r['fps']:g} kl./s")
    if s["ocena"] == "niepewna":
        print("⚠ siatka niepewna (mowa, swobodne tempo albo brak perkusji): wynik orientacyjny, sprawdź uchem")
    for w in r["ciecia"]:
        znak = {"idealnie": "✓", "dobrze": "·", "popraw": "✗"}[w["ocena"]]
        print(f"  {znak} {w['t']:7.3f} s → {w['do']} {w['cel']:.3f} s: {w['blad_ms']:+.0f} ms ({w['blad_kl']:.1f} kl.) {w['ocena']}")
    if r["wspolne_przesuniecie_ms"] is not None:
        ms = r["wspolne_przesuniecie_ms"]
        print(f"⚠ wszystkie cięcia przesunięte o {ms:+.0f} ms względem bitów: to przesunięcie dźwięku przy kodowaniu, "
              f"nie błędy cięć. Przesuń całą muzykę (i efekty) o {abs(ms):.0f} ms {'wcześniej' if ms < 0 else 'później'}, "
              "nie poprawiaj cięć po kolei.")
    print(f"Do poprawy: {r['popraw']} (ponad 3 klatki od bitu)" if r["popraw"] else "Wszystkie cięcia w bicie (≤ 3 klatki).")
    return 1 if r["popraw"] else 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["sprawdz"]:
        return main_sprawdz(argv[1:])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plik", nargs="+")
    ap.add_argument("--szczyt", action="store_true", help="efekty dźwiękowe: czas szczytu (przesunięcie przy układaniu)")
    ap.add_argument("--od", type=float, default=0.0)
    ap.add_argument("--do", type=float)
    ap.add_argument("--json", help="zapisz wynik do pliku JSON")
    a = ap.parse_args(argv)
    if a.szczyt:
        res = [peak(Path(f)) for f in a.plik]
        for r in res:
            print(f"{Path(r['plik']).name}: szczyt {r['szczyt']:.3f} s (początek {r['poczatek']:.3f} s, długość {r['dlugosc']:.2f} s)"
                  f" → start efektu = chwila zdarzenia − {r['szczyt']:.3f} s")
        if a.json:
            Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        return 0
    a.plik = a.plik[0]
    r = analyze(Path(a.plik), a.od, a.do)
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    bars = ", ".join(f"{t:.2f}" for t in r["takty"][:12]) + (" …" if len(r["takty"]) > 12 else "")
    print(f"{Path(a.plik).name}: {r['bpm']} BPM (bit co {r['bit_s']:.3f} s), pierwszy bit {r['pierwszy_bit']:.2f} s")
    print(f"Takty (tu cięcia): {bars}")
    print(f"Drop: {r['drop']:.2f} s (tu najmocniejsza scena)" if r["drop"] is not None else "Drop: nie wykryto wyraźnego")
    s = r["siatka"]
    print(f"Siatka: {s['ocena']} (bity z uderzeniem {s['trafienia']:.0%}, uderzenia na bitach {s['na_bitach']:.0%}"
          + (f", średni błąd {s['sredni_blad_ms']:.0f} ms" if s["sredni_blad_ms"] is not None else "")
          + (f", tempo ×{s['mnoznik']:g} względem pierwszego pomiaru" if s["mnoznik"] != 1 else "") + ")")
    ile = {k: sum(1 for u in r["uderzenia"] if u["k"] == k) for k in PASMA}
    print("Uderzenia: " + ", ".join(f"{k} {n}" for k, n in ile.items()))
    if r["najmocniejsze"]:
        print("Najmocniejsze (tylko tu uderzenie całego kadru): " + ", ".join(
            f"{o['t']:.2f} s" + ("" if o["na_bicie"] else " (między bitami)") for o in r["najmocniejsze"]))
    if ile["talerz"]:
        linie = opis_talerzy(r["takty_info"])
        for linia in linie[:6]:
            print("  " + linia)
        if len(linie) > 6:
            print(f"  … i {len(linie) - 6} kolejnych odcinków (pełna lista: --json, klucz takty_info)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
