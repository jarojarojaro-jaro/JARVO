/* Jarvo: ustawienia strony figur iso-glow i zegar wirtualny (iso.py wkleja ten plik na początek <head>).

   window.ISO_JARVO: ustawienia wpisane przy budowie (iso.py zbuduj / png / wideo), parametry adresu je nadpisują:
     ?kadr         sama figura na całym ekranie (bez paska, listy figur i stopki): osadzenie na stronie, PNG, film
     ?podpis       w kadrze także podpis „Rys. N · nazwa” i odczyt
     ?motyw=jasny|ciemny, ?akcent=<nazwa koloru z palety>, ?tlo=0 (przezroczyste tło), ?figura=<id>, ?demo
     ?render=1     render klatka po klatce (html_wideo.py --preset jarvo, iso.py png): kadr + zegar wirtualny

   Zegar wirtualny (render): api.after / every / loop / flash i demo() figury idą po czasie strony, nie ścianie,
   więc window.__seek(t) pokazuje stan w chwili t (sekundy) zawsze tak samo. Animacje i przejścia CSS stają
   w tym samym czasie (document.getAnimations()). Globalnych setTimeout ani requestAnimationFrame nie ruszamy
   (używa ich przeglądarka i Playwright); figura bierze czas z api (api.after, api.loop(ts), api.now()). */
(() => {
  const BAKED = /*ISO_JARVO*/{}/*ISO_JARVO*/;
  const q = new URLSearchParams(location.search);
  const J = window.ISO_JARVO = Object.assign({ kadr: false, podpis: false, motyw: 'auto', tlo: true }, BAKED);
  for (const k of ['kadr', 'podpis', 'demo', 'render']) if (q.has(k) && q.get(k) !== '0') J[k] = true;
  for (const k of ['motyw', 'akcent', 'figura']) if (q.get(k)) J[k] = q.get(k);
  if (q.get('tlo') === '0') J.tlo = false;
  if (J.render) J.kadr = true;
  const R = document.documentElement;
  if (J.kadr) R.dataset.kadr = '';
  if (J.podpis) R.dataset.podpis = '';
  if (J.motyw === 'jasny') R.dataset.theme = 'light';
  if (J.motyw === 'ciemny') R.dataset.theme = 'dark';
  if (!J.tlo) R.dataset.tlo = '0';

  const realny = {
    after: (fn, ms) => setTimeout(fn, ms), every: (fn, ms) => setInterval(fn, ms),
    clear: id => { clearTimeout(id); clearInterval(id); }, raf: fn => requestAnimationFrame(fn), now: () => performance.now(),
  };
  if (!J.render) { window.__isoCzas = realny; return; }

  // ---------------------------------------------------------------- zegar wirtualny
  const KLATKA = 1000 / 60, POCZATEK_ID = 1e9, LIMIT_KROKOW = 200000;
  let teraz = 0, nr = POCZATEK_ID, kolejnosc = 0, nastepnaKlatka = KLATKA;
  const zegary = new Map();            // id → {kiedy, fn, co (ms; 0 = raz), k (kolejność przy tym samym czasie)}
  let klatki = new Map();              // id → fn (api.loop: jedna klatka co 1/60 s czasu strony)
  const start = new WeakMap();         // animacja CSS/WAAPI → czas strony, w którym się pojawiła
  const bledy = window.__isoBledy = [];
  const wywolaj = (fn, args) => {
    try { if (typeof fn === 'function') fn(...args); }
    catch (e) { bledy.push(String(e && e.stack || e)); if (window.reportError) window.reportError(e); }
  };
  const wirtualny = {
    after: (fn, ms) => { const id = ++nr; zegary.set(id, { kiedy: teraz + Math.max(0, +ms || 0), fn, co: 0, k: ++kolejnosc }); return id; },
    every: (fn, ms) => { const id = ++nr, co = Math.max(1, +ms || 0); zegary.set(id, { kiedy: teraz + co, fn, co, k: ++kolejnosc }); return id; },
    clear: id => { if (zegary.delete(id) || klatki.delete(id)) return; realny.clear(id); },
    raf: fn => { const id = ++nr; klatki.set(id, fn); if (nastepnaKlatka <= teraz) nastepnaKlatka = (Math.floor(teraz / KLATKA) + 1) * KLATKA; return id; },
    now: () => teraz,
  };
  window.__isoCzas = wirtualny;
  // clearTimeout(id) w figurze na uchwycie z api.after: id wirtualne zdejmujemy z naszej kolejki, resztę oddajemy przeglądarce
  const ct = window.clearTimeout, ci = window.clearInterval;
  window.clearTimeout = id => { if (!zegary.delete(id)) ct(id); };
  window.clearInterval = id => { if (!zegary.delete(id)) ci(id); };

  const animacje = () => {
    for (const a of document.getAnimations()) {
      if (!start.has(a)) start.set(a, teraz);
      try { a.pause(); a.currentTime = Math.max(0, teraz - start.get(a)); } catch (e) { /* animacja już zdjęta */ }
    }
  };
  async function naprzod(cel) {
    for (let krok = 0; ; krok++) {
      if (krok > LIMIT_KROKOW) throw new Error(`iso: ponad ${LIMIT_KROKOW} zdarzeń do ${cel} ms (pętla zegarów w figurze?)`);
      let nast = null;
      for (const [id, z] of zegary) if (z.kiedy <= cel && (!nast || z.kiedy < nast[1].kiedy || (z.kiedy === nast[1].kiedy && z.k < nast[1].k))) nast = [id, z];
      const klatka = klatki.size ? nastepnaKlatka : Infinity;
      if (nast && nast[1].kiedy <= klatka) {
        const [id, z] = nast;
        teraz = Math.max(teraz, z.kiedy); animacje();
        if (z.co) { z.kiedy += z.co; z.k = ++kolejnosc; } else zegary.delete(id);
        wywolaj(z.fn, []);
      } else if (klatka <= cel) {
        teraz = Math.max(teraz, klatka); nastepnaKlatka = klatka + KLATKA; animacje();
        const fns = [...klatki.values()]; klatki = new Map();
        for (const fn of fns) wywolaj(fn, [teraz]);
      } else break;
      await null;                     // mikrozadania (Promise) z wywołania przed następnym zdarzeniem
      animacje();                     // nowe przejścia CSS dostają czas startu z tej chwili
    }
    teraz = cel;
    if (nastepnaKlatka <= teraz) nastepnaKlatka = (Math.floor(teraz / KLATKA) + 1) * KLATKA;
    animacje();
  }
  // cofnięcie czasu: figura od nowa (mount czyści swoje zegary), potem znów do przodu
  function odNowa() {
    zegary.clear(); klatki = new Map(); teraz = 0; nastepnaKlatka = KLATKA;
    if (window.__isoMount) window.__isoMount();
    animacje();
  }
  window.__seek = async (t) => {
    const cel = Math.max(0, +t || 0) * 1000;
    if (cel < teraz - 1e-6) odNowa();
    await naprzod(cel);
  };
  window.__W = J.w || 1600; window.__H = J.h || 1200;
  if (J.dlugosc) window.__DUR = J.dlugosc;
  window.__ready = false;
  const gotowe = async () => {
    try {
      await document.fonts.ready;
      await document.fonts.load('16px "JetBrains Mono"', 'Zażółć gęślą jaźń 0123');
    } catch (e) { /* krój systemowy */ }
    animacje();
    window.__ready = true;
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', gotowe); else gotowe();
})();
