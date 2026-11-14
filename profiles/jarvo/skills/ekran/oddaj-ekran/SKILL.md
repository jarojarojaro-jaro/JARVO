---
name: oddaj-ekran
description: "Krok właściciela przez VNC: płatność, CAPTCHA po próbie"
version: 1.3.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [computer-use, handoff, login, payment, captcha, human-in-the-loop]
    related_skills: [praca-na-ekranie, formularze]
  jarvo:
    agent: jarvo
    autonomy: A1
    reviewed: "2026-11-14"
---

# Oddaj ekran właścicielowi

Kroki właściciela: płatność, zakup, zamówienie, wysłanie wiadomości do ludzi, publikacja i usunięcie konta bez linii
`ZGODA WŁAŚCICIELA` w karcie (w rozmowie: bez polecenia właściciela na tę akcję); CAPTCHA, która nie przeszła po
Twojej próbie; wybór pliku z jego dysku. Logowanie, rejestrację, hasło i kod SMS robisz sam (Ty, Jarvo).
Przygotowujesz wszystko do kroku właściciela i prosisz go dokładnie o ten jeden krok. Właściciel robi go przez VNC
na pulpicie serwera, gdzie okno Komputera Jarva jest widoczne.

## Kiedy
- Wejście Komputera odmówiło z `code: wymaga_czlowieka` (`next_step: ask_owner`).
- Widzisz na ekranie krok z listy wyżej, zanim w niego klikniesz (nie czekaj na odmowę).
- Serwis odmówił automatowi po Twojej próbie (CAPTCHA nie przeszła, „potwierdź, że nie jesteś robotem”, blokada).
- Przeglądarka Jarva (Komputer natywnie) dokłada kroki właściciela: wybór pliku z jego dysku (`wybor_pliku`)
  i OK w oknie potwierdzenia płatności, zakupu albo wysyłki bez zgody w karcie (`okno_wrazliwe`; Anuluj klikasz
  sam). Prośba jak zawsze: gdzie i co kliknąć albo który plik wybrać (nazwa, nie zawartość).

## Jak
1. `capture` `mode: som`: ekran w stanie gotowym do kroku właściciela (formularz wypełniony, koszyk z sumą).
2. `komputer` akcja `oddaj`, `prosba`: jedno zdanie, gdzie i co kliknąć, bez haseł i danych osobowych.
   Dobrze: „Przez VNC na pulpicie serwera kliknij obrazki w CAPTCHA na proton.me i daj znać”. „Sprawdź koszyk
   (2 produkty, 318 zł) i kliknij Zapłać”. Źle: „Coś się zablokowało”.
3. Komputer staje (pauza z Twoją prośbą). Wznowić może tylko właściciel; Ty nie próbujesz.
4. Karta kanbana: `kanban_block` z tym samym zdaniem i `screenshot_path`. Rozmowa (HQ, Telegram): napisz prośbę
   i dołącz zrzut (na Telegramie przez MEDIA).
5. Po wznowieniu: najpierw `capture` (właściciel mógł zmienić ekran), dopiero potem dalsza praca.

## Nigdy
- Hasła i kodu nie powtarzasz w czacie, pliku ani raporcie. Hasło od właściciela wpisujesz w pole i zapisujesz
  w menedżerze haseł przeglądarki; kod SMS czytasz z telefonu.
- Nie szukasz drogi obok odmowy (punkt zamiast elementu, klawiatura zamiast kliknięcia, inna strona tego samego
  serwisu).
- Z zalogowanej sesji właściciela korzystasz tylko w zakresie zadania.
