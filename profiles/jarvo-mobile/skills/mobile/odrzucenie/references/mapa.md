# Mapa odrzuceń: wytyczna → droga → punkty listy

Pełna mapa jest w `scripts/odrzucenie.py` (`APPLE`, `GOOGLE`); tu najczęstsze przypadki małych aplikacji.

| Wiadomość | Wytyczna | Droga | Co robisz | Punkty |
|---|---|---|---|---|
| „unable to sign in with the demo account” | 2.1 | wyjaśnienie | sprawdź konto demo na produkcji, nowe hasło w App Review Information, kroki logowania | 25 |
| „we found bugs / the app crashed” | 2.1 | poprawka | odtwórz na urządzeniu (bramka, logi), nowy build | 26, 33 |
| „placeholder content / incomplete” | 2.1 | poprawka | treści zamiast tekstów zastępczych, JARVO-TODO zamknięte | 26 |
| „screenshots do not show the app in use” | 2.3.3 | poprawka | kadry z funkcjami (`pakiet.py zrzuty`), nie logowanie | 36, 37 |
| „references to Android” | 2.3.10 | poprawka | usuń obce platformy z karty, zrzutów i ekranów iOS | 37, 41 |
| „keywords include competitor names” | 2.3.7 | poprawka | słowa kluczowe bez nazw firm | 40 |
| „primarily a repackaged website” | 4.2, 4.2.2 | poprawka (rzadko wyjaśnienie) | funkcje natywne z planu; przy pewnym argumencie wylicz je w odpowiedzi | 28 |
| „spam / similar to other apps” | 4.3 | poprawka | własny wygląd i treści; jedna aplikacja zamiast kopii | 29 |
| „submitted by a service on behalf of the client” | 4.2.6 | wyjaśnienie | wysyła właściciel ze swojego konta (to jego aplikacja) | 1 |
| „Sign in with Apple required” | 4.8 | poprawka | `expo-apple-authentication` na ekranie logowania | 23 |
| „no account deletion” | 5.1.1(v) | poprawka | ekran Usuń konto + backend + strona w sieci | 22 |
| „purpose string not sufficient” | 5.1.1(ii) | poprawka | konkretny polski powód (`zgodnosc.py`) | 11, 12 |
| „requires login before showing content” | 5.1.1(v) | poprawka | katalog i informacje bez konta | 24 |
| „shares data with AI without consent” | 5.1.2(i) | poprawka | ekran zgody przed pierwszym użyciem AI | 18 |
| Google: „Broken Functionality” | — | poprawka | raport przedpremierowy, logi, nowy `versionCode` | 26, 33 |
| Google: „Data safety” | — | poprawka | formularz zgodny z aplikacją i bibliotekami (`prywatnosc-szkic.json`) | 17 |
| Google: „App access / login credentials” | — | wyjaśnienie | konto demo bez 2FA w Treści aplikacji → Dostęp | 25 |

**Odpowiedź (EN):** podziękowanie, dla każdej wytycznej: co zmieniono i w którym buildzie albo gdzie dokładnie jest
funkcja (ekran po ekranie), konto demo, propozycja nagrania. Bez emocji, bez „we think”, bez obietnic poza tym buildem.
**Apple:** odpowiedź w App Review albo odwołanie do App Review Board (jedno na zgłoszenie); przy aktualizacji z ważną
poprawką Apple może pozwolić odłożyć problem nieprawny do następnej wersji. **Google:** odwołanie ze strony stanu zasad
(jedno na decyzję) albo poprawka z nowym `versionCode`.
