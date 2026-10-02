# Metadane karty: limity i zasady

| Pole | Gdzie | Limit | Uwagi |
|---|---|---|---|
| Nazwa | App Store `title`, Google `title.txt` | 30 znaków | nazwa marki; bez słów kluczowych doklejonych po myślniku |
| Podtytuł | App Store `subtitle` | 30 znaków | jedna korzyść („Wizyty i pieczątki w salonie”) |
| Tekst promocyjny | App Store `promoText` | 170 znaków | można zmieniać bez nowej wersji; bez cen |
| Opis | App Store `description`, Google `full_description.txt` | 4000 znaków | pierwsze 2–3 zdania widać bez rozwijania: korzyść, nie historia firmy |
| Krótki opis | Google `short_description.txt` | 80 znaków | jedno zdanie, co klient załatwi |
| Słowa kluczowe | App Store `keywords` | **100 bajtów** UTF-8 | po przecinku bez spacji; ą, ę, ł… to 2 bajty; każde > 2 znaki |
| Co nowego | App Store `releaseNotes` | 4000 znaków | konkretnie, co się zmieniło (2.3.1(a): ogólniki odrzucane) |
| Notatki dla recenzenta | `apple.review.notes` | 4000 bajtów | **po angielsku**: funkcje, ścieżka testu krok po kroku, konto demo, aktualizacje |

**Słowa kluczowe** (Apple 2.3.7): bez nazwy aplikacji i firmy (już się liczą), bez nazw konkurencji i platform
(Booksy, Wolt, Pyszne.pl, Google, Android…), bez liczby mnogiej obok pojedynczej, bez kategorii. Polskie odmiany
wybieraj według tego, jak szukają klienci („fryzjer”, nie „fryzjerstwo”).

**Zakazane w każdym polu:** „#1”, „najlepsza”, „najtańsza”, „darmowa”, „za darmo”, rabaty i procenty, emoji,
WIELKIE LITERY (poza skrótami: SMS, QR, BLIK…), na karcie iOS żadnego „Android” ani „Google Play” (2.3.10).
W nazwie, podtytule i krótkim opisie także „nowość”, „top”, „hit”, „beta” (Google: twierdzenia promocyjne).

**Adresy:** `privacyPolicyUrl` to ten sam adres co w aplikacji (ekran Prywatność); `supportUrl` ze stroną z e-mailem
albo telefonem; w Google adres usuwania konta wpisuje właściciel w Data safety (`firma.usuwanie_konta_url`).

**Notatki dla recenzenta, wzór** (szkic robi `pakiet.py szkic`):
```
Main features:
- Booking a visit: choose a service, a stylist and a time slot (Home tab).
How to test:
1. Open the app. The home screen shows the services and opening hours, no account needed.
2. Tap a service, pick any stylist and a free time slot, then confirm the booking.
3. Sign in with the demo account from the App Review Information fields (no SMS code, no 2FA).
4. Account deletion: More (Więcej) → Delete account (Usuń konto).
Updates: we use EAS Update only for bug fixes. New features ship in new App Store versions.
```
Polskie nazwy przycisków w nawiasach są w porządku (interfejs jest po polsku), zdania nie.
