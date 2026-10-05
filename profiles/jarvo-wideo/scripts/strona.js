// Strona klienta w filmie: kamera po zrzucie strony z `assety.py --film` (kafle 2×, `uklad.json` z celami).
// Strona: import { stronaZUkladu, zbudujStrone, kamera, przewijanie, wycieczka, najazd, lupa, uderzenie, zakreslacz,
//                  sprawdzPlan } from '/_lib/jarvo/strona.js';
// Ruchy to czyste funkcje czasu t (sekundy): fabryka zwraca funkcję t → stan kamery {x, y, zoom}, gdzie (x, y) to punkt
// strony (piksele CSS całej strony) na środku kadru, a zoom = piksele kadru na piksel strony.
// Zasady i liczby: film-z-kodu/references/strona-filmowana.md. Pomysły i liczby ruchów (przewijanie ~10% strony na
// sekundę z postojem i hamowaniem, wycieczka do 4 punktów, lupa, uderzenie, zakreślacz) za video-talkcraft (licencja
// niekomercyjna: wzięte tylko liczby, kod nasz); przybliżanie przez CSS `zoom` (ostre wycinki) za video-shotcraft
// (Apache-2.0, PageCam).

import { bezier } from './ruch.js';

const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, u) => a + (b - a) * u;
const gladko = bezier(0.42, 0, 0.58, 1);
const kadrDomyslny = () => [globalThis.__W ?? 1920, globalThis.__H ?? 1080];

export const LICZBY = Object.freeze({
  tempo: 0.10,            // przewijanie: część wysokości strony na sekundę
  postoj: 1.5,            // postój na przystanku 1–2 s
  rozped: 0.6,            // ruszanie
  hamowanie: 1.4,         // hamowanie zaczyna się ~1,4 s przed przystankiem
  wycieczkaZoom: 1.4,     // wycieczka: przybliżenie 1,3–1,5 szerokości strony
  trzymaj: 1.0,           // wycieczka: postój w punkcie 0,8–1,2 s
  przejazd: 1.15,         // wycieczka: przejazd 1,05–1,3 s
  krzywa: [0.16, 1, 0.3, 1],
  punktyMax: 4,
  lupa: 1.75,             // lupa 1,5–2×
  lupaWys: 1 / 3,         // najwyżej trzecia część wysokości kadru
  lupaWejscie: 0.3,
  lupaTlo: 0.8,           // jasność tła pod lupą 0,75–0,85
  uderzenie: 2.3,         // uderzenie (crash zoom): 6 klatek do 2,3×
  uderzenieKlatki: 6,
  uderzeniaMax: 2,        // najwyżej 2 na film
  zakreslacz: 0.6,        // przeciągnięcie zakreślacza 0,4–0,8 s
});

// ---------------------------------------------------------------- strona z uklad.json
// uklad = JSON z assety.py --film; zwraca {szer, wys, dpr, kafle, pusta, cele, cel(id), srodek(id), katalog}
export function stronaZUkladu(uklad, { strona = 'start', widok = 'desktop', katalog = '' } = {}) {
  const s = uklad?.strony?.[strona];
  if (!s) throw new Error(`uklad.json: brak strony „${strona}” (są: ${Object.keys(uklad?.strony || {}).join(', ') || 'żadne'})`);
  const w = s[widok];
  if (!w || !w.kafle) throw new Error(`uklad.json: strona „${strona}” nie ma widoku „${widok}”${w?.brak ? ` (${w.brak})` : ''}`);
  const cele = Object.fromEntries((w.cele || []).filter(c => !c.brak).map(c => [c.id, c]));
  const cel = (id) => {
    if (typeof id === 'object' && id) return id;
    const c = cele[id];
    if (!c) throw new Error(`nieznany cel „${id}” (są: ${Object.keys(cele).slice(0, 40).join(', ')})`);
    return c;
  };
  const srodek = (id) => { const c = cel(id); return { x: c.x + c.w / 2, y: c.y + c.h / 2 }; };
  return { szer: w.szer, wys: w.wys, dpr: w.dpr, kafle: w.kafle, pusta: w.pusta || [], cele, cel, srodek, katalog, widok };
}

