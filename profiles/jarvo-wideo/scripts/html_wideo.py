#!/usr/bin/env python3
"""Animacja HTML albo Lottie → klatki, arkusz do oceny i wideo (przeglądarka z obrazu, bez pobierania).

    python3 html_wideo.py klatki anim.html --czasy 0,1.5,3 [--preset iart] [--out katalog] [--arkusz arkusz.jpg]
    python3 html_wideo.py wideo  anim.html --dlugosc 6 [--fps 30] -o film.mp4 [--preset …] [--alfa]
    python3 html_wideo.py lottie scena/lottie.json [-o film.mp4|.mov|.webm|.gif] [--alfa] [--tlo "#101010"]
    python3 html_wideo.py lottie scena/lottie.json --klatki 0,45,89 --arkusz arkusz.jpg

Każda klatka to stan animacji w chwili t (uprząż czasu strony, nie zegar ścienny), więc wideo jest płynne
i powtarzalne niezależnie od szybkości maszyny. Uprząż: parametr w URL (--param t --jednostka s|ms|klatka;
strona czyta go przy wczytaniu i pauzuje) albo funkcja seek w JS (--seek "t => tl.seek(t)", bez przeładowań).
Presety (flagi je nadpisują):
  jarvo          nasz kontrakt (rodzaje-filmu/references/kontrakt-html.md): window.__seek(t), window.__ready,
                rozmiar z window.__W/__H, strona z lokalnego serwera: biblioteki z /_lib/ (three, gsap), bez CDN
  iart          ?t=<s>, gotowe: window.__ready        (kinetic-typography, chart-animation, lower-thirds…)
  pixel2motion  ?t=<ms>, gotowe: window.__p2mReady, kadr #logo-root
  bang          window.OPENER.seek(t), ?clean=1, rozmiar z OPENER.W/H (bang-motion; zamiast snap/export-frames.mjs)
--subklatki N (wideo): motion blur, każda klatka to średnia N chwil między klatkami (N× dłużej).
--serwer: strona z http://127.0.0.1 (fetch plików obok, moduły ES, /_lib/ = wspólne node_modules narzędzi).
lottie: renderer Skottie z oficjalnego playera (canvaskit-wasm, `narzedzia.py instaluj lottie`), ten sam co w playerze.
Wyjście: .mp4 (H.264, yuv420p, zakres TV, faststart), .mov (ProRes; z --alfa 4444 z przezroczystością),
.webm (VP9; z --alfa przezroczyste), .gif. Wymaga: playwright w Pythonie (`narzedzia.py instaluj html`), ffmpeg.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import math
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import narzedzia as nz  # noqa: E402
import wideo_lib as wl  # noqa: E402

BANG_SEEK = """async (t) => {
  const O = window.OPENER;
  if (O.seekFrame) { await O.seekFrame(t); O.seek(t); return; }
  O.seek(t);
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  O.seek(t);
}"""
PRESETS: dict[str, dict] = {
    # ?render=1: strona nie odpala pętli podglądu (rAF z zegarem nadpisałby klatkę między seek a zrzutem)
    # seek nie zwraca wyniku __seek: oś GSAP to obiekt „thenable” (await czekałby na koniec zatrzymanej osi)
    "jarvo": {"seek": "async (t) => { const r = window.__seek(t); if (r instanceof Promise) await r; }",
             "gotowe": "window.__ready === true", "serwer": True,
             "query": {"render": "1"}, "rozmiar_js": "[window.__W || 1920, window.__H || 1080]"},
    "iart": {"param": "t", "jednostka": "s", "gotowe": "window.__ready === true"},
    "pixel2motion": {"param": "t", "jednostka": "ms", "gotowe": "window.__p2mReady === true", "selektor": "#logo-root"},
    "bang": {"seek": BANG_SEEK, "query": {"clean": "1"},
             "gotowe": "window.OPENER && window.OPENER.ready && (!window.OPENER.clipsReady || window.OPENER.clipsReady())",
             "rozmiar_js": "[window.OPENER.W || 1920, window.OPENER.H || 1080]"},
}
DEFAULTS = {"param": "t", "jednostka": "s", "gotowe": None, "seek": None, "selektor": None, "query": {},
            "rozmiar_js": None, "serwer": False}
BROWSER_ARGS = ["--enable-webgl", "--ignore-gpu-blocklist", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                "--autoplay-policy=no-user-gesture-required", "--allow-file-access-from-files"]
RAF2 = "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
FONTS = "() => (document.fonts ? document.fonts.ready.then(() => true) : true)"
LOTTIE_ASSET_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ttf", ".otf", ".ttc", ".woff", ".woff2"}
TIMEOUT_MS = 60_000


# ---------------------------------------------------------------- czyste funkcje (testowane bez przeglądarki)

def parse_times(text: str) -> list[float]:
    return [float(x) for x in text.replace(";", ",").split(",") if x.strip()]


def parse_size(text: str) -> tuple[int, int]:
    w, _, h = text.lower().partition("x")
    return int(w), int(h)


def page_url(src: str, query: dict) -> str:
    if "://" in src:
        base = src
    else:
        path = Path(src)
        if not path.exists():
            raise SystemExit(f"brak pliku: {src}")
        base = path.resolve().as_uri()
    parts = urlsplit(base)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q.update({k: str(v) for k, v in (query or {}).items()})
    return urlunsplit(parts._replace(query=urlencode(q)))


def time_value(t: float, unit: str, fps: float) -> str:
    if unit == "ms":
        return str(int(round(t * 1000)))
    if unit == "klatka":
        return str(int(round(t * fps)))
    return f"{t:.4f}".rstrip("0").rstrip(".") or "0"


def frame_times(duration: float, fps: float) -> list[float]:
    return [i / fps for i in range(max(1, int(round(duration * fps))))]


def subframe_times(times: list[float], fps: float, n: int) -> list[float]:
    """N chwil w obrębie każdej klatki (0, 1/n, … czasu klatki) do uśrednienia w motion blur."""
    return [t + k / (fps * n) for t in times for k in range(n)]


def resolve_opts(preset: str | None, **flags) -> dict:
    """Preset + jawne flagi (None = nie podano) → komplet opcji."""
    if preset and preset not in PRESETS:
        raise SystemExit(f"nieznany preset {preset!r} ({' | '.join(PRESETS)})")
    opts = {**DEFAULTS, **(PRESETS.get(preset or "", {}))}
    query = {**opts["query"], **(flags.pop("query", None) or {})}     # --query dokłada, nie kasuje presetu
    opts.update({k: v for k, v in flags.items() if v is not None})
    opts["query"] = query
    return opts


def encode_cmd(pattern: str, fps: float, out: Path, alfa: bool) -> list[str]:
    head = ["ffmpeg", "-y", "-framerate", f"{fps:g}", "-i", pattern]
    ext = out.suffix.lower()
    if ext == ".mov":
        return head + ["-c:v", "prores_ks", "-profile:v", "4444" if alfa else "3",
                       "-pix_fmt", "yuva444p10le" if alfa else "yuv422p10le", str(out)]
    if ext == ".webm":
        return head + ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "30", "-row-mt", "1",
                       "-pix_fmt", "yuva420p" if alfa else "yuv420p", str(out)]
    if ext == ".gif":
        return head + ["-vf", "split[a][b];[a]palettegen=reserve_transparent=1[p];[b][p]paletteuse", str(out)]
    if ext != ".mp4":
        raise SystemExit(f"nieobsługiwany format wyjścia {ext!r} (.mp4 | .mov | .webm | .gif)")
    if alfa:
        raise SystemExit("--alfa: MP4 (H.264) nie ma przezroczystości; użyj .mov (ProRes 4444) albo .webm")
    return head + ["-vf", f"pad=ceil(iw/2)*2:ceil(ih/2)*2,{wl.TV_RANGE}", "-c:v", "libx264", "-preset", "medium",
                   "-crf", "18", *wl.ENC_LIMITS, "-movflags", "+faststart", str(out)]


def lottie_check(data: dict) -> list[str]:
    """Minimalny kontrakt pliku Lottie (text-to-lottie: v, fr, ip, op, w, h, nm, assets, layers; op wyłączne)."""
    problems = [f"brak pola {k!r}" for k in ("v", "fr", "ip", "op", "w", "h", "layers") if k not in data]
    if not problems:
        if not data["layers"]:
            problems.append("pusta lista layers")
        if float(data["op"]) <= float(data["ip"]):
            problems.append("op ≤ ip (animacja bez klatek)")
        if float(data["fr"]) <= 0:
            problems.append("fr ≤ 0")
    return problems


# ---------------------------------------------------------------- przeglądarka

def ensure_playwright() -> None:
    try:
        import playwright.sync_api  # noqa: F401
        return
    except ImportError:
        pass
    venv_py = Path(nz.py())
    if venv_py.exists() and Path(sys.prefix).resolve() != nz.VENV.resolve() and not os.environ.get("JARVO_HTML_REEXEC"):
        os.environ["JARVO_HTML_REEXEC"] = "1"      # jeden skok do venv narzędzi, bez pętli
        os.execv(str(venv_py), [str(venv_py), str(Path(__file__).resolve()), *sys.argv[1:]])
    raise SystemExit("brak playwright w Pythonie: python3 $HERMES_HOME/scripts/narzedzia.py instaluj html")


def launch(p):
    exe = nz.headless_shell()
    kwargs = {"args": BROWSER_ARGS, **({"executable_path": exe} if exe else {})}
    return p.chromium.launch(**kwargs)


def _page(browser, size: tuple[int, int], scale: float, errors: list[str]):
    page = browser.new_page(viewport={"width": size[0], "height": size[1]}, device_scale_factor=scale)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.set_default_timeout(TIMEOUT_MS)
    return page


def capture(src: str, times: list[float], names: list[str], out_dir: Path, o: dict, fps: float, size: tuple[int, int],
            size_explicit: bool, scale: float, alfa: bool, wait_ms: int) -> list[Path]:
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []
    errors: list[str] = []

    def settle(page) -> None:
        if o["gotowe"]:
            page.wait_for_function(o["gotowe"], timeout=TIMEOUT_MS)
        page.evaluate(FONTS)
        page.evaluate(RAF2)

    httpd = None
    if o["serwer"] and "://" not in src:          # strona z lokalnego serwera: fetch, moduły ES, /_lib/
        page_file = Path(src).resolve()
        if not page_file.exists():
            raise SystemExit(f"brak pliku: {src}")
        httpd = serve(page_file.parent, lib=True)
        src = f"http://127.0.0.1:{httpd.server_address[1]}/{quote(page_file.name)}"
    try:
        _run_capture(sync_playwright, src, times, names, out_dir, o, fps, size, size_explicit, scale, alfa, wait_ms,
                     frames, errors, settle)
    finally:
        if httpd:
            httpd.shutdown()
    for e in dict.fromkeys(errors):
        print(f"  ! błąd JS na stronie: {e[:300]}", file=sys.stderr)
    return frames


def _run_capture(sync_playwright, src, times, names, out_dir, o, fps, size, size_explicit, scale, alfa, wait_ms,
                 frames, errors, settle) -> None:
    with sync_playwright() as p:
        browser = launch(p)
        page = _page(browser, size, scale, errors)
        if o["seek"]:
            page.goto(page_url(src, o["query"]), wait_until="load")
            settle(page)
            if o["rozmiar_js"] and not size_explicit:
                w, h = page.evaluate(f"() => {o['rozmiar_js']}")
                page.set_viewport_size({"width": int(w), "height": int(h)})
                page.evaluate(RAF2)
        for t, name in zip(times, names):
            if o["seek"]:
                page.evaluate(o["seek"], t)
                page.evaluate(RAF2)
            else:
                page.goto(page_url(src, {**o["query"], o["param"]: time_value(t, o["jednostka"], fps)}), wait_until="load")
                settle(page)
            if wait_ms:
                page.wait_for_timeout(wait_ms)
            path = out_dir / name
            target = page.locator(o["selektor"]).first if o["selektor"] else page
            target.screenshot(path=str(path), omit_background=alfa)
            frames.append(path)
        browser.close()


def sheet(frames: list[Path], labels: list[str], out: Path, width: int = 1600) -> Path:
    """Arkusz klatek z etykietami czasu (przezroczystość na szarym tle) do oceny okiem (vision)."""
    from PIL import Image, ImageDraw

    ims = []
    for f in frames:
        im = Image.open(f)
        if im.mode in ("RGBA", "LA", "P"):
            base = Image.new("RGBA", im.size, "#808080")
            base.alpha_composite(im.convert("RGBA"))
            im = base
        ims.append(im.convert("RGB"))
    n = len(ims)
    cols = min(n, 4 if ims[0].width >= ims[0].height else 6)
    rows = math.ceil(n / cols)
    cw = width // cols
    ch = max(1, int(cw * ims[0].height / ims[0].width))
    lab = 24
    canvas = Image.new("RGB", (cw * cols, (ch + lab) * rows), "#1c1c1c")
    draw = ImageDraw.Draw(canvas)
    for i, (im, label) in enumerate(zip(ims, labels)):
        x, y = (i % cols) * cw, (i // cols) * (ch + lab)
        canvas.paste(im.resize((cw, ch)), (x, y + lab))
        draw.text((x + 6, y + 5), label, fill="#ffffff")
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=88)
    return out


def blend(paths: list[Path], out: Path, alfa: bool) -> Path:
    """Średnia podklatek (motion blur jak migawka 360°)."""
    import numpy as np
    from PIL import Image

    acc = None
    for p in paths:
        a = np.asarray(Image.open(p).convert("RGBA"), dtype=np.float32)
        acc = a if acc is None else acc + a
    img = Image.fromarray(np.clip(acc / len(paths) + 0.5, 0, 255).astype("uint8"), "RGBA")
    (img if alfa else img.convert("RGB")).save(out)
    return out


def encode(frames_dir: Path, fps: float, out: Path, alfa: bool) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    wl.run(encode_cmd(str(frames_dir / "f%05d.png"), fps, out, alfa))
    return out


# ---------------------------------------------------------------- Lottie (Skottie z oficjalnego playera)

LOTTIE_PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<style>html,body{margin:0;background:__BG__}canvas{display:block}</style></head>
<body><canvas id="c"></canvas>
<script src="/ck/canvaskit.js"></script>
<script>
(async () => {
  try {
    const CK = await CanvasKitInit({ locateFile: (f) => '/ck/' + f });
    const json = await (await fetch('/scene/' + encodeURIComponent(__NAME__))).text();
    const assets = {};
    for (const a of __ASSETS__) assets[a] = await (await fetch('/scene/' + encodeURIComponent(a))).arrayBuffer();
    const anim = CK.MakeManagedAnimation(json, assets);
    if (!anim) throw new Error('Skottie nie wczytał animacji (zły JSON albo nieobsługiwana funkcja)');
    const size = anim.size();
    const el = document.getElementById('c');
    el.width = Math.round(size[0] * __SCALE__);
    el.height = Math.round(size[1] * __SCALE__);
    const surface = CK.MakeSWCanvasSurface(el);
    const cv = surface.getCanvas();
    const rect = CK.LTRBRect(0, 0, el.width, el.height);
    window.__lottie = { fps: anim.fps(), frames: Math.round(anim.duration() * anim.fps()), w: el.width, h: el.height };
    window.__seek = (f) => { cv.clear(CK.TRANSPARENT); anim.seekFrame(f); anim.render(cv, rect); surface.flush(); };
    window.__seek(0);
    window.__ready = true;
  } catch (e) { window.__error = String((e && e.stack) || e); }
})();
</script></body></html>
"""


