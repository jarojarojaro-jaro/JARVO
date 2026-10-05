# Strona klienta w filmie: zrzut, marka, wycinki, kamera

Czytasz przy filmie, który pokazuje stronę albo aplikację klienta (`rodzaje-filmu`: promo-produktu, explainer
z dowodem ze strony). Strona jest filmowana z własnego zrzutu, a nie nagrywana z przeglądarki ani rysowana od nowa.
Skąd: video-shotcraft (Apache-2.0: zrzut 2×, wycinki, pusta plansza, wygląd z kolorów i krojów produktu, lądowanie
w slocie) i video-talkcraft (licencja niekomercyjna: wzięte tylko pomysły i liczby, opisane po naszemu).

## 1. Zrzut (`assety.py --film`)
```bash
python3 $HERMES_HOME/scripts/assety.py <URL> --film --out out/wideo/src/<nazwa>/assets [--podstrony /cennik] [--wycinki "cta=.btn-primary"]
```
`--out` w katalogu animacji: `html_wideo.py` serwuje tylko katalog strony (`out/wideo/src/<nazwa>/`).
| Plik w `assets/` | Co |
|---|---|
| `film/<strona>-desktop-<k>.png` | cała strona 1920 px w 2× (3840 px szerokości), kafle do 12 000 px wysokości |
| `film/<strona>-telefon-<k>.png` | to samo na telefonie: 390 px w 3× (1170 px szerokości) |
| `film/<strona>-<widok>-<id>.png` | wycinek z przezroczystym tłem: logo, h1, 3 przyciski, 6 kart, 4 ceny, 2 formularze, własne |
| `film/<strona>-<widok>-pusta-<k>.png` | kafel z ukrytymi wyciętymi elementami (tylko kafle, na których coś wycięto) |
| `film/uklad.json` | `strony.<strona>.<widok>`: `szer`, `dpr`, `wys`, `kafle` [{plik, y, h}], `pusta`, `cele`, `przygotowanie` |
| `marka.json`, `marka.css` | role kolorów, krój, rogi, cień, podpowiedź charakteru ruchu (niżej) |

- **`cele`:** `{id, typ, tekst, x, y, w, h}` w pikselach CSS całej strony (piksel obrazu = × `dpr`). Typy: `logo`,
  `nawigacja`, `naglowek` (z `poziom`), `przycisk`, `cena`, `karta`, `formularz`, `obraz`, `sekcja`, `wlasny`.
  Cel z polem `wycinek` ma swój plik; `brak` = własny selektor nic nie znalazł.
- **Przygotowanie strony** robi skrypt: paski przypięte (fixed, sticky) wracają na miejsce, baner cookie znika (zgody
  nie klikamy), przewinięcie do końca i z powrotem wczytuje leniwe obrazy, fonty i animacje są gotowe. W wyniku
  `przygotowanie` = ile ukrył i ile odpiął. Baner wciąż widoczny na kaflu → kadrujesz poza nim.
- Strona dłuższa niż `--wysokosc-max` (12 000 px) jest ucięta (`uciete` w wyniku). Film i tak pokazuje górę i kilka sekcji.
- Dane osobowe na zrzucie (nazwiska klientów, e-maile, numery zamówień) zastępujesz zmyślonymi albo kadrujesz poza nie.

## 2. Wygląd z marki
- `marka.css` dołączasz w animacji (`<link rel="stylesheet" href="assets/marka.css">`) i bierzesz z niej wszystko:
  kolory `--marka-strona`, `-powierzchnia`, `-pole`, `-tekst`, `-przygaszony`, `-akcent`, `-akcent-tekst`,
  `-obramowanie`; kroje `--marka-font-naglowek`, `-tekst`, `-przycisk` z rozmiarami `--marka-h1-px`…; rogi
  `--marka-promien-przycisk`, `-karta`, `-pole`; `--marka-cien-karty`.
- Każdy tytuł, podpis, liczba, przejście i drobina używa tych wartości. Odstępstwo (np. ciemne tło finału) opisujesz
  w BRIEF jednym zdaniem. Rola w `zgadniete` jest policzona z innych, nie zmierzona: porównaj ją ze zrzutem.
- Akcent to kolor głównego przycisku. Marka z dwoma akcentami: drugi z `paleta` w `assety.json`.
- Kroju strony może nie być w `/_lib/kroje/kroje.css`: bierzesz najbliższy tego samego typu (szeryfowy, bezszeryfowy,
  geometryczny) i piszesz to w RAPORT. Rozmiary strony są na ekran 1440 px; na kadr 1080 p mnożysz je ×1,5–2.
- `charakter` to podpowiedź charakteru ruchu z wyglądu (`rodzaje-filmu/references/ruch-i-kompozycja.md` §1);
  BRIEF i słowa właściciela wygrywają.