// zoom, przy którym strona wypełnia szerokość kadru
export const dopasuj = (strona, kadr = kadrDomyslny()) => kadr[0] / strona.szer;

// kamera nie pokazuje nic poza stroną (gdy strona jest węższa od kadru: środek)
export function ogranicz(stan, strona, kadr = kadrDomyslny()) {
  const pw = kadr[0] / stan.zoom / 2, ph = kadr[1] / stan.zoom / 2;
  const x = strona.szer <= 2 * pw ? strona.szer / 2 : clamp(stan.x, pw, strona.szer - pw);
  const y = strona.wys <= 2 * ph ? strona.wys / 2 : clamp(stan.y, ph, strona.wys - ph);
  return { ...stan, x, y };
}

// punkt strony → piksele kadru (podpisy, kursor, ramki nad stroną)
export function wKadrze(stan, punkt, kadr = kadrDomyslny()) {
  return { x: (punkt.x - stan.x) * stan.zoom + kadr[0] / 2, y: (punkt.y - stan.y) * stan.zoom + kadr[1] / 2 };
}

const punkt = (strona, p) => (typeof p === 'number' ? { x: strona.szer / 2, y: p }
  : (typeof p === 'string' || p?.id) ? strona.srodek(p) : { x: p.x ?? strona.szer / 2, y: p.y });

function oznacz(f, typ, od, koniec, maxZoom, extra = {}) {
  return Object.assign(f, { typ, od, do: koniec, maxZoom, ...extra });
}

// ---------------------------------------------------------------- ruchy kamery
// Przewijanie z postojami: od góry (albo `start`) przez przystanki (id celu, y strony albo {x, y}); cel stoi na środku
// kadru przez `postoj` s. Prędkość ~10% wysokości strony na sekundę (najwyżej 0,6 wysokości widoku na sekundę),
// rozpęd 0,6 s, hamowanie 1,4 s. Zwraca f(t) → {x, y, zoom, faza: 'start'|'jazda'|'postoj'|'koniec', przystanek}.
export function przewijanie({ strona, od = 0, przystanki = [], start = 'gora', kadr = kadrDomyslny(), przyblizenie = 1,
                              tempo = LICZBY.tempo, postoj = LICZBY.postoj, rozped = LICZBY.rozped,
                              hamowanie = LICZBY.hamowanie } = {}) {
  if (!przystanki.length) throw new Error('przewijanie: podaj przystanki (id celów albo y strony)');
  const zoom = dopasuj(strona, kadr) * przyblizenie;
  const widok = kadr[1] / zoom;
  const v = clamp(tempo * strona.wys, 0.15 * widok, 0.6 * widok);
  const na = (p) => ogranicz({ ...punkt(strona, p), zoom }, strona, kadr);
  const p0 = start === 'gora' ? na(0) : na(start);
  const odcinki = [];
  let t = od, prev = p0;
  przystanki.forEach((p, i) => {
    const cel = na(p);
    const d = Math.hypot(cel.x - prev.x, cel.y - prev.y);
    const T = d < 1 ? 0 : d / v + (rozped + hamowanie) / 2;
    odcinki.push({ od: t, do: t + T, z: prev, na: cel, d, T, i });
    t += T;
    odcinki.push({ od: t, do: t + postoj, postoj: true, na: cel, i });
    t += postoj;
    prev = cel;
  });
  const koniec = t;
  const f = (tt) => {
    if (tt <= od) return { ...p0, faza: 'start', przystanek: -1 };
    for (const o of odcinki) {
      if (tt > o.do) continue;
      if (o.postoj) return { ...o.na, faza: 'postoj', przystanek: o.i };
      const s = trapez(o.d, o.T, rozped, hamowanie)(tt - o.od) / (o.d || 1);
      return { x: lerp(o.z.x, o.na.x, s), y: lerp(o.z.y, o.na.y, s), zoom, faza: 'jazda', przystanek: o.i };
    }
    return { ...prev, faza: 'koniec', przystanek: przystanki.length - 1 };
  };
  return oznacz(f, 'przewijanie', od, koniec, zoom,
    { chwile: odcinki.filter(o => o.postoj).map(o => ({ przystanek: o.i, od: o.od, do: o.do })) });
}

