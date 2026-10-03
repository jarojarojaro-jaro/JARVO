# Karta strony referencyjnej (własna baza w skarbcu)

Plik: `@@KNOWLEDGE_DIR@@/inspiracje/strony/<branza>/<domena>.md`, obok katalog `<domena>/` z `brand_extract.sh --kit`
(`DESIGN.md`, `tokens.json`, `dembrandt.json`, `wcag.json`) i `screenshots.cjs` (`screenshots/`).
Piszesz tylko to, co widać na stronie i w `DESIGN.md`. Bez cytowania tekstów strony (najwyżej nazwa sekcji),
bez danych osób, bez ocen firmy. Zrzuty zostają w skarbcu (użytek wewnętrzny), nie trafiają do projektu ani do klienta.

```markdown
---
typ: zrodlo
tagi: [inspiracja, <branza>]
utworzono: <RRRR-MM-DD>
zmieniono: <RRRR-MM-DD>
status: aktualna
zrodlo: https://<domena>
agent: jarvo-web
wazne_do: <RRRR-MM-DD + 12 miesięcy>   # strony zmieniają wygląd: po terminie zbierz ponownie albo usuń kartę
---
# <domena> (<branża>)

**Jedno zdanie: czym jest firma i co strona robi najlepiej** (np. „biuro nieruchomości premium; wyszukiwarka ofert w hero”).
Wskazał: właściciel | Web (`web_search`), <data>.

## Układ
- Hero: <zdjęcie / wideo / tekst>, <co jest w pierwszym ekranie: H1, wyszukiwarka, CTA>, <wysokość: cały ekran / część>.
- Sekcje po kolei: <oferty> → <o firmie> → <opinie> → <kontakt> (nazwy funkcji, nie teksty strony).
- Nawigacja i mobile: <menu, przyklejony nagłówek, CTA na telefonie>.

## Styl (z DESIGN.md)
- Paleta: <tło>, <tekst>, <akcent> (hex), proporcje: <dużo bieli, akcent tylko w CTA>.
- Fonty: <nagłówki>, <tekst>; skala: <H1 px / tekst px>.
- Odstępy i siatka: <sekcje co … px, kolumny, zaokrąglenia>.
- Zdjęcia i ruch: <własne zdjęcia ofert, pełna szerokość; animacje>.

## Co bierzemy
- <wzorzec 1: dlaczego działa dla tej branży>
- <wzorzec 2>

## Czego unikamy
- <np. karuzela w hero, mały kontrast szarego tekstu (wcag.json)>

## Powiązane
- [[inspiracje/_hub-inspiracje|Inspiracje]] · [[agenci/jarvo-web/_hub-web|Web]]
- [[inspiracje/strony/<branza>/<domena>/DESIGN|DESIGN.md]]
```
