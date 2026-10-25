---
name: style-malarskie
description: "35 stylów malarskich: żywy obraz od jaskini do Van Gogha."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, painting, art-history, style, animation, canvas, procedural]
    related_skills: [rodzaje-filmu, film-z-kodu, style-motion, gramatyki-explainera, lektor-i-dzwiek, kontrola-wideo]
  jarvo:
    agent: jarvo-wideo
    autonomy: A1
    reviewed: "2026-10-06"
---

# Style malarskie

Żywy obraz w jednym z 35 stylów: malowidło jaskiniowe, Egipt, mozaika rzymska, gotycki rękopis, Van Gogh, Klimt,
tusz, piksel 8-bit, Hopper, Ghibli, Haring i inne. Kadr maluje kod: płaski podkład, renderer stylu (pociągnięcia,
kropki, kamienie mozaiki, raster), rekwizyty osobno, postać przez ten sam materiał i małe pętle motywów epoki, więc
obraz cały czas żyje. Silnik i 35 scen-wzorów to huashu-art-motion (MIT, 花叔) pod polską nakładką
(`/_lib/jarvo/huashu_pl.js`: kroje z ą–ż), a strona, render i kontrola są nasze (`malarz.py`, `html_wideo.py`).

## Kiedy
- Film albo ujęcie w stylu epoki lub malarza: spot marki kultury, luksusu, rzemiosła, historia firmy „od jaskini
  do dziś”, puenta z humorem, mocne otwarcie 3–6 s, tło pod lektora.
- Film o zmianie: przegląd epok, ta sama scena w kilku stylach, podróż bohatera przez obrazy (`metoda.md`,
  `dlugi-zwoj.md`), z przejściem-podpisem każdego stylu i cięciami na bicie (`rytm.md`).

## Nie do
- Styl motion design (wrząca linia, izometria, HUD, płaski wektor) → `style-motion`; styl kina na gotowym
  silniku (akwarela, anime, miedzioryt) w 30–75 s → `lemo-opuscar` (`film-z-kodu`).
- Fragment explainera z lektorem (wykres, tablica, 3b1b) → `gramatyki-explainera`.
- Kopia cudzego obrazu, postaci albo logo (Marvel, Ghibli, plakat z prawami): bierzesz gramatykę formy, nie dzieło.

## Przebieg (wszystko samo, bez zatwierdzania po drodze)
1. **Silnik raz:** `@@PY@@ "$HERMES_HOME/scripts/narzedzia.py" instaluj huashu`.
2. **Styl:** `references/wybor.md` (tabela 35 stylów i zasady wyboru), obraz wszystkich naraz:
   `malarz.py galeria -o out/wideo/galeria-stylow.jpg`. Czytasz tylko kartę wybranego stylu
   (`references/style/<id>.md`) i raz `references/metoda.md` (mechanizm, pięć warstw, renderery, pułapki).
3. **Wzór:** `malarz.py wzor <id> --arkusz out/wideo/wzor-<id>.jpg` (stopklatki sceny-wzoru: dziewczyna, kot
  i stół z ich filmu). Bierzesz technikę, nie scenę.
4. **Szkielet:** `malarz.py nowy out/wideo/src/film --styl <id>[,<id>…]` → `index.html` (kontrakt jarvo), `eras.js`
  (odcinki, ósemki przy BPM, przejście-podpis), `sceny/<id>.js` (kopia sceny-wzoru do przerobienia).
5. **Najpierw jedna klatka:** przerabiasz scenę na swój temat (szkielet sceny, przedmioty, postać, kolory marki),
  stopklatki `html_wideo.py klatki out/wideo/src/film/index.html --preset jarvo --czasy … --arkusz …` obok wzoru
  (vision): czy styl rozpoznajesz od razu, czy postać przeszła przez materiał stylu, polskie znaki.
6. **Ruch:** ruch główny i 2–4 pętle motywów w oknie postoju, bez migotania (karta: „Co się rusza”);
  `krytyka.py determinizm out/wideo/src/film/index.html --czasy 1.3,4.2 --preset jarvo`.
7. **Pomiar i film:** `html_wideo.py pomiar … --preset jarvo --dlugosc <s>` (błędy JS, kroje zastępcze, martwe
  odcinki), potem `html_wideo.py wideo … --dlugosc <s> -o out/wideo/<film>.mp4`. Do filmu idzie przez projekt
  edytora (`film-z-kodu/references/projekt-edytora.md`) z muzyką na siatce bitów (`rytm.md`); przed oddaniem
  `kontrola-wideo`.

## Pion 9:16
Silnik, 35 scen i przejścia mają kadr 1920×1080 na sztywno (stałe `W, H`). Film pionowy robisz z poziomego w
projekcie edytora: `projekt.py kadr <film> <id> --wypelnij --fx 0.5` (wycinek środka: główny przedmiot i postać
w pasie x 656–1264) albo `--rozmyte` (cały obraz, rozmyte tło nad i pod). Scenę pod pion komponujesz od razu tak,
żeby to, co ważne, stało w środkowym pasie.

## Zasady, które łamią się najczęściej
- **Postać przechodzi przez materiał stylu** (pociągnięcia, ziarno, papier przez `multiply`, raster), inaczej
  wygląda jak naklejka. Ludzie z klatek AI w stylu filmu (`postacie.md`, `malarz.py potnij` / `wytnij`).
- **Obraz żyje, ale nie migocze:** pociągnięcia stoją, zmienia się pole kierunków; „wrzenie” tylko linii rysunku.
- **Deterministycznie:** każdy los z ziarnem; ta sama chwila dwa razy = te same piksele.
- **Przejście-podpis z materiału nowego stylu**, 0,4–0,5 s gdy złożone; uderzenie kamery na obu warstwach
  (`przejscia.md`).
- **Postarzanie nie na postaci** (łuszczenie, plamy tylko w tle). Postaci autora silnika (`lib/rig_huashu.js`)
  nie używasz; szkielet `RIG` (dziewczyna, kot) to makieta i postać w stylach geometrycznych.
- **Tekst:** krój z polskimi znakami (nakładka podmienia kroje bez nich), „Zażółć gęślą jaźń” na arkuszu; litery
  ze ścieżek (`22_constructivism`) dopisujesz sam.

## Pliki
- `references/wybor.md`: 35 stylów w tabeli i zasady wyboru (ciężkie style, pion, żyjący artyści).
- `references/metoda.md`: pięć warstw mechanizmu, cztery drogi (kod, warstwy AI, obraz → wideo, mieszana),
  szkielet silnika, renderery, pułapki, specyfikacja autora stylu i samokontrola.
- `references/przejscia.md`: przejścia-podpisy (`TRANSITIONS`), jak je projektować, tabela przejść, pion 9:16.
- `references/postacie.md`: postacie z klatek AI i z kodu, wycinanie z zielonego tła.
- `references/dlugi-zwoj.md`: bohater idzie przez obrazy w jednym długim ujęciu.
- `references/rytm.md`: siatka bitów, coraz krótsze odcinki, muzyka i efekty na siatce.
- `references/zasady-huashu.md`: sprawdzone zasady z dowodami (ruch, przejścia, tekst, dane, kontrola).
- `references/style/<id>.md`: 35 kart stylów.

## Wynik
`out/wideo/<film>.mp4` (16:9, z projektu edytora także 9:16), strona i sceny w `out/wideo/src/<film>/`, arkusz
stopklatek obok wzoru, pomiar bez błędów; w RAPORT.md: styl i dlaczego, co zmieniłeś względem sceny-wzoru, czas
renderu, dwa inne kierunki, które można było dać (gdy właściciela nie było przy wyborze).
