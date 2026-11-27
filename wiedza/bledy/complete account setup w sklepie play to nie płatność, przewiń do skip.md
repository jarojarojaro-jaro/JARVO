---
typ: blad
tagi: [telefon, sklep-play, google, adb, phoneuse]
utworzono: 2026-11-27
zmieniono: 2026-11-27
status: aktualna
zrodlo: "rozmowa z JARO 27.11 02:50–03:12 (instalacja OLX na first), panel rozmowy.db przebieg p_001a21ab28c2d36104aa8, agent.log Jarva; raport nasz-telefon.md 27.11"
agent: jarvo
sygnatury: ["Complete account setup", "Dokończ konfigurowanie konta", "Review your account to continue installing apps", SheetUiBuilderHostActivity, "finsky.billing.acquire", "Try Google Play Pass"]
wystapienia: 1
---
# Complete account setup w Sklepie Play to nie płatność, przewiń do Skip

**Plansza „Complete account setup” przy instalacji ze Sklepu Play to potwierdzenie konta Google: „Continue”, potem przewijasz metody płatności do „Skip”, a „Try Google Play Pass” zamykasz „Not now”.**

**Objaw:** 27.11 o 02:50 JARO kazał zainstalować OLX na first; Jarvo uznał planszę Sklepu za płatność za darmową aplikację, szukał APK na stronach za Cloudflare i wgrał Aurora Store, aż JARO napisał, że to ekran potwierdzenia konta Google.

**Przyczyna:** ekran był czytany surowym `adb shell uiautomator dump` z grepem po `text=`: wycinek nie pokazał, że lista się przewija, a „Skip” był dopiero po przewinięciu. Nazwa aktywności `finsky.billing.acquire.SheetUiBuilderHostActivity` i przyciski „Add card”, „Add PayPal”, „Pay with BLIK” na drugiej planszy wyglądały jak żądanie zapłaty.

**Jak poprawnie:** ekran telefonu czytasz `mcp__phone__screen` w całości (flaga `scroll` mówi, że lista ma dalszy ciąg) i planszę rozpoznajesz po tytule i wszystkich przyciskach po przewinięciu. „Complete account setup” → „Continue” → przewiń → „Skip”; „Try Google Play Pass” → „Not now”; metod płatności nigdy nie dodajesz. Aplikację instalujesz ze Sklepu Play, bez sklepów zastępczych i stron z APK. Surowe adb do ekranu strażnik odrzuca, gdy ciało PhoneUse odpowiada (skill `telefon`).

## Powiązane
- hub: [[bledy/_hub-bledy|Księga błędów]]
- [[bledy/google nie loguje w przeglądarce komputera, konta google na telefonie|Google tylko na telefonie]]
- [[bledy/cloudflare nie przepuszcza komputera, krok na telefonie floty|Cloudflare nie przepuszcza Komputera]]
- [[fleet/lekcje|Księga lekcji floty]]