## 3. Wycinek ląduje w slocie
- Ujęcie „element wlatuje na stronę”: tłem jest pusta plansza, wycinek leci i ląduje dokładnie w swoim `x, y`
  (z przestrzeleniem charakteru), a w chwili lądowania zostaje w miejscu (te same piksele co na pełnym kaflu,
  bez skoku). Nigdy nie zostaje w powietrzu obok strony.
- Wycinki w 2× są ostre do przybliżenia 2×. Większe przybliżenie tylko na chwilę uderzenia.
- `S.wycinek(scena, strona, 'karta-4')` kładzie wycinek jako `<img>` w jego miejscu na scenie; ruch dokładasz sam
  (`ladowanie` z `ruch.js`), a scenę budujesz z pustej planszy: `zbudujStrone(kadr, strona, {pusta: true})`.

## 4. Kamera po stronie (`/_lib/jarvo/strona.js`)
Strona się filmuje, nie wkleja: kamera przewija, jedzie od elementu do elementu, pokazuje lupę albo zakreśla tekst.
Każdy ruch to funkcja czasu `t → {x, y, zoom}`: punkt strony (piksele CSS) na środku kadru i przybliżenie (piksele
kadru na piksel strony; `dopasuj` = cała szerokość strony w kadrze). Kamera nigdy nie pokazuje nic poza stroną.
```js
import * as S from '/_lib/jarvo/strona.js';
const st = S.stronaZUkladu(await (await fetch('assets/film/uklad.json')).json(), { katalog: 'assets/film/' });
const { el: scena, gotowe } = S.zbudujStrone(document.getElementById('kadr'), st);   // kafle jeden pod drugim
const jazda = S.przewijanie({ strona: st, od: 0.5, przystanki: ['karta-4', 'formularz-1'] });
const lupa = S.lupa({ strona: st, cel: 'cena-1', od: jazda.chwile[0].od + 0.1, do: jazda.chwile[0].do });
const L = S.lupaDOM(document.getElementById('kadr'), st);
S.wymagajPlanu([jazda, lupa], { strona: st });            // błąd planu zatrzymuje render z powodem
window.__seek = (t) => {
  const kam = jazda(t); S.kamera(scena, kam);             // CSS zoom + przesunięcie: ostre wycinki i tekst DOM
  const l = lupa(t, kam); scena.style.filter = `brightness(${l.tlo})`; L.aktualizuj(l);
};
await gotowe; await L.gotowe; window.__ready = true;
```
| Ruch | Funkcja | Liczby (domyślne) |
|---|---|---|
| przewijanie z postojami | `przewijanie({przystanki, start, tempo, postoj})` | ~10% wysokości strony na sekundę (najwyżej 0,6 widoku/s), rozpęd 0,6 s, hamowanie 1,4 s, postój 1,5 s; cel na środku kadru; `chwile` = postoje |
| wycieczka po elementach | `wycieczka({punkty, start: 'calosc', nachylenie})` | najwyżej 4 punkty, przybliżenie 1,3–1,5 (domyślnie 1,4), postój 1 s, przejazd 1,15 s krzywą `0.16, 1, 0.3, 1`; nachylenie 14° / −20° w przejeździe |
| wolny najazd na ujęcie | `najazd({od, do, z: 1, na: 1.05})` | 100% → 104–106% przez całe ujęcie, liniowo (kamera nie staje przed cięciem) |
| lupa | `lupa({cel, od, do, powiekszenie})` + `lupaDOM` | 1,5–2× (1,75), najwyżej 1/3 wysokości kadru, wyskakuje w 0,3 s, tło przygasa do 0,8 |
| uderzenie (crash zoom) | `uderzenie({cel, od, baza})` | 6 klatek do 2,3×, najwyżej 2 na film, na mocnym bicie |
| zakreślacz | `zakreslacz({cel, od, czas})` | pas pod tekstem w 0,4–0,8 s (0,6), kolor akcentu marki z przezroczystością |

- **Jeden ruch kamery naraz** (przewijanie, wycieczka, najazd). Lupa i zakreślacz tylko na postoju (`chwile`
  przewijania i wycieczki), nigdy w trakcie jazdy. `sprawdzPlan` liczy to przed renderem: błąd = dwa ruchy kamery
  naraz albo lupa w ruchu; ostrzeżenie = zakreślacz w ruchu, więcej niż 2 uderzenia, przybliżenie większe niż
  rozdzielczość zrzutu (`dpr`).
- `wKadrze(stan, punkt)` zamienia punkt strony na piksele kadru: tam stawiasz podpis, kursor albo ramkę nad stroną.
- Strona telefonu (`widok: 'telefon'`) w kadrze 9:16 wypełnia szerokość (390 px → 1080 px kadru, zrzut 3×).
- Ujęcie strony ma jednego bohatera: przystanek przewijania albo punkt wycieczki to ten element, o którym mówi
  lektor albo napis (zasady: `rodzaje-filmu/references/ruch-i-kompozycja.md`).
