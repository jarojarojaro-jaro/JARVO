#!/usr/bin/env python3
"""Żywy schemat: architektura, flota, przepływ zlecenia, który „działa” (kropki płyną po strzałkach, log się
przewija, liczniki rosną, kroki podświetlają się po kolei), z jednego pliku JSON. Układ stoi, każda klatka to cały
schemat. Na posty X, Instagram, LinkedIn i do prezentacji, zamiast statycznego PNG.

    zywy_schemat.py strona schemat.json [-o schemat.html]   # strona do podglądu i renderu (offline, kroje lokalnie)
    zywy_schemat.py sprawdz schemat.html [--probki 120]      # układ w ~120 chwilach: tekst poza ramką, ramki na sobie,
                                                             # błędy strony; kod 1 = do poprawy
    zywy_schemat.py film schemat.html -o schemat.mp4         # html_wideo.py wideo (czas i fps z configu) + cicha
                                                             # ścieżka AAC (Telegram i komunikatory nie robią z niego GIF-a)
    zywy_schemat.py formaty                                  # formaty platform i motywy Jarva

Klatki do oceny i pomiar jak w każdej animacji HTML (`html_wideo.py`, preset `livepanel`):
    html_wideo.py klatki schemat.html --preset livepanel --czasy 1,8,15,22 --arkusz arkusz.jpg
    html_wideo.py pomiar schemat.html --preset livepanel --dlugosc 28

Silnik strony to skill zewnętrzny `live-panel` (MIT): szablon `assets/template.html`, schemat pliku
(`references/config-schema.md`) i gramatyka ruchu (`references/motion-grammar.md`). Jarvo dokłada formaty platform
(`canvas.preset`: x, ig, pion, kwadrat, poziom), motywy w kolorach Jarva (`theme.preset`: jarvo-jasny,
jarvo-ciemny), polskie kroje OFL wstawione w stronę (bez Google Fonts) i tę kontrolę. Kod wyjścia: 0 ok,
1 problemy w układzie, 2 złe wejście.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# silnik krojów edytora: w dystrybucji kopiowany obok (build.py), w repo leży w hq/plugin (jak w projekt.py)
_REPO = HERE.parents[2] if len(HERE.parents) > 2 else HERE
for _cand in (HERE, _REPO / "hq" / "plugin"):
    if (_cand / "edytor.py").exists():
        sys.path.insert(0, str(_cand))
        break

KROJE = next((p for p in (HERE / "kroje", _REPO / "hq" / "web" / "fonts" / "kroje") if (p / "kroje.css").exists()), None)
SZABLON = HERE.parent / "skills" / "video" / "live-panel" / "assets" / "template.html"   # skill zewnętrzny w profilu
ZNACZNIK = "<!--LIVE_CONFIG-->"

# canvas.preset → (szerokość, wysokość, gdzie); presety live-panel (4:5, 3:4, 1:1) działają dalej
FORMATY: dict[str, tuple[int, int, str]] = {
    "x": (1200, 1500, "X (4:5, jak oryginał live-panel)"),
    "ig": (1080, 1350, "Instagram, Facebook, LinkedIn: post w siatce (4:5)"),
    "pion": (1080, 1920, "Reels, TikTok, Shorts, relacja (9:16; dół i prawy bok pod UI platformy)"),
    "kwadrat": (1080, 1080, "post kwadratowy (1:1)"),
    "poziom": (1920, 1080, "YouTube, prezentacja, strona (16:9)"),
}
# theme.preset Jarva = preset live-panel + krój z polskimi znakami + kolory Jarva; config może nadpisać każde pole
MOTYWY: dict[str, dict] = {
    "jarvo-jasny": {"preset": "light-pastel", "font": '"Inter", "DejaVu Sans", sans-serif',
                    "opis": "białe tło, pastelowe ramki, Inter; kropki i akcent w czerwieni Jarva",
                    # teksty na pastelach ≥ 4,5:1 (WCAG AA; pomiar html_wideo): dim, blt, ort ciemniejsze niż w live-panel
                    "colors": {"fg": "#1B1D22", "ink": "#1B1D22", "dim": "#5B6270", "line": "#1B1D22",
                               "blt": "#2A5AAE", "ort": "#A04E0C", "rdt": "#B51A33",
                               "pk": "#D4213D", "ak": "#D4213D", "akf": "#FDECEF"}},
    "jarvo-ciemny": {"preset": "terminal-dark", "font": '"JetBrains Mono", "DejaVu Sans Mono", monospace',
                     "opis": "ciemny terminal, JetBrains Mono, segmentowe ramki (styl oryginału)",
                     "colors": {"ak": "#FF4D6A"}},
}
GENERYCZNE = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-monospace", "ui-sans-serif"}


def _rodziny(stos: str) -> list[str]:
    return [r.strip().strip("'\"") for r in str(stos).split(",") if r.strip()]


def kroje_w_configu(cfg: dict) -> set[str]:
    """Każda rodzina z `font` (motyw i elementy), bez nazw ogólnych."""
    out: set[str] = set()

    def idz(v) -> None:
        if isinstance(v, dict):
            for k, x in v.items():
                if k == "font" and isinstance(x, str):
                    out.update(r for r in _rodziny(x) if r.lower() not in GENERYCZNE)
                else:
                    idz(x)
        elif isinstance(v, list):
            for x in v:
                idz(x)
    idz(cfg)
    return out


def rozwin(cfg: dict) -> tuple[dict, list[str]]:
    """Formaty i motywy Jarva → pola, które rozumie szablon live-panel. Zwraca (config, uwagi)."""
    cfg = copy.deepcopy(cfg)
    uwagi: list[str] = []
    cv = cfg.setdefault("canvas", {})
    if cv.get("preset") in FORMATY:
        w, h, _ = FORMATY[cv.pop("preset")]
        cv.setdefault("width", w)
        cv.setdefault("height", h)
    th = cfg.get("theme") or {}
    if th.get("preset") in MOTYWY:
        baza = MOTYWY[th["preset"]]
        nowy = {k: v for k, v in baza.items() if k != "opis"}
        nowy.update({k: v for k, v in th.items() if k not in ("preset", "colors")})
        nowy["colors"] = {**baza["colors"], **(th.get("colors") or {})}
        cfg["theme"] = nowy
    meta = cfg.setdefault("meta", {})
    meta.setdefault("lang", "pl")
    if not cfg.get("credit"):
        uwagi.append("brak linii `credit` na dole: źródło liczb albo „liczby poglądowe”, autor przerabianego obrazka")
    if cfg.get("machines") and "poglądow" not in json.dumps(cfg, ensure_ascii=False).lower() \
            and "źródło" not in str((cfg.get("credit") or {}).get("text", "")).lower():
        uwagi.append("liczniki i log bez podpisu „poglądowo” ani źródła w `credit`: liczba bez źródła to liczba poglądowa")
    return cfg, uwagi


def strona(cfg: dict, szablon: Path | None = None, kroje_dir: Path | None = KROJE) -> tuple[str, list[str]]:
    """Samodzielna strona: szablon live-panel + config (rozwinięty) + kroje użyte w configu jako data: URL."""
    szablon = szablon or SZABLON
    if not szablon.is_file():
        raise SystemExit(f"brak szablonu live-panel: {szablon} (skill zewnętrzny video/live-panel; przebuduj profil)")
    html = szablon.read_text(encoding="utf-8")
    if ZNACZNIK not in html or "</head>" not in html:
        raise SystemExit(f"szablon {szablon} bez {ZNACZNIK} albo </head>: inna wersja live-panel?")
    cfg, uwagi = rozwin(cfg)
    styl = ""
    if kroje_dir is not None:
        import edytor as ed
        rodziny = kroje_w_configu(cfg)
        styl = ed.kroje_css(kroje_dir, rodziny)
        znane = set(re.findall(r'font-family: "([^"]+)"', (kroje_dir / "kroje.css").read_text(encoding="utf-8")))
        brak = sorted(r for r in rodziny if r not in znane and r not in ("DejaVu Sans", "DejaVu Sans Mono"))
        if brak:
            uwagi.append("kroje spoza zestawu Jarva (strona użyje zastępczych): " + ", ".join(brak))
    blob = json.dumps(cfg, ensure_ascii=False).replace("</", "<\\/")
    html = html.replace(ZNACZNIK, f'<script id="live-config" type="application/json">{blob}</script>', 1)
    if styl:
        html = html.replace("</head>", f"<style>{styl}</style></head>", 1)
    return html, uwagi


def config_strony(plik: Path) -> dict:
    """Config osadzony w stronie z `strona` (czas, fps, płótno)."""
    m = re.search(r'<script id="live-config" type="application/json">(.*?)</script>', plik.read_text(encoding="utf-8"), re.S)
    if not m:
        raise SystemExit(f"{plik}: brak configu live-panel (strona nie z `zywy_schemat.py strona`?)")
    return json.loads(m.group(1))


def film(plik: Path, wyjscie: Path, audio: bool = True) -> int:
    """Wideo przez html_wideo.py (preset livepanel), potem cicha ścieżka AAC bez ponownego kodowania obrazu."""
    import wideo_lib as wl
    cv = config_strony(plik).get("canvas") or {}
    wyjscie.parent.mkdir(parents=True, exist_ok=True)
    surowy = wyjscie.with_name(wyjscie.stem + ".bez-audio.mp4") if audio else wyjscie
    r = subprocess.run([sys.executable, str(HERE / "html_wideo.py"), "wideo", str(plik), "--preset", "livepanel",
                        "--dlugosc", str(cv.get("duration", 30)), "--fps", str(cv.get("fps", 30)), "-o", str(surowy)])
    if r.returncode or not audio:
        return r.returncode
    subprocess.run([wl.need("ffmpeg"), "-y", "-v", "error", "-i", str(surowy), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                    "-map", "0:v", "-map", "1:a", "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "32k",
                    "-movflags", "+faststart", str(wyjscie)], check=True)
    surowy.unlink()
    print(f"✓ {wyjscie} (cicha ścieżka AAC)")
    return 0


def sprawdz(plik: Path, probki: int = 120) -> dict:
    """`window.__check()` live-panel w `probki` chwilach: tekst wychodzący z ramki, ramki na sobie, błędy strony."""
    import html_wideo as hw
    from playwright.sync_api import sync_playwright

    problemy: dict[str, list[float]] = {}
    bledy: list[str] = []
    with sync_playwright() as p:
        browser = hw.launch(p)
        page = hw._page(browser, (1200, 1500), 1.0, bledy)
        page.goto(plik.resolve().as_uri() + "?manual=1", wait_until="load")
        page.wait_for_function("window.__ready === true || !!window.__error", timeout=hw.TIMEOUT_MS)
        page.evaluate(hw.FONTS)
        w, h, dlugosc = page.evaluate("""() => { const s = document.getElementById('stage');
            const c = JSON.parse(document.getElementById('live-config').textContent).canvas || {};
            return [parseInt(s.style.width) || 1200, parseInt(s.style.height) || 1500, c.duration || 30]; }""")
        page.set_viewport_size({"width": w, "height": h})
        page.evaluate(hw.RAF2)
        for i in range(probki):
            t = round(dlugosc * i / probki + 0.013 * i, 3) % dlugosc
            page.evaluate("t => window.seek(t)", t)
            for pr in page.evaluate("() => window.__check()"):
                problemy.setdefault(pr, []).append(t)
        if err := page.evaluate("() => window.__error || ''"):
            bledy.append(err.strip())
        browser.close()
    return {"rozmiar": [w, h], "dlugosc": dlugosc, "probek": probki, "bledy": list(dict.fromkeys(bledy)),
            "problemy": [{"problem": k, "pierwszy_t": v[0], "probek": len(v)} for k, v in problemy.items()]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("strona", help="config JSON → samodzielna strona HTML")
    s.add_argument("config")
    s.add_argument("-o", "--wyjscie", help="plik .html (domyślnie obok configu)")
    s.add_argument("--szablon", help="inny template.html live-panel")
    s = sub.add_parser("sprawdz", help="układ strony w wielu chwilach (kod 1 = problemy)")
    s.add_argument("strona")
    s.add_argument("--probki", type=int, default=120)
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("film", help="strona → MP4 (html_wideo.py, preset livepanel) z cichą ścieżką AAC")
    s.add_argument("strona")
    s.add_argument("-o", "--wyjscie", required=True)
    s.add_argument("--bez-audio", action="store_true", help="bez cichej ścieżki (np. do dalszego montażu)")
    sub.add_parser("formaty", help="formaty platform i motywy Jarva")
    a = ap.parse_args(argv)

    if a.cmd == "formaty":
        for k, (w, h, gdzie) in FORMATY.items():
            print(f"canvas.preset {k:<8} {w}×{h}  {gdzie}")
        for k, m in MOTYWY.items():
            print(f"theme.preset  {k:<13} {m['opis']}")
        return 0
    if a.cmd == "strona":
        src = Path(a.config)
        try:
            cfg = json.loads(src.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"✗ {src}: {e}", file=sys.stderr)
            return 2
        html, uwagi = strona(cfg, Path(a.szablon) if a.szablon else None)
        out = Path(a.wyjscie) if a.wyjscie else src.with_suffix(".html")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        for u in uwagi:
            print(f"  ! {u}")
        print(f"✓ {out} ({len(html) // 1024} kB)")
        return 0
    if a.cmd == "film":
        return film(Path(a.strona), Path(a.wyjscie), not a.bez_audio)
    import narzedzia as nz
    nz.wymagaj_playwright(__file__, "JARVO_ZS_REEXEC")
    wynik = sprawdz(Path(a.strona), a.probki)
    if a.json:
        print(json.dumps(wynik, ensure_ascii=False, indent=1))
    else:
        for e in wynik["bledy"]:
            print(f"  ✗ błąd strony: {e[:300]}")
        for pr in wynik["problemy"]:
            print(f"  ✗ {pr['problem']} (od t={pr['pierwszy_t']} s, {pr['probek']} z {wynik['probek']} próbek)")
        w, h = wynik["rozmiar"]
        print(f"{'✓' if not (wynik['bledy'] or wynik['problemy']) else '✗'} {a.strona}: {w}×{h}, {wynik['dlugosc']} s, "
              f"{wynik['probek']} próbek, problemów: {len(wynik['problemy']) + len(wynik['bledy'])}")
    return 1 if wynik["bledy"] or wynik["problemy"] else 0


if __name__ == "__main__":
    sys.exit(main())
