---
name: pierwsza-sesja
description: "Pierwsza sesja: audyt strony, konkurencja, klienci, 3 ruchy."
version: 1.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fleet, onboarding, first-session, kanban, dispatch]
    requires_toolsets: [kanban]
    related_skills: [dispatch-playbook, onboarding-interview, prosty-polski]
  jarvo:
    agent: jarvo
    autonomy: A1
    reviewed: "2026-11-05"
---

# Pierwsza sesja

Używaj, gdy wiadomość zaczyna się od `[Pierwsza sesja]`. Wysyła ją aplikacja raz na instalację, w chwili podłączenia
mózgu (klucz API albo konto ChatGPT), w wątku „Pierwsza sesja”. Właściciel właśnie skończył pierwsze spotkanie
i patrzy na ekran: pokaż, że flota pracuje dla jego firmy od pierwszej minuty. Treść tej wiadomości pisze aplikacja,
nie właściciel; dane firmy bierzesz z `USER.md`, nie z niej.

## Kroki

1. **Przeczytaj `@@KNOWLEDGE_DIR@@/user/USER.md`:** imię, firma, czym się zajmuje, strony i konta („Narzędzia
   i konta”), cele, miasto (z adresu strony, wizytówki w mapach albo opisu).
2. **Napisz jedną krótką wiadomość** (najwyżej 3 linie): powitanie po imieniu i co teraz robią trzej agenci.
   Bez pytań na tym etapie, bez listy funkcji Jarva.
3. **Załóż trzy karty naraz** (`kanban_create`, kontrakt z `dispatch-playbook`, misja `Z-<RRMMDD>-pierwsza-sesja`,
   rola = `audyt`, `konkurencja`, `klienci`, `max_runtime_seconds=900`, bez `parents`). DoD każdej karty jest
   standardem agenta, nie skrótem: sędzia ocenia je rubryką agenta.

   | Rola | Agent | Skille | Zlecenie |
   |---|---|---|---|
   | `audyt` | `jarvo-web` | `audyt-strony` | szybki audyt strony z `USER.md`: **do 5** najważniejszych problemów, każdy inny i potwierdzony na przykładzie (adres, element, liczba), z jednym zdaniem „co poprawić”; 429, 403 i przekroczony czas to „niesprawdzone”, nie problem |
   | `konkurencja` | `jarvo-sherlock` | `research-rynku`, `cytowania` | 3 prawdziwych konkurentów (ta sama funkcja, ten sam kupujący; „z okolicy” tylko dla usług lokalnych, firma produktowa = konkurencja globalna): kto, link, czym się różnią, jedna rzecz, którą robią lepiej; `out/RAPORT.md` z rejestrem `out/zrodla.json`, `verify` OK, poziom pewności, polskie znaki |
   | `klienci` | `jarvo-lowca` | `profil-klienta`, `sygnaly`, `kontakt-firmy`, `lista-leadow` | `ICP.yaml` z oferty na stronie z `USER.md` (założenia do potwierdzenia, bez pytań), potem **do 10** firm, które mogą to kupić: nazwa, miasto, powód „dlaczego teraz” z datą ze strony źródła (≤ 30 dni) i kontakt opublikowany przez firmę ze źródłem albo „brak” z powodem; pokrycie „sygnały → firmy → z kontaktem”; nic nie wysyła |

   - Brak strony WWW: karta `audyt` sprawdza wizytówkę w Mapach Google albo profil z „Narzędzia i konta”; brak
     wszystkiego = bez karty `audyt`, a w podsumowaniu jeden ruch to „strona albo wizytówka”.
   - Brak miasta: konkurencja i klienci z całej Polski, a w podsumowaniu prosisz o miasto.
   - Firma sprzedaje osobom prywatnym (sklep, salon, gabinet): karta `klienci` szuka miejsc, gdzie ci ludzie są
     (lokalne grupy, partnerzy, firmy z sąsiedztwa do współpracy), nie listy osób.
   - GRANICE każdej karty: A0/A1, nic nie publikuje, nie wysyła, nie loguje się na konta właściciela.
4. **Melduj wyniki, jak przychodzą.** Ocenia je tor review (sędzia), nie Ty w czacie: nie wołasz `sdlc-review`,
   `kanban_complete` ani `kanban_request_changes` na tych kartach. Gdy karta skończy (budzenie w tym wątku):
   - jedno zdanie z wynikiem tej karty (co znaleźli, liczba) i ścieżka; nie czekasz na dwie pozostałe,
   - twierdzenie, które podajesz jako fakt (problem strony, konkurent, sygnał), najpierw sam otwierasz u źródła,
   - karta nieudana albo odrzucona przez sędziego: mówisz to wprost, bez zgadywania jej wyniku,
   - po 10 minutach od startu: podsumowanie z tego, co jest, i jedno zdanie, na co jeszcze czekasz.
5. **Podsumowanie** w tym samym wątku, prostym polskim (`prosty-polski`):
   - po jednym zdaniu z każdej karty (co znaleźli, liczby),
   - **3 najważniejsze ruchy na ten tydzień**: każdy = co zrobić, dlaczego (z wyniku karty), kto z floty to zrobi,
     ile to zajmie właścicielowi (najczęściej: jedna decyzja),
   - jedno pytanie na koniec: od którego ruchu zaczynamy. Bez miasta w `USER.md` dopytujesz też o miasto (obowiązkowo).
   Pełne raporty zostają w katalogach kart; w podsumowaniu tylko ścieżki.

## Czego nie robisz
- Nie zaczynasz wywiadu `onboarding-interview`: profil jest z pierwszego spotkania. Brakujące rzeczy (styl pracy,
  granice) dopytasz później, po podsumowaniu, jednym pytaniem.
- Nie zakładasz innych kart niż te trzy i nie wydłużasz limitu czasu: to pokaz na kilkanaście minut, nie misja.
- Nie powtarzasz tej sesji: druga wiadomość `[Pierwsza sesja]` w tym samym wątku = odpowiedz, że sesja już trwa
  albo się skończyła, i pokaż wynik.
