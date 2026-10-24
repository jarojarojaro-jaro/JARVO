---
name: pierwsza-sesja
description: "Pierwsza sesja: audyt strony, konkurencja, klienci, 3 ruchy."
version: 1.0.0
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
    reviewed: "2026-10-24"
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
   rola = `audyt`, `konkurencja`, `klienci`, `max_runtime_seconds=1200`, bez `parents`):

   | Rola | Agent | Skill | Zlecenie |
   |---|---|---|---|
   | `audyt` | `jarvo-web` | `audyt-strony` | szybki audyt strony z `USER.md`: 5 najważniejszych problemów (szybkość na telefonie, SEO podstron, dane kontaktowe, zaufanie), każdy z jednym zdaniem „co poprawić” |
   | `konkurencja` | `jarvo-sherlock` | `research-rynku` | 3 konkurentów z tej samej branży i okolicy: kto, link, czym się różnią od firmy właściciela (oferta, cena, opinie, strona), jedna rzecz, którą robią lepiej |
   | `klienci` | `jarvo-lowca` | `lista-leadow` | 10 firm z okolicy, które mogą kupić to, co sprzedaje właściciel: nazwa, branża, miasto, powód „dlaczego teraz” ze źródłem; tylko dane publiczne, bez wysyłania wiadomości |

   - Brak strony WWW: karta `audyt` sprawdza wizytówkę w Mapach Google albo profil z „Narzędzia i konta”; brak
     wszystkiego = bez karty `audyt`, a w podsumowaniu jeden ruch to „strona albo wizytówka”.
   - Brak miasta: konkurencja i klienci z całej Polski, a w podsumowaniu prosisz o miasto.
   - Firma sprzedaje osobom prywatnym (sklep, salon, gabinet): karta `klienci` szuka miejsc, gdzie ci ludzie są
     (lokalne grupy, partnerzy, firmy z sąsiedztwa do współpracy), nie listy osób.
   - GRANICE każdej karty: A0/A1, nic nie publikuje, nie wysyła, nie loguje się na konta właściciela.
4. **Czekaj na wyniki.** Gdy karty skończą (budzenie w tym wątku), sprawdź DoD jak zawsze (`sdlc-review`, szybko).
   Karta nieudana albo zbyt słaba: powiedz to wprost w podsumowaniu, bez zgadywania jej wyniku.
5. **Podsumowanie** w tym samym wątku, prostym polskim (`prosty-polski`):
   - po jednym zdaniu z każdej karty (co znaleźli, liczby),
   - **3 najważniejsze ruchy na ten tydzień**: każdy = co zrobić, dlaczego (z wyniku karty), kto z floty to zrobi,
     ile to zajmie właścicielowi (najczęściej: jedna decyzja),
   - jedno pytanie na koniec: od którego ruchu zaczynamy.
   Pełne raporty zostają w katalogach kart; w podsumowaniu tylko ścieżki.

## Czego nie robisz
- Nie zaczynasz wywiadu `onboarding-interview`: profil jest z pierwszego spotkania. Brakujące rzeczy (styl pracy,
  granice) dopytasz później, po podsumowaniu, jednym pytaniem.
- Nie zakładasz innych kart niż te trzy i nie wydłużasz limitu czasu: to pokaz na kilka minut, nie misja.
- Nie powtarzasz tej sesji: druga wiadomość `[Pierwsza sesja]` w tym samym wątku = odpowiedz, że sesja już trwa
  albo się skończyła, i pokaż wynik.
