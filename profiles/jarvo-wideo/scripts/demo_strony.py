#!/usr/bin/env python3
"""Demo strony: nagranie przejścia po stronie z widocznym kursorem, tempem dla człowieka i napisami kroków.

Metoda za affaan-m/ECC `ui-demo` (MIT): rozpoznanie → próba → nagranie, nigdy od razu nagranie.

    demo_strony.py rozpoznaj <url> [<url>…] [-o elementy.json]   # co jest na stronie: pola, przyciski, linki
    demo_strony.py proba <demo.json>                              # każdy krok bez nagrywania; kod 1 = zły selektor
    demo_strony.py nagraj <demo.json> -o out/wideo/demo/demo.mp4 [--bez-paska]

Scenariusz `demo.json` (czasy w sekundach, pauzy mnożone przez `tempo`):
    {"url": "http://127.0.0.1:4321/", "rozmiar": [1280, 720], "skala": 1, "tempo": 1.0, "domeny": ["nova.pl"],
     "kroki": [
       {"napis": "Krok 1: strona główna"},
       {"najedz": "section .card", "max": 4},
       {"klik": "text=Cennik", "etykieta": "menu Cennik"},
       {"wpisz": "#email", "tekst": "anna@example.com", "etykieta": "pole e-mail"},
       {"wpisz": "#haslo", "tekst_env": "DEMO_HASLO", "etykieta": "hasło konta testowego"},
       {"wybierz": "select#plan", "opcja": "Firma"},
       {"przewin": 600}, {"przewin": "#kontakt"},
       {"idz": "/blog"}, {"czekaj": 2}, {"napis": ""}]}

Adres startowy to nasz podgląd (localhost) albo strona użytkownika; przejście na domenę spoza `url` i `domeny`
kończy się błędem. Hasło tylko ze zmiennej środowiskowej (`tekst_env`), nigdy w scenariuszu.
`rozmiar` to rozmiar filmu; `skala` > 1 nagrywa mniejszą stronę ostrzej (pion Reels: [1080, 1920] + skala 1.5 =
strona 720×1280 w układzie telefonu). Wynik nagrania: MP4 (H.264, 30 kl./s), `<film>.srt` z napisami kroków (do `projekt.py napisy --srt`) i
`<film>.kroki.json` (oś: kiedy który krok). `--bez-paska`: napisy tylko w SRT (edytowalne w HQ), nie w obrazie.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import narzedzia as nz  # noqa: E402

TYPY = ("napis", "idz", "klik", "wpisz", "wybierz", "przewin", "najedz", "czekaj")
PAUZY = {"start": 2.0, "idz": 3.0, "klik": 2.0, "wpisz": 1.0, "wybierz": 1.5, "przewin": 1.5, "najedz": 0.6,
         "napis": 1.2, "koniec": 3.0}
PISANIE_MS = 35
LOKALNE = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

KURSOR_JS = """() => {
  if (document.getElementById('jarvo-kursor')) return;
  const c = document.createElement('div');
  c.id = 'jarvo-kursor';
  c.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M5 3L19 12L12 13L9 20L5 3Z" fill="white" stroke="black" stroke-width="1.5" stroke-linejoin="round"/></svg>';
  c.style.cssText = 'position:fixed;z-index:2147483647;pointer-events:none;width:26px;height:26px;left:-40px;top:-40px;'
    + 'transition:left .08s linear,top .08s linear;filter:drop-shadow(1px 2px 2px rgba(0,0,0,.35))';
  document.documentElement.appendChild(c);
  const p = window.__jarvoKursor;
  if (p) { c.style.left = p[0] + 'px'; c.style.top = p[1] + 'px'; }
  document.addEventListener('mousemove', e => {
    c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; window.__jarvoKursor = [e.clientX, e.clientY];
  }, true);
}"""
PASEK_JS = """(tekst) => {
  let b = document.getElementById('jarvo-napis');
  if (!b) {
    b = document.createElement('div');
    b.id = 'jarvo-napis';
    b.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:2147483646;pointer-events:none;text-align:center;'
      + 'padding:14px 28px;background:rgba(10,10,12,.78);color:#fff;font:600 20px/1.35 system-ui,-apple-system,"Segoe UI",sans-serif;'
      + 'letter-spacing:.2px;transition:opacity .3s;opacity:0';
    document.documentElement.appendChild(b);
  }
  if (tekst) { b.textContent = tekst; b.style.opacity = '1'; } else { b.style.opacity = '0'; }
}"""
# okno modalne (<dialog>, popover) leży w „górnej warstwie” ponad każdym z-index: nakładki przenosimy do niego
WARSTWA_JS = """() => {
  let top = null;
  try { top = [...document.querySelectorAll('dialog[open], :popover-open')].pop() || null; }
  catch (e) { top = [...document.querySelectorAll('dialog[open]')].pop() || null; }
  const host = top || document.documentElement;
  for (const id of ['jarvo-napis', 'jarvo-kursor']) {
    const el = document.getElementById(id);
    if (el && el.parentElement !== host) host.appendChild(el);
  }
}"""
ELEMENTY_JS = """() => {
  const out = [];
  document.querySelectorAll('a[href], button, input, select, textarea, [role=button], [contenteditable=true]').forEach(el => {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || getComputedStyle(el).visibility === 'hidden') return;
    const tekst = (el.innerText || el.value || '').trim().replace(/\\s+/g, ' ').slice(0, 50);
    let sel = el.id ? '#' + el.id : el.name ? `${el.tagName.toLowerCase()}[name="${el.name}"]` : '';
    if (!sel && tekst && ['A', 'BUTTON'].includes(el.tagName)) sel = `text=${tekst}`;
    out.push({tag: el.tagName.toLowerCase(), typ: el.type || '', nazwa: el.name || '', placeholder: el.placeholder || '',
              tekst, rola: el.getAttribute('role') || '', href: el.getAttribute('href') || '', selektor: sel,
              opcje: el.tagName === 'SELECT' ? Array.from(el.options).map(o => o.text.trim()).slice(0, 12) : undefined});
  });
  return out;
}"""


# ------------------------------------------------------------------ scenariusz (bez przeglądarki)

def wczytaj(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def typ_kroku(k: dict) -> str | None:
    return next((t for t in TYPY if t in k), None)


def host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def dozwolony(url: str, sc: dict) -> bool:
    h = host(url)
    if not h:
        return True                                     # ścieżka względna: zostajemy na stronie
    dozw = {host(sc["url"]), *(d.lower().lstrip(".") for d in sc.get("domeny") or [])}
    return h in LOKALNE or any(h == d or h.endswith("." + d) for d in dozw if d)


def sprawdz_scenariusz(sc: dict, env: dict | None = None) -> list[str]:
    env = os.environ if env is None else env
    bledy = []
    if not str(sc.get("url") or "").startswith(("http://", "https://")):
        bledy.append("url: adres http(s) strony startowej")
    rozmiar = sc.get("rozmiar", [1280, 720])
    if not (isinstance(rozmiar, list) and len(rozmiar) == 2 and all(isinstance(x, int) and 320 <= x <= 3840 for x in rozmiar)):
        bledy.append("rozmiar: [szerokość, wysokość] w pikselach (320–3840)")
    if not 0.25 <= float(sc.get("tempo", 1.0)) <= 3:
        bledy.append("tempo: 0,25–3 (mnożnik pauz)")
    if not 1 <= float(sc.get("skala", 1)) <= 3:
        bledy.append("skala: 1–3 (rozmiar filmu / rozmiar strony; 1,5 = pion 1080×1920 z układem telefonu)")
    kroki = sc.get("kroki") or []
    if not kroki:
        bledy.append("kroki: co najmniej jeden krok")
    for n, k in enumerate(kroki, 1):
        t = typ_kroku(k) if isinstance(k, dict) else None
        if not t:
            bledy.append(f"krok {n}: nieznany typ (dozwolone: {', '.join(TYPY)})")
            continue
        if t in ("klik", "wpisz", "wybierz", "najedz") and not str(k[t]).strip():
            bledy.append(f"krok {n}: {t} wymaga selektora")
        if t == "wpisz":
            if "tekst" in k and "tekst_env" in k or not ("tekst" in k or "tekst_env" in k):
                bledy.append(f"krok {n}: wpisz wymaga dokładnie jednego z: tekst, tekst_env")
            elif "tekst_env" in k and not env.get(k["tekst_env"]):
                bledy.append(f"krok {n}: brak zmiennej środowiskowej {k['tekst_env']}")
            if "tekst" in k and any(s in str(k[t]).lower() for s in ("pass", "hasl", "haslo", "password")):
                bledy.append(f"krok {n}: hasło tylko przez tekst_env (zmienna środowiskowa), nie w scenariuszu")
        if t == "wybierz" and not k.get("opcja"):
            bledy.append(f"krok {n}: wybierz wymaga pola opcja (tekst opcji)")
        if t == "idz" and not dozwolony(urljoin(sc.get("url", ""), str(k["idz"])), sc):
            bledy.append(f"krok {n}: {k['idz']} jest poza stroną i listą domeny (nagrywamy tylko nasz podgląd albo stronę użytkownika)")
        if t in ("czekaj",) and not 0 < float(k[t]) <= 30:
            bledy.append(f"krok {n}: czekaj 0–30 s")
    if sc.get("url") and not dozwolony(sc["url"], sc):
        bledy.append("url poza listą domen")
    return bledy


def pauza(k: dict, typ: str, tempo: float) -> float:
    return float(k.get("pauza", PAUZY.get(typ, 1.0))) * tempo


def etykieta(k: dict) -> str:
    t = typ_kroku(k) or "?"
    return str(k.get("etykieta") or f"{t} {k.get(t)}")


def srt(os_napisow: list[tuple[float, float, str]]) -> str:
    def ts(s: float) -> str:
        ms = int(round(max(0.0, s) * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    return "".join(f"{i}\n{ts(a)} --> {ts(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(os_napisow, 1) if t and b > a)


def os_z_krokow(zdarzenia: list[dict], koniec: float) -> list[tuple[float, float, str]]:
    """Zdarzenia `napis` (czas, tekst) → przedziały napisów do SRT; pusty napis kończy poprzedni."""
    out, akt = [], None
    for z in zdarzenia:
        if z["typ"] != "napis":
            continue
        if akt:
            out.append((akt[0], z["t"], akt[1]))
        akt = (z["t"], z["tekst"]) if z["tekst"] else None
    if akt:
        out.append((akt[0], koniec, akt[1]))
    return out


# ------------------------------------------------------------------ przeglądarka

def ensure_playwright() -> None:
    nz.wymagaj_playwright(__file__, "JARVO_DEMO_REEXEC")


def przegladarka(p):
    exe = nz.headless_shell()
    return p.chromium.launch(**({"executable_path": exe} if exe else {}))


def widoczne(page) -> list[dict]:
    return page.evaluate(ELEMENTY_JS)


class Rezyser:
    """Wykonuje kroki scenariusza; w próbie tylko sprawdza selektory, w nagraniu rusza kursorem i czeka."""

    def __init__(self, page, sc: dict, nagranie: bool, pasek: bool, t0: float):
        self.page, self.sc, self.nagranie, self.pasek, self.t0 = page, sc, nagranie, pasek, t0
        self.tempo = float(sc.get("tempo", 1.0))
        self.zdarzenia: list[dict] = []
        self.bledy: list[str] = []

    def t(self) -> float:
        return time.monotonic() - self.t0

    def czekaj(self, s: float) -> None:
        if self.nagranie and s > 0:
            self.page.wait_for_timeout(int(min(s, 0.3) * 1000))
            self.page.evaluate(WARSTWA_JS)             # po akcji mogło się otworzyć okno modalne
            if s > 0.3:
                self.page.wait_for_timeout(int((s - 0.3) * 1000))

    def nakladki(self) -> None:
        if self.nagranie:
            self.page.evaluate(KURSOR_JS)
            if self.pasek:
                self.page.evaluate(PASEK_JS, self._napis)

    _napis = ""

    def idz(self, url: str) -> None:
        cel = urljoin(self.sc["url"], url)
        if not dozwolony(cel, self.sc):
            raise SystemExit(f"przejście poza stronę: {cel}")
        self.page.goto(cel, wait_until="load")
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:  # noqa: BLE001  (strona z ciągłym ruchem sieci: wystarczy load)
            pass
        self.nakladki()

    def element(self, sel: str, n: int, opis: str):
        loc = self.page.locator(sel).first
        try:
            loc.wait_for(state="visible", timeout=5000)
            return loc
        except Exception:  # noqa: BLE001
            lista = "\n    ".join(f"{e['tag']} {e['selektor'] or ''} „{e['tekst']}”" for e in widoczne(self.page)[:40])
            self.bledy.append(f"krok {n} ({opis}): nie widać elementu {sel!r} na {self.page.url}\n  widoczne:\n    {lista}")
            return None

    def ruch(self, loc) -> None:
        if not self.nagranie:
            return
        loc.scroll_into_view_if_needed()
        self.page.wait_for_timeout(250)
        box = loc.bounding_box()
        if box:
            self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=14)
            self.page.wait_for_timeout(int(350 * self.tempo))

    def krok(self, n: int, k: dict) -> None:
        typ = typ_kroku(k)
        opis = etykieta(k)
        self.zdarzenia.append({"t": round(self.t(), 3), "typ": typ, "krok": n, "opis": opis,
                               **({"tekst": k["napis"]} if typ == "napis" else {})})
        if typ == "napis":
            self._napis = k["napis"]
            if self.nagranie and self.pasek:
                self.page.evaluate(PASEK_JS, k["napis"])
        elif typ == "idz":
            self.idz(str(k["idz"]))
        elif typ == "czekaj":
            self.czekaj(float(k["czekaj"]))
            return
        elif typ == "przewin":
            cel = k["przewin"]
            if isinstance(cel, (int, float)):               # kółko myszy: działa też w kontenerze z przewijaniem
                w, h = self.sc.get("rozmiar", [1280, 720])
                sk = float(self.sc.get("skala", 1))
                if not self.page.evaluate("() => window.__jarvoKursor"):
                    self.page.mouse.move(w / sk / 2, h / sk / 2)
                for _ in range(12):
                    self.page.mouse.wheel(0, cel / 12)
                    self.page.wait_for_timeout(45 if self.nagranie else 5)
            elif (loc := self.element(str(cel), n, opis)) is not None:
                loc.evaluate("el => el.scrollIntoView({behavior: 'smooth', block: 'center'})")
        elif typ == "najedz":
            for loc in self.page.locator(str(k["najedz"])).all()[: int(k.get("max", 5))]:
                if loc.is_visible():
                    self.ruch(loc)
                    self.czekaj(pauza(k, typ, self.tempo))
            if not self.page.locator(str(k["najedz"])).count():
                self.element(str(k["najedz"]), n, opis)
            return
        else:
            loc = self.element(str(k[typ]), n, opis)
            if loc is None:
                return
            self.ruch(loc)                           # w próbie akcje też się wykonują (kolejne kroki są na tej stronie)
            if typ == "klik":
                adres = self.page.url
                loc.click()
                self.page.wait_for_load_state("load")
                if self.page.url != adres:
                    if not dozwolony(self.page.url, self.sc):
                        raise SystemExit(f"klik wyprowadził poza stronę: {self.page.url}")
                    self.nakladki()
            elif typ == "wpisz":
                tekst = os.environ[k["tekst_env"]] if "tekst_env" in k else str(k["tekst"])
                loc.click()
                loc.fill("")
                if self.nagranie:
                    loc.press_sequentially(tekst, delay=int(PISANIE_MS * self.tempo))
                else:
                    loc.fill(tekst)
            elif typ == "wybierz":
                if str(k["opcja"]) not in [o.strip() for o in loc.locator("option").all_inner_texts()]:
                    self.bledy.append(f"krok {n} ({opis}): brak opcji „{k['opcja']}”")
                    return
                loc.select_option(label=str(k["opcja"]))
        self.czekaj(pauza(k, typ, self.tempo))


def graj(sc: dict, nagranie: bool, katalog: Path | None = None, pasek: bool = True):
    from playwright.sync_api import sync_playwright

    w, h = sc.get("rozmiar", [1280, 720])
    sk = float(sc.get("skala", 1))                     # skala 1,5: strona 720×1280 (układ telefonu) → film 1080×1920
    with sync_playwright() as p:
        br = przegladarka(p)
        vw, vh = round(w / sk), round(h / sk)
        opcje = {"viewport": {"width": vw, "height": vh}, "device_scale_factor": 1}
        if nagranie:                                   # nagranie w pikselach strony; do `rozmiar` skaluje ffmpeg
            opcje["record_video_dir"] = str(katalog)
            opcje["record_video_size"] = {"width": vw, "height": vh}
        ctx = br.new_context(**opcje)
        page = ctx.new_page()
        page.set_default_timeout(15000)
        t_ctx = time.monotonic()
        r = Rezyser(page, sc, nagranie, pasek, t_ctx)
        r.idz(sc["url"])
        start = time.monotonic() - t_ctx               # tyle nagrania to biała strona przed załadowaniem: wycinamy
        r.t0 = time.monotonic()
        r.czekaj(PAUZY["start"] * r.tempo)
        for n, k in enumerate(sc["kroki"], 1):
            r.krok(n, k)
        r.czekaj(PAUZY["koniec"] * r.tempo)
        koniec = r.t()
        video = page.video
        ctx.close()
        sciezka = Path(video.path()) if (nagranie and video) else None
        br.close()
    return r, start, koniec, sciezka


def do_mp4(webm: Path, mp4: Path, start: float, dlugosc: float, rozmiar: list[int]) -> None:
    mp4.parent.mkdir(parents=True, exist_ok=True)
    w, h = rozmiar
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{start:.3f}", "-i", str(webm), "-t", f"{dlugosc:.3f}",
           "-vf", f"scale={w}:{h}:flags=lanczos,setsar=1", "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", "-an", str(mp4)]
    subprocess.run(cmd, check=True)


# ------------------------------------------------------------------ polecenia

def cmd_rozpoznaj(a) -> int:
    ensure_playwright()
    from playwright.sync_api import sync_playwright

    wynik = {}
    with sync_playwright() as p:
        br = przegladarka(p)
        page = br.new_page(viewport={"width": 1280, "height": 720})
        for url in a.url:
            page.goto(url, wait_until="load")
            wynik[url] = {"tytul": page.title(), "elementy": widoczne(page)}
            print(f"== {url} ({len(wynik[url]['elementy'])} elementów)")
            for e in wynik[url]["elementy"][:60]:
                opcje = f" opcje: {', '.join(e['opcje'])}" if e.get("opcje") else ""
                print(f"  {e['tag']}{'[' + e['typ'] + ']' if e['typ'] else ''} {e['selektor'] or '(bez selektora)'} "
                      f"„{e['tekst'] or e['placeholder']}”{opcje}")
        br.close()
    if a.o:
        Path(a.o).write_text(json.dumps(wynik, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"✓ {a.o}")
    return 0


def proba(sc: dict) -> list[str]:
    bledy = sprawdz_scenariusz(sc)
    if bledy:
        return bledy
    r, *_ = graj(sc, nagranie=False)
    return r.bledy


def cmd_proba(a) -> int:
    sc = wczytaj(a.demo)
    ensure_playwright()
    bledy = proba(sc)
    for b in bledy:
        print(f"✗ {b}")
    print("PRÓBA NIEUDANA: popraw selektory (demo_strony.py rozpoznaj <url>)" if bledy
          else f"✓ próba: {len(sc['kroki'])} kroków, wszystkie elementy widoczne")
    return 1 if bledy else 0


def cmd_nagraj(a) -> int:
    sc = wczytaj(a.demo)
    ensure_playwright()
    bledy = proba(sc)                                   # nigdy nie nagrywamy bez udanej próby
    if bledy:
        for b in bledy:
            print(f"✗ {b}")
        raise SystemExit("próba nieudana: nic nie nagrano")
    if not shutil.which("ffmpeg"):
        raise SystemExit("brak ffmpeg")
    out = Path(a.o)
    with tempfile.TemporaryDirectory(prefix="demo-") as tmp:
        r, start, koniec, webm = graj(sc, nagranie=True, katalog=Path(tmp), pasek=not a.bez_paska)
        if r.bledy or not webm:
            raise SystemExit("nagranie przerwane: " + "; ".join(r.bledy or ["brak pliku wideo"]))
        do_mp4(webm, out, start, koniec, sc.get("rozmiar", [1280, 720]))
    napisy = os_z_krokow(r.zdarzenia, koniec)
    out.with_suffix(".srt").write_text(srt(napisy), encoding="utf-8")
    out.with_suffix(".kroki.json").write_text(json.dumps(
        {"url": sc["url"], "rozmiar": sc.get("rozmiar", [1280, 720]), "dlugosc": round(koniec, 2),
         "pasek_w_obrazie": not a.bez_paska, "zdarzenia": r.zdarzenia}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ {out} ({koniec:.1f} s, {len(sc['kroki'])} kroków, napisów {len(napisy)})")
    print(f"MEDIA:{out.resolve()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("rozpoznaj", help="spis widocznych elementów na stronach")
    s.add_argument("url", nargs="+")
    s.add_argument("-o", help="zapisz JSON")
    s.set_defaults(fn=cmd_rozpoznaj)
    s = sub.add_parser("proba", help="przejście scenariusza bez nagrywania")
    s.add_argument("demo", type=Path)
    s.set_defaults(fn=cmd_proba)
    s = sub.add_parser("nagraj", help="próba, potem nagranie MP4 + SRT")
    s.add_argument("demo", type=Path)
    s.add_argument("-o", required=True, help="plik MP4")
    s.add_argument("--bez-paska", action="store_true", help="napisy kroków tylko w SRT (edytowalne w HQ)")
    s.set_defaults(fn=cmd_nagraj)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
