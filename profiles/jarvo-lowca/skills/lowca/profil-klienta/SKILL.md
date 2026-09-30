---
name: profil-klienta
description: "ICP: kogo szukamy, gdzie, jaki ból i jakie sygnały."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [leads, icp, b2b, sales, targeting]
    related_skills: [sygnaly, kwalifikacja, lista-leadow]
  jarvo:
    agent: jarvo-lowca
    autonomy: A1
    reviewed: "2026-09-30"
---

# Profil idealnego klienta (ICP)

Pierwszy krok każdego szukania. ICP mówi, **kogo** szukamy i **po czym poznamy, że to dobry moment**. Bez niego lista
to przypadkowe firmy. Wynik: `ICP.yaml` (czyta go `leady.py`) i `ICP.md` (dla człowieka).

## Kroki
1. **Oferta w jednym zdaniu:** co użytkownik sprzedaje, komu, za ile (rząd wielkości), jaki problem rozwiązuje.
   Brak w karcie i w brand kicie → `kanban_block(kind="needs_input")` z propozycją ICP do potwierdzenia.
2. **Kto kupuje:** branże jako prefiksy PKD (np. `62` IT, `47.91` sprzedaż wysyłkowa, `56.10` restauracje), region
   (województwa), forma i wielkość (nowe spółki, firmy po przetargu, instytucje publiczne jako zamawiający), rola
   decydenta (właściciel, marketing, IT, zakupy).
3. **Po czym poznamy „teraz”:** sygnały z tabeli źródeł w skillu `sygnaly`, z wagą 0–3 i oknem świeżości
   w dniach. Przetargi: prefiksy CPV (np. `72` usługi IT, `79341` reklama, `45` roboty budowlane).
4. **Wykluczenia:** formy (`FUNDACJA`, `STOWARZYSZENIE`), słowa (`likwidacji`, konkurenci użytkownika), własni klienci.
5. **Próg dopasowania** (`prog`, domyślnie 0,5): część kryteriów, które firma musi spełnić. 1,0 = wszystkie.

## `ICP.yaml`
```yaml
nazwa: "Strony www dla nowych spółek (Mazowsze)"
oferta: "Strona firmowa w 7 dni dla nowo założonych spółek"
dopasowanie:
  pkd: ["62", "70", "73"]          # prefiksy PKD (bez kropek też działa)
  woj: [MAZOWIECKIE]               # nazwy albo kody PL14
  cpv: ["72", "79341"]             # tylko przy przetargach
  slowa: ["strona", "sklep internetowy"]   # w opisie sygnału albo przedmiocie przetargu
  wyklucz_slowa: ["likwidacji"]
  wyklucz_formy: [FUNDACJA, STOWARZYSZENIE]
  prog: 1.0
sygnaly:                           # waga 0–3, okno świeżości w dniach (reszta: wartości domyślne leady.py)
  krs-nowa-firma: {waga: 3, okno: 30}
  przetarg-ogloszenie: {waga: 3, okno: 14}
  rekrutacja: {waga: 2, okno: 30}
```

## Wyjścia
`@@WORKSPACES_DIR@@/jarvo-lowca/leady/<projekt>/ICP.yaml` i `ICP.md` (oferta, kto, sygnały z uzasadnieniem, wykluczenia,
czego nie wiemy). Kopia w `out/leady/<projekt>/`.

## Definition of Done
- [ ] oferta w jednym zdaniu i decydent nazwany,
- [ ] co najmniej 2 kryteria dopasowania i 2 sygnały z wagą i oknem, każdy z uzasadnieniem w `ICP.md`,
- [ ] wykluczenia wpisane (albo „brak” z powodem).
