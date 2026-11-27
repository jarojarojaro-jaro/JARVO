# Changelog: jarvo-hacker

## Niewydane
- `browser_*` działa na Chrome z trwałym profilem przeglądarki (logowania zostają między zadaniami), nawigacja zwraca zwartą listę elementów z refami i tekstem, klik, klawisz i Wstecz zwracają widok strony po ustaleniu, a blokada antybotowa mówi wprost: telefon floty, potem `kanban_block`.
- Telefon `first` prowadzisz skillem `telefon` narzędziami `mcp__phone__*` (surowe adb do ekranu strażnik odrzuca, gdy ciało PhoneUse odpowiada), a MAPA mówi o nim zgodnie z przydziałem.
- Obraz z narzędzi (zrzut, `shot` telefonu, `vision_analyze`) widzisz od razu jako obraz w wyniku narzędzia, bez osobnego opisu modelu pomocniczego, a wszystkie narzędzia są w zestawie od razu, bez `tool_search`.
- Raport, terminy, eksport i notatka w Mózgu podają godziny w czasie polskim; baza trzyma UTC.
- `agregatory.py` codziennie czyta DevGrants Daily, HackList, Hackathon Hub, BuildJams, advance.to i make.fun, łączy powtórki, porównuje z bazą i daje tabelę hackathonów spoza bazy od 5000 USD; liczby dla właściciela Hacker bierze z niego.
- Rutyna `hacker-terminy` codziennie szuka nowych hackathonów i raportuje najlepsze do wzięcia; gdy w czymś startujemy, przypomina nasz następny krok.
- Śledzenie udziału i historii (`ustaw`, `notuj`, `historia`), a notatka „kalendarz hackathonów” w Mózgu odświeża się po każdej zmianie bazy i co rano.
- Kalendarz hackathonów: `out/KALENDARZ.md` i `out/hackatony.ics` z etapami i naszymi kamieniami.
- Nowy agent Hacker: radar hackathonów, baza `hackatony.py` z terminami w UTC i zasadami, ocena wartości, plan pod jury, budowa projektu, zgłoszenie i retrospektywa.
