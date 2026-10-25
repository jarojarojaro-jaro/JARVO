---
name: formularze
description: "Formularz na ekranie: pola, listy, sprawdzenie wartości"
version: 1.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [computer-use, forms, input, select, verify]
    related_skills: [praca-na-ekranie, oddaj-ekran]
  jarvo:
    agent: jarvo-operator
    autonomy: A1
    reviewed: "2026-10-25"
---

# Formularze

Wypełniasz formularz pole po polu i każde sprawdzasz. Wysłanie formularza, który loguje, płaci, zamawia, wysyła
albo publikuje, robi właściciel: wejście Komputera i tak zatrzyma taki przycisk (`przycisk_wrazliwy`) i Enter
w takim formularzu (`formularz_wrazliwy`).

## Przed wypełnieniem
1. Dane tylko z karty albo od właściciela. Czego brakuje, nie zmyślasz: pytasz (`clarify` na Telegramie) albo
   zostawiasz pole puste i piszesz w raporcie.
2. `capture` `mode: ax`: lista pól (rola `entry`, `combo box`, `check box`, `radio button`), ich napisy i przycisk
   wysyłki. Zapisz w `todo` mapę „pole → wartość”.
3. Pola, których nie wypełniasz nigdy: hasło, numer karty, CVV, BLIK, PIN, kod SMS, 2FA, kod jednorazowy, token.
   Wejście je zatrzyma (`pole_wrazliwe`), a Ty od razu robisz `oddaj-ekran`.

## Wypełnianie
- Pole tekstowe: klik w pole (`element`, w tle), potem `type` z `delivery_mode: foreground`. Pisanie bez fokusu
  wejście blokuje (`brak_fokusu`), więc zawsze najpierw klik w to pole. Pole z wartością: zaznacz wszystko `key`
  `ctrl+a`, potem `type` (oba na wierzchu).
- Lista wyboru (`combo box`, `select`): `set_value` z napisem opcji, bez otwierania menu.
- Pole z podpowiedziami (adres, miasto): `type`, `wait` 1 s, `capture`, klik w właściwą podpowiedź.
- Pole daty: najpierw spróbuj `type` w formacie strony (np. `19.10.2026`); kalendarz klikasz tylko, gdy pole nie
  przyjmuje tekstu.
- Pole wieloliniowe: nowa linia to Shift+Enter (`key` `shift+return` albo `\n` w środku tekstu `type`). Zwykły Enter i Ctrl+Enter traktuj jak wysyłkę: w formularzu z przyciskiem płatności, logowania albo
  wysyłki i w polu poza formularzem (czat, komentarz) robi to właściciel (`formularz_wrazliwy`,
  `wysylka_bez_formularza`).
- Kolejne pole: `key` `tab` osobno albo klik w pole. Tab i inne znaki sterujące w tekście `type` wejście odrzuca
  (`znak_sterujacy`), a Enter w środku tekstu pola jednowierszowego też (`enter_w_srodku`).
- Skrótów Alt+litera (accesskey strony) nie używasz: wejście je odrzuca (`accesskey`); klikasz przycisk elementem.
- Schowek należy do właściciela: nie wklejasz (Ctrl+V, Shift+Insert) i nie kopiujesz (`schowek`), tekst piszesz
  przez `type`. Skróty okna przeglądarki (pasek adresu, nowa karta, otwórz plik, zapisz, drukuj) wejście odrzuca
  (`skrot_przegladarki`): adres otwierasz przez `launch_app` z `urls` albo linkiem na stronie.
- Pole wyboru pliku (załącznik, zdjęcie, faktura) wypełnia właściciel (`wybor_pliku`): przygotuj resztę
  formularza i `oddaj-ekran` z nazwą pliku, który ma wybrać.
- Baner albo nakładka strony przykrywa pole lub przycisk (`element_przesloniety`): zamknij ją zwykłym przyciskiem
  (np. „Zamknij”, „Tylko niezbędne”), przewiń, zrób nowy `capture` i dopiero wtedy klikaj.
- Zgody i regulaminy (`check box` z „Akceptuję”, „Zgadzam się”): zaznacza właściciel, chyba że karta wprost mówi
  inaczej dla tej jednej zgody; zgody marketingowe zawsze zostawiasz puste.

## Sprawdzenie
Po każdym polu `capture_after: true`: wartość w drzewie ma być ta, którą wpisałeś (bez obciętych znaków, z polskimi
literami). Strona pokazuje błąd pola („Nieprawidłowy NIP”) → popraw raz według komunikatu; drugi błąd → raport.
Na koniec pełny `capture` `som` całego formularza (przewiń, jeśli długi) i porównanie z mapą z `todo`.

## Wysłanie
- Formularz zwykły (wyszukiwanie, filtr, kalkulator, zapis szkicu): wysyłasz sam.
- Formularz wrażliwy (logowanie, rejestracja, zakup, płatność, wysyłka wiadomości, publikacja, zgoda): nie
  wysyłasz. `oddaj-ekran` z prośbą „sprawdź formularz X i kliknij Y”, a w raporcie lista wpisanych pól (bez
  danych wrażliwych).
