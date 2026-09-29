---
name: wdrozenie
description: "Podgląd (A1) i wdrożenie produkcyjne (A2, tylko za zgodą)."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [web, deploy, preview, hosting]
    related_skills: [publish-site, cloudflare-temporary-deploy]
  jarvo:
    agent: jarvo-web
    autonomy: A2
    reviewed: "2026-09-26"
---

# Podgląd i wdrożenie

## Podgląd (A1, bez pytania)
- lokalny: `npx astro preview --host 0.0.0.0` (URL dostępny tylko w sieci serwera; podaj ścieżkę i komendę w raporcie),
- tymczasowy publiczny: skill `cloudflare-temporary-deploy` (link wygasa). Użyj, gdy użytkownik ma obejrzeć stronę z telefonu.

## Wdrożenie produkcyjne (A2)
Warunek: w karcie albo w komentarzu jest **wyraźna zgoda użytkownika** z datą (np. „Decyzja użytkownika 2026-10-02: wdrożyć na nova.pl”).
Bez tego: `kanban_block(kind="needs_input", reason="Gotowe do wdrożenia na <cel>. Potrzebna zgoda użytkownika.")`.

Z zgodą:
1. Sprawdź, czy build jest identyczny z zaakceptowanym (ten sam commit/katalog `dist/`).
2. Wdróż skillem `publish-site` (GitHub Pages / Cloudflare Pages / Netlify), zgodnie z celem ze zgody. Nic więcej.
3. Po wdrożeniu: `seo_check.py` + Lighthouse + `security_check.py url` na produkcyjnym URL, zrzuty, weryfikacja przekierowań i HTTPS.
4. Raport: URL, commit/wersja, wyniki po wdrożeniu, jak cofnąć (rollback).

## Nigdy
Zmiany DNS, rejestracja domen, płatne plany, usuwanie istniejących projektów hostingowych, bez osobnej zgody na każdą z tych rzeczy.
