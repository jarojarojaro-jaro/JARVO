# Rubryka filmu 0–100

Start: 100. Za każdą różnicę w osiach 1–5: −8, w osiach 6–10: −5. Pozycja blokująca: −15 i werdykt BLOCK,
dopóki nie zniknie. Wynik to liczba całkowita; PASS od 85 (przy czystej technice).

| # | Oś | Co sprawdzam | Przykład różnicy |
|---|---|---|---|
| 1 | Hook | treść w 0–2 s, zrozumiała bez dźwięku, klatka 0 nie jest pusta | „pierwsze 2 s to logo na czarnym tle” |
| 2 | Przesłanie | jedno, jasne; widz wie, po co oglądał | „dwa tematy: parzenie i ceny” |
| 3 | Dopasowanie obrazu | ujęcie pokazuje to, o czym mówi lektor | „scena 2 mówi o mleku, obraz: ziarna” |
| 4 | Rytm | zmiana obrazu co 2–4 s, brak dłużyzn, tempo lektora 2–3 słowa/s | „scena 4 stoi 6 s” |
| 5 | Napisy | poprawne, zsynchronizowane, czytelne, poza strefami UI | „nazwa marki z błędem w 0:07” |
| 6 | Dźwięk | głos wyraźny, muzyka pod głosem, bez trzasków i nagłych skoków | „muzyka głośniejsza od lektora w 0:12” |
| 7 | Jakość obrazu | ostrość, brak artefaktów AI, spójna kolorystyka | „scena 3 AI: zdeformowana dłoń” |
| 8 | Marka | kolory, font, logo, ton zgodne z kitem | „akcent napisów spoza palety” |
| 9 | Kadr i format | obiekty w kadrze po przycięciu, strefy UI wolne | „logo pod prawym paskiem przycisków” |
| 10 | CTA i zakończenie | jedno konkretne CTA (gdy karta chce), zakończenie nie urwane | „film kończy się w pół zdania” |

## Blokujące (−15, BLOCK)
- ujęcie ze znakiem wodnym, obcym logo albo rozpoznawalną osobą bez podstawy; muzyka bez licencji,
- deepfake, klon głosu realnej osoby, podszywanie się pod markę,
- fakt, liczba albo obietnica bez źródła; treść sprzeczna z kartą,
- jakakolwiek publikacja albo wgranie na konto bez zgody.

## Najmniejsza poprawka
Poprawka wskazuje jedno miejsce i jedną zmianę: `scena 3: "ujecie": {"stock_id": "pexels:…"}`,
`napisy: akcent "#E9C46A" (kolor z kitu)`, `montaz.py glosnosc … --lufs -14`. Nie „popraw rytm”, tylko co i gdzie.
