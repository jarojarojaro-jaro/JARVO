# Rysunek klatka po klatce (wzór `05-cel-boil`)

Animacja rysunkowa jak z tuszu i papieru: kreska „wrze” (każdy rysunek jest trochę inny), ruch idzie na dwójkach,
kolor wyjeżdża poza kontur. Widz poznaje styl po drżącej linii i rytmie 12 rysunków na sekundę.
Wzór: okładka `$MGSTYLES/videos/05-cel-boil.jpg`, kod `$MGSTYLES/demos/05-cel-boil/` (MIT), ocena jury 8,07;
1920×1080, 24 kl./s, 10 s (240 klatek). Klatki wzoru (0,375 smear, 0,417 kopie, 6,5 i 6,542 klatki uderzenia;
ok. 0,3 s na klatkę na 4 rdzeniach bez GPU; `$MGSTYLES` z `narzedzia.py env mg`):
```
python3 $HERMES_HOME/scripts/html_wideo.py klatki $MGSTYLES/demos/05-cel-boil/index.html --preset mg \
  --czasy 0.375,0.417,1.5,4,6.5,6.542,9 --arkusz out/wideo/wzor-05-cel-boil.jpg
```

## Do czego
- Piekarnia rzemieślnicza, palarnia kawy, browar kraftowy: spot „robione ręcznie”, 9:16 i 1:1, 15–20 s.
- Szkoła, przedszkole, dom kultury, biblioteka gminna: zaproszenie na warsztaty albo festyn, 9:16, 15 s.
- Maskotka restauracji albo sklepu: intro postaci na stronę i social, 16:9 i 1:1, 8–12 s.
- Cukiernia, pracownia ceramiki, kwiaciarnia: seria 3 filmów po 10 s z jedną postacią.

## Nie do
- Dane, B2B, finanse, prawo (wygląda niepoważnie): `plaski-wektor.md` albo `izometria.md`.
- Marka premium i spokojna: `rysunek-linia.md`. Dużo tekstu, częste zmiany treści: `plaski-wektor.md`.
- Długa historia z wieloma ujęciami postaci (> 30 s): skill `anidoodle` (`motion-graphics.md`, `rodzaje-filmu`).

## Cechy stylu (sprawdzalne)
- Ekspozycja przy 24 kl./s: ruch na dwójkach (12 rysunków/s), szybka akcja na jedynkach (potarcie, skok, obrót),
  zawieszenie na trójkach („ta-da”, koniec). Wzór: 11 odcinków, 146 rysunków na 240 klatek.
- Wrzenie: punkty linii przesunięte szumem o 2,2–2,4 px przy skali 70 px (tytuł 1,6–1,8 przy 80, drobny napis 0,9
  przy 30). Stojące rzeczy krążą po 4 wariantach (3 na trójkach), ruchome dostają nowy rysunek co rysunek.
  W zbliżeniu amplituda i grubość × 0,55–0,7 (ta sama ręka w każdym planie).
- Piórko 6 px (scena ×1,4): zwężenie 14 px na początku i 26 px na końcu do 25%, nacisk ±35%, prawy dół +35%,
  okrągłe końce; zamknięte kształty 1–2 pociągnięciami, wyjazd 2,5 px. Kolor przesunięty o (−5, +4) px, wrze osobno.
- Uderzenie: klatka 9 smear (główka ciągnięta wstecz o 1,1× drogi z klatki), klatka 10 trzy kopie pozy, klatka 12
  biały błysk. Kulminacja 6,5 s (65%): klatka czarna i czerwona po 1 klatce, wstrząs 18 px gaśnie do 7,2 s.
- Efekty: dym znika w 4 rysunkach (pełny → dziura → większa dziura → pierścień), 30 iskier, linie prędkości.
- Papier: krem `#F6ECD4`, ząbek mnożony z siłą 0,5 i przesuwany co rysunek, kurz 0,22 zmieniany co rysunek.
- Paleta wzoru (role): tusz `#1C1613`, czerwień `#E5402B`, żółć `#FFC425`, krem `#F4E9D0`; u klienta 3–4 kolory marki.

## Technika
- Canvas 2D (`kontrakt-html.md`, skill `rodzaje-filmu`), 24 kl./s. Z `/_lib/jarvo/kreska.js` (silnik wzoru):
  `rysunek`, `kreska`, `petla`, `wypelnij`, `kreskowanie`, `okrag`, `splajn`, `przeksztalc`, `PRZESUNIECIE`.
- Na początku `__seek`: `const R = rysunek(t, 24, PLAN)`. Ruch postaci z `R.t`, iskry i błyski z `R.t1`, ziarno
  wrzenia `R.id` (w ruchu) albo `R.wariant` (stoi). Plan wzoru (od klatki, krok):
  `[[0,2],[8,1],[24,2],[48,1],[60,2],[108,3],[120,2],[132,1],[168,2],[224,1],[230,3]]`.
- Kształt: `przeksztalc(P, {x, y, r, sx, sy})` (`sx`, `sy` z `ladowanie(R.t, t0, 'zabawny')` z `ruch.js`) →
  `wypelnij(g, gesta, kolor, {ziarno, ...PRZESUNIECIE})` → `petla(g, gesta, {ziarno, pociagniecia: 2})`; linie
  `kreska(g, P, {ziarno, w: 6})`, obrysy `okrag`, `splajn(P, true)`, cień `kreskowanie(g, poly)`; zbliżenie `waga`.
- Wykończenie z `plotno.js` (kurz wzoru nie ma źródła): pod spodem `papier(g, W, H, {kolor: '#f6ecd4'})`, na wierzchu
  `papier(g, W, H, {tryb: 'multiply', sila: 0.5, kartka: R.wariant})`, `kurz(g, W, H, R.wariant)`, lekka `winieta`.
