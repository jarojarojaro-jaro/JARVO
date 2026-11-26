#!/usr/bin/env python3
"""Film rysowany: ręka rysuje schematy i pisze odręcznie pod lektora (silnikjava, MIT: ręka, pismo, 21 stylów,
kamera, ścieranie tablicy, rolki 9:16). Strona i scena są nasze, render robi html_wideo.py, wynik to projekt edytora.

    rysowany.py style [--json]                                     # 21 stylów silnika: id, nazwa, do czego
    rysowany.py wzor notebook [--czasy 2,6,12] [--arkusz out/wideo/wzor-notebook.jpg]   # stopklatki filmu-wzoru stylu
    rysowany.py nowy out/wideo/src/film --styl chalk [--pion] [--tytul "Jak działa agent?"]   # strona + scena.js
    rysowany.py glos out/wideo/src/film out/wideo/src/film/os_czasu.json    # czasy słów lektora → glos/voice.json
    rysowany.py glos out/wideo/src/film lektor.slowa.json --lektor lektor.mp3   # krótki lektor (film.py lektor)
    rysowany.py sprawdz out/wideo/src/film [--json]                # lint i audyt silnika (kod wyjścia 1 = do poprawy)
    rysowany.py film out/wideo/src/film -o out/wideo/film.mp4 [--fps 30] [--arkusz qa.jpg] [-- <opcje projekt.py z-kodu>]

`nowy` robi w katalogu `index.html` (kontrakt jarvo dla html_wideo.py: __seek, __ready, __W/__H/__DUR; silnik
z /_lib/silnikjava/, kroje stylów z /_lib/silnikjava/kroje/fonts.css) i `scena.js` (export function zbuduj(glos) →
Storyboard): punkt startu, który przerabiasz. Kadr sceny 1280×720 (render 1920×1080) albo z --pion 720×1280 (render
1080×1920, strefa bezpieczna rolki x 36 do 640, y 150 do 900). Napisy rolki silnika są wyłączone: napisy lektora idą do
projektu edytora jako tekst (karaoke ze słów).

`glos` zamienia czasy słów naszego lektora (film.py narracja: os_czasu.json, albo film.py lektor: <plik>.slowa.json)
na voice.json silnika: zdanie = beat (sb.say), słowa z czasem od początku zdania (kotwice `cue`), bez drugiej drogi
TTS. Silnik układa zdania sam (lektor czeka na rękę do 1,5 s), więc `film` składa ścieżkę lektora od nowa: każde
zdanie wycięte z nagrania i położone tam, gdzie postawił je silnik; słowa karaoke przesunięte tak samo.

`sprawdz` to lint i audyt silnika (port tools/lint.mjs i tools/audit.mjs silnikjava w naszej przeglądarce, z krojami
stylu): fizyka ręki, kolejność obiektu, kotwice, przestoje, strefa rolki (lint: błędy i ostrzeżenia) oraz skoki ręki
i czas klatki p95 (audyt, 30 kl./s, skok > 70 px, budżet 33 ms przy szerokości 1280). Kod wyjścia 1: błąd lintu albo
skok ręki albo p95 ponad budżet.

`film`: render strony przez html_wideo.py (obraz bez napisów i bez dźwięku), lektor ułożony pod silnik, cięcia
ujęć na początkach akapitów lektora i na ścieraniu tablicy, potem `projekt.py z-kodu … --karaoke --render`
(film = render projektu edytora `<film>.edycja.json`). Opcje po `--` idą do `projekt.py z-kodu` (np. --muzyka plik).
Wymaga `narzedzia.py instaluj silnikjava`. Kod wyjścia: 0 ok, 1 błąd sprawdzenia albo renderu, 2 złe wejście.
"""

from __future__ import annotations

import argparse
import array
import json
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import narzedzia as nz  # noqa: E402
import wideo_lib as wl  # noqa: E402

SKALA = {"poziom": (1280, 720, 1920, 1080), "pion": (720, 1280, 1080, 1920)}   # kadr sceny i render
SR = 48000
PRZED, PO = 0.12, 0.2          # zapas nagrania przed i po zdaniu przy wycinaniu z lektora (pauzy narracji ≥ 0,33 s)
FPS_AUDYTU, SKOK_PX, BUDZET_MS = 30, 70, 33.0   # jak tools/audit.mjs silnikjava
KONIEC_ZDANIA = re.compile(r"[.!?…]+[\"'”»)]*$")


# ---------------------------------------------------------------- strona i scena

