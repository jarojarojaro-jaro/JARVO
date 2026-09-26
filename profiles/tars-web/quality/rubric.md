# Rubryka: tars-web

## Blokujące (poprawki obowiązkowe)
- Build nie przechodzi albo podglądu nie da się uruchomić instrukcją z RAPORT.md.
- Lighthouse mobile < 90 w którejś kategorii bez uzasadnienia i planu (sędzia mierzy sam w rundzie 2).
- Poziome przewijanie lub nachodzące elementy na 375, 768 albo 1440 px.
- Brak w `<head>`: title, description, canonical, lang, viewport, favicon, OG title/image.
- Krytyczne lub poważne naruszenia axe (kontrast, brak etykiet formularzy, obrazy bez alt w treści).
- Martwe linki wewnętrzne.
- Niezgodność z brand kitem (kolory/fonty spoza kitu bez uzasadnienia).
- Jakakolwiek akcja A2 bez zgody (wdrożenie na produkcję, push na główną gałąź użytkownika, DNS).
- Raport z liczbami, których sędzia nie może odtworzyć.

## Ważne
- Obrazy bez AVIF/WebP, bez `srcset`/wymiarów.
- Brak JSON-LD tam, gdzie treść na to pozwala (Organization, Product, FAQ).
- Tekst roboczy nieoznaczony jako `[SZKIC]`.

## Uwagi (nie blokują)
- Preferencje estetyczne w granicach brand kitu, drobne różnice wyników Lighthouse (±3 pkt).
