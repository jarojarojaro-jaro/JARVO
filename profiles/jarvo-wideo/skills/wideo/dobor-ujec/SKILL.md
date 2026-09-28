---
name: dobor-ujec
description: "Wybór ujęć okiem: arkusz klatek, ocena, odrzuty."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, vision, footage, selection, quality]
    related_skills: [material-stock, krotki-film, montaz-nagran, kontrola-wideo]
  jarvo:
    agent: jarvo-wideo
    autonomy: A1
    reviewed: "2026-09-28"
---

# Dobór ujęć okiem

Skrypt wybiera szybko, ale nie widzi. Każde ujęcie w finale oglądam na arkuszu klatek narzędziem `vision_analyze`.

## Kiedy użyć
- Przed finałem każdego filmu ze stockiem, generacją AI albo wieloma nagraniami użytkownika.
- Gdy trzeba wybrać najlepszy dubel, najlepszy fragment długiego ujęcia albo miniaturę.

## Kiedy NIE używać
- Plansze kolorowe i animacje z kodu (widzę je w szkicu, nie w materiałach źródłowych).

## Kroki
1. **Arkusz kandydatów:**
   - stock: `stock.py szukaj "<zapytanie>" --arkusz out/wideo/kandydaci-s<N>.jpg` (numer = kolejność na liście),
   - pliki (nagrania, generacje AI): `python3 $HERMES_HOME/scripts/kadry.py arkusz a.mp4 b.mp4 c.mp4 --klatek 4 -o out/wideo/kandydaci.jpg`
     (rząd = klip, klatki równo rozłożone, podpis `klip.klatka czas`).
2. **Ocena** (`vision_analyze` na arkuszu, pytanie konkretne): dla każdego kandydata 0–2 w kryteriach:
   | Kryterium | 0 | 2 |
   |---|---|---|
   | pasuje do zdania sceny | inny temat | pokazuje dokładnie to, o czym mówi lektor |
   | jakość | nieostre, szum, przepalone | ostre, dobre światło |
   | kadr pod format | ważny obiekt ucięty po przycięciu | obiekt w środkowej 1/3 |
   | czystość | znak wodny, logo, obcy tekst | czyste |
   | ryzyko | rozpoznawalna twarz w centrum, marka | brak |
   Odrzut, gdy „czystość” albo „ryzyko” = 0. Wybór: najwyższa suma; remis → ujęcie z ruchem.
3. **Fragment:** gdy najlepsza część jest w środku klipu, wpisz `"od": <sekunda>` w ujęciu sceny.
   Cięcia w długim nagraniu: `kadry.py sceny nagranie.mp4` (lista ujęć z czasami).
4. **Spójność serii:** podobna temperatura barw i tempo ruchu w sąsiednich scenach; jedna odstająca → wymień.
5. **Zapis decyzji** w `out/wideo/DOBOR.md`: scena, wybrane id/plik, dlaczego, odrzucone i powód (1 linia każde).

## Wyjścia
- `out/wideo/kandydaci*.jpg`, `out/wideo/DOBOR.md`, `stock_id` / `plik` / `od` w planie.

## Definition of Done
- [ ] każde ujęcie w finale obejrzane na arkuszu (vision), z oceną w DOBOR.md,
- [ ] zero odrzutów z kryterium czystości i ryzyka w finale,
- [ ] ważny obiekt mieści się w kadrze po przycięciu do formatu.
