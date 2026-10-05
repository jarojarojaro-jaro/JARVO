# Ujęcia z kart shotcraft w naszym HTML (`/_lib/jarvo/ujecia.js`)

Czytasz, gdy karta z `inspiracje.py ujecia` ma znak „u nas: ujecia.js …”: zamiast stawiać projekt Remotion,
robisz to ujęcie w animacji HTML (`rodzaje-filmu/references/kontrakt-html.md`). Skąd: karty i dema video-shotcraft
(Vincent Wei, Apache-2.0). Z nich są czasy w klatkach, krzywe, przestrzelenia i limity; kod jest nasz, bez Reacta.

Każda funkcja to czysta funkcja czasu `t` w sekundach (klatka karty `KL` = 1/30 s): zwraca liczby (pozycja, skala,
krycie, rozmycie, cień), a styl elementu ustawiasz sam w `window.__seek(t)`. Ten sam `t` = ta sama klatka, w każdej
przeglądarce renderu. Wygląd (kolory, kroje, rogi) bierzesz z `marka.css` (`strona-filmowana.md` §2).

```js
import * as U from '/_lib/jarvo/ujecia.js';
import * as S from '/_lib/jarvo/strona.js';
// 6 kart oferty wlatuje z talii na swoje miejsca w zrzucie strony (pusta plansza pod spodem)
const karty = ['karta-1', 'karta-2', 'karta-3'].map(id => ({ el: S.wycinek(scena, st, id), c: st.cel(id) }));
window.__seek = (t) => karty.forEach(({ el, c }, k) => {
  const r = U.rozdanie(t, k, { od: 1 });                     // talia w punkcie (960, 1400) strony
  const x = 960 + (c.x - 960) * r.p, y = 1400 + (c.y - 1400) * r.p;
  el.style.transform = `translate(${x - c.x}px, ${y - c.y - r.z}px) scale(${r.skala})`;
  el.style.boxShadow = U.cien(r.uniesienie); el.style.opacity = t >= r.start ? 1 : 0;
});
```