- Smear = 1 klatka wydłużonego kształtu; kopie = 3 pełne pozy między rysunkami (`duchy(t, rysuj, 3, 1/96)`
  z `ruch.js`, `rysuj` pomija krycie). Bez podklatek.
- Tytuł (1–2 słowa): szkielety liter, `kreska` po kresce co 0,125 s, ogonki polskich liter jako osobne kreski.
  Dłuższy tekst: Caveat Brush, Caveat, Patrick Hand (`/_lib/kroje/kroje.css`) przez `fillText`, ±1 px i ±0,6°
  na wariant. Przed `__ready` dla każdego kroju kanwy `await document.fonts.load('64px "Caveat Brush"',
  'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')` (polskie litery są w osobnym pliku), teksty do `window.__teksty`.
- Do przeniesienia z `js/scene.js` (komentarz `// za mg-styles-15 (MIT), demos/05-cel-boil/js/scene.js`): dym
  `cloud`/`smokeGroup` (wiersze 692–783), `impactFrame` (1868+). `glyphPolys` pomiń: opentype nie czyta woff2.

## Rytm (10 s wzoru → film klienta)
| Czas | Co się dzieje |
|---|---|
| 0–0,33 | Hak: noc, zapałka cofa się (przygotowanie na dwójkach), czerwone światło na konturach |
| 0,33–1,0 | Potarcie na jedynkach: smear, kopie, błysk; zapłon 0,5 s, zapałka ląduje na pudełku 1,0 s |
| 1,0–2,5 | Płomyk się budzi (oczy, mrugnięcie), przysiad, skok na jedynkach 2,0 s, lądowanie 2,5 s |
| 2,5–6,25 | Taniec na dwójkach w takt (co 0,5 s), „ta-da” na trójkach 4,5 s, obrót i najazd 1,4× → 2,05× |
| 6,5 | Kulminacja: klatka czarna + czerwona, dym, iskry, wstrząs |
| 7,25–8,83 | Iskry piszą tytuł (11 kresek co 0,125 s), tytuł osiada 8,5 s, napis i hasło do 8,83 s |
| 9,1–10 | Odjazd do kartki (100 → 84%), kartkowanie rysunków, mrugnięcie 9,7 s, koniec na trójkach |
- 15 s: odcinki × 1,5, kulminacja ok. 9,5 s (63%) po 0,3 s wstrzymania na trójkach, logo i hasło od 12 s, koniec
  stoi 1 s (wrzenie = drobny ruch). 30 s: dwie sceny „tańca” (np. wałek i bochenek).
- 9:16: nowy układ z `L.u = Math.min(W, H) / 100`: postać w środkowej 1/3 wysokości, tytuł nad nią, hasło pod nią.

## Dźwięk
- Swingujący jazz 120 BPM (bit co 0,5 s = 12 klatek): kontrabas pizzicato, ksylofon, miotełki, pianino;
  akcent z `projekt.py dzwieki --kategoria dzingle` (pizzicato).
- Cue ok. 0,03 s przed klatką: potarcie `scratch` + `burner`, skok `whoosh`, lądowania `pop` i `boing`, iskry
  `sparkle`, kreska tytułu = nuta (`chime`, `pitch` 0,9 → 1,3), kartkowanie `kartka` (`--kategoria codzienne`).
- Kulminacja: 0,25 s ciszy, potem `thump` + `crack` + `bum-kreskowka` najgłośniej (reszta `vol` 0,5–0,8); −14 LUFS.

## Pułapki
- Ziarno wrzenia = numer klatki (szum zamiast rysunku) albo ruch postaci z `t` zamiast `R.t` (filtr, nie animacja).
- Prompt chce papieru 10–15%, kod przyciemnia o kilka procent: zostań przy kodzie (mocny papier brudzi kolory marki).
- Błysk, klatki uderzenia i wstrząs to uderzenia całego kadru: najwyżej 3 na film (`pomiar`: `uderzenia_kadru`);
  `qa_wideo.py` może zgłosić klatkę uderzenia jako „mrugnięcie”: zamierzone, wpisz do RAPORT.
- Układ wzoru na sztywno 1920×1080 (`STAGE`, `CLOSE`, `C0`): przenosisz funkcje, nie współrzędne. CPU: na dwójkach
  dwie klatki mają ten sam rysunek, więc gotową warstwę postaci trzymaj w `Map` po `R.id`.
- Szkielety liter wzoru to tylko H, A, N, D, M, E (+ F, R, B, Y): polskie litery dorysowujesz sam.

## Kontrola
- `python3 $HERMES_HOME/scripts/html_wideo.py klatki out/wideo/src/index.html --preset jarvo --fps 24
  --czasy 0.5,0.542,9.5,9.542,14.5 --arkusz out/wideo/arkusz.jpg` (smear i kopie, dwie klatki uderzenia, koniec).
- `krytyka.py pasek out/wideo/film.mp4 --t 9.5 --klatek 12`: na dwójkach pary klatek z tą samą pozą, kreska zmienia
  się co rysunek; stojący przedmiot ma 4 różne rysunki, piąty = pierwszy.
- `… pomiar out/wideo/src/index.html --preset jarvo --dlugosc 15` bez błędów, potem `… wideo out/wideo/src/index.html
  --preset jarvo --dlugosc 15 --fps 24 -o out/wideo/film.mp4` (360 klatek po ok. 0,3 s, przeglądarki równolegle: 1–2 min).
- `krytyka.py telefon out/wideo/film.mp4`: kontur widać (9:16: piórko ≥ 6 px), ogonki są, koniec stoi ≥ 0,8 s.
