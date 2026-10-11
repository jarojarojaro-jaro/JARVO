---
name: raport-reklam
description: "Raport wyników reklam: tydzień, kampania, test, eksport CSV."
version: 1.1.0
author: "Jarvo"
license: MIT
metadata:
  hermes:
    tags: [ads, reporting]
    related_skills: [optymalizacja, publikacja-reczna, wnioski-marki]
  jarvo:
    agent: jarvo-ads
    autonomy: A0
    reviewed: "2026-10-11"
---

# Raport reklam

## Źródła danych
- podłączone konto: `ads.py statystyki --konto … --od … --do … --poziom reklama --json`,
- bez podłączenia: eksport CSV z Ads Managera (Raporty → Eksportuj) albo Google Ads (Raporty → Pobierz CSV) →
  `$HERMES_HOME/scripts/eksport.py plik.csv` (tabela) / `--json` (dla `eksperyment.py`).

## Rodzaje
- **krótki** (Telegram, ≤ 8 linii): wydane / koperta, wynik i CPA vs cel, co się zmieniło, decyzja do podjęcia,
- **tygodniowy**: jak krótki + trend dzień po dniu (wykres PNG), najlepsze i najsłabsze reklamy, testy, wnioski, plan,
- **końcowy testu/kampanii**: pytanie → wynik z `eksperyment.py` (P, przedziały) → co to znaczy → wniosek → następny test.

## Zasady
- zawsze zakres dat i źródło danych; waluta i liczby w formacie polskim (1 234,56 zł),
- CPA/ROAS vs cel z planu, nie „dobrze/źle”,
- przy teście wielu zmiennych: „wygrał pakiet B”, nie „wygrał hook z pytaniem”,
- atrybucja: okno Mety (domyślnie 7 dni po kliknięciu, 1 dzień po obejrzeniu) i Google różnią się; nie sumuj konwersji
  z dwóch platform jako faktów (skill `attribution`),
- wykresy: HTML → PNG (Chromium z obrazu), jedna myśl na wykres, podpisane osie.

## Zmiany do wyklikania (bez podłączonego konta)
Gdy dane są z eksportu CSV, a kampanię prowadzi właściciel (`publikacja-reczna`), raport kończy się listą zmian,
które on wyklika: co (reklama, zestaw), co zrobić i gdzie (Menedżer reklam → Reklamy → przełącznik przy nazwie;
Google Ads → Słowa kluczowe → Wykluczające), dlaczego (liczba z raportu). Sam z siebie proponujesz tylko to,
co zmniejsza wydatek albo go nie zmienia (wyłącz słabą reklamę, wykluczenie, przesunięcie w tej samej kwocie).
Więcej pieniędzy, dłuższy termin albo nowa kampania to nowa prośba o zgodę i nowa paczka.

## Wyjścia
`out/raporty/<RRRR-MM-DD>.md` (+ PNG), krótka wersja do wiadomości, przy eksporcie CSV lista zmian do wyklikania.

## Definition of Done
- [ ] daty, źródło, waluta w każdym raporcie,
- [ ] werdykty testów z `eksperyment.py`, remis nazwany remisem,
- [ ] jedna konkretna rekomendacja na końcu (przy CSV: zmiany do wyklikania z miejscem i powodem).
