#!/usr/bin/env python3
"""Prawdziwe assety produktu ze strony: zrzuty (desktop i telefon, cała strona i ekran), logo, kolory, fonty.

    python3 assety.py https://jarvo.pl [--out out/wideo/src/assets] [--podstrony /pricing,/features]

Zasada reelu marki: interfejs i produkt pokazujesz z tych zrzutów (kadrujesz i animujesz prawdziwe wycinki),
nigdy nie rysujesz UI z wyobraźni. Wynik: katalog z PNG i `assety.json` (lista plików, paleta z użyciem,
fonty, logo, tytuł, opis). Przed animowaniem wypisz w RAPORT, co znalazłeś i czego brakuje (np. logo tylko jako PNG).
Wymaga: playwright w Pythonie (`narzedzia.py instaluj html`). Kod wyjścia: 0 ok, 2 strona niedostępna.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import html_wideo as hw  # noqa: E402
import narzedzia as nz  # noqa: E402

WIDOKI = {"desktop": (1440, 900, 1), "telefon": (390, 844, 3)}
ZBIERZ_JS = r"""
() => {
  const count = (m, k) => m.set(k, (m.get(k) || 0) + 1);
  const colors = new Map(), fonts = new Map();
  const els = [...document.querySelectorAll('body *')].slice(0, 4000);
  for (const el of els) {
    const r = el.getBoundingClientRect(); if (r.width * r.height < 4) continue;
    const cs = getComputedStyle(el);
    for (const p of ['color', 'backgroundColor', 'borderTopColor']) {
      const v = cs[p]; if (!v || v === 'rgba(0, 0, 0, 0)' || v === 'transparent') continue;
      if (p === 'borderTopColor' && cs.borderTopWidth === '0px') continue;
      count(colors, v);
    }
    if (el.childNodes.length && [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()))
      count(fonts, cs.fontFamily.split(',')[0].replace(/["']/g, '').trim() + ' ' + cs.fontWeight);
  }
  const abs = (u) => { try { return new URL(u, location.href).href; } catch { return null; } };
  const logos = [];
  for (const sel of ['header svg', 'header img', 'nav img', 'nav svg', '[class*=logo] img', '[class*=logo] svg', 'a[href="/"] img', 'a[href="/"] svg'])
    for (const el of document.querySelectorAll(sel)) {
      if (el.tagName.toLowerCase() === 'svg') logos.push({typ: 'svg', svg: el.outerHTML.slice(0, 200000)});
      else if (el.src) logos.push({typ: 'img', url: abs(el.currentSrc || el.src)});
      if (logos.length > 4) break;
    }
  const icons = [...document.querySelectorAll('link[rel*=icon], link[rel=apple-touch-icon]')].map(l => abs(l.href));
  const meta = (n) => (document.querySelector(`meta[property="${n}"], meta[name="${n}"]`) || {}).content || null;
  return {tytul: document.title, opis: meta('description') || meta('og:description'), og_image: abs(meta('og:image') || ''),
          kolory: [...colors].sort((a, b) => b[1] - a[1]).slice(0, 16), fonty: [...fonts].sort((a, b) => b[1] - a[1]).slice(0, 8),
          logo: logos, ikony: icons};
}
"""


def hex_(css: str) -> str | None:
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?", css)
    if not m or (m.group(4) and float(m.group(4)) < 0.5):
        return None
    return "#{:02X}{:02X}{:02X}".format(*map(int, m.groups()[:3]))


def pobierz(url: str, dest: Path) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 jarvo-wideo"})
        with urllib.request.urlopen(req, timeout=20) as r:
            dest.write_bytes(r.read())
        return str(dest)
    except Exception:  # noqa: BLE001 - brak pojedynczego pliku nie przerywa zbierania
        return None


def zbierz(url: str, out: Path, podstrony: list[str]) -> dict:
    from playwright.sync_api import sync_playwright
    out.mkdir(parents=True, exist_ok=True)
    wynik: dict = {"url": url, "zrzuty": [], "uwaga": "animuj wycinki tych zrzutów; UI z wyobraźni jest zakazane"}
    with sync_playwright() as p:
        br = hw.launch(p)
        for i, sciezka in enumerate(["", *podstrony]):
            adres = urllib.parse.urljoin(url, sciezka) if sciezka else url
            slug = re.sub(r"\W+", "-", sciezka.strip("/")) or "start"
            for nazwa, (w, h, skala) in WIDOKI.items():
                page = br.new_page(viewport={"width": w, "height": h}, device_scale_factor=skala)
                try:
                    page.goto(adres, wait_until="networkidle", timeout=45000)
                except Exception as exc:  # noqa: BLE001
                    if i == 0 and nazwa == "desktop":
                        raise SystemExit(f"✗ strona niedostępna: {adres} ({str(exc)[:160]})")
                    continue
                page.wait_for_timeout(800)
                for tryb, full in (("ekran", False), ("cala", True)):
                    f = out / f"{slug}-{nazwa}-{tryb}.png"
                    page.screenshot(path=str(f), full_page=full)
                    wynik["zrzuty"].append(str(f))
                if i == 0 and nazwa == "desktop":
                    info = page.evaluate(ZBIERZ_JS)
                page.close()
        br.close()
    paleta = []
    for css, n in info["kolory"]:
        hx = hex_(css)
        if hx and hx not in [p["hex"] for p in paleta]:
            paleta.append({"hex": hx, "uzycia": n})
    logo_pliki = []
    for k, lg in enumerate(info["logo"][:3]):
        if lg["typ"] == "svg":
            f = out / f"logo-{k}.svg"
            svg = lg["svg"] if "xmlns" in lg["svg"] else lg["svg"].replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
            f.write_text(svg, encoding="utf-8")
            logo_pliki.append(str(f))
        elif lg.get("url"):
            ext = Path(urllib.parse.urlparse(lg["url"]).path).suffix or ".png"
            if (f := pobierz(lg["url"], out / f"logo-{k}{ext}")):
                logo_pliki.append(f)
    for k, ic in enumerate(info["ikony"][:2]):
        ext = Path(urllib.parse.urlparse(ic).path).suffix or ".png"
        if (f := pobierz(ic, out / f"ikona-{k}{ext}")):
            logo_pliki.append(f)
    if info.get("og_image") and (f := pobierz(info["og_image"], out / "og.png")):
        wynik["og"] = f
    wynik.update(tytul=info["tytul"], opis=info["opis"], paleta=paleta[:10],
                 fonty=[{"font": f, "uzycia": n} for f, n in info["fonty"]], logo=logo_pliki,
                 braki=[x for x, ok in (("logo", logo_pliki), ("paleta", paleta), ("fonty", info["fonty"])) if not ok])
    (out / "assety.json").write_text(json.dumps(wynik, ensure_ascii=False, indent=2), encoding="utf-8")
    return wynik


def ensure_playwright() -> None:
    nz.wymagaj_playwright(__file__, "JARVO_HTML_REEXEC")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--out", default="out/wideo/src/assets")
    ap.add_argument("--podstrony", default="", help="ścieżki po przecinku, np. /cennik,/funkcje")
    a = ap.parse_args(argv)
    ensure_playwright()
    w = zbierz(a.url, Path(a.out), [s for s in a.podstrony.split(",") if s.strip()])
    print(json.dumps({k: w[k] for k in ("tytul", "paleta", "fonty", "logo", "braki")} | {"zrzutow": len(w["zrzuty"]),
                     "plik": str(Path(a.out) / "assety.json")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
