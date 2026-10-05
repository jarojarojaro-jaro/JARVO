# Kontrakt HTML: własna animacja (Canvas, SVG, Three.js, GSAP) → wideo

Jeden plik `out/wideo/src/<nazwa>/index.html` (+ assety obok). Ta sama strona służy do podglądu (odtwarza się
w pętli) i do renderu klatka po klatce: `html_wideo.py --preset jarvo` woła `window.__seek(t)` dla każdej klatki.

## Twarde reguły
1. `window.__seek(t)` rysuje **cały** stan w chwili `t` (sekundy) i nic nie zwraca (albo `Promise`, gdy czeka). Nic poza `t`: zero `Date.now`,
   `performance.now`, `setTimeout`, `Math.random` bez ziarna (`mulberry32(seed)`), zero stanu z poprzedniej klatki
   (fizyka i cząstki liczone od `t = 0` albo z krokiem stałym od zera do `t`).
2. `window.__W`, `window.__H` = rozmiar kadru (1080×1920 pion, 1920×1080 poziom); `window.__DUR` = długość w s.
3. `window.__ready = true` dopiero po fontach (`await document.fonts.ready`), obrazach i teksturach.
4. Biblioteki lokalnie z `/_lib/` (html_wideo serwuje wspólne `node_modules`; `narzedzia.py instaluj html`):
   Three.js `/_lib/three/build/three.module.js` (+ `/_lib/three/examples/jsm/…`), GSAP `/_lib/gsap/dist/gsap.min.js`,
   nasz ruch `/_lib/jarvo/ruch.js` (charakter ruchu z marki, lądowanie, wyjście, smugi: `ruch-i-kompozycja.md`),
   moduły stylów `/_lib/jarvo/{kreska,morph,crt,plotno,piksel}.js` (skill `style-motion`), kamera po zrzucie strony
   klienta `/_lib/jarvo/strona.js` (`film-z-kodu/references/strona-filmowana.md`).
   Bez CDN: render ma działać offline i zawsze tak samo.
5. Tekst jako prawdziwy tekst, nie bitmapa z AI. Kroje: `<link rel="stylesheet" href="/_lib/kroje/kroje.css">`
   = 68 krojów OFL z polskimi znakami (te same co w edytorze HQ, np. Anton, Inter, Fraunces, Caveat, Press Start 2P,
   Space Mono), wpisujesz rodzinę po nazwie; sprawdź „Zażółć gęślą jaźń” na arkuszu. Polskie litery są w osobnym
   pliku kroju (latin-ext), który przeglądarka pobiera dopiero, gdy zobaczy taki znak: tekst na kanwie (`fillText`)
   pierwszej klatki wyjdzie innym krojem. Przed `__ready` każdy krój kanwy z próbką:
   `await document.fonts.load('64px "Anton"', 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')`.
6. **Tekst na kanwie podajesz pomiarowi:** `window.__teksty = () => [...]` zwraca teksty bieżącej klatki
   `{tekst, x, y, w, h, kolor, rozmiar, krycie, widoczny?, id?}` (prostokąt w pikselach kadru, `widoczny` = odsłonięta
   część przy pisaniu). Tekst w DOM (HTML, SVG) `pomiar` czyta sam; bez `__teksty` tekst z `fillText` jest dla niego
   niewidoczny (zostają tylko kontrole obrazu).
7. **Parametry do strojenia** (HQ: przycisk **◐ Animacja**, podgląd na żywo z suwakami): to, co właściciel może chcieć
   zmienić bez Ciebie (kolory, teksty, tempo, krzywe wejścia, włącz/wyłącz element), trzymasz w `parametry.json` obok
   strony i czytasz przy starcie do `window.__params`; każda klatka bierze wartości z tego obiektu (nie kopiuj ich do
   stałych), więc HQ zmienia je na żywo, a render czyta ten sam plik. Typy: `liczba` (`min`, `max`, `krok`), `kolor`
   (`#RRGGBB`), `tekst`, `przelacznik`, `wybor` (`opcje`), `krzywa` (`[x1, y1, x2, y2]` jak cubic-bezier). Najwyżej
   kilkanaście pól, nazwy po polsku dla właściciela; po zmianie parametrów pomiar trzeba powtórzyć. Wartości zapisane
   przez właściciela w HQ to jego decyzje: zmieniasz je tylko na jego prośbę, a nowe pole dopisujesz z obecną wartością.

