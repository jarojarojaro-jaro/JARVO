#!/usr/bin/env python3
"""Prawdziwe assety produktu ze strony: zrzuty (desktop i telefon, cała strona i ekran), logo, kolory, fonty, marka.

    python3 assety.py https://jarvo.pl [--out out/wideo/src/assets] [--podstrony /pricing,/features]
    python3 assety.py https://jarvo.pl --film [--wycinki "cta=.btn-primary,plan=.pricing-card"] [--wysokosc-max 12000]

Zasada reelu marki: interfejs i produkt pokazujesz z tych zrzutów (kadrujesz i animujesz prawdziwe wycinki),
nigdy nie rysujesz UI z wyobraźni. Wynik: katalog z PNG i `assety.json` (lista plików, paleta z użyciem,
fonty, logo, tytuł, opis) oraz `marka.json` i `marka.css`: siedem ról kolorów (strona, powierzchnia, pole, tekst,
przygaszony, akcent z kolorem tekstu na nim, obramowanie), skala kroju (h1–h3, tekst, przycisk), promienie rogów,
cień karty, szerokość treści i podpowiedź charakteru ruchu do `ruch.js` (decyduje BRIEF i słowa właściciela).
Przed animowaniem wypisz w RAPORT, co znalazłeś i czego brakuje (np. logo tylko jako PNG).

`--film`: zrzut do filmowania strony (`film/`, przewodnik `film/uklad.json`). Desktop 1920 px w 2× i telefon
390 px w 3×, po przygotowaniu strony: przypięte elementy (fixed, sticky) wracają na swoje miejsce, banery cookie
są ukryte (nie klikamy zgody), strona przewinięta do końca i z powrotem (leniwe obrazy), fonty wczytane, animacje
dociągnięte do końca. Cała strona w kaflach (≤ 12 000 px wysokości), mapa elementów `cele` ({id, typ, tekst, x, y,
w, h} w pikselach CSS całej strony: nagłówki, przyciski, obrazy, sekcje, karty, formularze, ceny, logo, nawigacja),
wycinki ważnych elementów z przezroczystym tłem (logo, h1, przyciski, karty, ceny, formularze i `--wycinki`)
i pusta plansza (kafle bez wyciętych elementów: wycinek wlatuje na swoje prawdziwe miejsce).
Zrzut 2× wystarcza na najazd do 2× bez rozmycia (zasada: rozdzielczość ≥ kadr × największe przybliżenie);
filmujesz go modułem `/_lib/jarvo/strona.js` (skill `film-z-kodu`, `references/strona-filmowana.md`).
Wymaga: playwright w Pythonie (`narzedzia.py instaluj html`). Kod wyjścia: 0 ok, 2 strona niedostępna.
"""
from __future__ import annotations

import argparse
import colorsys
import json
import math
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import html_wideo as hw  # noqa: E402
import narzedzia as nz  # noqa: E402

