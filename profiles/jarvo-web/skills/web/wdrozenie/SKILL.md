---
name: wdrozenie
description: "Podgląd (A1) i wdrożenie produkcyjne (A2, tylko za zgodą)."
version: 1.4.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [web, deploy, preview, hosting, indexnow, bing, search-console]
    related_skills: [publish-site, cloudflare-temporary-deploy]
  jarvo:
    agent: jarvo-web
    autonomy: A2
    reviewed: "2026-11-19"
---

# Podgląd i wdrożenie

## Podgląd (A1, bez pytania)
- lokalny: `npx astro preview --host 127.0.0.1` (adres działa tylko na tym komputerze, nie na telefonie ani
  w Telegramie: człowiekowi podaj link z `@@PY@@ "@@REPO_DIR@@/scripts/jarvo_link.py" <katalog dist/>`, ścieżkę i komendę w raporcie),
- tymczasowy publiczny: skill `cloudflare-temporary-deploy` (link wygasa). Użyj, gdy użytkownik ma obejrzeć stronę z telefonu.

## Wdrożenie produkcyjne (A2)
**Strony właściciela na jego hostingu** (12 domen, repo `jarojarojaro-jaro/<domena>`, `main` = strona na żywo) **nie
wdrażasz sam.** Twoja część: zmiana na gałęzi repo strony (strona z builda: wpisy z `z_buildu` w `.strona.json`
podmieniasz zawartością `build/`, reszta repo bez zmian), podgląd w `<dane>/jarvo/workspaces/podglad/<domena>/`
(zawartość repo bez `.git`, `.github`, `.gitignore`, `.strona.json`) i `kanban_request_review`. Wgrywa tylko Jarvo
(skill `wgrywanie-stron`) po zgodzie właściciela; na hosting się nie łączysz (ssh, rsync, FTP). Procedura niżej dotyczy
innych celów (GitHub Pages, Cloudflare Pages, Netlify).

Warunek: w karcie albo w komentarzu jest **wyraźna zgoda użytkownika** jego słowami, z datą i godziną (np. `Decyzja
właściciela (2026-10-02 14:05): „wdrażaj na nova.pl”`). „Decyzja Jarva” albo decyzja bez słów właściciela to nie zgoda.
Bez tego: `kanban_block(kind="needs_input", reason="Gotowe do wdrożenia na <cel> (wersja <odcisk dist/>). Potrzebna zgoda użytkownika.")`.

Z zgodą:
1. Sprawdź, czy build jest identyczny z zaakceptowanym: `@@PY@@ "@@REPO_DIR@@/scripts/odcisk.py" out/site/dist --sprawdz <odcisk ze zgody>`
   (kod 1 = `dist/` zmienił się po zgodzie → nowa zgoda).
2. Wdróż skillem `publish-site` (GitHub Pages / Cloudflare Pages / Netlify), zgodnie z celem ze zgody. Nic więcej.
3. Po wdrożeniu: `seo_check.py <produkcyjny URL>` (bez `--podglad`: noindex i soft 404 to błędy) + Lighthouse, zrzuty, weryfikacja przekierowań i HTTPS.
   Nagłówki bezpieczeństwa mierzysz **tylko na domenie, którą właśnie wdrożyłeś**, jednym żądaniem: `curl -sI <produkcyjny URL>`
   (albo `security_check.py naglowki <produkcyjny URL>`, też jedno żądanie). Nigdy `security_check.py url` na produkcji
   (pełny skan tylko na podglądzie) i nigdy pętla po innych domenach: nagłówki zmienia wgranie, nie upływ czasu (18.11 skan
   12 domen, ok. 660 żądań, i wspólny hosting zablokował nasze IP).
4. Zgłoszenie wyszukiwarkom ([references/wyszukiwarki.md](references/wyszukiwarki.md)): gdy kontrola z punktu 3 nie ma błędów,
   `@@PY@@ "@@REPO_DIR@@/profiles/jarvo-web/scripts/indexnow.py" zglos <produkcyjny URL> --katalog <projekt>/public`
   (adresy z sitemapy do IndexNow: Bing i reszta wyszukiwarek IndexNow; zgoda na wdrożenie obejmuje to zgłoszenie).
   Bing Webmaster Tools i Google Search Console zakłada właściciel: przy pierwszym wdrożeniu domeny pytasz, czy już są,
   a jeśli nie, dajesz gotową instrukcję z adresem sitemapy. Domena zweryfikowana w Bing: po ok. 48 h raport AI Performance
   (które podstrony cytuje AI), procedura i warunki w punkcie 2a referencji.
5. Raport: URL, commit/wersja, wyniki po wdrożeniu, wynik IndexNow, stan Bing Webmaster Tools i Search Console, raport
   AI Performance przejrzany (tak/nie), jak cofnąć (rollback).

## Nigdy
Zgłaszanie podglądu albo stagingu do wyszukiwarek, stare „pingi” sitemapy (Google i Bing je wyłączyli), zakładanie
kont w Bing Webmaster Tools czy Search Console za właściciela. Zmiany DNS, rejestracja domen, płatne plany, usuwanie istniejących projektów hostingowych, bez osobnej zgody na każdą z tych rzeczy.