## Parametry (reguła 7)
```json
{"pola": [
  {"klucz": "tlo", "typ": "kolor", "etykieta": "Tło", "wartosc": "#0B1220"},
  {"klucz": "tytul", "typ": "tekst", "etykieta": "Tytuł", "wartosc": "Kawa z palarni Jarvo"},
  {"klucz": "tempo", "typ": "liczba", "etykieta": "Tempo", "min": 0.5, "max": 2, "krok": 0.05, "wartosc": 1},
  {"klucz": "wejscie", "typ": "krzywa", "etykieta": "Wejście tytułu", "wartosc": [0.16, 1, 0.3, 1]},
  {"klucz": "logo", "typ": "przelacznik", "etykieta": "Logo na końcu", "wartosc": true}]}
```
```js
const P = window.__params = {};                         // HQ podmienia wartości na żywo i woła __seek(t)
try { for (const f of (await (await fetch('parametry.json')).json()).pola) P[f.klucz] = f.wartosc; } catch (e) {}
// krzywa z parametru: bezier(...P.wejscie)(postęp 0–1) → 0–1 (cubic-bezier jak w CSS)
const bezier = (x1, y1, x2, y2) => (x) => { let a = 0, b = 1, t = x;
  for (let i = 0; i < 24; i++) { t = (a + b) / 2; const u = 1 - t, bx = 3*u*u*t*x1 + 3*u*t*t*x2 + t*t*t; if (bx < x) a = t; else b = t; }
  const u = 1 - t; return 3*u*u*t*y1 + 3*u*t*t*y2 + t*t*t; };
```

## Szkielet (Canvas 2D; Three.js i GSAP niżej)
```html
<!doctype html><html lang="pl"><head><meta charset="utf-8">
<style>html,body{margin:0;background:#0b0d12}canvas{display:block}</style></head><body>
<canvas id="c"></canvas>
<script type="module">
const W = 1080, H = 1920, DUR = 12;                     // kadr i długość
Object.assign(window, { __W: W, __H: H, __DUR: DUR });
const c = document.getElementById('c'); c.width = W; c.height = H; const g = c.getContext('2d');
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ease = (x) => 1 - Math.pow(1 - clamp(x), 3);     // easeOutCubic
const seg = (t, a, b) => clamp((t - a) / (b - a));      // postęp sceny a..b
let napisy = [];                                        // teksty klatki dla pomiaru (reguła 6)
function draw(t) {
  g.clearRect(0, 0, W, H); napisy = [];
  // scena 1 (0–3 s): hak; scena 2 (3–7 s): …; każda scena liczy swój postęp z seg(t, start, koniec)
  // tekst: g.fillText(s, x, y) i napisy.push({tekst: s, x, y: y - 64, w: g.measureText(s).width, h: 80, kolor: '#fff', rozmiar: 64, krycie: a})
}
window.__seek = (t) => draw(t);
window.__teksty = () => napisy;
await document.fonts.ready; draw(0); window.__ready = true;
if (!new URLSearchParams(location.search).has('render')) {           // podgląd dla człowieka
  const t0 = performance.now(); (function loop(now) { draw(((now - t0) / 1000) % DUR); requestAnimationFrame(loop); })(t0);
}
</script></body></html>
```
`--preset jarvo` otwiera stronę z `?render=1`: pętla podglądu musi być wyłączona w tym trybie (jak wyżej), inaczej
rysowałaby klatki z zegara między `__seek` a zrzutem.

**Three.js:** `<script type="importmap">{"imports":{"three":"/_lib/three/build/three.module.js",
"three/addons/":"/_lib/three/examples/jsm/"}}</script>`, `renderer = new THREE.WebGLRenderer({canvas: c,
antialias: true, preserveDrawingBuffer: true})`, w `__seek`: ustaw kamerę, obiekty i uniformy shaderów z `t`,
potem `renderer.render(scene, camera)`. Bez `clock.getDelta()`.
**GSAP:** `<script src="/_lib/gsap/dist/gsap.min.js"></script>`, jedna oś `const tl = gsap.timeline({paused: true})`,
`window.__seek = (t) => { tl.seek(t, false); }` (w klamrach: `__seek` nie zwraca osi, bo oś GSAP jest „thenable”;
jeśli coś ładujesz asynchronicznie przy seek, zwróć prawdziwy `Promise`).