STRONA = """<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><title>{tytul}</title>
<!-- rysowany.py: film rysowany silnikjava (MIT) w kontrakcie jarvo (html_wideo.py --preset jarvo) -->
<link rel="stylesheet" href="/_lib/silnikjava/kroje/fonts.css">
<style>html,body{{margin:0;background:#000;overflow:hidden}}canvas{{display:block}}</style></head>
<body><canvas id="c"></canvas>
<script type="module">
import {{ Player, Sketch, Voice, loadFonts }} from '/_lib/silnikjava/src/index.js';
{import_sceny}
const GLOS = {glos};   // czasy słów lektora (rysowany.py glos); null = film bez lektora

const glos = GLOS ? await Voice.load(GLOS) : null;
// napisy rolki silnika wyłączone: napisy lektora idą do projektu edytora jako tekst (karaoke)
const zbudujBezNapisow = () => {{ const s = zbuduj(glos); s.captions = null; return s; }};
const sb = zbudujBezNapisow();
const scene = sb.scene();
const W = scene.h > scene.w ? 1080 : 1920, H = Math.round(W * scene.h / scene.w), DUR = scene.duration + 1;
Object.assign(window, {{ __W: W, __H: H, __DUR: DUR }});
const c = document.getElementById('c');
c.style.width = W + 'px'; c.style.height = H + 'px';
const player = new Player(c, scene, {{ trigger: 'manual', audio: false }});
window.__player = player;
window.__silnik = {{ zbuduj: zbudujBezNapisow, Sketch, loadFonts }};
window.__seek = (t) => {{ player.seek(t); }};
// oś filmu dla rysowany.py film: gdzie silnik postawił zdania lektora i gdzie ściera tablicę
window.__os = () => ({{
  dlugosc: DUR, w: W, h: H, format: sb.format, styl: sb.theme ?? 'paper',
  zdania: sb.audio.map((a) => {{
    const moje = sb.items.filter((it) => it.beat === a.id).map((it) => it.seg.start);
    return {{ id: a.id, start: a.start, dur: a.dur, czeka: a.wait ?? 0,
             rysunek_od: moje.length ? Math.min(...moje) : a.start, rysunek_do: a.drawEnd ?? a.start + a.dur }};
  }}),
  scieranie: sb.clears.map((k) => k.item.seg.start),
}});
await player.loaded;
player.seek(0);
window.__ready = true;
if (!new URLSearchParams(location.search).has('render')) player.play();   // podgląd dla człowieka (bez dźwięku)
</script></body></html>
"""

SCENA = """// Scena filmu rysowanego (silnikjava, MIT): punkt startu z rysowany.py nowy, przerób ją na swój temat.
// Zasady rysownika: skill film-rysowany, references/zasady-rysownika.md (kopia docs/ZASADY.md silnika).
// Kadr sceny {w}×{h} jednostek (render {rw}×{rh} px){strefa}. Czas wynika z ręki i lektora, nie z wpisanych sekund:
// obiekt w całości (kontur → kolor → detale → podpis), potem następny; kotwica `cue` na pierwszym kroku obiektu.
import {{ Storyboard, rect, line }} from '/_lib/silnikjava/src/index.js';

export function zbuduj(glos) {{
  const sb = new Storyboard({{ theme: '{styl}'{format} }});
  const tytul = () => {{
    sb.write({tytul_js}, {cx}, {ty}, {{ size: {ts}, font: 'title', align: 'center', keep: true }});
    sb.pen(line({ux0}, {uy}, {ux1}, {uy}, {{ seed: 2 }}), {{ color: 'teal', w: 4, keep: true }});
  }};
  // jeden obiekt na zdanie: ramka, kolor, podpis (kolejne miejsca w siatce; co {na_tablicy} zdania ścieranie tablicy)
  const obiekt = (i, cue) => {{
    const k = i % {na_tablicy}, x = {x0} + k * {dx}, y = {y0} + k * {dy};
    sb.pen(rect(x, y, {bw}, {bh}, {{ seed: 10 + i }}), {{ color: 'ink', w: 3, seed: 10 + i, cue }});
    sb.crayon([[x + 6, y + 6], [x + {bw} - 6, y + 6], [x + {bw} - 6, y + {bh} - 6], [x + 6, y + {bh} - 6]],
              {{ color: ['sky', 'coral', 'ochre', 'teal'][i % 4], seed: 20 + i }});
    sb.write(String(i + 1), x + {bw} / 2, y + {bh} / 2 + 18, {{ size: 56, align: 'center' }});
  }};
  if (!glos) {{                       // bez lektora: tempo ręki, na końcu chwila na obejrzenie
    tytul();
    for (let i = 0; i < 3; i++) obiekt(i);
    sb.wait(1);
    return sb;
  }}
  sb.say(glos.beat(1), tytul);       // zdanie 1: tytuł (ręka rusza 0,3 s przed głosem)
  glos.beats.slice(1).forEach((b, i) => {{
    if (i > 0 && i % {na_tablicy} === 0) sb.clear();
    sb.say(b, () => obiekt(i, b.words[0]?.w));
  }});
  sb.wait(0.8);
  return sb;
}}
"""


