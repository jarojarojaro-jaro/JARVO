# Kontrakt HTML: własna animacja (Canvas, SVG, Three.js, GSAP) → wideo

Jeden plik `out/wideo/src/<nazwa>/index.html` (+ assety obok). Ta sama strona służy do podglądu (odtwarza się
w pętli) i do renderu klatka po klatce: `html_wideo.py --preset jarvo` woła `window.__seek(t)` dla każdej klatki.

## Pięć twardych reguł
1. `window.__seek(t)` rysuje **cały** stan w chwili `t` (sekundy) i nic nie zwraca (albo `Promise`, gdy czeka). Nic poza `t`: zero `Date.now`,
   `performance.now`, `setTimeout`, `Math.random` bez ziarna (`mulberry32(seed)`), zero stanu z poprzedniej klatki
   (fizyka i cząstki liczone od `t = 0` albo z krokiem stałym od zera do `t`).
2. `window.__W`, `window.__H` = rozmiar kadru (1080×1920 pion, 1920×1080 poziom); `window.__DUR` = długość w s.
3. `window.__ready = true` dopiero po fontach (`await document.fonts.ready`), obrazach i teksturach.
4. Biblioteki lokalnie z `/_lib/` (html_wideo serwuje wspólne `node_modules`; `narzedzia.py instaluj html`):
   Three.js `/_lib/three/build/three.module.js` (+ `/_lib/three/examples/jsm/…`), GSAP `/_lib/gsap/dist/gsap.min.js`.
   Bez CDN: render ma działać offline i zawsze tak samo.
5. Tekst jako prawdziwy tekst (font z polskimi znakami: sprawdź „Zażółć gęślą jaźń” na arkuszu), nie bitmapa z AI.
6. **Tekst na kanwie podajesz pomiarowi:** `window.__teksty = () => [...]` zwraca teksty bieżącej klatki
   `{tekst, x, y, w, h, kolor, rozmiar, krycie, widoczny?, id?}` (prostokąt w pikselach kadru, `widoczny` = odsłonięta
   część przy pisaniu). Tekst w DOM (HTML, SVG) `pomiar` czyta sam; bez `__teksty` tekst z `fillText` jest dla niego
   niewidoczny (zostają tylko kontrole obrazu).

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

## Pułapki renderu
- `will-change` na czymś, co skaluje kamera → rozmyty tekst; nie używaj. `z-index` na każdej warstwie.
- Dziecko z `visibility: visible` prześwituje przez ukrytego rodzica: używaj `inherit`.
- Wszystkie zmienne zadeklarowane przed pierwszym `__seek` (render woła go od razu).
- Wideo w stronie: przekoduj all-intra (`ffmpeg -i in.mp4 -g 1 -an klip.mp4`), wczytaj jako blob URL (serwer renderu
  nie przewija zakresami), w `__seek` ustaw `currentTime` i zwróć `Promise` czekający na `seeked`.
- `backdrop-filter: url()` źle czyta mapy przesunięć w Chromium: „szkło” = klon sceny pod elementem + filtr SVG.
- Szybki ruch: `--subklatki 8` (4 zostawia duchy) i trochę wolniej; potem klatka po klatce przez szybkie chwile
  i `qa_wideo.py` (wykrywa pojedyncze „mrugnięcia”).
- Dźwięk: prawdziwy efekt na każde zdarzenie, położony wg szczytu (`rytm.py efekt.wav --szczyt`), całość −14 LUFS.

## Render
```bash
H=$HERMES_HOME/scripts/html_wideo.py
python3 $H klatki out/wideo/src/<nazwa>/index.html --preset jarvo --czasy 0,1.5,3,6,9,11.9 --arkusz out/wideo/qa-look.jpg
python3 $H pomiar out/wideo/src/<nazwa>/index.html --preset jarvo --dlugosc 12 --platforma tiktok   # przed finałem
python3 $H wideo  out/wideo/src/<nazwa>/index.html --preset jarvo --dlugosc 12 --fps 30 -o out/wideo/<nazwa>.mp4
```
- Najpierw arkusz (1 klatka na scenę) → vision → poprawki; dopiero potem całość.
- **Pomiar** (`pomiar.json` + `pomiar.md` obok strony): czas czytania, tekst poza kadrem i pod UI platformy, kontrast,
  kroje zastępcze, czarne przerwy, martwe odcinki, rytm, błędy JS i zasobów. W trakcie poprawek `--tryb szybki`;
  film oddajesz tylko z pełnym i aktualnym raportem bez błędów (`html_wideo.py aktualny <strona>` = 0). Świadomy
  wyjątek z powodem: `--wyjatek "czas_czytania@Logo=znak marki, nie tekst do czytania"`.
- `--subklatki 4` = motion blur (4× dłużej); tylko w finale i przy szybkim ruchu. `--alfa -o x.mov` = przezroczyste tło.
- WebGL liczy się na CPU (VPS bez GPU): zmierz czas 1 klatki (`klatki --czasy 5`) i oszacuj całość, zanim ruszysz 60 s w 60 fps.
- Dźwięk (lektor, muzyka, efekty) dokłada `film.py` (`"plik"` + `"koniec": "stop"`) albo `montaz.py`; potem `qa_wideo.py`.

## Trzy formaty z jednej osi czasu
Jedna scena, jedna oś czasu, **układ liczony z rozmiaru kadru**, a nie stałe piksele: `const L = layout(W, H)`
na starcie (`W`, `H` z `window.__W/__H`), a każda scena rysuje w jednostkach `L` (np. `L.u = Math.min(W, H) / 100`,
`L.safe` = bezpieczne marginesy platformy, `L.pion = H > W`). Dla pionu układ się **przestawia** (tekst nad obrazem
zamiast obok, większa typografia), a nie przycina z poziomu. Render każdego formatu tym samym plikiem:
`html_wideo.py wideo anim.html --preset jarvo --rozmiar 1080x1920 …`, `--rozmiar 1080x1080`, `--rozmiar 1920x1080`.
Kontrola: `krytyka.py telefon` dla każdego formatu (tekst czytelny w 360 px).
