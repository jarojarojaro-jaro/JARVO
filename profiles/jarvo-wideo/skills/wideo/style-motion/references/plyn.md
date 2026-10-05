# Płyn, krople w znak marki (wzór `07-liquid`)

Lśniące krople spadają, rozpłaszczają się, zlewają w jedną masę, zalewają kadr i na końcu układają się w znak marki.
Poznasz go po gęstym, szklistym połysku, szyjkach, które się wyciągają i pękają, i literach jak z galaretki.
Wzór: okładka `$MGSTYLES/videos/07-liquid.jpg`, kod `$MGSTYLES/demos/07-liquid/` (MIT), ocena jury 7,57;
1920×1080, 30 kl./s, 10 s, czysty WebGL2 (shader pola odległości). Klatki wzoru (4,2 s = zalew, 6,5 s = znak):
```
python3 $HERMES_HOME/scripts/html_wideo.py klatki $MGSTYLES/demos/07-liquid/index.html --preset mg \
  --query mb=1 --czasy 1.2,4.2,6.5,8.5 --arkusz out/wideo/wzor-07-liquid.jpg
```
`mb=1` wyłącza rozmycie liczone w stronie (10–24 stanów na klatkę): klatka ok. 11 s zamiast do 90 s (CPU, bez GPU).

## Do czego
- Browar rzemieślniczy, soki, kombucha, palarnia kawy, lodziarnia: odsłonięcie logo albo smaku, 9:16 lub 1:1, 8–12 s.
- Kosmetyki i pielęgnacja, salon paznokci albo koloryzacji: nowa linia, kolor sezonu, 9:16, 10 s.
- Producent albo sklep z farbami, myjnia: zalew kolorem jako przejście marki, 16:9, 10–15 s.
- Czołówka albo przejście dla dowolnej marki (zalew zamiast cięcia), każdy format, 3–6 s.

## Nie do
- Dużo tekstu, poważne B2B (kancelaria, księgowość): `plaski-wektor.md` albo `zorza-szklo.md`.
- Prawdziwe zdjęcia produktu: `3d.md` albo `kolaz.md`.
- Szybka robota na dziś (render bardzo ciężki): `morph.md`, przemiana kształtów 2D z szybkim renderem.

## Cechy stylu (sprawdzalne)
- Zlewanie: gładka suma pól `m − log Σ e^(−k(d−m))/k`, k = 0,1 px⁻¹ (mostek ok. 10 px), przy zbieraniu 0,062
  (więcej mazi). Prompt każe rozmycie + próg; kod liczy to dokładnie i miesza tak samo gradient i kolor.
- Krople to elipsy rozciągnięte wzdłuż prędkości: `1 + min(0,45; v/5200)`; szyjki to zwężane kapsuły.
  Limity: 72 krople, 20 szyjek, 4 litery, 32 pęcherzyki; rzut `bezier(0.22, 1, 0.36, 1)`, grawitacja 5000 px/s².
- Lądowanie: sprężyna od ściśnięcia 1,3 do kałuży 0,5 (6 Hz, tłumienie 0,5–0,62), przestrzelenie o połowę mniejsze.
- Pękanie: szyjka strumienia pęka po 0,167 s, kikut odskakuje (7 Hz, 0,45); kropelki korony odrywają się
  2–3 klatki po kontakcie; mostki między literami pękają tuż przed znakiem.
- Zalew: 3 ukośne fale (L→P, P→L, L→P) co 0,07 s; czoło = 3 sinusy (wagi 0,58/0,30/0,14, częstotliwość
  ×1/×1,87/×3,13, amplituda 80–90 px); czoło przechodzi w 0,46–0,62 s, pełne zanurzenie ok. 0,45 s.
- Połysk: kopuła z `tanh`, Fresnel 0,04 + 0,96·(1 − n.z)⁵, studio (softbox ×30, pasek ×14, góra ×12, kontra ×4),
  błysk `pow 900`, światło przechodzące, miękki cień, odbicie w podłodze; barwa ciemnieje z grubością.
- Wykończenie: bloom na 6 poziomach, tonemapping z zachowaniem barwy (k = 0,72), winieta 0,28, ziarno 0,03.
- Paleta wzoru (role; kolory z marki): tło śliwka #120517 → #340F3C; płyn średni #FF5C0F / #FF1A70 / #8F1FFF,
  cienki #FFBD4D / #FF80A8 / #D685FF, głęboki #CC1A0A / #9E054D / #3D0A99; napisy #FFE8F0.

## Technika
- Modułu Jarva do płynu nie ma: silnik przenosisz ze wzoru (`// za mg-styles-15 (MIT), demos/07-liquid/js/<plik>`).
  To moduły ES: kopiujesz je do `out/wideo/src/` i piszesz nową scenę, silnik zostaje.
- `shaders.js`: `fadd`/`fres` (97–101) i `field()` (133–219) = pole; `env()` (221–244) i `shadeLiquid()` (246–337)
  = połysk; palety (60–94); `waveShape`/`floodSD` (104–131) = zalew. Paleta marki: 3 barwy × 3 grubości.
- `scene.js`: `createFilm(cues, word)` daje stan z `t` (krople, szyjki, litery, zalew); pomocnicze `bezier`, `spring`,
  `camAt`, `makeDroplet`/`emitDroplet`, `sheet` (260–284). Choreografię piszesz od nowa w swoim `cues.json`.
