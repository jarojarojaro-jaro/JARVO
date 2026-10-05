# Strona klienta w filmie: zrzut, marka, wycinki

Czytasz przy filmie, który pokazuje stronę albo aplikację klienta (`rodzaje-filmu`: promo-produktu, explainer
z dowodem ze strony). Strona jest filmowana z własnego zrzutu, a nie nagrywana z przeglądarki ani rysowana od nowa.
Skąd: video-shotcraft (Apache-2.0: zrzut 2×, wycinki, pusta plansza, wygląd z kolorów i krojów produktu, lądowanie
w slocie) i video-talkcraft (licencja niekomercyjna: wzięte tylko pomysły i liczby, opisane po naszemu).

## 1. Zrzut (`assety.py --film`)
```bash
python3 $HERMES_HOME/scripts/assety.py <URL> --film [--podstrony /cennik] [--wycinki "cta=.btn-primary"]
```
| Plik w `out/wideo/src/assets/` | Co |
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
- `marka.css` dołączasz w animacji (`<link rel="stylesheet" href="../assets/marka.css">`) i bierzesz z niej wszystko:
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