WIDOKI = {"desktop": (1440, 900, 1), "telefon": (390, 844, 3)}
WIDOKI_FILMU = {"desktop": (1920, 1080, 2), "telefon": (390, 844, 3)}
KAFEL_MAX_PX = 12000            # wysokość kafla w pikselach obrazu (Chromium tnie zrzuty powyżej 16 384 px)
WYSOKOSC_MAX = 12000            # strona dłuższa (px CSS) jest ucinana: film i tak pokazuje górę i kilka sekcji
WYCINKI_LIMIT = {"logo": 1, "naglowek": 1, "przycisk": 3, "karta": 6, "cena": 4, "formularz": 2}
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
# surowe dane do tokenów marki: role kolorów liczymy w Pythonie (czyste funkcje, testy), tu tylko zbieramy
MARKA_JS = r"""
() => {
  const solid = c => !!c && c !== 'transparent' && !/^rgba\(.*,\s*0(\.0+)?\)$/.test(c);
  const add = (m, k, w) => { if (k) m.set(k, (m.get(k) || 0) + w); };
  const top = (m, n = 12) => [...m].sort((a, b) => b[1] - a[1]).slice(0, n);
  const vis = (el, cs, r) => r.width > 2 && r.height > 2 && cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity > 0.05;
  let strona = null;
  for (const el of [document.body, document.documentElement]) {
    const c = getComputedStyle(el).backgroundColor; if (solid(c)) { strona = c; break; }
  }
  const BTN = 'button, [role=button], input[type=submit], input[type=button], a[class*=btn], a[class*=button], a[class*=cta], .btn, .button';
  const POLE = 'input:not([type=submit]):not([type=button]):not([type=checkbox]):not([type=radio]):not([type=hidden]), textarea, select';
  const pow = new Map(), txt = new Map(), btn = new Map(), pola = new Map(), ram = new Map(), linki = new Map();
  const rad = {przycisk: new Map(), karta: new Map(), pole: new Map()}, cien = new Map(), szer = new Map();
  const vw = innerWidth, vh = innerHeight;
  for (const el of [...document.querySelectorAll('body *')].slice(0, 6000)) {
    const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    if (!vis(el, cs, r)) continue;
    const area = r.width * r.height, bg = cs.backgroundColor;
    if (el.matches(BTN)) {
      if (solid(bg)) add(btn, bg + '|' + cs.color, 1);
      add(rad.przycisk, cs.borderTopLeftRadius + '|' + Math.round(r.height), 1);
      continue;
    }
    if (el.matches(POLE)) {
      add(pola, solid(bg) ? bg : null, 1); add(rad.pole, cs.borderTopLeftRadius, 1);
      if (cs.borderTopWidth !== '0px' && solid(cs.borderTopColor)) add(ram, cs.borderTopColor, 1);
      continue;
    }
    if (el.tagName === 'A' && solid(cs.color)) add(linki, cs.color, 1);
    if (solid(bg) && area > 6000) add(pow, bg, area);
    const karta = area > 12000 && area < vw * vh * 0.6 && (solid(bg) || cs.boxShadow !== 'none' || cs.borderTopWidth !== '0px');
    if (karta) {
      add(rad.karta, cs.borderTopLeftRadius, 1);
      if (cs.boxShadow !== 'none') add(cien, cs.boxShadow, 1);
    }
    if (cs.borderTopWidth !== '0px' && cs.borderTopStyle !== 'none' && solid(cs.borderTopColor)) add(ram, cs.borderTopColor, 1);
    const tekst = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join('');
    if (tekst) add(txt, cs.color, tekst.length);
    const lewo = r.left, prawo = vw - r.right;
    if (r.width > 480 && r.width < vw - 40 && Math.abs(lewo - prawo) < 4) add(szer, Math.round(r.width), 1);
  }
  const krój = {};
  for (const [nazwa, sel] of [['h1', 'h1'], ['h2', 'h2'], ['h3', 'h3'], ['tekst', 'p, li'], ['maly', 'small, figcaption, .caption'], ['przycisk', BTN]]) {
    const m = new Map();
    for (const el of [...document.querySelectorAll(sel)].slice(0, 400)) {
      const cs = getComputedStyle(el), r = el.getBoundingClientRect();
      if (!vis(el, cs, r) || !el.textContent.trim()) continue;
      const lh = cs.lineHeight === 'normal' ? 'normal' : (parseFloat(cs.lineHeight) / parseFloat(cs.fontSize)).toFixed(2);
      add(m, JSON.stringify({font: cs.fontFamily.split(',')[0].replace(/["']/g, '').trim(), px: Math.round(parseFloat(cs.fontSize)),
                             waga: +cs.fontWeight, interlinia: lh, odstep: cs.letterSpacing,
                             wielkie: cs.textTransform === 'uppercase'}), el.textContent.trim().length);
    }
    const t = top(m, 1)[0];
    if (t) krój[nazwa] = JSON.parse(t[0]);
  }
  return {strona, powierzchnie: top(pow), teksty: top(txt), przyciski: top(btn).map(([k, n]) => [...k.split('|'), n]),
          pola: top(pola), obramowania: top(ram), linki: top(linki), kroj: krój,
          promienie: {przycisk: top(rad.przycisk, 5).map(([k, n]) => [...k.split('|'), n]), karta: top(rad.karta, 5), pole: top(rad.pole, 5)},
          cienie: top(cien, 3), szerokosci: top(szer, 5), szer_okna: vw};
}
"""
# przygotowanie strony do zrzutu filmowego: banery cookie ukryte (bez klikania zgody), przypięte elementy na miejsce
PRZYGOTUJ_JS = r"""
() => {
  const COOKIE = /cookie|ciasteczk|consent|zgod[ay] na|rodo|gdpr|prywatno/i;
  const ZNANE = '#onetrust-consent-sdk, #onetrust-banner-sdk, #CybotCookiebotDialog, .cc-window, .cky-consent-container, '
              + '#usercentrics-root, .fc-consent-root, #cmpbox, #cmpwrapper, .qc-cmp2-container, #didomi-host';
  let ukryte = 0, przypiete = 0;
  for (const el of document.querySelectorAll(ZNANE)) { el.style.setProperty('display', 'none', 'important'); ukryte++; }
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    if ((cs.position !== 'fixed' && cs.position !== 'sticky') || cs.display === 'none') continue;
    const r = el.getBoundingClientRect();
    if (COOKIE.test((el.innerText || '').slice(0, 2000)) && el.querySelector('button, a, [role=button]') && r.height < innerHeight * 0.9) {
      el.style.setProperty('display', 'none', 'important'); ukryte++; continue;
    }
    el.style.setProperty('position', cs.position === 'fixed' && r.height >= innerHeight * 0.9 ? 'absolute' : 'static', 'important');
    przypiete++;
  }
  for (const d of document.querySelectorAll('dialog[open]')) if (COOKIE.test(d.innerText || '')) { d.close(); ukryte++; }
  document.documentElement.style.setProperty('overflow', 'visible', 'important');
  document.body.style.setProperty('overflow', 'visible', 'important');
  for (const img of document.querySelectorAll('img[loading=lazy]')) img.loading = 'eager';
  return {ukryte, przypiete};
}
"""
# mapa elementów strony (piksele CSS całej strony); każdy cel dostaje data-jarvo-cel do wycinka
CELE_JS = r"""
(limit) => {
  const vis = (el) => { const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    return r.width > 4 && r.height > 4 && cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity > 0.05; };
  const box = (el) => { const r = el.getBoundingClientRect();
    return {x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height)}; };
  const tekst = (el) => (el.innerText || el.getAttribute('aria-label') || el.getAttribute('alt') || '').replace(/\s+/g, ' ').trim().slice(0, 80);
  const ramkaTekstu = (el) => { const r = document.createRange(); r.selectNodeContents(el); const b = r.getBoundingClientRect();
    return b.width > 0 ? {x: Math.round(b.left + scrollX), y: Math.round(b.top + scrollY), w: Math.round(b.width), h: Math.round(b.height)} : null; };
  const maxY = limit;
  const cele = [], uzyte = new Set(), licz = {};
  const dodaj = (typ, el, extra = {}) => {
    if (uzyte.has(el) || !vis(el)) return;
    const b = box(el); if (b.y > maxY) return;
    licz[typ] = (licz[typ] || 0) + 1;
    const id = `${typ}-${licz[typ]}`;
    el.setAttribute('data-jarvo-cel', id); uzyte.add(el);
    cele.push({id, typ, tekst: tekst(el), ...b, ...extra});
    if (typ === 'naglowek' || typ === 'cena') {          // blok bywa szerszy od napisu: zakreślacz i lupa idą po tekście
      const n = ramkaTekstu(el); if (n && n.w < b.w - 8) cele[cele.length - 1].napis = n;
    }
  };
  const LOGO = 'header [class*=logo], nav [class*=logo], a[href="/"] img, a[href="/"] svg, header img, header svg';
  const pierwsze = (sel) => [...document.querySelectorAll(sel)].find(vis);
  const logo = pierwsze(LOGO); if (logo) dodaj('logo', logo);
  const nav = pierwsze('header, nav, [role=banner]'); if (nav) dodaj('nawigacja', nav);
  for (const el of [...document.querySelectorAll('h1, h2, h3')].slice(0, 40)) if (tekst(el)) dodaj('naglowek', el, {poziom: +el.tagName[1]});
  const BTN = 'button, [role=button], input[type=submit], a[class*=btn], a[class*=button], a[class*=cta], .btn, .button';
  for (const el of [...document.querySelectorAll(BTN)].slice(0, 60)) {
    if ((licz.przycisk || 0) >= 20) break;
    if (tekst(el)) dodaj('przycisk', el);
  }
  const CENA = /(\d[\d\s.,]*\s?(zł|pln|€|eur|\$|usd|£))|((zł|pln|€|\$|£)\s?\d)/i;
  for (const el of document.querySelectorAll('body *')) {
    if ((licz.cena || 0) >= 10) break;
    if (el.children.length > 2 || !CENA.test(el.textContent || '') || (el.textContent || '').length > 40) continue;
    if ([...el.children].some(c => CENA.test(c.textContent || ''))) continue;
    dodaj('cena', el);
  }
  const KARTA = 'article, [class*=card], [class*=Card], [class*=tile], [class*=plan], [class*=pricing] > *';
  for (const el of [...document.querySelectorAll(KARTA)].slice(0, 80)) {
    if ((licz.karta || 0) >= 20) break;
    const r = el.getBoundingClientRect();
    if (r.width > 120 && r.height > 80 && r.width < innerWidth * 0.95) dodaj('karta', el);
  }
  for (const el of [...document.querySelectorAll('form')].slice(0, 6)) dodaj('formularz', el);
  for (const el of [...document.querySelectorAll('img, picture, video, canvas, svg')].slice(0, 200)) {
    if ((licz.obraz || 0) >= 20) break;
    const r = el.getBoundingClientRect();
    if (r.width * r.height > 40000 && !el.closest('[data-jarvo-cel^="logo"]')) dodaj('obraz', el);
  }
  for (const el of [...document.querySelectorAll('main > *, section, footer, [class*=hero]')].slice(0, 60)) {
    if ((licz.sekcja || 0) >= 20) break;
    if (el.getBoundingClientRect().height > 200) dodaj('sekcja', el);
  }
  return {cele, wys: Math.min(document.documentElement.scrollHeight, maxY), wys_pelna: document.documentElement.scrollHeight};
}
"""
SERIF = ("serif", "playfair", "lora", "merriweather", "cormorant", "georgia", "times", "baskerville", "garamond",
         "crimson", "fraunces", "dm serif", "libre caslon", "bodoni", "didot", "prata", "spectral", "noto serif")


