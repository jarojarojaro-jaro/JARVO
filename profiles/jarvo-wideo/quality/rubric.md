# Rubryka: jarvo-wideo

## Blokujące (poprawki obowiązkowe)
- `qa_wideo.py` zgłasza błąd (kodek/pix_fmt, rozdzielczość albo proporcje niezgodne z formatem, czarny początek, głośność poza −20…−10 LUFS, za długi dla platformy).
- Brak werdyktu `out/wideo/<film>/kontrola.json` albo wynik < 85 bez nazwanych powodów i decyzji w `decisions_needed`.
- Hook dłuższy niż 2 s do pierwszej treści (plansza tytułowa, logo, cisza na starcie).
- Napisy z błędami (nazwy własne, liczby, polskie znaki), nieczytelne na telefonie albo w strefie interfejsu 9:16.
- Ujęcie ze znakiem wodnym, obcym logo, cudzym tekstem na ekranie albo rozpoznawalną osobą bez podstawy.
- Brak źródła i licencji ujęcia stock albo muzyki w `film.json`/RAPORT; muzyka bez prawa użycia; deepfake, klon głosu realnej osoby.
- Jakakolwiek publikacja, wgranie na konto albo planowanie posta bez zgody użytkownika.
- Obietnice, liczby i „fakty” w scenariuszu bez źródła (research → `jarvo-sherlock`).

## Ważne
- Scena bez zmiany obrazu dłużej niż ~4 s (bez ruchu, cięcia albo tekstu), rytm niezgodny z tonem.
- Lektor za szybki (> 3 słowa/s) albo za wolny (< 2), muzyka zagłusza głos, true peak > −1 dBTP.
- Brak wariantów, gdy karta ich wymaga; brak miniatury; brak `.srt` dla platform z napisami „miękkimi”.
- Brak rejestru generacji AI (prompt, model, koszt) albo przekroczony limit generacji z karty.
- Ujęcia niespójne kolorystycznie lub stylistycznie bez uzasadnienia; brak CTA, gdy karta go wymaga.

## Uwagi (nie blokują)
- Preferencje estetyczne w granicach brand kitu (krój napisów, kolor akcentu, przejścia).

## Rolki z długiego nagrania (clipmaker)
- Blokujące: rolka zmienia sens wypowiedzi (wycięte zaprzeczenie, cudzy pogląd jako teza, sklejone wątki);
  brak KANDYDACI.md z ocenami albo plan.json; `klipy.py sprawdz` z błędami; rolka bez projektu `.edycja.json`
  (człowiek nie może jej poprawić w HQ); twarz mówcy poza kadrem.
- Ważne: hook później niż w 3 s, rolka urwana w pół zdania, dwie rolki o tym samym temacie, oceny < 7 bez wyjaśnienia,
  nazwy własne i liczby w napisach niepoprawione, rolka zmieniona przez człowieka nadpisana przez `zbuduj`.