// profil prędkości: stałe przyspieszenie przez `a` s, jazda, stałe hamowanie przez `b` s; zwraca drogę 0 → d
export function trapez(d, T, a, b) {
  if (T <= 0) return () => d;
  if (a + b > T) { const k = T / (a + b); a *= k; b *= k; }
  const v = d / (T - a / 2 - b / 2);
  return (tau) => {
    if (tau <= 0) return 0;
    if (tau >= T) return d;
    if (tau < a) return v * tau * tau / (2 * a);
    if (tau <= T - b) return v * a / 2 + v * (tau - a);
    const r = T - tau;
    return d - v * r * r / (2 * b);
  };
}

// Wycieczka: kamera staje kolejno w punktach (najwyżej 4), w każdym `trzymaj` s; przejazd `przejazd` s krzywą
// (0.16, 1, 0.3, 1). Punkt: {cel | x, y, przyblizenie (1,3–1,5)}. `start: 'calosc'` zaczyna od całej szerokości.
// `nachylenie`: rotX 14° / rotY −20° na przejazdach (perspective na kontenerze). Zwraca f(t) → {x, y, zoom, rotX, rotY}.
export function wycieczka({ strona, od = 0, punkty = [], kadr = kadrDomyslny(), trzymaj = LICZBY.trzymaj,
                            przejazd = LICZBY.przejazd, krzywa = LICZBY.krzywa, start = null, nachylenie = false } = {}) {
  if (!punkty.length) throw new Error('wycieczka: podaj punkty');
  if (punkty.length > LICZBY.punktyMax) throw new Error(`wycieczka: najwyżej ${LICZBY.punktyMax} punkty na ujęcie (jest ${punkty.length}); podziel na dwa ujęcia`);
  const fit = dopasuj(strona, kadr);
  const stany = punkty.map(p => {
    const pp = typeof p === 'string' ? { cel: p } : p;
    const xy = pp.cel ? strona.srodek(pp.cel) : punkt(strona, pp);
    return ogranicz({ ...xy, zoom: fit * (pp.przyblizenie ?? LICZBY.wycieczkaZoom) }, strona, kadr);
  });
  if (start === 'calosc') stany.unshift(ogranicz({ x: strona.szer / 2, y: stany[0].y, zoom: fit }, strona, kadr));
  const krok = trzymaj + przejazd;
  const e = bezier(...krzywa);
  const koniec = od + (stany.length - 1) * krok + trzymaj;
  const f = (t) => {
    const tt = Math.max(0, t - od);
    const i = Math.min(stany.length - 1, Math.floor(tt / krok));
    const w = tt - i * krok;
    const a = stany[i], b = stany[Math.min(i + 1, stany.length - 1)];
    const r = i >= stany.length - 1 || w <= trzymaj ? 0 : clamp((w - trzymaj) / przejazd);
    const u = e(r);
    const zoom = Math.exp(lerp(Math.log(a.zoom), Math.log(b.zoom), u));      // przybliżenie w skali logarytmicznej
    const lot = nachylenie ? Math.sin(Math.PI * r) : 0;                      // nachylenie najmocniejsze w połowie czasu
    return { x: lerp(a.x, b.x, u), y: lerp(a.y, b.y, u), zoom, rotX: 14 * lot, rotY: -20 * lot, punkt: u > 0.5 ? i + 1 : i };
  };
  const chwile = stany.map((_, i) => ({ punkt: i, od: od + i * krok, do: od + i * krok + trzymaj }));
  return oznacz(f, 'wycieczka', od, koniec, Math.max(...stany.map(s => s.zoom)), { chwile });
}

