// Ekran: kineskop (CRT), taśma VHS i interfejs HUD jako jeden filtr WebGL2 nakładany na gotową klatkę (canvas 2D,
// WebGL, obraz). Wszystkie zakłócenia liczone z numeru klatki, nie z zegara: render klatka po klatce = podgląd.
// Strona: import { ekran, wlaczanie, wylaczanie } from '/_lib/jarvo/crt.js';
//   const e = ekran(document.querySelector('#wyjscie'), 'vhs');        // canvas wyjścia (WebGL2), tryb crt | vhs | hud
//   e.rysuj(scena, klatka, { pasek: 0.6, zaklocenie: 1 });              // scena = canvas z klatką, zmiany na tę klatkę
// (html_wideo.py i podgląd HQ serwują ten plik pod /_lib/jarvo/; zasady stylów: style-motion/references/)
// Render w kontenerze liczy WebGL procesorem (SwiftShader): płótno wyjścia 1920×1080 kosztuje ok. 0,2 s na klatkę
// (vhs ok. 0,5 s), 960×540 rozciągnięte na kadr (CSS albo drawImage) ok. 3× mniej przy tym samym wyglądzie.
//
// Przeniesione z mg-styles-15 (MIT, Vincentwei1021): kineskop i ostry piksel z demos/20-pixel/film.js, taśma
// z demos/10-synthwave/index.html, linie, aberracja, włączanie i wyłączanie z demos/22-hud/js/post.js.

const ZERO = { krzywizna: 0, linie: 0, poswiata: 0, winieta: 0, linie3: 0, chwiej: 0, pasek: 0, zaklocenie: 0,
               krwawienie: 0, rozszczep: 0, aberracja: 0, snieg: 0, ziarno: 0, glowica: 0, wlacz: 1, wylacz: 0, blysk: 0 };

// krzywizna: beczka kineskopu (0,03) · linie: linie wiązki wg rzędów źródła (pixel art) · poswiata: luminofor ·
// linie3: linie co 3 px wyjścia · chwiej: falowanie linii taśmy · pasek: pasek śledzenia 0–1 · zaklocenie: zerwane
// linie 0–1 · krwawienie: rozmyty kolor taśmy (YIQ) · rozszczep: R/B w poziomie (px) · aberracja: R/B od środka ·
// snieg: szum zamiast obrazu 0–1 · ziarno: amplituda ziarna · glowica: szum głowicy na dole · wlacz: 0 → 1 otwiera
// obraz z poziomej linii · wylacz: 0 → 1 ściska obraz w linię, potem w kropkę · blysk: biały błysk 0–1.
export const TRYBY = Object.freeze({
  crt: Object.freeze({ ...ZERO, krzywizna: 0.03, linie: 1, poswiata: 0.55, winieta: 0.24 }),
  vhs: Object.freeze({ ...ZERO, chwiej: 1, krwawienie: 1, rozszczep: 1.2, linie3: 0.12, winieta: 0.35, ziarno: 0.05, glowica: 1 }),
  hud: Object.freeze({ ...ZERO, linie3: 0.2, aberracja: 0.0007, winieta: 0.4, ziarno: 0.028 }),
});

const VS = `#version 300 es
in vec2 p; void main(){ gl_Position = vec4(p, 0., 1.); }`;