def strona(import_sceny: str, glos: str | None, tytul: str = "Film rysowany") -> str:
    return STRONA.format(tytul=tytul.replace("<", "&lt;"), import_sceny=import_sceny,
                         glos=json.dumps(glos) if glos else "null")


def scena(styl: str, pion: bool, tytul: str) -> str:
    w, h, rw, rh = SKALA["pion" if pion else "poziom"]
    if pion:                           # strefa bezpieczna rolki: x 36 do 640, y 150 do 900
        uklad = dict(cx=338, ty=250, ts=60, ux0=120, ux1=556, uy=275, x0=168, y0=330, dx=0, dy=180, bw=340, bh=150,
                     na_tablicy=3, strefa=", strefa bezpieczna rolki x 36 do 640, y 150 do 900")
    else:
        uklad = dict(cx=640, ty=130, ts=72, ux0=380, ux1=900, uy=160, x0=140, y0=280, dx=360, dy=0, bw=280, bh=260,
                     na_tablicy=3, strefa="")
    return SCENA.format(w=w, h=h, rw=rw, rh=rh, styl=styl, format=", format: 'reel'" if pion else "",
                        tytul_js=json.dumps(tytul, ensure_ascii=False), **uklad)


def silnik() -> Path:
    if not nz.silnikjava_gotowe():
        raise SystemExit("✗ brak silnikjava: python3 $HERMES_HOME/scripts/narzedzia.py instaluj silnikjava")
    return nz.SILNIKJAVA


def style(sj: Path) -> list[dict]:
    """21 stylów z rejestru silnika (examples/scenes/styles/index.js): id, nazwa, opis, funkcja filmu-wzoru."""
    tekst = (sj / "examples" / "scenes" / "styles" / "index.js").read_text(encoding="utf-8")
    wzor = re.compile(r"\{ id: '([a-z0-9-]+)', name: '([^']+)', build: (\w+), about: '((?:[^'\\]|\\.)*)' \}")
    return [{"id": m[1], "nazwa": m[2], "wzor": m[3], "opis": m[4].replace("\\\\", "\\")} for m in wzor.finditer(tekst)]


# ---------------------------------------------------------------- lektor → voice.json silnika

def _sciezka(p: str, *bazy: Path) -> Path | None:
    for baza in (Path.cwd(), *bazy):
        q = (baza / p) if not Path(p).is_absolute() else Path(p)
        if q.is_file():
            return q.resolve()
    return None


def zdania_z_osi(os_: dict) -> list[dict]:
    """os_czasu.json z film.py narracja → zdania {id, tekst, start, koniec, ujecie, slowa [{tekst, start, koniec}]}."""
    return [{"tekst": z["tekst"], "start": float(z["start"]), "koniec": float(z["koniec"]), "ujecie": z.get("ujecie"),
             "slowa": [{"tekst": w["tekst"], "start": float(w["start"]), "koniec": float(w["koniec"])}
                       for w in z.get("slowa") or []]} for z in os_.get("zdania") or []]


def zdania_ze_slow(slowa: list[dict]) -> list[dict]:
    """Słowa z czasem (film.py lektor: [{start, end, text}]) → zdania podzielone na . ! ? …; jedno ujęcie."""
    out: list[dict] = []
    for w in slowa:
        tekst = str(w.get("text") or w.get("tekst") or "").strip()
        if not tekst:
            continue
        if not out or KONIEC_ZDANIA.search(out[-1]["slowa"][-1]["tekst"]):
            out.append({"slowa": [], "ujecie": "u1"})
        out[-1]["slowa"].append({"tekst": tekst, "start": float(w.get("start")), "koniec": float(w.get("end", w.get("koniec")))})
    for z in out:
        z.update(tekst=" ".join(w["tekst"] for w in z["slowa"]), start=z["slowa"][0]["start"], koniec=z["slowa"][-1]["koniec"])
    return out