Wiedza o GSAP: `gsap-timeline` (osie, etykiety), `gsap-plugins` (SplitText, MorphSVG, MotionPath: darmowe),
`gsap-performance`; o Three.js: skille `threejs-*` (po temacie). Krzywe i czasy ruchu UI: `animate`.

## Techniki (ruch jak ze studia)
- **Sprężyny w zamkniętej postaci:** `spring(t) = 1 − e^(−ζωt)·(cos ωdt + ζω/ωd·sin ωdt)` od chwili zmiany; brak stanu.
  Wartość z wieloma celami = **suma sprężyn, jedna na zmianę** (`Σ (cel_i − cel_i−1)·spring(t − t_i)`): dalej czysta funkcja `t`.
- **Kamera = jedna transformacja kontenera**, klucze `[t, zoom, x, y]` z easingiem, zoom interpolowany w skali log
  (`exp(lerp(log z0, log z1))`), jeden ruch na scenę, nigdy zoom w przód i w tył pod rząd; kursor skaluje się z kamerą.
- **Wspólny element przy przekazaniu:** zalew niesie kopię słów bańki, przycisk niesie swoją etykietę w stronę.
  **Zalew** (kolor wylewa się z obiektu) musi przykryć najdalszy róg (promień > przekątna od środka) i trwać 0,3–0,35 s;
  krócej = błysk, połowa ekranu zmienia się w jednej klatce.
- **Rozciąganie:** dwie krawędzie wskaźnika (zakładki, przełącznika) na różnych sprężynach: przód wyprzedza tył.
- **Przeciąganie:** gdy kursor trzyma, wartość = funkcja jego pozycji; po puszczeniu sprężyna od miejsca, gdzie była.
- **Tekst:** wyrasta spod linii maski; tekst podmieniany w zmieniającym kształt pojemniku ma własną maskę i własne
  wejście/wyjście (inaczej nachodzi); pisanie w stałych liniach, kamera nie goni zawijającego się kursora.
- **Pętla:** ostatnia klatka = pierwsza, łącznie z pozycją i prędkością kursora (inaczej zacina się na przejściu).
- **Charakter ruchu** marki (6 do wyboru, czasy i krzywe w `ruch.js`) ustala długość głównego ruchu, krzywą
  i przestrzelenie dla całego filmu (`ruch-i-kompozycja.md`); liczby niżej to drobne ruchy w jego obrębie.
- **Liczby ruchu** (za skillem fframes, MIT): wejście 0,3–0,6 s, wyjście 0,2–0,3 s (szybciej i bliżej), spoczynek
  1–3 s z małym ruchem w tle. Wejście z krótkiego dystansu (40–120 px) z kryciem 0 → 1; skala od 0,9–0,96, nigdy
  od 0; obrót najwyżej ±6°. Kolejno: elementy listy co 60–120 ms, słowa co 40–60 ms, litery co 20–40 ms; naraz
  jeden główny ruch, reszta mniej i później. Animuj `transform` i krycie, nie rozmiar czcionki (drży).
  Sprężyny do wzoru wyżej (masa 1): **szybka** ω 17,3, ζ 0,75 (interfejs, lekkie przestrzelenie), **miękka**
  ω 12,2, ζ 0,73 (przyjazna), **skoczna** ω 14,8, ζ 0,40 (rzadko). Krzywe: `bezier(0.16, 1, 0.3, 1)` (szybko, potem
  osiada: slajdy, plansze), `bezier(0.65, 0, 0.35, 1)` (kamera, przemiany). Licznik „0 → 12 480”: 1,2–1,8 s tą
  pierwszą krzywą, cyfry o stałej szerokości (`font-variant-numeric: tabular-nums`), wyrównane do prawej.

## Pułapki renderu
- `will-change` na czymś, co skaluje kamera → rozmyty tekst; nie używaj. `z-index` na każdej warstwie.
- Dziecko z `visibility: visible` prześwituje przez ukrytego rodzica: używaj `inherit`.
- Wszystkie zmienne zadeklarowane przed pierwszym `__seek` (render woła go od razu).
- Wideo w stronie: przekoduj all-intra (`ffmpeg -i in.mp4 -g 1 -an klip.mp4`), wczytaj jako blob URL (serwer renderu
  nie przewija zakresami), w `__seek` ustaw `currentTime` i zwróć `Promise` czekający na `seeked`.