// Wolny najazd na jedno ujęcie (warstwa kamery bez efektu PowerPointa): 100% → 104–106% przez całe ujęcie.
export function najazd({ strona, cel = null, od = 0, do: koniec, z = 1, na = 1.05, kadr = kadrDomyslny() } = {}) {
  if (koniec === undefined) throw new Error('najazd: podaj „do” (koniec ujęcia)');
  const fit = dopasuj(strona, kadr);
  const xy = cel ? strona.srodek(cel) : { x: strona.szer / 2, y: kadr[1] / fit / 2 };
  const f = (t) => {
    const u = clamp((t - od) / (koniec - od));
    return ogranicz({ ...xy, zoom: fit * lerp(z, na, u) }, strona, kadr);      // liniowo: kamera nie staje przed cięciem
  };
  return oznacz(f, 'najazd', od, koniec, fit * Math.max(z, na));
}

// Lupa nad celem: wyskakuje w 0,3 s, powiększa 1,5–2×, ma najwyżej 1/3 wysokości kadru, tło przygasa do 0,8.
// f(t, kamera) → {widac, skala, tlo, ramka {x, y, w, h} w kadrze, zrodlo {x, y, w, h} na stronie, zoom treści}.
export function lupa({ strona, cel, od = 0, do: koniec, powiekszenie = LICZBY.lupa, kadr = kadrDomyslny(),
                       margines = 12, tlo = LICZBY.lupaTlo } = {}) {
  if (koniec === undefined) throw new Error('lupa: podaj „do”');
  const c = strona.cel(cel).napis ?? strona.cel(cel);          // napis węższy od bloku: lupa na samym tekście
  const zrodlo = { x: c.x - margines, y: c.y - margines, w: c.w + 2 * margines, h: c.h + 2 * margines };
  const f = (t, kam) => {
    const wej = clamp((t - od) / LICZBY.lupaWejscie), wyj = clamp((t - (koniec - 0.2)) / 0.2);
    const widac = t >= od && t < koniec;
    const zoomKam = kam?.zoom ?? dopasuj(strona, kadr);
    let zoom = zoomKam * powiekszenie;
    const maxH = kadr[1] * LICZBY.lupaWys;
    if (zrodlo.h * zoom > maxH) zoom = maxH / zrodlo.h;                       // lupa nie większa niż 1/3 kadru
    if (zrodlo.w * zoom > kadr[0] * 0.8) zoom = kadr[0] * 0.8 / zrodlo.w;
    const w = zrodlo.w * zoom, h = zrodlo.h * zoom;
    const s = wKadrze(kam ?? { x: strona.szer / 2, y: c.y, zoom: zoomKam }, { x: c.x + c.w / 2, y: c.y + c.h / 2 }, kadr);
    const nad = s.y - h / 2 - c.h * zoomKam / 2 - 24 > 0;                      // lupa nad celem, a gdy brak miejsca: pod
    const y = clamp(nad ? s.y - c.h * zoomKam / 2 - 24 - h : s.y + c.h * zoomKam / 2 + 24, 16, kadr[1] - h - 16);
    const x = clamp(s.x - w / 2, 16, kadr[0] - w - 16);
    const pop = bezier(0.34, 1.56, 0.64, 1)(wej) * (1 - wyj);
    return { widac, skala: widac ? 0.6 + 0.4 * pop : 0, krycie: widac ? Math.min(1, wej * 2) * (1 - wyj) : 0,
             tlo: widac ? lerp(1, tlo, Math.min(wej, 1 - wyj)) : 1, ramka: { x, y, w, h }, zrodlo, zoom };
  };
  return oznacz(f, 'lupa', od, koniec, null, { powiekszenie });
}

// Uderzenie (crash zoom) w cel: 6 klatek do 2,3× na kamerze bazowej (funkcja t → stan albo stan); najwyżej 2 na film.
export function uderzenie({ strona, cel, od = 0, baza, przyblizenie = LICZBY.uderzenie, fps = globalThis.__FPS ?? 30,
                            kadr = kadrDomyslny() } = {}) {
  const czas = LICZBY.uderzenieKlatki / fps;
  const xy = strona.srodek(cel);
  const e = bezier(0.2, 0.9, 0.3, 1);
  const f = (t) => {
    const b = typeof baza === 'function' ? baza(t) : (baza ?? { x: strona.szer / 2, y: xy.y, zoom: dopasuj(strona, kadr) });
    const u = e(clamp((t - od) / czas));
    return ogranicz({ ...b, x: lerp(b.x, xy.x, u), y: lerp(b.y, xy.y, u), zoom: b.zoom * lerp(1, przyblizenie, u) }, strona, kadr);
  };
  return oznacz(f, 'uderzenie', od, od + czas, dopasuj(strona, kadr) * przyblizenie);
}

