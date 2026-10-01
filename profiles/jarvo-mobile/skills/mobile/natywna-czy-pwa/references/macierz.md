# Macierz decyzji: strona, PWA, Wallet, platforma, aplikacja

source: WebKit (web push dla aplikacji z ekranu głównego, iOS 16.4), Apple Wallet i PassKit, Google Wallet API,
App Store Review Guidelines 4.2 i 4.2.6, Google Play: Trusted Web Activity, cenniki Apple, Google Play, Expo, Supabase
reviewed: 2026-10-01

Katalog funkcji i poziomy obsługi są w `decyzja.py` (jedno źródło prawdy: `decyzja.py funkcje`). Tu: dlaczego.

## Rozwiązania

| Rozwiązanie | Kiedy wygrywa | Ograniczenia, o których mówisz |
|---|---|---|
| **Lepsza strona** | rzadkie użycie (raz w miesiącu i rzadziej), informacja, jednorazowe zakupy | brak powiadomień push; przypomnienia SMS/e-mail |
| **PWA** | strona już jest, klienci wracają, potrzebne powiadomienia na Androidzie, ikona na ekranie | iPhone: powiadomienia tylko po dodaniu do ekranu głównego (iOS 16.4+), trzeba to klientom pokazać; brak NFC, Bluetooth, lokalizacji w tle; w App Store jej nie ma (w Google Play może być jako Trusted Web Activity) |
| **Karta w Wallet** | karta stałego klienta, pieczątki, karnety, bilety, vouchery | Apple: konto Apple Developer (99 $/rok) do podpisu kart; Google Wallet API bez opłat; powiadomienia tylko o zmianie karty |
| **Gotowa platforma** | rezerwacje (Booksy), zamówienia (Pyszne.pl, Wolt, Glovo, Uber Eats), gdy liczy się ruch z platformy | abonament albo prowizja; klienci i dane należą do platformy |
| **Aplikacja w sklepach** | codzienne/cotygodniowe użycie przez tych samych klientów, powiadomienia jako sedno, offline, aparat i skaner, NFC, Bluetooth, lokalizacja w tle, narzędzie dla ekipy w terenie | Apple 99 $/rok, Google 25 $ raz, recenzje (dni), utrzymanie 10–20 h/rok, ryzyko 4.2 bez funkcji ponad stronę |

## Zasady oceny (`decyzja.py ocen`)
- Funkcja „musi”, której rozwiązanie nie obsługuje (0) → rozwiązanie odpada.
- „Musi” z ograniczeniami (1) → −8 pkt i opis ograniczenia; „fajnie” → +3 (1) albo +6 (2).
- Aplikacja bez żadnej „musi”, której przeglądarka nie zrobi dobrze → −35 pkt i ryzyko 4.2 („przepakowana strona”).
- Częstotliwość: raz w miesiącu −15, rzadziej −30 dla aplikacji (klienci jej nie zainstalują albo usuną); codziennie
  albo co tydzień przez tych samych klientów +10.
- Pracownicy: aplikacja bez walki o instalację (+5); dystrybucja przez TestFlight (wersje ważne 90 dni) albo prywatne
  aplikacje Google Play; często wystarcza PWA.
- Budżet < 99 $/rok → aplikacja −20 (nie pokrywa konta Apple Developer).
- Karta w Wallet dochodzi jako uzupełnienie strony, PWA i platformy, gdy w potrzebach jest lojalność albo karnety.

## Fakty, które warto powiedzieć właścicielowi
- PWA w UE działa na iPhonie (Apple w 2024 wycofał się z planu wyłączenia aplikacji z ekranu głównego w UE).
- Aplikacja w App Store i Google Play to dwa konta właściciela (Apple 4.2.6: generator aplikacji nie wysyła ich
  w imieniu klientów), recenzja Apple zwykle do 24–48 h, Google do 7 dni; nowe konto osobiste Google wymaga testu
  zamkniętego z 12 testerami przez 14 dni (konto organizacji z numerem D-U-N-S nie).
- Konto Apple jako firma wymaga numeru D-U-N-S (bezpłatny); jako osoba: w sklepie widać imię i nazwisko.
- W UE karta aplikacji pokazuje dane przedsiębiorcy (adres, telefon, e-mail; DSA): przy działalności zarejestrowanej
  w domu warto mieć adres do doręczeń.

## Źródła
- WebKit, web push dla aplikacji z ekranu głównego: https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/
- Apple Wallet (PassKit): https://developer.apple.com/wallet/
- Google Wallet API: https://developers.google.com/wallet
- App Store Review Guidelines 4.2, 4.2.6: https://developer.apple.com/app-store/review/guidelines/
- Trusted Web Activity: https://developer.android.com/develop/ui/views/layout/webapps/trusted-web-activities
- Google Play, test zamknięty dla nowych kont osobistych: https://support.google.com/googleplay/android-developer/answer/14151465
- Cenniki: https://developer.apple.com/programs/, https://expo.dev/pricing, https://supabase.com/pricing