const FS = `#version 300 es
precision highp float;
uniform sampler2D uTex;
uniform vec2 uSrc, uOut;
uniform float uKlatka, uKrzywizna, uLinie, uPoswiata, uWinieta, uLinie3, uChwiej, uPasek, uZaklocenie,
  uKrwawienie, uRozszczep, uAberracja, uSnieg, uZiarno, uGlowica, uWlacz, uWylacz, uBlysk;
out vec4 o;
float h11(float p){ p = fract(p * .1031); p *= p + 33.33; p *= p + p; return fract(p); }
float h21(vec2 p){ vec3 q = fract(vec3(p.xyx) * .1031); q += dot(q, q.yzx + 33.33); return fract((q.x + q.y) * q.z); }
float vn(float x){ float i = floor(x), f = fract(x); f = f * f * (3. - 2. * f); return mix(h11(i), h11(i + 1.), f); }
vec3 yiq(vec3 c){ return vec3(dot(c, vec3(.299, .587, .114)), dot(c, vec3(.596, -.274, -.322)), dot(c, vec3(.211, -.523, .312))); }
vec3 rgb(vec3 c){ return vec3(c.x + .956 * c.y + .621 * c.z, c.x - .272 * c.y - .647 * c.z, c.x - 1.106 * c.y + 1.703 * c.z); }
vec3 ostry(vec2 uv){   // piksel źródła płaski w środku, krawędź wygładzona na 1 px wyjścia (bez mory na krzywiźnie)
  vec2 t = uv * uSrc, fl = floor(t), s = t - fl, sc = max(uOut / uSrc, vec2(1.)), reg = .5 - .5 / sc, cd = s - .5;
  return textureLod(uTex, (fl + (cd - clamp(cd, -reg, reg)) * sc + .5) / uSrc, 0.).rgb; }
void main(){
  vec2 P = vec2(gl_FragCoord.x, uOut.y - gl_FragCoord.y), uv = P / uOut;
  float fr = uKlatka, csy = 1., csx = 1.;
  if (uWylacz > 0.) { csy = max(pow(1. - min(uWylacz / .6, 1.), 2.2), .003); csx = uWylacz > .6 ? max(1. - (uWylacz - .6) / .4, 0.) : 1.; }
  uv = vec2(.5 + (uv.x - .5) / max(csx, 1e-3), .5 + (uv.y - .5) / csy);
  vec2 c = uv * 2. - 1.;
  if (uKrzywizna > 0.) { c = c * (1. + uKrzywizna * dot(c, c)) / (1. + uKrzywizna); uv = c * .5 + .5; }
  vec2 e = min(uv, 1. - uv);
  float ramka = uKrzywizna > 0. ? smoothstep(0., .0022, e.x) * smoothstep(0., .004, e.y) : step(0., min(e.x, e.y));
  float y = uv.y * uOut.y, ln = floor(y), wob = 0.;
  float pasek = smoothstep(.075, 0., abs(uv.y - fract(fr * .023 + .18))) * uPasek;
  if (uChwiej > 0.) {
    wob = ((vn(y * .03 + fr * .9) - .5) * (1.1 + 12. * uPasek) + (vn(y * .45 + fr * 7.3) - .5) * (.35 + 2.5 * uPasek)) * uChwiej;
    wob += pasek * (h21(vec2(ln * .5, fr)) - .5) * 70.;
  }
  float zs = floor(fr * .5) + 1., gh = 6. + 14. * h11(zs * 1.7 + .3), rz = floor((y + h11(zs) * 80.) / gh);
  float zon = uZaklocenie * step(.82, h21(vec2(rz, zs)));
  wob += zon * (h21(vec2(rz, zs + 5.)) < .5 ? -1. : 1.) * (8. + 32. * h21(vec2(rz, zs + 3.)));
  float glw = uGlowica * (1. - smoothstep(uOut.y - 17., uOut.y - 5., y));
  wob += glw * (16. + 24. * h21(vec2(ln, fr)));
  uv.x += wob / uOut.x;
  vec2 o1 = vec2(1. / uOut.x, 0.);
  vec3 col = ostry(uv);
  if (uKrwawienie > 0.) {
    float Y = yiq(col).x * .6 + .2 * (yiq(textureLod(uTex, uv + o1, 0.).rgb).x + yiq(textureLod(uTex, uv - o1, 0.).rgb).x);
    vec2 iq = vec2(0.); float ws = 0.;
    for (int i = 0; i < 9; i++) { float fi = float(i), w = exp(-fi * .32); iq += yiq(textureLod(uTex, uv - o1 * (fi * 1.7 + 1. + zon * 3.), 0.).rgb).yz * w; ws += w; }
    vec3 b = rgb(vec3(Y, iq / ws * 1.1));
    float rs = 0., rw = 0.;
    for (int i = 1; i <= 6; i++) { float fi = float(i), w = exp(-fi * .38); rs += textureLod(uTex, uv - o1 * (fi + uRozszczep), 0.).r * w; rw += w; }
    b.r = max(b.r, rs / rw * .82);
    col = mix(col, b, uKrwawienie);
  }
  float sp = uRozszczep * (1. + zon);
  if (sp > 0.) { col.r = mix(col.r, textureLod(uTex, uv + o1 * sp, 0.).r, .6); col.b = mix(col.b, textureLod(uTex, uv - o1 * sp, 0.).b, .6); }
  if (uAberracja > 0.) {
    vec2 dc = uv - .5, ab = dc * uAberracja * (.3 + dot(dc * vec2(1.78, 1.), dc * vec2(1.78, 1.)) * 1.2) * (1. + 10. * zon);
    col.r = textureLod(uTex, uv + ab, 0.).r; col.b = textureLod(uTex, uv - ab, 0.).b;
  }
  if (uLinie > 0.) {
    float lum = dot(col, vec3(.3, .59, .11)), sy = fract(uv.y * uSrc.y) - .5, bw = mix(.30, .47, lum);
    col *= mix(1., mix(.64, 1., smoothstep(bw + .13, bw - .05, abs(sy))) * 1.1, uLinie);
  }
  if (uPoswiata > 0.) {   // poświata z pomniejszonych kopii źródła (mipmapy): 5 odczytów zamiast 16, ten sam promień
    vec2 ts = 2.2 / uSrc;
    vec3 g = textureLod(uTex, uv, 1.).rgb * .4 + (textureLod(uTex, uv + vec2(ts.x, 0.), 1.5).rgb
      + textureLod(uTex, uv - vec2(ts.x, 0.), 1.5).rgb + textureLod(uTex, uv + vec2(0., ts.y), 1.5).rgb
      + textureLod(uTex, uv - vec2(0., ts.y), 1.5).rgb) * .15;
    col += max(g - .3, 0.) * uPoswiata;
  }
  float sn = h21(vec2(floor(P.x * .5) + fr * 37., ln * 1.3 + fr * 17.));
  col = mix(col, vec3(sn * .9), uSnieg);
  col += pasek * sn * sn * .55;
  col = mix(col, vec3(h21(vec2(P.x + fr, ln))) * .55, glw * .55);
  col *= 1. - uLinie3 * (.5 - .5 * cos(y * 6.2831853 / 3.));
  col *= 1. - uWinieta * pow(length(c) / 1.4142, 2.6);
  col += (h21(P * 1.37 + fr * 13.1) - .5) * uZiarno + (h21(P + fr) - .5) / 255.;
  col = mix(col, vec3(1.), uBlysk);
  if (uWlacz < 1.) {
    float ah = uWlacz * .5, dy = abs(P.y / uOut.y - .5), hx = exp(-pow((P.x / uOut.x - .5) / (.18 + .9 * uWlacz), 2.));
    float lg = exp(-pow((dy - ah) * uOut.y / (3. + 6. * (1. - uWlacz)), 2.)) * (1. - uWlacz) * 1.6 * hx;
    col = col * smoothstep(ah + .002, ah - .002, dy) + vec3(.75, .95, 1.) * lg;
  }
  if (uWylacz > 0.) {
    col *= (1. + 2. * uWylacz);
    float dyp = abs(P.y / uOut.y - .5) * uOut.y, dxn = abs(P.x / uOut.x - .5) * 2.;
    float lg = exp(-dyp * dyp / (4. + 400. * csy)) * smoothstep(csx + .03, csx - .03, dxn) * smoothstep(.15, .55, uWylacz);
    float dg = exp(-(dxn * dxn * 900. + dyp * dyp / 30.)) * smoothstep(.55, .9, uWylacz) * (1. - .6 * smoothstep(.9, 1., uWylacz));
    col = col * ramka + vec3(.8, .97, 1.) * (lg * 1.1 + dg * 1.4);
    ramka = 1.;
  }
  o = vec4(clamp(col * ramka, 0., 1.), 1.);
}`;