| Karta shotcraft | Funkcje | Liczby z karty | Kiedy |
|---|---|---|---|
| `deck-deal-flyin` | `rozdanie(t, k)`, `startRozdania(k)`, `zapowiedzRozdania(t, od)` | odstęp 4 klatki maleje o 0,16 do 0,2; lot 8 klatek łukiem 90 px, skala 1,06; osiadanie 4 klatki z przestrzeleniem; docisk 0,996 → 1; zapowiedź 12 klatek (talia −45 px, górna karta −30 px); pełna siatka stoi 0,5 s | oferta, cennik, galeria: dużo kart naraz |
| `list-stack-press` | `stos(t, i)`, `docisk(t, n)`, `podswietlenie(t, i)`, `licznikZdarzen(t, chwile)` | karta co 12 klatek z 600 px, lot 22 klatki z przestrzeleniem, ±2° na zmianę, skala 1,06 → 1; każde lądowanie wciska stos o 6 px (8 klatek); pasek podświetlenia 3 klatki po lądowaniu, 7 klatek do 40% szerokości; licznik krok 8 klatek | lista zamówień, powiadomień, zadań: „przybywa” |
| `row-embed` | `wiersz(t, i)` | wiersz co 9 klatek, 12 klatek z −120 px i przechylenia 16°; skala 1,06 → 0,995 → 1; łatka znika 2 klatki po lądowaniu; szew akcentu 2 px: 5 klatek od środka, gaśnie w 8 | nowy wiersz w tabeli, wpis w zrzucie |
| `type-and-filter` | `pisanie(t, tekst)`, `filtr(t, i)`, `doSlotu(t)`, `klik(t, od)` | 3 klatki na znak, kursor miga co 8; oddech 11 klatek; karty spoza wyniku gasną co 0,4 klatki w 5 klatek, opadając 8 px; wynik do slotu 10 klatek, uniesienie 18 px; klik: dwa kręgi 14 → 54 / 78 px, drugi 3 klatki później | wyszukiwarka, filtr, „znajdź swoje” |
| `paper-title-card` | `tytulPapier(t, slowa, {akcent})` | słowo co 4 klatki, 9 klatek: skala 1,28 → 1, rozmycie 7 → 0 px; jedno słowo-akcent (kursywa, kolor akcentu); kreska 18 klatek po ostatnim słowie; karta 50–55 klatek, gaśnie w 8 | spokojny tytuł rozdziału, marka premium |
| `odometer-digit-roll` | `licznikBebnowy(t, wartosc)` | cyfra od lewej co 7 klatek (pierwsza po 20), 16 klatek hamowania z przestrzeleniem o pół wiersza, 6 klatek powrotu; duchy ±0,5 wiersza tylko w ruchu; przecinek, % i spacja stoją; puls 8 klatek (skala 1,035); potem ≥ 45 klatek spokoju; najwyżej 6 cyfr (`uwaga`) | jedna liczba z `fakty.json` |
| `beat-cut-moves` | `przyspieszenie(t)`, `flesz(t)` | A: cięcia 0/49/65/77/85/91/95 klatka, błysk 1 klatka, potem 35 klatek z najazdem do 1,06; B: trzy błyski (30/52/70) coraz bliżej (1 / 2,3 / 4), biel 0,95 → 0 w 4 klatki, kadr osiada z 1,03 i −16 px w 6 klatek, 60 klatek spokoju | szczyt filmu na bicie; **raz na film, jeden z dwóch** |
| `speed-ramp-freeze` | `przemapuj(t, klucze)`, `sprawdzTempo(klucze)`, `kolko(t, od, dlugosc)`, `ZWOLNIENIE` | tempo szybko/wolno ≥ 10×, wolne okno ≥ 40 klatek, stop-klatka ≥ 45 klatek, najwyżej 2 na 30 s; kółko markerem 8 klatek, znika w 8 | jeden moment, który widz ma zauważyć |
| `depth-layer-moves` | `paralaksa(droga)`, `WARSTWY`, `dollyZoom(t)` | warstwy 0,35 / 0,7 / 1,4 drogi (tło rozmycie 2 px, nasycenie 0,92, krycie 0,85; przód rozmycie 3 px), najwyżej 4; dolly: tło 1 → 2,25 i rozmycie do 3,5 px, cień bohatera 12 → 28 px | głębia w płaskim kadrze; **dolly raz na film** |
| `outro-group-photo-launch` | `grupaElement(t, i)`, `grupaLitera(t, i)`, `grupaKamera(t)` | element co 3 klatki (od 4.), 12 klatek z prawdziwym przestrzeleniem, z 360–500 px, obrót ×2 do swojego (±5°), skala 1,12 → 1, poświata 6 klatek; litery znaku od 42. klatki co 1,8, reszta przygasa (−12% krycia, −8% nasycenia); kamera 4° → 0 i 1,06 → 1 przez 40 klatek, potem +0,035; tło rozmywa się do 14 px | finał: wszystko, co było w filmie, na jednym zdjęciu, potem znak |
| `spotlight-hero-card` | `reflektor(t, {cel, start})`, `kartaBohatera(t, {od})` | światło przez 4 przystanki w 44 klatki, promień 620 → 420 → 360, puls +6%, winieta 0,16 → 0,42; karta wstaje 10 klatek, unosi się 54 (±4 px, okres 40), siada 18 z dociskiem 0,997; obwódka dwa okrążenia (14 klatek, potem 20 przy 0,62) | otwarcie z jednym bohaterem: produkt, karta, plan cenowy |

- **Wycinek ląduje w swoim slocie.** `p` (droga 0 → 1) prowadzi element z talii, z dołu albo z boku do jego `x, y`
  z `uklad.json`; po lądowaniu stoi dokładnie na pikselach zrzutu (`strona-filmowana.md` §3).
- **Cień mówi o wysokości:** `U.cien(uniesienie)` daje szeroki, miękki cień w powietrzu i krótki na ziemi
  (0 2 px 8 px → 0 32 px 64 px). Bez cienia element w locie wygląda na naklejony.
- **Mocne ujęcia raz:** `U.sprawdzUjecia(['flesz', 'dollyZoom', 'stop', …], { dlugosc })` przed renderem, uwagi
  do RAPORT. Raz na film: `przyspieszenie` albo `flesz` (nigdy oba), `dollyZoom`, `reflektor`, `grupa`;
  stop-klatki najwyżej 2 na 30 s.
- Liczby z kart są sprawdzone na 30 kl./s; przy 60 kl./s funkcje działają tak samo (liczą w sekundach).
  Zmieniasz je tylko z powodem w BRIEF (np. wolniej dla charakteru „spokojny”: `ruch-i-kompozycja.md` §1).
- Karta bez znaku „u nas” albo z ruchem, którego tu nie ma: robisz go w Remotion przez shotcraft
  (`narzedzia.md`, sekcja video-shotcraft) albo sam w HTML, z liczbami z karty i dema.
