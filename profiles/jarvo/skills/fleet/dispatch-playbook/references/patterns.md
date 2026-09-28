# Wzorce misji

Każdy wzorzec to punkt wyjścia. Dopasuj go do intencji, nie odwrotnie.

## 1. Research → decyzja
- `jarvo-sherlock` / `research`: raport z odpowiedzią na pytanie użytkownika, poziomem pewności i rekomendacją.
- Po akceptacji: Jarvo relacjonuje wnioski (nie wkleja całego raportu), podaje ścieżkę do raportu i pyta o decyzję, jeśli taka wynika.

## 2. Landing produktu (pełny launch)
1. `jarvo-sherlock` / `rynek`: grupa docelowa, 3–5 konkurentów (propozycje wartości, ceny, komunikacja), słowa kluczowe PL z intencją.
2. `jarvo-web` / `landing` (parents: rynek): landing w Astro, SEO on-page pod słowa kluczowe, schema Product/Organization, favicony, OG, podgląd.
3. `jarvo-studio` / `grafiki` (parents: rynek): OG image, 3 grafiki social (1080×1350, 1080×1920), 5 postów.
4. opcjonalnie `jarvo-wideo` / `film` (parents: rynek): film 20–30 s 9:16 (hook, przesłanie i CTA z raportu rynku).
5. `jarvo-reka` / `zlozenie` (parents: landing, grafiki, film): pakiet z INDEX.md.
Decyzje przed rozdaniem: nazwa produktu, język, domena/ścieżka, CTA (np. zapis na listę), paleta z brand kitu.

## 3. Audyt + naprawa strony
1. `jarvo-web` / `audyt`: raport priorytetów (P0–P3) z dowodami (Lighthouse, axe, linki, SEO).
2. Jarvo → decyzja użytkownika: które priorytety naprawiać (domyślnie P0 + P1).
3. `jarvo-web` / `poprawki`: zmiany na kopii/gałęzi + raport przed/po. Wdrożenie = osobna decyzja (A2).

## 4. Kampania / content
1. `jarvo-sherlock` / `odbiorcy`: kim są odbiorcy, gdzie są, co działa u konkurencji.
2. `jarvo-studio` / `kampania` (parents: odbiorcy): pakiet (posty, grafiki, kalendarz) + `BRIEF-WIDEO.md`, gdy kampania ma filmy.
3. `jarvo-wideo` / `filmy` (parents: kampania): filmy z briefu Studia (formaty, warianty A/B, napisy).
4. `jarvo-reka` / `zlozenie`: pakiet + kalendarz w jednym dokumencie.
Publikacja = decyzja użytkownika (A2), potem Studio ustawia kolejkę.

## 5. Brand kit z istniejącej strony
1. `jarvo-web` / `brand`: `brand-z-url` → `@@KNOWLEDGE_DIR@@/brands/<slug>/`.
2. `jarvo-studio` / `brand-review` (parents: brand): weryfikacja tonu komunikacji i elementów wizualnych, uzupełnienie `product-marketing.md`.
3. Jarvo → użytkownik: akceptacja brand kitu (ustawia `approved_by_owner: true`).

## 6. Film (pojedynczy albo seria)
1. opcjonalnie `jarvo-sherlock` / `fakty`: dane i źródła, gdy film podaje liczby, porównania albo twierdzenia.
2. `jarvo-wideo` / `film` (parents: fakty): scenariusz → ujęcia → lektor → napisy → montaż, kontrola ≥ 85.
Nagranie użytkownika (📎) albo długi materiał: jedna karta `jarvo-wideo` (montaż / klipy), bez researchu.
Decyzje przed rozdaniem tylko, gdy zmieniają wynik: platforma/format, długość, głos (M/K), muzyka marki.

## 7. Szybkie zadanie (pojedyncze)
Jedna karta dla właściwego agenta, bez MISSION.md (tylko wpis w INDEX.md z ID `Z-…`).
Przykłady: „zrób favicon z tego logo”, „sprawdź, czy ta informacja jest prawdziwa”, „przerób ten PDF na DOCX”.
