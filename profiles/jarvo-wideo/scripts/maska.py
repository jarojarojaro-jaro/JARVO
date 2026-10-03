#!/usr/bin/env python3
"""Maska osoby (MODNet, Apache-2.0) dla typografii: gdzie w kadrze jest osoba i jej głowa, żeby napis stanął obok
twarzy, a nie na niej, i klatka po klatce sylwetka do napisu „za osobą” (tekst w tle, osoba przed nim).

    maska.py model                                 # pobierz model raz (26 MB, przypięta suma SHA-256)
    maska.py opis <film> --chwile 1.2,3.4,…        # JSON: osoba i głowa w każdej chwili osi (0–1 kadru)
    maska.py klatki <film> --od 2.15 --do 3.68     # sylwetki klatek osi → <film>.maska/ (PNG z kanałem alfa)

Działa Pythonem narzędzi z obrazu (/opt/jarvo/venv: onnxruntime + numpy); typografia.py woła go sam. Klatki osi
składa jak eksport (klip, czas źródła, dopasowanie kadru), w rozdzielczości modelu (dłuższy bok 512). Sylwetki leżą
w `<film>.maska/` z `indeks.json` (klucz osi: zmiana klipów unieważnia maski; edytor HQ i eksport sprawdzają klucz).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import projekt as pr  # noqa: E402  (oś projektu i silnik edytora: pr.ed)

ed = pr.ed
# MODNet (ZHKKKe/MODNet, Apache-2.0), eksport ONNX „photographic portrait matting” z DavG25/modnet-pretrained-models
MODEL_URL = ("https://huggingface.co/DavG25/modnet-pretrained-models/resolve/903cc06311b3b12071edfa1b42b534e4a31c718a"
             "/models/modnet_photographic_portrait_matting.onnx")
MODEL_SHA256 = "07c308cf0fc7e6e8b2065a12ed7fc07e1de8febb7dc7839d7b7f15dd66584df9"
MODEL_PLIK = "modnet_photographic_portrait_matting.onnx"
BOK = 512                 # dłuższy bok klatki dla modelu (wielokrotność 32)
PROG = 0.5                # piksel należy do osoby, gdy alfa ≥ 0,5


def katalog_modeli() -> Path:
    return Path(os.environ.get("JARVO_MODELS_DIR", "/opt/data/jarvo/models")) / "modnet"


def model() -> Path:
    """Plik modelu: pobrany raz i sprawdzony sumą; zła suma = plik usunięty i błąd (nic nie działa na podmienionym)."""
    dest = katalog_modeli() / MODEL_PLIK
    if dest.is_file() and _sha(dest) == MODEL_SHA256:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(MODEL_URL, timeout=120) as r, tmp.open("wb") as f:   # noqa: S310 (stały adres https)
        while chunk := r.read(1 << 20):
            f.write(chunk)
    if _sha(tmp) != MODEL_SHA256:
        tmp.unlink(missing_ok=True)
        raise SystemExit("model MODNet: zła suma SHA-256 pobranego pliku (nie używam go)")
    tmp.replace(dest)
    return dest


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def rozmiar(W: int, H: int) -> tuple[int, int]:
    """Klatka dla modelu: proporcje kadru, dłuższy bok 512, oba boki wielokrotnością 32."""
    k = BOK / max(W, H)
    return max(32, round(W * k / 32) * 32), max(32, round(H * k / 32) * 32)


def dopasowanie(c: dict, w: int, h: int) -> str:
    """Filtr ffmpeg kadru klipu jak przy eksporcie (pr.kadr_osi), w rozmiarze modelu."""
    if c.get("fit") == "cover":
        return ed.cover_filter(w, h, {"zoom": 1, "fx": 0.5, "fy": 0.5, **c})
    if c.get("fit") == "blur":
        return ed.blur_filter(w, h, 0)
    return f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"


def klatki_osi(proj: dict, numery: list[int], fps: float, w: int, h: int):
    """(numer klatki osi, RGB w×h) dla podanych numerów; jeden ffmpeg na ciągły odcinek w jednym klipie."""
    lay = pr.layout(proj["clips"])
    numery = sorted(set(numery))
    i = 0
    while i < len(numery):
        t0 = numery[i] / fps
        c, s, e = next((x for x in lay if x[1] <= t0 < x[2]), lay[-1])
        j = i
        while j + 1 < len(numery) and numery[j + 1] == numery[j] + 1 and numery[j + 1] / fps < e:
            j += 1
        n = j - i + 1
        sp = float(c.get("speed") or 1)
        u = float(c["in"]) + (t0 - s) * sp
        src = ["-i", str(c["src"])] if c.get("kind") == "image" else ["-ss", f"{max(0.0, u):.3f}", "-i", str(c["src"])]
        chain = f"[0:v]setpts=(PTS-STARTPTS)/{sp},fps={fps},{dopasowanie(c, w, h)}" if c.get("kind") != "image" \
            else f"[0:v]{dopasowanie(c, w, h)}"
        r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", *src, "-filter_complex", chain,
                            "-frames:v", str(1 if c.get("kind") == "image" else n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           capture_output=True, check=True)
        size = w * h * 3
        ramki = [r.stdout[k * size:(k + 1) * size] for k in range(len(r.stdout) // size)]
        for k in range(n):
            if ramki:
                yield numery[i + k], ramki[min(k, len(ramki) - 1)]
        i = j + 1


class Model:
    def __init__(self) -> None:
        import onnxruntime as ort  # type: ignore  # noqa: PLC0415
        so = ort.SessionOptions()
        so.intra_op_num_threads = max(1, min(4, os.cpu_count() or 2))
        so.log_severity_level = 3
        self.s = ort.InferenceSession(str(model()), sess_options=so, providers=["CPUExecutionProvider"])

    def alfa(self, rgb: bytes, w: int, h: int):
        """Sylwetka osoby: tablica h×w, 0 (tło) – 1 (osoba)."""
        import numpy as np  # noqa: PLC0415
        x = np.frombuffer(rgb, dtype=np.uint8).reshape(h, w, 3).astype(np.float32) / 127.5 - 1.0
        out = self.s.run(None, {"input": x.transpose(2, 0, 1)[None]})[0]
        return np.clip(out[0, 0], 0.0, 1.0)


def opis_alfy(a) -> dict:
    """Osoba (ramka sylwetki), głowa (górna część sylwetki do ramion) i pokrycie kadru; współrzędne 0–1."""
    import numpy as np  # noqa: PLC0415
    h, w = a.shape
    m = a >= PROG
    pokrycie = float(m.mean())
    if pokrycie < 0.01:
        return {"osoba": None, "glowa": None, "pokrycie": round(pokrycie, 3)}
    rows, cols = np.where(m.any(axis=1))[0], np.where(m.any(axis=0))[0]
    y0, y1, x0, x1 = int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1
    szer = m.sum(axis=1)
    # głowa: od czubka w dół, aż sylwetka wyraźnie się poszerzy (ramiona) albo minie ~0,6 jej szerokości wysokości
    gora = szer[y0:y0 + max(2, (y1 - y0) // 12)]
    baza = float(np.median(gora[gora > 0])) if (gora > 0).any() else float(szer[y0])
    yg = y0 + 1
    while yg < y1 and szer[yg] <= max(baza * 1.9, baza + w * 0.04) and yg - y0 < 1.5 * max(baza, w * 0.08):
        yg += 1
    yg = max(yg, y0 + int(0.12 * h)) if yg - y0 < 0.06 * h else yg
    # szerokość głowy: w każdym wierszu tylko ciągły odcinek sylwetki pod czubkiem (uniesiona dłoń obok to nie głowa)
    cx = int(np.mean(np.where(m[y0])[0]))
    gx0, gx1 = cx, cx + 1
    for y in range(y0, min(yg, y1)):
        kol = np.where(m[y])[0]
        if not len(kol):
            continue
        k = int(np.argmin(np.abs(kol - cx)))
        przerwy = np.where(np.diff(kol) > 1)[0]
        a = int(kol[przerwy[przerwy < k][-1] + 1]) if (przerwy < k).any() else int(kol[0])
        b = int(kol[przerwy[przerwy >= k][0]]) if (przerwy >= k).any() else int(kol[-1])
        gx0, gx1 = min(gx0, a), max(gx1, b + 1)
    r = lambda v, n: round(v / n, 3)  # noqa: E731
    return {"osoba": [r(x0, w), r(y0, h), r(x1, w), r(y1, h)], "glowa": [r(gx0, w), r(y0, h), r(gx1, w), r(min(yg, y1), h)],
            "pokrycie": round(pokrycie, 3)}


def png_alfa(a, dest: Path) -> Path:
    """Sylwetka jako PNG RGBA: biały z alfą = maska (przeglądarka maskuje nim klatkę, ffmpeg bierze kanał alfa)."""
    import numpy as np  # noqa: PLC0415
    h, w = a.shape
    px = np.empty((h, w, 4), dtype=np.uint8)
    px[..., :3] = 255
    px[..., 3] = np.round(a * 255).astype(np.uint8)
    raw = np.concatenate([np.zeros((h, 1), dtype=np.uint8), px.reshape(h, w * 4)], axis=1).tobytes()
    chunk = lambda t, d: len(d).to_bytes(4, "big") + t + d + (zlib.crc32(t + d) & 0xFFFFFFFF).to_bytes(4, "big")  # noqa: E731
    dest.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", w.to_bytes(4, "big") + h.to_bytes(4, "big") + bytes([8, 6, 0, 0, 0]))
                     + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
    return dest


# ---------------------------------------------------------------- polecenia

def cmd_model(_a) -> int:
    print(model())
    return 0


def cmd_opis(a) -> int:
    proj = pr.load(Path(a.film).resolve())
    cv = proj["canvas"]
    fps = float(cv["fps"])
    w, h = rozmiar(cv["w"], cv["h"])
    chwile = [float(x) for x in a.chwile.split(",") if x.strip()]
    numery = {int(t * fps): t for t in chwile}
    m = Model()
    po_numerze = {k: opis_alfy(m.alfa(rgb, w, h)) for k, rgb in klatki_osi(proj, list(numery), fps, w, h)}
    print(json.dumps([{"t": t, **po_numerze.get(k, {"osoba": None, "glowa": None, "pokrycie": 0.0})}
                      for k, t in sorted(numery.items())], ensure_ascii=False))
    return 0


def cmd_klatki(a) -> int:
    film = Path(a.film).resolve()
    proj = pr.load(film)
    cv = proj["canvas"]
    fps = float(cv["fps"])
    w, h = rozmiar(cv["w"], cv["h"])
    total = pr.total(proj)
    od, do = max(0.0, float(a.od)), min(total, float(a.do))
    d = ed.maska_dir(film)
    d.mkdir(exist_ok=True)
    klucz = ed.maska_klucz(proj)
    idx_p = d / "indeks.json"
    try:
        idx = json.loads(idx_p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        idx = {}
    if idx.get("klucz") != klucz or idx.get("fps") != fps:      # inna oś: stare sylwetki nie pasują do klatek
        for p in d.glob("k*.png"):
            p.unlink()
        idx = {"klucz": klucz, "fps": fps, "w": w, "h": h, "klatki": []}
    gotowe = set(idx["klatki"])
    numery = [k for k in range(int(od * fps), max(int(od * fps) + 1, int(round(do * fps))))
              if k not in gotowe or not (d / f"k{k:06d}.png").exists()]       # policzone wcześniej zostają
    nowe = []
    if numery:
        m = Model()
        for k, rgb in klatki_osi(proj, numery, fps, w, h):
            png_alfa(m.alfa(rgb, w, h), d / f"k{k:06d}.png")
            nowe.append(k)
    idx["klatki"] = sorted(gotowe | set(nowe))
    idx_p.write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    print(f"Maska: {len(nowe)} nowych klatek {od:.2f}–{do:.2f} s → {d}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("model", help="pobierz i sprawdź model").set_defaults(fn=cmd_model)
    sp = sub.add_parser("opis", help="osoba i głowa w chwilach osi (JSON)")
    sp.add_argument("film")
    sp.add_argument("--chwile", required=True, help="sekundy osi po przecinku")
    sp.set_defaults(fn=cmd_opis)
    sp = sub.add_parser("klatki", help="sylwetki klatek osi do napisu za osobą")
    sp.add_argument("film")
    sp.add_argument("--od", type=float, required=True)
    sp.add_argument("--do", type=float, required=True)
    sp.set_defaults(fn=cmd_klatki)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
