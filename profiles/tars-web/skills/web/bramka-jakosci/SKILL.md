---
name: bramka-jakosci
description: "Przed oddaniem strony: rubryka designu 0–100 i testy wrogie."
version: 1.0.0
author: "Jarvo (rubryka i werdykt na bazie oh-my-hermes, MIT)"
license: MIT
metadata:
  hermes:
    tags: [web, design, quality, visual-qa, accessibility]
    related_skills: [nowa-strona, landing-produktowy, audyt-strony, frontend-design, design-md, impeccable]
  tars:
    agent: tars-web
    autonomy: A1
    reviewed: "2026-09-28"
---

# Bramka jakości (design i odporność strony)

Lighthouse i axe mówią, czy strona jest **poprawna**. Ta bramka mówi, czy jest **dobra**: czy przeszłaby
u seniora product designu (klasa Linear / Stripe / Supabase). **Technicznie czysta, ale płaska nie przechodzi.**

## Kiedy użyć
- zawsze przed `kanban_request_review` dla nowej strony, landingu albo przebudowy wyglądu,
- gdy karta mówi „premium”, „ma robić wrażenie”, „na nagrodę”.

## Kiedy NIE używać
- sam audyt cudzej strony bez zmian → `audyt-strony` (bramkę możesz dołączyć jako ocenę, bez pętli poprawek),
- poprawka techniczna bez zmiany wyglądu (meta, favicon, obrazy).

## Kroki
1. **Kierunek.** Nazwij kierunek z karty i brand kitu: *operacyjny* (narzędzie, dane), *minimalistyczny/edytorski*,
   *premium/miękki* albo *odważny/ekspresyjny*. Oceniasz w jego ramach: narzędzie nie traci punktów za brak blichtru,
   strona premium traci.
2. **Zrzuty.** `node $HERMES_HOME/scripts/screenshots.cjs <url> out/jakosc/runda-N --full` (375/768/1440) plus stany:
   hover, fokus (Tab), formularz z błędem, pusty stan, jeśli strona je ma. Ocena bez świeżych zrzutów nie istnieje.
3. **Testy wrogie.** `node $HERMES_HOME/scripts/hostile.cjs <url> out/jakosc/wrogie` → `hostile.json`
   (wolne łącze, brak JS, 320 px, sama klawiatura, długie polskie słowa, reduced motion, konsola).
   `offline` (zasoby z innych serwerów) liczy się, gdy DoD mówi „offline”, „jeden plik” albo „bez zależności
   zewnętrznych”. Scenariusz z `not_run` to brak pomiaru, nie zaliczenie.
4. **Ocena rubryką.** Przejdź 10 osi z `references/rubryka.md`. Każda oś: zaliczona albo różnica z dowodem
   (który zrzut, co widać) i **najmniejszą zmianą**, która ją naprawi.
5. **Werdykt** w formacie z `references/werdykt.md`: liczba 0–100, `PASS` / `REVISE` / `BLOCK`, lista różnic.
   Zapisz do `out/jakosc/werdykt-runda-N.json`.
6. **Pętla.** Poniżej 90 → wprowadź zmiany z listy różnic, zrób nowe zrzuty (runda N+1) i oceń od nowa.
   Ponowna ocena tych samych zrzutów to nie runda. Najwyżej 3 rundy; potem oddajesz z ostatnim werdyktem i listą
   niezamkniętych różnic w `metadata.risks` (nie udajesz `PASS`).
7. **„Na nagrodę”** (tylko gdy karta o to prosi): dodatkowo `references/poziom-nagrody.md`.

## Wyjścia
- `out/jakosc/werdykt-runda-N.json`, zrzuty rund, `out/jakosc/wrogie/hostile.json`,
- w `out/RAPORT.md` sekcja „Jakość”: kierunek, wynik ostatniej rundy, co poprawiono między rundami, wyniki testów wrogich.

## Definition of Done
- ostatnia runda ≥ 90 i `PASS`, oparta na zrzutach z tej samej wersji strony, co oddawana,
- testy wrogie bez porażek (poza `offline`, gdy DoD go nie wymaga) albo każda porażka opisana w `metadata.risks`,
- w `metadata.dod_check` punkt jakości ma dowód: plik werdyktu i wynik liczbowy.

## Zasady
- Najpierw treść i hierarchia, potem polerowanie: piękna strona z błędną treścią odpada pierwsza.
- Wynik to liczba całkowita, a nie przymiotnik; różnica bez poprawki i poprawka bez różnicy się nie liczą.
- Brand kit wygrywa z gustem: oś „coś własnego” nie uzasadnia koloru spoza kitu.