// Zakreślacz pod tekstem celu (ramka `napis`, gdy blok jest szerszy): pas przeciąga się w 0,4–0,8 s. f(t) → {u, pas {x, y, w, h}}.
export function zakreslacz({ strona, cel, od = 0, czas = LICZBY.zakreslacz } = {}) {
  const c = strona.cel(cel).napis ?? strona.cel(cel);
  const f = (t) => {
    const u = gladko(clamp((t - od) / czas));
    return { u, pas: { x: c.x - 6, y: c.y + c.h * 0.12, w: (c.w + 12) * u, h: c.h * 0.82 } };
  };
  return oznacz(f, 'zakreslacz', od, od + czas, null);
}

// ---------------------------------------------------------------- plan ruchów
// Kontrola zasad przed renderem: jeden ruch kamery naraz, lupa nigdy w czasie przewijania, zakreślacz nie w trakcie
// jazdy, najwyżej 2 uderzenia na film, przybliżenie nie większe niż rozdzielczość zrzutu (dpr).
// Zwraca {bledy, ostrzezenia}; wymagajPlanu() rzuca przy błędach (render staje z powodem).
export function sprawdzPlan(ruchy, { strona } = {}) {
  const bledy = [], ostrzezenia = [];
  const kamery = ruchy.filter(r => ['przewijanie', 'wycieczka', 'najazd', 'uderzenie'].includes(r.typ));
  const naraz = (a, b) => a.od < b.do && b.od < a.do;
  const opis = (r) => `${r.typ} ${r.od.toFixed(2)}–${r.do.toFixed(2)} s`;
  for (let i = 0; i < kamery.length; i++) {
    for (let j = i + 1; j < kamery.length; j++) {
      const a = kamery[i], b = kamery[j];
      if (naraz(a, b) && !(a.typ === 'uderzenie' || b.typ === 'uderzenie')) bledy.push(`dwa ruchy kamery naraz: ${opis(a)} i ${opis(b)}`);
    }
  }
  for (const l of ruchy.filter(r => r.typ === 'lupa')) {
    for (const p of ruchy.filter(r => r.typ === 'przewijanie' || r.typ === 'wycieczka')) {
      const jazda = !(p.chwile || []).some(c => l.od >= c.od && l.do <= c.do);
      if (naraz(l, p) && jazda) bledy.push(`lupa w czasie ruchu kamery: ${opis(l)} przy ${opis(p)} (lupa tylko na postoju)`);
    }
  }
  for (const z of ruchy.filter(r => r.typ === 'zakreslacz')) {
    for (const p of ruchy.filter(r => r.typ === 'przewijanie' || r.typ === 'wycieczka')) {
      if (naraz(z, p) && !(p.chwile || []).some(c => z.od >= c.od && z.do <= c.do)) ostrzezenia.push(`zakreślacz w czasie ruchu kamery: ${opis(z)} (rób go na postoju)`);
    }
  }
  const uderzenia = ruchy.filter(r => r.typ === 'uderzenie').length;
  if (uderzenia > LICZBY.uderzeniaMax) ostrzezenia.push(`uderzeń ${uderzenia}, najwyżej ${LICZBY.uderzeniaMax} na film`);
  if (strona?.dpr) {
    for (const r of ruchy) {
      if (r.maxZoom && r.typ !== 'uderzenie' && r.maxZoom > strona.dpr * 1.02) {
        ostrzezenia.push(`${opis(r)}: przybliżenie ${r.maxZoom.toFixed(2)}× przekracza rozdzielczość zrzutu (${strona.dpr}×): obraz się rozmyje`);
      }
    }
  }
  return { bledy, ostrzezenia };
}

