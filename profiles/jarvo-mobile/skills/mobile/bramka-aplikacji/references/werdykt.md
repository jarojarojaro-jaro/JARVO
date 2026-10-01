# Werdykt bramki aplikacji (jedna runda)

source: oh-my-hermes `omh-visual-qa/references/visual-verdict-contract.md` (MIT), przełożone; bramka jakości Weba
reviewed: 2026-10-01

Ocena agenta (`out/jakosc/ocena-runda-N.json`, szablon: `bramka.py ocena-szablon`):

```json
{"runda": 2, "osie": [
  {"os": 4, "nazwa": "Tekst i duża czcionka", "zaliczona": false,
   "dowod": "android/duza-czcionka-ekran.png: przycisk „Zarezerwuj termin” ucięty do „Zarezerwuj ter…”",
   "roznica": "etykieta przycisku w jednej linii przy font_scale 2.0",
   "poprawka": "Przycisk: numberOfLines usunięte, minHeight zamiast height (src/components/Przycisk.tsx)"},
  {"os": 1, "nazwa": "Pierwsze 30 sekund", "zaliczona": true, "dowod": "web/iphone-jasny/start.png: lista wolnych terminów bez logowania"}
]}
```

Werdykt (`bramka.py werdykt`): `wynik` 0–100, `werdykt` PASS / REVISE / BLOCK, `blokady`, `problemy` (−15), `roznice`
(z osi), `niezmierzone` (warstwy i scenariusze bez pomiaru), `warstwy` (web, android, ios).

- Ponowna ocena tych samych zrzutów to nie runda: nowa runda = nowe zrzuty po poprawkach.
- Wyczerpane rundy to zgłoszona blokada, nigdy ciche `PASS`.
- `niezmierzone` przepisujesz do `metadata.risks` (np. „iOS: brak tokenu GitHub, niezmierzone”).
