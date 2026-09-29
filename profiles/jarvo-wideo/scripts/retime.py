#!/usr/bin/env python3
"""Retime: przycinanie i przyspieszanie filmu z KODU (kompozycja HyperFrames) bez pisania go od nowa.

    python3 retime.py projekt/index.v1.html --kotwice kotwice.json -o projekt/index.html [--tempo-animacji 0.85] [--zakladka 0.55]
    python3 retime.py mapuj kotwice.json 12.5 25 32.5     # stare czasy → nowe (do dopasowania lektora, muzyki, SFX)

Film z kodu to funkcja czasu, więc „montaż” robi się na osi czasu, a nie na MP4: zamiast wycinać klatki, przesuwasz
CHWILE (wejścia, cięcia, liczniki) bliżej siebie, a ruch (sprężyny, wjazdy) zostawiasz płynny. Dzięki temu lektor,
muzyka i efekty można wygenerować na nowej osi, bez „szarpnięć” po ciętym dźwięku.

kotwice.json: {"kotwice": [[stary_czas, nowy_czas], ...], "koniec": 30.5}. Między kotwicami czas liczy się liniowo
(nachylenie < 1 = szybciej), przed pierwszą i po ostatniej 1:1, nowy czas nigdy < 0. Kotwice muszą rosnąć w obu osiach.
Skrypt: (1) wstrzykuje do kompozycji mapę czasu i osłonę na `tl.to/from/fromTo/set` (pozycje mapowane, długości
animacji × --tempo-animacji), (2) przelicza `data-start`/`data-duration` scen (nakładka --zakladka na przejście),
korzeń `data-duration` i ścieżki audio, (3) `const TOTAL = …` na nowy koniec. `tl.to(clock, …)` (zegar HUD) idzie po
surowej osi i trwa cały film. Wynik przechodzi `hyperframes check` jak każda kompozycja.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


class Timemap:
    def __init__(self, anchors: list[list[float]]):
        pts = [(float(a), float(b)) for a, b in anchors]
        for (a0, b0), (a1, b1) in zip(pts, pts[1:]):
            if a1 <= a0 or b1 < b0:
                raise SystemExit(f"Kotwice muszą rosnąć (stary ściśle, nowy nie malejąco): {a0}->{b0}, {a1}->{b1}")
        self.pts = pts

    def __call__(self, t: float) -> float:
        p = self.pts
        if not p:
            return max(0.0, t)
        if t <= p[0][0]:
            return max(0.0, p[0][1] + (t - p[0][0]))
        if t >= p[-1][0]:
            return p[-1][1] + (t - p[-1][0])
        for (a0, b0), (a1, b1) in zip(p, p[1:]):
            if a0 <= t <= a1:
                return b0 + (t - a0) * (b1 - b0) / (a1 - a0)
        return t


PROXY = r"""const ANCH = __ANCH__;
      const DS = __DS__;
      const M = (t) => {
        if (!ANCH.length) return Math.max(0, t);
        if (t <= ANCH[0][0]) return Math.max(0, ANCH[0][1] + (t - ANCH[0][0]));
        const L = ANCH[ANCH.length - 1];
        if (t >= L[0]) return L[1] + (t - L[0]);
        for (let i = 0; i < ANCH.length - 1; i++) {
          const a = ANCH[i], b = ANCH[i + 1];
          if (t >= a[0] && t <= b[0]) return a[1] + ((t - a[0]) * (b[1] - a[1])) / (b[0] - a[0]);
        }
        return t;
      };
      const _tl = gsap.timeline({ paused: true });
      const _fx = (v) => (v && typeof v.duration === "number" ? Object.assign({}, v, { duration: v.duration * DS }) : v);
      const tl = {
        to: (t, v, p) => _tl.to(t, _fx(v), p === undefined ? p : M(p)),
        from: (t, v, p) => _tl.from(t, _fx(v), p === undefined ? p : M(p)),
        fromTo: (t, f, v, p) => _tl.fromTo(t, f, _fx(v), p === undefined ? p : M(p)),
        set: (t, v, p) => _tl.set(t, v, p === undefined ? p : M(p)),
      };"""


def inject(html: str, anchors: list[list[float]], ds: float, total: float) -> str:
    if "const ANCH =" in html:
        raise SystemExit("Kompozycja ma już mapę czasu (retime uruchamiaj na oryginale, np. index.v1.html).")
    pat = re.compile(r"const tl = gsap\.timeline\(\{ paused: true \}\);")
    if not pat.search(html):
        raise SystemExit("Nie znaleziono `const tl = gsap.timeline({ paused: true });` (wzorzec kompozycji z jednym tl).")
    proxy = PROXY.replace("__ANCH__", json.dumps(anchors)).replace("__DS__", str(ds))
    html = pat.sub(lambda m: proxy, html, count=1)
    html = re.sub(r"\btl\.to\(clock,", "_tl.to(clock,", html)
    html = re.sub(r'window\.__timelines\["([^"]+)"\]\s*=\s*tl;', r'window.__timelines["\1"] = _tl;', html)
    html = re.sub(r"const TOTAL = [\d.]+;", f"const TOTAL = {total};", html, count=1)
    return html


SEC = re.compile(r'(<section\b[^>]*?\bdata-start=")([\d.]+)("[^>]*?\bdata-duration=")([\d.]+)(")')


def patch_structure(html: str, tm: Timemap, total: float, overlap: float) -> tuple[str, list[dict]]:
    secs = [(m.start(), float(m.group(2)), float(m.group(4))) for m in SEC.finditer(html)]
    starts = [s for _, s, _ in secs]
    report: list[dict] = []
    idx = {"i": 0}

    def repl(m: re.Match) -> str:
        i = idx["i"]
        idx["i"] += 1
        ns = tm(float(m.group(2)))
        nxt = tm(starts[i + 1]) if i + 1 < len(starts) else None
        nd = (nxt - ns + overlap) if nxt is not None else (total - ns)
        nd = round(max(0.3, nd), 3)
        report.append({"scena": i + 1, "start": round(ns, 3), "dlugosc": nd})
        return f"{m.group(1)}{round(ns, 3)}{m.group(3)}{nd}{m.group(5)}"

    html = SEC.sub(repl, html)
    html = re.sub(r'(data-composition-id="[^"]+"[^>]*?data-duration=")[\d.]+(")', lambda m: f"{m.group(1)}{total}{m.group(2)}", html, count=1)
    html = re.sub(r'(<audio\b[^>]*?data-duration=")[\d.]+(")', lambda m: f"{m.group(1)}{total}{m.group(2)}", html)
    return html, report


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "mapuj":
        spec = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        tm = Timemap(spec["kotwice"])
        for t in argv[2:]:
            print(f"{float(t):g} -> {tm(float(t)):.3f}")
        return 0
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", help="oryginalna kompozycja (np. projekt/index.v1.html)")
    ap.add_argument("--kotwice", required=True)
    ap.add_argument("-o", required=True)
    ap.add_argument("--tempo-animacji", type=float, default=0.85, help="mnożnik długości animacji (0.85 = 15%% szybciej)")
    ap.add_argument("--zakladka", type=float, default=0.55, help="nakładka scen na przejściu (s)")
    a = ap.parse_args(argv)
    spec = json.loads(Path(a.kotwice).read_text(encoding="utf-8"))
    anchors, total = spec["kotwice"], float(spec["koniec"])
    tm = Timemap(anchors)
    html = Path(a.html).read_text(encoding="utf-8")
    html = inject(html, anchors, a.tempo_animacji, total)
    html, report = patch_structure(html, tm, total, a.zakladka)
    Path(a.o).write_text(html, encoding="utf-8")
    print(json.dumps({"wynik": a.o, "koniec_s": total, "sceny": report}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
