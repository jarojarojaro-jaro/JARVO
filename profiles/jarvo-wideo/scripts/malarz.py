#!/usr/bin/env python3
"""Style malarskie: żywy obraz w jednym z 35 stylów (jaskinia, Van Gogh, tusz, Klimt, piksel…) z silnika kanwy
huashu-art-motion (MIT) pod polską nakładką, renderem i kontrolą Jarva.

    malarz.py style [--szukaj noc] [--json]                       # katalog 35 stylów z kart skillu style-malarskie
    malarz.py wzor 09_postimp [--czasy 0.3,0.6,0.9] [--arkusz out/wideo/wzor-09_postimp.jpg]   # stopklatki sceny-wzoru
    malarz.py galeria [--t 0.8] [-o out/wideo/galeria-stylow.jpg]  # jeden kadr każdego stylu na jednym arkuszu
    malarz.py nowy out/wideo/src/film --styl 09_postimp[,17_ink,…] [--osemki 8] [--bpm 128]   # szkielet filmu
    malarz.py wytnij surowe/*.png --out out/wideo/src/sprites [--soft 30 --hard 100 --pad 4]  # zielone tło → PNG + pozycja
    malarz.py potnij surowe/chod.png --out out/wideo/src/klatki/chod [--pick N] [--white]     # arkusz póz → klatki

`wzor` i `galeria` renderują sceny-wzory z ich filmów (`eras_gallery.js`, scena `16_2026` z filmu głównego, bo gra
liczy się z jego czasu) naszą stroną w kontrakcie jarvo, bez tabliczki roku. `nowy` robi stronę filmu w katalogu:
`index.html` (biblioteki z /_lib/huashu/, nakładka /_lib/jarvo/huashu_pl.js, silnik `engine.js`), `eras.js`
(tabela odcinków: ósemki przy BPM, przejście-podpis wchodzącego stylu) i `sceny/<id>.js` = kopia sceny-wzoru jako
punkt startu (zmieniasz scenę, technikę zostawiasz). Kadr zawsze 1920×1080: biblioteki i sceny mają ten rozmiar na
sztywno; pion 9:16 przez projekt edytora (`projekt.py kadr … --wypelnij --fx` albo `--rozmyte`).
Postaci autora silnika (`lib/rig_huashu.js`) strona nie ładuje. `wytnij` i `potnij` to port ich `key_green.py`
i `key_split.py` (warstwy i klatki postaci z AI na zielonym tle). Kod wyjścia: 0 ok, 1 błąd renderu, 2 złe wejście.
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import narzedzia as nz  # noqa: E402

SKILL = HERE.parent / "skills" / "wideo" / "style-malarskie"
KARTY = SKILL / "references" / "style"
W, H = 1920, 1080
# biblioteki stylów w kolejności ich index.html, bez rig_huashu.js (postać autora) i bibliotek gramatyk explainera
LIBY = ["fonts", "util", "paint", "brush", "render", "post", "rig", "kit"]
FILM_WZORU = {"16_2026": "eras.js"}             # domyślnie eras_gallery.js (35 stylów po 5 ósemek)
CZASY_WZORU = "0.3,0.6,0.9"
TYTUL = re.compile(r"^# (.+?) \(`(\d{2}_[a-z0-9_]+)`\)\s*$", re.M)
ID = re.compile(r"^\d{2}_[a-z0-9_]+$")


# ---------------------------------------------------------------- katalog

def _sekcja(tekst: str, naglowek: str) -> list[str]:
    """Punkty listy z sekcji `## <naglowek>` (wiersze kontynuacji doklejone)."""
    m = re.search(rf"^## {re.escape(naglowek)}\s*$(.*?)(?=^## |\Z)", tekst, re.M | re.S)
    punkty: list[str] = []
    for w in (m.group(1).splitlines() if m else []):
        if w.startswith("- "):
            punkty.append(w[2:].strip())
        elif w.startswith("  ") and punkty and w.strip():
            punkty[-1] += " " + w.strip()
    return punkty


def karta(plik: Path) -> dict | None:
    tekst = plik.read_text(encoding="utf-8")
    m = TYTUL.search(tekst)
    if not m:
        return None
    return {"id": m.group(2), "nazwa": m.group(1), "do_czego": _sekcja(tekst, "Do czego"),
            "nie_do": _sekcja(tekst, "Nie do"), "karta": f"references/style/{plik.name}"}


def katalog(katalog_kart: Path = KARTY) -> list[dict]:
    return [k for k in (karta(p) for p in sorted(katalog_kart.glob("*.md"))) if k]


def styl(id_: str, katalog_kart: Path = KARTY) -> dict:
    for k in katalog(katalog_kart):
        if k["id"] == id_:
            return k
    raise SystemExit(f"✗ nieznany styl {id_} (lista: malarz.py style)")


# ---------------------------------------------------------------- tabele odcinków silnika

ERA = re.compile(r"\{\s*id:\s*'(\d{2}_[a-z0-9_]+)'(.*)$", re.M)
PRZEJSCIE = re.compile(r"transition:\s*\{([^}]*)\}")
POLE = re.compile(r"(\w+):\s*('[^']*'|-?[\d.]+)")


def odcinki(js: str) -> list[dict]:
    """Odcinki z eras*.js silnika w kolejności filmu: id i przejście-podpis z tego samego wiersza."""
    out = []
    for m in ERA.finditer(js):
        tr = PRZEJSCIE.search(m.group(2))
        przejscie = None
        if tr:
            przejscie = {k: (v.strip("'") if v.startswith("'") else float(v)) for k, v in POLE.findall(tr.group(1))}
            przejscie = {k: (int(v) if isinstance(v, float) and v.is_integer() and k in ("cx", "cy") else v)
                         for k, v in przejscie.items()}
        out.append({"id": m.group(1), "przejscie": przejscie})
    return out


def silnik() -> Path:
    if not nz.huashu_gotowe():
        raise SystemExit("✗ brak silnika huashu-art-motion: python3 $HERMES_HOME/scripts/narzedzia.py instaluj huashu")
    return nz.HUASHU / "scripts" / "engine"


def biblioteki() -> str:
    return "\n".join(f'<script src="/_lib/huashu/lib/{n}.js"></script>' for n in LIBY)


# ---------------------------------------------------------------- strony

STRONA_WZORU = """<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><title>wzór stylu</title>
<!-- malarz.py: scena-wzór huashu-art-motion (MIT) bez tabliczki roku, czas lokalny odcinka -->
<style>html,body{{margin:0;background:#000;overflow:hidden}}canvas{{display:block}}#ui{{display:none}}</style></head>
<body><canvas id="c" width="1920" height="1080"></canvas>
<div id="ui"><input id="scrub" type="range"><span id="tt"></span><button id="play"></button></div>
{biblioteki}
<script src="/_lib/jarvo/huashu_pl.js"></script>
<script src="/_lib/huashu/{eras}"></script>
<script>for (const e of window.ERAS) delete e.counter; window.SCENE_DIR = '/_lib/huashu/scenes';</script>
<script src="/_lib/huashu/transitions.js"></script>
<script src="/_lib/huashu/scenes/index.js"></script>
<script src="/_lib/huashu/engine.js"></script>
<script>
// jeden styl: t = czas lokalny odcinka; galeria (STYL null): t = numer odcinka + czas lokalny / 10
const STYL = {styl};
window.__seek = (t) => {{
  if (STYL) return window.renderSolo(STYL, t, {{ counter: false }});
  const i = Math.floor(t + 1e-6);
  return window.renderSolo(window.ERAS[i].id, (t - i) * 10, {{ counter: false }});
}};
</script>
</body></html>
"""

STRONA_FILMU = """<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><title>{tytul}</title>
<!-- malarz.py nowy: film w stylach {style} na silniku huashu-art-motion (MIT); odcinki w eras.js, sceny w sceny/ -->
<style>
html,body{{margin:0;background:#111;overflow:hidden}}
canvas{{display:block;width:100vw;height:auto;max-width:1920px}}
#ui{{position:fixed;left:8px;bottom:8px;color:#ddd;font:12px monospace}}
body.render #ui{{display:none}}
</style></head>
<body>
<canvas id="c" width="1920" height="1080"></canvas>
<div id="ui"><input id="scrub" type="range" min="0" max="60" step="0.0166667" value="0" style="width:600px"> <span id="tt"></span> <button id="play">play</button></div>
{biblioteki}
<script src="/_lib/jarvo/huashu_pl.js"></script>
<script src="eras.js"></script>
<script>window.SCENE_DIR = 'sceny';</script>
<script src="/_lib/huashu/transitions.js"></script>
<script src="/_lib/huashu/scenes/index.js"></script>
<script src="/_lib/huashu/engine.js"></script>
</body></html>
"""

ERAS_FILMU = """// Tabela odcinków filmu (malarz.py nowy). Kolejność = kolejność w filmie, id = plik sceny sceny/<id>.js.
// Długość: eighths (ósemki przy window.BPM) albo dur (sekundy, np. pod lektora); film trwa tyle, ile suma.
// transition: przejście-podpis WCHODZĄCEGO stylu (karta stylu, przejscia.md); cx, cy ustaw na swój przedmiot w kadrze.
// Tabliczka (opcjonalnie): counter: {{ mode: 'tag', name: 'Van Gogh', year: 1889, font: 'Poppins-800', size: 96,
//   color: '#fff' }} albo licznik roku (engine.js: U.yearCounter); krój z polskimi znakami (nakładka huashu_pl.js).
window.BPM = {bpm};
window.PUNCH = {punch};          // uderzenie kamery na wejściu odcinka (0.03); explainer, prezentacja, dane: 0
window.ERAS = [
{odcinki}
];
"""

NAGLOWEK_SCENY = """// Punkt startu: scena-wzór {id} z huashu-art-motion (MIT, © alchaincyf, commit {rev}; licencja: $HUASHU/LICENSE).
// Zmieniasz scenę (szkielet, przedmioty, postać, kolory marki), technikę stylu zostawiasz: karta {karta}
// w skillu style-malarskie. Kadr 1920×1080, draw(c, lt, t): lt = czas odcinka, t = czas filmu.
"""
UWAGA_2026 = ("// Uwaga: ta scena liczy grę z globalnej klatki filmu-wzoru (FR = t * 60, klatki 657–911 = 10,95–15,18 s);\n"
              "// w swoim filmie przesuń ją na czas odcinka, np. const FR = t => (t - T0) * 60 + 657.\n"
              "// Podpis w rogu (klatki 842–870): window.SIGNATURE = 'marka' w eras.js albo usuń signature();\n"
              "// bez tego scena pisze nazwę modelu z ich filmu.\n")


def strona_wzoru(katalog_strony: Path, id_: str | None, eras: str) -> Path:
    plik = katalog_strony / "wzor.html"
    plik.write_text(STRONA_WZORU.format(biblioteki=biblioteki(), eras=eras,
                                        styl=json.dumps(id_) if id_ else "null"), encoding="utf-8")
    return plik


def html_wideo(*args: str) -> int:
    return subprocess.run([sys.executable, str(HERE / "html_wideo.py"), *args]).returncode


def html_wideo_json(*args: str) -> dict:
    r = subprocess.run([sys.executable, str(HERE / "html_wideo.py"), *args], capture_output=True, text=True)
    if r.stderr:
        print(r.stderr.rstrip(), file=sys.stderr)
    if r.returncode:
        raise SystemExit(f"✗ html_wideo.py: kod {r.returncode}")
    return json.loads(r.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------- polecenia

def cmd_style(a) -> int:
    lista = katalog()
    if a.szukaj:
        q = a.szukaj.lower()
        lista = [k for k in lista if q in (k["id"] + " " + k["nazwa"] + " " + " ".join(k["do_czego"])).lower()]
    if a.json:
        print(json.dumps(lista, ensure_ascii=False, indent=1))
        return 0
    for k in lista:
        do = k["do_czego"][0] if k["do_czego"] else ""
        print(f"{k['id']:<18} {k['nazwa']}\n{'':<18} {do[:150]}")
    print(f"\n{len(lista)} z {len(katalog())} stylów · karta: skills/wideo/style-malarskie/references/style/<id>.md")
    return 0


def cmd_wzor(a) -> int:
    styl(a.id)
    eng = silnik()
    eras = FILM_WZORU.get(a.id, "eras_gallery.js")
    if a.id not in [o["id"] for o in odcinki((eng / eras).read_text(encoding="utf-8"))]:
        raise SystemExit(f"✗ {a.id} nie ma w {eras} silnika")
    arkusz = a.arkusz or f"out/wideo/wzor-{a.id}.jpg"
    with tempfile.TemporaryDirectory(prefix="jarvo-malarz-") as tmp:
        strona = strona_wzoru(Path(tmp), a.id, eras)
        return html_wideo("klatki", str(strona), "--preset", "jarvo", "--czasy", a.czasy,
                          "--out", a.out or f"out/wideo/klatki-wzor-{a.id}", "--arkusz", arkusz)


def wymagaj_obrazu() -> None:
    """numpy i Pillow są w Pythonie narzędzi (`narzedzia.py instaluj html`): bez nich skrypt raz rusza tamtym."""
    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
        return
    except ImportError:
        pass
    venv_py = Path(nz.py())
    if venv_py.exists() and Path(sys.prefix).resolve() != nz.VENV.resolve() and not os.environ.get("JARVO_MALARZ_REEXEC"):
        os.environ["JARVO_MALARZ_REEXEC"] = "1"
        os.execv(str(venv_py), [str(venv_py), str(Path(__file__).resolve()), *sys.argv[1:]])
    raise SystemExit("✗ brak numpy/Pillow: python3 $HERMES_HOME/scripts/narzedzia.py instaluj html")


def czcionka(rozmiar: int):
    from PIL import ImageFont
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf",
              "/Library/Fonts/Arial Unicode.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, rozmiar)
    return ImageFont.load_default()


def arkusz_galerii(klatki: list[Path], podpisy: list[str], out: Path, kolumny: int = 5, szer: int = 384) -> Path:
    from PIL import Image, ImageDraw
    wys, pas = szer * H // W, 26
    wiersze = -(-len(klatki) // kolumny)
    plotno = Image.new("RGB", (szer * kolumny, (wys + pas) * wiersze), "#1c1c1c")
    rys, font = ImageDraw.Draw(plotno), czcionka(15)
    for i, (k, podpis) in enumerate(zip(klatki, podpisy)):
        x, y = (i % kolumny) * szer, (i // kolumny) * (wys + pas)
        plotno.paste(Image.open(k).convert("RGB").resize((szer, wys)), (x, y + pas))
        rys.text((x + 6, y + 5), podpis if len(podpis) <= 46 else podpis[:45] + "…", fill="#ffffff", font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    plotno.save(out, quality=86)
    return out


def cmd_galeria(a) -> int:
    wymagaj_obrazu()
    eng = silnik()
    if not 0 <= a.t < 1.1:
        raise SystemExit("✗ --t to czas lokalny odcinka galerii: 0–1,1 s")
    ids = [o["id"] for o in odcinki((eng / "eras_gallery.js").read_text(encoding="utf-8"))]
    nazwy = {k["id"]: k["nazwa"] for k in katalog()}
    czasy = [i + a.t / 10 for i in range(len(ids))]
    out = Path(a.o)
    katalog_klatek = out.parent / f"klatki-{out.stem}"
    with tempfile.TemporaryDirectory(prefix="jarvo-malarz-") as tmp:
        strona = strona_wzoru(Path(tmp), None, "eras_gallery.js")
        r = html_wideo_json("klatki", str(strona), "--preset", "jarvo", "--czasy", ",".join(f"{t:.3f}" for t in czasy),
                            "--out", str(katalog_klatek))
    klatki = [Path(p) for p in r["klatki"]]
    podpisy = [f"{i} · {nazwy.get(i, '?')}" for i in ids]
    arkusz_galerii(klatki, podpisy, out)
    (out.with_suffix(".json")).write_text(json.dumps([{"id": i, "nazwa": nazwy.get(i), "klatka": str(k)}
                                                       for i, k in zip(ids, klatki)], ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    print(json.dumps({"arkusz": str(out), "stylow": len(ids), "klatki": str(katalog_klatek)}, ensure_ascii=False))
    return 0


def cmd_nowy(a) -> int:
    ids = [s.strip() for s in a.styl.split(",") if s.strip()]
    if not ids or len(set(ids)) != len(ids):
        raise SystemExit("✗ --styl: lista różnych id stylów (ten sam styl drugi raz: skopiuj scenę pod nowym id)")
    karty = [styl(i) for i in ids]
    eng = silnik()
    podpisy = {o["id"]: o["przejscie"] for o in odcinki((eng / "eras_gallery.js").read_text(encoding="utf-8"))}
    kat = Path(a.katalog)
    pliki = [kat / "index.html", kat / "eras.js", *[kat / "sceny" / f"{i}.js" for i in ids]]
    zajete = [str(p) for p in pliki if p.exists()]
    if zajete and not a.nadpisz:
        raise SystemExit(f"✗ już jest: {', '.join(zajete)} (--nadpisz)")
    (kat / "sceny").mkdir(parents=True, exist_ok=True)
    wiersze = []
    for n, i in enumerate(ids):
        e = {"id": i, "eighths": a.osemki}
        if n and podpisy.get(i):
            e["transition"] = podpisy[i]
        wiersze.append("  " + json.dumps(e, ensure_ascii=False).replace('"', "'") + ",")
    (kat / "eras.js").write_text(ERAS_FILMU.format(bpm=f"{a.bpm:g}", punch=0.03 if len(ids) > 1 else 0,
                                                   odcinki="\n".join(wiersze)), encoding="utf-8")
    (kat / "index.html").write_text(STRONA_FILMU.format(tytul=kat.name, style=", ".join(ids), biblioteki=biblioteki()),
                                    encoding="utf-8")
    for i, k in zip(ids, karty):
        kod = (eng / "scenes" / f"{i}.js").read_text(encoding="utf-8")
        glowa = NAGLOWEK_SCENY.format(id=i, rev=nz.HUASHU_REV[:7], karta=k["karta"]) + (UWAGA_2026 if i == "16_2026" else "")
        (kat / "sceny" / f"{i}.js").write_text(glowa + kod, encoding="utf-8")
    dlugosc = len(ids) * a.osemki * 30 / a.bpm
    print(json.dumps({"strona": str(kat / "index.html"), "odcinki": ids, "dlugosc": round(dlugosc, 3),
                      "dalej": [f"python3 $HERMES_HOME/scripts/html_wideo.py klatki {kat}/index.html --preset jarvo "
                                f"--czasy 0.5,1.5 --arkusz out/wideo/klatki-{kat.name}.jpg",
                                f"python3 $HERMES_HOME/scripts/html_wideo.py wideo {kat}/index.html --preset jarvo "
                                f"--dlugosc {dlugosc:g} -o out/wideo/{kat.name}.mp4"]}, ensure_ascii=False, indent=1))
    return 0


def klucz_zieleni(rgb, soft: float, hard: float):
    """Zielone tło → (rgba, alfa): przezroczystość z przewagi zieleni, zielona poświata na brzegach zbita do max(r, b)."""
    import numpy as np
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    nadmiar = g - np.maximum(r, b)
    alfa = 1 - np.clip((nadmiar - soft) / max(1e-6, hard - soft), 0, 1)
    g2 = np.where(nadmiar > 0, np.minimum(g, np.maximum(r, b) + 0.25 * np.clip(nadmiar, 0, 30)), g)
    return np.dstack([r, g2, b, alfa * 255]).clip(0, 255).astype(np.uint8), alfa


def wytnij(pliki: list[Path], out: Path, soft: float = 30, hard: float = 100, pad: int = 4) -> dict:
    """Warstwy z AI na zielonym tle (droga B): przycięte RGBA + lewy górny róg w kadrze (sprites.json), żeby wkleić
    w to samo miejsce, w którym model namalował."""
    import numpy as np
    from PIL import Image
    out.mkdir(parents=True, exist_ok=True)
    meta_p = out / "sprites.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    for f in pliki:
        rgb = np.asarray(Image.open(f).convert("RGB")).astype(np.float32)
        rgba, alfa = klucz_zieleni(rgb, soft, hard)
        ys, xs = np.where(alfa > 0.05)
        if not len(xs):
            print(f"⚠ {f}: same zielone tło, pomijam", file=sys.stderr)
            continue
        x0, y0 = max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad)
        x1, y1 = min(rgb.shape[1], int(xs.max()) + pad + 1), min(rgb.shape[0], int(ys.max()) + pad + 1)
        Image.fromarray(rgba[y0:y1, x0:x1]).save(out / f"{f.stem}.png")
        meta[f.stem] = {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "kadr": [rgb.shape[1], rgb.shape[0]]}
    meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def potnij(plik: Path, przedrostek: Path, pick: int | None = None, biale: bool = False) -> list[dict]:
    """Arkusz póz (zielone tło albo biały papier z `biale`) → osobne PNG po pustych kolumnach: przerwy węższe niż
    12 px łączą pozy, kawałki węższe niż 40 px odpadają."""
    import numpy as np
    from PIL import Image
    rgb = np.asarray(Image.open(plik).convert("RGB")).astype(np.float32)
    if biale:
        alfa = 1 - np.clip((rgb.min(2) - 225) / 25, 0, 1)
        alfa = np.maximum(alfa, rgb.max(2) - rgb.min(2) > 40)
        obraz, maska = rgb.clip(0, 255).astype(np.uint8), alfa > 0.1
    else:
        obraz, alfa = klucz_zieleni(rgb, 30, 100)
        maska = alfa > 0.05
    kol, odcinki_, x, n = maska.any(0), [], 0, maska.shape[1]
    while x < n:
        if kol[x]:
            x0 = x
            while x < n and kol[x:x + 12].any():
                x += 1
            if x - x0 > 40:
                odcinki_.append((x0, x))
        x += 1
    przedrostek.parent.mkdir(parents=True, exist_ok=True)
    wynik = []
    for k, (x0, x1) in enumerate(odcinki_):
        if pick is not None and k != pick:
            continue
        ys = np.where(maska[:, x0:x1].any(1))[0]
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        nazwa = f"{przedrostek.name}.png" if pick is not None else f"{przedrostek.name}_{k}.png"
        Image.fromarray(obraz[y0:y1, x0:x1]).save(przedrostek.parent / nazwa)
        wynik.append({"plik": str(przedrostek.parent / nazwa), "x0": x0, "x1": x1, "y0": y0, "y1": y1})
    return wynik


def cmd_wytnij(a) -> int:
    wymagaj_obrazu()
    brak = [p for p in a.pliki if not Path(p).exists()]
    if brak:
        raise SystemExit(f"✗ brak plików: {', '.join(brak)}")
    meta = wytnij([Path(p) for p in a.pliki], Path(a.out), a.soft, a.hard, a.pad)
    print(json.dumps({"sprites": str(Path(a.out) / "sprites.json"), "warstwy": meta}, ensure_ascii=False, indent=1))
    return 0


def cmd_potnij(a) -> int:
    wymagaj_obrazu()
    if not Path(a.plik).exists():
        raise SystemExit(f"✗ brak pliku {a.plik}")
    wynik = potnij(Path(a.plik), Path(a.out), a.pick, a.white)
    print(json.dumps({"klatki": wynik}, ensure_ascii=False, indent=1))
    return 0 if wynik else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("style", help="35 stylów z kart skillu (id, nazwa, do czego)")
    s.add_argument("--szukaj", help="fragment nazwy albo zastosowania (np. noc, luksus, gra)")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("wzor", help="stopklatki sceny-wzoru stylu (czas lokalny odcinka)")
    s.add_argument("id")
    s.add_argument("--czasy", default=CZASY_WZORU, help=f"s od początku odcinka (domyślnie {CZASY_WZORU})")
    s.add_argument("--arkusz", help="JPG (domyślnie out/wideo/wzor-<id>.jpg)")
    s.add_argument("--out", help="katalog klatek (domyślnie out/wideo/klatki-wzor-<id>)")
    s = sub.add_parser("galeria", help="jeden kadr każdego z 35 stylów na arkuszu z podpisami")
    s.add_argument("--t", type=float, default=0.8, help="czas lokalny odcinka galerii (s, domyślnie 0,8)")
    s.add_argument("-o", default="out/wideo/galeria-stylow.jpg")
    s = sub.add_parser("nowy", help="szkielet filmu: index.html, eras.js, sceny/<id>.js")
    s.add_argument("katalog")
    s.add_argument("--styl", required=True, help="id stylów po przecinku, w kolejności filmu")
    s.add_argument("--osemki", type=int, default=8, help="ósemek na odcinek (8 przy 128 BPM = 1,875 s)")
    s.add_argument("--bpm", type=float, default=128)
    s.add_argument("--nadpisz", action="store_true")
    s = sub.add_parser("wytnij", help="zielone tło → przycięte PNG z pozycją w kadrze (sprites.json)")
    s.add_argument("pliki", nargs="+")
    s.add_argument("-o", "--out", required=True)
    s.add_argument("--soft", type=float, default=30)
    s.add_argument("--hard", type=float, default=100)
    s.add_argument("--pad", type=int, default=4)
    s = sub.add_parser("potnij", help="arkusz póz na zielonym (albo białym) tle → osobne klatki")
    s.add_argument("plik")
    s.add_argument("-o", "--out", required=True, help="przedrostek plików (…/chod → chod_0.png, chod_1.png)")
    s.add_argument("--pick", type=int, help="tylko ta poza (od 0), zapis jako <przedrostek>.png")
    s.add_argument("--white", action="store_true", help="biały papier: bez wycinania, samo przycięcie")
    a = ap.parse_args(argv)
    if a.cmd == "wzor" and not ID.match(a.id):
        raise SystemExit(f"✗ id stylu wygląda jak 09_postimp, nie {a.id}")
    if a.cmd == "nowy" and (a.osemki < 1 or a.bpm <= 0):
        raise SystemExit("✗ --osemki ≥ 1, --bpm > 0")
    return {"style": cmd_style, "wzor": cmd_wzor, "galeria": cmd_galeria, "nowy": cmd_nowy,
            "wytnij": cmd_wytnij, "potnij": cmd_potnij}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
