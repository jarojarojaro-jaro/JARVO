---
name: weekly-review
description: "Przegląd tygodnia: jakość floty, wnioski, propozycje."
version: 1.5.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fleet, retro, quality, cron]
    related_skills: [fleet-improvement, mission-ledger]
  jarvo:
    agent: jarvo
    autonomy: A0
    reviewed: "2026-10-13"
---

# Przegląd tygodnia

Rutyna cron (niedziela wieczorem). Skrypt `fleet_report.py --mode weekly` dał Ci dane z 7 dni,
w tym `quality`: dla każdego agenta liczba zakończonych kart, recenzji, poprawek i akceptacji
za pierwszym razem, oraz `liczby` (`liczby.py`, bez modelu): eskalacje (pytania, poza zakresem, porzucone),
awarie pracownika, cisza (karty bez sygnału życia, blokady bez powodu) i tokeny każdego agenta.

## Co przygotować
1. **Wynik tygodnia:** zamknięte misje (efekty, nie karty), co utknęło i dlaczego.
2. **Jakość agentów:** akceptacja za 1. razem = `first_pass / done`. Poniżej 60% → przejrzyj
   komentarze sędziego z tych kart (`kanban_show`) i znajdź **powtarzający się** wzorzec błędu.
3. **Wnioski → księga lekcji → propozycje** (skill `fleet-improvement`): nowe obserwacje dopisz do
   `@@KNOWLEDGE_DIR@@/fleet/lekcje.md`. `lekcje` z danych (`lekcje.py`, 0 tokenów) mówi resztę: `przeterminowane`
   usuń z księgi, propozycje (maks. 3) tylko z `gotowe`, każda z dowodem (które karty, jaki błąd). Dla `wdrozone`
   jedna linia skutku: `zaszkodziło` albo `uwaga` o powrotach błędu → propozycja poprawki albo cofnięcia, `pomogło`
   → krótko, `brak pomiaru` → bez wniosku. `bledy_formatu` → popraw te linie w księdze.
4. **Poczekalnia skilli:** `poczekalnia` z danych (`poczekalnia.py`): skille, które agenci sami sobie dopisali i czekają
   na zgodę. Każdy wpis oceń (skill `fleet-improvement`, „Poczekalnia skilli”) i daj w propozycjach: zatwierdzić albo
   odrzucić, z odciskiem. `blokuje: true` → tylko odrzucić. `brama_wylaczona` niepusta → linia „⚠” na górze. Pusta → pomiń.
5. **Pamięć:** przejrzyj wpisy swojej pamięci. Wpis bez źródła i daty uzupełnij albo usuń; wpis, który przeczy
   nowszym faktom, popraw. Nic nie usuwasz z `USER.md` bez pytania użytkownika.
6. **Koszty:** tokeny z `liczby.tokeny` (i `tokeny_na_karte`) w jednej linii; cisza i awarie wymień z numerami kart,
   bo to praca, która przepadła bez śladu.
7. **Skarbiec wiedzy (synteza tygodnia, jedyna praca drogiego modelu w skarbcu):** przeczytaj wpisy z ostatnich 7 dni
   w `@@KNOWLEDGE_DIR@@/LOG.md` i raport `@@KNOWLEDGE_DIR@@/LINT.md`. Zgłoś szkic `wiedza_zapisz(typ="rozmowa",
   tytul="Tydzień floty RRRR-MM-DD", zrodlo="LOG.md i LINT.md skarbca; strona <strona.plik>")` z trzema sekcjami: **co się zmieniło** (nowe
   i zaktualizowane notatki, po jednym zdaniu), **co dryfuje** (sprzeczności, przeterminowane, sieroty z lintu), **co warto
   zbadać** (pytania, na które skarbiec nie ma notatki). Orzeczenia i lekcje z ≥ 3 potwierdzeniami zgłoś w propozycjach
   `fleet-improvement` jako kandydatów do SOUL albo skilla (repo jest źródłem prawdy). Brak wpisów w LOG z 7 dni → pomiń.
8. **Styl wiadomości:** `prosty_polski` z danych (skill `prosty-polski`, liczy `prosty.py`): ile Twoich wiadomości do
   właściciela było w normie i co zawodziło najczęściej, w jednej linii. Poniżej 80% w normie → lekcja w księdze
   (`fleet-improvement`) z dwoma przykładami potknięć. Brak wiadomości → pomiń.
9. **Evals (pomiar ze stagingu, docs/RSI.md):** `evals` z danych: na agenta wynik ostatniego pełnego przebiegu
   (`score` 0..1, `zaliczone`/`n`), wynik zbioru odłożonego (`odlozony`), `seria` z poprzednich przebiegów i `kanarek`.
   `nieocenione` > 0 albo `score` null = przebieg bez sędziego: to nie pomiar jakości, nie wyciągaj z niego wniosków.
   Jedna linia: agenci ze spadkiem w `seria` (≥ 0,05) albo `odlozony` niższym o ≥ 0,1 od `score`. Spadek to sygnał
   do `fleet-improvement` (dowód: daty i commity z `evals`), nie wyrok. `kanarek: true` → osobna linia na górze:
   „⚠ Alarm kanarka u <agent>: agent czytał pliki evals, wyniki niewiarygodne, sprawdź ślady przebiegu”.
   Brak `evals` albo pusty → pomiń (evals uruchamia właściciel na stagingu: `scripts/evals-staging.sh`).
10. **Strona tygodnia:** `strona` z danych (`raport_strona.py`, bez modelu): te same liczby jako strona z kaflami
   i paskami (jakość i tokeny na agenta, zrobione, stoi, w toku). Wiadomość niesie `strona.link` w ostatniej linii;
   wniosków nie przepisuj na stronę, zostają w wiadomości. Brak `strona` albo `strona.blad` → bez linii, błąd w jednym zdaniu.

## Format
```
📊 Tydzień floty
Zrobione: <2–4 linie>
Jakość: sherlock 5/6 za 1. razem, web 3/5 (powtarza się: brak zrzutów mobile), studio 4/4
Evals: web 0,82 (było 0,88, spadek po a1b2c3d), reszta bez zmian
Lekcje: 2 gotowe, 1 wdrożona pomogła (studio +0,1), 1 do usunięcia
Poczekalnia: web chce dodać skill `zrzuty-mobile` (sam po zadaniu, skan czysty), odcisk 3f9c0a1b2d4e
Skarbiec: +7 notatek, 1 sprzeczność do rozstrzygnięcia (link w zakładce Wiedza)
Styl: 18/20 wiadomości prostym polskim (najczęściej: za długie zdania)
Proponuję ulepszyć:
1. <agent>: <zmiana> (<dowód>)
Decyzja: wdrożyć propozycje 1–2? Zatwierdzić skill z poczekalni? (nic nie wchodzi bez Twojego „ok”)
Strona tygodnia: <strona.link>
```

Brak aktywności w tygodniu → `[SILENT]`.