const NAZWY = Object.keys(ZERO);
const uniform = (n) => 'u' + n[0].toUpperCase() + n.slice(1);

export function ekran(cel, tryb = 'crt', opcje = {}) {
  if (!TRYBY[tryb]) throw new Error(`nieznany tryb ekranu: ${tryb} (${Object.keys(TRYBY).join(', ')})`);
  const gl = cel.getContext('webgl2', { preserveDrawingBuffer: true, antialias: false, alpha: false });
  if (!gl) throw new Error('crt.js: brak WebGL2 w tej przeglądarce');
  const shader = (typ, zrodlo) => {
    const s = gl.createShader(typ);
    gl.shaderSource(s, zrodlo); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  };
  const prog = gl.createProgram();
  gl.attachShader(prog, shader(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, shader(gl.FRAGMENT_SHADER, FS));
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
  gl.useProgram(prog);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, 'p');
  gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  gl.bindTexture(gl.TEXTURE_2D, gl.createTexture());
  for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR],
                        [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
  const U = Object.fromEntries([...NAZWY, 'src', 'out', 'klatka', 'tex'].map((n) => [n, gl.getUniformLocation(prog, uniform(n))]));
  gl.uniform1i(U.tex, 0);
  const ust = { ...TRYBY[tryb], ...opcje };
  return {
    ust,
    // zrodlo: canvas / obraz z gotową klatką (pixel art: mały canvas, np. 320×180; skalę robi filtr),
    // klatka: numer klatki (zakłócenia), zmiany: parametry tylko na tę klatkę (np. { wlacz: wlaczanie(t, 0) }).
    rysuj(zrodlo, klatka = 0, zmiany = {}) {
      const p = { ...ust, ...zmiany };
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, zrodlo);
      gl.generateMipmap(gl.TEXTURE_2D);   // pomniejszone kopie do poświaty (i pełny łańcuch, bo filtr używa mipmap)
      gl.viewport(0, 0, cel.width, cel.height);
      gl.uniform2f(U.src, zrodlo.width || zrodlo.naturalWidth, zrodlo.height || zrodlo.naturalHeight);
      gl.uniform2f(U.out, cel.width, cel.height);
      gl.uniform1f(U.klatka, klatka);
      for (const n of NAZWY) gl.uniform1f(U[n], p[n]);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      gl.finish();
    },
  };
}

// Włączenie od chwili t0: 0 (pozioma linia) → 1 (pełny obraz) w `czas` s, szybko na początku. Do `wlacz`.
export function wlaczanie(t, t0, czas = 0.37) {
  const u = Math.min(1, Math.max(0, (t - t0) / czas));
  return u >= 1 ? 1 : 1 - Math.pow(2, -10 * u);
}
// Wyłączenie od chwili t1: 0 → 1 w `czas` s (obraz w linię do 0,6, potem linia w kropkę). Do `wylacz`.
export function wylaczanie(t, t1, czas = 0.2) {
  return Math.min(1, Math.max(0, (t - t1) / czas));
}
