---
source: "Wzorzec @twoclipping (UI morph, 907 tys. wyświetleń) i @verbove (MakerMap), opisany w analizie trendu Opus 5.5 (wrzesień 2026); własny szablon Jarvo"
reviewed: "2026-09-29"
---
# Jeden kształt, zero cięć (UI morph jako lista stanów)

Jeden kontener nigdy nie jest cięty: każdy stan to **ten sam element**, który zmienia rozmiar, promień rogów
i wypełnienie, a jego treść podmienia się za krótkim rozmyciem. Kursor wywołuje każdą zmianę prawdziwym kliknięciem.
Ostatnia klatka = pierwsza, więc film się zapętla. Pasuje do promo produktu, launchu funkcji, reklamy aplikacji.

## Spec do wypełnienia przed kodem (`out/wideo/src/SPEC.xml`)
```xml
<wejscia>
  Produkt + URL, 8–12 stanów UI, które opowiadają historię, prawdziwe dane w każdym stanie
  (z assety.py albo od klienta), kolory i fonty marki + jeden akcent, muzyka ~120 BPM (albo synteza), formaty.
</wejscia>
<kierunek>
  Jeden kontener, zero cięć. Kursor prowadzi każdą zmianę. Ciepłe neutralne tło, jeden akcent.
  Sprężyny z najwyżej małym przestrzałem. Zakazane: gumowe odbicia, glow, gradient na UI, cząsteczki, martwy czas.
</kierunek>
<struktura>
  120 BPM, 8 taktów, coś na każdym bicie:
  logo → przycisk CTA → pole e-mail (pisane) → loader → ✓ sukces → karta panelu → wykres rysuje się sam
  → podpowiedź po najechaniu → paleta ⌘K → toast → logo.
</struktura>
<budowa>
  1. Jeden plik HTML, jeden canvas, window.__seek(t) (kontrakt-html.md). Bez przejść CSS, timerów, stanu.
  2. Sprężyny w zamkniętej postaci; wartość z wieloma celami = suma sprężyn, jedna na zmianę.
  3. Tekst w przemieniającym się kontenerze wchodzi po starcie przemiany i wychodzi przed następną.
  4. Wskaźniki (zakładki): przód i tył na różnych sprężynach, więc się rozciągają.
  5. Siatka bitów z rytm.py; start na mocnym bicie; dźwięki UI (click, pop, whoosh) z sound.mjs na zdarzeniach.
  6. Render html_wideo.py --subklatki 4 (motion blur).
</budowa>
<pulapki>
  Nigdy will-change na tym, co kamera skaluje (rozmyty tekst).
  Ostatnia klatka = pierwsza, łącznie z pozycją i prędkością kursora (krytyka.py petla).
</pulapki>
<start>
  Najpierw lista stanów na siatce bitów (tabela: takt, bit, stan, treść, dźwięk). Dopiero potem kod.
</start>
```

## Tabela stanów (przykład)
| Takt.bit | Stan | Rozmiar / promień | Treść (prawdziwa) | Kursor | Dźwięk |
|---|---|---|---|---|---|
| 1.1 | logo | 160×160 / 80 | znak marki | poza kadrem | — |
| 1.3 | przycisk | 320×72 / 36 | „Zacznij za darmo” | wjeżdża, klik na 2.1 | click |
| 2.1 | pole e-mail | 520×72 / 16 | wpisywane „ola@firma.pl” | tekst | tick co literę |
| … | … | … | … | … | … |

## Kontrola
`krytyka.py pasek` na każdej przemianie (tekst nie nachodzi), `krytyka.py petla` (szew), `determinizm`.
