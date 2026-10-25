---
name: oddaj-ekran
description: "Krok właściciela: logowanie, płatność, CAPTCHA, prośba"
version: 1.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [computer-use, handoff, login, payment, captcha, human-in-the-loop]
    related_skills: [praca-na-ekranie, formularze]
  jarvo:
    agent: jarvo-operator
    autonomy: A1
    reviewed: "2026-10-25"
---

# Oddaj ekran właścicielowi

Niektóre kroki robi tylko człowiek: logowanie (także „Zaloguj przez Google”), rejestracja, płatność, zakup,
zamówienie, wysłanie wiadomości, publikacja, zgoda w serwisie, zmiana ustawień konta, CAPTCHA, kod SMS i 2FA.
Ty przygotowujesz wszystko do tego kroku i prosisz właściciela dokładnie o ten jeden krok.

## Kiedy
- Wejście Komputera odmówiło z `code: wymaga_czlowieka` (`next_step: ask_owner`).
- Widzisz na ekranie krok z listy wyżej, zanim w niego klikniesz (nie czekaj na odmowę).
- Serwis odmówił automatowi (CAPTCHA, „potwierdź, że nie jesteś robotem”, blokada): to też blokada, nie zagadka.
- Przeglądarka Jarva (Komputer natywnie) dokłada trzy kroki właściciela: wybór pliku z jego dysku (`wybor_pliku`),
  OK w oknie potwierdzenia płatności, zakupu, logowania albo wysyłki (`okno_wrazliwe`; Anuluj klikasz sam)
  i CAPTCHA (`captcha`). Prośba jak zawsze: gdzie i co kliknąć albo który plik wybrać (nazwa, nie zawartość).

## Jak
1. `capture` `mode: som`: ekran w stanie gotowym do kroku właściciela (formularz wypełniony, koszyk z sumą).
2. `komputer` akcja `oddaj`, `prosba`: jedno zdanie, gdzie i co kliknąć, bez haseł i danych osobowych.
   Dobrze: „W Ekranie HQ zaloguj się do panelu sklepu Acme i daj znać”. „Sprawdź koszyk (2 produkty, 318 zł)
   i kliknij Zapłać”. Źle: „Coś się zablokowało”.
3. Komputer staje (pauza z Twoją prośbą). Wznowić może tylko właściciel; Ty nie próbujesz.
4. Karta kanbana: `kanban_block` z tym samym zdaniem i `screenshot_path`. Rozmowa (HQ, Telegram): napisz prośbę
   i dołącz zrzut (na Telegramie przez MEDIA).
5. Po wznowieniu: najpierw `capture` (właściciel mógł zmienić ekran), dopiero potem dalsza praca.

## Nigdy
- Nie przyjmujesz hasła, kodu ani numeru karty w czacie, nawet od właściciela: prosisz, żeby wpisał je sam
  w Ekranie HQ.
- Nie szukasz drogi obok odmowy (punkt zamiast elementu, klawiatura zamiast kliknięcia, inna strona tego samego
  serwisu).
- Nie klikasz „Zapamiętaj mnie”, „Zaufaj temu urządzeniu” ani zgód za właściciela.
- Z zalogowanej sesji właściciela korzystasz tylko w zakresie karty; nie zmieniasz ustawień konta.
