#!/usr/bin/env python3
"""Krytyka reżyserska: narzędzia, którymi film ogląda się jak surowy motion director, nie dumny autor.

    python3 krytyka.py telefon film.mp4 [-o out/wideo/<film>/telefon.jpg]      # 1 kl./s w 360 px szer., siatka 5×N
    python3 krytyka.py pasek film.mp4 --t 4.2 [--klatek 12] [-o pasek.jpg]    # kolejne klatki wokół szybkiej akcji
    python3 krytyka.py martwe film.mp4 [--prog 2.5]                           # odcinki bez zmiany obrazu (martwy takt)
    python3 krytyka.py petla film.mp4 [-o petla.mp4]                          # szew pętli: ostatnia vs pierwsza klatka
    python3 krytyka.py determinizm anim.html --czasy 1.3,4.2 [--preset jarvo]  # ta sama klatka 2× = ten sam obraz
    python3 krytyka.py ocena kontrola.json                                    # czy runda spełnia pętlę (7 osi ≥ 8)

Wszystko działa na gotowym MP4 z dowolnego silnika (poza `determinizm`, który renderuje HTML przez html_wideo.py).
Obrazy oglądasz przez vision_analyze. Kod wyjścia: 0 = ok, 1 = znaleziony problem, 2 = złe wejście. --json dla maszyn.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wideo_lib as wl  # noqa: E402

OSIE = ["hook", "telefon", "ruch", "roznorodnosc", "kompozycja", "marka", "dzwiek"]
OSIE_OPIS = {
    "hook": "haczyk w pierwszych 2 s",
    "telefon": "czytelność w 360 px szerokości",
    "ruch": "jakość ruchu: sprężyny, wyhamowanie, zero martwych klatek",
    "roznorodnosc": "nowa rzecz co 2–4 s",
    "kompozycja": "kadr, hierarchia, oddech; zero zakazanych chwytów",
    "marka": "kolory, fonty, logo, ton z kitu",
    "dzwiek": "dźwięk na bitach i zdarzeniach, −14 LUFS",
}


def ff(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([wl.need("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", *args],
                          capture_output=True, text=True)


def telefon(film: Path, out: Path) -> dict:
    dur = wl.duration(film)
    rows = max(1, -(-int(dur) // 5))
    r = ff(["-i", str(film), "-vf", f"fps=1,scale=360:-2,tile=5x{rows}:padding=6:color=0x202020", "-frames:v", "1", str(out)])
    if r.returncode:
        raise SystemExit(f"✗ ffmpeg: {r.stderr.strip()[:300]}")
    return {"arkusz": str(out), "klatek": int(dur), "pytanie": "czy każdy tekst da się przeczytać na tym rozmiarze?"}


def pasek(film: Path, t: float, n: int, out: Path) -> dict:
    fps = float(eval_fps(film))
    start = max(0.0, t - (n / 2) / fps)
    r = ff(["-ss", f"{start:.3f}", "-i", str(film), "-vf", f"scale=320:-2,tile={n}x1:padding=4:color=0x202020",
            "-frames:v", "1", str(out)])
    if r.returncode:
        raise SystemExit(f"✗ ffmpeg: {r.stderr.strip()[:300]}")
    return {"pasek": str(out), "od": round(start, 3), "klatek": n,
            "szukaj": "wyskoki (pop), nachodzący tekst, przejazd bez wyhamowania, zła strona ruchu"}


def eval_fps(film: Path) -> float:
    p = wl.probe(film)
    for s in p.get("streams", []):
        if s.get("codec_type") == "video":
            num, _, den = (s.get("avg_frame_rate") or "30/1").partition("/")
            return float(num) / float(den or 1) if float(num) else 30.0
    return 30.0


def roznice(film: Path, fps: float = 5.0) -> list[float]:
    """Średnia bezwzględna różnica kolejnych klatek (64×64, szarość), co 1/fps s."""
    r = subprocess.run([wl.need("ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", str(film), "-vf",
                        f"fps={fps},scale=64:64,format=gray", "-f", "rawvideo", "-"], capture_output=True)
    raw = r.stdout
    k = 64 * 64
    frames = [raw[i:i + k] for i in range(0, len(raw) - k + 1, k)]
    return [sum(abs(a - b) for a, b in zip(frames[i - 1], frames[i])) / k for i in range(1, len(frames))]


def martwe(film: Path, prog: float, fps: float = 5.0) -> dict:
    d = roznice(film, fps)
    odc, start = [], None
    for i, v in enumerate(d + [99.0]):
        if v < 0.6:           # praktycznie ta sama klatka (poniżej szumu kompresji)
            start = i if start is None else start
        elif start is not None:
            dl = (i - start) / fps
            if dl >= prog:
                odc.append({"od": round(start / fps, 2), "do": round(i / fps, 2), "sek": round(dl, 2)})
            start = None
    # koniec filmu: celowy „hold” na logo do 2 s jest ok
    dur = len(d) / fps
    odc = [o for o in odc if not (o["do"] >= dur - 0.3 and o["sek"] <= 2.5)]
    return {"martwe": odc, "prog_s": prog, "ok": not odc}


def petla(film: Path, out: Path | None) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        a, b = Path(tmp) / "a.gray", Path(tmp) / "b.gray"
        ff(["-i", str(film), "-vf", "scale=96:96,format=gray", "-frames:v", "1", "-f", "rawvideo", str(a)])
        ff(["-sseof", "-0.2", "-i", str(film), "-vf", "scale=96:96,format=gray", "-update", "1", "-f", "rawvideo", str(b)])
        pa, pb = a.read_bytes(), b.read_bytes()
    diff = sum(abs(x - y) for x, y in zip(pa, pb)) / max(1, len(pa))
    wynik = {"roznica_szwu": round(diff, 2), "ok": diff < 4.0,
             "uwaga": "ostatnia klatka = pierwsza (także pozycja i prędkość kursora); różnica < 4 = szew niewidoczny"}
    if out:
        ff(["-stream_loop", "1", "-i", str(film), "-c", "copy", str(out)])
        wynik["podglad"] = str(out)
    return wynik


def determinizm(src: str, czasy: str, preset: str) -> dict:
    hashes = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, str(Path(__file__).with_name("html_wideo.py")), "klatki", src,
                                "--czasy", czasy, "--preset", preset, "--out", tmp], capture_output=True, text=True)
            if r.returncode:
                raise SystemExit(f"✗ html_wideo: {(r.stderr or r.stdout).strip()[-400:]}")
            hashes.append([hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in sorted(Path(tmp).glob("*.png"))])
    rozne = [t for t, a, b in zip(czasy.split(","), *hashes) if a != b]
    return {"czasy": czasy.split(","), "ok": not rozne and bool(hashes[0]), "rozne_klatki": rozne,
            "uwaga": "różnica = Math.random bez ziarna, zegar, stan między klatkami albo animacja CSS"}


def ocena(plik: Path) -> dict:
    k = json.loads(plik.read_text(encoding="utf-8"))
    osie = k.get("osie") or {}
    brak = [o for o in OSIE if o not in osie]
    slabe = {o: v for o, v in osie.items() if isinstance(v, (int, float)) and v < 8}
    problemy = k.get("problemy") or []
    bez_czasu = [p for p in problemy if not isinstance(p, dict) or "t" not in p]
    ok = not brak and not slabe and not bez_czasu
    return {"runda": k.get("runda"), "ok": ok, "brak_osi": brak, "ponizej_8": slabe,
            "problemy_bez_czasu": len(bez_czasu),
            "dalej": "PASS pętli: wszystkie osie ≥ 8" if ok else "popraw 3 najgorsze problemy, render tylko tych sekund, nowa runda"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("telefon"); s.add_argument("film"); s.add_argument("-o")
    s = sub.add_parser("pasek"); s.add_argument("film"); s.add_argument("--t", type=float, required=True)
    s.add_argument("--klatek", type=int, default=12); s.add_argument("-o")
    s = sub.add_parser("martwe"); s.add_argument("film"); s.add_argument("--prog", type=float, default=2.5)
    s = sub.add_parser("petla"); s.add_argument("film"); s.add_argument("-o")
    s = sub.add_parser("determinizm"); s.add_argument("zrodlo"); s.add_argument("--czasy", required=True)
    s.add_argument("--preset", default="jarvo")
    s = sub.add_parser("ocena"); s.add_argument("plik")
    a = ap.parse_args(argv)
    if a.cmd not in ("determinizm",) and not Path(getattr(a, "film", getattr(a, "plik", ""))).exists():
        print("✗ brak pliku", file=sys.stderr)
        return 2
    if a.cmd == "telefon":
        f = Path(a.film); r = telefon(f, Path(a.o or f.with_name(f.stem + "-telefon.jpg")))
    elif a.cmd == "pasek":
        f = Path(a.film); r = pasek(f, a.t, a.klatek, Path(a.o or f.with_name(f"{f.stem}-pasek-{a.t:g}.jpg")))
    elif a.cmd == "martwe":
        r = martwe(Path(a.film), a.prog)
    elif a.cmd == "petla":
        r = petla(Path(a.film), Path(a.o) if a.o else None)
    elif a.cmd == "determinizm":
        r = determinizm(a.zrodlo, a.czasy, a.preset)
    else:
        r = ocena(Path(a.plik))
    print(json.dumps(r, ensure_ascii=False, indent=None if a.json else 2))
    return 0 if r.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
