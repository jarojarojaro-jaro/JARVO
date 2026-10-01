---
name: natywna-czy-pwa
description: "Czy firmie potrzebna aplikacja: rekomendacja z kosztami."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [mobile, pwa, native-app, wallet, decision, costs]
    related_skills: [audyt-mobilny]
  jarvo:
    agent: jarvo-mobile
    autonomy: A1
    reviewed: "2026-10-01"
---

# Natywna czy PWA?

Najtańsza aplikacja to ta, której nie trzeba budować. Ten workflow zamienia „chcę aplikację” na listę potrzeb, sprawdza,
co je obsługuje (lepsza strona, PWA, karta w Wallet, gotowa platforma, aplikacja w sklepach), i daje rekomendację
z kosztami, ryzykiem odrzucenia w sklepie i następnym krokiem. Decyzję podejmuje właściciel.

## Kiedy użyć
- „chcę aplikację”, „zróbcie nam apkę”, „czy potrzebujemy aplikacji”, „PWA czy natywna”, „aplikacja jak konkurencja”,
- zawsze przed pierwszą aplikacją dla firmy (także gdy karta mówi od razu „zrób aplikację”).

## Kiedy NIE używać
- firma ma już działającą aplikację i chce zmian → najpierw `audyt-mobilny`,
- decyzja już zapadła i jest zapisana w karcie (`REKOMENDACJA.md` z poprzedniej karty) → nie powtarzasz.

## Wejścia
Cel aplikacji jednym zdaniem i kto z niej korzysta. Resztę zbierasz do `potrzeby.yaml`
(`python3 $HERMES_HOME/scripts/decyzja.py szablon > out/decyzja/potrzeby.yaml`).

## Kroki
1. **Potrzeby.** Wypełnij `potrzeby.yaml` z karty, rozmowy, strony firmy i `audyt-mobilny` (gdy był). Brakuje ważnej
   rzeczy → najwyżej 3 pytania naraz przez `kanban_block(kind="needs_input")`, każde z propozycją odpowiedzi:
   - co klient ma załatwić w aplikacji i jak robi to dziś (telefon, Booksy, strona),
   - jak często ten sam klient by jej użył (codziennie, co tydzień, raz w miesiącu, rzadziej),
   - które funkcje są „musi”, a które „fajnie” (lista: `decyzja.py funkcje`),
   - kto używa: klienci czy pracownicy; budżet roczny na licencje.
   „Musi” to tylko to, bez czego aplikacja nie ma sensu: „chcę być w App Store” wpisujesz jako `obecnosc-w-sklepie`,
   nie udajesz innej potrzeby.
2. **Ocena:** `python3 $HERMES_HOME/scripts/decyzja.py ocen out/decyzja/potrzeby.yaml --out out/decyzja`.
3. **Interpretacja** (`references/macierz.md`):
   - pokazujesz zwycięzcę **i** to, co jest „blisko” (≤ 5 pkt): tam decyduje właściciel, opisz różnicę w jednym zdaniu,
   - ryzyko 4.2 (aplikacja nie daje więcej niż strona) mówisz wprost; jeśli właściciel i tak chce aplikację, wypisz,
     co musiałaby robić ponad stronę (powiadomienia, karta lojalnościowa, offline), żeby przejść recenzję i mieć sens,
   - rzadkie użycie (raz w miesiącu i rzadziej) = przypomnienia SMS/e-mail i karta w Wallet zamiast aplikacji,
   - koszty: licencje z datą sprawdzenia, praca jako szacunek; nie obiecujesz terminu recenzji sklepów.
4. **Następny krok:** propozycja karty z `decyzja.json` (`nastepny_krok`): PWA i strona → Web; Wallet i aplikacja →
   Twórca aplikacji; platforma → właściciel. Nic nie budujesz przed decyzją właściciela.
5. **Raport** `out/RAPORT.md`: rekomendacja w 3–5 zdaniach, tabela porównania (z `REKOMENDACJA.md`), pytania do decyzji.

## Wyjścia
`out/decyzja/potrzeby.yaml`, `REKOMENDACJA.md`, `decyzja.json`; `out/RAPORT.md`; w `metadata.decisions_needed` wybór
właściciela i propozycja następnej karty.

## Definition of Done
- [ ] `potrzeby.yaml` z celem, częstotliwością, funkcjami „musi” i „fajnie”, odbiorcami i budżetem (założenia oznaczone),
- [ ] rekomendacja z `decyzja.py`, opcje „blisko” opisane, ryzyka (4.2, rzadkie użycie, budżet) wprost,
- [ ] koszty licencji z datą, praca jako szacunek,
- [ ] następny krok z nazwą agenta; nic nie zbudowane przed decyzją.

## Typowe błędy
- Wpisanie wszystkich funkcji jako „musi”: każde rozwiązanie wtedy odpada i ranking traci sens.
- Rekomendacja aplikacji, bo „konkurencja ma”: to nie potrzeba klienta.
- Pominięcie karty w Wallet przy lojalności i karnetach: to często najtańsze rozwiązanie na iPhonie i Androidzie.
