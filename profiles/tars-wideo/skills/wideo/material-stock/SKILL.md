---
name: material-stock
description: "Darmowe ujęcia i zdjęcia stock (Pexels, Pixabay) z licencją."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [video, stock, pexels, pixabay, footage, license]
    related_skills: [krotki-film, dobor-ujec, wideo-ai]
  tars:
    agent: tars-wideo
    autonomy: A1
    reviewed: "2026-09-28"
---

# Materiał stock (Pexels, Pixabay)

Darmowe ujęcia wideo i zdjęcia do scen: `$HERMES_HOME/scripts/stock.py`. Klucz: `PEXELS_API_KEY` albo `PIXABAY_API_KEY`
(darmowy, dashboard → Keys przy profilu głównym). Wyniki i pliki trafiają do wspólnego cache, drugi raz bez pobierania.

## Kiedy użyć
- Scena potrzebuje realnego obrazu (produkt ogólny, miejsce, czynność, klimat), a użytkownik nie dał materiału.
- Tło pod tekst, b-roll do nagrania użytkownika, zdjęcia do scen z ruchem kamery.

## Kiedy NIE używać
- Konkretny produkt, lokal, osoba z marki: stock pokaże „podobny”, nie ten. Prośba o zdjęcia/nagrania (przez TARS-a) albo AI z referencją.
- Brak klucza: `film.py sprawdz` zgłosi błąd; wtedy pliki użytkownika, `wideo-ai` albo plansze (`kolor`).

## Kroki
1. **Zapytanie:** 2–4 słowa po angielsku, obiekt + ujęcie + nastrój („barista pouring milk slow motion”, „city night rain”).
   Polskie zapytania też działają (locale pl-PL), ale angielskie dają więcej wyników.
2. **Szukaj z arkuszem:**
   `python3 $HERMES_HOME/scripts/stock.py szukaj "barista latte art" --format 9:16 --min-sek 5 --arkusz out/wideo/kandydaci-s2.jpg`
   (numery na arkuszu = kolejność na liście). Zdjęcia: `--typ zdjecie`.
3. **Obejrzyj** arkusz (`dobor-ujec`, `vision_analyze`) i wybierz id; słabe wyniki → zmień zapytanie (synonim, szerszy plan).
   - ✅ Punkt kontrolny: orientacja zgodna z formatem, min. 1080 px krótszego boku, długość ≥ sceny.
4. **Do planu** wpisz `"ujecie": {"stock_id": "pexels:123"}` (film.py pobierze i przytnie). Ręcznie:
   `stock.py pobierz pexels:123 --format 9:16 --do out/wideo/src`.
5. **Licencja:** obok pliku `.json` (autor, strona, licencja); `film.json` zbiera to dla wszystkich scen. Do RAPORT.md
   przepisz listę źródeł; podpis autora w opisie posta mile widziany (Pexels), niewymagany.

## Licencje w skrócie
- Pexels i Pixabay: darmowe użycie komercyjne bez podpisu. Nie wolno: sprzedawać materiału bez zmian, sugerować,
  że osoba z kadru poleca produkt, używać rozpoznawalnych osób w kontekście wrażliwym, prezentować cudzych znaków
  towarowych z kadru jako własnych.
- Rozpoznawalna twarz w centrum reklamy produktu → wybierz inne ujęcie albo kadr bez twarzy.

## Wyjścia
- wybrane `stock_id` w `out/wideo/src/plan.json`, arkusze kandydatów `out/wideo/kandydaci-*.jpg`, źródła w `film.json`.

## Definition of Done
- [ ] każde ujęcie stock obejrzane (arkusz) i dobrane do zdania sceny,
- [ ] bez znaków wodnych, obcych logo, cudzego tekstu i przypadkowych twarzy w centrum,
- [ ] autor, strona i licencja każdego ujęcia w `film.json` i RAPORT.md.