def voice_json(zdania: list[dict], lektor: str, podzialy: set[float] | None = None) -> dict:
    """Zdania lektora → voice.json silnika: beat na zdanie (id b1…), czasy słów od początku zdania (w, s, e),
    `p` = podział napisu po słowie, `ujecie` = akapit narracji (cięcie ujęcia), meta: plik lektora i czas zdania."""
    beats, meta = [], []
    for i, z in enumerate(zdania, 1):
        st = z["start"]
        slowa = [{"w": w["tekst"], "s": round(max(0.0, w["start"] - st), 3), "e": round(max(0.0, w["koniec"] - st), 3),
                  **({"p": True} if podzialy and round(w["start"], 3) in podzialy else {})} for w in z["slowa"]]
        beats.append({"id": f"b{i}", "text": z["tekst"], "audio": None, "duration": round(z["koniec"] - st, 3),
                      "ujecie": z.get("ujecie"), "words": slowa})
        meta.append({"id": f"b{i}", "start": round(st, 3), "koniec": round(z["koniec"], 3)})
    return {"source": "jarvo", "lektor": lektor, "zdania": meta, "beats": beats}


def cmd_glos(a) -> int:
    katalog, zrodlo = Path(a.katalog), Path(a.zrodlo)
    if not (katalog / "index.html").is_file():
        raise SystemExit(f"✗ brak {katalog}/index.html (najpierw rysowany.py nowy)")
    d = json.loads(zrodlo.read_text(encoding="utf-8"))
    if isinstance(d, dict) and "zdania" in d:
        zdania, lektor = zdania_z_osi(d), a.lektor or d.get("lektor")
    else:
        zdania, lektor = zdania_ze_slow(d if isinstance(d, list) else d.get("words") or []), a.lektor
    if not zdania:
        raise SystemExit(f"✗ {zrodlo}: brak zdań ze słowami")
    plik = _sciezka(str(lektor or ""), zrodlo.resolve().parent) if lektor else None
    if plik is None:
        raise SystemExit(f"✗ nie znajduję nagrania lektora ({lektor!r}): podaj --lektor plik")
    podzialy = None
    slowa_lektora = plik.with_suffix(".slowa.json")       # film.py narracja: podziały napisów z narracji (`|`)
    if slowa_lektora.is_file():
        podzialy = {round(float(w["start"]), 3) for w in json.loads(slowa_lektora.read_text(encoding="utf-8"))
                    if isinstance(w, dict) and w.get("podzial")}
    (katalog / "glos").mkdir(parents=True, exist_ok=True)
    wl.write_json(katalog / "glos" / "voice.json", voice_json(zdania, plik.as_posix(), podzialy))
    html = (katalog / "index.html").read_text(encoding="utf-8")
    (katalog / "index.html").write_text(re.sub(r"^const GLOS = .*?;", 'const GLOS = "glos/voice.json";', html, count=1,
                                               flags=re.M), encoding="utf-8")
    print(json.dumps({"glos": (katalog / "glos" / "voice.json").as_posix(), "zdania": len(zdania),
                      "slowa": sum(len(z["slowa"]) for z in zdania), "lektor": plik.as_posix(),
                      "uzycie": "scena.js: sb.say(glos.beat(N), () => { … cue: 'słowo' … })"}, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------- lektor pod oś silnika

def czytaj_pcm(plik: Path) -> array.array:
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(plik), "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                       capture_output=True)
    if r.returncode:
        raise SystemExit(f"✗ ffmpeg nie odczytał {plik}: {r.stderr.decode(errors='replace')[-300:]}")
    pcm = array.array("h")
    pcm.frombytes(r.stdout[:len(r.stdout) // 2 * 2])
    return pcm


def uloz_lektor(pcm: array.array, glos: dict, os_: dict) -> tuple[array.array, list[dict]]:
    """Każde zdanie z nagrania (z zapasem PRZED/PO, bez wchodzenia w sąsiednie) położone tam, gdzie silnik postawił
    jego beat; słowa karaoke przesunięte tak samo. Czysta funkcja: PCM (mono, SR) i voice.json → PCM filmu i słowa."""
    start_silnika = {z["id"]: float(z["start"]) for z in os_["zdania"]}
    zdania = glos["zdania"]
    out = array.array("h", bytes(2 * int(round(os_["dlugosc"] * SR))))
    slowa: list[dict] = []
    for i, (z, beat) in enumerate(zip(zdania, glos["beats"])):
        if z["id"] not in start_silnika:
            continue
        przed = min(PRZED, (z["start"] - zdania[i - 1]["koniec"]) / 2) if i else min(PRZED, z["start"])
        po = min(PO, (zdania[i + 1]["start"] - z["koniec"]) / 2) if i + 1 < len(zdania) else PO
        a, b = int(round((z["start"] - przed) * SR)), min(len(pcm), int(round((z["koniec"] + po) * SR)))
        na = int(round((start_silnika[z["id"]] - przed) * SR))
        for k, v in enumerate(pcm[a:b], na):
            if 0 <= k < len(out):
                out[k] = max(-32768, min(32767, out[k] + v))
        t0 = start_silnika[z["id"]]
        slowa += [{"start": round(t0 + w["s"], 3), "end": round(t0 + w["e"], 3), "text": w["w"],
                   **({"podzial": True} if w.get("p") else {})} for w in beat["words"]]
    return out, slowa


def zapisz_wav(pcm: array.array, plik: Path) -> Path:
    with wave.open(str(plik), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(pcm.tobytes())
    return plik


def ciecia(os_: dict, glos: dict | None) -> list[float]:
    """Cięcia ujęć projektu: początek rysunku pierwszego zdania każdego akapitu lektora (albo ścieranie tablicy tuż
    przed nim); film bez lektora tnie się na ścieraniu tablicy."""
    if not glos or not os_["zdania"]:
        return sorted(round(t, 3) for t in os_["scieranie"])
    ujecie = {b["id"]: b.get("ujecie") for b in glos["beats"]}
    out = []
    zd = os_["zdania"]
    for prev, z in zip(zd, zd[1:]):
        if ujecie.get(z["id"]) == ujecie.get(prev["id"]):
            continue
        t = z["rysunek_od"]
        przed = [s for s in os_["scieranie"] if prev["rysunek_do"] - 1e-6 <= s <= t]
        out.append(round(min([t, *przed]), 3))
    return out


# ---------------------------------------------------------------- przeglądarka: oś, lint, audyt

LINT_JS = """async () => {
  // jak tools/lint.mjs silnikjava: świeży scenariusz, Sketch z prawdziwymi krojami stylu, sb.lint(sk)
  const S = window.__silnik, sb = S.zbuduj();
  const sk = new S.Sketch(window.__player.ctx, { theme: sb.theme ?? 'paper' });
  await S.loadFonts(sk.fonts);
  const problemy = sb.lint(sk).map((i) => ({ poziom: i.level === 'warn' ? 'uwaga' : 'blad', t: +i.time.toFixed(2),
                                             nazwa: i.name, problem: i.problem }));
  const kroki = [...sb.items].sort((a, b) => a.seg.start - b.seg.start).map((i) => ({ start: +i.seg.start.toFixed(2),
    dur: +i.seg.dur.toFixed(2), nazwa: i.name, zdanie: i.beat ?? null,
    kotwica: i.cue ? { slowo: i.cue.word, t: +i.cue.target.toFixed(2) } : null }));
  return { dlugosc: sb.duration, krokow: sb.items.length, problemy, kroki };
}"""

AUDYT_JS = """({ fps, jumpPx, width }) => {
  // jak tools/audit.mjs silnikjava (sizeCanvas na szerokość `width`, rozgrzewka, render każdej klatki,
  // pozycja ręki z sk.tool w jednostkach sceny)
  const pl = window.__player, c = pl.canvas;
  Object.assign(c.style, { position: 'fixed', left: '0', top: '0', maxWidth: 'none' });
  c.style.width = `${width}px`; c.style.height = `${Math.round((width * pl.scene.h) / pl.scene.w)}px`;
  pl.pause(); pl.resize();
  const sk = pl.sk, sc = pl.scene.w / (sk.ctx.canvas.width || pl.scene.w);
  let pos = null;
  const orig = sk.tool.bind(sk);
  sk.tool = (x, y, o) => {
    const m = sk.ctx.getTransform();
    pos = { x: (m.a * x + m.c * y + m.e) * sc, y: (m.b * x + m.d * y + m.f) * sc };
    return orig(x, y, o);
  };
  for (let i = 0; i < 10; i++) pl.renderAt(i / fps);
  const times = [], track = [], n = Math.ceil(pl.duration * fps);
  for (let i = 0; i <= n; i++) {
    const t = i / fps; pos = null;
    const t0 = performance.now(); pl.renderAt(t); times.push(performance.now() - t0);
    track.push(pos && { t, ...pos });
  }
  sk.tool = orig;
  const step = track.map((q, i) => (i && q && track[i - 1] ? Math.hypot(q.x - track[i - 1].x, q.y - track[i - 1].y) : 0));
  const jumps = []; let visible = 0, maxSpeed = 0;
  for (let i = 0; i < track.length; i++) {
    if (track[i]) visible++;
    maxSpeed = Math.max(maxSpeed, step[i] * fps);
    const around = Math.max(step[i - 1] ?? 0, step[i + 1] ?? 0);
    if (step[i] > jumpPx && step[i] > 2.5 * around) jumps.push({ t: +track[i].t.toFixed(2), px: Math.round(step[i]) });
  }
  const sorted = [...times].sort((a, b) => a - b);
  const q = (k) => sorted[Math.min(sorted.length - 1, Math.floor(k * sorted.length))];
  return { klatek: times.length, sr_ms: times.reduce((a, b) => a + b, 0) / times.length, p95_ms: q(0.95),
           max_ms: sorted[sorted.length - 1], reka_proc: (100 * visible) / track.length, vmax: maxSpeed, skoki: jumps };
}"""


def w_przegladarce(strona_html: Path, *zadania: tuple[str, object]) -> tuple[list, list[str]]:
    """Strona z lokalnego serwera Wideografa (/_lib/silnikjava/ i kroje), gotowość jak przy renderze; wynik każdego
    (js, argument) po kolei w tej samej karcie. Zwraca wyniki i błędy strony."""
    import html_wideo as hw
    from playwright.sync_api import sync_playwright
    httpd = hw.serve(strona_html.resolve().parent, lib=True)
    bledy: list[str] = []
    try:
        with sync_playwright() as p:
            browser = hw.launch(p)
            page = hw._page(browser, (1920, 1080), 1.0, bledy)
            page.goto(f"http://127.0.0.1:{httpd.server_address[1]}/{strona_html.name}?render=1", wait_until="load")
            hw.czekaj_gotowe(page, "window.__ready === true", bledy)
            wyniki = [page.evaluate(js, arg) if arg is not None else page.evaluate(js) for js, arg in zadania]
            browser.close()
    finally:
        httpd.shutdown()
    return wyniki, bledy


def ocena(lint: dict, audyt: dict | None, budzet: float) -> dict:
    bledy = [p for p in lint["problemy"] if p["poziom"] == "blad"]
    uwagi = [p for p in lint["problemy"] if p["poziom"] != "blad"]
    wynik = {"ok": not bledy, "lint": {"krokow": lint["krokow"], "dlugosc_s": round(lint["dlugosc"], 2),
                                         "bledy": bledy, "uwagi": uwagi}}
    if audyt is not None:
        audyt = {k: (round(v, 1) if isinstance(v, float) else v) for k, v in audyt.items()}
        audyt["w_budzecie"] = audyt["p95_ms"] <= budzet
        wynik["audyt"] = audyt
        wynik["ok"] = wynik["ok"] and not audyt["skoki"] and audyt["w_budzecie"]
    return wynik


def cmd_sprawdz(a) -> int:
    silnik()
    nz.wymagaj_playwright(__file__, "JARVO_RYSOWANY_REEXEC")
    strona_html = Path(a.katalog) / "index.html"
    if not strona_html.is_file():
        raise SystemExit(f"✗ brak {strona_html}")
    zadania: list[tuple[str, object]] = [(LINT_JS, None)]
    if not a.bez_audytu:
        zadania.append((AUDYT_JS, {"fps": FPS_AUDYTU, "jumpPx": a.skok, "width": 1280}))
    wyniki, bledy_strony = w_przegladarce(strona_html, *zadania)
    w = ocena(wyniki[0], wyniki[1] if len(wyniki) > 1 else None, a.budzet)
    if bledy_strony:
        w["bledy_strony"] = list(dict.fromkeys(bledy_strony))
        w["ok"] = False
    wl.write_json(Path(a.katalog) / "sprawdzenie.json", {**w, "kroki": wyniki[0]["kroki"]})
    if a.json:
        print(json.dumps(w, ensure_ascii=False, indent=1))
    else:
        li = w["lint"]
        print(f"lint: {li['krokow']} kroków, {li['dlugosc_s']} s, {len(li['bledy'])} błędów, {len(li['uwagi'])} uwag")
        for p in li["bledy"] + li["uwagi"]:
            print(f"  {'BŁĄD ' if p['poziom'] == 'blad' else 'uwaga'}  {p['t']:6.2f} s  {p['nazwa']}: {p['problem']}")
        if "audyt" in w:
            au = w["audyt"]
            skoki = " ".join(f"{s['t']}s:{s['px']}px" for s in au["skoki"][:5])
            print(f"audyt: {au['klatek']} klatek, p95 {au['p95_ms']} ms (budżet {a.budzet:g}), ręka {au['reka_proc']}%, "
                  f"vmax {round(au['vmax'])} px/s" + (f", skoki: {skoki}" if skoki else ", bez skoków"))
        for b in w.get("bledy_strony", []):
            print(f"  ! strona: {b[:300]}")
        print("✓ zasady rysownika i płynność OK" if w["ok"] else "✗ do poprawy (scena.js), potem sprawdz od nowa")
    return 0 if w["ok"] else 1


# ---------------------------------------------------------------- render i projekt edytora

def html_wideo(argv: list[str]) -> None:
    """html_wideo.py tym samym Pythonem; ostrzeżenie o pomiarze HTML pomijamy: ten silnik sprawdza `sprawdz`."""
    p = subprocess.run([sys.executable, str(HERE / "html_wideo.py"), *argv], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    for linia in p.stderr.splitlines():
        if not linia.startswith("⚠ pomiar animacji"):
            print(linia, file=sys.stderr)
    if p.returncode:
        raise SystemExit(f"✗ html_wideo.py {argv[0]}: kod {p.returncode}")
    print(p.stdout.strip(), file=sys.stderr)


def cmd_film(a, z_kodu: list[str]) -> int:
    silnik()
    nz.wymagaj_playwright(__file__, "JARVO_RYSOWANY_REEXEC")
    katalog = Path(a.katalog)
    strona_html = katalog / "index.html"
    if not strona_html.is_file():
        raise SystemExit(f"✗ brak {strona_html}")
    (os_,), bledy = w_przegladarce(strona_html, ("() => window.__os()", None))
    if bledy:
        raise SystemExit("✗ strona z błędami: " + "; ".join(dict.fromkeys(bledy))[:600])
    obraz = katalog / "obraz.mp4"
    print(f"▶ render {os_['w']}×{os_['h']}, {os_['dlugosc']:.1f} s ({os_['styl']})", file=sys.stderr, flush=True)
    html_wideo(["wideo", str(strona_html), "--preset", "jarvo", "--dlugosc", f"{os_['dlugosc']:.3f}", "--fps", str(a.fps),
                "-o", str(obraz), *(["--arkusz", a.arkusz] if a.arkusz else [])])
    glos_plik = katalog / "glos" / "voice.json"
    glos = json.loads(glos_plik.read_text(encoding="utf-8")) if glos_plik.is_file() and os_["zdania"] else None
    cmd = [sys.executable, str(HERE / "projekt.py"), "z-kodu", a.o, "--obraz", str(obraz)]
    tn = ciecia(os_, glos)
    if tn:
        wl.write_json(katalog / "ciecia.json", tn)
        cmd += ["--ciecia", str(katalog / "ciecia.json")]
    if glos:
        pcm, slowa = uloz_lektor(czytaj_pcm(Path(glos["lektor"])), glos, os_)
        zapisz_wav(pcm, katalog / "glos.wav")
        wl.write_json(katalog / "glos.slowa.json", slowa)
        cmd += ["--glos", str(katalog / "glos.wav"), "--slowa", str(katalog / "glos.slowa.json"), "--karaoke"]
    cmd += [*z_kodu, "--render"]
    print("▶ projekt edytora: " + " ".join(cmd[1:]), file=sys.stderr, flush=True)
    if subprocess.run(cmd).returncode:
        return 1
    wynik = {"film": a.o, "projekt": str(Path(a.o).with_suffix(".edycja.json")), "obraz": obraz.as_posix(),
             "dlugosc_s": round(os_["dlugosc"], 2), "ciecia": tn, "lektor": bool(glos),
             "czeka_na_reke_s": round(sum(z["czeka"] for z in os_["zdania"]), 2)}
    if a.arkusz:
        wynik["arkusz"] = a.arkusz
    print(json.dumps(wynik, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------- katalog stylów, wzór, nowy

def cmd_style(a) -> int:
    lista = style(silnik())
    if a.json:
        print(json.dumps(lista, ensure_ascii=False, indent=1))
        return 0
    for s in lista:
        print(f"{s['id']:<11} {s['nazwa']:<20} {s['opis']}")
    print("paper       Papier (domyślny)    pióro na kremowym papierze (bez filmu-wzoru)")
    return 0


def cmd_wzor(a) -> int:
    sj = silnik()
    nz.wymagaj_playwright(__file__, "JARVO_RYSOWANY_REEXEC")
    if a.styl not in {s["id"] for s in style(sj)}:
        raise SystemExit(f"✗ nieznany styl {a.styl!r} (lista: rysowany.py style)")
    katalog = wl.katalog_roboczy("jarvo-rysowany-wzor-")
    imp = ("import { STYLES } from '/_lib/silnikjava/examples/scenes/styles/index.js';\n"
           f"const zbuduj = (glos) => STYLES.find((s) => s.id === {json.dumps(a.styl)}).build(glos);")
    (katalog / "index.html").write_text(strona(imp, f"/_lib/silnikjava/examples/voice/{a.styl}/voice.json",
                                               f"wzór {a.styl}"), encoding="utf-8")
    arkusz = a.arkusz or f"out/wideo/wzor-{a.styl}.jpg"
    try:
        czasy = a.czasy
        if not czasy:
            (dl,), _ = w_przegladarce(katalog / "index.html", ("() => window.__DUR", None))
            czasy = ",".join(f"{dl * k / 9:.1f}" for k in range(1, 9))
        html_wideo(["klatki", str(katalog / "index.html"), "--preset", "jarvo", "--czasy", czasy, "--out",
                    str(katalog / "klatki"), "--arkusz", arkusz])
    finally:
        shutil.rmtree(katalog, ignore_errors=True)
    print(json.dumps({"styl": a.styl, "arkusz": arkusz, "scena_wzoru": f"$SILNIKJAVA/examples/scenes/styles/{a.styl}.js",
                      "tekst_lektora_wzoru": f"$SILNIKJAVA/examples/voice/{a.styl}/script.md"}, ensure_ascii=False))
    return 0


def cmd_nowy(a) -> int:
    sj = silnik()
    if a.styl != "paper" and a.styl not in {s["id"] for s in style(sj)}:
        raise SystemExit(f"✗ nieznany styl {a.styl!r} (lista: rysowany.py style)")
    katalog = Path(a.katalog)
    katalog.mkdir(parents=True, exist_ok=True)
    for plik in ("index.html", "scena.js"):
        if (katalog / plik).exists() and not a.nadpisz:
            raise SystemExit(f"✗ {katalog / plik} już jest (--nadpisz, gdy od nowa)")
    (katalog / "index.html").write_text(strona("import { zbuduj } from './scena.js';", None, a.tytul), encoding="utf-8")
    (katalog / "scena.js").write_text(scena(a.styl, a.pion, a.tytul), encoding="utf-8")
    print(json.dumps({"strona": (katalog / "index.html").as_posix(), "scena": (katalog / "scena.js").as_posix(),
                      "styl": a.styl, "format": "pion 1080x1920" if a.pion else "poziom 1920x1080",
                      "dalej": [f"rysowany.py glos {katalog.as_posix()} <os_czasu.json>",
                                f"rysowany.py sprawdz {katalog.as_posix()}",
                                f"rysowany.py film {katalog.as_posix()} -o out/wideo/<film>.mp4"]}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    z_kodu: list[str] = []
    if "--" in args:
        i = args.index("--")
        args, z_kodu = args[:i], args[i + 1:]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("style")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("wzor")
    s.add_argument("styl")
    s.add_argument("--czasy", help="sekundy po przecinku (domyślnie 8 chwil z całego filmu)")
    s.add_argument("--arkusz", help="JPG ze stopklatkami (domyślnie out/wideo/wzor-<styl>.jpg)")
    s = sub.add_parser("nowy")
    s.add_argument("katalog")
    s.add_argument("--styl", default="paper", help="id stylu (rysowany.py style), domyślnie paper")
    s.add_argument("--pion", action="store_true", help="rolka 9:16 (kadr 720×1280, render 1080×1920)")
    s.add_argument("--tytul", default="Jak to działa?")
    s.add_argument("--nadpisz", action="store_true")
    s = sub.add_parser("glos")
    s.add_argument("katalog")
    s.add_argument("zrodlo", help="os_czasu.json (film.py narracja) albo <lektor>.slowa.json (film.py lektor)")
    s.add_argument("--lektor", help="nagranie lektora (domyślnie z os_czasu.json)")
    s = sub.add_parser("sprawdz")
    s.add_argument("katalog")
    s.add_argument("--skok", type=int, default=SKOK_PX, help="skok ręki w px między klatkami (domyślnie 70)")
    s.add_argument("--budzet", type=float, default=BUDZET_MS, help="p95 czasu klatki w ms (domyślnie 33)")
    s.add_argument("--bez-audytu", action="store_true", help="tylko lint (sekundy zamiast pełnego przejścia klatek)")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("film")
    s.add_argument("katalog")
    s.add_argument("-o", required=True, help="film .mp4 (obok projekt <film>.edycja.json)")
    s.add_argument("--fps", type=int, default=30)
    s.add_argument("--arkusz", help="JPG z 11 klatkami filmu (do obejrzenia)")
    a = ap.parse_args(args)
    if a.cmd != "film" and z_kodu:
        raise SystemExit("opcje po `--` tylko przy `film` (idą do projekt.py z-kodu)")
    return {"style": cmd_style, "wzor": cmd_wzor, "nowy": cmd_nowy, "glos": cmd_glos, "sprawdz": cmd_sprawdz,
            "film": lambda x: cmd_film(x, z_kodu)}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
