---
name: onboarding-interview
description: "Wywiad startowy: poznaj użytkownika, zapisz jego profil."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [fleet, onboarding, user-profile, memory]
    related_skills: [mission-ledger]
  tars:
    agent: tars
    autonomy: A1
    reviewed: "2026-09-26"
---

# Wywiad startowy

Używaj przy pierwszej rozmowie (pusty profil użytkownika) albo gdy użytkownik powie „poznajmy się”
lub „zaktualizuj, co o mnie wiesz”. Cel: flota zna użytkownika od pierwszego dnia i nie pyta w kółko o to samo.

## Przebieg (rozmowa, nie formularz)
Maksymalnie 3 pytania w jednej wiadomości, w 3–4 rundach. Każdą rundę zaczynasz od krótkiego podsumowania tego, co już wiesz.

1. **Kim jesteś:** czym się zajmujesz, firma/marki (nazwy, strony WWW), rola, miasto/strefa czasowa.
2. **Cele:** na czym zależy w najbliższych 3 miesiącach, jakie projekty są w toku.
3. **Styl pracy:** jak ma do Ciebie mówić flota (długość, ton, emotki), kiedy przeszkadzać, a kiedy nie, godziny ciszy.
4. **Zasoby i granice:** jakich narzędzi/kont używasz (Notion, Google, Canva, hosting stron), czego flocie nie wolno, budżety.

## Zapis
- Plik wspólny: `@@KNOWLEDGE_DIR@@/user/USER.md` (szablon: `references/USER.template.md`).
  Czytają go wszyscy agenci, więc piszesz **tylko to, co przydatne w pracy**, bez danych wrażliwych (hasła, numery dokumentów, zdrowie).
- Pamięć TARS-a: najważniejsze preferencje komunikacji i stałe zasady (krótko).
- Marki z adresami stron → zaproponuj misję „brand kit” (`dispatch-playbook`, wzorzec 5).

## Na koniec
Pokaż użytkownikowi streszczenie (5–8 punktów) i zapytaj, czy się zgadza. Zmiany nanieś od razu.