export function wymagajPlanu(ruchy, opcje = {}) {
  const w = sprawdzPlan(ruchy, opcje);
  for (const o of w.ostrzezenia) console.warn('strona.js:', o);
  if (w.bledy.length) throw new Error('strona.js: ' + w.bledy.join('; '));
  return w;
}

// ---------------------------------------------------------------- DOM
// Scena strony: kafle jeden pod drugim w pikselach CSS strony (obraz 2× daje ostrość przy przybliżeniu).
// `pusta: true` = pusta plansza tam, gdzie jest (wycinki lądują na swoje miejsca). Zwraca {el, gotowe: Promise}.
export function zbudujStrone(kontener, strona, { pusta = false } = {}) {
  const el = document.createElement('div');
  el.className = 'jarvo-strona';
  el.style.cssText = `position:absolute;left:0;top:0;width:${strona.szer}px;height:${strona.wys}px;transform-origin:0 0;`;
  const zamiana = Object.fromEntries((pusta ? strona.pusta : []).map(k => [k.y, k.plik]));
  const obrazy = strona.kafle.map(k => {
    const img = new Image();
    img.decoding = 'sync';
    img.src = strona.katalog + (zamiana[k.y] ?? k.plik);
    img.style.cssText = `position:absolute;left:0;top:${k.y}px;width:${strona.szer}px;height:${k.h}px;`;
    el.appendChild(img);
    return img;
  });
  kontener.appendChild(el);
  const gotowe = Promise.all(obrazy.map(i => i.decode().catch(() => { throw new Error(`brak kafla ${i.src}`); })));
  return { el, gotowe };
}

// Kamera na scenie: CSS `zoom` (ostre wycinki i tekst DOM, nie `transform: scale`) i przesunięcie w jednostkach
// po przybliżeniu: punkt (x, y) trafia na środek kadru.
export function kamera(el, stan, kadr = kadrDomyslny()) {
  el.style.zoom = String(stan.zoom);
  el.style.transform = `translate(${kadr[0] / 2 / stan.zoom - stan.x}px, ${kadr[1] / 2 / stan.zoom - stan.y}px)`;
}

// Wycinek celu jako <img> w swoim miejscu na stronie (do lądowania w slocie); `katalog` jak w stronaZUkladu.
export function wycinek(scena, strona, id) {
  const c = strona.cel(id);
  if (!c.wycinek) throw new Error(`cel „${id}” nie ma wycinka (assety.py --film wycina logo, h1, przyciski, karty, ceny, formularze i --wycinki)`);
  const img = new Image();
  img.src = strona.katalog + c.wycinek;
  img.style.cssText = `position:absolute;left:${c.x}px;top:${c.y}px;width:${c.w}px;height:${c.h}px;will-change:transform;`;
  scena.appendChild(img);
  return img;
}

// Lupa w DOM: okno z tą samą stroną w większym przybliżeniu nad celem. Tło przygaszasz sam: filter brightness(stan.tlo).
// const L = lupaDOM(kontener, strona); … L.aktualizuj(lupa1(t, stanKamery));
export function lupaDOM(kontener, strona, { promien = 18, ramka = '3px solid #fff' } = {}) {
  const el = document.createElement('div');
  el.className = 'jarvo-lupa';
  el.style.cssText = `position:absolute;overflow:hidden;border-radius:${promien}px;border:${ramka};`
    + 'box-shadow:0 18px 50px rgba(0,0,0,.35);transform-origin:50% 100%;opacity:0;pointer-events:none;';
  const { el: wnetrze, gotowe } = zbudujStrone(el, strona);
  kontener.appendChild(el);
  const aktualizuj = (s) => {
    el.style.opacity = String(s.krycie);
    if (!s.widac) return;
    Object.assign(el.style, { left: `${s.ramka.x}px`, top: `${s.ramka.y}px`, width: `${s.ramka.w}px`, height: `${s.ramka.h}px`,
                              transform: `scale(${s.skala})` });
    wnetrze.style.zoom = String(s.zoom);
    wnetrze.style.transform = `translate(${-s.zrodlo.x}px, ${-s.zrodlo.y}px)`;
  };
  return { el, gotowe, aktualizuj };
}
