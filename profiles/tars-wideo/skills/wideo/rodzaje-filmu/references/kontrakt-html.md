# Kontrakt HTML: własna animacja (Canvas, SVG, Three.js, GSAP) → wideo

Jeden plik `out/wideo/src/<nazwa>/index.html` (+ assety obok). Ta sama strona służy do podglądu (odtwarza się
w pętli) i do renderu klatka po klatce: `html_wideo.py --preset tars` woła `window.__seek(t)` dla każdej klatki.

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
function draw(t) {
  g.clearRect(0, 0, W, H);
  // scena 1 (0–3 s): hak; scena 2 (3–7 s): …; każda scena liczy swój postęp z seg(t, start, koniec)
}
window.__seek = (t) => draw(t);
await document.fonts.ready; draw(0); window.__ready = true;
if (!new URLSearchParams(location.search).has('render')) {           // podgląd dla człowieka
  const t0 = performance.now(); (function loop(now) { draw(((now - t0) / 1000) % DUR); requestAnimationFrame(loop); })(t0);
}
</script></body></html>
```
`--preset tars` otwiera stronę z `?render=1`: pętla podglądu musi być wyłączona w tym trybie (jak wyżej), inaczej
rysowałaby klatki z zegara między `__seek` a zrzutem.

**Three.js:** `<script type="importmap">{"imports":{"three":"/_lib/three/build/three.module.js",
"three/addons/":"/_lib/three/examples/jsm/"}}</script>`, `renderer = new THREE.WebGLRenderer({canvas: c,
antialias: true, preserveDrawingBuffer: true})`, w `__seek`: ustaw kamerę, obiekty i uniformy shaderów z `t`,
potem `renderer.render(scene, camera)`. Bez `clock.getDelta()`.
**GSAP:** `<script src="/_lib/gsap/dist/gsap.min.js"></script>`, jedna oś `const tl = gsap.timeline({paused: true})`,
`window.__seek = (t) => { tl.seek(t, false); }` (w klamrach: `__seek` nie zwraca osi, bo oś GSAP jest „thenable”;
jeśli coś ładujesz asynchronicznie przy seek, zwróć prawdziwy `Promise`).

## Render
```bash
H=$HERMES_HOME/scripts/html_wideo.py
python3 $H klatki out/wideo/src/<nazwa>/index.html --preset tars --czasy 0,1.5,3,6,9,11.9 --arkusz out/wideo/qa-look.jpg
python3 $H wideo  out/wideo/src/<nazwa>/index.html --preset tars --dlugosc 12 --fps 30 -o out/wideo/<nazwa>.mp4
```
- Najpierw arkusz (1 klatka na scenę) → vision → poprawki; dopiero potem całość.
- `--subklatki 4` = motion blur (4× dłużej); tylko w finale i przy szybkim ruchu. `--alfa -o x.mov` = przezroczyste tło.
- WebGL liczy się na CPU (VPS bez GPU): zmierz czas 1 klatki (`klatki --czasy 5`) i oszacuj całość, zanim ruszysz 60 s w 60 fps.
- Dźwięk (lektor, muzyka, efekty) dokłada `film.py` (`"plik"` + `"koniec": "stop"`) albo `montaz.py`; potem `qa_wideo.py`.
