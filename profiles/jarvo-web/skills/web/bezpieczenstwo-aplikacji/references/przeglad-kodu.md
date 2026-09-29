---
source: "Metodyka anthropics/claude-code-security-review (MIT, Anthropic 2025), claudecode/prompts.py i findings_filter.py; zaadaptowane po polsku"
reviewed: "2026-09-29"
---
# Przegląd kodu jak security engineer

**Cel:** ustalenia z realnym potencjałem wykorzystania, nie ogólny code review. Fałszywy alarm kosztuje zaufanie.

## Zasady
1. Zgłaszasz tylko przy pewności **≥ 0,8**, że da się to wykorzystać; każde ustalenie ma **scenariusz ataku** krok po kroku.
2. Pomijasz: teoretyczne ryzyka bez ścieżki ataku, styl, DoS i wyczerpanie zasobów (to krok 15 listy), sekrety w plikach
   na dysku serwera (to skan, krok 1).
3. Nawet coś wykorzystywalne tylko z sieci lokalnej może być WYSOKIE.

## Kategorie
- **Wejście:** SQL/NoSQL injection, command injection, path traversal, template injection, XXE.
- **Autoryzacja:** obejście logowania, eskalacja uprawnień, błędy sesji, JWT (brak weryfikacji, `alg: none`), IDOR
  (cudzy rekord po zmianie ID w adresie).
- **Kryptografia i sekrety:** klucze w kodzie, słabe algorytmy, przewidywalna losowość (`Math.random` do tokenów),
  wyłączona weryfikacja certyfikatu.
- **Wykonanie kodu:** deserializacja (pickle, YAML), `eval`, XSS (odbity, zapisany, DOM).
- **Ujawnienie danych:** dane wrażliwe w logach i odpowiedziach API, zbyt szerokie `select *` zwracane do klienta,
  informacje debug.

## Metoda (3 fazy)
1. **Kontekst:** jakie biblioteki bezpieczeństwa i wzorce ma projekt (walidacja, ORM, middleware auth), jaki model zagrożeń.
2. **Porównanie:** gdzie nowy/badany kod odstępuje od bezpiecznych wzorców projektu, gdzie powstaje nowa powierzchnia ataku.
3. **Przepływ danych:** od każdego wejścia (formularz, parametr, nagłówek, webhook, plik) do operacji wrażliwych
   (zapytanie, system plików, powłoka, HTML, przelew).

## Format ustalenia (do RAPORT.md i JSON)
```json
{"plik": "src/api/orders.ts", "linia": 42, "waga": "WYSOKIE", "kategoria": "idor",
 "opis": "GET /api/orders/:id zwraca zamówienie bez sprawdzenia właściciela",
 "scenariusz": "zalogowany użytkownik zmienia id w adresie i czyta cudze zamówienia z adresami",
 "poprawka": "where id = $1 and user_id = $2 (z sesji)", "pewnosc": 0.9}
```
