/* Rys. — Ekspres do kawy (przykład Jarva): przyciski parzą espresso albo doppio, para z dyszy, klik w filiżankę
   ją opróżnia, spacja włącza i wyłącza. Czas tylko z api (after / every), więc PNG i film wychodzą zawsze tak samo. */
FIGS.push({
  id: 'ekspres',
  name: 'Ekspres do kawy',
  hint: '1 espresso · 2 doppio · P para · klik w filiżankę · spacja wł./wył.',
  aria: 'Izometryczny ekspres do kawy z filiżanką. Klawisz 1 albo lewy przycisk parzy espresso, 2 podwójne, P puszcza parę z dyszy; klik w filiżankę ją opróżnia, spacja włącza i wyłącza ekspres.',
  css: `
    [data-fig="ekspres"] .ekspres-kawa { fill:var(--accent); opacity:0; transition:opacity .25s; }
    [data-fig="ekspres"] #ekspres-filizanka, [data-fig="ekspres"] #ekspres-korpus { cursor:pointer; }
    [data-fig="ekspres"] #ekspres-filizanka:hover .face.top { stroke:var(--ink); }
    [data-fig="ekspres"] .ekspres-strumien { opacity:0; transition:opacity .15s; }
    [data-fig="ekspres"].parzy .ekspres-strumien { opacity:1; }
  `,
  mount(stage, api) {
    /*  bryły               x    y    z    w    d    h
        podstawa            0    0    0  280  230    7
        korpus             60   30    7  160  110  150   -> przód y=140, góra z=157
        pojemnik na ziarno 150   44  157   54   54   34
        tacka              72  140    7  136   64   10   -> góra z=17
        filiżanka         122  156   17   36   32   26   -> góra z=43
        grupa (głowica)   114  140   78   52   18   14
        uchwyt kolby      136  158   73    8   44    5                                   */
    const K = api.iso.frame([[0,230,0],[280,0,7],[280,230,0],[60,30,191],[220,30,157],[204,44,191],[248,118,130]]);
    const { TOP, FRONT, SIDE, box, path } = K, slits = api.iso.slits, esc = api.iso.esc;
    let svg = box(0,0,0, 280,230,7, 14);
    svg += `<g transform="${TOP(0,0,7)}"><rect class="detail" x="9" y="9" width="262" height="212" rx="10"/>
      ${[[18,18],[262,18],[18,212],[262,212]].map(([x,y]) => `<circle class="face recess" cx="${x}" cy="${y}" r="3"/>`).join('')}</g>`;

    // korpus i jego ściany
    svg += `<g id="ekspres-korpus">${box(60,30,7, 160,110,150, 8)}</g>`;
    svg += `<g transform="${FRONT(60,140,157)}">
      <rect class="face recess" x="14" y="12" width="132" height="44" rx="6"/>
      <rect class="halo" x="20" y="17" width="72" height="34" rx="4" filter="url(#bloom)"/>
      <rect class="face glass" filter="url(#soft)" x="20" y="17" width="72" height="34" rx="4"/>
      <text class="scr" id="ekspres-temp" x="27" y="35" font-size="12">92°</text>
      <text class="scr" id="ekspres-stan" x="27" y="46" font-size="6.5">gotowy</text>
      <circle class="led" id="ekspres-led" filter="url(#soft)" cx="134" cy="22" r="2.4"/>
      <text class="label" x="104" y="40" font-size="6">CREMA</text>
      <text class="label" x="104" y="48" font-size="4.5">mod. 01</text>
      ${slits(16, 144, 4, 128, 140)}
    </g>`;
    svg += `<g transform="${SIDE(220,140,157)}">${slits(14, 96, 4, 14, 60)}<rect class="face recess" x="10" y="104" width="90" height="30" rx="4"/></g>`;

    // pojemnik na ziarno (z tyłu na górze)
    svg += box(150,44,157, 54,54,34, 6);
    svg += `<g transform="${TOP(150,44,191)}"><rect class="face recess" x="8" y="8" width="38" height="38" rx="8"/>${slits(14, 40, 4, 14, 40, false)}</g>`;
    svg += `<g transform="${FRONT(150,98,191)}"><text class="label" x="8" y="20" font-size="6.5">ZIARNO</text></g>`;

    // przyciski na blacie (przód góry): espresso, doppio, para
    const PRZYCISKI = [['1', 76, 'espresso', '1×'], ['2', 100, 'doppio', '2×'], ['p', 124, 'para', 'PARA']];
    PRZYCISKI.forEach(([k, x]) => { svg += `<g class="press ekspres-przycisk" data-k="${k}">${box(x,102,157, 18,16,4, 3)}</g>`; });
    svg += `<g transform="${TOP(60,30,157)}">${PRZYCISKI.map(([, x, , opis]) =>
      `<text class="label" x="${x - 60 + 1}" y="${118 - 30 + 8}" font-size="5.5">${esc(opis)}</text>`).join('')}</g>`;

    // dysza pary (prawa ściana)
    const dysza = path([[220,116,128],[236,122,122],[246,126,112],[246,126,52]]);
    svg += `<path class="wire-under" d="${dysza}"/><path class="wire" id="ekspres-dysza" filter="url(#soft)" d="${dysza}"/>`;
    svg += `<path class="pulse" id="ekspres-para" filter="url(#glow)" pathLength="1000" d="${dysza}"/>`;

    // tacka z kratką
    svg += box(72,140,7, 136,64,10, 4);
    svg += `<g transform="${TOP(72,140,17)}"><rect class="face recess" x="6" y="6" width="124" height="52" rx="3"/>${slits(12, 124, 6, 10, 54)}</g>`;

    // filiżanka (klik = pusta)
    svg += `<g id="ekspres-filizanka">${box(122,156,17, 36,32,26, 10)}
      <g transform="${TOP(122,156,43)}"><rect class="face recess" x="4" y="4" width="28" height="24" rx="8"/>
        <rect class="ekspres-kawa" id="ekspres-kawa" filter="url(#soft)" x="6" y="6" width="24" height="20" rx="7"/></g>
      <g transform="${SIDE(158,188,40)}"><rect class="face" x="8" y="4" width="14" height="14" rx="6"/><rect class="face recess" x="11" y="7" width="8" height="8" rx="4"/></g>
    </g>`;

    // grupa, kolba i strumień kawy
    svg += box(114,140,78, 52,18,14, 4);
    svg += `<g transform="${FRONT(114,158,92)}"><rect class="face recess" x="6" y="5" width="40" height="6" rx="3"/></g>`;
    svg += box(126,146,72, 28,14,6, 3);
    svg += box(136,158,73, 8,44,5, 2.5);
    const strumien = path([[140,152,72],[140,152,58],[140,152,44]]);
    svg += `<g class="ekspres-strumien"><path class="wire hot" filter="url(#glow)" d="${strumien}"/>
      <path class="pulse" id="ekspres-kropla" filter="url(#glow)" pathLength="1000" d="${strumien}"/></g>`;

    stage.setAttribute('viewBox', K.viewBox);
    stage.innerHTML = svg;

    const q = s => stage.querySelector(s);
    const przyciski = new Map([...stage.querySelectorAll('.ekspres-przycisk')].map(el => [el.dataset.k, el]));
    const st = { on: true, ml: 0, cel: 0, rodzaj: '', para: false, parzenie: null, krople: null, paraT: null };
    function render() {
      stage.classList.toggle('on', st.on);
      stage.classList.toggle('parzy', !!st.parzenie);
      api.power(st.on);
      q('.glass').classList.toggle('hot', st.on); q('.halo').classList.toggle('hot', st.on);
      q('#ekspres-led').classList.toggle('hot', st.on);
      q('#ekspres-dysza').classList.toggle('hot', st.para);
      q('#ekspres-temp').textContent = st.on ? '92°' : '';
      q('#ekspres-stan').textContent = !st.on ? '' : st.parzenie ? `parzę ${st.ml} ml` : st.para ? 'para' : st.ml ? 'gotowe' : 'gotowy';
      const kawa = q('#ekspres-kawa');
      kawa.style.opacity = st.ml ? String(0.35 + 0.65 * Math.min(1, st.ml / 50)) : '0';
      przyciski.forEach((el, k) => el.classList.toggle('latched', (k === 'p' && st.para) || (st.parzenie && st.rodzaj === (k === '1' ? 'espresso' : 'doppio'))));
      const czesci = [st.on ? 'wł.' : 'wył.'];
      if (st.on) czesci.push('92°c');
      if (st.rodzaj && st.ml) czesci.push(`${st.rodzaj} ${st.ml} ml`);
      if (st.para) czesci.push('para');
      api.readout(czesci.join(' · '));
    }
    function stop() {
      api.clear(st.parzenie); api.clear(st.krople); st.parzenie = st.krople = null;
    }
    function parz(rodzaj) {
      if (!st.on || st.parzenie) return;
      st.rodzaj = rodzaj; st.ml = 0; st.cel = rodzaj === 'doppio' ? 50 : 25;
      st.krople = api.every(260, () => api.replay(q('#ekspres-kropla')));
      st.parzenie = api.every(80, () => { st.ml += 1; if (st.ml >= st.cel) stop(); render(); });
      render();
    }
    function para() {
      if (!st.on) return;
      st.para = true; api.replay(q('#ekspres-para'));
      api.clear(st.paraT);
      [300, 600, 900].forEach(ms => api.after(ms, () => st.para && api.replay(q('#ekspres-para'))));
      st.paraT = api.after(1200, () => { st.para = false; render(); });
      render();
    }
    function nacisnij(k) {
      const el = przyciski.get(k); if (!el) return false;
      api.flash(el);
      if (k === 'p') para(); else parz(k === '1' ? 'espresso' : 'doppio');
      return true;
    }
    function wlacznik() { st.on = !st.on; if (!st.on) { stop(); st.para = false; } render(); }
    stage.addEventListener('click', e => {
      const b = e.target.closest('.ekspres-przycisk');
      if (b) { nacisnij(b.dataset.k); return; }
      if (e.target.closest('#ekspres-filizanka') && !st.parzenie) { st.ml = 0; st.rodzaj = ''; render(); return; }
      if (e.target.closest('#ekspres-korpus')) wlacznik();
    });
    render();
    return {
      key: e => { const k = e.key.toLowerCase(); if (k === ' ') { wlacznik(); return true; } return nacisnij(k); },
      unmount: stop,
      demo: () => { api.after(200, () => nacisnij('1')); api.after(2600, () => nacisnij('p')); },
    };
  },
});