class _Quiet(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".wasm": "application/wasm",
                      ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json"}
    lib_root: Path | None = None      # /_lib/… → wspólne node_modules narzędzi (three, gsap)

    def translate_path(self, path: str) -> str:
        clean = unquote(urlsplit(path).path)
        if self.lib_root is not None and clean.startswith("/_lib/"):
            root = self.lib_root.resolve()
            target = (root / clean[len("/_lib/"):]).resolve()
            return str(target) if root in target.parents else str(root / "__poza_lib__")
        return super().translate_path(path)

    def log_message(self, *args) -> None:  # noqa: D401 - cisza w logach
        pass


def serve(root: Path, lib: bool = False) -> http.server.ThreadingHTTPServer:
    handler = type("_Lib", (_Quiet,), {"lib_root": nz.NODE / "node_modules"}) if lib else _Quiet
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(handler, directory=str(root)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def lottie_render(src: Path, frames_sel: list[float] | None, fps_out: float | None, out_dir: Path, alfa: bool,
                  bg: str, scale: float) -> tuple[list[Path], list[str], dict]:
    from playwright.sync_api import sync_playwright

    ck = nz.canvaskit_dir()
    if not (ck / "canvaskit.js").exists():
        raise SystemExit("brak playera Lottie (canvaskit): python3 $HERMES_HOME/scripts/narzedzia.py instaluj lottie")
    data = json.loads(src.read_text(encoding="utf-8"))
    problems = lottie_check(data)
    if problems:
        raise SystemExit(f"{src}: " + "; ".join(problems))
    scene = src.parent
    assets = sorted(p.name for p in scene.iterdir()
                    if p.is_file() and p.name not in (src.name, "controls.json") and p.suffix.lower() in LOTTIE_ASSET_EXT)
    tmp = Path(tempfile.mkdtemp(prefix="jarvo-lottie-"))
    httpd = None
    try:
        (tmp / "ck").symlink_to(ck, target_is_directory=True)
        (tmp / "scene").symlink_to(scene, target_is_directory=True)
        html = (LOTTIE_PAGE.replace("__BG__", "transparent" if alfa else bg).replace("__NAME__", json.dumps(src.name))
                .replace("__ASSETS__", json.dumps(assets)).replace("__SCALE__", f"{scale:g}"))
        (tmp / "index.html").write_text(html, encoding="utf-8")
        httpd = serve(tmp)
        url = f"http://127.0.0.1:{httpd.server_address[1]}/index.html"
        out_dir.mkdir(parents=True, exist_ok=True)
        errors: list[str] = []
        with sync_playwright() as p:
            browser = launch(p)
            page = _page(browser, (64, 64), 1.0, errors)
            page.goto(url, wait_until="load")
            page.wait_for_function("window.__ready === true || !!window.__error", timeout=TIMEOUT_MS)
            err = page.evaluate("() => window.__error || null")
            if err:
                raise SystemExit(f"Skottie: {err}")
            info = page.evaluate("() => window.__lottie")
            page.set_viewport_size({"width": int(info["w"]), "height": int(info["h"])})
            if frames_sel is not None:
                sel = frames_sel
            else:
                fps = fps_out or info["fps"]
                sel = [i * info["fps"] / fps for i in range(max(1, int(round(info["frames"] * fps / info["fps"]))))]
            paths, labels = [], []
            for i, f in enumerate(sel):
                page.evaluate("(f) => window.__seek(f)", f)
                path = out_dir / f"f{i:05d}.png"
                page.locator("#c").screenshot(path=str(path), omit_background=alfa)
                paths.append(path)
                labels.append(f"klatka {f:g}")
            browser.close()
        for e in dict.fromkeys(errors):
            print(f"  ! błąd JS: {e[:300]}", file=sys.stderr)
        return paths, labels, info
    finally:
        if httpd:
            httpd.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- CLI

def _html_opts(a) -> dict:
    query = dict(parse_qsl(a.query)) if a.query else None
    return resolve_opts(a.preset, param=a.param, jednostka=a.jednostka, gotowe=a.gotowe, seek=a.seek,
                        selektor=a.selektor, query=query, serwer=True if a.serwer else None)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("klatki", "wideo"):
        s = sub.add_parser(name)
        s.add_argument("zrodlo", help="plik .html albo URL (http://127.0.0.1:…)")
        s.add_argument("--preset", choices=sorted(PRESETS))
        s.add_argument("--param", help="nazwa parametru czasu w URL (domyślnie t)")
        s.add_argument("--jednostka", choices=["s", "ms", "klatka"])
        s.add_argument("--gotowe", help="wyrażenie JS: strona gotowa do zrzutu (np. window.__ready === true)")
        s.add_argument("--seek", help="funkcja JS ustawiająca czas bez przeładowania, np. \"t => tl.seek(t)\"")
        s.add_argument("--selektor", help="zrzut tylko tego elementu (CSS), np. #stage")
        s.add_argument("--query", help="dodatkowe parametry URL, np. clean=1&lang=pl")
        s.add_argument("--rozmiar", help="okno przeglądarki SZERxWYS (domyślnie 1920x1080; 9:16 → 1080x1920)")
        s.add_argument("--skala", type=float, default=1.0, help="gęstość pikseli (2 = ostrzej, 4× więcej pikseli)")
        s.add_argument("--alfa", action="store_true", help="przezroczyste tło (.mov / .webm / PNG)")
        s.add_argument("--fps", type=float, default=30.0)
        s.add_argument("--czekaj", type=int, default=0, help="dodatkowe ms po ustawieniu czasu (animacje CSS z opóźnieniem)")
        s.add_argument("--serwer", action="store_true", help="strona z lokalnego serwera (fetch, moduły ES, /_lib/)")
        if name == "klatki":
            s.add_argument("--czasy", required=True, help="sekundy po przecinku, np. 0,1.5,3")
            s.add_argument("--out", default="out/wideo/klatki")
            s.add_argument("--arkusz", help="JPG z klatkami i czasami (do vision_analyze)")
        else:
            s.add_argument("--dlugosc", type=float, required=True, help="sekundy")
            s.add_argument("-o", "--wyjscie", required=True, help="film .mp4 | .mov | .webm | .gif")
            s.add_argument("--arkusz", help="dodatkowo arkusz ~12 klatek z filmu")
            s.add_argument("--zostaw-klatki", action="store_true")
            s.add_argument("--subklatki", type=int, default=1, help="motion blur: średnia N chwil na klatkę (2–8)")
    lo = sub.add_parser("lottie")
    lo.add_argument("plik", help="lottie.json (assety i fonty obok, jak w playerze)")
    lo.add_argument("-o", "--wyjscie", help="film .mp4 | .mov | .webm | .gif")
    lo.add_argument("--klatki", help="numery klatek do zrzutu zamiast filmu, np. 0,45,89")
    lo.add_argument("--out", default="out/wideo/klatki-lottie")
    lo.add_argument("--arkusz", help="JPG z klatkami (do vision_analyze)")
    lo.add_argument("--fps", type=float, help="fps filmu (domyślnie fr animacji)")
    lo.add_argument("--alfa", action="store_true")
    lo.add_argument("--tlo", default="#000000", help="tło bez --alfa (CSS), np. #ffffff")
    lo.add_argument("--skala", type=float, default=1.0, help="mnożnik rozdzielczości (w, h z pliku)")
    a = ap.parse_args(argv)
    ensure_playwright()

    if a.cmd == "lottie":
        if not a.wyjscie and not a.klatki:
            raise SystemExit("lottie: podaj -o film.mp4 albo --klatki 0,45,89")
        work = Path(a.out) if a.klatki else Path(tempfile.mkdtemp(prefix="jarvo-lottie-klatki-"))
        frames, labels, info = lottie_render(Path(a.plik).resolve(), parse_times(a.klatki) if a.klatki else None,
                                             a.fps, work, a.alfa, a.tlo, a.skala)
        result = {"klatek": len(frames), "fps_animacji": info["fps"], "rozmiar": [info["w"], info["h"]]}
        if a.arkusz:
            pick = frames if a.klatki else frames[:: max(1, len(frames) // 12)]
            lab = labels if a.klatki else labels[:: max(1, len(frames) // 12)]
            result["arkusz"] = str(sheet(pick, lab, Path(a.arkusz)))
        if a.wyjscie:
            result["film"] = str(encode(work, a.fps or info["fps"], Path(a.wyjscie), a.alfa))
        if not a.klatki:
            shutil.rmtree(work, ignore_errors=True)
        else:
            result["katalog"] = str(work)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    o = _html_opts(a)
    size = parse_size(a.rozmiar) if a.rozmiar else (1920, 1080)
    if a.cmd == "klatki":
        times = parse_times(a.czasy)
        names = [f"t{t:08.3f}.png" for t in times]
        frames = capture(a.zrodlo, times, names, Path(a.out), o, a.fps, size, bool(a.rozmiar), a.skala, a.alfa, a.czekaj)
        result = {"klatki": [str(f) for f in frames]}
        if a.arkusz:
            result["arkusz"] = str(sheet(frames, [f"t={t:g}s" for t in times], Path(a.arkusz)))
        print(json.dumps(result, ensure_ascii=False))
        return 0

    times = frame_times(a.dlugosc, a.fps)
    work = Path(tempfile.mkdtemp(prefix="jarvo-html-klatki-"))
    n = max(1, a.subklatki)
    if n == 1:
        frames = capture(a.zrodlo, times, [f"f{i:05d}.png" for i in range(len(times))], work, o, a.fps, size,
                         bool(a.rozmiar), a.skala, a.alfa, a.czekaj)
    else:
        sub_times = subframe_times(times, a.fps, n)
        subs = capture(a.zrodlo, sub_times, [f"s{i:06d}.png" for i in range(len(sub_times))], work / "sub", o, a.fps,
                       size, bool(a.rozmiar), a.skala, a.alfa, a.czekaj)
        frames = [blend(subs[i * n:(i + 1) * n], work / f"f{i:05d}.png", a.alfa) for i in range(len(times))]
    out = encode(work, a.fps, Path(a.wyjscie), a.alfa)
    result = {"film": str(out), "klatek": len(frames), "fps": a.fps, **({"subklatki": n} if n > 1 else {})}
    if a.arkusz:
        step = max(1, len(frames) // 12)
        result["arkusz"] = str(sheet(frames[::step], [f"t={t:.2f}s" for t in times[::step]], Path(a.arkusz)))
    if a.zostaw_klatki:
        result["katalog_klatek"] = str(work)
    else:
        shutil.rmtree(work, ignore_errors=True)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
