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
4. opcjonalnie, gdy kampania ma budżet reklamowy: `jarvo-ads` / `reklamy` (parents: kampania, filmy): plan kampanii
   płatnej (budżet, grupy odbiorców, test kreacji, prognoza) i wnioski dla Studia; start kampanii tylko przez Skarbiec
   z kodem zgody (A2), a bez Skarbca: plan i kreacje do ręcznego wgrania.
5. `jarvo-reka` / `zlozenie`: pakiet + kalendarz w jednym dokumencie.
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

## 7. Leady → pierwsza wiadomość
1. `jarvo-lowca` / `leady`: ICP (oferta, kogo szukamy, region) → sygnały z KRS, przetargów, stron firm → ranking z
   „dlaczego teraz” i kontaktem, który firma sama opublikowała (`LEADY.md`, `leady.csv`).
2. Jarvo → decyzja użytkownika: do których firm pisać (domyślnie top 10).
3. opcjonalnie `jarvo-studio` / `wiadomosci` (parents: leady): szkic pierwszej wiadomości na firmę (`copy-pl`), z „dlaczego teraz”.
Wysyłka = decyzja człowieka (A2); agent niczego nie wysyła. Monitoring (rutyna) tylko za zgodą użytkownika.

## 8. Aplikacja mobilna („chcę aplikację”)
1. `jarvo-mobile` / `decyzja`: `natywna-czy-pwa`: potrzeby (`potrzeby.yaml`) → rekomendacja (strona, PWA, karta w Wallet,
   platforma albo aplikacja w sklepach) z kosztami, ryzykiem odrzucenia (Apple 4.2) i następnym krokiem.
2. Jarvo → decyzja użytkownika: które rozwiązanie (przy opcjach „blisko” pokaż obie).
3. Dalej według decyzji: strona albo PWA → `jarvo-web` (parents: decyzja); karta w Wallet albo aplikacja → `jarvo-mobile`.
Bez kroku 1 nikt nie zaczyna aplikacji. Konta Apple, Google i Expo są zawsze właściciela; wysyłka do sklepów = A2.

## 9. Audyt mobilny → poprawki
1. `jarvo-mobile` / `audyt`: `audyt-mobilny` (aplikacje w sklepach, linki strona → aplikacja, PWA, opinie z App Store)
   → trzy priorytety i propozycje kart.
2. Jarvo → decyzja użytkownika, co poprawiać; karty z propozycji: `jarvo-web` (pliki `.well-known`, baner, odznaki,
   manifest, strony prywatności i usuwania konta), `jarvo-studio` (opis, „Co nowego”), właściciel (konsole sklepów).
Jako pierwszy kontakt z firmą z listy Łowcy: audyt to wartość bez dostępu do kont; wysyłka do firmy = A2.

## 10. Wyjaśnij mi filmem
Prośba „wytłumacz mi to filmem” (pomysł Karpathy'ego: zrozumienie szybciej z filmu niż z tekstu). Przy trudnym temacie
możesz sam zaproponować film jednym zdaniem; zlecasz dopiero po „tak”.
1. opcjonalnie `jarvo-sherlock` / `fakty`, gdy tematu nie ma w skarbcu, w raportach misji ani w dokumentacji.
2. `jarvo-wideo` / `wyjasnienie` (parents: fakty): rodzaj explainer, wariant „dla właściciela”
   (`rodzaje-filmu/references/explainer.md`). Karta:
   - KONTEKST: film dla właściciela, żeby zrozumiał <temat>; nie do publikacji; co już wie, czego nie.
   - WEJŚCIA: pełne ścieżki notatek skarbca, raportów misji albo dokumentów, z których pochodzą fakty.
   - DoD: 60–90 s, 16:9 (9:16, gdy prosi o telefon), lektor PL i napisy, zdanie lektora do 20 słów, każdy fakt
     z WEJŚĆ (lista faktów i źródeł w RAPORT), `qa_wideo.py` bez błędów.
   - GRANICE: A1, bez płatnej generacji AI (`video_generate`, `image_generate`), bez publikacji, budżet 30 min.
Po akceptacji wyślij ścieżkę pliku i jedno zdanie, czego film uczy.

## 11. Szybkie zadanie (pojedyncze)
Jedna karta dla właściwego agenta, bez MISSION.md (tylko wpis w INDEX.md z ID `Z-…`).
Przykłady: „zrób favicon z tego logo”, „sprawdź, czy ta informacja jest prawdziwa”, „przerób ten PDF na DOCX”.
