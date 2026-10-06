# Światłocień Rembrandta (`32_rembrandt`)

Barok z 1642 roku: prawie cały obraz tonie w ciepłym brązowym mroku, światło z okna i ze świecy wycina twarz, dłonie
i filiżankę. Grubo nałożona farba (impast) tylko w światłach, ciemna strona postaci rozpływa się w tle, na wierzchu
spękania, ziarno, winieta i złotobrązowy werniks. Jakość wzoru: ★ (do zrobienia od nowa); słabość wzoru: postać jest
płaska (ocena 5/10), ten styl najbardziej wymaga przebudowy (przebij ją).
Wzór: `python3 $HERMES_HOME/scripts/malarz.py wzor 32_rembrandt --czasy 0.4,0.8,1.2 --arkusz out/wideo/wzor-32_rembrandt.jpg`;
kod `$HUASHU/scripts/engine/scenes/32_rembrandt.js` (MIT). Wzór to scena z dziewczyną, kotem i stołem: bierzesz
technikę, nie scenę.

## Do czego
- Muzeum, historia, archiwum, dokument: 20–60 s z lektorem, nastrojowo.
- Marka premium „z tradycją”: whisky, kawa, czekolada, zegarmistrz, rzemiosło: 10–30 s.
- Scena wieczorna, przy świecy; zapowiedź podcastu kryminalnego albo historycznego: 15 s.

## Nie do
- Jasny, radosny ton: `16_2026`, `31_haring` albo `30_matisse`.
- Przekaz, w którym cały kadr musi być czytelny: otoczenie ma tylko ok. 0,13 światła, detale poza plamami światła
  giną.
- Twarde, nowoczesne światło bez faktury farby: `24_hopper`.

## Cechy stylu (sprawdzalne)
- Mapa światła: tło rgb(30,21,13), czyli światło otoczenia ok. 0.13. Na nie w trybie `lighter`:
  - snop światła z okna: klinowy wielokąt, blur 40 px, w cache, α 0.8–0.95;
  - samo okno: r330;
  - twarz r250 α0.95, pierś r230 α0.55, kot r240 α0.8, blat r280 α0.6;
  - świeca: r190+40·fc, α 0.6+0.4·fc;
  - „światło oddzielające” na ścianie za ciemną stroną postaci: r300 α0.35 (Rembrandt rozjaśnia ścianę za cieniem
    postaci, żeby oddzielić ją od tła);
  - całą mapę nakładasz na obraz w `multiply`.
- Pociągnięcia tła: cell18, len54, w16, jitter 6, kąt −0.9 + 1.6·noise(0.003); paleta mixBase 0.7; potem rozmycie
  2,2 px nałożone w 75% (rozcierany podkład).
- Utrata krawędzi: postać najpierw z `blur(2.4px)` w pełnym kryciu, na to ostra warstwa α0.62. Ciemna strona wtapia
  się w tło, rysy twarzy zostają czytelne.
- Impast (pędzel z włosia): jedno pociągnięcie = round(w/1.3) cienkich równoległych włosków, każdy z jasnością ±17,
  końce losowo skrócone o 0–25%, grubość 1.4–2.6; pod spodem cień α0.28, na wierzchu 2+w/3 jasnych punktów. Tylko
  w światłach: blond włosy, kołnierz, porcelanowa filiżanka, perła, biała pierś kota, czubek głowy kota.
- Warstwy wierzchnie: spękania α0.28×0.28; ziarno density 0.05 α0.12; winieta 0.75; `soft-light`
  rgba(200,140,60,.35).
- Palety regionów (z kodu, `PAINT.swatch`): ściana `#5a3c20 #6e4a28 #4e3418 #6a4a28 #4a3018 #765030` (0.7), mrok
  `#2a1a0c #3a2412 #1e1208 #4a2e16` (0.5), kilim `#8a2e18 #6a2010 #a8441e #c8943a #2a3a5a` (0.7), szyba
  `#fff2d0 #f2d8a0 #e8c888 #fff8e8` (0.6).
- Kroje plakietki we wzorze: `CormorantGaramond-500`, podpis `IMFellEnglish-400i`; oba mają polskie znaki.

## Jak go zbudować
Kolejność warstw:
1. Szkielet: `python3 $HERMES_HOME/scripts/malarz.py nowy out/wideo/src/film --styl 32_rembrandt`. `P` = `PAINT`
   (`paint.js`, `brush.js` z `P.impasto`, `render.js` z `P.lightMap`/`P.applyLight`/`P.pool`).
