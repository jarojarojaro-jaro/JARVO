# Werdykt wizualny (jedna runda)

Praca wizualna nie ma naturalnego końca: „wygląda lepiej” kończy pętlę, gdy skończy się cierpliwość. Werdykt daje
jej liczbę i próg.

```json
{
  "runda": 2,
  "zrzuty": "out/jakosc/runda-2/",
  "wynik": 84,
  "werdykt": "REVISE",
  "roznice": [
    {"os": "rytm odstępów",
     "roznica": "Karty mają 12 px wewnętrznego odstępu przy 24 px w sekcji wyżej; rząd 3 kart na 1440 wygląda ciasno.",
     "poprawka": "Padding kart = token space-6 (24 px); nowe zrzuty 1440/768/375."}
  ]
}
```

- `wynik`: liczba całkowita 0–100, żeby dwie rundy dało się porównać, a regres było widać.
- `werdykt`: `PASS` (≥ 90 i zrzuty z oddawanej wersji), `REVISE` (< 90, jest jeszcze runda), `BLOCK`
  (brak zrzutów, zrzuty z innej wersji, wyczerpane rundy; nazwij, czego brakuje).
- `roznice`: każda para „co jest nie tak” + „najmniejsza zmiana”. Pusta lista przy wyniku < 90 to sprzeczność.
- Wyczerpane rundy to zgłoszona blokada, nigdy ciche `PASS`.
- Różnice pikselowe (porównanie zrzutów) wskazują, gdzie patrzeć; nie dają wyniku. Ten sam piksel może być błędem
  (kontrast, zła etykieta), więc ocenia rubryka.

Źródło: oh-my-hermes, `omh-visual-qa/references/visual-verdict-contract.md` (MIT), przełożone.
