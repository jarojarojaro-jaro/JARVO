# Pixel art z kineskopu (wzór `20-pixel`)

Gra 8-bitowa: świat z dużych, równych pikseli w palecie 32 kolorów, bohater biegnie, skacze i zbiera monety,
a całość świeci przez kineskop. Poznasz go po ostrych pikselach, ditheringu w kratkę i liniach ekranu.
Wzór: okładka `$MGSTYLES/videos/20-pixel.jpg`, kod `$MGSTYLES/demos/20-pixel/` (MIT), ocena jury 8,07;
1920×1080 (bufor 320×180 × 6), 30 kl./s, 10 s. Klatki wzoru (6,4 s = otwarcie skrzyni; ok. 0,45 s na klatkę):
```
@@PY@@ "$HERMES_HOME/scripts/html_wideo.py" klatki "@@TOOLS_DIR@@/mg-styles-15/demos/20-pixel/index.html" --preset mg \
  --czasy 0.2,2.4,4.6,6.4,7.4,9 --arkusz out/wideo/wzor-20-pixel.jpg
```
`--query nocrt=1` pokazuje obraz bez kineskopu, `--query sheet=1` arkusz sprite'ów.

## Do czego
- Studio gier: zwiastun, zapowiedź na Steam, rekrutacja; 16:9, 15–30 s.
- Szkoła programowania dla dzieci, firma IT szukająca ludzi („level up”); 9:16, 15 s.
- Sklep z grami planszowymi i wideo, turniej e-sportowy, LAN party w szkole; 1:1 lub 9:16, 10–15 s.
- Program lojalnościowy, pierwsze kroki w aplikacji (punkty zbierane jak monety); 9:16, 15–20 s.

## Nie do
- Luksus, jedzenie na apetyt, zdrowie: `zorza-szklo.md` albo `plyn.md`.
- Produkt, który trzeba pokazać ze zdjęcia, drobne detale: `3d.md` albo `kolaz.md`.
- Neon i lata 80. bez gry: `synthwave.md`. Interfejs sci-fi z danymi: `hud.md`.

