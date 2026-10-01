# Rubryka aplikacji: 10 osi

source: Apple Human Interface Guidelines, Material Design 3, WCAG 2.2, App Store Review Guidelines (2.1, 4.2, 4.3, 5.1.1),
oh-my-hermes `omh-design-quality-gate` (MIT), bramka jakości Weba
reviewed: 2026-10-01

Pytanie: czy dobry projektant aplikacji mobilnych (klasa Revolut, Booksy, Allegro) by to podpisał i czy recenzent sklepu
zobaczy aplikację, a nie stronę w okienku? Każda oś: **zaliczona** albo **różnica** z dowodem (zrzut: warstwa, motyw,
ekran) i najmniejszą zmianą. Zaliczenie bez dowodu to nie recenzja.

| Oś | Zaliczona, gdy | Różnica, gdy |
|---|---|---|
| 1. **Pierwsze 30 sekund** | pierwszy ekran pokazuje wartość bez konta; jasne, co zrobić dalej | ekran logowania na start, pusty start, ściana zgód |
| 2. **Nawigacja wg platformy** | dolne zakładki (≤ 5), przewidywalne „wstecz”, tytuły ekranów, Android: gest i przycisk wstecz | menu hamburger jako jedyna nawigacja, ślepe zaułki, „wstecz” zamyka aplikację w połowie formularza |
| 3. **Kciuk i cele dotyku** | cele ≥ 44 pt / 48 dp, główna akcja w zasięgu kciuka, odstępy między celami | małe ikony-przyciski, sklejone linki, główna akcja u góry ekranu |
| 4. **Tekst i duża czcionka** | czytelne przy największej czcionce systemowej (zrzuty `duza-czcionka`), polskie znaki, długie słowa się zawijają | ucięte etykiety, nachodzący tekst, poziome przewijanie przy dużym tekście |
| 5. **Stany ekranów** | ładowanie, pusto (z akcją), błąd (z ponowieniem), brak sieci na każdym ekranie z danymi | biały ekran, kręciołek bez końca, surowy komunikat błędu |
| 6. **Formularze i klawiatura** | typ klawiatury, autouzupełnianie, pole widoczne nad klawiaturą, błąd przy polu | pole pod klawiaturą, klawiatura liter przy telefonie, błąd w okienku |
| 7. **Tryb ciemny i kontrast** | oba motywy dopracowane, kontrast AA (axe bez poważnych), żadnych sztywnych kolorów | biały prostokąt w trybie ciemnym, szary tekst na szarym |
| 8. **Ruch i płynność** | animacje krótkie i z powodem, „ogranicz ruch” respektowane, przewijanie płynne | animacja dla ozdoby, przycięcia, pętle mimo „ogranicz ruch” |
| 9. **Uprawnienia i zaufanie** | prośba w momencie użycia z ekranem wyjaśnienia, odmowa nie blokuje reszty, prywatność i kontakt w dwóch dotknięciach | zgody przy starcie, aplikacja bezużyteczna po odmowie |
| 10. **Marka i dopracowanie** | ikona, ekran startowy, kolory i ton z brand kitu, coś własnego zamiast domyślnych komponentów | wygląd szablonu, przypadkowe kolory, ikona z literami bez powodu, gdy jest logo |

## Punkty
Start 100. Różnica: **−8** na osiach 1–5, **−5** na osiach 6–10. Każdy problem blokujący z kontroli (test wrogi `blad`,
poważny błąd axe, błąd konsoli, nieudana kontrola kodu, oś bez dowodu) **−15**. Wynik < 90 → `REVISE`.
`BLOCK` niezależnie od punktów: awaria na urządzeniu, sekret w kodzie, brak zrzutów, 4. runda.
Liczy to `bramka.py werdykt`; Ty dajesz ocenę osi z dowodami.
