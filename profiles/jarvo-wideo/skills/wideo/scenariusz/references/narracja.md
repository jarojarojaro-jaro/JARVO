# Narracja filmu, który coś wyjaśnia

Tekst lektora do explainera, filmu „wyjaśnij mi filmem” i każdego filmu z kodu, w którym lektor prowadzi widza.
Krótka reklama 20–40 s idzie wzorami z `hooki.md`; tu chodzi o to, żeby widz po 60–90 s rozumiał, a nie tylko zapamiętał.

Zasady i wynik ślepego porównania za anything2explainer (licencja niekomercyjna: bierzemy myśl i liczby, opis jest
nasz): ten sam materiał napisany według tych zasad oceniono na 8,2/10, a ułożony po kolei za spisem treści źródła na 4,3/10.

## Zasady
1. **Zacznij w sytuacji, nie w definicji.** Widz jest gdzieś i coś mu się dzieje: „Wchodzisz do piekarni o siódmej,
   przed tobą dziesięć osób”. Nie „Kolejka to zjawisko…”, nie „Cześć, dziś opowiem…”.
2. **Jedna linia opowieści.** Każdy akapit wynika z poprzedniego: „więc”, „ale”, „dlatego”, „i wtedy”. Test: przestaw
   dwa akapity. Nic się nie psuje? To nie opowieść, tylko lista; przepisz.
3. **Dlaczego → jak → co z tego masz.** Najpierw problem i stawka dla widza, potem mechanizm, na końcu skutek w jego
   życiu albo firmie. Mechanizm bez stawki nikogo nie trzyma.
4. **Liczba w skali, którą czuć.** „3,5 mln bochenków rocznie” → „jeden co dziewięć sekund, dzień i noc”. Liczba bez
   przeliczenia albo bez źródła (`fakty.json` od Sherlocka) wypada z tekstu.
5. **Jedna analogia przez cały film.** Wybierz ją raz i wracaj do niej (kolejka, sito, magazyn), zamiast nowej co
   akapit. Wiesz, gdzie się psuje (brief Sherlocka): tam jej nie ciągniesz.
6. **Najpierw prosta myśl, potem nazwa.** „Sklep pamięta, co oglądałeś. Ta pamięć to ciasteczko.” Termin przed
   myślą widz musi przetłumaczyć sam i gubi wątek.
7. **Lektor nie opisuje obrazu.** „Na ekranie widzisz wykres” marnuje zdanie: obraz to pokazuje. Lektor mówi to,
   czego obraz nie powie (dlaczego, co z tego wynika).
8. **Koniec odwraca początek.** Wróć do sytuacji z pierwszego zdania i pokaż ją inaczej („Następnym razem, gdy
   staniesz w tej kolejce, wiesz, że to nie piekarz jest wolny”). Nigdy „Podsumowując…” i powtórka punktów.
9. **Rozdział kończy się pytaniem**, na które odpowiada następny (tylko film od 3 min, z rozdziałami `#`).

## Liczby (Edge TTS, `film.py narracja` z domyślnymi pauzami)
- Ok. 2 słowa na sekundę gotowego filmu: 60 s ≈ 120 słów, 90 s ≈ 180, 3 min ≈ 360. Zmierzone tempo samego
  czytania Marka przy `+0%` z pauzami w akapicie: ok. 2,3 słowa/s; powyżej 2,7 widz nie nadąża.
- Zdanie ≤ 20 słów, strona czynna; jedno zdanie w linii pliku narracji.
- Akapit = ujęcie = jedna myśl obrazu: 2–4 zdania, co najmniej 4 s. Krótszy akapit połącz z sąsiednim.
- Rozdziały tylko od 3 min: 3–5 min = 3–4 rozdziały po co najmniej 60 s; krótszy film to jedna opowieść.
- Napis ≤ 42 znaki: dłuższe zdanie dzielisz `|` w miejscu oddechu.

## Kontrola (`film.py narracja --sprawdz`)
Skrypt łapie to, co da się złapać ze słów: start od definicji albo powitania, akapity zaczynane jak lista („po
pierwsze”, „kolejny”, „ponadto”), lektor opisujący obraz („na ekranie”, „jak widać”), koniec, który streszcza
(„podsumowując”, „w skrócie”), rozdział bez pytania na końcu, kilka zdań w linii, za długie zdania, napisy i akapity.
Z briefem Sherlocka (`fakty.json` obok narracji) sprawdza też liczby zapisane cyframi: z listy niepewnych = błąd,
bez pokrycia w briefie = ostrzeżenie; liczbę słowami („dziesięć osób”) przepuszcza, więc fakt piszesz cyframi.
Linii opowieści, analogii i skali liczb nie sprawdzi: czytasz tekst na głos i odpowiadasz na testy z zasad 2, 4 i 5.
