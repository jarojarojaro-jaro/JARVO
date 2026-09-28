---
name: graf-kodu
description: "Mapa dużego repo: kto woła funkcję, co zmiana posypie."
version: 1.0.0
author: "Jarvo (silnik: codebase-memory-mcp, DeusData, MIT)"
license: MIT
metadata:
  hermes:
    tags: [code, graph, refactor, impact, call-graph]
  jarvo:
    autonomy: A0
    reviewed: "2026-09-28"
---

# Graf kodu

Szybka mapa **istniejącego, dużego** kodu (setki plików, cudze repo, aplikacja klienta): zamiast czytać plik po
pliku pytasz „kto woła tę funkcję?”, „co ona uruchamia?”, „co dotknie moja zmiana?”. Lokalnie, bez klucza API
i bez tokenów modelu.

## Kiedy użyć
- zmiana w cudzym albo dużym repo: zanim ruszysz funkcję, sprawdź wywołujących (`kto-wola`),
- refaktor, zmiana nazwy albo sygnatury, usuwanie „martwego” kodu,
- pierwsze wejście w nieznany projekt (`architektura`), przegląd diffu przed oddaniem (`wplyw`).

## Kiedy NIE używać
- mała strona albo skrypt, który piszesz od zera: zwykłe szukanie (`grep`, odczyt pliku) jest szybsze,
- pytania o treść, dokumenty, markę: to nie jest baza wiedzy, tylko kod.

## Kroki
```bash
G=$HERMES_HOME/skills/kod/graf-kodu/scripts/graf_kodu.py
python3 $G indeks <repo>                          # na początku zadania (pierwszy raz pobiera silnik, ~41 MB)
python3 $G architektura <repo>                    # nieznany projekt: języki, pakiety, trasy, gorące miejsca
python3 $G kto-wola <repo> <funkcja>              # przed zmianą funkcji
python3 $G co-wola <repo> <funkcja> --glebokosc 3
python3 $G szukaj <repo> '.*Checkout.*' --rodzaj Function
python3 $G wplyw <repo>                           # po zmianach, przed oddaniem: co dotknięte i z jakim ryzykiem
```
Nazwa niejednoznaczna → skrypt wypisze pełne nazwy (`projekt.moduł.funkcja`), podaj właściwą.
Po większych zmianach `indeks` jeszcze raz (ok. 7 s na repo wielkości Jarvo; jedno pytanie ok. 5 s).

## Zasady
- **Graf to wskazówka, nie dowód.** Rozwiązuje nazwy statycznie: przy dwóch funkcjach o tej samej nazwie w różnych
  modułach potrafi przypisać wywołania nie tej, a importów dynamicznych (ładowanie modułu po ścieżce, `eval`) nie widzi.
  Każde miejsce, które zmieniasz albo uznajesz za nieużywane, **potwierdź odczytem pliku** (`grep -rn`).
- „0 wywołujących” nie znaczy „martwy kod”: sprawdź importy dynamiczne, szablony, wywołania z HTML i konfiguracji.
- Do raportu: wynik `wplyw` jako lista dotkniętych funkcji; w `metadata.risks` to, czego graf nie widzi.
