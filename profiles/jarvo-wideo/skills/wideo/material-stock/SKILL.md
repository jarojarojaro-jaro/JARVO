---
name: material-stock
description: "Ujęcia, zdjęcia i dźwięki stock z licencją."
version: 1.2.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, stock, pexels, pixabay, openverse, sound, footage, license]
    related_skills: [krotki-film, dobor-ujec, wideo-ai]
  jarvo:
    agent: jarvo-wideo
    autonomy: A1
    reviewed: "2026-10-05"
---

# Materiał stock (Pexels, Pixabay, Openverse)

Darmowe ujęcia wideo i zdjęcia do scen: `"$HERMES_HOME/scripts/stock.py"`. Klucz: `PEXELS_API_KEY` albo `PIXABAY_API_KEY`
(darmowy, dashboard → Keys przy profilu głównym). Wyniki i pliki trafiają do wspólnego cache, drugi raz bez pobierania.

## Kiedy użyć
- Scena potrzebuje realnego obrazu (produkt ogólny, miejsce, czynność, klimat), a użytkownik nie dał materiału.
- Tło pod tekst, b-roll do nagrania użytkownika, zdjęcia do scen z ruchem kamery.

## Kiedy NIE używać
- Konkretny produkt, lokal, osoba z marki: stock pokaże „podobny”, nie ten. Prośba o zdjęcia/nagrania (przez Jarva) albo AI z referencją.
- Brak klucza: `film.py sprawdz` zgłosi błąd; wtedy pliki użytkownika, `wideo-ai` albo plansze (`kolor`).

## Kroki
1. **Zapytanie:** 2–4 słowa po angielsku, obiekt + ujęcie + nastrój („barista pouring milk slow motion”, „city night rain”).
   Polskie zapytania też działają (locale pl-PL), ale angielskie dają więcej wyników.
2. **Szukaj z arkuszem:**
   `@@PY@@ "$HERMES_HOME/scripts/stock.py" szukaj "barista latte art" --format 9:16 --min-sek 5 --arkusz out/wideo/kandydaci-s2.jpg`
   (numery na arkuszu = kolejność na liście). Zdjęcia: `--typ zdjecie`.
3. **Obejrzyj** arkusz (`dobor-ujec`, `vision_analyze`) i wybierz id; słabe wyniki → zmień zapytanie (synonim, szerszy plan).
   - ✅ Punkt kontrolny: orientacja zgodna z formatem, min. 1080 px krótszego boku, długość ≥ sceny.
     Zdjęcie z ruchem kamery (`ruch` zoom, oddal, panorama) musi być większe od kadru o powiększenie ruchu
     (1,12×; w 9:16 co najmniej 1210×2151); `film.py sprawdz` ostrzega o mniejszym.
4. **Do planu** wpisz `"ujecie": {"stock_id": "pexels:123"}` (film.py pobierze i przytnie). Ręcznie:
   `stock.py pobierz pexels:123 --format 9:16 --do out/wideo/src`.
5. **Licencja:** obok pliku `.json` (autor, strona, licencja); `film.json` zbiera to dla wszystkich scen. Do RAPORT.md
   przepisz listę źródeł; podpis autora w opisie posta mile widziany (Pexels), niewymagany.

## Licencje w skrócie
- Pexels i Pixabay: darmowe użycie komercyjne bez podpisu. Nie wolno: sprzedawać materiału bez zmian ani
  rozpowszechniać samego pliku (żyje tylko w filmie), sugerować, że osoba z kadru poleca produkt, pokazywać
  rozpoznawalnych osób w złym świetle, używać rozpoznawalnych znaków towarowych z kadru w reklamie towarów i usług,
  wprowadzać w błąd. Prawa osób trzecich w kadrze (logo, budynek, dzieło sztuki) sprawdzasz sam.
- Rozpoznawalna twarz w centrum reklamy produktu → wybierz inne ujęcie albo kadr bez twarzy.

## Dźwięki (Openverse)
`stock.py szukaj "<słowo>" --typ dzwiek` szuka efektów, tła i muzyki w Openverse (bez klucza; z indeksu tylko
Freesound, bo Wikimedia to głównie nagrania wymowy słów). Domyślnie CC0, `--licencja by` dokłada CC BY z podpisem
(`atrybucja` w `.json`); NC, ND i SA nigdy. `pobierz openverse:<id> --typ dzwiek` czyta stronę pliku: usunięty
dźwięk albo inna licencja = odmowa. Kolejność i zasady dźwięku: skill `lektor-i-dzwiek` (najpierw biblioteka CC0).

## Pułapki poza `stock.py`
`stock.py` (API) zwraca tylko darmowy materiał Pexels i Pixabay oraz dźwięki Freesound z Openverse. Gdy szukasz w przeglądarce albo właściciel
podsyła link, licencję czytasz na stronie tego konkretnego pliku, nie z pamięci, i zapisujesz link oraz nazwę
licencji w RAPORT:
- **Pixabay:** pierwsze wyniki wyszukiwarki to sponsorowane zdjęcia iStock (płatne, inna licencja). Bierzesz tylko
  pliki z pixabay.com.
- **Unsplash:** zdjęcia oznaczone Unsplash+ są płatne; darmowe tylko ze zwykłą licencją Unsplash.
- **Vecteezy, Freepik:** darmowe pliki wymagają podpisu autora, a „Pro” i „Premium” są płatne. W filmie bez podpisu
  ich nie bierzesz.
- **Wikimedia Commons:** każdy plik ma własną licencję; CC BY i CC BY-SA wymagają podpisu (BY-SA także tej samej
  licencji dla przeróbki), więc do reklamy zwykle odpadają. Bez wahania tylko CC0 i domena publiczna.
- **Mixkit:** tylko „Free License”; wideo z licencją „Restricted” pomijasz.
- **Muzyka z sieci** (Pixabay Music, YouTube Audio Library): część utworów ma zgłoszenia Content ID; link do strony
  utworu w RAPORT pozwala właścicielowi odwołać zgłoszenie.

## Wyjścia
- wybrane `stock_id` w `out/wideo/src/plan.json`, arkusze kandydatów `out/wideo/kandydaci-*.jpg`, źródła w `film.json`.

## Definition of Done
- [ ] każde ujęcie stock obejrzane (arkusz) i dobrane do zdania sceny,
- [ ] bez znaków wodnych, obcych logo, cudzego tekstu i przypadkowych twarzy w centrum,
- [ ] autor, strona i licencja każdego ujęcia w `film.json` i RAPORT.md (dźwięk CC BY: podpis z `atrybucja` także w opisie posta),
- [ ] materiał spoza `stock.py`: licencja odczytana na stronie pliku, link i jej nazwa w RAPORT.md.
