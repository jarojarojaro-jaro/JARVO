#!/usr/bin/env python3
"""Pracownia malarza (silnikjava, MIT): film, na którym obraz powstaje pociągnięcie po pociągnięciu albo kreska po
kresce, z pracy zrobionej przez malarza silnika (`maluj.mjs`: pędzel olejny albo kredki, pastele, węgiel, ołówek, tusz,
akwarela). Strona pracowni jest ich, render robi html_wideo.py, wynik to projekt edytora HQ.

    pracownia.py klatki out/malarz/jezioro/obraz.json [--czasy 2,8,20,33] --arkusz out/wideo/pracownia.jpg
    pracownia.py film out/malarz/jezioro/obraz.json -o out/wideo/jezioro.mp4 [--czas 30] [--koniec 3.5]
                      [--uklad pion|poziom] [--dzwiek] [--arkusz qa.jpg] [-- <opcje projekt.py z-kodu, np. --muzyka m.wav>]

Obraz (`obraz.json`) robi malarz silnika, wołany przez narzedzia.py (ścieżki ze zmiennych narzędzia):
    narzedzia.py uruchom silnikjava -- node {MALARZ}/maluj.mjs {MALARZ}/motywy/jezioro.js --styl etiuda --out out/malarz/jezioro

Obok obraz.json powstaje `pracownia.html` (kontrakt jarvo: __seek = klatka(t) pracowni, rozmiar z płótna pracowni,
moduły z /_lib/malarz/), potem `pracownia.mp4` (obraz filmu bez dźwięku) i z `--dzwiek` `szelest.wav` (szelest
narzędzia w rytm ruchu ręki: ich lib/dzwiek.js, liczony w tej samej stronie). `film` składa projekt edytora:
`projekt.py z-kodu <film> --obraz pracownia.mp4 [--efekty szelest.wav] --render`, więc właściciel podmieni dźwięk,
doda muzykę albo przytnie film w edytorze HQ. Kadr: pion 1080×1920, a praca szersza niż 1,2:1 sama w poziomie
1920×1080 (--uklad wymusza). Czas: --czas s malowania (domyślnie 30) + --koniec s gotowego obrazu (3,5) + 0,9 s wstępu.
Wymaga `narzedzia.py instaluj silnikjava`. Kod wyjścia: 0 ok, 1 błąd renderu, 2 złe wejście.
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import narzedzia as nz  # noqa: E402

SR_SZELESTU = 44100            # jak wav() w lib/dzwiek.js
HZ_RUCHU = 240                 # jak film.mjs: ruch narzędzia 240 razy na sekundę

STRONA = """<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><title>Pracownia</title>
<!-- pracownia.py: film z pracowni malarza silnikjava (MIT) w kontrakcie jarvo (html_wideo.py --preset jarvo) -->
<style>html,body{{margin:0;background:#0d0b0a;overflow:hidden}}canvas{{display:block}}</style></head>
<body><canvas id="kadr"></canvas>
<script>
// ustawienia filmu (pracownia czyta je z adresu strony); przy renderze (?render=1) bez pętli podglądu
{{ const q = new URLSearchParams(location.search), u = {ustawienia};
  for (const [k, v] of Object.entries(u)) if (!q.has(k)) q.set(k, v);
  if (q.has('render')) q.set('film', '1');
  history.replaceState(null, '', location.pathname + '?' + q); }}
</script>
<script type="module" src="/_lib/malarz/pracownia/pracownia.js"></script>
<script type="module">
const p = await window.__malarz.gotowy;
Object.assign(window, {{ __W: p.canvas.width, __H: p.canvas.height, __DUR: p.czas }});
window.__seek = (t) => {{ p.klatka(t); }};
await document.fonts.ready;
p.klatka(0);
window.__ready = true;
</script></body></html>
"""

# szelest liczony w stronie (szelest z lib/dzwiek.js na ruchu z pracowni), próbki jak wav(): 16 bitów, mono
SZELEST_JS = """async (hz) => {
  const { szelest } = await import('/_lib/malarz/lib/dzwiek.js');
  const s = szelest(window.__malarz.ruch(hz), hz);
  const b = new Uint8Array(s.length * 2), v = new DataView(b.buffer);
  for (let i = 0; i < s.length; i++) v.setInt16(i * 2, Math.round(Math.max(-1, Math.min(1, s[i])) * 32767), true);
  let bin = '';
  for (let i = 0; i < b.length; i += 0x8000) bin += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000));
  return btoa(bin);
}"""


def strona(czas: float, koniec: float, uklad: str | None, plik: str = "obraz.json") -> str:
    u = {"obraz": plik, "czas": f"{czas:g}", "koniec": f"{koniec:g}", "jakosc": "2", **({"uklad": uklad} if uklad else {})}
    return STRONA.format(ustawienia=json.dumps(u))


def zapisz_szelest(probki_b64: str, plik: Path) -> Path:
    with wave.open(str(plik), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR_SZELESTU)
        f.writeframes(base64.b64decode(probki_b64))
    return plik


def przygotuj(obraz: Path, a) -> Path:
    if not nz.silnikjava_gotowe():
        raise SystemExit("✗ brak silnikjava: python3 $HERMES_HOME/scripts/narzedzia.py instaluj silnikjava")
    if not obraz.is_file():
        raise SystemExit(f"✗ brak {obraz} (najpierw maluj.mjs malarza)")
    html = obraz.parent / "pracownia.html"
    html.write_text(strona(a.czas, a.koniec, a.uklad, obraz.name), encoding="utf-8")
    return html


def html_wideo(argv: list[str]) -> str:
    p = subprocess.run([sys.executable, str(HERE / "html_wideo.py"), *argv], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    for linia in p.stderr.splitlines():           # pomiar HTML nie dotyczy pracowni (obraz bez tekstu filmu)
        if not linia.startswith("⚠ pomiar animacji"):
            print(linia, file=sys.stderr)
    if p.returncode:
        raise SystemExit(f"✗ html_wideo.py {argv[0]}: kod {p.returncode}")
    return p.stdout.strip()


def czas_filmu(html: Path) -> float:
    import html_wideo as hw
    from playwright.sync_api import sync_playwright
    return _w_stronie(hw, sync_playwright, html, "() => window.__DUR", None)


def _w_stronie(hw, sync_playwright, html: Path, js: str, arg):
    httpd = hw.serve(html.resolve().parent, lib=True)
    bledy: list[str] = []
    try:
        with sync_playwright() as p:
            browser = hw.launch(p)
            page = hw._page(browser, (1080, 1920), 1.0, bledy)
            page.goto(f"http://127.0.0.1:{httpd.server_address[1]}/{html.name}?render=1", wait_until="load")
            hw.czekaj_gotowe(page, "window.__ready === true", bledy)
            wynik = page.evaluate(js, arg)
            browser.close()
    finally:
        httpd.shutdown()
    return wynik


def cmd_klatki(a) -> int:
    nz.wymagaj_playwright(__file__, "JARVO_PRACOWNIA_REEXEC")
    html = przygotuj(Path(a.obraz), a)
    czasy = a.czasy
    if not czasy:
        dl = czas_filmu(html)
        czasy = ",".join(f"{dl * f:.2f}" for f in (0.03, 0.12, 0.3, 0.55, 0.8, 0.99))   # jak film.mjs --arkusz
    print(html_wideo(["klatki", str(html), "--preset", "jarvo", "--czasy", czasy,
                      "--out", str(html.parent / "klatki"), "--arkusz", a.arkusz]))
    return 0


def cmd_film(a, z_kodu: list[str]) -> int:
    nz.wymagaj_playwright(__file__, "JARVO_PRACOWNIA_REEXEC")
    html = przygotuj(Path(a.obraz), a)
    dl = czas_filmu(html)
    obraz_mp4 = html.parent / "pracownia.mp4"
    print(f"▶ pracownia: {dl:.1f} s", file=sys.stderr, flush=True)
    html_wideo(["wideo", str(html), "--preset", "jarvo", "--dlugosc", f"{dl:.3f}", "--fps", str(a.fps),
                "-o", str(obraz_mp4), *(["--arkusz", a.arkusz] if a.arkusz else [])])
    cmd = [sys.executable, str(HERE / "projekt.py"), "z-kodu", a.o, "--obraz", str(obraz_mp4)]
    if a.dzwiek:
        import html_wideo as hw
        from playwright.sync_api import sync_playwright
        szelest = zapisz_szelest(_w_stronie(hw, sync_playwright, html, SZELEST_JS, HZ_RUCHU), html.parent / "szelest.wav")
        cmd += ["--efekty", str(szelest)]
    cmd += [*z_kodu, "--render"]
    print("▶ projekt edytora: " + " ".join(cmd[1:]), file=sys.stderr, flush=True)
    if subprocess.run(cmd).returncode:
        return 1
    print(json.dumps({"film": a.o, "projekt": str(Path(a.o).with_suffix(".edycja.json")), "obraz": obraz_mp4.as_posix(),
                      "dlugosc_s": round(dl, 2), "szelest": a.dzwiek, **({"arkusz": a.arkusz} if a.arkusz else {})},
                     ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    z_kodu: list[str] = []
    if "--" in args:
        i = args.index("--")
        args, z_kodu = args[:i], args[i + 1:]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nazwa in ("klatki", "film"):
        s = sub.add_parser(nazwa)
        s.add_argument("obraz", help="obraz.json z maluj.mjs (albo zapis ze szkicownika)")
        s.add_argument("--czas", type=float, default=30.0, help="sekundy malowania (domyślnie 30)")
        s.add_argument("--koniec", type=float, default=3.5, help="sekundy gotowego obrazu na końcu (domyślnie 3,5)")
        s.add_argument("--uklad", choices=["pion", "poziom"], help="kadr (domyślnie wg proporcji pracy)")
        if nazwa == "klatki":
            s.add_argument("--czasy", help="sekundy po przecinku (domyślnie 6 chwil z całego filmu)")
            s.add_argument("--arkusz", required=True, help="JPG ze stopklatkami")
        else:
            s.add_argument("-o", required=True, help="film .mp4 (obok projekt <film>.edycja.json)")
            s.add_argument("--fps", type=int, default=30)
            s.add_argument("--dzwiek", action="store_true", help="szelest narzędzia jako efekty w projekcie")
            s.add_argument("--arkusz", help="JPG z 12 klatkami filmu")
    a = ap.parse_args(args)
    if a.cmd != "film" and z_kodu:
        raise SystemExit("opcje po `--` tylko przy `film` (idą do projekt.py z-kodu)")
    return cmd_film(a, z_kodu) if a.cmd == "film" else cmd_klatki(a)


if __name__ == "__main__":
    sys.exit(main())
