# HUD, interfejs sci-fi (wzór `22-hud`)

Ekran celownika z filmu science fiction: cyjanowe linie na prawie czarnym tle, pierścienie z podziałką, radar,
kolumny liczb i ramki, które łapią cel, po czym cały ekran zmienia kolor na alarmowy. Poznasz go po narożnikach
ramki zaciskających się na celu i po liniach skanu.
Wzór: okładka `$MGSTYLES/videos/22-hud.jpg`, kod `$MGSTYLES/demos/22-hud/` (MIT), ocena jury 7,93; 1920×1080,
30 kl./s, 10 s. Klatki wzoru (6,4 s = namierzenie, kulminacja; Three.js z bloomem, ok. 1,5 s na klatkę na CPU):
```
python3 $HERMES_HOME/scripts/html_wideo.py klatki $MGSTYLES/demos/22-hud/index.html --preset mg \
  --czasy 1.5,4,6.4,6.6,9 --arkusz out/wideo/wzor-22-hud.jpg
```

## Do czego
- Firma IT, cyberbezpieczeństwo, SOC: „wykrywamy zagrożenie w sekundy”, 16:9, 10–15 s.
- Logistyka i kurierzy: „namierzamy Twoją paczkę” (mapa Polski, cel = magazyn), 9:16, 10–15 s.
- Drony, geodezja, monitoring upraw: pomiar działki z danymi na żywo, 16:9, 15–20 s.
- Gaming, e-sport, turniej w szkole (9:16, 10 s); otwarcie konferencji technologicznej (16:9, 8–12 s).

## Nie do
- Ciepłe marki, jedzenie, zdrowie: `kreska.md` albo `naklejki.md`. Oferta do czytania: `plaski-wektor.md`.
- Neon, retro, muzyka lat 80: `synthwave.md`. Gra pikselowa: `pixel.md`.

## Cechy stylu (sprawdzalne)
- Paleta wzoru (role): linia #00E5FF, przygaszona #0B7C8C, głęboka #0E3A42, biel #E8FEFF, czerwień #FF2A1F,
  tło #020A0D; alarm #FF6600 (prompt #FF6A00). Trzy jasności elementów: 100, 60 i 30%.
- Siatka sześciokątów co 30 px, odsłaniana falą od środka od 1,2 s, do promienia 1500 px w 1,2 s.
- Radar: stożek 2,0 s na obrót, ogon 0,6π, punkty gasną jak e^(−1,6s) (s = pół obrotu od przejścia wiązki).
- Liczby: losowe cyfry przez 4 klatki (prompt 3–5), potem prawdziwa wartość; pisanie 90 znaków/s (współrzędne 34),
  kursor █ miga 2,5 Hz. Panel włącza się migotaniem: krycie 0,7 → 0,1 → 1 → 0,45 → 1 w kolejnych klatkach.
- Ramki celu: wlot 8 klatek (outCubic), 2 klatki szukania ±18 px, zatrzask skali 1,35 → 1,08 → 0,96 → 1,0 przy
  połowie boku 130 px; w chwili namierzenia zaciśnięcie do 72 px w 0,2 s (outExpo), 3 echa, pierścień z 36 odcinków.
- Klatka namierzenia: błysk 1 → 0,3 (linie białe, czerń zostaje czarna), aberracja 0,0007 + 0,003·e^(−7Δ),
  fala koloru alarmu do 1350 px w 0,45 s, napis 1,15 → 1 w 3 klatki.
- Wykończenie: linie co 3 px (0,9 + 0,1·cos), zakłócenia w 54 pasach, ziarno 0,028, włączenie i wyłączenie jak
  kineskop. Tekst świeci (8 kopii, 1,5 i 3 px) nad ciemną obwódką; mono do danych, kanciasty krój do etykiet.

## Technika
- HUD rysujesz Canvas 2D do ukrytego canvasu `scena`, na wierzch `const e = ekran(cel, 'hud', { poswiata: 0.35 })`
  z `crt.js` (cel = canvas wyjścia; tryb `hud` = linie 3 px, aberracja, winieta, ziarno; `poswiata` zamiast bloomu).
- W klatce: `e.rysuj(scena, klatka, { wlacz: wlaczanie(t, 0), wylacz: wylaczanie(t, DUR - 0.23), zaklocenie: z,
  aberracja: 0.0007 + (t > LOCK ? 0.003 * Math.exp(-7 * (t - LOCK)) : 0) })`; `z` z listy zdarzeń jak `GL`
  w `index.html` wzoru (początek, długość, siła), poza nimi 0.
- Błysk namierzenia rób w scenie (linie ×2,6 jaśniej, reszta ×0,25 przez 2 klatki); `blysk` z `crt.js` rozjaśnia
  też czerń, więc najwyżej 0,15 na 1 klatkę.
- Przenieś z `demos/22-hud/js/util.js` (czyste, ok. 65 wierszy): `roll`, `typed`, `frameOf`, `hash`; z `js/hud.js`:
  `brackets` (L75), `radar` (L332–357) i uproszczone `acquire` (L492–580, bez globalnych `ctx` i `K`). Komentarz
  `// za mg-styles-15 (MIT), demos/22-hud/js/<plik>`.