# ---------------------------------------------------------------- kolory
def rgb(css: str) -> tuple[int, int, int, float] | None:
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?", css or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4) or 1)


def hex_(css: str) -> str | None:
    c = rgb(css)
    if not c or c[3] < 0.5:
        return None
    return "#{:02X}{:02X}{:02X}".format(*c[:3])


def _kanaly(hx: str) -> tuple[float, float, float]:
    return tuple(int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5))


def luminancja(hx: str) -> float:
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in _kanaly(hx)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def kontrast(a: str, b: str) -> float:
    la, lb = sorted((luminancja(a), luminancja(b)), reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


def nasycenie(hx: str) -> float:
    return colorsys.rgb_to_hls(*_kanaly(hx))[2]


def miks(a: str, b: str, u: float) -> str:
    ca, cb = _kanaly(a), _kanaly(b)
    return "#{:02X}{:02X}{:02X}".format(*(round((x + (y - x) * u) * 255) for x, y in zip(ca, cb)))


def _hexy(pary) -> list[tuple[str, float]]:
    """[[css, waga], …] → [(hex, waga)] bez półprzezroczystych i z wagami zsumowanymi po tym samym kolorze."""
    out: dict[str, float] = {}
    for css, w in pary or []:
        if (hx := hex_(css)):
            out[hx] = out.get(hx, 0) + float(w)
    return sorted(out.items(), key=lambda kv: -kv[1])


def role_kolorow(s: dict) -> dict:
    """Siedem ról kolorów marki z surowych zliczeń strony (MARKA_JS): strona, powierzchnia, pole, tekst, przygaszony,
    akcent (+ akcent_tekst) i obramowanie. Brakująca rola jest liczona z pozostałych i oznaczona w „zgadniete”."""
    zgadniete = []
    strona = hex_(s.get("strona") or "") or "#FFFFFF"
    if not hex_(s.get("strona") or ""):
        zgadniete.append("strona")
    teksty = _hexy(s.get("teksty"))
    razem = sum(w for _, w in teksty) or 1
    # tekst = najmocniejszy z częstych szarych (≥ 10% znaków), nie najczęstszy: opisy bywają przygaszone
    czeste = [hx for hx, w in teksty if w >= 0.1 * razem and nasycenie(hx) < 0.5] or [hx for hx, _ in teksty]
    tekst = (max(czeste, key=lambda hx: kontrast(hx, strona)) if czeste
             else ("#111111" if luminancja(strona) > 0.4 else "#F5F5F5"))
    if not teksty:
        zgadniete.append("tekst")
    k_tekst = kontrast(tekst, strona)
    przyg = [hx for hx, _ in teksty
             if hx != tekst and nasycenie(hx) < 0.5 and 2.5 <= kontrast(hx, strona) < k_tekst]
    przygaszony = przyg[0] if przyg else miks(tekst, strona, 0.4)
    if not przyg:
        zgadniete.append("przygaszony")
    pow_ = [hx for hx, _ in _hexy(s.get("powierzchnie")) if hx != strona and kontrast(hx, strona) < 1.6]
    powierzchnia = pow_[0] if pow_ else miks(strona, tekst, 0.04)
    if not pow_:
        zgadniete.append("powierzchnia")
    przyciski: dict[str, dict] = {}
    for bg, kolor, n in s.get("przyciski") or []:
        if (hb := hex_(bg)):
            p = przyciski.setdefault(hb, {"n": 0, "teksty": {}})
            p["n"] += n
            if (ht := hex_(kolor)):
                p["teksty"][ht] = p["teksty"].get(ht, 0) + n
    kandydaci = [hb for hb in sorted(przyciski, key=lambda h: -przyciski[h]["n"]) if kontrast(hb, strona) >= 1.4]
    nasycone = [hb for hb in kandydaci if nasycenie(hb) >= 0.25]
    linki = [hx for hx, _ in _hexy(s.get("linki")) if nasycenie(hx) >= 0.3 and kontrast(hx, strona) >= 2]
    akcent = (nasycone or kandydaci or linki or [tekst])[0]
    if not (nasycone or kandydaci):
        zgadniete.append("akcent")
    na_akcencie = przyciski.get(akcent, {}).get("teksty", {})
    dobre = [ht for ht in sorted(na_akcencie, key=lambda h: -na_akcencie[h]) if kontrast(ht, akcent) >= 3]
    akcent_tekst = dobre[0] if dobre else max(("#FFFFFF", "#111111", strona, tekst), key=lambda c: kontrast(c, akcent))
    pola = [hx for hx, _ in _hexy(s.get("pola"))]
    pole = pola[0] if pola else powierzchnia
    ramy = [hx for hx, _ in _hexy(s.get("obramowania")) if kontrast(hx, strona) < 3]
    obramowanie = ramy[0] if ramy else miks(strona, tekst, 0.15)
    if not ramy:
        zgadniete.append("obramowanie")
    return {"strona": strona, "powierzchnia": powierzchnia, "pole": pole, "tekst": tekst, "przygaszony": przygaszony,
            "akcent": akcent, "akcent_tekst": akcent_tekst, "obramowanie": obramowanie, "zgadniete": zgadniete}


def _px(v) -> float | None:
    m = re.match(r"\s*([\d.]+)px", str(v or ""))
    return float(m.group(1)) if m else None


def promienie(s: dict) -> dict:
    """Najczęstszy promień rogów przycisku, karty i pola (px); przycisk-pigułka (promień ≥ połowy wysokości) = 999."""
    out = {}
    for rola, lista in (s.get("promienie") or {}).items():
        wart = next((w for w in lista or [] if _px(w[0]) is not None), None)
        if wart is None:
            continue
        px = _px(wart[0])
        if rola == "przycisk" and len(wart) > 2 and wart[1].isdigit() and px >= int(wart[1]) / 2 - 0.5 and px > 0:
            px = 999
        out[rola] = round(px)
    return out


def podpowiedz_charakteru(kolory: dict, kroj: dict, prom: dict) -> dict:
    """Podpowiedź charakteru ruchu (ruch.js) z wyglądu strony; dowód w „dlaczego”. Decyduje BRIEF i właściciel."""
    nas = nasycenie(kolory["akcent"])
    h = kroj.get("h1") or kroj.get("h2") or {}
    font = (h.get("font") or "").lower()
    szeryf = any(x in font for x in SERIF) and "sans" not in font
    waga = h.get("waga") or 400
    r = prom.get("przycisk", prom.get("karta", 6))
    dowody = [f"akcent {kolory['akcent']} (nasycenie {nas:.2f})", f"rogi przycisku {r if r != 999 else 'pigułka'}",
              f"nagłówek {h.get('font', '?')} {waga}"]
    if szeryf and nas < 0.45:
        nazwa = "luksus"
    elif r >= 20 and nas >= 0.6:
        nazwa = "zabawny"
    elif waga >= 800 and nas >= 0.5:
        nazwa = "odwazny"
    elif r <= 6 and nas < 0.5:
        nazwa = "zaufanie"
    elif nas < 0.45 and 8 <= r <= 16:
        nazwa = "spokojny"
    else:
        nazwa = "przyjazny"
    return {"nazwa": nazwa, "dlaczego": ", ".join(dowody),
            "uwaga": "podpowiedź z wyglądu; słowa właściciela o marce i BRIEF wygrywają (ruch-i-kompozycja.md)"}


def marka(s: dict) -> dict:
    kolory = role_kolorow(s)
    prom = promienie(s)
    kroj = s.get("kroj") or {}
    szer = [w for w, _ in s.get("szerokosci") or []]
    cien = (s.get("cienie") or [[None]])[0][0]
    return {"kolory": kolory, "kroj": kroj, "promienie": prom, "cien_karty": cien,
            "szerokosc_tresci": szer[0] if szer else None, "szerokosc_okna": s.get("szer_okna"),
            "charakter": podpowiedz_charakteru(kolory, kroj, prom)}


def marka_css(m: dict) -> str:
    """Zmienne CSS marki do animacji: `@import url('assets/marka.css')` i `var(--marka-akcent)`."""
    k = m["kolory"]
    linie = [f"  --marka-{rola.replace('_', '-')}: {k[rola]};" for rola in
             ("strona", "powierzchnia", "pole", "tekst", "przygaszony", "akcent", "akcent_tekst", "obramowanie")]
    kroj = m.get("kroj") or {}
    for rola in ("h1", "h2", "h3", "tekst", "przycisk"):
        if (f := kroj.get(rola)):
            nazwa = "naglowek" if rola == "h1" else rola
            if rola in ("h1", "tekst", "przycisk"):
                linie.append(f"  --marka-font-{nazwa}: \"{f['font']}\";")
            linie.append(f"  --marka-{rola}-px: {f['px']}px;")
            linie.append(f"  --marka-{rola}-waga: {f['waga']};")
    for rola, px in (m.get("promienie") or {}).items():
        linie.append(f"  --marka-promien-{rola}: {px}px;")
    if m.get("cien_karty"):
        linie.append(f"  --marka-cien-karty: {m['cien_karty']};")
    ch = (m.get("charakter") or {}).get("nazwa")
    return ("/* marka ze strony (assety.py): role kolorów, krój, rogi, cień; charakter ruchu: "
            f"{ch} (podpowiedź) */\n:root {{\n" + "\n".join(linie) + "\n}\n")


# ---------------------------------------------------------------- zrzut do filmu
def kafle(wysokosc: int, dpr: float, max_px: int = KAFEL_MAX_PX) -> list[tuple[int, int]]:
    """Podział strony (px CSS) na kafle [(y, h)], każdy ≤ max_px pikseli obrazu."""
    krok = max(1, int(max_px // dpr))
    wysokosc = max(1, int(wysokosc))
    return [(y, min(krok, wysokosc - y)) for y in range(0, wysokosc, krok)]


def wybierz_wycinki(cele: list[dict], limity: dict | None = None) -> list[str]:
    """Id celi do wycięcia: logo, h1, pierwsze przyciski, karty, ceny i formularze (limity WYCINKI_LIMIT)."""
    limity = limity or WYCINKI_LIMIT
    licz: dict[str, int] = {}
    out = []
    for c in cele:
        typ = c["typ"]
        if typ == "naglowek" and c.get("poziom") != 1:
            continue
        if typ in limity and licz.get(typ, 0) < limity[typ] and c["w"] * c["h"] >= 16:
            licz[typ] = licz.get(typ, 0) + 1
            out.append(c["id"])
    return out


def przygotuj(page, wys_max: int) -> dict:
    """Strona gotowa do zrzutu: przypięte na miejsce, cookie ukryte, leniwe obrazy wczytane, fonty gotowe."""
    info = page.evaluate(PRZYGOTUJ_JS)
    h = page.viewport_size["height"]
    y = 0
    while y < min(page.evaluate("document.documentElement.scrollHeight"), wys_max):
        y += int(h * 0.8)
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(120)
    page.evaluate("window.scrollTo(0, 0)")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(700)
    drugie = page.evaluate(PRZYGOTUJ_JS)         # elementy dołożone przez skrypty po przewinięciu
    return {k: info[k] + drugie[k] for k in info}


def zrzut_filmu(page, out: Path, prefiks: str, wys_max: int, wlasne: dict[str, str]) -> dict:
    """Kafle całej strony, cele, wycinki i pusta plansza jednego widoku."""
    dpr = page.evaluate("devicePixelRatio")
    info = przygotuj(page, wys_max)
    mapa = page.evaluate(CELE_JS, wys_max)
    cele = mapa["cele"]
    for nazwa, sel in wlasne.items():
        el = page.query_selector(sel)
        if el and (b := el.bounding_box()):
            page.evaluate("([el, id]) => el.setAttribute('data-jarvo-cel', id)", [el, nazwa])
            sy = page.evaluate("scrollY")
            cele.append({"id": nazwa, "typ": "wlasny", "tekst": (el.inner_text() or "")[:80].strip(),
                         "x": round(b["x"]), "y": round(b["y"] + sy), "w": round(b["width"]), "h": round(b["height"])})
        else:
            cele.append({"id": nazwa, "typ": "wlasny", "brak": f"selektor {sel!r} nic nie znalazł"})
    szer = page.viewport_size["width"]
    wys = mapa["wys"]
    widok = {"szer": szer, "dpr": dpr, "wys": wys, "wys_pelna": mapa["wys_pelna"], "kafle": [], "pusta": [],
             "cele": cele, "przygotowanie": info}
    podzial = kafle(wys, dpr)
    for k, (y, h) in enumerate(podzial, 1):
        f = out / f"{prefiks}-{k}.png"
        page.screenshot(path=str(f), full_page=True, clip={"x": 0, "y": y, "width": szer, "height": h},
                        animations="disabled", caret="hide")
        widok["kafle"].append({"plik": f.name, "y": y, "h": h})
    do_wyciecia = wybierz_wycinki(cele) + [n for n in wlasne if any(c["id"] == n and "brak" not in c for c in cele)]
    for c in cele:
        if c["id"] not in do_wyciecia:
            continue
        f = out / f"{prefiks}-{c['id']}.png"
        try:
            page.locator(f'[data-jarvo-cel="{c["id"]}"]').first.screenshot(path=str(f), omit_background=True,
                                                                             animations="disabled", timeout=8000)
            c["wycinek"] = f.name
        except Exception as exc:  # noqa: BLE001 - jeden wycinek nie przerywa zrzutu
            c["wycinek_blad"] = str(exc)[:160]
    page.evaluate("window.scrollTo(0, 0)")
    wyciete = [c for c in cele if c.get("wycinek")]
    if wyciete:
        for c in wyciete:
            page.evaluate("(id) => { const el = document.querySelector(`[data-jarvo-cel=\"${id}\"]`);"
                          " if (el) el.style.setProperty('visibility', 'hidden', 'important'); }", c["id"])
        for k, (y, h) in enumerate(podzial, 1):
            if not any(y < c["y"] + c["h"] and c["y"] < y + h for c in wyciete):
                continue
            f = out / f"{prefiks}-pusta-{k}.png"
            page.screenshot(path=str(f), full_page=True, clip={"x": 0, "y": y, "width": szer, "height": h},
                            animations="disabled", caret="hide")
            widok["pusta"].append({"plik": f.name, "y": y, "h": h})
    return widok


def film(url: str, out: Path, podstrony: list[str], wys_max: int, wlasne: dict[str, str]) -> dict:
    from playwright.sync_api import sync_playwright
    out.mkdir(parents=True, exist_ok=True)
    uklad: dict = {"url": url, "zasada": "filmujesz te kafle i wycinki (strona.js); UI z wyobraźni jest zakazane",
                   "strony": {}}
    with sync_playwright() as p:
        br = hw.launch(p)
        for i, sciezka in enumerate(["", *podstrony]):
            adres = urllib.parse.urljoin(url, sciezka) if sciezka else url
            slug = re.sub(r"\W+", "-", sciezka.strip("/")) or "start"
            strona = uklad["strony"].setdefault(slug, {"adres": adres})
            for nazwa, (w, h, skala) in WIDOKI_FILMU.items():
                page = br.new_page(viewport={"width": w, "height": h}, device_scale_factor=skala)
                try:
                    page.goto(adres, wait_until="networkidle", timeout=45000)
                except Exception as exc:  # noqa: BLE001
                    if i == 0 and nazwa == "desktop":
                        raise SystemExit(f"✗ strona niedostępna: {adres} ({str(exc)[:160]})")
                    strona[nazwa] = {"brak": str(exc)[:160]}
                    continue
                strona[nazwa] = zrzut_filmu(page, out, f"{slug}-{nazwa}", wys_max, wlasne if nazwa == "desktop" else {})
                page.close()
        br.close()
    (out / "uklad.json").write_text(json.dumps(uklad, ensure_ascii=False, indent=1), encoding="utf-8")
    return uklad


# ---------------------------------------------------------------- zwykłe assety
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
                    page.evaluate(PRZYGOTUJ_JS)          # przycisk zgody na cookie to nie akcent marki
                    surowe = page.evaluate(MARKA_JS)
                page.close()
        br.close()
    paleta = []
    for css, n in info["kolory"]:
        hx = hex_(css)
        if hx and hx not in [p["hex"] for p in paleta]:
            paleta.append({"hex": hx, "uzycia": n})
    logo_pliki, widziane = [], set()
    for k, lg in enumerate(info["logo"][:3]):
        klucz = lg.get("svg") or lg.get("url")
        if klucz in widziane:                    # to samo logo pod kilkoma selektorami
            continue
        widziane.add(klucz)
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
    m = marka(surowe)
    (out / "marka.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "marka.css").write_text(marka_css(m), encoding="utf-8")
    wynik.update(tytul=info["tytul"], opis=info["opis"], paleta=paleta[:10],
                 fonty=[{"font": f, "uzycia": n} for f, n in info["fonty"]], logo=logo_pliki,
                 marka={"plik": str(out / "marka.json"), "css": str(out / "marka.css"), "kolory": m["kolory"],
                        "charakter": m["charakter"]},
                 braki=[x for x, ok in (("logo", logo_pliki), ("paleta", paleta), ("fonty", info["fonty"])) if not ok])
    (out / "assety.json").write_text(json.dumps(wynik, ensure_ascii=False, indent=2), encoding="utf-8")
    return wynik


def wlasne_wycinki(tekst: str) -> dict[str, str]:
    """„cta=.btn-primary,plan=.pricing-card” → {nazwa: selektor}; nazwa bez spacji i ukośników."""
    out = {}
    for kawalek in filter(None, (x.strip() for x in (tekst or "").split(","))):
        nazwa, _, sel = kawalek.partition("=")
        if not sel or not re.fullmatch(r"[\w-]+", nazwa.strip()):
            raise SystemExit(f"--wycinki: „{kawalek}” ma być nazwa=selektor (nazwa: litery, cyfry, -, _)")
        out[nazwa.strip()] = sel.strip()
    return out


def podsumowanie_filmu(uklad: dict) -> dict:
    out = {}
    for slug, s in uklad["strony"].items():
        for widok, w in s.items():
            if not isinstance(w, dict) or "kafle" not in w:
                continue
            out[f"{slug}/{widok}"] = {
                "wysokosc": w["wys"], "uciete": w["wys_pelna"] > w["wys"], "kafle": len(w["kafle"]),
                "cele": len(w["cele"]), "wycinki": sum(1 for c in w["cele"] if c.get("wycinek")),
                "pusta": len(w["pusta"]), "przygotowanie": w["przygotowanie"],
                "braki": [c["id"] + ": " + c["brak"] for c in w["cele"] if c.get("brak")]}
    return out


def ensure_playwright() -> None:
    nz.wymagaj_playwright(__file__, "JARVO_HTML_REEXEC")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--out", default="out/wideo/src/assets")
    ap.add_argument("--podstrony", default="", help="ścieżki po przecinku, np. /cennik,/funkcje")
    ap.add_argument("--film", action="store_true", help="także zrzut do filmowania strony: film/ i film/uklad.json")
    ap.add_argument("--wycinki", default="", help="własne wycinki do --film: nazwa=selektor,…")
    ap.add_argument("--wysokosc-max", type=int, default=WYSOKOSC_MAX, help="ile strony (px CSS) zrzucić do filmu")
    a = ap.parse_args(argv)
    wlasne = wlasne_wycinki(a.wycinki)
    if wlasne and not a.film:
        ap.error("--wycinki działa z --film")
    ensure_playwright()
    podstrony = [s for s in a.podstrony.split(",") if s.strip()]
    w = zbierz(a.url, Path(a.out), podstrony)
    wynik = {k: w[k] for k in ("tytul", "paleta", "fonty", "logo", "braki")} | {
        "marka": {"kolory": w["marka"]["kolory"], "charakter": w["marka"]["charakter"], "css": w["marka"]["css"]},
        "zrzutow": len(w["zrzuty"]), "plik": str(Path(a.out) / "assety.json")}
    if a.film:
        uklad = film(a.url, Path(a.out) / "film", podstrony, a.wysokosc_max, wlasne)
        wynik["film"] = {"uklad": str(Path(a.out) / "film" / "uklad.json"), **podsumowanie_filmu(uklad)}
    print(json.dumps(wynik, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
