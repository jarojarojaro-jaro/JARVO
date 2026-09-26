---
name: favicon-i-meta
description: "Komplet faviconów, manifest, meta, OG i JSON-LD z logo."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [web, favicon, pwa, meta, open-graph, json-ld]
    related_skills: [seo-schema, optymalizacja-obrazow]
  tars:
    agent: tars-web
    autonomy: A1
    reviewed: 2026-09-26
---

# Favicon i meta

## Ikony
```bash
node $HERMES_HOME/scripts/favicons.cjs <logo.svg|png> out/icons \
  --name "<Nazwa>" --short "<Krótka>" --color "<#kolor marki>" --bg "<#tło>" --lang pl
```
Skrypt (pakiet `favicons`) tworzy: `favicon.ico` (16/32/48), `favicon.svg` (jeśli wejście SVG),
`apple-touch-icon.png` (180), `icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `site.webmanifest`
oraz `out/icons/head.html` z tagami do `<head>`.

Zasady: źródło **wektorowe** (SVG) albo PNG ≥ 512 px; ikona maskable ma margines bezpieczeństwa (~10%);
mały rozmiar = uproszczony sygnet, nie pełne logo z tekstem.

## Meta (w `<head>` każdej strony)
```html
<html lang="pl">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{≤ 60 znaków, fraza na początku}</title>
<meta name="description" content="{140–160 znaków}">
<link rel="canonical" href="{absolutny URL}">
<meta property="og:type" content="website">
<meta property="og:title" content="…"><meta property="og:description" content="…">
<meta property="og:image" content="{absolutny URL, 1200×630}"><meta property="og:url" content="…">
<meta property="og:locale" content="pl_PL"><meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="{kolor marki}">
<link rel="icon" href="/favicon.ico" sizes="32x32"><link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="manifest" href="/site.webmanifest">
```
JSON-LD: minimum `Organization` (name, url, logo, sameAs) i `WebSite`; więcej przez skill `seo-schema`.

## Weryfikacja
`python3 $HERMES_HOME/scripts/seo_check.py <url-podglądu>` → brak błędów w sekcjach `head`, `icons`, `og`, `jsonld`.
