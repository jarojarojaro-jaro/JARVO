---
name: generacja-ai
description: "Obrazy z AI (OpenRouter): prompt, spójność serii, koszt."
version: 1.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [ai, image-generation, openrouter]
    related_skills: [image, grafika-social]
  jarvo:
    agent: jarvo-studio
    autonomy: A1
    reviewed: "2026-09-28"
---

# Generacja AI (obrazy)

Narzędzie: `image_generate` (wtyczka Hermesa, dostawca OpenRouter, domyślny łańcuch jakościowy wtyczki).
Parametry i aktualne możliwości modelu widać w schemacie narzędzia. Wideo z AI robi `jarvo-wideo` (skill `wideo-ai`).

## Kiedy AI, a kiedy kod
- **AI:** zdjęcia produktowe w scenach, ilustracje, tła, klimat, b-roll, warianty koncepcji.
- **Kod (`grafika-social`):** wszystko z tekstem, logo, liczbami, ceną. AI zniekształca litery, więc tekst zawsze nakładasz kodem.

## Prompt (struktura)
```
[Temat] + [Kompozycja/kadr] + [Światło] + [Styl/medium] + [Paleta z brand kitu] + [Nastrój] + [Proporcje]
Negatywy: bez tekstu, bez logotypów, bez znaków wodnych, bez zniekształconych dłoni/twarzy
```
Przykład: „Szklana butelka serum na kamiennym postumencie, kadr 3/4, miękkie światło z lewej, fotografia produktowa,
paleta: głęboki granat i złoto (#0d1b3e, #c9a227), spokojny, premium, 4:5, bez tekstu”.

## Spójność serii
- ten sam opis stylu i palety w każdym prompcie (zapisz go w `out/grafiki/STYL.md`),
- obraz referencyjny (image-to-image), jeśli model to obsługuje,
- ta sama proporcja i kadrowanie w serii.

## Budżet i jakość
- najpierw 2–4 szkice → wybór → finał; limit generacji z karty (domyślnie: 12 obrazów; ponad limit strażnik wtyczki
  wymaga zgody człowieka, a bez niej zgłoś blokadę z liczbą potrzebnych generacji),
- każdą generację zapisuj z promptem i modelem w `out/grafiki/generacje.jsonl`,
- sprawdź wynik (vision): artefakty, dłonie, twarze, czytelność produktu. Wadliwe odrzucasz, nie „poprawiasz tekstem”.

## Prawa i etyka
Bez wizerunków realnych osób, bez stylu konkretnych żyjących artystów „w stylu X”, bez logotypów cudzych marek.
Informacja w RAPORT.md, które elementy są wygenerowane przez AI (część platform wymaga oznaczania).
