# Rubryka: jarvo-web

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
- Nowa strona / landing bez werdyktu `bramka-jakosci` albo z ostatnią rundą < 90 (sędzia ocenia sam tą samą
  rubryką w rundzie 1: hierarchia, typografia, rytm odstępów, kolory, stany, coś własnego, ruch z umiarem,
  polski tekst, bez domyślnego gustu modelu, wybrane a nie odziedziczone; start 100, −8 za oś 1–5, −5 za 6–10).
- Porażka testu wrogiego (`out/jakosc/wrogie/hostile.json`: konsola, brak JS, 320 px, klawiatura, długie słowa,
  reduced motion) bez wyjaśnienia; `offline` (zasoby z innych serwerów) blokuje, gdy DoD mówi „offline”,
  „jeden plik” albo „bez zależności zewnętrznych”.

## Ważne
- Obrazy bez AVIF/WebP, bez `srcset`/wymiarów.
- Brak JSON-LD tam, gdzie treść na to pozwala (Organization, Product, FAQ).
- Tekst roboczy nieoznaczony jako `[SZKIC]`.
- Nowa strona / landing bez sekcji „Inspiracje” w `out/PLAN.md`: wybrane 3–5 referencji z uzasadnieniem
  (co bierzemy, czego nie; skill `inspiracje-stron`).

## Uwagi (nie blokują)
- Preferencje estetyczne w granicach brand kitu, drobne różnice wyników Lighthouse (±3 pkt).
