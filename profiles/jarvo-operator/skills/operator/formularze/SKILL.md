---
name: formularze
description: "Formularz na ekranie: pola, listy, sprawdzenie wartości"
version: 1.4.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [computer-use, forms, input, select, verify]
    related_skills: [praca-na-ekranie, oddaj-ekran]
  jarvo:
    agent: jarvo-operator
    autonomy: A1
    reviewed: "2026-11-10"
---

# Formularze

Wypełniasz formularz pole po polu i każde sprawdzasz. Logowanie i rejestrację wysyłasz sam (hasło i kod wpisujesz,
hasło zapisujesz w menedżerze haseł przeglądarki). Formularz, który płaci, zamawia, wysyła wiadomość do ludzi albo
publikuje, wysyłasz tylko z linią `ZGODA WŁAŚCICIELA` w karcie; bez niej wejście zatrzyma przycisk
(`przycisk_wrazliwy`) i Enter (`formularz_wrazliwy`).

## Przed wypełnieniem
1. Dane tylko z karty albo od właściciela. Czego brakuje, nie zmyślasz: pytasz (`clarify` na Telegramie) albo
   zostawiasz pole puste i piszesz w raporcie.
2. `komputer` `patrz` (w kontenerze `capture` `mode: ax`): lista pól (rola `entry`, `combo box`, `check box`,
   `radio button`), ich napisy i przycisk wysyłki. Zapisz w `todo` mapę „pole → wartość”.
3. Pola, których nie wypełniasz nigdy: hasło, numer karty, CVV, BLIK, PIN, kod SMS, 2FA, kod jednorazowy, token.
   Wejście je zatrzyma (`pole_wrazliwe`), a Ty od razu robisz `oddaj-ekran`.

## Wypełnianie
- Natywnie cały formularz to jedna albo dwie paczki `komputer` `kroki` z `obserwuj: true`: na pole
  `{"type_text": {"name": "Imię", "text": "Jan"}}` (cel to pole o tym napisie: sterownik klika w nie i pisze; pole
  z wartością najpierw `{"press_key": {"name": "Imię", "key": "a", "modifiers": ["ctrl"]}}`), na listę
  `{"set_value": {"name": "Kraj", "value": "Polska"}}`. Wejście ocenia każde pole osobno, a krok właściciela
  (pole hasła, karty, kodu) kończy paczkę. W kontenerze (`computer_use`): klik w pole (`element`, w tle), potem
  `type` z `delivery_mode: foreground`; pisanie bez fokusu wejście blokuje (`brak_fokusu`).
- Lista wyboru (`combo box`, `select`): `set_value` z napisem opcji, bez otwierania menu.
- Pole z podpowiedziami (adres, miasto): w jednej paczce `type_text`, `{"wait_for": {"text": "<podpowiedź>"}}`
  i klik w podpowiedź napisem; w kontenerze `type`, `wait` 1 s, `capture`, klik w właściwą podpowiedź.
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
  (`skrot_przegladarki`): adres otwierasz `komputer` akcją `idz` (w kontenerze paskiem adresu: element 0, klik,
  `type` z adresem i nową linią na końcu) albo linkiem na stronie.
- Pole wyboru pliku (załącznik, zdjęcie, faktura) wypełnia właściciel (`wybor_pliku`): przygotuj resztę
  formularza i `oddaj-ekran` z nazwą pliku, który ma wybrać.
- Baner albo nakładka strony przykrywa pole lub przycisk (`element_przesloniety`, w `zasloniety_przez` co leży na
  wierzchu): zamknij ją zwykłym przyciskiem (np. „Zamknij”, „Tylko niezbędne”) i dopiero wtedy klikaj.
- Zgody i regulaminy (`check box` z „Akceptuję”, „Zgadzam się”): zaznacza właściciel, chyba że karta wprost mówi
  inaczej dla tej jednej zgody; zgody marketingowe zawsze zostawiasz puste.

## Sprawdzenie
Po każdym polu paragon kroku: `effect: confirmed` = sterownik odczytał pole i jest w nim Twój tekst; inaczej
obserwacja (`obserwuj: true`, w kontenerze `capture_after: true`) i wartość pola (`= „…”` w `patrz`) ma być ta,
którą wpisałeś (bez obciętych znaków, z polskimi literami).
Strona pokazuje błąd pola („Nieprawidłowy NIP”; paragon pokaże go w `nowe:`) → popraw raz według komunikatu;
drugi błąd → raport.
Na koniec porównanie obserwacji z mapą z `todo`; zrzut całego formularza (`computer_use` `capture` `som`,
przewiń, jeśli długi), gdy właściciel ma go sprawdzić.

## Wysłanie
- Formularz zwykły (wyszukiwanie, filtr, kalkulator, zapis szkicu): wysyłasz sam.
- Logowanie, rejestracja, kod weryfikacyjny: wysyłasz sam.
- Płatność, zakup, wysyłka wiadomości, publikacja: tylko z linią `ZGODA WŁAŚCICIELA` w karcie; bez niej `oddaj-ekran`
  z prośbą „sprawdź formularz X i kliknij Y”, a w raporcie lista wpisanych pól (bez haseł i kodów).
