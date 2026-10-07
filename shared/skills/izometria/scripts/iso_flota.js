/* Rys. — Flota Jarvo: wieża z mostkiem szefa na górze i pokojami agentów (po dwa na piętro), terminal TY i skrzynka
   RAPORT. Klik w terminal albo spacja puszcza zlecenie przez flotę: szef rozpisuje karty, agenci pracują, szef
   sprawdza wyniki, raport wraca do Ciebie. Dane między znacznikami FLOTA wstawia `iso.py flota` z fleet.yaml
   (tu przykład); czas tylko z api, więc PNG i film wychodzą zawsze tak samo. */
(() => {
const FLOTA = /*FLOTA*/{"szef": {"nazwa": "Jarvo", "rola": "main judge"}, "agenci": [{"nazwa": "Sherlock", "rola": "researcher-detektyw"}, {"nazwa": "Web", "rola": "web senior dev"}, {"nazwa": "Studio", "rola": "marketing i kreacja"}, {"nazwa": "Wideograf", "rola": "wideograf"}, {"nazwa": "Ręka", "rola": "prawa ręka"}], "przyklad": [0, 1, 2]}/*FLOTA*/;
const A = FLOTA.agenci, N = A.length, SZEF = FLOTA.szef.nazwa.toLowerCase();
const agentow = n => n === 1 ? 'agent' : (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14)) ? 'agenci' : 'agentów';
const lista = A.map(a => `${a.nazwa} (${a.rola})`).join(', ');

FIGS.push({
  id: 'flota',
  name: 'Flota Jarvo',
  hint: 'Klik w pokój = kto to · terminal TY albo spacja = zlecenie · strzałki + Enter · o = zgaś',
  aria: `Izometryczna wieża floty. Na górze mostek: ${FLOTA.szef.nazwa} (${FLOTA.szef.rola}). Niżej pokoje agentów: ${lista}. `
    + 'Kliknij pokój, żeby zobaczyć, kto to. Kliknij terminal TY albo naciśnij spację: zlecenie przejdzie przez flotę '
    + 'od szefa do agentów i z powrotem jako raport.',
  css: `
    [data-fig="flota"] .flota-pokoj, [data-fig="flota"] .flota-most, [data-fig="flota"] #flota-ty { cursor:pointer; }
    [data-fig="flota"] .flota-pokoj:hover .band, [data-fig="flota"] .flota-most:hover .face.top { stroke:var(--ink); }
    [data-fig="flota"] .flota-txt { fill:var(--ink); font-family:var(--mono); transition:fill .3s; }
    [data-fig="flota"] .flota-rola { opacity:.8; }
    [data-fig="flota"] .on .flota-txt, [data-fig="flota"] .flota-ty-on .flota-txt, [data-fig="flota"] .flota-raport-on .flota-txt { fill:var(--accent-hi); }
    [data-fig="flota"] .flota-pokoj.praca .led.hot { animation:blink .6s steps(1) infinite; }
    [data-fig="flota"] .flota-kursor { fill:none; stroke:var(--accent-hi); stroke-width:1.6; vector-effect:non-scaling-stroke; opacity:0; pointer-events:none; }
    [data-fig="flota"] .kursor .flota-kursor { opacity:1; filter:url(#soft); }
    [data-fig="flota"] .flota-maszt { fill:none; stroke:var(--line); stroke-width:1.2; vector-effect:non-scaling-stroke; }
    [data-fig="flota"] .flota-latarnia { fill:var(--accent-hi); animation:flota-mig 1.4s steps(1) infinite; }
    [data-fig="flota"] .flota-latarnia-halo { fill:var(--accent); opacity:.5; animation:flota-mig 1.4s steps(1) infinite; }
    [data-fig="flota"] .flota-kartka { fill:var(--accent); stroke:var(--accent-hi); stroke-width:.8; vector-effect:non-scaling-stroke; opacity:0; transition:opacity .3s; }
    [data-fig="flota"] .flota-kartka.hot { opacity:.9; }
    @keyframes flota-mig { 0% { opacity:1; } 45% { opacity:.08; } }
    @media (prefers-reduced-motion:reduce) { [data-fig="flota"] .flota-latarnia, [data-fig="flota"] .flota-latarnia-halo,
      [data-fig="flota"] .flota-pokoj.praca .led.hot { animation:none; } }
  `,
  mount(stage, api) {
    const F = Math.max(1, Math.ceil(N / 2));
    /*  bryły                 x    y    z    w    d    h
        płyta                 0    0    0  260  220    7
        hol (parter)         80   60    7   90   90   26   -> przód y=150, bok x=170
        piętra agentów       80   60   33   90   90  F×30  (dwa pokoje na piętro: przód i bok, pierwsi agenci u góry)
        mostek szefa         88   68   ZT   74   74   30   + maszt 36 z latarnią
        terminal TY          14  168    7   36   36   30
        skrzynka RAPORT     196   24    7   40   36   22                                                       */
    const PZ = 7, TX = 80, TY = 60, TW = 90, TD = 90, FY = TY + TD, SX = TX + TW, LH = 26, FH = 30;
    const Z0 = PZ + LH, ZT = Z0 + F * FH, BX = TX + 8, BY = TY + 8, BW = TW - 16, BD = TD - 16, BH = 30, ZB = ZT + BH;
    const ZW = PZ + .5, RX = SX + 1.5, RY = FY + 1.5;          // kable po płycie i pion przy narożniku wieży
    const K = api.iso.frame([[0,220,0],[260,0,PZ],[260,220,0],[0,0,PZ],[125,105,ZB + 46],[TX,FY,ZT],[SX,TY,ZT]], 0.05);
    const { P, TOP, FRONT, SIDE, box, path } = K, slits = api.iso.slits, esc = api.iso.esc;

    // płyta
    let svg = box(0,0,0, 260,220,PZ, 12);
    svg += `<g transform="${TOP(0,0,PZ)}"><rect class="detail" x="8" y="8" width="244" height="204" rx="8"/>
      ${[[18,18],[242,18],[18,202],[242,202]].map(([x,y]) => `<circle class="face recess" cx="${x}" cy="${y}" r="2.6"/>`).join('')}</g>`;
    svg += `<g transform="${FRONT(0,220,PZ)}"><text class="label" x="16" y="5.4" font-size="4.4" letter-spacing=".6">${esc(`${FLOTA.szef.nazwa} · ${N + 1} ${agentow(N + 1)}`.toUpperCase())}</text></g>`;
    svg += `<g transform="${SIDE(260,220,PZ)}">${slits(150, 206, 3, 2, 5)}</g>`;

    // hol: drzwi zleceń z przodu, wyjście raportów z boku
    svg += box(TX,TY,PZ, TW,TD,LH, 2);
    svg += `<g transform="${FRONT(TX,FY,Z0)}">
      <text class="label" x="7" y="15" font-size="5">ZLECENIA</text>
      <rect class="halo" id="flota-drzwi-halo" x="31" y="3" width="28" height="${LH - 3}" filter="url(#bloom)"/>
      <rect class="face glass" id="flota-drzwi" filter="url(#soft)" x="33" y="5" width="24" height="${LH - 5}"/>
      <line class="detail" x1="45" y1="5" x2="45" y2="${LH}"/>${slits(66, 84, 4, 6, LH - 4)}</g>`;
    svg += `<g transform="${SIDE(SX,FY,Z0)}">
      <text class="label" x="7" y="15" font-size="5">RAPORTY</text>
      <rect class="face glass" id="flota-wyjscie" filter="url(#soft)" x="44" y="9" width="12" height="${LH - 9}"/>${slits(66, 84, 4, 6, LH - 4)}</g>`;

    // piętra: pokój z przodu i z boku, szyba z nazwą i rolą, kontrolka przy narożniku (tam dochodzi kabel)
    svg += box(TX,TY,Z0, TW,TD,F * FH, 0);
    for (let i = 0; i < 2 * F; i++) {
      const k = F - 1 - Math.floor(i / 2), przod = i % 2 === 0, w = przod ? TW : TD;
      const t = przod ? FRONT(TX, FY, Z0 + (k + 1) * FH) : SIDE(SX, FY, Z0 + (k + 1) * FH);
      if (i >= N) { svg += `<g transform="${t}"><rect class="face band" width="${w}" height="${FH}"/>${slits(8, w - 8, 6, 6, FH - 6)}</g>`; continue; }
      const gx = przod ? 5 : 14, gw = w - 19, lx = przod ? w - 7 : 7;
      svg += `<g class="flota-pokoj" data-i="${i}" transform="${t}">
        <rect class="face band" width="${w}" height="${FH}"/>
        <rect class="halo" x="${gx - 2}" y="3" width="${gw + 4}" height="${FH - 6}" filter="url(#bloom)"/>
        <rect class="face glass" filter="url(#soft)" x="${gx}" y="5" width="${gw}" height="${FH - 10}" rx="1.5"/>
        <text class="flota-txt" x="${gx + 5}" y="14" font-size="8.5">${esc(A[i].nazwa.toUpperCase())}</text>
        <text class="flota-txt flota-rola" x="${gx + 5}" y="21.6" font-size="4.8">${esc(A[i].rola)}</text>
        <circle class="led" filter="url(#soft)" cx="${lx}" cy="${FH / 2}" r="2.2"/>
        <rect class="flota-kursor" x="-.6" y="-.6" width="${w + 1.2}" height="${FH + 1.2}"/>
      </g>`;
    }
    svg += `<g transform="${TOP(TX,TY,ZT)}"><rect class="detail" x="3" y="3" width="${TW - 6}" height="${TD - 6}" rx="1"/></g>`;

    // mostek szefa z masztem i latarnią
    const szyba = (w, gora, dol) => `<rect class="halo" x="2" y="2" width="${w - 4}" height="${BH - 6}" filter="url(#bloom)"/>
        <rect class="face glass" filter="url(#soft)" x="4" y="4" width="${w - 8}" height="${BH - 10}" rx="2"/>
        <text class="flota-txt" x="9" y="13.5" font-size="${gora.length > 7 ? 7 : 9}">${esc(gora)}</text>
        <text class="flota-txt flota-rola" x="9" y="20.5" font-size="4.8">${esc(dol)}</text>`;
    svg += `<g class="flota-most" id="flota-most">${box(BX,BY,ZT, BW,BD,BH, 3)}
      <g transform="${FRONT(BX,BY + BD,ZB)}">${szyba(BW, FLOTA.szef.nazwa.toUpperCase(), FLOTA.szef.rola)}
        <rect class="flota-kursor" x="-.6" y="-.6" width="${BW + 1.2}" height="${BH + 1.2}"/></g>
      <g transform="${SIDE(BX + BW,BY + BD,ZB)}">${szyba(BD, 'MISJE', 'karty · ocena')}</g>
      <g transform="${TOP(BX,BY,ZB)}"><rect class="detail" x="4" y="4" width="${BW - 8}" height="${BD - 8}" rx="2"/></g>
    </g>`;
    const mx = BX + BW / 2, my = BY + BD / 2, m = z => P(mx, my, z).map(n => n.toFixed(2)).join(' ');
    svg += box(mx - 4, my - 4, ZB, 8, 8, 6, 1);
    svg += `<path class="flota-maszt" d="M${m(ZB + 6)}L${m(ZB + 38)}"/>`;
    const lp = P(mx, my, ZB + 40);
    svg += `<circle class="flota-latarnia-halo" cx="${lp[0]}" cy="${lp[1]}" r="7" filter="url(#bloom)"/>`
      + `<circle class="flota-latarnia" filter="url(#glow)" cx="${lp[0]}" cy="${lp[1]}" r="2.2"/>`;

    // skrzynka RAPORT (tył po prawej) i terminal TY (przód po lewej)
    svg += box(196,24,PZ, 40,36,22, 3);
    svg += `<g transform="${TOP(196,24,PZ + 22)}"><rect class="face recess" x="5" y="5" width="30" height="26" rx="2"/>
      <rect class="flota-kartka" id="flota-kartka" filter="url(#soft)" x="9" y="8" width="22" height="20"/></g>`;
    svg += `<g id="flota-raport" transform="${FRONT(196,60,PZ + 22)}">
      <rect class="halo" x="2" y="2" width="36" height="14" filter="url(#bloom)"/>
      <rect class="face glass" filter="url(#soft)" x="4" y="4" width="32" height="12" rx="2"/>
      <text class="flota-txt" x="8" y="12.4" font-size="6">RAPORT</text></g>`;
    svg += `<g class="press" id="flota-ty">${box(14,168,PZ, 36,36,30, 3)}
      <g transform="${TOP(14,168,PZ + 30)}">${slits(8, 30, 4, 8, 28)}</g>
      <g transform="${FRONT(14,204,PZ + 30)}">
        <rect class="halo" x="2" y="2" width="32" height="22" filter="url(#bloom)"/>
        <rect class="face glass" filter="url(#soft)" x="4" y="4" width="28" height="18" rx="2"/>
        <text class="flota-txt" x="8" y="12.5" font-size="7.5">TY</text>
        <text class="flota-txt flota-rola" x="8" y="19" font-size="4.6">zlecenie</text></g>
    </g>`;

    // kable (stałe) i impulsy (jednorazowe, api.replay): zlecenie → hol → pion → mostek → pokoje → mostek → raport
    const kabel = (id, pkt) => { const d = path(pkt); return `<path class="wire-under" d="${d}"/><path class="wire" id="${id}" filter="url(#soft)" d="${d}"/>`; };
    const puls = (id, pkt) => `<path class="pulse" id="${id}" filter="url(#glow)" pathLength="1000" d="${path(pkt)}"/>`;
    const ZLEC = [[50,186,ZW],[125,186,ZW],[125,RY,ZW]], PION = [[125,RY,ZW],[RX,RY,ZW],[RX,RY,ZT],[BX + BW,BY + BD,ZT]];
    const WYJ = [[RX,RY,ZW],[RX,100,ZW],[216,100,ZW],[216,60.5,ZW]], NAROZ = [[BX + BW,BY + BD,ZT],[RX,RY,ZT]];
    svg += kabel('flota-k-zlecenie', ZLEC) + kabel('flota-k-pion', PION) + kabel('flota-k-raport', WYJ);
    svg += puls('flota-p-zlecenie', ZLEC) + puls('flota-p-pion', PION) + puls('flota-p-raport', [...NAROZ, ...WYJ]);
    A.forEach((a, i) => {
      const z = Z0 + (F - 1 - Math.floor(i / 2)) * FH + FH / 2;
      const dol = [...NAROZ, [RX,RY,z], i % 2 === 0 ? [TX + TW - 7,RY,z] : [RX,FY - 7,z]];
      svg += puls(`flota-p-dol-${i}`, dol) + puls(`flota-p-gora-${i}`, dol.slice().reverse());
    });

    stage.setAttribute('viewBox', K.viewBox);
    stage.innerHTML = svg;

    // stan: jeden obiekt, jedno render(); klik i klawiatura wołają te same funkcje
    const q = s => stage.querySelector(s);
    const pokoje = [...stage.querySelectorAll('.flota-pokoj')].sort((a, b) => a.dataset.i - b.dataset.i);
    const most = q('#flota-most'), ty = q('#flota-ty'), raport = q('#flota-raport');
    const PUSTO = () => ({ on: new Set(), praca: new Set(), most: false, ty: false, drzwi: false, raport: false, krok: '', wybrany: null });
    const st = { ...PUSTO(), kursor: -1 };
    let zegary = [];
    const swiec = (el, on) => el.querySelectorAll('.glass, .halo, .led').forEach(e => e.classList.toggle('hot', on));
    const opis = i => i < 0 ? `${SZEF} · ${FLOTA.szef.rola}` : `${A[i].nazwa.toLowerCase()} · ${A[i].rola}`;
    function render() {
      pokoje.forEach((el, i) => {
        el.classList.toggle('on', st.on.has(i)); el.classList.toggle('praca', st.praca.has(i));
        el.classList.toggle('kursor', st.kursor === i + 1); swiec(el, st.on.has(i));
      });
      most.classList.toggle('on', st.most); most.classList.toggle('kursor', st.kursor === 0); swiec(most, st.most);
      ty.classList.toggle('flota-ty-on', st.ty); swiec(ty, st.ty);
      raport.classList.toggle('flota-raport-on', st.raport); swiec(raport, st.raport);
      ['#flota-drzwi', '#flota-drzwi-halo', '#flota-k-pion'].forEach(s => q(s).classList.toggle('hot', st.drzwi));
      ['#flota-wyjscie', '#flota-kartka', '#flota-k-raport'].forEach(s => q(s).classList.toggle('hot', st.raport));
      q('#flota-k-zlecenie').classList.toggle('hot', st.ty);
      api.power(st.on.size > 0 || st.most || st.ty || st.raport);
      api.readout(st.krok || (st.wybrany !== null ? opis(st.wybrany) : `${N + 1} ${agentow(N + 1)} · spacja = zlecenie`));
    }
    const t = (ms, fn) => zegary.push(api.after(ms, fn));
    function stop() { zegary.forEach(z => api.clear(z)); zegary = []; }
    function zlecenie() {
      stop();
      Object.assign(st, PUSTO(), { ty: true, krok: '1/5 zlecenie od ciebie' });
      api.flash(ty); render();
      const przyklad = FLOTA.przyklad.filter(i => i >= 0 && i < N);
      t(150, () => api.replay(q('#flota-p-zlecenie')));
      t(600, () => { st.drzwi = true; render(); api.replay(q('#flota-p-pion')); });
      t(1150, () => { st.most = true; st.krok = `2/5 ${SZEF} rozpisuje karty`; render(); });
      let ms = 1550;
      przyklad.forEach((i, n) => {
        t(ms + n * 280, () => api.replay(q(`#flota-p-dol-${i}`)));
        t(ms + n * 280 + 450, () => {
          st.on.add(i); st.praca.add(i);
          const kto = przyklad.filter(j => st.on.has(j)).map(j => A[j].nazwa.toLowerCase());
          st.krok = `3/5 ${kto.length > 1 ? 'pracują' : 'pracuje'}: ${kto.join(', ')}`; render();
        });
      });
      ms += przyklad.length * 280 + 450 + 600;
      przyklad.forEach((i, n) => t(ms + n * 250, () => { st.praca.delete(i); render(); api.replay(q(`#flota-p-gora-${i}`)); }));
      ms += przyklad.length * 250 + 450;
      t(ms, () => { st.krok = `4/5 ${SZEF} sprawdza wyniki`; render(); api.replay(q('#flota-p-pion')); });
      t(ms + 700, () => api.replay(q('#flota-p-raport')));
      t(ms + 1250, () => { st.raport = true; st.krok = '5/5 raport dla ciebie'; render(); });
    }
    function wybierz(i) {                                    // -1 = szef na mostku
      st.krok = ''; st.wybrany = i; st.kursor = i + 1;
      if (i < 0) st.most = !st.most;
      else { if (st.on.has(i)) st.on.delete(i); else st.on.add(i); st.praca.delete(i); }
      render();
    }
    function kursor(d) { st.kursor = Math.max(0, Math.min(N, st.kursor + d)); st.wybrany = st.kursor - 1; st.krok = ''; render(); }
    stage.addEventListener('click', e => {
      if (e.target.closest('#flota-ty')) { zlecenie(); return; }
      const p = e.target.closest('.flota-pokoj');
      if (p) { wybierz(+p.dataset.i); return; }
      if (e.target.closest('#flota-most')) wybierz(-1);
    });
    render();
    return {
      key(e) {
        if (e.key === ' ') { if (!e.repeat) zlecenie(); return true; }
        if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') { kursor(-1); return true; }
        if (e.key === 'ArrowDown' || e.key === 'ArrowRight') { kursor(1); return true; }
        if (e.key === 'Enter') { if (st.kursor >= 0) wybierz(st.kursor - 1); return true; }
        if (e.key === 'o' || e.key === 'O') { stop(); Object.assign(st, PUSTO()); render(); return true; }
        return false;
      },
      unmount: stop,
      demo: () => api.after(200, zlecenie),
    };
  },
});
})();