- `backdrop-filter: url()` źle czyta mapy przesunięć w Chromium: „szkło” = klon sceny pod elementem + filtr SVG.
- Szybki ruch: smuga, duchy albo rozciągnięcie z `ruch.js` (motion blur z `--subklatki` wydłuża render N razy:
  tylko na prośbę właściciela) i trochę wolniej; potem klatka po klatce przez szybkie chwile
  i `qa_wideo.py` (wykrywa pojedyncze „mrugnięcia”).
- Dźwięk: prawdziwy efekt na każde zdarzenie, położony wg szczytu (`rytm.py efekt.wav --szczyt`), całość −14 LUFS;
  duża chwila = zdanie dźwiękowe (narastanie → uderzenie → błysk), seria elementów = dwa efekty na zmianę, coraz ciszej;
  czasy efektów z tych samych stałych co animacja (zasady w `lektor-i-dzwiek`).

## Film z lektorem: oś czasu z narracji
Lektor najpierw, animacja za nim. Tekst lektora w `out/wideo/src/narracja.txt`:
```
# Kolejka                                   ← rozdział (tylko film od 3 min: plansza rozdziału), nie jest czytany
Wchodzisz do piekarni o siódmej rano.       ← linia = jedno zdanie lektora
Przed tobą {kolejka}dziesięć osób. | Każdy czeka.   ← | = podział napisu, {nazwa} = chwila na początku słowa
                                            ← pusty wiersz = koniec akapitu = cięcie ujęcia
To pół godziny dziennie.{zegar}             ← {nazwa} na końcu linii = koniec zdania
```
```bash
python3 $HERMES_HOME/scripts/film.py narracja out/wideo/src/narracja.txt --sprawdz          # tekst, szacunek długości
python3 $HERMES_HOME/scripts/film.py narracja out/wideo/src/narracja.txt -o out/wideo/src/lektor.wav \
  --os out/wideo/src/<nazwa>/os_czasu.json --cel 60-90 [--glos pl-PL-ZofiaNeural] [--tempo -5%]
```
Każde zdanie jest syntezowane osobno, przycięte do słyszalnej mowy i położone z pauzą: 0,33 s w akapicie, 1 s po
akapicie, 1,5 s przed rozdziałem, 0,5 s na wejście i 1,5 s na końcu (`--pauzy zdanie=0.4,akapit=1.2`). Wynik:
`lektor.wav` od 0 s filmu (pauzy są już w pliku), `lektor.slowa.json` i `lektor.srt` (napisy z podziałami `|`)
oraz `os_czasu.json`: zdania, ujęcia, rozdziały, napisy i chwile po nazwie. Strona czyta go modułem `os_czasu.js`:
```js
import { wczytajOs } from '/_lib/jarvo/os_czasu.js';
const O = await wczytajOs();                          // os_czasu.json obok strony
Object.assign(window, { __W: W, __H: H, __DUR: O.dlugosc });
// w draw(t):
const u = O.ujecie(t);                                // bieżące ujęcie: u.id, u.nr, u.start, u.koniec, u.mowa_koniec
const wejscie = O.postep(t, O.bit('kolejka', -0.2), O.bit('kolejka', 0.3));   // liczba wchodzi ze słowem
const napis = O.napis(t);                             // grupa napisów w chwili t (gdy strona rysuje napisy sama)
```
- W scenie z lektorem żadnych sekund wpisanych w kod: każda chwila z `O.bit()`: `u3` (początek ujęcia),
  `u3.z2` (2. zdanie), `u3.mowa_koniec`, `u3.koniec` (cięcie), `r2` (rozdział), własna `{nazwa}` z narracji.
  Element wchodzi od 0,2 s przed do 0,1 s po swoim słowie; nowy element tylko na ważnym zdaniu.
- Ujęcie = akapit. Cięcie wypada w pauzie po akapicie, 0,25 s przed pierwszym słowem następnego: obraz zmienia
  się, gdy lektor milknie, a ostatni element ląduje najpóźniej przy `uN.mowa_koniec` i stoi do cięcia (oddech).
- Inny tekst, głos albo tempo = `film.py narracja` jeszcze raz; strona się nie zmienia, idzie za nową osią. Nazwa
  chwili, której w osi już nie ma, zatrzymuje render i pomiar z nazwą (`nieznana chwila „…”`), nic nie przesuwa się po cichu.