- Fala koloru w Canvas 2D: HUD rysujesz dwa razy (kolor linii i alarm), alarm przycinasz kołem od celu (`arc` +
  `clip`), promień 1350·outCubic w 0,45 s. Wersja WebGL: `COMP_FS` z `js/post.js` (L4–58).
- Siatka hex raz do kafla offscreen, odsłanianie maską koła. Glob: Three.js z `/_lib/three/` i linie rosnące
  (`lineMat`/`buildLines`, `js/holo.js` L68–103); prościej Canvas 2D: kontur Polski, plan działki, serwerownia.
  `blurLayer` wzoru (`filter: blur` całego planu) nie przenoś: plan poza ostrością przygaś do 45% krycia.
- Kroje: JetBrains Mono 400–600 (dane), Chakra Petch 700 (etykiety, napis namierzenia), Teko 500 albo Saira
  Condensed 800 (nagłówki); Rajdhani i HarmonyOS z wzoru nie ma w `/_lib/kroje/`. Przed `__ready`:
  `await document.fonts.load('64px "Chakra Petch"', 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')` dla każdego kroju na kanwie.
  Cały tekst z kanwy podajesz w `__teksty` (reguła 6 kontraktu), inaczej `pomiar` go nie widzi.
- Czas renderu: wzór ok. 1,5 s na klatkę (300 klatek ≈ 8 min w jednej przeglądarce); Canvas 2D + `crt.js` jest dużo
  lżejszy. Zmierz `klatki --preset jarvo --czasy 5`; gdy całość wyjdzie ponad kilka minut, podaj czas właścicielowi.

## Rytm (10 s wzoru → film klienta)
| Czas | Co się dzieje |
|---|---|
| 0–2,4 | Hak: włączenie kineskopu (0,37 s); pierścienie, panele i siatka rysują się warstwami co 0,25 s |
| 2,4–4,4 | Dane ożywają: radar 2 s na obrót, kolumny losują 4 klatki i stają, wykresiki; kontur rośnie |
| 4,4–5,9 | Sygnał wykryty; 3 kandydaci co 0,5 s: „ANALIZA” → „BRAK” z krzyżykiem |
| 5,9–6,4 | Ramki wlatują z rogów (8 klatek), szukają, zatrzask; 0,25 s dziury w muzyce przed celem |
| 6,4 (64%) | Kulminacja: namierzenie, błysk, fala koloru alarmu, napis „NAMIERZONO” (albo nazwa usługi) |
| 7,0–8,4 | Najazd na cel, współrzędne i wynik pisane; od 8,4 logo i hasło klienta w panelu |
| 8,9–10 | Kadr stoi ok. 0,9 s (radar dalej się kręci), wysyłanie 9,0–9,4, wyłączenie kineskopu od 9,77 |

- 15–30 s: dłuższe budowanie (warstwy do 4 s), 2–3 cele z mniejszym zatrzaskiem, jedno duże namierzenie w 60–65%.
- 9:16: kolumny danych nad i pod lunetą, luneta ok. 0,8 szerokości kadru, dane w 2 pasach. Wzór ma 16:9 na sztywno
  (`PerspectiveCamera(30, 16/9)`, kolumny x 96–396 i 1524–1824, luneta 802 px, shadery 1920/1080).

## Dźwięk
- Darksynth ok. 120 BPM, mrocznie (wzór: D frygijski): pulsujący bas, motyw 3 nut; pierwszy takt = namierzenie.
  Włączenie `buzz` + `crack`; panel `bip`; pisanie `pisanie-cyfrowe`; dane `dane` (biblioteka); radar cichy `whoosh`.
- 0,25 s dziury w podkładzie przed namierzeniem: przytnij muzykę (np. `muzyka-napiecie`) pod 6,15–6,4 s.
- Namierzenie: `thump` + `potwierdzenie` + `glitch`; alarm `bip` 4 razy co 0,5 s (6,9 / 7,4 / 7,9 / 8,4);
  wyłączenie krótki `buzz`; całość −14 LUFS.

## Pułapki
- Za gęsto i za drobno: mono 13 px w 1080p na telefonie to szum. Tekst do czytania ≥ 3% wysokości kadru (32 px).
- Prompt: zatrzask 1,4 → 1,0; kod: 1,35 → 1,08 → 0,96 → 1,0 (przestrzał i osiadanie). Bierz kod.
- Cel to rzecz klienta (paczka, serwer, działka), nigdy osoba, prawdziwe miasto jako cel ani obiekt wojskowy.
- Kolor marki jako linia, ale tło zostaje prawie czarne; jasne tło zabija blask i linie skanu.

## Kontrola
- `html_wideo.py klatki out/wideo/src/index.html --preset jarvo --czasy 6.2,6.23,6.27,6.3,6.33,6.37,6.4,6.43
  --arkusz out/wideo/zatrzask.jpg`: wlot, zatrzask 1,35/1,08/0,96/1,0 i jedna ostra klatka namierzenia.
- Pasek klatek od startu liczby: losowe cyfry przez 4 klatki, w 5. prawdziwa wartość; kursor miga 2,5 Hz.
- Arkusz 0.1, 1.5, 4, 6.4, 6.6, 9, 9.9: obraz otwiera się z linii i gaśnie do kropki, jeden bohater, alarm po fali.
- `html_wideo.py pomiar out/wideo/src/index.html --preset jarvo --dlugosc 10`: kontrast; logo czytelne na 360 px.
