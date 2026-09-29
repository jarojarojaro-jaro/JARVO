---
name: podlacz-konto
description: "Podłączenie Meta Ads i Google Ads do Skarbca krok po kroku."
version: 1.0.0
author: "Jarvo"
license: MIT
metadata:
  hermes:
    tags: [ads, setup, meta, google]
    related_skills: [start-kampanii, audyt-konta]
  jarvo:
    agent: jarvo-ads
    autonomy: A0
    reviewed: "2026-09-29"
---

# Podłączenie konta

Prowadzisz użytkownika przez podłączenie konta **do Skarbca**. Tokeny wkleja on sam w panelu Skarbca albo w pliku
na serwerze, nigdy w czacie z Tobą. Jeśli wklei token w czacie: nie powtarzaj go, poproś o unieważnienie i nowy token.

## Meta Ads (~15 min)
1. business.facebook.com → Business Manager z kontem reklamowym (waluta PLN, strefa Europe/Warsaw) i podpiętą kartą.
2. Strona FB i konto IG połączone z Business Managerem; piksel/zbiór danych (Menedżer zdarzeń).
3. **Limit wydatków konta** (Rozliczenia → Limit wydatków konta), np. 1000 zł: ostatnia warstwa ochrony.
4. developers.facebook.com → Utwórz aplikację → typ **Business** → dodaj produkt **Marketing API**.
5. Business Manager → Ustawienia firmy → Użytkownicy systemowi → Dodaj (rola Administrator) → Przypisz zasoby:
   konto reklamowe (Zarządzaj kampaniami), strona, piksel.
6. Wygeneruj token użytkownika systemowego dla tej aplikacji z uprawnieniami: `ads_management`, `ads_read`,
   `business_management`, `pages_read_engagement`, `pages_manage_ads`. Token „nigdy nie wygasa”.
7. Wklej token i ID konta (`act_…`) w **panelu Skarbca** (HQ → Reklamy → Podłącz) albo w `compose/skarbiec.env`
   (`META_TOKEN=…`, `META_KONTA=act_…`) i uruchom wdrożenie.
8. Chcesz najpierw za 0 zł? W aplikacji: Marketing API → Narzędzia → **Konto reklamowe sandbox**: pełne API bez emisji.

## Google Ads (~20 min)
1. Konto Google Ads (PLN) + **konto menedżera (MCC)**, pod które podpinasz konto reklamowe.
2. MCC → Narzędzia → Centrum API → **token deweloperski** (poziom Explorer działa od razu na prawdziwych kontach,
   do 2 880 operacji dziennie).
3. Google Cloud: projekt → włącz Google Ads API → dane logowania OAuth (aplikacja komputerowa) → client ID i secret.
4. Skarbiec: HQ → Reklamy → Podłącz Google → logowanie Google w przeglądarce (refresh token trafia tylko do Skarbca).
   Albo `compose/skarbiec.env`: `GOOGLE_DEVELOPER_TOKEN`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
   `GOOGLE_REFRESH_TOKEN`, `GOOGLE_LOGIN_CUSTOMER_ID` (MCC), `GOOGLE_KONTA`.
5. Budżet konta w Google (Płatności → budżet konta) jako ostatnia warstwa ochrony.

## Kanał zgód
Kody zgody Skarbiec wysyła przez **podłączony komunikator** (Telegram / Discord / Slack: to, co ma użytkownik)
i pokazuje w HQ pole na kod. Brak komunikatora → kody tylko w panelu Skarbca (osobne hasło).
Limit miesięczny (domyślnie 1000 zł) użytkownik ustawia sam w `compose/skarbiec.yaml`; agent nie może go zmienić.

## Weryfikacja
`ads.py doctor`: konta widoczne, waluta, strefa czasu, uprawnienia, piksel, limit konta, kanał zgód. Każdy brak
opisz jednym zdaniem z instrukcją naprawy.

## Definition of Done
- [ ] `ads.py doctor` = ok dla każdej podłączonej platformy,
- [ ] limit wydatków konta ustawiony po stronie platformy (albo świadoma decyzja użytkownika),
- [ ] kanał zgód działa (testowy kod doszedł),
- [ ] żaden token nie pojawił się w czacie, plikach agenta ani raporcie.