## Cechy stylu (sprawdzalne)
- Bufor 320×180 (pion 180×320), skala całkowita ×6; najazdy tylko ×8, ×10, ×12 (dzielą 1920 i 1080).
- Paleta 32 kolory (wzór „QUEST-32”, od #0d0b1a do #ffffff, odniesienie); każdy slot (niebo, trawa, woda) ma
  6 etapów: dzień, popołudnie, złota godzina, zachód, zmierzch, noc.
- Zmiana etapu w 4 klatkach: 2 kroki pośrednie (1/3 i 2/3), każdy to najbliższy kolor palety (wagi 0,3/0,59/0,11).
- Dithering Bayera 4×4 na niebie, poświacie, mgle, promieniach i ramce dialogu; cykl kolorów: woda co 3 klatki,
  gwiazdy co 4, wodospad rampą 8 kroków.
- Paralaksa w pełnych pikselach `floor(cx·k)`: k = 0,125 (góry), 0,3 (sosny), 0,55 (wzgórza), 1,0 (ziemia),
  1,4 (pierwszy plan); kamera 2 px bufora na klatkę.
- Sprite'y z obrysem 1 px: bieg 6 rysunków po 3 klatki (10 kl./s), oddech 2 rysunki co 12 klatek, moneta 4.
- Czas z tabel: łuk skoku `round(112·s(1−s))`, poślizg `[0,2,3,4,5,6,7,7,8…]`, logo spada 12 klatek
  (`dy = −128·(1−(i/12)²)`), odbicie 0, −5, −2, 0 px co 2 klatki, ściśnięcie 6, 3, −4, −4 px, połysk 6+2 px
  po 18 px na klatkę.
- Kineskop: beczka 0,03, linie wiązki grubsze na jasnym (0,30–0,47), poświata (16 próbek, próg 0,30, siła 0,55),
  winieta 0,24, włączenie w 11 klatkach (kropka → linia → obraz).
- Dialog: 1 znak co 3 klatki; „PRESS START” miga 12 klatek tak, 12 nie.

## Technika
- `piksel.js` to port silnika wzoru: `bufor(320, 180)`, `prostokat`, `linia`, `ditheruj(b, x, y, w, h, postep,
  kA, kB)`, `sprite(wiersze, legenda)`, `obrysuj(s, k)`, `nanies(b, s, x, y, { odbicie, zamiana })`, `napis(tekst,
  kroj, rozmiar, k, { cien })`, `paleta(kolory, etapy).tablica(a, b, u, 3)`, `cykl(lista, klatka, 3)`, `pokaz`.
- Raz `const e = ekran(wyjscie, 'crt')` z `crt.js`; w `__seek(t)`: `f = Math.round(t * 30)`, świat z `f` (bez stanu),
  `pokaz(maly, b, pal, tablica)` na płótno 320×180, `e.rysuj(maly, f, { wlacz: wlaczanie(t, 0) })`: ostry piksel
  (środek płaski, krawędź wygładzona na 1 px wyjścia, bez mory na krzywiźnie).
- Najazd: filtrowi dajesz wycinek bufora 240×135 (×8), 192×108 (×10) albo 160×90 (×12).
- Paleta z marki: 2–3 kolory marki, po 3–5 odcieni, ciemny kontur i biel, razem ≤ 32; pory dnia = tablice slotów.
- Krój: Press Start 2P z `/_lib/kroje/` ma polskie litery (podzbiór latin-ext, sprawdzone ą ć ę ł ń ó ś ź ż
  i wielkie), ostry w 8 px albo wielokrotności 8. Przed `__ready`:
  `await document.fonts.load('8px "Press Start 2P"', 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')`, inaczej `napis` w pierwszych klatkach
  rasteryzuje krój zastępczy. Fusion Pixel 12 z wzoru nie ma w `/_lib/kroje/`. Teksty podajesz w `__teksty`.
- Przenieś z `film.js` (`// za mg-styles-15 (MIT), demos/20-pixel/film.js`): `buildLogo5` (322–345: logo
  z komórek 4 px, rampa z ditheringiem, faza, wyciągnięcie, kontur), `drawLogo` (675–701), `layer` i `blitLayer`
  (349–350, warstwy paralaksy liczone raz), tabele `SKID` (432) i `PWR` (808–813), `tinyNum` (cyfry 3×5).
- Ruch z tabel w pełnych pikselach, nie krzywe charakterów z `ruch.js`; bez motion bluru (pixel art go nie zna):
  szybki ruch = rysunek pośredni i linie prędkości z pikseli, bez `smuga` i `duchy`.
- Render lekki: wzór ok. 0,45 s na klatkę (15 s ≈ 3,5 min w jednej przeglądarce, kilka naraz szybciej). Kineskop
  liczy procesor: płótno `ekran` 960×540 rozciągnięte na kadr jest ok. 3× tańsze niż 1920×1080 i wygląda tak samo.

## Rytm (10 s wzoru → film klienta)
| Czas | Co się dzieje |
|---|---|
| 0–0,4 | Hak: włączenie kineskopu w 11 klatkach, bohater już biegnie |
| 0,3–4,4 | Skoki, monety (produkty marki), wróg z „+500”, poślizg 4,0 s, „!” 4,4 s; pora dnia co ok. 1,5 s |
| 4,6–5,8 | Okno dialogu pisze zdanie marki (1 znak co 3 klatki) |
| 5,9–6,4 | Trzy najazdy ×8, ×10, ×12 co 0,1 s, skrzynia drży i podskakuje; 6,2–6,4 s cisza i bezruch |
| 6,4 (64%) | Kulminacja: skrzynia się otwiera, 1 biała klatka, promienie, fontanna monet; 6,8 s przedmiot nad głową |
| 7,2–10 | Logo spada i odbija się, połysk 7,6 s, wstęga z hasłem 8,0 s, fala nocy, „NACIŚNIJ START” miga |

- 15–30 s: kolejne poziomy po 3–5 s, każdy w innej porze dnia; kulminacja 9–10 s / 18–19 s, logo od 80%.
- 9:16: bufor 180×320 (×6 = 1080×1920), świat pionowy (wspinaczka po platformach), logo w górnej trzeciej, dialog
  nad dolną strefą UI. Wzór ma `GROUND = 150`, `CHEST_X`, `CAM_END` na sztywno.

## Dźwięk
- Chiptune jak z konsoli NES, 150 BPM (wzór: C-dur): melodia na fali prostokątnej 25%, druga 12,5%, arpeggia,
  bas na trójkącie, perkusja z szumu. Podkład z biblioteki: `muzyka-8bit`.
- Z biblioteki: skok `skok-retro`, moneta `moneta-gra`, wróg `w-dol`, najazdy `w-gore`, skrzynia `power-up`,
  przedmiot `wygrana-gra` albo `dzingiel-8bit`; z `sound.mjs`: pisanie `tick` co znak (`pitch` 1,2–1,3).
- 0,2 s ciszy przed otwarciem skrzyni (zostaje szum kineskopu); całość −14 LUFS.

## Pułapki
- Skala niecałkowita albo wygładzanie przeglądarki: piksele różnej wielkości i mora. Tylko `pokaz` i `crt.js`.
- Kolory spoza palety (gradient CSS, przezroczystość, `shadowBlur`): przejście = dithering albo krok palety.
- Pozycje z ułamkiem piksela (bez `floor`): pixel art pływa. Ruch w pełnych pikselach, rysunki co 2–3 klatki.
- Prompt mówi o najbliższym sąsiedzie, kod ma ostry piksel z wygładzoną krawędzią (`reg = 0,5 − 0,5/skala`);
  `crt.js` robi to samo co kod. Tabele klatek (włączenie, odbicie) zakładają 30 kl./s.

## Kontrola
- `html_wideo.py klatki out/wideo/src/index.html --preset jarvo --czasy 0.2,2.4,4.6,6.4,6.5,7.4,9.5 --arkusz
  out/wideo/arkusz.jpg`: 6,4 s jedna biała klatka, 6,5 s promienie, 9,5 s logo stoi (miga tylko napis startu).
- Klatka powiększona ×4: piksel bufora = 6×6 px wyjścia, krawędzie ostre, kolory tylko z palety; „Zażółć gęślą
  jaźń” w Press Start 2P z polskimi literami, nie w kroju zastępczym.
- `html_wideo.py pomiar out/wideo/src/index.html --preset jarvo --dlugosc 15`: czas czytania dialogu (10 znaków/s,
  potem ≥ 1,5 s stania), `uderzenia_kadru` ≤ 3 (biała klatka się liczy, najazd bez powrotu nie).
