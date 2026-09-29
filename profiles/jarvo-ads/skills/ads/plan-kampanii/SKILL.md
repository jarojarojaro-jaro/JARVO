---
name: plan-kampanii
description: "Plan kampanii Meta/Google: cel, struktura, budżet, prognoza."
version: 1.0.0
author: "Jarvo"
license: MIT
metadata:
  hermes:
    tags: [ads, meta, google, campaign, planning]
    related_skills: [ads, plan-testu, start-kampanii, sledzenie-konwersji]
  jarvo:
    agent: jarvo-ads
    autonomy: A1
    reviewed: "2026-09-29"
---

# Plan kampanii

Każda płatna akcja zaczyna się od planu. Plan to dokument, który użytkownik czyta w 2 minuty i wie: po co, za ile,
co dostanie i po czym poznamy sukces.

## Wejścia (o co zapytać, jeśli brak)
- **cel biznesowy** (sprzedaż, leady, zapisy, instalacje, ruch, rozpoznawalność) i **miara sukcesu** (np. CPA ≤ 40 zł),
- produkt/oferta, strona docelowa (URL), grupa docelowa, rynek i język,
- budżet (łącznie lub dziennie) i termin; brak budżetu → zaproponuj 2 warianty (minimum sensowne i rekomendowane),
- dostępne kreacje; brak → brief dla Studia/Wideografa w planie,
- stan śledzenia konwersji (piksel/CAPI, konwersje Google); brak → `sledzenie-konwersji` zanim wydamy na konwersje.

## Kroki
1. **Cel → typ kampanii.** Meta: Sprzedaż / Leady / Ruch / Aktywność / Rozpoznawalność / Promocja aplikacji
   (`references/meta.md`). Google: Search (popyt istnieje), Performance Max (sklep, feed), YouTube/Demand Gen (popyt
   do zbudowania) (`references/google.md`). Kampania na konwersje bez śledzenia konwersji = błąd planu.
2. **Platforma.** Popyt aktywny (ludzie szukają) → Google Search. Popyt do wywołania, produkt wizualny → Meta.
   Mały budżet (< 50 zł/dzień) → jedna platforma, jedna kampania.
3. **Struktura.** Mało kampanii i zestawów, dużo sygnału: Meta zwykle 1 kampania, 1–3 zestawy, 3–6 reklam;
   Google Search: grupy reklam po intencji, 1 RSA na grupę + rozszerzenia. Konwencja nazw niżej.
4. **Odbiorcy / słowa kluczowe.** Meta: szeroko + wykluczenia; zainteresowania tylko przy małym rynku.
   Google: frazy o intencji zakupowej, dopasowanie do frazy/ścisłe na start, lista wykluczeń od dnia 1.
5. **Budżet i czas.** Meta: ≥ 50 wyników/tydzień na zestaw, żeby wyjść z fazy uczenia; jeśli budżet nie pozwala,
   optymalizuj na zdarzenie wyżej w lejku (np. dodanie do koszyka, lead zamiast zakupu). Min. 7 dni.
6. **Prognoza.** `$HERMES_HOME/scripts/planer.py prognoza --budzet … --dni … --cpm … --ctr … --cvr …`. Założenia z konta
   (`ads.py statystyki`) albo jawnie oznaczone jako założenie z widełkami.
7. **Testy (opcjonalnie).** Kilka wersji reklam → `plan-testu`. Jedna dobra reklama też jest ok: wtedy mierzymy względem celu.
8. **Koperta.** Budżet łączny, maks. dziennie, daty, konta, co wolno w kopercie (wyłączać słabe, przesuwać budżet).

Punkt kontrolny: czy ktoś spoza projektu zrozumie z planu, co i dlaczego? Czy prognoza ma źródło założeń?

## Konwencja nazw
`<MARKA>_<platforma>_<cel>_<RRMMDD>` (kampania), `<odbiorcy>_<miejsca>` (zestaw/grupa),
`<test>_<atrybuty>_<format>_v<n>` (reklama), np. `JARVO_meta_leady_260930`, `szeroko_PL_auto`, `T01_hook-pytanie_9x16_v1`.

## Wyjścia
`out/PLAN.md`: cel i miara, platforma i typ kampanii (dlaczego), struktura (tabela), odbiorcy/słowa, budżet i koperta,
prognoza z widełkami, ryzyka, brief kreacji (lub link do `out/brief-kreacji.md`), co musi zrobić użytkownik (zgoda, konto).

## Definition of Done
- [ ] cel biznesowy i miara sukcesu wpisane liczbą,
- [ ] typ kampanii uzasadniony celem, struktura w tabeli z nazwami wg konwencji,
- [ ] prognoza z `planer.py`, założenia z danych konta albo oznaczone,
- [ ] koperta: łącznie, dziennie, daty, co wolno w kopercie,
- [ ] śledzenie konwersji sprawdzone (albo kampania nie optymalizuje na konwersje).

## Typowe błędy
- rozdrobnienie budżetu na wiele zestawów (nikt nie wyjdzie z uczenia),
- optymalizacja na zakup bez piksela/CAPI,
- Google Search na dopasowaniu przybliżonym bez wykluczeń (przepalanie na nietrafione hasła),
- obiecywanie wyniku zamiast widełek.