- `--dlugosc` renderu i pomiaru = `O.dlugosc` (narracja podaje gotowe polecenie). Napisy wypalasz z
  `lektor.slowa.json` (`napisy.py --slowa`) albo rysuje je strona z `O.napis(t)`, nie oba naraz.
- Fakty: brief Sherlocka w `out/wideo/src/fakty.json` (katalog wyżej niż strona). `narracja` sprawdza z nim liczby
  lektora, a `pomiar` liczby na ekranie stojące ≥ 0,5 s (klatki licznika w ruchu nie): `liczba_niepewna` = błąd,
  `liczba_bez_zrodla` = ostrzeżenie (oś wykresu, numer kroku: `--wyjatek "liczba_bez_zrodla@50=oś wykresu…"`).
  Zmiana briefu = pomiar nieaktualny.

## Render
```bash
H=$HERMES_HOME/scripts/html_wideo.py
python3 $H klatki out/wideo/src/<nazwa>/index.html --preset jarvo --czasy 0,1.5,3,6,9,11.9 --arkusz out/wideo/qa-look.jpg
python3 $H pomiar out/wideo/src/<nazwa>/index.html --preset jarvo --dlugosc 12 --platforma tiktok   # przed finałem
python3 $H wideo  out/wideo/src/<nazwa>/index.html --preset jarvo --dlugosc 12 --fps 30 -o out/wideo/<nazwa>.mp4
```
- Najpierw arkusz (1 klatka na scenę) → vision → poprawki; dopiero potem całość.
- **Pomiar** (`pomiar.json` + `pomiar.md` obok strony): czas czytania (błąd poniżej 70% minimum dla szybkiego
  czytelnika, ostrzeżenie poniżej spokojnego czytania: znaki bez spacji / 15 + 1,5 s), tekst poza kadrem i pod UI platformy, kontrast,
  kroje zastępcze, czarne przerwy, martwe odcinki, rytm, błędy JS i zasobów; ostrzeżenia kompozycji: pusta scena,
  brak oddechu przed cięciem i na końcu, > 3 uderzenia całego kadru. W trakcie poprawek `--tryb szybki`;
  film oddajesz tylko z pełnym i aktualnym raportem bez błędów (`html_wideo.py aktualny <strona>` = 0). Świadomy
  wyjątek z powodem: `--wyjatek "czas_czytania@Logo=znak marki, nie tekst do czytania"`.
- `--subklatki N` = motion blur (render N× dłuższy): tylko na wyraźną prośbę właściciela. `--alfa -o x.mov` = przezroczyste tło.
- WebGL liczy się na CPU (VPS bez GPU): zmierz czas 1 klatki (`klatki --czasy 5`) i oszacuj całość, zanim ruszysz 60 s w 60 fps.
  `wideo` renderuje w kilku przeglądarkach naraz (samo: do 4, według rdzeni i pamięci; `--rownolegle N`) i czeka
  na miejsce, gdy na maszynie trwają już 2 pełne rendery albo przy trwającym renderze wolnej pamięci jest < 30%.
- Dźwięk (lektor, muzyka, efekty) dokłada `film.py` (`"plik"` + `"koniec": "stop"`) albo `montaz.py`; potem `qa_wideo.py`.
  Film z lektorem z `narracja` i muzyką pisaną kodem: `muzyka.py zrob film.mp4 -o final.mp4 --lektor src/lektor.wav
  --cues cues.json` (głos w miksie, muzyka ściszana pod mowę, efekty w pauzach; skill `lektor-i-dzwiek`).

## Trzy formaty z jednej osi czasu
Jedna scena, jedna oś czasu, **układ liczony z rozmiaru kadru**, a nie stałe piksele: `const L = layout(W, H)`
na starcie (`W`, `H` z `window.__W/__H`), a każda scena rysuje w jednostkach `L` (np. `L.u = Math.min(W, H) / 100`,
`L.safe` = bezpieczne marginesy platformy, `L.pion = H > W`). Dla pionu układ się **przestawia** (tekst nad obrazem
zamiast obok, większa typografia), a nie przycina z poziomu. Render każdego formatu tym samym plikiem:
`html_wideo.py wideo anim.html --preset jarvo --rozmiar 1080x1920 …`, `--rozmiar 1080x1080`, `--rozmiar 1920x1080`.
Kontrola: `krytyka.py telefon` dla każdego formatu (tekst czytelny w 360 px).
