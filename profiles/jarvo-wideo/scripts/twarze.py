#!/usr/bin/env python3
"""Twarze w nagraniu (YuNet z OpenCV Zoo, MIT): gdzie są twarze w chwilach źródła, żeby kadr 9:16 stał na mówcy
sam, bez zgadywania fx/fy z arkusza klatek.

    twarze.py model                                          # pobierz model raz (230 KB, przypięta suma SHA-256)
    twarze.py wykryj <nagranie> --odcinki 10-35.5,60-80 [--co 0.5]

wykryj: JSON {"w", "h", "co", "probki": [[t, [[x0, y0, x1, y1, pewnosc, oczy i usta: 10 liczb], …]], …]} ze
współrzędnymi 0–1 klatki źródła (po obrocie z telefonu). Próbki leżą na stałej siatce co `co` sekund, więc odcinki
różnych rolek dzielą wyniki: policzone próbki zostają w <nagranie>.twarze.json obok nagrania.

Działa Pythonem narzędzi z obrazu (/opt/jarvo/venv: onnxruntime + numpy, bez OpenCV); klipy.py woła go sam.
Klatka: dłuższy bok 640 (wejście modelu 640×640 z dopełnieniem), dekodowanie wyjść jak cv::FaceDetectorYN.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wideo_lib as wl  # noqa: E402  (probe z obrotem)

# YuNet 2023mar (Shiqi Yu, MIT) z repozytorium OpenCV na Hugging Face, przypięty commit
MODEL_URL = ("https://huggingface.co/opencv/face_detection_yunet/resolve/3cc26e7f1014a5ee5d74a42acee58bafc9d0a310"
             "/face_detection_yunet_2023mar.onnx")
MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
MODEL_PLIK = "face_detection_yunet_2023mar.onnx"
BOK = 640                 # wejście modelu 640×640
PEWNOSC = 0.7             # twarz, gdy wynik ≥ 0,7 (OpenCV w przykładzie 0,9; niżej łapie też twarz z profilu)
NMS = 0.3
CO = 0.5                  # domyślnie dwie próbki na sekundę


def katalog_modeli() -> Path:
    return Path(os.environ.get("JARVO_MODELS_DIR", "/opt/data/jarvo/models")) / "yunet"


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def model() -> Path:
    """Plik modelu: pobrany raz i sprawdzony sumą; zła suma = plik usunięty i błąd."""
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
        raise SystemExit("model YuNet: zła suma SHA-256 pobranego pliku (nie używam go)")
    tmp.replace(dest)
    return dest


def rozmiar(W: int, H: int) -> tuple[int, int]:
    """Klatka dla modelu: proporcje źródła, dłuższy bok 640, boki parzyste."""
    k = BOK / max(W, H)
    return max(2, int(W * k) // 2 * 2), max(2, int(H * k) // 2 * 2)


def dekoduj(wyj: dict, w: int, h: int, prog: float = PEWNOSC, nms: float = NMS) -> list[list[float]]:
    """Wyjścia YuNet (cls/obj/bbox/kps na krokach 8, 16, 32) → twarze w pikselach klatki w×h po NMS:
    [x0, y0, x1, y1, pewność, 5 punktów (oko P, oko L, nos, usta P, usta L) × (x, y)]."""
    import numpy as np  # noqa: PLC0415
    wiersze = []
    for s in (8, 16, 32):
        cols = BOK // s
        cls = np.clip(wyj[f"cls_{s}"][0, :, 0], 0, 1)
        obj = np.clip(wyj[f"obj_{s}"][0, :, 0], 0, 1)
        score = np.sqrt(cls * obj)
        ok = np.where(score >= prog)[0]
        if not len(ok):
            continue
        c, r = (ok % cols).astype(np.float32), (ok // cols).astype(np.float32)
        bb, kp = wyj[f"bbox_{s}"][0, ok], wyj[f"kps_{s}"][0, ok]
        cx, cy = (c + bb[:, 0]) * s, (r + bb[:, 1]) * s
        bw, bh = np.exp(bb[:, 2]) * s, np.exp(bb[:, 3]) * s
        pk = np.empty((len(ok), 10), dtype=np.float32)
        pk[:, 0::2] = (kp[:, 0::2] + c[:, None]) * s
        pk[:, 1::2] = (kp[:, 1::2] + r[:, None]) * s
        wiersze.append(np.column_stack([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2, score[ok], pk]))
    if not wiersze:
        return []
    d = np.concatenate(wiersze)
    d = d[np.argsort(-d[:, 4])]
    zostaja = []
    while len(d):
        a = d[0]
        zostaja.append(a)
        ix0, iy0 = np.maximum(a[0], d[1:, 0]), np.maximum(a[1], d[1:, 1])
        ix1, iy1 = np.minimum(a[2], d[1:, 2]), np.minimum(a[3], d[1:, 3])
        inter = np.clip(ix1 - ix0, 0, None) * np.clip(iy1 - iy0, 0, None)
        pole = lambda x: (x[..., 2] - x[..., 0]) * (x[..., 3] - x[..., 1])  # noqa: E731
        iou = inter / np.maximum(pole(a) + pole(d[1:]) - inter, 1e-6)
        d = d[1:][iou <= nms]
    out = []
    for f in zostaja:       # tylko twarze, których środek jest w klatce (dopełnienie modelu nie ma twarzy)
        if 0 <= (f[0] + f[2]) / 2 < w and 0 <= (f[1] + f[3]) / 2 < h:
            out.append([float(v) for v in f])
    return out


class Detektor:
    def __init__(self) -> None:
        import onnxruntime as ort  # type: ignore  # noqa: PLC0415
        so = ort.SessionOptions()
        so.intra_op_num_threads = max(1, min(4, os.cpu_count() or 2))
        so.log_severity_level = 3
        self.s = ort.InferenceSession(str(model()), sess_options=so, providers=["CPUExecutionProvider"])
        self.nazwy = [o.name for o in self.s.get_outputs()]

    def twarze(self, rgb: bytes, w: int, h: int) -> list[list[float]]:
        """Klatka RGB w×h (dłuższy bok ≤ 640) → twarze ze współrzędnymi 0–1 klatki."""
        import numpy as np  # noqa: PLC0415
        x = np.zeros((BOK, BOK, 3), dtype=np.float32)
        x[:h, :w] = np.frombuffer(rgb, dtype=np.uint8).reshape(h, w, 3)[:, :, ::-1]   # BGR jak OpenCV, bez skalowania
        wyj = dict(zip(self.nazwy, self.s.run(None, {"input": x.transpose(2, 0, 1)[None]})))
        out = []
        for f in dekoduj(wyj, w, h):
            xy = [f[k] / (w if k % 2 == 0 else h) for k in range(4)]
            kp = [f[5 + k] / (w if k % 2 == 0 else h) for k in range(10)]
            out.append([round(v, 4) for v in (*xy, f[4], *kp)])
        return out


def siatka(od: float, do: float, co: float = CO) -> list[float]:
    """Chwile próbek odcinka na stałej siatce (wspólne dla nakładających się odcinków)."""
    k0, k1 = math.ceil(od / co - 1e-9), math.floor(do / co + 1e-9)
    return [round(k * co, 3) for k in range(k0, k1 + 1)]


def klatki(src: Path, chwile: list[float], w: int, h: int):
    """(chwila, RGB w×h) dla chwil siatki; jeden ffmpeg na ciąg sąsiednich chwil (fps = 1/co)."""
    i = 0
    while i < len(chwile):
        j = i
        while j + 1 < len(chwile) and chwile[j + 1] - chwile[j] < 1.5 * (chwile[1] - chwile[0] if len(chwile) > 1 else 1):
            j += 1
        co = (chwile[j] - chwile[i]) / (j - i) if j > i else 1.0
        n = j - i + 1
        r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-ss", f"{chwile[i]:.3f}",
                            "-i", str(src), "-vf", f"fps={1 / co:.6f},scale={w}:{h}", "-frames:v", str(n),
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
        size = w * h * 3
        for k in range(min(n, len(r.stdout) // size)):
            yield chwile[i + k], r.stdout[k * size:(k + 1) * size]
        i = j + 1


def pamiec_path(src: Path) -> Path:
    return src.with_name(src.stem + ".twarze.json")


def wykryj(src: Path, odcinki: list[tuple[float, float]], co: float = CO) -> dict:
    v = wl.probe(src).get("video") or {}
    W, H = int(v.get("width") or 0), int(v.get("height") or 0)
    if not W or not H:
        raise SystemExit(f"{src.name}: brak obrazu (twarze tylko z wideo)")
    w, h = rozmiar(W, H)
    pp = pamiec_path(src)
    try:
        pam = json.loads(pp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pam = {}
    if pam.get("model") != MODEL_SHA256[:12] or pam.get("co") != co or pam.get("w") != W or pam.get("h") != H:
        pam = {"model": MODEL_SHA256[:12], "co": co, "w": W, "h": H, "probki": {}}
    chwile = sorted({t for od, do in odcinki for t in siatka(od, do, co)})
    brak = [t for t in chwile if f"{t:.3f}" not in pam["probki"]]
    if brak:
        det = Detektor()
        for t, rgb in klatki(src, brak, w, h):
            pam["probki"][f"{t:.3f}"] = det.twarze(rgb, w, h)
        try:
            pp.write_text(json.dumps(pam, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass                                   # nagranie w katalogu tylko do odczytu: bez pamięci podręcznej
    return {"w": W, "h": H, "co": co, "probki": [[t, pam["probki"][f"{t:.3f}"]] for t in chwile if f"{t:.3f}" in pam["probki"]]}


def odcinki_arg(s: str) -> list[tuple[float, float]]:
    out = []
    for kaw in s.split(","):
        a, _, b = kaw.strip().partition("-")
        if a and b and float(b) > float(a) >= 0:
            out.append((float(a), float(b)))
    if not out:
        raise SystemExit("--odcinki: od-do[,od-do…] w sekundach źródła")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("model", help="pobierz i sprawdź model").set_defaults(fn=lambda a: print(model()) or 0)
    sp = sub.add_parser("wykryj", help="twarze w odcinkach źródła (JSON)")
    sp.add_argument("nagranie")
    sp.add_argument("--odcinki", required=True, help="od-do po przecinku, sekundy źródła")
    sp.add_argument("--co", type=float, default=CO, help="odstęp próbek w sekundach (domyślnie 0,5)")
    sp.set_defaults(fn=lambda a: print(json.dumps(wykryj(Path(a.nagranie).resolve(), odcinki_arg(a.odcinki),
                                                          max(0.04, a.co)))) or 0)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
