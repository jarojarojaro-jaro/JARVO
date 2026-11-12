---
name: szybki-research
description: "Domyślny research: 10–15 min, raport na jedną stronę."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [research, quick, citations]
    related_skills: [szybki-fakt, metoda-sherlocka, cytowania, weryfikacja-faktow]
  jarvo:
    agent: jarvo-sherlock
    autonomy: A1
    reviewed: "2026-11-12"
---

# Szybki research

Domyślny tryb każdej karty researchu (decyzja właściciela 12.11: podstawowy, dobry research ma trwać minuty, nie
godziny). Pytanie „jak to zrobić”, „co wybrać”, „czy to działa”, „jakie są opcje” → odpowiedź w 10–15 minut.
Pełna metoda (`metoda-sherlocka`: wątki, podagenci, tabele wszystkiego) tylko wtedy, gdy karta mówi wprost
„pełny research” albo „głęboki”. Jeden fakt (cena, data, limit) → `szybki-fakt`.

## Budżet
- **10–15 minut, najwyżej ok. 20 wywołań narzędzi**, 3–6 wyszukiwań, 4–8 przeczytanych stron.
- Bez podagentów (`delegate_task`), bez `git clone`, bez uruchamiania cudzego kodu, bez plików CSV i tabel
  „wszystkiego”: sprawdzasz to, co zmienia odpowiedź.
- Lista z karty (np. 15 repozytoriów) → sprawdzasz 3–5 najważniejszych dla odpowiedzi; resztę wymieniasz
  jednym zdaniem jako „nie sprawdzone”.

## Kroki
1. **Pytanie w jednym zdaniu** (`notes/brief.md`, jedna linia): co ma wiedzieć właściciel po przeczytaniu.
2. **Jedna runda szukania:** najpierw źródła pierwotne (dokumentacja, repozytorium, strona producenta, cennik).
   Strony czytasz przez `extract.py <url> --tier … --type …` (rejestr źródeł, numer `[n]`, skill `cytowania`).
3. **Stop**, gdy masz odpowiedź albo dwa kolejne wyszukiwania nic nie wnoszą. Czego nie znalazłeś, nie
   uzupełniasz z pamięci modelu: piszesz „nie potwierdzone”.
4. **Komendy i wersje** (przepis „zrób to tak”): flagę i nazwę pliku podajesz tylko z dokumentacji albo kodu
   tej samej wersji, którą każesz pobrać; czego nie sprawdziłeś, oznaczasz „sprawdź `--help`”.
5. Raport, `sources.py verify out/RAPORT.md --dowody`, przekazanie do oceny.

## Wynik: `out/RAPORT.md` (jedna strona, do ok. 400 słów)
```
# <pytanie>
**Odpowiedź:** <2–4 zdania z numerami [n]>
## Ustalenia
- <3–7 punktów: fakt, liczba, data, [n]>
## Rekomendacja
<co zrobić: 1 ścieżka, kroki, koszt i czas, gdy znane>
## Luki
<czego nie sprawdzono albo nie potwierdzono>
## Źródła
<blok z `sources.py render --replace-in out/RAPORT.md --styl dowody`>
```

## Definition of Done
- odpowiedź na pytanie z CEL w pierwszym akapicie, raport do ok. 400 słów,
- każde kluczowe twierdzenie z numerem źródła z rejestru; `sources.py verify out/RAPORT.md --dowody` bez błędów,
- luki nazwane wprost; budżet dotrzymany (w przekazaniu: czas i liczba wywołań).
