---
name: wywiad
description: "Mglisty, duży cel: jedno pytanie naraz, max 6, potem brief."
version: 1.0.0
author: "Jarvo (protokół rund na bazie oh-my-hermes deep-interview, MIT)"
license: MIT
metadata:
  hermes:
    tags: [fleet, intake, clarification, interview]
    related_skills: [intake, dispatch-playbook, mission-ledger]
  tars:
    agent: tars
    autonomy: A1
    reviewed: "2026-09-28"
---

# Wywiad przed misją

Uruchamia go **tylko** `intake` (krok 3), gdy bramka wywiadu jest spełniona. Nigdy dla rozmowy, statusu, decyzji,
zlecenia jednego agenta ani gdy użytkownik mówi „rób”, „bez pytań”, „sam zdecyduj”.

## Trzy rzeczy do ustalenia
1. **Efekt:** co ma istnieć, gdy skończymy (np. landing + 6 postów + plan publikacji).
2. **Granice:** czego nie robimy, marka, termin, budżet, kanały.
3. **Po czym poznamy, że gotowe:** kryterium, które da się sprawdzić (liczba, data, akceptacja konkretnej rzeczy).

## Zanim zapytasz
Sprawdź, co już wiadomo: pamięć, `@@KNOWLEDGE_DIR@@/user/USER.md`, brand kity w `@@KNOWLEDGE_DIR@@/brands/`,
`@@MISSIONS_DIR@@/INDEX.md`. O rzeczy, które tam są, nie pytasz. O to, co agent ustali sam (technologia, kolejność
prac, narzędzia), też nie.

## Rundy
- **Jedno pytanie w wiadomości.** Najpierw o tę z trzech rzeczy, która najbardziej zmienia plan, a nie o najłatwiejszą.
- Pytanie brzmi jak od kolegi: jedno zdanie, bez wstępu, bez powtarzania tego, co użytkownik napisał.
- Pod pytaniem **2–4 prawdziwe odpowiedzi** (z rekomendowaną oznaczoną „(polecam)”) i ostatnia: „Inne: napisz po swojemu”.
  Numer, słowa z listy albo zupełnie inna odpowiedź: wszystko jest dobre. Nie dopytujesz, bo odpowiedź była spoza listy.
- Pierwsza linia wiadomości: `Pytanie N/6` (żeby było widać, że pytań jest mało). Słów „runda”, „wymiar”,
  „jasność” w pytaniu nie używasz.
- Nowy wątek z odpowiedzi przypisujesz do jednej z trzech rzeczy; nie zwiększa limitu pytań.

## Zatrzymanie (pierwsza pasująca reguła kończy wywiad)
1. **Trzy rzeczy jasne** → brief i start.
2. **Użytkownik mówi „rób”, „wystarczy”, „ruszaj”** → od razu brief; niejasne punkty jako założenia z wartością, którą przyjmujesz.
3. **Szóste pytanie za nami** → brief z tym, co jest; nierozstrzygnięte jako założenia.

**Przed 4. pytaniem** zamiast pytać: jedno zdanie, co już wiesz, i wybór: „1. Dopytaj jeszcze (najwyżej 3 pytania)
2. Ruszaj z tym, co masz (polecam, jeśli brakujące rzeczy mają rozsądne domyślne) 3. Inne”.
Gdy wahasz się między kolejnym pytaniem a startem: startuj.

## Brief (koniec wywiadu)
Zapisz w `MISSION.md` misji (skill `mission-ledger`):
```
## Brief
Efekt: …
Czego nie robimy: …
Po czym poznamy, że gotowe: …
Założenia (do zmiany w każdej chwili): …
```
Użytkownikowi: 3–5 linii briefu i jedno zdanie startu jak w `intake` (krok 5). Bez dodatkowego „czy się zgadzasz?”,
chyba że misja zawiera akcję A2 (publikacja, wydatek, wdrożenie). Potem `dispatch-playbook`: brief trafia do
KONTEKSTU i DoD kart.