- `textsdf.js`: `buildLetterSDF({ word, family, weight, size, tracking, pad, sigma })`, litera na kanał RGBA, najwyżej
  4. Krój Fraunces 900 z `/_lib/kroje/` (wzór miał osobny krój Fraunces „Liquid”); przed budową SDF
  `await document.fonts.load('900 400px "Fraunces"', 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')`.
- `engine.js` `createEngine`: zostaw bufor RGBA16F, bloom i post, ale jeden stan na klatkę (bez akumulacji
  N stanów). Szybki lot = rozciągnięcie elipsy w polu; bez podklatek i bez `--subklatki`.
- Hasło na płótnie 2D nad WebGL (wzór: `type.js`), Inter 600, wejście `ladowanie` z `ruch.js`, tekst w `__teksty`.
- Wersja lekka (np. 9:16 na dziś): kształty na płótnie 2D z filtrem SVG `feGaussianBlur` + `feColorMatrix` (próg
  alfy) = maź bez połysku; render szybki, wygląd płaski. Powiedz właścicielowi, którą wersję robisz.
- Czas renderu: klatka wzoru 1920×1080 ok. 11 s na CPU, więc 15 s filmu (450 klatek) ≈ 80 min w jednej przeglądarce.
  Zmierz `klatki --preset jarvo --czasy 4` swojej strony, policz całość i podaj właścicielowi przed renderem.
  Taniej: bufor WebGL 1440×810 rozciągnięty CSS-em (ok. 1,8× szybciej), mniej kropli i odbić.

## Rytm (10 s wzoru → film klienta)
| Czas | Co się dzieje |
|---|---|
| 0–0,4 | Hak: makro kropli na dziobku, znak marki widać przez nią odwrócony jak przez soczewkę |
| 0,4–1,6 | Cztery krople lądują co 0,4 s z koroną i kropelkami |
| 2,0–3,2 | Kałuże podskakują i zlewają się w masę na środku; 3,2 s masa skacze |
| 4,0–5,35 | Uderzenie 4,0 s, zalew kadru 4,0–4,4 s, fale spływają 4,55–5,35 s, zostają grudki liter |
| 6,2–6,4 | Cisza: mostek między literami się ściska |
| 6,4 (64%) | Kulminacja: litery wskakują w znak marki, galaretowe drganie; odblask 7,2 s |
| 8,3–10 | Kropla spada z litery, ląduje 8,4 s, fala odsłania hasło do 8,8 s; stoi ok. 1,2 s z drganiem galarety |

- 15–30 s: więcej zlewań (co 1,5–2 s), drugi zalew jako przejście między scenami; kulminacja 9–10 s / 18–19 s.
- 9:16: krople spadają przez całą wysokość, znak na środku, hasło niżej. Wzór ma świat 1920×1080 na sztywno
  (podłoga `FY` 872, horyzont `HOR` 786, klucze kamery, `bloomAt` 960/540): przelicz wszystko.

## Dźwięk
- Future bass 150 BPM (wzór: D-dur): każde lądowanie to strojona „mokra” nuta; muzyka z licencją, takty z `rytm.py`.
- Lądowania: `drip` i `splash` z `sound.mjs` (`pitch` niżej dla dużej kropli), pęknięcie szyjki `pop`; z biblioteki
  `kropla`, `plusk`, `plusk-duzy`, `sluz`, `plop`.
- Zalew: muzyka „pod wodą” (stłumione wysokie) 4,0–5,35 s; przed znakiem `riser`, potem 0,2 s ciszy.
- Znak: `pop` + `bas` z biblioteki; odblask `sparkle`; hasło: cichy `drip` na fali. Całość −14 LUFS.

## Pułapki
- Rozmycie w stronie: bez `?mb=1` wzór liczy 10–24 stanów na klatkę, render 6× dłuższy. U nas zawsze 1 stan.
- Bez `EXT_color_buffer_float` strona rzuca błąd: sprawdź pierwszą klatkę renderu, nie tylko podgląd.
- Limit 4 liter SDF: dłuższą nazwę daj jako jeden kształt SDF albo drugą teksturę (zmiana shadera); nie ucinaj.
- Krój niezaładowany przed `buildLetterSDF` daje inne litery bez błędu.
- `out/cues_derived.json` wzoru (czasy kropelek dla dźwięku) nie ma generatora w repo: u nas czasy kropel licz tą
  samą funkcją co obraz i zapisuj w `cues.json`, inaczej dźwięk się rozjedzie.
- Ziarno losowania zużywane w kolejności budowy (nowe losowanie przestawia resztę): grupa kropel = własne ziarno.

## Kontrola
- `html_wideo.py klatki out/wideo/src/index.html --preset jarvo --czasy 0.2,1.2,2.4,4.2,5.3,6.4,8.6 --arkusz
  out/wideo/arkusz.jpg`: znak widać w 0,2 s, zalew kryje cały kadr w 4,2 s, znak czytelny w 6,4 s.
- Pasek co 1/30 s przy lądowaniu i pęknięciu szyjki: kropelki odrywają się 2–3 klatki po kontakcie, bez migotania.
- `html_wideo.py pomiar out/wideo/src/index.html --preset jarvo --dlugosc 15` (w trakcie `--tryb szybki`).
- Na 360 px połysk nie robi ze znaku brei; ostatnia klatka: znak i hasło (≥ 3% wysokości) stoją 0,8–1,2 s.