2. Jasny podkład, czyli kolory „w pełnym świetle”: pokój, okno z ołowianymi szprosami w romby, turecki kilim na stole.
3. Brązowe szerokie pociągnięcia na tle (`P.strokes`, parametry wyżej), rozmycie 2,2 px w 75%. Statyczne, więc do
   cache (`rb_static`).
4. Kilim osobną warstwą, drobne pociągnięcia.
5. Postać: płasko, gradient objętości, drobne pociągnięcia, potem utrata krawędzi.
6. Mapa światła: `P.lightMap('klucz', 'rgb(30,21,13)', g => { … P.pool(g, x, y, r, 'r,g,b', a) … })`, potem
   `P.applyLight(c, mapa)` (multiply). Snop światła raz do cache (`rb_beam`).
7. Szyba: rozjaśnienie `screen` i przesuwający się cień chmury.
8. Impast (`P.impasto(c, punkty, w, kolor, blask)`) tylko w światłach.
9. Płomień świecy, kurz w snopie, para.
10. Spękania (`P.craquelure`), ziarno (`P.grain`), winieta – raz do cache (`rb_over`); na koniec `soft-light`
    złotobrązowy werniks.

## Co się rusza
- Ruch główny: picie herbaty, para.
- Migotanie: `flick(t) = 0.5·noise(2.2t) + 0.25·noise(6.5t)`; środki plam światła dryfują z noise(0.9t) o ±14 px.
- Chmura: `cloud = 0.5 + 0.5·sin(2.2t − 0.6)`, światło okna ×(1 − 0.35·cloud), a ciemna radialna plama przejeżdża
  przez szybę z prędkością 260 px/s.
- Płomień świecy (noise przechyla go na boki i zmienia wysokość); w snopie 70 drobin kurzu (`P.particles`, widoczne
  tylko w snopie, migoczą: α `0.25 + 0.5·(0.5 + 0.5·sin(4t + 2.1i))`).
- Pole ruchu 8,0% (między 0,45 a 1,0 s).

## Przejście-podpis (wejście w ten styl)
- `chiaroscuro`, 0,45 s (`cx 580, cy 300` – okno): stary obraz zapada się w ciemny brąz (winieta zamyka się od
  brzegów, `multiply`), potem skośny snop z okna (blur 40 px) odsłania nowy obraz, z ciepłym blaskiem `lighter`;
  od p>0,8 wywołują się też ciemne partie. Uwaga: w indeksie źródła przy Rembrandcie stoi „przysłona starej taśmy”
  – to `irisFilm`, które w kodzie prowadzi do `33_rubberhose`.

## Wydajność
- Ok. 47 ms na klatkę.
- Cache: tło z pociągnięciami (`rb_static`), snop (`rb_beam`), warstwy wierzchnie (`rb_over`). Mapę światła licz
  co klatkę (migocze), na płótnie z `P.lightMap` (sam robi `reset()`).

## Pułapki
- Impast jako trzy równe linie (cień, pociągnięcie, jasny grzbiet) wygląda jak biała naklejka albo plaster. Rób go
  włosiem (`P.impasto`).
- Kopiowanie fragmentu podkładu (`drawImage(b, x,y,w,h…)`) przenosi tło bez pociągnięć i zostawia prostokątną łatę.
  Rekwizyty rysuj osobną warstwą po pociągnięciach, nie kopiuj obszarów.
- Ziarno density 0.12 / α0.22 brudzi twarz kropkami; 0.05 / 0.12 jest w sam raz.
- Dłoń rysuj przed filiżanką, bo inaczej elipsa dłoni zakryje porcelanę. Kolejność w `drawGirl`: „dłoń → filiżanka →
  kciuk” – trzymaj ją, gdy rysujesz postać od nowa.
- Słabość wzoru: postać płaska. Przepuść ją przez ten sam renderer co tło (pociągnięcia, utrata krawędzi, impast),
  a mapa światła ma modelować jej bryłę.

## Kontrola
- Czy otoczenie jest naprawdę ciemne, a światło skupia się na twarzy, dłoniach i filiżance?
- Czy ciemna strona postaci rozpływa się w tle, a rysy twarzy są czytelne?
- Czy impast jest tylko w światłach i wygląda jak farba, nie jak naklejka?
- Czy światło okna oddycha (chmura), a świeca migocze?
- Czy twarz nie jest zabrudzona ziarnem?
