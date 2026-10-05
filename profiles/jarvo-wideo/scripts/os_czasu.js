// Oś czasu lektora dla animacji HTML (kontrakt `--preset jarvo`): chwile po nazwie zamiast sekund wpisanych w kod.
// `film.py narracja narracja.txt` zapisuje os_czasu.json (zdania, ujęcia, rozdziały, napisy, chwile); strona czyta go
// obok siebie. Nowe nagranie lektora = nowy plik, a animacja idzie za nim bez zmian w kodzie.
//
//   import { wczytajOs } from '/_lib/jarvo/os_czasu.js';
//   const O = await wczytajOs();                 // os_czasu.json obok strony (albo podana ścieżka)
//   window.__DUR = O.dlugosc;
//   O.bit('u3.z2')          → s: początek 2. zdania ujęcia 3 (też 'u3', 'u3.mowa', 'u3.koniec', 'r2', własne {nazwa})
//   O.bit('licznik', -0.1)  → s: chwila z przesunięciem (wejście elementu 0,1 s przed słowem)
//   O.postep(t, 'u3', 'u3.koniec')  → 0–1 między dwiema chwilami (jak seg)
//   O.ujecie(t)             → ujęcie trwające w chwili t ({id, nr, start, koniec, mowa_start, mowa_koniec, zdania})
//   O.zdanie(t), O.napis(t) → zdanie / grupa napisów w chwili t (albo null)
//
// Nieznana nazwa chwili rzuca błąd: render i pomiar go zgłoszą (po zmianie tekstu lektora nic nie przesuwa się po cichu).

export function osZDanych(dane) {
  if (!dane || typeof dane.dlugosc !== 'number' || !dane.chwile) {
    throw new Error('os_czasu.json bez dlugosc i chwile: zrób go od nowa (film.py narracja)');
  }
  const chwile = dane.chwile;
  const uzyte = new Set();
  const bit = (nazwa, przesuniecie = 0) => {
    if (!(nazwa in chwile)) {
      const podobne = Object.keys(chwile).filter((k) => k.split('.')[0] === String(nazwa).split('.')[0]).slice(0, 6);
      throw new Error(`nieznana chwila „${nazwa}” w os_czasu.json` + (podobne.length ? ` (są np.: ${podobne.join(', ')})` : ''));
    }
    uzyte.add(nazwa);
    return chwile[nazwa] + przesuniecie;
  };
  const clamp = (x) => Math.min(1, Math.max(0, x));
  const w = (lista, t) => lista.find((x) => t >= x.start && t < x.koniec) || null;
  return {
    dane,
    dlugosc: dane.dlugosc,
    chwile,
    ujecia: dane.ujecia || [],
    zdania: dane.zdania || [],
    rozdzialy: dane.rozdzialy || [],
    napisy: dane.napisy || [],
    bit,
    postep: (t, a, b) => {
      const ta = typeof a === 'number' ? a : bit(a);
      const tb = typeof b === 'number' ? b : bit(b);
      return tb > ta ? clamp((t - ta) / (tb - ta)) : (t >= tb ? 1 : 0);
    },
    ujecie: (t) => w(dane.ujecia || [], t) || (dane.ujecia || []).at(-1) || null,
    zdanie: (t) => w(dane.zdania || [], t),
    napis: (t) => w(dane.napisy || [], t),
    rozdzial: (t) => w(dane.rozdzialy || [], t) || (dane.rozdzialy || []).at(-1) || null,
    uzyte: () => [...uzyte],
  };
}

export async function wczytajOs(sciezka = 'os_czasu.json') {
  const r = await fetch(sciezka);
  if (!r.ok) throw new Error(`brak ${sciezka} obok strony (HTTP ${r.status}): film.py narracja … --os <katalog strony>/os_czasu.json`);
  const O = osZDanych(await r.json());
  window.__os = O;
  return O;
}
